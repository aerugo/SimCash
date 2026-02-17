"""Multi-day policy optimization game."""
from __future__ import annotations

import sys
import json
import copy
import random
import logging
from pathlib import Path
from typing import Any

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from payment_simulator._core import Orchestrator  # type: ignore
from payment_simulator.config.schemas import SimulationConfig  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_POLICY: dict[str, Any] = {
    "version": "2.0",
    "policy_id": "default_fifo",
    "parameters": {"initial_liquidity_fraction": 1.0},
    "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
    "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
}


class GameDay:
    """Results from one day of simulation."""

    def __init__(self, day_num: int, seed: int, policies: dict[str, dict],
                 costs: dict[str, dict], events: list[dict],
                 balance_history: dict[str, list], total_cost: int,
                 per_agent_costs: dict[str, int]):
        self.day_num = day_num
        self.seed = seed
        self.policies = policies
        self.costs = costs
        self.events = events
        self.balance_history = balance_history
        self.total_cost = total_cost
        self.per_agent_costs = per_agent_costs

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day_num,
            "seed": self.seed,
            "policies": {
                aid: {"initial_liquidity_fraction": p["parameters"].get("initial_liquidity_fraction", 1.0)}
                for aid, p in self.policies.items()
            },
            "costs": self.costs,
            "events": self.events,
            "balance_history": self.balance_history,
            "total_cost": self.total_cost,
            "per_agent_costs": self.per_agent_costs,
        }


class Game:
    """Multi-day policy optimization game."""

    def __init__(self, game_id: str, raw_yaml: dict, use_llm: bool = False,
                 mock_reasoning: bool = True, max_days: int = 10):
        self.game_id = game_id
        self.raw_yaml = raw_yaml
        self.use_llm = use_llm
        self.mock_reasoning = mock_reasoning
        self.max_days = max_days
        self.days: list[GameDay] = []
        self.agent_ids: list[str] = [a["id"] for a in raw_yaml.get("agents", [])]
        self.policies: dict[str, dict] = {aid: copy.deepcopy(DEFAULT_POLICY) for aid in self.agent_ids}
        self.reasoning_history: dict[str, list[dict]] = {aid: [] for aid in self.agent_ids}
        self._base_seed = raw_yaml.get("simulation", {}).get("rng_seed", 42)

    @property
    def current_day(self) -> int:
        return len(self.days)

    @property
    def is_complete(self) -> bool:
        return self.current_day >= self.max_days

    def run_day(self) -> GameDay:
        """Run one day of simulation with current policies."""
        day_num = self.current_day
        seed = self._base_seed + day_num

        scenario = copy.deepcopy(self.raw_yaml)
        for agent_cfg in scenario.get("agents", []):
            agent_id = agent_cfg.get("id")
            if agent_id in self.policies:
                policy = self.policies[agent_id]
                fraction = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
                agent_cfg["liquidity_allocation_fraction"] = fraction
                agent_cfg["policy"] = {"type": "InlineJson", "json_string": json.dumps(policy)}

        scenario.setdefault("simulation", {})["rng_seed"] = seed

        sim_config = SimulationConfig.from_dict(scenario)
        ffi_config = sim_config.to_ffi_dict()
        orch = Orchestrator.new(ffi_config)

        ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]
        all_events: list[dict] = []
        balance_history: dict[str, list] = {aid: [] for aid in self.agent_ids}

        for tick in range(ticks):
            orch.tick()
            events = orch.get_tick_events(tick)
            all_events.extend([dict(e) for e in events])
            for aid in self.agent_ids:
                balance_history[aid].append(orch.get_agent_balance(aid) or 0)

        costs: dict[str, dict] = {}
        per_agent_costs: dict[str, int] = {}
        total_cost = 0
        for aid in self.agent_ids:
            ac = orch.get_agent_accumulated_costs(aid)
            agent_cost = {
                "liquidity_cost": ac.get("liquidity_cost", 0),
                "delay_cost": ac.get("delay_cost", 0),
                "penalty_cost": ac.get("penalty_cost", 0) + ac.get("deadline_penalty_cost", 0),
                "total": ac.get("total", 0),
            }
            costs[aid] = agent_cost
            per_agent_costs[aid] = int(ac.get("total", 0))
            total_cost += per_agent_costs[aid]

        day = GameDay(
            day_num=day_num,
            seed=seed,
            policies=copy.deepcopy(self.policies),
            costs=costs,
            events=all_events,
            balance_history=balance_history,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
        )
        self.days.append(day)
        return day

    async def optimize_policies(self) -> dict[str, dict]:
        """Run optimization step between days. Returns reasoning per agent."""
        if not self.days:
            return {}

        last_day = self.days[-1]
        reasoning: dict[str, dict] = {}

        for aid in self.agent_ids:
            if self.mock_reasoning:
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
            else:
                try:
                    result = await _real_optimize(aid, self.policies[aid], last_day,
                                                  self.days, self.raw_yaml)
                except Exception as e:
                    logger.warning("Real LLM optimization failed for %s, falling back to mock: %s", aid, e)
                    result = _mock_optimize(aid, self.policies[aid], last_day, self.days)

            if result.get("new_policy"):
                self.policies[aid] = result["new_policy"]

            reasoning[aid] = result
            self.reasoning_history[aid].append(result)

        return reasoning

    def get_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_day": self.current_day,
            "max_days": self.max_days,
            "is_complete": self.is_complete,
            "use_llm": self.use_llm,
            "agent_ids": self.agent_ids,
            "current_policies": {
                aid: {"initial_liquidity_fraction": p["parameters"].get("initial_liquidity_fraction", 1.0)}
                for aid, p in self.policies.items()
            },
            "days": [d.to_dict() for d in self.days],
            "cost_history": {
                aid: [d.per_agent_costs.get(aid, 0) for d in self.days]
                for aid in self.agent_ids
            },
            "fraction_history": {
                aid: [
                    d.policies.get(aid, {}).get("parameters", {}).get("initial_liquidity_fraction", 1.0)
                    for d in self.days
                ]
                for aid in self.agent_ids
            },
            "reasoning_history": self.reasoning_history,
        }


def _mock_optimize(agent_id: str, current_policy: dict, last_day: GameDay,
                   all_days: list[GameDay]) -> dict[str, Any]:
    """Generate believable mock policy changes with game-theoretic reasoning."""
    current_fraction = current_policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
    agent_cost = last_day.costs.get(agent_id, {})
    liq_cost = agent_cost.get("liquidity_cost", 0)
    delay_cost = agent_cost.get("delay_cost", 0)
    penalty_cost = agent_cost.get("penalty_cost", 0)
    total = agent_cost.get("total", 0)

    # Decide direction
    if penalty_cost > 0 and current_fraction < 0.95:
        # Penalties mean we need more liquidity
        delta = random.uniform(0.05, 0.15)
        direction = "increase"
        reason = f"Deadline penalties ({penalty_cost:.0f}) detected — increasing liquidity to avoid future penalties."
    elif liq_cost > delay_cost and current_fraction > 0.15:
        # Liquidity cost dominates — reduce fraction
        delta = random.uniform(0.05, 0.12)
        direction = "decrease"
        reason = f"Liquidity cost ({liq_cost:.0f}) exceeds delay cost ({delay_cost:.0f}) — reducing allocation to cut borrowing expense."
    elif delay_cost > liq_cost * 1.5 and current_fraction < 0.95:
        delta = random.uniform(0.03, 0.10)
        direction = "increase"
        reason = f"Delay cost ({delay_cost:.0f}) significantly exceeds liquidity cost ({liq_cost:.0f}) — increasing allocation to speed up settlements."
    else:
        # Small random perturbation toward equilibrium (~0.3-0.5)
        target = 0.35 + random.uniform(-0.05, 0.05)
        delta = abs(current_fraction - target) * random.uniform(0.1, 0.3)
        direction = "decrease" if current_fraction > target else "increase"
        reason = f"Costs roughly balanced (total={total:.0f}). Fine-tuning toward estimated equilibrium."

    if direction == "increase":
        new_fraction = min(1.0, current_fraction + delta)
    else:
        new_fraction = max(0.05, current_fraction - delta)

    new_fraction = round(new_fraction, 3)

    # Build new policy
    new_policy = copy.deepcopy(current_policy)
    new_policy["parameters"]["initial_liquidity_fraction"] = new_fraction
    new_policy["policy_id"] = f"opt_day{len(all_days)}_{agent_id}"

    # Build reasoning text
    day_num = len(all_days)
    trend = ""
    if day_num >= 2:
        prev_cost = all_days[-2].per_agent_costs.get(agent_id, 0)
        curr_cost = last_day.per_agent_costs.get(agent_id, 0)
        if curr_cost < prev_cost:
            trend = f" Cost improved from {prev_cost:,} to {curr_cost:,} ({(prev_cost-curr_cost)/max(prev_cost,1)*100:.1f}% reduction)."
        else:
            trend = f" Cost worsened from {prev_cost:,} to {curr_cost:,}."

    reasoning = (
        f"Day {day_num} analysis for {agent_id}: {reason}{trend} "
        f"Adjusting fraction {current_fraction:.3f} → {new_fraction:.3f}. "
        f"Strategy: {direction} liquidity allocation to minimize expected total cost "
        f"given opponent's likely response."
    )

    return {
        "new_policy": new_policy,
        "reasoning": reasoning,
        "old_fraction": current_fraction,
        "new_fraction": new_fraction,
        "accepted": True,
        "mock": True,
    }


async def _real_optimize(agent_id: str, current_policy: dict, last_day: GameDay,
                         all_days: list[GameDay], raw_yaml: dict) -> dict[str, Any]:
    """Use the real LLM optimization infrastructure."""
    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer
    from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import ScenarioConstraints
    from payment_simulator.experiments.runner.llm_client import ExperimentLLMClient
    from payment_simulator.llm import LLMConfig
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    constraints = ScenarioConstraints(
        allowed_parameters=["initial_liquidity_fraction"],
        allowed_fields=["system_tick_in_day", "balance", "ticks_to_deadline"],
        allowed_actions={"payment_tree": ["Release", "Hold"], "bank_tree": ["NoAction"]},
    )

    optimizer = PolicyOptimizer(constraints=constraints, max_retries=2)

    llm_config = LLMConfig(
        model="openai:gpt-5.2",
        reasoning_effort="high",
        reasoning_summary="detailed",
    )
    client = ExperimentLLMClient(llm_config)

    current_fraction = current_policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)

    result = await optimizer.optimize(
        agent_id=agent_id,
        current_policy=current_policy,
        current_iteration=len(all_days),
        current_metrics={"total_cost_mean": last_day.per_agent_costs.get(agent_id, 0)},
        llm_client=client,
        llm_model="gpt-5.2",
        current_cost=last_day.per_agent_costs.get(agent_id, 0),
        events=last_day.events,
    )

    new_fraction = None
    if result.was_accepted and result.new_policy:
        new_fraction = result.new_policy.get("parameters", {}).get("initial_liquidity_fraction")

    return {
        "new_policy": result.new_policy if result.was_accepted else None,
        "reasoning": (
            f"LLM proposed: fraction {current_fraction:.3f} → "
            f"{new_fraction:.3f if new_fraction else 'rejected'}. "
            f"{'Accepted' if result.was_accepted else 'Rejected'}."
        ),
        "old_fraction": current_fraction,
        "new_fraction": new_fraction,
        "accepted": result.was_accepted,
        "mock": False,
    }
