# Exp3 Iteration Plan: Three-Period Dummy Example

## Objective

Recreate the Three-Period Dummy Example from Castro et al. (2025) Section 7.2, where agents jointly learn initial liquidity allocation AND payment timing decisions.

## Paper Reference

### Section 7.2: Three-Period Dummy Example

**Setup:**
- P^A = P^B = [0.2, 0.2, 0] — symmetric payment demands as fractions of collateral B
- 3 periods: t=0 (beginning of day), t=1 (first payments), t=2 (second payments)
- Both initial liquidity x₀ AND intraday payment fraction x_t are learned

**Key Results (Scenario 1: All Payments Divisible):**

1. **When r_c < r_d (liquidity cheaper than delay):**
   - Agents allocate ~25% initial liquidity
   - Delay few payments (~10%)

2. **When r_d < r_c (delay cheaper than liquidity):**
   - Agents allocate ~20% initial liquidity
   - Delay more payments (~25%)

**Cost Structure from Paper:**
- r_c = 0.1 (initial liquidity cost per unit)
- r_d = 0.2 (delay cost per tick per unit NOT paid)
- r_b = 0.4 (end-of-day borrowing cost)

## Gap Analysis

### Current exp3_joint.yaml Issues

| Aspect | Paper Requirement | Current Config | Status |
|--------|-------------------|----------------|--------|
| Payment arrival | FIXED [0.2, 0.2, 0] | Stochastic Poisson | ❌ WRONG |
| Payment amounts | 20% of collateral | LogNormal variable | ❌ WRONG |
| Periods | 3 (t=0,1,2) | 3 ticks | ✓ OK |
| Cost structure | r_c < r_d < r_b | Complex bps rates | ⚠️ VERIFY |

### Current exp3.yaml Issues

| Aspect | Paper Requirement | Current Config | Status |
|--------|-------------------|----------------|--------|
| Parameters | initial_liquidity_fraction, payment_fraction | Has urgency_threshold, liquidity_buffer | ❌ TOO COMPLEX |
| Actions | Payment: Release/Hold | OK | ✓ OK |
| Fields | Minimal (tick, liquidity, demand) | Many queue fields | ⚠️ SIMPLIFY |

## Implementation Phases

### Phase 1: Fix Scenario Configuration

**Goal:** Make exp3_joint.yaml match paper's Three-Period Dummy Example exactly.

1. Remove stochastic arrivals (rate_per_tick, arrival_config)
2. Add fixed "scripted" transactions:
   - t=0: A owes B 20% of collateral, B owes A 20% of collateral
   - t=1: Same pattern
   - t=2: No new payments (P_2 = 0)
3. Verify cost parameters satisfy r_c < r_d < r_b

### Phase 2: Simplify Policy Constraints

**Goal:** Remove confusion from LLM by limiting to exactly what paper uses.

1. **Parameters:**
   - `initial_liquidity_fraction` (x₀ ∈ [0,1]) — fraction of collateral to post
   - `payment_fraction` (x_t ∈ [0,1]) — fraction of queued payments to release (optional)

2. **Fields:**
   - `system_tick_in_day` — current tick (0, 1, 2)
   - `balance` — current liquidity
   - `effective_liquidity` — balance + credit
   - `queue1_total_value` — pending payment value

3. **Actions:**
   - payment_tree: Release, Hold
   - collateral_tree: PostCollateral, HoldCollateral

### Phase 3: Run and Iterate

1. Run experiment with GPT-5.2, reasoning=high
2. Analyze convergence behavior
3. Compare to paper results:
   - Initial liquidity should converge to ~20-25%
   - Payment delay should match cost regime (r_c vs r_d)

## Success Criteria

- [ ] Both agents converge to similar initial liquidity (symmetric demands)
- [ ] Initial liquidity fraction ≈ 0.20-0.25 (matching paper)
- [ ] Payment fraction ≈ 0.75-0.90 (depending on r_c vs r_d)
- [ ] Total cost stabilizes within 15 iterations
- [ ] No JSON parsing errors

## Key Insight

The paper's "Three-Period Dummy Example" is DETERMINISTIC with FIXED payment demands. It's NOT stochastic like the 12-period case. This is a fundamental difference that must be corrected.
