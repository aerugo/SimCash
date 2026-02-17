# UX Fixes Meta-Plan

**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`
**Source**: UX First Impressions Report (`docs/reports/ux-first-impressions-2026-02-17.md`)

## Overview

10 plans addressing UX issues identified in the first-impressions report. All changes target the `web/` directory (frontend + backend for Plan 4 only).

## Dependency Graph

```
Plan 1 (remove-duplicate-launch) ─── no deps
Plan 2 (day-context-reasoning)   ─── no deps
Plan 3 (onboarding-explainer)    ─── no deps
Plan 4 (custom-scenario-game)    ─── no deps (but Plan 1 should go first to avoid stale UI)
Plan 5 (game-completion-summary) ─── no deps
Plan 6 (event-summary-collapse)  ─── no deps
Plan 7 (cost-rate-tooltips)      ─── no deps
Plan 8 (empty-state-guidance)    ─── no deps
Plan 9 (balance-chart-improve)   ─── no deps
Plan 10 (hide-mock-label)        ─── depends on Plan 2 (both touch reasoning section)
```

All plans are largely independent. Plan 10 should follow Plan 2 since both modify the reasoning display section of `GameView.tsx`.

## Recommended Implementation Order

### Wave 1 — Critical & Quick Wins (1-2 hours)
| Plan | Name | Effort | Files |
|------|------|--------|-------|
| 1 | remove-duplicate-launch | Low | HomeView.tsx |
| 7 | cost-rate-tooltips | Low | HomeView.tsx |
| 10 | hide-mock-label | Trivial | GameView.tsx |
| 8 | empty-state-guidance | Low | GameView.tsx |

**Rationale**: All low-effort, high-impact fixes. Plans 1+7 both touch HomeView so do them together. Plans 10+8 both touch GameView.

### Wave 2 — Medium Complexity (2-3 hours)
| Plan | Name | Effort | Files |
|------|------|--------|-------|
| 2 | day-context-reasoning | Medium | GameView.tsx |
| 6 | event-summary-collapse | Low | GameView.tsx + new component |
| 5 | game-completion-summary | Low | GameView.tsx + new component |
| 9 | balance-chart-improve | Low | GameView.tsx |

**Rationale**: All GameView changes. Plan 2 is the most impactful UX fix in this wave.

### Wave 3 — New Features (3-4 hours)
| Plan | Name | Effort | Files |
|------|------|--------|-------|
| 3 | onboarding-explainer | Medium | HomeView.tsx + new component |
| 4 | custom-scenario-game | Medium | Backend + Frontend |

**Rationale**: These add new functionality. Plan 4 is the only one with backend changes.

## Effort Summary

| Effort | Plans | Est. Total |
|--------|-------|------------|
| Trivial | 10 | 15 min |
| Low | 1, 5, 6, 7, 8, 9 | 3 hours |
| Medium | 2, 3, 4 | 4 hours |
| **Total** | | **~7 hours** |

## Testing Strategy

### Unit Tests (per plan)
Each plan includes specific test files using Vitest + React Testing Library:
- Component rendering tests
- User interaction tests (click, toggle)
- Conditional visibility tests

### Integration Tests
- Plan 4 (custom-scenario-game): Backend pytest tests for inline config
- Plans 2+10: Combined GameView reasoning tests

### Visual Verification
After each wave, manual check:
```bash
# Start backend
cd web/backend && $HOME/Library/Python/3.9/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8642

# Start frontend
cd web/frontend && npm run dev
```

Walk through:
1. **Wave 1**: Verify Game tab has no Launch button, tooltips work, mock badge subtle, empty state shows
2. **Wave 2**: Click through days to verify reasoning changes, event summary collapses, completion panel shows, chart improved
3. **Wave 3**: How It Works section collapses, Custom Builder can start games

### Regression
Run full test suite after each wave:
```bash
cd web/frontend && npx vitest run
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest web/backend/tests/ -v
```
