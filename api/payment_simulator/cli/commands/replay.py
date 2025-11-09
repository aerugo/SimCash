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
    get_collateral_events_by_tick,
    get_lsm_cycles_by_tick,
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


def _reconstruct_lsm_events(lsm_cycles: list[dict]) -> list[dict]:
    """Reconstruct LSM cycle events from database records.

    Args:
        lsm_cycles: List of LSM cycle records for current tick

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> cycles = [{"cycle_type": "bilateral", ...}]
        >>> events = _reconstruct_lsm_events(cycles)
        >>> events[0]["event_type"]
        'LsmBilateralOffset'
    """
    events = []

    for cycle in lsm_cycles:
        if cycle["cycle_type"] == "bilateral":
            # Bilateral offset: agent_ids = [A, B, A] (length 3), 2 transactions
            # The Rust backend models bilateral offsets as a cycle [A, B, A]
            if len(cycle["agent_ids"]) == 3 and len(cycle["tx_ids"]) == 2:
                # Get transaction amounts from database (if available)
                tx_amounts = cycle.get("tx_amounts", [])
                if len(tx_amounts) >= 2:
                    amount_a = tx_amounts[0]
                    amount_b = tx_amounts[1]
                else:
                    # Fallback to simplified version
                    amount_a = cycle["settled_value"]
                    amount_b = cycle["settled_value"]

                events.append({
                    "event_type": "LsmBilateralOffset",
                    "agent_a": cycle["agent_ids"][0],
                    "agent_b": cycle["agent_ids"][1],
                    "tx_id_a": cycle["tx_ids"][0],
                    "tx_id_b": cycle["tx_ids"][1],
                    "amount_a": amount_a,
                    "amount_b": amount_b,
                    "amount": cycle["settled_value"],
                })
        else:
            # Multilateral cycle - include all detailed fields from database
            event = {
                "event_type": "LsmCycleSettlement",
                "agent_ids": cycle["agent_ids"],
                "tx_ids": cycle["tx_ids"],
                "settled_value": cycle["settled_value"],
            }

            # Include tx_amounts if available (otherwise fallback to simplified)
            tx_amounts = cycle.get("tx_amounts", [])
            if tx_amounts:
                event["tx_amounts"] = tx_amounts
            else:
                # Simplified fallback
                event["amounts"] = [cycle["settled_value"] // len(cycle["tx_ids"])] * len(cycle["tx_ids"])

            # Include all additional fields that log_lsm_cycle_visualization uses
            if "net_positions" in cycle and cycle["net_positions"]:
                event["net_positions"] = cycle["net_positions"]

            if "total_value" in cycle and cycle["total_value"] is not None:
                event["total_value"] = cycle["total_value"]

            if "max_net_outflow" in cycle and cycle["max_net_outflow"] is not None:
                event["max_net_outflow"] = cycle["max_net_outflow"]

            if "max_net_outflow_agent" in cycle and cycle["max_net_outflow_agent"]:
                event["max_net_outflow_agent"] = cycle["max_net_outflow_agent"]

            events.append(event)

    return events


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


def _reconstruct_collateral_events(collateral_events: list[dict]) -> list[dict]:
    """Reconstruct collateral events from database records.

    Args:
        collateral_events: List of collateral event records for current tick

    Returns:
        List of event dicts compatible with verbose output functions

    Examples:
        >>> events = [{"action": "post", "amount": 100000, ...}]
        >>> reconstructed = _reconstruct_collateral_events(events)
        >>> reconstructed[0]["event_type"]
        'CollateralPost'
    """
    return [
        {
            "event_type": "CollateralPost" if event["action"] == "post" else "CollateralWithdraw",
            "agent_id": event["agent_id"],
            "amount": event["amount"],
            "reason": event["reason"],
            "new_total": event["posted_collateral_after"],
        }
        for event in collateral_events
    ]


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
            help="Verbose mode: show detailed events (default: True for replay)",
        ),
    ] = True,
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

        elif verbose:
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

            replay_start = time.time()
            tick_count_arrivals = 0
            tick_count_settlements = 0
            tick_count_lsm = 0

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
                lsm_events_raw = []
                collateral_events_raw = []
                cost_accrual_events_raw = []

                for event in tick_events_result["events"]:
                    event_type = event["event_type"]
                    if event_type == "Arrival":
                        arrival_events_raw.append(event)
                    elif event_type == "Settlement":
                        settlement_events_raw.append(event)
                    elif event_type in ["LsmBilateralOffset", "LsmCycleSettlement"]:
                        lsm_events_raw.append(event)
                    elif event_type in ["CollateralPost", "CollateralWithdraw"]:
                        collateral_events_raw.append(event)
                    elif event_type == "CostAccrual":
                        cost_accrual_events_raw.append(event)

                # Also get collateral and LSM data from dedicated tables (for compatibility)
                collateral_data = get_collateral_events_by_tick(db_manager.conn, simulation_id, tick_num)
                lsm_data = get_lsm_cycles_by_tick(db_manager.conn, simulation_id, tick_num)

                # Reconstruct events from database (using simulation_events data)
                arrival_events = _reconstruct_arrival_events_from_simulation_events(arrival_events_raw)
                settlement_events = _reconstruct_settlement_events_from_simulation_events(settlement_events_raw)

                # Reconstruct LSM events from BOTH sources (simulation_events and dedicated table)
                lsm_from_events = _reconstruct_lsm_events_from_simulation_events(lsm_events_raw)
                lsm_from_table = _reconstruct_lsm_events(lsm_data)

                # Prefer simulation_events if available (more complete), otherwise use table
                lsm_events = lsm_from_events if lsm_from_events else lsm_from_table

                # Reconstruct collateral events from BOTH sources (simulation_events and dedicated table)
                collateral_from_events = _reconstruct_collateral_events_from_simulation_events(collateral_events_raw)
                collateral_from_table = _reconstruct_collateral_events(collateral_data)

                # Prefer simulation_events if available (more complete), otherwise use table
                collateral_events = collateral_from_events if collateral_from_events else collateral_from_table

                # Reconstruct cost accrual events
                cost_accrual_events = _reconstruct_cost_accrual_events(cost_accrual_events_raw)

                # Combine all events
                events = arrival_events + settlement_events + lsm_events + collateral_events + cost_accrual_events

                # Update statistics
                num_arrivals = len(arrival_events)
                num_settlements = len(settlement_events)
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

                # Query agent states and queue snapshots (needed for DatabaseStateProvider)
                agent_states_list = []
                queue_snapshots = {}
                total_cost = 0
                if has_full_replay:
                    agent_states_list = get_tick_agent_states(db_manager.conn, simulation_id, tick_num)
                    queue_snapshots = get_tick_queue_snapshots(db_manager.conn, simulation_id, tick_num)
                    # Calculate total cost from agent states
                    for state in agent_states_list:
                        costs = state.get("costs", {})
                        total_cost += costs.get("total", 0)

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

                    # Query database for EOD agent metrics
                    from payment_simulator.persistence.queries import get_agent_daily_metrics

                    # Get list of agent IDs from config
                    agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

                    # Build mapping of agent_id -> credit_limit from config
                    agent_credit_limits = {
                        agent["id"]: agent.get("credit_limit", 0)
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

                            # Calculate credit utilization
                            balance = row_dict["closing_balance"]
                            credit_limit = agent_credit_limits.get(agent_id, 0)
                            credit_util = 0
                            if credit_limit and credit_limit > 0:
                                used = max(0, credit_limit - balance)
                                credit_util = (used / credit_limit) * 100

                            agent_stats.append({
                                "id": agent_id,
                                "final_balance": balance,
                                "credit_utilization": credit_util,
                                "queue1_size": row_dict["queue1_eod_size"],
                                "queue2_size": 0,  # Not tracked
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

                    log_end_of_day_statistics(
                        day=current_day,
                        total_arrivals=daily_stats["arrivals"],
                        total_settlements=daily_stats["settlements"],
                        total_lsm_releases=daily_stats["lsm_releases"],
                        total_costs=day_total_costs,
                        agent_stats=agent_stats,
                    )

                    # Reset daily stats for next day
                    daily_stats = {
                        "arrivals": 0,
                        "settlements": 0,
                        "lsm_releases": 0,
                    }

            replay_duration = time.time() - replay_start
            ticks_replayed = end_tick - from_tick + 1
            ticks_per_second = ticks_replayed / replay_duration if replay_duration > 0 else 0

            log_success(f"\nReplay complete: {ticks_replayed} ticks in {replay_duration:.2f}s ({ticks_per_second:.1f} ticks/s)", False)
            log_info("Replayed from database (not re-executed)", False)

            # Build and output final summary as JSON
            # Get list of agent IDs from config
            agent_ids = [agent["id"] for agent in config_dict.get("agents", [])]

            output_data = {
                "replay": {
                    "simulation_id": simulation_id,
                    "from_tick": from_tick,
                    "to_tick": end_tick,
                    "ticks_replayed": ticks_replayed,
                    "duration_seconds": round(replay_duration, 3),
                    "ticks_per_second": round(ticks_per_second, 2),
                    "source": "database",  # Indicates this is database replay, not re-execution
                    "full_replay_data": has_full_replay,  # Indicates if policy decisions, agent states, costs available
                },
                "metrics": {
                    "total_arrivals": tick_count_arrivals,
                    "total_settlements": tick_count_settlements,
                    "total_lsm_releases": tick_count_lsm,
                    "settlement_rate": round(tick_count_settlements / tick_count_arrivals, 4) if tick_count_arrivals > 0 else 0,
                },
                "agents": [{"id": aid} for aid in agent_ids],  # Simplified, no final balances
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
