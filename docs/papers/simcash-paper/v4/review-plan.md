# Peer Review Response Plan

## Review Summary

The reviewer identified the paper as "potentially publishable" with a "clear core idea" but flagged several "must-fix consistency and methodology issues." This document tracks our response to each issue.

---

## Priority 1: Must-Fix Before Circulation

### 1.1 Exp2 Appendix C Cost Tables Are Inconsistent

**Issue**: Appendix C shows `BANK_A Cost == BANK_B Cost` at every iteration (e.g., both $225.49 at Iteration 2), but:
- Bootstrap statistics show different costs (BANK_A $164.40 vs BANK_B $130.85)
- Liquidity fractions differ (30% vs 15%)
- Charts show different per-agent cost trajectories

**Root Cause Investigation**:
- [ ] Query database to verify actual per-agent costs
- [ ] Check if appendix generation script used wrong column or aggregated incorrectly
- [ ] Determine if "Total Cost" column was duplicated into per-agent columns

**Fix**:
- [ ] Regenerate Appendix C tables with correct per-agent costs
- [ ] Verify regenerated values match bootstrap statistics and charts
- [ ] Add explicit column definitions (e.g., "Agent cost = liquidity cost + delay cost + penalties for that agent")

**Verification**: Cross-check at least 3 data points against:
1. Raw database `policy_evaluations` table
2. Bootstrap statistics in Section 5.2.1
3. Per-agent convergence charts

---

### 1.2 Text/Config Mismatches

**Issue A: Exp1 Description**
- Paper says: "Fixed payment arrivals at tick 0: BANK_A sends 0.2, BANK_B sends 0.2"
- Config shows: BANK_B sends 0.15 at tick 0, 0.05 at tick 1; BANK_A sends 0.15 at tick 1

**Fix**:
- [ ] Update Section 4.1 Exp1 description to match `exp1_2period.yaml` exactly
- [ ] Explain the asymmetric arrival structure that enables free-riding

**Issue B: Exp2 Poisson Rate**
- Paper says: "Poisson arrivals (λ=0.5/tick)"
- Config shows: `rate_per_tick: 2.0`

**Fix**:
- [ ] Update Section 4.1 Exp2 description to state λ=2.0/tick
- [ ] Or clarify if 0.5 refers to something else (e.g., per-agent rate)

**Verification**: Grep all YAML configs and ensure every parameter mentioned in prose matches exactly.

---

### 1.3 Appendix D Prompt Isolation Audit - Balance Leakage

**Issue**: The audit claims "policy parameters remain hidden" but balance trajectories at tick 0 directly reveal `initial_liquidity_fraction`:
```
[tick 0] RtgsImmediateSettlement: ... Balance: $500.00 → $350.00
```
If the pool size ($1000) is known or inferable, then $500 balance → 50% liquidity fraction.

**Options**:

**Option A: Reframe as Observable-Balance Game** (Recommended - less disruptive)
- [ ] Update Appendix D to acknowledge balance visibility explicitly reveals liquidity allocation
- [ ] Reframe the theoretical model: "Agents observe counterparty balances but not decision rules"
- [ ] Argue this matches real RTGS institutional settings (central bank sees all balances)
- [ ] Update paper framing: this is a game with observable actions, not hidden policies
- [ ] The equilibrium result still holds because we're finding fixed points, not relying on hidden information

**Option B: Fix Leakage and Rerun** (More rigorous but expensive)
- [ ] Modify prompt generation to hide counterparty balance changes
- [ ] Rerun all 9 experiments
- [ ] Show equilibria persist without balance visibility
- [ ] Update Appendix D with new audit

**Decision**: [TBD - discuss with co-authors]

**Minimum Required**:
- [ ] Rewrite Appendix D verdict to be accurate about what is visible
- [ ] Remove claim that "policy parameters are private" if balance reveals them
- [ ] Add explicit statement: "Agents observe counterparty balances at settlement time"

---

### 1.4 Learning Dynamic and Acceptance Criterion Ambiguity

**Issue A: Sequential vs Simultaneous Updates**
- Tables show both agents updating in same iteration
- Paper says "iterative best-response" which implies sequential

**Fix**:
- [ ] Add Algorithm 1 box in Section 3.3 with explicit pseudocode:
  ```
  for iteration = 1 to max_iterations:
      for agent in [BANK_A, BANK_B]:  # Sequential within iteration
          proposed_policy = LLM.propose(agent, context)
          cost_current = evaluate(current_policies)
          cost_proposed = evaluate(current_policies with agent's proposal)
          if accept(cost_current, cost_proposed):
              current_policies[agent] = proposed_policy
      if converged(history, window=5, threshold=0.05):
          break
  ```
- [ ] Clarify: "Within each iteration, agents update sequentially; BANK_A proposes first, then BANK_B responds to BANK_A's updated policy"

**Issue B: "cost delta > 0" vs "statistically significant"**
- Deterministic (Exp1/3): Accept if `new_cost < old_cost`
- Stochastic (Exp2): What exactly?

**Fix**:
- [ ] Define acceptance criterion precisely in Section 3.3:
  - Deterministic mode: Accept if `mean_new_cost < mean_old_cost`
  - Bootstrap mode: Accept if `mean_new_cost < mean_old_cost` (point estimate comparison)
- [ ] Acknowledge limitation: "We use point estimate comparison rather than formal hypothesis testing; this can accept noise-driven improvements"
- [ ] Add to Future Work: "More sophisticated acceptance criteria (e.g., requiring CI non-overlap) could improve stochastic convergence"

**Issue C: Common Random Numbers**
- [ ] Clarify whether same seeds are used for comparing current vs proposed policy
- [ ] If yes, document this variance reduction technique
- [ ] If no, acknowledge this as a limitation

---

## Priority 2: Strongly Recommended Enhancements

### 2.1 Best-Response Verification Plots

**Purpose**: Prove converged policies are actually Nash equilibria, not just fixed points.

**Method**:
- [ ] For each experiment's final policy pair (π_A*, π_B*):
  - Sweep BANK_A's liquidity fraction from 0% to 40% in 1% increments, holding BANK_B fixed at π_B*
  - Compute expected cost C_A(ℓ_A | π_B*) for each point
  - Plot and show minimum aligns with π_A*
  - Repeat for BANK_B
- [ ] For Exp2: Use 200 Monte Carlo samples per grid point

**Output**:
- Figure 8: Best-Response Verification (6 subplots: 2 agents × 3 experiments)
- Add Section 5.6 "Nash Equilibrium Verification"

**Effort**: ~2-4 hours (mostly computation time for Exp2)

---

### 2.2 Out-of-Sample Evaluation for Exp2

**Purpose**: Address concern about overfitting to the 50 bootstrap samples used during optimization.

**Method**:
- [ ] Evaluate final Exp2 policies on 1000 fresh random seeds
- [ ] Report: mean, median, std dev, 95th percentile, CVaR(95)
- [ ] Compare to in-sample statistics

**Output**:
- Table in Section 5.2: "Out-of-Sample Evaluation (n=1000)"
- Discussion of generalization

**Effort**: ~1 hour

---

### 2.3 Baseline Optimizer Comparison

**Purpose**: Justify LLM approach vs simpler alternatives for 1D optimization.

**Method**:
- [ ] Implement grid search baseline (0-50% in 1% increments)
- [ ] Implement golden-section search baseline
- [ ] Compare: iterations to convergence, final cost, wall-clock time

**Output**:
- Appendix E: Baseline Comparison
- Brief mention in Discussion: "While grid search achieves similar results for 1D policies, the LLM approach scales to higher-dimensional policy spaces (future work)"

**Effort**: ~2-3 hours

**Alternative**: Simply acknowledge in limitations that 1D optimization doesn't showcase LLM advantages, and position multi-parameter policies as future work.

---

### 2.4 Demonstrate Nontrivial Timing Policy

**Purpose**: Earn the "policy tree" framing by showing LLM can discover when to hold vs release.

**Method**:
- [ ] Design Exp4 with:
  - High liquidity cost (incentivizes low reserves)
  - Low delay cost (holding is cheap)
  - Payment recycling opportunity (incoming payments fund outgoing)
- [ ] Run experiment allowing LLM to modify `payment_tree` beyond simple Release
- [ ] Show discovered policy includes conditional holding

**Output**:
- Section 5.5 or Appendix: "Extended Experiment: Timing Optimization"
- Demonstrate LLM proposes `Hold` under specific conditions

**Effort**: ~4-6 hours (new experiment design + runs)

**Alternative**: Defer to future work with explicit acknowledgment: "Current experiments optimize only `initial_liquidity_fraction`; extending to timing decisions is future work."

---

## Priority 3: Writing/Presentation Cleanups

### 3.1 Units Consistency
- [ ] Add explicit statement: "All monetary amounts reported in dollars; simulator uses integer cents internally"
- [ ] Verify all charts use consistent $ formatting
- [ ] Check appendix tables match chart scales

### 3.2 Citations
- [ ] Fix "Castro et al. (2025)" → "Castro et al. (2013)" throughout
- [ ] Verify "OpenAI (2024) GPT-5.2 Technical Report" is citable; if not, use model-agnostic description
- [ ] Add citations for adjacent work (LLMs in multi-agent simulation, LLMs as optimizers)

### 3.3 Claim Discipline
- [ ] Remove or qualify "first to apply LLMs to..." unless literature scan supports it
- [ ] Soften novelty claims to "we demonstrate" rather than "we pioneer"

### 3.4 Bootstrap Terminology
- [ ] Clarify: "We use Monte Carlo sampling from the stochastic simulator with different random seeds, which we term 'bootstrap evaluation' following [citation]"
- [ ] Or rename to "Monte Carlo policy evaluation" if "bootstrap" is misleading

### 3.5 Appendix Duplication
- [ ] Check final document for repeated blocks
- [ ] Ensure Appendix C appears only once

---

## Implementation Order

### Phase 1: Critical Fixes (Before any circulation)
1. Regenerate Exp2 Appendix C tables with correct per-agent costs
2. Fix all text/config mismatches (Exp1 description, Exp2 λ)
3. Rewrite Appendix D with honest assessment of balance visibility
4. Add Algorithm 1 box defining learning dynamic precisely

### Phase 2: Verification (Strengthens claims significantly)
5. Generate best-response verification plots
6. Run out-of-sample evaluation for Exp2

### Phase 3: Enhancements (Nice to have)
7. Baseline optimizer comparison
8. Timing policy experiment (or defer to future work)

### Phase 4: Polish
9. All writing cleanups
10. Final consistency check

---

## Tracking

| Issue | Status | Assigned | Notes |
|-------|--------|----------|-------|
| 1.1 Exp2 cost tables | TODO | | |
| 1.2a Exp1 description | TODO | | |
| 1.2b Exp2 λ rate | TODO | | |
| 1.3 Balance leakage | TODO | | Need decision: Option A or B |
| 1.4a Algorithm box | TODO | | |
| 1.4b Acceptance criterion | TODO | | |
| 2.1 BR verification | TODO | | |
| 2.2 Out-of-sample | TODO | | |
| 2.3 Baseline comparison | TODO | | May defer |
| 2.4 Timing experiment | TODO | | May defer |
| 3.x Writing cleanups | TODO | | |

---

## Decision Points for Co-Authors

1. **Balance leakage**: Option A (reframe) or Option B (fix and rerun)?
2. **Baseline comparison**: Include or defer to future work?
3. **Timing experiment**: Include or defer to future work?
4. **Bootstrap terminology**: Keep "bootstrap" or rename to "Monte Carlo"?
