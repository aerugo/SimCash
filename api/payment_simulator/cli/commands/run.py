"""Run command - Execute simulations from config files."""

import json
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import polars as pl
import typer
import yaml
from payment_simulator._core import Orchestrator
from payment_simulator.cli.output import (  # Enhanced verbose mode functions
    create_progress,
    log_agent_queues_detailed,
    log_agent_state,
    log_arrivals,
    log_collateral_activity,
    log_cost_breakdown,
    log_costs,
    log_end_of_day_statistics,
    log_error,
    log_info,
    log_lsm_activity,
    log_lsm_cycle_visualization,
    log_policy_decisions,
    log_settlement_details,
    log_settlements,
    log_success,
    log_tick_start,
    log_tick_summary,
    log_transaction_arrivals,
    output_json,
    output_jsonl,
)
from payment_simulator.config import SimulationConfig
from typing_extensions import Annotated


def _persist_day_data(
    orch: Orchestrator,
    db_manager,
    sim_id: str,
    day: int,
    quiet: bool = False,
) -> None:
    """Persist all data for a completed day.

    This helper encapsulates the EOD persistence logic that was duplicated
    across normal and verbose modes.

    Args:
        orch: The orchestrator instance
        db_manager: Database manager instance
        sim_id: Simulation ID
        day: Day number to persist
        quiet: Whether to suppress log messages
    """
    from payment_simulator.persistence.writers import (
        write_daily_agent_metrics,
        write_transactions,
    )

    # Write transactions for this day
    txs = orch.get_transactions_for_day(day)
    if txs:
        tx_count = write_transactions(db_manager.conn, sim_id, txs)
        log_info(f"  Persisted {tx_count} transactions for day {day}", quiet)

    # Write agent metrics for this day
    metrics = orch.get_daily_agent_metrics(day)
    if metrics:
        metrics_count = write_daily_agent_metrics(db_manager.conn, sim_id, metrics)
        log_info(f"  Persisted {metrics_count} agent metrics for day {day}", quiet)

    # Write collateral events for this day
    collateral_events = orch.get_collateral_events_for_day(day)
    if collateral_events:
        df = pl.DataFrame(collateral_events)
        # Insert excluding auto-generated id column
        db_manager.conn.execute(
            """
            INSERT INTO collateral_events (
                simulation_id, agent_id, tick, day, action, amount, reason, layer,
                balance_before, posted_collateral_before, posted_collateral_after,
                available_capacity_after
            )
            SELECT * FROM df
        """
        )
        log_info(
            f"  Persisted {len(collateral_events)} collateral events for day {day}",
            quiet,
        )

    # Write agent queue snapshots for this day
    queue_snapshot_count = 0
    for agent_id in orch.get_agent_ids():
        queue_contents = orch.get_agent_queue1_contents(agent_id)
        if queue_contents:
            queue_data = [
                {
                    "simulation_id": sim_id,
                    "agent_id": agent_id,
                    "day": day,
                    "queue_type": "queue1",
                    "position": idx,
                    "transaction_id": tx_id,
                }
                for idx, tx_id in enumerate(queue_contents)
            ]
            df = pl.DataFrame(queue_data)
            db_manager.conn.execute(
                "INSERT INTO agent_queue_snapshots SELECT * FROM df"
            )
            queue_snapshot_count += len(queue_contents)
    if queue_snapshot_count > 0:
        log_info(
            f"  Persisted {queue_snapshot_count} queue snapshots for day {day}", quiet
        )

    # Write LSM cycles for this day
    lsm_cycles = orch.get_lsm_cycles_for_day(day)
    if lsm_cycles:
        lsm_data = [
            {
                "simulation_id": sim_id,
                "tick": cycle["tick"],
                "day": cycle["day"],
                "cycle_type": cycle["cycle_type"],
                "cycle_length": cycle["cycle_length"],
                "agents": json.dumps(cycle["agents"]),
                "transactions": json.dumps(cycle["transactions"]),
                "settled_value": cycle["settled_value"],
                "total_value": cycle["total_value"],
            }
            for cycle in lsm_cycles
        ]
        df = pl.DataFrame(lsm_data)
        db_manager.conn.execute(
            """
            INSERT INTO lsm_cycles (
                simulation_id, tick, day, cycle_type, cycle_length,
                agents, transactions, settled_value, total_value
            ) SELECT
                simulation_id, tick, day, cycle_type, cycle_length,
                agents, transactions, settled_value, total_value
            FROM df
        """
        )
        log_info(f"  Persisted {len(lsm_cycles)} LSM cycles for day {day}", quiet)


def _persist_simulation_metadata(
    db_manager,
    sim_id: str,
    config: Path,
    config_dict: dict,
    ffi_dict: dict,
    agent_ids: list,
    total_arrivals: int,
    total_settlements: int,
    total_costs: int,
    sim_duration: float,
    quiet: bool = False,
) -> None:
    """Persist final simulation metadata to database tables.

    This helper encapsulates the simulation metadata persistence logic
    that was duplicated across normal and verbose modes.

    Args:
        db_manager: Database manager instance
        sim_id: Simulation ID
        config: Path to configuration file
        config_dict: Configuration dictionary
        ffi_dict: FFI configuration dictionary
        agent_ids: List of agent IDs
        total_arrivals: Total number of transaction arrivals
        total_settlements: Total number of settlements
        total_costs: Total costs in cents
        sim_duration: Simulation duration in seconds
        quiet: Whether to suppress log messages
    """
    import hashlib

    config_hash = hashlib.sha256(str(config_dict).encode()).hexdigest()

    # Write simulation run record
    # Calculate timestamps
    end_time = datetime.now()
    start_time_dt = end_time - timedelta(seconds=sim_duration)
    ticks_per_second = (
        (ffi_dict["ticks_per_day"] * ffi_dict["num_days"]) / sim_duration
        if sim_duration > 0
        else 0
    )

    db_manager.conn.execute(
        """
        INSERT INTO simulation_runs (
            simulation_id, config_name, config_hash, description,
            start_time, end_time,
            ticks_per_day, num_days, rng_seed,
            status, total_transactions
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            sim_id,
            config.name,
            config_hash,
            f"Simulation run from {config.name}",
            start_time_dt,
            end_time,
            ffi_dict["ticks_per_day"],
            ffi_dict["num_days"],
            ffi_dict["rng_seed"],
            "completed",
            total_arrivals,
        ],
    )

    # Serialize config to JSON for storage
    config_json = json.dumps(config_dict)

    # Persist to simulations table (Phase 5 query interface)
    db_manager.conn.execute(
        """
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents, config_json,
            status, started_at, completed_at,
            total_arrivals, total_settlements, total_cost_cents,
            duration_seconds, ticks_per_second
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            sim_id,
            config.name,
            config_hash,
            ffi_dict["rng_seed"],
            ffi_dict["ticks_per_day"],
            ffi_dict["num_days"],
            len(agent_ids),
            config_json,
            "completed",
            start_time_dt,
            end_time,
            total_arrivals,
            total_settlements,
            total_costs,
            sim_duration,
            ticks_per_second,
        ],
    )

    log_success(f"Simulation metadata persisted (ID: {sim_id})", quiet)


def run_simulation(
    config: Annotated[
        Path,
        typer.Option(
            "--config",
            "-c",
            help="Configuration file (YAML or JSON)",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    ticks: Annotated[
        Optional[int],
        typer.Option("--ticks", "-t", help="Override number of ticks to run"),
    ] = None,
    seed: Annotated[
        Optional[int],
        typer.Option("--seed", "-s", help="Override RNG seed"),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress logs (stdout only)"),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option(
            "--output",
            "-o",
            help="Output format",
            case_sensitive=False,
        ),
    ] = "json",
    stream: Annotated[
        bool,
        typer.Option(
            "--stream",
            help="Stream tick results as JSONL",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Verbose mode: show detailed events in real-time",
        ),
    ] = False,
    persist: Annotated[
        bool,
        typer.Option(
            "--persist",
            "-p",
            help="Persist transactions and metrics to database",
        ),
    ] = False,
    full_replay: Annotated[
        bool,
        typer.Option(
            "--full-replay",
            help="Capture all per-tick data for perfect replay (requires --persist). Data is batched and written at EOD.",
        ),
    ] = False,
    db_path: Annotated[
        str,
        typer.Option(
            "--db-path",
            help="Database file path (default: simulation_data.db)",
        ),
    ] = "simulation_data.db",
    simulation_id: Annotated[
        Optional[str],
        typer.Option(
            "--simulation-id",
            help="Custom simulation ID (auto-generated if not provided)",
        ),
    ] = None,
):
    """Run a simulation from a configuration file.

    Examples:

        # Basic run with JSON output
        payment-sim run --config scenario.yaml

        # AI-friendly quiet mode
        payment-sim run --config cfg.yaml --quiet

        # Override parameters
        payment-sim run --config cfg.yaml --seed 999 --ticks 500

        # Stream results for long simulations
        payment-sim run --config large.yaml --stream

        # Verbose mode: show detailed real-time events
        payment-sim run --config scenario.yaml --verbose --ticks 20
    """
    try:
        # Validate full_replay requires persist
        if full_replay and not persist:
            log_error("--full-replay requires --persist to be enabled")
            raise typer.Exit(1)

        # Load configuration
        log_info(f"Loading configuration from {config}", quiet)

        with open(config) as f:
            if config.suffix in [".yaml", ".yml"]:
                config_dict = yaml.safe_load(f)
            elif config.suffix == ".json":
                import json

                config_dict = json.load(f)
            else:
                log_error(f"Unsupported file format: {config.suffix}")
                raise typer.Exit(1)

        # Apply overrides
        if seed is not None:
            config_dict.setdefault("simulation", {})["rng_seed"] = seed
            log_info(f"Overriding seed: {seed}", quiet)

        if ticks is not None:
            config_dict.setdefault("simulation", {})["num_days"] = 1
            config_dict["simulation"]["ticks_per_day"] = ticks
            log_info(f"Overriding ticks: {ticks}", quiet)

        # Validate configuration
        try:
            sim_config = SimulationConfig.from_dict(config_dict)
        except Exception as e:
            log_error(f"Invalid configuration: {e}")
            raise typer.Exit(1)

        # Convert to FFI format
        ffi_dict = sim_config.to_ffi_dict()

        # Calculate total ticks
        total_ticks = ffi_dict["ticks_per_day"] * ffi_dict["num_days"]

        log_info(f"Creating simulation (seed: {ffi_dict['rng_seed']})", quiet)

        # Create orchestrator
        start_time = time.time()
        orch = Orchestrator.new(ffi_dict)
        create_time = time.time() - start_time

        log_success(f"Simulation created in {create_time:.3f}s", quiet)

        # Initialize persistence if enabled
        db_manager = None
        sim_id = None
        if persist:
            import hashlib
            import json

            from payment_simulator.persistence.connection import DatabaseManager
            from payment_simulator.persistence.writers import (
                write_daily_agent_metrics,
                write_policy_snapshots,
                write_transactions,
            )

            sim_id = simulation_id or f"sim-{uuid.uuid4().hex[:8]}"
            log_info(f"Persistence enabled (DB: {db_path}, ID: {sim_id})", quiet)

            db_manager = DatabaseManager(db_path)

            # Initialize schema if needed (idempotent - safe to call multiple times)
            if not db_manager.is_initialized():
                # Fresh database - initialize without verbose validation
                log_info("Database not initialized, creating schema...", quiet)
                db_manager.initialize_schema()
            else:
                # Database exists - validate schema
                if not db_manager.validate_schema(quiet=quiet):
                    log_info("Schema incomplete, re-initializing...", quiet)
                    db_manager.initialize_schema()

            # Capture initial policy snapshots (Phase 4: Policy Snapshot Tracking)
            log_info("Capturing initial policy snapshots...", quiet)
            policies = orch.get_agent_policies()
            snapshots = []
            for policy in policies:
                policy_json = json.dumps(policy["policy_config"], sort_keys=True)
                policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()

                snapshots.append(
                    {
                        "simulation_id": sim_id,
                        "agent_id": policy["agent_id"],
                        "snapshot_day": 0,
                        "snapshot_tick": 0,
                        "policy_hash": policy_hash,
                        "policy_json": policy_json,
                        "created_by": "init",
                    }
                )

            if snapshots:
                policy_count = write_policy_snapshots(db_manager.conn, snapshots)
                log_info(f"  Persisted {policy_count} initial policy snapshots", quiet)

        # Run simulation
        if verbose:
            # Verbose mode: show detailed events in real-time
            log_info(
                f"Running {total_ticks} ticks (verbose mode)...", True
            )  # Always suppress this in verbose

            # Get agent IDs for state tracking
            agent_ids = orch.get_agent_ids()

            # Track previous balances for change detection
            prev_balances = {
                agent_id: orch.get_agent_balance(agent_id) for agent_id in agent_ids
            }

            # Track daily statistics for end-of-day summaries
            ticks_per_day = ffi_dict["ticks_per_day"]
            daily_stats = {
                "arrivals": 0,
                "settlements": 0,
                "lsm_releases": 0,
                "costs": 0,
            }

            # Initialize buffers for full replay mode (if enabled)
            if persist and full_replay and db_manager:
                log_info(
                    "Full replay mode enabled: collecting per-tick data", quiet=True
                )
                # Buffers accumulate data during the day
                day_policy_decisions = []
                day_agent_states = []
                day_queue_snapshots = []

                # Track previous costs for calculating deltas
                prev_agent_costs = {agent_id: {} for agent_id in agent_ids}

            tick_results = []
            sim_start = time.time()

            for tick_num in range(total_ticks):
                # ═══════════════════════════════════════════════════════════
                # TICK HEADER
                # ═══════════════════════════════════════════════════════════
                log_tick_start(tick_num)

                # Execute tick
                result = orch.tick()
                tick_results.append(result)

                # Update daily stats
                daily_stats["arrivals"] += result["num_arrivals"]
                daily_stats["settlements"] += result["num_settlements"]
                daily_stats["lsm_releases"] += result["num_lsm_releases"]
                daily_stats["costs"] += result["total_cost"]

                # Get all events for this tick
                events = orch.get_tick_events(tick_num)

                # Full replay mode: collect data in memory
                if persist and full_replay and db_manager:
                    import json

                    current_day = tick_num // ticks_per_day

                    # 1. Collect policy decisions
                    policy_events = [
                        e
                        for e in events
                        if e.get("event_type")
                        in ["PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"]
                    ]
                    for event in policy_events:
                        day_policy_decisions.append(
                            {
                                "simulation_id": sim_id,
                                "agent_id": event["agent_id"],
                                "tick": tick_num,
                                "day": current_day,
                                "decision_type": event["event_type"]
                                .replace("Policy", "")
                                .lower(),
                                "tx_id": event["tx_id"],
                                "reason": event.get("reason"),
                                "num_splits": event.get("num_splits"),
                                "child_tx_ids": (
                                    json.dumps(event.get("child_ids", []))
                                    if event.get("child_ids")
                                    else None
                                ),
                            }
                        )

                    # 2. Collect agent states
                    for agent_id in agent_ids:
                        current_balance = orch.get_agent_balance(agent_id)
                        costs = orch.get_agent_accumulated_costs(agent_id)
                        collateral = orch.get_agent_collateral_posted(agent_id) or 0

                        # Calculate cost deltas
                        prev_costs = prev_agent_costs.get(agent_id, {})

                        day_agent_states.append(
                            {
                                "simulation_id": sim_id,
                                "agent_id": agent_id,
                                "tick": tick_num,
                                "day": current_day,
                                "balance": current_balance,
                                "balance_change": current_balance
                                - prev_balances[agent_id],
                                "posted_collateral": collateral,
                                "liquidity_cost": costs["liquidity_cost"],
                                "delay_cost": costs["delay_cost"],
                                "collateral_cost": costs["collateral_cost"],
                                "penalty_cost": costs["deadline_penalty"],
                                "split_friction_cost": costs["split_friction_cost"],
                                "liquidity_cost_delta": costs["liquidity_cost"]
                                - prev_costs.get("liquidity_cost", 0),
                                "delay_cost_delta": costs["delay_cost"]
                                - prev_costs.get("delay_cost", 0),
                                "collateral_cost_delta": costs["collateral_cost"]
                                - prev_costs.get("collateral_cost", 0),
                                "penalty_cost_delta": costs["deadline_penalty"]
                                - prev_costs.get("deadline_penalty", 0),
                                "split_friction_cost_delta": costs[
                                    "split_friction_cost"
                                ]
                                - prev_costs.get("split_friction_cost", 0),
                            }
                        )

                        # Update previous costs for next tick
                        prev_agent_costs[agent_id] = costs

                    # 3. Collect queue snapshots
                    for agent_id in agent_ids:
                        # Queue 1 (agent's internal queue)
                        queue1_contents = orch.get_agent_queue1_contents(agent_id)
                        for position, tx_id in enumerate(queue1_contents):
                            day_queue_snapshots.append(
                                {
                                    "simulation_id": sim_id,
                                    "agent_id": agent_id,
                                    "tick": tick_num,
                                    "queue_type": "queue1",
                                    "position": position,
                                    "tx_id": tx_id,
                                }
                            )

                    # RTGS queue (central queue)
                    rtgs_contents = orch.get_rtgs_queue_contents()
                    for position, tx_id in enumerate(rtgs_contents):
                        tx = orch.get_transaction_details(tx_id)
                        if tx:
                            day_queue_snapshots.append(
                                {
                                    "simulation_id": sim_id,
                                    "agent_id": tx["sender_id"],
                                    "tick": tick_num,
                                    "queue_type": "rtgs",
                                    "position": position,
                                    "tx_id": tx_id,
                                }
                            )

                # ═══════════════════════════════════════════════════════════
                # SECTION 1: ARRIVALS (detailed)
                # ═══════════════════════════════════════════════════════════
                if result["num_arrivals"] > 0:
                    log_transaction_arrivals(orch, events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 2: POLICY DECISIONS
                # ═══════════════════════════════════════════════════════════
                log_policy_decisions(events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 3: SETTLEMENTS (detailed with mechanisms)
                # ═══════════════════════════════════════════════════════════
                if result["num_settlements"] > 0 or any(
                    e.get("event_type") in ["LsmBilateralOffset", "LsmCycleSettlement"]
                    for e in events
                ):
                    log_settlement_details(orch, events, tick_num)

                # ═══════════════════════════════════════════════════════════
                # SECTION 4: LSM CYCLE VISUALIZATION
                # ═══════════════════════════════════════════════════════════
                log_lsm_cycle_visualization(events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 5: COLLATERAL ACTIVITY
                # ═══════════════════════════════════════════════════════════
                log_collateral_activity(events)

                # ═══════════════════════════════════════════════════════════
                # SECTION 6: AGENT STATES (detailed queues)
                # ═══════════════════════════════════════════════════════════
                for agent_id in agent_ids:
                    current_balance = orch.get_agent_balance(agent_id)
                    balance_change = current_balance - prev_balances[agent_id]

                    # Only show agents with activity or non-empty queues
                    queue1_size = orch.get_queue1_size(agent_id)
                    rtgs_queue = orch.get_rtgs_queue_contents()
                    agent_in_rtgs = any(
                        orch.get_transaction_details(tx_id).get("sender_id") == agent_id
                        for tx_id in rtgs_queue
                        if orch.get_transaction_details(tx_id)
                    )

                    if balance_change != 0 or queue1_size > 0 or agent_in_rtgs:
                        log_agent_queues_detailed(
                            orch, agent_id, current_balance, balance_change
                        )

                    prev_balances[agent_id] = current_balance

                # ═══════════════════════════════════════════════════════════
                # SECTION 7: COST BREAKDOWN
                # ═══════════════════════════════════════════════════════════
                if result["total_cost"] > 0:
                    log_cost_breakdown(orch, agent_ids)

                # ═══════════════════════════════════════════════════════════
                # SECTION 8: TICK SUMMARY
                # ═══════════════════════════════════════════════════════════
                total_queued = sum(orch.get_queue1_size(aid) for aid in agent_ids)
                log_tick_summary(
                    result["num_arrivals"],
                    result["num_settlements"],
                    result["num_lsm_releases"],
                    total_queued,
                )

                # ═══════════════════════════════════════════════════════════
                # END-OF-DAY SUMMARY (if applicable)
                # ═══════════════════════════════════════════════════════════
                if (tick_num + 1) % ticks_per_day == 0:
                    current_day = tick_num // ticks_per_day

                    # Gather agent statistics for end-of-day summary
                    agent_stats = []
                    for agent_id in agent_ids:
                        balance = orch.get_agent_balance(agent_id)
                        credit_limit = orch.get_agent_credit_limit(agent_id)

                        # Calculate credit utilization
                        credit_util = 0
                        if credit_limit and credit_limit > 0:
                            used = max(0, credit_limit - balance)
                            credit_util = (used / credit_limit) * 100

                        # Get queue sizes
                        queue1_size = orch.get_queue1_size(agent_id)
                        rtgs_queue = orch.get_rtgs_queue_contents()
                        queue2_size = sum(
                            1
                            for tx_id in rtgs_queue
                            if orch.get_transaction_details(tx_id)
                            and orch.get_transaction_details(tx_id).get("sender_id")
                            == agent_id
                        )

                        # Get costs for this agent (cumulative for the day)
                        costs = orch.get_agent_accumulated_costs(agent_id)
                        agent_total_costs = 0
                        if costs:
                            agent_total_costs = sum(
                                [
                                    costs.get("liquidity_cost", 0),
                                    costs.get("delay_cost", 0),
                                    costs.get("collateral_cost", 0),
                                    costs.get(
                                        "deadline_penalty", 0
                                    ),  # Note: FFI exports as "deadline_penalty"
                                    costs.get("split_friction_cost", 0),
                                ]
                            )

                        agent_stats.append(
                            {
                                "id": agent_id,
                                "final_balance": balance,
                                "credit_utilization": credit_util,
                                "queue1_size": queue1_size,
                                "queue2_size": queue2_size,
                                "total_costs": agent_total_costs,
                            }
                        )

                    log_end_of_day_statistics(
                        day=current_day,
                        total_arrivals=daily_stats["arrivals"],
                        total_settlements=daily_stats["settlements"],
                        total_lsm_releases=daily_stats["lsm_releases"],
                        total_costs=daily_stats["costs"],
                        agent_stats=agent_stats,
                    )

                    # Persist at end of day if enabled
                    if persist and db_manager:
                        _persist_day_data(
                            orch, db_manager, sim_id, current_day, quiet=True
                        )

                    # Full replay mode: batch write all data for this day
                    if persist and full_replay and db_manager:
                        from payment_simulator.persistence.writers import (
                            write_policy_decisions_batch,
                            write_tick_agent_states_batch,
                            write_tick_queue_snapshots_batch,
                        )

                        log_info(
                            f"  Writing full replay data for day {current_day}...",
                            quiet=True,
                        )
                        batch_start = time.time()

                        # Write policy decisions
                        if day_policy_decisions:
                            policy_count = write_policy_decisions_batch(
                                db_manager.conn, day_policy_decisions
                            )
                            log_info(
                                f"    → {policy_count} policy decisions", quiet=True
                            )

                        # Write agent states
                        if day_agent_states:
                            states_count = write_tick_agent_states_batch(
                                db_manager.conn, day_agent_states
                            )
                            log_info(
                                f"    → {states_count} agent state snapshots",
                                quiet=True,
                            )

                        # Write queue snapshots
                        if day_queue_snapshots:
                            queues_count = write_tick_queue_snapshots_batch(
                                db_manager.conn, day_queue_snapshots
                            )
                            log_info(
                                f"    → {queues_count} queue snapshots", quiet=True
                            )

                        batch_duration = time.time() - batch_start
                        log_info(
                            f"  Full replay data written in {batch_duration:.2f}s",
                            quiet=True,
                        )

                        # Clear buffers for next day
                        day_policy_decisions = []
                        day_agent_states = []
                        day_queue_snapshots = []

                    # Reset daily stats for next day
                    daily_stats = {
                        "arrivals": 0,
                        "settlements": 0,
                        "lsm_releases": 0,
                        "costs": 0,
                    }

            sim_duration = time.time() - sim_start
            ticks_per_second = total_ticks / sim_duration if sim_duration > 0 else 0

            log_success(
                f"\nSimulation complete: {total_ticks} ticks in {sim_duration:.2f}s ({ticks_per_second:.1f} ticks/s)",
                False,
            )

            # Build and output final summary as JSON
            agent_ids = orch.get_agent_ids()
            agents = []
            for agent_id in agent_ids:
                agents.append(
                    {
                        "id": agent_id,
                        "final_balance": orch.get_agent_balance(agent_id),
                        "queue1_size": orch.get_queue1_size(agent_id),
                    }
                )

            total_arrivals = sum(r["num_arrivals"] for r in tick_results)
            total_settlements = sum(r["num_settlements"] for r in tick_results)
            total_lsm_releases = sum(r["num_lsm_releases"] for r in tick_results)
            total_costs = sum(r["total_cost"] for r in tick_results)

            output_data = {
                "simulation": {
                    "config_file": str(config),
                    "seed": ffi_dict["rng_seed"],
                    "ticks_executed": total_ticks,
                    "duration_seconds": round(sim_duration, 3),
                    "ticks_per_second": round(ticks_per_second, 2),
                },
                "metrics": {
                    "total_arrivals": total_arrivals,
                    "total_settlements": total_settlements,
                    "total_lsm_releases": total_lsm_releases,
                    "settlement_rate": (
                        round(total_settlements / total_arrivals, 4)
                        if total_arrivals > 0
                        else 0
                    ),
                },
                "agents": agents,
                "costs": {
                    "total_cost": total_costs,
                },
                "performance": {
                    "ticks_per_second": round(ticks_per_second, 2),
                },
            }

            # Persist simulation metadata if enabled
            if persist and db_manager:
                _persist_simulation_metadata(
                    db_manager,
                    sim_id,
                    config,
                    config_dict,
                    ffi_dict,
                    agent_ids,
                    total_arrivals,
                    total_settlements,
                    total_costs,
                    sim_duration,
                    quiet=False,
                )

                # Add simulation_id to output
                output_data["simulation"]["simulation_id"] = sim_id
                output_data["simulation"]["database"] = db_path

            output_json(output_data)

        elif stream:
            # Streaming mode: output JSONL
            log_info(f"Running {total_ticks} ticks (streaming)...", quiet)

            # Track results for persistence metadata
            tick_results = []
            sim_start = time.time()

            # Track days for persistence
            ticks_per_day = ffi_dict["ticks_per_day"]
            num_days = ffi_dict["num_days"]

            for day in range(num_days):
                # Run ticks for this day
                for tick_in_day in range(ticks_per_day):
                    tick_result = orch.tick()
                    tick_results.append(tick_result)

                    # Stream output
                    output_jsonl(
                        {
                            "tick": tick_result["tick"],
                            "arrivals": tick_result["num_arrivals"],
                            "settlements": tick_result["num_settlements"],
                            "lsm_releases": tick_result["num_lsm_releases"],
                            "costs": tick_result["total_cost"],
                        }
                    )

                # Persist at end of day if enabled
                if persist and db_manager:
                    _persist_day_data(orch, db_manager, sim_id, day, quiet)

            sim_duration = time.time() - sim_start
            log_success(f"Completed {total_ticks} ticks", quiet)

            # Persist simulation metadata if enabled
            if persist and db_manager:
                agent_ids = orch.get_agent_ids()
                total_arrivals = sum(r["num_arrivals"] for r in tick_results)
                total_settlements = sum(r["num_settlements"] for r in tick_results)
                total_costs = sum(r["total_cost"] for r in tick_results)

                _persist_simulation_metadata(
                    db_manager,
                    sim_id,
                    config,
                    config_dict,
                    ffi_dict,
                    agent_ids,
                    total_arrivals,
                    total_settlements,
                    total_costs,
                    sim_duration,
                    quiet,
                )

        else:
            # Normal mode: run all ticks then output summary
            log_info(f"Running {total_ticks} ticks...", quiet)

            tick_results = []
            sim_start = time.time()

            # Track days for persistence
            ticks_per_day = ffi_dict["ticks_per_day"]
            num_days = ffi_dict["num_days"]
            current_tick = 0

            if not quiet:
                with create_progress() as progress:
                    task = progress.add_task(
                        f"[cyan]Running simulation...", total=total_ticks
                    )

                    for day in range(num_days):
                        # Run ticks for this day
                        for _ in range(ticks_per_day):
                            result = orch.tick()
                            tick_results.append(result)
                            current_tick += 1
                            progress.update(task, advance=1)

                        # Persist at end of day if enabled
                        if persist and db_manager:
                            _persist_day_data(orch, db_manager, sim_id, day, quiet)
            else:
                for day in range(num_days):
                    # Run ticks for this day
                    for _ in range(ticks_per_day):
                        result = orch.tick()
                        tick_results.append(result)
                        current_tick += 1

                    # Persist at end of day if enabled
                    if persist and db_manager:
                        _persist_day_data(orch, db_manager, sim_id, day, quiet)

            sim_duration = time.time() - sim_start
            ticks_per_second = total_ticks / sim_duration if sim_duration > 0 else 0

            log_success(
                f"Completed in {sim_duration:.2f}s ({ticks_per_second:.1f} ticks/s)",
                quiet,
            )

            # Collect final state
            agent_ids = orch.get_agent_ids()
            agents = []
            for agent_id in agent_ids:
                agents.append(
                    {
                        "id": agent_id,
                        "final_balance": orch.get_agent_balance(agent_id),
                        "queue1_size": orch.get_queue1_size(agent_id),
                    }
                )

            # Aggregate metrics
            total_arrivals = sum(r["num_arrivals"] for r in tick_results)
            total_settlements = sum(r["num_settlements"] for r in tick_results)
            total_lsm_releases = sum(r["num_lsm_releases"] for r in tick_results)
            total_costs = sum(r["total_cost"] for r in tick_results)

            # Build output
            output_data = {
                "simulation": {
                    "config_file": str(config),
                    "seed": ffi_dict["rng_seed"],
                    "ticks_executed": total_ticks,
                    "duration_seconds": round(sim_duration, 3),
                    "ticks_per_second": round(ticks_per_second, 2),
                },
                "metrics": {
                    "total_arrivals": total_arrivals,
                    "total_settlements": total_settlements,
                    "total_lsm_releases": total_lsm_releases,
                    "settlement_rate": (
                        round(total_settlements / total_arrivals, 4)
                        if total_arrivals > 0
                        else 0
                    ),
                },
                "agents": agents,
                "costs": {
                    "total_cost": total_costs,
                },
                "performance": {
                    "ticks_per_second": round(ticks_per_second, 2),
                },
            }

            # Persist simulation metadata if enabled
            if persist and db_manager:
                _persist_simulation_metadata(
                    db_manager,
                    sim_id,
                    config,
                    config_dict,
                    ffi_dict,
                    agent_ids,
                    total_arrivals,
                    total_settlements,
                    total_costs,
                    sim_duration,
                    quiet,
                )

            # Output results
            if output_format.lower() == "json":
                # Add simulation_id to output if persisted
                if persist and sim_id:
                    output_data["simulation"]["simulation_id"] = sim_id
                    output_data["simulation"]["database"] = db_path

                output_json(output_data)
            else:
                log_error(f"Unsupported output format: {output_format}")
                raise typer.Exit(1)

    except typer.Exit:
        raise
    except KeyboardInterrupt:
        log_error("Interrupted by user")
        raise typer.Exit(130)
    except Exception as e:
        log_error(f"Error: {e}")
        if not quiet:
            import traceback

            console_err = typer.get_text_stream("stderr")
            console_err.write(traceback.format_exc())
        raise typer.Exit(1)
