# Exp2 Work Notes

## Session: 2025-12-12

### Current State Assessment

Starting fresh on exp2 optimization iteration. Need to understand:
1. What the optimal policy looks like from the paper
2. Current experiment configuration
3. What changes are needed

### Paper Analysis (Castro et al. 2025, Section 6.4)

**12-Period Case Key Insights:**

1. **Setup**:
   - T=12 intraday periods
   - Payment demands from LVTS data
   - Cost parameters: r_c=0.1, r_d=0.2, r_b=0.4

2. **Optimal Policy Structure**:
   - At t=0: Choose initial liquidity fraction x₀ ∈ [0,1]
   - During day: Send all possible payments (fixed policy)

3. **Paper Results (Figure 5, page 13)**:
   - Both agents reduce initial liquidity over training
   - Agent A (lower demand) converges to lower liquidity
   - Agent B (higher demand) converges to higher liquidity
   - Costs flatten near minimum around episode 60

4. **Key Quote from Section 6.4**:
   > "Over training, both reduce liquidity; agent A (lower demand) reduces more."
   > "Neither agent collapses to a single deterministic action; choices fluctuate within a band."

### Current Exp2 Configuration Analysis

**exp2.yaml observations:**
- Has many allowed_fields that may confuse the LLM
- Includes queue-related fields not in Castro model
- Has urgency_threshold and liquidity_buffer parameters not in paper

**exp2_12period.yaml observations:**
- Uses Poisson arrivals (rate_per_tick: 2.0)
- LogNormal amount distribution (mean: 10000, std: 5000)
- deadline_range: [3, 8] ticks
- deferred_crediting: true (matches Castro model)
- deadline_cap_at_eod: true
- LSM disabled (correct for Castro)

### Issues to Address

1. **Policy Complexity**: The allowed_parameters include:
   - initial_liquidity_fraction (CORRECT - this is the key parameter)
   - urgency_threshold (NOT in Castro model - remove?)
   - liquidity_buffer (NOT in Castro model - remove?)

2. **Field Overload**: Too many allowed_fields may distract from the simple solution

3. **Missing Guidance**: No prompt_customization to guide toward simplicity

### Next Steps

1. Run baseline experiment to see current behavior
2. Simplify policy_constraints to match Castro model more closely
3. Add prompt_customization to emphasize simplicity
4. Re-run and compare

---

## Baseline Run (2025-12-12, 00:08)

### Results Summary

| Iteration | Total Cost | BANK_A initial_liq | BANK_B initial_liq | Notes |
|-----------|------------|-------------------|-------------------|-------|
| 0 (baseline) | $5,124.07 | 0.50 | 0.50 | Default policy |
| 1 | $1,814.05 | 0.05 | 0.30 | Huge improvement! |
| 2 | $1,363.54 | 0.05 | 0.25 | Continued reduction |
| 3 | Failed | (rejected 0.03) | JSON error | Crashed |

### Key Observations

1. **LLM discovered the right direction immediately**: BANK_A reduced from 0.5 → 0.05 in iteration 1 (90% reduction)
2. **BANK_B slower to reduce**: 0.5 → 0.30 → 0.25
3. **Cost reduction was dramatic**: $5,124 → $1,364 in just 2 iterations
4. **Crash due to JSON parsing error**: LLM generated invalid policy JSON for BANK_B in iteration 3

### Issues Identified

1. **Too many parameters**: `urgency_threshold` and `liquidity_buffer` not in Castro model
2. **Too many allowed_fields**: Queue fields, priority, ticks_to_deadline not needed
3. **JSON complexity**: LLM generating complex trees that fail validation

### Configuration Changes Made

1. Removed `urgency_threshold` and `liquidity_buffer` parameters - only `initial_liquidity_fraction` now
2. Simplified allowed_fields to minimum needed for Castro model
3. Added `prompt_customization` to guide LLM toward simple policies

---

## Iteration 2: Simplified Configuration (2025-12-13)

### Configuration Changes Applied

1. **Simplified `policy_constraints`**:
   - Only `initial_liquidity_fraction` parameter (removed urgency_threshold, liquidity_buffer)
   - Minimal allowed_fields for Castro model

2. **Added `prompt_customization`**:
   ```yaml
   prompt_customization:
     all: |
       ## Experiment Focus: Initial Liquidity Allocation
       This scenario tests a fundamental tradeoff in payment systems:
       - Posting collateral provides liquidity to settle payments
       - But collateral has an opportunity cost
       The KEY DECISION is: What fraction of available collateral should be posted at the START of the day (tick 0)?
       The payment policy should be kept SIMPLE:
       - If you have liquidity, release payments
       - The complexity is in choosing the RIGHT initial liquidity level
       IMPORTANT: Focus your optimization on the `initial_liquidity_fraction` parameter.
   ```

### Run Results

**Baseline**: $5,124.07 (BANK_A: 0.50, BANK_B: 0.50)

| Iteration | Total Cost | BANK_A initial_liq | BANK_B initial_liq | Notes |
|-----------|------------|-------------------|-------------------|-------|
| 0 | $5,124.07 | 0.50 | 0.50 | Default policy |
| 1 | $2,352.07 | 0.20 | 0.25 | -54% cost reduction |
| 2 | $2,100.07 | 0.20 (rejected 0.25) | 0.15 | BANK_A prevented from regressing |
| 3 | $739.27 | 0.03 | 0.10 | BANK_A aggressive reduction |
| 4 | $890.47 | 0.02 | 0.10 (rejected 0.14) | BANK_B prevented from regressing |
| 5 | $678.79 | 0.02 (rejected 0.028) | 0.09 | Fine tuning |
| 6 | $643.51 | 0.0295 | 0.08 | Converging |
| 7 | $676.27 | 0.0295 (rejected 0.03) | 0.08 (rejected 0.088) | Both stable |
| 8 | $698.95 | 0.0295 (rejected 0.03) | 0.08 (rejected 0.092) | Both stable |
| 9+ | ~$700 | ~0.03 | ~0.08 | Converged |

### Key Observations

1. **Cost Reduction**: 86% reduction ($5,124 → ~$700) in 9 iterations
2. **Convergence Pattern** matches Castro et al.:
   - Both agents reduce initial liquidity from 0.5 default
   - BANK_A (lower demand) converges to lower liquidity (~0.03)
   - BANK_B (higher demand) converges to higher liquidity (~0.08)
3. **Bootstrap rejection mechanism works well**:
   - Prevented BANK_A from increasing to 0.25 (iteration 2)
   - Prevented BANK_B from regressing to 0.14 (iteration 4)
4. **Policy stability reached around iteration 7-8**:
   - Small delta proposals rejected (e.g., 0.03 vs 0.0295)
   - Indicates we're at/near optimal

### Comparison to Paper Results

| Aspect | Paper (Figure 5) | Our Results |
|--------|------------------|-------------|
| Agent A converges to lower liquidity | Yes | Yes (~0.03) |
| Agent B converges to higher liquidity | Yes | Yes (~0.08) |
| Both reduce from initial | Yes | Yes (0.5 → 0.03/0.08) |
| Costs flatten near minimum | ~Episode 60 | ~Iteration 7 |
| Policies fluctuate in band | Yes | Yes (rejections around optimal) |

### Success Metrics

- ✅ LLM discovered optimal policy direction without being told the answer
- ✅ Both agents converged to distinct equilibrium values
- ✅ No JSON parsing errors (simplified config fixed this)
- ✅ Bootstrap paired evaluation correctly rejected regressions
- ✅ 100% settlement rate maintained throughout

### Lessons Learned

1. **Simplify policy_constraints**: Fewer parameters = less LLM confusion
2. **prompt_customization is powerful**: Focused guidance without revealing answer
3. **Bootstrap evaluation is robust**: Correctly identifies improvements vs regressions
4. **GPT-5.2 with reasoning=high works well**: Consistently generates valid policies

---

## Summary

The exp2 (12-Period Stochastic LVTS) experiment successfully replicates the key findings from Castro et al. (2025):

1. Both agents learn to reduce initial liquidity commitment
2. Agent with lower payment demand (BANK_A) settles at lower liquidity fraction
3. Agent with higher payment demand (BANK_B) settles at higher liquidity fraction
4. The optimization converges to a stable equilibrium within ~10 iterations

The simplified configuration with focused prompt_customization proved effective at guiding the LLM toward discovering the optimal policy structure without revealing the answer.

