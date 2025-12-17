"""Tests for paper builder - TDD RED phase.

These tests define the expected behavior of the paper builder module.
"""

from __future__ import annotations

from pathlib import Path
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
    provider = MagicMock(spec=[
        "get_iteration_results", "get_final_bootstrap_stats",
        "get_convergence_iteration", "get_run_id",
        "get_all_pass_summaries", "get_pass_summary",
        "get_convergence_statistics", "get_num_passes"
    ])

    provider.get_iteration_results.return_value = [
        {"iteration": 1, "agent_id": "BANK_A", "cost": 5000, "liquidity_fraction": 0.3, "accepted": True},
        {"iteration": 1, "agent_id": "BANK_B", "cost": 3000, "liquidity_fraction": 0.2, "accepted": True},
        {"iteration": 2, "agent_id": "BANK_A", "cost": 0, "liquidity_fraction": 0.0, "accepted": True},
        {"iteration": 2, "agent_id": "BANK_B", "cost": 5000, "liquidity_fraction": 0.33, "accepted": True},
    ]

    provider.get_final_bootstrap_stats.return_value = {
        "BANK_A": {"mean_cost": 16440, "std_dev": 500, "ci_lower": 15500, "ci_upper": 17400, "num_samples": 50},
        "BANK_B": {"mean_cost": 13349, "std_dev": 800, "ci_lower": 11800, "ci_upper": 14900, "num_samples": 50},
    }

    provider.get_convergence_iteration.return_value = 2
    provider.get_run_id.return_value = "exp1-20251215-abc123"

    # Mock pass summaries
    provider.get_all_pass_summaries.return_value = [
        {"pass_num": 1, "iterations": 2, "bank_a_liquidity": 0.0, "bank_b_liquidity": 0.33,
         "bank_a_cost": 0, "bank_b_cost": 5000, "total_cost": 5000},
        {"pass_num": 2, "iterations": 3, "bank_a_liquidity": 0.05, "bank_b_liquidity": 0.30,
         "bank_a_cost": 100, "bank_b_cost": 4500, "total_cost": 4600},
        {"pass_num": 3, "iterations": 2, "bank_a_liquidity": 0.02, "bank_b_liquidity": 0.35,
         "bank_a_cost": 50, "bank_b_cost": 5200, "total_cost": 5250},
    ]

    provider.get_pass_summary.return_value = {
        "pass_num": 1, "iterations": 2, "bank_a_liquidity": 0.0, "bank_b_liquidity": 0.33,
        "bank_a_cost": 0, "bank_b_cost": 5000, "total_cost": 5000
    }

    # Mock convergence statistics
    provider.get_convergence_statistics.return_value = {
        "exp_id": "exp1", "mean_iterations": 2.3, "min_iterations": 2,
        "max_iterations": 3, "convergence_rate": 1.0
    }

    provider.get_num_passes.return_value = 3

    return provider


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    """Create temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


# =============================================================================
# Phase 4.1: Document Structure Tests (RED)
# =============================================================================


class TestDocumentStructure:
    """Test LaTeX document structure generation."""

    def test_wrap_document_creates_complete_document(self) -> None:
        """wrap_document should create complete LaTeX document."""
        from src.paper_builder import wrap_document

        content = r"\section{Test} Some content."
        result = wrap_document(content)

        assert r"\documentclass" in result
        assert r"\begin{document}" in result
        assert r"\end{document}" in result
        assert r"\section{Test} Some content." in result

    def test_wrap_document_includes_required_packages(self) -> None:
        """Document should include common LaTeX packages."""
        from src.paper_builder import wrap_document

        result = wrap_document("test")

        # Should include common packages
        assert r"\usepackage" in result

    def test_wrap_document_includes_title_and_author(self) -> None:
        """Document should include title and author."""
        from src.paper_builder import wrap_document

        result = wrap_document("test", title="Test Paper", author="Test Author")

        assert r"\title{Test Paper}" in result
        assert r"\author{Test Author}" in result
        assert r"\maketitle" in result

    def test_wrap_document_returns_string(self) -> None:
        """wrap_document must return str type."""
        from src.paper_builder import wrap_document

        result = wrap_document("test")
        assert isinstance(result, str)


# =============================================================================
# Phase 4.2: Paper Generation Tests (RED)
# =============================================================================


class TestGeneratePaper:
    """Test paper generation function."""

    def test_generate_paper_creates_tex_file(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """generate_paper should create .tex file."""
        from src.paper_builder import generate_paper

        tex_path = generate_paper(mock_provider, tmp_output_dir)

        assert tex_path.exists()
        assert tex_path.suffix == ".tex"

    def test_generate_paper_returns_path(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """generate_paper should return Path to tex file."""
        from src.paper_builder import generate_paper

        result = generate_paper(mock_provider, tmp_output_dir)

        assert isinstance(result, Path)

    def test_generate_paper_includes_all_sections(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """Generated paper should include all standard sections."""
        from src.paper_builder import generate_paper

        tex_path = generate_paper(mock_provider, tmp_output_dir)
        content = tex_path.read_text()

        # Check for main sections
        assert r"\begin{abstract}" in content
        assert r"\section{Introduction}" in content
        assert r"\section{Results}" in content or r"\section{Experimental Results}" in content
        assert r"\section{Discussion}" in content
        assert r"\section{Conclusion}" in content
        assert r"\appendix" in content

    def test_generate_paper_is_valid_latex(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """Generated paper should be structurally valid LaTeX."""
        from src.paper_builder import generate_paper

        tex_path = generate_paper(mock_provider, tmp_output_dir)
        content = tex_path.read_text()

        # Basic structural checks
        assert content.count(r"\begin{document}") == 1
        assert content.count(r"\end{document}") == 1
        assert content.index(r"\begin{document}") < content.index(r"\end{document}")

    def test_generate_paper_uses_provider_data(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """Generated paper should use data from provider."""
        from src.paper_builder import generate_paper

        generate_paper(mock_provider, tmp_output_dir)

        # Verify provider was called
        mock_provider.get_iteration_results.assert_called()
        mock_provider.get_convergence_iteration.assert_called()


# =============================================================================
# Phase 4.3: Section Selection Tests (RED)
# =============================================================================


class TestSectionSelection:
    """Test custom section selection."""

    def test_generate_paper_with_custom_sections(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """generate_paper should accept custom section list."""
        from src.paper_builder import generate_paper
        from src.sections import generate_abstract, generate_conclusion

        tex_path = generate_paper(
            mock_provider,
            tmp_output_dir,
            sections=[generate_abstract, generate_conclusion],
        )

        content = tex_path.read_text()

        # Should have abstract and conclusion
        assert r"\begin{abstract}" in content
        assert r"\section{Conclusion}" in content

        # Should NOT have other sections
        assert r"\section{Introduction}" not in content
        assert r"\section{Discussion}" not in content

    def test_generate_paper_with_single_section(
        self, mock_provider: MagicMock, tmp_output_dir: Path
    ) -> None:
        """generate_paper should work with single section."""
        from src.paper_builder import generate_paper
        from src.sections import generate_abstract

        tex_path = generate_paper(
            mock_provider,
            tmp_output_dir,
            sections=[generate_abstract],
        )

        content = tex_path.read_text()
        assert r"\begin{abstract}" in content


# =============================================================================
# Phase 4.4: Build Paper Entry Point Tests (RED)
# =============================================================================


class TestBuildPaper:
    """Test build_paper main entry point."""

    def test_build_paper_from_data_dir(self, tmp_output_dir: Path) -> None:
        """build_paper should create paper from data directory."""
        from src.paper_builder import build_paper

        # Use actual data directory
        data_dir = Path("data")

        # Skip if data doesn't exist
        if not data_dir.exists():
            pytest.skip("Data directory not available")

        tex_path = build_paper(data_dir, tmp_output_dir)

        assert tex_path.exists()
        assert tex_path.suffix == ".tex"

    def test_build_paper_creates_output_dir_if_needed(self, tmp_path: Path) -> None:
        """build_paper should create output directory if it doesn't exist."""
        from src.paper_builder import build_paper

        data_dir = Path("data")
        output_dir = tmp_path / "new_output"

        if not data_dir.exists():
            pytest.skip("Data directory not available")

        tex_path = build_paper(data_dir, output_dir)

        assert output_dir.exists()
        assert tex_path.exists()


# =============================================================================
# Phase 4.5: Module Interface Tests (RED)
# =============================================================================


class TestModuleInterface:
    """Test paper_builder module public interface."""

    def test_module_exports_wrap_document(self) -> None:
        """Module should export wrap_document."""
        from src import paper_builder

        assert hasattr(paper_builder, "wrap_document")

    def test_module_exports_generate_paper(self) -> None:
        """Module should export generate_paper."""
        from src import paper_builder

        assert hasattr(paper_builder, "generate_paper")

    def test_module_exports_build_paper(self) -> None:
        """Module should export build_paper."""
        from src import paper_builder

        assert hasattr(paper_builder, "build_paper")

    def test_section_generator_type_alias(self) -> None:
        """Module should export SectionGenerator type."""
        from src.paper_builder import SectionGenerator

        # Should be a callable type
        assert SectionGenerator is not None
