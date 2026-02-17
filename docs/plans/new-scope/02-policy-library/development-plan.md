# Policy Library — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 1, Item 2

## Goal

Serve the 30+ existing policy JSON files from `simulator/policies/` as a browsable library. Users can browse, preview, and assign policies to agents before launching a simulation. Each policy has metadata describing its strategy, complexity, trees used, and actions used.

## Web Invariants

- **WEB-INV-1**: Policy Reality — every policy assigned from the library MUST be what the engine executes
- **WEB-INV-3**: Scenario Integrity — policies must be compatible with the chosen scenario

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/policy_library.py` | Load, parse, and serve policies from `simulator/policies/` with metadata |
| `web/backend/tests/test_policy_library.py` | Tests for policy loading, metadata, compatibility |
| `web/frontend/src/components/PolicyCard.tsx` | Policy card (name, strategy description, complexity, trees used) |
| `web/frontend/src/components/PolicyBrowser.tsx` | Browsable policy list with filters |
| `web/frontend/src/views/PolicyLibraryView.tsx` | Full policy library view |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/main.py` | Add `/api/policies/library` endpoints |
| `web/backend/app/game.py` | Accept policy assignment from library |
| `web/frontend/src/App.tsx` | Add Policy Library tab |
| `web/frontend/src/types.ts` | Add `PolicyMeta` type |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: policy loading, metadata extraction, validation via FFI | 3h | 15 tests |
| 2 | Backend: API endpoints, policy-scenario compatibility check | 2h | 6 tests |
| 3 | Frontend: PolicyLibraryView, PolicyCard, PolicyBrowser | 3h | tsc + build |
| 4 | Integration: assign library policy to game agents | 2h | 5 tests + UI protocol |

## Phase 1: Policy Loading & Metadata

### Backend

Create `web/backend/app/policy_library.py`:

```python
@dataclass
class PolicyMeta:
    id: str                      # filename without .json
    name: str                    # human-readable (derived from filename + content)
    description: str             # strategy description
    category: str                # "simple" | "adaptive" | "crisis" | "target2" | "test"
    complexity: str              # "basic" | "intermediate" | "advanced"
    trees_used: list[str]        # ["payment_tree", "bank_tree", ...]
    actions_used: list[str]      # ["Release", "Hold", "Split", ...]
    fields_used: list[str]       # ["balance", "ticks_to_deadline", ...]
    has_state_registers: bool    # uses bank_state_* fields
    has_conditions: bool         # has condition nodes (not just a single action)
    parameters: dict[str, Any]   # parameter definitions
    max_depth: int               # deepest tree depth

class PolicyLibrary:
    def __init__(self, policy_dir: Path):
        self._policies: dict[str, PolicyMeta] = {}
        self._raw: dict[str, dict] = {}
        self._load_all(policy_dir)
    
    def list_policies(self, category: str = None) -> list[PolicyMeta]
    def get_policy(self, id: str) -> PolicyMeta
    def get_policy_json(self, id: str) -> dict
    def validate_policy(self, json_dict: dict) -> tuple[bool, list[str]]
```

Metadata extraction: parse JSON tree, walk nodes to find all actions/fields/conditions, measure depth, detect state registers.

### Tests

1. `test_all_policies_load` — all 30+ JSON files parse without error
2. `test_all_policies_valid_via_ffi` — each policy creates a valid `Orchestrator` (engine accepts it)
3. `test_metadata_trees_used` — `sophisticated_adaptive_bank.json` uses all 4 trees
4. `test_metadata_actions_fifo` — `fifo.json` uses only Release
5. `test_metadata_actions_splitter` — splitter policies include Split action
6. `test_metadata_fields_detect` — policies with balance conditions list "balance" in fields_used
7. `test_metadata_state_registers` — memory-driven policies have `has_state_registers=True`
8. `test_metadata_conditions_detect` — `fifo.json` has `has_conditions=False`; complex policies `True`
9. `test_metadata_depth` — simple policies depth 1, complex policies depth 3+
10. `test_metadata_category_target2` — `target2_*.json` categorized as "target2"
11. `test_list_by_category` — filtering works
12. `test_get_nonexistent` — returns error
13. `test_validate_valid_policy` — valid JSON passes
14. `test_validate_invalid_missing_version` — caught
15. `test_validate_invalid_unknown_action` — caught

## Phase 2: API Endpoints

Add to `main.py`:
```
GET  /api/policies/library              → list all policies with metadata
GET  /api/policies/library?category=X   → filtered
GET  /api/policies/{id}                 → full metadata + raw JSON
POST /api/policies/validate             → validate custom policy JSON
```

### Tests
1. `test_library_endpoint_all` — returns all policies
2. `test_library_endpoint_filter` — category filter works
3. `test_detail_endpoint` — returns metadata + JSON
4. `test_detail_404` — unknown policy
5. `test_validate_valid` — valid JSON
6. `test_validate_invalid` — invalid JSON with errors

## Phase 3: Frontend

**PolicyCard.tsx**: Name, category badge, complexity dots (●○○ basic, ●●○ intermediate, ●●● advanced), trees used as icons, action count.

**PolicyBrowser.tsx**: Filterable list/grid with category tabs (All | Simple | Adaptive | TARGET2 | Crisis), complexity filter, search.

**PolicyLibraryView.tsx**: Full view with PolicyBrowser + detail panel showing selected policy's full info and raw JSON.

## Phase 4: Integration — Assign Policy to Agents

Modify game creation to accept per-agent policy assignments from the library:
```
POST /api/games
{
  "scenario_id": "target2_crisis_25day",
  "agent_policies": {
    "BANK_A": "target2_aggressive_settler",
    "BANK_B": "target2_conservative_offsetter",
    "BANK_C": "cautious_liquidity_preserver"
  }
}
```

### Tests
1. `test_create_game_with_library_policies` — game creates with assigned policies
2. `test_assigned_policy_actually_used` — run 1 day, verify non-FIFO behavior (Hold policy → unsettled payments)
3. `test_different_policies_different_results` — FIFO vs Hold-heavy → different cost profiles
4. `test_policy_scenario_compatibility` — incompatible policy actions → clear error
5. `test_default_fifo_when_unassigned` — agents without assignment get FIFO

### UI Test Protocol

```
Protocol: W1-Policy-Library
Wave: 1

1. Open app, sign in
2. Navigate to Policy Library
3. VERIFY: At least 15 policies visible
4. VERIFY: Each card shows name, complexity, category, trees used
5. Filter by "TARGET2"
6. VERIFY: Only target2_* policies shown
7. Click a complex policy (sophisticated_adaptive_bank)
8. VERIFY: Detail shows all 4 trees used, state registers, multiple actions
9. VERIFY: Raw JSON is viewable
10. Navigate to Scenario Library → pick any multi-agent scenario
11. Assign different policies to different agents
12. Launch, step 1 day
13. VERIFY: Agents have different cost profiles (not identical)
14. VERIFY: If a Hold-heavy policy was assigned, some payments are unsettled

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] All 30+ policies load and validate through FFI
- [ ] Metadata accurately reflects policy content (trees, actions, fields, depth)
- [ ] Policies can be assigned to game agents
- [ ] WEB-INV-1 verified: assigned policy is what the engine executes
