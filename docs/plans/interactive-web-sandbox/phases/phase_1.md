# Phase 1: Backend Enhancements

**Status**: Pending
**Started**: —

## Objective

Extend the FastAPI backend with all endpoints needed for the full-featured sandbox: custom scenario CRUD, config inspection, export, replay, and event filtering.

## Invariants Enforced

- INV-1: All new scenario config values use integer cents for money
- INV-3: No new FFI surface — use existing Orchestrator methods and SimulationConfig.to_ffi_dict()

## Implementation Steps

### Step 1.1: Scenario Store + CRUD

**New file**: `web/backend/app/scenarios.py`

In-memory scenario store with CRUD:
```python
class ScenarioStore:
    scenarios: dict[str, dict]  # id -> scenario config (YAML-format dict)
    
    def create(self, name: str, config: dict) -> str
    def get(self, scenario_id: str) -> dict | None
    def list_all(self) -> list[dict]
    def update(self, scenario_id: str, config: dict) -> bool
    def delete(self, scenario_id: str) -> bool
```

**New endpoints in main.py:**
- `POST /api/scenarios` — create custom scenario
- `GET /api/scenarios` — list all (custom + presets)
- `GET /api/scenarios/{id}` — get one
- `PUT /api/scenarios/{id}` — update
- `DELETE /api/scenarios/{id}` — delete

**Scenario format** (matches existing YAML structure):
```json
{
  "name": "My Scenario",
  "simulation": {"ticks_per_day": 6, "num_days": 1, "rng_seed": 42},
  "agents": [
    {"id": "BANK_A", "liquidity_pool": 100000, "opening_balance": 0}
  ],
  "cost_rates": { ... },
  "scenario_events": [ ... ],
  "deferred_crediting": true,
  "lsm_config": {"enable_bilateral": false, "enable_cycles": false}
}
```

### Step 1.2: Config Inspector

**New endpoint:**
- `GET /api/simulations/{id}/config` — returns the full FFI config dict that was passed to `Orchestrator.new()`

SimulationInstance already stores `ffi_config`. Just expose it.

### Step 1.3: Export

**New endpoint:**
- `GET /api/simulations/{id}/export` — returns full JSON dump:
```json
{
  "sim_id": "...",
  "raw_config": { ... },
  "ffi_config": { ... },
  "tick_history": [ ... ],  // all tick results
  "balance_history": { ... },
  "cost_history": { ... },
  "final_state": { ... }
}
```

### Step 1.4: Replay

**New endpoint:**
- `GET /api/simulations/{id}/replay/{tick}` — returns tick_history[tick] plus state at that tick

Derives from existing `tick_history` array on SimulationInstance.

### Step 1.5: Event Filtering

**New endpoint:**
- `GET /api/simulations/{id}/events?type=Arrival&agent=BANK_A&tick_from=0&tick_to=5` — returns filtered events from tick_history

### Step 1.6: Scenario Validation

**New endpoint:**
- `POST /api/scenarios/validate` — validates a scenario config without creating it. Returns validation errors or success.

Uses `SimulationConfig(**config)` to validate, catches Pydantic errors.

## Files

| File | Action |
|------|--------|
| `web/backend/app/scenarios.py` | CREATE |
| `web/backend/app/main.py` | MODIFY — add new endpoints |
| `web/backend/app/models.py` | MODIFY — add scenario models |
| `web/backend/app/simulation.py` | MODIFY — expose config/export/replay |

## Verification

```bash
cd web/backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8642

# Test each endpoint with curl
curl -s localhost:8642/api/scenarios | python3 -m json.tool
curl -s -X POST localhost:8642/api/scenarios -H 'Content-Type: application/json' -d '{"name":"test",...}'
curl -s localhost:8642/api/simulations/{id}/config
curl -s localhost:8642/api/simulations/{id}/export
curl -s localhost:8642/api/simulations/{id}/replay/0
curl -s 'localhost:8642/api/simulations/{id}/events?type=Arrival'
```

## Completion Criteria
- [ ] All 6 new endpoint groups respond correctly
- [ ] Existing endpoints unchanged
- [ ] Scenario validation catches bad configs
- [ ] Export includes all simulation data
- [ ] Replay returns correct state for each tick
