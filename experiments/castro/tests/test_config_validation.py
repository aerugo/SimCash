"""
Config Validation Tests for Castro Experiments.

These tests verify that the experiment configurations:
1. Load correctly without errors
2. Have Castro alignment features enabled (deferred_crediting, deadline_cap_at_eod)
3. Have cost rates that match the Castro paper
4. Have proper agent configurations
5. Have LSM disabled (not in Castro model)

These are critical safeguards to prevent experimental results being distorted
by configuration errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml


# ============================================================================
# Config File Existence Tests
# ============================================================================


class TestConfigFilesExist:
    """Verify all required config files exist."""

    def test_exp1_config_exists(self, exp1_config_path: Path) -> None:
        """Experiment 1 config file must exist."""
        assert exp1_config_path.exists(), f"Missing: {exp1_config_path}"
        assert exp1_config_path.suffix == ".yaml"

    def test_exp2_config_exists(self, exp2_config_path: Path) -> None:
        """Experiment 2 config file must exist."""
        assert exp2_config_path.exists(), f"Missing: {exp2_config_path}"
        assert exp2_config_path.suffix == ".yaml"

    def test_exp3_config_exists(self, exp3_config_path: Path) -> None:
        """Experiment 3 config file must exist."""
        assert exp3_config_path.exists(), f"Missing: {exp3_config_path}"
        assert exp3_config_path.suffix == ".yaml"

    def test_seed_policy_exists(self, seed_policy_path: Path) -> None:
        """Seed policy file must exist."""
        assert seed_policy_path.exists(), f"Missing: {seed_policy_path}"
        assert seed_policy_path.suffix == ".json"


# ============================================================================
# Castro Alignment Feature Tests
# ============================================================================


class TestCastroAlignmentFeatures:
    """Verify Castro alignment features are enabled in all configs."""

    def test_exp1_deferred_crediting_enabled(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 1 must have deferred_crediting: true."""
        assert exp1_config_dict.get("deferred_crediting") is True, (
            "deferred_crediting must be True for Castro alignment. "
            "Without this, within-tick recycling is allowed which creates "
            "different equilibrium dynamics than Castro's model."
        )

    def test_exp1_deadline_cap_at_eod_enabled(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 1 must have deadline_cap_at_eod: true."""
        assert exp1_config_dict.get("deadline_cap_at_eod") is True, (
            "deadline_cap_at_eod must be True for Castro alignment. "
            "Without this, transactions can have multi-day deadlines which "
            "reduces settlement urgency."
        )

    def test_exp2_deferred_crediting_enabled(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 2 must have deferred_crediting: true."""
        assert exp2_config_dict.get("deferred_crediting") is True

    def test_exp2_deadline_cap_at_eod_enabled(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 2 must have deadline_cap_at_eod: true."""
        assert exp2_config_dict.get("deadline_cap_at_eod") is True

    def test_exp3_deferred_crediting_enabled(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 3 must have deferred_crediting: true."""
        assert exp3_config_dict.get("deferred_crediting") is True

    def test_exp3_deadline_cap_at_eod_enabled(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 3 must have deadline_cap_at_eod: true."""
        assert exp3_config_dict.get("deadline_cap_at_eod") is True


# ============================================================================
# LSM Disabled Tests (Not in Castro Model)
# ============================================================================


class TestLsmDisabled:
    """Verify LSM is disabled in all Castro configs.

    The Castro et al. paper uses pure RTGS without LSM optimization.
    """

    def test_exp1_lsm_bilateral_disabled(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 1 must have LSM bilateral offset disabled."""
        lsm_config = exp1_config_dict.get("lsm_config", {})
        assert lsm_config.get("enable_bilateral") is False, (
            "LSM bilateral must be disabled for Castro alignment"
        )

    def test_exp1_lsm_cycles_disabled(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Experiment 1 must have LSM cycle detection disabled."""
        lsm_config = exp1_config_dict.get("lsm_config", {})
        assert lsm_config.get("enable_cycles") is False, (
            "LSM cycles must be disabled for Castro alignment"
        )

    def test_exp2_lsm_disabled(self, exp2_config_dict: dict[str, Any]) -> None:
        """Experiment 2 must have LSM disabled."""
        lsm_config = exp2_config_dict.get("lsm_config", {})
        assert lsm_config.get("enable_bilateral") is False
        assert lsm_config.get("enable_cycles") is False

    def test_exp3_lsm_disabled(self, exp3_config_dict: dict[str, Any]) -> None:
        """Experiment 3 must have LSM disabled."""
        lsm_config = exp3_config_dict.get("lsm_config", {})
        assert lsm_config.get("enable_bilateral") is False
        assert lsm_config.get("enable_cycles") is False


# ============================================================================
# Cost Rate Validation Tests
# ============================================================================


class TestCostRates:
    """Verify cost rates match Castro paper derivations.

    Castro uses daily rates:
    - r_c = 0.1 (10% per day collateral opportunity cost)
    - r_d = 0.2 (20% per day delay cost)
    - r_b = 0.4 (40% per day borrowing/overdraft cost)

    These must be divided by ticks_per_day for per-tick rates.
    """

    def test_exp1_collateral_cost_rate(
        self,
        exp1_config_dict: dict[str, Any],
        exp1_expected_rates: dict[str, float],
    ) -> None:
        """Exp1 collateral cost: 0.1/day / 2 ticks = 5%/tick = 500 bps."""
        cost_rates = exp1_config_dict.get("cost_rates", {})
        actual = cost_rates.get("collateral_cost_per_tick_bps")
        expected = exp1_expected_rates["collateral_cost_per_tick_bps"]
        assert actual == expected, (
            f"Collateral cost mismatch: got {actual} bps, expected {expected} bps. "
            f"Formula: 0.1/day / 2 ticks * 10000 = 500 bps/tick"
        )

    def test_exp1_delay_cost_rate(
        self,
        exp1_config_dict: dict[str, Any],
    ) -> None:
        """Exp1 delay cost: 0.2/day / 2 ticks = 0.1/tick per cent = 0.001."""
        cost_rates = exp1_config_dict.get("cost_rates", {})
        actual = cost_rates.get("delay_cost_per_tick_per_cent")
        expected = 0.001  # 0.2 / 2 / 100 = 0.001
        assert actual == pytest.approx(expected, rel=0.01), (
            f"Delay cost mismatch: got {actual}, expected {expected}. "
            f"Formula: 0.2/day / 2 ticks = 0.1/tick, scaled per cent = 0.001"
        )

    def test_exp1_overdraft_cost_rate(
        self,
        exp1_config_dict: dict[str, Any],
        exp1_expected_rates: dict[str, float],
    ) -> None:
        """Exp1 overdraft cost: 0.4/day / 2 ticks = 20%/tick = 2000 bps."""
        cost_rates = exp1_config_dict.get("cost_rates", {})
        actual = cost_rates.get("overdraft_bps_per_tick")
        expected = exp1_expected_rates["overdraft_bps_per_tick"]
        assert actual == expected, (
            f"Overdraft cost mismatch: got {actual} bps, expected {expected} bps. "
            f"Formula: 0.4/day / 2 ticks * 10000 = 2000 bps/tick"
        )

    def test_exp2_cost_rates_scaled_for_12_ticks(
        self,
        exp2_config_dict: dict[str, Any],
        exp2_expected_rates: dict[str, float],
    ) -> None:
        """Exp2 costs must be divided by 12 (ticks_per_day)."""
        cost_rates = exp2_config_dict.get("cost_rates", {})

        # Collateral: 0.1 / 12 * 10000 = 83.33 -> 83
        assert cost_rates.get("collateral_cost_per_tick_bps") == 83, (
            "Collateral cost should be 83 bps (0.1/12 * 10000)"
        )

        # Delay: 0.2 / 12 / 100 = 0.000167
        assert cost_rates.get("delay_cost_per_tick_per_cent") == pytest.approx(
            0.00017, rel=0.1
        )

        # Overdraft: 0.4 / 12 * 10000 = 333.33 -> 333
        assert cost_rates.get("overdraft_bps_per_tick") == 333, (
            "Overdraft cost should be 333 bps (0.4/12 * 10000)"
        )

    def test_exp3_cost_rates_scaled_for_3_ticks(
        self,
        exp3_config_dict: dict[str, Any],
        exp3_expected_rates: dict[str, float],
    ) -> None:
        """Exp3 costs must be divided by 3 (ticks_per_day)."""
        cost_rates = exp3_config_dict.get("cost_rates", {})

        # Collateral: 0.1 / 3 * 10000 = 333.33 -> 333
        assert cost_rates.get("collateral_cost_per_tick_bps") == 333, (
            "Collateral cost should be 333 bps (0.1/3 * 10000)"
        )

        # Delay: 0.2 / 3 / 100 = 0.000667
        assert cost_rates.get("delay_cost_per_tick_per_cent") == pytest.approx(
            0.00067, rel=0.1
        )

        # Overdraft: 0.4 / 3 * 10000 = 1333.33 -> 1333
        assert cost_rates.get("overdraft_bps_per_tick") == 1333, (
            "Overdraft cost should be 1333 bps (0.4/3 * 10000)"
        )


class TestNonCastroCostsDisabled:
    """Verify non-Castro penalty costs are disabled.

    Castro uses continuous rate-based costs, not one-time penalties.
    """

    @pytest.mark.parametrize(
        "config_fixture", ["exp1_config_dict", "exp2_config_dict", "exp3_config_dict"]
    )
    def test_eod_penalty_disabled(
        self, config_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        """EOD penalty must be 0 (Castro uses rate-based costs)."""
        config = request.getfixturevalue(config_fixture)
        cost_rates = config.get("cost_rates", {})
        assert cost_rates.get("eod_penalty_per_transaction") == 0

    @pytest.mark.parametrize(
        "config_fixture", ["exp1_config_dict", "exp2_config_dict", "exp3_config_dict"]
    )
    def test_deadline_penalty_disabled(
        self, config_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        """Deadline penalty must be 0 (Castro uses rate-based costs)."""
        config = request.getfixturevalue(config_fixture)
        cost_rates = config.get("cost_rates", {})
        assert cost_rates.get("deadline_penalty") == 0

    @pytest.mark.parametrize(
        "config_fixture", ["exp1_config_dict", "exp2_config_dict", "exp3_config_dict"]
    )
    def test_split_friction_disabled(
        self, config_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        """Split friction cost must be 0 (not in Castro model)."""
        config = request.getfixturevalue(config_fixture)
        cost_rates = config.get("cost_rates", {})
        assert cost_rates.get("split_friction_cost") == 0

    @pytest.mark.parametrize(
        "config_fixture", ["exp1_config_dict", "exp2_config_dict", "exp3_config_dict"]
    )
    def test_overdue_multiplier_is_one(
        self, config_fixture: str, request: pytest.FixtureRequest
    ) -> None:
        """Overdue delay multiplier must be 1.0 (no extra penalty)."""
        config = request.getfixturevalue(config_fixture)
        cost_rates = config.get("cost_rates", {})
        assert cost_rates.get("overdue_delay_multiplier") == 1.0


# ============================================================================
# Agent Configuration Tests
# ============================================================================


class TestAgentConfiguration:
    """Verify agent configurations match Castro experiment requirements."""

    def test_exp1_has_two_agents(self, exp1_config_dict: dict[str, Any]) -> None:
        """Experiment 1 must have exactly 2 agents (BANK_A, BANK_B)."""
        agents = exp1_config_dict.get("agents", [])
        assert len(agents) == 2
        agent_ids = {a["id"] for a in agents}
        assert agent_ids == {"BANK_A", "BANK_B"}

    def test_exp1_agents_zero_opening_balance(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 agents must have zero opening balance (liquidity via collateral)."""
        agents = exp1_config_dict.get("agents", [])
        for agent in agents:
            assert agent.get("opening_balance") == 0, (
                f"Agent {agent['id']} should have 0 opening balance"
            )

    def test_exp1_agents_have_max_collateral_capacity(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 agents must have max_collateral_capacity defined."""
        agents = exp1_config_dict.get("agents", [])
        for agent in agents:
            assert "max_collateral_capacity" in agent, (
                f"Agent {agent['id']} must have max_collateral_capacity"
            )
            assert agent["max_collateral_capacity"] > 0

    def test_exp1_agents_use_from_json_policy(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 agents must use FromJson policy (for optimization)."""
        agents = exp1_config_dict.get("agents", [])
        for agent in agents:
            policy = agent.get("policy", {})
            assert policy.get("type") == "FromJson", (
                f"Agent {agent['id']} must use FromJson policy for optimization"
            )

    def test_exp2_has_two_agents(self, exp2_config_dict: dict[str, Any]) -> None:
        """Experiment 2 must have exactly 2 agents."""
        agents = exp2_config_dict.get("agents", [])
        assert len(agents) == 2

    def test_exp2_agents_have_arrival_configs(
        self, exp2_config_dict: dict[str, Any]
    ) -> None:
        """Exp2 agents must have arrival_config for stochastic arrivals."""
        agents = exp2_config_dict.get("agents", [])
        for agent in agents:
            assert "arrival_config" in agent, (
                f"Agent {agent['id']} must have arrival_config for Exp2"
            )

    def test_exp3_has_two_agents(self, exp3_config_dict: dict[str, Any]) -> None:
        """Experiment 3 must have exactly 2 agents."""
        agents = exp3_config_dict.get("agents", [])
        assert len(agents) == 2


# ============================================================================
# Simulation Settings Tests
# ============================================================================


class TestSimulationSettings:
    """Verify simulation settings match experiment requirements."""

    def test_exp1_ticks_per_day(self, exp1_config_dict: dict[str, Any]) -> None:
        """Experiment 1 must have 2 ticks per day."""
        simulation = exp1_config_dict.get("simulation", {})
        assert simulation.get("ticks_per_day") == 2

    def test_exp1_num_days(self, exp1_config_dict: dict[str, Any]) -> None:
        """Experiment 1 must run for 1 day."""
        simulation = exp1_config_dict.get("simulation", {})
        assert simulation.get("num_days") == 1

    def test_exp2_ticks_per_day(self, exp2_config_dict: dict[str, Any]) -> None:
        """Experiment 2 must have 12 ticks per day."""
        simulation = exp2_config_dict.get("simulation", {})
        assert simulation.get("ticks_per_day") == 12

    def test_exp3_ticks_per_day(self, exp3_config_dict: dict[str, Any]) -> None:
        """Experiment 3 must have 3 ticks per day."""
        simulation = exp3_config_dict.get("simulation", {})
        assert simulation.get("ticks_per_day") == 3


# ============================================================================
# Scenario Events Tests (Deterministic Payment Profile)
# ============================================================================


class TestScenarioEvents:
    """Verify scenario events define correct payment profiles."""

    def test_exp1_has_scenario_events(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 must use scenario_events for deterministic payments."""
        assert "scenario_events" in exp1_config_dict
        events = exp1_config_dict["scenario_events"]
        assert len(events) > 0

    def test_exp1_payment_profile_matches_castro(
        self, exp1_config_dict: dict[str, Any]
    ) -> None:
        """Exp1 payment profile must match Castro paper.

        Bank A: P^A = [0, $150] - No period 1 outgoing, $150 in period 2
        Bank B: P^B = [$150, $50] - $150 in period 1, $50 in period 2
        """
        events = exp1_config_dict.get("scenario_events", [])

        # Find BANK_A outgoing payments
        bank_a_payments = [
            e for e in events
            if e.get("type") == "CustomTransactionArrival"
            and e.get("from_agent") == "BANK_A"
        ]

        # Find BANK_B outgoing payments
        bank_b_payments = [
            e for e in events
            if e.get("type") == "CustomTransactionArrival"
            and e.get("from_agent") == "BANK_B"
        ]

        # BANK_A: Should have 1 payment of $150 in period 2 (tick 1)
        assert len(bank_a_payments) == 1, "Bank A should have 1 outgoing payment"
        assert bank_a_payments[0]["amount"] == 15000  # $150 in cents
        # Payment arrives at tick 1 (period 2)
        assert bank_a_payments[0]["schedule"]["tick"] == 1

        # BANK_B: Should have 2 payments - $150 in period 1, $50 in period 2
        assert len(bank_b_payments) == 2, "Bank B should have 2 outgoing payments"

        # Find period 1 and period 2 payments
        p1_payment = next(
            (p for p in bank_b_payments if p["schedule"]["tick"] == 0), None
        )
        p2_payment = next(
            (p for p in bank_b_payments if p["schedule"]["tick"] == 1), None
        )

        assert p1_payment is not None, "Bank B should have period 1 payment"
        assert p1_payment["amount"] == 15000  # $150 in cents

        assert p2_payment is not None, "Bank B should have period 2 payment"
        assert p2_payment["amount"] == 5000  # $50 in cents

    def test_exp3_symmetric_payment_profile(
        self, exp3_config_dict: dict[str, Any]
    ) -> None:
        """Exp3 must have symmetric payment profile.

        Both banks: P = [$200, $200, $0]
        """
        events = exp3_config_dict.get("scenario_events", [])

        bank_a_payments = [
            e for e in events
            if e.get("type") == "CustomTransactionArrival"
            and e.get("from_agent") == "BANK_A"
        ]

        bank_b_payments = [
            e for e in events
            if e.get("type") == "CustomTransactionArrival"
            and e.get("from_agent") == "BANK_B"
        ]

        # Both should have 2 payments of $200 each
        assert len(bank_a_payments) == 2
        assert len(bank_b_payments) == 2

        for payment in bank_a_payments + bank_b_payments:
            assert payment["amount"] == 20000  # $200 in cents
