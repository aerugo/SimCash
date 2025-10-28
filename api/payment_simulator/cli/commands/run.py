"""Run command - Execute simulations from config files."""

import time
import yaml
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer

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

        # Run simulation
        if verbose:
            # Verbose mode: show detailed events in real-time
            log_info(f"Running {total_ticks} ticks (verbose mode)...", True)  # Always suppress this in verbose

            # Get agent IDs for state tracking
            agent_ids = orch.get_agent_ids()

            # Track previous balances for change detection
            prev_balances = {agent_id: orch.get_agent_balance(agent_id) for agent_id in agent_ids}

            tick_results = []
            sim_start = time.time()

            for tick_num in range(total_ticks):
                # Log tick start
                log_tick_start(tick_num)

                # Execute tick
                result = orch.tick()
                tick_results.append(result)

                # Log arrivals
                if result["num_arrivals"] > 0:
                    log_arrivals(result["num_arrivals"])

                # Log settlements
                if result["num_settlements"] > 0:
                    log_settlements(result["num_settlements"])

                # Log LSM activity
                if result["num_lsm_releases"] > 0:
                    log_lsm_activity(bilateral=result["num_lsm_releases"], cycles=0)

                # Log costs
                if result["total_cost"] > 0:
                    log_costs(result["total_cost"])

                # Log agent states with balance changes
                for agent_id in agent_ids:
                    current_balance = orch.get_agent_balance(agent_id)
                    queue_size = orch.get_queue1_size(agent_id)
                    balance_change = current_balance - prev_balances[agent_id]

                    # Only show agents with activity
                    if balance_change != 0 or queue_size > 0:
                        log_agent_state(agent_id, current_balance, queue_size, balance_change)

                    prev_balances[agent_id] = current_balance

                # Calculate total queued
                total_queued = sum(orch.get_queue1_size(aid) for aid in agent_ids)

                # Log summary
                log_tick_summary(
                    result["num_arrivals"],
                    result["num_settlements"],
                    result["num_lsm_releases"],
                    total_queued
                )

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

            if not quiet:
                with create_progress() as progress:
                    task = progress.add_task(
                        f"[cyan]Running simulation...",
                        total=total_ticks
                    )

                    for _ in range(total_ticks):
                        result = orch.tick()
                        tick_results.append(result)
                        progress.update(task, advance=1)
            else:
                for _ in range(total_ticks):
                    result = orch.tick()
                    tick_results.append(result)

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

            # Output results
            if output_format.lower() == "json":
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
