# Bootstrap Optimization Fixes - Development Plan

**Status**: In Progress
**Created**: 2026-02-22
**Branch**: `feature/interactive-web-sandbox`

## Summary

Fix 5 issues preventing the LLM optimization loop from converging: verify deployment timing, add diagnostic logging for fraction changes & rejection history, relax CV thresholds for crisis scenarios, and fix the REST path policy injection bug.

## Critical Invariants to Respect

- **INV-9**: Policy Evaluation Identity — `_build_ffi_config()` is the single path for policy→engine; any logging must not alter this path
- **INV-11**: Agent Isolation — diagnostic logs must not leak cross-agent info into prompts
- **INV-13**: Bootstrap Seed Hierarchy — no changes to seed logic

## Current State Analysis

Game `54ca8546` (Lehman Month, 25 days, revision `simcash-00117-6mq`) produced 0 acceptances across ~150 bootstrap evaluations. Three failure modes observed:

1. **Most agents (4/6)**: `cost_a == cost_b` exactly — LLM changes decision tree but not `initial_liquidity_fraction`, so costs don't change
2. **LARGE_BANK_1/2**: LLM increases fraction (wrong direction) every round despite rejection memory fix
3. **Two valid improvements killed by CV threshold**: LARGE_BANK_2 delta=+545k (CV=0.638>0.5), MID_BANK_2 delta=+188k (CV=1.652>0.5)

### Files to Modify
| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/game.py` | No fraction logging, no rejection count logging, REST path missing inject | Add logging (P2, P3), add inject call (P5) |
| `web/backend/app/game.py` | Hardcoded profile defaults | Auto-detect crisis → use aggressive profile (P4) |
| `web/backend/app/main.py` | REST `auto_run_game` missing inject | Add inject after optimize (P5) |

## Phase Overview

| Phase | Description | Risk | Files |
|-------|-------------|------|-------|
| 1 | Verify deployment timing | None (read-only) | logs only |
| 2 | Log proposed vs current fraction | Low | `game.py` |
| 3 | Log rejection history count reaching LLM | Low | `game.py`, `streaming_optimizer.py` |
| 4 | Auto-detect crisis scenarios → aggressive bootstrap profile | Medium | `game.py` |
| 5 | Fix REST path `_inject_policies_into_orch()` | Low | `main.py` |

## Phase 1: Verify Deployment Timing

**Goal**: Confirm whether game `54ca8546` was launched on revision `simcash-00117-6mq` (with cost relabeling fix) or an earlier revision.

**Method**: Check Cloud Run logs for the game creation timestamp vs revision deploy time.

**Success Criteria**:
- [ ] Know definitively if cost relabeling was active for this game

## Phase 2: Log Proposed vs Current Fraction

**Goal**: Add a log line in `_run_real_bootstrap()` showing `current_fraction → proposed_fraction` per agent so we can see if the LLM is actually changing the lever.

**Deliverables**:
- Log line: `"Bootstrap for {aid}: fraction {current:.3f} → {proposed:.3f}, tree_changed={bool}"`

**Success Criteria**:
- [ ] Can see fraction changes in Cloud Run logs per agent per day

## Phase 3: Log Rejection History Reaching LLM

**Goal**: Verify the LLM sees rejected policies. Add log showing count of rejected policies in the iteration history passed to the prompt builder.

**Deliverables**:
- Log line in `_real_optimize()` or `streaming_optimizer.py`: `"Optimizing {aid}: {n} rejected policies in history"`

**Success Criteria**:
- [ ] Can confirm rejection history is non-empty after day 2+

## Phase 4: Auto-Detect Crisis → Aggressive Bootstrap Profile

**Goal**: Crisis scenarios (Lehman-type with market events) have high cost variance. The "moderate" CV threshold (0.5) kills valid improvements. Auto-detect crisis scenarios and default to "aggressive" profile (CV threshold 1.0).

**Design**:
- In `Game.__init__`, detect crisis features: `scenario_events` with shock/failure/crisis keywords, or `num_days > 10`
- If crisis detected AND no explicit profile set, default to "aggressive" instead of "moderate"
- Can also just remove the CV check entirely — the CI significance check already handles noise

**Key Decision**: Prefer removing CV check over auto-detection. The CI check (`require_significance` + `ci_lower > 0`) is the statistically correct way to handle noise. CV is a redundant, overly conservative gate. The paper's pipeline doesn't use CV.

**Deliverables**:
- Remove CV threshold check from `_run_real_bootstrap()`
- OR: change default profile to "aggressive" for scenarios with events

**Success Criteria**:
- [ ] Valid improvements (positive delta, significant CI) are accepted
- [ ] Bad proposals still rejected (negative delta or non-significant)

## Phase 5: Fix REST Path Policy Injection

**Goal**: Add `game._inject_policies_into_orch()` in the HTTP `auto_run_game()` endpoint after `optimize_policies()`, matching the websocket path.

**Deliverables**:
- Add inject call in `main.py` `auto_run_game()` after `optimize_policies()` for `every_scenario_day` mode

**Success Criteria**:
- [ ] REST-based auto-run applies updated policies between days

## Testing Strategy

- **Manual**: Launch new Lehman Month after deploy, observe bootstrap logs for fraction changes and acceptances
- **Unit**: No new unit tests needed (logging changes only for P2-P3, P4 is threshold removal, P5 is 3-line fix)

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| Phase 3 | Pending | |
| Phase 4 | Pending | |
| Phase 5 | Pending | |
