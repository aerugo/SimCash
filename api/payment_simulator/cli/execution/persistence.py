"""
Centralized persistence management for simulation execution.

Eliminates duplication of persistence logic across 4 execution modes.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Optional

from payment_simulator._core import Orchestrator


# Import existing persistence helpers from run.py module
# These will be moved to persistence package in Phase 5 cleanup
from payment_simulator.cli.commands.run import (
    _persist_day_data,
    _persist_simulation_metadata,
)
from payment_simulator.persistence.writers import (
    write_policy_snapshots,
    write_policy_decisions_batch,
    write_tick_agent_states_batch,
    write_tick_queue_snapshots_batch,
)


class PersistenceManager:
    """Manages all persistence operations during simulation execution.

    Encapsulates database operations to ensure consistent persistence
    across all execution modes (normal, verbose, stream, event_stream).

    This class eliminates the 4-way duplication of persistence logic
    where each mode had its own persistence calls, leading to bugs like
    event_stream mode missing EOD persistence.

    Attributes:
        db_manager: Database manager instance
        sim_id: Simulation ID for this run
        full_replay: Whether to capture per-tick data for replay
        replay_buffers: Buffers for full replay data (if enabled)

    Usage:
        db_manager = DatabaseManager("simulation_data.db")
        persistence = PersistenceManager(db_manager, "sim-abc123", full_replay=True)

        # At start
        persistence.persist_initial_snapshots(orch)

        # Each tick
        persistence.on_tick_complete(tick, orch)

        # End of day
        if is_eod:
            persistence.on_day_complete(day, orch)

        # End of simulation
        persistence.persist_final_metadata(...
)
    """

    def __init__(
        self,
        db_manager: Any,
        sim_id: str,
        full_replay: bool = False
    ):
        """Initialize persistence manager.

        Args:
            db_manager: DatabaseManager instance
            sim_id: Simulation ID
            full_replay: Enable per-tick data capture for full replay

        Example:
            >>> db = DatabaseManager("test.db")
            >>> pm = PersistenceManager(db, "sim-123", full_replay=False)
        """
        self.db_manager = db_manager
        self.sim_id = sim_id
        self.full_replay = full_replay

        # Initialize replay buffers if full replay mode
        if full_replay:
            self.replay_buffers = {
                "policy_decisions": [],
                "agent_states": [],
                "queue_snapshots": [],
            }
            # Track previous state for delta calculations
            self._prev_balances: dict[str, int] = {}
            self._prev_costs: dict[str, dict[str, int]] = {}
        else:
            self.replay_buffers = None

    def persist_initial_snapshots(self, orch: Orchestrator) -> None:
        """Persist initial policy snapshots at t=0.

        All modes should persist policy configurations at simulation start
        for audit trail and reproducibility.

        Args:
            orch: Orchestrator instance

        Example:
            >>> persistence.persist_initial_snapshots(orch)
            # Writes policy snapshots to policy_snapshots table
        """
        policies = orch.get_agent_policies()
        snapshots = []

        for policy in policies:
            policy_json = json.dumps(policy["policy_config"], sort_keys=True)
            policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

            snapshots.append({
                "simulation_id": self.sim_id,
                "agent_id": policy["agent_id"],
                "snapshot_day": 0,
                "snapshot_tick": 0,
                "policy_hash": policy_hash,
                "policy_json": policy_json,
                "created_by": "init",
            })

        if snapshots:
            write_policy_snapshots(self.db_manager.conn, snapshots)

    def on_tick_complete(self, tick: int, orch: Orchestrator) -> None:
        """Called after each tick completes (for full replay buffering).

        If full_replay is enabled, buffers per-tick data for later persistence.
        Otherwise, this is a no-op.

        Args:
            tick: Tick number
            orch: Orchestrator instance

        Example:
            >>> for tick in range(100):
            ...     result = orch.tick()
            ...     persistence.on_tick_complete(tick, orch)
        """
        if not self.full_replay:
            return

        # Calculate day for this tick
        # Note: ticks_per_day should be passed in initialization for proper calculation
        # For now, we'll get it from the tick context
        events = orch.get_tick_events(tick)
        agent_ids = orch.get_agent_ids()

        # Determine day from tick (assumes we have access to ticks_per_day)
        # This will be refined in implementation
        day = tick // 10  # Placeholder - will be fixed when integrating

        # 1. Buffer policy decision events
        policy_events = [
            e for e in events
            if e.get("event_type") in ["PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"]
        ]

        for event in policy_events:
            self.replay_buffers["policy_decisions"].append({
                "simulation_id": self.sim_id,
                "agent_id": event["agent_id"],
                "tick": tick,
                "day": day,
                "decision_type": event["event_type"].replace("Policy", "").lower(),
                "tx_id": event["tx_id"],
                "reason": event.get("reason"),
                "num_splits": event.get("num_splits"),
                "child_tx_ids": (
                    json.dumps(event.get("child_ids", []))
                    if event.get("child_ids")
                    else None
                ),
            })

        # 2. Buffer agent state snapshots
        for agent_id in agent_ids:
            current_balance = orch.get_agent_balance(agent_id)
            unsecured_cap = orch.get_agent_unsecured_cap(agent_id)
            costs = orch.get_agent_accumulated_costs(agent_id)
            collateral = orch.get_agent_collateral_posted(agent_id) or 0

            # Calculate balance change (defaults to 0 for first tick, so change = opening balance)
            prev_balance = self._prev_balances.get(agent_id, 0)
            balance_change = current_balance - prev_balance
            self._prev_balances[agent_id] = current_balance

            # Calculate cost deltas
            prev_costs = self._prev_costs.get(agent_id, {})

            self.replay_buffers["agent_states"].append({
                "simulation_id": self.sim_id,
                "agent_id": agent_id,
                "tick": tick,
                "day": day,
                "balance": current_balance,
                "balance_change": balance_change,
                "unsecured_cap": unsecured_cap,
                "posted_collateral": collateral,
                "liquidity_cost": costs["liquidity_cost"],
                "delay_cost": costs["delay_cost"],
                "collateral_cost": costs["collateral_cost"],
                "penalty_cost": costs["deadline_penalty"],
                "split_friction_cost": costs["split_friction_cost"],
                "liquidity_cost_delta": costs["liquidity_cost"] - prev_costs.get("liquidity_cost", 0),
                "delay_cost_delta": costs["delay_cost"] - prev_costs.get("delay_cost", 0),
                "collateral_cost_delta": costs["collateral_cost"] - prev_costs.get("collateral_cost", 0),
                "penalty_cost_delta": costs["deadline_penalty"] - prev_costs.get("deadline_penalty", 0),
                "split_friction_cost_delta": costs["split_friction_cost"] - prev_costs.get("split_friction_cost", 0),
            })

            # Update previous costs
            self._prev_costs[agent_id] = costs

        # 3. Buffer queue snapshots
        for agent_id in agent_ids:
            # Queue 1 (agent's internal queue)
            queue1_contents = orch.get_agent_queue1_contents(agent_id)
            for position, tx_id in enumerate(queue1_contents):
                self.replay_buffers["queue_snapshots"].append({
                    "simulation_id": self.sim_id,
                    "agent_id": agent_id,
                    "tick": tick,
                    "queue_type": "queue1",
                    "position": position,
                    "tx_id": tx_id,
                })

        # RTGS queue (central queue)
        rtgs_contents = orch.get_rtgs_queue_contents()
        for position, tx_id in enumerate(rtgs_contents):
            tx = orch.get_transaction_details(tx_id)
            if tx:
                self.replay_buffers["queue_snapshots"].append({
                    "simulation_id": self.sim_id,
                    "agent_id": tx["sender_id"],
                    "tick": tick,
                    "queue_type": "rtgs",
                    "position": position,
                    "tx_id": tx_id,
                })

    def on_day_complete(self, day: int, orch: Orchestrator) -> None:
        """Called at end of each day.

        Persists all EOD data (transactions, agent metrics, collateral events, etc.)
        and flushes replay buffers if full_replay mode is enabled.

        This ensures ALL modes persist data consistently at EOD.

        Args:
            day: Day number
            orch: Orchestrator instance

        Example:
            >>> if is_end_of_day(tick):
            ...     persistence.on_day_complete(day, orch)
        """
        # Always persist EOD data (ALL modes)
        _persist_day_data(orch, self.db_manager, self.sim_id, day, quiet=False)

        # If full replay mode, flush buffers to database
        if self.full_replay and self.replay_buffers:
            # Write policy decisions
            if self.replay_buffers["policy_decisions"]:
                write_policy_decisions_batch(
                    self.db_manager.conn,
                    self.replay_buffers["policy_decisions"]
                )

            # Write agent states
            if self.replay_buffers["agent_states"]:
                write_tick_agent_states_batch(
                    self.db_manager.conn,
                    self.replay_buffers["agent_states"]
                )

            # Write queue snapshots
            if self.replay_buffers["queue_snapshots"]:
                write_tick_queue_snapshots_batch(
                    self.db_manager.conn,
                    self.replay_buffers["queue_snapshots"]
                )

            # Clear buffers for next day
            self.replay_buffers["policy_decisions"] = []
            self.replay_buffers["agent_states"] = []
            self.replay_buffers["queue_snapshots"] = []

    def persist_final_metadata(
        self,
        config_path: Path | str,
        config_dict: dict[str, Any],
        ffi_dict: dict[str, Any],
        agent_ids: list[str],
        total_arrivals: int,
        total_settlements: int,
        total_costs: int,
        duration: float,
        orch: Orchestrator
    ) -> None:
        """Persist final simulation metadata.

        Called once at the end of simulation to write metadata tables
        (simulations, simulation_runs, simulation_events).

        CRITICAL: Also flushes any remaining replay buffers to ensure
        all tick-level data is persisted (e.g., if simulation ends mid-day).

        Args:
            config_path: Path to configuration file
            config_dict: Configuration dictionary
            ffi_dict: FFI configuration dictionary
            agent_ids: List of agent IDs
            total_arrivals: Total number of arrivals
            total_settlements: Total number of settlements
            total_costs: Total costs in cents
            duration: Simulation duration in seconds
            orch: Orchestrator instance

        Example:
            >>> persistence.persist_final_metadata(
            ...     config_path="scenario.yaml",
            ...     config_dict={...},
            ...     ffi_dict={...},
            ...     agent_ids=["BANK_A", "BANK_B"],
            ...     total_arrivals=1000,
            ...     total_settlements=950,
            ...     total_costs=50000,
            ...     duration=2.5,
            ...     orch=orch
            ... )
        """
        # CRITICAL FIX: Flush remaining replay buffers before finalizing
        # This ensures tick-level data after the last EOD is persisted
        if self.full_replay and self.replay_buffers:
            # Write policy decisions
            if self.replay_buffers["policy_decisions"]:
                write_policy_decisions_batch(
                    self.db_manager.conn,
                    self.replay_buffers["policy_decisions"]
                )

            # Write agent states
            if self.replay_buffers["agent_states"]:
                write_tick_agent_states_batch(
                    self.db_manager.conn,
                    self.replay_buffers["agent_states"]
                )

            # Write queue snapshots
            if self.replay_buffers["queue_snapshots"]:
                write_tick_queue_snapshots_batch(
                    self.db_manager.conn,
                    self.replay_buffers["queue_snapshots"]
                )

            # Clear buffers
            self.replay_buffers["policy_decisions"] = []
            self.replay_buffers["agent_states"] = []
            self.replay_buffers["queue_snapshots"] = []

        _persist_simulation_metadata(
            self.db_manager,
            self.sim_id,
            Path(config_path),
            config_dict,
            ffi_dict,
            agent_ids,
            total_arrivals,
            total_settlements,
            total_costs,
            duration,
            orch,
            quiet=False
        )
