"""Output formatting utilities for CLI.

Follows the golden rule:
- stdout = machine-readable data (JSON, JSONL)
- stderr = human-readable logs (progress, errors, info, verbose output)

This separation allows:
- Piping JSON to other tools while preserving colored logs in terminal
- Capturing verbose logs to file while keeping colors: cmd 2> output.log
- Redirecting both streams independently as needed
"""

import sys
import json
from typing import Any, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

# stderr console for human logs (preserves colors when redirected)
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


def log_section_separator():
    """Log a visual separator between major sections within a tick.

    Uses a lighter style than tick headers to create visual hierarchy
    without being too noisy.
    """
    console.print("\n[dim]" + "─" * 70 + "[/dim]\n")


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


def log_agent_state(provider, agent_id: str, balance_change: int = 0, quiet: bool = False):
    """Log agent state with detailed queue contents (UNIFIED for live & replay).

    Replaces both old log_agent_state() and log_agent_state_from_db().
    Works with any StateProvider implementation (Orchestrator or Database).

    Shows:
    - Agent balance with color coding (overdraft = red, negative change = yellow)
    - Queue 1 (internal) contents with transaction details
    - Queue 2 (RTGS) contents for this agent's transactions
    - Total queued value
    - Credit utilization percentage
    - Collateral posted (if any)

    Args:
        provider: StateProvider instance (OrchestratorStateProvider or DatabaseStateProvider)
        agent_id: Agent identifier
        balance_change: Balance change since last tick (cents)
        quiet: Suppress output if True
    """
    if quiet:
        return

    # Get agent state from provider
    balance = provider.get_agent_balance(agent_id)
    credit_limit = provider.get_agent_credit_limit(agent_id)
    collateral = provider.get_agent_collateral_posted(agent_id)
    queue1_contents = provider.get_agent_queue1_contents(agent_id)
    rtgs_queue = provider.get_rtgs_queue_contents()

    # Format balance with color coding
    balance_str = f"${balance / 100:,.2f}"
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    # Balance change indicator
    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    # Credit utilization (Issue #4 fix)
    credit_str = ""
    if credit_limit and credit_limit > 0:
        # Credit is only "used" when balance is negative (overdraft)
        used = max(0, -balance)
        utilization_pct = (used / credit_limit) * 100

        if utilization_pct > 80:
            util_str = f"[red]{utilization_pct:.0f}% used[/red]"
        elif utilization_pct > 50:
            util_str = f"[yellow]{utilization_pct:.0f}% used[/yellow]"
        else:
            util_str = f"[green]{utilization_pct:.0f}% used[/green]"

        credit_str = f" | Credit: {util_str}"

    console.print(f"  {agent_id}: {balance_str}{change_str}{credit_str}")

    # Queue 1 (internal)
    if queue1_contents:
        total_value = 0
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 1 ({len(queue1_contents)} transactions, ${total_value / 100:,.2f} total):")
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                priority_str = f"P:{tx['priority']}"
                console.print(
                    f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                    f"${tx['remaining_amount'] / 100:,.2f} | {priority_str} | "
                    f"⏰ Tick {tx['deadline_tick']}"
                )
        console.print()

    # Queue 2 (RTGS) - filter for this agent's transactions
    agent_rtgs_txs = []
    for tx_id in rtgs_queue:
        tx = provider.get_transaction_details(tx_id)
        if tx and tx.get("sender_id") == agent_id:
            agent_rtgs_txs.append(tx_id)

    if agent_rtgs_txs:
        total_value = 0
        for tx_id in agent_rtgs_txs:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 2 - RTGS ({len(agent_rtgs_txs)} transactions, ${total_value / 100:,.2f}):")
        for tx_id in agent_rtgs_txs:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                console.print(
                    f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                    f"${tx['remaining_amount'] / 100:,.2f} | P:{tx['priority']} | "
                    f"⏰ Tick {tx['deadline_tick']}"
                )
        console.print()

    # Collateral
    if collateral and collateral > 0:
        console.print(f"     Collateral Posted: ${collateral / 100:,.2f}")
        console.print()


def log_agent_financial_stats_table(provider, agent_ids: list[str], quiet: bool = False):
    """Display comprehensive financial stats for all agents.

    Shows a unified view of all financial metrics for each agent:
    - Balance (settlement account)
    - Credit Limit (maximum overdraft allowed)
    - Credit Used (current overdraft amount)
    - Available Liquidity (balance + credit + collateral)
    - Headroom (percentage of available liquidity remaining)
    - Posted Collateral
    - Queue 1 Size and Value
    - Total Costs

    Args:
        provider: StateProvider instance (OrchestratorStateProvider or DatabaseStateProvider)
        agent_ids: List of agent IDs to display
        quiet: Suppress output if True
    """
    if quiet:
        return

    console.print()
    console.print("[bold cyan]💰 Agent Financial Stats[/bold cyan]")
    console.print()

    for agent_id in agent_ids:
        balance = provider.get_agent_balance(agent_id)
        credit_limit = provider.get_agent_credit_limit(agent_id) or 0
        collateral = provider.get_agent_collateral_posted(agent_id) or 0
        queue1_contents = provider.get_agent_queue1_contents(agent_id)
        costs = provider.get_agent_accumulated_costs(agent_id)

        # Calculate derived metrics
        credit_used = max(0, -balance) if balance < 0 else 0
        available_liquidity = balance + credit_limit + collateral

        # Calculate headroom percentage
        max_liquidity = credit_limit + collateral
        if max_liquidity > 0:
            headroom_pct = (available_liquidity / max_liquidity) * 100
        else:
            headroom_pct = 100.0 if balance >= 0 else 0.0

        # Calculate queue value
        queue1_value = 0
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                queue1_value += tx.get("remaining_amount", 0)

        # Total costs
        total_cost = costs.get("total_cost", 0)

        # Format balance with color coding
        balance_str = f"${balance / 100:,.2f}"
        if balance < 0:
            balance_str = f"[red]{balance_str} (overdraft)[/red]"
        elif balance < 100000:  # Less than $1000
            balance_str = f"[yellow]{balance_str}[/yellow]"
        else:
            balance_str = f"[green]{balance_str}[/green]"

        # Format headroom with color coding
        if headroom_pct < 20:
            headroom_str = f"[red]{headroom_pct:.1f}%[/red]"
        elif headroom_pct < 50:
            headroom_str = f"[yellow]{headroom_pct:.1f}%[/yellow]"
        else:
            headroom_str = f"[green]{headroom_pct:.1f}%[/green]"

        # Display agent stats
        console.print(f"[bold]{agent_id}[/bold]")
        console.print(f"  Balance:            {balance_str}")
        console.print(f"  Credit Limit:       ${credit_limit / 100:,.2f}" if credit_limit > 0 else "  Credit Limit:       None")
        if credit_used > 0:
            console.print(f"  Credit Used:        [yellow]${credit_used / 100:,.2f}[/yellow]")
        console.print(f"  Available Liquidity: ${available_liquidity / 100:,.2f}")
        console.print(f"  Headroom:           {headroom_str}")
        if collateral > 0:
            console.print(f"  Posted Collateral:  [magenta]${collateral / 100:,.2f}[/magenta]")
        if len(queue1_contents) > 0:
            console.print(f"  Queue 1:            {len(queue1_contents)} txs, ${queue1_value / 100:,.2f} total")
        if total_cost > 0:
            console.print(f"  Total Costs:        [red]${total_cost / 100:,.2f}[/red]")
            # Show cost breakdown
            if costs.get("liquidity_cost", 0) > 0:
                console.print(f"    • Liquidity:      ${costs['liquidity_cost'] / 100:,.2f}")
            if costs.get("collateral_cost", 0) > 0:
                console.print(f"    • Collateral:     ${costs['collateral_cost'] / 100:,.2f}")
            if costs.get("delay_cost", 0) > 0:
                console.print(f"    • Delay:          ${costs['delay_cost'] / 100:,.2f}")
            if costs.get("split_friction_cost", 0) > 0:
                console.print(f"    • Split Friction: ${costs['split_friction_cost'] / 100:,.2f}")
            if costs.get("deadline_penalty", 0) > 0:
                console.print(f"    • Deadline Miss:  ${costs['deadline_penalty'] / 100:,.2f}")
        console.print()


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

    console.print()
    console.print(f"  Summary: {' | '.join(parts)}")


# ============================================================================
# Event Stream Mode - Chronological One-Line Event Display
# ============================================================================

def log_event_chronological(event: dict, tick: int, quiet: bool = False):
    """Log a single event in compact one-line chronological format.

    Designed for --event-stream mode where events are shown in strict chronological
    order without categorization.

    Args:
        event: Event dict from get_tick_events()
        tick: Tick number
        quiet: Suppress output if True

    Example Output:
        [Tick 42] Arrival: TX a1b2c3d4 | BANK_A → BANK_B | $1,000.00
        [Tick 42] PolicySubmit: BANK_A | TX a1b2c3d4
        [Tick 42] Settlement: TX a1b2c3d4 | BANK_A → BANK_B | $1,000.00
    """
    if quiet:
        return

    event_type = event.get("event_type", "Unknown")
    tx_id_short = event.get("tx_id", "")[:8] if event.get("tx_id") else ""

    # Format based on event type
    if event_type == "Arrival":
        sender = event.get("sender_id", "?")
        receiver = event.get("receiver_id", "?")
        amount = event.get("amount", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] Arrival: TX {tx_id_short} | "
            f"{sender} → {receiver} | ${amount / 100:,.2f}"
        )

    elif event_type == "PolicySubmit":
        agent = event.get("agent_id", "?")
        console.print(
            f"[cyan][Tick {tick}][/cyan] [green]PolicySubmit[/green]: {agent} | TX {tx_id_short}"
        )

    elif event_type == "PolicyHold":
        agent = event.get("agent_id", "?")
        reason = event.get("reason", "")
        console.print(
            f"[cyan][Tick {tick}][/cyan] [yellow]PolicyHold[/yellow]: {agent} | TX {tx_id_short} - {reason}"
        )

    elif event_type == "PolicyDrop":
        agent = event.get("agent_id", "?")
        reason = event.get("reason", "")
        console.print(
            f"[cyan][Tick {tick}][/cyan] [red]PolicyDrop[/red]: {agent} | TX {tx_id_short} - {reason}"
        )

    elif event_type == "PolicySplit":
        agent = event.get("agent_id", "?")
        num_splits = event.get("num_splits", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [magenta]PolicySplit[/magenta]: {agent} | TX {tx_id_short} → {num_splits} children"
        )

    elif event_type == "Settlement":
        sender = event.get("sender_id", "?")
        receiver = event.get("receiver_id", "?")
        amount = event.get("amount", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [green]Settlement[/green]: TX {tx_id_short} | "
            f"{sender} → {receiver} | ${amount / 100:,.2f}"
        )

    elif event_type == "QueuedRtgs":
        sender = event.get("sender_id", "?")
        console.print(
            f"[cyan][Tick {tick}][/cyan] [yellow]QueuedRtgs[/yellow]: TX {tx_id_short} | {sender}"
        )

    elif event_type == "LsmBilateralOffset":
        tx_a = event.get("tx_id_a", "")[:8]
        tx_b = event.get("tx_id_b", "")[:8]
        amount = event.get("amount", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [magenta]LSM-Bilateral[/magenta]: TX {tx_a} ⟷ TX {tx_b} | ${amount / 100:,.2f}"
        )

    elif event_type == "LsmCycleSettlement":
        tx_ids = event.get("tx_ids", [])
        cycle_value = event.get("cycle_value", 0)
        tx_count = len(tx_ids)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [magenta]LSM-Cycle[/magenta]: {tx_count} txs | ${cycle_value / 100:,.2f}"
        )

    elif event_type == "CollateralPost":
        agent = event.get("agent_id", "?")
        amount = event.get("amount", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [yellow]CollateralPost[/yellow]: {agent} | ${amount / 100:,.2f}"
        )

    elif event_type == "CollateralWithdraw":
        agent = event.get("agent_id", "?")
        amount = event.get("amount", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [yellow]CollateralWithdraw[/yellow]: {agent} | ${amount / 100:,.2f}"
        )

    elif event_type == "CostAccrual":
        agent = event.get("agent_id", "?")
        costs = event.get("costs", {})
        total = costs.get("total", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [yellow]CostAccrual[/yellow]: {agent} | ${total / 100:,.2f}"
        )

    elif event_type == "EndOfDay":
        day = event.get("day", 0)
        unsettled = event.get("unsettled_count", 0)
        penalties = event.get("total_penalties", 0)
        console.print(
            f"[cyan][Tick {tick}][/cyan] [bold cyan]EndOfDay[/bold cyan]: Day {day} | "
            f"{unsettled} unsettled | ${penalties / 100:,.2f} penalties"
        )

    else:
        # Generic fallback for unknown event types
        console.print(f"[cyan][Tick {tick}][/cyan] {event_type}: {event}")


# ============================================================================
# Enhanced Verbose Mode - Detailed Transaction/Event Logging
# ============================================================================

def log_transaction_arrivals(provider, events, quiet=False):
    """Log detailed transaction arrivals (verbose mode).

    For each arrival event, shows:
    - Transaction ID (truncated to 8 chars)
    - Sender → Receiver
    - Amount (formatted as currency)
    - Priority level (with color coding)
    - Deadline tick

    Args:
        provider: StateProvider instance (for querying transaction details if needed)
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        📥 3 transaction(s) arrived:
           • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00 | P:8 HIGH | ⏰ Tick 50
           • TX e5f6g7h8: BANK_B → BANK_C | $250.50 | P:5 MED | ⏰ Tick 55
    """
    if quiet:
        return

    arrival_events = [e for e in events if e.get("event_type") == "Arrival"]
    if not arrival_events:
        return

    console.print()
    console.print(f"📥 [cyan]{len(arrival_events)} transaction(s) arrived:[/cyan]")

    for event in arrival_events:
        tx_id = event["tx_id"][:8]  # Truncate for readability
        sender = event["sender_id"]
        receiver = event["receiver_id"]
        amount = event["amount"]

        # Prefer priority/deadline from event (replay), but fall back to querying (live)
        priority = event.get("priority")
        deadline = event.get("deadline_tick")

        if priority is None or deadline is None:
            # Fall back to querying transaction details (live execution)
            tx_details = provider.get_transaction_details(event["tx_id"])
            if tx_details:
                priority = tx_details.get("priority", 0)
                deadline = tx_details.get("deadline_tick", 0)
            else:
                priority = 0
                deadline = 0

        # Color code priority
        if priority >= 7:
            priority_str = f"P:{priority} [red]HIGH[/red]"
        elif priority >= 4:
            priority_str = f"P:{priority} MED"
        else:
            priority_str = f"P:{priority} LOW"

        amount_str = f"${amount / 100:,.2f}"

        console.print(f"   • TX {tx_id}: {sender} → {receiver}")
        console.print(f"     {amount_str} | {priority_str} | ⏰ Tick {deadline}")


def log_settlement_details(provider, events, tick, quiet=False):
    """Log detailed settlements showing how each transaction settled.

    Categorizes settlements by mechanism:
    - RTGS Immediate: Settled immediately upon submission
    - LSM Bilateral: Paired with offsetting transaction
    - LSM Cycle: Part of multilateral netting cycle

    Args:
        provider: StateProvider instance (not currently used, for consistency)
        events: List of events from get_tick_events()
        tick: Current tick number
        quiet: Suppress output if True

    Example Output:
        ✅ 5 transaction(s) settled:

           RTGS Immediate (2):
           • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00
           • TX e5f6g7h8: BANK_C → BANK_D | $500.00

           LSM Bilateral Offset (2):
           • TX i9j0k1l2 ⟷ TX m3n4o5p6: BANK_A ⇄ BANK_B | $750.00
    """
    if quiet:
        return

    # Categorize settlements by mechanism (using new specific event types)
    rtgs_immediate = [e for e in events if e.get("event_type") == "RtgsImmediateSettlement"]
    queue_releases = [e for e in events if e.get("event_type") == "Queue2LiquidityRelease"]
    lsm_bilateral = [e for e in events if e.get("event_type") == "LsmBilateralOffset"]
    lsm_cycles = [e for e in events if e.get("event_type") == "LsmCycleSettlement"]

    # Legacy: Also include old generic Settlement events for backward compatibility
    legacy_settlements = [e for e in events if e.get("event_type") == "Settlement"]

    total_settlements = len(rtgs_immediate) + len(queue_releases) + len(legacy_settlements)
    if total_settlements == 0 and len(lsm_bilateral) == 0 and len(lsm_cycles) == 0:
        return

    # Display header with total settlements
    console.print()
    total = total_settlements + len(lsm_bilateral) + len(lsm_cycles)
    console.print(f"✅ [green]{total} transaction(s) settled:[/green]")
    console.print()

    # RTGS immediate settlements (new specific event type)
    if rtgs_immediate:
        console.print(f"   [green]RTGS Immediate ({len(rtgs_immediate)}):[/green]")
        for event in rtgs_immediate:
            tx_id = event.get("tx_id", "unknown")[:8]
            sender = event.get("sender", "unknown")
            receiver = event.get("receiver", "unknown")
            amount = event.get("amount", 0)
            balance_before = event.get("sender_balance_before")
            balance_after = event.get("sender_balance_after")

            # Show basic settlement info
            console.print(f"   • TX {tx_id}: {sender} → {receiver} | ${amount / 100:,.2f}")

            # Show balance audit trail if available
            if balance_before is not None and balance_after is not None:
                console.print(f"     [dim]Balance: ${balance_before/100:,.2f} → ${balance_after/100:,.2f}[/dim]")
        console.print()

    # Queue 2 liquidity releases (new specific event type)
    if queue_releases:
        console.print(f"   [yellow]Queue 2 Releases ({len(queue_releases)}):[/yellow]")
        for event in queue_releases:
            tx_id = event.get("tx_id", "unknown")[:8]
            sender = event.get("sender", "unknown")
            receiver = event.get("receiver", "unknown")
            amount = event.get("amount", 0)
            wait_ticks = event.get("queue_wait_ticks", 0)
            reason = event.get("release_reason", "unknown")

            console.print(f"   • TX {tx_id}: {sender} → {receiver} | ${amount / 100:,.2f}")
            console.print(f"     [dim]Queued for {wait_ticks} tick(s) | Released: {reason}[/dim]")
        console.print()

    # Legacy generic Settlement events (deprecated but shown for compatibility)
    if legacy_settlements:
        console.print(f"   [dim]Legacy Settlements ({len(legacy_settlements)}):[/dim]")
        for event in legacy_settlements:
            tx_id = event.get("tx_id", "unknown")[:8]
            sender = event.get("sender_id", "unknown")
            receiver = event.get("receiver_id", "unknown")
            amount = event.get("amount", 0)
            console.print(f"   • TX {tx_id}: {sender} → {receiver} | ${amount / 100:,.2f}")
        console.print()

    # LSM bilateral offsets
    if lsm_bilateral:
        console.print(f"   [magenta]LSM Bilateral Offset ({len(lsm_bilateral)}):[/magenta]")
        for event in lsm_bilateral:
            tx_a = event.get("tx_id_a", "unknown")[:8]
            tx_b = event.get("tx_id_b", "unknown")[:8]
            amount = event.get("amount", 0)
            console.print(
                f"   • TX {tx_a} ⟷ TX {tx_b}: ${amount / 100:,.2f}"
            )
        console.print()

    # LSM cycles
    if lsm_cycles:
        console.print(f"   [magenta]LSM Cycle ({len(lsm_cycles)}):[/magenta]")
        for event in lsm_cycles:
            agent_ids = event.get("agent_ids", [])
            tx_amounts = event.get("tx_amounts", [])
            net_positions = event.get("net_positions", {})

            if agent_ids:
                cycle_str = " → ".join(agent_ids) + f" → {agent_ids[0]}"
                console.print(f"   • Cycle: {cycle_str}")

                # Show each transaction with sender/receiver if we have the data
                tx_ids = event.get("tx_ids", [])
                for i, tx_id in enumerate(tx_ids):
                    amount = tx_amounts[i] if i < len(tx_amounts) else 0
                    if i < len(agent_ids):
                        sender = agent_ids[i]
                        receiver = agent_ids[(i + 1) % len(agent_ids)]
                        console.print(f"     - {sender}→{receiver}: TX {tx_id[:8]} (${amount / 100:,.2f})")
                    else:
                        console.print(f"     - TX {tx_id[:8]}: ${amount / 100:,.2f}")

                # Show liquidity metrics if available
                total_value = event.get("total_value", 0)
                max_net_outflow = event.get("max_net_outflow", 0)
                if total_value > 0 and max_net_outflow is not None:
                    liquidity_saved = total_value - max_net_outflow
                    if liquidity_saved > 0:
                        efficiency = (liquidity_saved / total_value) * 100
                        console.print(f"     [green]✨ Saved: ${liquidity_saved / 100:,.2f} ({efficiency:.1f}%)[/green]")
        console.print()


def log_agent_queues_detailed(orch, agent_id, balance, balance_change, quiet=False):
    """Log agent state with detailed queue contents (verbose mode).

    Shows:
    - Agent balance with color coding (overdraft = red, negative change = yellow)
    - Queue 1 (internal) contents with transaction details
    - Queue 2 (RTGS) contents for this agent's transactions
    - Total queued value
    - Credit utilization percentage
    - Collateral posted (if any)

    Args:
        orch: Orchestrator instance
        agent_id: Agent identifier
        balance: Current balance in cents
        balance_change: Balance change since last tick
        quiet: Suppress output if True

    Example Output:
        BANK_A: $5,000.00 (+$500.00) | Credit: 25% used
           Queue 1 (3 transactions, $2,500.00 total):
           • TX a1b2c3d4 → BANK_B: $1,000.00 | P:8 | ⏰ Tick 50
           • TX e5f6g7h8 → BANK_C: $750.00 | P:5 | ⏰ Tick 55

           Collateral Posted: $1,000,000.00
    """
    if quiet:
        return

    # Format balance with color coding
    balance_str = f"${balance / 100:,.2f}"
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    # Balance change indicator
    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    # Credit utilization (Issue #4 fix)
    credit_limit = orch.get_agent_credit_limit(agent_id)
    credit_str = ""
    if credit_limit and credit_limit > 0:
        # Credit is only "used" when balance is negative (overdraft)
        used = max(0, -balance)
        utilization_pct = (used / credit_limit) * 100

        if utilization_pct > 80:
            util_str = f"[red]{utilization_pct:.0f}% used[/red]"
        elif utilization_pct > 50:
            util_str = f"[yellow]{utilization_pct:.0f}% used[/yellow]"
        else:
            util_str = f"[green]{utilization_pct:.0f}% used[/green]"

        credit_str = f" | Credit: {util_str}"

    console.print(f"  {agent_id}: {balance_str}{change_str}{credit_str}")

    # Queue 1 (internal)
    queue1_contents = orch.get_agent_queue1_contents(agent_id)
    if queue1_contents:
        total_value = 0
        for tx_id in queue1_contents:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 1 ({len(queue1_contents)} transactions, ${total_value / 100:,.2f} total):")
        for tx_id in queue1_contents:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                priority_str = f"P:{tx['priority']}"
                console.print(f"     • TX {tx_id[:8]} → {tx['receiver_id']}: ${tx['remaining_amount'] / 100:,.2f} | {priority_str} | ⏰ Tick {tx['deadline_tick']}")
        console.print()

    # Queue 2 (RTGS) - filter for this agent's transactions
    rtgs_queue = orch.get_rtgs_queue_contents()
    agent_rtgs_txs = []
    for tx_id in rtgs_queue:
        tx = orch.get_transaction_details(tx_id)
        if tx and tx.get("sender_id") == agent_id:
            agent_rtgs_txs.append(tx_id)

    if agent_rtgs_txs:
        total_value = 0
        for tx_id in agent_rtgs_txs:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 2 - RTGS ({len(agent_rtgs_txs)} transactions, ${total_value / 100:,.2f}):")
        for tx_id in agent_rtgs_txs:
            tx = orch.get_transaction_details(tx_id)
            if tx:
                console.print(f"     • TX {tx_id[:8]} → {tx['receiver_id']}: ${tx['remaining_amount'] / 100:,.2f} | P:{tx['priority']} | ⏰ Tick {tx['deadline_tick']}")
        console.print()

    # Collateral
    collateral = orch.get_agent_collateral_posted(agent_id)
    if collateral and collateral > 0:
        console.print(f"     Collateral Posted: ${collateral / 100:,.2f}")
        console.print()


def log_policy_decisions(events, quiet=False):
    """Log policy decisions made this tick (verbose mode).

    Shows submit/hold/drop/split decisions with reasoning.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🎯 Policy Decisions (5):
           BANK_A:
           • SUBMIT: TX a1b2c3d4 → BANK_B ($1,000.00)
           • HOLD: TX e5f6g7h8 → BANK_C ($5,000.00) - Preserving buffer

           BANK_B:
           • DROP: TX m3n4o5p6 → BANK_D - Past deadline
    """
    if quiet:
        return

    policy_events = [
        e for e in events
        if e.get("event_type") in ["PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"]
    ]

    if not policy_events:
        return

    console.print()
    console.print(f"🎯 [blue]Policy Decisions ({len(policy_events)}):[/blue]")

    # Group by agent
    by_agent = {}
    for event in policy_events:
        agent_id = event.get("agent_id", "unknown")
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    for agent_id, agent_events in by_agent.items():
        console.print(f"   [bold]{agent_id}:[/bold]")
        for event in agent_events:
            event_type = event.get("event_type")
            tx_id = event.get("tx_id", "unknown")[:8]

            if event_type == "PolicySubmit":
                console.print(f"   • [green]SUBMIT[/green]: TX {tx_id}")
            elif event_type == "PolicyHold":
                reason = event.get("reason", "no reason")
                console.print(f"   • [yellow]HOLD[/yellow]: TX {tx_id} - {reason}")
            elif event_type == "PolicyDrop":
                reason = event.get("reason", "no reason")
                console.print(f"   • [red]DROP[/red]: TX {tx_id} - {reason}")
            elif event_type == "PolicySplit":
                num_splits = event.get("num_splits", 0)
                console.print(f"   • [magenta]SPLIT[/magenta]: TX {tx_id} → {num_splits} children")
        console.print()


def log_collateral_activity(events, quiet=False):
    """Log collateral post/withdraw events (verbose mode).

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        💰 Collateral Activity (2):
           BANK_A:
           • POSTED: $1,000,000.00 - Strategic decision | New Total: $5,000,000.00

           BANK_B:
           • WITHDRAWN: $500,000.00 - Reduce opportunity cost | New Total: $2,500,000.00
    """
    if quiet:
        return

    collateral_events = [
        e for e in events
        if e.get("event_type") in ["CollateralPost", "CollateralWithdraw", "CollateralTimerWithdrawn"]
    ]

    if not collateral_events:
        return

    console.print()
    console.print(f"💰 [yellow]Collateral Activity ({len(collateral_events)}):[/yellow]")

    # Group by agent
    by_agent = {}
    for event in collateral_events:
        agent_id = event.get("agent_id", "unknown")
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    for agent_id, agent_events in by_agent.items():
        console.print(f"   [bold]{agent_id}:[/bold]")
        for event in agent_events:
            event_type = event.get("event_type")
            amount = event.get("amount", 0)

            if event_type == "CollateralPost":
                reason = event.get("reason", "no reason")
                new_total = event.get("new_total", 0)
                console.print(f"   • [green]POSTED[/green]: ${amount / 100:,.2f} - {reason} | New Total: ${new_total / 100:,.2f}")
            elif event_type == "CollateralWithdraw":
                reason = event.get("reason", "no reason")
                new_total = event.get("new_total", 0)
                console.print(f"   • [yellow]WITHDRAWN[/yellow]: ${amount / 100:,.2f} - {reason} | New Total: ${new_total / 100:,.2f}")
            elif event_type == "CollateralTimerWithdrawn":
                original_reason = event.get("original_reason", "unknown")
                posted_at_tick = event.get("posted_at_tick", "?")
                console.print(f"   • [cyan]AUTO-WITHDRAWN (timer)[/cyan]: ${amount / 100:,.2f} - Originally posted at tick {posted_at_tick} ({original_reason})")
        console.print()


def log_scenario_events(events, quiet=False):
    """Log scenario event executions (verbose mode).

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🎬 Scenario Events (3):
           • DirectTransfer: BANK_A → BANK_B ($100,000.00)
           • CustomTransactionArrival: BANK_A → BANK_B ($50,000.00)
             Priority: 7, TX: tx_123
           • CollateralAdjustment: BANK_A +$200,000.00 collateral
    """
    if quiet:
        return

    scenario_events = [
        e for e in events
        if e.get("event_type") == "ScenarioEventExecuted"
    ]

    if not scenario_events:
        return

    console.print()
    console.print(f"🎬 [magenta]Scenario Events ({len(scenario_events)}):[/magenta]")

    for event in scenario_events:
        scenario_type = event.get("scenario_event_type", "Unknown")

        # Handle both formats: details dict (from replay) or details_json string (from FFI)
        details = event.get("details", {})
        if not details:
            import json
            details_json = event.get("details_json", "{}")
            if isinstance(details_json, str):
                details = json.loads(details_json)
            else:
                details = details_json

        if scenario_type == "DirectTransfer":
            from_agent = details.get("from_agent", "?")
            to_agent = details.get("to_agent", "?")
            amount = details.get("amount", 0)
            console.print(f"   • [cyan]DirectTransfer:[/cyan] {from_agent} → {to_agent} (${amount / 100:,.2f})")

        elif scenario_type == "custom_transaction_arrival":
            from_agent = details.get("from_agent", "?")
            to_agent = details.get("to_agent", "?")
            amount = details.get("amount", 0)
            priority = details.get("priority", 5)
            tx_id = details.get("tx_id", "?")
            console.print(f"   • [green]CustomTransactionArrival:[/green] {from_agent} → {to_agent} (${amount / 100:,.2f})")
            console.print(f"     Priority: {priority}, TX: {tx_id}")

        elif scenario_type == "CollateralAdjustment":
            agent_id = details.get("agent", "?")
            delta = details.get("delta", 0)
            sign = "+" if delta >= 0 else ""
            console.print(f"   • [yellow]CollateralAdjustment:[/yellow] {agent_id} {sign}${delta / 100:,.2f} collateral")

        elif scenario_type == "GlobalArrivalRateChange":
            multiplier = details.get("multiplier", 1.0)
            console.print(f"   • [blue]GlobalArrivalRateChange:[/blue] All arrival rates × {multiplier:.2f}")

        elif scenario_type == "AgentArrivalRateChange":
            agent_id = details.get("agent", "?")
            multiplier = details.get("multiplier", 1.0)
            console.print(f"   • [blue]AgentArrivalRateChange:[/blue] {agent_id} arrival rate × {multiplier:.2f}")

        elif scenario_type == "CounterpartyWeightChange":
            agent_id = details.get("agent", "?")
            counterparty = details.get("counterparty", "?")
            new_weight = details.get("new_weight", 0.0)
            console.print(f"   • [green]CounterpartyWeightChange:[/green] {agent_id} → {counterparty} weight = {new_weight:.2f}")

        elif scenario_type == "DeadlineWindowChange":
            agent_id = details.get("agent", "?")
            new_window = details.get("new_window", 0)
            console.print(f"   • [yellow]DeadlineWindowChange:[/yellow] {agent_id} deadline window = {new_window} ticks")

        else:
            # Generic fallback for unknown event types
            console.print(f"   • [dim]{scenario_type}:[/dim] {details}")

    console.print()


def log_cost_breakdown(provider, agent_ids, quiet=False):
    """Log detailed cost breakdown by agent and type (UNIFIED for live & replay).

    Replaces both old log_cost_breakdown() and log_cost_breakdown_from_db().
    Works with any StateProvider implementation (Orchestrator or Database).

    Shows costs accrued this tick broken down by:
    - Liquidity cost (overdraft/borrowing fees)
    - Delay cost (time-based for unsettled transactions)
    - Collateral cost (opportunity cost of posted collateral)
    - Penalty cost (end-of-day penalties)
    - Split friction cost (cost of splitting transactions)

    Args:
        provider: StateProvider instance (OrchestratorStateProvider or DatabaseStateProvider)
        agent_ids: List of agent identifiers
        quiet: Suppress output if True

    Example Output:
        💰 Costs Accrued This Tick: $125.50

           BANK_A: $75.25
           • Liquidity: $50.00
           • Delay: $25.00
           • Split: $0.25

           BANK_B: $50.25
           • Delay: $50.00
           • Split: $0.25
    """
    if quiet:
        return

    total_cost = 0
    agent_costs = []

    for agent_id in agent_ids:
        costs = provider.get_agent_accumulated_costs(agent_id)
        if costs:
            # Calculate total from all cost components
            # Note: Use "penalty_cost" (database format) instead of "deadline_penalty" (old FFI format)
            agent_total = (
                costs.get("liquidity_cost", 0) +
                costs.get("delay_cost", 0) +
                costs.get("collateral_cost", 0) +
                costs.get("penalty_cost", 0) +
                costs.get("split_friction_cost", 0)
            )

            if agent_total > 0:
                agent_costs.append((agent_id, costs, agent_total))
                total_cost += agent_total

    if total_cost == 0:
        return

    console.print()
    console.print(f"💰 [yellow]Costs Accrued This Tick: ${total_cost / 100:,.2f}[/yellow]")
    console.print()

    for agent_id, costs, agent_total in agent_costs:
        console.print(f"   {agent_id}: ${agent_total / 100:,.2f}")

        if costs.get("liquidity_cost", 0) > 0:
            console.print(f"   • Liquidity: ${costs['liquidity_cost'] / 100:,.2f}")
        if costs.get("delay_cost", 0) > 0:
            console.print(f"   • Delay: ${costs['delay_cost'] / 100:,.2f}")
        if costs.get("collateral_cost", 0) > 0:
            console.print(f"   • Collateral: ${costs['collateral_cost'] / 100:,.2f}")
        if costs.get("penalty_cost", 0) > 0:
            console.print(f"   • Penalty: ${costs['penalty_cost'] / 100:,.2f}")
        if costs.get("split_friction_cost", 0) > 0:
            console.print(f"   • Split: ${costs['split_friction_cost'] / 100:,.2f}")

        console.print()


def log_queued_rtgs(events, quiet=False):
    """Log transactions entering Queue 2 (RTGS central queue) (verbose mode).

    Shows when transactions are queued in the RTGS system due to insufficient
    liquidity for immediate settlement.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        📋 2 transaction(s) queued in RTGS:
           • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00 | Insufficient balance
           • TX e5f6g7h8: BANK_C → BANK_D | $500.00 | Insufficient balance
    """
    if quiet:
        return

    queued_events = [e for e in events if e.get("event_type") == "QueuedRtgs"]
    if not queued_events:
        return

    console.print()
    console.print(f"📋 [yellow]{len(queued_events)} transaction(s) queued in RTGS:[/yellow]")

    for event in queued_events:
        tx_id = event.get("tx_id", "unknown")[:8]
        sender_id = event.get("sender_id", "unknown")
        # Note: QueuedRtgs event doesn't include receiver/amount in current Rust implementation
        # We'd need to query the transaction details for full info
        console.print(f"   • TX {tx_id}: {sender_id} | Insufficient balance")

    console.print()


def log_cost_accrual_events(events, quiet=False):
    """Log individual cost accrual events (verbose mode).

    Shows when costs are accrued by agents in real-time, providing visibility
    into the cost accumulation process beyond just the aggregated breakdown.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        💰 Cost Accruals (3):
           BANK_A: $12.50
           • Liquidity: $8.00 | Delay: $4.50

           BANK_B: $25.00
           • Delay: $25.00
    """
    if quiet:
        return

    cost_events = [e for e in events if e.get("event_type") == "CostAccrual"]
    if not cost_events:
        return

    console.print()
    console.print(f"💰 [yellow]Cost Accruals ({len(cost_events)}):[/yellow]")

    for event in cost_events:
        agent_id = event.get("agent_id", "unknown")
        costs = event.get("costs", {})

        # Calculate total from components
        total = costs.get("total", 0)

        console.print(f"   {agent_id}: ${total / 100:,.2f}")

        # Show non-zero cost components
        components = []
        if costs.get("liquidity_cost", 0) > 0:
            components.append(f"Liquidity: ${costs['liquidity_cost'] / 100:,.2f}")
        if costs.get("delay_cost", 0) > 0:
            components.append(f"Delay: ${costs['delay_cost'] / 100:,.2f}")
        if costs.get("collateral_cost", 0) > 0:
            components.append(f"Collateral: ${costs['collateral_cost'] / 100:,.2f}")
        if costs.get("penalty_cost", 0) > 0:
            components.append(f"Penalty: ${costs['penalty_cost'] / 100:,.2f}")
        if costs.get("split_friction_cost", 0) > 0:
            components.append(f"Split: ${costs['split_friction_cost'] / 100:,.2f}")

        if components:
            console.print(f"   • {' | '.join(components)}")
        console.print()


def log_end_of_day_event(events, quiet=False):
    """Log structured EndOfDay event (verbose mode).

    Shows the EndOfDay event as a structured notification before the detailed
    end-of-day summary statistics.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🌙 End of Day 0 - 95 settled, 5 unsettled, $125.50 in penalties
    """
    if quiet:
        return

    eod_events = [e for e in events if e.get("event_type") == "EndOfDay"]
    if not eod_events:
        return

    for event in eod_events:
        day = event.get("day", 0)
        unsettled_count = event.get("unsettled_count", 0)
        total_penalties = event.get("total_penalties", 0)

        console.print()
        console.print(
            f"🌙 [cyan]End of Day {day}[/cyan] - "
            f"{unsettled_count} unsettled, "
            f"${total_penalties / 100:,.2f} in penalties"
        )
        console.print()


def log_lsm_cycle_visualization(events, quiet=False):
    """Visualize LSM cycles showing circular payment chains (verbose mode).

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🔄 LSM Cycles (2):

           Cycle 1 (Bilateral):
           BANK_A ⇄ BANK_B
           • A→B: TX a1b2c3d4 ($1,000.00)
           • B→A: TX e5f6g7h8 ($750.00)
           Net Settlement: $250.00

           Cycle 2 (Multilateral - 3 agents):
           BANK_A → BANK_B → BANK_C → BANK_A
           • TX i9j0k1l2 ($500.00)
           • TX m3n4o5p6 ($450.00)
           • TX q7r8s9t0 ($300.00)
    """
    if quiet:
        return

    lsm_bilateral = [e for e in events if e.get("event_type") == "LsmBilateralOffset"]
    lsm_cycles = [e for e in events if e.get("event_type") == "LsmCycleSettlement"]

    total_cycles = len(lsm_bilateral) + len(lsm_cycles)
    if total_cycles == 0:
        return

    console.print()
    console.print(f"🔄 [magenta]LSM Cycles ({total_cycles}):[/magenta]")
    console.print()

    cycle_num = 1

    # Bilateral offsets
    for event in lsm_bilateral:
        console.print(f"   Cycle {cycle_num} (Bilateral):")

        # Get all information from event (no orchestrator lookup needed)
        tx_id_a = event.get("tx_id_a", "")
        tx_id_b = event.get("tx_id_b", "")
        agent_a = event.get("agent_a", "unknown")
        agent_b = event.get("agent_b", "unknown")
        amount_a = event.get("amount_a", 0)
        amount_b = event.get("amount_b", 0)

        console.print(f"   {agent_a} ⇄ {agent_b}")
        console.print(f"   • {agent_a}→{agent_b}: TX {tx_id_a[:8]} (${amount_a / 100:,.2f})")
        console.print(f"   • {agent_b}→{agent_a}: TX {tx_id_b[:8]} (${amount_b / 100:,.2f})")

        # Calculate offset vs liquidity breakdown
        total_value = amount_a + amount_b
        net = abs(amount_a - amount_b)

        if net > 0:
            # Determine direction
            if amount_a > amount_b:
                console.print(f"   💫 Net Settlement: {agent_a} → {agent_b}: ${net / 100:,.2f}")
            else:
                console.print(f"   💫 Net Settlement: {agent_b} → {agent_a}: ${net / 100:,.2f}")

        # Show liquidity saved
        if total_value > 0:
            offset_amount = total_value - net  # Amount netted out (smaller of the two)
            liquidity_saved = offset_amount
            efficiency = (liquidity_saved / total_value) * 100
            console.print(f"   [green]✨ Saved: ${liquidity_saved / 100:,.2f} ({efficiency:.1f}%)[/green]")

        console.print()
        cycle_num += 1

    # Multilateral cycles
    for event in lsm_cycles:
        tx_ids = event.get("tx_ids", [])
        agent_ids = event.get("agent_ids", [])
        tx_amounts = event.get("tx_amounts", [])
        net_positions = event.get("net_positions", {})
        total_value = event.get("total_value", 0)
        max_net_outflow = event.get("max_net_outflow", 0)

        num_agents = len(agent_ids) if agent_ids else len(tx_ids)

        console.print(f"   Cycle {cycle_num} (Multilateral - {num_agents} agents):")

        # Display cycle information from event data
        if agent_ids and tx_amounts:
            # Show cycle: A → B → C → A
            cycle_str = " → ".join(agent_ids)
            console.print(f"   {cycle_str}")

            # Show each transaction in cycle with sender/receiver
            for i, tx_id in enumerate(tx_ids):
                if i < len(agent_ids) and i < len(tx_amounts):
                    sender = agent_ids[i]
                    receiver = agent_ids[(i + 1) % len(agent_ids)]
                    amount = tx_amounts[i]
                    console.print(f"   • {sender}→{receiver}: TX {tx_id[:8]} (${amount / 100:,.2f})")
        elif tx_ids:
            # Minimal display if agent_ids/amounts not available
            console.print(f"   {len(tx_ids)} transactions in cycle")
            for tx_id in tx_ids:
                console.print(f"   • TX {tx_id[:8]}")

        # Show liquidity metrics if available
        console.print()
        if total_value > 0:
            console.print(f"   [cyan]💰 Gross Value: ${total_value / 100:,.2f}[/cyan]")

            if max_net_outflow is not None and max_net_outflow > 0:
                console.print(f"   [yellow]💫 Max Liquidity Used: ${max_net_outflow / 100:,.2f}[/yellow]")

                liquidity_saved = total_value - max_net_outflow
                if liquidity_saved > 0:
                    efficiency = (liquidity_saved / total_value) * 100
                    console.print(
                        f"   [green]✨ Liquidity Saved: ${liquidity_saved / 100:,.2f} "
                        f"({efficiency:.1f}%)[/green]"
                    )

        # Show net positions if available
        if net_positions:
            console.print()
            console.print("   Net Positions:")
            # Show in cycle order if we have agent_ids
            if agent_ids:
                for agent_id in agent_ids[:-1]:  # Exclude duplicate last agent
                    if agent_id in net_positions:
                        net_pos = net_positions[agent_id]
                        if net_pos > 0:
                            console.print(f"   • {agent_id}: [green]+${net_pos / 100:,.2f}[/green] (inflow)")
                        elif net_pos < 0:
                            console.print(
                                f"   • {agent_id}: [red]-${abs(net_pos) / 100:,.2f}[/red] "
                                "(outflow - used liquidity)"
                            )
                        else:
                            console.print(f"   • {agent_id}: [dim]$0.00[/dim] (net zero)")
            else:
                # Fallback: show all net positions
                for agent_id, net_pos in sorted(net_positions.items()):
                    if net_pos > 0:
                        console.print(f"   • {agent_id}: [green]+${net_pos / 100:,.2f}[/green] (inflow)")
                    elif net_pos < 0:
                        console.print(
                            f"   • {agent_id}: [red]-${abs(net_pos) / 100:,.2f}[/red] "
                            "(outflow - used liquidity)"
                        )
                    else:
                        console.print(f"   • {agent_id}: [dim]$0.00[/dim] (net zero)")

        console.print()
        cycle_num += 1


def log_agent_state_from_db(mock_orch, agent_id: str, state_data: dict, queue_data: dict, quiet=False):
    """Log agent state from database (full replay mode).

    Shows:
    - Agent balance with color coding
    - Queue 1 (internal) contents from database
    - Queue 2 (RTGS) contents from database
    - Total queued value
    - Collateral posted

    Args:
        mock_orch: Mock orchestrator for transaction details
        agent_id: Agent identifier
        state_data: Agent state dict from database (balance, collateral, etc.)
        queue_data: Queue contents dict {queue_type: [tx_ids]}
        quiet: Suppress output if True

    Example:
        >>> log_agent_state_from_db(mock_orch, "BANK_A", state, queues)
    """
    if quiet:
        return

    balance = state_data.get("balance", 0)
    balance_change = state_data.get("balance_change", 0)
    collateral = state_data.get("posted_collateral", 0)

    # Format balance with color coding
    balance_str = f"${balance / 100:,.2f}"
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    # Balance change indicator
    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    console.print(f"  {agent_id}: {balance_str}{change_str}")

    # Queue 1 (internal)
    queue1_tx_ids = queue_data.get("queue1", [])
    if queue1_tx_ids:
        total_value = 0
        for tx_id in queue1_tx_ids:
            tx = mock_orch.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 1 ({len(queue1_tx_ids)} transactions, ${total_value / 100:,.2f} total):")
        for tx_id in queue1_tx_ids:
            tx = mock_orch.get_transaction_details(tx_id)
            if tx:
                priority_str = f"P:{tx['priority']}"
                console.print(f"     • TX {tx_id[:8]} → {tx['receiver_id']}: ${tx['remaining_amount'] / 100:,.2f} | {priority_str} | ⏰ Tick {tx['deadline_tick']}")
        console.print()

    # Queue 2 (RTGS)
    rtgs_tx_ids = queue_data.get("rtgs", [])
    if rtgs_tx_ids:
        total_value = 0
        for tx_id in rtgs_tx_ids:
            tx = mock_orch.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 2 - RTGS ({len(rtgs_tx_ids)} transactions, ${total_value / 100:,.2f}):")
        for tx_id in rtgs_tx_ids:
            tx = mock_orch.get_transaction_details(tx_id)
            if tx:
                console.print(f"     • TX {tx_id[:8]} → {tx['receiver_id']}: ${tx['remaining_amount'] / 100:,.2f} | P:{tx['priority']} | ⏰ Tick {tx['deadline_tick']}")
        console.print()

    # Collateral
    if collateral and collateral > 0:
        console.print(f"     Collateral Posted: ${collateral / 100:,.2f}")
        console.print()


def log_cost_breakdown_from_db(agent_states: list[dict], quiet=False):
    """Log detailed cost breakdown from database (full replay mode).

    Shows cumulative costs for each agent (matching original run behavior).

    Args:
        agent_states: List of agent state dicts from database
        quiet: Suppress output if True

    Example:
        >>> log_cost_breakdown_from_db(agent_states)
    """
    if quiet:
        return

    # Calculate total costs (cumulative, not deltas)
    total_cost = 0
    agent_costs = []

    for state in agent_states:
        agent_id = state.get("agent_id", "unknown")

        # Sum all cumulative costs (NOT deltas - to match original run behavior)
        tick_cost = (
            state.get("liquidity_cost", 0) +
            state.get("delay_cost", 0) +
            state.get("collateral_cost", 0) +
            state.get("penalty_cost", 0) +
            state.get("split_friction_cost", 0)
        )

        if tick_cost > 0:
            agent_costs.append((agent_id, state, tick_cost))
            total_cost += tick_cost

    if total_cost == 0:
        return

    console.print()
    console.print(f"💰 [yellow]Costs Accrued This Tick: ${total_cost / 100:,.2f}[/yellow]")
    console.print()

    for agent_id, state, agent_total in agent_costs:
        console.print(f"   {agent_id}: ${agent_total / 100:,.2f}")

        if state.get("liquidity_cost", 0) > 0:
            console.print(f"   • Liquidity: ${state['liquidity_cost'] / 100:,.2f}")
        if state.get("delay_cost", 0) > 0:
            console.print(f"   • Delay: ${state['delay_cost'] / 100:,.2f}")
        if state.get("collateral_cost", 0) > 0:
            console.print(f"   • Collateral: ${state['collateral_cost'] / 100:,.2f}")
        if state.get("penalty_cost", 0) > 0:
            console.print(f"   • Penalty: ${state['penalty_cost'] / 100:,.2f}")
        if state.get("split_friction_cost", 0) > 0:
            console.print(f"   • Split: ${state['split_friction_cost'] / 100:,.2f}")

        console.print()


def log_end_of_day_statistics(
    day,
    total_arrivals,
    total_settlements,
    total_lsm_releases,
    total_costs,
    agent_stats,
    quiet=False
):
    """Log comprehensive end-of-day statistics (verbose mode).

    Args:
        day: Day number (0-indexed)
        total_arrivals: Total arrivals for the day
        total_settlements: Total settlements for the day
        total_lsm_releases: Total LSM releases for the day
        total_costs: Total costs accrued for the day
        agent_stats: Per-agent statistics (list of dicts)
        quiet: Suppress output if True

    Example Output:
        ════════════════════════════════════════════════════════════════
                             END OF DAY 0 SUMMARY
        ════════════════════════════════════════════════════════════════

        📊 SYSTEM-WIDE METRICS:
        • Total Transactions: 10,000
        • Settled: 9,500 (95.0%)
        • Unsettled: 500 (5.0%)
        • LSM Releases: 1,200 (12.6% of settlements)
        • Settlement Rate: 95.0%

        💰 COSTS:
        • Total: $12,500.00

        👥 AGENT PERFORMANCE:

        BANK_A:
        • Final Balance: $5,000,000.00
        • Total Costs: $3,200.00
    """
    if quiet:
        return

    console.print()
    console.print("═" * 64)
    console.print(f"[bold cyan]{'END OF DAY ' + str(day) + ' SUMMARY':^64}[/bold cyan]")
    console.print("═" * 64)
    console.print()

    # System-wide metrics
    settlement_rate = (total_settlements / total_arrivals * 100) if total_arrivals > 0 else 0
    unsettled = total_arrivals - total_settlements
    lsm_pct = (total_lsm_releases / total_settlements * 100) if total_settlements > 0 else 0

    console.print("[bold]📊 SYSTEM-WIDE METRICS:[/bold]")
    console.print(f"• Total Transactions: {total_arrivals:,}")
    console.print(f"• Settled: {total_settlements:,} ({settlement_rate:.1f}%)")
    console.print(f"• Unsettled: {unsettled:,} ({(unsettled/total_arrivals*100) if total_arrivals > 0 else 0:.1f}%)")
    # FIX: LSM releases now uses corrected count (parent transactions only)
    console.print(f"• LSM Settled: {total_lsm_releases:,} ({lsm_pct:.1f}% of settlements)")
    console.print(f"• Settlement Rate: {settlement_rate:.1f}%")
    console.print()

    # Costs
    console.print("[bold]💰 COSTS:[/bold]")
    console.print(f"• Total: ${total_costs / 100:,.2f}")
    console.print()

    # Agent performance
    console.print("[bold]👥 AGENT PERFORMANCE:[/bold]")
    console.print()

    for agent in agent_stats:
        console.print(f"[bold]{agent['id']}:[/bold]")
        console.print(f"• Final Balance: ${agent['final_balance'] / 100:,.2f}")

        if 'credit_utilization' in agent:
            console.print(f"• Credit Utilization: {agent['credit_utilization']:.0f}%")

        if 'queue1_size' in agent:
            console.print(f"• Queue 1: {agent['queue1_size']} transactions")

        if 'queue2_size' in agent:
            console.print(f"• Queue 2: {agent['queue2_size']} transactions")

        if 'total_costs' in agent:
            console.print(f"• Total Costs: ${agent['total_costs'] / 100:,.2f}")

        console.print()

    console.print("═" * 64)
    console.print()

def log_transactions_near_deadline(
    provider,
    within_ticks: int,
    current_tick: int,
    quiet: bool = False
) -> None:
    """Display transactions approaching deadline (early warning).

    Args:
        provider: StateProvider instance
        within_ticks: Number of ticks ahead to check (e.g., 2)
        current_tick: Current tick number
        quiet: If True, suppress output
    """
    if quiet:
        return

    transactions = provider.get_transactions_near_deadline(within_ticks)
    if not transactions:
        return

    console.print()
    console.print("[yellow]⚠️  Transactions Near Deadline (within 2 ticks):[/yellow]")

    for tx in sorted(transactions, key=lambda t: t['deadline_tick']):
        ticks_until = tx['ticks_until_deadline']
        remaining = tx.get('remaining_amount', tx['amount'])

        warning = "🔴 NEXT TICK!" if ticks_until <= 1 else "⚠️"

        console.print(
            f"  {warning} TX {tx['tx_id'][:8]}... | "
            f"{tx['sender_id']} → {tx['receiver_id']} | "
            f"${remaining / 100:,.2f} | "
            f"Deadline: Tick {tx['deadline_tick']} ({ticks_until} tick{'s' if ticks_until != 1 else ''} away)"
        )


def log_overdue_transactions_summary(
    provider,
    quiet: bool = False
) -> None:
    """Display summary of all overdue transactions with costs.

    Args:
        provider: StateProvider instance
        quiet: If True, suppress output
    """
    if quiet:
        return

    overdue_txs = provider.get_overdue_transactions()
    if not overdue_txs:
        return

    console.print()
    console.print("[red]🔥 Overdue Transactions:[/red]")

    total_overdue_cost = 0

    for tx in sorted(overdue_txs, key=lambda t: t.get('ticks_overdue', 0), reverse=True):
        ticks_overdue = tx.get('ticks_overdue', 0)
        total_cost = tx.get('total_overdue_cost', 0)
        deadline_penalty = tx.get('deadline_penalty_cost', 0)
        delay_cost = tx.get('estimated_delay_cost', 0)
        remaining = tx.get('remaining_amount', tx['amount'])

        total_overdue_cost += total_cost

        console.print(
            f"  🔥 TX {tx['tx_id'][:8]}... | "
            f"{tx['sender_id']} → {tx['receiver_id']} | "
            f"${remaining / 100:,.2f} | "
            f"Overdue: {ticks_overdue} tick{'s' if ticks_overdue != 1 else ''}"
        )
        console.print(
            f"     💸 Costs: Penalty ${deadline_penalty / 100:,.2f} + "
            f"Delay ${delay_cost / 100:,.2f} = "
            f"[bold red]${total_cost / 100:,.2f}[/bold red]"
        )

    if total_overdue_cost > 0:
        console.print(f"\n  [bold red]Total Overdue Cost: ${total_overdue_cost / 100:,.2f}[/bold red]")


def log_transaction_went_overdue_event(event: dict, quiet: bool = False) -> None:
    """Log when a transaction becomes overdue.

    Args:
        event: TransactionWentOverdue event dict
        quiet: If True, suppress output
    """
    if quiet:
        return

    console.print(
        f"\n[red]❌ Transaction Went Overdue:[/red] TX {event['tx_id'][:8]}..."
    )
    console.print(
        f"   {event['sender_id']} → {event['receiver_id']} | "
        f"${event['remaining_amount'] / 100:,.2f}"
    )
    console.print(
        f"   Deadline: Tick {event['deadline_tick']} | "
        f"Current: Tick {event['tick']} | "
        f"[red]{event['ticks_overdue']} tick{'s' if event['ticks_overdue'] != 1 else ''} late[/red]"
    )
    console.print(
        f"   💸 Deadline Penalty Charged: [bold red]${event['deadline_penalty_cost'] / 100:,.2f}[/bold red]"
    )


def log_overdue_transaction_settled_event(event: dict, quiet: bool = False) -> None:
    """Log when an overdue transaction is finally settled.

    Args:
        event: OverdueTransactionSettled event dict
        quiet: If True, suppress output
    """
    if quiet:
        return

    console.print(
        f"\n[green]✅ Overdue Transaction Settled:[/green] TX {event['tx_id'][:8]}..."
    )
    console.print(
        f"   {event['sender_id']} → {event['receiver_id']} | "
        f"${event['settled_amount'] / 100:,.2f}"
    )
    console.print(
        f"   Was overdue for: [red]{event['total_ticks_overdue']} tick{'s' if event['total_ticks_overdue'] != 1 else ''}[/red] "
        f"(Deadline: {event['deadline_tick']}, Overdue since: {event['overdue_since_tick']})"
    )

    total_cost = event['deadline_penalty_cost'] + event['estimated_delay_cost']
    console.print(
        f"   💸 Total Cost: Penalty ${event['deadline_penalty_cost'] / 100:,.2f} + "
        f"Delay ${event['estimated_delay_cost'] / 100:,.2f} = "
        f"[bold red]${total_cost / 100:,.2f}[/bold red]"
    )


def log_state_register_events(events, quiet=False):
    """Log state register update events (Phase 4.5: Policy micro-memory).

    Displays when agents update their memory registers, showing how policy
    decisions are affected by state.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🧠 Agent Memory Updates (3):
           BANK_A:
           • bank_state_cooldown: 0.0 → 42.0 (policy_action)
           • bank_state_counter: 5.0 → 6.0 (increment)

           BANK_B:
           • bank_state_cooldown: 0.0 → 20.0 (policy_action)
    """
    if quiet:
        return

    state_events = [
        e for e in events
        if e.get("event_type") == "StateRegisterSet"
    ]

    if not state_events:
        return

    console.print()
    console.print(f"🧠 [cyan]Agent Memory Updates ({len(state_events)}):[/cyan]")

    # Group by agent
    by_agent = {}
    for event in state_events:
        agent_id = event.get("agent_id", "unknown")
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    for agent_id, agent_events in by_agent.items():
        console.print(f"   [bold]{agent_id}:[/bold]")
        for event in agent_events:
            register_key = event.get("register_key", "unknown")
            old_value = event.get("old_value", 0.0)
            new_value = event.get("new_value", 0.0)
            reason = event.get("reason", "no reason")

            # Format register key for display (remove bank_state_ prefix)
            display_key = register_key.replace("bank_state_", "")

            # Color based on reason
            if reason == "eod_reset":
                console.print(f"   • [dim]{display_key}: {old_value} → {new_value} ([yellow]EOD reset[/yellow])[/dim]")
            elif new_value > old_value:
                console.print(f"   • [green]{display_key}: {old_value} → {new_value}[/green] ({reason})")
            elif new_value < old_value:
                console.print(f"   • [yellow]{display_key}: {old_value} → {new_value}[/yellow] ({reason})")
            else:
                console.print(f"   • {display_key}: {old_value} → {new_value} ({reason})")
        console.print()


def log_budget_operations(events, quiet=False):
    """Log budget operations (Phase 3.3: Bank-Level Budgets).

    Displays when agents set their release budgets, showing adaptive
    budget management strategies.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        💰 Release Budget Updates (2):
           BANK_A:
           • Max Release: $50,000.00

           BANK_B:
           • Max Release: $75,000.00
           • Focus: COUNTERPARTY_X
           • Max per Counterparty: $25,000.00
    """
    if quiet:
        return

    budget_events = [
        e for e in events
        if e.get("event_type") == "BankBudgetSet"
    ]

    if not budget_events:
        return

    console.print()
    console.print(f"💰 [cyan]Release Budget Updates ({len(budget_events)}):[/cyan]")

    for event in budget_events:
        agent_id = event.get("agent_id", "unknown")
        max_value = event.get("max_value", 0)
        focus_counterparties = event.get("focus_counterparties")
        max_per_counterparty = event.get("max_per_counterparty")

        console.print(f"   [bold]{agent_id}:[/bold]")

        # Always show max release value
        console.print(f"   • [green]Max Release:[/green] ${max_value/100:,.2f}")

        # Show focus counterparties if specified
        if focus_counterparties:
            if isinstance(focus_counterparties, list):
                focus_str = ", ".join(focus_counterparties)
            else:
                focus_str = str(focus_counterparties)
            console.print(f"   • [yellow]Focus:[/yellow] {focus_str}")

        # Show max per counterparty if specified
        if max_per_counterparty is not None:
            console.print(f"   • [yellow]Max per Counterparty:[/yellow] ${max_per_counterparty/100:,.2f}")

        console.print()


def log_performance_diagnostics(timing: dict, tick: int) -> None:
    """Display performance breakdown for a single tick.

    Shows microsecond and millisecond timings for each phase of tick execution,
    along with percentage of total time spent in each phase.

    Args:
        timing: Dict containing microsecond timings for each phase
        tick: Current tick number
    """
    from rich.table import Table

    table = Table(title=f"⏱️  Performance Diagnostics - Tick {tick}", show_header=True, header_style="bold magenta")
    table.add_column("Phase", style="cyan", no_wrap=True, width=25)
    table.add_column("Time (μs)", justify="right", style="yellow", width=15)
    table.add_column("Time (ms)", justify="right", style="yellow", width=12)
    table.add_column("% of Total", justify="right", style="green", width=12)

    total = timing["total_micros"]

    phases = [
        ("Arrivals", timing["arrivals_micros"]),
        ("Policy Evaluation", timing["policy_eval_micros"]),
        ("RTGS Settlement", timing["rtgs_settlement_micros"]),
        ("RTGS Queue Processing", timing["rtgs_queue_micros"]),
        ("LSM Coordinator", timing["lsm_micros"]),
        ("Cost Accrual", timing["cost_accrual_micros"]),
    ]

    for name, micros in phases:
        pct = (micros / total * 100) if total > 0 else 0
        millis = micros / 1000.0
        table.add_row(name, f"{micros:,}", f"{millis:.2f}", f"{pct:.1f}%")

    # Add separator row
    table.add_row("", "", "", "", style="dim")

    # Add total row
    millis_total = total / 1000.0
    table.add_row("TOTAL", f"{total:,}", f"{millis_total:.2f}", "100.0%", style="bold")

    console.print(table)
    console.print()  # Blank line for spacing


def log_performance_diagnostics_compact(timing: dict, tick: int) -> None:
    """Display compact performance summary for a single tick.

    Shows total time and top phases in a single line format suitable for
    non-verbose mode with progress bar.

    Args:
        timing: Dict containing microsecond timings for each phase
        tick: Current tick number
    """
    total = timing["total_micros"]
    millis_total = total / 1000.0

    phases = [
        ("Arrivals", timing["arrivals_micros"]),
        ("Policy", timing["policy_eval_micros"]),
        ("RTGS", timing["rtgs_settlement_micros"]),
        ("Queue", timing["rtgs_queue_micros"]),
        ("LSM", timing["lsm_micros"]),
        ("Costs", timing["cost_accrual_micros"]),
    ]

    # Sort by time descending and take top 3
    sorted_phases = sorted(phases, key=lambda x: x[1], reverse=True)
    top_phases = sorted_phases[:3]

    # Format top phases with percentages
    phase_strs = []
    for name, micros in top_phases:
        pct = (micros / total * 100) if total > 0 else 0
        if pct >= 1.0:  # Only show phases that are at least 1%
            phase_strs.append(f"{name}:{pct:.0f}%")

    phase_info = ", ".join(phase_strs) if phase_strs else "balanced"

    console.print(f"[dim]⏱️  Tick {tick}: {millis_total:.2f}ms ({phase_info})[/dim]")
