# E2E Tests for Diagnostic Dashboard

This directory contains end-to-end tests that verify the complete diagnostic dashboard flow using a real database created from the 12-bank simulation scenario.

## Test Files

- **`test_diagnostic_dashboard_e2e.py`**: Python tests for API endpoints with real simulation data

## Tests Included

The test suite includes 6 comprehensive tests:

1. **test_simulation_metadata_endpoint** - Verifies simulation metadata API returns correct config and summary
2. **test_agent_list_endpoint** - Tests agent list API with all 12 banks from different policies
3. **test_transactions_endpoint** - Validates transaction pagination and data structure
4. **test_simulation_list_endpoint** - Checks simulation list includes our test simulation
5. **test_daily_metrics_data** - Verifies daily agent metrics are persisted correctly
6. **test_transaction_data_quality** - Validates transaction data completeness and consistency

## Running the Tests

### Prerequisites

1. **Build Rust backend**:
   ```bash
   cd backend
   maturin develop --release
   ```

2. **Install Python dependencies**:
   ```bash
   cd api
   pip install -e .
   # or with uv:
   uv sync
   ```

### Run All E2E Tests

```bash
cd api
pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v -s
```

### Run Specific Test

```bash
cd api
pytest tests/e2e/test_diagnostic_dashboard_e2e.py::test_simulation_metadata_endpoint -v -s
```

### With uv (Recommended)

```bash
cd api
uv run python -m pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v -s
```

## How It Works

### Test Fixture: `simulation_database`

The tests use a module-scoped fixture that:

1. **Runs the 12-bank simulation** with these parameters:
   - Config: `examples/configs/12_bank_4_policy_comparison.yaml`
   - Ticks: 100 (reduced from 1000 for faster testing)
   - Seed: 42 (deterministic results)
   - Persistence: Enabled

2. **Creates a test database** in a temporary directory
   - Contains 12 agents using 4 different policies
   - Real transaction data, metrics, costs, collateral events
   - Persisted to DuckDB

3. **Runs once per test session** - All 6 tests share the same database for efficiency

4. **Cleans up on success** - Database is kept on failure for debugging

### The 12 Banks

The simulation includes 12 banks using 4 distinct policy types:

**Adaptive Liquidity Manager (ALM)**:
- ALM_CONSERVATIVE
- ALM_BALANCED  
- ALM_AGGRESSIVE

**Agile Regional Bank (ARB)**:
- ARB_LARGE_REGIONAL
- ARB_MEDIUM_REGIONAL
- ARB_SMALL_REGIONAL

**Goliath National Bank (GNB)**:
- GNB_TIER1_BEHEMOTH
- GNB_MAJOR_NATIONAL
- GNB_REGIONAL_NATIONAL

**Momentum Investment Bank (MIB)**:
- MIB_PRIME_BROKER
- MIB_HEDGE_FUND_DESK
- MIB_PROP_TRADING

## Test Database Location

- **CI/Temp**: Uses pytest's `tmp_path` for isolation
- **Local Dev**: Stored in `api/test_databases/` for easy inspection
  - Kept on test failure for debugging
  - Cleaned up on success

### Inspecting the Test Database

If a test fails, you can inspect the database:

```bash
duckdb api/test_databases/test_diagnostic_dashboard_e2e_test_*.db

# Example queries:
D SELECT * FROM simulations;
D SELECT COUNT(*) FROM transactions;
D SELECT agent_id, COUNT(*) FROM transactions GROUP BY agent_id;
D SELECT * FROM daily_agent_metrics LIMIT 10;
```

## Expected Test Duration

- **Simulation**: ~1-2 seconds (100 ticks)
- **Tests**: ~2-3 seconds total
- **Total**: ~3-5 seconds for all 6 tests

## Troubleshooting

### "ModuleNotFoundError: No module named 'payment_simulator_core_rs'"

The Rust backend needs to be built:
```bash
cd backend
maturin develop --release
```

### "Config file not found"

Make sure you're running from the `api` directory and the config exists:
```bash
ls ../examples/configs/12_bank_4_policy_comparison.yaml
```

### "Simulation failed"

Check that the CLI works directly:
```bash
cd api
python -m payment_simulator.cli.main run --config ../examples/configs/minimal.yaml --quiet
```

### pytest.mark.e2e warnings

To remove the warnings about unknown markers, add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "e2e: end-to-end tests with real database"
]
```

## Integration with Frontend E2E Tests

The frontend also has Playwright e2e tests that use a similar approach:
- Location: `frontend/diagnostic/tests/e2e/diagnostic-dashboard-real.spec.ts`
- See: `frontend/diagnostic/tests/e2e/README.md`

## CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Build Rust Backend
  run: |
    cd backend
    maturin develop --release

- name: Run E2E Tests
  run: |
    cd api
    pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v
```

## Test Data Quality

The tests verify:

- ✅ All 12 agents are present with correct IDs
- ✅ Transactions have complete required fields
- ✅ Daily metrics are recorded for all agents
- ✅ Settlement rates are realistic (0-100%)
- ✅ Configuration is persisted correctly (seed 42, etc.)
- ✅ API responses match expected schema
