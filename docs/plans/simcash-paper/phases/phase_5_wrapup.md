# Phase 5: Wrap-Up and Integration

**Goal**: Complete the programmatic paper generation system with chart integration, real data verification, and documentation.

**Approach**: TDD - Write failing tests first, then implement.

---

## Overview

The core system (DataProvider → Sections → PaperBuilder) is complete with 94 passing tests. This phase focuses on:

1. **Chart/Figure Integration** - Include existing charts in generated LaTeX
2. **Real Data Verification** - Verify generated content matches database
3. **CLI Entry Point** - Simple command-line interface
4. **Documentation** - Build instructions and usage

---

## Phase 5.1: Figure Inclusion (TDD)

### Tests First (RED)

```python
# tests/test_figures.py

class TestIncludeFigure:
    """Test figure inclusion helper."""

    def test_include_figure_basic(self) -> None:
        """Should generate LaTeX figure environment."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="charts/exp1_convergence.png",
            caption="Experiment 1 Convergence",
            label="fig:exp1_conv",
        )

        assert r"\begin{figure}" in result
        assert r"\end{figure}" in result
        assert r"\includegraphics" in result
        assert "charts/exp1_convergence.png" in result
        assert r"\caption{Experiment 1 Convergence}" in result
        assert r"\label{fig:exp1_conv}" in result

    def test_include_figure_with_width(self) -> None:
        """Should support width parameter."""
        from src.latex.figures import include_figure

        result = include_figure(
            path="chart.png",
            caption="Test",
            label="fig:test",
            width=0.8,
        )

        assert r"width=0.8\textwidth" in result
```

### Implementation (GREEN)

Create `src/latex/figures.py`:

```python
def include_figure(
    path: str,
    caption: str,
    label: str,
    width: float = 1.0,
    position: str = "htbp",
) -> str:
    """Generate LaTeX figure environment."""
    return rf"""
\begin{{figure}}[{position}]
    \centering
    \includegraphics[width={width}\textwidth]{{{path}}}
    \caption{{{caption}}}
    \label{{{label}}}
\end{{figure}}
"""
```

---

## Phase 5.2: Chart Path Resolution (TDD)

### Tests First (RED)

```python
# tests/test_charts.py

class TestChartPaths:
    """Test chart path resolution."""

    def test_get_convergence_chart_path(self) -> None:
        """Should return path to convergence chart."""
        from src.charts import get_convergence_chart_path

        path = get_convergence_chart_path("exp1", pass_num=1)
        assert "exp1" in str(path)
        assert "convergence" in str(path).lower()

    def test_get_bootstrap_chart_path(self) -> None:
        """Should return path to bootstrap chart."""
        from src.charts import get_bootstrap_chart_path

        path = get_bootstrap_chart_path("exp2", pass_num=1)
        assert "exp2" in str(path)
        assert "bootstrap" in str(path).lower()
```

### Implementation (GREEN)

Create `src/charts/__init__.py`:

```python
from pathlib import Path

CHARTS_DIR = Path(__file__).parent.parent.parent / "output" / "charts"

def get_convergence_chart_path(exp_id: str, pass_num: int) -> Path:
    """Get path to convergence chart for experiment."""
    return CHARTS_DIR / f"{exp_id}_pass{pass_num}_convergence.png"

def get_bootstrap_chart_path(exp_id: str, pass_num: int) -> Path:
    """Get path to bootstrap chart for experiment."""
    return CHARTS_DIR / f"{exp_id}_pass{pass_num}_bootstrap.png"
```

---

## Phase 5.3: Real Data Verification Tests (TDD)

### Tests First (RED)

These tests verify the generated paper content matches actual database values.

```python
# tests/test_real_data_integration.py

from pathlib import Path
import pytest

class TestRealDataIntegration:
    """Verify generated paper uses correct real data."""

    @pytest.fixture
    def provider(self):
        from src.data_provider import DatabaseDataProvider
        return DatabaseDataProvider(Path("data/"))

    @pytest.fixture
    def generated_paper(self, provider, tmp_path):
        from src.paper_builder import generate_paper
        return generate_paper(provider, tmp_path).read_text()

    def test_exp1_convergence_iteration_in_paper(self, provider, generated_paper):
        """Paper should contain correct exp1 convergence iteration."""
        convergence = provider.get_convergence_iteration("exp1", pass_num=1)
        assert str(convergence) in generated_paper

    def test_exp2_bootstrap_mean_in_paper(self, provider, generated_paper):
        """Paper should contain correct exp2 bootstrap means."""
        stats = provider.get_final_bootstrap_stats("exp2", pass_num=1)

        # Check BANK_A mean appears (formatted as dollars)
        bank_a_mean = stats["BANK_A"]["mean_cost"]
        dollars = bank_a_mean / 100
        # Should find the dollar value somewhere in the paper
        assert f"{dollars:.2f}" in generated_paper or f"{dollars:,.2f}" in generated_paper

    def test_exp2_agents_have_different_costs_in_appendix(self, provider, generated_paper):
        """CRITICAL: Exp2 appendix must show DIFFERENT costs for agents."""
        # This is the bug fix verification
        results = provider.get_iteration_results("exp2", pass_num=1)
        iter2 = [r for r in results if r["iteration"] == 2]

        if len(iter2) >= 2:
            costs = {r["agent_id"]: r["cost"] for r in iter2}
            bank_a_dollars = f"{costs['BANK_A']/100:.2f}"
            bank_b_dollars = f"{costs['BANK_B']/100:.2f}"

            # Both values should appear
            assert bank_a_dollars in generated_paper
            assert bank_b_dollars in generated_paper
            # And they should be different
            assert bank_a_dollars != bank_b_dollars
```

---

## Phase 5.4: CLI Entry Point (TDD)

### Tests First (RED)

```python
# tests/test_cli.py

import subprocess
from pathlib import Path

class TestCLI:
    """Test command-line interface."""

    def test_cli_generates_paper(self, tmp_path):
        """CLI should generate paper.tex."""
        result = subprocess.run(
            ["python", "-m", "src.cli",
             "--data-dir", "data/",
             "--output-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0
        assert (tmp_path / "paper.tex").exists()

    def test_cli_prints_output_path(self, tmp_path):
        """CLI should print path to generated file."""
        result = subprocess.run(
            ["python", "-m", "src.cli",
             "--data-dir", "data/",
             "--output-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert "paper.tex" in result.stdout
```

### Implementation (GREEN)

Create `src/cli.py`:

```python
"""CLI for paper generation."""

import argparse
from pathlib import Path

from src.paper_builder import build_paper


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SimCash paper")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args()

    tex_path = build_paper(args.data_dir, args.output_dir)
    print(f"Generated: {tex_path}")


if __name__ == "__main__":
    main()
```

---

## Phase 5.5: Documentation

### README for v5

Create `docs/papers/simcash-paper/v5/README.md`:

```markdown
# SimCash Paper v5 - Programmatic Generation

## Quick Start

```bash
cd docs/papers/simcash-paper/v5
python -m src.cli --data-dir data/ --output-dir output/
```

## Architecture

```
DataProvider (Protocol)
    ↓
Section Generators (7 functions)
    ↓
PaperBuilder (compose + wrap)
    ↓
paper.tex
```

## Running Tests

```bash
cd docs/papers/simcash-paper/v5
python -m pytest tests/ -v
```
```

---

## Implementation Order

| Step | Component | Tests | Est. LOC |
|------|-----------|-------|----------|
| 5.1 | Figure inclusion | 3 | ~30 |
| 5.2 | Chart paths | 3 | ~20 |
| 5.3 | Real data verification | 4 | ~50 |
| 5.4 | CLI entry point | 2 | ~25 |
| 5.5 | Documentation | - | ~50 |

**Total**: ~12 new tests, ~175 lines of code

---

## Success Criteria

- [ ] `include_figure()` generates valid LaTeX
- [ ] Chart paths resolve correctly
- [ ] Real data tests verify bug fix (Exp2 different costs)
- [ ] CLI generates paper from command line
- [ ] README documents usage
- [ ] All tests pass (target: ~106 total)

---

## Out of Scope (Deferred)

- PDF compilation (requires pdflatex)
- Chart regeneration via CLI subprocess
- Reviewer fixes (separate phase)
