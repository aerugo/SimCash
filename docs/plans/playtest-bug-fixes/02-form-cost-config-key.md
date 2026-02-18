# Bug Fix: Form Mode Doesn't Parse Cost Config

## Problem

The Scenario Editor's Form mode reads cost rates from `doc.cost_rates` (line 55 of `ScenarioForm.tsx`), and the YAML templates also use `cost_rates`. This is correct — the engine schema field IS `cost_rates`.

However, users writing raw YAML might use `cost_config` (as I did in the playtest), which silently fails — the engine ignores unrecognized keys and uses defaults.

The real fix has two parts:
1. The Form already uses the correct key (`cost_rates`). ✅ No fix needed for Form→YAML.
2. The YAML→Form parsing reads `cost_rates` correctly. ✅ Working.

**Root cause of the playtest issue**: I wrote `cost_config:` in the YAML instead of `cost_rates:`. The engine silently ignored it. The Form mode showed defaults because the YAML simply didn't have `cost_rates`.

## Fix

### Phase 1: Add YAML validation warning for unknown top-level keys

**File: `web/backend/app/scenario_editor.py`**

In the `validate_scenario` endpoint, after Pydantic parsing succeeds, check for unrecognized top-level keys in the raw YAML and return warnings:

```python
KNOWN_TOP_KEYS = {"simulation", "agents", "cost_rates", "lsm_config", "scenario_events", 
                  "queue_config", "rtgs_config", "priority_escalation", "policy_feature_toggles"}

raw_keys = set(yaml_doc.keys())
unknown = raw_keys - KNOWN_TOP_KEYS
warnings = [f"Unknown key '{k}' will be ignored. Did you mean 'cost_rates'?" 
            for k in unknown if k.startswith("cost")]
```

Return warnings alongside validation result so the frontend can display them.

### Phase 2: Frontend displays warnings

**File: `web/frontend/src/views/ScenarioEditorView.tsx`**

Show warnings in the validation panel as amber/yellow items below the green "Valid" badge. Users see: "⚠️ Unknown key 'cost_config' — did you mean 'cost_rates'?"

## Tests

- Submit YAML with `cost_config:` → validation succeeds but returns warning about unknown key
- Submit YAML with `cost_rates:` → no warnings
- Frontend renders warnings in amber

## Scope

- **Files**: 1 backend, 1 frontend
- **Effort**: 20 minutes
- **Risk**: Low — additive warning, doesn't change validation behavior
