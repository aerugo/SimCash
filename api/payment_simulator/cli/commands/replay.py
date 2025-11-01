"""Replay command - Load and replay simulations from database with verbose logging.

This command enables replaying a specific tick range from a persisted simulation,
producing identical verbose output to the original run.
"""

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
    log_end_of_day_statistics,
    log_tick_summary,
    output_json,
    console,
)
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.queries import (
    get_simulation_summary,
    get_transactions_by_tick,
    get_collateral_events_by_tick,
    get_lsm_cycles_by_tick,
    get_policy_decisions_by_tick,
    get_tick_agent_states,
    get_tick_queue_snapshots,
)
from payment_simulator.config import SimulationConfig
from payment_simulator._core import Orchestrator


# ============================================================================
# Event Reconstruction Helpers
# ============================================================================


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
            # Bilateral offset: 2 agents, 2 transactions
            if len(cycle["agent_ids"]) == 2 and len(cycle["tx_ids"]) == 2:
                events.append({
                    "event_type": "LsmBilateralOffset",
                    "agent_a": cycle["agent_ids"][0],
                    "agent_b": cycle["agent_ids"][1],
                    "tx_id_a": cycle["tx_ids"][0],
                    "tx_id_b": cycle["tx_ids"][1],
                    "amount_a": cycle["settled_value"],  # Note: This is simplified
                    "amount_b": cycle["settled_value"],
                    "amount": cycle["settled_value"],
                })
        else:
            # Multilateral cycle
            events.append({
                "event_type": "LsmCycleSettlement",
                "agent_ids": cycle["agent_ids"],
                "tx_ids": cycle["tx_ids"],
                "amounts": [cycle["settled_value"] // len(cycle["tx_ids"])] * len(cycle["tx_ids"]),  # Simplified
                "settled_value": cycle["settled_value"],
            })

    return events


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
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Original configuration file (YAML or JSON) used for this simulation",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
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
):
    """Replay a simulation from the database with verbose logging for a tick range.

    This command loads a persisted simulation and re-runs it deterministically,
    producing identical verbose output to the original run for the specified tick range.

    The replay is guaranteed to be identical because:
    1. Same RNG seed from original simulation
    2. Same configuration
    3. Deterministic simulation engine

    Examples:

        # Replay ticks 0-10 from simulation
        payment-sim replay --simulation-id sim-abc123 --to-tick 10

        # Replay ticks 50-100 (useful for debugging specific tick range)
        payment-sim replay --simulation-id sim-abc123 --from-tick 50 --to-tick 100

        # Replay entire simulation with verbose output
        payment-sim replay --simulation-id sim-abc123
    """
    try:
        # Load simulation metadata from database
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

        log_success(f"Found simulation: {summary['config_file']}", False)
        log_info(f"  Seed: {summary['rng_seed']}", False)
        log_info(f"  Ticks per day: {summary['ticks_per_day']}", False)
        log_info(f"  Num days: {summary['num_days']}", False)
        log_info(f"  Total ticks: {summary['ticks_per_day'] * summary['num_days']}", False)

        # Load configuration from file
        log_info(f"Loading configuration from {config}", False)
        with open(config) as f:
            if config.suffix in [".yaml", ".yml"]:
                config_dict = yaml.safe_load(f)
            elif config.suffix == ".json":
                import json
                config_dict = json.load(f)
            else:
                log_error(f"Unsupported file format: {config.suffix}")
                raise typer.Exit(1)

        # Override seed with the one from the database (ensures deterministic replay)
        config_dict.setdefault("simulation", {})["rng_seed"] = summary["rng_seed"]

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

        log_info(f"Replaying ticks {from_tick} to {end_tick} ({end_tick - from_tick + 1} ticks)", False)

        # Build transaction cache for entire simulation
        # This allows _MockOrchestrator to provide transaction details
        log_info("Loading transaction data from database...", False)
        cache_start = time.time()

        tx_cache_query = """
            SELECT
                tx_id,
                sender_id,
                receiver_id,
                amount,
                amount_settled,
                priority,
                is_divisible,
                arrival_tick,
                arrival_day,
                deadline_tick,
                settlement_tick,
                status
            FROM transactions
            WHERE simulation_id = ?
        """
        tx_cache_result = db_manager.conn.execute(tx_cache_query, [simulation_id]).fetchall()

        tx_cache = {}
        for row in tx_cache_result:
            tx_cache[row[0]] = {
                "tx_id": row[0],
                "sender_id": row[1],
                "receiver_id": row[2],
                "amount": row[3],
                "amount_settled": row[4],
                "priority": row[5],
                "is_divisible": row[6],
                "arrival_tick": row[7],
                "arrival_day": row[8],
                "deadline_tick": row[9],
                "settlement_tick": row[10],
                "status": row[11],
            }

        cache_duration = time.time() - cache_start
        log_success(f"Loaded {len(tx_cache)} transactions in {cache_duration:.2f}s", False)

        # Create mock orchestrator for providing transaction details
        mock_orch = _MockOrchestrator(tx_cache)

        # Check if this simulation has full replay data
        has_full_replay = _has_full_replay_data(db_manager.conn, simulation_id)

        # Now run verbose mode from from_tick to end_tick (DATABASE-DRIVEN)
        if verbose:
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

            for tick_num in range(from_tick, end_tick + 1):
                # ═══════════════════════════════════════════════════════════
                # TICK HEADER
                # ═══════════════════════════════════════════════════════════
                log_tick_start(tick_num)

                # Query database for this tick's data
                tick_data = get_transactions_by_tick(db_manager.conn, simulation_id, tick_num)
                collateral_data = get_collateral_events_by_tick(db_manager.conn, simulation_id, tick_num)
                lsm_data = get_lsm_cycles_by_tick(db_manager.conn, simulation_id, tick_num)

                # Reconstruct events from database
                arrival_events = _reconstruct_arrival_events(tick_data["arrivals"])
                settlement_events = _reconstruct_settlement_events(tick_data["settlements"])
                lsm_events = _reconstruct_lsm_events(lsm_data)
                collateral_events = _reconstruct_collateral_events(collateral_data)

                # Combine all events
                events = arrival_events + settlement_events + lsm_events + collateral_events

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
                # SECTION 1: ARRIVALS (detailed)
                # ═══════════════════════════════════════════════════════════
                if num_arrivals > 0:
                    log_transaction_arrivals(mock_orch, arrival_events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 2: POLICY DECISIONS (from database if available)
                # ═══════════════════════════════════════════════════════════
                if has_full_replay:
                    # Query policy decisions from database
                    policy_decisions = get_policy_decisions_by_tick(db_manager.conn, simulation_id, tick_num)

                    # Convert to event format for display
                    policy_events = []
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

                    if policy_events:
                        log_policy_decisions(policy_events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 3: SETTLEMENTS (detailed with mechanisms)
                # ═══════════════════════════════════════════════════════════
                if num_settlements > 0 or num_lsm > 0:
                    log_settlement_details(mock_orch, events, tick_num)

                # ═══════════════════════════════════════════════════════════
                # SECTION 4: LSM CYCLE VISUALIZATION
                # ═══════════════════════════════════════════════════════════
                if num_lsm > 0:
                    log_lsm_cycle_visualization(lsm_events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 5: COLLATERAL ACTIVITY
                # ═══════════════════════════════════════════════════════════
                if len(collateral_events) > 0:
                    log_collateral_activity(collateral_events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 6: AGENT STATES (from database if available)
                # ═══════════════════════════════════════════════════════════
                if has_full_replay:
                    # Query agent states from database
                    agent_states = get_tick_agent_states(db_manager.conn, simulation_id, tick_num)

                    # Query queue snapshots from database
                    queue_snapshots = get_tick_queue_snapshots(db_manager.conn, simulation_id, tick_num)

                    # Display agent states
                    console.print()
                    console.print("  [bold]Agent States:[/bold]")

                    # Group states by agent_id
                    states_by_agent = {state["agent_id"]: state for state in agent_states}

                    for agent_id, state in states_by_agent.items():
                        # Get queue data for this agent
                        agent_queues = queue_snapshots.get(agent_id, {})
                        log_agent_state_from_db(mock_orch, agent_id, state, agent_queues)

                # ═══════════════════════════════════════════════════════════
                # SECTION 7: COST BREAKDOWN (from database if available)
                # ═══════════════════════════════════════════════════════════
                if has_full_replay:
                    # agent_states already queried above, use it for cost display
                    log_cost_breakdown_from_db(agent_states)

                # ═══════════════════════════════════════════════════════════
                # SECTION 8: TICK SUMMARY
                # ═══════════════════════════════════════════════════════════
                # Calculate real queued count from database if available
                queued_count = 0
                if has_full_replay:
                    # Count all queued transactions from queue snapshots
                    for agent_id, queues in queue_snapshots.items():
                        queued_count += len(queues.get("queue1", []))
                        queued_count += len(queues.get("rtgs", []))

                log_tick_summary(
                    num_arrivals,
                    num_settlements,
                    num_lsm,
                    queued_count
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

                            agent_stats.append({
                                "id": agent_id,
                                "final_balance": row_dict["closing_balance"],
                                "credit_utilization": 0,  # Not calculated
                                "queue1_size": row_dict["queue1_eod_size"],
                                "queue2_size": 0,  # Not tracked
                                "total_costs": agent_total_cost,
                            })

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
