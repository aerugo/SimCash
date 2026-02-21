"""Multi-day policy optimization game."""
from __future__ import annotations

import sys
import json
import copy
import random
import logging
import concurrent.futures
from pathlib import Path
from typing import Any

import duckdb

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from payment_simulator._core import Orchestrator  # type: ignore
from payment_simulator.config.schemas import SimulationConfig  # type: ignore

logger = logging.getLogger(__name__)

DEFAULT_POLICY: dict[str, Any] = {
    "version": "2.0",
    "policy_id": "default_fifo",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
    "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
}


class GameDay:
    """Results from one day of simulation."""

    def __init__(self, day_num: int, seed: int, policies: dict[str, dict],
                 costs: dict[str, dict], events: list[dict],
                 balance_history: dict[str, list], total_cost: int,
                 per_agent_costs: dict[str, int],
                 tick_events: list[list[dict]] | None = None,
                 optimized: bool = False,
                 event_summary: dict[str, dict[str, int]] | None = None,
                 total_arrivals: int | None = None,
                 total_settled: int | None = None,
                 per_agent_cost_std: dict[str, int] | None = None):
        self.day_num = day_num
        self.seed = seed
        self.policies = policies
        self.costs = costs
        self.events = events
        self.balance_history = balance_history
        self.total_cost = total_cost
        self.per_agent_costs = per_agent_costs
        self.per_agent_cost_std = per_agent_cost_std or {}  # std dev from multi-seed eval
        self.tick_events = tick_events or []  # tick_events[i] = events for tick i
        self.optimized = optimized  # whether LLM optimization occurred after this day
        self.optimization_prompts: dict[str, dict] = {}  # agent_id → StructuredPrompt.to_dict()

        # Cache settlement stats — computed once from events, persisted in checkpoints
        if event_summary is not None:
            self._event_summary = event_summary
            self._total_arrivals = total_arrivals or 0
            self._total_settled = total_settled or 0
        else:
            self._compute_event_summary()

    def _compute_event_summary(self) -> None:
        """Compute settlement stats from raw events and cache them."""
        _SETTLEMENT_TYPES = {"Settlement", "RtgsImmediateSettlement", "LsmBilateralOffset", "Queue2LiquidityRelease"}
        summary: dict[str, dict[str, int]] = {}
        arrivals = 0
        settled = 0
        for e in self.events:
            etype = e.get("event_type", "")
            if etype == "Arrival":
                sender = e.get("sender_id", "")
                if sender:
                    summary.setdefault(sender, {"arrivals": 0, "settled": 0})
                    summary[sender]["arrivals"] += 1
                    arrivals += 1
            elif etype in _SETTLEMENT_TYPES:
                sender = e.get("sender_id", "") or e.get("sender", "")
                if sender:
                    summary.setdefault(sender, {"arrivals": 0, "settled": 0})
                    summary[sender]["settled"] += 1
                    settled += 1
        self._event_summary = summary
        self._total_arrivals = arrivals
        self._total_settled = settled

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day_num,
            "seed": self.seed,
            "policies": {aid: p for aid, p in self.policies.items()},
            "costs": self.costs,
            "events": self.events,
            "balance_history": self.balance_history,
            "total_cost": self.total_cost,
            "per_agent_costs": self.per_agent_costs,
            "num_ticks": len(self.tick_events),
            "optimized": self.optimized,
        }

    def to_summary_dict(self) -> dict[str, Any]:
        """Lightweight dict for WS messages — omits large event arrays.

        Uses cached event summary stats so settlement rates survive checkpoint
        round-trips (where raw events are not persisted).
        """
        return {
            "day": self.day_num,
            "seed": self.seed,
            "policies": {aid: p for aid, p in self.policies.items()},
            "costs": self.costs,
            "events": [],  # Empty — use event_summary or replay API for details
            "balance_history": self.balance_history,
            "total_cost": self.total_cost,
            "per_agent_costs": self.per_agent_costs,
            "num_ticks": len(self.tick_events),
            "optimized": self.optimized,
            "event_count": len(self.events) or (self._total_arrivals + self._total_settled),
            "event_summary": self._event_summary,
            "total_arrivals": self._total_arrivals,
            "total_settled": self._total_settled,
            "has_prompts": bool(self.optimization_prompts),
            "prompt_agents": list(self.optimization_prompts.keys()),
        }


class Game:
    """Multi-day policy optimization game."""

    def __init__(self, game_id: str, raw_yaml: dict, use_llm: bool = False,
                 simulated_ai: bool = True, max_days: int = 1,
                 num_eval_samples: int = 1, optimization_interval: int = 1,
                 constraint_preset: str = "simple",
                 starting_policies: dict[str, str] | None = None,
                 optimization_schedule: str = "every_round",
                 prompt_profile: dict[str, dict] | None = None):
        self.game_id = game_id
        self.raw_yaml = raw_yaml
        self.use_llm = use_llm
        self.simulated_ai = simulated_ai
        self.max_days = max_days
        self.num_eval_samples = num_eval_samples  # Bootstrap-lite: run N seeds, average costs
        self.optimization_interval = max(1, optimization_interval)
        self.constraint_preset = constraint_preset
        self.optimization_schedule = optimization_schedule  # "every_round" or "every_scenario_day"
        self.prompt_profile: dict[str, dict] = prompt_profile or {}  # block_id → {enabled, options}
        self.days: list[GameDay] = []
        self.agent_ids: list[str] = [a["id"] for a in raw_yaml.get("agents", [])]
        self.policies: dict[str, dict] = {aid: copy.deepcopy(DEFAULT_POLICY) for aid in self.agent_ids}
        self.reasoning_history: dict[str, list[dict]] = {aid: [] for aid in self.agent_ids}
        self._base_seed = raw_yaml.get("simulation", {}).get("rng_seed", 42)

        # Intra-scenario state
        sim_cfg = raw_yaml.get("simulation", {})
        self._scenario_num_days: int = sim_cfg.get("num_days", 1)
        self._ticks_per_day: int = sim_cfg.get("ticks_per_day", 12)
        self._live_orch: Any = None  # Persistent Orchestrator for intra-scenario mode
        self._day_tick_offset: int = 0
        self._prev_cumulative_costs: dict[str, int] = {}

        # For single-day scenarios, intra-scenario is identical to every_round
        if self._scenario_num_days <= 1 and self.optimization_schedule == "every_scenario_day":
            self.optimization_schedule = "every_round"

        # Intra-scenario mode forces single eval sample (can't re-run mid-scenario)
        if self.optimization_schedule == "every_scenario_day":
            self.num_eval_samples = 1

        # Apply starting policies (agent_id → policy JSON string)
        if starting_policies:
            for agent_id, policy_json_str in starting_policies.items():
                if agent_id not in self.agent_ids:
                    raise ValueError(f"Unknown agent ID in starting_policies: {agent_id}")
                try:
                    policy = json.loads(policy_json_str)
                except (json.JSONDecodeError, TypeError) as e:
                    raise ValueError(f"Invalid policy JSON for {agent_id}: {e}")
                fraction = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
                policy.setdefault("parameters", {})["initial_liquidity_fraction"] = fraction
                self.policies[agent_id] = policy

    @property
    def current_day(self) -> int:
        return len(self.days)

    @property
    def is_complete(self) -> bool:
        return self.current_day >= self.max_days

    def should_optimize(self, day_num: int) -> bool:
        """Whether optimization should run after the given day number."""
        return (day_num + 1) % self.optimization_interval == 0

    def _build_ffi_config(self, seed: int) -> dict:
        """Build FFI config dict from current policies at given seed."""
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
        return sim_config.to_ffi_dict()

    def _run_single_sim(self, seed: int) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]]]:
        """Run one simulation with current policies at given seed.
        
        Returns (events, balance_history, costs, per_agent_costs, total_cost, tick_events).
        tick_events[i] = list of events for tick i (for replay).
        """
        ffi_config = self._build_ffi_config(seed)
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

    def _run_cost_only(self, seed: int) -> dict[str, dict]:
        """Run simulation and return only costs (thread-safe, GIL-releasing).

        Returns parsed JSON: { "BANK_A": { "total_cost": ..., ... }, ... }
        """
        ffi_config = self._build_ffi_config(seed)
        orch = Orchestrator.new(ffi_config)

        ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]
        result_json = orch.run_and_get_all_costs(ticks)
        return json.loads(result_json)

    def _run_scenario_day(self) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]], dict[str, dict[str, int]], int, int]:
        """Run one scenario day (ticks_per_day ticks) on the persistent Orchestrator.

        For intra-scenario mode: keeps the Orchestrator alive between days,
        tracks costs per day (engine resets accumulators at day boundaries),
        and tracks cumulative settlement stats across the round (since
        transactions can arrive on Day N and settle on Day N+k).

        Returns: (events, balance_history, costs, per_agent_costs, total_cost,
                  tick_events, cumulative_event_summary, cumulative_arrivals, cumulative_settled)
        """
        if self._live_orch is None:
            # Start of a new round — create Orchestrator
            round_num = self.current_day // self._scenario_num_days
            seed = self._base_seed + round_num
            ffi_config = self._build_ffi_config(seed)
            self._live_orch = Orchestrator.new(ffi_config)
            self._day_tick_offset = 0
            # Track cumulative arrivals/settlements across the round
            # (transactions can arrive on Day N and settle on Day N+k)
            self._round_cumulative_arrivals: dict[str, int] = {}
            self._round_cumulative_settled: dict[str, int] = {}

        all_events: list[dict] = []
        tick_events: list[list[dict]] = []
        balance_history: dict[str, list] = {aid: [] for aid in self.agent_ids}

        for t in range(self._ticks_per_day):
            tick = self._day_tick_offset + t
            self._live_orch.tick()
            events = self._live_orch.get_tick_events(tick)
            tick_event_list = [dict(e) for e in events]
            all_events.extend(tick_event_list)
            tick_events.append(tick_event_list)
            for aid in self.agent_ids:
                balance_history[aid].append(self._live_orch.get_agent_balance(aid) or 0)

        self._day_tick_offset += self._ticks_per_day

        # Costs: engine resets accumulators at each day boundary (engine.rs:2958),
        # so get_agent_accumulated_costs() returns THIS day's costs directly.
        costs: dict[str, dict] = {}
        per_agent_costs: dict[str, int] = {}
        total_cost = 0
        for aid in self.agent_ids:
            ac = self._live_orch.get_agent_accumulated_costs(aid)
            day_total = int(ac.get("total_cost", 0))
            day_delay = int(ac.get("delay_cost", 0))
            day_penalty = int(ac.get("deadline_penalty", 0))
            day_overdraft = int(ac.get("liquidity_cost", 0))
            day_collateral = int(ac.get("collateral_cost", 0))
            day_split = int(ac.get("split_friction_cost", 0))
            day_opportunity = max(0, day_total - day_delay - day_penalty - day_overdraft - day_collateral - day_split)

            costs[aid] = {
                "liquidity_cost": day_opportunity,
                "delay_cost": day_delay,
                "penalty_cost": day_penalty,
                "total": day_total,
            }
            per_agent_costs[aid] = day_total
            total_cost += day_total

        # Update cumulative settlement stats across the round
        _SETTLEMENT_TYPES = {"Settlement", "RtgsImmediateSettlement", "LsmBilateralOffset", "Queue2LiquidityRelease"}
        for e in all_events:
            etype = e.get("event_type", "")
            if etype == "Arrival":
                sender = e.get("sender_id", "")
                if sender:
                    self._round_cumulative_arrivals.setdefault(sender, 0)
                    self._round_cumulative_arrivals[sender] += 1
            elif etype in _SETTLEMENT_TYPES:
                sender = e.get("sender_id", "") or e.get("sender", "")
                if sender:
                    self._round_cumulative_settled.setdefault(sender, 0)
                    self._round_cumulative_settled[sender] += 1

        # Build cumulative event summary for display
        cum_summary: dict[str, dict[str, int]] = {}
        cum_arrivals = 0
        cum_settled = 0
        all_agents = set(self._round_cumulative_arrivals) | set(self._round_cumulative_settled)
        for aid in all_agents:
            a = self._round_cumulative_arrivals.get(aid, 0)
            s = self._round_cumulative_settled.get(aid, 0)
            cum_summary[aid] = {"arrivals": a, "settled": s}
            cum_arrivals += a
            cum_settled += s

        # Check if this is the last scenario day in the current round
        scenario_day_index = self.current_day % self._scenario_num_days
        if scenario_day_index == self._scenario_num_days - 1:
            # End of round — destroy Orchestrator
            self._live_orch = None
            self._day_tick_offset = 0

        return all_events, balance_history, costs, per_agent_costs, total_cost, tick_events, cum_summary, cum_arrivals, cum_settled

    def _inject_policies_into_orch(self):
        """Update all agent policies in the live Orchestrator after optimization."""
        if self._live_orch is None:
            return
        for aid in self.agent_ids:
            policy_json = json.dumps(self.policies[aid])
            self._live_orch.update_agent_policy(aid, policy_json)

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

        # If multi-sample, run additional seeds in parallel and average costs
        if self.num_eval_samples > 1:
            all_per_agent: dict[str, list[int]] = {aid: [per_agent_costs[aid]] for aid in self.agent_ids}
            all_costs: dict[str, list[dict]] = {aid: [costs[aid]] for aid in self.agent_ids}

            extra_seeds = [seed + i * 1000 for i in range(1, self.num_eval_samples)]

            # Use GIL-releasing FFI for thread-parallel extra samples
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(extra_seeds), 8)) as pool:
                futures = {s: pool.submit(self._run_cost_only, s) for s in extra_seeds}
                extra_results = {s: futures[s].result() for s in extra_seeds}

            for sample_seed in extra_seeds:
                s_costs_json = extra_results[sample_seed]
                for aid in self.agent_ids:
                    agent_c = s_costs_json.get(aid, {})
                    all_per_agent[aid].append(agent_c.get("total_cost", 0))
                    all_costs[aid].append({
                        "liquidity_cost": agent_c.get("liquidity_cost", 0),
                        "delay_cost": agent_c.get("delay_cost", 0),
                        "penalty_cost": agent_c.get("penalty_cost", 0),
                    })
            
            # Average costs across samples + compute std dev
            import math
            n = self.num_eval_samples
            total_cost = 0
            cost_std_per_agent: dict[str, int] = {}
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
                # Std dev of total cost across samples
                if n > 1:
                    mean = sum(all_per_agent[aid]) / n
                    variance = sum((x - mean) ** 2 for x in all_per_agent[aid]) / (n - 1)
                    cost_std_per_agent[aid] = int(math.sqrt(variance))
                else:
                    cost_std_per_agent[aid] = 0
        else:
            cost_std_per_agent = {aid: 0 for aid in self.agent_ids}

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
            per_agent_cost_std=cost_std_per_agent,
        )
        self.days.append(day)
        return day

    def simulate_day(self) -> GameDay:
        """Run simulation without committing to game state.

        Returns a GameDay that can be committed via commit_day().
        Unlike run_day(), this does NOT append to self.days — the caller
        must explicitly call commit_day() after confirming delivery.
        """
        day_num = self.current_day

        cum_event_summary = None
        cum_arrivals = None
        cum_settled = None
        if self.optimization_schedule == "every_scenario_day":
            all_events, balance_history, costs, per_agent_costs, total_cost, tick_events, cum_event_summary, cum_arrivals, cum_settled = self._run_scenario_day()
            seed = self._base_seed + (day_num // self._scenario_num_days)
        else:
            seed = self._base_seed + day_num
            all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self._run_single_sim(seed)

        if self.num_eval_samples > 1:
            all_per_agent: dict[str, list[int]] = {aid: [per_agent_costs[aid]] for aid in self.agent_ids}
            all_costs: dict[str, list[dict]] = {aid: [costs[aid]] for aid in self.agent_ids}

            extra_seeds = [seed + i * 1000 for i in range(1, self.num_eval_samples)]

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(extra_seeds), 8)) as pool:
                futures = {s: pool.submit(self._run_cost_only, s) for s in extra_seeds}
                extra_results = {s: futures[s].result() for s in extra_seeds}

            for sample_seed in extra_seeds:
                s_costs_json = extra_results[sample_seed]
                for aid in self.agent_ids:
                    agent_c = s_costs_json.get(aid, {})
                    all_per_agent[aid].append(agent_c.get("total_cost", 0))
                    all_costs[aid].append({
                        "liquidity_cost": agent_c.get("liquidity_cost", 0),
                        "delay_cost": agent_c.get("delay_cost", 0),
                        "penalty_cost": agent_c.get("penalty_cost", 0),
                    })

            import math
            n = self.num_eval_samples
            total_cost = 0
            cost_std_per_agent: dict[str, int] = {}
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
                if n > 1:
                    mean = sum(all_per_agent[aid]) / n
                    variance = sum((x - mean) ** 2 for x in all_per_agent[aid]) / (n - 1)
                    cost_std_per_agent[aid] = int(math.sqrt(variance))
                else:
                    cost_std_per_agent[aid] = 0
        else:
            cost_std_per_agent = {aid: 0 for aid in self.agent_ids}

        return GameDay(
            day_num=day_num,
            seed=seed,
            policies=copy.deepcopy(self.policies),
            costs=costs,
            events=all_events,
            balance_history=balance_history,
            total_cost=total_cost,
            per_agent_costs=per_agent_costs,
            per_agent_cost_std=cost_std_per_agent,
            tick_events=tick_events,
            # In intra-scenario mode, use cumulative settlement stats across the round
            # (transactions can arrive on Day N and settle on Day N+k)
            event_summary=cum_event_summary,
            total_arrivals=cum_arrivals,
            total_settled=cum_settled,
        )

    def commit_day(self, day: GameDay):
        """Commit a previously simulated day to game state.

        Only call after confirming the day was successfully delivered
        to the client (e.g. WS send succeeded).
        """
        self.days.append(day)

    def save_day_to_duckdb(self, db_path: Path, day: GameDay):
        """Write a day's results to the DuckDB file."""
        con = duckdb.connect(str(db_path))
        con.execute(
            """INSERT OR REPLACE INTO days (day, seed, total_cost, policies, costs, per_agent_costs, balance_history, events)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                day.day_num,
                day.seed,
                day.total_cost,
                json.dumps({aid: p for aid, p in day.policies.items()}),
                json.dumps(day.costs),
                json.dumps(day.per_agent_costs),
                json.dumps(day.balance_history),
                json.dumps(day.events[:200]),  # Cap events to keep DB small
            ],
        )
        con.close()

    async def optimize_policies_streaming(self, send_fn):
        """Run optimization with streaming text chunks.

        All agents optimise in parallel (up to 10 concurrently). Each agent's
        LLM call streams chunks independently; the WebSocket receives
        interleaved events tagged with agent_id so the frontend can display
        per-agent progress.

        Args:
            send_fn: async callable(dict) to send WS messages.
                Called with optimization_start, optimization_chunk,
                optimization_complete messages.
        """
        import asyncio
        import time as _time
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

        # --- Mock mode: sequential (instant, no parallelism needed) ---
        if self.simulated_ai:
            for aid in self.agent_ids:
                await send_fn({
                    "type": "optimization_start",
                    "day": last_day.day_num,
                    "agent_id": aid,
                })
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
                if evaluator and result.get("new_policy"):
                    result = self._run_bootstrap(evaluator, aid, result)
                await send_fn({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })
                self._apply_result(aid, result)
            return

        # --- Real LLM mode: parallel agent optimization ---
        MAX_CONCURRENT = 10
        semaphore = asyncio.Semaphore(min(len(self.agent_ids), MAX_CONCURRENT))

        # Results collected per agent (order doesn't matter for policy application
        # since agents are game-theoretically isolated — each only sees own results).
        results: dict[str, dict] = {}

        async def optimize_one_agent(aid: str) -> None:
            """Run LLM optimization for a single agent, streaming events to WS."""
            async with semaphore:
                await send_fn({
                    "type": "optimization_start",
                    "day": last_day.day_num,
                    "agent_id": aid,
                })

                result = None
                try:
                    async for event in stream_optimize(
                        aid, self.policies[aid], last_day, self.days, self.raw_yaml,
                        constraint_preset=self.constraint_preset,
                        prompt_profile=self.prompt_profile,
                    ):
                        if event["type"] == "chunk":
                            await send_fn({
                                "type": "optimization_chunk",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "text": event["text"],
                            })
                        elif event["type"] == "retry":
                            # Notify frontend of retry (both as chunk for streaming display and as dedicated event)
                            await send_fn({
                                "type": "optimization_chunk",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "text": f"\n⏳ Retrying ({event['attempt']}/{event['max_retries']}) in {event['delay']:.0f}s — {event['reason'][:80]}\n",
                            })
                            await send_fn({
                                "type": "agent_retry",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "reason": event["reason"][:120],
                                "attempt": event["attempt"],
                                "max_retries": event["max_retries"],
                            })
                        elif event["type"] == "result":
                            result = event["data"]
                        elif event["type"] == "error":
                            error_msg = event["message"]
                            logger.error("LLM optimization failed permanently for %s: %s", aid, error_msg)
                            await send_fn({
                                "type": "agent_error",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "message": error_msg,
                                "fatal": True,
                            })
                            raise RuntimeError(f"LLM optimization failed for {aid}: {error_msg}")
                except RuntimeError:
                    raise  # Re-raise LLM failures — do NOT fall back to mock
                except Exception as e:
                    logger.error("Streaming optimization failed for %s: %s", aid, e, exc_info=True)
                    await send_fn({
                        "type": "agent_error",
                        "day": last_day.day_num,
                        "agent_id": aid,
                        "message": str(e)[:200],
                        "fatal": True,
                    })
                    raise RuntimeError(f"LLM optimization failed for {aid}: {e}")

                if result is None:
                    await send_fn({
                        "type": "agent_error",
                        "day": last_day.day_num,
                        "agent_id": aid,
                        "message": "No result from LLM after all retries",
                        "fatal": True,
                    })
                    raise RuntimeError(f"LLM optimization produced no result for {aid}")

                # Bootstrap evaluation gate
                if evaluator and result.get("new_policy"):
                    result = self._run_bootstrap(evaluator, aid, result)

                await send_fn({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })
                results[aid] = result

        # Fire all agent tasks concurrently
        _par_start = _time.monotonic()
        tasks = [asyncio.create_task(optimize_one_agent(aid)) for aid in self.agent_ids]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)
        _par_elapsed = _time.monotonic() - _par_start
        logger.warning(
            "Parallel optimization for %d agents completed in %.1fs",
            len(self.agent_ids), _par_elapsed,
        )

        # Check for fatal LLM failures — abort experiment if any agent failed
        for i, r in enumerate(gather_results):
            if isinstance(r, Exception):
                aid = self.agent_ids[i]
                error_msg = str(r)
                logger.error("Agent %s optimization failed fatally: %s", aid, error_msg)
                await send_fn({
                    "type": "experiment_error",
                    "message": f"Experiment stopped: LLM optimization failed for {aid} after all retries. {error_msg}",
                    "fatal": True,
                })
                # Mark game as stopped so auto-run doesn't continue
                self.auto_run = False
                return  # Do NOT apply any results — abort this round

        # Apply results (order doesn't matter — agents are isolated)
        for aid in self.agent_ids:
            if aid in results:
                self._store_prompt(last_day, aid, results[aid])
                self._apply_result(aid, results[aid])

    def _run_bootstrap(self, evaluator, aid: str, result: dict) -> dict:
        """Run bootstrap paired evaluation and annotate result."""
        import time as _time
        other_policies = {
            other_aid: self.policies[other_aid]
            for other_aid in self.agent_ids if other_aid != aid
        }
        _bs_start = _time.monotonic()
        eval_result = evaluator.evaluate(
            raw_yaml=self.raw_yaml,
            agent_id=aid,
            old_policy=self.policies[aid],
            new_policy=result["new_policy"],
            base_seed=self._base_seed + self.current_day * 100,
            other_policies=other_policies,
        )
        logger.warning("Bootstrap eval for %s: %.1fs (%d samples)", aid, _time.monotonic() - _bs_start, self.num_eval_samples)
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
        return result

    def _store_prompt(self, day: 'GameDay', aid: str, result: dict) -> None:
        """Store structured prompt data from optimization result on the day."""
        sp = result.get("structured_prompt")
        if sp:
            day.optimization_prompts[aid] = sp

    def _apply_result(self, aid: str, result: dict) -> None:
        """Apply an optimization result: update policy and record history.
        
        Validates new policy by building a test config before applying.
        If validation fails, keeps the old policy and marks the result.
        """
        if result and result.get("new_policy"):
            old_policy = self.policies[aid]
            self.policies[aid] = result["new_policy"]
            try:
                ffi_config = self._build_ffi_config(self._base_seed)
                Orchestrator.new(ffi_config)
            except Exception as e:
                logger.warning("Policy validation failed for %s: %s — keeping old policy", aid, e)
                self.policies[aid] = old_policy
                result["rejected"] = True
                result["rejection_reason"] = str(e)
                result["new_policy"] = None
        if result:
            self.reasoning_history[aid].append(result)

    async def optimize_policies(self) -> dict[str, dict]:
        """Run optimization step between days. Returns reasoning per agent.

        All agents optimise in parallel. When num_eval_samples > 1, uses
        WebBootstrapEvaluator for paired comparison.
        """
        import asyncio
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

        async def optimize_one(aid: str) -> tuple[str, dict]:
            if self.simulated_ai:
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
            else:
                # Real LLM mode — never fall back to mock. Fail hard.
                result = await _real_optimize(aid, self.policies[aid], last_day,
                                              self.days, self.raw_yaml,
                                              constraint_preset=self.constraint_preset)

            if evaluator and result.get("new_policy"):
                result = self._run_bootstrap(evaluator, aid, result)

            return aid, result

        # Run all agents concurrently
        tasks = [optimize_one(aid) for aid in self.agent_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for item in results:
            if isinstance(item, Exception):
                logger.error("Agent optimization raised: %s", item)
                continue
            aid, result = item
            self._apply_result(aid, result)
            if last_day:
                self._store_prompt(last_day, aid, result)
            reasoning[aid] = result

        return reasoning

    def get_state(self) -> dict[str, Any]:
        return {
            "game_id": self.game_id,
            "current_day": self.current_day,
            "max_days": self.max_days,
            "is_complete": self.is_complete,
            "use_llm": self.use_llm,
            "num_eval_samples": self.num_eval_samples,
            "optimization_interval": self.optimization_interval,
            "constraint_preset": self.constraint_preset,
            "optimization_schedule": self.optimization_schedule,
            "scenario_num_days": self._scenario_num_days,
            "agent_ids": self.agent_ids,
            "current_policies": {
                aid: p for aid, p in self.policies.items()
            },
            "days": [d.to_summary_dict() for d in self.days],
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

    # ── Checkpoint persistence ───────────────────────────────────────

    def to_checkpoint(self, scenario_id: str = "", uid: str = "") -> dict[str, Any]:
        """Serialize full game state to a checkpoint dict."""
        from datetime import datetime, timezone
        status = "complete" if self.is_complete else ("running" if self.days else "created")
        return {
            "version": 1,
            "game_id": self.game_id,
            "uid": uid,
            "scenario_id": scenario_id,
            "created_at": getattr(self, '_created_at', datetime.now(timezone.utc).isoformat()),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "config": {
                "raw_yaml": self.raw_yaml,
                "use_llm": self.use_llm,
                "simulated_ai": self.simulated_ai,
                "max_days": self.max_days,
                "num_eval_samples": self.num_eval_samples,
                "optimization_interval": self.optimization_interval,
                "constraint_preset": self.constraint_preset,
                "optimization_schedule": self.optimization_schedule,
                "base_seed": self._base_seed,
                "prompt_profile": self.prompt_profile,
            },
            "progress": {
                "current_day": self.current_day,
                "agent_ids": self.agent_ids,
                "policies": copy.deepcopy(self.policies),
                "reasoning_history": copy.deepcopy(self.reasoning_history),
                "days": [self._day_to_checkpoint(d) for d in self.days],
            },
        }

    @staticmethod
    def _day_to_checkpoint(day: 'GameDay') -> dict[str, Any]:
        """Serialize a GameDay for checkpoint (excludes tick_events for size)."""
        return {
            "day_num": day.day_num,
            "seed": day.seed,
            "policies": copy.deepcopy(day.policies),
            "costs": day.costs,
            "events_summary": {
                "total": len(day.events) or (day._total_arrivals + day._total_settled),
                "types": {},  # could add event type counts
            },
            "settlement_stats": {
                "event_summary": day._event_summary,
                "total_arrivals": day._total_arrivals,
                "total_settled": day._total_settled,
            },
            "balance_history": day.balance_history,
            "total_cost": day.total_cost,
            "per_agent_costs": day.per_agent_costs,
            "per_agent_cost_std": day.per_agent_cost_std,
            "optimized": day.optimized,
            "optimization_prompts": day.optimization_prompts,
        }

    @classmethod
    def from_checkpoint(cls, data: dict) -> 'Game':
        """Reconstruct a Game from a checkpoint dict."""
        config = data["config"]
        progress = data["progress"]

        game = cls(
            game_id=data["game_id"],
            raw_yaml=config["raw_yaml"],
            use_llm=config.get("use_llm", True),
            simulated_ai=config.get("simulated_ai", False),
            max_days=config.get("max_days", 1),
            num_eval_samples=config.get("num_eval_samples", 1),
            optimization_interval=config.get("optimization_interval", 1),
            constraint_preset=config.get("constraint_preset", "simple"),
            optimization_schedule=config.get("optimization_schedule", "every_round"),
            prompt_profile=config.get("prompt_profile"),
        )
        game._base_seed = config.get("base_seed", 42)
        game._created_at = data.get("created_at", "")
        game._scenario_id = data.get("scenario_id", "")
        game._uid = data.get("uid", "")

        # Restore policies
        game.policies = copy.deepcopy(progress.get("policies", game.policies))

        # Restore reasoning history
        game.reasoning_history = copy.deepcopy(progress.get("reasoning_history", game.reasoning_history))

        # Restore days (without tick_events — those live in DuckDB)
        for day_data in progress.get("days", []):
            day = GameDay(
                day_num=day_data["day_num"],
                seed=day_data["seed"],
                policies=copy.deepcopy(day_data.get("policies", {})),
                costs=day_data.get("costs", {}),
                events=[],  # Not stored in checkpoint — use DuckDB for replay
                balance_history=day_data.get("balance_history", {}),
                total_cost=day_data.get("total_cost", 0),
                per_agent_costs=day_data.get("per_agent_costs", {}),
                tick_events=[],
                optimized=day_data.get("optimized", False),
                event_summary=day_data.get("settlement_stats", {}).get("event_summary"),
                total_arrivals=day_data.get("settlement_stats", {}).get("total_arrivals"),
                total_settled=day_data.get("settlement_stats", {}).get("total_settled"),
                per_agent_cost_std=day_data.get("per_agent_cost_std", {}),
            )
            day.optimization_prompts = day_data.get("optimization_prompts", {})
            game.days.append(day)

        return game


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
        "old_policy": current_policy,
        "reasoning": reasoning,
        "old_fraction": current_fraction,
        "new_fraction": new_fraction,
        "accepted": True,
        "mock": True,
    }


async def _real_optimize(agent_id: str, current_policy: dict, last_day: GameDay,
                         all_days: list[GameDay], raw_yaml: dict,
                         constraint_preset: str = "simple") -> dict[str, Any]:
    """Use the real LLM optimization infrastructure.

    Reuses the existing PolicyOptimizer + ExperimentLLMClient from the experiment
    runner. Builds proper context with agent-isolated events, cost breakdown, and
    iteration history. Always accepts new policies (temporal mode — the cost landscape
    shifts as counterparties change).
    """
    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer
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

    # Build constraints from preset
    from .constraint_presets import build_constraints
    constraints = build_constraints(constraint_preset, raw_yaml)

    optimizer = PolicyOptimizer(constraints=constraints, max_retries=2)

    # Use platform settings for model selection (admin-switchable)
    from .settings import settings_manager, MAAS_MODEL_CONFIG
    llm_config = settings_manager.get_llm_config()

    client = ExperimentLLMClient(llm_config)

    # MaaS models (GLM-5, Gemini 3 preview) need custom provider config.
    # Patch the client's agent creation to use our _create_agent helper.
    if llm_config.model_name in MAAS_MODEL_CONFIG:
        from .streaming_optimizer import _create_agent
        _orig_generate = client.generate_policy

        async def _maas_generate_policy(prompt, current_policy=None, context=None):
            """Override that uses _create_agent for MaaS/global-region model support.
            
            Must return a parsed dict (like the original generate_policy),
            NOT an LLMResponse. PolicyOptimizer.optimize() expects a dict.
            """
            user_prompt = client._build_user_prompt(prompt, current_policy, context)
            system_prompt = client.system_prompt or ""
            agent = _create_agent(llm_config, system_prompt)
            import time
            start = time.time()
            result = await agent.run(user_prompt, model_settings=llm_config.to_model_settings())
            latency = time.time() - start
            raw = str(result.output)
            # Parse the raw response into a policy dict — same as original generate_policy
            parsed = client.parse_policy(raw)
            if not isinstance(parsed, dict):
                raise TypeError(
                    f"_maas_generate_policy must return dict, got {type(parsed).__name__}. "
                    f"This breaks PolicyOptimizer.optimize() which passes the return value "
                    f"to ConstraintValidator.validate()."
                )
            return parsed

        client.generate_policy = _maas_generate_policy

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
        llm_model=llm_config.model_name,
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
        "old_policy": current_policy,
        "reasoning": reasoning_text,
        "old_fraction": current_fraction,
        "new_fraction": new_fraction,
        "accepted": result.was_accepted,
        "mock": False,
        "reasoning_summary": result.reasoning_summary if hasattr(result, 'reasoning_summary') else None,
        "validation_errors": result.validation_errors if hasattr(result, 'validation_errors') else [],
    }
