# Create Tab Fixes — Development Plan

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox

## Goal

Fix all bugs and UX gaps discovered during the Create tab playtest (2026-02-18). Five issues, five one-phase plans, in priority order.

## Context

Playtest notes: `memory/playtest-editors-2026-02-18.md`

## Plans

| # | Plan | Priority | Est. | Key Change |
|---|------|----------|------|------------|
| 01 | [Scenario Editor Dual-Mode](plan-01-scenario-editor-dual-mode.md) | **P1** | 4-6h | Form + YAML dual-mode editing with bidirectional sync. Fixes event builder YAML format (`trigger/params` → `schedule/flat`). State persistence. |
| 02 | [Policy Validator Rust Compat](plan-02-policy-validator-rust-compat.md) | P2 | 2h | Better error messages, compound expression support (`and`/`or`/`not`), all Value types. |
| 03 | [Policy Save Fix](plan-03-policy-save-fix.md) | P2 | 2h | Save to backend, stay on tab, load saved dropdown. |
| 04 | [Starting Policy Selection](plan-04-starting-policy-selection.md) | P2 | 4h | Per-agent starting policy picker in Game Setup. Connects Policy Editor → Game. |
| 05 | [Editor State Persistence](plan-05-editor-state-persistence.md) | P3 | 1.5h | Lift state to App level so tab switches don't reset editors. |

**Total estimated**: ~14-16h

## Execution Order

1. **Plan 01** first (P1, fixes broken functionality)
2. **Plans 02-03** can run in parallel (independent backends)
3. **Plan 04** after 03 (needs custom policy save endpoint)
4. **Plan 05** last or alongside 01 (pure frontend, low risk)

Plan 05 is partially subsumed by Plan 01 (which already lifts state for the scenario editor). Plan 05 adds policy editor persistence.

## Pre-Deploy Verification

```bash
# All backend tests
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short \
  --ignore=../web/backend/tests/test_real_llm.py \
  --ignore=../web/backend/tests/test_e2e_models.py

# Frontend
cd web/frontend && npx tsc -b && npm run build
```

## Success Criteria

- [ ] Event Timeline Builder produces valid YAML (engine-compatible)
- [ ] Scenario Editor has Form + YAML modes with bidirectional sync
- [ ] Policy validator gives helpful errors for wrong formats
- [ ] Policy Save stays on Policy tab, persists to backend
- [ ] Starting policies can be assigned per-agent in Game Setup
- [ ] Editor state survives tab navigation
- [ ] All existing 227+ tests still pass
- [ ] All 5 UI test protocols pass
