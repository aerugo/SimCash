# Castro Experiment Archive

This directory contains archived code and documentation from the Castro experiment.

## Directory Structure

### `docs-2025-12-03/`
Archived documentation from initial experiment phase:
- `LAB_NOTES.md` - Extensive experimental logs (116 KB)
- `RESEARCH_PAPER.md` - Draft paper with results
- `VALIDATION_ERROR_REPORT.md` - Error analysis findings
- `HANDOVER.md` - Status and protocols document

**Key results from this phase:**
- Exp 1 (2-period deterministic): 92.5% cost reduction
- Exp 3 (joint learning): 99.95% cost reduction
- Exp 2 (stochastic): 8.5% cost increase (challenging)

### `deprecated-scripts-2025-12-03/`
Deprecated optimizer scripts superseded by current versions:
- `optimizer.py` - Original version (DEPRECATED: corrupts seed files)
- `optimizer_v2.py` - Enhanced prompts (DEPRECATED: corrupts seed files)
- `optimizer_v3.py` - Per-tick event logs (superseded by `reproducible_experiment.py`)
- `optimizer_v4.py` - Structured output (superseded by `robust_experiment.py`)

### `pre-castro-alignment/`
Experiments from before Castro-alignment features were implemented (2025-12-02):
- Used immediate crediting instead of deferred crediting
- Did not cap deadlines at EOD
- Results are not comparable to aligned experiments

### Root-level `.archived` files
- `constrained.py.archived` - Old constrained policy generator
- `optimizer_v5.py.archived` - Archived optimizer version
- `policy_agent.py.archived` - Old policy agent
- `test_policy_agent.py.archived` - Old tests

## Current Active Code

The current experiment code is in the parent directory:
- `scripts/reproducible_experiment.py` - Main experiment runner
- `scripts/robust_experiment.py` - Constrained schema version
- `generator/robust_policy_agent.py` - Current LLM policy agent
- `schemas/` - Current Pydantic schemas

See `../ARCHITECTURE.md` for comprehensive technical documentation.
