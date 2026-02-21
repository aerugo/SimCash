# Custom Scenario & Policy CRUD — Development Plan

**Status**: Draft
**Date**: 2026-02-21
**Branch**: feature/interactive-web-sandbox
**Estimated effort**: ~6-8 hours (2 phases)

## Goal

Enable users to save, edit, and delete custom scenarios and policies with Firestore persistence, so they survive Cloud Run restarts. Surface custom items in the Library alongside built-in presets.

## Context

The backend already has in-memory CRUD endpoints (`_custom_scenarios` / `_custom_policies` dicts) and the frontend has a Scenario Editor with "Save & Launch". But:
- Data is lost on every deploy/restart (in-memory only)
- No UPDATE or DELETE endpoints
- No user scoping (all custom items are global)
- Custom items don't appear in the Library views
- No edit/delete UI on saved items

## Web Invariants

| Invariant | How it applies |
|-----------|----------------|
| WEB-INV-3: Scenario Integrity | All saved scenarios must pass `SimulationConfig.from_dict()` validation before save |
| WEB-INV-5: Auth Gate | Custom items scoped to authenticated user (`uid`). Guests cannot save. |
| WEB-INV-7: Relative URLs | All API calls via `authFetch()` with relative paths |

## Architecture Decision: Firestore

Custom scenarios and policies will be stored in Firestore (database: `simcash-platform`), following the existing pattern in `collections.py` and `admin.py`.

**Collection structure:**
```
users/{uid}/custom_scenarios/{scenario_id}  →  { name, description, yaml_string, config, summary, created_at, updated_at }
users/{uid}/custom_policies/{policy_id}     →  { name, description, json_string, summary, created_at, updated_at }
```

Per-user subcollections — simple, secure, no cross-user leakage. Firestore handles indexing.

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/user_content.py` | Firestore-backed CRUD for custom scenarios + policies |
| `web/backend/tests/test_user_content.py` | Backend tests (mocked Firestore) |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/scenario_editor.py` | Replace in-memory dict with `user_content` calls, add PUT/DELETE endpoints, require uid |
| `web/backend/app/policy_editor.py` | Same: replace in-memory, add PUT/DELETE, require uid |
| `web/backend/app/main.py` | Remove `saved_scenarios`/`saved_policies` dicts, wire updated routers |
| `web/frontend/src/views/ScenarioLibraryView.tsx` | Add "My Scenarios" tab, edit/delete buttons |
| `web/frontend/src/views/PolicyLibraryView.tsx` | Add "My Policies" tab, edit/delete buttons |
| `web/frontend/src/views/ScenarioEditorView.tsx` | Support edit mode (load existing scenario), save-only button (not just save+launch) |
| `web/frontend/src/views/PolicyEditorView.tsx` | Support edit mode, save button |
| `web/frontend/src/api.ts` | Add CRUD API functions for custom scenarios/policies |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only |
| `web/backend/app/storage.py` | Game storage only — custom content goes to Firestore |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: Firestore persistence + full CRUD endpoints | 3h | 8+ tests |
| 2 | Frontend: Library integration + edit/delete UI | 3h | TypeScript + build + UI protocol |

---

## Phase 1: Backend — Firestore CRUD

### 1a. `user_content.py` — Firestore storage layer

New module following the `collections.py` pattern:

```python
class UserContentStore:
    """Firestore-backed storage for user's custom scenarios and policies."""

    def __init__(self, collection_type: str):  # "custom_scenarios" or "custom_policies"
        ...

    def list(self, uid: str) -> list[dict]
    def get(self, uid: str, item_id: str) -> dict | None
    def save(self, uid: str, item_id: str, data: dict) -> None
    def delete(self, uid: str, item_id: str) -> bool
```

- Uses lazy Firestore init via `_get_fs_db()` pattern from `collections.py`
- Falls back to in-memory dict if Firestore unavailable (local dev)
- Timestamps: `created_at` on first save, `updated_at` on every save

### 1b. Update `scenario_editor.py`

- Replace `_custom_scenarios` dict with `UserContentStore("custom_scenarios")`
- All endpoints require `uid: str = Depends(get_current_user)`
- Add `PUT /api/scenarios/custom/{scenario_id}` — update existing
- Add `DELETE /api/scenarios/custom/{scenario_id}` — delete
- Validate on save and update (existing validation logic preserved)

### 1c. Update `policy_editor.py`

- Same pattern as scenario_editor
- Add `PUT /api/policies/custom/{policy_id}` — update existing
- Add `DELETE /api/policies/custom/{policy_id}` — delete

### 1d. Clean up `main.py`

- Remove `saved_scenarios` and `saved_policies` dicts
- Remove duplicate CRUD endpoints (lines ~472-506) that overlap with `scenario_editor.py`

### Tests (`test_user_content.py`)

1. `test_save_and_list_scenarios` — save 2, list returns both
2. `test_get_scenario` — save 1, get by id
3. `test_update_scenario` — save, update, verify changes
4. `test_delete_scenario` — save, delete, verify gone
5. `test_user_isolation` — user A's scenarios invisible to user B
6. `test_save_invalid_scenario_rejected` — bad YAML returns 400
7. `test_save_and_list_policies` — same for policies
8. `test_delete_nonexistent_returns_404`

Mock Firestore with in-memory fallback (tests run without credentials).

---

## Phase 2: Frontend — Library Integration + Edit/Delete UI

### 2a. API functions (`api.ts`)

```typescript
// Custom scenarios
export async function listCustomScenarios(): Promise<CustomScenario[]>
export async function saveCustomScenario(data: CustomScenarioRequest): Promise<CustomScenario>
export async function updateCustomScenario(id: string, data: CustomScenarioRequest): Promise<CustomScenario>
export async function deleteCustomScenario(id: string): Promise<void>

// Custom policies (same pattern)
export async function listCustomPolicies(): Promise<CustomPolicy[]>
export async function saveCustomPolicy(data: CustomPolicyRequest): Promise<CustomPolicy>
export async function updateCustomPolicy(id: string, data: CustomPolicyRequest): Promise<CustomPolicy>
export async function deleteCustomPolicy(id: string): Promise<void>
```

### 2b. Scenario Library — "My Scenarios" tab

In `ScenarioLibraryView.tsx`:
- Add "My Scenarios" filter tab (alongside existing category tabs)
- Fetch custom scenarios on mount
- Show custom scenarios as cards with edit ✏️ and delete 🗑️ buttons
- Edit → navigate to `/create?edit={scenario_id}` (loads scenario into editor)
- Delete → confirmation dialog → DELETE API call → refresh list

### 2c. Policy Library — "My Policies" tab

Same pattern in the policies sub-tab:
- "My Policies" tab
- Cards with edit/delete
- Edit → navigate to `/create?tab=policy&edit={policy_id}`

### 2d. Scenario Editor — edit mode

In `ScenarioEditorView.tsx`:
- Check URL for `?edit={id}` on mount
- If editing: fetch scenario, populate form fields, show "Update" button instead of "Save & Launch"
- Add standalone "Save" button (save without launching)
- Show "Save & Launch" only for new scenarios or as secondary action

### 2e. Policy Editor — edit mode

Same pattern in `PolicyEditorView.tsx`:
- Load from `?edit={id}`
- Pre-populate JSON editor
- Save/Update button

### Frontend verification

```bash
cd web/frontend && npx tsc -b && npm run build
```

### UI Test Protocol

```
Protocol: Custom Scenario CRUD
1. Open https://simcash-487714.web.app
2. Sign in
3. Navigate to Create → Scenario
4. Fill in: name="Test Scenario", 2 agents, 3 ticks
5. Click "Save"
6. VERIFY: Success toast, scenario saved
7. Navigate to Library → Scenarios → "My Scenarios" tab
8. VERIFY: "Test Scenario" appears as a card
9. Click edit ✏️ on the scenario
10. VERIFY: Editor loads with pre-filled data
11. Change name to "Test Scenario v2", click "Update"
12. VERIFY: Updated in library
13. Click delete 🗑️ on the scenario
14. VERIFY: Confirmation dialog appears
15. Confirm delete
16. VERIFY: Scenario removed from list
```

---

## Success Criteria

- [ ] All existing tests still pass
- [ ] 8+ new backend tests pass
- [ ] Frontend TypeScript compiles clean
- [ ] Frontend builds successfully
- [ ] Custom scenarios persist across Cloud Run restarts (Firestore)
- [ ] Custom scenarios appear in Library under "My Scenarios"
- [ ] Edit loads scenario back into editor
- [ ] Delete removes scenario with confirmation
- [ ] User isolation: users only see their own custom content
- [ ] Guests cannot save (get appropriate error/disabled UI)
- [ ] WEB-INV-3 verified: invalid scenarios rejected on save
- [ ] WEB-INV-5 verified: auth required for all CRUD ops
