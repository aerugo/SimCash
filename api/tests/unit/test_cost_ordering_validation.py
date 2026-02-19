"""Unit tests for cost ordering validation.

Phase 5 TDD: Tests for check_cost_ordering() which warns when the
cost hierarchy (liquidity < delay < penalty) is likely violated.
"""

from payment_simulator.config.schemas import CostRates, PenaltyMode
from payment_simulator.validation.cost_ordering import (
    CostOrderingWarning,
    check_cost_ordering,
)


class TestWellOrderedConfigs:
    """Configs that should produce no warnings."""

    def test_default_config_no_warnings(self) -> None:
        """Default CostRates should be well-ordered."""
        rates = CostRates()
        warnings = check_cost_ordering(rates)
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"

    def test_rate_mode_well_ordered_no_warnings(self) -> None:
        """Rate-mode penalties with sensible bps should be fine."""
        rates = CostRates(
            delay_cost_per_tick_per_cent=0.0001,
            deadline_penalty={"mode": "rate", "bps_per_event": 100.0},  # 1%
            eod_penalty={"mode": "rate", "bps_per_event": 200.0},      # 2%
            overdraft_bps_per_tick=0.001,
        )
        warnings = check_cost_ordering(rates)
        assert len(warnings) == 0, f"Unexpected warnings: {warnings}"


class TestDeadlinePenaltyWarnings:
    """Configs where deadline penalty is too low relative to delay."""

    def test_warns_fixed_penalty_less_than_delay(self) -> None:
        """Fixed penalty much smaller than accumulated delay → warning."""
        rates = CostRates(
            delay_cost_per_tick_per_cent=0.01,  # very high delay rate
            deadline_penalty=100,                # tiny fixed penalty ($1)
            eod_penalty=0,
        )
        warnings = check_cost_ordering(rates)
        categories = [w.category for w in warnings]
        assert "deadline_vs_delay" in categories

    def test_warns_rate_penalty_bps_less_than_delay(self) -> None:
        """Rate penalty bps lower than accumulated delay bps → warning."""
        rates = CostRates(
            delay_cost_per_tick_per_cent=0.01,  # 100 bps delay per tick
            deadline_penalty={"mode": "rate", "bps_per_event": 1.0},  # 0.01% one-time
            eod_penalty=0,
        )
        warnings = check_cost_ordering(rates)
        categories = [w.category for w in warnings]
        assert "deadline_bps_vs_delay_bps" in categories


class TestEodPenaltyWarnings:
    """Configs where EOD penalty is too low."""

    def test_warns_eod_less_than_delay(self) -> None:
        """EOD penalty much smaller than accumulated delay → warning."""
        rates = CostRates(
            delay_cost_per_tick_per_cent=0.01,
            deadline_penalty=0,
            eod_penalty=100,  # tiny
        )
        warnings = check_cost_ordering(rates)
        categories = [w.category for w in warnings]
        assert "eod_vs_delay" in categories


class TestOverdraftVsDelayWarnings:
    """Configs where overdraft is more expensive than delay."""

    def test_warns_overdraft_exceeds_delay(self) -> None:
        """When overdraft per tick > delay per tick → warning."""
        rates = CostRates(
            overdraft_bps_per_tick=10.0,         # very expensive overdraft
            delay_cost_per_tick_per_cent=0.0001,  # cheap delay
            deadline_penalty=50_000,
            eod_penalty=10_000,
        )
        warnings = check_cost_ordering(rates)
        categories = [w.category for w in warnings]
        assert "overdraft_vs_delay" in categories

    def test_no_warning_when_overdraft_cheaper(self) -> None:
        """Normal case: overdraft cheaper than delay → no warning."""
        rates = CostRates(
            overdraft_bps_per_tick=0.001,
            delay_cost_per_tick_per_cent=0.0001,
        )
        warnings = check_cost_ordering(rates)
        overdraft_warnings = [w for w in warnings if w.category == "overdraft_vs_delay"]
        assert len(overdraft_warnings) == 0


class TestNonBlocking:
    """Validation is advisory — never blocks simulation."""

    def test_returns_list_not_exception(self) -> None:
        """Even badly ordered config returns warnings, not exceptions."""
        rates = CostRates(
            delay_cost_per_tick_per_cent=1.0,  # absurdly high
            deadline_penalty=1,
            eod_penalty=1,
            overdraft_bps_per_tick=1000.0,
        )
        warnings = check_cost_ordering(rates)
        assert isinstance(warnings, list)
        assert all(isinstance(w, CostOrderingWarning) for w in warnings)

    def test_zero_delay_no_crash(self) -> None:
        """Zero delay cost should not crash."""
        rates = CostRates(delay_cost_per_tick_per_cent=0.0)
        warnings = check_cost_ordering(rates)
        assert isinstance(warnings, list)
