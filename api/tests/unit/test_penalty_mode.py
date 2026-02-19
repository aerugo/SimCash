"""Unit tests for PenaltyMode Pydantic model.

Phase 3 TDD: Tests for PenaltyMode parsing, validation, and FFI serialization.
These tests verify backwards compatibility (bare int → Fixed) and new dict format.
"""

import pytest
from pydantic import ValidationError

from payment_simulator.config.schemas import CostRates, PenaltyMode


# =============================================================================
# PenaltyMode model tests
# =============================================================================


class TestPenaltyModeFixed:
    """Test PenaltyMode with fixed amount."""

    def test_explicit_fixed(self) -> None:
        """Explicit fixed mode parses correctly."""
        mode = PenaltyMode(mode="fixed", amount=50_000)
        assert mode.mode == "fixed"
        assert mode.amount == 50_000
        assert mode.bps_per_event is None

    def test_fixed_missing_amount_rejected(self) -> None:
        """Fixed mode without amount raises validation error."""
        with pytest.raises(ValidationError):
            PenaltyMode(mode="fixed")

    def test_fixed_zero_amount(self) -> None:
        """Fixed mode with zero amount is valid."""
        mode = PenaltyMode(mode="fixed", amount=0)
        assert mode.amount == 0


class TestPenaltyModeRate:
    """Test PenaltyMode with rate-based calculation."""

    def test_explicit_rate(self) -> None:
        """Explicit rate mode parses correctly."""
        mode = PenaltyMode(mode="rate", bps_per_event=50.0)
        assert mode.mode == "rate"
        assert mode.bps_per_event == 50.0
        assert mode.amount is None

    def test_rate_missing_bps_rejected(self) -> None:
        """Rate mode without bps_per_event raises validation error."""
        with pytest.raises(ValidationError):
            PenaltyMode(mode="rate")

    def test_rate_zero_bps(self) -> None:
        """Rate mode with zero bps is valid."""
        mode = PenaltyMode(mode="rate", bps_per_event=0.0)
        assert mode.bps_per_event == 0.0


class TestPenaltyModeInvalid:
    """Test invalid PenaltyMode configurations."""

    def test_invalid_mode_rejected(self) -> None:
        """Unknown mode string raises validation error."""
        with pytest.raises(ValidationError):
            PenaltyMode(mode="invalid", amount=100)


# =============================================================================
# FFI serialization tests
# =============================================================================


class TestPenaltyModeFfi:
    """Test FFI dict serialization."""

    def test_fixed_to_ffi(self) -> None:
        """Fixed mode serializes to FFI dict."""
        mode = PenaltyMode(mode="fixed", amount=50_000)
        ffi = mode.to_ffi_dict()
        assert ffi == {"mode": "fixed", "amount": 50_000}

    def test_rate_to_ffi(self) -> None:
        """Rate mode serializes to FFI dict."""
        mode = PenaltyMode(mode="rate", bps_per_event=50.0)
        ffi = mode.to_ffi_dict()
        assert ffi == {"mode": "rate", "bps_per_event": 50.0}


# =============================================================================
# CostRates backwards compatibility tests
# =============================================================================


class TestCostRatesBackwardsCompat:
    """Test that CostRates accepts both bare int and PenaltyMode dict."""

    def test_bare_int_deadline_penalty(self) -> None:
        """Bare integer for deadline_penalty parses as Fixed mode."""
        rates = CostRates(deadline_penalty=50_000)
        assert isinstance(rates.deadline_penalty, PenaltyMode)
        assert rates.deadline_penalty.mode == "fixed"
        assert rates.deadline_penalty.amount == 50_000

    def test_bare_int_eod_penalty(self) -> None:
        """Bare integer for eod_penalty parses as Fixed mode."""
        rates = CostRates(eod_penalty=10_000)
        assert isinstance(rates.eod_penalty, PenaltyMode)
        assert rates.eod_penalty.mode == "fixed"
        assert rates.eod_penalty.amount == 10_000

    def test_old_field_name_eod(self) -> None:
        """Old field name 'eod_penalty_per_transaction' accepted via alias."""
        rates = CostRates(eod_penalty_per_transaction=10_000)
        assert isinstance(rates.eod_penalty, PenaltyMode)
        assert rates.eod_penalty.mode == "fixed"
        assert rates.eod_penalty.amount == 10_000

    def test_dict_rate_mode(self) -> None:
        """Dict with mode='rate' parses as Rate mode."""
        rates = CostRates(
            deadline_penalty={"mode": "rate", "bps_per_event": 50.0},
            eod_penalty={"mode": "rate", "bps_per_event": 100.0},
        )
        assert rates.deadline_penalty.mode == "rate"
        assert rates.deadline_penalty.bps_per_event == 50.0
        assert rates.eod_penalty.mode == "rate"
        assert rates.eod_penalty.bps_per_event == 100.0

    def test_dict_fixed_mode(self) -> None:
        """Dict with mode='fixed' parses as Fixed mode."""
        rates = CostRates(
            deadline_penalty={"mode": "fixed", "amount": 50_000},
        )
        assert rates.deadline_penalty.mode == "fixed"
        assert rates.deadline_penalty.amount == 50_000

    def test_default_values(self) -> None:
        """Default CostRates has Fixed-mode penalties."""
        rates = CostRates()
        assert isinstance(rates.deadline_penalty, PenaltyMode)
        assert rates.deadline_penalty.mode == "fixed"
        assert rates.deadline_penalty.amount == 50_000
        assert isinstance(rates.eod_penalty, PenaltyMode)
        assert rates.eod_penalty.mode == "fixed"
        assert rates.eod_penalty.amount == 10_000

    def test_full_config_all_bare_ints(self) -> None:
        """Complete CostRates with all bare integers still works."""
        rates = CostRates(
            overdraft_bps_per_tick=0.001,
            delay_cost_per_tick_per_cent=0.0001,
            collateral_cost_per_tick_bps=0.0002,
            eod_penalty=10_000,
            deadline_penalty=50_000,
            split_friction_cost=1000,
            overdue_delay_multiplier=5.0,
        )
        assert rates.deadline_penalty.amount == 50_000
        assert rates.eod_penalty.amount == 10_000


# =============================================================================
# CostRates FFI serialization tests
# =============================================================================


class TestCostRatesFfi:
    """Test CostRates FFI dict output for penalty fields."""

    def test_ffi_fixed_mode(self) -> None:
        """Fixed-mode penalties serialize as dicts in FFI output."""
        rates = CostRates(deadline_penalty=50_000, eod_penalty=10_000)
        # The _cost_rates_to_ffi_dict is on SimulationConfig, not CostRates
        # So we test the PenaltyMode serialization directly
        assert rates.deadline_penalty.to_ffi_dict() == {"mode": "fixed", "amount": 50_000}
        assert rates.eod_penalty.to_ffi_dict() == {"mode": "fixed", "amount": 10_000}

    def test_ffi_rate_mode(self) -> None:
        """Rate-mode penalties serialize as dicts in FFI output."""
        rates = CostRates(
            deadline_penalty={"mode": "rate", "bps_per_event": 50.0},
            eod_penalty={"mode": "rate", "bps_per_event": 100.0},
        )
        assert rates.deadline_penalty.to_ffi_dict() == {"mode": "rate", "bps_per_event": 50.0}
        assert rates.eod_penalty.to_ffi_dict() == {"mode": "rate", "bps_per_event": 100.0}
