# SimCash Paper v5 - Programmatic Generation

This directory contains a fully programmatic paper generation system that eliminates manual transcription errors by generating all tables, figures, and data-driven text directly from experiment databases.

## Quick Start

```bash
cd docs/papers/simcash-paper/v5

# Generate paper.tex
python -m src.cli --data-dir data/ --output-dir output/

# Or via Python API
python -c "
from pathlib import Path
from src.paper_builder import build_paper
build_paper(Path('data/'), Path('output/'))
"
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│               PaperBuilder                       │
│  build_paper() → generate_paper() → wrap_document()
└──────────────────────┬──────────────────────────┘
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌────────┐       ┌────────┐        ┌────────┐
│Abstract│       │Results │        │Appendix│
│  .py   │       │  .py   │        │  .py   │
└────┬───┘       └────┬───┘        └────┬───┘
     │                │                 │
     └────────────────┼─────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │    DataProvider     │
           │     (Protocol)      │
           └──────────┬──────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │  DatabaseDataProvider │
           │   (DuckDB queries)   │
           └──────────┬──────────┘
                      │
         ┌────────────┼────────────┐
         │            │            │
         ▼            ▼            ▼
      exp1.db      exp2.db      exp3.db
```

## Directory Structure

```
v5/
├── data/                    # Experiment databases (gitignored)
│   ├── exp1.db
│   ├── exp2.db
│   └── exp3.db
├── output/                  # Generated files (gitignored)
│   └── paper.tex
├── src/                     # Python source
│   ├── cli.py               # CLI entry point
│   ├── paper_builder.py     # Main composition logic
│   ├── data_provider.py     # DataProvider protocol + DB implementation
│   ├── sections/            # Section generators
│   │   ├── abstract.py
│   │   ├── introduction.py
│   │   ├── methods.py
│   │   ├── results.py
│   │   ├── discussion.py
│   │   ├── conclusion.py
│   │   └── appendices.py
│   ├── latex/               # LaTeX formatting
│   │   ├── formatting.py    # format_money, format_percent
│   │   ├── tables.py        # Table generators
│   │   └── figures.py       # Figure inclusion
│   └── charts/              # Chart path resolution
│       └── __init__.py
└── tests/                   # Test suite (118 tests)
    ├── test_data_provider.py
    ├── test_latex_formatting.py
    ├── test_sections.py
    ├── test_paper_builder.py
    ├── test_figures.py
    ├── test_real_data_integration.py
    └── test_cli.py
```

## Running Tests

```bash
cd docs/papers/simcash-paper/v5

# Run all tests
/home/user/SimCash/api/.venv/bin/python -m pytest tests/ -v

# Run specific test file
/home/user/SimCash/api/.venv/bin/python -m pytest tests/test_real_data_integration.py -v

# Run with coverage
/home/user/SimCash/api/.venv/bin/python -m pytest tests/ --cov=src
```

## Key Design Principles

### 1. Single Source of Truth
All data flows from experiment databases through `DataProvider`. No hardcoded values.

### 2. Protocol-Based Testing
`DataProvider` is a Protocol, enabling testing with mock data:

```python
from unittest.mock import MagicMock

mock_provider = MagicMock(spec=DataProvider)
mock_provider.get_iteration_results.return_value = [...]
result = generate_results(mock_provider)
```

### 3. Composition Over Inheritance
Sections are pure functions composed by `PaperBuilder`:

```python
sections = [generate_abstract, generate_introduction, generate_results]
content = "\n\n".join(section(provider) for section in sections)
```

### 4. Bug Prevention
The v4 paper had a critical bug where Exp2 showed identical costs for BANK_A and BANK_B. This is prevented by:

- **Test `test_exp2_agents_have_different_costs_in_database`**: Verifies database has different values
- **Test `test_exp2_different_costs_appear_in_paper`**: Verifies generated paper shows different values
- **Data-driven generation**: Values come from DB queries, not manual transcription

## Customization

### Generate Specific Sections Only

```python
from src.paper_builder import generate_paper
from src.sections import generate_abstract, generate_results

generate_paper(
    provider,
    output_dir,
    sections=[generate_abstract, generate_results],  # Only these
)
```

### Add a New Section

1. Create `src/sections/newsection.py`:
```python
def generate_newsection(provider: DataProvider) -> str:
    data = provider.get_some_data()
    return rf"\section{{New Section}} Content: {data}"
```

2. Add to `src/sections/__init__.py`
3. Add to `DEFAULT_SECTIONS` in `paper_builder.py`
4. Write tests in `tests/test_sections.py`

## Type Safety

Full type annotations throughout. Run mypy:

```bash
/home/user/SimCash/api/.venv/bin/python -m mypy src/ --ignore-missing-imports
```

## Dependencies

- Python 3.11+
- duckdb (for database queries)
- pytest (for testing)
- mypy, ruff (for linting)
