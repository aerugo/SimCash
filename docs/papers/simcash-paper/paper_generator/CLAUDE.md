# Paper Generator - Style Guide & AI Agent Workflow

## Overview

This is the **SimCash paper generation system** - a programmatic LaTeX paper generator that produces academic research papers from experiment databases stored in DuckDB.

**Key Principle**: Data flows from databases through DataProvider → section generators → LaTeX output. Never hardcode values.

> **Essential Reading**: Before working on this codebase, read the root [`/CLAUDE.md`](/CLAUDE.md) for project-wide invariants (especially: integer cents for money, determinism).

---

## 🔴 CRITICAL: AI Agent Workflow Pattern

### The Read-Output-Edit-Source Pattern

When AI agents work on the paper, they face a fundamental challenge: the source code uses variables, functions, and data queries to generate values. Reading `src/sections/results.py` shows code like `format_money(stats['mean_cost'])`, not the actual dollar amounts.

**MANDATORY WORKFLOW:**

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: ALWAYS read output/paper.tex FIRST                    │
│  ─────────────────────────────────────────────────────────────  │
│  This file contains the COMPILED paper with actual values:     │
│    - Real dollar amounts ($164.40, not format_money(cost))     │
│    - Populated tables with data                                │
│    - Computed statistics and percentages                       │
│                                                                 │
│  This lets you UNDERSTAND what the paper currently says.       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: ALWAYS edit files in src/ to make changes             │
│  ─────────────────────────────────────────────────────────────  │
│  The source code generates the paper:                          │
│    - src/sections/*.py      → Section content                  │
│    - src/latex/tables.py    → Table generators                 │
│    - src/data_provider.py   → Data queries                     │
│    - src/charts/generators.py → Matplotlib charts              │
│                                                                 │
│  NEVER edit output/paper.tex directly - it gets overwritten!   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Regenerate and verify                                  │
│  ─────────────────────────────────────────────────────────────  │
│  cd docs/papers/simcash-paper/paper_generator                   │
│  ./generate_paper.sh                                            │
│                                                                 │
│  ALWAYS use generate_paper.sh - it ensures pdflatex is          │
│  installed and produces both paper.tex AND paper.pdf.           │
│                                                                 │
│  Then read output/paper.tex again to verify your changes.       │
└─────────────────────────────────────────────────────────────────┘
```

### Why This Matters

```python
# What you see in src/sections/results.py:
stats = provider.get_final_bootstrap_stats("exp1", pass_num=1)
content = f"The mean cost was {format_money(stats['mean_cost'])}..."

# What you see in output/paper.tex (after generation):
# "The mean cost was \$164.40..."
```

**Without reading output/paper.tex first**, you cannot know:
- What values the paper currently shows
- Whether a change is needed
- What the narrative flow looks like with real data

### Files to NEVER Edit

| File | Why |
|------|-----|
| `output/paper.tex` | Overwritten on every generation |
| `output/paper.pdf` | Generated from paper.tex |
| `output/charts/*.png` | Generated by chart generators |

### Files to ALWAYS Edit

| File | When |
|------|------|
| `src/sections/*.py` | Changing paper content or narrative |
| `src/latex/tables.py` | Modifying table structure or formatting |
| `src/latex/formatting.py` | Changing number/money formatting |
| `src/data_provider.py` | Adding new data queries |
| `src/charts/generators.py` | Modifying visualizations |

---

## Project Structure

```
paper_generator/
├── CLAUDE.md                ← You are here
├── config.yaml              # REQUIRED: Run_id mappings for reproducibility
├── configs/                 # Alternative experiment configs
├── data/                    # Experiment databases
│   ├── exp1.db
│   ├── exp2.db
│   └── exp3.db
├── output/                  # Generated output (READ ONLY for understanding)
│   ├── paper.tex            # ← READ THIS to understand the paper
│   ├── paper.pdf
│   └── charts/              # Generated PNG charts
├── src/                     # Source code (EDIT THIS to change paper)
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Config loader and validation
│   ├── paper_builder.py     # Main composition logic
│   ├── data_provider.py     # DataProvider protocol + DB implementation
│   ├── sections/            # Section generators
│   │   ├── abstract.py
│   │   ├── introduction.py
│   │   ├── related_work.py
│   │   ├── methods.py
│   │   ├── results.py       # Main results with tables and figures
│   │   ├── discussion.py
│   │   ├── conclusion.py
│   │   ├── references.py
│   │   └── appendices.py
│   ├── latex/               # LaTeX formatting
│   │   ├── formatting.py    # format_money, format_percent, escape_latex
│   │   ├── tables.py        # Table generators
│   │   └── figures.py       # Figure inclusion
│   └── charts/              # Chart generators
│       └── generators.py    # Matplotlib chart generation
├── tests/                   # Comprehensive test suite
│   ├── test_data_provider.py
│   ├── test_latex_formatting.py
│   ├── test_sections.py
│   ├── test_paper_builder.py
│   ├── test_chart_generators.py
│   ├── test_config.py
│   ├── test_cli.py
│   └── test_real_data_integration.py
└── pyrightconfig.json       # Type checking config
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI (cli.py)                           │
│  python -m src.cli --config config.yaml --output-dir output/│
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Paper Builder (paper_builder.py)            │
│  - Creates DataProvider                                     │
│  - Orchestrates section generators                          │
│  - Generates charts (optional)                              │
│  - Wraps in LaTeX document structure                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
│ DataProvider │ │   Sections   │ │ Chart Generators │
│  (Protocol)  │ │  (generate_*)│ │   (matplotlib)   │
└──────┬───────┘ └──────────────┘ └──────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│         DatabaseDataProvider (DuckDB)                │
│  - get_iteration_results(exp_id, pass_num)           │
│  - get_final_bootstrap_stats(exp_id, pass_num)       │
│  - get_convergence_iteration(exp_id, pass_num)       │
│  - get_pass_summary(exp_id, pass_num)                │
│  - get_all_pass_summaries(exp_id)                    │
│  - get_convergence_statistics(exp_id)                │
└──────────────────────────────────────────────────────┘
```

---

## Python Style Guide

### Type System Philosophy

This codebase uses **strict, complete typing**. Every function signature must be fully annotated.

**Core Rules:**
1. Every parameter has a type annotation
2. Every function has a return type (use `-> None` for void)
3. No partially unknown types (avoid `Any`)
4. All generic classes specify type arguments

### Use Native Python Types

Use Python 3.11+ built-in generics. Never import from `typing` for basic types.

```python
# Correct - native types
def process(items: list[str], lookup: dict[str, int]) -> list[int]:
    return [lookup[item] for item in items]

def find_experiment(exp_id: str) -> ExperimentConfig | None:
    return configs.get(exp_id)

# Wrong - legacy typing imports
from typing import List, Dict, Optional
def process(items: List[str]) -> List[int]: ...  # NO
```

### Use Union Syntax, Not Optional

```python
# Correct
def find(id: str) -> User | None:
    ...

# Wrong
from typing import Optional
def find(id: str) -> Optional[User]: ...  # NO
```

### TypedDict for Data Structures

All data structures from DataProvider use TypedDict:

```python
from typing import TypedDict

class AgentIterationResult(TypedDict):
    iteration: int
    agent_id: str
    cost: int              # ALWAYS cents (integer)
    liquidity_fraction: float
    accepted: bool

class BootstrapStats(TypedDict):
    mean_cost: int         # Cents
    std_dev: int           # Cents
    ci_lower: int          # Cents
    ci_upper: int          # Cents
    num_samples: int
```

### Use Protocols for Interfaces

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class DataProvider(Protocol):
    """Abstraction for accessing experiment data."""

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Return iteration results for an experiment pass."""
        ...

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Return final bootstrap statistics per agent."""
        ...
```

### Use Dataclasses for Value Objects

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ExperimentPass:
    """Configuration for a single experiment pass."""
    exp_id: str
    pass_num: int
    run_id: str


@dataclass
class PaperConfig:
    """Paper generation configuration."""
    experiments: dict[str, list[ExperimentPass]]
    output_filename: str = "paper.tex"
    charts_dir: str = "charts"
```

---

## 🔴 Critical Invariants

### 1. Money is ALWAYS Integer Cents

**CRITICAL INVARIANT**: All monetary values are `int` representing cents.

```python
# GOOD
cost: int = 16440  # $164.40
format_money(16440)  # Returns r"\$164.40"

# BAD - NEVER DO THIS
cost: float = 164.40  # NO FLOATS FOR MONEY!
```

This aligns with the project-wide invariant in `/CLAUDE.md`.

### 2. Data Access via DataProvider Protocol

**ALL data must flow through the DataProvider protocol**. Never query databases directly in section generators.

```python
# GOOD: Section uses provider
def generate_results(provider: DataProvider) -> str:
    results = provider.get_iteration_results("exp1", pass_num=1)
    return f"Experiment 1 converged in {len(results)} iterations..."

# BAD: Direct database access in section
def generate_results(data_dir: Path) -> str:
    conn = duckdb.connect(str(data_dir / "exp1.db"))  # NO!
    ...
```

**Why?** Testability (mock providers), consistency, single source of truth.

### 3. LaTeX Special Character Escaping

Use `escape_latex()` for any dynamic text that may contain special characters:

```python
from src.latex.formatting import escape_latex

# Agent IDs contain underscores
escape_latex("BANK_A")  # Returns r"BANK\_A"

# Other special characters
escape_latex("100%")    # Returns r"100\%"
escape_latex("A & B")   # Returns r"A \& B"
```

**Where to apply**: Agent IDs in tables, any user-provided text, filenames.

---

## Common Tasks

### Adding a New Section

1. **Create section file**: `src/sections/new_section.py`

```python
"""New section generator."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_new_section(provider: DataProvider) -> str:
    """Generate the new section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the section
    """
    # Fetch data via provider
    data = provider.get_some_data("exp1", pass_num=1)

    return r"""
\section{New Section Title}

Your LaTeX content here with data: {data}
""".format(data=data)
```

2. **Export in `__init__.py`**: Add to `src/sections/__init__.py`

3. **Add to paper builder** in `paper_builder.py`:

```python
DEFAULT_SECTIONS: list[SectionGenerator] = [
    generate_abstract,
    generate_introduction,
    # ...
    generate_new_section,  # Add here
    generate_conclusion,
]
```

4. **Write tests**: `tests/test_sections.py`

### Adding a New Data Query

1. **Add to Protocol** in `data_provider.py`:

```python
@runtime_checkable
class DataProvider(Protocol):
    # ... existing methods ...

    def get_new_metric(self, exp_id: str, pass_num: int) -> NewMetricType:
        """Get the new metric for analysis."""
        ...
```

2. **Implement in DatabaseDataProvider**:

```python
def get_new_metric(self, exp_id: str, pass_num: int) -> NewMetricType:
    """Get new metric from database."""
    run_id = self.get_run_id(exp_id, pass_num)
    conn = self._get_connection(exp_id)

    result = conn.execute(
        """SELECT column1, column2 FROM table WHERE run_id = ?""",
        [run_id],
    ).fetchall()

    return NewMetricType(field1=result[0][0], field2=result[0][1])
```

3. **Add TypedDict** for return type:

```python
class NewMetricType(TypedDict):
    field1: int
    field2: float
```

4. **Write tests** in `tests/test_data_provider.py`

### Adding a New Table Generator

```python
# In src/latex/tables.py

def generate_new_table(
    data: list[SomeType],
    caption: str,
    label: str,
) -> str:
    """Generate a new table.

    Args:
        data: List of data items
        caption: Table caption
        label: LaTeX label for referencing

    Returns:
        Complete LaTeX table string
    """
    rows = []
    for item in data:
        row = format_table_row([
            escape_latex(item["name"]),  # Escape special chars!
            format_money(item["cost"]),
            format_percent(item["rate"]),
        ])
        rows.append(row)

    return rf"""
\begin{{table}}[H]
\centering
\caption{{{caption}}}
\label{{{label}}}
\begin{{tabular}}{{lrr}}
\toprule
Name & Cost & Rate \\
\midrule
{chr(10).join(rows)}
\bottomrule
\end{{tabular}}
\end{{table}}
"""
```

### Adding a New Chart Type

```python
# In src/charts/generators.py

def generate_new_chart(
    db_path: Path,
    exp_id: str,
    pass_num: int,
    output_path: Path,
) -> Path:
    """Generate new chart type."""
    conn = duckdb.connect(str(db_path), read_only=True)
    # ... query data ...

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x_data, y_data, color=COLORS["bank_a"])
    ax.set_xlabel("X Label")
    ax.set_ylabel("Y Label")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    return output_path
```

Then include in section:

```python
from src.latex.figures import include_figure

figure = include_figure(
    path=f"charts/{exp_id}_pass{pass_num}_new.png",
    caption="New Chart Description",
    label=f"fig:{exp_id}_new",
    width=0.8,
)
```

---

## Debugging LaTeX Compilation Errors

**Common Issues:**

| Error | Cause | Fix |
|-------|-------|-----|
| "Missing $ inserted" | Unescaped underscore | Use `escape_latex()` for agent IDs |
| "Undefined control sequence" | Missing package | Check `wrap_document()` has needed `\usepackage` |
| "File not found" | Wrong chart path | Use flat naming: `charts/exp1_pass1_combined.png` |
| "Overfull hbox" | Content too wide | Use `\resizebox` or adjust column widths |

**Compilation Commands:**

```bash
cd docs/papers/simcash-paper/paper_generator/output
pdflatex -interaction=nonstopmode paper.tex  # First pass
pdflatex -interaction=nonstopmode paper.tex  # Resolve cross-refs
```

---

## Development Commands

This project uses [Astral UV](https://docs.astral.sh/uv/) for package management.

### Initial Setup

```bash
cd docs/papers/simcash-paper/paper_generator

# Install all dependencies (including payment-simulator from ../../../api)
uv sync --extra dev

# This creates a .venv/ with all dependencies installed
```

### After Code Changes

```bash
# After changing Python code in src/: No rebuild needed

# After changing payment-simulator (api/): Re-sync to pick up changes
uv sync --extra dev
```

### 🔴 MANDATORY: Running the Paper Generator

**ALWAYS use `generate_paper.sh` to generate the paper.** This script ensures:
1. LaTeX packages (pdflatex, texlive) are installed
2. The full paper generation runs including PDF compilation
3. Consistent output across environments

```bash
cd docs/papers/simcash-paper/paper_generator

# RECOMMENDED: Generate complete paper with PDF
./generate_paper.sh
```

**Why not run the Python CLI directly?** The `generate_paper.sh` script handles LaTeX dependency installation automatically. Running `python -m src.cli` directly may fail if pdflatex is not installed, or produce only a `.tex` file without the PDF.

### Alternative: CLI Options (Advanced)

If you need fine-grained control, you can use the Python CLI directly (but ensure pdflatex is installed first):

```bash
cd docs/papers/simcash-paper/paper_generator

# Generate paper (config.yaml is required)
uv run python -m src.cli --config config.yaml --output-dir output/

# Generate without charts (faster)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-charts

# Generate .tex only (no PDF compilation)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf
```

### Testing & Linting

```bash
cd docs/papers/simcash-paper/paper_generator

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_latex_formatting.py -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html

# Type checking with mypy
uv run mypy src/

# Type checking with pyright (matches VS Code Pylance)
uv run pyright src/

# Linting with ruff
uv run ruff check src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Alternative: Using the Activated Virtual Environment

If you prefer to activate the virtual environment:

```bash
cd docs/papers/simcash-paper/paper_generator
source .venv/bin/activate

# Then run commands directly
python -m src.cli --config config.yaml --output-dir output/
pytest tests/ -v
mypy src/
```

---

## Testing Strategy

### Test Hierarchy

```
tests/
├── test_data_provider.py        # DataProvider queries
├── test_latex_formatting.py     # Formatting helpers + tables
├── test_figures.py              # Figure includes
├── test_sections.py             # Section generators
├── test_paper_builder.py        # Full paper assembly
├── test_chart_generators.py     # Chart generation
├── test_config.py               # Config loading and validation
├── test_cli.py                  # CLI interface
└── test_real_data_integration.py # End-to-end with real data
```

### Mock DataProvider Pattern

Tests use mock providers to avoid database dependencies:

```python
@pytest.fixture
def mock_provider():
    """Create mock DataProvider for testing."""
    provider = Mock(spec=DataProvider)

    provider.get_iteration_results.return_value = [
        AgentIterationResult(
            iteration=1,
            agent_id="BANK_A",
            cost=16440,  # Cents!
            liquidity_fraction=0.35,
            accepted=True,
        ),
    ]

    return provider


def test_section_uses_provider(mock_provider):
    result = generate_results(mock_provider)
    mock_provider.get_iteration_results.assert_called_once()
```

---

## Quick Reference

### Key Functions

| Function | Purpose |
|----------|---------|
| `build_paper()` | Main entry point - generates entire paper |
| `generate_paper()` | Assemble sections into LaTeX |
| `wrap_document()` | Add LaTeX preamble and structure |
| `escape_latex()` | Escape special characters |
| `format_money()` | Format cents as `\$X.XX` |
| `format_percent()` | Format decimal as `XX.X\%` |
| `format_ci()` | Format confidence interval |
| `include_figure()` | Generate figure include |
| `generate_all_paper_charts()` | Generate all PNG charts |

### Chart Naming Convention

Charts use flat naming in `output/charts/`:
```
{exp_id}_pass{pass_num}_{type}.png

Examples:
exp1_pass1_combined.png      # Cost vs liquidity, both agents
exp1_pass1_bankA.png         # BANK_A convergence
exp2_pass1_ci_width.png      # Bootstrap CI width evolution
exp3_pass2_variance_evolution.png  # Variance over iterations
```

---

## Anti-Patterns to Avoid

### 1. Editing output/paper.tex Directly

```python
# BAD - Changes will be overwritten!
# Manually editing output/paper.tex

# GOOD - Edit the source
# Edit src/sections/results.py, then regenerate
```

### 2. Direct Database Access in Sections

```python
# BAD
def generate_results(data_dir: Path) -> str:
    conn = duckdb.connect(...)  # NO!

# GOOD
def generate_results(provider: DataProvider) -> str:
    data = provider.get_iteration_results(...)
```

### 3. Float Money

```python
# BAD
cost = 164.40  # Float dollars

# GOOD
cost = 16440  # Integer cents
```

### 4. Unescaped Text in LaTeX

```python
# BAD
row = f"{agent_id} & {cost}"  # BANK_A breaks LaTeX!

# GOOD
row = f"{escape_latex(agent_id)} & {format_money(cost)}"
```

### 5. Nested Chart Paths

```python
# BAD - LaTeX expects flat paths
output_path = output_dir / exp_id / f"pass{pass_num}" / "chart.png"

# GOOD - Flat naming
output_path = output_dir / f"{exp_id}_pass{pass_num}_chart.png"
```

### 6. Hardcoded Values in Sections

```python
# BAD
return "Experiment converged in 8 iterations..."

# GOOD
iterations = provider.get_convergence_iteration("exp1", 1)
return f"Experiment converged in {iterations} iterations..."
```

---

## Checklist Before Committing

### AI Agent Workflow
- [ ] Read `output/paper.tex` to understand current paper state
- [ ] Made edits only in `src/` directory
- [ ] Regenerated paper and verified changes in `output/paper.tex`

### Type Safety
- [ ] All functions have complete type annotations (params + return)
- [ ] No bare `list`, `dict` without type arguments
- [ ] No `Any` where a specific type is known
- [ ] Using `str | None` not `Optional[str]`
- [ ] Using `list[str]` not `List[str]`

### Verification
- [ ] Tests pass: `python -m pytest tests/`
- [ ] Type checking passes: `python -m mypy src/`
- [ ] Paper compiles: `python -m src.cli --config config.yaml --output-dir output/`
- [ ] All money values are `int` (cents, never floats)
- [ ] LaTeX special characters escaped with `escape_latex()`

---

## Proactive Agent Delegation

When working on paper generator tasks, consider delegating to specialized agents:

| Agent | Trigger When | File |
|-------|--------------|------|
| **paper-generator** | Main agent for this module | `.claude/agents/paper-generator.md` |
| **python-stylist** | Type annotations, modern Python patterns | `.claude/agents/python-stylist.md` |
| **test-engineer** | Writing pytest tests, test strategy | `.claude/agents/test-engineer.md` |

---

*Last updated: 2025-12-17*
*For project-wide invariants, see root `/CLAUDE.md`*
*For Python patterns, see `/api/CLAUDE.md`*
