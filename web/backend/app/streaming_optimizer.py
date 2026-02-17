"""Streaming LLM optimization for real-time reasoning display.

Builds the same prompt as _real_optimize() but uses pydantic-ai's
run_stream + stream_text to yield text chunks as they arrive.
"""
from __future__ import annotations

import json
import re
import sys
import logging
from pathlib import Path
from typing import Any, AsyncIterator

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

logger = logging.getLogger(__name__)


def _create_agent(llm_config: Any, system_prompt: str) -> Any:
    """Create a pydantic-ai Agent, handling MaaS models (GLM-5 etc) with custom publisher/region."""
    import os
    from pydantic_ai import Agent

    from .settings import settings_manager, MAAS_MODEL_CONFIG

    model_name = llm_config.model_name
    maas_meta = MAAS_MODEL_CONFIG.get(model_name)

    if maas_meta and llm_config.provider == "google-vertex":
        # MaaS model on Vertex AI — needs custom publisher and/or region
        try:
            from pydantic_ai.providers.google_vertex import GoogleVertexProvider
            provider = GoogleVertexProvider(
                model_publisher=maas_meta.get("publisher", "google"),
                region=maas_meta.get("region", os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-north1")),
            )
            return Agent(model_name, provider=provider, system_prompt=system_prompt)  # type: ignore[arg-type]
        except Exception as e:
            logger.warning("Failed to create MaaS provider for %s: %s, falling back", model_name, e)

    return Agent(llm_config.full_model_string, system_prompt=system_prompt)


async def stream_optimize(
    agent_id: str,
    current_policy: dict[str, Any],
    last_day: Any,  # GameDay
    all_days: list[Any],
    raw_yaml: dict[str, Any],
    constraint_preset: str = "simple",
) -> AsyncIterator[dict[str, Any]]:
    """Stream LLM optimization, yielding events as they happen.

    Yields dicts with:
      {"type": "chunk", "text": "..."}     — text delta
      {"type": "result", "data": {...}}    — final parsed result (same shape as _real_optimize return)
      {"type": "error", "message": "..."}  — on failure
    """
    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer
    from payment_simulator.ai_cash_mgmt.prompts.event_filter import (
        filter_events_for_agent,
        format_filtered_output,
    )
    from payment_simulator.ai_cash_mgmt.prompts.context_types import (
        SingleAgentIterationRecord,
    )
    from payment_simulator.ai_cash_mgmt.prompts.user_prompt_builder import UserPromptBuilder
    from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import build_single_agent_context
    from payment_simulator.llm.config import LLMConfig
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    try:
        from pydantic_ai import Agent
    except ImportError as e:
        yield {"type": "error", "message": f"pydantic_ai required: {e}"}
        return

    # Build constraints from preset
    from .constraint_presets import build_constraints
    constraints = build_constraints(constraint_preset, raw_yaml)

    optimizer = PolicyOptimizer(constraints=constraints, max_retries=2)

    # Get LLM config from platform settings (admin-switchable)
    from .settings import settings_manager
    llm_config = settings_manager.get_llm_config()

    # Build system prompt
    cost_rates = raw_yaml.get("cost_rates", {})
    system_prompt = optimizer.get_system_prompt(cost_rates=cost_rates)

    # Build iteration history
    current_fraction = current_policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
    agent_cost = last_day.per_agent_costs.get(agent_id, 0)
    agent_costs = last_day.costs.get(agent_id, {})
    cost_breakdown = {
        "delay_cost": agent_costs.get("delay_cost", 0),
        "overdraft_cost": agent_costs.get("liquidity_cost", 0),
        "deadline_penalty": agent_costs.get("penalty_cost", 0),
        "eod_penalty": 0,
    }

    iteration_history: list[SingleAgentIterationRecord] = []
    best_cost = float("inf")
    for i, day in enumerate(all_days):
        day_agent_cost = day.per_agent_costs.get(agent_id, 0)
        day_policy = day.policies.get(agent_id, current_policy)
        is_best = day_agent_cost < best_cost
        if is_best:
            best_cost = day_agent_cost
        iteration_history.append(SingleAgentIterationRecord(
            iteration=i + 1,
            metrics={"total_cost_mean": day_agent_cost},
            policy=day_policy,
            was_accepted=True,
            is_best_so_far=is_best,
        ))

    # Filter events for agent isolation
    filtered_events = filter_events_for_agent(agent_id, last_day.events)
    simulation_trace = None
    if filtered_events:
        simulation_trace = format_filtered_output(
            agent_id, filtered_events, include_tick_headers=True
        )

    current_metrics = {
        "total_cost_mean": agent_cost,
        "iteration": len(all_days),
    }

    # Build the prompt (same as PolicyOptimizer.optimize does internally)
    prompt = build_single_agent_context(
        current_iteration=len(all_days),
        current_policy=current_policy,
        current_metrics=current_metrics,
        iteration_history=iteration_history,
        simulation_trace=simulation_trace,
        sample_seed=last_day.seed,
        sample_cost=agent_cost,
        mean_cost=agent_cost,
        cost_std=0,
        cost_breakdown=cost_breakdown,
        cost_rates=cost_rates,
        agent_id=agent_id,
    )

    # Add policy section
    user_prompt_builder = UserPromptBuilder(agent_id, current_policy)
    policy_section = user_prompt_builder._build_policy_section()
    prompt += f"\n\n{policy_section}"

    # Build final user prompt (same as ExperimentLLMClient._build_user_prompt)
    user_prompt = f"""{prompt}

Current policy:
{json.dumps(current_policy, indent=2)}

Generate an improved policy that reduces total cost.
Output ONLY the JSON policy, no explanation."""

    # Create pydantic-ai agent
    agent = _create_agent(llm_config, system_prompt)
    model_settings = llm_config.to_model_settings()

    # Fix: google-vertex provider needs thinking_config in model_settings
    if llm_config.provider == "google-vertex" and llm_config.thinking_config:
        model_settings["google_thinking_config"] = llm_config.thinking_config

    yield {"type": "model_info", "model": llm_config.model, "provider": llm_config.provider}

    # Stream the response
    full_text = ""
    try:
        async with agent.run_stream(user_prompt, model_settings=model_settings) as stream_result:
            async for chunk in stream_result.stream_text(delta=True):
                full_text += chunk
                yield {"type": "chunk", "text": chunk}
    except Exception as e:
        logger.error("Streaming LLM call failed for %s: %s", agent_id, e)
        yield {"type": "error", "message": str(e)}
        return

    # Parse the accumulated response into a policy
    try:
        new_policy = _parse_policy_response(full_text)
        new_fraction = new_policy.get("parameters", {}).get("initial_liquidity_fraction")

        reasoning_text = (
            f"LLM proposed: fraction {current_fraction:.3f} → {new_fraction:.3f}. "
            f"Cost was {agent_cost:,}. "
            f"Breakdown: delay={cost_breakdown['delay_cost']:,}, "
            f"penalty={cost_breakdown['deadline_penalty']:,}, "
            f"opportunity={max(0, agent_cost - cost_breakdown['delay_cost'] - cost_breakdown['deadline_penalty']):,}."
        )

        yield {
            "type": "result",
            "data": {
                "new_policy": new_policy,
                "reasoning": reasoning_text,
                "old_fraction": current_fraction,
                "new_fraction": new_fraction,
                "accepted": True,
                "mock": False,
                "raw_response": full_text,
            },
        }
    except Exception as e:
        logger.warning("Failed to parse streamed response for %s: %s", agent_id, e)
        yield {
            "type": "result",
            "data": {
                "new_policy": None,
                "reasoning": f"LLM optimization failed for {agent_id}: {e}. Keeping fraction at {current_fraction:.3f}.",
                "old_fraction": current_fraction,
                "new_fraction": None,
                "accepted": False,
                "mock": False,
                "raw_response": full_text,
            },
        }


def _parse_policy_response(text: str) -> dict[str, Any]:
    """Parse LLM response text into a policy dict. Same logic as ExperimentLLMClient.parse_policy."""
    text = text.strip()

    # Strip markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

    # Try to find JSON object
    # Sometimes the LLM wraps the JSON in explanation text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]

    policy = json.loads(text)

    # Ensure required fields
    if "version" not in policy:
        policy["version"] = "2.0"
    if "policy_id" not in policy:
        import uuid
        policy["policy_id"] = f"llm_stream_{uuid.uuid4().hex[:8]}"

    return policy
