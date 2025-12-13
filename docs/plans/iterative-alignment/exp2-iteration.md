# Exp2 (12-Period Stochastic) Optimization Iteration Plan

## Overview

This plan documents the iterative work to make the policy optimization successfully discover the optimal policy for the 12-period stochastic scenario from Castro et al. (2025).

## Target: Paper's Optimal Policy

From Castro et al. (2025) Section 6.4:

### Key Findings for T=12:

1. **Initial Liquidity Decision** is the ONLY strategic variable
   - Choose x₀ ∈ [0,1] at t=0: ℓ₀ = x₀ · B (fraction of collateral)
   - No other collateral decisions allowed during day

2. **Intraday Policy is FIXED** to "send all possible payments"
   - If P_t < ℓ_{t-1}: send all (x_t = 1)
   - Otherwise: send what you can (x_t = ℓ_{t-1}/P_t)

3. **Cost Structure**: r_c < r_d < r_b
   - r_c = 0.1 (collateral cost per unit)
   - r_d = 0.2 (delay cost per tick per unit)
   - r_b = 0.4 (end-of-day borrowing cost)

4. **Optimal Behavior**:
   - Agent with higher outgoing demand needs higher initial liquidity
   - Agent receiving payments early can rely on incoming liquidity
   - Balance: enough liquidity to avoid delay costs, not too much to waste on collateral costs

### What the LLM Should Discover:

The LLM should learn to:
1. Set `initial_liquidity_fraction` appropriately based on payment patterns
2. Keep the payment tree simple: Release when possible
3. NOT over-engineer the collateral strategy

## Phase 1: Baseline Assessment

### 1.1 Review Current Setup
- [x] Read exp2.yaml configuration
- [x] Read exp2_12period.yaml scenario
- [ ] Identify misalignments with paper

### 1.2 Run Baseline Experiment
- [ ] Run exp2 with current config
- [ ] Record output and policy evolution
- [ ] Identify where policy goes wrong

## Phase 2: Configuration Alignment

### 2.1 Simplify Policy Constraints
The LLM may be confused by too many allowed fields/actions. Simplify to match Castro model:

**Minimal Fields Needed:**
- `system_tick_in_day` (to identify t=0 for initial collateral)
- `max_collateral_capacity` (to compute initial allocation)
- `remaining_collateral_capacity` (same)
- `balance` / `effective_liquidity` (to know if can release)
- `amount` / `remaining_amount` (payment amount)

**Remove confusing fields:**
- `queue1_total_value`, `outgoing_queue_size` - not in Castro model
- `ticks_to_deadline`, `priority` - not used for simple Release policy

### 2.2 Simplify Action Space
**Payment tree**: Only Release/Hold (keep it simple)
**Collateral tree**: PostCollateral/HoldCollateral at tick 0 only

### 2.3 Add Prompt Customization
Use the `prompt_customization` field to guide the LLM toward the Castro-style policy without giving away the answer.

## Phase 3: Prompt Engineering

### 3.1 Experiment Customization
Add experiment-specific guidance that:
- Emphasizes the simplicity of the optimal policy
- Points toward initial liquidity as the key decision
- Discourages over-engineering the payment tree

### 3.2 Cost Rate Context
Ensure cost rates are clearly presented:
- Highlight r_c < r_d < r_b relationship
- Emphasize that initial collateral is cheaper than delay

## Phase 4: Iteration Testing

### 4.1 Run Optimized Experiment
- [ ] Run with improved config
- [ ] Use `--audit` to inspect LLM prompts/responses
- [ ] Track policy evolution

### 4.2 Analyze Results
- [ ] Compare discovered policy to paper's optimal
- [ ] Identify remaining gaps
- [ ] Iterate as needed

## Success Criteria

The experiment is successful when:
1. LLM discovers that initial_liquidity_fraction is the key parameter
2. Payment tree converges to simple Release policy
3. Total cost approaches theoretical optimum
4. Policy is stable across iterations

## Notes

- Important: Never reveal the paper's findings in the prompt
- Focus on making the problem well-specified, not on giving hints
- Let the LLM discover the optimal policy through simulation feedback
