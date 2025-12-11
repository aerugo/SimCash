# Phase 7: Documentation

**Status:** In Progress
**Created:** 2025-12-10
**Duration Estimate:** 2-3 days

---

## Objectives

1. Create comprehensive CLI documentation for the new `experiment` command group
2. Document the new `payment_simulator.llm` module
3. Document the new `payment_simulator.experiments` module
4. Update existing documentation with corrected terminology (Monte Carlo → Bootstrap)
5. Add architecture documentation for the experiment framework

---

## Pre-work: Verify Test Coverage

Before writing docs, ensure all modules have adequate test coverage:

```bash
# LLM module tests
cd api && .venv/bin/python -m pytest tests/llm/ -v

# Experiments module tests
.venv/bin/python -m pytest tests/experiments/ -v

# CLI tests
.venv/bin/python -m pytest tests/cli/test_experiment_commands.py -v
```

---

## Phase 7.1: CLI Documentation

### Files to Create

| File | Purpose |
|------|---------|
| `docs/reference/cli/experiment.md` | Full documentation for `experiment` command group |

### Content Outline: `docs/reference/cli/experiment.md`

```markdown
# Experiment CLI Commands

The `payment-sim experiment` command group provides tools for running,
validating, and managing LLM policy optimization experiments.

## Commands Overview

| Command | Description |
|---------|-------------|
| `run` | Run an experiment from YAML configuration |
| `validate` | Validate an experiment configuration file |
| `list` | List experiments in a directory |
| `info` | Show detailed experiment information |
| `template` | Generate an experiment configuration template |

## Run Command

Run an experiment from a YAML configuration file.

### Usage

```bash
payment-sim experiment run <config.yaml> [OPTIONS]
```

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `--dry-run` | Validate config without running | `false` |
| `--seed INT` | Override master seed | from config |
| `--verbose/-v` | Enable verbose output | `false` |

### Examples

```bash
# Run with defaults
payment-sim experiment run experiments/exp1.yaml

# Dry run (validate only)
payment-sim experiment run experiments/exp1.yaml --dry-run

# Override seed
payment-sim experiment run experiments/exp1.yaml --seed 12345
```

## Validate Command

Validate an experiment YAML configuration file.

### Usage

```bash
payment-sim experiment validate <config.yaml>
```

### Examples

```bash
payment-sim experiment validate experiments/exp1.yaml
```

## List Command

List available experiments in a directory.

### Usage

```bash
payment-sim experiment list <directory>
```

### Examples

```bash
payment-sim experiment list experiments/castro/experiments/
```

## Info Command

Show detailed information about an experiment framework.

### Usage

```bash
payment-sim experiment info
```

## Template Command

Generate an experiment configuration template.

### Usage

```bash
payment-sim experiment template [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-o/--output PATH` | Write to file instead of stdout |

### Examples

```bash
# Print template to stdout
payment-sim experiment template

# Write to file
payment-sim experiment template -o my_experiment.yaml
```
```

### Files to Update

| File | Changes |
|------|---------|
| `docs/reference/cli/index.md` | Add link to experiment commands |

---

## Phase 7.2: LLM Module Documentation

### Files to Create

| File | Purpose |
|------|---------|
| `docs/reference/llm/index.md` | LLM module overview |
| `docs/reference/llm/configuration.md` | LLMConfig reference |
| `docs/reference/llm/protocols.md` | Protocol definitions |
| `docs/reference/llm/providers.md` | Provider-specific settings |

### Content Outline: `docs/reference/llm/index.md`

```markdown
# LLM Integration Module

The `payment_simulator.llm` module provides unified LLM abstraction for
all modules needing LLM capabilities.

## Quick Start

```python
from payment_simulator.llm import LLMConfig, PydanticAILLMClient

# Create configuration
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    temperature=0.0,
)

# Create client
client = PydanticAILLMClient(config)

# Generate structured output
result = await client.generate_structured_output(
    prompt="...",
    response_model=MyModel,
)
```

## Key Components

- **LLMConfig**: Unified configuration for all LLM providers
- **LLMClientProtocol**: Protocol for LLM client implementations
- **PydanticAILLMClient**: PydanticAI-based implementation
- **AuditCaptureLLMClient**: Wrapper for capturing interactions

## Supported Providers

- Anthropic (Claude models)
- OpenAI (GPT, O1, O3 models)
- Google (Gemini models)
```

### Content Outline: `docs/reference/llm/configuration.md`

```markdown
# LLM Configuration

## LLMConfig

Unified configuration for all LLM providers.

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | required | Model in provider:model format |
| `temperature` | `float` | `0.0` | Sampling temperature |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `timeout_seconds` | `int` | `120` | Request timeout |
| `thinking_budget` | `int \| None` | `None` | Anthropic extended thinking budget |
| `reasoning_effort` | `str \| None` | `None` | OpenAI reasoning effort (low/medium/high) |

### Model String Format

```
provider:model-name
```

Examples:
- `anthropic:claude-sonnet-4-5`
- `openai:gpt-4o`
- `openai:o1`
- `google:gemini-2.5-flash`

### Provider-Specific Options

#### Anthropic Extended Thinking

```python
config = LLMConfig(
    model="anthropic:claude-sonnet-4-5",
    thinking_budget=8000,  # tokens
)
```

#### OpenAI Reasoning Effort

```python
config = LLMConfig(
    model="openai:o1",
    reasoning_effort="high",  # low, medium, high
)
```
```

---

## Phase 7.3: Experiments Module Documentation

### Files to Create

| File | Purpose |
|------|---------|
| `docs/reference/experiments/index.md` | Experiments module overview |
| `docs/reference/experiments/configuration.md` | ExperimentConfig YAML reference |
| `docs/reference/experiments/runner.md` | Runner protocols and implementations |

### Content Outline: `docs/reference/experiments/index.md`

```markdown
# Experiment Framework

The `payment_simulator.experiments` module provides a YAML-driven framework
for running LLM policy optimization experiments.

## Key Features

- **YAML Configuration**: Define experiments in declarative YAML files
- **Bootstrap Evaluation**: Statistical policy comparison with paired samples
- **Deterministic Execution**: Same seed = same results
- **Multiple LLM Providers**: Support for Anthropic, OpenAI, Google

## Architecture

```
┌─────────────────────────────────────────────────┐
│  ExperimentConfig (YAML)                        │
│  ├── Scenario path                              │
│  ├── Evaluation settings                        │
│  ├── Convergence criteria                       │
│  ├── LLM configuration                          │
│  └── Output settings                            │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────┐
│  ExperimentRunner                               │
│  ├── Bootstrap evaluation                       │
│  ├── Paired policy comparison                   │
│  ├── LLM policy generation                      │
│  └── Result persistence                         │
└─────────────────────────────────────────────────┘
```

## Quick Start

1. Create experiment YAML (see configuration.md)
2. Run: `payment-sim experiment run my_experiment.yaml`
3. View results in output database
```

### Content Outline: `docs/reference/experiments/configuration.md`

```markdown
# Experiment Configuration

Experiments are configured via YAML files.

## Example Configuration

```yaml
name: my_experiment
description: "Description of the experiment"

scenario: configs/scenario.yaml

evaluation:
  mode: bootstrap  # or "deterministic"
  num_samples: 10
  ticks: 12

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0

optimized_agents:
  - BANK_A
  - BANK_B

constraints: module.path.CONSTRAINTS

output:
  directory: results
  database: experiments.db

master_seed: 42
```

## Configuration Reference

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Experiment identifier |
| `scenario` | path | Path to scenario YAML |
| `evaluation` | object | Evaluation settings |
| `convergence` | object | Convergence criteria |
| `llm` | object | LLM configuration |
| `optimized_agents` | list | Agent IDs to optimize |

### Evaluation Modes

#### Bootstrap Mode (Recommended)

```yaml
evaluation:
  mode: bootstrap
  num_samples: 10  # Number of bootstrap samples
  ticks: 12        # Ticks per evaluation
```

Uses paired comparison: same samples evaluated with both old and new policies.
Policy accepted when mean(delta) > 0 (new policy cheaper).

#### Deterministic Mode

```yaml
evaluation:
  mode: deterministic
  ticks: 2
```

Single evaluation with no sampling. Best for deterministic scenarios.
```

---

## Phase 7.4: Update Existing Documentation

### Files to Update

| File | Changes |
|------|---------|
| `docs/reference/cli/index.md` | Add experiment commands section |
| `CLAUDE.md` | Add new modules info, update terminology |
| All docs | Replace "Monte Carlo" with "Bootstrap" |

### Terminology Fixes

Search and replace in all documentation:

| Old Term | New Term |
|----------|----------|
| Monte Carlo | bootstrap |
| `--verbose-monte-carlo` | `--verbose-bootstrap` |
| MonteCarloContextBuilder | BootstrapContextBuilder |

---

## Verification Checklist

### Documentation Quality

- [ ] All code examples tested and working
- [ ] All CLI commands documented with examples
- [ ] All configuration options documented
- [ ] No "Monte Carlo" terminology in new docs
- [ ] Links between related docs working
- [ ] Consistent formatting across all docs

### Technical Accuracy

- [ ] All module imports verified
- [ ] All class/function names correct
- [ ] All field types accurate
- [ ] Default values match code

### Final Checks

```bash
# Verify no Monte Carlo references in new docs
grep -r "Monte Carlo" docs/reference/llm/ docs/reference/experiments/

# Verify CLI help matches docs
payment-sim experiment --help
payment-sim experiment run --help

# Verify imports match docs
python -c "from payment_simulator.llm import LLMConfig, PydanticAILLMClient"
python -c "from payment_simulator.experiments.config import ExperimentConfig"
```

---

## Notes

```
(Add notes as work progresses)
```
