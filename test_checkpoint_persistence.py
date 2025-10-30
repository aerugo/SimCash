#!/usr/bin/env python3
"""
Test checkpoint persistence across server restarts.

This script demonstrates that checkpoints can be restored after
the application restarts, proving true persistence.
"""

import json
import subprocess
import time
import sys
from pathlib import Path
import httpx
from rich.console import Console
from rich.table import Table
from rich import box

console = Console()


def start_api_server(port=8000):
    """Start the FastAPI server in the background."""
    console.print(f"\n[cyan]Starting API server on port {port}...[/cyan]")

    # Determine if we need to cd to api directory
    import os
    cwd = "api" if os.path.exists("api/payment_simulator") else "."

    # Set database path environment variable
    db_path = os.path.abspath("test_checkpoint.db")
    env = os.environ.copy()
    env["PAYMENT_SIM_DB_PATH"] = db_path

    # Start server in background
    process = subprocess.Popen(
        ["uv", "run", "uvicorn", "payment_simulator.api.main:app", "--port", str(port), "--log-level", "error"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    # Wait for server to be ready
    max_attempts = 30
    for i in range(max_attempts):
        try:
            response = httpx.get(f"http://localhost:{port}/health", timeout=1)
            if response.status_code == 200:
                console.print(f"[green]✓ Server started (PID: {process.pid})[/green]")
                return process
        except (httpx.RequestError, httpx.TimeoutException):
            time.sleep(0.5)

    console.print("[red]✗ Failed to start server[/red]")
    process.kill()
    sys.exit(1)


def stop_server(process):
    """Stop the API server."""
    console.print(f"\n[yellow]Stopping API server (PID: {process.pid})...[/yellow]")
    process.terminate()
    try:
        process.wait(timeout=5)
        console.print("[green]✓ Server stopped[/green]")
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        console.print("[yellow]✓ Server killed[/yellow]")


def create_simulation(config_file, port=8000):
    """Create a simulation via API."""
    console.print(f"\n[cyan]Creating simulation from {config_file}...[/cyan]")

    with open(config_file, 'r') as f:
        import yaml
        config = yaml.safe_load(f)

    response = httpx.post(
        f"http://localhost:{port}/simulations",
        json=config,
        timeout=10
    )

    if response.status_code != 200:
        console.print(f"[red]✗ Failed to create simulation: {response.text}[/red]")
        sys.exit(1)

    sim_id = response.json()["simulation_id"]
    console.print(f"[green]✓ Simulation created: {sim_id}[/green]")
    return sim_id


def run_ticks(sim_id, num_ticks, port=8000):
    """Run simulation for specified number of ticks."""
    console.print(f"\n[cyan]Running {num_ticks} ticks...[/cyan]")

    response = httpx.post(
        f"http://localhost:{port}/simulations/{sim_id}/tick",
        params={"count": num_ticks},
        timeout=30
    )

    if response.status_code != 200:
        console.print(f"[red]✗ Failed to run ticks: {response.text}[/red]")
        sys.exit(1)

    result = response.json()
    console.print(f"[green]✓ Executed {num_ticks} ticks (final tick: {result['final_tick']})[/green]")
    return result


def get_simulation_state(sim_id, port=8000):
    """Get current simulation state and stats."""
    console.print(f"\n[cyan]Fetching simulation state...[/cyan]")

    response = httpx.get(
        f"http://localhost:{port}/simulations/{sim_id}/state",
        timeout=10
    )

    if response.status_code != 200:
        console.print(f"[red]✗ Failed to get state: {response.text}[/red]")
        sys.exit(1)

    state = response.json()
    console.print(f"[green]✓ State retrieved[/green]")
    return state


def print_kpis(state, title="KPIs and Stats"):
    """Print KPIs and stats in a nice table."""
    console.print(f"\n[bold cyan]{title}[/bold cyan]")

    # Create metrics table
    metrics_table = Table(title="Simulation State", box=box.ROUNDED)
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="yellow", justify="right")

    metrics_table.add_row("Simulation ID", state["simulation_id"])
    metrics_table.add_row("Current Tick", str(state["current_tick"]))
    metrics_table.add_row("Current Day", str(state["current_day"]))
    metrics_table.add_row("Queue 2 Size", str(state["queue2_size"]))

    console.print(metrics_table)

    # Create agents table
    agents_table = Table(title="Agent Balances", box=box.ROUNDED)
    agents_table.add_column("Agent ID", style="cyan")
    agents_table.add_column("Balance", style="yellow", justify="right")
    agents_table.add_column("Queue Size", style="magenta", justify="right")

    for agent_id, agent_data in state["agents"].items():
        balance = agent_data["balance"] / 100  # Convert cents to dollars
        agents_table.add_row(
            agent_id,
            f"${balance:,.2f}",
            str(agent_data["queue1_size"])
        )

    console.print(agents_table)

    return state


def save_checkpoint(sim_id, description, port=8000):
    """Save a checkpoint."""
    console.print(f"\n[cyan]Saving checkpoint...[/cyan]")

    response = httpx.post(
        f"http://localhost:{port}/simulations/{sim_id}/checkpoint",
        json={
            "checkpoint_type": "manual",
            "description": description
        },
        timeout=10
    )

    if response.status_code != 200:
        console.print(f"[red]✗ Failed to save checkpoint: {response.text}[/red]")
        sys.exit(1)

    checkpoint_id = response.json()["checkpoint_id"]
    console.print(f"[green]✓ Checkpoint saved: {checkpoint_id}[/green]")
    return checkpoint_id


def load_checkpoint(checkpoint_id, port=8000):
    """Load a checkpoint."""
    console.print(f"\n[cyan]Loading checkpoint {checkpoint_id}...[/cyan]")

    response = httpx.post(
        f"http://localhost:{port}/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id},
        timeout=10
    )

    if response.status_code != 200:
        console.print(f"[red]✗ Failed to load checkpoint: {response.text}[/red]")
        sys.exit(1)

    sim_id = response.json()["simulation_id"]
    tick = response.json()["current_tick"]
    console.print(f"[green]✓ Checkpoint loaded: {sim_id} (tick {tick})[/green]")
    return sim_id


def compare_states(state1, state2):
    """Compare two simulation states."""
    console.print("\n[bold cyan]Comparing States...[/bold cyan]")

    differences = []

    # Compare basic metrics
    for key in ["current_tick", "current_day", "queue2_size"]:
        if state1[key] != state2[key]:
            differences.append(f"{key}: {state1[key]} != {state2[key]}")

    # Compare agent balances
    for agent_id in state1["agents"]:
        if agent_id not in state2["agents"]:
            differences.append(f"Agent {agent_id} missing in state2")
        else:
            if state1["agents"][agent_id]["balance"] != state2["agents"][agent_id]["balance"]:
                differences.append(f"{agent_id} balance: {state1['agents'][agent_id]['balance']} != {state2['agents'][agent_id]['balance']}")
            if state1["agents"][agent_id]["queue1_size"] != state2["agents"][agent_id]["queue1_size"]:
                differences.append(f"{agent_id} queue: {state1['agents'][agent_id]['queue1_size']} != {state2['agents'][agent_id]['queue1_size']}")

    if differences:
        console.print("[red]✗ States differ:[/red]")
        for diff in differences:
            console.print(f"  [red]{diff}[/red]")
        return False
    else:
        console.print("[green]✓ States are IDENTICAL![/green]")
        return True


def main():
    """Run the checkpoint persistence test."""
    console.print("\n[bold magenta]═══════════════════════════════════════════════════════════[/bold magenta]")
    console.print("[bold magenta]   Checkpoint Persistence Test: Survive Server Restarts   [/bold magenta]")
    console.print("[bold magenta]═══════════════════════════════════════════════════════════[/bold magenta]")

    port = 8000

    # Step 1: Start server and run first simulation
    console.print("\n[bold]STEP 1: Run first simulation (20 ticks)[/bold]")
    server1 = start_api_server(port)

    try:
        sim1_id = create_simulation("test_checkpoint_sim1.yaml", port)
        run_ticks(sim1_id, 20, port)
        state1 = get_simulation_state(sim1_id, port)
        print_kpis(state1, "First Simulation - Initial State (20 ticks)")

        # Save checkpoint
        checkpoint_id = save_checkpoint(sim1_id, "After 20 ticks - before server restart", port)

    finally:
        stop_server(server1)

    console.print("\n[bold yellow]⏸  Server 1 stopped. First simulation state saved to checkpoint.[/bold yellow]")
    time.sleep(2)

    # Step 2: Start server again and run different simulation
    console.print("\n[bold]STEP 2: Run different simulation (5 ticks)[/bold]")
    server2 = start_api_server(port)

    try:
        sim2_id = create_simulation("test_checkpoint_sim2.yaml", port)
        run_ticks(sim2_id, 5, port)
        state2 = get_simulation_state(sim2_id, port)
        print_kpis(state2, "Second Simulation - Different Scenario (5 ticks)")

    finally:
        stop_server(server2)

    console.print("\n[bold yellow]⏸  Server 2 stopped. Different simulation ran.[/bold yellow]")
    time.sleep(2)

    # Step 3: Start server again and load first simulation from checkpoint
    console.print("\n[bold]STEP 3: Restore first simulation from checkpoint[/bold]")
    server3 = start_api_server(port)

    try:
        sim1_restored_id = load_checkpoint(checkpoint_id, port)
        state1_restored = get_simulation_state(sim1_restored_id, port)
        print_kpis(state1_restored, "First Simulation - Restored from Checkpoint")

        # Compare states
        console.print("\n[bold magenta]═══════════════════════════════════════════════════════════[/bold magenta]")
        console.print("[bold magenta]               VALIDATION: Compare States                  [/bold magenta]")
        console.print("[bold magenta]═══════════════════════════════════════════════════════════[/bold magenta]")

        identical = compare_states(state1, state1_restored)

        if identical:
            console.print("\n[bold green]🎉 SUCCESS! Checkpoint persistence verified![/bold green]")
            console.print("[green]   The simulation was perfectly restored after:[/green]")
            console.print("[green]   • Server restart #1[/green]")
            console.print("[green]   • Running a different simulation[/green]")
            console.print("[green]   • Server restart #2[/green]")
            console.print("[green]   All KPIs and stats are IDENTICAL![/green]")
        else:
            console.print("\n[bold red]❌ FAILED! States differ after restoration.[/bold red]")
            sys.exit(1)

    finally:
        stop_server(server3)

    console.print("\n[bold cyan]Test completed successfully![/bold cyan]\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Test interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)
