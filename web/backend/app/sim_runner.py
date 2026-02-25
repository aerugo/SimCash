"""Simulation execution: FFI config building, single/multi-seed runs, scenario days."""
from __future__ import annotations

import copy
import json
import math
import logging
import concurrent.futures
from typing import Any

from payment_simulator._core import Orchestrator  # type: ignore
from payment_simulator.config.schemas import SimulationConfig  # type: ignore

logger = logging.getLogger(__name__)


class SimulationRunner:
    """Runs simulations against the Rust engine.

    Holds references to scenario config and policies (shared with Game).
    Manages the persistent Orchestrator for intra-scenario mode.
    """

    def __init__(
        self,
        raw_yaml: dict,
        agent_ids: list[str],
        policies: dict[str, dict],
        ticks_per_day: int,
        scenario_num_days: int,
        base_seed: int,
    ):
        self.raw_yaml = raw_yaml
        self.agent_ids = agent_ids
        self.policies = policies  # shared reference with Game
        self.ticks_per_day = ticks_per_day
        self.scenario_num_days = scenario_num_days
        self.base_seed = base_seed

        # Reference to completed days (set by Game for fast-forward replay)
        self._completed_days: list[Any] = []

        # Intra-scenario state
        self._live_orch: Any = None
        self._day_tick_offset: int = 0
        self._round_cumulative_arrivals: dict[str, int] = {}
        self._round_cumulative_settled: dict[str, int] = {}

    def build_ffi_config(self, seed: int) -> dict:
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

    def run_single(self, seed: int) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]]]:
        """Run one simulation with current policies at given seed.

        Returns (events, balance_history, costs, per_agent_costs, total_cost, tick_events).
        """
        ffi_config = self.build_ffi_config(seed)
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

        costs, per_agent_costs, total_cost = self._extract_costs(orch)
        return all_events, balance_history, costs, per_agent_costs, total_cost, tick_events

    def run_cost_only(self, seed: int) -> dict[str, dict]:
        """Run simulation and return only costs (thread-safe, GIL-releasing)."""
        ffi_config = self.build_ffi_config(seed)
        orch = Orchestrator.new(ffi_config)
        ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]
        result_json = orch.run_and_get_all_costs(ticks)
        return json.loads(result_json)

    def run_scenario_day(self, current_day: int) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]], dict[str, dict[str, int]], int, int]:
        """Run one scenario day on the persistent Orchestrator.

        Returns: (events, balance_history, costs, per_agent_costs, total_cost,
                  tick_events, cumulative_event_summary, cumulative_arrivals, cumulative_settled)
        """
        if self._live_orch is None:
            round_num = current_day // self.scenario_num_days
            seed = self.base_seed + round_num
            scenario_day_index = current_day % self.scenario_num_days
            needs_replay = scenario_day_index > 0 and self._completed_days

            if needs_replay:
                # Build FFI config with round's FIRST day's policies (not current)
                round_start_day = current_day - scenario_day_index
                first_day_policies = None
                for d in self._completed_days:
                    if d.day_num == round_start_day:
                        first_day_policies = d.policies
                        break
                if first_day_policies:
                    saved_policies = self.policies
                    self.policies = first_day_policies
                    ffi_config = self.build_ffi_config(seed)
                    self.policies = saved_policies
                else:
                    ffi_config = self.build_ffi_config(seed)
            else:
                ffi_config = self.build_ffi_config(seed)

            self._live_orch = Orchestrator.new(ffi_config)
            self._day_tick_offset = 0
            self._round_cumulative_arrivals = {}
            self._round_cumulative_settled = {}

            if needs_replay:
                self._fast_forward_replay(current_day, scenario_day_index)

        all_events: list[dict] = []
        tick_events: list[list[dict]] = []
        balance_history: dict[str, list] = {aid: [] for aid in self.agent_ids}

        for t in range(self.ticks_per_day):
            tick = self._day_tick_offset + t
            self._live_orch.tick()
            events = self._live_orch.get_tick_events(tick)
            tick_event_list = [dict(e) for e in events]
            all_events.extend(tick_event_list)
            tick_events.append(tick_event_list)
            for aid in self.agent_ids:
                balance_history[aid].append(self._live_orch.get_agent_balance(aid) or 0)

        self._day_tick_offset += self.ticks_per_day

        costs, per_agent_costs, total_cost = self._extract_costs(self._live_orch)

        # Update cumulative settlement stats
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

        # End of round — destroy Orchestrator
        scenario_day_index = current_day % self.scenario_num_days
        if scenario_day_index == self.scenario_num_days - 1:
            self._live_orch = None
            self._day_tick_offset = 0

        return all_events, balance_history, costs, per_agent_costs, total_cost, tick_events, cum_summary, cum_arrivals, cum_settled

    def run_with_samples(
        self,
        seed: int,
        costs: dict[str, dict],
        per_agent_costs: dict[str, int],
        total_cost: int,
        num_eval_samples: int,
    ) -> tuple[dict[str, dict], dict[str, int], int, dict[str, int]]:
        """Average costs over multiple seeds.

        Returns (costs, per_agent_costs, total_cost, cost_std_per_agent).
        """
        if num_eval_samples <= 1:
            return costs, per_agent_costs, total_cost, {aid: 0 for aid in self.agent_ids}

        all_per_agent: dict[str, list[int]] = {aid: [per_agent_costs[aid]] for aid in self.agent_ids}
        all_costs: dict[str, list[dict]] = {aid: [costs[aid]] for aid in self.agent_ids}

        extra_seeds = [seed + i * 1000 for i in range(1, num_eval_samples)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(extra_seeds), 8)) as pool:
            futures = {s: pool.submit(self.run_cost_only, s) for s in extra_seeds}
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

        n = num_eval_samples
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

    def _fast_forward_replay(self, current_day: int, scenario_day_index: int) -> None:
        """Replay completed days in the current round to rebuild Orchestrator state.

        When a container dies mid-round and the game is restored from checkpoint,
        the Orchestrator is fresh. We replay all completed days in this round
        (ticking and injecting policies between days) so the Orchestrator reaches
        the correct state for the next day.

        Args:
            current_day: The day about to be simulated.
            scenario_day_index: How many days into the current round we are (1-based offset).
        """
        round_start_day = current_day - scenario_day_index
        logger.info(
            "Fast-forward replay: replaying %d days (days %d-%d) for round starting at day %d",
            scenario_day_index, round_start_day, current_day - 1, round_start_day,
        )

        # The Orchestrator was initialized with day 0's policies via build_ffi_config.
        # We tick through each completed day, then inject the NEXT day's policies
        # (the result of optimization after that day).
        for replay_offset in range(scenario_day_index):
            replay_day_num = round_start_day + replay_offset
            completed_day = None
            for d in self._completed_days:
                if d.day_num == replay_day_num:
                    completed_day = d
                    break

            if completed_day is None:
                logger.warning("Fast-forward: no completed day data for day %d, cannot replay", replay_day_num)
                break

            # Tick through this day (discard events — we only need the state change)
            for t in range(self.ticks_per_day):
                self._live_orch.tick()

            self._day_tick_offset += self.ticks_per_day

            # Rebuild cumulative settlement stats from the completed day
            if hasattr(completed_day, '_event_summary') and completed_day._event_summary:
                for aid, stats in completed_day._event_summary.items():
                    self._round_cumulative_arrivals[aid] = (
                        self._round_cumulative_arrivals.get(aid, 0) + stats.get("arrivals", 0)
                    )
                    self._round_cumulative_settled[aid] = (
                        self._round_cumulative_settled.get(aid, 0) + stats.get("settled", 0)
                    )

            # Inject the NEXT day's policies (optimization result after this day).
            # For the last replayed day, the next day is the one about to be
            # simulated — inject current self.policies for that.
            next_day_num = replay_day_num + 1
            if next_day_num < current_day:
                next_completed = None
                for d in self._completed_days:
                    if d.day_num == next_day_num:
                        next_completed = d
                        break
                if next_completed:
                    for aid in self.agent_ids:
                        next_policy = next_completed.policies.get(aid)
                        if next_policy:
                            self._live_orch.update_agent_policy(aid, json.dumps(next_policy))
            else:
                # Last replayed day — inject current policies for upcoming simulation
                for aid in self.agent_ids:
                    self._live_orch.update_agent_policy(aid, json.dumps(self.policies[aid]))

        logger.info("Fast-forward replay complete: tick_offset=%d", self._day_tick_offset)

    def inject_policies_into_orch(self) -> None:
        """Update all agent policies in the live Orchestrator after optimization."""
        if self._live_orch is None:
            return
        for aid in self.agent_ids:
            policy_json = json.dumps(self.policies[aid])
            self._live_orch.update_agent_policy(aid, policy_json)

    def _extract_costs(self, orch: Any) -> tuple[dict[str, dict], dict[str, int], int]:
        """Extract cost breakdown from an Orchestrator instance."""
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
        return costs, per_agent_costs, total_cost
