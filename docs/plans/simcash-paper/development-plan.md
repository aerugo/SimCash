# Programmatic Paper Generation System - Development Plan

**Status**: In Progress
**Created**: 2025-12-17
**Branch**: `claude/tree-experiments-charts-hxsAh`
**Output Directory**: `docs/papers/simcash-paper/v5/`

## Summary

Build a fully programmatic LaTeX paper generation system where every section, table, and chart is defined in Python code. This eliminates manual transcription errors (like the Exp2 cost table bug) and ensures reproducibility.

## Problem Statement

The v4 paper had critical errors:
- Appendix C showed duplicated cost values (`BANK_A Cost == BANK_B Cost`) when they should differ
- Manual transcription from database to markdown introduced inconsistencies
- No single source of truth—data existed in DB, charts, and text independently

**Solution**: Generate the entire paper programmatically from the database, ensuring data flows through a single pipeline.

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs extracted as integers, formatted at display time
- **INV-5**: Replay Identity - Use same data queries that replay uses for consistency

**NEW INV (Proposed)**: Paper Generation Identity
- Any value appearing in the paper (table, chart, or prose) MUST be computed from the same database query
- No hardcoded values in analysis text—all numbers must be variables from data

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        PaperBuilder                              │
│  Composes sections, generates final LaTeX document               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Section    │   │  Section    │   │  Section    │
│  Generator  │   │  Generator  │   │  Generator  │
│  (Abstract) │   │  (Results)  │   │  (Appendix) │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └────────────────┼─────────────────┘
                        │
                        ▼
              ┌─────────────────┐
              │  DataProvider   │
              │  (Protocol)     │
              └────────┬────────┘
                       │
         ┌─────────────┼─────────────┐
         │             │             │
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │ Database │  │   CLI    │  │  Config  │
   │ Queries  │  │  Tools   │  │  Files   │
   └──────────┘  └──────────┘  └──────────┘
```

## Key Design Decisions

1. **Raw LaTeX over pylatex**: Maximum control, easier debugging, no dependency
2. **Sections as functions**: Each section is a `Callable[[DataProvider], str]` returning LaTeX
3. **Composition via list**: Paper structure defined by ordering section functions
4. **Protocol-based data access**: `DataProvider` protocol enables testing with mock data
5. **Charts via CLI subprocess**: Reuse existing `payment-sim` chart generation
6. **Type-safe throughout**: Full type annotations, TypedDicts for query results

## File Structure

```
docs/papers/simcash-paper/v5/
├── data/                       # Experiment databases (copied)
│   ├── exp1.db
│   ├── exp2.db
│   └── exp3.db
├── configs/                    # Experiment configs (copied)
│   ├── exp1_2period.yaml
│   ├── exp2_12period.yaml
│   └── exp3_3period.yaml
├── output/                     # Generated outputs
│   ├── charts/                 # Generated chart PNGs
│   ├── paper.tex               # Generated LaTeX
│   └── paper.pdf               # Compiled PDF
├── src/                        # Python source
│   ├── __init__.py
│   ├── build_paper.py          # Main entry point
│   ├── data_provider.py        # DataProvider protocol + implementation
│   ├── sections/               # Section generators
│   │   ├── __init__.py
│   │   ├── abstract.py
│   │   ├── introduction.py
│   │   ├── methods.py
│   │   ├── results.py
│   │   ├── discussion.py
│   │   ├── conclusion.py
│   │   └── appendices.py
│   ├── components/             # Reusable LaTeX components
│   │   ├── __init__.py
│   │   ├── tables.py           # Table generators
│   │   └── figures.py          # Figure inclusion
│   ├── charts/                 # Chart generation
│   │   ├── __init__.py
│   │   └── generators.py       # Chart generation via CLI
│   └── latex/                  # LaTeX utilities
│       ├── __init__.py
│       ├── document.py         # Document structure
│       └── formatting.py       # Number/money formatting
└── tests/                      # Tests
    ├── test_data_provider.py
    ├── test_tables.py
    └── test_sections.py
```

## Phase Overview

| Phase | Description | TDD Focus | Deliverables |
|-------|-------------|-----------|--------------|
| 1 | Data Provider | Query accuracy | `data_provider.py`, tests |
| 2 | LaTeX Components | Table/figure correctness | `components/`, tests |
| 3 | Chart Generation | Chart reproduction | `charts/`, tests |
| 4 | Section Generators | Content structure | `sections/`, tests |
| 5 | Paper Builder | Full integration | `build_paper.py`, PDF |
| 6 | Reviewer Fixes | Address peer review | Updated content |

---

## Phase 1: Data Provider

**Goal**: Create typed, tested data access layer for experiment results.

### Deliverables
1. `DataProvider` protocol defining all required queries
2. `DatabaseDataProvider` implementation using DuckDB
3. TypedDicts for all return types
4. Unit tests verifying query accuracy

### Key Types

```python
from typing import Protocol, TypedDict

class AgentIterationResult(TypedDict):
    """Per-agent results for one iteration."""
    iteration: int
    agent_id: str
    cost: int  # cents
    liquidity_fraction: float
    accepted: bool

class BootstrapStats(TypedDict):
    """Bootstrap evaluation statistics."""
    mean_cost: int
    std_dev: int
    ci_lower: int
    ci_upper: int
    num_samples: int

class DataProvider(Protocol):
    """Protocol for accessing experiment data."""

    def get_iteration_results(
        self, exp_id: str, pass_num: int
    ) -> list[AgentIterationResult]:
        """Get per-agent costs for all iterations."""
        ...

    def get_final_bootstrap_stats(
        self, exp_id: str, pass_num: int
    ) -> dict[str, BootstrapStats]:
        """Get bootstrap statistics for final iteration, keyed by agent_id."""
        ...

    def get_convergence_iteration(self, exp_id: str, pass_num: int) -> int:
        """Get iteration number where convergence was detected."""
        ...
```

### Success Criteria
- [ ] All queries return correct data verified against manual DB inspection
- [ ] TypedDicts enforce structure at type-check time
- [ ] Tests cover all three experiments across all passes

---

## Phase 2: LaTeX Components

**Goal**: Create reusable table and figure generators.

### Deliverables
1. `format_money(cents: int) -> str` - Consistent money formatting
2. `format_percent(fraction: float) -> str` - Consistent percent formatting
3. `generate_results_table(data: list[...]) -> str` - Results table LaTeX
4. `generate_bootstrap_table(data: dict[...]) -> str` - Bootstrap stats table
5. `include_figure(path: str, caption: str, label: str) -> str` - Figure inclusion

### Key Functions

```python
def format_money(cents: int) -> str:
    """Format cents as dollars: 12345 -> '$123.45'"""
    return f"\\${cents / 100:.2f}"

def generate_iteration_table(
    results: list[AgentIterationResult],
    caption: str,
    label: str,
) -> str:
    """Generate LaTeX table for iteration-by-iteration results."""
    ...
```

### Success Criteria
- [ ] Tables match expected LaTeX structure
- [ ] All numbers formatted consistently
- [ ] Tests verify output for known inputs

---

## Phase 3: Chart Generation

**Goal**: Generate charts programmatically via CLI.

### Deliverables
1. `generate_convergence_chart(db_path, exp_id, output_dir)` - Per-experiment charts
2. `generate_bootstrap_charts(db_path, output_dir)` - Bootstrap visualization
3. Integration with existing `payment-sim` CLI

### Approach
- Use `subprocess` to call `payment-sim experiment` commands
- Capture chart paths for inclusion in LaTeX
- Handle errors gracefully with clear messages

### Success Criteria
- [ ] Charts generated match v4 charts visually
- [ ] All 27+ charts generated without manual intervention
- [ ] Bootstrap charts generated from database

---

## Phase 4: Section Generators

**Goal**: Implement all paper sections as composable functions.

### Section Functions

Each section follows the pattern:

```python
def generate_results_section(provider: DataProvider) -> str:
    """Generate Section 5: Results."""

    # Get data
    exp1_results = provider.get_iteration_results("exp1", pass_num=1)

    # Generate tables
    exp1_table = generate_iteration_table(exp1_results, ...)

    # Generate analysis text (with data-driven values)
    analysis = f"""
    All three passes converged to the theoretically-predicted asymmetric
    equilibrium where BANK_A achieves {format_money(exp1_results[-1]['cost'])}
    cost by free-riding on BANK_B's liquidity provision.
    """

    return f"""
\\section{{Results}}

\\subsection{{Experiment 1: Asymmetric Equilibrium}}

{exp1_table}

{analysis}
"""
```

### Deliverables
1. `abstract.py` - Abstract section
2. `introduction.py` - Introduction + contributions
3. `methods.py` - Framework description + algorithm box
4. `results.py` - All experiment results with tables/figures
5. `discussion.py` - Analysis and limitations
6. `conclusion.py` - Conclusion + future work
7. `appendices.py` - Detailed tables, prompt audit

### Success Criteria
- [ ] Each section generates valid LaTeX
- [ ] All data values come from DataProvider (no hardcoding)
- [ ] Sections can be reordered by changing composition order

---

## Phase 5: Paper Builder

**Goal**: Compose sections into complete document, compile to PDF.

### Deliverables
1. `build_paper.py` - Main entry point
2. LaTeX preamble with packages, formatting
3. Document structure (title, sections, bibliography)
4. PDF compilation via `pdflatex`

### Main Entry Point

```python
def build_paper(
    data_dir: Path,
    output_dir: Path,
    sections: list[SectionGenerator] | None = None,
) -> Path:
    """Build complete paper from databases.

    Args:
        data_dir: Directory containing exp{1,2,3}.db
        output_dir: Directory for output files
        sections: Optional custom section list (for testing)

    Returns:
        Path to generated PDF
    """
    provider = DatabaseDataProvider(data_dir)

    # Default sections if not provided
    if sections is None:
        sections = [
            generate_abstract,
            generate_introduction,
            generate_methods,
            generate_results,
            generate_discussion,
            generate_conclusion,
            generate_appendices,
        ]

    # Generate LaTeX
    content = "\n\n".join(section(provider) for section in sections)
    latex = wrap_document(content)

    # Write and compile
    tex_path = output_dir / "paper.tex"
    tex_path.write_text(latex)

    compile_latex(tex_path)

    return output_dir / "paper.pdf"
```

### Success Criteria
- [ ] Single command generates complete PDF
- [ ] Sections can be commented out for debugging
- [ ] Compilation errors reported clearly

---

## Phase 6: Reviewer Fixes

**Goal**: Address peer review issues in the programmatic framework.

### Issues to Fix
1. **Exp2 cost tables**: Now generated from DB, automatically correct
2. **Text/config mismatches**: Config values read programmatically
3. **Algorithm box**: Add to methods section
4. **Balance leakage**: Update Appendix D text

### Deliverables
1. Verified correct Exp2 tables
2. Config-driven scenario descriptions
3. Algorithm pseudocode in LaTeX
4. Updated audit conclusions

---

## Testing Strategy

### Unit Tests
- `test_data_provider.py`: Verify queries against known DB state
- `test_tables.py`: Verify table LaTeX output
- `test_formatting.py`: Verify money/percent formatting

### Integration Tests
- `test_sections.py`: Verify each section generates valid LaTeX
- `test_build.py`: Verify end-to-end PDF generation

### Invariant Tests
- `test_data_consistency.py`: Verify same value appears in table and prose
- `test_no_hardcoded_values.py`: Grep for hardcoded dollar amounts

---

## Documentation Updates

After implementation:
- [ ] Update `docs/papers/simcash-paper/README.md` with build instructions
- [ ] Add usage examples to section docstrings
- [ ] Document DataProvider query semantics

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Data Provider | Pending | |
| Phase 2: LaTeX Components | Pending | |
| Phase 3: Chart Generation | Pending | |
| Phase 4: Section Generators | Pending | |
| Phase 5: Paper Builder | Pending | |
| Phase 6: Reviewer Fixes | Pending | |

---

## CLI Interface

Final usage:

```bash
# Generate paper from databases
cd docs/papers/simcash-paper/v5
python -m src.build_paper --data-dir data/ --output-dir output/

# Generate specific sections only (for debugging)
python -m src.build_paper --sections results,appendices

# Regenerate charts only
python -m src.build_paper --charts-only
```

---

## Dependencies

```
# Add to pyproject.toml or requirements.txt
duckdb>=0.9.0      # Database queries
matplotlib>=3.8.0  # Chart generation (already present)
```

LaTeX dependencies (system):
```
pdflatex
bibtex (optional)
```
