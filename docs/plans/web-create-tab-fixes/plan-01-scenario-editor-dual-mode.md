# Plan 01: Scenario Editor — Form + YAML Dual-Mode Editing

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox
**Priority**: P1

## Goal

Replace the YAML-only scenario editor with a **dual-mode editor** that offers both a structured form view and a raw YAML view. Changes in either mode must propagate to the other in real time. Invalid YAML blocks Save & Launch. The Event Timeline Builder's YAML output must match the engine's expected schema (fixing the `trigger/params` → `schedule/flat-fields` format mismatch).

## Problem

1. **The Event Timeline Builder generates invalid YAML** — it outputs `trigger: {type: OneTime, tick: N}` + `params: {from_agent: ..., ...}` but the Rust engine (via `SimulationConfig.from_dict()`) expects `schedule: {type: OneTime, tick: N}` with flat fields (`from_agent`, `to_agent`, `amount`) at the event level. Scenarios with builder-added events fail validation.

2. **The editor is YAML-only** — researchers who aren't YAML-fluent struggle. A form-based mode for scenario parameters (agents, cost rates, simulation settings) would make the tool accessible, while power users still need raw YAML access.

3. **Tab switching loses state** — navigating away from the Create tab resets the editor.

## Web Invariants

- **WEB-INV-3 (Scenario Integrity)**: Every scenario created via the editor MUST validate via `SimulationConfig.from_dict()`.
- **WEB-INV-6 (Dark Mode Only)**: All new form elements use slate/sky/violet palette.

## Files

### Modified

| File | Changes |
|------|---------|
| `web/frontend/src/components/EventTimelineBuilder.tsx` | Fix `eventsToYaml()` to emit `schedule` + flat fields instead of `trigger` + `params`. Fix `yamlToEvents()` to read both formats (backward compat). |
| `web/frontend/src/views/ScenarioEditorView.tsx` | Add dual-mode toggle (Form/YAML). Build structured form for simulation params, agents, cost rates. Two-way sync between form state and YAML string. Validation gate on save. |
| `web/frontend/src/types.ts` | Add types for structured scenario form state if needed. |
| `web/backend/app/scenario_editor.py` | No changes needed — validation already uses `SimulationConfig.from_dict()`. |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/payment_simulator/config/schemas.py` | Engine schema is the source of truth |

## Phase 1: Fix Event YAML Format + Dual-Mode Editor

**Est. Time**: 4-6h

### Backend

No backend changes. The validator already uses the canonical `SimulationConfig.from_dict()` path.

### Frontend

#### 1. Fix EventTimelineBuilder YAML Output

In `EventTimelineBuilder.tsx`, fix `eventsToYaml()`:

**Before** (broken):
```yaml
scenario_events:
  - type: DirectTransfer
    trigger:
      type: OneTime
      tick: 5
    params:
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500000
```

**After** (matches engine schema):
```yaml
scenario_events:
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 500000
    schedule:
      type: OneTime
      tick: 5
```

Each event type has different fields at the top level. The mapping from event type → flat fields is already defined in `PARAM_FIELDS`. Use that to emit flat fields instead of wrapping in `params:`.

Also update `yamlToEvents()` to parse both `trigger` (legacy) and `schedule` (correct) keywords, and both `params` (legacy nested) and flat field layouts.

#### 2. Build Structured Form Mode

Add a `mode` toggle to `ScenarioEditorView`: **📋 Form** | **📝 YAML**

**Form mode** renders structured inputs for:
- **Simulation**: `ticks_per_day` (number), `num_days` (number), `rng_seed` (number)
- **Cost Rates**: `liquidity_cost_bps` (number), `delay_cost_per_tick` (number), `deadline_penalty` (number), `eod_penalty` (number)
- **Agents** (dynamic list, add/remove):
  - `id` (text), `opening_balance` (number), `liquidity_pool` (number)
  - Arrival config: `rate_per_tick` (number), distribution type (select), `mean` (number), `std_dev` (number)
  - Counterparty weights (dynamic key-value pairs: agent_id → weight)
  - `deadline_range` (two numbers: min, max)
- **LSM Config** (optional toggle): `enable_bilateral` (checkbox), `enable_cycles` (checkbox)
- **Events**: The existing EventTimelineBuilder component (unchanged)

**Two-way sync logic:**
- Form → YAML: On any form field change, serialize the form state to YAML string via `js-yaml` and update the YAML state. This is the **source of truth** in form mode.
- YAML → Form: On switching from YAML mode to Form mode, parse the YAML via `js-yaml` and populate form state. If YAML is invalid, show an error banner and stay in YAML mode (user must fix YAML before switching to form).
- YAML mode: Direct textarea editing (current behavior). On switching back to Form mode, re-parse.

**State management:**
- Maintain a single `yaml` string as the canonical state (same as now).
- The form is a *view* that reads from and writes to this YAML string.
- When in form mode, each form field change triggers: update form state → serialize to YAML → set `yaml` state.
- When in YAML mode, textarea edits update `yaml` state directly.
- Mode switch from YAML → Form: parse `yaml`, populate form. If parse fails, block switch + show error.

**Validation gate:**
- "Save & Launch" button is disabled unless `valid === true` (already implemented).
- Add: Validate button auto-triggers on mode switch to catch issues early.

#### 3. State Persistence Across Tab Switches

Lift scenario editor state up to `App.tsx` (or a context) so it survives tab navigation. Options:
- **Simple**: Store `{yaml, scenarioName, scenarioDesc, valid}` in App-level state, pass as props.
- **Context**: Create `ScenarioEditorContext` — overkill for now.

Go with the simple approach: App stores the editor state, passes it down.

### Tests

**Backend**: No new backend tests needed (validator unchanged).

**Frontend**:
- `npx tsc -b` must pass with zero errors
- `npm run build` must succeed

**New unit-testable logic** (if we extract to utils):
- `eventsToYaml()` produces correct format for each event type
- `yamlToEvents()` parses both legacy and correct formats
- Round-trip: events → YAML → events produces identical data

### Verification

```bash
cd web/frontend && npx tsc -b && npm run build
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short \
  --ignore=../web/backend/tests/test_real_llm.py \
  --ignore=../web/backend/tests/test_e2e_models.py
```

### UI Test Protocol

```
Protocol: Scenario Editor Dual-Mode
Wave: Create Tab Fixes

1. Open http://localhost:5173
2. Click ✏️ Create tab → Scenario sub-tab
3. VERIFY: Default is Form mode. See structured inputs for Simulation, Cost Rates, Agents.
4. Change ticks_per_day to 8 in form.
5. VERIFY: YAML textarea (if visible in split view or on switch) shows ticks_per_day: 8.
6. Switch to YAML mode.
7. VERIFY: YAML contains ticks_per_day: 8 and all form values.
8. Edit YAML: change num_days to 3.
9. Switch back to Form mode.
10. VERIFY: num_days field shows 3.
11. In YAML mode, type invalid YAML (e.g., remove a colon).
12. Try switching to Form mode.
13. VERIFY: Error banner shown, stays in YAML mode.
14. Fix YAML. Click Validate.
15. VERIFY: Valid scenario, summary appears.
16. Use Event Timeline Builder: add a DirectTransfer event at tick 5.
17. VERIFY: YAML shows `schedule: {type: OneTime, tick: 5}` and `from_agent:` at event level (NOT `trigger:` or `params:`).
18. Click Validate.
19. VERIFY: ✅ Valid, features include "Event: DirectTransfer".
20. Click Save & Launch.
21. VERIFY: Game starts with correct agent count and tick count.
22. Navigate to another tab and back to Create → Scenario.
23. VERIFY: Previous scenario state is preserved (name, YAML, description).

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] All existing 227+ backend tests still pass
- [ ] Frontend TypeScript compiles clean
- [ ] Frontend builds successfully
- [ ] Event Timeline Builder produces engine-compatible YAML
- [ ] Form ↔ YAML sync works bidirectionally
- [ ] Invalid YAML blocks mode switch to Form
- [ ] Scenario state persists across tab switches
- [ ] UI test protocol passes
