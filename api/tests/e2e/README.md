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

## CLI Usage Examples

The payment simulator CLI provides powerful event filtering and display modes for analyzing simulations.

### Basic Usage

```bash
# Run simulation with default output (JSON summary)
payment-sim run --config ../examples/configs/12_bank_4_policy_comparison.yaml --ticks 100

# Quiet mode (suppress logs, JSON only)
payment-sim run --config scenario.yaml --quiet --ticks 50
```

### Verbose Mode (Categorized Events)

Shows detailed events grouped by category (arrivals, policies, settlements, etc.):

```bash
# Verbose mode with all events
payment-sim run --config scenario.yaml --verbose --ticks 100

# Verbose mode with persistence
payment-sim run --config scenario.yaml --verbose --persist --ticks 100
```

### Event Stream Mode (Chronological Display)

Shows events in strict chronological order with compact one-line format:

```bash
# Event stream mode
payment-sim run --config scenario.yaml --event-stream --ticks 50

# Event stream with persistence
payment-sim run --config scenario.yaml --event-stream --persist --ticks 100
```

### Event Filtering

Filter events by type, agent, transaction, or tick range. **Filters require `--verbose` or `--event-stream` mode**.

#### Filter by Event Type

Show only specific event types (comma-separated):

```bash
# Show only Arrival events
payment-sim run --config scenario.yaml --event-stream --filter-event-type Arrival

# Show Arrivals and Settlements
payment-sim run --config scenario.yaml --event-stream --filter-event-type "Arrival,Settlement"

# Show policy decisions
payment-sim run --config scenario.yaml --verbose --filter-event-type "PolicySubmit,PolicyHold,PolicyDrop"
```

Available event types:
- Transaction lifecycle: `Arrival`, `Settlement`, `QueuedRtgs`
- Policy decisions: `PolicySubmit`, `PolicyHold`, `PolicyDrop`, `PolicySplit`
- LSM optimization: `LsmBilateralOffset`, `LsmCycleSettlement`
- Collateral: `CollateralPost`, `CollateralWithdraw`
- Cost tracking: `CostAccrual`
- System: `EndOfDay`

#### Filter by Agent

Show only events involving a specific agent:

```bash
# Show all events from ALM_CONSERVATIVE
payment-sim run --config scenario.yaml --verbose --filter-agent ALM_CONSERVATIVE

# Show events from BANK_A
payment-sim run --config scenario.yaml --event-stream --filter-agent BANK_A
```

Agent filter matches both:
- `agent_id` field (policy events)
- `sender_id` field (transaction events)

#### Filter by Transaction

Show events for a specific transaction ID:

```bash
# Track a specific transaction (you'll need the actual tx_id from output)
payment-sim run --config scenario.yaml --event-stream --filter-tx "abc123def456"
```

#### Filter by Tick Range

Show events within a specific tick range:

```bash
# Show events from tick 10 to 50
payment-sim run --config scenario.yaml --event-stream --filter-tick-range "10-50"

# Show events from tick 20 onwards
payment-sim run --config scenario.yaml --event-stream --filter-tick-range "20-"

# Show events up to tick 30
payment-sim run --config scenario.yaml --event-stream --filter-tick-range "-30"
```

### Combining Filters (AND Logic)

All filters use AND logic - events must match ALL specified criteria:

```bash
# Show Arrivals and Settlements from ALM_CONSERVATIVE in ticks 10-50
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type "Arrival,Settlement" \
  --filter-agent ALM_CONSERVATIVE \
  --filter-tick-range "10-50"

# Show only Policy decisions from BANK_A in first 20 ticks
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type "PolicySubmit,PolicyHold,PolicyDrop" \
  --filter-agent BANK_A \
  --filter-tick-range "-20"
```

### Common Use Cases

#### Debugging a Specific Agent's Behavior

```bash
# See all events for a specific agent
payment-sim run --config scenario.yaml --event-stream \
  --filter-agent ALM_AGGRESSIVE \
  --ticks 100
```

#### Analyzing Settlement Patterns

```bash
# Focus on settlements and queueing
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type "Settlement,QueuedRtgs" \
  --ticks 100
```

#### Understanding Policy Decisions

```bash
# See all policy decisions in verbose mode
payment-sim run --config scenario.yaml --verbose \
  --filter-event-type "PolicySubmit,PolicyHold,PolicyDrop,PolicySplit" \
  --ticks 50
```

#### Monitoring Early Tick Behavior

```bash
# Focus on first 20 ticks
payment-sim run --config scenario.yaml --event-stream \
  --filter-tick-range "-20"
```

### Error Handling

```bash
# ❌ Filters require --verbose or --event-stream
payment-sim run --config scenario.yaml --filter-event-type Arrival
# Error: Event filters (--filter-*) require either --verbose or --event-stream mode

# ✅ Correct: Include --event-stream
payment-sim run --config scenario.yaml --event-stream --filter-event-type Arrival
```
