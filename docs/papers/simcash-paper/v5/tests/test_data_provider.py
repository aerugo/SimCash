"""Tests for DataProvider - TDD RED phase first.

These tests define the expected behavior of the data provider layer.
Run with: python -m pytest tests/test_data_provider.py -v
"""

from __future__ import annotations

from pathlib import Path
from typing import get_type_hints

import pytest


# =============================================================================
# Phase 1.1: TypedDict Structure Tests (RED)
# =============================================================================


class TestAgentIterationResultTypedDict:
    """Test that AgentIterationResult has all required fields."""

    def test_has_iteration_field(self) -> None:
        """AgentIterationResult must have 'iteration' field of type int."""
        from src.data_provider import AgentIterationResult

        hints = get_type_hints(AgentIterationResult)
        assert "iteration" in hints, "Missing 'iteration' field"
        assert hints["iteration"] is int, "iteration must be int"

    def test_has_agent_id_field(self) -> None:
        """AgentIterationResult must have 'agent_id' field of type str."""
        from src.data_provider import AgentIterationResult

        hints = get_type_hints(AgentIterationResult)
        assert "agent_id" in hints, "Missing 'agent_id' field"
        assert hints["agent_id"] is str, "agent_id must be str"

    def test_has_cost_field(self) -> None:
        """AgentIterationResult must have 'cost' field of type int (cents)."""
        from src.data_provider import AgentIterationResult

        hints = get_type_hints(AgentIterationResult)
        assert "cost" in hints, "Missing 'cost' field"
        assert hints["cost"] is int, "cost must be int (cents, not dollars)"

    def test_has_liquidity_fraction_field(self) -> None:
        """AgentIterationResult must have 'liquidity_fraction' field of type float."""
        from src.data_provider import AgentIterationResult

        hints = get_type_hints(AgentIterationResult)
        assert "liquidity_fraction" in hints, "Missing 'liquidity_fraction' field"
        assert hints["liquidity_fraction"] is float, "liquidity_fraction must be float"

    def test_has_accepted_field(self) -> None:
        """AgentIterationResult must have 'accepted' field of type bool."""
        from src.data_provider import AgentIterationResult

        hints = get_type_hints(AgentIterationResult)
        assert "accepted" in hints, "Missing 'accepted' field"
        assert hints["accepted"] is bool, "accepted must be bool"


class TestBootstrapStatsTypedDict:
    """Test that BootstrapStats has all required fields."""

    def test_has_mean_cost_field(self) -> None:
        """BootstrapStats must have 'mean_cost' field of type int."""
        from src.data_provider import BootstrapStats

        hints = get_type_hints(BootstrapStats)
        assert "mean_cost" in hints, "Missing 'mean_cost' field"
        assert hints["mean_cost"] is int, "mean_cost must be int (cents)"

    def test_has_std_dev_field(self) -> None:
        """BootstrapStats must have 'std_dev' field of type int."""
        from src.data_provider import BootstrapStats

        hints = get_type_hints(BootstrapStats)
        assert "std_dev" in hints, "Missing 'std_dev' field"
        assert hints["std_dev"] is int, "std_dev must be int (cents)"

    def test_has_ci_lower_field(self) -> None:
        """BootstrapStats must have 'ci_lower' field of type int."""
        from src.data_provider import BootstrapStats

        hints = get_type_hints(BootstrapStats)
        assert "ci_lower" in hints, "Missing 'ci_lower' field"
        assert hints["ci_lower"] is int, "ci_lower must be int (cents)"

    def test_has_ci_upper_field(self) -> None:
        """BootstrapStats must have 'ci_upper' field of type int."""
        from src.data_provider import BootstrapStats

        hints = get_type_hints(BootstrapStats)
        assert "ci_upper" in hints, "Missing 'ci_upper' field"
        assert hints["ci_upper"] is int, "ci_upper must be int (cents)"

    def test_has_num_samples_field(self) -> None:
        """BootstrapStats must have 'num_samples' field of type int."""
        from src.data_provider import BootstrapStats

        hints = get_type_hints(BootstrapStats)
        assert "num_samples" in hints, "Missing 'num_samples' field"
        assert hints["num_samples"] is int, "num_samples must be int"


# =============================================================================
# Phase 1.2: DataProvider Protocol Tests (RED)
# =============================================================================


class TestDataProviderProtocol:
    """Test that DataProvider protocol defines required methods."""

    def test_protocol_has_get_iteration_results(self) -> None:
        """DataProvider must define get_iteration_results method."""
        from src.data_provider import DataProvider

        assert hasattr(DataProvider, "get_iteration_results")

    def test_protocol_has_get_final_bootstrap_stats(self) -> None:
        """DataProvider must define get_final_bootstrap_stats method."""
        from src.data_provider import DataProvider

        assert hasattr(DataProvider, "get_final_bootstrap_stats")

    def test_protocol_has_get_convergence_iteration(self) -> None:
        """DataProvider must define get_convergence_iteration method."""
        from src.data_provider import DataProvider

        assert hasattr(DataProvider, "get_convergence_iteration")

    def test_protocol_has_get_run_id(self) -> None:
        """DataProvider must define get_run_id method."""
        from src.data_provider import DataProvider

        assert hasattr(DataProvider, "get_run_id")

    def test_database_provider_implements_protocol(self) -> None:
        """DatabaseDataProvider must implement DataProvider protocol."""
        from src.data_provider import DatabaseDataProvider, DataProvider

        # Create instance with test data directory
        provider = DatabaseDataProvider(Path("data/"))

        # Check protocol compliance via isinstance (requires @runtime_checkable)
        assert isinstance(provider, DataProvider), (
            "DatabaseDataProvider must implement DataProvider protocol"
        )


# =============================================================================
# Phase 1.4: Integration Tests Against Real Data (RED)
# =============================================================================


class TestDatabaseDataProviderQueries:
    """Integration tests verifying queries against actual experiment databases."""

    @pytest.fixture
    def provider(self) -> "DatabaseDataProvider":
        """Create provider with actual data directory."""
        from src.data_provider import DatabaseDataProvider

        return DatabaseDataProvider(Path("data/"))

    # -------------------------------------------------------------------------
    # Experiment 1 Tests: Asymmetric Equilibrium
    # -------------------------------------------------------------------------

    def test_exp1_pass1_returns_results(self, provider: "DataProvider") -> None:
        """Exp1 Pass 1 should return non-empty iteration results."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        assert len(results) > 0, "Should have iteration results"

    def test_exp1_pass1_final_iteration_bank_a_cost(
        self, provider: "DataProvider"
    ) -> None:
        """Exp1 Pass 1 BANK_A should converge to 0 cost (free-rider)."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        assert bank_a["cost"] == 0, f"BANK_A should have 0 cost, got {bank_a['cost']}"

    def test_exp1_pass1_final_iteration_bank_b_cost(
        self, provider: "DataProvider"
    ) -> None:
        """Exp1 Pass 1 BANK_B should have positive cost (liquidity provider)."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_b = next(r for r in final_results if r["agent_id"] == "BANK_B")
        # BANK_B provides liquidity so should have positive cost
        assert bank_b["cost"] > 0, (
            f"BANK_B should have positive cost as liquidity provider, got {bank_b['cost']}"
        )

    def test_exp1_pass1_final_iteration_bank_a_liquidity(
        self, provider: "DataProvider"
    ) -> None:
        """Exp1 Pass 1 BANK_A should converge to 0% liquidity."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        assert bank_a["liquidity_fraction"] == 0.0, (
            f"BANK_A should have 0% liquidity, got {bank_a['liquidity_fraction']}"
        )

    def test_exp1_pass1_final_iteration_bank_b_liquidity(
        self, provider: "DataProvider"
    ) -> None:
        """Exp1 Pass 1 BANK_B should have positive liquidity (provider role)."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_b = next(r for r in final_results if r["agent_id"] == "BANK_B")
        # BANK_B provides liquidity so should have positive fraction
        assert bank_b["liquidity_fraction"] > 0, (
            f"BANK_B should have positive liquidity, got {bank_b['liquidity_fraction']}"
        )
        # Asymmetric: BANK_A should have less liquidity than BANK_B
        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        assert bank_a["liquidity_fraction"] < bank_b["liquidity_fraction"], (
            f"Asymmetric equilibrium: BANK_A ({bank_a['liquidity_fraction']}) "
            f"should have less liquidity than BANK_B ({bank_b['liquidity_fraction']})"
        )

    # -------------------------------------------------------------------------
    # Experiment 2 Tests: Stochastic + BUG FIX VERIFICATION
    # -------------------------------------------------------------------------

    def test_exp2_pass1_agents_have_different_costs(
        self, provider: "DataProvider"
    ) -> None:
        """CRITICAL: Exp2 agents must have DIFFERENT costs (bug fix verification).

        This test prevents the Appendix C bug where both agents showed identical
        costs ($225.49) despite having different liquidity fractions.
        """
        results = provider.get_iteration_results("exp2", pass_num=1)

        # Check iteration 2 specifically (where bug was observed in v4)
        iter2_results = [r for r in results if r["iteration"] == 2]

        if len(iter2_results) >= 2:
            costs = {r["agent_id"]: r["cost"] for r in iter2_results}
            assert costs["BANK_A"] != costs["BANK_B"], (
                f"BUG: Exp2 agents should have different costs! "
                f"BANK_A={costs['BANK_A']}, BANK_B={costs['BANK_B']}"
            )

    def test_exp2_pass1_bootstrap_stats_exist(self, provider: "DataProvider") -> None:
        """Exp2 should have bootstrap statistics."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)
        assert len(stats) == 2, "Should have stats for 2 agents"
        assert "BANK_A" in stats
        assert "BANK_B" in stats

    def test_exp2_pass1_has_nonzero_std_dev(self, provider: "DataProvider") -> None:
        """Exp2 bootstrap should show variance for stochastic scenario."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)

        # At least one agent should have nonzero std dev
        std_devs = [s["std_dev"] for s in stats.values()]
        assert any(sd > 0 for sd in std_devs), (
            f"Exp2 should have some variance, got std_devs={std_devs}"
        )

    def test_exp2_pass1_bootstrap_ci_bounds(self, provider: "DataProvider") -> None:
        """Exp2 bootstrap CI bounds should be sensible."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)

        for agent_id, s in stats.items():
            assert s["ci_lower"] <= s["mean_cost"] <= s["ci_upper"], (
                f"{agent_id}: CI bounds should contain mean. "
                f"lower={s['ci_lower']}, mean={s['mean_cost']}, upper={s['ci_upper']}"
            )

    # -------------------------------------------------------------------------
    # Experiment 3 Tests: Symmetric Equilibrium
    # -------------------------------------------------------------------------

    def test_exp3_pass1_both_agents_have_liquidity(
        self, provider: "DataProvider"
    ) -> None:
        """Exp3 Pass 1 both agents should have positive liquidity allocation."""
        results = provider.get_iteration_results("exp3", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        bank_b = next(r for r in final_results if r["agent_id"] == "BANK_B")

        # Both agents should have positive liquidity (symmetric scenario)
        assert bank_a["liquidity_fraction"] > 0, (
            f"BANK_A should have positive liquidity, got {bank_a['liquidity_fraction']}"
        )
        assert bank_b["liquidity_fraction"] > 0, (
            f"BANK_B should have positive liquidity, got {bank_b['liquidity_fraction']}"
        )

    def test_exp3_pass1_both_agents_have_costs(self, provider: "DataProvider") -> None:
        """Exp3 Pass 1 both agents should have positive costs."""
        results = provider.get_iteration_results("exp3", pass_num=1)
        final_iter = max(r["iteration"] for r in results)
        final_results = [r for r in results if r["iteration"] == final_iter]

        bank_a = next(r for r in final_results if r["agent_id"] == "BANK_A")
        bank_b = next(r for r in final_results if r["agent_id"] == "BANK_B")

        # Both agents should have positive costs
        assert bank_a["cost"] > 0, f"BANK_A should have positive cost, got {bank_a['cost']}"
        assert bank_b["cost"] > 0, f"BANK_B should have positive cost, got {bank_b['cost']}"

    # -------------------------------------------------------------------------
    # Cross-Pass Consistency Tests
    # -------------------------------------------------------------------------

    def test_all_passes_have_data(self, provider: "DataProvider") -> None:
        """All 9 experiment/pass combinations should have data."""
        for exp_id in ["exp1", "exp2", "exp3"]:
            for pass_num in [1, 2, 3]:
                results = provider.get_iteration_results(exp_id, pass_num)
                assert len(results) > 0, f"{exp_id} pass {pass_num} should have data"

    def test_convergence_iteration_matches_data(
        self, provider: "DataProvider"
    ) -> None:
        """get_convergence_iteration should match max iteration in results."""
        for exp_id in ["exp1", "exp2", "exp3"]:
            results = provider.get_iteration_results(exp_id, pass_num=1)
            expected_max = max(r["iteration"] for r in results)
            actual = provider.get_convergence_iteration(exp_id, pass_num=1)
            assert actual == expected_max, (
                f"{exp_id}: convergence iteration mismatch. "
                f"expected={expected_max}, got={actual}"
            )

    def test_run_id_format(self, provider: "DataProvider") -> None:
        """Run IDs should follow expected format."""
        run_id = provider.get_run_id("exp1", pass_num=1)
        assert run_id.startswith("exp1-"), f"Run ID should start with 'exp1-': {run_id}"
        assert len(run_id) > 10, f"Run ID seems too short: {run_id}"
