"""Real data integration tests - verify generated paper matches database.

These tests are CRITICAL for ensuring the v4 bug (duplicate costs) never recurs.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def data_dir() -> Path:
    """Path to experiment databases."""
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def provider(data_dir: Path):
    """Create DatabaseDataProvider with real data."""
    from src.data_provider import DatabaseDataProvider

    if not data_dir.exists():
        pytest.skip("Data directory not available")

    return DatabaseDataProvider(data_dir)


@pytest.fixture
def generated_paper(provider, tmp_path: Path) -> str:
    """Generate paper and return content as string."""
    from src.paper_builder import generate_paper

    tex_path = generate_paper(provider, tmp_path)
    return tex_path.read_text()


# =============================================================================
# Phase 5.3: Real Data Verification Tests
# =============================================================================


class TestConvergenceDataInPaper:
    """Verify convergence iterations appear correctly in paper."""

    def test_exp1_convergence_iteration_in_abstract(
        self, provider, generated_paper: str
    ) -> None:
        """Abstract should contain correct exp1 convergence iteration."""
        convergence = provider.get_convergence_iteration("exp1", pass_num=1)

        # The iteration number should appear in the abstract
        assert str(convergence) in generated_paper, (
            f"Exp1 convergence iteration {convergence} not found in paper"
        )

    def test_exp2_convergence_iteration_in_paper(
        self, provider, generated_paper: str
    ) -> None:
        """Paper should contain correct exp2 convergence iteration."""
        convergence = provider.get_convergence_iteration("exp2", pass_num=1)

        assert str(convergence) in generated_paper, (
            f"Exp2 convergence iteration {convergence} not found in paper"
        )

    def test_exp3_convergence_iteration_in_paper(
        self, provider, generated_paper: str
    ) -> None:
        """Paper should contain correct exp3 convergence iteration."""
        convergence = provider.get_convergence_iteration("exp3", pass_num=1)

        assert str(convergence) in generated_paper, (
            f"Exp3 convergence iteration {convergence} not found in paper"
        )


class TestCostDataInPaper:
    """Verify cost data appears correctly in paper."""

    def test_exp1_final_costs_in_paper(
        self, provider, generated_paper: str
    ) -> None:
        """Paper should contain exp1 final iteration costs."""
        results = provider.get_iteration_results("exp1", pass_num=1)
        convergence = provider.get_convergence_iteration("exp1", pass_num=1)

        final_results = [r for r in results if r["iteration"] == convergence]

        for result in final_results:
            # Format as dollars (how it appears in paper)
            dollars = result["cost"] / 100
            # Check for formatted value (could be $X.XX or $X,XXX.XX)
            formatted = f"{dollars:.2f}"

            assert formatted in generated_paper, (
                f"Cost {formatted} for {result['agent_id']} not found in paper"
            )


class TestBugFixVerification:
    """CRITICAL: Verify the v4 bug (duplicate costs) cannot recur."""

    def test_exp2_agents_have_different_costs_in_database(
        self, provider
    ) -> None:
        """Database should have DIFFERENT costs for exp2 agents."""
        results = provider.get_iteration_results("exp2", pass_num=1)

        # Get iteration 2 results (where the bug was visible)
        iter2_results = [r for r in results if r["iteration"] == 2]

        if len(iter2_results) >= 2:
            costs = {r["agent_id"]: r["cost"] for r in iter2_results}

            assert costs.get("BANK_A") != costs.get("BANK_B"), (
                f"BUG: Exp2 iteration 2 has identical costs! "
                f"BANK_A={costs.get('BANK_A')}, BANK_B={costs.get('BANK_B')}"
            )

    def test_exp2_different_costs_appear_in_paper(
        self, provider, generated_paper: str
    ) -> None:
        """CRITICAL: Paper must show DIFFERENT costs for exp2 agents."""
        results = provider.get_iteration_results("exp2", pass_num=1)

        # Get iteration 2 results
        iter2_results = [r for r in results if r["iteration"] == 2]

        if len(iter2_results) >= 2:
            costs = {r["agent_id"]: r["cost"] for r in iter2_results}

            bank_a_dollars = f"{costs['BANK_A']/100:.2f}"
            bank_b_dollars = f"{costs['BANK_B']/100:.2f}"

            # Both values should appear in the paper
            assert bank_a_dollars in generated_paper, (
                f"BANK_A cost {bank_a_dollars} not found in paper"
            )
            assert bank_b_dollars in generated_paper, (
                f"BANK_B cost {bank_b_dollars} not found in paper"
            )

            # And they must be different (the actual bug fix)
            assert bank_a_dollars != bank_b_dollars, (
                f"BUG DETECTED: Exp2 agents have identical costs in paper! "
                f"Both show ${bank_a_dollars}"
            )

    def test_exp2_bootstrap_means_are_different(
        self, provider, generated_paper: str
    ) -> None:
        """Bootstrap means for exp2 agents should be different."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)

        if "BANK_A" in stats and "BANK_B" in stats:
            mean_a = stats["BANK_A"]["mean_cost"]
            mean_b = stats["BANK_B"]["mean_cost"]

            assert mean_a != mean_b, (
                f"Bootstrap means should differ: BANK_A={mean_a}, BANK_B={mean_b}"
            )


class TestDataProviderConsistency:
    """Verify DataProvider returns consistent data."""

    def test_multiple_calls_return_same_data(self, provider) -> None:
        """Multiple calls should return identical results."""
        results1 = provider.get_iteration_results("exp1", pass_num=1)
        results2 = provider.get_iteration_results("exp1", pass_num=1)

        assert results1 == results2, "DataProvider should be deterministic"

    def test_all_experiments_have_data(self, provider) -> None:
        """All three experiments should have data."""
        for exp_id in ["exp1", "exp2", "exp3"]:
            results = provider.get_iteration_results(exp_id, pass_num=1)
            assert len(results) > 0, f"{exp_id} should have results"

    def test_all_passes_have_data(self, provider) -> None:
        """All passes should have data for each experiment."""
        for exp_id in ["exp1", "exp2", "exp3"]:
            for pass_num in [1, 2, 3]:
                results = provider.get_iteration_results(exp_id, pass_num=pass_num)
                assert len(results) > 0, f"{exp_id} pass {pass_num} should have results"
