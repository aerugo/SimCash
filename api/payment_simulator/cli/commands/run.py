"""Run command - Execute simulations from config files."""

import json
import time
import uuid
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer
import polars as pl

from payment_simulator.cli.output import (
    output_json,
    output_jsonl,
    log_info,
    log_success,
    log_error,
    create_progress,
    log_tick_start,
    log_arrivals,
    log_settlements,
    log_lsm_activity,
    log_agent_state,
    log_costs,
    log_tick_summary,
    # Enhanced verbose mode functions
    log_transaction_arrivals,
    log_settlement_details,
    log_agent_queues_detailed,
    log_policy_decisions,
    log_collateral_activity,
    log_cost_breakdown,
    log_lsm_cycle_visualization,
    log_end_of_day_statistics,
)
from payment_simulator.config import SimulationConfig
from payment_simulator._core import Orchestrator


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
        total_ticks = (
            ffi_dict["ticks_per_day"]
            * ffi_dict["num_days"]
        )

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
            from payment_simulator.persistence.connection import DatabaseManager
            from payment_simulator.persistence.writers import (
                write_transactions,
                write_daily_agent_metrics,
                write_policy_snapshots,
            )
            import hashlib
            import json

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

                snapshots.append({
                    "simulation_id": sim_id,
                    "agent_id": policy["agent_id"],
                    "snapshot_day": 0,
                    "snapshot_tick": 0,
                    "policy_hash": policy_hash,
                    "policy_json": policy_json,
                    "created_by": "init",
                })

            if snapshots:
                policy_count = write_policy_snapshots(db_manager.conn, snapshots)
                log_info(f"  Persisted {policy_count} initial policy snapshots", quiet)

        # Run simulation
        if verbose:
            # Verbose mode: show detailed events in real-time
            log_info(f"Running {total_ticks} ticks (verbose mode)...", True)  # Always suppress this in verbose

            # Get agent IDs for state tracking
            agent_ids = orch.get_agent_ids()

            # Track previous balances for change detection
            prev_balances = {agent_id: orch.get_agent_balance(agent_id) for agent_id in agent_ids}

            # Track daily statistics for end-of-day summaries
            ticks_per_day = ffi_dict["ticks_per_day"]
            daily_stats = {
                "arrivals": 0,
                "settlements": 0,
                "lsm_releases": 0,
                "costs": 0,
            }

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
                if result["num_settlements"] > 0 or any(e.get("event_type") in ["LsmBilateralOffset", "LsmCycleSettlement"] for e in events):
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
                        log_agent_queues_detailed(orch, agent_id, current_balance, balance_change)

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
                    total_queued
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
                            1 for tx_id in rtgs_queue
                            if orch.get_transaction_details(tx_id) and
                            orch.get_transaction_details(tx_id).get("sender_id") == agent_id
                        )

                        # Get costs for this agent (cumulative for the day)
                        costs = orch.get_agent_accumulated_costs(agent_id)
                        agent_total_costs = 0
                        if costs:
                            agent_total_costs = sum([
                                costs.get("liquidity_cost", 0),
                                costs.get("delay_cost", 0),
                                costs.get("collateral_cost", 0),
                                costs.get("penalty_cost", 0),
                                costs.get("split_friction_cost", 0),
                            ])

                        agent_stats.append({
                            "id": agent_id,
                            "final_balance": balance,
                            "credit_utilization": credit_util,
                            "queue1_size": queue1_size,
                            "queue2_size": queue2_size,
                            "total_costs": agent_total_costs,
                        })

                    log_end_of_day_statistics(
                        day=current_day,
                        total_arrivals=daily_stats["arrivals"],
                        total_settlements=daily_stats["settlements"],
                        total_lsm_releases=daily_stats["lsm_releases"],
                        total_costs=daily_stats["costs"],
                        agent_stats=agent_stats,
                    )

                    # Reset daily stats for next day
                    daily_stats = {
                        "arrivals": 0,
                        "settlements": 0,
                        "lsm_releases": 0,
                        "costs": 0,
                    }

            sim_duration = time.time() - sim_start
            ticks_per_second = total_ticks / sim_duration if sim_duration > 0 else 0

            log_success(f"\nSimulation complete: {total_ticks} ticks in {sim_duration:.2f}s ({ticks_per_second:.1f} ticks/s)", False)

            # Build and output final summary as JSON
            agent_ids = orch.get_agent_ids()
            agents = []
            for agent_id in agent_ids:
                agents.append({
                    "id": agent_id,
                    "final_balance": orch.get_agent_balance(agent_id),
                    "queue1_size": orch.get_queue1_size(agent_id),
                })

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
                    "settlement_rate": round(total_settlements / total_arrivals, 4) if total_arrivals > 0 else 0,
                },
                "agents": agents,
                "costs": {
                    "total_cost": total_costs,
                },
                "performance": {
                    "ticks_per_second": round(ticks_per_second, 2),
                },
            }
            output_json(output_data)

        elif stream:
            # Streaming mode: output JSONL
            log_info(f"Running {total_ticks} ticks (streaming)...", quiet)

            for tick_num in range(total_ticks):
                tick_result = orch.tick()
                output_jsonl({
                    "tick": tick_result["tick"],
                    "arrivals": tick_result["num_arrivals"],
                    "settlements": tick_result["num_settlements"],
                    "lsm_releases": tick_result["num_lsm_releases"],
                    "costs": tick_result["total_cost"],
                })

            log_success(f"Completed {total_ticks} ticks", quiet)

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
                        f"[cyan]Running simulation...",
                        total=total_ticks
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

                            # Write collateral events for this day (Phase 2.3)
                            collateral_events = orch.get_collateral_events_for_day(day)
                            if collateral_events:
                                df = pl.DataFrame(collateral_events)
                                db_manager.conn.execute("INSERT INTO collateral_events SELECT * FROM df")
                                log_info(f"  Persisted {len(collateral_events)} collateral events for day {day}", quiet)

                            # Write agent queue snapshots for this day (Phase 3.3)
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
                                    db_manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")
                                    queue_snapshot_count += len(queue_contents)
                            if queue_snapshot_count > 0:
                                log_info(f"  Persisted {queue_snapshot_count} queue snapshots for day {day}", quiet)

                            # Write LSM cycles for this day (Phase 4.3)
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
                                db_manager.conn.execute("INSERT INTO lsm_cycles (simulation_id, tick, day, cycle_type, cycle_length, agents, transactions, settled_value, total_value) SELECT simulation_id, tick, day, cycle_type, cycle_length, agents, transactions, settled_value, total_value FROM df")
                                log_info(f"  Persisted {len(lsm_cycles)} LSM cycles for day {day}", quiet)
            else:
                for day in range(num_days):
                    # Run ticks for this day
                    for _ in range(ticks_per_day):
                        result = orch.tick()
                        tick_results.append(result)
                        current_tick += 1

                    # Persist at end of day if enabled
                    if persist and db_manager:
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

                        # Write collateral events for this day (Phase 2.3)
                        collateral_events = orch.get_collateral_events_for_day(day)
                        if collateral_events:
                            df = pl.DataFrame(collateral_events)
                            db_manager.conn.execute("INSERT INTO collateral_events SELECT * FROM df")
                            log_info(f"  Persisted {len(collateral_events)} collateral events for day {day}", quiet)

                        # Write agent queue snapshots for this day (Phase 3.3)
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
                                db_manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")
                                queue_snapshot_count += len(queue_contents)
                        if queue_snapshot_count > 0:
                            log_info(f"  Persisted {queue_snapshot_count} queue snapshots for day {day}", quiet)

                        # Write LSM cycles for this day (Phase 4.3)
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
                            db_manager.conn.execute("INSERT INTO lsm_cycles (simulation_id, tick, day, cycle_type, cycle_length, agents, transactions, settled_value, total_value) SELECT simulation_id, tick, day, cycle_type, cycle_length, agents, transactions, settled_value, total_value FROM df")
                            log_info(f"  Persisted {len(lsm_cycles)} LSM cycles for day {day}", quiet)

            sim_duration = time.time() - sim_start
            ticks_per_second = total_ticks / sim_duration if sim_duration > 0 else 0

            log_success(f"Completed in {sim_duration:.2f}s ({ticks_per_second:.1f} ticks/s)", quiet)

            # Collect final state
            agent_ids = orch.get_agent_ids()
            agents = []
            for agent_id in agent_ids:
                agents.append({
                    "id": agent_id,
                    "final_balance": orch.get_agent_balance(agent_id),
                    "queue1_size": orch.get_queue1_size(agent_id),
                })

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
                    "settlement_rate": round(total_settlements / total_arrivals, 4) if total_arrivals > 0 else 0,
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
                import hashlib
                config_hash = hashlib.sha256(str(config_dict).encode()).hexdigest()

                # Write simulation run record
                # Calculate timestamps
                end_time = datetime.now()
                start_time_dt = end_time - timedelta(seconds=sim_duration)

                db_manager.conn.execute("""
                    INSERT INTO simulation_runs (
                        simulation_id, config_name, config_hash, description,
                        start_time, end_time,
                        ticks_per_day, num_days, rng_seed,
                        status, total_transactions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
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
                ])

                # NEW: Persist to simulations table (Phase 5 query interface)
                # This enables list_simulations(), compare_simulations(), and other queries
                db_manager.conn.execute("""
                    INSERT INTO simulations (
                        simulation_id, config_file, config_hash, rng_seed,
                        ticks_per_day, num_days, num_agents,
                        status, started_at, completed_at,
                        total_arrivals, total_settlements, total_cost_cents,
                        duration_seconds, ticks_per_second
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    sim_id,
                    config.name,
                    config_hash,
                    ffi_dict["rng_seed"],
                    ffi_dict["ticks_per_day"],
                    ffi_dict["num_days"],
                    len(agent_ids),
                    "completed",
                    start_time_dt,
                    end_time,
                    total_arrivals,
                    total_settlements,
                    total_costs,
                    sim_duration,
                    ticks_per_second,
                ])

                log_success(f"Simulation metadata persisted (ID: {sim_id})", quiet)

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
