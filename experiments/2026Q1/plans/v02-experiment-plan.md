# v0.2 Settlement Optimization Experiment Plan

## Overview

Three phases, 60 total experiments:

- **Phase A:** 24 experiments — complete the 3-run replication for C1-C4 (no retries, `max_policy_proposals: 1`)
- **Phase B:** 1 canary experiment — verify retry mechanism works with `max_policy_proposals: 2`
- **Phase C:** 36 experiments — full 3-run replication of C1-C4 with retries (`max_policy_proposals: 2`)

**Scenario:** Castro Exp2 (`2bank_12tick`), 10 rounds, starting_fraction 0.5
**Models:** GLM (`google-vertex:glm-4.7-maas`), Flash (`google-vertex:gemini-2.5-flash`), Pro (`google-vertex:gemini-2.5-pro`)

---

## Phase A: Complete No-Retry Replication (24 experiments)

We already have 1 run per condition from the initial v0.2 batch. Need 2 more runs each to match wave 1 methodology (3 runs per cell).

### Prompt profiles (same as initial batch):

```yaml
C1-info:
  usr_liquidity_context: {enabled: true}
  usr_balance_trajectory: {enabled: true}

C2-floor:
  usr_liquidity_context: {enabled: true}
  usr_balance_trajectory: {enabled: true}
  sys_settlement_constraint: {enabled: true}

C3-guidance:
  usr_liquidity_context: {enabled: true}
  usr_balance_trajectory: {enabled: true}
  sys_settlement_constraint: {enabled: true}
  usr_worst_case: {enabled: true}

C4-composition:
  usr_liquidity_context: {enabled: true}
  usr_balance_trajectory: {enabled: true}
  sys_settlement_constraint: {enabled: true}
  usr_worst_case: {enabled: true}
  sys_tree_composition: {enabled: true}
```

### Experiment list (max_policy_proposals: 1):

| # | Name | Model | Run | Condition |
|---|------|-------|-----|-----------|
| A1 | Castro C1-info GLM r2 | glm-4.7 | 2 | C1-info |
| A2 | Castro C1-info GLM r3 | glm-4.7 | 3 | C1-info |
| A3 | Castro C1-info Flash r2 | flash | 2 | C1-info |
| A4 | Castro C1-info Flash r3 | flash | 3 | C1-info |
| A5 | Castro C1-info Pro r2 | pro | 2 | C1-info |
| A6 | Castro C1-info Pro r3 | pro | 3 | C1-info |
| A7 | Castro C2-floor GLM r2 | glm-4.7 | 2 | C2-floor |
| A8 | Castro C2-floor GLM r3 | glm-4.7 | 3 | C2-floor |
| A9 | Castro C2-floor Flash r2 | flash | 2 | C2-floor |
| A10 | Castro C2-floor Flash r3 | flash | 3 | C2-floor |
| A11 | Castro C2-floor Pro r2 | pro | 2 | C2-floor |
| A12 | Castro C2-floor Pro r3 | pro | 3 | C2-floor |
| A13 | Castro C3-guidance GLM r2 | glm-4.7 | 2 | C3-guidance |
| A14 | Castro C3-guidance GLM r3 | glm-4.7 | 3 | C3-guidance |
| A15 | Castro C3-guidance Flash r2 | flash | 2 | C3-guidance |
| A16 | Castro C3-guidance Flash r3 | flash | 3 | C3-guidance |
| A17 | Castro C3-guidance Pro r2 | pro | 2 | C3-guidance |
| A18 | Castro C3-guidance Pro r3 | pro | 3 | C3-guidance |
| A19 | Castro C4-comp GLM r2 | glm-4.7 | 2 | C4-composition |
| A20 | Castro C4-comp GLM r3 | glm-4.7 | 3 | C4-composition |
| A21 | Castro C4-comp Flash r2 | flash | 2 | C4-composition |
| A22 | Castro C4-comp Flash r3 | flash | 3 | C4-composition |
| A23 | Castro C4-comp Pro r2 | pro | 2 | C4-composition |
| A24 | Castro C4-comp Pro r3 | pro | 3 | C4-composition |

**Execution:** 2-slot parallel (GLM/Flash parallel, Pro exclusive when needed). ~7 min per Castro experiment → ~1.5 hours for all 24.

---

## Phase B: Canary — Verify Retry Mechanism (1 experiment)

Before committing to 36 experiments, run ONE experiment with `max_policy_proposals: 2` and verify:

| # | Name | Model | Config |
|---|------|-------|--------|
| B1 | Castro C2-floor Flash (retry canary) | flash | max_policy_proposals: 2, C2-floor profile |

**Why Flash C2-floor:** Flash had 61% acceptance under C2, meaning ~7 rejections. With retries, at least some of those should show `validation_attempts: 2`. Flash also runs fastest, so quickest feedback loop.

### Verification checklist after B1 completes:
1. `GET /experiments/{id}/optimization-threads` → check `validation_attempts` field
2. At least one thread should have `validation_attempts: 2` (retry occurred)
3. If retry occurred: check that the retry prompt contains rejection feedback ("settlement rate was X% vs 95% floor")
4. If ALL threads show `validation_attempts: 1` → retries not working, STOP and debug with Nash
5. Verify `max_policy_proposals` is visible in experiment metadata (for reproducibility)

**GATE: Do not proceed to Phase C until B1 verification passes.**

---

## Phase C: Full Retry Replication (36 experiments)

3 runs × 4 conditions × 3 models = 36 experiments, all with `max_policy_proposals: 2`.

### Experiment list:

| # | Name | Model | Run | Condition |
|---|------|-------|-----|-----------|
| C1-C36 | Castro {condition} {model} (retry r{1-3}) | all | 1-3 | C1/C2/C3/C4 |

Same prompt profiles as Phase A, with `max_policy_proposals: 2` added to each.

(Full 36-row table follows same pattern as Phase A but with 3 runs instead of 2.)

**Execution:** ~2.5 hours for all 36. Can overlap with Phase A if canary passes quickly.

---

## Pipeline Configuration

### run-pipeline.py updates needed:
1. Add `max_policy_proposals` field support in experiment creation payload
2. Phase A experiments: `max_policy_proposals: 1` (explicit, even if default)
3. Phase C experiments: `max_policy_proposals: 2`

### experiment-plan.yaml additions:
- 24 Phase A entries (append to existing)
- 1 Phase B canary entry
- 36 Phase C entries

### Naming convention:
- Phase A: `Castro Exp2 — {Model} (C{n}-{name} r{2,3})`
- Phase B: `Castro Exp2 — Flash (C2-floor retry-canary)`
- Phase C: `Castro Exp2 — {Model} (C{n}-{name} retry r{1,2,3})`

---

## Execution Order

1. **Launch Phase A** (all 24, parallel pipeline)
2. **While Phase A runs, launch Phase B canary** (single experiment, manual)
3. **Verify B1** against checklist
4. If B1 passes → **Launch Phase C** (all 36, parallel pipeline)
5. If B1 fails → notify Nash, wait for fix, re-run canary

### Estimated timeline:
- Phase A: ~1.5 hours
- Phase B: ~10 minutes (single Castro experiment)
- Phase C: ~2.5 hours
- **Total: ~4.5 hours** (with overlap: ~3 hours)

---

## Analysis Plan (after all phases complete)

### Key comparisons:
1. **Within no-retry (Phase A):** Do C1-C4 results replicate across 3 runs? What's the variance?
2. **No-retry vs retry (Phase A vs C):** Does `max_policy_proposals: 2` improve outcomes?
3. **Retry impact by model:** Prediction: retries help GLM/Pro more than Flash (more rejections to recover from)
4. **Retry impact by condition:** C2-floor should benefit most (highest rejection rates)
5. **Acceptance rate change:** Does retry increase effective acceptance? (Expected: yes, from ~50% to ~70-80%)
6. **Cost of retries:** More LLM calls per experiment. Track token usage for cost analysis.

### Statistical tests:
- 3 runs per cell enables mean ± std reporting
- Mann-Whitney U for no-retry vs retry comparison (small n, non-parametric)
- Report effect sizes, not just p-values
