# SimCash Paper - Programmatic Generation

This directory contains a fully programmatic paper generation system that eliminates manual transcription errors by generating all tables, figures, and data-driven text directly from experiment databases.

## Quick Start

This project uses [Astral UV](https://docs.astral.sh/uv/) for package management.

### Initial Setup

```bash
# 1. Set up Git LFS (required for database files)
brew install git-lfs
git lfs install
git clone <repo>
# If repo already cloned, pull LFS files:
git lfs pull

# 2. Navigate to paper generator
cd docs/papers/simcash-paper/paper_generator

# 3. Install all dependencies (including payment-simulator from ../../../../api)
uv sync --extra dev
```

### Run Missing Experiments

The `run_missing_experiments.py` script automatically runs any experiments that have empty `run_id` values in `config.yaml`:

```bash
cd docs/papers/simcash-paper/paper_generator

# Run all missing experiments (using uv environment)
uv run python run_missing_experiments.py config.yaml

# Preview what would run (dry run)
uv run python run_missing_experiments.py config.yaml --dry-run

# Or if you have the venv activated:
python run_missing_experiments.py config.yaml
```

> **Note**: The script requires the `payment-simulator` package from `api/`. Make sure you've run `uv sync --extra dev` first to install all dependencies.

**Key features:**
- **Parallel execution**: Different experiments (exp1, exp2, exp3) run in parallel
- **Sequential passes**: Passes for the same experiment run sequentially (to avoid database locks)
- **Auto-update config**: Updates `config.yaml` with run_ids as experiments complete
- **Live output**: All experiment output streams to terminal with prefixes like `[exp1:P3]`

**Example workflow:**
```bash
# 1. Set empty run_ids in config.yaml for experiments you want to (re-)run
# 2. Run missing experiments
uv run python run_missing_experiments.py config.yaml

# 3. Generate the paper
./generate_paper.sh
```

### Generate the Paper

**A `config.yaml` file is REQUIRED** for paper generation. The config explicitly maps experiment passes to specific run_ids, ensuring reproducible paper generation and preventing issues with database ordering or incomplete experiment runs.

```bash
cd docs/papers/simcash-paper/paper_generator

# Generate paper.tex and compile to PDF
uv run python -m src.cli --config config.yaml --output-dir output/

# Or skip PDF compilation (faster, .tex only)
uv run python -m src.cli --config config.yaml --output-dir output/ --skip-pdf

# Or via Python API
uv run python -c "
from pathlib import Path
from src.config import load_config
from src.paper_builder import build_paper
config = load_config(Path('config.yaml'))
build_paper(Path('data/'), Path('output/'), config=config)
"
```

## Config File

The `config.yaml` file specifies:
- Database paths for each experiment
- Explicit run_id mappings for each experiment pass
- Output configuration

Example:
```yaml
databases:
  exp1: data/exp1.db
  exp2: data/exp2.db
  exp3: data/exp3.db

experiments:
  exp1:
    name: "2-Period Deterministic Nash Equilibrium"
    passes:
      1: "exp1-20251216-233551-55f475"
      2: "exp1-20251217-004551-624d09"
      3: "exp1-20251217-011413-2cd7d6"
  # ... etc

output:
  paper_filename: paper.tex
  charts_dir: charts
```

### Validation

Before paper generation, the system validates that:
1. All run_ids in the config exist in the database
2. All referenced experiment runs have completed (have a `completed_at` timestamp)

If validation fails, you'll see a clear error message listing which runs are incomplete or missing.

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
├── config.yaml              # REQUIRED: Run_id mappings for reproducibility
├── data/                    # Experiment databases
│   ├── exp1.db
│   ├── exp2.db
│   └── exp3.db
├── output/                  # Generated files
│   ├── paper.tex
│   ├── paper.pdf
│   └── charts/              # Generated charts
├── src/                     # Python source
│   ├── cli.py               # CLI entry point
│   ├── config.py            # Config loader and validation
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
│   └── charts/              # Chart generators
│       └── generators.py
└── tests/                   # Test suite
    ├── test_data_provider.py
    ├── test_latex_formatting.py
    ├── test_sections.py
    ├── test_paper_builder.py
    ├── test_figures.py
    ├── test_real_data_integration.py
    ├── test_config.py
    └── test_cli.py
```

## Running Tests

```bash
cd docs/papers/simcash-paper/paper_generator

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_real_data_integration.py -v

# Run with coverage
uv run pytest tests/ --cov=src --cov-report=html
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

Full type annotations throughout. Run type checking:

```bash
cd docs/papers/simcash-paper/paper_generator

# Type checking with mypy
uv run mypy src/

# Type checking with pyright (matches VS Code Pylance)
uv run pyright src/

# Linting with ruff
uv run ruff check src/ tests/
```

## Dependencies

- Python 3.11+
- [Astral UV](https://docs.astral.sh/uv/) for package management
- duckdb (database queries)
- matplotlib (chart generation)
- pyyaml (config parsing)
- payment-simulator (from ../../../../api, for experiment analysis)

Dev dependencies:
- pytest, pytest-cov (testing)
- mypy, pyright (type checking)
- ruff (linting and formatting)
