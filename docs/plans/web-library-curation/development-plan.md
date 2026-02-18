# Library Curation & Collections — Development Plan

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox

## Goal

Curate the scenario and policy libraries so only well-developed items are visible by default. Introduce **scenario collections** (themed groups). Archive the rest — admins can toggle visibility per-item from a new admin tab. Keep exp1/exp2/exp3 from the SimCash paper in a "Paper Experiments" collection.

## Web Invariants

- **WEB-INV-3 (Scenario Integrity)**: All scenarios still validate via `SimulationConfig.from_dict()` — archived items are hidden, not deleted
- **WEB-INV-5 (Auth Gate)**: Visibility admin endpoints require admin role
- **WEB-INV-6 (Dark Mode)**: New admin tab matches existing theme

## Current State

**Scenarios (18 total):**
- 7 preset scenarios from `scenario_pack.py` (2bank_2tick, 2bank_12tick, 2bank_3tick, 3bank_6tick, 4bank_8tick, 2bank_stress, 5bank_12tick)
- 11 example configs from `examples/configs/` (advanced_policy_crisis, bis_liquidity_delay_tradeoff, crisis_resolution_10day, suboptimal_policies_10day/25day, target2_crisis_25day + bad_policy, target2_lsm_features_test, test_minimal_eod, test_near_deadline, test_priority_escalation)

**Policies (29 total):**
- From `simulator/policies/` — mix of well-developed (aggressive_market_maker, balanced_cost_optimizer, fifo) and test/niche ones (cost_aware_test, time_aware_test, mock_splitting)

## Design

### Collections

A **collection** is a named, ordered group of scenarios with a description and icon. Scenarios can belong to multiple collections. Collections are defined in a config file, not Firestore (they're developer-curated, not user-created).

**Default collections:**
| Collection | Icon | Scenarios |
|------------|------|-----------|
| Paper Experiments | 📄 | preset_2bank_12tick (exp2), bis_liquidity_delay_tradeoff (exp1), suboptimal_policies_10day (exp3) |
| Getting Started | 🚀 | preset_2bank_2tick, preset_2bank_3tick, preset_2bank_12tick |
| Network Effects | 🌐 | preset_3bank_6tick, preset_4bank_8tick, preset_5bank_12tick |
| Crisis & Stress | ⚡ | preset_2bank_stress, advanced_policy_crisis, target2_crisis_25day, crisis_resolution_10day |
| LSM Exploration | 🔧 | target2_lsm_features_test, target2_crisis_25day |

### Visibility

Each scenario and policy has a `visible` boolean. Default: curated list is visible, rest archived.

**Default visible scenarios (10):** All 7 presets + bis_liquidity_delay_tradeoff + advanced_policy_crisis + crisis_resolution_10day

**Default archived scenarios (8):** suboptimal_policies_10day, suboptimal_policies_25day, target2_crisis_25day, target2_crisis_25day_bad_policy, target2_lsm_features_test, test_minimal_eod, test_near_deadline, test_priority_escalation

**Default visible policies (15):** fifo, aggressive_market_maker, balanced_cost_optimizer, cautious_liquidity_preserver, deadline_driven_trader, efficient_proactive, goliath_national_bank, momentum_investment_bank, adaptive_liquidity_manager, smart_splitter, sophisticated_adaptive_bank, target2_aggressive_settler, target2_conservative_offsetter, target2_crisis_proactive_manager, target2_priority_escalator

**Default archived policies (14):** agile_regional_bank, cost_aware_test, deadline, efficient_memory_adaptive, efficient_splitting, liquidity_aware, liquidity_splitting, memory_driven_strategist, mock_splitting, smart_budget_manager, target2_crisis_risk_denier, target2_limit_aware, target2_priority_aware, time_aware_test

### Storage

Visibility overrides stored in Firestore `simcash-platform` database, collection `library_settings`:
- Doc `scenario_visibility`: `{<scenario_id>: bool}`
- Doc `policy_visibility`: `{<policy_id>: bool}`

Falls back to hardcoded defaults when no Firestore doc exists (local dev).

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/collections.py` | Collection definitions + visibility logic |
| `web/backend/tests/test_collections.py` | Tests for collections + visibility |
| `web/frontend/src/components/LibraryCurationAdmin.tsx` | Admin tab for toggling visibility |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/scenario_library.py` | Filter by visibility, add collection membership |
| `web/backend/app/policy_library.py` | Filter by visibility |
| `web/backend/app/main.py` | Add collection endpoints, admin visibility endpoints |
| `web/frontend/src/views/ScenarioLibraryView.tsx` | Show collections, "Show archived" toggle |
| `web/frontend/src/views/PolicyLibraryView.tsx` | "Show archived" toggle |
| `web/frontend/src/components/AdminDashboard.tsx` | Add "Library" tab with curation UI |
| `web/frontend/src/api.ts` | Add collection + visibility API calls |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only |
| `simulator/policies/*.json` | Policy files stay — just hidden in UI |
| `examples/configs/*.yaml` | Config files stay — just hidden in UI |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: collections + visibility | 2h | 12 tests |
| 2 | Frontend: collection UI + admin curation | 2h | tsc + build |

## Phase 1: Backend — Collections & Visibility

### New files

**`web/backend/app/collections.py`**
- `COLLECTIONS` list with id, name, icon, description, scenario_ids
- `DEFAULT_SCENARIO_VISIBILITY` and `DEFAULT_POLICY_VISIBILITY` dicts
- `get_visibility(item_type) -> dict[str, bool]` — reads Firestore, falls back to defaults
- `set_visibility(item_type, item_id, visible) -> None` — writes to Firestore
- `get_collections() -> list[dict]` — returns collection metadata

### Modified files

**`web/backend/app/scenario_library.py`**
- `get_library(include_archived=False)` — filter by visibility
- Add `collections` field to scenario metadata (list of collection ids it belongs to)
- Add `visible` field to metadata

**`web/backend/app/policy_library.py`**
- `get_library(include_archived=False)` — filter by visibility
- Add `visible` field to metadata

**`web/backend/app/main.py`**
- `GET /api/collections` — list collections with scenario counts
- `GET /api/collections/{id}` — collection detail with scenario list
- `GET /api/admin/library` — all items with visibility status (admin only)
- `PATCH /api/admin/library/{type}/{id}` — toggle visibility (admin only)

### Tests (`test_collections.py`)
1. `test_get_collections_returns_all` — all defined collections returned
2. `test_collection_has_valid_scenario_ids` — all referenced scenarios exist
3. `test_default_visibility_scenarios` — correct defaults
4. `test_default_visibility_policies` — correct defaults
5. `test_scenario_library_filters_archived` — hidden scenarios excluded
6. `test_scenario_library_includes_archived` — `include_archived=True` returns all
7. `test_policy_library_filters_archived` — hidden policies excluded
8. `test_collection_endpoint` — GET /api/collections returns list
9. `test_admin_library_requires_auth` — 401/403 without admin
10. `test_admin_toggle_visibility` — PATCH changes visibility
11. `test_paper_experiments_collection` — exp1/exp2/exp3 present
12. `test_scenario_has_collection_membership` — scenarios include `collections` field

## Phase 2: Frontend — Collection UI & Admin Curation

### Modified files

**`web/frontend/src/views/ScenarioLibraryView.tsx`**
- Add collection chips/pills at top (clickable filters)
- Clicking a collection shows only its scenarios
- "📄 Paper Experiments" collection prominently featured
- "Show archived" toggle at bottom (loads hidden scenarios)
- Archived items shown with reduced opacity + "Archived" badge

**`web/frontend/src/views/PolicyLibraryView.tsx`**
- "Show archived" toggle
- Archived items with reduced opacity

**`web/frontend/src/components/AdminDashboard.tsx`**
- New "📚 Library" tab alongside existing Users and Model tabs
- Two sections: Scenarios and Policies
- Each item shows: name, visibility toggle switch, collection badges
- Bulk actions: "Archive all test_*" button
- Search/filter within admin list

**`web/frontend/src/api.ts`**
- `fetchCollections()`, `fetchCollectionDetail(id)`
- `fetchAdminLibrary()`, `toggleLibraryVisibility(type, id, visible)`

### UI Test Protocol
```
1. Open app, navigate to Library > Scenarios
2. VERIFY: Collection chips shown at top (Paper Experiments, Getting Started, etc.)
3. VERIFY: Only ~10 scenarios visible (not 18)
4. Click "Paper Experiments" collection
5. VERIFY: Shows 3 scenarios (exp1, exp2, exp3)
6. Toggle "Show archived"
7. VERIFY: All 18 scenarios shown, archived ones have badge + reduced opacity
8. Navigate to Admin > Library tab
9. VERIFY: All scenarios and policies listed with toggle switches
10. Toggle a visible scenario to archived
11. VERIFY: Scenario disappears from public library view
12. Toggle it back
13. VERIFY: Scenario reappears
```

## Success Criteria
- [ ] All existing tests still pass
- [ ] 12+ new tests pass
- [ ] Only curated items visible by default
- [ ] Collections group scenarios logically
- [ ] Paper Experiments collection has exp1/exp2/exp3
- [ ] Admin can toggle visibility without code changes
- [ ] "Show archived" lets researchers access everything
- [ ] WEB-INV-3 verified (all scenarios still validate)
