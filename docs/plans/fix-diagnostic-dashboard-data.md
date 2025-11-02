# Fix Diagnostic Dashboard Data Persistence

**Created**: 2025-11-02
**Status**: In Progress
**Type**: Bug Fix + Enhancement

---

## Executive Summary

The diagnostic dashboard at `/simulations/{sim_id}` displays blank configuration fields, shows "Agents (0)", and has empty transactions page when viewing database-persisted simulations. This occurs because the `simulations` table stores only summary metadata without full configuration details.

**Solution**: Store complete configuration as JSON in the database (mirroring the pattern already used by `simulation_checkpoints` table).

---

## Problem Statement

### Current Issues

1. **Blank Configuration Fields**
   - Ticks per Day: ✓ (shows)
   - Number of Days: ✓ (shows)
   - RNG Seed: ✓ (shows)
   - Number of Agents: ✓ (shows)
   - **Agents Section**: ❌ Shows "Agents (0)" even when agents exist

2. **Missing Agent Details**
   - No agent list displayed
   - Cannot navigate to agent detail pages
   - No agent balances or credit limits shown

3. **Empty Transactions Page**
   - Likely due to transactions not being persisted during CLI runs

4. **No E2E Test Coverage**
   - No test runs actual scenario (e.g., `12_bank_4_policy_comparison.yaml`)
   - Tests manually insert minimal data
   - Missing validation that frontend works with real persisted data

### Root Cause

The `SimulationRecord` model (in `api/payment_simulator/persistence/models.py`) stores:
```python
class SimulationRecord(BaseModel):
    simulation_id: str
    config_file: str
    rng_seed: int
    ticks_per_day: int
    num_days: int
    num_agents: int  # ← Only count, not actual agent configs!
    # ... other summary fields
```

The API endpoint falls back to empty agents array:
```python
config_dict = {
    "rng_seed": rng_seed,
    "ticks_per_day": ticks_per_day,
    "agents": [],  # ⚠️ Always empty for DB simulations!
}
```

### Why This Pattern Exists

The `simulation_checkpoints` table **already stores full config**:
```python
class SimulationCheckpointRecord(BaseModel):
    # ...
    config_json: str = Field(..., description="Complete config (FFI dict as JSON)")
```

We just need to apply this same pattern to the main `simulations` table.

---

## Solution Design

### Option 1: Store Full Config in Database (Selected)

**Strategy**: Add `config_json` column to `simulations` table containing the complete configuration as JSON string.

**Advantages**:
- ✅ Self-contained database (no dependency on YAML files)
- ✅ Proven pattern (checkpoints already use this)
- ✅ Frontend gets all data in one query
- ✅ Works for moved/renamed config files
- ✅ Enables config comparison queries

**Disadvantages**:
- Schema migration required
- Slightly larger database size (acceptable tradeoff)

### Data Flow

```
YAML Config File
    ↓
CLI: Load & Validate
    ↓
Orchestrator.new(config_dict)
    ↓
Run Simulation
    ↓
CLI: Persist to Database
    ├─ simulations table: metadata + config_json  ← NEW!
    ├─ transactions table: all transactions
    ├─ daily_agent_metrics: agent stats
    └─ collateral_events: collateral actions
    ↓
Frontend: Query /simulations/{sim_id}
    ↓
API: Parse config_json and return full config
    ↓
Dashboard: Display all agents, config, metrics
```

---

## Implementation Plan (TDD)

### Phase 1: Database Schema Migration

**Files to Modify**:
- `api/payment_simulator/persistence/models.py`
- `api/migrations/002_add_config_json_to_simulations.sql` (NEW)

**Changes**:
1. Add migration file:
```sql
-- Migration: Add config_json to simulations table
ALTER TABLE simulations ADD COLUMN config_json TEXT;
```

2. Update `SimulationRecord` model:
```python
class SimulationRecord(BaseModel):
    # ... existing fields ...
    config_json: Optional[str] = Field(None, description="Complete configuration as JSON")
```

**Test**:
```python
def test_simulation_record_accepts_config_json():
    record = SimulationRecord(
        simulation_id="sim-001",
        config_file="test.yaml",
        config_json='{"simulation": {...}, "agents": [...]}',
        # ... other fields ...
    )
    assert record.config_json is not None
```

---

### Phase 2: Update Persistence Layer

**Files to Modify**:
- `api/payment_simulator/persistence/writers.py`

**Changes**:
1. Store `config_json` when persisting simulation metadata:
```python
def write_simulation_metadata(conn, sim_id, config_dict, ...):
    # Serialize config to JSON
    config_json = json.dumps(config_dict)
    
    conn.execute("""
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, config_json,
            rng_seed, ticks_per_day, num_days, num_agents,
            status, started_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        sim_id, config_file, config_hash, config_json,
        rng_seed, ticks_per_day, num_days, num_agents,
        'running', datetime.now()
    ])
```

**Test**:
```python
def test_persist_simulation_stores_config_json(tmp_path):
    db_path = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_path))
    db_manager.setup()
    
    config = {
        "simulation": {"ticks_per_day": 100, "num_days": 5, "rng_seed": 42},
        "agents": [
            {"id": "BANK_A", "opening_balance": 1000000, "credit_limit": 0},
            {"id": "BANK_B", "opening_balance": 2000000, "credit_limit": 0},
        ],
    }
    
    # Persist simulation
    write_simulation_metadata(db_manager.get_connection(), "sim-001", config, ...)
    
    # Verify config_json stored
    conn = db_manager.get_connection()
    row = conn.execute(
        "SELECT config_json FROM simulations WHERE simulation_id = ?",
        ["sim-001"]
    ).fetchone()
    
    assert row[0] is not None
    stored_config = json.loads(row[0])
    assert len(stored_config["agents"]) == 2
    assert stored_config["agents"][0]["id"] == "BANK_A"
```

---

### Phase 3: Update API Endpoint

**Files to Modify**:
- `api/payment_simulator/api/main.py`

**Changes**:
```python
@app.get("/simulations/{sim_id}", response_model=SimulationMetadataResponse)
def get_simulation_metadata(sim_id: str):
    # ... existing code to check in-memory simulations ...
    
    # Query database
    conn = manager.db_manager.get_connection()
    
    sim_query = """
        SELECT
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            config_json,  -- ← NEW COLUMN
            status, started_at, completed_at,
            total_arrivals, total_settlements, total_cost_cents,
            duration_seconds, ticks_per_second
        FROM simulations
        WHERE simulation_id = ?
    """
    sim_result = conn.execute(sim_query, [sim_id]).fetchone()
    
    if not sim_result:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
    
    # Unpack with config_json
    (
        sim_id_result, config_file, config_hash, rng_seed,
        ticks_per_day, num_days, num_agents,
        config_json_str,  # ← NEW
        status, started_at, completed_at,
        total_arrivals, total_settlements, total_cost_cents,
        duration_seconds, ticks_per_second,
    ) = sim_result
    
    # Parse config from JSON if available
    if config_json_str:
        config_dict = json.loads(config_json_str)
    else:
        # Fallback for old simulations without config_json
        config_dict = {
            "config_file": config_file,
            "config_hash": config_hash,
            "rng_seed": rng_seed,
            "ticks_per_day": ticks_per_day,
            "num_days": num_days,
            "num_agents": num_agents,
            "agents": [],  # Empty for backwards compatibility
        }
    
    # ... rest of response building ...
```

**Test** (update existing test):
```python
def test_get_simulation_metadata_from_database_with_config_json(client_with_db):
    """Test that config_json is parsed and agents are returned."""
    from payment_simulator.api.main import manager
    import json
    
    conn = manager.db_manager.get_connection()
    
    config = {
        "simulation": {"ticks_per_day": 100, "num_days": 5, "rng_seed": 42},
        "agents": [
            {"id": "BANK_A", "opening_balance": 1000000, "credit_limit": 500000},
            {"id": "BANK_B", "opening_balance": 2000000, "credit_limit": 0},
        ],
    }
    
    sim_id = "sim-test-001"
    conn.execute("""
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            config_json,  -- ← NEW
            status, started_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        sim_id, "test.yaml", "abc123", 42,
        100, 5, 2,
        json.dumps(config),  # ← Store full config
        "completed", datetime.now(), datetime.now()
    ])
    
    # Query API
    response = client_with_db.get(f"/simulations/{sim_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify agents are returned
    assert "config" in data
    assert "agents" in data["config"]
    assert len(data["config"]["agents"]) == 2  # ← Not 0!
    assert data["config"]["agents"][0]["id"] == "BANK_A"
    assert data["config"]["agents"][0]["opening_balance"] == 1000000
```

---

### Phase 4: CLI Integration

**Files to Check/Modify**:
- `api/payment_simulator/cli/commands/run.py` (or wherever simulation runs happen)

**Ensure**:
1. Config is passed to persistence layer
2. All transactions are written to database
3. Agent metrics are written at EOD

**Already Exists?**:
Check if CLI already calls `write_simulation_metadata()` - if so, just verify config_dict is passed correctly.

---

### Phase 5: E2E Test (Critical!)

**File**: `frontend/diagnostic/tests/e2e/database-simulation.spec.ts` (NEW)

**Purpose**: Test complete flow from CLI simulation run → database persistence → frontend display

**Test Scenario**:
```typescript
import { test, expect } from '@playwright/test'
import { exec } from 'child_process'
import { promisify } from 'util'
import path from 'path'

const execAsync = promisify(exec)

test.describe('Database-Persisted Simulation Flow', () => {
  let simId: string
  let dbPath: string

  test.beforeAll(async () => {
    // Create temp database
    dbPath = path.join('/tmp', `test-sim-${Date.now()}.db`)
    
    // Run simulation via CLI with database persistence
    const configPath = path.join(
      __dirname,
      '../../../examples/configs/12_bank_4_policy_comparison.yaml'
    )
    
    const { stdout } = await execAsync(
      `PAYMENT_SIM_DB_PATH=${dbPath} ` +
      `python -m payment_simulator.cli.main run ${configPath} --persist`
    )
    
    // Extract simulation ID from output
    const match = stdout.match(/Simulation ID: ([\w-]+)/)
    simId = match![1]
  })

  test('displays complete simulation config from database', async ({ page }) => {
    // Start API server with test database
    await page.goto(`http://localhost:5173/simulations/${simId}`)

    // Verify config section populated
    await expect(page.getByText(/ticks per day/i)).toBeVisible()
    await expect(page.getByText('200')).toBeVisible() // From config

    // Verify RNG seed shown
    await expect(page.getByText(/rng seed/i)).toBeVisible()
    await expect(page.getByText('42')).toBeVisible()

    // Verify number of agents
    await expect(page.getByText(/agents \(12\)/i)).toBeVisible()
  })

  test('displays all 12 agents from database', async ({ page }) => {
    await page.goto(`http://localhost:5173/simulations/${simId}`)

    // Verify each agent is listed
    const agentNames = [
      'ALM_CONSERVATIVE', 'ALM_BALANCED', 'ALM_AGGRESSIVE',
      'ARB_LARGE_REGIONAL', 'ARB_MEDIUM_REGIONAL', 'ARB_SMALL_REGIONAL',
      'GNB_TIER1_BEHEMOTH', 'GNB_MAJOR_NATIONAL', 'GNB_REGIONAL_NATIONAL',
      'MIB_PRIME_BROKER', 'MIB_HEDGE_FUND_DESK', 'MIB_PROP_TRADING',
    ]

    for (const agentName of agentNames) {
      await expect(page.getByText(agentName)).toBeVisible()
    }
  })

  test('navigates to agent detail page', async ({ page }) => {
    await page.goto(`http://localhost:5173/simulations/${simId}`)

    // Click first agent
    await page.getByText('ALM_CONSERVATIVE').click()

    // Verify navigation worked
    await expect(page).toHaveURL(/\/agents\/ALM_CONSERVATIVE/)
    await expect(page.getByRole('heading', { level: 1 })).toContainText('ALM_CONSERVATIVE')
  })

  test('displays transactions from database', async ({ page }) => {
    await page.goto(`http://localhost:5173/simulations/${simId}/transactions`)

    // Should have many transactions (12 banks × ~150 tx/day × 5 days ≈ 9000+)
    await expect(page.getByText(/total transactions/i)).toBeVisible()
    
    // Should show transaction table
    await expect(page.locator('table tbody tr')).not.toHaveCount(0)
  })

  test('displays events timeline from database', async ({ page }) => {
    await page.goto(`http://localhost:5173/simulations/${simId}/events`)

    // Should have events
    await expect(page.locator('[data-testid="event-card"]')).not.toHaveCount(0)
  })

  test.afterAll(async () => {
    // Cleanup test database
    await execAsync(`rm -f ${dbPath}`)
  })
})
```

---

## Migration Strategy

### Backwards Compatibility

Old simulations without `config_json` will still work:
```python
if config_json_str:
    config_dict = json.loads(config_json_str)  # Full config
else:
    config_dict = build_minimal_config(...)  # Fallback
```

### Data Migration (Optional)

For existing database simulations, we **cannot** recreate full config from summary data. Options:

1. **Leave old data as-is** (recommended)
   - Frontend shows minimal config for old sims
   - New simulations get full config
   
2. **Re-run simulations** (if needed)
   - Only if complete analysis of old runs is critical
   - Re-run with updated CLI to populate config_json

---

## Testing Strategy

### Test Levels

1. **Unit Tests** (Models)
   - `SimulationRecord` accepts config_json
   - JSON serialization/deserialization

2. **Integration Tests** (Persistence)
   - Writers store config_json correctly
   - Queries retrieve and parse config_json

3. **Integration Tests** (API)
   - Endpoint returns full config when available
   - Endpoint falls back gracefully when missing

4. **E2E Tests** (Frontend)
   - Complete flow: CLI → DB → API → Frontend
   - All dashboard sections populated
   - Navigation works

### Test Coverage Goals

- Unit: 100% of new code
- Integration: All critical paths
- E2E: At least one complete scenario (12-bank config)

---

## Implementation Checklist

### Phase 1: Database Schema
- [ ] Create migration file `002_add_config_json_to_simulations.sql`
- [ ] Update `SimulationRecord` model to include `config_json`
- [ ] Run migration on test database
- [ ] Write unit test for model

### Phase 2: Persistence Layer
- [ ] Update `writers.py` to store config_json
- [ ] Write integration test for persistence
- [ ] Verify test passes

### Phase 3: API Endpoint
- [ ] Update `get_simulation_metadata()` to parse config_json
- [ ] Update existing test to verify agent array populated
- [ ] Add test for fallback behavior (missing config_json)
- [ ] Verify all tests pass

### Phase 4: CLI Integration
- [ ] Verify CLI passes config to persistence
- [ ] Ensure transactions persisted during runs
- [ ] Test manual CLI run with database

### Phase 5: E2E Testing
- [ ] Write E2E test for complete flow
- [ ] Run E2E test (should fail initially)
- [ ] Fix any remaining issues
- [ ] Verify E2E test passes

### Phase 6: Verification
- [ ] Run full test suite
- [ ] Manual verification: Run 12-bank scenario, view in frontend
- [ ] Verify all dashboard sections populated
- [ ] Verify transactions page not empty
- [ ] Document any edge cases

---

## Success Criteria

✅ Dashboard shows complete configuration for database simulations
✅ "Agents (12)" instead of "Agents (0)"
✅ All agent names, balances, credit limits displayed
✅ Can navigate to individual agent detail pages
✅ Transactions page populated with data
✅ E2E test passes with real scenario
✅ All existing tests continue to pass
✅ Backwards compatible with old simulations

---

## Risks & Mitigations

### Risk 1: Large Config JSON Size
**Concern**: Config JSON might be large for complex scenarios

**Mitigation**:
- JSON is text and compresses well
- Database can handle text blobs
- Only stored once per simulation
- Much smaller than transaction/event data

### Risk 2: Breaking Changes
**Concern**: Changes might break existing functionality

**Mitigation**:
- Fallback for missing config_json (backwards compatible)
- Comprehensive test coverage
- TDD approach (tests written first)

### Risk 3: Migration Issues
**Concern**: Schema migration might fail on production data

**Mitigation**:
- Simple ALTER TABLE (non-destructive)
- New column is nullable
- No data transformation needed

---

## Timeline Estimate

- Phase 1 (Schema): 30 minutes
- Phase 2 (Persistence): 45 minutes  
- Phase 3 (API): 45 minutes
- Phase 4 (CLI): 15 minutes (verify only)
- Phase 5 (E2E): 1 hour
- Phase 6 (Verification): 30 minutes

**Total**: ~3.5 hours

---

## References

- `api/payment_simulator/persistence/models.py` - Database schema
- `api/payment_simulator/api/main.py` - API endpoints
- `frontend/diagnostic/src/pages/SimulationDashboardPage.tsx` - Frontend
- `examples/configs/12_bank_4_policy_comparison.yaml` - Test scenario
- `docs/plans/diagnostic-frontend.md` - Original frontend plan

---

**Next Steps**: Begin implementation following TDD approach, starting with Phase 1 (Database Schema).
