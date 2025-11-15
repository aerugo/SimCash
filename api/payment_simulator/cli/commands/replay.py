"""Replay command - Load and replay simulations from database with verbose logging.

This command enables replaying a specific tick range from a persisted simulation,
producing identical verbose output to the original run.
"""

import json
import time
import typer
import yaml
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

from payment_simulator.cli.output import (
    log_info,
    log_success,
    log_error,
    log_tick_start,
    log_transaction_arrivals,
    log_settlement_details,
    log_agent_queues_detailed,
    log_policy_decisions,
    log_collateral_activity,
    log_cost_breakdown,
    log_agent_state_from_db,
    log_cost_breakdown_from_db,
    log_lsm_cycle_visualization,
    log_end_of_day_event,
    log_end_of_day_statistics,
    log_tick_summary,
    output_json,
    console,
)
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.queries import (
    get_simulation_summary,
    get_policy_decisions_by_tick,
    get_tick_agent_states,
    get_tick_queue_snapshots,
)
from payment_simulator.persistence.event_queries import get_simulation_events
from payment_simulator.config import SimulationConfig
from payment_simulator._core import Orchestrator


# ============================================================================
# Event Reconstruction Helpers
# ============================================================================


def _reconstruct_arrival_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct arrival events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'Arrival'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "Arrival", "details": "{...}", ...}]
        >>> arrivals = _reconstruct_arrival_events_from_simulation_events(events)
        >>> arrivals[0]["event_type"]
        'Arrival'
    """
    result = []
    for event in events:
        details = event["details"]  # Already parsed by get_simulation_events
        result.append({
            "event_type": "Arrival",
            "tx_id": event["tx_id"],
            "sender_id": details.get("sender_id"),
            "receiver_id": details.get("receiver_id"),
            "amount": details.get("amount"),
            "priority": details.get("priority", 5),  # Default to 5 (standard priority)
            "deadline_tick": details.get("deadline") or details.get("deadline_tick"),  # FFI uses "deadline"
            "is_divisible": details.get("is_divisible", False),  # Include is_divisible
        })
    return result


def _reconstruct_settlement_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct settlement events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'Settlement'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "Settlement", "details": "...", ...}]
        >>> settlements = _reconstruct_settlement_events_from_simulation_events(events)
        >>> settlements[0]["event_type"]
        'Settlement'
    """
    result = []
    for event in events:
        details = event["details"]  # Already parsed by get_simulation_events
        result.append({
            "event_type": "Settlement",
            "tx_id": event["tx_id"],
            "sender_id": details.get("sender_id"),
            "receiver_id": details.get("receiver_id"),
            "amount": details.get("amount"),
        })
    return result


def _reconstruct_arrival_events(arrivals: list[dict]) -> list[dict]:
    """Reconstruct arrival events from database transaction records.

    Args:
        arrivals: List of transaction records with arrival_tick = current tick

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> arrivals = [{"tx_id": "abc", "sender_id": "A", ...}]
        >>> events = _reconstruct_arrival_events(arrivals)
        >>> events[0]["event_type"]
        'Arrival'
    """
    return [
        {
            "event_type": "Arrival",
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount"],
            "priority": tx["priority"],
            "deadline_tick": tx["deadline_tick"],
        }
        for tx in arrivals
    ]


def _reconstruct_settlement_events(settlements: list[dict]) -> list[dict]:
    """Reconstruct settlement events from database transaction records.

    Args:
        settlements: List of transaction records with settlement_tick = current tick

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> settlements = [{"tx_id": "abc", "sender_id": "A", ...}]
        >>> events = _reconstruct_settlement_events(settlements)
        >>> events[0]["event_type"]
        'Settlement'
    """
    return [
        {
            "event_type": "Settlement",
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount_settled"],
        }
        for tx in settlements
    ]


def _reconstruct_lsm_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct LSM events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'LsmBilateralOffset' or 'LsmCycleSettlement'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "LsmBilateralOffset", "details": {...}}]
        >>> lsm_events = _reconstruct_lsm_events_from_simulation_events(events)
        >>> lsm_events[0]["event_type"]
        'LsmBilateralOffset'
    """
    result = []
    for event in events:
        event_type = event["event_type"]
        details = event.get("details", {})

        if event_type == "LsmBilateralOffset":
            result.append({
                "event_type": "LsmBilateralOffset",
                "agent_a": details.get("agent_a", "unknown"),
                "agent_b": details.get("agent_b", "unknown"),
                "tx_id_a": details.get("tx_id_a", ""),
                "tx_id_b": details.get("tx_id_b", ""),
                "tx_ids": details.get("tx_ids", []),  # CRITICAL: Extract tx_ids for settlement counting
                "amount_a": details.get("amount_a", 0),
                "amount_b": details.get("amount_b", 0),
                "amount": details.get("amount", details.get("amount_a", 0) + details.get("amount_b", 0)),
            })
        elif event_type == "LsmCycleSettlement":
            result.append({
                "event_type": "LsmCycleSettlement",
                "agent_ids": details.get("agent_ids", []),
                "tx_ids": details.get("tx_ids", []),
                "tx_amounts": details.get("tx_amounts", []),
                "settled_value": details.get("settled_value", 0),
                "net_positions": details.get("net_positions", []),
                "total_value": details.get("total_value", 0),
                "max_net_outflow": details.get("max_net_outflow", 0),
                "max_net_outflow_agent": details.get("max_net_outflow_agent", ""),
            })

    return result


def _reconstruct_collateral_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct collateral events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'CollateralPost' or 'CollateralWithdraw'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "CollateralPost", "agent_id": "BANK_A", "details": {...}}]
        >>> collateral = _reconstruct_collateral_events_from_simulation_events(events)
        >>> collateral[0]["event_type"]
        'CollateralPost'
    """
    result = []
    for event in events:
        event_type = event["event_type"]
        details = event.get("details", {})

        if event_type in ["CollateralPost", "CollateralWithdraw"]:
            result.append({
                "event_type": event_type,
                "agent_id": event.get("agent_id") or details.get("agent_id"),
                "amount": details.get("amount", 0),
                "reason": details.get("reason", ""),
                "new_total": details.get("new_total", 0),
            })
    return result


def _reconstruct_cost_accrual_events(events: list[dict]) -> list[dict]:
    """Reconstruct cost accrual events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'CostAccrual'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "CostAccrual", "agent_id": "BANK_A", "details": {"costs": {...}}}]
        >>> cost_events = _reconstruct_cost_accrual_events(events)
        >>> cost_events[0]["event_type"]
        'CostAccrual'
    """
    result = []
    for event in events:
        if event["event_type"] == "CostAccrual":
            details = event.get("details", {})
            # Cost breakdown is in details.costs
            costs = details.get("costs", {})

            result.append({
                "event_type": "CostAccrual",
                "agent_id": event.get("agent_id") or details.get("agent_id"),
                "costs": costs,
            })
    return result


def _reconstruct_scenario_events_from_simulation_events(events: list[dict]) -> list[dict]:
    """Reconstruct scenario events from simulation_events table.

    Args:
        events: List of simulation event records with event_type = 'ScenarioEventExecuted'

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"event_type": "ScenarioEventExecuted", "details": {...}}]
        >>> scenario_events = _reconstruct_scenario_events_from_simulation_events(events)
        >>> scenario_events[0]["event_type"]
        'ScenarioEventExecuted'
    """
    result = []
    for event in events:
        if event["event_type"] == "ScenarioEventExecuted":
            outer_details = event.get("details", {})
            scenario_event_type = outer_details.get("scenario_event_type", "Unknown")

            # Parse inner details JSON
            details_json = outer_details.get("details_json", "{}")
            if isinstance(details_json, str):
                inner_details = json.loads(details_json)
            else:
                inner_details = details_json

            # Build event dict with all fields
            result.append({
                "event_type": "ScenarioEventExecuted",
                "scenario_event_type": scenario_event_type,
                "tick": event["tick"],
                "details": inner_details,
            })
    return result


def _reconstruct_state_register_events(events: list[dict]) -> list[dict]:
    """Reconstruct state register events from simulation_events table.

    Phase 4.6: Decision Path Auditing - state register updates with decision paths.

    Args:
        events: List of simulation event records with event_type = 'StateRegisterSet'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "StateRegisterSet":
            details = event.get("details", {})
            result.append({
                "event_type": "StateRegisterSet",
                "tick": event["tick"],
                "agent_id": event.get("agent_id"),
                "register_key": details.get("register_key"),
                "old_value": details.get("old_value"),
                "new_value": details.get("new_value"),
                "reason": details.get("reason"),
                "decision_path": details.get("decision_path"),  # Phase 4.6
            })
    return result


def _reconstruct_budget_events(events: list[dict]) -> list[dict]:
    """Reconstruct bank budget events from simulation_events table.

    Phase 3.3: Bank-Level Budgets - SetReleaseBudget actions.

    Args:
        events: List of simulation event records with event_type = 'BankBudgetSet'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "BankBudgetSet":
            details = event.get("details", {})
            result.append({
                "event_type": "BankBudgetSet",
                "tick": event["tick"],
                "agent_id": event.get("agent_id"),
                "max_value": details.get("max_value"),
                "focus_counterparties": details.get("focus_counterparties"),
                "max_per_counterparty": details.get("max_per_counterparty"),
            })
    return result


def _reconstruct_collateral_timer_events(events: list[dict]) -> list[dict]:
    """Reconstruct collateral timer withdrawal events from simulation_events table.

    Phase 3.4: Collateral Timers - automatic withdrawal when timer expires.

    Args:
        events: List of simulation event records with event_type = 'CollateralTimerWithdrawn'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "CollateralTimerWithdrawn":
            details = event.get("details", {})
            result.append({
                "event_type": "CollateralTimerWithdrawn",
                "tick": event["tick"],
                "agent_id": event.get("agent_id"),
                "amount": details.get("amount"),
                "original_reason": details.get("original_reason"),
                "posted_at_tick": details.get("posted_at_tick"),
            })
    return result


def _reconstruct_transaction_went_overdue_events(events: list[dict]) -> list[dict]:
    """Reconstruct TransactionWentOverdue events from simulation_events table.

    Phase 4: Replay Identity - missing event types fix.

    Args:
        events: List of simulation event records with event_type = 'TransactionWentOverdue'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "TransactionWentOverdue":
            details = event.get("details", {})
            # Merge top-level fields with details for display functions
            result.append({
                "event_type": "TransactionWentOverdue",
                "tick": event["tick"],
                "tx_id": event.get("tx_id"),
                "sender_id": details.get("sender_id"),
                "receiver_id": details.get("receiver_id"),
                "amount": details.get("amount"),
                "remaining_amount": details.get("remaining_amount"),
                "deadline_tick": details.get("deadline_tick"),
                "ticks_overdue": details.get("ticks_overdue"),
                "deadline_penalty_cost": details.get("deadline_penalty_cost"),
            })
    return result


def _reconstruct_queued_rtgs_events(events: list[dict]) -> list[dict]:
    """Reconstruct QueuedRtgs events from simulation_events table.

    Phase 4: Replay Identity - missing event types fix.

    Args:
        events: List of simulation event records with event_type = 'QueuedRtgs'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "QueuedRtgs":
            details = event.get("details", {})
            # Merge top-level fields with details for display functions
            result.append({
                "event_type": "QueuedRtgs",
                "tick": event["tick"],
                "tx_id": event.get("tx_id"),
                "sender_id": details.get("sender_id"),
                # Add other fields as needed by display logic
            })
    return result


def _reconstruct_rtgs_immediate_settlement_events(events: list[dict]) -> list[dict]:
    """Reconstruct RtgsImmediateSettlement events from simulation_events table.

    CRITICAL FIX (Discrepancy #3): These events are needed for "RTGS Immediate" display block.

    Args:
        events: List of simulation event records with event_type = 'RtgsImmediateSettlement'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "RtgsImmediateSettlement":
            details = event.get("details", {})
            result.append({
                "event_type": "RtgsImmediateSettlement",
                "tick": event["tick"],
                "tx_id": event.get("tx_id"),
                "sender": details.get("sender"),
                "receiver": details.get("receiver"),
                "amount": details.get("amount", 0),
                "sender_balance_before": details.get("sender_balance_before"),
                "sender_balance_after": details.get("sender_balance_after"),
            })
    return result


def _reconstruct_queue2_liquidity_release_events(events: list[dict]) -> list[dict]:
    """Reconstruct Queue2LiquidityRelease events from simulation_events table.

    CRITICAL FIX (Discrepancy #3): These events are needed for "Queue 2 Releases" display block.

    Args:
        events: List of simulation event records with event_type = 'Queue2LiquidityRelease'

    Returns:
        List of event dicts compatible with verbose output functions
    """
    result = []
    for event in events:
        if event["event_type"] == "Queue2LiquidityRelease":
            details = event.get("details", {})
            result.append({
                "event_type": "Queue2LiquidityRelease",
                "tick": event["tick"],
                "tx_id": event.get("tx_id"),
                "sender": details.get("sender"),
                "receiver": details.get("receiver"),
                "amount": details.get("amount", 0),
                "queue_wait_ticks": details.get("queue_wait_ticks", 0),
                "release_reason": details.get("release_reason", ""),
            })
    return result


def _reconstruct_queue_snapshots(
    conn,
    simulation_id: str,
    tick: int,
    tx_cache: dict[str, dict]
) -> dict[str, dict]:
    """Reconstruct queue snapshots from transaction cache and events.

    CRITICAL FIX (Discrepancy #1): Near-deadline warnings require knowing which
    transactions are queued. Without --full-replay, queue_snapshots weren't available.
    This reconstructs them from transaction state.

    Args:
        conn: Database connection
        simulation_id: Simulation identifier
        tick: Current tick
        tx_cache: Transaction cache with full transaction info

    Returns:
        Dict mapping agent_id to queue state:
        {
            "AGENT_ID": {
                "queue1": [tx_id1, tx_id2, ...],  # Generic queue
                "rtgs": [tx_id3, tx_id4, ...]     # RTGS queue
            }
        }
    """
    # Get all settlement events up to and including current tick
    # to determine which transactions have been settled
    settled_query = """
        SELECT tx_id, SUM(CAST(json_extract_string(details, '$.amount') AS BIGINT)) as settled_amount
        FROM simulation_events
        WHERE simulation_id = ?
        AND tick <= ?
        AND event_type IN (
            'Settlement', 'RtgsImmediateSettlement', 'Queue2LiquidityRelease',
            'LsmBilateralOffset', 'LsmCycleSettlement'
        )
        AND tx_id IS NOT NULL
        GROUP BY tx_id
    """
    settled_result = conn.execute(settled_query, [simulation_id, tick]).fetchall()
    settled_amounts = {row[0]: row[1] if row[1] is not None else 0 for row in settled_result}

    # Also check LSM events which settle multiple transactions at once
    lsm_query = """
        SELECT json_extract_string(details, '$.tx_ids') as tx_ids_json
        FROM simulation_events
        WHERE simulation_id = ?
        AND tick <= ?
        AND event_type IN ('LsmBilateralOffset', 'LsmCycleSettlement')
    """
    lsm_result = conn.execute(lsm_query, [simulation_id, tick]).fetchall()
    for row in lsm_result:
        if row[0]:
            try:
                import json
                tx_ids = json.loads(row[0])
                for tx_id in tx_ids:
                    # Mark as fully settled (LSM settles full amounts)
                    if tx_id in tx_cache:
                        settled_amounts[tx_id] = tx_cache[tx_id]["amount"]
            except:
                pass

    # Build queue snapshots by agent
    queue_snapshots = {}
    for tx_id, tx in tx_cache.items():
        # Skip if not arrived yet
        if tx["arrival_tick"] > tick:
            continue

        # CRITICAL: Check if settled BY current tick (not final status)
        # tx_cache contains final state, but we need state AT this tick
        # A transaction is settled at tick T if settlement_tick <= T
        settlement_tick = tx.get("settlement_tick")
        if settlement_tick is not None and settlement_tick <= tick:
            # Transaction was settled by this tick - not queued
            continue

        # Also check with settled_amounts from events query
        settled = settled_amounts.get(tx_id, 0)
        remaining = tx["amount"] - settled
        if remaining <= 0:
            continue

        # Transaction is queued at this tick - add to sender's queue
        sender = tx["sender_id"]
        if sender not in queue_snapshots:
            queue_snapshots[sender] = {"queue1": [], "rtgs": []}

        # Add to generic queue (exact queue doesn't matter for near-deadline detection)
        queue_snapshots[sender]["rtgs"].append(tx_id)

    return queue_snapshots


def _calculate_final_queue_sizes(
    conn,
    simulation_id: str,
    final_tick: int,
    tx_cache: dict[str, dict],
    agent_ids: list[str]
) -> dict[str, int]:
    """Calculate queue sizes at final tick from events.

    CRITICAL FIX (Discrepancy #6): JSON queue sizes were 0 without --full-replay.
    This reconstructs queue sizes from transaction state at final tick.

    Args:
        conn: Database connection
        simulation_id: Simulation identifier
        final_tick: Last tick of simulation
        tx_cache: Transaction cache
        agent_ids: List of agent IDs

    Returns:
        Dict mapping agent_id -> queue1_size
    """
    queue_snapshots = _reconstruct_queue_snapshots(conn, simulation_id, final_tick, tx_cache)

    # Count queued transactions per agent
    queue_sizes = {agent_id: 0 for agent_id in agent_ids}
    for agent_id, queues in queue_snapshots.items():
        queue_sizes[agent_id] = len(queues.get("queue1", [])) + len(queues.get("rtgs", []))

    return queue_sizes


def _has_full_replay_data(conn, simulation_id: str) -> bool:
    """Check if simulation has full replay data (--full-replay was used).

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier

    Returns:
        True if simulation has tick agent states (primary indicator of --full-replay)

    Examples:
        >>> has_data = _has_full_replay_data(conn, "sim-abc123")
        >>> if has_data:
        ...     # Display full replay
    """
    try:
        # Check if tick_agent_states table exists and has data for this simulation
        # This is the primary indicator that --full-replay was used
        result = conn.execute(
            "SELECT COUNT(*) FROM tick_agent_states WHERE simulation_id = ?",
            [simulation_id]
        ).fetchone()
        return result[0] > 0 if result else False
    except Exception:
        # Table doesn't exist or other error
        return False


def _get_summary_statistics(conn, simulation_id: str, from_tick: int, to_tick: int) -> dict:
    """DEPRECATED: This function should NOT be used for replay summary statistics.

    ⚠️  WARNING: This function recalculates statistics from simulation_events, which can
    produce DIFFERENT results than the authoritative values persisted by the run command.
    This violates the Replay Identity principle.

    ✅  CORRECT APPROACH: Use get_simulation_summary() to get authoritative statistics
    from the simulations table, which contains the exact values from the original run.

    Historical context:
    - This function was originally created to provide summary stats for replay
    - It manually counts events and reconstructs agent states from tick_agent_states
    - This approach is fragile and has caused discrepancies (e.g., settlement counts off by 20)

    Replacement:
    - For summary stats: Use get_simulation_summary(conn, simulation_id)
    - For agent balances: Query daily_agent_metrics for the final day

    This function is kept for backward compatibility but should be removed in a future cleanup.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation identifier
        from_tick: Starting tick (inclusive)
        to_tick: Ending tick (inclusive)

    Returns:
        Dict with total_arrivals, total_settlements, total_lsm_releases, final_agent_states

    Examples:
        >>> stats = _get_summary_statistics(conn, "sim-abc", 0, 99)
        >>> stats["total_arrivals"]
        533
    """
    # Count arrivals in tick range
    arrivals_query = """
        SELECT COUNT(*) FROM simulation_events
        WHERE simulation_id = ? AND event_type = 'Arrival'
        AND tick BETWEEN ? AND ?
    """
    result = conn.execute(arrivals_query, [simulation_id, from_tick, to_tick]).fetchone()
    total_arrivals = result[0] if result else 0

    # Count settlements (both Settlement events and LSM events)
    # For LSM events, we need to count the transactions they settle (from tx_ids array)
    settlements_query = """
        SELECT COUNT(*) FROM simulation_events
        WHERE simulation_id = ? AND event_type = 'Settlement'
        AND tick BETWEEN ? AND ?
    """
    result = conn.execute(settlements_query, [simulation_id, from_tick, to_tick]).fetchone()
    total_settlements = result[0] if result else 0

    # Count LSM-settled transactions by extracting tx_ids from event details
    lsm_query = """
        SELECT event_type, details FROM simulation_events
        WHERE simulation_id = ?
        AND event_type IN ('LsmBilateralOffset', 'LsmCycleSettlement')
        AND tick BETWEEN ? AND ?
    """
    lsm_results = conn.execute(lsm_query, [simulation_id, from_tick, to_tick]).fetchall()

    total_lsm_releases = len(lsm_results)
    lsm_settlements = 0
    for event_type, details_json in lsm_results:
        details = json.loads(details_json) if isinstance(details_json, str) else details_json
        tx_ids = details.get("tx_ids", [])
        lsm_settlements += len(tx_ids)

    total_settlements += lsm_settlements

    # Get final agent states from the last tick in range
    # Try tick_agent_states first (if full replay data available)
    agent_states = []
    try:
        agent_states_query = """
            SELECT agent_id, balance, queue1_size, costs
            FROM tick_agent_states
            WHERE simulation_id = ? AND tick = ?
        """
        agent_states_results = conn.execute(agent_states_query, [simulation_id, to_tick]).fetchall()

        for agent_id, balance, queue1_size, costs_json in agent_states_results:
            costs = json.loads(costs_json) if isinstance(costs_json, str) else (costs_json or {})
            agent_states.append({
                "id": agent_id,
                "final_balance": balance,
                "queue1_size": queue1_size,
                "total_cost": costs.get("total", 0),
            })
    except Exception:
        # tick_agent_states not available, skip agent states
        pass

    # Calculate total cost
    total_cost = sum(agent.get("total_cost", 0) for agent in agent_states)

    return {
        "total_arrivals": total_arrivals,
        "total_settlements": total_settlements,
        "total_lsm_releases": total_lsm_releases,
        "agent_states": agent_states,
        "total_cost": total_cost,
    }


class _MockOrchestrator:
    """Lightweight mock orchestrator for database replay.

    Provides minimal interface needed by verbose output functions without
    running actual simulation. Transaction details come from database cache.
    """

    def __init__(self, tx_cache: dict[str, dict]):
        """Initialize with transaction cache.

        Args:
            tx_cache: Dict mapping tx_id -> transaction details
        """
        self._tx_cache = tx_cache

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Get transaction details from cache.

        Args:
            tx_id: Transaction identifier

        Returns:
            Transaction details dict or None if not found
        """
        tx = self._tx_cache.get(tx_id)
        if not tx:
            return None

        # Convert database record format to orchestrator format
        return {
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount"],
            "remaining_amount": tx.get("amount", 0) - tx.get("amount_settled", 0),
            "priority": tx["priority"],
            "deadline_tick": tx["deadline_tick"],
            "status": tx["status"],
            "is_divisible": tx.get("is_divisible", False),
        }


def replay_simulation(
    simulation_id: Annotated[
        str,
        typer.Option(
            "--simulation-id",
            "-s",
            help="Simulation ID to replay from database",
        ),
    ],
    from_tick: Annotated[
        int,
        typer.Option(
            "--from-tick",
            help="Starting tick for verbose output (inclusive)",
        ),
    ] = 0,
    to_tick: Annotated[
        Optional[int],
        typer.Option(
            "--to-tick",
            help="Ending tick for verbose output (inclusive, defaults to last tick)",
        ),
    ] = None,
    db_path: Annotated[
        str,
        typer.Option(
            "--db-path",
            help="Database file path (default: simulation_data.db)",
        ),
    ] = "simulation_data.db",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Verbose mode: show detailed tick-by-tick events",
        ),
    ] = False,
    event_stream: Annotated[
        bool,
        typer.Option(
            "--event-stream",
            help="Output events as JSON lines (one event per line, machine-readable format)",
        ),
    ] = False,
):
    """Replay a simulation from the database with verbose logging for a tick range.

    This command loads a persisted simulation's configuration and data from the database,
    displaying the tick-by-tick events that occurred during the original run.

    The configuration is automatically loaded from the database, so you don't need
    to provide the original config file.

    Examples:

        # Replay ticks 0-10 from simulation
        payment-sim replay --simulation-id sim-abc123 --to-tick 10

        # Replay ticks 50-100 (useful for debugging specific tick range)
        payment-sim replay --simulation-id sim-abc123 --from-tick 50 --to-tick 100

        # Replay entire simulation with verbose output
        payment-sim replay --simulation-id sim-abc123

        # Output events as JSON lines (machine-readable)
        payment-sim replay --simulation-id sim-abc123 --event-stream --from-tick 100 --to-tick 200
    """
    try:
        # Load simulation metadata from database
        if not event_stream:
            log_info(f"Loading simulation {simulation_id} from {db_path}", False)

        db_manager = DatabaseManager(db_path)

        # Get simulation summary (try simulations table first, then simulation_runs)
        summary = get_simulation_summary(db_manager.conn, simulation_id)

        if not summary:
            # Fallback: try simulation_runs table for incomplete/interrupted simulations
            query = """
                SELECT
                    rng_seed,
                    ticks_per_day,
                    num_days
                FROM simulation_runs
                WHERE simulation_id = ?
            """
            result = db_manager.conn.execute(query, [simulation_id]).fetchone()

            if result:
                log_info(f"Found incomplete simulation in database (loading from simulation_runs)", False)
                summary = {
                    "simulation_id": simulation_id,
                    "rng_seed": result[0],
                    "ticks_per_day": result[1],
                    "num_days": result[2],
                    "config_file": "unknown (incomplete run)",
                }
            else:
                log_error(f"Simulation {simulation_id} not found in database")
                log_info("Available simulations:", False)

                # Show available simulations
                sims_query = "SELECT DISTINCT simulation_id FROM simulation_runs ORDER BY start_time DESC LIMIT 10"
                available = db_manager.conn.execute(sims_query).fetchall()
                if available:
                    for sim in available:
                        log_info(f"  - {sim[0]}", False)
                else:
                    log_info("  (no simulations found in database)", False)

                raise typer.Exit(1)

        if not event_stream:
            log_success(f"Found simulation: {summary['config_file']}", False)
            log_info(f"  Seed: {summary['rng_seed']}", False)
            log_info(f"  Ticks per day: {summary['ticks_per_day']}", False)
            log_info(f"  Num days: {summary['num_days']}", False)
            log_info(f"  Total ticks: {summary['ticks_per_day'] * summary['num_days']}", False)

            # Load configuration from database
            log_info("Loading configuration from database", False)

        # Check if config_json is available in summary
        if "config_json" not in summary or not summary["config_json"]:
            log_error("Configuration not found in database.")
            log_info("This simulation may have been created before config persistence was implemented.", False)
            log_info("Config persistence was added on 2025-01-XX. Please re-run the simulation to enable replay.", False)
            raise typer.Exit(1)

        import json
        config_dict = json.loads(summary["config_json"])
        if not event_stream:
            log_success("Configuration loaded from database", False)

        # Validate configuration
        try:
            sim_config = SimulationConfig.from_dict(config_dict)
        except Exception as e:
            log_error(f"Invalid configuration: {e}")
            raise typer.Exit(1)

        # Convert to FFI format
        ffi_dict = sim_config.to_ffi_dict()

        # Calculate tick range
        total_ticks = summary['ticks_per_day'] * summary['num_days']
        end_tick = to_tick if to_tick is not None else total_ticks - 1

        if from_tick < 0 or from_tick >= total_ticks:
            log_error(f"Invalid from_tick: {from_tick} (must be 0 to {total_ticks-1})")
            raise typer.Exit(1)

        if end_tick < from_tick or end_tick >= total_ticks:
            log_error(f"Invalid to_tick: {end_tick} (must be {from_tick} to {total_ticks-1})")
            raise typer.Exit(1)

        if not event_stream:
            log_info(f"Replaying ticks {from_tick} to {end_tick} ({end_tick - from_tick + 1} ticks)", False)

        # Build transaction cache for entire simulation from simulation_events
        # This allows _MockOrchestrator to provide transaction details
        if not event_stream:
            log_info("Loading transaction data from simulation_events...", False)
        cache_start = time.time()

        # Query all Arrival and Settlement events to build transaction cache
        tx_cache = {}

        # Get all Arrival events to populate initial transaction data (with pagination)
        offset = 0
        while True:
            arrival_events_result = get_simulation_events(
                conn=db_manager.conn,
                simulation_id=simulation_id,
                event_type="Arrival",
                sort="tick_asc",
                limit=1000,
                offset=offset,
            )

            # Build transaction cache from arrival events
            for event in arrival_events_result["events"]:
                details = event["details"]  # Already parsed by get_simulation_events
                tx_id = event["tx_id"]
                if tx_id:
                    tx_cache[tx_id] = {
                        "tx_id": tx_id,
                        "sender_id": details.get("sender_id"),
                        "receiver_id": details.get("receiver_id"),
                        "amount": details.get("amount", 0),
                        "amount_settled": 0,  # Will be updated from settlement events
                        "priority": details.get("priority", 0),  # Default to 0 if not present
                        "is_divisible": details.get("is_divisible", False),
                        "arrival_tick": event["tick"],
                        "arrival_day": event["day"],
                        "deadline_tick": details.get("deadline") or details.get("deadline_tick", 0),
                        "settlement_tick": None,  # Will be updated from settlement events
                        "status": "pending",  # Will be updated from settlement events
                    }

            # Check if there are more events to fetch
            if len(arrival_events_result["events"]) < 1000:
                break
            offset += 1000

        # Update cache with settlement information (with pagination)
        offset = 0
        while True:
            settlement_events_result = get_simulation_events(
                conn=db_manager.conn,
                simulation_id=simulation_id,
                event_type="Settlement",
                sort="tick_asc",
                limit=1000,
                offset=offset,
            )

            for event in settlement_events_result["events"]:
                details = event["details"]  # Already parsed by get_simulation_events
                tx_id = event["tx_id"]
                if tx_id and tx_id in tx_cache:
                    tx_cache[tx_id]["amount_settled"] = details.get("amount", 0)
                    tx_cache[tx_id]["settlement_tick"] = event["tick"]
                    tx_cache[tx_id]["status"] = "settled"

            # Check if there are more events to fetch
            if len(settlement_events_result["events"]) < 1000:
                break
            offset += 1000

        cache_duration = time.time() - cache_start
        if not event_stream:
            log_success(f"Loaded {len(tx_cache)} transactions in {cache_duration:.2f}s", False)

        # Create mock orchestrator for providing transaction details
        mock_orch = _MockOrchestrator(tx_cache)

        # Check if this simulation has full replay data
        has_full_replay = _has_full_replay_data(db_manager.conn, simulation_id)

        # Now run replay mode from from_tick to end_tick (DATABASE-DRIVEN)
        if event_stream:
            # Event stream mode: output events as JSON lines
            import sys

            replay_start = time.time()

            for tick_num in range(from_tick, end_tick + 1):
                # Query simulation_events for this tick
                tick_events_result = get_simulation_events(
                    conn=db_manager.conn,
                    simulation_id=simulation_id,
                    tick=tick_num,
                    sort="tick_asc",
                    limit=1000,
                    offset=0,
                )

                # Output each event as a JSON line
                for event in tick_events_result["events"]:
                    # Create output event with tick information
                    output_event = {
                        "simulation_id": simulation_id,
                        "tick": event["tick"],
                        "day": event["day"],
                        "event_type": event["event_type"],
                        "event_id": event["event_id"],
                        "timestamp": event["event_timestamp"],
                        "details": event["details"],
                    }

                    # Add optional fields if present
                    if event.get("tx_id"):
                        output_event["tx_id"] = event["tx_id"]
                    if event.get("agent_id"):
                        output_event["agent_id"] = event["agent_id"]

                    # Output as JSON line
                    print(json.dumps(output_event), flush=True)

            replay_duration = time.time() - replay_start

            # Output final metadata as JSON line
            metadata = {
                "_metadata": True,
                "replay_complete": True,
                "simulation_id": simulation_id,
                "from_tick": from_tick,
                "to_tick": end_tick,
                "duration_seconds": round(replay_duration, 3),
                "ticks_per_second": round((end_tick - from_tick + 1) / replay_duration, 2) if replay_duration > 0 else 0,
            }
            print(json.dumps(metadata), flush=True)

        else:
            # Non-event-stream mode: either verbose tick-by-tick or summary only
            replay_start = time.time()

            # Initialize statistics variables
            tick_count_arrivals = 0
            tick_count_settlements = 0
            tick_count_lsm = 0
            ticks_replayed = end_tick - from_tick + 1

            if verbose:
                # Verbose mode: show detailed tick-by-tick events
                log_info("Database replay mode: showing persisted events", False)
                if has_full_replay:
                    log_success("Full replay data available (policy decisions, agent states, costs)", False)
                else:
                    log_info("Note: Policy decisions and per-tick agent states not available", False)
                    log_info("      (run with --persist --full-replay to capture full data)", False)

                # Track daily statistics
                ticks_per_day = summary["ticks_per_day"]
                daily_stats = {
                    "arrivals": 0,
                    "settlements": 0,
                    "lsm_releases": 0,
                }

                # Initialize previous balances for tracking changes
                # For the first tick in replay range, we need the balances from the previous tick
                # (or initial balances if from_tick == 0)
                prev_balances = {}
                agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

                if from_tick == 0:
                    # Use opening balances from config (stored in cents)
                    for agent_config in config_dict.get("agents", []):
                        prev_balances[agent_config["id"]] = agent_config.get("opening_balance", 0)
                else:
                    # Query agent states from previous tick
                    if has_full_replay:
                        prev_tick_states = get_tick_agent_states(db_manager.conn, simulation_id, from_tick - 1)
                        for state in prev_tick_states:
                            prev_balances[state["agent_id"]] = state.get("balance", 0)
                    else:
                        # Without full replay data, assume balances start at opening config values
                        for agent_config in config_dict.get("agents", []):
                            prev_balances[agent_config["id"]] = agent_config.get("opening_balance", 0)

                for tick_num in range(from_tick, end_tick + 1):
                    # ═══════════════════════════════════════════════════════════
                    # TICK HEADER
                    # ═══════════════════════════════════════════════════════════
                    log_tick_start(tick_num)

                    # Query simulation_events for this tick
                    tick_events_result = get_simulation_events(
                        conn=db_manager.conn,
                        simulation_id=simulation_id,
                        tick=tick_num,
                        sort="tick_asc",
                        limit=1000,  # Max limit allowed by get_simulation_events
                        offset=0,
                    )

                    # Organize events by type
                    arrival_events_raw = []
                    settlement_events_raw = []
                    rtgs_immediate_events_raw = []  # DISCREPANCY #3 FIX
                    queue2_release_events_raw = []  # DISCREPANCY #3 FIX
                    lsm_events_raw = []
                    collateral_events_raw = []
                    cost_accrual_events_raw = []
                    scenario_events_raw = []
                    state_register_events_raw = []  # Phase 4.6: Decision path auditing
                    budget_events_raw = []  # Phase 3.3: Bank-level budgets
                    collateral_timer_events_raw = []  # Phase 3.4: Collateral timer auto-withdrawal
                    # PHASE 4 FIX: Add missing event types for replay identity
                    transaction_went_overdue_events_raw = []
                    queued_rtgs_events_raw = []

                    for event in tick_events_result["events"]:
                        event_type = event["event_type"]
                        if event_type == "Arrival":
                            arrival_events_raw.append(event)
                        elif event_type == "Settlement":
                            settlement_events_raw.append(event)
                        # DISCREPANCY #3 FIX: Capture specific settlement event types
                        elif event_type == "RtgsImmediateSettlement":
                            rtgs_immediate_events_raw.append(event)
                        elif event_type == "Queue2LiquidityRelease":
                            queue2_release_events_raw.append(event)
                        elif event_type in ["LsmBilateralOffset", "LsmCycleSettlement"]:
                            lsm_events_raw.append(event)
                        elif event_type in ["CollateralPost", "CollateralWithdraw"]:
                            collateral_events_raw.append(event)
                        elif event_type == "CollateralTimerWithdrawn":  # Phase 3.4
                            collateral_timer_events_raw.append(event)
                        elif event_type == "CostAccrual":
                            cost_accrual_events_raw.append(event)
                        elif event_type == "ScenarioEventExecuted":
                            scenario_events_raw.append(event)
                        elif event_type == "StateRegisterSet":  # Phase 4.6
                            state_register_events_raw.append(event)
                        elif event_type == "BankBudgetSet":  # Phase 3.3
                            budget_events_raw.append(event)
                        # PHASE 4 FIX: Capture missing event types
                        elif event_type == "TransactionWentOverdue":
                            transaction_went_overdue_events_raw.append(event)
                        elif event_type == "QueuedRtgs":
                            queued_rtgs_events_raw.append(event)

                    # Reconstruct events from database (using simulation_events table as SINGLE SOURCE)
                    # This is the unified replay architecture - NO manual reconstruction from legacy tables
                    arrival_events = _reconstruct_arrival_events_from_simulation_events(arrival_events_raw)
                    settlement_events = _reconstruct_settlement_events_from_simulation_events(settlement_events_raw)
                    # DISCREPANCY #3 FIX: Reconstruct specific settlement event types
                    rtgs_immediate_events = _reconstruct_rtgs_immediate_settlement_events(rtgs_immediate_events_raw)
                    queue2_release_events = _reconstruct_queue2_liquidity_release_events(queue2_release_events_raw)
                    lsm_events = _reconstruct_lsm_events_from_simulation_events(lsm_events_raw)
                    collateral_events = _reconstruct_collateral_events_from_simulation_events(collateral_events_raw)
                    collateral_timer_events = _reconstruct_collateral_timer_events(collateral_timer_events_raw)  # Phase 3.4
                    cost_accrual_events = _reconstruct_cost_accrual_events(cost_accrual_events_raw)
                    scenario_events = _reconstruct_scenario_events_from_simulation_events(scenario_events_raw)
                    state_register_events = _reconstruct_state_register_events(state_register_events_raw)  # Phase 4.6
                    budget_events = _reconstruct_budget_events(budget_events_raw)  # Phase 3.3
                    # PHASE 4 FIX: Reconstruct missing event types
                    transaction_went_overdue_events = _reconstruct_transaction_went_overdue_events(transaction_went_overdue_events_raw)
                    queued_rtgs_events = _reconstruct_queued_rtgs_events(queued_rtgs_events_raw)

                    # Combine all events
                    events = (
                        arrival_events + settlement_events +
                        # DISCREPANCY #3 FIX: Include specific settlement events for display
                        rtgs_immediate_events + queue2_release_events +
                        lsm_events + collateral_events +
                        collateral_timer_events + cost_accrual_events + scenario_events +
                        state_register_events + budget_events +
                        # PHASE 4 FIX: Include missing event types for replay identity
                        transaction_went_overdue_events + queued_rtgs_events
                    )

                    # Update statistics
                    num_arrivals = len(arrival_events)

                    # CRITICAL FIX (Discrepancy #2): Count ALL settlement event types
                    # Rust emits specific settlement events (RtgsImmediateSettlement, Queue2LiquidityRelease)
                    # instead of generic Settlement events. We must count them all.
                    num_settlements = (
                        len(settlement_events) +  # Legacy generic Settlement events
                        len(rtgs_immediate_events) +  # Specific RTGS immediate settlements
                        len(queue2_release_events)  # Specific Queue2 releases
                    )

                    # LSM events settle multiple transactions - count them from tx_ids field
                    num_lsm_settlements = 0
                    for lsm_event in lsm_events:
                        tx_ids = lsm_event.get("tx_ids", [])
                        num_lsm_settlements += len(tx_ids)
                    num_settlements += num_lsm_settlements  # Add LSM-settled transactions to total

                    num_lsm = len(lsm_events)

                    daily_stats["arrivals"] += num_arrivals
                    daily_stats["settlements"] += num_settlements
                    daily_stats["lsm_releases"] += num_lsm

                    tick_count_arrivals += num_arrivals
                    tick_count_settlements += num_settlements
                    tick_count_lsm += num_lsm

                    # ═══════════════════════════════════════════════════════════
                    # PREPARE DATA FOR SHARED DISPLAY FUNCTION
                    # ═══════════════════════════════════════════════════════════
                    # Query policy decisions and add to events
                    policy_events = []
                    if has_full_replay:
                        policy_decisions = get_policy_decisions_by_tick(db_manager.conn, simulation_id, tick_num)
                        for decision in policy_decisions:
                            event_type_map = {
                                "submit": "PolicySubmit",
                                "hold": "PolicyHold",
                                "drop": "PolicyDrop",
                                "split": "PolicySplit",
                            }
                            event_type = event_type_map.get(decision["decision_type"], "PolicySubmit")
                            policy_event = {
                                "event_type": event_type,
                                "agent_id": decision["agent_id"],
                                "tx_id": decision["tx_id"],
                                "reason": decision.get("reason"),
                            }
                            if event_type == "PolicySplit":
                                policy_event["num_splits"] = decision.get("num_splits")
                                if decision.get("child_tx_ids"):
                                    import json
                                    policy_event["child_ids"] = json.loads(decision["child_tx_ids"])
                            policy_events.append(policy_event)

                    # Add policy events to events list for display
                    all_events = events + policy_events

                    # DISCREPANCY #4 FIX: Calculate total_cost from CostAccrual events
                    # NOT from agent_states (which only exist with --full-replay)
                    # This ensures cost breakdown displays even without --full-replay
                    total_cost = 0
                    for event in cost_accrual_events:
                        # CostAccrual events have individual cost amounts
                        total_cost += event.get("liquidity_cost", 0)
                        total_cost += event.get("delay_cost", 0)
                        total_cost += event.get("collateral_cost", 0)
                        total_cost += event.get("penalty_cost", 0)
                        total_cost += event.get("split_friction_cost", 0)

                    # Query agent states and queue snapshots (needed for DatabaseStateProvider)
                    agent_states_list = []
                    if has_full_replay:
                        agent_states_list = get_tick_agent_states(db_manager.conn, simulation_id, tick_num)
                        # NOTE: total_cost already calculated from CostAccrual events above
                        # No need to recalculate from agent_states (would duplicate)

                    # CRITICAL FIX (Discrepancy #1): Reconstruct queue_snapshots from events
                    # Without --full-replay, queue_snapshots wasn't available, so near-deadline
                    # transactions couldn't be detected. Now we reconstruct from events.
                    queue_snapshots = _reconstruct_queue_snapshots(
                        db_manager.conn,
                        simulation_id,
                        tick_num,
                        mock_orch._tx_cache
                    )

                    # Convert agent_states list to dict for DatabaseStateProvider
                    agent_states_dict = {state["agent_id"]: state for state in agent_states_list}

                    # ═══════════════════════════════════════════════════════════
                    # USE SHARED DISPLAY FUNCTION (SINGLE SOURCE OF TRUTH)
                    # ═══════════════════════════════════════════════════════════
                    from payment_simulator.cli.execution.display import display_tick_verbose_output
                    from payment_simulator.cli.execution.state_provider import DatabaseStateProvider

                    # Create DatabaseStateProvider for replay
                    provider = DatabaseStateProvider(
                        conn=db_manager.conn,
                        simulation_id=simulation_id,
                        tick=tick_num,
                        tx_cache=mock_orch._tx_cache,
                        agent_states=agent_states_dict,
                        queue_snapshots=queue_snapshots,
                    )

                    # Call shared display function - ensures live and replay can NEVER diverge
                    prev_balances = display_tick_verbose_output(
                        provider=provider,
                        events=all_events,
                        tick_num=tick_num,
                        agent_ids=agent_ids,
                        prev_balances=prev_balances,
                        num_arrivals=num_arrivals,
                        num_settlements=num_settlements,
                        num_lsm_releases=num_lsm,
                        total_cost=total_cost,
                    )

                    # ═══════════════════════════════════════════════════════════
                    # END-OF-DAY SUMMARY (if applicable)
                    # ═══════════════════════════════════════════════════════════
                    if (tick_num + 1) % ticks_per_day == 0:
                        current_day = tick_num // ticks_per_day

                        # CRITICAL FIX: Query FULL DAY statistics from database
                        # NOT just the replayed tick range (which could be a single tick)
                        # This fixes Discrepancy #5 - EOD metrics scope confusion

                        # Calculate full day tick range
                        day_start_tick = current_day * ticks_per_day
                        day_end_tick = (current_day + 1) * ticks_per_day - 1

                        # Query full day arrivals
                        day_arrivals_query = """
                            SELECT COUNT(*) FROM simulation_events
                            WHERE simulation_id = ? AND event_type = 'Arrival'
                            AND tick BETWEEN ? AND ?
                        """
                        day_arrivals_result = db_manager.conn.execute(
                            day_arrivals_query, [simulation_id, day_start_tick, day_end_tick]
                        ).fetchone()
                        full_day_arrivals = day_arrivals_result[0] if day_arrivals_result else 0

                        # Query full day settlements (including LSM settlements)
                        # Count Settlement events
                        day_settlements_query = """
                            SELECT COUNT(*) FROM simulation_events
                            WHERE simulation_id = ? AND event_type = 'Settlement'
                            AND tick BETWEEN ? AND ?
                        """
                        day_settlements_result = db_manager.conn.execute(
                            day_settlements_query, [simulation_id, day_start_tick, day_end_tick]
                        ).fetchone()
                        full_day_settlements = day_settlements_result[0] if day_settlements_result else 0

                        # Count LSM-settled transactions by extracting tx_ids from LSM events
                        day_lsm_query = """
                            SELECT event_type, details FROM simulation_events
                            WHERE simulation_id = ?
                            AND event_type IN ('LsmBilateralOffset', 'LsmCycleSettlement')
                            AND tick BETWEEN ? AND ?
                        """
                        day_lsm_results = db_manager.conn.execute(
                            day_lsm_query, [simulation_id, day_start_tick, day_end_tick]
                        ).fetchall()

                        full_day_lsm_releases = len(day_lsm_results)
                        day_lsm_settlements = 0
                        for event_type, details_json in day_lsm_results:
                            details = json.loads(details_json) if isinstance(details_json, str) else details_json
                            tx_ids = details.get("tx_ids", [])
                            day_lsm_settlements += len(tx_ids)

                        full_day_settlements += day_lsm_settlements

                        # Query database for EOD agent metrics
                        from payment_simulator.persistence.queries import get_agent_daily_metrics

                        # Get list of agent IDs from config
                        agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

                        # Build mapping of agent_id -> unsecured_cap from config
                        # Note: credit_limit backwards compatibility has been removed (Phase 8 complete)
                        # All configs must now use unsecured_cap directly
                        agent_credit_limits = {
                            agent["id"]: agent.get("unsecured_cap", 0)
                            for agent in config_dict.get("agents", [])
                        }

                        agent_stats = []
                        day_total_costs = 0
                        for agent_id in agent_ids:
                            metrics_df = get_agent_daily_metrics(db_manager.conn, simulation_id, agent_id)

                            # Filter for current day
                            day_metrics = metrics_df.filter(metrics_df["day"] == current_day)

                            if len(day_metrics) > 0:
                                # Convert to dict to avoid Polars formatting issues
                                row_dict = day_metrics.to_dicts()[0]
                                agent_total_cost = row_dict["total_cost"]
                                day_total_costs += agent_total_cost

                                # Calculate credit utilization (CRITICAL FIX - Discrepancy #8)
                                # Must match Rust's Agent::allowed_overdraft_limit() formula exactly!
                                # Rust: collateral_capacity + unsecured_cap
                                balance = row_dict["closing_balance"]
                                unsecured_cap = agent_credit_limits.get(agent_id, 0)  # Contains unsecured_cap (or unsecured_cap fallback)

                                # Get collateral backing from database
                                posted_collateral = row_dict.get("closing_posted_collateral", 0)

                                # Calculate collateral_capacity using same formula as Rust
                                # Rust: (posted_collateral * (1.0 - collateral_haircut)).floor()
                                collateral_haircut = 0.02  # Default from Agent::new()
                                collateral_capacity = int(posted_collateral * (1.0 - collateral_haircut))

                                # Rust formula: allowed_overdraft_limit = collateral_capacity + unsecured_cap
                                allowed_overdraft = collateral_capacity + unsecured_cap

                                credit_util = 0
                                if allowed_overdraft and allowed_overdraft > 0:
                                    # If balance is negative, we're using credit equal to the overdraft amount
                                    # If balance is positive, we're not using any credit
                                    used = max(0, -balance)
                                    credit_util = (used / allowed_overdraft) * 100

                                # PHASE 2 FIX: Calculate Queue2 size using StateProvider
                                # Queue2 = transactions in RTGS queue that belong to this agent
                                queue2_size = provider.get_queue2_size(agent_id)

                                agent_stats.append({
                                    "id": agent_id,
                                    "final_balance": balance,
                                    "credit_utilization": credit_util,
                                    "queue1_size": row_dict["queue1_eod_size"],
                                    "queue2_size": queue2_size,
                                    "total_costs": agent_total_cost,
                                })

                        # Show end-of-day event (must match live execution output)
                        # Query events from the last tick of the day
                        last_tick_of_day = (current_day + 1) * ticks_per_day - 1
                        eod_events_result = get_simulation_events(
                            conn=db_manager.conn,
                            simulation_id=simulation_id,
                            tick=last_tick_of_day,
                            sort="tick_asc",
                            limit=1000,
                            offset=0,
                        )
                        log_end_of_day_event(eod_events_result["events"])

                        # CRITICAL: Use full day statistics, NOT accumulated daily_stats which only
                        # covers the replayed tick range. This fixes Discrepancy #5.
                        # FIX Discrepancy #11: Sort agents alphabetically to match run output
                        agent_stats.sort(key=lambda x: x["id"])
                        log_end_of_day_statistics(
                            day=current_day,
                            total_arrivals=full_day_arrivals,
                            total_settlements=full_day_settlements,
                            total_lsm_releases=full_day_lsm_releases,
                            total_costs=day_total_costs,
                            agent_stats=agent_stats,
                        )

                        # Reset daily stats for next day (still useful for tracking replayed range)
                        daily_stats = {
                            "arrivals": 0,
                            "settlements": 0,
                            "lsm_releases": 0,
                        }

                # Verbose mode statistics are already tracked in tick_count_* variables
                log_success(f"\nReplay complete: {ticks_replayed} ticks", False)
                log_info("Replayed from database (not re-executed)", False)

            else:
                # Non-verbose mode: get summary statistics from authoritative simulations table
                # This ensures replay output matches run output exactly (Replay Identity principle)
                log_info("Loading summary statistics from database", False)

                # Use authoritative summary from simulations table (persisted by run command)
                # This is the SINGLE SOURCE OF TRUTH for final statistics
                tick_count_arrivals = summary["total_arrivals"]
                tick_count_settlements = summary["total_settlements"]
                total_cost = summary["total_cost_cents"]

                # CRITICAL FIX (Discrepancy #9): Query FULL SIMULATION LSM count, not just replayed range
                # LSM release count not in summary table - calculate from ALL events for this simulation
                lsm_query = """
                    SELECT COUNT(*) FROM simulation_events
                    WHERE simulation_id = ?
                    AND event_type IN ('LsmBilateralOffset', 'LsmCycleSettlement')
                """
                result = db_manager.conn.execute(lsm_query, [simulation_id]).fetchone()
                tick_count_lsm = result[0] if result else 0

                # Get final agent balances from daily_agent_metrics (always available, not dependent on --full-replay)
                final_day = summary["num_days"] - 1
                agent_metrics_query = """
                    SELECT agent_id, closing_balance, queue1_eod_size
                    FROM daily_agent_metrics
                    WHERE simulation_id = ? AND day = ?
                """
                agent_results = db_manager.conn.execute(agent_metrics_query, [simulation_id, final_day]).fetchall()
                agent_states_from_db = [
                    {
                        "id": row[0],
                        "final_balance": row[1],
                        "queue1_size": row[2],
                    }
                    for row in agent_results
                ]

            # Calculate replay duration and performance metrics
            replay_duration = time.time() - replay_start
            ticks_per_second = ticks_replayed / replay_duration if replay_duration > 0 else 0

            # Build and output final summary as JSON (matching run command format)
            # Determine which agent states to use based on execution mode
            if 'agent_states_from_db' in locals() and agent_states_from_db:
                # Non-verbose mode: use authoritative stats from simulations table
                agents_output = agent_states_from_db
                # total_cost already set from summary["total_cost_cents"] in non-verbose block
            elif has_full_replay:
                # Verbose mode with full replay data: get final agent states
                agent_states_list = get_tick_agent_states(db_manager.conn, simulation_id, end_tick)
                agents_output = []
                total_cost = 0
                for state in agent_states_list:
                    costs = state.get("costs", {})
                    agent_total_cost = costs.get("total", 0) if isinstance(costs, dict) else 0
                    total_cost += agent_total_cost
                    agents_output.append({
                        "id": state["agent_id"],
                        "final_balance": state.get("balance", 0),
                        "queue1_size": state.get("queue1_size", 0),
                    })
            else:
                # No full replay data: minimal agent info
                agents_output = [{"id": agent["id"]} for agent in config_dict.get("agents", [])]
                total_cost = 0

            # Build output matching run command format
            # Determine agents output: try multiple sources in priority order
            if 'agent_states_from_db' in locals() and agent_states_from_db:
                # Best: Non-verbose mode queried daily_agent_metrics
                final_agents_output = agent_states_from_db
            elif has_full_replay and 'agents_output' in locals():
                # Good: Verbose mode with full replay data
                final_agents_output = agents_output
            elif not has_full_replay:
                # Fallback: Query daily_agent_metrics for final balances
                # This handles verbose mode without full replay data
                final_day = summary["num_days"] - 1
                agent_metrics_query = """
                    SELECT agent_id, closing_balance, queue1_eod_size
                    FROM daily_agent_metrics
                    WHERE simulation_id = ? AND day = ?
                """
                try:
                    agent_results = db_manager.conn.execute(agent_metrics_query, [simulation_id, final_day]).fetchall()
                    final_agents_output = [
                        {
                            "id": row[0],
                            "final_balance": row[1],
                            "queue1_size": row[2],
                        }
                        for row in agent_results
                    ]
                except Exception:
                    # CRITICAL FIX (Discrepancy #6): Calculate queue sizes from events
                    # when daily_agent_metrics unavailable
                    agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

                    # Calculate final tick
                    final_tick = summary["ticks_per_day"] * summary["num_days"] - 1

                    # Reconstruct queue sizes from events
                    queue_sizes = _calculate_final_queue_sizes(
                        conn=db_manager.conn,
                        simulation_id=simulation_id,
                        final_tick=final_tick,
                        tx_cache=mock_orch._tx_cache,
                        agent_ids=agent_ids
                    )

                    # Get final balances from simulation summary or query
                    # Try to get from daily_agent_metrics even if queue1_eod_size failed
                    balance_query = """
                        SELECT agent_id, closing_balance
                        FROM daily_agent_metrics
                        WHERE simulation_id = ? AND day = ?
                    """
                    try:
                        balance_results = db_manager.conn.execute(balance_query, [simulation_id, final_day]).fetchall()
                        balances = {row[0]: row[1] for row in balance_results}
                    except:
                        # Last resort: balances from config (opening balances)
                        balances = {agent["id"]: agent.get("opening_balance", 0) for agent in config_dict.get("agents", [])}

                    final_agents_output = [
                        {
                            "id": agent_id,
                            "final_balance": balances.get(agent_id, 0),
                            "queue1_size": queue_sizes.get(agent_id, 0),
                        }
                        for agent_id in agent_ids
                    ]
            else:
                # Last resort: agent IDs only
                # CRITICAL FIX (Discrepancy #6): Even in last resort, calculate queue sizes
                agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

                final_tick = summary["ticks_per_day"] * summary["num_days"] - 1
                queue_sizes = _calculate_final_queue_sizes(
                    conn=db_manager.conn,
                    simulation_id=simulation_id,
                    final_tick=final_tick,
                    tx_cache=mock_orch._tx_cache,
                    agent_ids=agent_ids
                )

                final_agents_output = [
                    {
                        "id": agent_id,
                        "queue1_size": queue_sizes.get(agent_id, 0),
                    }
                    for agent_id in agent_ids
                ]

            # PHASE 1 FIX: Use authoritative statistics from simulations table
            # This ensures replay output matches run output exactly (Replay Identity principle)
            #
            # The summary dict contains authoritative stats persisted by run command:
            # - total_arrivals: Full simulation arrivals
            # - total_settlements: Full simulation settlements
            # - total_cost_cents: Full simulation costs
            #
            # We must NOT use tick_count_* variables which only count the replayed tick range!
            total_ticks = summary['ticks_per_day'] * summary['num_days']
            # FIX Discrepancy #11: Sort agents alphabetically to match run output
            final_agents_output.sort(key=lambda x: x["id"])

            output_data = {
                "simulation": {
                    "config_file": summary.get("config_file", "loaded from database"),
                    "seed": summary["rng_seed"],
                    # CRITICAL: Show full simulation ticks, not just replayed range
                    "ticks_executed": total_ticks,
                    # Add metadata to distinguish replay from run
                    "replay_range": f"{from_tick}-{end_tick}" if from_tick != 0 or end_tick != total_ticks - 1 else "full",
                    "ticks_replayed": ticks_replayed,
                    "duration_seconds": round(replay_duration, 3),
                    "ticks_per_second": round(ticks_per_second, 2),
                    "simulation_id": simulation_id,
                    "database": db_path,
                },
                "metrics": {
                    # CRITICAL: Use authoritative stats from summary table
                    "total_arrivals": summary["total_arrivals"],
                    "total_settlements": summary["total_settlements"],
                    "total_lsm_releases": summary.get("total_lsm_releases", tick_count_lsm),
                    # FIX Discrepancy #10: Use full precision to match run output
                    "settlement_rate": summary["total_settlements"] / summary["total_arrivals"] if summary["total_arrivals"] > 0 else 0,
                },
                "agents": final_agents_output,
                "costs": {
                    # CRITICAL: Use authoritative cost from summary table
                    "total_cost": summary.get("total_cost_cents", total_cost),
                },
                "performance": {
                    "ticks_per_second": round(ticks_per_second, 2),
                },
            }
            output_json(output_data)

        db_manager.close()

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        log_error("Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        log_error(f"Error: {e}")
        import traceback
        console_err = typer.get_text_stream("stderr")
        console_err.write(traceback.format_exc())
        raise typer.Exit(1)
