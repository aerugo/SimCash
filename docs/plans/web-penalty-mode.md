# Penalty Mode Frontend Support — Development Plan

**Status**: Draft
**Date**: 2026-02-19
**Branch**: `feature/interactive-web-sandbox` (merge `feature/penalty-mode` first)
**Depends on**: `feature/penalty-mode` (backend, by Dennis)

## Goal

Surface the new `PenaltyMode` (fixed vs rate-based) for deadline and EOD penalties in the scenario configuration UI, result displays, and in-app documentation. Users should be able to toggle between a flat cent amount and a bps-of-transaction-amount rate, with clear explanations of what each means.

## Web Invariants

- **WEB-INV-3 (Scenario Integrity)**: Config produced by the form must load via `SimulationConfig.from_dict()` without error. Both `fixed` and `rate` modes must serialize correctly.
- **WEB-INV-4 (Cost Consistency)**: Displayed cost breakdowns must still sum correctly regardless of penalty mode.

## Files

### Modified

| File | Changes |
|------|---------|
| `web/frontend/src/types.ts` | Add `PenaltyMode` type, update `cost_rates` fields |
| `web/frontend/src/components/ScenarioForm.tsx` | Replace `NumberField` for penalties with `PenaltyModeField` component |
| `web/frontend/src/components/AgentDetailModal.tsx` | Format penalty display with mode label |
| `web/backend/docs/cost-model.md` | Update deadline/EOD sections for both modes, remove "Castro" references |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Already done by Dennis on `feature/penalty-mode` |
| `web/backend/app/` | Backend already handles both modes via Pydantic |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Merge penalty-mode, types + form UI | 1h | tsc + build |
| 2 | Display formatting + docs update | 30m | tsc + build |

## Phase 1: Types & Form UI

### Merge
- Merge `feature/penalty-mode` into `feature/interactive-web-sandbox` (or rebase)

### Types (`types.ts`)

Add:
```typescript
type PenaltyMode =
  | { mode: 'fixed'; amount: number }
  | { mode: 'rate'; bps_per_event: number };
```

Update `cost_rates` in both `ScenarioConfig` and `ScenarioFormData`:
```typescript
cost_rates: {
  liquidity_cost_per_tick_bps: number;
  delay_cost_per_tick_per_cent: number;
  deadline_penalty: PenaltyMode;
  eod_penalty: PenaltyMode;  // rename from eod_penalty_per_transaction
};
```

### YAML Parsing (`ScenarioForm.tsx`)

Update `parseYamlToForm()` to handle three shapes:
- Bare integer → `{ mode: 'fixed', amount: value }`
- Object with `mode: 'fixed'` → pass through
- Object with `mode: 'rate'` → pass through

Update `formToYaml()` to serialize `PenaltyMode` objects (not bare numbers) into the YAML output. Also emit `eod_penalty` (not the old `eod_penalty_per_transaction` alias).

### Form Component

New `PenaltyModeField` component:

```
┌─ Deadline Penalty ──────────────────────┐
│  [Fixed ▾]  [$500.00 ___________]       │  ← dropdown + amount in dollars
│  — or —                                 │
│  [Rate ▾]   [50.0 bps __________]       │  ← dropdown + bps input
└─────────────────────────────────────────┘
```

Concretely: a small toggle/select (`Fixed` / `Rate`) followed by the appropriate input field. When switching modes, carry over a sensible default (e.g. switching to rate → 50 bps, switching to fixed → 50000 cents).

Tooltip: "Fixed: flat fee in cents regardless of payment size. Rate: basis points of the transaction amount — scales with payment value."

### Validation

- Fixed: `amount` must be a non-negative integer
- Rate: `bps_per_event` must be non-negative
- Frontend validation only (backend validates too)

### Verification

```bash
cd web/frontend && npx tsc -b && npm run build
```

UI check:
1. Open scenario form
2. Verify deadline & EOD penalty show mode toggle
3. Switch to Rate mode, enter 50 bps
4. Switch back to Fixed, verify amount preserved
5. Export YAML — verify correct `PenaltyMode` structure
6. Import YAML with bare integer — verify reads as Fixed
7. Import YAML with `{ mode: rate, bps_per_event: 50 }` — verify reads as Rate

## Phase 2: Display Formatting & Docs

### Cost Display (`AgentDetailModal.tsx`)

Where penalty costs appear in results, no changes needed to the cost number itself (it's already an i64 from the engine). But if we show the configured penalty rate anywhere in results, format as:
- Fixed: `$500.00 (fixed)`
- Rate: `50.0 bps`

### In-App Docs (`cost-model.md`)

Update sections 3 and 4:

**Section 3 — Deadline Penalty**: Replace the current "flat fee" description. Explain both modes:
- Fixed: flat amount in cents, same regardless of transaction size
- Rate: basis points of the transaction amount, scales with value
- Note that rate mode uses the **remaining unsettled amount** for EOD penalties

**Section 4 — End-of-Day Penalty**: Same dual-mode explanation.

**Section "The Ordering Constraint"**: Remove "Castro et al. require" — replace with a general explanation that the cost ordering `liquidity < delay < penalty` is important for well-behaved incentives. Note that rate-mode penalties help maintain this ordering across different transaction sizes (which is the whole motivation). Mention the backend's cost-ordering validation warning.

**Remove all "Castro" references** from the doc.

### Verification

```bash
cd web/frontend && npx tsc -b && npm run build
```

Browse docs page → The Cost Model → verify updated content renders correctly.

## Success Criteria

- [ ] TypeScript compiles clean
- [ ] Frontend builds successfully
- [ ] Scenario form handles fixed/rate toggle for both penalty fields
- [ ] YAML round-trip preserves PenaltyMode correctly (fixed, rate, bare int import)
- [ ] Cost model docs updated with both modes, no Castro references
- [ ] Existing scenarios with bare integers still load correctly (backwards compat)
