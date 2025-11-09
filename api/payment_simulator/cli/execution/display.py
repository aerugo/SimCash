"""Shared verbose output display logic.

This module contains the SINGLE SOURCE OF TRUTH for verbose tick output.
Both live execution and replay MUST call display_tick_verbose_output().

This ensures they can NEVER diverge - if new output sections are added,
both modes automatically get them.
"""

from typing import Any

from payment_simulator.cli.execution.state_provider import StateProvider


def display_tick_verbose_output(
    provider: StateProvider,
    events: list[dict],
    tick_num: int,
    agent_ids: list[str],
    prev_balances: dict[str, int],
    num_arrivals: int,
    num_settlements: int,
    num_lsm_releases: int,
    total_cost: int = 0,
    event_filter: Any = None,
    quiet: bool = False,
) -> dict[str, int]:
    """Display all verbose output sections for a tick.

    This is the SINGLE SOURCE OF TRUTH for tick verbose output.
    Both live execution (strategies.py) and replay (replay.py) MUST call this.

    Args:
        provider: StateProvider (OrchestratorStateProvider or DatabaseStateProvider)
        events: All events for this tick
        tick_num: Current tick number
        agent_ids: List of all agent IDs
        prev_balances: Previous tick's balances (for calculating changes)
        num_arrivals: Count of arrivals this tick
        num_settlements: Count of settlements this tick
        num_lsm_releases: Count of LSM releases this tick
        total_cost: Total cost accrued this tick (for conditional display)
        event_filter: Optional filter to apply to events
        quiet: Suppress output if True

    Returns:
        Updated prev_balances dict for next tick

    Sections displayed (in order):
        1. Transaction Arrivals
        2. Policy Decisions
        3. Settlements (RTGS + LSM)
        4. Queued RTGS
        5. LSM Cycle Visualization
        6. Collateral Activity
        7. Agent States (detailed queues)
        8. Cost Accruals
        9. Cost Breakdown
        10. Tick Summary
    """
    from payment_simulator.cli.output import (
        log_agent_state,
        log_collateral_activity,
        log_cost_accrual_events,
        log_cost_breakdown,
        log_lsm_cycle_visualization,
        log_policy_decisions,
        log_queued_rtgs,
        log_settlement_details,
        log_tick_summary,
        log_transaction_arrivals,
    )

    if quiet:
        return prev_balances

    # Apply event filter if specified
    display_events = events
    if event_filter:
        display_events = [e for e in events if event_filter.matches(e, tick_num)]

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: ARRIVALS (detailed)
    # ═══════════════════════════════════════════════════════════
    if num_arrivals > 0:
        log_transaction_arrivals(provider, display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: POLICY DECISIONS
    # ═══════════════════════════════════════════════════════════
    log_policy_decisions(display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 3: SETTLEMENTS (detailed with mechanisms)
    # ═══════════════════════════════════════════════════════════
    if num_settlements > 0 or any(
        e.get("event_type") in ["LsmBilateralOffset", "LsmCycleSettlement"]
        for e in display_events
    ):
        log_settlement_details(provider, display_events, tick_num)

    # ═══════════════════════════════════════════════════════════
    # SECTION 3.5: QUEUED TRANSACTIONS (RTGS)
    # ═══════════════════════════════════════════════════════════
    log_queued_rtgs(display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 4: LSM CYCLE VISUALIZATION
    # ═══════════════════════════════════════════════════════════
    log_lsm_cycle_visualization(display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 5: COLLATERAL ACTIVITY
    # ═══════════════════════════════════════════════════════════
    log_collateral_activity(display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 6: AGENT STATES (detailed queues)
    # ═══════════════════════════════════════════════════════════
    updated_balances = {}
    for agent_id in agent_ids:
        current_balance = provider.get_agent_balance(agent_id)
        balance_change = current_balance - prev_balances.get(agent_id, current_balance)

        # Only show agents with activity or non-empty queues
        queue1_size = provider.get_queue1_size(agent_id)
        rtgs_queue = provider.get_rtgs_queue_contents()
        agent_in_rtgs = any(
            provider.get_transaction_details(tx_id).get("sender_id") == agent_id
            for tx_id in rtgs_queue
            if provider.get_transaction_details(tx_id)
        )

        if balance_change != 0 or queue1_size > 0 or agent_in_rtgs:
            log_agent_state(provider, agent_id, balance_change)

        updated_balances[agent_id] = current_balance

    # ═══════════════════════════════════════════════════════════
    # SECTION 6.5: COST ACCRUAL EVENTS
    # ═══════════════════════════════════════════════════════════
    log_cost_accrual_events(display_events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 7: COST BREAKDOWN
    # ═══════════════════════════════════════════════════════════
    if total_cost > 0:
        log_cost_breakdown(provider, agent_ids)

    # ═══════════════════════════════════════════════════════════
    # SECTION 8: TICK SUMMARY
    # ═══════════════════════════════════════════════════════════
    total_queued = sum(provider.get_queue1_size(aid) for aid in agent_ids)
    log_tick_summary(
        num_arrivals,
        num_settlements,
        num_lsm_releases,
        total_queued,
    )

    return updated_balances
