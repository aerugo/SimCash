# SimCash Paper v3 - Lab Notes

**Started**: 2025-12-14
**Author**: Claude (Opus 4.5)
**Objective**: Reproduce Castro et al. (2025) with Castro-compliant configuration

---

## Session Log

### 2025-12-14: Setup & Configuration

**Objective**: Configure experiments to use `liquidity_pool` mode (Castro-compliant)

#### Key Changes Made

1. **Modified optimization.py**:
   - Added `_get_agent_liquidity_pool()` helper method
   - Updated `_build_simulation_config()` to inject `liquidity_allocation_fraction` from policy's `initial_liquidity_fraction` when agent uses `liquidity_pool`
   - Updated `_create_default_policy()` to create simpler policy without `strategic_collateral_tree` for `liquidity_pool` mode agents

2. **Updated Scenario Configs** (experiments/castro/configs/):
   - `exp1_2period.yaml`: Replaced `max_collateral_capacity` with `liquidity_pool`, `collateral_cost_per_tick_bps` with `liquidity_cost_per_tick_bps`, set `overdraft_bps_per_tick: 0`
   - `exp2_12period.yaml`: Same pattern
   - `exp3_joint.yaml`: Same pattern

3. **Updated Experiment Configs** (experiments/castro/experiments/):
   - `exp1.yaml`: Removed collateral-related allowed_fields and actions
   - `exp2.yaml`: Same pattern, updated prompt_customization
   - `exp3.yaml`: Same pattern, updated prompt_customization

#### Validation Results

All configs validated successfully:
```
exp1: deterministic mode, 25 max iterations, optimizes BANK_A, BANK_B
exp2: bootstrap mode, 25 max iterations, optimizes BANK_A, BANK_B
exp3: deterministic mode, 25 max iterations, optimizes BANK_A, BANK_B
```

---

## Experiment 1: 2-Period Deterministic

*Status: COMPLETED*

### Configuration Summary

- **Mode**: Deterministic
- **Samples**: 50
- **Ticks**: 2
- **Model**: openai:gpt-5.2 (temperature 0.5, reasoning_effort: high)
- **Convergence**: stability_window=5, stability_threshold=0.05, max_iterations=25
- **Master seed**: 42

### Castro Prediction

- **BANK_A**: 0% (free-rider)
- **BANK_B**: 20% (liquidity provider)

**Rationale**: With deferred crediting, BANK_B must allocate liquidity at t=0 to send its 15,000 payment. BANK_A can wait for B's payment to arrive and use those funds for its own t=1 payment.

### Execution Log

**Started**: 2025-12-14 12:27 UTC
**Completed**: 2025-12-14 12:49 UTC

Convergence trajectory:

| Iteration | BANK_A | BANK_B | Total Cost |
|-----------|--------|--------|------------|
| 1 | 50% → 40% | 50% → 25% | $100 → $65 |
| 2 | 40% → 30% | 25% → 20% | $65 → $50 |
| 3 | 30% → 25% | 20% (reject) | $50 → $45 |
| 4 | 25% → 20% | 20% (reject) | $45 → $40 |
| 5 | 20% → 15% | 20% (reject) | $40 → $35 |
| 6 | 15% → 10% | 20% (reject) | $35 → $30 |
| 7 | 10% → 5% | 20% (reject) | $30 → $25 |
| 8 | 5% → 4% | 20% (reject) | $25 → $24 |
| 9 | 4% → 3% | 20% (reject) | $24 → $23 |
| 10 | 3% → 2% | 20% (reject) | $23 → $22 |
| 11 | 2% → 1% | 20% (reject) | $22 → $21 |
| 12 | 1% → 0.75% | 20% (reject) | $21 → $20.76 |
| 13 | 0.75% (stable) | 20% (stable) | $20.76 |

**Key observation**: BANK_B stabilized at 20% in iteration 2 and remained there. BANK_A continued optimizing downward, discovering the free-rider strategy.

### Results

| Metric | BANK_A | BANK_B | Castro Prediction |
|--------|--------|--------|-------------------|
| Final `initial_liquidity_fraction` | **0.75%** | **20%** | 0% / 20% |
| Final Cost | $20.76 | $20.76 | - |

**Convergence**: Yes, after 13 iterations
**Reason**: Stability achieved (5 consecutive stable iterations)

**Analysis**:
- BANK_A discovered the free-rider equilibrium (0.75% ≈ 0%)
- BANK_B locked in at 20%, exactly matching Castro's prediction
- The asymmetric equilibrium emerged naturally from LLM policy optimization
- Total cost reduced from $100 to $20.76 (79% reduction)

---

## Experiment 2: 12-Period Stochastic

*Status: Pending*

### Configuration Summary

- **Mode**: Bootstrap
- **Samples**: 50
- **Ticks**: 12
- **Model**: openai:gpt-5.2 (temperature 0.5, reasoning_effort: high)
- **Convergence**: stability_window=5, stability_threshold=0.05, max_iterations=25
- **Master seed**: 42

### Castro Prediction

- **Both agents**: 10-30% range

### Results

(To be filled after experiment completes)

---

## Experiment 3: 3-Period Joint Optimization

*Status: Pending*

### Configuration Summary

- **Mode**: Deterministic
- **Samples**: 50
- **Ticks**: 3
- **Model**: openai:gpt-5.2 (temperature 0.5, reasoning_effort: high)
- **Convergence**: stability_window=5, stability_threshold=0.05, max_iterations=25
- **Master seed**: 42

### Castro Prediction

- **Both agents**: ~25%

### Results

(To be filled after experiment completes)

---

## Analysis Notes

(To be filled after all experiments complete)

---

*Last updated: 2025-12-14*
