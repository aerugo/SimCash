"""Output formatting utilities for CLI.

Follows the golden rule:
- stdout = machine-readable data (JSON, JSONL)
- stderr = human-readable logs (progress, errors, info)
"""

import sys
import json
from typing import Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# stderr console for human logs (never goes to stdout)
console = Console(stderr=True)


def output_json(data: Any, indent: Optional[int] = 2):
    """Output JSON to stdout (machine-readable).

    Args:
        data: Data to serialize as JSON
        indent: Indentation level (None for compact)
    """
    print(json.dumps(data, indent=indent), flush=True)


def output_jsonl(data: Any):
    """Output JSONL to stdout (streaming, one JSON object per line).

    Args:
        data: Data to serialize as JSON (one line)
    """
    print(json.dumps(data), flush=True)


def log_info(message: str, quiet: bool = False):
    """Log info message to stderr.

    Args:
        message: Message to log
        quiet: If True, suppress output
    """
    if not quiet:
        console.print(f"[blue]ℹ[/blue] {message}")


def log_success(message: str, quiet: bool = False):
    """Log success message to stderr.

    Args:
        message: Message to log
        quiet: If True, suppress output
    """
    if not quiet:
        console.print(f"[green]✓[/green] {message}")


def log_error(message: str):
    """Log error message to stderr (always shown).

    Args:
        message: Error message to log
    """
    console.print(f"[red]✗[/red] {message}", style="bold red")


def log_warning(message: str, quiet: bool = False):
    """Log warning message to stderr.

    Args:
        message: Warning message to log
        quiet: If True, suppress output
    """
    if not quiet:
        console.print(f"[yellow]⚠[/yellow] {message}", style="yellow")


def create_progress(description: str = "Processing...") -> Progress:
    """Create a progress bar for stderr.

    Args:
        description: Progress description

    Returns:
        Progress instance configured for stderr
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,  # Output to stderr
    )


# ============================================================================
# Verbose Mode Logging
# ============================================================================

def log_tick_start(tick: int):
    """Log start of tick (verbose mode).

    Args:
        tick: Tick number
    """
    console.print(f"\n[bold cyan]═══ Tick {tick} ═══[/bold cyan]")


def log_arrivals(count: int, details: str = ""):
    """Log transaction arrivals (verbose mode).

    Args:
        count: Number of arrivals
        details: Additional details
    """
    if count > 0:
        emoji = "📥"
        console.print(f"{emoji} [cyan]{count} transaction(s) arrived[/cyan] {details}")


def log_settlements(count: int, details: str = ""):
    """Log settlements (verbose mode).

    Args:
        count: Number of settlements
        details: Additional details
    """
    if count > 0:
        emoji = "✅"
        console.print(f"{emoji} [green]{count} transaction(s) settled[/green] {details}")


def log_lsm_activity(bilateral: int = 0, cycles: int = 0):
    """Log LSM activity (verbose mode).

    Args:
        bilateral: Number of bilateral offsets
        cycles: Number of cycle settlements
    """
    total = bilateral + cycles
    if total > 0:
        emoji = "🔄"
        parts = []
        if bilateral > 0:
            parts.append(f"{bilateral} bilateral")
        if cycles > 0:
            parts.append(f"{cycles} cycles")
        console.print(f"{emoji} [magenta]LSM freed {total} transaction(s)[/magenta] ({', '.join(parts)})")


def log_agent_state(agent_id: str, balance: int, queue_size: int, balance_change: int = 0):
    """Log agent state (verbose mode).

    Args:
        agent_id: Agent identifier
        balance: Current balance in cents
        queue_size: Queue size
        balance_change: Change in balance (if tracked)
    """
    balance_str = f"${balance / 100:,.2f}"

    # Color code balance
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    queue_str = ""
    if queue_size > 0:
        queue_str = f" | Queue: [yellow]{queue_size}[/yellow]"

    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    console.print(f"  {agent_id}: {balance_str}{change_str}{queue_str}")


def log_costs(cost: int):
    """Log costs accrued (verbose mode).

    Args:
        cost: Cost in cents
    """
    if cost > 0:
        console.print(f"💰 [yellow]Costs accrued: ${cost / 100:,.2f}[/yellow]")


def log_tick_summary(arrivals: int, settlements: int, lsm: int, queued: int):
    """Log tick summary line (verbose mode).

    Args:
        arrivals: Arrivals this tick
        settlements: Settlements this tick
        lsm: LSM releases this tick
        queued: Total queued transactions
    """
    parts = [
        f"[cyan]{arrivals} in[/cyan]",
        f"[green]{settlements} settled[/green]",
    ]
    if lsm > 0:
        parts.append(f"[magenta]{lsm} LSM[/magenta]")
    if queued > 0:
        parts.append(f"[yellow]{queued} queued[/yellow]")

    console.print(f"  Summary: {' | '.join(parts)}")
