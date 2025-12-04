# Lab Notes: Castro Experiment

**Researcher**: Claude (Opus 4)
**Date Started**: 2025-12-04
**Project**: LLM-based Policy Optimization for Payment Systems

---

## Overview

This notebook tracks experiments replicating and extending Castro et al. (2025) "Strategic Payment Timing" using LLM-based policy optimization.

See `ARCHITECTURE.md` for technical documentation of the codebase.

---

## Experiment Log

### Session 2025-12-04 (Session 2) - GPT-5.1 High Reasoning Experiments

#### Environment Setup

**Bug Fixes Applied:**
1. **JSON Parsing Bug**: Fixed `run_single_simulation()` to extract JSON from stdout when persistence messages precede JSON output
2. **Path Resolution Bug**: Fixed `run_simulations_parallel()` to use absolute paths for `work_dir` parameter (subprocess runs from `simcash_root`, not castro directory)

#### Experiment 1: Two-Period Deterministic (Castro-Aligned)

**Configuration:**
- Model: GPT-5.1 with high reasoning effort
- Seeds: 1 (deterministic)
- Max iterations: 15
- Database: `results/exp1_gpt51_opus4_session2_run3.db`

**Results:**
| Iteration | Cost | Change from Baseline |
|-----------|------|---------------------|
| 1 (baseline) | $29,000 | - |
| 2 | $21,500 | -25.9% |
| 3 | $24,000 | -17.2% |
| 4 | $26,500 | -8.6% |
| **5 (best)** | **$7,750** | **-73.3%** |
| 6 | $29,000 | 0% |
| 7 | $29,000 | 0% |
| 8 | $26,500 | -8.6% |
| 9 | $25,500 | -12.1% |
| 10 | $15,000 | -48.3% |
| 11 | $13,000 | -55.2% |
| 12 | $18,688 | -35.6% |
| 13 | $24,000 | -17.2% |
| 14 | $14,000 | -51.7% |
| 15 (final) | $22,000 | -24.1% |

**Key Statistics:**
- Best cost: $7,750 at iteration 5 (73.3% reduction)
- Final cost: $22,000 (24.1% reduction from baseline)
- LLM calls: 14
- Total tokens: ~56,000
- Avg latency: 26.7s
- Validation errors: 27 (policy validation failures requiring fixes)

**Best Policy Parameters (Iteration 5):**
```json
BANK_A: {"urgency_threshold": 3.0, "liquidity_buffer": 1.05, "initial_collateral_fraction": 0.25}
BANK_B: {"urgency_threshold": 3.0, "liquidity_buffer": 1.1, "initial_collateral_fraction": 0.2}
```

**Observations:**
1. **High Variance**: GPT-5.1 showed significant variance in optimization, with costs ranging from $7,750 to $29,000
2. **Validation Challenges**: 27 validation errors indicate the LLM struggles to produce syntactically valid policies
3. **Non-Monotonic Progress**: Cost did not decrease monotonically; iteration 5's excellent result was not maintained
4. **Castro Equilibrium**: The best result at $7,750 approaches the Castro-predicted Nash equilibrium (Bank A ~$0, Bank B ~$2,000 = $2,000 total), but didn't quite reach it
5. **Collateral Strategy**: Best iteration used moderate collateral fractions (0.20-0.25), suggesting partial pre-funding

**Hypothesis**: The LLM may benefit from:
- Elitist selection (always keeping best policy)
- More explicit game-theoretic guidance
- Structured parameter bounds

---

#### Experiment 2: Twelve-Period Stochastic (Castro-Aligned)

**Configuration:**
- Model: GPT-5.1 with high reasoning effort
- Seeds: 10 (stochastic)
- Max iterations: 15
- Database: `results/exp2_gpt51_opus4_session2_run1.db`

**Results:**
| Iteration | Mean Cost | Std Dev | Change from Baseline |
|-----------|-----------|---------|---------------------|
| 1 (baseline) | $4,980.3M | ±$224K | - |
| 2 | $4,980.3M | ±$224K | 0% |
| 3 | $4,876.5M | ±$224K | -2.1% |
| 4 | $4,876.5M | ±$224K | -2.1% |
| 5 | $2,490.3M | ±$224K | -50.0% |
| 6 | $2,490.3M | ±$224K | -50.0% |
| 7 | $5,478.3M | ±$224K | +10.0% |
| 8 | $4,980.3M | ±$224K | 0% |
| 9 | $3,830.3M | ±$224K | -23.1% |
| 10 | $4,980.3M | ±$224K | 0% |
| **11 (best)** | **$207.7M** | ±$224K | **-95.8%** |
| 12 | $5,478.3M | ±$224K | +10.0% |
| 13 | $2,988.3M | ±$224K | -40.0% |
| 14 | $2,789.1M | ±$224K | -44.0% |
| 15 (final) | $4,980.3M | ±$224K | 0% |

**Key Statistics:**
- Best cost: $207.7M at iteration 11 (95.8% reduction!)
- Final cost: $4,980.3M (regressed to baseline)
- LLM calls: 14
- Total tokens: ~56,000
- Avg latency: 27.8s
- Settlement rate: 100% (all iterations)

**Best Policy Parameters (Iteration 11):**
```json
BANK_A: {"urgency_threshold": 3.0, "liquidity_buffer": 0.85, "initial_collateral_fraction": 0.25}
BANK_B: {"urgency_threshold": 3.0, "liquidity_buffer": 0.85, "initial_collateral_fraction": 0.25}
```

**Observations:**
1. **Extreme Cost Levels**: The $4.98B baseline cost is driven by the high unsecured_cap ($100M) being multiplied by collateral fractions. This inflates collateral costs dramatically.
2. **Spectacular Best Result**: Iteration 11 achieved 95.8% cost reduction with symmetric policies (both banks using liquidity_buffer=0.85, initial_collateral_fraction=0.25)
3. **Severe Instability**: The best result was immediately lost in iteration 12, jumping from $207.7M to $5,478.3M - a 26x cost increase
4. **Low Variance Within Seeds**: The ±$224K std deviation on multi-billion dollar costs shows all seeds produce nearly identical results
5. **No Convergence**: Final iteration regressed completely to baseline, showing no learning retention

**Key Insight**: The LLM discovered that reducing liquidity_buffer from 1.05 to 0.85 dramatically reduces collateral costs. The optimal policy uses minimal collateral posting.

---
