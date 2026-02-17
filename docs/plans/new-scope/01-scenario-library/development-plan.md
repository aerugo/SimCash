# Scenario Library — Development Plan

**Status**: Draft  
**Date**: 2026-02-17  
**Branch**: `feature/interactive-web-sandbox`  
**Master Plan Ref**: Wave 1, Items 1 + 3 (backend + frontend)

## Goal

Replace hardcoded scenario presets with a browsable scenario library serving all existing configs (11 example scenarios + 3 paper experiments) with rich metadata, tags, and feature descriptions. Users browse, filter, and select scenarios before launching a simulation.

## Web Invariants

- **WEB-INV-3**: Scenario Integrity — every scenario MUST load via `SimulationConfig.from_dict()` without error
- **WEB-INV-4**: Cost Consistency — scenarios produce correct costs
- **WEB-INV-7**: Relative URLs — all API calls relative

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/scenario_library.py` | Load, validate, and serve scenarios from `examples/configs/` + paper configs with metadata |
| `web/backend/tests/test_scenario_library.py` | Tests for scenario loading, validation, metadata accuracy |
| `web/backend/tests/golden/scenarios.json` | Golden file: expected metadata for all library scenarios |
| `web/frontend/src/components/ScenarioCard.tsx` | Scenario card component (name, description, tags, agent count, features) |
| `web/frontend/src/components/ScenarioDetail.tsx` | Scenario detail page (full description, config preview, features, launch button) |
| `web/frontend/src/views/ScenarioLibraryView.tsx` | Browsable grid of scenario cards with filters |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/main.py` | Add `/api/scenarios/library` and `/api/scenarios/{id}/detail` endpoints |
| `web/frontend/src/App.tsx` | Add Scenario Library tab |
| `web/frontend/src/types.ts` | Add `ScenarioMeta`, `ScenarioDetail` types |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only |
| `examples/configs/` | Read only — these are the source scenarios |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | Backend: scenario loading + metadata extraction + validation | 3h | 12 tests |
| 2 | Backend: API endpoints + golden file validation | 2h | 8 tests |
| 3 | Frontend: ScenarioLibraryView + ScenarioCard + ScenarioDetail | 3h | tsc + build |
| 4 | Integration: launch game from library scenario | 1h | 3 tests + UI protocol |

## Phase 1: Scenario Loading & Metadata

### Backend

Create `web/backend/app/scenario_library.py`:

```python
@dataclass
class ScenarioMeta:
    id: str                    # filename without extension
    name: str                  # human-readable name
    description: str           # what this scenario tests
    category: str              # "paper" | "crisis" | "lsm" | "advanced" | "basic"
    tags: list[str]            # ["stochastic", "lsm", "crisis", "multi-agent", ...]
    num_agents: int
    ticks_per_day: int
    features: list[str]        # ["LSM bilateral", "custom events", "priority escalation", ...]
    cost_params: dict          # key cost rates
    difficulty: str            # "beginner" | "intermediate" | "advanced"
    source: str                # "examples/configs/..." or "paper_configs/..."

class ScenarioLibrary:
    def __init__(self, dirs: list[Path]):
        self._scenarios: dict[str, ScenarioMeta] = {}
        self._configs: dict[str, dict] = {}
        self._load_all(dirs)
    
    def list_scenarios(self, category: str = None, tag: str = None) -> list[ScenarioMeta]
    def get_scenario(self, id: str) -> ScenarioMeta
    def get_config(self, id: str) -> dict  # validated YAML dict
    def validate_config(self, yaml_dict: dict) -> tuple[bool, list[str]]  # via SimulationConfig.from_dict()
```

Metadata extraction: parse YAML, count agents, detect features (LSM enabled? custom events? stochastic arrivals?), categorize automatically.

### Tests (`test_scenario_library.py`)

1. `test_all_example_configs_load` — every YAML in `examples/configs/` loads without error
2. `test_all_paper_configs_load` — exp1, exp2, exp3 configs load without error
3. `test_metadata_agent_count_matches` — extracted num_agents matches actual config
4. `test_metadata_ticks_matches` — extracted ticks_per_day matches config
5. `test_metadata_features_detect_lsm` — LSM-enabled scenarios have "LSM" in features
6. `test_metadata_features_detect_events` — scenarios with events have "custom events" in features
7. `test_metadata_features_detect_stochastic` — stochastic scenarios tagged correctly
8. `test_validate_valid_config` — valid YAML passes validation
9. `test_validate_invalid_config` — missing required fields caught
10. `test_list_by_category` — filtering by category works
11. `test_list_by_tag` — filtering by tag works
12. `test_get_nonexistent_scenario` — returns appropriate error

## Phase 2: API Endpoints + Golden Files

### Backend

Add to `main.py`:
```
GET  /api/scenarios/library              → list all scenarios with metadata
GET  /api/scenarios/library?category=X   → filtered list
GET  /api/scenarios/{id}/detail          → full metadata + config preview
POST /api/scenarios/validate             → validate a custom YAML config
```

### Golden File

`web/backend/tests/golden/scenarios.json` — snapshot of all scenario metadata. Tests assert current output matches golden. Update golden when scenarios are intentionally added/changed.

### Tests

1. `test_library_endpoint_returns_all` — GET returns all scenarios
2. `test_library_endpoint_filter_category` — category filter works
3. `test_library_endpoint_filter_tag` — tag filter works
4. `test_detail_endpoint` — returns full metadata + config
5. `test_detail_endpoint_404` — unknown id returns 404
6. `test_validate_endpoint_valid` — valid YAML returns ok
7. `test_validate_endpoint_invalid` — invalid returns errors
8. `test_golden_file_matches` — output matches golden snapshot

## Phase 3: Frontend

### Components

**ScenarioCard.tsx**: Compact card showing name, description snippet, tags as pills, agent count badge, tick count, difficulty indicator.

**ScenarioDetail.tsx**: Full page/modal showing complete description, feature list, cost parameters, config YAML preview (read-only), "Launch Simulation" button with options (mock/real LLM, max days, eval samples).

**ScenarioLibraryView.tsx**: Grid of ScenarioCards with:
- Category tabs: All | Paper | Crisis | LSM | Advanced
- Tag filter chips
- Search by name/description
- Sort by difficulty/agent count

### Types (`types.ts`)
```typescript
interface ScenarioMeta {
  id: string;
  name: string;
  description: string;
  category: string;
  tags: string[];
  num_agents: number;
  ticks_per_day: number;
  features: string[];
  difficulty: string;
}
```

### Verification
- `npx tsc -b` passes
- `npm run build` succeeds

## Phase 4: Integration

### Connect Library to Game Creation

Modify game creation flow: selecting a scenario from the library → configuring options → `POST /api/games` with the library scenario's config.

### Tests

1. `test_create_game_from_library_scenario` — POST /api/games with library scenario id → game created with correct agent count
2. `test_step_library_scenario_game` — step 1 day → non-zero costs, correct agent count
3. `test_all_library_scenarios_runnable` — create + step 1 day for EVERY library scenario (integration)

### UI Test Protocol

```
Protocol: W1-Scenario-Library
Wave: 1

1. Open the app, sign in
2. Navigate to Scenario Library
3. VERIFY: At least 10 scenarios visible
4. VERIFY: Each card shows name, description, agent count, tags
5. Click category filter "Crisis"
6. VERIFY: Only crisis scenarios shown (TARGET2 Crisis, etc.)
7. Click a crisis scenario card
8. VERIFY: Detail page shows full description, features, cost params
9. VERIFY: Config YAML preview is visible
10. Click "Launch Simulation" with default settings
11. VERIFY: Game starts, correct number of agents shown
12. Step 1 day
13. VERIFY: Events appear, costs are non-zero
14. Go back to library, select a different scenario (e.g., BIS LSM)
15. Launch and step 1 day
16. VERIFY: Different agent count and/or features than the crisis scenario

PASS if all VERIFY steps succeed.
```

## Success Criteria

- [ ] All 11 example configs + 3 paper configs load and pass validation
- [ ] Metadata extraction correctly identifies features, agent count, tick count
- [ ] Golden file validates metadata stability
- [ ] Library UI shows all scenarios with filtering
- [ ] Every library scenario can create and run a game
- [ ] WEB-INV-3 verified: all scenarios pass `SimulationConfig.from_dict()`
