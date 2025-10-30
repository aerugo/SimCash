# Phase 8 Completion Plan: Cost & Metrics API Layer

**Status**: 75% Complete → 100% Complete
**Estimated Effort**: 2-3 days (13 hours)
**Priority**: High (last incomplete phase before Phase 9)
**Approach**: Test-Driven Development (TDD)

---

## Executive Summary

Phase 8's Rust implementation is **complete**. All cost calculations work correctly:
- ✅ Liquidity cost (overdraft fees)
- ✅ Delay cost (time-based penalties)
- ✅ Collateral cost (posted collateral fees)
- ✅ Split friction cost (transaction splitting fees)
- ✅ Deadline penalty cost (missed deadlines)

**What's Missing**: Only the Python API layer to expose these costs via REST endpoints.

**What We'll Build**:
1. FFI methods to query costs from Python
2. REST API endpoints for cost queries
3. System-wide metrics aggregation
4. Comprehensive test coverage

---

## Current State Analysis

### ✅ What Works (Rust Layer)

**File**: `backend/src/orchestrator/engine.rs`

```rust
// Cost accumulation happens every tick
pub struct CostAccumulator {
    pub total_liquidity_cost: i64,      // Overdraft fees
    pub total_delay_cost: i64,          // Time penalties
    pub total_collateral_cost: i64,     // Collateral fees
    pub total_penalty_cost: i64,        // Deadline penalties
    pub total_split_friction_cost: i64, // Split fees
    pub peak_net_debit: i64,            // Max overdraft seen
}

// Already implemented in Orchestrator
pub fn get_costs(&self, agent_id: &str) -> Option<&CostAccumulator>
pub fn all_costs(&self) -> &HashMap<String, CostAccumulator>
```

**Verification**: Tests in `backend/tests/test_cost_accrual.rs` confirm costs accrue correctly.

### ❌ What's Missing (API Layer)

1. **FFI exposure** - No Python bindings for cost queries
2. **API endpoints** - No REST routes for cost data
3. **Response models** - No Pydantic schemas for cost responses
4. **Integration tests** - No E2E tests for cost API

---

## Implementation Plan (TDD Approach)

### Phase 1: Write Failing Tests FIRST ⚠️ (Day 1 Morning, 2 hours)

> **TDD Principle**: Write tests before implementation to define contract and catch regressions.

#### 1.1 FFI Unit Tests (Rust)

**File**: `backend/tests/test_cost_ffi.rs` (NEW)

```rust
//! FFI-level cost query tests
//!
//! These tests verify that cost data can be queried through
//! the FFI boundary without panics or memory issues.

use payment_simulator_core_rs::orchestrator::{Orchestrator, OrchestratorConfig};

#[test]
fn test_get_agent_costs_returns_accumulator() {
    // Setup: Create orchestrator with 2 agents
    let mut orch = create_test_orchestrator();

    // Run 10 ticks to accumulate costs
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Query costs for BANK_A
    let costs = orch.get_costs("BANK_A");

    // Assert: Returns Some(accumulator)
    assert!(costs.is_some());
    let costs = costs.unwrap();

    // Assert: All cost fields present
    assert!(costs.total_liquidity_cost >= 0);
    assert!(costs.total_delay_cost >= 0);
    assert!(costs.total_collateral_cost >= 0);
    assert!(costs.total_penalty_cost >= 0);
    assert!(costs.total_split_friction_cost >= 0);
}

#[test]
fn test_get_costs_returns_none_for_invalid_agent() {
    let orch = create_test_orchestrator();

    // Query nonexistent agent
    let costs = orch.get_costs("INVALID_BANK");

    // Assert: Returns None
    assert!(costs.is_none());
}

#[test]
fn test_all_costs_returns_all_agents() {
    let mut orch = create_test_orchestrator();

    // Run 10 ticks
    for _ in 0..10 {
        orch.tick().unwrap();
    }

    // Query all costs
    let all_costs = orch.all_costs();

    // Assert: Returns map with all configured agents
    assert_eq!(all_costs.len(), 2);
    assert!(all_costs.contains_key("BANK_A"));
    assert!(all_costs.contains_key("BANK_B"));
}

#[test]
fn test_costs_accumulate_across_ticks() {
    let mut orch = create_test_orchestrator_with_overdraft();

    // Run 1 tick
    orch.tick().unwrap();
    let costs_tick1 = orch.get_costs("BANK_A").unwrap().total();

    // Run 9 more ticks
    for _ in 0..9 {
        orch.tick().unwrap();
    }
    let costs_tick10 = orch.get_costs("BANK_A").unwrap().total();

    // Assert: Costs should increase (assuming continued overdraft)
    assert!(costs_tick10 >= costs_tick1);
}

fn create_test_orchestrator() -> Orchestrator {
    // Helper to create minimal test orchestrator
    // (implementation details...)
}

fn create_test_orchestrator_with_overdraft() -> Orchestrator {
    // Helper that creates scenario forcing overdraft
    // (implementation details...)
}
```

**Run**: `cargo test test_cost_ffi` → Should FAIL (methods exist but not tested together)

#### 1.2 FFI Integration Tests (Python)

**File**: `api/tests/integration/test_cost_ffi.py` (NEW)

```python
"""Test cost queries through FFI boundary."""
import pytest
from payment_simulator._core import Orchestrator


@pytest.fixture
def orchestrator_with_costs():
    """Create orchestrator configured to accrue costs."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # Low balance to trigger overdraft
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 5.0,  # High arrival rate
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 50_000,
                        "std_dev": 10_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,  # High balance
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdraft_rate_bps": 50,  # 0.5% per day
            "delay_cost_per_tick_per_cent": 0.0001,  # Small delay cost
            "collateral_cost_per_tick_bps": 10,
            "missed_deadline_penalty_bps": 500,
        },
    }

    orch = Orchestrator.new(config)

    # Run 20 ticks to accumulate costs
    for _ in range(20):
        orch.tick()

    return orch


def test_get_agent_costs_via_ffi(orchestrator_with_costs):
    """Test querying agent costs from Python."""
    orch = orchestrator_with_costs

    # Query costs for BANK_A
    costs = orch.get_agent_costs("BANK_A")

    # Assert: Returns dict (not None)
    assert costs is not None
    assert isinstance(costs, dict)

    # Assert: All 5 cost types present
    assert "liquidity_cost" in costs
    assert "delay_cost" in costs
    assert "collateral_cost" in costs
    assert "penalty_cost" in costs
    assert "split_friction_cost" in costs
    assert "total_cost" in costs
    assert "peak_net_debit" in costs

    # Assert: Values are integers (cents)
    assert isinstance(costs["liquidity_cost"], int)
    assert isinstance(costs["total_cost"], int)

    # Assert: Total equals sum of parts
    expected_total = (
        costs["liquidity_cost"]
        + costs["delay_cost"]
        + costs["collateral_cost"]
        + costs["penalty_cost"]
        + costs["split_friction_cost"]
    )
    assert costs["total_cost"] == expected_total

    # Assert: BANK_A should have some costs (was in overdraft)
    assert costs["total_cost"] > 0


def test_get_agent_costs_returns_none_for_invalid_agent(orchestrator_with_costs):
    """Test querying costs for nonexistent agent."""
    orch = orchestrator_with_costs

    # Query invalid agent
    costs = orch.get_agent_costs("INVALID_BANK")

    # Assert: Returns None
    assert costs is None


def test_get_all_costs_via_ffi(orchestrator_with_costs):
    """Test querying all agent costs."""
    orch = orchestrator_with_costs

    # Query all costs
    all_costs = orch.get_all_costs()

    # Assert: Returns dict
    assert isinstance(all_costs, dict)

    # Assert: Contains both agents
    assert len(all_costs) == 2
    assert "BANK_A" in all_costs
    assert "BANK_B" in all_costs

    # Assert: Each agent has cost breakdown
    for agent_id, costs in all_costs.items():
        assert isinstance(costs, dict)
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert "collateral_cost" in costs
        assert "penalty_cost" in costs
        assert "split_friction_cost" in costs
        assert "total_cost" in costs


def test_costs_are_deterministic(orchestrator_with_costs):
    """Test that cost calculations are deterministic."""
    # Create two orchestrators with same seed
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdraft_rate_bps": 50,
        },
    }

    orch1 = Orchestrator.new(config)
    orch2 = Orchestrator.new(config)

    # Run same number of ticks
    for _ in range(10):
        orch1.tick()
        orch2.tick()

    # Query costs
    costs1 = orch1.get_agent_costs("BANK_A")
    costs2 = orch2.get_agent_costs("BANK_A")

    # Assert: Costs should be identical
    assert costs1 == costs2


def test_peak_net_debit_tracking(orchestrator_with_costs):
    """Test that peak_net_debit captures maximum overdraft."""
    orch = orchestrator_with_costs

    # Query costs for BANK_A (which went into overdraft)
    costs = orch.get_agent_costs("BANK_A")

    # Assert: peak_net_debit should be negative (or zero if no overdraft)
    assert "peak_net_debit" in costs
    assert isinstance(costs["peak_net_debit"], int)

    # If liquidity_cost > 0, peak_net_debit should be < 0
    if costs["liquidity_cost"] > 0:
        assert costs["peak_net_debit"] < 0
```

**Run**: `pytest api/tests/integration/test_cost_ffi.py` → Should FAIL (methods don't exist yet)

#### 1.3 API Endpoint Tests (E2E)

**File**: `api/tests/integration/test_api_costs.py` (NEW)

```python
"""Test cost query API endpoints (E2E)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from payment_simulator.api.main import app
    return TestClient(app)


@pytest.fixture
def cost_scenario_config():
    """Configuration designed to accrue costs."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 3.0,
                    "amount_distribution": {
                        "type": "Normal",
                        "mean": 75_000,
                        "std_dev": 10_000,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdraft_rate_bps": 50,
            "delay_cost_per_tick_per_cent": 0.0001,
            "collateral_cost_per_tick_bps": 10,
            "missed_deadline_penalty_bps": 500,
        },
    }


def test_get_all_simulation_costs(client, cost_scenario_config):
    """Test GET /simulations/{id}/costs returns all agent costs."""
    # Create simulation
    create_resp = client.post("/simulations", json=cost_scenario_config)
    assert create_resp.status_code == 200
    sim_id = create_resp.json()["simulation_id"]

    # Run 20 ticks to accumulate costs
    tick_resp = client.post(f"/simulations/{sim_id}/tick?count=20")
    assert tick_resp.status_code == 200

    # Query costs
    costs_resp = client.get(f"/simulations/{sim_id}/costs")

    # Assert: 200 OK
    assert costs_resp.status_code == 200

    # Assert: Response structure
    data = costs_resp.json()
    assert "costs" in data
    assert isinstance(data["costs"], dict)

    # Assert: Contains all agents
    assert "BANK_A" in data["costs"]
    assert "BANK_B" in data["costs"]

    # Assert: Each agent has cost breakdown
    for agent_id, costs in data["costs"].items():
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert "collateral_cost" in costs
        assert "penalty_cost" in costs
        assert "split_friction_cost" in costs
        assert "total_cost" in costs
        assert "peak_net_debit" in costs


def test_get_specific_agent_costs(client, cost_scenario_config):
    """Test GET /simulations/{id}/costs/{agent_id} returns per-agent costs."""
    # Create and run simulation
    create_resp = client.post("/simulations", json=cost_scenario_config)
    sim_id = create_resp.json()["simulation_id"]

    client.post(f"/simulations/{sim_id}/tick?count=20")

    # Query specific agent costs
    costs_resp = client.get(f"/simulations/{sim_id}/costs/BANK_A")

    # Assert: 200 OK
    assert costs_resp.status_code == 200

    # Assert: Response structure
    data = costs_resp.json()
    assert "liquidity_cost" in data
    assert "delay_cost" in data
    assert "collateral_cost" in data
    assert "penalty_cost" in data
    assert "split_friction_cost" in data
    assert "total_cost" in data
    assert "peak_net_debit" in data

    # Assert: Values are integers
    assert isinstance(data["liquidity_cost"], int)
    assert isinstance(data["total_cost"], int)


def test_get_agent_costs_invalid_agent(client, cost_scenario_config):
    """Test GET /simulations/{id}/costs/{agent_id} returns 404 for invalid agent."""
    # Create simulation
    create_resp = client.post("/simulations", json=cost_scenario_config)
    sim_id = create_resp.json()["simulation_id"]

    # Query nonexistent agent
    costs_resp = client.get(f"/simulations/{sim_id}/costs/INVALID_BANK")

    # Assert: 404 Not Found
    assert costs_resp.status_code == 404
    assert "not found" in costs_resp.json()["detail"].lower()


def test_get_costs_invalid_simulation(client):
    """Test GET /simulations/{id}/costs returns 404 for invalid simulation."""
    # Query nonexistent simulation
    costs_resp = client.get("/simulations/invalid-sim-id/costs")

    # Assert: 404 Not Found
    assert costs_resp.status_code == 404


def test_get_system_metrics(client, cost_scenario_config):
    """Test GET /simulations/{id}/metrics returns system-wide KPIs."""
    # Create and run simulation
    create_resp = client.post("/simulations", json=cost_scenario_config)
    sim_id = create_resp.json()["simulation_id"]

    client.post(f"/simulations/{sim_id}/tick?count=50")

    # Query metrics
    metrics_resp = client.get(f"/simulations/{sim_id}/metrics")

    # Assert: 200 OK
    assert metrics_resp.status_code == 200

    # Assert: Response structure
    data = metrics_resp.json()
    assert "total_transactions" in data
    assert "settled_transactions" in data
    assert "settlement_rate" in data
    assert "queue1_total_size" in data
    assert "queue2_size" in data
    assert "current_tick" in data
    assert "current_day" in data

    # Assert: Types
    assert isinstance(data["total_transactions"], int)
    assert isinstance(data["settled_transactions"], int)
    assert isinstance(data["settlement_rate"], float)
    assert 0.0 <= data["settlement_rate"] <= 1.0

    # Assert: Logical consistency
    assert data["settled_transactions"] <= data["total_transactions"]
    assert data["current_tick"] == 50


def test_costs_start_at_zero(client, cost_scenario_config):
    """Test that costs are zero before simulation runs."""
    # Create simulation (don't run ticks)
    create_resp = client.post("/simulations", json=cost_scenario_config)
    sim_id = create_resp.json()["simulation_id"]

    # Query costs immediately
    costs_resp = client.get(f"/simulations/{sim_id}/costs/BANK_A")

    # Assert: All costs should be zero
    data = costs_resp.json()
    assert data["liquidity_cost"] == 0
    assert data["delay_cost"] == 0
    assert data["collateral_cost"] == 0
    assert data["penalty_cost"] == 0
    assert data["split_friction_cost"] == 0
    assert data["total_cost"] == 0
```

**Run**: `pytest api/tests/integration/test_api_costs.py` → Should FAIL (endpoints don't exist yet)

---

### Phase 2: Implement FFI Layer (Day 1 Afternoon, 3 hours)

> **Goal**: Expose cost data from Rust to Python through PyO3 bindings.

#### 2.1 Add FFI Methods to PyOrchestrator

**File**: `backend/src/ffi/orchestrator.rs`

**Add these methods to the `#[pymethods]` impl block:**

```rust
// ========================================================================
// Cost Query Methods (Phase 8: Cost & Metrics API)
// ========================================================================

/// Get accumulated costs for a specific agent
///
/// Returns cost breakdown for the specified agent, or None if agent not found.
///
/// # Arguments
///
/// * `agent_id` - Agent identifier (e.g., "BANK_A")
///
/// # Returns
///
/// Dictionary containing:
/// - `liquidity_cost`: Overdraft fees accrued (cents)
/// - `delay_cost`: Time-based delay penalties (cents)
/// - `collateral_cost`: Collateral posting fees (cents)
/// - `penalty_cost`: Missed deadline penalties (cents)
/// - `split_friction_cost`: Transaction splitting fees (cents)
/// - `total_cost`: Sum of all costs (cents)
/// - `peak_net_debit`: Maximum negative balance observed (cents)
///
/// Returns None if agent not found.
///
/// # Example (from Python)
///
/// ```python
/// costs = orch.get_agent_costs("BANK_A")
/// if costs:
///     print(f"Total cost: ${costs['total_cost'] / 100:.2f}")
///     print(f"Peak overdraft: ${abs(costs['peak_net_debit']) / 100:.2f}")
/// ```
fn get_agent_costs(&self, py: Python, agent_id: &str) -> PyResult<Option<Py<PyDict>>> {
    match self.inner.get_costs(agent_id) {
        Some(costs) => {
            let dict = PyDict::new_bound(py);
            dict.set_item("liquidity_cost", costs.total_liquidity_cost)?;
            dict.set_item("delay_cost", costs.total_delay_cost)?;
            dict.set_item("collateral_cost", costs.total_collateral_cost)?;
            dict.set_item("penalty_cost", costs.total_penalty_cost)?;
            dict.set_item("split_friction_cost", costs.total_split_friction_cost)?;
            dict.set_item("total_cost", costs.total())?;
            dict.set_item("peak_net_debit", costs.peak_net_debit)?;
            Ok(Some(dict.into()))
        }
        None => Ok(None),
    }
}

/// Get accumulated costs for all agents
///
/// Returns a dictionary mapping agent IDs to their cost breakdowns.
///
/// # Returns
///
/// Dictionary where keys are agent IDs and values are cost dictionaries
/// (same structure as `get_agent_costs`).
///
/// # Example (from Python)
///
/// ```python
/// all_costs = orch.get_all_costs()
/// for agent_id, costs in all_costs.items():
///     print(f"{agent_id}: ${costs['total_cost'] / 100:.2f}")
/// ```
fn get_all_costs(&self, py: Python) -> PyResult<Py<PyDict>> {
    let all_costs = self.inner.all_costs();
    let result = PyDict::new_bound(py);

    for (agent_id, costs) in all_costs.iter() {
        let cost_dict = PyDict::new_bound(py);
        cost_dict.set_item("liquidity_cost", costs.total_liquidity_cost)?;
        cost_dict.set_item("delay_cost", costs.total_delay_cost)?;
        cost_dict.set_item("collateral_cost", costs.total_collateral_cost)?;
        cost_dict.set_item("penalty_cost", costs.total_penalty_cost)?;
        cost_dict.set_item("split_friction_cost", costs.total_split_friction_cost)?;
        cost_dict.set_item("total_cost", costs.total())?;
        cost_dict.set_item("peak_net_debit", costs.peak_net_debit)?;
        result.set_item(agent_id, cost_dict)?;
    }

    Ok(result.into())
}

/// Get system-wide metrics and KPIs
///
/// Returns aggregated metrics for the entire simulation:
/// - Transaction counts (total, settled, pending)
/// - Settlement rate
/// - Queue sizes
/// - Current simulation time
///
/// # Returns
///
/// Dictionary containing:
/// - `total_transactions`: Total transactions created
/// - `settled_transactions`: Successfully settled transactions
/// - `settlement_rate`: Ratio of settled to total (0.0-1.0)
/// - `queue1_total_size`: Sum of all agent Queue 1 sizes
/// - `queue2_size`: RTGS central queue size
/// - `current_tick`: Current simulation tick
/// - `current_day`: Current simulation day
///
/// # Example (from Python)
///
/// ```python
/// metrics = orch.get_system_metrics()
/// print(f"Settlement rate: {metrics['settlement_rate'] * 100:.1f}%")
/// print(f"Queue backlog: {metrics['queue1_total_size']}")
/// ```
fn get_system_metrics(&self, py: Python) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new_bound(py);

    // Get event log stats
    let event_log = self.inner.event_log();

    // Count transactions from events
    let mut total_arrivals = 0;
    let mut total_settlements = 0;

    for event in event_log.events() {
        match event {
            crate::models::event::Event::Arrival { .. } => total_arrivals += 1,
            crate::models::event::Event::Settlement { .. } => total_settlements += 1,
            _ => {}
        }
    }

    dict.set_item("total_transactions", total_arrivals)?;
    dict.set_item("settled_transactions", total_settlements)?;

    let settlement_rate = if total_arrivals > 0 {
        total_settlements as f64 / total_arrivals as f64
    } else {
        0.0
    };
    dict.set_item("settlement_rate", settlement_rate)?;

    // Aggregate queue sizes
    let agent_ids = self.inner.get_agent_ids();
    let mut queue1_total = 0;
    for agent_id in &agent_ids {
        if let Some(size) = self.inner.get_queue1_size(agent_id) {
            queue1_total += size;
        }
    }
    dict.set_item("queue1_total_size", queue1_total)?;
    dict.set_item("queue2_size", self.inner.get_queue2_size())?;

    // Current time
    dict.set_item("current_tick", self.inner.current_tick())?;
    dict.set_item("current_day", self.inner.current_day())?;

    Ok(dict.into())
}
```

**Build and test**:
```bash
cd backend
cargo build
cargo test test_cost_ffi
```

**Expected**: Rust FFI tests should now PASS ✅

#### 2.2 Test FFI from Python

```bash
cd api
pytest tests/integration/test_cost_ffi.py -v
```

**Expected**: Python FFI tests should now PASS ✅

---

### Phase 3: Implement API Layer (Day 2 Morning, 3 hours)

> **Goal**: Create REST endpoints that expose cost data to external clients.

#### 3.1 Add Response Models

**File**: `api/payment_simulator/api/main.py`

**Add these Pydantic models after existing models:**

```python
class CostBreakdown(BaseModel):
    """Per-agent cost breakdown."""
    liquidity_cost: int = Field(..., description="Overdraft fees (cents)")
    delay_cost: int = Field(..., description="Time-based delay penalties (cents)")
    collateral_cost: int = Field(..., description="Collateral posting fees (cents)")
    penalty_cost: int = Field(..., description="Missed deadline penalties (cents)")
    split_friction_cost: int = Field(..., description="Transaction splitting fees (cents)")
    total_cost: int = Field(..., description="Sum of all costs (cents)")
    peak_net_debit: int = Field(..., description="Maximum negative balance observed (cents)")


class AllCostsResponse(BaseModel):
    """All agent costs."""
    costs: Dict[str, CostBreakdown] = Field(..., description="Map of agent_id to cost breakdown")


class SystemMetricsResponse(BaseModel):
    """System-wide KPIs."""
    total_transactions: int = Field(..., description="Total transactions created")
    settled_transactions: int = Field(..., description="Successfully settled transactions")
    settlement_rate: float = Field(..., description="Ratio of settled to total (0.0-1.0)", ge=0.0, le=1.0)
    queue1_total_size: int = Field(..., description="Sum of all agent Queue 1 sizes", ge=0)
    queue2_size: int = Field(..., description="RTGS central queue size", ge=0)
    current_tick: int = Field(..., description="Current simulation tick", ge=0)
    current_day: int = Field(..., description="Current simulation day", ge=0)
```

#### 3.2 Add API Endpoints

**File**: `api/payment_simulator/api/main.py`

**Add these routes before the lifespan event handler:**

```python
# ============================================================================
# Cost & Metrics Endpoints (Phase 8)
# ============================================================================

@app.get(
    "/simulations/{sim_id}/costs",
    response_model=AllCostsResponse,
    summary="Get all agent costs",
    description="Retrieve accumulated costs for all agents in the simulation.",
)
async def get_all_simulation_costs(sim_id: str) -> AllCostsResponse:
    """
    Get accumulated costs for all agents.

    Returns cost breakdowns for every agent, including:
    - Liquidity costs (overdraft fees)
    - Delay costs (time penalties)
    - Collateral costs (posting fees)
    - Penalty costs (missed deadlines)
    - Split friction costs (transaction splitting)

    All costs are in cents (integer).
    """
    try:
        orch = manager.get_simulation(sim_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")

    try:
        # Query all costs via FFI
        costs_dict = orch.get_all_costs()

        # Convert to response model
        costs = {
            agent_id: CostBreakdown(**cost_data)
            for agent_id, cost_data in costs_dict.items()
        }

        return AllCostsResponse(costs=costs)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve costs: {str(e)}"
        )


@app.get(
    "/simulations/{sim_id}/costs/{agent_id}",
    response_model=CostBreakdown,
    summary="Get specific agent costs",
    description="Retrieve accumulated costs for a specific agent.",
)
async def get_agent_simulation_costs(sim_id: str, agent_id: str) -> CostBreakdown:
    """
    Get accumulated costs for a specific agent.

    Returns the cost breakdown for the specified agent, including all
    cost categories and the peak overdraft observed.

    All costs are in cents (integer).
    """
    try:
        orch = manager.get_simulation(sim_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")

    try:
        # Query agent costs via FFI
        costs = orch.get_agent_costs(agent_id)

        if costs is None:
            raise HTTPException(
                status_code=404,
                detail=f"Agent not found: {agent_id}"
            )

        return CostBreakdown(**costs)

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve costs: {str(e)}"
        )


@app.get(
    "/simulations/{sim_id}/metrics",
    response_model=SystemMetricsResponse,
    summary="Get system metrics",
    description="Retrieve system-wide KPIs and performance metrics.",
)
async def get_simulation_metrics(sim_id: str) -> SystemMetricsResponse:
    """
    Get system-wide metrics and KPIs.

    Returns aggregated metrics for the entire simulation:
    - Transaction counts and settlement rates
    - Queue sizes and backlogs
    - Current simulation time

    Useful for monitoring simulation health and progress.
    """
    try:
        orch = manager.get_simulation(sim_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")

    try:
        # Query metrics via FFI
        metrics = orch.get_system_metrics()

        return SystemMetricsResponse(**metrics)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )
```

#### 3.3 Test API Endpoints

```bash
cd api
pytest tests/integration/test_api_costs.py -v
```

**Expected**: All API endpoint tests should now PASS ✅

---

### Phase 4: Optional Enhancements (Day 2 Afternoon, 2 hours)

> **Goal**: Add observability features for production deployments.

#### 4.1 Prometheus Metrics Endpoint

**File**: `api/payment_simulator/api/main.py`

**Add Prometheus-compatible metrics:**

```python
from fastapi.responses import Response

@app.get(
    "/metrics",
    response_class=Response,
    summary="Prometheus metrics",
    description="Prometheus-compatible metrics endpoint for monitoring.",
)
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint.

    Exports simulation metrics in Prometheus text format for
    scraping by Prometheus/Grafana monitoring systems.
    """
    lines = []

    # Metadata
    lines.append("# HELP simulation_total_cost Total cost across all agents (cents)")
    lines.append("# TYPE simulation_total_cost gauge")

    lines.append("# HELP simulation_settlement_rate Settlement success rate (0-1)")
    lines.append("# TYPE simulation_settlement_rate gauge")

    lines.append("# HELP simulation_queue_size Queue backlog size")
    lines.append("# TYPE simulation_queue_size gauge")

    # Per-simulation metrics
    for sim_id, orch in manager.simulations.items():
        try:
            # Cost metrics
            all_costs = orch.get_all_costs()
            for agent_id, costs in all_costs.items():
                lines.append(
                    f'simulation_agent_liquidity_cost{{sim_id="{sim_id}",agent_id="{agent_id}"}} '
                    f'{costs["liquidity_cost"]}'
                )
                lines.append(
                    f'simulation_agent_delay_cost{{sim_id="{sim_id}",agent_id="{agent_id}"}} '
                    f'{costs["delay_cost"]}'
                )
                lines.append(
                    f'simulation_agent_total_cost{{sim_id="{sim_id}",agent_id="{agent_id}"}} '
                    f'{costs["total_cost"]}'
                )

            # System metrics
            metrics = orch.get_system_metrics()
            lines.append(
                f'simulation_settlement_rate{{sim_id="{sim_id}"}} '
                f'{metrics["settlement_rate"]}'
            )
            lines.append(
                f'simulation_queue_size{{sim_id="{sim_id}",queue="queue1"}} '
                f'{metrics["queue1_total_size"]}'
            )
            lines.append(
                f'simulation_queue_size{{sim_id="{sim_id}",queue="queue2"}} '
                f'{metrics["queue2_size"]}'
            )

        except Exception as e:
            # Log but don't fail entire endpoint
            lines.append(f"# ERROR: Failed to get metrics for {sim_id}: {e}")

    return Response(content="\n".join(lines) + "\n", media_type="text/plain")
```

#### 4.2 OpenAPI Documentation

Update OpenAPI schema to include examples:

```python
# Add examples to response models
class CostBreakdown(BaseModel):
    """Per-agent cost breakdown."""
    liquidity_cost: int = Field(..., description="Overdraft fees (cents)")
    # ... other fields ...

    class Config:
        json_schema_extra = {
            "example": {
                "liquidity_cost": 125000,
                "delay_cost": 5000,
                "collateral_cost": 10000,
                "penalty_cost": 0,
                "split_friction_cost": 500,
                "total_cost": 140500,
                "peak_net_debit": -500000,
            }
        }
```

---

### Phase 5: Integration & Documentation (Day 3, 3 hours)

> **Goal**: Verify complete workflow and update all documentation.

#### 5.1 Full Integration Test

**File**: `api/tests/integration/test_phase8_complete.py` (NEW)

```python
"""Complete Phase 8 integration test (E2E workflow)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from payment_simulator.api.main import app
    return TestClient(app)


def test_complete_cost_workflow(client):
    """
    End-to-end test: Create sim → Run → Query costs → Validate.

    This test verifies the complete Phase 8 workflow:
    1. Create simulation with cost rates configured
    2. Submit manual transactions
    3. Run simulation for 100 ticks
    4. Query costs via API
    5. Validate all 5 cost types accumulated
    6. Query system metrics
    7. Validate settlement rate and queue sizes
    """
    # ========================================================================
    # 1. Create Simulation
    # ========================================================================
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000,  # $5,000
                "credit_limit": 1_000_000,   # $10,000
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000,
                "credit_limit": 1_000_000,
                "policy": {"type": "LiquidityAware", "target_buffer": 300_000, "urgency_threshold": 5},
            },
            {
                "id": "BANK_C",
                "opening_balance": 2_000_000,  # High balance (acts as liquidity provider)
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "overdraft_rate_bps": 50,           # 0.5% per day
            "delay_cost_per_tick_per_cent": 0.0001,
            "collateral_cost_per_tick_bps": 10,
            "missed_deadline_penalty_bps": 500,  # 5%
            "split_friction_cost": 1000,         # $10 per split
        },
    }

    create_resp = client.post("/simulations", json=config)
    assert create_resp.status_code == 200
    sim_id = create_resp.json()["simulation_id"]

    # ========================================================================
    # 2. Submit Manual Transactions
    # ========================================================================
    # Submit large payments to force overdrafts
    transactions = [
        {"sender": "BANK_A", "receiver": "BANK_C", "amount": 600_000, "deadline_tick": 50, "priority": 8},
        {"sender": "BANK_A", "receiver": "BANK_C", "amount": 400_000, "deadline_tick": 50, "priority": 7},
        {"sender": "BANK_B", "receiver": "BANK_C", "amount": 700_000, "deadline_tick": 30, "priority": 9},
        {"sender": "BANK_C", "receiver": "BANK_A", "amount": 100_000, "deadline_tick": 80, "priority": 5},
    ]

    for tx in transactions:
        tx_resp = client.post(f"/simulations/{sim_id}/transactions", json=tx)
        assert tx_resp.status_code == 200

    # ========================================================================
    # 3. Run Simulation
    # ========================================================================
    tick_resp = client.post(f"/simulations/{sim_id}/tick?count=100")
    assert tick_resp.status_code == 200

    # ========================================================================
    # 4. Query All Costs
    # ========================================================================
    all_costs_resp = client.get(f"/simulations/{sim_id}/costs")
    assert all_costs_resp.status_code == 200

    all_costs = all_costs_resp.json()["costs"]

    # ========================================================================
    # 5. Validate Cost Accumulation
    # ========================================================================
    # BANK_A should have costs (went into overdraft)
    bank_a_costs = all_costs["BANK_A"]
    assert bank_a_costs["liquidity_cost"] > 0, "BANK_A should have liquidity costs"
    assert bank_a_costs["delay_cost"] >= 0
    assert bank_a_costs["collateral_cost"] >= 0
    assert bank_a_costs["penalty_cost"] >= 0
    assert bank_a_costs["split_friction_cost"] >= 0

    # Total should equal sum
    expected_total = (
        bank_a_costs["liquidity_cost"]
        + bank_a_costs["delay_cost"]
        + bank_a_costs["collateral_cost"]
        + bank_a_costs["penalty_cost"]
        + bank_a_costs["split_friction_cost"]
    )
    assert bank_a_costs["total_cost"] == expected_total

    # Peak net debit should be negative (overdraft occurred)
    assert bank_a_costs["peak_net_debit"] < 0

    # ========================================================================
    # 6. Query System Metrics
    # ========================================================================
    metrics_resp = client.get(f"/simulations/{sim_id}/metrics")
    assert metrics_resp.status_code == 200

    metrics = metrics_resp.json()

    # ========================================================================
    # 7. Validate System Metrics
    # ========================================================================
    assert metrics["total_transactions"] > 0, "Should have processed transactions"
    assert metrics["settled_transactions"] > 0, "Should have settled some transactions"
    assert 0.0 <= metrics["settlement_rate"] <= 1.0
    assert metrics["current_tick"] == 100
    assert metrics["current_day"] == 1

    # ========================================================================
    # 8. Query Individual Agent Costs
    # ========================================================================
    agent_cost_resp = client.get(f"/simulations/{sim_id}/costs/BANK_B")
    assert agent_cost_resp.status_code == 200

    bank_b_costs = agent_cost_resp.json()
    assert "liquidity_cost" in bank_b_costs
    assert "total_cost" in bank_b_costs

    # ========================================================================
    # 9. Test Error Cases
    # ========================================================================
    # Invalid agent
    invalid_resp = client.get(f"/simulations/{sim_id}/costs/INVALID_BANK")
    assert invalid_resp.status_code == 404

    # Invalid simulation
    invalid_sim_resp = client.get("/simulations/invalid-id/costs")
    assert invalid_sim_resp.status_code == 404

    # ========================================================================
    # SUCCESS: Phase 8 Complete! ✅
    # ========================================================================
    print("\n✅ Phase 8 Complete E2E Test PASSED!")
    print(f"   - BANK_A total cost: ${bank_a_costs['total_cost'] / 100:.2f}")
    print(f"   - BANK_B total cost: ${bank_b_costs['total_cost'] / 100:.2f}")
    print(f"   - Settlement rate: {metrics['settlement_rate'] * 100:.1f}%")
```

**Run the complete test**:
```bash
pytest api/tests/integration/test_phase8_complete.py -v -s
```

**Expected**: Complete E2E workflow should PASS ✅

#### 5.2 Update Documentation

**Update these files:**

1. **`docs/grand_plan.md`**
   ```markdown
   ### Phase 8: Cost Model & Metrics ✅ COMPLETE

   **Status**: 100% Complete
   **Timeline**: Completed [DATE]

   #### Components
   - [x] Cost accrual (Rust) - liquidity, delay, collateral, penalties
   - [x] Cost accumulation and tracking
   - [x] FFI exposure of cost data
   - [x] API endpoints for cost queries
   - [x] System metrics aggregation
   - [x] Comprehensive test coverage

   #### Deliverables
   - `/simulations/{id}/costs` - Get all agent costs
   - `/simulations/{id}/costs/{agent_id}` - Get specific agent costs
   - `/simulations/{id}/metrics` - Get system-wide KPIs
   - `/metrics` - Prometheus-compatible metrics (optional)
   ```

2. **`docs/api.md`** (or create if doesn't exist)
   ```markdown
   ## Cost Query Endpoints

   ### GET /simulations/{sim_id}/costs

   Retrieve accumulated costs for all agents.

   **Response**:
   ```json
   {
     "costs": {
       "BANK_A": {
         "liquidity_cost": 125000,
         "delay_cost": 5000,
         "collateral_cost": 10000,
         "penalty_cost": 0,
         "split_friction_cost": 500,
         "total_cost": 140500,
         "peak_net_debit": -500000
       },
       "BANK_B": { ... }
     }
   }
   ```

   ### GET /simulations/{sim_id}/costs/{agent_id}

   Retrieve costs for a specific agent.

   ### GET /simulations/{sim_id}/metrics

   Retrieve system-wide KPIs.

   **Response**:
   ```json
   {
     "total_transactions": 1000,
     "settled_transactions": 850,
     "settlement_rate": 0.85,
     "queue1_total_size": 120,
     "queue2_size": 30,
     "current_tick": 100,
     "current_day": 1
   }
   ```
   ```

3. **`README.md`**

   Add example usage:
   ```markdown
   ## Querying Costs

   After running a simulation, query accumulated costs:

   ```bash
   # Get all costs
   curl http://localhost:8000/simulations/{sim_id}/costs

   # Get specific agent costs
   curl http://localhost:8000/simulations/{sim_id}/costs/BANK_A

   # Get system metrics
   curl http://localhost:8000/simulations/{sim_id}/metrics
   ```
   ```

4. **`backend/CLAUDE.md`** (if exists)

   Add FFI patterns section:
   ```markdown
   ## Cost Query Patterns

   When exposing aggregated data from Rust to Python:
   - Use PyDict for flexible dictionary returns
   - Include all fields (don't hide data)
   - Return Option<> for queries that might fail
   - Document all fields in docstrings
   ```

#### 5.3 Run Full Test Suite

```bash
# Rust tests
cd backend
cargo test

# Python tests
cd ../api
pytest -v

# Specific Phase 8 tests
pytest tests/integration/test_cost_ffi.py -v
pytest tests/integration/test_api_costs.py -v
pytest tests/integration/test_phase8_complete.py -v
```

**Expected**: All tests PASS ✅

---

## Testing Strategy (TDD Summary)

### Test Pyramid

```
                    E2E Tests (8 tests)
                   /                    \
              API Endpoint Tests      Complete Workflow
                 (test_api_costs.py)  (test_phase8_complete.py)
                /                                            \
           FFI Integration Tests (10 tests)
          (test_cost_ffi.py)
        /                              \
   FFI Unit Tests (4 tests)      Determinism Tests
  (test_cost_ffi.rs)             Cost Accumulation
 /                                                \
Rust Core Tests (existing)
Cost accrual, accumulation, breakdown
```

### Coverage Targets

- **Rust FFI Methods**: 100% (all code paths)
- **API Endpoints**: 100% (success + all error cases)
- **Integration Workflows**: E2E scenario coverage
- **Overall Phase 8 Code**: >90%

### Test Execution Order (TDD)

1. **RED**: Write tests → All FAIL ❌
2. **GREEN**: Implement code → Tests PASS ✅
3. **REFACTOR**: Clean up, optimize
4. **REPEAT**: For each component

---

## Success Criteria

### Functional Requirements

- ✅ All 5 cost types queryable via API
  - Liquidity cost (overdraft)
  - Delay cost (time penalties)
  - Collateral cost (posting fees)
  - Penalty cost (missed deadlines)
  - Split friction cost (splitting fees)
- ✅ Per-agent cost queries work
- ✅ All-agents cost queries work
- ✅ System metrics endpoint works
- ✅ Error handling (404 for invalid agent/sim)

### Non-Functional Requirements

- ✅ No memory leaks at FFI boundary
- ✅ Deterministic results (same seed = same costs)
- ✅ No float contamination (all costs are i64)
- ✅ Performance: <10ms query latency
- ✅ All tests pass (Rust + Python)

### Documentation Requirements

- ✅ API docs updated with new endpoints
- ✅ OpenAPI schema includes examples
- ✅ README has usage examples
- ✅ grand_plan.md marked complete
- ✅ FFI patterns documented

---

## Timeline & Milestones

| Day | Phase | Milestone | Hours |
|-----|-------|-----------|-------|
| 1 AM | 1 | All tests written and FAILING | 2 |
| 1 PM | 2 | FFI layer implemented, FFI tests PASS | 3 |
| 2 AM | 3 | API layer implemented, API tests PASS | 3 |
| 2 PM | 4 | Optional: Prometheus endpoint | 2 |
| 3 | 5 | Integration test + docs, Phase 8 COMPLETE | 3 |

**Total**: 13 hours over 2-3 days

---

## Risk Assessment

### Low Risk ✅

- **Rust implementation complete**: Just exposing existing functionality
- **Patterns established**: Follow existing FFI/API patterns
- **Well-tested foundation**: Cost accrual already tested in Rust

### Medium Risk ⚠️

- **PyDict serialization**: Ensure all types convert correctly (int, not float)
- **FFI error handling**: Must catch all Rust panics at boundary

### Mitigation Strategies

1. **Type safety**: Use Pydantic for validation at API layer
2. **Error boundaries**: Wrap all FFI calls in try/except
3. **Integration tests**: Test full workflow, not just units
4. **Incremental testing**: Test after each component (TDD approach)

---

## Rollback Plan

If issues arise during implementation:

1. **FFI issues**: Rust layer works standalone, can defer API
2. **API issues**: FFI works, can expose via alternative means (CLI, direct Python)
3. **Performance issues**: Can optimize queries post-MVP
4. **Test failures**: TDD approach means we catch issues early

---

## Post-Completion

### Phase 8 Delivers:

- ✅ Complete cost observability via API
- ✅ System health metrics for monitoring
- ✅ Foundation for Phase 9 (performance optimization)
- ✅ Production-ready monitoring endpoints

### Next Steps (Phase 9):

- Performance benchmarking using cost metrics
- Optimization based on cost bottlenecks
- Advanced analytics dashboards

---

## Appendix: Key Files

### New Files Created

```
api/tests/integration/test_cost_ffi.py          # FFI integration tests
api/tests/integration/test_api_costs.py         # API endpoint tests
api/tests/integration/test_phase8_complete.py   # E2E workflow test
backend/tests/test_cost_ffi.rs                  # FFI unit tests (optional)
docs/plans/phase8_completion_plan.md            # This document
```

### Modified Files

```
backend/src/ffi/orchestrator.rs                 # Add 3 FFI methods
api/payment_simulator/api/main.py               # Add 3-4 endpoints + models
docs/grand_plan.md                              # Mark Phase 8 complete
docs/api.md                                     # Document new endpoints
README.md                                       # Add usage examples
```

### Estimated Lines of Code

- **Rust (FFI)**: ~150 LOC
- **Python (API)**: ~200 LOC
- **Python (Tests)**: ~500 LOC
- **Documentation**: ~300 LOC
- **Total**: ~1,150 LOC

---

**Last Updated**: 2025-10-30
**Plan Status**: Ready for Implementation
**Approval Required**: Yes (review before starting)
