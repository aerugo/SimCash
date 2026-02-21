"""Streaming LLM optimization for real-time reasoning display.

Builds the same prompt as _real_optimize() but uses pydantic-ai's
run_stream + stream_text to yield text chunks as they arrive.

Supports retry with exponential backoff for transient errors (429, 503).
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import logging
import time as _time
from pathlib import Path
from typing import Any, AsyncIterator

# Timeout for a single LLM optimization call (seconds).
LLM_CALL_TIMEOUT_SECONDS = 600

# If no chunk arrives for this long, assume the connection is dead.
LLM_CHUNK_STALL_SECONDS = 90

# Retry settings for transient errors (429 RESOURCE_EXHAUSTED, 503, etc.)
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 60.0

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

logger = logging.getLogger(__name__)


def _is_retryable(error: Exception) -> bool:
    """Check if an error is transient and worth retrying."""
    # Timeouts are always retryable
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return True
    msg = str(error).lower()
    # 429 RESOURCE_EXHAUSTED, 503 UNAVAILABLE, connection resets, timeouts, cancel scope bugs
    return any(code in msg for code in ("429", "resource_exhausted", "503", "unavailable", "deadline_exceeded", "connection reset", "timeout", "cancel scope"))


def _create_agent(llm_config: Any, system_prompt: str) -> Any:
    """Create a pydantic-ai Agent, handling MaaS models (GLM-5 etc) with custom publisher/region."""
    from pydantic_ai import Agent

    from .settings import MAAS_MODEL_CONFIG

    model_name = llm_config.model_name
    maas_meta = MAAS_MODEL_CONFIG.get(model_name)

    if maas_meta and llm_config.provider == "google-vertex":
        # MaaS model on Vertex AI — needs custom publisher and/or region
        try:
            from pydantic_ai.providers.google import GoogleProvider
            from pydantic_ai.models.google import GoogleModel

            provider = GoogleProvider(
                location=maas_meta.get("region", "global"),
                vertexai=True,
            )
            # Use full publisher path: publishers/{pub}/models/{model}
            publisher = maas_meta.get("publisher", "google")
            full_model_name = f"publishers/{publisher}/models/{model_name}"
            model = GoogleModel(full_model_name, provider=provider)
            return Agent(model, system_prompt=system_prompt)
        except Exception as e:
            logger.warning("Failed to create MaaS provider for %s: %s, falling back", model_name, e)

    return Agent(llm_config.full_model_string, system_prompt=system_prompt)


def _build_optimization_prompt(
    agent_id: str,
    current_policy: dict[str, Any],
    last_day: Any,
    all_days: list[Any],
    raw_yaml: dict[str, Any],
    constraint_preset: str = "simple",
) -> tuple[str, str, dict[str, Any]]:
    """Build system prompt and user prompt for optimization.

    Returns (system_prompt, user_prompt, context) where context holds
    current_fraction, agent_cost, cost_breakdown for result formatting.
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
    from .constraint_presets import build_constraints

    constraints = build_constraints(constraint_preset, raw_yaml)
    optimizer = PolicyOptimizer(constraints=constraints, max_retries=2)

    cost_rates = raw_yaml.get("cost_rates", {})
    system_prompt = optimizer.get_system_prompt(cost_rates=cost_rates)

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

    user_prompt_builder = UserPromptBuilder(agent_id, current_policy)
    policy_section = user_prompt_builder._build_policy_section()
    prompt += f"\n\n{policy_section}"

    user_prompt = f"""{prompt}

Current policy:
{json.dumps(current_policy, indent=2)}

Generate an improved policy that reduces total cost.
Output ONLY the JSON policy, no explanation."""

    context = {
        "current_fraction": current_fraction,
        "agent_cost": agent_cost,
        "cost_breakdown": cost_breakdown,
    }
    return system_prompt, user_prompt, context


async def stream_optimize(
    agent_id: str,
    current_policy: dict[str, Any],
    last_day: Any,  # GameDay
    all_days: list[Any],
    raw_yaml: dict[str, Any],
    constraint_preset: str = "simple",
) -> AsyncIterator[dict[str, Any]]:
    """Stream LLM optimization with retry on transient errors.

    Yields dicts with:
      {"type": "chunk", "text": "..."}     — text delta
      {"type": "result", "data": {...}}    — final parsed result
      {"type": "error", "message": "..."}  — on failure (after all retries exhausted)
      {"type": "retry", "attempt": N, "delay": S, "reason": "..."} — retry notification
    """
    from payment_simulator.llm.config import LLMConfig
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    try:
        from pydantic_ai import Agent
    except ImportError as e:
        yield {"type": "error", "message": f"pydantic_ai required: {e}"}
        return

    # Build prompts (done once, not retried)
    system_prompt, user_prompt, ctx = _build_optimization_prompt(
        agent_id, current_policy, last_day, all_days, raw_yaml, constraint_preset,
    )
    current_fraction = ctx["current_fraction"]
    agent_cost = ctx["agent_cost"]
    cost_breakdown = ctx["cost_breakdown"]

    # Get LLM config
    from .settings import settings_manager
    llm_config = settings_manager.get_llm_config()

    agent = _create_agent(llm_config, system_prompt)
    model_settings = llm_config.to_model_settings()
    if llm_config.provider == "google-vertex" and llm_config.thinking_config:
        model_settings["google_thinking_config"] = llm_config.thinking_config

    yield {"type": "model_info", "model": llm_config.model, "provider": llm_config.provider}

    logger.warning(
        "LLM call for %s: system_prompt=%d chars, user_prompt=%d chars, model=%s",
        agent_id, len(system_prompt), len(user_prompt), llm_config.model,
    )

    # Retry loop with exponential backoff
    last_error: Exception | None = None
    usage_info: dict[str, Any] = {}
    thinking_text = ""
    for attempt in range(1, MAX_RETRIES + 1):
        full_text = ""
        thinking_text = ""
        usage_info = {}
        _llm_start = _time.monotonic()

        try:
            async with asyncio.timeout(LLM_CALL_TIMEOUT_SECONDS):
                async with agent.run_stream(user_prompt, model_settings=model_settings) as stream_result:
                    # Use stream_responses to capture thinking parts AND text parts
                    from pydantic_ai.messages import ThinkingPart, TextPart
                    prev_text_len = 0
                    async for response, _is_last in stream_result.stream_responses(debounce_by=None):
                        for part in response.parts:
                            if isinstance(part, ThinkingPart) and part.content:
                                # Accumulate thinking (may arrive in chunks)
                                if len(part.content) > len(thinking_text):
                                    thinking_text = part.content
                            elif isinstance(part, TextPart) and part.content:
                                # Yield text deltas
                                new_text = part.content
                                if len(new_text) > prev_text_len:
                                    delta = new_text[prev_text_len:]
                                    full_text = new_text
                                    prev_text_len = len(new_text)
                                    yield {"type": "chunk", "text": delta}

                    # Capture usage after stream completes
                    try:
                        u = stream_result.usage()
                        usage_info = {
                            "input_tokens": u.input_tokens or 0,
                            "output_tokens": u.output_tokens or 0,
                            "thinking_tokens": (u.details or {}).get("thoughts_tokens", 0),
                            "total_tokens": (u.input_tokens or 0) + (u.output_tokens or 0),
                        }
                    except Exception:
                        pass

            # Success — break out of retry loop
            _llm_elapsed = _time.monotonic() - _llm_start
            logger.warning(
                "LLM call for %s completed: %.1fs, response=%d chars, thinking=%d chars (attempt %d)",
                agent_id, _llm_elapsed, len(full_text), len(thinking_text), attempt,
            )
            break

        except Exception as e:
            _llm_elapsed = _time.monotonic() - _llm_start
            last_error = e

            if attempt < MAX_RETRIES and _is_retryable(e):
                backoff = min(INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
                reason = str(e)[:120]
                logger.warning(
                    "LLM call for %s failed (attempt %d/%d, %.1fs): %s — retrying in %.1fs",
                    agent_id, attempt, MAX_RETRIES, _llm_elapsed, reason, backoff,
                )
                yield {
                    "type": "retry",
                    "attempt": attempt,
                    "max_retries": MAX_RETRIES,
                    "delay": backoff,
                    "reason": reason,
                }
                await asyncio.sleep(backoff)
                # Clear any partial text from failed attempt for the UI
                if full_text:
                    yield {"type": "chunk", "text": f"\n\n[Retry {attempt + 1}/{MAX_RETRIES}]\n"}
                continue
            else:
                logger.error(
                    "LLM call for %s failed (attempt %d/%d, %.1fs): %s — no more retries",
                    agent_id, attempt, MAX_RETRIES, _llm_elapsed, e,
                )
                error_msg = _format_error_for_user(e, attempt)
                yield {"type": "error", "message": error_msg}
                return
    else:
        # All retries exhausted (shouldn't reach here due to return above, but safety net)
        error_msg = _format_error_for_user(last_error, MAX_RETRIES) if last_error else "Unknown error"
        yield {"type": "error", "message": error_msg}
        return

    # Parse and validate the policy, retrying with feedback on validation errors
    MAX_VALIDATION_RETRIES = 5
    validation_attempt = 0
    validation_user_prompt = user_prompt  # may get error feedback appended

    while True:
        validation_attempt += 1

        # Parse
        try:
            new_policy = _parse_policy_response(full_text)
        except Exception as e:
            logger.warning("Failed to parse streamed response for %s: %s", agent_id, e)
            if validation_attempt < MAX_VALIDATION_RETRIES:
                # Retry with parse error feedback
                error_feedback = (
                    f"\n\n--- VALIDATION ERROR (attempt {validation_attempt}/{MAX_VALIDATION_RETRIES}) ---\n"
                    f"Your previous response could not be parsed: {e}\n"
                    f"Please try again with a valid JSON policy block."
                )
                validation_user_prompt = user_prompt + error_feedback
                yield {"type": "chunk", "text": f"\n\n[Parse error, retrying {validation_attempt + 1}/{MAX_VALIDATION_RETRIES}]\n"}
                logger.warning("Parse error for %s (attempt %d/%d): %s — retrying", agent_id, validation_attempt, MAX_VALIDATION_RETRIES, e)

                # Re-run LLM with feedback
                full_text, thinking_text, usage_info, _llm_elapsed = await _rerun_llm(
                    agent, validation_user_prompt, model_settings, agent_id,
                )
                continue

            yield {
                "type": "result",
                "data": {
                    "new_policy": None,
                    "reasoning": f"LLM response could not be parsed for {agent_id}: {e}. Keeping fraction at {current_fraction:.3f}.",
                    "old_fraction": current_fraction,
                    "new_fraction": None,
                    "accepted": False,
                    "mock": False,
                    "raw_response": full_text,
                    "thinking": thinking_text,
                    "usage": usage_info,
                    "latency_seconds": round(_llm_elapsed, 1),
                    "model": llm_config.model,
                },
            }
            return

        # Validate against scenario constraints
        from .constraint_presets import build_constraints
        from payment_simulator.ai_cash_mgmt.constraints import ConstraintValidator
        constraints = build_constraints(constraint_preset, raw_yaml)
        validator = ConstraintValidator(constraints)
        validation_result = validator.validate(new_policy)

        if validation_result.is_valid:
            # Success — emit result
            new_fraction = new_policy.get("parameters", {}).get("initial_liquidity_fraction")
            reasoning_text = (
                f"LLM proposed: fraction {current_fraction:.3f} → {new_fraction:.3f}. "
                f"Cost was {agent_cost:,}. "
                f"Breakdown: delay={cost_breakdown['delay_cost']:,}, "
                f"penalty={cost_breakdown['deadline_penalty']:,}, "
                f"opportunity={max(0, agent_cost - cost_breakdown['delay_cost'] - cost_breakdown['deadline_penalty']):,}."
            )
            if validation_attempt > 1:
                reasoning_text += f" (validated after {validation_attempt} attempts)"

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
                    "thinking": thinking_text,
                    "usage": usage_info,
                    "latency_seconds": round(_llm_elapsed, 1),
                    "model": llm_config.model,
                    "validation_attempts": validation_attempt,
                },
            }
            return

        # Validation failed
        errors_str = "; ".join(validation_result.errors)
        logger.warning(
            "Policy validation failed for %s (attempt %d/%d): %s",
            agent_id, validation_attempt, MAX_VALIDATION_RETRIES, errors_str,
        )

        if validation_attempt >= MAX_VALIDATION_RETRIES:
            # Give up — keep old policy
            yield {
                "type": "result",
                "data": {
                    "new_policy": None,
                    "reasoning": f"Policy validation failed after {MAX_VALIDATION_RETRIES} attempts for {agent_id}: {errors_str}. Keeping fraction at {current_fraction:.3f}.",
                    "old_fraction": current_fraction,
                    "new_fraction": None,
                    "accepted": False,
                    "mock": False,
                    "raw_response": full_text,
                    "thinking": thinking_text,
                    "usage": usage_info,
                    "latency_seconds": round(_llm_elapsed, 1),
                    "model": llm_config.model,
                    "validation_attempts": validation_attempt,
                },
            }
            return

        # Retry with validation error feedback
        error_feedback = (
            f"\n\n--- VALIDATION ERROR (attempt {validation_attempt}/{MAX_VALIDATION_RETRIES}) ---\n"
            f"Your previous policy was invalid. Errors:\n{errors_str}\n\n"
            f"Please fix these issues and provide a corrected policy."
        )
        validation_user_prompt = user_prompt + error_feedback
        yield {"type": "chunk", "text": f"\n\n[Validation error: {errors_str} — retrying {validation_attempt + 1}/{MAX_VALIDATION_RETRIES}]\n"}

        # Re-run LLM with feedback
        full_text, thinking_text, usage_info, _llm_elapsed = await _rerun_llm(
            agent, validation_user_prompt, model_settings, agent_id,
        )


async def _rerun_llm(
    agent: Any,
    user_prompt: str,
    model_settings: dict,
    agent_id: str,
) -> tuple[str, str, dict, float]:
    """Re-run LLM call (non-streaming) for validation retries.

    Returns (full_text, thinking_text, usage_info, elapsed_seconds).
    """
    _start = _time.monotonic()
    try:
        async with asyncio.timeout(LLM_CALL_TIMEOUT_SECONDS):
            result = await agent.run(user_prompt, model_settings=model_settings)
        elapsed = _time.monotonic() - _start
        full_text = result.output if hasattr(result, 'output') else str(result.data)
        # Extract usage
        usage_info = {}
        if hasattr(result, 'usage') and result.usage:
            usage_info = {
                "input_tokens": getattr(result.usage, 'request_tokens', 0) or getattr(result.usage, 'requests', 0),
                "output_tokens": getattr(result.usage, 'response_tokens', 0) or getattr(result.usage, 'responses', 0),
            }
        logger.warning(
            "Validation retry LLM call for %s: %.1fs, %d chars",
            agent_id, elapsed, len(full_text),
        )
        return full_text, "", usage_info, elapsed
    except Exception as e:
        elapsed = _time.monotonic() - _start
        logger.warning("Validation retry LLM call failed for %s: %s", agent_id, e)
        raise


def _format_error_for_user(error: Exception | None, attempts: int) -> str:
    """Convert an exception to a human-readable error message."""
    if error is None:
        return "Optimization failed after all retries."

    msg = str(error)
    if "429" in msg or "resource_exhausted" in msg.lower():
        return f"Rate limited by the AI provider (tried {attempts}× with backoff). The model is temporarily overloaded — try again in a minute."
    if "503" in msg or "unavailable" in msg.lower():
        return f"AI service temporarily unavailable (tried {attempts}×). Please retry shortly."
    if "timeout" in msg.lower() or isinstance(error, asyncio.TimeoutError):
        return f"AI response timed out after {LLM_CALL_TIMEOUT_SECONDS}s (tried {attempts}×). The model may be overloaded."
    if "404" in msg or "not_found" in msg.lower():
        return f"Model not found or not accessible. Check the model configuration in Admin settings."
    # Generic fallback
    return f"Optimization failed: {msg[:200]}"


def _parse_policy_response(text: str) -> dict[str, Any]:
    """Parse LLM response text into a policy dict. Same logic as ExperimentLLMClient.parse_policy."""
    text = text.strip()

    # Strip markdown code blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            text = match.group(1).strip()

    # Try to find JSON object
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        text = text[brace_start : brace_end + 1]

    policy = json.loads(text)

    if "version" not in policy:
        policy["version"] = "2.0"
    if "policy_id" not in policy:
        import uuid
        policy["policy_id"] = f"llm_stream_{uuid.uuid4().hex[:8]}"

    return policy
