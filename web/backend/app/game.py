"""Multi-day policy optimization game."""
from __future__ import annotations

import math
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
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector  # type: ignore
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler  # type: ignore
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator  # type: ignore

logger = logging.getLogger(__name__)

# ── Bootstrap acceptance profiles ────────────────────────────────────
# Per-agent risk profiles for the bootstrap evaluation gate.
# Agents can set `bootstrap_profile: "conservative"` or provide custom
# thresholds via `bootstrap_thresholds: {n_samples: 100, ...}` in the
# scenario YAML.

BOOTSTRAP_PROFILES: dict[str, dict[str, Any]] = {
    "conservative": {
        "n_samples": 100,
        "cv_threshold": 0.3,
        "require_significance": True,   # 95% CI lower > 0
        "min_improvement_pct": 0.02,    # new cost must be ≥2% cheaper
    },
    "moderate": {
        "n_samples": 50,
        "cv_threshold": 0.5,
        "require_significance": True,
        "min_improvement_pct": 0.0,
    },
    "aggressive": {
        "n_samples": 20,
        "cv_threshold": 1.0,
        "require_significance": False,  # accept if delta_sum > 0, skip CI
        "min_improvement_pct": 0.0,
    },
}
DEFAULT_BOOTSTRAP_PROFILE = "moderate"


def _resolve_bootstrap_thresholds(agent_cfg: dict[str, Any]) -> dict[str, Any]:
    """Resolve bootstrap thresholds for an agent from its scenario config.

    Priority:
    1. agent.bootstrap_thresholds (custom dict) — full override
    2. agent.bootstrap_profile (str) — named profile lookup
    3. DEFAULT_BOOTSTRAP_PROFILE fallback
    """
    # Custom thresholds take priority
    custom = agent_cfg.get("bootstrap_thresholds")
    if isinstance(custom, dict):
        # Merge with moderate defaults so partial overrides work
        base = dict(BOOTSTRAP_PROFILES["moderate"])
        base.update(custom)
        return base

    # Named profile
    profile_name = agent_cfg.get("bootstrap_profile", DEFAULT_BOOTSTRAP_PROFILE)
    if profile_name in BOOTSTRAP_PROFILES:
        return dict(BOOTSTRAP_PROFILES[profile_name])

    logger.warning("Unknown bootstrap_profile '%s', using moderate", profile_name)
    return dict(BOOTSTRAP_PROFILES["moderate"])


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
        self.rejected_policies: dict[str, dict] = {}  # agent_id → rejected policy (for learning)
        self.agent_histories: dict[str, Any] = {}  # agent_id → AgentTransactionHistory (for bootstrap)

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
                 include_groups: list[str] | None = None,
                 exclude_groups: list[str] | None = None,
                 starting_policies: dict[str, str] | None = None,
                 optimization_schedule: str = "every_scenario_day",
                 prompt_profile: dict[str, dict] | None = None):
        self.game_id = game_id
        self.raw_yaml = raw_yaml
        self.use_llm = use_llm
        self.simulated_ai = simulated_ai
        self.max_days = max_days
        self.num_eval_samples = num_eval_samples  # Bootstrap-lite: run N seeds, average costs
        self.optimization_interval = max(1, optimization_interval)
        self.constraint_preset = constraint_preset
        self.include_groups = include_groups
        self.exclude_groups = exclude_groups
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

    def _run_with_samples(
        self,
        seed: int,
        events: list[dict],
        balance_history: dict[str, list],
        costs: dict[str, dict],
        per_agent_costs: dict[str, int],
        total_cost: int,
        tick_events: list[list[dict]],
    ) -> tuple[dict[str, dict], dict[str, int], int, dict[str, int]]:
        """Average costs over multiple seeds if num_eval_samples > 1.

        Takes the representative run's results and optionally runs extra
        cost-only seeds in parallel, averaging all costs and computing std dev.

        Returns (costs, per_agent_costs, total_cost, cost_std_per_agent).
        Mutates nothing — returns new dicts.
        """
        if self.num_eval_samples <= 1:
            return costs, per_agent_costs, total_cost, {aid: 0 for aid in self.agent_ids}

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

        n = self.num_eval_samples
        avg_costs: dict[str, dict] = {}
        avg_per_agent: dict[str, int] = {}
        avg_total = 0
        cost_std_per_agent: dict[str, int] = {}
        for aid in self.agent_ids:
            at = sum(all_per_agent[aid]) // n
            ad = sum(c["delay_cost"] for c in all_costs[aid]) // n
            ap = sum(c["penalty_cost"] for c in all_costs[aid]) // n
            al = sum(c["liquidity_cost"] for c in all_costs[aid]) // n
            avg_costs[aid] = {
                "liquidity_cost": al,
                "delay_cost": ad,
                "penalty_cost": ap,
                "total": at,
            }
            avg_per_agent[aid] = at
            avg_total += at
            if n > 1:
                mean = sum(all_per_agent[aid]) / n
                variance = sum((x - mean) ** 2 for x in all_per_agent[aid]) / (n - 1)
                cost_std_per_agent[aid] = int(math.sqrt(variance))
            else:
                cost_std_per_agent[aid] = 0

        return avg_costs, avg_per_agent, avg_total, cost_std_per_agent

    def run_day(self) -> GameDay:
        """Run one day of simulation with current policies."""
        day_num = self.current_day
        seed = self._base_seed + day_num

        all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self._run_single_sim(seed)
        costs, per_agent_costs, total_cost, cost_std = self._run_with_samples(
            seed, all_events, balance_history, costs, per_agent_costs, total_cost, tick_events,
        )

        day = GameDay(
            day_num=day_num, seed=seed, policies=copy.deepcopy(self.policies),
            costs=costs, events=all_events, balance_history=balance_history,
            total_cost=total_cost, per_agent_costs=per_agent_costs,
            tick_events=tick_events, per_agent_cost_std=cost_std,
        )
        self.days.append(day)
        return day

    def simulate_day(self) -> GameDay:
        """Run simulation without committing to game state.

        Returns a GameDay that can be committed via commit_day().
        Unlike run_day(), this does NOT append to self.days.
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

        costs, per_agent_costs, total_cost, cost_std = self._run_with_samples(
            seed, all_events, balance_history, costs, per_agent_costs, total_cost, tick_events,
        )

        # Collect transaction histories for bootstrap evaluation
        collector = TransactionHistoryCollector()
        flat_events = [e for tick_list in tick_events for e in tick_list]
        collector.process_events(flat_events)
        agent_histories = {aid: collector.get_agent_history(aid) for aid in self.agent_ids}

        day = GameDay(
            day_num=day_num, seed=seed, policies=copy.deepcopy(self.policies),
            costs=costs, events=all_events, balance_history=balance_history,
            total_cost=total_cost, per_agent_costs=per_agent_costs,
            per_agent_cost_std=cost_std, tick_events=tick_events,
            event_summary=cum_event_summary, total_arrivals=cum_arrivals,
            total_settled=cum_settled,
        )
        day.agent_histories = agent_histories
        return day

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

    async def optimize_all_agents(self, send_fn=None) -> dict[str, dict]:
        """Run optimization for all agents, optionally streaming progress.

        Args:
            send_fn: async callable(dict) to send WS messages, or None for
                silent HTTP mode. When None, results are collected and returned.

        Returns:
            dict mapping agent_id → optimization result (reasoning, policy, etc.).
            In streaming mode, results are also sent via send_fn.
        """
        import asyncio
        import time as _time
        from .streaming_optimizer import stream_optimize

        if not self.days:
            return {}

        last_day = self.days[-1]

        async def _send(msg: dict) -> None:
            if send_fn is not None:
                await send_fn(msg)

        # --- Mock mode: sequential (instant, no parallelism needed) ---
        if self.simulated_ai:
            reasoning: dict[str, dict] = {}
            for aid in self.agent_ids:
                await _send({
                    "type": "optimization_start",
                    "day": last_day.day_num,
                    "agent_id": aid,
                })
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
                if result.get("new_policy"):
                    result = self._run_real_bootstrap(aid, last_day, result)
                await _send({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })
                self._apply_result(aid, result)
                reasoning[aid] = result
            return reasoning

        # --- Real LLM mode: parallel agent optimization ---
        MAX_CONCURRENT = 10
        semaphore = asyncio.Semaphore(min(len(self.agent_ids), MAX_CONCURRENT))

        # Results collected per agent (order doesn't matter for policy application
        # since agents are game-theoretically isolated — each only sees own results).
        results: dict[str, dict] = {}

        async def optimize_one_agent(aid: str) -> None:
            """Run LLM optimization for a single agent, streaming events."""
            async with semaphore:
                await _send({
                    "type": "optimization_start",
                    "day": last_day.day_num,
                    "agent_id": aid,
                })

                result = None
                try:
                    async for event in stream_optimize(
                        aid, self.policies[aid], last_day, self.days, self.raw_yaml,
                        constraint_preset=self.constraint_preset,
                        include_groups=self.include_groups,
                        exclude_groups=self.exclude_groups,
                        prompt_profile=self.prompt_profile,
                    ):
                        if event["type"] == "chunk":
                            await _send({
                                "type": "optimization_chunk",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "text": event["text"],
                            })
                        elif event["type"] == "retry":
                            await _send({
                                "type": "optimization_chunk",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "text": f"\n⏳ Retrying ({event['attempt']}/{event['max_retries']}) in {event['delay']:.0f}s — {event['reason'][:80]}\n",
                            })
                            await _send({
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
                            await _send({
                                "type": "agent_error",
                                "day": last_day.day_num,
                                "agent_id": aid,
                                "message": error_msg,
                                "fatal": True,
                            })
                            raise RuntimeError(f"LLM optimization failed for {aid}: {error_msg}")
                except RuntimeError:
                    raise
                except Exception as e:
                    logger.error("Streaming optimization failed for %s: %s", aid, e, exc_info=True)
                    await _send({
                        "type": "agent_error",
                        "day": last_day.day_num,
                        "agent_id": aid,
                        "message": str(e)[:200],
                        "fatal": True,
                    })
                    raise RuntimeError(f"LLM optimization failed for {aid}: {e}")

                if result is None:
                    await _send({
                        "type": "agent_error",
                        "day": last_day.day_num,
                        "agent_id": aid,
                        "message": "No result from LLM after all retries",
                        "fatal": True,
                    })
                    raise RuntimeError(f"LLM optimization produced no result for {aid}")

                if result.get("new_policy"):
                    result = self._run_real_bootstrap(aid, last_day, result)

                await _send({
                    "type": "optimization_complete",
                    "day": last_day.day_num,
                    "agent_id": aid,
                    "data": result,
                })
                results[aid] = result

        _par_start = _time.monotonic()
        tasks = [asyncio.create_task(optimize_one_agent(aid)) for aid in self.agent_ids]
        gather_results = await asyncio.gather(*tasks, return_exceptions=True)
        _par_elapsed = _time.monotonic() - _par_start
        logger.warning(
            "Parallel optimization for %d agents completed in %.1fs",
            len(self.agent_ids), _par_elapsed,
        )

        for i, r in enumerate(gather_results):
            if isinstance(r, Exception):
                aid = self.agent_ids[i]
                error_msg = str(r)
                logger.error("Agent %s optimization failed fatally: %s", aid, error_msg)
                await _send({
                    "type": "experiment_error",
                    "message": f"Experiment stopped: LLM optimization failed for {aid} after all retries. {error_msg}",
                    "fatal": True,
                })
                self.auto_run = False
                return {}

        for aid in self.agent_ids:
            if aid in results:
                self._store_prompt(last_day, aid, results[aid])
                self._apply_result(aid, results[aid])

        return results

    def _run_real_bootstrap(self, aid: str, day: 'GameDay', result: dict) -> dict:
        """Run paper's bootstrap evaluation: resample → single-agent sandbox → paired comparison.

        Uses TransactionHistoryCollector → BootstrapSampler → BootstrapPolicyEvaluator
        from api/payment_simulator/ai_cash_mgmt/bootstrap/. This is the same statistical
        method used in the paper (50 bootstrap samples, SOURCE→TARGET→SINK sandbox).

        Delta convention: cost_a - cost_b (positive = new policy is cheaper = improvement).
        """
        import math
        import statistics
        import time as _time

        history = day.agent_histories.get(aid)
        if not history or (not history.outgoing and not history.incoming):
            logger.warning("No transaction history for %s on day %d, skipping bootstrap", aid, day.day_num)
            return result

        # Extract agent config from scenario YAML
        agent_cfg = next((a for a in self.raw_yaml.get("agents", []) if a.get("id") == aid), None)
        if not agent_cfg:
            logger.warning("Agent %s not found in scenario config, skipping bootstrap", aid)
            return result

        _bs_start = _time.monotonic()

        # Phase 2: Log proposed vs current fraction
        current_fraction = self.policies[aid].get("parameters", {}).get("initial_liquidity_fraction", 1.0)
        proposed_fraction = result["new_policy"].get("parameters", {}).get("initial_liquidity_fraction", 1.0)
        tree_changed = (json.dumps(self.policies[aid].get("payment_tree", {}), sort_keys=True) !=
                        json.dumps(result["new_policy"].get("payment_tree", {}), sort_keys=True))
        logger.info("Bootstrap for %s: fraction %.3f → %.3f (delta=%.3f), tree_changed=%s",
                     aid, current_fraction, proposed_fraction, proposed_fraction - current_fraction, tree_changed)

        # Resolve per-agent bootstrap thresholds
        thresholds = _resolve_bootstrap_thresholds(agent_cfg)
        n_samples = thresholds["n_samples"]
        cv_threshold = thresholds["cv_threshold"]
        require_significance = thresholds["require_significance"]
        min_improvement_pct = thresholds.get("min_improvement_pct", 0.0)

        # Step 1: Generate bootstrap samples (resampled transaction schedules)
        sampler = BootstrapSampler(seed=self._base_seed + day.day_num * 100)
        samples = sampler.generate_samples(
            agent_id=aid,
            n_samples=n_samples,
            outgoing_records=history.outgoing,
            incoming_records=history.incoming,
            total_ticks=self._ticks_per_day,
        )

        # Step 2: Paired evaluation on single-agent sandboxes
        # Pass cost_rates from scenario config directly — keys match CostRates pydantic fields
        scenario_cost_rates = self.raw_yaml.get("cost_rates") or None

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=agent_cfg.get("opening_balance", 0),
            credit_limit=agent_cfg.get("unsecured_cap", 0),
            liquidity_pool=agent_cfg.get("liquidity_pool"),
            max_collateral_capacity=agent_cfg.get("max_collateral_capacity"),
            cost_rates=scenario_cost_rates,
        )
        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a=self.policies[aid],   # current/old
            policy_b=result["new_policy"],  # proposed/new
        )
        # delta = cost_a - cost_b. Positive = new is cheaper = improvement.

        # Diagnostic: log per-sample costs to detect zero-cost or identical-cost issues
        if deltas:
            costs_a = [d.cost_a for d in deltas]
            costs_b = [d.cost_b for d in deltas]
            logger.info("Bootstrap costs for %s: cost_a=[min=%d, max=%d, mean=%d], cost_b=[min=%d, max=%d, mean=%d]",
                        aid, min(costs_a), max(costs_a), sum(costs_a)//len(costs_a),
                        min(costs_b), max(costs_b), sum(costs_b)//len(costs_b))

        # Step 3: Compute statistics
        delta_values = [d.delta for d in deltas]
        n = len(delta_values)
        delta_sum = sum(delta_values)
        mean_delta = delta_sum // n if n else 0

        if n >= 2 and mean_delta != 0:
            std = statistics.stdev(delta_values)
            se = std / math.sqrt(n)
            ci_lower = int(mean_delta - 1.96 * se)
            ci_upper = int(mean_delta + 1.96 * se)
            cv = abs(std / mean_delta)
        else:
            ci_lower = ci_upper = mean_delta
            cv = 0.0

        mean_old = sum(d.cost_a for d in deltas) // n if n else 0
        mean_new = sum(d.cost_b for d in deltas) // n if n else 0

        # Step 4: Acceptance criteria (per-agent thresholds)
        accepted = True
        rejection_reason = ""
        profile_name = agent_cfg.get("bootstrap_profile", DEFAULT_BOOTSTRAP_PROFILE)
        if "bootstrap_thresholds" in agent_cfg:
            profile_name = "custom"

        if delta_sum <= 0:
            accepted = False
            rejection_reason = f"No improvement: delta_sum={delta_sum} (old={mean_old:,}, new={mean_new:,})"
        elif min_improvement_pct > 0 and mean_old > 0:
            improvement_pct = delta_sum / (n * mean_old) if n else 0
            if improvement_pct < min_improvement_pct:
                accepted = False
                rejection_reason = f"Improvement too small: {improvement_pct:.1%} < {min_improvement_pct:.0%} threshold"
        if accepted and require_significance and ci_lower <= 0 and n >= 2:
            accepted = False
            rejection_reason = f"Not significant: 95% CI [{ci_lower:,}, {ci_upper:,}] includes zero"
        # CV check removed — the CI significance check (ci_lower > 0) is the
        # statistically correct noise filter. CV was redundant and too strict for
        # crisis scenarios with high cost variance. Paper's pipeline doesn't use CV.

        _bs_elapsed = _time.monotonic() - _bs_start
        logger.warning(
            "Bootstrap eval for %s [%s]: %.1fs, %d samples, delta_sum=%d, accepted=%s%s",
            aid, profile_name, _bs_elapsed, n, delta_sum, accepted,
            f" ({rejection_reason})" if rejection_reason else "",
        )

        # Annotate result with bootstrap details
        result["bootstrap"] = {
            "delta_sum": delta_sum,
            "mean_delta": mean_delta,
            "cv": round(cv, 4),
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "num_samples": n,
            "old_mean_cost": mean_old,
            "new_mean_cost": mean_new,
            "rejection_reason": rejection_reason,
            "profile": profile_name,
            "cv_threshold": cv_threshold,
            "require_significance": require_significance,
        }

        if not accepted:
            result["accepted"] = False
            result["rejection_reason"] = rejection_reason
            result["reasoning"] += f" [REJECTED: {rejection_reason}]"
            # Preserve rejected policy so LLM can learn from failures
            rejected_pol = result.get("new_policy")
            result["rejected_policy"] = rejected_pol
            result["rejected_fraction"] = result.get("new_fraction")
            result["new_policy"] = None
            result["new_fraction"] = None
            # Store on the day for iteration history builder
            if rejected_pol:
                day.rejected_policies[aid] = rejected_pol

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
            "include_groups": self.include_groups,
            "exclude_groups": self.exclude_groups,
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
            "rejected_policies": day.rejected_policies,
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
            include_groups=config.get("include_groups"),
            exclude_groups=config.get("exclude_groups"),
            optimization_schedule=config.get("optimization_schedule", "every_scenario_day"),
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
            day.rejected_policies = day_data.get("rejected_policies", {})
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


    # _real_optimize() removed in Phase 2 — all optimization goes through
    # optimize_all_agents() → streaming_optimizer.stream_optimize()
