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
                 per_agent_costs: dict[str, int],
                 tick_events: list[list[dict]] | None = None):
        self.day_num = day_num
        self.seed = seed
        self.policies = policies
        self.costs = costs
        self.events = events
        self.balance_history = balance_history
        self.total_cost = total_cost
        self.per_agent_costs = per_agent_costs
        self.tick_events = tick_events or []  # tick_events[i] = events for tick i

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
            "num_ticks": len(self.tick_events),
        }


class Game:
    """Multi-day policy optimization game."""

    def __init__(self, game_id: str, raw_yaml: dict, use_llm: bool = False,
                 mock_reasoning: bool = True, max_days: int = 10,
                 num_eval_samples: int = 1):
        self.game_id = game_id
        self.raw_yaml = raw_yaml
        self.use_llm = use_llm
        self.mock_reasoning = mock_reasoning
        self.max_days = max_days
        self.num_eval_samples = num_eval_samples  # Bootstrap-lite: run N seeds, average costs
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

    def _run_single_sim(self, seed: int) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]]]:
        """Run one simulation with current policies at given seed.
        
        Returns (events, balance_history, costs, per_agent_costs, total_cost, tick_events).
        tick_events[i] = list of events for tick i (for replay).
        """
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
        tick_events: list[list[dict]] = []
        balance_history: dict[str, list] = {aid: [] for aid in self.agent_ids}

        for tick in range(ticks):
            orch.tick()
            events = orch.get_tick_events(tick)
            tick_event_list = [dict(e) for e in events]
            all_events.extend(tick_event_list)
            tick_events.append(tick_event_list)
            for aid in self.agent_ids:
                balance_history[aid].append(orch.get_agent_balance(aid) or 0)

        costs: dict[str, dict] = {}
        per_agent_costs: dict[str, int] = {}
        total_cost = 0
        for aid in self.agent_ids:
            ac = orch.get_agent_accumulated_costs(aid)
            agent_total = int(ac.get("total_cost", 0))
            delay = int(ac.get("delay_cost", 0))
            penalty = int(ac.get("deadline_penalty", 0))
            overdraft = int(ac.get("liquidity_cost", 0))
            collateral = int(ac.get("collateral_cost", 0))
            split = int(ac.get("split_friction_cost", 0))
            opportunity_cost = max(0, agent_total - delay - penalty - overdraft - collateral - split)
            costs[aid] = {
                "liquidity_cost": opportunity_cost,
                "delay_cost": delay,
                "penalty_cost": penalty,
                "total": agent_total,
            }
            per_agent_costs[aid] = agent_total
            total_cost += agent_total

        return all_events, balance_history, costs, per_agent_costs, total_cost, tick_events

    def run_day(self) -> GameDay:
        """Run one day of simulation with current policies.
        
        If num_eval_samples > 1, runs multiple seeds and averages costs
        for a more robust signal (bootstrap-lite). The representative run
        (first seed) provides events and balance history for display.
        """
        day_num = self.current_day
        seed = self._base_seed + day_num

        # Run the representative simulation (always shown in UI)
        all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self._run_single_sim(seed)

        # If multi-sample, run additional seeds and average costs
        if self.num_eval_samples > 1:
            all_per_agent: dict[str, list[int]] = {aid: [per_agent_costs[aid]] for aid in self.agent_ids}
            all_costs: dict[str, list[dict]] = {aid: [costs[aid]] for aid in self.agent_ids}
            
            for sample_idx in range(1, self.num_eval_samples):
                sample_seed = seed + sample_idx * 1000  # Spread seeds
                _, _, s_costs, s_per_agent, _, _ = self._run_single_sim(sample_seed)
                for aid in self.agent_ids:
                    all_per_agent[aid].append(s_per_agent[aid])
                    all_costs[aid].append(s_costs[aid])
            
            # Average costs across samples
            n = self.num_eval_samples
            total_cost = 0
            for aid in self.agent_ids:
                avg_total = sum(all_per_agent[aid]) // n
                avg_delay = sum(c["delay_cost"] for c in all_costs[aid]) // n
                avg_penalty = sum(c["penalty_cost"] for c in all_costs[aid]) // n
                avg_liq = sum(c["liquidity_cost"] for c in all_costs[aid]) // n
                costs[aid] = {
                    "liquidity_cost": avg_liq,
                    "delay_cost": avg_delay,
                    "penalty_cost": avg_penalty,
                    "total": avg_total,
                }
                per_agent_costs[aid] = avg_total
                total_cost += avg_total

        day = GameDay(
            day_num=day_num,
            seed=seed,
            policies=copy.deepcopy(self.policies),
            costs=costs,
            events=all_events,
            balance_history=balance_history,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            tick_events=tick_events,
        )
        self.days.append(day)
        return day

    async def optimize_policies_streaming(self, send_fn):
        """Run optimization with streaming text chunks.

        Args:
            send_fn: async callable(dict) to send WS messages.
                Called with optimization_start, optimization_chunk,
                optimization_complete messages.
        """
        from .bootstrap_eval import WebBootstrapEvaluator
        from .streaming_optimizer import stream_optimize

        if not self.days:
            return

        last_day = self.days[-1]
        evaluator = None
        if self.num_eval_samples > 1:
            evaluator = WebBootstrapEvaluator(
                num_samples=self.num_eval_samples,
                cv_threshold=0.5,
            )

        for aid in self.agent_ids:
            await send_fn({
                "type": "optimization_start",
                "day": last_day.day_num,
                "agent_id": aid,
            })

            if self.mock_reasoning:
                # Mock doesn't stream — just send result
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
                await send_fn({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })
            else:
                # Stream real LLM response
                result = None
                try:
                    async for event in stream_optimize(
                        aid, self.policies[aid], last_day, self.days, self.raw_yaml
                    ):
                        if event["type"] == "chunk":
                            await send_fn({
                                "type": "optimization_chunk",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "text": event["text"],
                            })
                        elif event["type"] == "result":
                            result = event["data"]
                        elif event["type"] == "error":
                            # Fall back to mock
                            result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
                            result["fallback_reason"] = event["message"]
                except Exception as e:
                    logger.warning("Streaming optimization failed for %s: %s", aid, e)
                    result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
                    result["fallback_reason"] = str(e)

                if result is None:
                    result = _mock_optimize(aid, self.policies[aid], last_day, self.days)

                # Bootstrap evaluation gate
                if evaluator and result.get("new_policy"):
                    other_policies = {
                        other_aid: self.policies[other_aid]
                        for other_aid in self.agent_ids if other_aid != aid
                    }
                    eval_result = evaluator.evaluate(
                        raw_yaml=self.raw_yaml,
                        agent_id=aid,
                        old_policy=self.policies[aid],
                        new_policy=result["new_policy"],
                        base_seed=self._base_seed + self.current_day * 100,
                        other_policies=other_policies,
                    )
                    result["bootstrap"] = {
                        "delta_sum": eval_result.delta_sum,
                        "mean_delta": eval_result.mean_delta,
                        "cv": eval_result.cv,
                        "ci_lower": eval_result.ci_lower,
                        "ci_upper": eval_result.ci_upper,
                        "num_samples": eval_result.num_samples,
                        "old_mean_cost": eval_result.old_mean_cost,
                        "new_mean_cost": eval_result.new_mean_cost,
                        "rejection_reason": eval_result.rejection_reason,
                    }
                    if not eval_result.accepted:
                        result["accepted"] = False
                        result["rejection_reason"] = eval_result.rejection_reason
                        result["reasoning"] += f" [REJECTED: {eval_result.rejection_reason}]"
                        result["new_policy"] = None
                        result["new_fraction"] = None

                await send_fn({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })

            # Apply policy if accepted
            if result and result.get("new_policy"):
                self.policies[aid] = result["new_policy"]

            if result:
                self.reasoning_history[aid].append(result)

    async def optimize_policies(self) -> dict[str, dict]:
        """Run optimization step between days. Returns reasoning per agent.
        
        When num_eval_samples > 1, uses WebBootstrapEvaluator for paired
        comparison (accept only if statistically significant improvement).
        When num_eval_samples == 1, always accepts (temporal mode).
        """
        from .bootstrap_eval import WebBootstrapEvaluator

        if not self.days:
            return {}

        last_day = self.days[-1]
        reasoning: dict[str, dict] = {}

        evaluator = None
        if self.num_eval_samples > 1:
            evaluator = WebBootstrapEvaluator(
                num_samples=self.num_eval_samples,
                cv_threshold=0.5,
            )

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

            # Bootstrap evaluation gate: only accept if statistically better
            if evaluator and result.get("new_policy"):
                other_policies = {
                    other_aid: self.policies[other_aid]
                    for other_aid in self.agent_ids if other_aid != aid
                }
                eval_result = evaluator.evaluate(
                    raw_yaml=self.raw_yaml,
                    agent_id=aid,
                    old_policy=self.policies[aid],
                    new_policy=result["new_policy"],
                    base_seed=self._base_seed + self.current_day * 100,
                    other_policies=other_policies,
                )
                result["bootstrap"] = {
                    "delta_sum": eval_result.delta_sum,
                    "mean_delta": eval_result.mean_delta,
                    "cv": eval_result.cv,
                    "ci_lower": eval_result.ci_lower,
                    "ci_upper": eval_result.ci_upper,
                    "num_samples": eval_result.num_samples,
                    "old_mean_cost": eval_result.old_mean_cost,
                    "new_mean_cost": eval_result.new_mean_cost,
                    "rejection_reason": eval_result.rejection_reason,
                }
                if not eval_result.accepted:
                    result["accepted"] = False
                    result["rejection_reason"] = eval_result.rejection_reason
                    result["reasoning"] += f" [REJECTED: {eval_result.rejection_reason}]"
                    result["new_policy"] = None  # Don't apply rejected policy
                    result["new_fraction"] = None

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
            "num_eval_samples": self.num_eval_samples,
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
    delay_cost = agent_cost.get("delay_cost", 0)
    penalty_cost = agent_cost.get("penalty_cost", 0)
    total = agent_cost.get("total", 0)
    # Compute opportunity cost: total - delay - penalty = liquidity opportunity cost
    opportunity_cost = max(0, total - delay_cost - penalty_cost)

    # Decide direction based on cost gradient
    if penalty_cost > 0:
        # Penalties mean we MUST increase — payments are failing at EOD
        delta = random.uniform(0.05, 0.15)
        direction = "increase"
        reason = f"Deadline penalties ({penalty_cost:,}) detected — critical: must increase liquidity to avoid payment failures."
    elif delay_cost > 0:
        # Delays mean we're close to the edge — increase slightly
        # But if opportunity cost is way bigger, we might still decrease
        if opportunity_cost > delay_cost * 3:
            delta = random.uniform(0.02, 0.08)
            direction = "decrease"
            reason = f"Delay costs ({delay_cost:,}) present but opportunity cost ({opportunity_cost:,}) dominates — cautiously reducing."
        else:
            delta = random.uniform(0.02, 0.06)
            direction = "increase"
            reason = f"Delay costs ({delay_cost:,}) indicate insufficient liquidity — increasing allocation."
    elif opportunity_cost > 0 and current_fraction > 0.05:
        # No delays, no penalties — pure opportunity cost, aggressively reduce
        # The bigger the fraction, the bigger the jump
        if current_fraction > 0.5:
            delta = current_fraction * random.uniform(0.3, 0.5)  # Big jumps when far from optimum
        elif current_fraction > 0.2:
            delta = current_fraction * random.uniform(0.15, 0.3)
        else:
            delta = current_fraction * random.uniform(0.05, 0.15)
        direction = "decrease"
        reason = f"Zero delays/penalties — opportunity cost ({opportunity_cost:,}) is pure waste. Aggressively reducing allocation."
    else:
        # At very low fraction with no cost info — tiny perturbation
        delta = random.uniform(0.01, 0.03)
        direction = random.choice(["increase", "decrease"])
        reason = f"Near optimal range. Small exploration step."

    if direction == "increase":
        new_fraction = min(1.0, current_fraction + delta)
    else:
        new_fraction = max(0.03, current_fraction - delta)

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
    """Use the real LLM optimization infrastructure.

    Reuses the existing PolicyOptimizer + ExperimentLLMClient from the experiment
    runner. Builds proper context with agent-isolated events, cost breakdown, and
    iteration history. Always accepts new policies (temporal mode — the cost landscape
    shifts as counterparties change).
    """
    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer
    from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
        ScenarioConstraints,
        ParameterSpec,
    )
    from payment_simulator.ai_cash_mgmt.prompts.event_filter import (
        filter_events_for_agent,
        format_filtered_output,
    )
    from payment_simulator.ai_cash_mgmt.prompts.context_types import (
        SingleAgentIterationRecord,
    )
    from payment_simulator.experiments.runner.llm_client import ExperimentLLMClient
    from payment_simulator.llm.config import LLMConfig
    from dotenv import load_dotenv
    import os

    load_dotenv(Path(__file__).resolve().parents[3] / ".env")

    # Build constraints matching exp2 config
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec(
                name="initial_liquidity_fraction",
                param_type="float",
                min_value=0.0,
                max_value=1.0,
                description="Fraction of liquidity_pool to allocate at simulation start.",
            ),
        ],
        allowed_fields=["system_tick_in_day", "balance", "amount", "remaining_amount", "ticks_to_deadline"],
        allowed_actions={"payment_tree": ["Release", "Hold"], "bank_tree": ["NoAction"]},
        lsm_enabled=False,
    )

    optimizer = PolicyOptimizer(constraints=constraints, max_retries=2)

    llm_config = LLMConfig(
        model="openai:gpt-5.2",
        reasoning_effort="high",
        reasoning_summary="detailed",
    )
    client = ExperimentLLMClient(llm_config)

    # Build dynamic system prompt with cost rates from scenario
    cost_rates = raw_yaml.get("cost_rates", {})
    dynamic_prompt = optimizer.get_system_prompt(cost_rates=cost_rates)
    client.set_system_prompt(dynamic_prompt)

    current_fraction = current_policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
    agent_cost = last_day.per_agent_costs.get(agent_id, 0)

    # Build cost breakdown from last day
    agent_costs = last_day.costs.get(agent_id, {})
    cost_breakdown = {
        "delay_cost": agent_costs.get("delay_cost", 0),
        "overdraft_cost": agent_costs.get("liquidity_cost", 0),
        "deadline_penalty": agent_costs.get("penalty_cost", 0),
        "eod_penalty": 0,
    }

    # Build iteration history for LLM context (agent sees only own history)
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
            was_accepted=True,  # Temporal mode: always accepted
            is_best_so_far=is_best,
        ))

    # Filter events for agent isolation (agent sees ONLY their own events)
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

    result = await optimizer.optimize(
        agent_id=agent_id,
        current_policy=current_policy,
        current_iteration=len(all_days),
        current_metrics=current_metrics,
        llm_client=client,
        llm_model="gpt-5.2",
        current_cost=float(agent_cost),
        iteration_history=iteration_history,
        events=last_day.events,  # Raw events for agent filtering
        simulation_trace=simulation_trace,
        sample_seed=last_day.seed,
        sample_cost=agent_cost,
        mean_cost=agent_cost,
        cost_std=0,
        cost_breakdown=cost_breakdown,
        cost_rates=cost_rates,
    )

    new_fraction = None
    new_policy = None
    reasoning_text = ""

    if result.was_accepted and result.new_policy:
        new_policy = result.new_policy
        new_fraction = new_policy.get("parameters", {}).get("initial_liquidity_fraction")
        reasoning_text = (
            f"LLM proposed: fraction {current_fraction:.3f} → {new_fraction:.3f}. Accepted. "
            f"Cost was {agent_cost:,}. "
            f"Breakdown: delay={cost_breakdown['delay_cost']:,}, "
            f"penalty={cost_breakdown['deadline_penalty']:,}, "
            f"opportunity={max(0, agent_cost - cost_breakdown['delay_cost'] - cost_breakdown['deadline_penalty']):,}."
        )
    else:
        # Even if rejected/failed, try to extract reasoning
        reasoning_text = (
            f"LLM optimization failed or rejected for {agent_id}. "
            f"Keeping fraction at {current_fraction:.3f}. Cost was {agent_cost:,}."
        )

    return {
        "new_policy": new_policy,
        "reasoning": reasoning_text,
        "old_fraction": current_fraction,
        "new_fraction": new_fraction,
        "accepted": result.was_accepted,
        "mock": False,
    }
