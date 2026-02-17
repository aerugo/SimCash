"""Policy-based simulation runner for web sandbox.

Wraps the existing ai_cash_mgmt optimization system.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add SimCash api to path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from payment_simulator._core import Orchestrator  # type: ignore[import-untyped]
from payment_simulator.config.schemas import SimulationConfig  # type: ignore[import-untyped]


def make_default_policy(agent_id: str, fraction: float = 1.0) -> dict[str, Any]:
    """Create a default FIFO policy."""
    return {
        "version": "2.0",
        "policy_id": f"default_{agent_id}",
        "parameters": {"initial_liquidity_fraction": fraction},
        "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
        "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
    }


def run_with_policy(
    raw_yaml: dict[str, Any],
    policies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Run a full simulation with specific policies for agents.

    Returns total costs and per-agent costs.
    """
    sc = SimulationConfig(**raw_yaml)
    ffi_config = sc.to_ffi_dict()

    # Apply policies: set initial_liquidity_fraction on agent configs
    for ac in ffi_config["agent_configs"]:
        aid = ac["id"]
        if aid in policies:
            policy = policies[aid]
            frac = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
            ac["liquidity_allocation_fraction"] = frac

    orch = Orchestrator.new(ffi_config)
    total_ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]

    # Run all ticks
    for _ in range(total_ticks):
        orch.tick()

    # Collect results
    per_agent_costs: dict[str, dict[str, Any]] = {}
    total_cost = 0
    for ac in ffi_config["agent_configs"]:
        aid = ac["id"]
        costs = orch.get_agent_accumulated_costs(aid)
        agent_total = int(costs.get("total_cost", costs.get("total", 0)))
        per_agent_costs[aid] = {
            "liquidity_cost": costs.get("liquidity_cost", 0),
            "delay_cost": costs.get("delay_cost", 0),
            "penalty_cost": costs.get("penalty_cost", 0) + costs.get("deadline_penalty_cost", 0),
            "total": agent_total,
        }
        total_cost += agent_total

    return {"total_cost": total_cost, "per_agent_costs": per_agent_costs}


def build_simulation_trace(tick_history: list[dict[str, Any]]) -> str:
    """Build a human-readable trace from tick history."""
    lines = []
    for td in tick_history:
        tick = td.get("tick", "?")
        lines.append(f"--- Tick {tick} ---")
        for aid, adata in td.get("agents", {}).items():
            c = adata.get("costs", {})
            lines.append(
                f"  {aid}: balance={adata.get('balance',0)}, "
                f"queue={adata.get('queue1_size',0)}, "
                f"total_cost={c.get('total',0)}"
            )
        for ev in td.get("events", [])[:10]:
            lines.append(f"  [{ev.get('event_type','?')}]")
    return "\n".join(lines)


async def optimize_policy_with_llm(
    raw_yaml: dict[str, Any],
    current_policies: dict[str, dict[str, Any]],
    agent_id: str,
    simulation_trace: str,
    current_cost: int,
    iteration: int,
) -> dict[str, Any]:
    """Use real LLM to optimize policy.

    Returns: {"policy": {...}, "reasoning": "...", "model": "..."}
    """
    try:
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer
        from payment_simulator.experiments.runner.llm_client import ExperimentLLMClient
        from payment_simulator.llm.config import LLMConfig
    except ImportError as e:
        return {
            "policy": None,
            "reasoning": f"Import error: {e}. Using mock instead.",
            "model": "error",
        }

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["OPENAI_API_KEY"] = api_key
                    break

    if not api_key:
        return {
            "policy": None,
            "reasoning": "No OPENAI_API_KEY found.",
            "model": "error",
        }

    model = "openai:gpt-4o"

    try:
        llm_config = LLMConfig(model=model)
        client = ExperimentLLMClient(llm_config)

        current_policy = current_policies.get(agent_id, make_default_policy(agent_id))

        prompt = f"""You are optimizing a payment policy for agent {agent_id} in a liquidity simulation.

Current iteration: {iteration}
Current total cost: {current_cost}
Current policy: {json.dumps(current_policy, indent=2)}

Simulation trace:
{simulation_trace[:5000]}

Propose an improved policy. Return ONLY a JSON object with this structure:
{{
  "version": "2.0",
  "policy_id": "web_opt_{iteration}",
  "parameters": {{
    "initial_liquidity_fraction": <float 0.05-0.95>
  }},
  "bank_tree": {{"type": "action", "node_id": "bank_root", "action": "NoAction"}},
  "payment_tree": <a decision tree with conditions or simple action>
}}

Think about what fraction of liquidity to allocate and whether to hold/release payments based on conditions like ticks_to_deadline."""

        result = await client.generate(prompt)
        text = result if isinstance(result, str) else str(result)

        # Extract JSON from response
        import re
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            policy = json.loads(json_match.group())
            reasoning = text[:json_match.start()] + text[json_match.end():]
            return {"policy": policy, "reasoning": reasoning.strip(), "model": model}
        else:
            return {"policy": None, "reasoning": f"No JSON found in: {text[:500]}", "model": model}

    except Exception as e:
        return {"policy": None, "reasoning": f"LLM error: {e}", "model": model}
