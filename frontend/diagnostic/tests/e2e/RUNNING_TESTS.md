# Running E2E Tests with Real 12-Bank Simulation

This guide explains how to run the end-to-end tests for the diagnostic dashboard that use a real simulation database.

## Prerequisites

1. **Python environment with Rust module built**:
   ```bash
   cd api
   uv run maturin develop --manifest-path ../backend/Cargo.toml --release
   ```

2. **Node dependencies installed**:
   ```bash
   cd frontend/diagnostic
   bun install
   ```

## Running the Tests

### Quick Start (Chromium Only)

```bash
cd frontend/diagnostic
bun test:e2e diagnostic-dashboard-real.spec.ts --project=chromium
```

### Run All Tests

```bash
cd frontend/diagnostic
bun test:e2e
```

### Run with UI (Debugging)

```bash
cd frontend/diagnostic
bun test:e2e --ui
```

## How the Tests Work

### 1. Test Setup Phase

Each test creates its own **unique database file** to avoid lock conflicts:

```
api/test_databases/e2e_test_<timestamp>_<random>.db
```

The `setupRealDatabase()` function:
- Runs the 12-bank simulation with 100 ticks
- Uses fixed seed (42) for deterministic results
- Creates a real DuckDB database with transactions, agents, metrics
- Returns the database path and simulation ID
- Provides cleanup function to delete the database after tests

### 2. Parallel Execution

The tests run in parallel with **3 workers** (configurable in `playwright.config.ts`). Each worker:
- Gets its own unique database file
- Runs the simulation independently
- Tests against its own data
- Cleans up after completion

### 3. API Integration

The tests verify:
- ✅ Simulation list loads
- ✅ Simulation dashboard displays correctly
- ✅ Agent metrics are accurate
- ✅ Configuration details render
- ✅ API endpoints return correct data

## Test Structure

```
tests/e2e/
├── diagnostic-dashboard-real.spec.ts  # 14 Playwright tests
├── setup-real-database.ts             # Test database setup utility
└── README.md                          # Test documentation
```

## Key Fixes Applied

### 1. PyO3 Module Name Fixed

**Problem**: Rust module had wrong symbol name (`_core` vs `payment_simulator_core_rs`)

**Fix**: Updated `backend/src/lib.rs`:
```rust
#[pymodule]
fn payment_simulator_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Now matches Cargo.toml library name
}
```

### 2. Parallel Test Database Locks Fixed

**Problem**: Multiple tests tried to write to same database, causing DuckDB lock errors

**Fix**: Each test gets unique database:
```typescript
const uniqueId = `${Date.now()}_${Math.random().toString(36).substring(7)}`;
const dbPath = join(testDbDir, `e2e_test_${uniqueId}.db`);
```

### 3. JSON Parsing Fixed

**Problem**: CLI output included non-JSON text like "Initializing..." before JSON

**Fix**: Extract JSON from last line that starts with `{`:
```typescript
const lines = output.trim().split("\n");
for (let i = lines.length - 1; i >= 0; i--) {
  if (lines[i].trim().startsWith("{")) {
    jsonLine = lines[i];
    break;
  }
}
```

### 4. Worker Count Optimized

**Problem**: Default 5 workers overwhelmed system with simultaneous simulations

**Fix**: Limited to 3 workers in `playwright.config.ts`:
```typescript
workers: process.env.CI ? 1 : 3
```

## Troubleshooting

### Test Fails: "Module not found"

**Solution**: Rebuild the Rust module:
```bash
cd api
uv run maturin develop --manifest-path ../backend/Cargo.toml --release
```

### Test Fails: "Database lock"

This should no longer happen with unique database files. If it does:
1. Check that no Python processes are holding locks: `ps aux | grep python`
2. Delete stale test databases: `rm api/test_databases/e2e_test_*.db`

### Test Fails: "JSON parse error"

The setup utility should handle this automatically. If it still fails:
1. Run simulation manually to see output:
   ```bash
   cd api
   uv run python -m payment_simulator.cli.main run \
     --config ../examples/configs/12_bank_4_policy_comparison.yaml \
     --persist --db-path test.db --quiet --ticks 100 --seed 42
   ```
2. Check if output ends with valid JSON

### TypeScript Errors

If you see "Cannot find module 'fs'" or "Cannot find name 'process'":
```bash
cd frontend/diagnostic
bun add -d @types/node
```

## Performance

- **Single test**: ~1-2 seconds (simulation + browser tests)
- **Full suite (14 tests)**: ~15-20 seconds with 3 workers
- **Database size**: ~1-5 MB per test

## Cleanup

Test databases are automatically cleaned up after each test. To manually clean:

```bash
rm api/test_databases/e2e_test_*.db
```

## Next Steps

After verifying these tests pass:
1. Run Python API tests: `cd api && uv run pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v`
2. Implement missing diagnostic dashboard pages (see `docs/plans/diagnostic-frontend.md`)
3. Add more e2e tests for agent detail pages, event timeline, etc.
