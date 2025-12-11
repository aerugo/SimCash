"""Unified display functions for experiment output.

These functions are the SINGLE SOURCE OF TRUTH for all output.
Both run and replay use these same functions with different providers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.table import Table

# Import unified VerboseConfig from verbose_logging (single source of truth)
from castro.verbose_logging import VerboseConfig

if TYPE_CHECKING:
    from castro.events import ExperimentEvent
    from castro.state_provider import ExperimentStateProvider

# Re-export for backward compatibility
__all__ = ["VerboseConfig", "display_experiment_output"]


# =============================================================================
# Main Display Function
# =============================================================================


def display_experiment_output(
    provider: ExperimentStateProvider,
    console: Console | None = None,
    verbose_config: VerboseConfig | None = None,
) -> None:
    """Display experiment output from any provider.

    This is the SINGLE SOURCE OF TRUTH for experiment output.
    Both `castro run` and `castro replay` use this function.

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

    Args:
        event: Event to display
        console: Console for output
        config: VerboseConfig controlling what to show
    """
    event_type = event.event_type

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
        event: experiment_start event
        console: Console for output
    """
    details = event.details
    console.print(f"\n[bold]Starting {details.get('experiment_name', 'experiment')}[/bold]")
    if "description" in details:
        console.print(f"  Description: {details['description']}")
    if "max_iterations" in details:
        console.print(f"  Max iterations: {details['max_iterations']}")
    if "num_samples" in details:
        console.print(f"  Bootstrap samples: {details['num_samples']}")
    if "model" in details:
        console.print(f"  LLM model: {details['model']}")
    console.print()


def display_iteration_start(event: ExperimentEvent, console: Console) -> None:
    """Display iteration start event.

    Args:
        event: iteration_start event
        console: Console for output
    """
    details = event.details
    iteration = event.iteration
    total_cost = details.get("total_cost", 0)

    console.print(f"\n[bold]Iteration {iteration}[/bold]")
    console.print(f"  Total cost: {_format_cost(total_cost)}")


def display_bootstrap_evaluation(event: ExperimentEvent, console: Console) -> None:
    """Display bootstrap evaluation event.

    Args:
        event: bootstrap_evaluation event
        console: Console for output
    """
    details = event.details
    seed_results = details.get("seed_results", [])
    mean_cost = details.get("mean_cost", 0)
    std_cost = details.get("std_cost", 0)

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
        event: llm_call event
        console: Console for output
    """
    details = event.details
    agent_id = details.get("agent_id", "unknown")
    model = details.get("model", "unknown")
    prompt_tokens = details.get("prompt_tokens", 0)
    completion_tokens = details.get("completion_tokens", 0)
    latency = details.get("latency_seconds", 0.0)

    console.print(f"\n[bold]LLM Call for {agent_id}:[/bold]")
    console.print(f"  Model: {model}")
    console.print(f"  Prompt tokens: {prompt_tokens}")
    console.print(f"  Completion tokens: {completion_tokens}")
    console.print(f"  Latency: {latency:.1f}s")

    # Show context summary if available
    context = details.get("context_summary", {})
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
        event: policy_change event
        console: Console for output
    """
    details = event.details
    agent_id = details.get("agent_id", "unknown")
    old_cost = details.get("old_cost", 0)
    new_cost = details.get("new_cost", 0)
    accepted = details.get("accepted", False)
    old_policy = details.get("old_policy", {})
    new_policy = details.get("new_policy", {})

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
        event: policy_rejected event
        console: Console for output
    """
    details = event.details
    agent_id = details.get("agent_id", "unknown")
    reason = details.get("rejection_reason", "unknown")
    errors = details.get("validation_errors", [])

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
# Helper Functions
# =============================================================================


def _format_cost(cost_cents: int) -> str:
    """Format cost in cents as dollar string.

    Args:
        cost_cents: Cost in cents

    Returns:
        Formatted string like "$123.45"
    """
    dollars = cost_cents / 100
    return f"${dollars:,.2f}"
