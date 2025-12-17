"""Tests for section generators - TDD RED phase.

These tests define the expected behavior of section generator functions.
Each section generator takes a DataProvider and returns LaTeX string.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from src.data_provider import DataProvider


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_provider() -> MagicMock:
    """Create mock DataProvider with realistic test data."""
    provider = MagicMock(spec=["get_iteration_results", "get_final_bootstrap_stats",
                               "get_convergence_iteration", "get_run_id"])

    # Mock exp1 data (asymmetric equilibrium)
    provider.get_iteration_results.return_value = [
        {"iteration": 1, "agent_id": "BANK_A", "cost": 5000, "liquidity_fraction": 0.3, "accepted": True},
        {"iteration": 1, "agent_id": "BANK_B", "cost": 3000, "liquidity_fraction": 0.2, "accepted": True},
        {"iteration": 2, "agent_id": "BANK_A", "cost": 2000, "liquidity_fraction": 0.15, "accepted": True},
        {"iteration": 2, "agent_id": "BANK_B", "cost": 4000, "liquidity_fraction": 0.25, "accepted": True},
        {"iteration": 3, "agent_id": "BANK_A", "cost": 0, "liquidity_fraction": 0.0, "accepted": True},
        {"iteration": 3, "agent_id": "BANK_B", "cost": 5000, "liquidity_fraction": 0.33, "accepted": True},
    ]

    provider.get_final_bootstrap_stats.return_value = {
        "BANK_A": {"mean_cost": 16440, "std_dev": 500, "ci_lower": 15500, "ci_upper": 17400, "num_samples": 50},
        "BANK_B": {"mean_cost": 13349, "std_dev": 800, "ci_lower": 11800, "ci_upper": 14900, "num_samples": 50},
    }

    provider.get_convergence_iteration.return_value = 3
    provider.get_run_id.return_value = "exp1-20251215-abc123"

    return provider


# =============================================================================
# Phase 3.1: Abstract Section Tests (RED)
# =============================================================================


class TestAbstractSection:
    """Test abstract section generator."""

    def test_generates_section_environment(self, mock_provider: MagicMock) -> None:
        """Abstract should use LaTeX abstract environment."""
        from src.sections.abstract import generate_abstract

        result = generate_abstract(mock_provider)

        assert r"\begin{abstract}" in result
        assert r"\end{abstract}" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_abstract must return str type."""
        from src.sections.abstract import generate_abstract

        result = generate_abstract(mock_provider)
        assert isinstance(result, str)

    def test_mentions_key_concepts(self, mock_provider: MagicMock) -> None:
        """Abstract should mention core concepts."""
        from src.sections.abstract import generate_abstract

        result = generate_abstract(mock_provider)

        # Should mention key concepts (case-insensitive check)
        result_lower = result.lower()
        assert "equilibrium" in result_lower or "convergence" in result_lower
        assert "agent" in result_lower or "bank" in result_lower


# =============================================================================
# Phase 3.2: Introduction Section Tests (RED)
# =============================================================================


class TestIntroductionSection:
    """Test introduction section generator."""

    def test_generates_section_command(self, mock_provider: MagicMock) -> None:
        """Introduction should use LaTeX section command."""
        from src.sections.introduction import generate_introduction

        result = generate_introduction(mock_provider)

        assert r"\section{Introduction}" in result or r"\section*{Introduction}" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_introduction must return str type."""
        from src.sections.introduction import generate_introduction

        result = generate_introduction(mock_provider)
        assert isinstance(result, str)

    def test_includes_contributions(self, mock_provider: MagicMock) -> None:
        """Introduction should include contributions subsection or list."""
        from src.sections.introduction import generate_introduction

        result = generate_introduction(mock_provider)
        result_lower = result.lower()

        # Should mention contributions
        assert "contribut" in result_lower


# =============================================================================
# Phase 3.3: Methods Section Tests (RED)
# =============================================================================


class TestMethodsSection:
    """Test methods/framework section generator."""

    def test_generates_section_command(self, mock_provider: MagicMock) -> None:
        """Methods should use LaTeX section command."""
        from src.sections.methods import generate_methods

        result = generate_methods(mock_provider)

        # Could be "Methods", "Framework", "Methodology", etc.
        assert r"\section{" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_methods must return str type."""
        from src.sections.methods import generate_methods

        result = generate_methods(mock_provider)
        assert isinstance(result, str)

    def test_describes_simulation_framework(self, mock_provider: MagicMock) -> None:
        """Methods should describe the simulation framework."""
        from src.sections.methods import generate_methods

        result = generate_methods(mock_provider)
        result_lower = result.lower()

        # Should mention simulation/framework concepts
        assert "simulation" in result_lower or "framework" in result_lower


# =============================================================================
# Phase 3.4: Results Section Tests (RED)
# =============================================================================


class TestResultsSection:
    """Test results section generator."""

    def test_generates_section_command(self, mock_provider: MagicMock) -> None:
        """Results should use LaTeX section command."""
        from src.sections.results import generate_results

        result = generate_results(mock_provider)

        assert r"\section{Results}" in result or r"\section{Experimental Results}" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_results must return str type."""
        from src.sections.results import generate_results

        result = generate_results(mock_provider)
        assert isinstance(result, str)

    def test_includes_experiment_subsections(self, mock_provider: MagicMock) -> None:
        """Results should have subsections for each experiment."""
        from src.sections.results import generate_results

        result = generate_results(mock_provider)

        # Should have subsections
        assert r"\subsection{" in result

    def test_uses_data_from_provider(self, mock_provider: MagicMock) -> None:
        """Results section must get data from provider, not hardcode."""
        from src.sections.results import generate_results

        generate_results(mock_provider)

        # Verify provider methods were called
        mock_provider.get_iteration_results.assert_called()

    def test_contains_formatted_values(self, mock_provider: MagicMock) -> None:
        """Results should contain properly formatted monetary values."""
        from src.sections.results import generate_results

        result = generate_results(mock_provider)

        # Should contain dollar signs (LaTeX escaped)
        assert r"\$" in result


# =============================================================================
# Phase 3.5: Discussion Section Tests (RED)
# =============================================================================


class TestDiscussionSection:
    """Test discussion section generator."""

    def test_generates_section_command(self, mock_provider: MagicMock) -> None:
        """Discussion should use LaTeX section command."""
        from src.sections.discussion import generate_discussion

        result = generate_discussion(mock_provider)

        assert r"\section{Discussion}" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_discussion must return str type."""
        from src.sections.discussion import generate_discussion

        result = generate_discussion(mock_provider)
        assert isinstance(result, str)

    def test_addresses_limitations(self, mock_provider: MagicMock) -> None:
        """Discussion should address limitations."""
        from src.sections.discussion import generate_discussion

        result = generate_discussion(mock_provider)
        result_lower = result.lower()

        assert "limitation" in result_lower


# =============================================================================
# Phase 3.6: Conclusion Section Tests (RED)
# =============================================================================


class TestConclusionSection:
    """Test conclusion section generator."""

    def test_generates_section_command(self, mock_provider: MagicMock) -> None:
        """Conclusion should use LaTeX section command."""
        from src.sections.conclusion import generate_conclusion

        result = generate_conclusion(mock_provider)

        assert r"\section{Conclusion}" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_conclusion must return str type."""
        from src.sections.conclusion import generate_conclusion

        result = generate_conclusion(mock_provider)
        assert isinstance(result, str)

    def test_mentions_future_work(self, mock_provider: MagicMock) -> None:
        """Conclusion should mention future work."""
        from src.sections.conclusion import generate_conclusion

        result = generate_conclusion(mock_provider)
        result_lower = result.lower()

        assert "future" in result_lower


# =============================================================================
# Phase 3.7: Appendices Section Tests (RED)
# =============================================================================


class TestAppendicesSection:
    """Test appendices section generator."""

    def test_generates_appendix_command(self, mock_provider: MagicMock) -> None:
        """Appendices should use LaTeX appendix command."""
        from src.sections.appendices import generate_appendices

        result = generate_appendices(mock_provider)

        # Should have appendix marker
        assert r"\appendix" in result or r"\section{Appendix" in result

    def test_returns_string(self, mock_provider: MagicMock) -> None:
        """generate_appendices must return str type."""
        from src.sections.appendices import generate_appendices

        result = generate_appendices(mock_provider)
        assert isinstance(result, str)

    def test_includes_detailed_tables(self, mock_provider: MagicMock) -> None:
        """Appendices should include detailed experiment tables."""
        from src.sections.appendices import generate_appendices

        result = generate_appendices(mock_provider)

        # Should have table environments
        assert r"\begin{table}" in result

    def test_uses_data_from_provider(self, mock_provider: MagicMock) -> None:
        """Appendices must get data from provider, not hardcode."""
        from src.sections.appendices import generate_appendices

        generate_appendices(mock_provider)

        # Verify provider methods were called
        mock_provider.get_iteration_results.assert_called()


# =============================================================================
# Phase 3.8: Integration Tests (RED)
# =============================================================================


class TestSectionIntegration:
    """Integration tests for section composition."""

    def test_all_sections_composable(self, mock_provider: MagicMock) -> None:
        """All sections should be composable into one document."""
        from src.sections.abstract import generate_abstract
        from src.sections.introduction import generate_introduction
        from src.sections.methods import generate_methods
        from src.sections.results import generate_results
        from src.sections.discussion import generate_discussion
        from src.sections.conclusion import generate_conclusion
        from src.sections.appendices import generate_appendices

        sections = [
            generate_abstract,
            generate_introduction,
            generate_methods,
            generate_results,
            generate_discussion,
            generate_conclusion,
            generate_appendices,
        ]

        # Should be able to join all sections
        full_content = "\n\n".join(section(mock_provider) for section in sections)

        assert isinstance(full_content, str)
        assert len(full_content) > 100  # Non-trivial content

    def test_sections_module_exports_all(self) -> None:
        """Sections module should export all section generators."""
        from src import sections

        assert hasattr(sections, "generate_abstract")
        assert hasattr(sections, "generate_introduction")
        assert hasattr(sections, "generate_methods")
        assert hasattr(sections, "generate_results")
        assert hasattr(sections, "generate_discussion")
        assert hasattr(sections, "generate_conclusion")
        assert hasattr(sections, "generate_appendices")


# =============================================================================
# Phase 3.9: Data-Driven Content Tests (RED)
# =============================================================================


class TestDataDrivenContent:
    """Test that sections use provider data, not hardcoded values."""

    def test_results_reflects_provider_data(self) -> None:
        """Results section should reflect provider data changes."""
        from src.sections.results import generate_results

        # Create two providers with different data
        provider1 = MagicMock()
        provider1.get_iteration_results.return_value = [
            {"iteration": 1, "agent_id": "BANK_A", "cost": 10000, "liquidity_fraction": 0.5, "accepted": True},
            {"iteration": 1, "agent_id": "BANK_B", "cost": 8000, "liquidity_fraction": 0.4, "accepted": True},
        ]
        provider1.get_final_bootstrap_stats.return_value = {}
        provider1.get_convergence_iteration.return_value = 1

        provider2 = MagicMock()
        provider2.get_iteration_results.return_value = [
            {"iteration": 1, "agent_id": "BANK_A", "cost": 50000, "liquidity_fraction": 0.9, "accepted": True},
            {"iteration": 1, "agent_id": "BANK_B", "cost": 45000, "liquidity_fraction": 0.85, "accepted": True},
        ]
        provider2.get_final_bootstrap_stats.return_value = {}
        provider2.get_convergence_iteration.return_value = 1

        result1 = generate_results(provider1)
        result2 = generate_results(provider2)

        # Results should be different (data-driven, not hardcoded)
        assert result1 != result2

    def test_appendices_reflects_provider_data(self) -> None:
        """Appendices should reflect provider data changes."""
        from src.sections.appendices import generate_appendices

        # Create two providers with different data
        provider1 = MagicMock()
        provider1.get_iteration_results.return_value = [
            {"iteration": 1, "agent_id": "BANK_A", "cost": 1000, "liquidity_fraction": 0.1, "accepted": True},
        ]
        provider1.get_final_bootstrap_stats.return_value = {
            "BANK_A": {"mean_cost": 1000, "std_dev": 100, "ci_lower": 800, "ci_upper": 1200, "num_samples": 10},
        }

        provider2 = MagicMock()
        provider2.get_iteration_results.return_value = [
            {"iteration": 1, "agent_id": "BANK_A", "cost": 99999, "liquidity_fraction": 0.99, "accepted": True},
        ]
        provider2.get_final_bootstrap_stats.return_value = {
            "BANK_A": {"mean_cost": 99999, "std_dev": 5000, "ci_lower": 90000, "ci_upper": 110000, "num_samples": 50},
        }

        result1 = generate_appendices(provider1)
        result2 = generate_appendices(provider2)

        # Results should be different (data-driven, not hardcoded)
        assert result1 != result2
