# Phase 8 API Completion: Cost & Metrics Exposure

## Status
- **Rust Backend**: ✅ 100% complete (all 5 cost types operational)
- **Python API Layer**: ❌ 0% complete (no endpoints yet)
- **Estimated Effort**: 2-3 days

## Objective
Expose cost data and system metrics via REST API following TDD principles.

---

## Part 1: Test-Driven Development Plan

### 1.1 FFI Layer Tests (Write First)

**File**: `api/tests/integration/test_cost_ffi.py`

```python
def test_get_agent_accumulated_costs():
    """FFI returns all 5 cost types for an agent."""
    # GIVEN: Simulation with costs accumulated
    orch = create_orchestrator_with_costs()

    # WHEN: Query agent costs
    costs = orch.get_agent_accumulated_costs("BANK_A")

    # THEN: All cost types present
    assert "liquidity_cost" in costs
    assert "collateral_cost" in costs
    assert "delay_cost" in costs
    assert "split_friction_cost" in costs
    assert "deadline_penalty" in costs
    assert all(isinstance(v, int) for v in costs.values())

def test_get_system_metrics():
    """FFI returns comprehensive system-wide metrics."""
    # GIVEN: Simulation with activity
    orch = create_orchestrator_with_activity()

    # WHEN: Query system metrics
    metrics = orch.get_system_metrics()

    # THEN: Contains expected KPIs
    assert metrics["total_arrivals"] >= 0
    assert metrics["total_settlements"] >= 0
    assert 0.0 <= metrics["settlement_rate"] <= 1.0
    assert metrics["avg_delay_ticks"] >= 0.0
    assert metrics["max_delay_ticks"] >= 0
    assert metrics["queue1_total_size"] >= 0
    assert metrics["queue2_total_size"] >= 0
    assert "peak_overdraft" in metrics

def test_cost_accumulation_over_ticks():
    """Costs increase monotonically over ticks."""
    # GIVEN: Agent with overdraft
    orch = create_orchestrator()
    initial_costs = orch.get_agent_accumulated_costs("BANK_A")

    # WHEN: Run ticks with overdraft
    for _ in range(10):
        orch.tick()

    # THEN: Liquidity costs increased
    final_costs = orch.get_agent_accumulated_costs("BANK_A")
    assert final_costs["liquidity_cost"] > initial_costs["liquidity_cost"]
```

### 1.2 API Endpoint Tests (Write First)

**File**: `api/tests/integration/test_cost_api.py`

```python
@pytest.mark.asyncio
async def test_get_simulation_costs_endpoint(test_client):
    """GET /simulations/{id}/costs returns cost breakdown."""
    # GIVEN: Running simulation
    sim_id = await create_test_simulation(test_client)
    await run_simulation_ticks(test_client, sim_id, 10)

    # WHEN: Query costs
    response = await test_client.get(f"/api/simulations/{sim_id}/costs")

    # THEN: Returns per-agent breakdown
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "total_system_cost" in data

    agent_costs = data["agents"]["BANK_A"]
    assert "liquidity_cost" in agent_costs
    assert "collateral_cost" in agent_costs
    assert "delay_cost" in agent_costs
    assert "split_friction_cost" in agent_costs
    assert "deadline_penalty" in agent_costs
    assert "total_cost" in agent_costs

@pytest.mark.asyncio
async def test_get_simulation_metrics_endpoint(test_client):
    """GET /simulations/{id}/metrics returns comprehensive KPIs."""
    # GIVEN: Running simulation
    sim_id = await create_test_simulation(test_client)
    await run_simulation_ticks(test_client, sim_id, 10)

    # WHEN: Query metrics
    response = await test_client.get(f"/api/simulations/{sim_id}/metrics")

    # THEN: Returns system-wide metrics
    assert response.status_code == 200
    data = response.json()

    # Settlement metrics
    assert "total_arrivals" in data
    assert "total_settlements" in data
    assert "settlement_rate" in data

    # Delay metrics
    assert "avg_delay_ticks" in data
    assert "max_delay_ticks" in data

    # Queue metrics
    assert "queue1_total_size" in data
    assert "queue2_total_size" in data

    # Liquidity metrics
    assert "peak_overdraft" in data
    assert "agents_in_overdraft" in data

@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint(test_client):
    """GET /metrics returns Prometheus-formatted metrics."""
    # GIVEN: Running simulations
    sim1 = await create_test_simulation(test_client, name="sim1")
    sim2 = await create_test_simulation(test_client, name="sim2")

    # WHEN: Query Prometheus endpoint
    response = await test_client.get("/metrics")

    # THEN: Returns Prometheus text format
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"

    text = response.text
    assert "# HELP payment_simulator_total_arrivals" in text
    assert "# TYPE payment_simulator_total_arrivals counter" in text
    assert "payment_simulator_total_arrivals{simulation_id=" in text

@pytest.mark.asyncio
async def test_costs_endpoint_404_for_nonexistent_simulation(test_client):
    """Returns 404 for non-existent simulation."""
    response = await test_client.get("/api/simulations/nonexistent/costs")
    assert response.status_code == 404
```

### 1.3 Unit Tests for Response Models (Write First)

**File**: `api/tests/unit/test_cost_models.py`

```python
def test_agent_cost_breakdown_model():
    """AgentCostBreakdown validates correctly."""
    breakdown = AgentCostBreakdown(
        liquidity_cost=1000,
        collateral_cost=500,
        delay_cost=200,
        split_friction_cost=50,
        deadline_penalty=0,
        total_cost=1750
    )
    assert breakdown.total_cost == 1750

def test_system_metrics_model():
    """SystemMetrics validates correctly."""
    metrics = SystemMetrics(
        total_arrivals=100,
        total_settlements=90,
        settlement_rate=0.9,
        avg_delay_ticks=2.5,
        max_delay_ticks=10,
        queue1_total_size=5,
        queue2_total_size=3,
        peak_overdraft=50000,
        agents_in_overdraft=2
    )
    assert metrics.settlement_rate == 0.9
    assert 0.0 <= metrics.settlement_rate <= 1.0
```

---

## Part 2: Implementation Steps (After Tests Written)

### Step 1: Rust FFI Methods
**File**: `backend/src/ffi/orchestrator.rs`

```rust
#[pymethods]
impl PyOrchestrator {
    /// Get accumulated costs for a specific agent
    fn get_agent_accumulated_costs(
        &self,
        py: Python,
        agent_id: String,
    ) -> PyResult<Py<PyDict>> {
        let costs = self.inner.get_agent_costs(&agent_id)
            .ok_or_else(|| PyKeyError::new_err(format!("Agent not found: {}", agent_id)))?;

        let dict = PyDict::new(py);
        dict.set_item("liquidity_cost", costs.liquidity_cost)?;
        dict.set_item("collateral_cost", costs.collateral_cost)?;
        dict.set_item("delay_cost", costs.delay_cost)?;
        dict.set_item("split_friction_cost", costs.split_friction_cost)?;
        dict.set_item("deadline_penalty", costs.deadline_penalty)?;
        dict.set_item("total_cost", costs.total())?;

        Ok(dict.into())
    }

    /// Get system-wide metrics
    fn get_system_metrics(&self, py: Python) -> PyResult<Py<PyDict>> {
        let metrics = self.inner.calculate_system_metrics();

        let dict = PyDict::new(py);
        dict.set_item("total_arrivals", metrics.total_arrivals)?;
        dict.set_item("total_settlements", metrics.total_settlements)?;
        dict.set_item("settlement_rate", metrics.settlement_rate)?;
        dict.set_item("avg_delay_ticks", metrics.avg_delay_ticks)?;
        dict.set_item("max_delay_ticks", metrics.max_delay_ticks)?;
        dict.set_item("queue1_total_size", metrics.queue1_total_size)?;
        dict.set_item("queue2_total_size", metrics.queue2_total_size)?;
        dict.set_item("peak_overdraft", metrics.peak_overdraft)?;
        dict.set_item("agents_in_overdraft", metrics.agents_in_overdraft)?;

        Ok(dict.into())
    }
}
```

**Corresponding Rust Core Methods** (if not exist):
**File**: `backend/src/orchestrator/engine.rs`

```rust
impl Orchestrator {
    /// Get accumulated costs for a specific agent
    pub fn get_agent_costs(&self, agent_id: &str) -> Option<&CostBreakdown> {
        self.accumulated_costs.get(agent_id)
    }

    /// Calculate comprehensive system metrics
    pub fn calculate_system_metrics(&self) -> SystemMetrics {
        let total_arrivals = self.state.total_arrivals();
        let total_settlements = self.state.total_settlements();

        let settlement_rate = if total_arrivals > 0 {
            total_settlements as f64 / total_arrivals as f64
        } else {
            0.0
        };

        let delays = self.state.calculate_all_delays();
        let avg_delay = if !delays.is_empty() {
            delays.iter().sum::<usize>() as f64 / delays.len() as f64
        } else {
            0.0
        };
        let max_delay = delays.iter().max().copied().unwrap_or(0);

        let queue1_size: usize = self.state.agents.values()
            .map(|a| a.queue_outgoing.len())
            .sum();
        let queue2_size = self.state.rtgs_queue.len();

        let peak_overdraft = self.state.agents.values()
            .map(|a| a.balance.min(0).abs())
            .max()
            .unwrap_or(0);

        let agents_in_overdraft = self.state.agents.values()
            .filter(|a| a.balance < 0)
            .count();

        SystemMetrics {
            total_arrivals,
            total_settlements,
            settlement_rate,
            avg_delay_ticks: avg_delay,
            max_delay_ticks: max_delay,
            queue1_total_size: queue1_size,
            queue2_total_size: queue2_size,
            peak_overdraft,
            agents_in_overdraft,
        }
    }
}

#[derive(Debug, Clone)]
pub struct SystemMetrics {
    pub total_arrivals: usize,
    pub total_settlements: usize,
    pub settlement_rate: f64,
    pub avg_delay_ticks: f64,
    pub max_delay_ticks: usize,
    pub queue1_total_size: usize,
    pub queue2_total_size: usize,
    pub peak_overdraft: i64,
    pub agents_in_overdraft: usize,
}
```

### Step 2: Pydantic Response Models
**File**: `api/payment_simulator/api/models.py`

```python
from pydantic import BaseModel, Field
from typing import Dict

class AgentCostBreakdown(BaseModel):
    """Cost breakdown for a single agent."""
    liquidity_cost: int = Field(..., description="Overdraft cost in cents")
    collateral_cost: int = Field(..., description="Collateral opportunity cost in cents")
    delay_cost: int = Field(..., description="Queue 1 delay cost in cents")
    split_friction_cost: int = Field(..., description="Transaction splitting cost in cents")
    deadline_penalty: int = Field(..., description="Deadline miss penalties in cents")
    total_cost: int = Field(..., description="Sum of all costs")

class CostResponse(BaseModel):
    """Response model for /simulations/{id}/costs endpoint."""
    simulation_id: str
    tick: int
    day: int
    agents: Dict[str, AgentCostBreakdown]
    total_system_cost: int

class SystemMetrics(BaseModel):
    """System-wide performance metrics."""
    total_arrivals: int
    total_settlements: int
    settlement_rate: float = Field(..., ge=0.0, le=1.0)
    avg_delay_ticks: float
    max_delay_ticks: int
    queue1_total_size: int
    queue2_total_size: int
    peak_overdraft: int
    agents_in_overdraft: int

class MetricsResponse(BaseModel):
    """Response model for /simulations/{id}/metrics endpoint."""
    simulation_id: str
    tick: int
    day: int
    metrics: SystemMetrics
```

### Step 3: FastAPI Endpoints
**File**: `api/payment_simulator/api/main.py`

```python
@app.get("/api/simulations/{simulation_id}/costs", response_model=CostResponse)
async def get_simulation_costs(simulation_id: str):
    """
    Get accumulated costs for all agents in a simulation.

    Returns per-agent cost breakdown and total system cost.
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")

    sim = simulation_manager.simulations[simulation_id]
    orchestrator = sim.orchestrator

    # Get costs for all agents
    agent_costs = {}
    total_system_cost = 0

    for agent_id in sim.config.agents.keys():
        costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)
        breakdown = AgentCostBreakdown(**costs_dict)
        agent_costs[agent_id] = breakdown
        total_system_cost += breakdown.total_cost

    return CostResponse(
        simulation_id=simulation_id,
        tick=orchestrator.current_tick(),
        day=orchestrator.current_day(),
        agents=agent_costs,
        total_system_cost=total_system_cost
    )

@app.get("/api/simulations/{simulation_id}/metrics", response_model=MetricsResponse)
async def get_simulation_metrics(simulation_id: str):
    """
    Get comprehensive system-wide metrics.

    Returns settlement rates, delays, queue statistics, and liquidity usage.
    """
    if simulation_id not in simulation_manager.simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")

    sim = simulation_manager.simulations[simulation_id]
    orchestrator = sim.orchestrator

    metrics_dict = orchestrator.get_system_metrics()
    metrics = SystemMetrics(**metrics_dict)

    return MetricsResponse(
        simulation_id=simulation_id,
        tick=orchestrator.current_tick(),
        day=orchestrator.current_day(),
        metrics=metrics
    )

@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format for all active simulations.
    """
    lines = []

    # Define metric metadata
    lines.append("# HELP payment_simulator_total_arrivals Total transactions arrived")
    lines.append("# TYPE payment_simulator_total_arrivals counter")
    lines.append("# HELP payment_simulator_total_settlements Total transactions settled")
    lines.append("# TYPE payment_simulator_total_settlements counter")
    lines.append("# HELP payment_simulator_settlement_rate Settlement rate (0-1)")
    lines.append("# TYPE payment_simulator_settlement_rate gauge")
    lines.append("# HELP payment_simulator_queue1_size Queue 1 total size")
    lines.append("# TYPE payment_simulator_queue1_size gauge")
    lines.append("# HELP payment_simulator_queue2_size Queue 2 (RTGS) size")
    lines.append("# TYPE payment_simulator_queue2_size gauge")

    # Collect metrics from all simulations
    for sim_id, sim in simulation_manager.simulations.items():
        metrics_dict = sim.orchestrator.get_system_metrics()

        lines.append(f'payment_simulator_total_arrivals{{simulation_id="{sim_id}"}} {metrics_dict["total_arrivals"]}')
        lines.append(f'payment_simulator_total_settlements{{simulation_id="{sim_id}"}} {metrics_dict["total_settlements"]}')
        lines.append(f'payment_simulator_settlement_rate{{simulation_id="{sim_id}"}} {metrics_dict["settlement_rate"]:.4f}')
        lines.append(f'payment_simulator_queue1_size{{simulation_id="{sim_id}"}} {metrics_dict["queue1_total_size"]}')
        lines.append(f'payment_simulator_queue2_size{{simulation_id="{sim_id}"}} {metrics_dict["queue2_total_size"]}')

    return "\n".join(lines) + "\n"
```

### Step 4: Integration Tests
Run the tests written in Part 1 to verify implementation.

```bash
# Run FFI tests
pytest api/tests/integration/test_cost_ffi.py -v

# Run API tests
pytest api/tests/integration/test_cost_api.py -v

# Run all tests
pytest api/tests/ -v
```

---

## Part 3: Success Criteria

### Functional Requirements
- ✅ Can query per-agent costs via `/simulations/{id}/costs`
- ✅ Can query system-wide metrics via `/simulations/{id}/metrics`
- ✅ Prometheus `/metrics` endpoint operational
- ✅ All 5 cost types exposed (liquidity, collateral, delay, split, deadline)
- ✅ Metrics include settlement rate, delays, queue sizes, liquidity usage

### Testing Requirements
- ✅ FFI tests pass (cost queries across boundary)
- ✅ API integration tests pass (E2E via HTTP)
- ✅ Unit tests pass (Pydantic model validation)
- ✅ Prometheus format validated (parseable by Prometheus)

### Performance Requirements
- ✅ Cost queries complete in <10ms (no heavy computation)
- ✅ Metrics endpoint scales to 10+ active simulations
- ✅ Prometheus endpoint returns in <50ms

---

## Part 4: Documentation Updates

### API Documentation
**File**: `docs/api.md` (update)

Add new endpoint documentation:

```markdown
### GET /api/simulations/{simulation_id}/costs

Returns accumulated costs for all agents.

**Response**:
```json
{
  "simulation_id": "sim-001",
  "tick": 150,
  "day": 1,
  "agents": {
    "BANK_A": {
      "liquidity_cost": 1000,
      "collateral_cost": 500,
      "delay_cost": 200,
      "split_friction_cost": 50,
      "deadline_penalty": 0,
      "total_cost": 1750
    }
  },
  "total_system_cost": 15000
}
```

### GET /api/simulations/{simulation_id}/metrics

Returns comprehensive system-wide metrics.

**Response**:
```json
{
  "simulation_id": "sim-001",
  "tick": 150,
  "day": 1,
  "metrics": {
    "total_arrivals": 1000,
    "total_settlements": 950,
    "settlement_rate": 0.95,
    "avg_delay_ticks": 2.5,
    "max_delay_ticks": 20,
    "queue1_total_size": 45,
    "queue2_total_size": 5,
    "peak_overdraft": 500000,
    "agents_in_overdraft": 3
  }
}
```

### GET /metrics

Prometheus-compatible metrics for all active simulations.

**Response** (text/plain):
```
# HELP payment_simulator_total_arrivals Total transactions arrived
# TYPE payment_simulator_total_arrivals counter
payment_simulator_total_arrivals{simulation_id="sim-001"} 1000
...
```
```

---

## Part 5: Implementation Order (TDD Flow)

### Day 1: FFI Layer (4-5 hours)
1. ✅ Write FFI tests (`test_cost_ffi.py`) - **RED**
2. ✅ Implement Rust core methods (`calculate_system_metrics()`)
3. ✅ Implement FFI bindings (`get_agent_accumulated_costs`, `get_system_metrics`)
4. ✅ Run tests - **GREEN**
5. ✅ Refactor if needed

### Day 2: API Layer (4-5 hours)
1. ✅ Write API tests (`test_cost_api.py`) - **RED**
2. ✅ Create Pydantic models (`models.py`)
3. ✅ Implement endpoints (`main.py`)
4. ✅ Run tests - **GREEN**
5. ✅ Manual testing with Swagger UI

### Day 3: Prometheus & Documentation (2-3 hours)
1. ✅ Write Prometheus endpoint tests - **RED**
2. ✅ Implement `/metrics` endpoint
3. ✅ Validate with Prometheus parser
4. ✅ Run all tests - **GREEN**
5. ✅ Update API documentation
6. ✅ Update configuration schema docs

---

## Part 6: Validation Checklist

Before marking Phase 8 complete:

- [ ] All tests pass (Rust + Python)
- [ ] API endpoints documented in `docs/api.md`
- [ ] Swagger UI shows new endpoints correctly
- [ ] Manual smoke test with test scenario
- [ ] Prometheus endpoint validated with `promtool check metrics`
- [ ] Performance targets met (<10ms for cost queries)
- [ ] No regressions in existing tests
- [ ] Update `grand_plan.md` to mark Phase 8 as ✅ COMPLETE

---

## Notes

### Why TDD for This Phase?
1. **Clear specification**: Grand plan has exact requirements
2. **Cross-layer testing**: FFI boundary needs strong contracts
3. **Regression prevention**: Existing functionality must not break
4. **Documentation**: Tests serve as living API examples

### Known Risks
1. **Rust methods may not exist**: May need to implement `calculate_system_metrics()` in Rust core
2. **Performance**: Metrics calculation must be O(n) or better
3. **FFI overhead**: Keep boundary crossings minimal

### Future Enhancements (Not in Scope)
- WebSocket streaming of metrics (Phase 14)
- Historical metrics queries (use Phase 10 persistence)
- Per-transaction cost attribution
- Cost predictions based on policy
