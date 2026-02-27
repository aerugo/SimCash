"""Multi-day policy optimization game."""
from __future__ import annotations

import math
import sys
import json
import copy
import random
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from payment_simulator._core import Orchestrator  # type: ignore (used in _apply_result validation)
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector  # type: ignore
from .sim_runner import SimulationRunner
from .bootstrap_gate import BootstrapGate
from . import serialization as _ser

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
        self.optimization_failed: bool = False  # whether optimization failed fatally
        self.optimization_prompts: dict[str, dict] = {}  # agent_id → StructuredPrompt.to_dict()
        self.optimization_results: dict[str, dict] = {}  # agent_id → full result dict
        self.rejected_policies: dict[str, dict] = {}  # agent_id → rejected policy (for learning)
        self.agent_histories: dict[str, Any] = {}  # agent_id → AgentTransactionHistory (for bootstrap)

        # Per-day cost deltas (not cumulative). Set by Game after computing delta.
        # Default: same as cumulative (correct for first day or single-day rounds).
        self.day_total_cost: int = total_cost
        self.day_per_agent_costs: dict[str, int] = dict(per_agent_costs)
        self.day_costs: dict[str, dict] = copy.deepcopy(costs)  # per-agent cost breakdown delta

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
            "costs": self.day_costs,
            "events": self.events,
            "balance_history": self.balance_history,
            "total_cost": self.day_total_cost,
            "per_agent_costs": self.day_per_agent_costs,
            "num_ticks": len(self.tick_events),
            "optimized": self.optimized,
            "optimization_failed": self.optimization_failed,
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
            "costs": self.day_costs,
            "events": [],  # Empty — use event_summary or replay API for details
            "balance_history": self.balance_history,
            "total_cost": self.day_total_cost,
            "per_agent_costs": self.day_per_agent_costs,
            "num_ticks": len(self.tick_events),
            "optimized": self.optimized,
            "optimization_failed": self.optimization_failed,
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
                 simulated_ai: bool = True, total_days: int = 1,
                 num_eval_samples: int = 1, optimization_interval: int = 1,
                 constraint_preset: str = "simple",
                 include_groups: list[str] | None = None,
                 exclude_groups: list[str] | None = None,
                 starting_policies: dict[str, str] | None = None,
                 optimization_schedule: str = "every_scenario_day",
                 prompt_profile: dict[str, dict] | None = None,
                 max_policy_proposals: int = 2):
        self.game_id = game_id
        self.raw_yaml = raw_yaml
        self.use_llm = use_llm
        self.simulated_ai = simulated_ai
        self.total_days = total_days
        self.num_eval_samples = num_eval_samples  # Bootstrap-lite: run N seeds, average costs
        self.optimization_interval = max(1, optimization_interval)
        self.constraint_preset = constraint_preset
        self.include_groups = include_groups
        self.exclude_groups = exclude_groups
        self.optimization_schedule = optimization_schedule  # "every_round" or "every_scenario_day"
        self.prompt_profile: dict[str, dict] = prompt_profile or {}  # block_id → {enabled, options}
        self.max_policy_proposals: int = max(1, min(5, max_policy_proposals))
        self.days: list[GameDay] = []
        self.stalled: bool = False
        self.stall_reason: str = ""
        self.agent_ids: list[str] = [a["id"] for a in raw_yaml.get("agents", [])]
        self.policies: dict[str, dict] = {aid: copy.deepcopy(DEFAULT_POLICY) for aid in self.agent_ids}
        self.reasoning_history: dict[str, list[dict]] = {aid: [] for aid in self.agent_ids}
        self._scenario_name: str = ""
        self._optimization_model: str = ""
        self._created_at: str = datetime.now(timezone.utc).isoformat()
        self.last_activity_at: str = datetime.now(timezone.utc).isoformat()
        self._base_seed = raw_yaml.get("simulation", {}).get("rng_seed", 42)

        # Scenario configuration
        sim_cfg = raw_yaml.get("simulation", {})
        self._scenario_num_days: int = sim_cfg.get("num_days", 1)
        self._ticks_per_day: int = sim_cfg.get("ticks_per_day", 12)

        # For single-day scenarios, intra-scenario is identical to every_round
        if self._scenario_num_days <= 1 and self.optimization_schedule == "every_scenario_day":
            self.optimization_schedule = "every_round"

        # Intra-scenario mode forces single eval sample (can't re-run mid-scenario)
        if self.optimization_schedule == "every_scenario_day":
            self.num_eval_samples = 1

        # Rate limit tracking for dynamic concurrency throttling
        self._rate_limited: bool = False
        self._rate_limited_since: str | None = None

        # Bootstrap gate (shares policies dict by reference)
        self.bootstrap_gate = BootstrapGate(
            raw_yaml=self.raw_yaml,
            agent_ids=self.agent_ids,
            ticks_per_day=self._ticks_per_day,
            base_seed=self._base_seed,
            policies=self.policies,
        )

        # Simulation runner (shares policies dict by reference)
        self.sim = SimulationRunner(
            raw_yaml=self.raw_yaml,
            agent_ids=self.agent_ids,
            policies=self.policies,
            ticks_per_day=self._ticks_per_day,
            scenario_num_days=self._scenario_num_days,
            base_seed=self._base_seed,
        )
        # Share days list for fast-forward replay after checkpoint restore
        self.sim._completed_days = self.days

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

    def touch_activity(self) -> None:
        """Update last_activity_at to now."""
        self.last_activity_at = datetime.now(timezone.utc).isoformat()

    @property
    def current_day(self) -> int:
        return len(self.days)

    @property
    def max_rounds(self) -> int:
        """Number of optimization rounds (user-configured concept)."""
        if self._scenario_num_days > 1:
            return self.total_days // self._scenario_num_days
        return self.total_days

    @property
    def current_round(self) -> int:
        """Current optimization round (0-indexed)."""
        if self._scenario_num_days > 1:
            return self.current_day // self._scenario_num_days
        return self.current_day

    @property
    def is_complete(self) -> bool:
        return self.current_day >= self.total_days

    @property
    def optimization_summary(self) -> dict[str, Any]:
        """Summary of optimization attempts and failures across all days."""
        total = 0
        failed = 0
        failed_days: list[int] = []
        for d in self.days:
            if d.optimized:
                total += 1
                if d.optimization_failed:
                    failed += 1
                    failed_days.append(d.day_num)
        return {"total": total, "optimized": total - failed, "failed": failed, "failed_days": failed_days}

    @property
    def quality(self) -> str:
        """'clean' if no optimization failures, 'degraded' if any."""
        for d in self.days:
            if d.optimization_failed:
                return "degraded"
        return "clean"

    def should_optimize(self, day_num: int) -> bool:
        """Whether optimization should run after the given day number."""
        return (day_num + 1) % self.optimization_interval == 0

    # ── Simulation delegation (to SimulationRunner) ────────────────────

    def _build_ffi_config(self, seed: int) -> dict:
        """Build FFI config dict from current policies at given seed."""
        return self.sim.build_ffi_config(seed)

    def _inject_policies_into_orch(self):
        """Update all agent policies in the live Orchestrator after optimization."""
        self.sim.inject_policies_into_orch()

    def run_day(self) -> GameDay:
        """Run one day and commit immediately.

        Convenience wrapper around simulate_day() + commit_day().
        Both HTTP and WS paths get identical behavior including
        transaction history collection for bootstrap evaluation.
        """
        day = self.simulate_day()
        self.commit_day(day)
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
            all_events, balance_history, costs, per_agent_costs, total_cost, tick_events, cum_event_summary, cum_arrivals, cum_settled = self.sim.run_scenario_day(day_num)
            seed = self._base_seed + (day_num // self._scenario_num_days)
        else:
            seed = self._base_seed + day_num
            all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self.sim.run_single(seed)

        costs, per_agent_costs, total_cost, cost_std = self.sim.run_with_samples(
            seed, costs, per_agent_costs, total_cost, self.num_eval_samples,
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

        # Engine resets cost accumulators at each day boundary (engine.rs:2973),
        # so values from _extract_costs() are already per-day. No delta needed.
        # GameDay.__init__ sets day_* = raw values, which is correct.
        assert day.day_total_cost >= 0, (
            f"Negative total cost {day.day_total_cost} on day {day_num}"
        )
        for aid, cost in day.day_per_agent_costs.items():
            assert cost >= 0, (
                f"Negative cost {cost} for agent {aid} on day {day_num}"
            )

        return day

    def commit_day(self, day: GameDay):
        """Commit a previously simulated day to game state.

        Only call after confirming the day was successfully delivered
        to the client (e.g. WS send succeeded).
        """
        self.days.append(day)
        self._trim_old_day_events()

    def _trim_old_day_events(self) -> None:
        """Trim events/tick_events from all but the last day to free memory.

        Preserves cached settlement stats (_event_summary, _total_arrivals,
        _total_settled) so summary endpoints still work.
        """
        if len(self.days) < 2:
            return
        for d in self.days[:-1]:
            d.events = []
            d.tick_events = []

    def recompute_day_events(self, day_num: int) -> list[list[dict]]:
        """Recompute tick_events for a day from its seed and stored policy.

        Uses the policy recorded on the day (not current policy) to ensure
        deterministic replay matches the original simulation.
        Returns list of tick event lists (same shape as GameDay.tick_events).
        """
        if day_num < 0 or day_num >= len(self.days):
            raise ValueError(f"Day {day_num} not found (have {len(self.days)} days)")
        day = self.days[day_num]

        # Temporarily swap policies to the ones used on that day
        saved_policies = self.policies
        self.policies = copy.deepcopy(day.policies)
        self.sim.policies = self.policies
        try:
            seed = day.seed
            _all_events, _balance_history, _costs, _per_agent_costs, _total_cost, tick_events = self.sim.run_single(seed)
            return tick_events
        finally:
            self.policies = saved_policies
            self.sim.policies = saved_policies

    def save_day_to_duckdb(self, db_path: Path, day: GameDay):
        """Write a day's results to the DuckDB file."""
        _ser.save_day_to_duckdb(db_path, day)

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
        from .streaming_optimizer import stream_optimize, stream_optimize_with_retries

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
        DEFAULT_MAX_CONCURRENT = 3
        saw_rate_limit_this_round = False

        async def _run_all_agents(max_concurrent: int) -> tuple[bool, dict[str, dict]]:
            """Run optimization for all agents. Returns (success, results_dict)."""
            nonlocal saw_rate_limit_this_round
            _inner_results: dict[str, dict] = {}
            sequential = max_concurrent <= 1
            semaphore = asyncio.Semaphore(min(len(self.agent_ids), max_concurrent))
            agent_index = 0

            async def _optimize_one(aid: str, idx: int) -> None:
                nonlocal saw_rate_limit_this_round
                async with semaphore:
                    # Inter-agent delay in sequential mode
                    if sequential and idx > 0:
                        await _send({"type": "optimization_chunk", "text": "⏳ Rate limit mode — waiting 15s before next agent\n"})
                        await asyncio.sleep(15)
                    await _send({"type": "optimization_start", "day": last_day.day_num, "agent_id": aid})
                    result = None
                    try:
                        # Use retry wrapper when max_policy_proposals > 1
                        _use_retries = self.max_policy_proposals > 1
                        logger.warning("Optimization for %s: max_policy_proposals=%d, _use_retries=%s, bootstrap_gate=%s",
                                       aid, self.max_policy_proposals, _use_retries, self.bootstrap_gate is not None)
                        if _use_retries:
                            _optimizer = stream_optimize_with_retries(
                                aid, self.policies[aid], last_day, self.days, self.raw_yaml,
                                bootstrap_gate=self.bootstrap_gate,
                                max_proposals=self.max_policy_proposals,
                                constraint_preset=self.constraint_preset,
                                include_groups=self.include_groups,
                                exclude_groups=self.exclude_groups,
                                prompt_profile=self.prompt_profile,
                                model_override=self._optimization_model or None,
                            )
                        else:
                            _optimizer = stream_optimize(
                                aid, self.policies[aid], last_day, self.days, self.raw_yaml,
                                constraint_preset=self.constraint_preset,
                                include_groups=self.include_groups,
                                exclude_groups=self.exclude_groups,
                                prompt_profile=self.prompt_profile,
                                model_override=self._optimization_model or None,
                            )
                        async for event in _optimizer:
                            etype = event["type"]
                            if etype == "chunk":
                                await _send({"type": "optimization_chunk", "day": last_day.day_num, "agent_id": aid, "text": event["text"]})
                            elif etype == "rate_limited":
                                saw_rate_limit_this_round = True
                                if not self._rate_limited:
                                    self._rate_limited = True
                                    self._rate_limited_since = datetime.now(timezone.utc).isoformat()
                                    logger.warning("Rate limit detected for game %s — switching to sequential mode", self.game_id)
                                    await _send({"type": "rate_limit_mode", "concurrent": 1, "message": "Switching to sequential optimization (rate limit detected)"})
                            elif etype == "retry":
                                await _send({"type": "optimization_chunk", "day": last_day.day_num, "agent_id": aid, "text": f"\n⏳ Retrying ({event['attempt']}/{event['max_retries']}) in {event['delay']:.0f}s — {event['reason'][:80]}\n"})
                                await _send({"type": "agent_retry", "day": last_day.day_num, "agent_id": aid, "reason": event["reason"][:120], "attempt": event["attempt"], "max_retries": event["max_retries"]})
                            elif etype == "result":
                                result = event["data"]
                            elif etype == "error":
                                error_msg = event["message"]
                                logger.error("LLM optimization failed permanently for %s: %s", aid, error_msg)
                                await _send({"type": "agent_error", "day": last_day.day_num, "agent_id": aid, "message": error_msg, "fatal": True})
                                raise RuntimeError(f"LLM optimization failed for {aid}: {error_msg}")
                            elif etype in ("bootstrap_evaluating", "bootstrap_accepted", "bootstrap_rejected", "bootstrap_retry"):
                                await _send({**event, "day": last_day.day_num, "agent_id": aid})
                            elif etype == "messages":
                                pass  # Internal — not forwarded to client
                    except RuntimeError:
                        raise
                    except Exception as e:
                        logger.error("Streaming optimization failed for %s: %s", aid, e, exc_info=True)
                        await _send({"type": "agent_error", "day": last_day.day_num, "agent_id": aid, "message": str(e)[:200], "fatal": True})
                        raise RuntimeError(f"LLM optimization failed for {aid}: {e}")
                    if result is None:
                        await _send({"type": "agent_error", "day": last_day.day_num, "agent_id": aid, "message": "No result from LLM after all retries", "fatal": True})
                        raise RuntimeError(f"LLM optimization produced no result for {aid}")
                    if not _use_retries and result.get("new_policy"):
                        result = self._run_real_bootstrap(aid, last_day, result)
                    await _send({"type": "optimization_complete", "day": last_day.day_num, "agent_id": aid, "data": result})
                    _inner_results[aid] = result

            if sequential:
                # Run agents one by one to respect rate limits
                for idx, aid in enumerate(self.agent_ids):
                    try:
                        await _optimize_one(aid, idx)
                    except Exception:
                        return False, {}
            else:
                tasks = [asyncio.create_task(_optimize_one(aid, idx)) for idx, aid in enumerate(self.agent_ids)]
                gather_results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in gather_results:
                    if isinstance(r, Exception):
                        return False, {}
            return True, _inner_results

        _par_start = _time.monotonic()

        # First attempt — use sequential if previously rate-limited
        first_concurrent = 1 if self._rate_limited else DEFAULT_MAX_CONCURRENT
        success, results = await _run_all_agents(first_concurrent)

        if not success:
            # Retry after 120s cooldown — ALWAYS sequential
            await _send({"type": "optimization_chunk", "text": "⏳ Rate limit cooldown — waiting 120s before retry..."})
            logger.warning("First optimization attempt failed for game %s, waiting 120s before retry", self.game_id)
            for countdown in range(120, 0, -30):
                await asyncio.sleep(30)
                if countdown > 30:
                    await _send({"type": "optimization_chunk", "text": f"⏳ Retry in {countdown - 30}s..."})

            await _send({"type": "optimization_chunk", "text": "🔄 Retrying optimization for all agents (sequential)..."})
            success, results = await _run_all_agents(1)

            if not success:
                # Second failure — stall
                self.stalled = True
                self.stall_reason = "optimization_failed_after_retry"
                for a in self.agent_ids:
                    failure_record = {
                        "day_num": last_day.day_num,
                        "failed": True,
                        "failure_reason": "Optimization failed after retry with 120s cooldown",
                        "reasoning": "Optimization failed after retry",
                        "accepted": False,
                        "new_policy": None,
                        "old_policy": copy.deepcopy(self.policies[a]),
                        "old_fraction": self.policies[a].get("parameters", {}).get("initial_liquidity_fraction"),
                        "new_fraction": None,
                        "mock": False,
                    }
                    self.reasoning_history[a].append(failure_record)
                await _send({
                    "type": "experiment_error",
                    "message": "Experiment stalled: LLM optimization failed after retry with 120s cooldown. Use resume to continue.",
                    "fatal": True,
                    "stalled": True,
                    "stall_reason": self.stall_reason,
                })
                return {}

        _par_elapsed = _time.monotonic() - _par_start
        logger.warning(
            "Optimization for %d agents completed in %.1fs (concurrent=%d)",
            len(self.agent_ids), _par_elapsed, first_concurrent,
        )

        # Recover to parallel mode if a full round succeeded with no 429s
        if success and not saw_rate_limit_this_round:
            if self._rate_limited:
                self._rate_limited = False
                self._rate_limited_since = None
                logger.info("No rate limits seen — recovering to parallel optimization for game %s", self.game_id)
                await _send({"type": "rate_limit_mode", "concurrent": DEFAULT_MAX_CONCURRENT, "message": "Recovered to parallel optimization"})

        for aid in self.agent_ids:
            if aid in results:
                results[aid]["day_num"] = last_day.day_num
                self._store_prompt(last_day, aid, results[aid])
                self._apply_result(aid, results[aid])

        return results

    def _run_real_bootstrap(self, aid: str, day: 'GameDay', result: dict) -> dict:
        """Run bootstrap evaluation via BootstrapGate."""
        return self.bootstrap_gate.evaluate(aid, day, result)

    def _store_prompt(self, day: 'GameDay', aid: str, result: dict) -> None:
        """Store structured prompt data from optimization result on the day."""
        sp = result.get("structured_prompt")
        if sp:
            day.optimization_prompts[aid] = sp
        # Store full result for inspection API
        day.optimization_results[aid] = result

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
            self._cap_reasoning_history()

    def _cap_reasoning_history(self, max_entries: int = 10) -> None:
        """Keep only the last max_entries reasoning records per agent."""
        for aid in self.agent_ids:
            hist = self.reasoning_history.get(aid, [])
            if len(hist) > max_entries:
                self.reasoning_history[aid] = hist[-max_entries:]

    def get_state(self) -> dict[str, Any]:
        return _ser.get_game_state(self)

    # ── Checkpoint persistence ───────────────────────────────────────

    def to_checkpoint(self, scenario_id: str = "", uid: str = "") -> dict[str, Any]:
        """Serialize full game state to a checkpoint dict."""
        return _ser.game_to_checkpoint(self, scenario_id, uid)

    @classmethod
    def from_checkpoint(cls, data: dict) -> 'Game':
        """Reconstruct a Game from a checkpoint dict."""
        return _ser.game_from_checkpoint(data)


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
