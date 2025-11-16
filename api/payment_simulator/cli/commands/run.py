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
    log_cost_accrual_events,
    log_cost_breakdown,
    log_costs,
    log_end_of_day_event,
    log_end_of_day_statistics,
    log_error,
    log_event_chronological,
    log_info,
    log_lsm_activity,
    log_lsm_cycle_visualization,
    log_performance_diagnostics,
    log_performance_diagnostics_compact,
    log_policy_decisions,
    log_queued_rtgs,
    log_settlement_details,
    log_settlements,
    log_success,
    log_tick_start,
    log_tick_summary,
    log_transaction_arrivals,
    output_json,
    output_jsonl,
)
from payment_simulator.cli.filters import EventFilter
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

    # LEGACY TABLE WRITE REMOVED (Phase 6: Unified Replay Architecture)
    # Collateral events now stored in simulation_events table via EventWriter
    # This legacy table write has been deprecated
    # collateral_events = orch.get_collateral_events_for_day(day)
    # if collateral_events:
    #     df = pl.DataFrame(collateral_events)
    #     db_manager.conn.execute(...)
    #     log_info(f"  Persisted {len(collateral_events)} collateral events...", quiet)

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

    # LEGACY TABLE WRITE REMOVED (Phase 6: Unified Replay Architecture)
    # LSM cycles now stored in simulation_events table via EventWriter
    # This legacy table write has been deprecated
    # lsm_cycles = orch.get_lsm_cycles_for_day(day)
    # if lsm_cycles:
    #     lsm_data = [{"simulation_id": sim_id, ...} for cycle in lsm_cycles]
    #     df = pl.DataFrame(lsm_data)
    #     db_manager.conn.execute(...)
    #     log_info(f"  Persisted {len(lsm_cycles)} LSM cycles...", quiet)


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
    orch: Orchestrator,
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
        orch: Orchestrator instance (for event persistence)
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

    # Persist all simulation events (Phase 2 - Event Timeline Enhancement)
    from payment_simulator.persistence.event_writer import write_events_batch

    events = orch.get_all_events()
    if events:
        event_count = write_events_batch(
            conn=db_manager.conn,
            simulation_id=sim_id,
            events=events,
            ticks_per_day=ffi_dict["ticks_per_day"],
        )
        log_info(f"  Persisted {event_count} simulation events", quiet)

    log_success(f"Simulation metadata persisted (ID: {sim_id})", quiet)


def _create_output_strategy(
    mode: str,
    orch: Orchestrator,
    agent_ids: list[str],
    ticks_per_day: int,
    quiet: bool,
    event_filter: Optional[EventFilter] = None,
    total_ticks: Optional[int] = None,
    show_debug: bool = False,
):
    """Factory function for creating mode-specific output strategies.

    This function creates the appropriate OutputStrategy implementation
    based on the execution mode (normal, verbose, stream, event_stream).

    Args:
        mode: Execution mode ("normal", "verbose", "stream", "event_stream")
        orch: Orchestrator instance
        agent_ids: List of agent IDs
        ticks_per_day: Ticks in one simulated day
        quiet: Whether to suppress progress output
        show_debug: If True, show performance diagnostics (verbose: detailed table, normal: compact)
        event_filter: Optional event filter for verbose/event_stream modes
        total_ticks: Total number of ticks (required for normal mode)

    Returns:
        OutputStrategy implementation for the specified mode

    Example:
        >>> strategy = _create_output_strategy(
        ...     mode="verbose",
        ...     orch=orch,
        ...     agent_ids=["BANK_A", "BANK_B"],
        ...     ticks_per_day=100,
        ...     quiet=False,
        ...     event_filter=None
        ... )
    """
    from payment_simulator.cli.execution.strategies import (
        EventStreamModeOutput,
        NormalModeOutput,
        StreamModeOutput,
        VerboseModeOutput,
    )

    if mode == "verbose":
        return VerboseModeOutput(orch, agent_ids, ticks_per_day, event_filter, show_debug)
    elif mode == "stream":
        return StreamModeOutput()
    elif mode == "event_stream":
        return EventStreamModeOutput()
    else:  # normal mode
        if total_ticks is None:
            raise ValueError("total_ticks is required for normal mode")
        return NormalModeOutput(quiet, total_ticks, show_debug)


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
            help="Verbose mode: show detailed events in real-time (grouped by category)",
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug",
            help="Show performance diagnostics for each tick (requires --verbose)",
        ),
    ] = False,
    event_stream: Annotated[
        bool,
        typer.Option(
            "--event-stream",
            help="Event stream mode: show all events chronologically (one-line format)",
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
    filter_event_type: Annotated[
        Optional[str],
        typer.Option(
            "--filter-event-type",
            help="Filter events by type (comma-separated, e.g., 'Arrival,Settlement')",
        ),
    ] = None,
    filter_agent: Annotated[
        Optional[str],
        typer.Option(
            "--filter-agent",
            help="Filter events by agent ID (matches agent_id or sender_id fields)",
        ),
    ] = None,
    filter_tx: Annotated[
        Optional[str],
        typer.Option(
            "--filter-tx",
            help="Filter events by transaction ID",
        ),
    ] = None,
    filter_tick_range: Annotated[
        Optional[str],
        typer.Option(
            "--filter-tick-range",
            help="Filter events by tick range (format: 'min-max', 'min-', or '-max')",
        ),
    ] = None,
    cost_chart: Annotated[
        bool,
        typer.Option(
            "--cost-chart",
            help="Generate and display cost chart after simulation (automatically enables --persist)",
        ),
    ] = False,
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

        # Event stream mode: chronological one-line events
        payment-sim run --config scenario.yaml --event-stream --ticks 50
    """
    try:
        # Validate mutually exclusive flags
        if verbose and event_stream:
            log_error("--verbose and --event-stream are mutually exclusive")
            raise typer.Exit(1)

        # Validate filter flags require verbose or event-stream mode
        has_filters = any(
            [filter_event_type, filter_agent, filter_tx, filter_tick_range]
        )
        if has_filters and not (verbose or event_stream):
            log_error(
                "Event filters (--filter-*) require either --verbose or --event-stream mode"
            )
            raise typer.Exit(1)

        # Validate full_replay requires persist
        if full_replay and not persist:
            log_error("--full-replay requires --persist to be enabled")
            raise typer.Exit(1)

        # Auto-enable persistence when --cost-chart is used
        if cost_chart:
            persist = True
            if not quiet:
                log_info("Auto-enabling persistence for cost chart generation", quiet)

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

        # Create event filter if any filters are specified
        event_filter = None
        if has_filters:
            event_filter = EventFilter.from_cli_args(
                filter_event_type=filter_event_type,
                filter_agent=filter_agent,
                filter_tx=filter_tx,
                filter_tick_range=filter_tick_range,
            )
            # Log filter configuration
            filter_desc = []
            if filter_event_type:
                filter_desc.append(f"types={filter_event_type}")
            if filter_agent:
                filter_desc.append(f"agent={filter_agent}")
            if filter_tx:
                filter_desc.append(f"tx={filter_tx}")
            if filter_tick_range:
                filter_desc.append(f"ticks={filter_tick_range}")
            log_info(f"Event filtering enabled: {', '.join(filter_desc)}", quiet)

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
                    db_manager.initialize_schema(force_recreate=True)

            # Check if using new runner (to avoid duplicate policy snapshot persistence)
            import os as os_module
            use_new_runner = os_module.getenv("USE_NEW_RUNNER", "true").lower() == "true"

            # Capture initial policy snapshots (Phase 4: Policy Snapshot Tracking)
            # Skip if using new runner - PersistenceManager handles this
            if not use_new_runner:
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

        # ═══════════════════════════════════════════════════════════
        # FEATURE FLAG: New Runner (Phase 5.2 - Default Enabled)
        # ═══════════════════════════════════════════════════════════
        # Check if we should use the new SimulationRunner
        # Default: true (new runner enabled by default)
        # Override: USE_NEW_RUNNER=false to use legacy implementation
        import os as os_module
        use_new_runner = os_module.getenv("USE_NEW_RUNNER", "true").lower() == "true"

        if use_new_runner and verbose:
            # NEW IMPLEMENTATION: Use SimulationRunner with VerboseModeOutput
            from payment_simulator.cli.execution.runner import (
                SimulationRunner,
                SimulationConfig as RunnerConfig,
            )
            from payment_simulator.cli.execution.persistence import PersistenceManager

            # Create output strategy
            agent_ids = orch.get_agent_ids()
            output = _create_output_strategy(
                mode="verbose",
                orch=orch,
                agent_ids=agent_ids,
                ticks_per_day=ffi_dict["ticks_per_day"],
                quiet=quiet,
                event_filter=event_filter,
                show_debug=debug,
            )

            # Create persistence manager if needed
            persistence = None
            if persist and db_manager:
                persistence = PersistenceManager(db_manager, sim_id, full_replay)

            # Create runner config
            runner_config = RunnerConfig(
                total_ticks=total_ticks,
                ticks_per_day=ffi_dict["ticks_per_day"],
                num_days=ffi_dict["num_days"],
                persist=persist,
                full_replay=full_replay,
                event_filter=event_filter,
            )

            # Run simulation via new runner
            sim_start = time.time()
            runner = SimulationRunner(orch, runner_config, output, persistence)
            final_stats = runner.run()
            sim_duration = time.time() - sim_start

            # Persist final metadata
            if persist and db_manager:
                # FIX: Use correct metrics from Rust instead of buggy tick counters
                # The tick counters count ALL settlements (including split children)
                # but get_system_metrics() correctly counts only effectively settled parents
                corrected_metrics = orch.get_system_metrics()

                persistence.persist_final_metadata(
                    config_path=config,
                    config_dict=config_dict,
                    ffi_dict=ffi_dict,
                    agent_ids=agent_ids,
                    total_arrivals=corrected_metrics["total_arrivals"],
                    total_settlements=corrected_metrics["total_settlements"],
                    total_costs=final_stats["total_costs"],
                    duration=sim_duration,
                    orch=orch,
                )

            # Generate cost charts if requested (accumulated and per-tick)
            if cost_chart and persist and sim_id:
                from payment_simulator.cli.commands.db import generate_cost_charts
                try:
                    # Create chart output path: examples/charts/scenario-name
                    # Find project root by looking for .git or backend directory
                    project_root = Path.cwd()
                    while project_root != project_root.parent:
                        if (project_root / ".git").exists() or (project_root / "backend").exists():
                            break
                        project_root = project_root.parent

                    chart_base_path = project_root / "examples/charts" / config.stem

                    generate_cost_charts(
                        simulation_id=sim_id,
                        db_path=db_path,
                        output_base_path=str(chart_base_path),
                        quiet=quiet,
                    )
                except Exception as e:
                    log_error(f"Failed to generate cost charts: {e}")

            # Output final JSON summary (even in verbose mode)
            agents = []
            for agent_id in agent_ids:
                agents.append(
                    {
                        "id": agent_id,
                        "final_balance": orch.get_agent_balance(agent_id),
                        "queue1_size": orch.get_queue1_size(agent_id),
                    }
                )

            output_data = {
                "simulation": {
                    "config_file": str(config),
                    "seed": ffi_dict["rng_seed"],
                    "ticks_executed": total_ticks,
                    "duration_seconds": round(sim_duration, 3),
                    "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
                },
                "metrics": {
                    "total_arrivals": final_stats["total_arrivals"],
                    "total_settlements": final_stats["total_settlements"],
                    "total_lsm_releases": final_stats.get("total_lsm_releases", 0),
                    "settlement_rate": final_stats.get("settlement_rate", 0),
                },
                "agents": agents,
                "costs": {
                    "total_cost": final_stats.get("total_costs", 0),
                },
                "performance": {
                    "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
                },
            }

            # Add simulation_id to output if persisted
            if persist and sim_id:
                output_data["simulation"]["simulation_id"] = sim_id
                output_data["simulation"]["database"] = db_path

            # Use compact JSON format (single line) for machine parseability
            output_json(output_data, indent=None)
            return

        elif use_new_runner and event_stream:
            # NEW IMPLEMENTATION: Use SimulationRunner with EventStreamModeOutput
            from payment_simulator.cli.execution.runner import (
                SimulationRunner,
                SimulationConfig as RunnerConfig,
            )
            from payment_simulator.cli.execution.persistence import PersistenceManager

            # Create output strategy
            agent_ids = orch.get_agent_ids()
            output = _create_output_strategy(
                mode="event_stream",
                orch=orch,
                agent_ids=agent_ids,
                ticks_per_day=ffi_dict["ticks_per_day"],
                quiet=quiet,
                event_filter=event_filter,
            )

            # Create persistence manager if needed
            persistence = None
            if persist and db_manager:
                persistence = PersistenceManager(db_manager, sim_id, False)  # event_stream: no full_replay

            # Create runner config
            runner_config = RunnerConfig(
                total_ticks=total_ticks,
                ticks_per_day=ffi_dict["ticks_per_day"],
                num_days=ffi_dict["num_days"],
                persist=persist,
                full_replay=False,
                event_filter=event_filter,
            )

            # Run simulation via new runner
            sim_start = time.time()
            runner = SimulationRunner(orch, runner_config, output, persistence)
            final_stats = runner.run()
            sim_duration = time.time() - sim_start

            # Persist final metadata
            if persist and db_manager:
                # FIX: Use correct metrics from Rust instead of buggy tick counters
                # The tick counters count ALL settlements (including split children)
                # but get_system_metrics() correctly counts only effectively settled parents
                corrected_metrics = orch.get_system_metrics()

                persistence.persist_final_metadata(
                    config_path=config,
                    config_dict=config_dict,
                    ffi_dict=ffi_dict,
                    agent_ids=agent_ids,
                    total_arrivals=corrected_metrics["total_arrivals"],
                    total_settlements=corrected_metrics["total_settlements"],
                    total_costs=final_stats["total_costs"],
                    duration=sim_duration,
                    orch=orch,
                )

            # Generate cost charts if requested (accumulated and per-tick)
            if cost_chart and persist and sim_id:
                from payment_simulator.cli.commands.db import generate_cost_charts
                try:
                    # Create chart output path: examples/charts/scenario-name
                    # Find project root by looking for .git or backend directory
                    project_root = Path.cwd()
                    while project_root != project_root.parent:
                        if (project_root / ".git").exists() or (project_root / "backend").exists():
                            break
                        project_root = project_root.parent

                    chart_base_path = project_root / "examples/charts" / config.stem

                    generate_cost_charts(
                        simulation_id=sim_id,
                        db_path=db_path,
                        output_base_path=str(chart_base_path),
                        quiet=quiet,
                    )
                except Exception as e:
                    log_error(f"Failed to generate cost charts: {e}")

            # Return early - new runner handles everything (final JSON already output)
            return

        elif use_new_runner and stream:
            # NEW IMPLEMENTATION: Use SimulationRunner with StreamModeOutput
            from payment_simulator.cli.execution.runner import (
                SimulationRunner,
                SimulationConfig as RunnerConfig,
            )
            from payment_simulator.cli.execution.persistence import PersistenceManager

            # Create output strategy
            agent_ids = orch.get_agent_ids()
            output = _create_output_strategy(
                mode="stream",
                orch=orch,
                agent_ids=agent_ids,
                ticks_per_day=ffi_dict["ticks_per_day"],
                quiet=quiet,
                event_filter=None,
            )

            # Create persistence manager if needed
            persistence = None
            if persist and db_manager:
                persistence = PersistenceManager(db_manager, sim_id, False)  # stream mode: no full_replay

            # Create runner config
            runner_config = RunnerConfig(
                total_ticks=total_ticks,
                ticks_per_day=ffi_dict["ticks_per_day"],
                num_days=ffi_dict["num_days"],
                persist=persist,
                full_replay=False,
                event_filter=None,
            )

            # Run simulation via new runner
            sim_start = time.time()
            runner = SimulationRunner(orch, runner_config, output, persistence)
            final_stats = runner.run()
            sim_duration = time.time() - sim_start

            # Persist final metadata
            if persist and db_manager:
                # FIX: Use correct metrics from Rust instead of buggy tick counters
                # The tick counters count ALL settlements (including split children)
                # but get_system_metrics() correctly counts only effectively settled parents
                corrected_metrics = orch.get_system_metrics()

                persistence.persist_final_metadata(
                    config_path=config,
                    config_dict=config_dict,
                    ffi_dict=ffi_dict,
                    agent_ids=agent_ids,
                    total_arrivals=corrected_metrics["total_arrivals"],
                    total_settlements=corrected_metrics["total_settlements"],
                    total_costs=final_stats["total_costs"],
                    duration=sim_duration,
                    orch=orch,
                )

            # Generate cost charts if requested (accumulated and per-tick)
            if cost_chart and persist and sim_id:
                from payment_simulator.cli.commands.db import generate_cost_charts
                try:
                    # Create chart output path: examples/charts/scenario-name
                    # Find project root by looking for .git or backend directory
                    project_root = Path.cwd()
                    while project_root != project_root.parent:
                        if (project_root / ".git").exists() or (project_root / "backend").exists():
                            break
                        project_root = project_root.parent

                    chart_base_path = project_root / "examples/charts" / config.stem

                    generate_cost_charts(
                        simulation_id=sim_id,
                        db_path=db_path,
                        output_base_path=str(chart_base_path),
                        quiet=quiet,
                    )
                except Exception as e:
                    log_error(f"Failed to generate cost charts: {e}")

            # Return early - new runner handles everything
            return

        elif use_new_runner and not verbose and not stream and not event_stream:
            # NEW IMPLEMENTATION: Use SimulationRunner with NormalModeOutput (normal mode)
            from payment_simulator.cli.execution.runner import (
                SimulationRunner,
                SimulationConfig as RunnerConfig,
            )
            from payment_simulator.cli.execution.persistence import PersistenceManager

            # Create output strategy
            agent_ids = orch.get_agent_ids()
            output = _create_output_strategy(
                mode="normal",
                orch=orch,
                agent_ids=agent_ids,
                ticks_per_day=ffi_dict["ticks_per_day"],
                quiet=quiet,
                event_filter=None,
                total_ticks=total_ticks,
                show_debug=debug,
            )

            # Create persistence manager if needed
            persistence = None
            if persist and db_manager:
                persistence = PersistenceManager(db_manager, sim_id, False)  # normal mode: no full_replay

            # Create runner config
            runner_config = RunnerConfig(
                total_ticks=total_ticks,
                ticks_per_day=ffi_dict["ticks_per_day"],
                num_days=ffi_dict["num_days"],
                persist=persist,
                full_replay=False,
                event_filter=None,
            )

            # Run simulation via new runner
            sim_start = time.time()
            runner = SimulationRunner(orch, runner_config, output, persistence)
            final_stats = runner.run()
            sim_duration = time.time() - sim_start

            # Persist final metadata
            if persist and db_manager:
                # FIX: Use correct metrics from Rust instead of buggy tick counters
                # The tick counters count ALL settlements (including split children)
                # but get_system_metrics() correctly counts only effectively settled parents
                corrected_metrics = orch.get_system_metrics()

                persistence.persist_final_metadata(
                    config_path=config,
                    config_dict=config_dict,
                    ffi_dict=ffi_dict,
                    agent_ids=agent_ids,
                    total_arrivals=corrected_metrics["total_arrivals"],
                    total_settlements=corrected_metrics["total_settlements"],
                    total_costs=final_stats["total_costs"],
                    duration=sim_duration,
                    orch=orch,
                )

            # Generate cost charts if requested (accumulated and per-tick)
            if cost_chart and persist and sim_id:
                from payment_simulator.cli.commands.db import generate_cost_charts
                try:
                    # Create chart output path: examples/charts/scenario-name
                    # Find project root by looking for .git or backend directory
                    project_root = Path.cwd()
                    while project_root != project_root.parent:
                        if (project_root / ".git").exists() or (project_root / "backend").exists():
                            break
                        project_root = project_root.parent

                    chart_base_path = project_root / "examples/charts" / config.stem

                    generate_cost_charts(
                        simulation_id=sim_id,
                        db_path=db_path,
                        output_base_path=str(chart_base_path),
                        quiet=quiet,
                    )
                except Exception as e:
                    log_error(f"Failed to generate cost charts: {e}")

            # Build and output final JSON
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

            output_data = {
                "simulation": {
                    "config_file": str(config),
                    "seed": ffi_dict["rng_seed"],
                    "ticks_executed": total_ticks,
                    "duration_seconds": round(sim_duration, 3),
                    "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
                },
                "metrics": {
                    "total_arrivals": final_stats["total_arrivals"],
                    "total_settlements": final_stats["total_settlements"],
                    "total_lsm_releases": final_stats.get("total_lsm_releases", 0),
                    "settlement_rate": final_stats.get("settlement_rate", 0),
                },
                "agents": agents,
                "costs": {
                    "total_cost": final_stats.get("total_costs", 0),
                },
                "performance": {
                    "ticks_per_second": round(final_stats.get("ticks_per_second", 0), 2),
                },
            }

            # Add simulation_id to output if persisted
            if persist and sim_id:
                output_data["simulation"]["simulation_id"] = sim_id
                output_data["simulation"]["database"] = db_path

            # Use compact JSON format (single line) for machine parseability
            output_json(output_data, indent=None)
            return

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
