# Phase 19: Documentation Overhaul for Production Release

**Status:** PLANNED
**Created:** 2025-12-11
**Estimated Duration:** 2-3 days
**Risk:** Low (documentation only, no code changes)
**Breaking Changes:** None

---

## Overview

Phase 19 systematically updates all documentation to reflect the completed refactor (Phases 0-18). The goal is **authoritative, production-ready documentation** for SimCash and its simulation/experiment running capabilities.

### Key Changes to Document

1. **YAML-Only Experiments**: Castro is now YAML config only, no Python code
2. **Generic Experiment Framework**: `payment_simulator.experiments` handles all experiments
3. **Core CLI**: `payment-sim experiment` commands work with any experiment YAML
4. **LLM Module**: Unified LLM abstraction with inline system_prompt support
5. **Terminology**: Bootstrap (not Monte Carlo) for sampling methods
6. **Architecture**: Simplified architecture with Castro as pure config

---

## Documentation Inventory

### Critical Updates Required (OUTDATED)

| Document | Issue | Priority |
|----------|-------|----------|
| `docs/reference/castro/index.md` | References deleted Python code (`castro/runner.py`, `cli.py`) | **P0** |
| `docs/reference/castro/cli-commands.md` | Documents `castro run` which no longer exists | **P0** |
| `docs/reference/castro/state-provider.md` | References Castro Python module | **P0** |
| `docs/reference/castro/events.md` | May reference deleted code | **P0** |
| `README.md` | Missing experiments framework, outdated test counts | **P1** |
| `docs/reference/experiments/index.md` | Needs update for YAML-only, GenericExperimentRunner | **P1** |
| `docs/reference/cli/commands/experiment.md` | Needs complete update for new commands | **P1** |

### Moderate Updates Required

| Document | Issue | Priority |
|----------|-------|----------|
| `docs/reference/llm/configuration.md` | Add `system_prompt` field documentation | **P2** |
| `docs/reference/experiments/configuration.md` | Add `policy_constraints` inline docs | **P2** |
| `docs/reference/experiments/runner.md` | Add GenericExperimentRunner docs | **P2** |
| `docs/reference/ai_cash_mgmt/configuration.md` | Verify BootstrapConfig terminology | **P2** |
| `docs/reference/patterns-and-conventions.md` | Add experiment framework patterns | **P2** |

### Review Required (May Be OK)

| Document | Check For | Priority |
|----------|-----------|----------|
| `docs/reference/architecture/*.md` | Any Castro references | **P3** |
| `docs/reference/cli/index.md` | Command structure accuracy | **P3** |
| `docs/reference/llm/index.md` | Accuracy check | **P3** |
| `docs/reference/llm/protocols.md` | Accuracy check | **P3** |
| `docs/reference/ai_cash_mgmt/index.md` | Monte Carlo → Bootstrap | **P3** |
| `docs/reference/ai_cash_mgmt/sampling.md` | Terminology check | **P3** |
| `docs/reference/orchestrator/*.md` | General accuracy | **P3** |
| `docs/reference/policy/*.md` | General accuracy | **P3** |
| `docs/reference/scenario/*.md` | General accuracy | **P3** |

---

## Task Breakdown

### Task 19.1: Update Castro Documentation (P0 - CRITICAL)

The Castro documentation is **severely outdated** - it references Python code that no longer exists.

**Current State (WRONG)**:
```
experiments/castro/
├── castro/
│   ├── run_id.py           # DELETED
│   ├── events.py           # DELETED
│   ├── state_provider.py   # DELETED
│   ├── display.py          # DELETED
│   ├── runner.py           # DELETED
│   └── ...
├── cli.py                  # DELETED
└── tests/                  # DELETED
```

**Actual State (CORRECT)**:
```
experiments/castro/
├── experiments/            # YAML experiment configs
│   ├── exp1.yaml
│   ├── exp2.yaml
│   └── exp3.yaml
├── configs/               # YAML scenario configs
├── papers/                # Research papers
├── README.md              # Documentation
└── pyproject.toml         # Minimal metadata
```

#### Files to Update:

**`docs/reference/castro/index.md`** - Complete rewrite:
- Remove all Python code references
- Document YAML-only structure
- Update CLI commands to `payment-sim experiment`
- Update architecture diagram
- Reference core experiment framework

**`docs/reference/castro/cli-commands.md`** - Complete rewrite or DELETE:
- Option A: Delete entirely (commands are now in core CLI)
- Option B: Redirect to `docs/reference/cli/commands/experiment.md`

**`docs/reference/castro/state-provider.md`** - DELETE or REDIRECT:
- StateProvider is now in core `experiments/runner/`
- Redirect to core documentation

**`docs/reference/castro/events.md`** - DELETE or REDIRECT:
- Events are now in core experiment framework
- Redirect to `docs/reference/experiments/` documentation

#### Verification:
```bash
# Check for references to deleted files
grep -r "castro/runner.py" docs/
grep -r "castro/cli.py" docs/
grep -r "castro run" docs/
grep -r "uv run castro" docs/
```

---

### Task 19.2: Update Root README.md (P1)

**Changes needed**:

1. **Add Experiments Section**:
```markdown
## Running Experiments

SimCash includes a YAML-driven experiment framework for LLM-based policy optimization:

```bash
# List available experiments
payment-sim experiment list experiments/castro/experiments/

# Validate experiment configuration
payment-sim experiment validate experiments/castro/experiments/exp1.yaml

# Run an experiment (requires LLM API key)
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# Dry-run (validate without LLM calls)
payment-sim experiment run experiments/castro/experiments/exp1.yaml --dry-run
```

See [Experiment Framework](docs/reference/experiments/index.md) for details.
```

2. **Update Test Counts**:
- Current: "280+ passing"
- Should reflect actual count (~500+)

3. **Update Architecture Diagram**:
- Add experiments layer to diagram

4. **Add Reference to Experiments/LLM docs**:
```markdown
| **Experiments** | [docs/reference/experiments/](docs/reference/experiments/index.md) — YAML experiment framework |
| **LLM** | [docs/reference/llm/](docs/reference/llm/index.md) — LLM integration |
```

---

### Task 19.3: Update Experiments Documentation (P1)

**`docs/reference/experiments/index.md`**:

1. **Update for YAML-only**:
   - Emphasize YAML-only experiment definition
   - Remove any references to Python experiment code
   - Document inline `system_prompt` and `policy_constraints`

2. **Update Architecture Diagram**:
   - Show GenericExperimentRunner
   - Show YAML → Runner → Result flow

3. **Update Quick Start**:
   - Use `payment-sim experiment` commands
   - Remove any `castro` CLI references

4. **Update Module Structure**:
```markdown
payment_simulator/experiments/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── experiment_config.py    # ExperimentConfig with inline prompts/constraints
├── runner/
│   ├── __init__.py
│   ├── protocol.py             # ExperimentRunnerProtocol
│   ├── result.py               # ExperimentResult, IterationRecord
│   ├── output.py               # OutputHandlerProtocol
│   ├── experiment_runner.py    # GenericExperimentRunner
│   ├── llm_client.py           # ExperimentLLMClient
│   ├── optimization.py         # OptimizationLoop
│   └── verbose.py              # VerboseConfig, VerboseLogger
├── cli/
│   └── commands.py             # CLI commands (run, list, validate, info)
└── persistence/
    └── repository.py           # ExperimentRepository
```

5. **Remove Castro Integration Section**:
   - Castro is now YAML-only, no special integration needed
   - Replace with "Creating Custom Experiments" section

**`docs/reference/experiments/configuration.md`**:
- Add `system_prompt` field documentation
- Add `policy_constraints` inline documentation
- Add `system_prompt_file` for external prompts
- Show complete YAML example with inline prompt

**`docs/reference/experiments/runner.md`**:
- Document GenericExperimentRunner
- Document ExperimentLLMClient
- Document OptimizationLoop
- Update class diagrams

---

### Task 19.4: Update CLI Documentation (P1)

**`docs/reference/cli/commands/experiment.md`**:

Complete update for new commands:

```markdown
# Experiment Commands

> Run and manage LLM policy optimization experiments

## Commands

| Command | Description |
|---------|-------------|
| `payment-sim experiment run` | Run experiment from YAML |
| `payment-sim experiment validate` | Validate experiment configuration |
| `payment-sim experiment list` | List experiments in directory |
| `payment-sim experiment info` | Show CLI/framework information |

## Run Command

```bash
payment-sim experiment run <config-path> [OPTIONS]
```

### Options

| Option | Type | Description |
|--------|------|-------------|
| `--dry-run` | flag | Validate without executing |
| `--seed` | int | Override master seed |
| `--db` | path | Database path for persistence |
| `--verbose` | flag | Enable all verbose output |
| `--verbose-iterations` | flag | Show iteration progress |
| `--verbose-bootstrap` | flag | Show bootstrap evaluation details |
| `--verbose-llm` | flag | Show LLM interactions |
| `--verbose-policy` | flag | Show policy changes |

### Examples

```bash
# Basic run
payment-sim experiment run experiments/castro/experiments/exp1.yaml

# Dry run (validate only)
payment-sim experiment run experiments/castro/experiments/exp1.yaml --dry-run

# With verbose output
payment-sim experiment run experiments/castro/experiments/exp1.yaml --verbose

# Override seed
payment-sim experiment run experiments/castro/experiments/exp1.yaml --seed 12345

# Persist to database
payment-sim experiment run experiments/castro/experiments/exp1.yaml --db results/exp1.db
```

## Validate Command

```bash
payment-sim experiment validate <config-path>
```

Validates experiment YAML configuration without running.

## List Command

```bash
payment-sim experiment list <directory>
```

Lists all valid experiment YAML files in a directory.

## Info Command

```bash
payment-sim experiment info
```

Shows experiment framework information and capabilities.
```

**`docs/reference/cli/index.md`**:
- Update command tree structure
- Verify experiment commands are listed correctly

---

### Task 19.5: Update LLM Documentation (P2)

**`docs/reference/llm/configuration.md`**:

Add `system_prompt` field:

```markdown
### system_prompt

Optional system prompt for LLM interactions:

```yaml
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies for the SimCash payment simulator.
    ...
```

**Priority**: Inline `system_prompt` in YAML takes precedence over default prompts.

**Use Cases**:
- Experiment-specific prompts (e.g., Castro has specific policy structure)
- Custom optimization objectives
- Domain-specific instructions
```

---

### Task 19.6: Update AI Cash Management Documentation (P2)

**`docs/reference/ai_cash_mgmt/configuration.md`**:
- Verify `BootstrapConfig` is documented (not MonteCarloConfig)
- Update any Monte Carlo terminology to Bootstrap

**`docs/reference/ai_cash_mgmt/sampling.md`**:
- Verify Bootstrap terminology
- Update any "Monte Carlo" references

**`docs/reference/ai_cash_mgmt/index.md`**:
- Review for Monte Carlo → Bootstrap terminology
- Verify architecture diagrams are accurate

---

### Task 19.7: Update Patterns and Conventions (P2)

**`docs/reference/patterns-and-conventions.md`**:

Add new patterns:

```markdown
## Experiment Framework Patterns

### YAML-Only Experiments

Experiments are defined entirely in YAML:
- Scenario configuration
- Evaluation parameters
- LLM configuration with inline system_prompt
- Policy constraints

**No Python code required** for new experiments.

### Inline vs Module-Based Configuration

| Approach | When to Use |
|----------|-------------|
| Inline `system_prompt` | Experiment-specific prompts |
| Inline `policy_constraints` | Experiment-specific constraints |
| `constraints_module` | Shared constraints across experiments |

### GenericExperimentRunner Pattern

All experiments use the same runner:
1. Load ExperimentConfig from YAML
2. Create GenericExperimentRunner(config)
3. Call runner.run() → ExperimentResult
```

---

### Task 19.8: Review Architecture Documentation (P3)

Check for outdated references in:
- `docs/reference/architecture/10-cli-architecture.md`
- `docs/reference/architecture/appendix-a-module-reference.md`

Look for:
- References to Castro Python code
- Outdated module structures
- Missing experiments/llm modules

---

### Task 19.9: Final Verification

1. **Link Validation**:
```bash
# Check for broken links
grep -r "\[.*\](.*\.md)" docs/ | while read line; do
  # Extract and verify each link
done
```

2. **Reference Validation**:
```bash
# Check for references to deleted code
grep -r "experiments/castro/castro" docs/
grep -r "castro/runner\.py" docs/
grep -r "castro/cli\.py" docs/
grep -r "castro run " docs/
grep -r "uv run castro" docs/
```

3. **Terminology Check**:
```bash
# Check for Monte Carlo terminology (should be Bootstrap)
grep -ri "monte.carlo" docs/reference/ai_cash_mgmt/
grep -ri "monte.carlo" docs/reference/experiments/
```

4. **Accuracy Spot Check**:
- Run CLI commands mentioned in docs
- Verify YAML examples are valid
- Verify code examples compile/run

---

## Files to Create/Delete/Modify

### DELETE (Obsolete)

| File | Reason |
|------|--------|
| `docs/reference/castro/cli-commands.md` | Castro CLI no longer exists |
| `docs/reference/castro/state-provider.md` | StateProvider is in core |
| `docs/reference/castro/events.md` | Events are in core |

### REWRITE (Heavily Outdated)

| File | Reason |
|------|--------|
| `docs/reference/castro/index.md` | Complete structure change |

### UPDATE (Moderate Changes)

| File | Changes |
|------|---------|
| `README.md` | Add experiments section, update counts |
| `docs/reference/experiments/index.md` | YAML-only, GenericExperimentRunner |
| `docs/reference/experiments/configuration.md` | Inline prompts/constraints |
| `docs/reference/experiments/runner.md` | GenericExperimentRunner |
| `docs/reference/cli/commands/experiment.md` | New commands |
| `docs/reference/cli/index.md` | Command tree |
| `docs/reference/llm/configuration.md` | system_prompt field |
| `docs/reference/patterns-and-conventions.md` | New patterns |

### REVIEW (Minor Updates Possible)

| File | Check For |
|------|-----------|
| `docs/reference/ai_cash_mgmt/*.md` | Bootstrap terminology |
| `docs/reference/architecture/*.md` | Castro references |
| `docs/reference/llm/index.md` | Accuracy |
| `docs/reference/llm/protocols.md` | Accuracy |

---

## Verification Checklist

After completing all tasks:

- [ ] No references to deleted Castro Python code
- [ ] No references to `castro run` or `uv run castro`
- [ ] All CLI examples use `payment-sim experiment`
- [ ] All YAML examples are valid (can be parsed)
- [ ] All links in documentation are valid
- [ ] No "Monte Carlo" terminology (use "Bootstrap")
- [ ] Test counts in README are accurate
- [ ] Architecture diagrams reflect current state
- [ ] experiments/castro/README.md matches reality

---

## Expected Outcome

After Phase 19:

1. **README.md**: Complete, accurate overview with experiments section
2. **Castro docs**: Reflect YAML-only reality, no Python code references
3. **Experiments docs**: Document GenericExperimentRunner, YAML-only approach
4. **CLI docs**: Accurate `payment-sim experiment` command reference
5. **LLM docs**: Document inline system_prompt support
6. **AI Cash Management docs**: Correct Bootstrap terminology
7. **All docs**: Consistent, accurate, production-ready

---

## TDD Approach for Documentation

While documentation doesn't have traditional tests, we can verify:

```bash
# 1. Validate no broken references
grep -r "castro/castro" docs/  # Should find nothing
grep -r "castro run" docs/     # Should find nothing (except historical)
grep -r "uv run castro" docs/  # Should find nothing

# 2. Validate YAML examples
python -c "
from pathlib import Path
import yaml
# Parse all YAML in docs and verify valid
"

# 3. Validate CLI commands exist
payment-sim experiment --help
payment-sim experiment run --help
payment-sim experiment validate --help
payment-sim experiment list --help

# 4. Validate code examples
python -c "
from payment_simulator.experiments.config import ExperimentConfig
from payment_simulator.experiments.runner import GenericExperimentRunner
from payment_simulator.llm import LLMConfig, LLMClientProtocol
"
```

---

*Document Version 1.0 - Phase 19 Documentation Overhaul*
