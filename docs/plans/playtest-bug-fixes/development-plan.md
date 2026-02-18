# Playtest Bug Fixes — Master Plan

5 issues found during the 2026-02-18 end-to-end playtest of the Scenario Editor, Event Timeline Builder, and Starting Policy features.

## Priority Order

| # | Bug | Severity | Effort | Plan |
|---|-----|----------|--------|------|
| 1 | Event field name mismatch | **P0** — events fail validation | 15 min | [01-event-field-names.md](01-event-field-names.md) |
| 2 | Unknown YAML keys silently ignored | **P1** — confusing for users | 20 min | [02-form-cost-config-key.md](02-form-cost-config-key.md) |
| 3 | Validation summary wrong costs | **N/A** — duplicate of #2 | 0 min | [03-validation-summary-costs.md](03-validation-summary-costs.md) |
| 4 | Static "fraction=1.000" banner | **P2** — cosmetic | 10 min | [04-starting-policy-banner.md](04-starting-policy-banner.md) |
| 5 | Save & Launch lacks game settings | **P2** — feature gap | 1-2 hrs | [05-save-launch-starting-policies.md](05-save-launch-starting-policies.md) |

## Implementation Waves

### Wave A: Critical fixes (30 min)
- **#1**: Fix `PARAM_FIELDS` mapping in EventTimelineBuilder.tsx + remove fake event types
- **#2**: Add unknown-key warnings to validation endpoint + frontend display

### Wave B: Polish (1-2 hrs)
- **#4**: Dynamic banner text in GameView.tsx
- **#5**: Extract GameSettingsPanel, wire into ScenarioEditorView

## Key Findings

1. **Event builder field names were never tested against the engine schema** — they were written from memory/intuition, not from the reference docs. Every event type except `DirectTransfer` had at least one wrong field name.

2. **The YAML key is `cost_rates`, not `cost_config`** — the engine's Pydantic model uses `cost_rates`, matching the reference docs. Writing `cost_config` is silently ignored. This is a "silent failure" pattern that should be caught by validation warnings.

3. **`LiquidityInjection` and `CreditLimitChange` don't exist** in the engine — they were added to the frontend event builder speculatively. They should be removed until the Rust engine supports them.

4. **The starting policy fix (fraction slider) is working correctly** — Day 0 showed the right fractions, and the optimization trajectories were clearly influenced by starting positions. The Game Complete banner showed A: 0.276, B: 0.174, C: 0.141, D: 0.191 after starting from 0.30, 1.00, 0.35, 0.70.
