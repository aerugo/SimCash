# Peer Review Response Plan

## Review Summary

The reviewer identified the paper as "potentially publishable" with a "clear core idea" but flagged several "must-fix consistency and methodology issues." This document tracks our response to each issue.

---

## Priority 1: Must-Fix Before Circulation

### 1.1 Text/Config Mismatches

**Issue A: Exp1 Description**
- Paper says: "Fixed payment arrivals at tick 0: BANK_A sends 0.2, BANK_B sends 0.2"
- Config shows: BANK_B sends 0.15 at tick 0, 0.05 at tick 1; BANK_A sends 0.15 at tick 1

**Fix**:
- [ ] Update Section 4.1 Exp1 description to match `exp1_2period.yaml` by getting the value programatically
- [ ] Explain the asymmetric arrival structure that enables free-riding

**Issue B: Exp2 Poisson Rate**
- Paper says: "Poisson arrivals (λ=0.5/tick)"
- Config shows: `rate_per_tick: 2.0`

**Fix**:
- [ ] Update Section 4.1 Exp2 description to get the value programatically
- [ ] Or clarify if 0.5 refers to something else (e.g., per-agent rate)

**Verification**: Grep all YAML configs and ensure every parameter mentioned in prose matches exactly.

---

### 1.2 Appendix D Prompt Isolation Audit - Balance Leakage

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

### 1.3 Learning Dynamic and Acceptance Criterion Ambiguity

**Issue A: Sequential vs Simultaneous Updates**
- Tables show both agents updating in same iteration
- Paper says "iterative best-response" which implies sequential
- Explain that what we mean is that the agents compare iteratively with their own cost in the last iteration, not that they wait for the other to finish updating

**Issue B: "cost delta > 0" vs "statistically significant"**
- Deterministic (Exp1/3): Accept if `new_cost < old_cost`
- Stochastic (Exp2): What exactly?

**Fix**:
- [ ] Define acceptance criterion precisely in Section 3.3:
  - Deterministic mode: Accept if `mean_new_cost < mean_old_cost`
  - Bootstrap mode: Accept if `mean_new_cost < mean_old_cost` (point estimate comparison)
- [ ] Acknowledge limitation: "We use point estimate comparison rather than formal hypothesis testing; this can accept noise-driven improvements"

---

## Priority 3: Writing/Presentation Cleanups

### 3.1 Units Consistency
- [ ] Verify all charts use consistent $ formatting
- [ ] Check appendix tables match chart scales

### 3.3 Claim Discipline
- [ ] Remove or qualify "first to apply LLMs to..." unless literature scan supports it
- [ ] Soften novelty claims to "we demonstrate" rather than "we pioneer"

### 3.5 Appendix Duplication
- [ ] Check final document for repeated blocks
- [ ] Ensure Appendix C appears only once
