# Accept/Reject Display - Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`
**Depends on**: `web-bootstrap-evaluation` (Plan 3)

## Summary

Show when policy proposals are accepted vs rejected and why. Currently all proposals are silently accepted. Need visual distinction, rejection reasons (CV too high, delta negative, CI crosses zero), and history of accepted/rejected per agent. This plan focuses on the frontend display; the backend evaluation logic comes from Plan 3.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all delta/cost values in integer cents; display in dollars
- **INV-2**: Determinism — display is read-only, doesn't affect simulation
- **INV-GAME-2**: Agent Isolation — each agent's accept/reject history shown separately
- **INV-GAME-3**: Bootstrap Identity — display matches experiment runner's acceptance criteria labels

## Current State Analysis

### What Exists (after Plan 3)

1. **Backend**: `optimize_policies()` returns `evaluation` dict with `accepted`, `rejection_reason`, `delta_sum`, `cv`, `ci_lower`, `ci_upper` per agent.
2. **Frontend**: `GameView.tsx` shows reasoning text. `GameOptimizationResult` type has `accepted: boolean` but no visual distinction.
3. **Types**: `EvaluationMetadata` interface (from Plan 3 Phase 4).

### What's Missing

- No visual distinction between accepted/rejected in reasoning cards
- No rejection reason display
- No detailed delta table view
- No policy history timeline showing accept/reject pattern over days
- No color coding in fraction chart for rejected proposals

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/frontend/src/components/GameView.tsx` | Shows reasoning text only | Add accept/reject badges, colored cards |
| `web/frontend/src/components/ReasoningCard.tsx` | Does not exist | New component for rich reasoning display |
| `web/frontend/src/components/PolicyTimeline.tsx` | Does not exist | Accept/reject timeline per agent |
| `web/frontend/src/components/DeltaDetailModal.tsx` | Does not exist | Detailed delta table modal |

## Phase Overview

| Phase | Description | Key Deliverables |
|-------|-------------|-----------------|
| 1 | Backend: Ensure acceptance criteria in game state | delta_sum, cv, ci, accepted, rejection_reason in API |
| 2 | Frontend: Rejection badges on reasoning cards | ✓/✗ badges, colored borders, rejection reason text |
| 3 | Frontend: Detailed rejection tooltip/modal | Delta table, CV value, threshold comparison |
| 4 | Frontend: Policy history timeline | Accept (green) vs reject (red) timeline per agent |
| 5 | Polish and test | Animations, accessibility, edge cases |
