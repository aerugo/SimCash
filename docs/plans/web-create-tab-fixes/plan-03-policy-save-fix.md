# Plan 03: Policy Save — Fix Navigation + Persist to Backend

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox
**Priority**: P2

## Goal

Fix the Policy Editor's Save button: it should save the policy to the backend, show a success confirmation, and **stay on the Policy Editor tab** (not navigate to Saved Scenarios). Saved policies should be retrievable via the "Load saved…" dropdown.

## Problem

1. Clicking Save in the Policy Editor navigates to the Saved Scenarios page (wrong tab).
2. The save is currently client-side only (`setSavedPolicies` in React state) — policies are lost on page reload.
3. No backend endpoint exists for saving custom policies.

## Web Invariants

- **WEB-INV-6 (Dark Mode Only)**: Success toast uses dark theme.

## Files

### New

| File | Purpose |
|------|---------|
| (none — add endpoint to existing `policy_editor.py`) | |

### Modified

| File | Changes |
|------|---------|
| `web/backend/app/policy_editor.py` | Add `POST /api/policies/custom` (save), `GET /api/policies/custom` (list), `GET /api/policies/custom/{id}` (get) endpoints. In-memory store (like scenarios). |
| `web/frontend/src/views/PolicyEditorView.tsx` | Fix `handleSave` to POST to backend. Show success toast. Do NOT navigate away. Load saved policies in dropdown via `GET /api/policies/custom`. |
| `web/backend/tests/test_policy_editor.py` | Add tests for save/list/get endpoints. |

### NOT Modified

| File | Why |
|------|-----|
| `web/frontend/src/views/ScenarioEditorView.tsx` | Separate editor |
| `web/frontend/src/App.tsx` | No navigation changes needed |

## Phase 1: Backend Save Endpoints + Frontend Fix

**Est. Time**: 2h

### Backend

Add to `policy_editor.py`:

```python
_custom_policies: dict[str, dict[str, Any]] = {}

class SavePolicyRequest(BaseModel):
    json_string: str
    name: str = ""
    description: str = ""

@router.post("/custom")
def save_custom_policy(req: SavePolicyRequest):
    """Save a custom policy. Validates first."""
    result = validate_policy_json(req.json_string)
    if not result.valid:
        raise HTTPException(400, detail=f"Invalid policy: {'; '.join(result.errors)}")
    data = json.loads(req.json_string)
    policy_id = data.get("policy_id", f"custom_{uuid4()[:8]}")
    entry = {
        "id": policy_id,
        "name": req.name or policy_id,
        "description": req.description,
        "json_string": req.json_string,
        "summary": result.summary,
    }
    _custom_policies[policy_id] = entry
    return entry

@router.get("/custom")
def list_custom_policies():
    return {"policies": list(_custom_policies.values())}

@router.get("/custom/{policy_id}")
def get_custom_policy(policy_id: str):
    if policy_id not in _custom_policies:
        raise HTTPException(404, detail="Not found")
    return _custom_policies[policy_id]
```

### Frontend

In `PolicyEditorView.tsx`:

1. Change `handleSave` to:
   - POST to `/api/policies/custom` with `{json_string, name, description}`
   - On success: show green toast "✅ Saved!" for 3 seconds, update saved policies dropdown
   - On error: show red error
   - Do NOT navigate. Do NOT call any tab-switching function.

2. Add `useEffect` on mount to fetch `/api/policies/custom` and populate the saved dropdown.

3. The current `handleSave` calls `setSavedPolicies` — this must have somehow triggered a navigation via parent callback or URL change. Investigate and remove any unintended navigation.

### Tests

| Test | What it verifies |
|------|------------------|
| `test_save_custom_policy` | POST saves and returns entry |
| `test_save_invalid_policy_rejected` | POST with bad JSON returns 400 |
| `test_list_custom_policies` | GET returns saved policies |
| `test_get_custom_policy` | GET by ID returns correct entry |
| `test_get_missing_policy_404` | GET non-existent returns 404 |

### Verification

```bash
cd api && .venv/bin/python -m pytest ../web/backend/tests/test_policy_editor.py -v --tb=short
cd web/frontend && npx tsc -b && npm run build
```

### UI Test Protocol

```
Protocol: Policy Save
Wave: Create Tab Fixes

1. Open http://localhost:5173
2. Click ✏️ Create → Policy sub-tab
3. VERIFY: Policy editor with JSON textarea visible
4. Load "Balance-Aware Hold" template
5. Click Validate
6. VERIFY: ✅ Valid
7. Click Save
8. VERIFY: Green "Saved!" toast appears. STILL on Policy Editor tab (NOT Saved Scenarios).
9. Change policy_id to "custom_test_2". Click Save.
10. VERIFY: "Load saved…" dropdown now contains both saved policies.
11. Load a different template. Then select "custom_test_2" from saved dropdown.
12. VERIFY: JSON editor shows the custom_test_2 policy.
13. Navigate to another tab and back to Create → Policy.
14. VERIFY: Saved policies still available in dropdown (fetched from backend).

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] All existing tests pass
- [ ] 5 new tests pass
- [ ] Save stays on Policy Editor tab
- [ ] Saved policies retrievable after page navigation
- [ ] Invalid policies rejected on save
