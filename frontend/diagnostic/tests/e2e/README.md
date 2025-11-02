# E2E Tests with Real 12-Bank Simulation Data

This directory contains end-to-end tests that use a real database created by running the 12-bank scenario simulation.

## Overview

The tests are organized into two main files:

1. **`diagnostic-dashboard-real.spec.ts`**: Playwright tests for the diagnostic dashboard UI
2. **`setup-real-database.ts`**: Utility that runs the simulation and creates the test database

## Test Strategy

These tests follow a different approach than the mocked tests:

- **Mocked tests** (`simulation-flow.spec.ts`, etc.): Use MSW to mock API responses, fast but don't test real data flow
- **Real data tests** (`diagnostic-dashboard-real.spec.ts`): Run actual simulation, create real database, test full stack

## Prerequisites

Before running these tests, ensure:

1. **Python environment** with `payment-simulator` installed:
   ```bash
   cd api
   pip install -e .
   ```

2. **Frontend dependencies** installed:
   ```bash
   cd frontend/diagnostic
   bun install
   ```

3. **API server** running on `localhost:8000`:
   ```bash
   cd api
   uvicorn payment_simulator.api.main:app --reload
   ```

## Running the Tests

### Python E2E Tests (Backend Only)

Test the API endpoints with a real database:

```bash
cd api
pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v -s -m e2e
```

This will:
1. Run the 12-bank simulation (100 ticks for speed)
2. Create a test database in `api/test_databases/`
3. Test all API endpoints with real data
4. Clean up on success (keep database on failure for debugging)

**Note**: The database is kept in `api/test_databases/` for easy inspection if a test fails.

### Playwright E2E Tests (Full Stack)

Test the complete diagnostic dashboard with real data:

```bash
cd frontend/diagnostic

# Run all e2e tests (including real data tests)
bun test:e2e

# Run only the real data tests
bun test:e2e diagnostic-dashboard-real.spec.ts

# Run with UI mode for debugging
bun test:e2e diagnostic-dashboard-real.spec.ts --ui
```

This will:
1. Run the 12-bank simulation (via `setup-real-database.ts`)
2. Create a test database
3. Start the frontend dev server
4. Run Playwright tests against the full stack
5. Clean up after tests

## Test Database

The simulation creates a database with:

- **12 agents** (banks) using 4 different policies:
  - 3 × Adaptive Liquidity Manager (ALM)
  - 3 × Agile Regional Bank (ARB)
  - 3 × Goliath National Bank (GNB)
  - 3 × Momentum Investment Bank (MIB)

- **100 ticks** (reduced from 1000 for faster testing)
- **Seed 42** (deterministic results)
- **Real transactions**, metrics, costs, collateral events, etc.

## Debugging Failed Tests

If a test fails:

### Python Tests

1. Check the terminal output for the simulation results
2. Inspect the database (kept on failure):
   ```bash
   duckdb api/test_databases/test_diagnostic_dashboard_e2e_*.db
   D SELECT * FROM simulations;
   D SELECT COUNT(*) FROM transactions;
   D SELECT * FROM daily_agent_metrics LIMIT 10;
   ```

### Playwright Tests

1. Open the Playwright HTML report:
   ```bash
   cd frontend/diagnostic
   bun playwright show-report
   ```

2. Inspect screenshots and traces in the report

3. Check the test database:
   ```bash
   duckdb api/test_databases/e2e_test.db
   D SELECT * FROM simulations;
   ```

## Test Coverage

### Python E2E Tests

- ✅ Simulation metadata endpoint
- ✅ Agent list endpoint
- ✅ Transactions endpoint (pagination)
- ✅ Simulation list endpoint
- ✅ Daily metrics data
- ✅ Transaction data quality

### Playwright E2E Tests

#### UI Tests
- ✅ Load simulation list
- ✅ Open simulation dashboard
- ✅ Display all 12 agents
- ✅ Show configuration details
- ✅ Show transaction data
- ✅ Navigate to events timeline
- ✅ Display agent metrics
- ✅ Verify data consistency
- ✅ Show realistic settlement rate
- ✅ Handle different policy types

#### API Integration Tests
- ✅ Simulation metadata endpoint
- ✅ Agent list endpoint  
- ✅ Transaction data endpoint

## Performance

Test execution times (approximate):

- **Python e2e**: ~15-30 seconds (simulation + tests)
- **Playwright e2e**: ~30-60 seconds (simulation + browser tests)

The simulation uses only 100 ticks (vs 1000 in production) for faster testing while still generating realistic data.

## Adding New Tests

To add new e2e tests with real data:

1. **For API tests**: Add to `api/tests/e2e/test_diagnostic_dashboard_e2e.py`
2. **For UI tests**: Add to `frontend/diagnostic/tests/e2e/diagnostic-dashboard-real.spec.ts`

Both test files use the same simulation fixture, so they share the database setup cost.

## Troubleshooting

### "Config file not found"

Make sure you're running from the correct directory and the config exists:
```bash
ls examples/configs/12_bank_4_policy_comparison.yaml
```

### "Simulation failed"

Check that the Python CLI works:
```bash
cd api
python -m payment_simulator.cli.main run --config ../examples/configs/minimal.yaml --quiet
```

### "API returns 500"

Ensure the API server is running and can access the test database:
```bash
curl http://localhost:8000/api/simulations
```

### "Process is undefined" error

This is a TypeScript type error that can be ignored - the tests will still run. To fix it, add `@types/node`:
```bash
cd frontend/diagnostic
bun add -d @types/node
```

## CI/CD Integration

For CI pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Python E2E Tests
  run: |
    cd api
    pytest tests/e2e/test_diagnostic_dashboard_e2e.py -v -m e2e

- name: Run Playwright E2E Tests
  run: |
    cd frontend/diagnostic
    bun test:e2e diagnostic-dashboard-real.spec.ts --reporter=github
```

The tests are designed to work in CI environments with the `CI=true` environment variable.
