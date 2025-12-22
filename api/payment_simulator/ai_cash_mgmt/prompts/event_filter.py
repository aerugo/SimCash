"""Event filtering for agent-isolated LLM prompts.

This module implements the CRITICAL INVARIANT for agent isolation:
An LLM optimizing for Agent X may ONLY see:
- Outgoing transactions FROM Agent X
- Incoming liquidity events TO Agent X balance
- Agent X's own policy and state changes

This prevents information leakage between agents during optimization.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def _get_str(event: dict[str, Any], key: str, default: str = "") -> str:
    """Safely get a string value from event dict."""
    val = event.get(key, default)
    if isinstance(val, str):
        return val
    return str(val) if val is not None else default


def _get_str_list(event: dict[str, Any], key: str) -> list[str]:
    """Safely get a list of strings from event dict."""
    val = event.get(key, [])
    if isinstance(val, list):
        return [str(x) for x in val]
    return []


def filter_events_for_agent(
    agent_id: str,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter simulation events to only those relevant to agent.

    Implements agent isolation: Agent X only sees their outgoing
    transactions and incoming liquidity events.

    Args:
        agent_id: ID of the target agent (e.g., "BANK_A").
        events: List of simulation events from Rust FFI.

    Returns:
        Filtered list of events visible to the target agent.
    """
    filtered: list[dict[str, Any]] = []

    for event in events:
        event_type = event.get("event_type", "")

        if _should_include_event(agent_id, event_type, event):
            filtered.append(event)

    return filtered


def _should_include_event(
    agent_id: str,
    event_type: str,
    event: dict[str, Any],
) -> bool:
    """Determine if an event should be included for the target agent.

    Args:
        agent_id: Target agent ID.
        event_type: Type of the event.
        event: Full event data.

    Returns:
        True if the event should be visible to the agent.
    """
    # =========================================================================
    # Outgoing transaction events (agent is sender)
    # =========================================================================

    if event_type == "Arrival":
        sender_id = _get_str(event, "sender_id")
        receiver_id = _get_str(event, "receiver_id")
        # Include if agent is sender (outgoing) OR receiver (incoming notification)
        return sender_id == agent_id or receiver_id == agent_id

    if event_type in ("PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"):
        return _get_str(event, "agent_id") == agent_id

    if event_type == "RtgsImmediateSettlement":
        sender = _get_str(event, "sender")
        receiver = _get_str(event, "receiver")
        # Include if agent is sender (outgoing) OR receiver (incoming liquidity)
        return sender == agent_id or receiver == agent_id

    if event_type in ("RtgsSubmission", "RtgsWithdrawal", "RtgsResubmission"):
        sender = _get_str(event, "sender")
        receiver = _get_str(event, "receiver")
        # Include if agent is sender (outgoing) OR receiver (notification)
        return sender == agent_id or receiver == agent_id

    if event_type == "TransactionWentOverdue":
        return _get_str(event, "sender_id") == agent_id

    if event_type == "OverdueTransactionSettled":
        return _get_str(event, "sender_id") == agent_id

    if event_type == "TransactionReprioritized":
        return _get_str(event, "agent_id") == agent_id

    if event_type == "PriorityEscalated":
        return _get_str(event, "sender_id") == agent_id

    # =========================================================================
    # Incoming liquidity events (agent receives liquidity)
    # =========================================================================

    if event_type == "Queue2LiquidityRelease":
        sender = _get_str(event, "sender")
        receiver = _get_str(event, "receiver")
        # Include if agent is sender (outgoing released) OR receiver (incoming)
        return sender == agent_id or receiver == agent_id

    if event_type == "QueuedRtgs":
        return _get_str(event, "sender_id") == agent_id

    if event_type == "LsmBilateralOffset":
        agent_a = _get_str(event, "agent_a")
        agent_b = _get_str(event, "agent_b")
        return agent_id in (agent_a, agent_b)

    if event_type == "LsmCycleSettlement":
        agents = _get_str_list(event, "agents")
        return agent_id in agents

    if event_type == "EntryDispositionOffset":
        agent_a = _get_str(event, "agent_a")
        agent_b = _get_str(event, "agent_b")
        return agent_id in (agent_a, agent_b)

    # =========================================================================
    # Agent state events (own state only)
    # =========================================================================

    if event_type in (
        "CollateralPost",
        "CollateralWithdraw",
        "CollateralTimerWithdrawn",
        "CollateralTimerBlocked",
    ):
        return _get_str(event, "agent_id") == agent_id

    if event_type == "StateRegisterSet":
        return _get_str(event, "agent_id") == agent_id

    if event_type == "BankBudgetSet":
        return _get_str(event, "agent_id") == agent_id

    if event_type == "CostAccrual":
        return _get_str(event, "agent_id") == agent_id

    # =========================================================================
    # General events (not agent-specific)
    # =========================================================================

    if event_type == "EndOfDay":
        # End of day is general info, include for all agents
        return True

    if event_type == "ScenarioEventExecuted":
        # Scenario events are general info
        return True

    if event_type == "AlgorithmExecution":
        # Algorithm info is general
        return True

    # =========================================================================
    # Limit-related events (agent is blocked)
    # =========================================================================

    if event_type == "BilateralLimitExceeded":
        return _get_str(event, "sender") == agent_id

    if event_type == "MultilateralLimitExceeded":
        return _get_str(event, "sender") == agent_id

    # Unknown event type - exclude to be safe
    return False


def format_filtered_output(
    agent_id: str,
    events: list[dict[str, Any]],
    include_tick_headers: bool = True,
) -> str:
    """Format filtered events as readable simulation output.

    Creates a human-readable representation of events suitable for LLM
    consumption. Events are grouped by tick with clear separators.

    Args:
        agent_id: ID of the target agent.
        events: Pre-filtered list of events.
        include_tick_headers: Whether to include tick separators.

    Returns:
        Formatted text output.
    """
    if not events:
        return f"No events recorded for {agent_id}.\n"

    # Group events by tick
    events_by_tick: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        tick = event.get("tick", 0)
        events_by_tick[tick].append(event)

    lines: list[str] = []

    for tick in sorted(events_by_tick.keys()):
        tick_events = events_by_tick[tick]

        if include_tick_headers:
            lines.append(f"\n═══ Tick {tick} ═══\n")

        # Format each event in this tick
        for event in tick_events:
            formatted = _format_single_event(agent_id, event)
            if formatted:
                lines.append(formatted)

    return "\n".join(lines)


def _format_single_event(agent_id: str, event: dict[str, Any]) -> str:
    """Format a single event for display.

    Args:
        agent_id: Target agent ID (for context).
        event: Event data.

    Returns:
        Formatted string representation.
    """
    event_type = event.get("event_type", "Unknown")

    if event_type == "Arrival":
        sender = event.get("sender_id", "?")
        receiver = event.get("receiver_id", "?")
        amount = event.get("amount", 0)
        priority = event.get("priority", 0)
        deadline = event.get("deadline", 0)
        tx_id = event.get("tx_id", "?")

        amount_fmt = _format_amount(amount)

        if sender == agent_id:
            direction = "📤 Outgoing"
        else:
            direction = "📥 Incoming"

        return (
            f"{direction} TX {tx_id[:8]}...: {sender} → {receiver}\n"
            f"  {amount_fmt} | Priority: {priority} | Deadline: Tick {deadline}"
        )

    if event_type == "RtgsImmediateSettlement":
        sender = event.get("sender", "?")
        receiver = event.get("receiver", "?")
        amount = event.get("amount", 0)
        balance_before = event.get("sender_balance_before", None)
        balance_after = event.get("sender_balance_after", None)
        tx_id = event.get("tx_id", "?")

        amount_fmt = _format_amount(amount)

        if sender == agent_id:
            # Outgoing settlement
            result = f"✅ RTGS Settled (outgoing): {sender} → {receiver} | {amount_fmt}"
            if balance_before is not None and balance_after is not None:
                result += f"\n  Balance: {_format_amount(balance_before)} → {_format_amount(balance_after)}"
        else:
            # Incoming settlement (liquidity)
            result = f"💰 Received: {sender} → {receiver} | {amount_fmt}"

        return result

    if event_type == "Queue2LiquidityRelease":
        sender = event.get("sender", "?")
        receiver = event.get("receiver", "?")
        amount = event.get("amount", 0)
        wait_ticks = event.get("queue_wait_ticks", 0)
        reason = event.get("release_reason", "")
        tx_id = event.get("tx_id", "?")

        amount_fmt = _format_amount(amount)

        if sender == agent_id:
            return f"✅ Queue Released: {sender} → {receiver} | {amount_fmt} (waited {wait_ticks} ticks)"
        else:
            return f"💰 Received (from queue): {sender} → {receiver} | {amount_fmt}"

    if event_type in ("PolicySubmit", "PolicyHold", "PolicyDrop"):
        tx_id = event.get("tx_id", "?")
        action = event_type.replace("Policy", "")
        reason = event.get("reason", "")

        result = f"📋 Decision: {action} TX {tx_id[:8]}..."
        if reason:
            result += f" ({reason})"
        return result

    if event_type == "PolicySplit":
        tx_id = event.get("tx_id", "?")
        num_splits = event.get("num_splits", 0)
        return f"📋 Decision: Split TX {tx_id[:8]}... into {num_splits} parts"

    if event_type == "CollateralPost":
        amount = event.get("amount", 0)
        new_total = event.get("new_total", 0)
        reason = event.get("reason", "")
        return f"💎 Posted Collateral: {_format_amount(amount)} (total: {_format_amount(new_total)})"

    if event_type == "CollateralWithdraw":
        amount = event.get("amount", 0)
        new_total = event.get("new_total", 0)
        return f"💎 Withdrew Collateral: {_format_amount(amount)} (total: {_format_amount(new_total)})"

    if event_type == "CostAccrual":
        costs = event.get("costs", {})
        if isinstance(costs, dict):
            total = sum(costs.values()) if costs else 0
            breakdown = ", ".join(f"{k}: {_format_amount(v)}" for k, v in costs.items() if v)
            if breakdown:
                return f"💸 Costs: {breakdown}"
            return f"💸 Costs: {_format_amount(total)}"
        return f"💸 Costs: {costs}"

    if event_type == "BankBudgetSet":
        max_value = event.get("max_value", 0)
        return f"🏦 Budget Set: Max release {_format_amount(max_value)}"

    if event_type == "LsmBilateralOffset":
        agent_a = event.get("agent_a", "?")
        agent_b = event.get("agent_b", "?")
        amount_a = event.get("amount_a", 0)
        amount_b = event.get("amount_b", 0)
        return f"🔄 LSM Bilateral: {agent_a} ↔ {agent_b} | {_format_amount(amount_a)}/{_format_amount(amount_b)}"

    if event_type == "LsmCycleSettlement":
        agents = event.get("agents", [])
        total_value = event.get("total_value", 0)
        return f"🔄 LSM Cycle: {' → '.join(agents)} | Total: {_format_amount(total_value)}"

    if event_type == "TransactionWentOverdue":
        tx_id = event.get("tx_id", "?")
        penalty = event.get("deadline_penalty_cost", 0)
        return f"⚠️ TX {tx_id[:8]}... became OVERDUE! Penalty: {_format_amount(penalty)}"

    if event_type == "OverdueTransactionSettled":
        tx_id = event.get("tx_id", "?")
        delay_cost = event.get("estimated_delay_cost", 0)
        return f"✅ Overdue TX {tx_id[:8]}... finally settled | Delay cost: {_format_amount(delay_cost)}"

    if event_type == "EndOfDay":
        day = event.get("day", 0)
        unsettled = event.get("unsettled_count", 0)
        penalties = event.get("total_penalties", 0)
        return f"🌙 End of Day {day}: {unsettled} unsettled | Penalties: {_format_amount(penalties)}"

    # RtgsSubmission - already covered by PolicySubmit decision, skip to avoid duplication
    if event_type == "RtgsSubmission":
        return ""

    if event_type == "RtgsWithdrawal":
        tx_id = event.get("tx_id", "?")
        return f"↩️ Withdrew TX {tx_id[:8]}... from queue"

    if event_type == "RtgsResubmission":
        tx_id = event.get("tx_id", "?")
        return f"🔄 Resubmitted TX {tx_id[:8]}... to queue"

    if event_type == "QueuedRtgs":
        tx_id = event.get("tx_id", "?")
        reason = event.get("reason", "insufficient liquidity")
        return f"📋 Queued TX {tx_id[:8]}... ({reason})"

    if event_type == "PriorityEscalated":
        tx_id = event.get("tx_id", "?")
        old_priority = event.get("old_priority", "?")
        new_priority = event.get("new_priority", "?")
        return f"⬆️ Priority escalated TX {tx_id[:8]}...: {old_priority} → {new_priority}"

    if event_type == "TransactionReprioritized":
        tx_id = event.get("tx_id", "?")
        new_priority = event.get("new_priority", "?")
        return f"🔀 Reprioritized TX {tx_id[:8]}... to priority {new_priority}"

    # Skip events that don't add useful information for optimization
    if event_type in (
        "ScenarioEventExecuted",
        "AlgorithmExecution",
        "StateRegisterSet",
        "BilateralLimitExceeded",
        "MultilateralLimitExceeded",
        "CollateralTimerWithdrawn",
        "CollateralTimerBlocked",
        "EntryDispositionOffset",
    ):
        return ""

    # Generic fallback - show event type only, not raw dict
    return f"• {event_type}"


def _format_amount(cents: int | float) -> str:
    """Format an amount in cents as dollars.

    Args:
        cents: Amount in integer cents.

    Returns:
        Formatted dollar string (e.g., "$1,234.56").
    """
    if not isinstance(cents, (int, float)):
        return str(cents)

    dollars = abs(cents) / 100
    formatted = f"${dollars:,.2f}"
    if cents < 0:
        formatted = f"-{formatted}"
    return formatted
