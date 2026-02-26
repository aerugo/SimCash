# SimCash Experiments — 2026 Q1

**Paper:** "SimCash — LLM-Optimized Payment Strategies in Simulated RTGS Environments"
**Authors:** Stefan (Research Director, Banking & Payments, Bank of Canada) & Hugi Aegisberg
**Period:** February 2026

## Overview

Systematic evaluation of LLM-optimized cash management strategies across simulated RTGS scenarios, comparing three Vertex AI models under varying complexity and prompt intervention conditions.

### Models
- `google-vertex:glm-4.7-maas` (GLM-4.7)
- `google-vertex:gemini-2.5-flash` (Gemini 2.5 Flash)
- `google-vertex:gemini-2.5-pro` (Gemini 2.5 Pro)

### Experiment Waves

| Wave | Experiments | Description |
|------|-------------|-------------|
| Wave 1 | 93 | 9 scenarios × 3 models × 3 runs + 10 baselines |
| v0.2 Settlement Optimization | 12+ | Castro Exp2 × 4 conditions (C1-C4) × 3 models |
| Phase A (v0.2 replication) | 24 | C1-C4 × 3 models × 2 additional runs |
| Phase C (retry mechanism) | 36 (planned) | C1-C4 × 3 models × 3 runs with `max_policy_proposals=2` |

### Key Findings

1. **Complexity threshold**: LLM optimization reduces costs 32-86% on simple scenarios (2-4 banks) but is *worse* than FIFO on complex scenarios (5+ banks)
2. **Strategy poverty**: LLMs use only 5/11 available policy actions; bank decision trees are universally NoAction
3. **Constraints > Information**: Adding a settlement floor constraint (C2) matters more than providing richer context (C1)
4. **Model selection > prompt engineering**: The gap between Flash and GLM/Pro under identical conditions exceeds the gap between prompt conditions for a single model
5. **Prompt complexity has an optimum**: GLM peaks at C2 (simple constraint), Flash at C3/C4 (full toolkit), Pro is stable across conditions

## Directory Structure

```
experiments/2026Q1/
├── README.md                 # This file
├── run-pipeline.py           # Automated experiment pipeline (2-slot parallel)
├── run-pipeline-v2.py        # Pipeline v2 variant
├── analyze_results.py        # Results analysis script
├── plans/
│   ├── experiment-plan.yaml  # Full experiment definitions (130 experiments)
│   ├── experiment-config.yaml
│   └── v02-experiment-plan.md # Phase A/B/C planning document
├── analysis/
│   ├── conference-paper-notes.md  # Detailed paper notes and findings
│   ├── simcash-analysis.md        # Platform analysis (74KB)
│   ├── preliminary-analysis.md
│   └── working-paper-notes.md
└── results/
    └── *.json                # 130 experiment result files
```

## Pipeline Usage

```bash
# Set API key
export SIMCASH_API_KEY="sk_live_..."
# Or store in .simcash-api-key file

# Run pipeline (reads experiment-plan.yaml, launches pending experiments)
python3 run-pipeline.py

# Pipeline features:
# - 2-slot parallelism (configurable)
# - Pro experiments run exclusively (rate limit protection)
# - Automatic polling and result collection
# - YAML state tracking (pending → running → complete)
```

## Reproducibility

- SimCash simulation is deterministic (seed 42)
- LLM stochasticity is the only source of variance across runs
- 3 runs per experimental cell enables mean ± std reporting
- Baselines use `use_llm: false` + `starting_fraction: 0.5` (FIFO)
- All experiment IDs and timestamps preserved in result JSONs

## v0.2 Prompt Conditions

| Condition | Prompt blocks enabled |
|-----------|----------------------|
| C1-info | `usr_liquidity_context`, `usr_balance_trajectory` |
| C2-floor | C1 + `sys_settlement_constraint` |
| C3-guidance | C2 + `usr_worst_case` |
| C4-composition | C3 + `sys_tree_composition` |
