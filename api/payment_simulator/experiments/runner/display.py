"""Unified display functions for experiment output.

These functions are the SINGLE SOURCE OF TRUTH for all output.
Both run and replay use these same functions with different providers.

All costs use integer cents (INV-1 compliance).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

from payment_simulator.experiments.runner.verbose import VerboseConfig

if TYPE_CHECKING:
    from payment_simulator.experiments.runner.state_provider import (
        ExperimentStateProviderProtocol,
    )

# Event type alias for display functions - events are dicts from core
ExperimentEvent = dict[str, Any]

__all__ = [
    "display_experiment_output",
    "display_experiment_start",
    "display_iteration_start",
    "display_bootstrap_evaluation",
    "display_llm_call",
    "display_policy_change",
    "display_policy_rejected",
    "display_experiment_end",
    "display_iteration_metrics",
    "display_llm_stats",
    "display_experiment_summary",
    "_format_cost",
]


# =============================================================================
# Main Display Function
# =============================================================================


def display_experiment_output(
    provider: ExperimentStateProviderProtocol,
    console: Console | None = None,
    verbose_config: VerboseConfig | None = None,
) -> None:
    """Display experiment output from any provider.

    This is the SINGLE SOURCE OF TRUTH for experiment output.
    Both `run` and `replay` commands use this function.

    Args:
        provider: ExperimentStateProvider (live or database)
        console: Rich Console for output (default: new Console)
        verbose_config: VerboseConfig controlling what to show
    """
    console = console or Console()
    verbose_config = verbose_config or VerboseConfig.all_enabled()

    # Display header with run metadata
    metadata = provider.get_run_metadata()
    if metadata:
        _display_header(metadata, console)

    # Display events
    for event in provider.get_all_events():
        _display_event(event, console, verbose_config)

    # Display final results
    result = provider.get_final_result()
    if result:
        _display_final_results(result, console)


def _display_header(metadata: dict[str, Any], console: Console) -> None:
    """Display experiment header.

    Args:
        metadata: Run metadata dict
        console: Console for output
    """
    console.print()
    console.print(f"[bold cyan]Run ID:[/bold cyan] {metadata.get('run_id', 'unknown')}")
    console.print(
        f"[bold cyan]Experiment:[/bold cyan] {metadata.get('experiment_name', 'unknown')}"
    )
    if "model" in metadata:
        console.print(f"[bold cyan]Model:[/bold cyan] {metadata.get('model')}")
    console.print()


def _display_event(
    event: ExperimentEvent,
    console: Console,
    config: VerboseConfig,
) -> None:
    """Display a single event.

    Routes to appropriate handler based on event type.
    Events are dicts with 'event_type' key from core StateProvider.

    Args:
        event: Event dict to display
        console: Console for output
        config: VerboseConfig controlling what to show
    """
    event_type = event.get("event_type", "")

    if event_type == "experiment_start":
        display_experiment_start(event, console)
    elif event_type == "iteration_start" and config.iterations:
        display_iteration_start(event, console)
    elif event_type == "bootstrap_evaluation" and config.bootstrap:
        display_bootstrap_evaluation(event, console)
    elif event_type == "llm_call" and config.llm:
        display_llm_call(event, console)
    elif event_type == "policy_change" and config.policy:
        display_policy_change(event, console)
    elif event_type == "policy_rejected" and config.rejections:
        display_policy_rejected(event, console)
    elif event_type == "experiment_end":
        display_experiment_end(event, console)
    # Metrics events (controlled by config.metrics)
    elif event_type == "iteration_metrics" and config.metrics:
        display_iteration_metrics(event, console)
    elif event_type == "llm_stats" and config.metrics:
        display_llm_stats(event, console)
    elif event_type == "experiment_summary" and config.metrics:
        display_experiment_summary(event, console)


def _display_final_results(result: dict[str, Any], console: Console) -> None:
    """Display final experiment results.

    Args:
        result: Final result dict
        console: Console for output
    """
    console.print()
    console.print("[bold green]Experiment Complete[/bold green]")

    if "final_cost" in result and result["final_cost"] is not None:
        cost_str = _format_cost(result["final_cost"])
        console.print(f"  Final Cost: {cost_str}")

    if "best_cost" in result and result["best_cost"] is not None:
        cost_str = _format_cost(result["best_cost"])
        console.print(f"  Best Cost: {cost_str}")

    if result.get("converged"):
        console.print(f"  Converged: Yes ({result.get('convergence_reason', 'unknown')})")
    else:
        console.print("  Converged: No")

    if "num_iterations" in result and result["num_iterations"] is not None:
        console.print(f"  Iterations: {result['num_iterations']}")

    console.print()


# =============================================================================
# Individual Event Display Functions
# =============================================================================


def display_experiment_start(event: ExperimentEvent, console: Console) -> None:
    """Display experiment start event.

    Args:
        event: experiment_start event dict
        console: Console for output
    """
    # Event data is directly in the event dict (no separate .details)
    console.print(f"\n[bold]Starting {event.get('experiment_name', 'experiment')}[/bold]")
    if "description" in event:
        console.print(f"  Description: {event['description']}")
    if "max_iterations" in event:
        console.print(f"  Max iterations: {event['max_iterations']}")
    if "num_samples" in event:
        console.print(f"  Bootstrap samples: {event['num_samples']}")
    if "model" in event:
        console.print(f"  LLM model: {event['model']}")
    console.print()


def display_iteration_start(event: ExperimentEvent, console: Console) -> None:
    """Display iteration start event.

    Args:
        event: iteration_start event dict
        console: Console for output
    """
    iteration = event.get("iteration", 0)
    total_cost = event.get("total_cost", 0)

    console.print(f"\n[bold]Iteration {iteration}[/bold]")
    console.print(f"  Total cost: {_format_cost(total_cost)}")


def display_bootstrap_evaluation(event: ExperimentEvent, console: Console) -> None:
    """Display bootstrap evaluation event.

    Args:
        event: bootstrap_evaluation event dict
        console: Console for output
    """
    seed_results = event.get("seed_results", [])
    mean_cost = event.get("mean_cost", 0)
    std_cost = event.get("std_cost", 0)

    console.print(f"\n[bold]Bootstrap Evaluation ({len(seed_results)} samples):[/bold]")

    # Create results table
    table = Table(show_header=True, header_style="bold")
    table.add_column("Seed", style="dim")
    table.add_column("Cost", justify="right")
    table.add_column("Settled", justify="right")
    table.add_column("Rate", justify="right")
    table.add_column("Note")

    best_cost = min((r.get("cost", float("inf")) for r in seed_results), default=0)

    for result in seed_results:
        seed = result.get("seed", 0)
        cost = result.get("cost", 0)
        settled = result.get("settled", 0)
        total = result.get("total", 0)
        rate = result.get("settlement_rate", 0.0)

        note = "Best" if cost == best_cost else ""

        table.add_row(
            f"0x{seed:08x}",
            _format_cost(cost),
            f"{settled}/{total}",
            f"{rate * 100:.1f}%",
            note,
        )

    console.print(table)
    console.print(f"  Mean: {_format_cost(mean_cost)} (std: {_format_cost(std_cost)})")


def display_llm_call(event: ExperimentEvent, console: Console) -> None:
    """Display LLM call event.

    Args:
        event: llm_call event dict
        console: Console for output
    """
    agent_id = event.get("agent_id", "unknown")
    model = event.get("model", "unknown")
    prompt_tokens = event.get("prompt_tokens", 0)
    completion_tokens = event.get("completion_tokens", 0)
    latency = event.get("latency_seconds", 0.0)

    console.print(f"\n[bold]LLM Call for {agent_id}:[/bold]")
    console.print(f"  Model: {model}")
    console.print(f"  Prompt tokens: {prompt_tokens}")
    console.print(f"  Completion tokens: {completion_tokens}")
    console.print(f"  Latency: {latency:.1f}s")

    # Show context summary if available
    context = event.get("context_summary", {})
    if context:
        console.print("  Key context provided:")
        for key, value in context.items():
            if isinstance(value, int) and key.endswith("_cost"):
                console.print(f"    - {key}: {_format_cost(value)}")
            else:
                console.print(f"    - {key}: {value}")


def display_policy_change(event: ExperimentEvent, console: Console) -> None:
    """Display policy change event.

    Args:
        event: policy_change event dict
        console: Console for output
    """
    agent_id = event.get("agent_id", "unknown")
    old_cost = event.get("old_cost", 0)
    new_cost = event.get("new_cost", 0)
    accepted = event.get("accepted", False)
    old_policy = event.get("old_policy", {})
    new_policy = event.get("new_policy", {})

    if accepted:
        console.print(f"\n[green]Policy improved:[/green] {_format_cost(old_cost)} → {_format_cost(new_cost)}")
    else:
        console.print(f"\n[yellow]Policy not improved:[/yellow] {_format_cost(old_cost)} → {_format_cost(new_cost)}")

    # Show parameter changes
    old_params = old_policy.get("parameters", {})
    new_params = new_policy.get("parameters", {})

    if old_params or new_params:
        table = Table(title=f"Policy Change: {agent_id}")
        table.add_column("Parameter")
        table.add_column("Old", justify="right")
        table.add_column("New", justify="right")
        table.add_column("Delta", justify="right")

        all_keys = set(old_params.keys()) | set(new_params.keys())
        for key in sorted(all_keys):
            old_val = old_params.get(key, "-")
            new_val = new_params.get(key, "-")

            if isinstance(old_val, (int, float)) and isinstance(new_val, (int, float)):
                if old_val != 0:
                    delta_pct = ((new_val - old_val) / old_val) * 100
                    delta_str = f"{delta_pct:+.0f}%"
                else:
                    delta_str = "-"
            else:
                delta_str = "-"

            table.add_row(key, str(old_val), str(new_val), delta_str)

        console.print(table)

    # Show decision
    decision = "ACCEPTED" if accepted else "REJECTED"
    improvement = ((old_cost - new_cost) / old_cost * 100) if old_cost > 0 else 0
    console.print(f"  Evaluation: {_format_cost(old_cost)} → {_format_cost(new_cost)} ({improvement:+.1f}%)")
    console.print(f"  Decision: {decision}")


def display_policy_rejected(event: ExperimentEvent, console: Console) -> None:
    """Display policy rejected event.

    Args:
        event: policy_rejected event dict
        console: Console for output
    """
    agent_id = event.get("agent_id", "unknown")
    reason = event.get("rejection_reason", "unknown")
    errors = event.get("validation_errors", [])

    console.print(f"\n[red]Policy rejected for {agent_id}[/red]")
    console.print(f"  Reason: {reason}")

    if errors:
        console.print("  Validation errors:")
        for error in errors:
            console.print(f"    - {error}")


def display_experiment_end(event: ExperimentEvent, console: Console) -> None:
    """Display experiment end event.

    Args:
        event: experiment_end event
        console: Console for output
    """
    # This is handled by _display_final_results from the provider
    # We just note that the experiment ended
    pass


# =============================================================================
# Metrics Display Functions (Replay-Safe)
# =============================================================================


def display_iteration_metrics(event: ExperimentEvent, console: Console) -> None:
    """Display iteration metrics event.

    Shows per-agent costs and liquidity fractions for an iteration.
    This is part of replay identity - output must be identical in run and replay.

    Note: Timing information is NOT included (excluded from replay identity).

    Args:
        event: iteration_metrics event dict with fields:
            - total_cost: Total cost in cents (integer, INV-1)
            - per_agent_costs: Dict mapping agent_id to cost in cents
            - per_agent_liquidity: Optional dict mapping agent_id to fraction
        console: Console for output
    """
    iteration = event.get("iteration", 0)
    total_cost = event.get("total_cost", 0)
    per_agent_costs = event.get("per_agent_costs", {})
    per_agent_liquidity = event.get("per_agent_liquidity", {})

    console.print(f"\n[bold]Iteration {iteration} Metrics[/bold]")

    # Create table for per-agent metrics
    table = Table(show_header=True, header_style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Cost", justify="right")
    if per_agent_liquidity:
        table.add_column("Liquidity", justify="right")

    for agent_id in sorted(per_agent_costs.keys()):
        cost = per_agent_costs[agent_id]
        cost_str = _format_cost(cost)

        if per_agent_liquidity and agent_id in per_agent_liquidity:
            liq = per_agent_liquidity[agent_id]
            liq_str = f"{liq * 100:.1f}%"
            table.add_row(agent_id, cost_str, liq_str)
        else:
            table.add_row(agent_id, cost_str)

    # Add total row
    total_str = _format_cost(total_cost)
    if per_agent_liquidity:
        table.add_row("[bold]Total[/bold]", f"[bold]{total_str}[/bold]", "")
    else:
        table.add_row("[bold]Total[/bold]", f"[bold]{total_str}[/bold]")

    console.print(table)


def display_llm_stats(event: ExperimentEvent, console: Console) -> None:
    """Display LLM statistics event.

    Shows LLM call counts and token usage for an iteration.
    This is part of replay identity - output must be identical in run and replay.

    Note: Latency/timing information is NOT included (excluded from replay identity).

    Args:
        event: llm_stats event dict with fields:
            - total_calls: Total LLM calls made
            - successful_calls: Number of successful calls
            - failed_calls: Number of failed calls
            - total_prompt_tokens: Total prompt tokens used
            - total_completion_tokens: Total completion tokens generated
        console: Console for output
    """
    iteration = event.get("iteration", 0)
    total_calls = event.get("total_calls", 0)
    successful_calls = event.get("successful_calls", 0)
    failed_calls = event.get("failed_calls", 0)
    prompt_tokens = event.get("total_prompt_tokens", 0)
    completion_tokens = event.get("total_completion_tokens", 0)

    console.print(f"\n[bold]LLM Stats (Iteration {iteration})[/bold]")
    console.print(f"  Calls: {successful_calls}/{total_calls} succeeded")

    if failed_calls > 0:
        console.print(f"  [red]Failed: {failed_calls}[/red]")

    console.print(f"  Prompt tokens: {prompt_tokens:,}")
    console.print(f"  Completion tokens: {completion_tokens:,}")
    console.print(f"  Total tokens: {prompt_tokens + completion_tokens:,}")


def display_experiment_summary(event: ExperimentEvent, console: Console) -> None:
    """Display experiment summary event.

    Shows final experiment statistics.
    This is part of replay identity - output must be identical in run and replay.

    Note: Duration/timing information is NOT included (excluded from replay identity).

    Args:
        event: experiment_summary event dict with fields:
            - num_iterations: Total iterations run
            - converged: Whether experiment converged
            - convergence_reason: Reason for termination
            - final_cost: Final cost in cents (integer, INV-1)
            - best_cost: Best cost achieved in cents (integer, INV-1)
            - total_llm_calls: Total LLM calls made
            - total_tokens: Total tokens used
        console: Console for output
    """
    num_iterations = event.get("num_iterations", 0)
    converged = event.get("converged", False)
    convergence_reason = event.get("convergence_reason", "unknown")
    final_cost = event.get("final_cost", 0)
    best_cost = event.get("best_cost", 0)
    total_llm_calls = event.get("total_llm_calls", 0)
    total_tokens = event.get("total_tokens", 0)

    console.print("\n[bold cyan]═══ Experiment Summary ═══[/bold cyan]")
    console.print(f"  Iterations: {num_iterations}")

    if converged:
        console.print(f"  [green]Converged: {convergence_reason}[/green]")
    else:
        console.print(f"  [yellow]Not converged: {convergence_reason}[/yellow]")

    console.print(f"  Final cost: {_format_cost(final_cost)}")
    console.print(f"  Best cost: {_format_cost(best_cost)}")

    if final_cost > 0 and best_cost < final_cost:
        improvement = (1 - best_cost / final_cost) * 100
        console.print(f"  Improvement: {improvement:.1f}%")

    console.print(f"  LLM calls: {total_llm_calls}")
    console.print(f"  Total tokens: {total_tokens:,}")


# =============================================================================
# Helper Functions
# =============================================================================


def _format_cost(cost_cents: int) -> str:
    """Format cost in cents as dollar string.

    Args:
        cost_cents: Cost in cents (INV-1 compliance)

    Returns:
        Formatted string like "$123.45"
    """
    dollars = cost_cents / 100
    return f"${dollars:,.2f}"
