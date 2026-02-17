# Policy Editor & Viewer — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 3 (viewer) + Wave 4 (editor)

## Goal

Render policy decision trees as visual flowcharts (viewer) and provide a JSON editor with schema validation for creating custom policies (editor). The viewer comes first (Wave 3) because it's needed for policy evolution display; the editor follows in Wave 4.

## Web Invariants

- **WEB-INV-1**: Policy Reality — edited policies must pass engine validation and execute correctly

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/components/PolicyTreeViewer.tsx` | Render policy JSON as a visual decision tree flowchart |
| `web/frontend/src/components/PolicyJsonEditor.tsx` | JSON editor with schema validation + autocomplete |
| `web/frontend/src/components/FieldPicker.tsx` | Searchable picker for 140+ context fields |
| `web/frontend/src/components/ActionPicker.tsx` | Action selector per tree type |
| `web/backend/app/policy_schema.py` | Serve policy schema (fields, actions, types) for editor autocomplete |
| `web/backend/tests/test_policy_schema.py` | Tests for schema endpoint |
| `web/backend/tests/test_policy_editor.py` | Tests for custom policy CRUD |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/main.py` | Add policy schema + custom policy endpoints |
| `web/backend/app/storage.py` | Save/load custom policies per user |
| `web/frontend/src/App.tsx` | Route to editor |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | PolicyTreeViewer — render JSON as visual tree | 4h | tsc + build |
| 2 | Backend: policy schema endpoint + custom policy CRUD | 2h | 8 tests |
| 3 | PolicyJsonEditor with validation | 4h | tsc + build |
| 4 | FieldPicker + ActionPicker helpers | 2h | tsc + build |
| 5 | Integration + UI protocol | 2h | 4 tests + UI protocol |

## Phase 1: Policy Tree Viewer (Wave 3)

### PolicyTreeViewer.tsx

Render a policy decision tree as a nested visual structure. CSS-based (not SVG/canvas — simpler, more accessible).

```
┌─ payment_tree ──────────────────────────────────────┐
│                                                      │
│  ◇ balance > 500000?                                │
│  ├─ TRUE                                            │
│  │  ◇ ticks_to_deadline < 3?                        │
│  │  ├─ TRUE                                         │
│  │  │  ■ Release (priority_override: 9)             │
│  │  └─ FALSE                                        │
│  │     ■ Hold                                       │
│  └─ FALSE                                           │
│     ■ Release                                       │
│                                                      │
└──────────────────────────────────────────────────────┘
```

Visual language:
- ◇ Diamond = condition node (with expression text)
- ■ Rectangle = action node (with action name + params)
- Indentation shows tree depth
- Color coding: conditions in blue, Release in green, Hold in amber, Split in purple
- Collapsible subtrees for deep policies
- Click node → show full expression/parameters in tooltip

Props:
```typescript
interface PolicyTreeViewerProps {
  policy: PolicyJson;
  treeType?: "payment_tree" | "bank_tree" | "strategic_collateral_tree" | "end_of_tick_collateral_tree";
  highlightPath?: string[];  // node IDs to highlight (for replay)
  compact?: boolean;
}
```

Show all present trees in tabs if no treeType specified.

## Phase 2: Backend — Schema + CRUD

### Policy Schema Endpoint

```
GET /api/policies/schema
→ {
    "fields": [
      {"name": "balance", "category": "agent", "description": "Current settlement account balance", "type": "f64"},
      {"name": "ticks_to_deadline", "category": "transaction", "description": "Ticks until deadline (can be negative)", "type": "f64"},
      ...
    ],
    "actions": {
      "payment_tree": [
        {"name": "Release", "description": "Submit transaction to RTGS", "parameters": {"priority_override": "optional int"}},
        {"name": "Hold", "description": "Keep in Queue 1", "parameters": {"reason": "optional string"}},
        ...
      ],
      "bank_tree": [...],
      "strategic_collateral_tree": [...],
      "end_of_tick_collateral_tree": [...]
    },
    "operators": {
      "comparison": ["==", "!=", "<", "<=", ">", ">="],
      "logical": ["and", "or", "not"],
      "arithmetic": ["+", "-", "*", "/", "max", "min", "ceil", "floor", "round", "abs", "clamp", "div0"]
    }
  }
```

Source: extract from Rust engine docs + `get_policy_schema()` FFI call.

### Custom Policy CRUD

```
POST   /api/policies/custom        → create (validate + save)
GET    /api/policies/custom         → list user's custom policies
GET    /api/policies/custom/{id}    → get one
PUT    /api/policies/custom/{id}    → update
DELETE /api/policies/custom/{id}    → delete
```

Storage: `gs://simcash-data/users/{uid}/policies/{id}.json`

### Tests

1. `test_schema_endpoint_returns_fields` — at least 50 fields
2. `test_schema_endpoint_returns_actions` — all 4 tree types present
3. `test_schema_fields_have_descriptions` — every field has a description
4. `test_create_custom_policy` — valid JSON saves
5. `test_create_invalid_policy` — missing version → error
6. `test_create_policy_invalid_action` — unknown action → error
7. `test_list_custom_policies` — returns user's policies
8. `test_delete_custom_policy` — removes

## Phase 3: Policy JSON Editor (Wave 4)

### PolicyJsonEditor.tsx

JSON editor with:
- Syntax highlighting (Monaco or CodeMirror)
- Live validation against policy schema
- Error annotations with line numbers
- Template insertion (start from FIFO, build up)
- Side panel: validation results + PolicyTreeViewer preview

Templates:
- "FIFO (Release All)" — simplest
- "Deadline-Aware" — Hold until near deadline, then Release
- "Liquidity-Aware" — check balance before releasing
- "Budget-Controlled" — bank_tree sets budget, payment_tree respects it
- "Full 4-Tree" — all trees with examples

## Phase 4: Field & Action Pickers

### FieldPicker.tsx

Searchable dropdown showing all 140+ context fields:
- Organized by category (Agent, Transaction, System, Collateral, Time, LSM, Cost)
- Search by name or description
- Click to insert `{"field": "balance"}` at cursor
- Shows type and description

### ActionPicker.tsx

Action selector filtered by tree type:
- Shows only actions valid for the current tree
- Description + parameter schema for each action
- Click to insert action node template

## Phase 5: Integration + UI Protocol

### Tests

1. `test_custom_policy_used_in_game` — assign custom policy, run 1 day, verify non-FIFO behavior
2. `test_complex_custom_policy` — policy with conditions → different behavior than FIFO
3. `test_custom_policy_viewer_data` — PolicyTreeViewer renders without error for all library policies
4. `test_custom_policy_roundtrip` — create → save → load → identical JSON

### UI Test Protocol

```
Protocol: W3-Policy-Viewer (Wave 3)

1. Run a game for 3 days with LLM optimization
2. Open Policy Evolution → click a day
3. VERIFY: PolicyTreeViewer renders the policy tree
4. VERIFY: Condition nodes show expressions
5. VERIFY: Action nodes show action names
6. Navigate to Policy Library → click "sophisticated_adaptive_bank"
7. VERIFY: All 4 trees rendered in tabs
8. VERIFY: State register references visible in conditions

Protocol: W4-Policy-Editor (Wave 4)

1. Navigate to Policy Editor
2. Select "Deadline-Aware" template
3. VERIFY: JSON populated, tree preview shows condition + actions
4. Modify urgency threshold from 5 to 3
5. VERIFY: Validation passes, tree preview updates
6. Add an invalid field reference "nonexistent_field"
7. VERIFY: Validation shows error with field name
8. Fix error, click "Save"
9. VERIFY: Policy saved to "My Policies"
10. Create a game, assign custom policy to an agent
11. Run 1 day
12. VERIFY: Agent behavior differs from FIFO (some payments held if policy has Hold)

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] PolicyTreeViewer renders all 30+ library policies without error
- [ ] All 4 tree types rendered in tabs
- [ ] JSON editor validates against schema with clear errors
- [ ] Field/action pickers show complete lists with descriptions
- [ ] Custom policies save, load, and execute correctly
- [ ] WEB-INV-1: custom policies are what the engine executes
