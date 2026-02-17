# Scenario Editor — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 4, Items 13-14

## Goal

Let researchers create custom scenarios in the browser: a YAML editor with live validation, an event timeline builder for scheduling custom events, and the ability to save and share custom scenarios.

## Web Invariants

- **WEB-INV-3**: Scenario Integrity — custom scenarios MUST validate via `SimulationConfig.from_dict()`
- **WEB-INV-4**: Cost Consistency — custom scenarios produce correct costs
- **WEB-INV-5**: Auth Gate — custom scenarios saved per user

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/views/ScenarioEditorView.tsx` | Full scenario editor: YAML editor + event builder + validation |
| `web/frontend/src/components/YamlEditor.tsx` | Code editor for YAML with syntax highlighting |
| `web/frontend/src/components/EventTimelineBuilder.tsx` | Visual event scheduling on a tick timeline |
| `web/frontend/src/components/ScenarioValidator.tsx` | Live validation feedback panel |
| `web/backend/tests/test_scenario_editor.py` | Tests for custom scenario validation + persistence |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/main.py` | Add `/api/scenarios/custom` CRUD endpoints |
| `web/backend/app/storage.py` | Save/load custom scenarios per user |
| `web/frontend/src/App.tsx` | Add Scenario Editor route |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: custom scenario CRUD + validation | 3h | 10 tests |
| 2 | Frontend: YAML editor with live validation | 4h | tsc + build |
| 3 | Frontend: Event timeline builder | 4h | tsc + build |
| 4 | Integration: save/load/launch custom scenarios | 2h | 4 tests + UI protocol |

## Phase 1: Backend — Custom Scenario CRUD

### Endpoints

```
POST   /api/scenarios/custom           → create (validate YAML, save to storage)
GET    /api/scenarios/custom            → list user's custom scenarios
GET    /api/scenarios/custom/{id}       → get one
PUT    /api/scenarios/custom/{id}       → update
DELETE /api/scenarios/custom/{id}       → delete
POST   /api/scenarios/validate          → validate without saving (already in Plan 01)
```

### Storage

Custom scenarios stored in GCS: `gs://simcash-data/users/{uid}/scenarios/{id}.yaml`
Index in: `gs://simcash-data/users/{uid}/scenarios/index.json`

### Validation Pipeline

```python
def validate_scenario(yaml_string: str) -> ValidationResult:
    """Full validation pipeline."""
    # 1. Parse YAML syntax
    # 2. Check required fields (agents, ticks_per_day, etc.)
    # 3. Load via SimulationConfig.from_dict() — catches engine-level errors
    # 4. Run 1 tick to verify engine accepts it
    # 5. Return: valid, warnings, errors
```

### Tests

1. `test_create_valid_scenario` — valid YAML saves, returns id
2. `test_create_invalid_yaml_syntax` — bad YAML → 400 with parse error
3. `test_create_missing_required_fields` — no agents → clear error
4. `test_create_invalid_config` — SimulationConfig rejects → clear error
5. `test_list_user_scenarios` — returns only user's scenarios
6. `test_get_scenario` — returns saved YAML
7. `test_update_scenario` — modifies existing
8. `test_delete_scenario` — removes from storage
9. `test_launch_custom_scenario` — POST /api/games with custom scenario id → game runs
10. `test_custom_scenario_with_events` — scenario with DirectTransfer event validates

## Phase 2: YAML Editor

**YamlEditor.tsx**: Monaco-style code editor (use `@monaco-editor/react` or a lighter alternative):
- YAML syntax highlighting
- Line numbers
- Error underlines from validation
- Template insertion (start from template)

**ScenarioValidator.tsx**: Side panel showing:
- ✅ YAML syntax valid
- ✅ Required fields present
- ✅ Engine accepts configuration
- ⚠️ Warnings (e.g., "25 days with 5 agents may be slow")
- ❌ Errors with line numbers

Templates available:
- "Basic 2-bank" — minimal working scenario
- "Stochastic arrivals" — Poisson/LogNormal
- "Crisis with events" — includes DirectTransfer events
- "LSM enabled" — bilateral + multilateral offsetting
- "Asymmetric agents" — different configs per agent

## Phase 3: Event Timeline Builder

**EventTimelineBuilder.tsx**: Visual interface for scheduling scenario events:

```
Tick: 0    5    10   15   20   25
      |    |    |    |    |    |
      ─────────────────────────────
                ▼         ▼
              Liq.      Rate
              Shock     Change
```

- Horizontal tick axis
- Click to add event at a tick
- Event type picker: DirectTransfer, CollateralAdjustment, GlobalArrivalRateChange, AgentArrivalRateChange, CounterpartyWeightChange, DeadlineWindowChange
- Configure event parameters in a form
- Drag to reposition events
- Output: YAML `scenario_events` section, merged into the main YAML

## Phase 4: Integration

Connect editor to game creation: "Validate & Launch" button that:
1. Validates the YAML
2. Saves to user's custom scenarios
3. Creates a game with the custom config
4. Navigates to GameView

### UI Test Protocol

```
Protocol: W4-Scenario-Editor
Wave: 4

1. Navigate to Scenario Editor
2. VERIFY: Empty editor with template picker
3. Select "Basic 2-bank" template
4. VERIFY: YAML populated, validation shows ✅
5. Change num_agents to 3, add a third agent config
6. VERIFY: Validation updates live, still ✅
7. Remove required field (ticks_per_day)
8. VERIFY: Validation shows ❌ with clear error message
9. Restore field, add a DirectTransfer event at tick 10
10. VERIFY: Event appears in timeline builder
11. VERIFY: Validation still ✅
12. Click "Validate & Launch"
13. VERIFY: Game starts with 3 agents
14. Step to day where tick 10 occurs
15. VERIFY: Event visible in event log (balance change from DirectTransfer)
16. Go back to Editor
17. VERIFY: Saved scenario appears in "My Scenarios" list

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] YAML editor with syntax highlighting and live validation
- [ ] All 7 event types configurable in timeline builder
- [ ] Custom scenarios validate through full pipeline (YAML → SimulationConfig → engine)
- [ ] Custom scenarios saved per user (GCS)
- [ ] Custom scenarios can launch games
- [ ] WEB-INV-3: every custom scenario passes engine validation before saving
