"""Cost ordering validation.

Warns when the cost configuration may violate the expected ordering:
    liquidity cost < delay cost < penalty cost

This ordering ensures banks prefer committing liquidity (cheapest) over
delaying payments (medium) over missing deadlines entirely (most expensive).

This is a diagnostic warning, not a hard constraint — some research scenarios
may intentionally violate this ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

from payment_simulator.config.schemas import CostRates, PenaltyMode


@dataclass(frozen=True)
class CostOrderingWarning:
    """A warning about potential cost ordering violation.

    Attributes:
        category: Short label (e.g. "deadline_vs_delay", "eod_vs_delay").
        message: Human-readable explanation.
    """

    category: str
    message: str


def check_cost_ordering(
    cost_rates: CostRates,
    reference_amount_cents: int = 1_000_000,
) -> list[CostOrderingWarning]:
    """Check whether cost ordering is likely violated.

    Compares penalty costs against delay costs for a reference transaction
    amount. For rate-based penalties, the comparison is exact. For fixed
    penalties, we check if the penalty is less than the accumulated delay
    cost over a reasonable number of ticks.

    Args:
        cost_rates: The cost configuration to check.
        reference_amount_cents: Reference transaction amount for comparison
            (default: $10,000 = 1_000_000 cents).

    Returns:
        List of warnings. Empty list means no issues detected.
    """
    warnings: list[CostOrderingWarning] = []

    # Delay cost per tick for the reference amount
    delay_per_tick = reference_amount_cents * cost_rates.delay_cost_per_tick_per_cent

    if delay_per_tick <= 0:
        # No delay cost configured — can't compare
        return warnings

    # Resolve penalties for the reference amount
    deadline_penalty = _resolve_penalty(cost_rates.deadline_penalty, reference_amount_cents)
    eod_penalty = _resolve_penalty(cost_rates.eod_penalty, reference_amount_cents)

    # Check: deadline penalty should exceed delay cost accumulated over
    # a reasonable window (e.g., 10 ticks of delay before deadline)
    # If the penalty is less than 10 ticks of delay, banks have no incentive
    # to avoid missing the deadline.
    delay_10_ticks = delay_per_tick * 10

    if deadline_penalty > 0 and deadline_penalty < delay_10_ticks:
        warnings.append(CostOrderingWarning(
            category="deadline_vs_delay",
            message=(
                f"Deadline penalty ({deadline_penalty} cents) is less than "
                f"10 ticks of delay cost ({delay_10_ticks:.0f} cents) for a "
                f"${reference_amount_cents / 100:,.0f} transaction. "
                f"Banks may have little incentive to avoid missing deadlines. "
                f"Consider increasing deadline_penalty or using rate mode."
            ),
        ))

    if eod_penalty > 0 and eod_penalty < delay_10_ticks:
        warnings.append(CostOrderingWarning(
            category="eod_vs_delay",
            message=(
                f"EOD penalty ({eod_penalty} cents) is less than "
                f"10 ticks of delay cost ({delay_10_ticks:.0f} cents) for a "
                f"${reference_amount_cents / 100:,.0f} transaction. "
                f"Consider increasing eod_penalty or using rate mode."
            ),
        ))

    # Check: for rate mode, compare bps directly
    # delay_cost_per_tick_per_cent is effectively a rate too
    # A one-time penalty in bps should exceed delay rate × reasonable ticks
    if isinstance(cost_rates.deadline_penalty, PenaltyMode) and cost_rates.deadline_penalty.mode == "rate":
        penalty_bps = cost_rates.deadline_penalty.bps_per_event or 0.0
        # delay rate in comparable units: delay_cost_per_tick_per_cent * 10000 gives bps-equivalent per tick
        delay_bps_per_tick = cost_rates.delay_cost_per_tick_per_cent * 10_000
        if delay_bps_per_tick > 0 and penalty_bps < delay_bps_per_tick * 5:
            warnings.append(CostOrderingWarning(
                category="deadline_bps_vs_delay_bps",
                message=(
                    f"Deadline penalty rate ({penalty_bps:.1f} bps one-time) is less than "
                    f"5 ticks of delay cost ({delay_bps_per_tick * 5:.1f} bps). "
                    f"The penalty may not dominate delay cost for short delays."
                ),
            ))

    # Check: liquidity cost should be less than delay cost
    # overdraft_bps_per_tick vs delay_cost_per_tick_per_cent
    if cost_rates.overdraft_bps_per_tick > 0:
        # Overdraft cost for reference amount per tick
        overdraft_per_tick = reference_amount_cents * cost_rates.overdraft_bps_per_tick / 10_000
        if overdraft_per_tick > delay_per_tick:
            warnings.append(CostOrderingWarning(
                category="overdraft_vs_delay",
                message=(
                    f"Overdraft cost ({overdraft_per_tick:.1f} cents/tick) exceeds "
                    f"delay cost ({delay_per_tick:.1f} cents/tick) for a "
                    f"${reference_amount_cents / 100:,.0f} transaction. "
                    f"Banks may prefer delaying over using overdraft, "
                    f"which inverts the intended cost ordering."
                ),
            ))

    return warnings


def _resolve_penalty(penalty: PenaltyMode, amount_cents: int) -> int:
    """Resolve a PenaltyMode to a concrete amount for comparison."""
    match penalty.mode:
        case "fixed":
            return penalty.amount or 0
        case "rate":
            bps = penalty.bps_per_event or 0.0
            return int(amount_cents * bps / 10_000)
