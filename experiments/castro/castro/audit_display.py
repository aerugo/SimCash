"""Audit display functions for Castro experiment replay.

Provides detailed audit trail output for replay --audit mode, including:
- Raw LLM prompts and responses
- Validation errors and retry attempts
- Per-agent iteration details

Example:
    >>> from castro.audit_display import display_audit_output
    >>> from castro.state_provider import DatabaseExperimentProvider
    >>> provider = DatabaseExperimentProvider(conn, "exp1-20251209-143022")
    >>> display_audit_output(provider, console, start_iteration=2, end_iteration=3)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from payment_simulator.ai_cash_mgmt.events import EVENT_LLM_INTERACTION

from castro.event_compat import CastroEvent

if TYPE_CHECKING:
    from typing import Any

    from castro.state_provider import ExperimentStateProvider

# Backward compatibility alias
ExperimentEvent = CastroEvent


def _get_event_data(event: Any) -> dict[str, Any]:
    """Get event data from either CastroEvent or EventRecord.

    CastroEvent has .details, EventRecord has .event_data.
    This helper supports both.
    """
    if hasattr(event, "details"):
        return event.details
    if hasattr(event, "event_data"):
        return event.event_data
    return {}


def display_audit_output(
    provider: ExperimentStateProvider,
    console: Console,
    start_iteration: int | None = None,
    end_iteration: int | None = None,
) -> None:
    """Display detailed audit output for an experiment run.

    Shows per-agent audit information for each iteration in the specified range,
    including raw LLM prompts, responses, validation results, and evaluation data.

    Args:
        provider: State provider (DatabaseExperimentProvider for replay).
        console: Rich Console for output.
        start_iteration: First iteration to display (inclusive). None = from start.
        end_iteration: Last iteration to display (inclusive). None = to end.
    """
    # Get run metadata
    metadata = provider.get_run_metadata()
    if metadata is None:
        console.print("[red]Run metadata not found[/red]")
        return

    run_id = metadata.get("run_id", "unknown")
    experiment_name = metadata.get("experiment_name", "unknown")

    # Print header
    console.print()
    console.print(
        Panel.fit(
            f"[bold]AUDIT TRAIL[/bold]\n"
            f"Run: {run_id}\n"
            f"Experiment: {experiment_name}",
            border_style="cyan",
        )
    )
    console.print()

    # Get all events
    all_events = list(provider.get_all_events())

    # Filter to LLM interaction events
    llm_events = [e for e in all_events if e.event_type == EVENT_LLM_INTERACTION]

    if not llm_events:
        console.print("[yellow]No LLM interaction events found for this run.[/yellow]")
        console.print("Note: Audit data is only available for runs that captured LLM interactions.")
        return

    # Get unique iterations and apply filters
    iterations = sorted({e.iteration for e in llm_events})

    if start_iteration is not None:
        iterations = [i for i in iterations if i >= start_iteration]
    if end_iteration is not None:
        iterations = [i for i in iterations if i <= end_iteration]

    if not iterations:
        console.print("[yellow]No iterations found in the specified range.[/yellow]")
        return

    # Display each iteration
    for iteration in iterations:
        console.print(format_iteration_header(iteration))
        console.print()

        # Get events for this iteration
        iter_events = [e for e in llm_events if e.iteration == iteration]

        # Group by agent
        agents = sorted({_get_event_data(e).get("agent_id", "unknown") for e in iter_events})

        for agent_id in agents:
            agent_events = [
                e for e in iter_events if _get_event_data(e).get("agent_id") == agent_id
            ]

            for event in agent_events:
                display_agent_audit(event, console)
                console.print()

        console.print()


def display_agent_audit(event: ExperimentEvent, console: Console) -> None:
    """Display audit information for a single agent's LLM interaction.

    Shows agent header and delegates to specialized display functions.

    Args:
        event: LLM interaction event to display.
        console: Rich Console for output.
    """
    agent_id = _get_event_data(event).get("agent_id", "unknown")

    console.print(format_agent_section_header(agent_id))
    console.print()

    # Display the full LLM interaction
    display_llm_interaction_audit(event, console)

    # Display validation result
    display_validation_audit(event, console)


def display_llm_interaction_audit(event: ExperimentEvent, console: Console) -> None:
    """Display detailed LLM interaction audit information.

    Shows:
    - System prompt
    - User prompt
    - Raw response
    - Model info and token counts

    Args:
        event: LLM interaction event to display.
        console: Rich Console for output.
    """
    details = _get_event_data(event)

    # Model info header
    model = details.get("model", "unknown")
    prompt_tokens = details.get("prompt_tokens", 0)
    completion_tokens = details.get("completion_tokens", 0)
    latency = details.get("latency_seconds", 0.0)

    console.print(f"[dim]Model: {model}[/dim]")
    console.print(
        f"[dim]Tokens: {prompt_tokens:,} prompt + {completion_tokens:,} completion = "
        f"{prompt_tokens + completion_tokens:,} total[/dim]"
    )
    console.print(f"[dim]Latency: {latency:.2f}s[/dim]")
    console.print()

    # System Prompt
    system_prompt = details.get("system_prompt", "")
    if system_prompt:
        console.print("[bold cyan]System Prompt[/bold cyan]")
        console.print(Panel(system_prompt, border_style="dim"))
        console.print()

    # User Prompt
    user_prompt = details.get("user_prompt", "")
    if user_prompt:
        console.print("[bold cyan]User Prompt[/bold cyan]")
        console.print(Panel(user_prompt, border_style="dim"))
        console.print()

    # Raw Response
    raw_response = details.get("raw_response", "")
    if raw_response:
        console.print("[bold cyan]Raw Response[/bold cyan]")
        # Try to pretty-print if it's JSON
        try:
            import json
            parsed = json.loads(raw_response)
            formatted = json.dumps(parsed, indent=2)
            syntax = Syntax(formatted, "json", theme="monokai", line_numbers=False)
            console.print(Panel(syntax, border_style="dim"))
        except (json.JSONDecodeError, TypeError):
            # Not valid JSON, show as plain text
            console.print(Panel(raw_response, border_style="dim"))
        console.print()


def display_validation_audit(event: ExperimentEvent, console: Console) -> None:
    """Display validation result for an LLM interaction.

    Shows whether the policy was successfully parsed and any errors.

    Args:
        event: LLM interaction event to display.
        console: Rich Console for output.
    """
    details = _get_event_data(event)
    parsing_error = details.get("parsing_error")
    parsed_policy = details.get("parsed_policy")

    console.print("[bold cyan]Validation[/bold cyan]")

    if parsing_error:
        console.print(f"  [red]Error:[/red] {parsing_error}")
    elif parsed_policy is not None:
        console.print("  [green]Policy valid[/green]")
    else:
        console.print("  [yellow]Unknown validation status[/yellow]")


def format_iteration_header(iteration: int) -> str:
    """Format an iteration header string.

    Args:
        iteration: Iteration number.

    Returns:
        Formatted header string with Rich markup.
    """
    separator = "=" * 70
    header_text = f" AUDIT: Iteration {iteration}"
    return (
        f"[bold blue]{separator}[/bold blue]\n"
        f"[bold blue]{header_text}[/bold blue]\n"
        f"[bold blue]{separator}[/bold blue]"
    )


def format_agent_section_header(agent_id: str) -> str:
    """Format an agent section header string.

    Args:
        agent_id: Agent identifier (e.g., "BANK_A").

    Returns:
        Formatted header string with Rich markup.
    """
    separator = "-" * 60
    return f"[bold]{separator}[/bold]\n[bold] Agent: {agent_id}[/bold]\n[bold]{separator}[/bold]"
