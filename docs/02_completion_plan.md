# Payment Simulator - Foundation Completion Plan (Final)
**Version:** 3.0 (After Triple Review)  
**Target:** Complete integration layer in **2-3 weeks**  
**Current Status:** Rust engine 100% complete, integration layer 5% complete  
**Last Updated:** October 28, 2025

---

## 🎯 Executive Summary

**CRITICAL INSIGHT:** The Rust simulation engine is **DONE**. All foundational phases (1-6) are complete:

- ✅ Core models
- ✅ RTGS + LSM settlement
- ✅ Two-queue architecture  
- ✅ Policy framework (5 policies)
- ✅ Orchestrator tick loop (9 steps)
- ✅ Arrival generation
- ✅ Transaction splitting

**What's Actually Left:**
- ❌ PyO3 FFI bindings (BLOCKER)
- ❌ Python FastAPI API
- ❌ CLI tool
- ❌ Integration tests

**Revised Timeline:** 2-3 weeks (not 3-4 weeks as originally estimated)

---

## 📋 What We Now Know

### **The Orchestrator Tick Loop is COMPLETE**

Found in `backend/src/orchestrator/engine.rs` (lines 4698-4986):

```rust
pub fn tick(&mut self) -> Result<TickResult, SimulationError> {
    // Step 1: Generate arrivals ✅
    // Step 2: Evaluate policies (including splitting) ✅
    // Step 3: Try RTGS settlement ✅
    // Step 4: Process RTGS queue ✅
    // Step 5: Run LSM coordinator ✅
    // Step 6: Accrue costs ✅
    // Step 7: Advance time ✅
    // Step 8: End-of-day handling ✅
}
```

### **Transaction Splitting is IMPLEMENTED**

Found in the same tick loop (lines 4792-4878):
- Policy returns `SubmitPartial { tx_id, num_splits }`
- Creates N child transactions with `Transaction::new_split()`
- Charges split friction cost
- All children submitted to pending settlements

### **The FFI is Just a Placeholder**

Found in `backend/src/lib.rs` (lines 2500-2505):
```rust
#[pymodule]
fn payment_simulator_core_rs(_py: Python, _m: &PyModule) -> PyResult<()> {
    // PyO3 exports will be added in Phase 5
    Ok(())
}
```

This means **ALL remaining work is in the integration layer.**

---

## 🚧 Priority 1: PyO3 FFI Bindings (Days 1-7)

**Current State:** Placeholder only  
**Target:** Working Python imports and basic operations  
**Effort:** 5-7 days  
**Status:** CRITICAL BLOCKER

### **Day 1: Type Wrapper Foundation**

#### Task 1.1: Create PyOrchestrator Wrapper
```rust
// backend/src/lib.rs - Replace placeholder with:

#[cfg(feature = "pyo3")]
use pyo3::prelude::*;
#[cfg(feature = "pyo3")]
use pyo3::types::{PyDict, PyList};

#[cfg(feature = "pyo3")]
#[pyclass(name = "Orchestrator")]
pub struct PyOrchestrator {
    inner: orchestrator::Orchestrator,
}

#[cfg(feature = "pyo3")]
#[pymethods]
impl PyOrchestrator {
    #[new]
    pub fn new(py: Python, config: Py<PyDict>) -> PyResult<Self> {
        // Step 1: Extract and validate config from Python dict
        let config_dict = config.as_ref(py);
        
        // Step 2: Convert to OrchestratorConfig
        let rust_config = config_from_py(py, config_dict)?;
        
        // Step 3: Create orchestrator
        let inner = orchestrator::Orchestrator::new(rust_config)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create orchestrator: {}", e)
            ))?;
        
        Ok(PyOrchestrator { inner })
    }
    
    pub fn tick(&mut self, py: Python) -> PyResult<PyObject> {
        // Call inner tick
        let result = self.inner.tick()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Tick failed: {}", e)
            ))?;
        
        // Convert TickResult to Python dict
        tick_result_to_py(py, &result)
    }
    
    pub fn get_state(&self, py: Python) -> PyResult<PyObject> {
        // Get state snapshot
        let state = self.inner.state();
        
        // Convert to Python dict
        state_to_py(py, state)
    }
    
    pub fn current_tick(&self) -> usize {
        self.inner.current_tick()
    }
    
    pub fn current_day(&self) -> usize {
        self.inner.current_day()
    }
}

#[cfg(feature = "pyo3")]
#[pymodule]
fn payment_simulator_core_rs(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PyOrchestrator>()?;
    Ok(())
}
```

**Deliverable:** Basic wrapper structure

---

### **Day 2-3: Type Conversion Functions**

#### Task 1.2: Python → Rust Conversion

```rust
// backend/src/lib.rs

#[cfg(feature = "pyo3")]
fn config_from_py(py: Python, dict: &PyDict) -> PyResult<orchestrator::OrchestratorConfig> {
    use pyo3::types::PyList;
    
    // Extract required fields
    let ticks_per_day = dict.get_item("ticks_per_day")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("ticks_per_day"))?
        .extract::<usize>()?;
    
    let num_days = dict.get_item("num_days")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("num_days"))?
        .extract::<usize>()?;
    
    let rng_seed = dict.get_item("rng_seed")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("rng_seed"))?
        .extract::<u64>()?;
    
    // Parse agent configs
    let agent_configs_py = dict.get_item("agent_configs")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("agent_configs"))?
        .downcast::<PyList>()?;
    
    let mut agent_configs = Vec::new();
    for item in agent_configs_py.iter() {
        let agent_dict = item.downcast::<PyDict>()?;
        agent_configs.push(agent_config_from_py(py, agent_dict)?);
    }
    
    // Parse cost rates (optional, use defaults if not provided)
    let cost_rates = if let Some(cost_rates_py) = dict.get_item("cost_rates")? {
        cost_rates_from_py(py, cost_rates_py.downcast::<PyDict>()?)?
    } else {
        orchestrator::CostRates::default()
    };
    
    // Parse LSM config (optional)
    let lsm_config = if let Some(lsm_py) = dict.get_item("lsm_config")? {
        lsm_config_from_py(py, lsm_py.downcast::<PyDict>()?)?
    } else {
        settlement::lsm::LsmConfig::default()
    };
    
    Ok(orchestrator::OrchestratorConfig {
        ticks_per_day,
        num_days,
        rng_seed,
        agent_configs,
        cost_rates,
        lsm_config,
    })
}

#[cfg(feature = "pyo3")]
fn agent_config_from_py(py: Python, dict: &PyDict) -> PyResult<orchestrator::AgentConfig> {
    let id = dict.get_item("id")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("id"))?
        .extract::<String>()?;
    
    let opening_balance = dict.get_item("balance")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("balance"))?
        .extract::<i64>()?;
    
    // Validate money is integer
    if !dict.get_item("balance")?.unwrap().is_instance_of::<pyo3::types::PyLong>()? {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("balance must be integer, got float")
        ));
    }
    
    let credit_limit = dict.get_item("credit_limit")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("credit_limit"))?
        .extract::<i64>()?;
    
    // Parse policy config
    let policy_str = dict.get_item("policy")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>("policy"))?
        .extract::<String>()?;
    
    let policy = match policy_str.as_str() {
        "fifo" => orchestrator::PolicyConfig::Fifo,
        "deadline" => {
            let urgency = dict.get_item("urgency_threshold")?.map(|v| v.extract()).transpose()?.unwrap_or(10);
            orchestrator::PolicyConfig::Deadline { urgency_threshold: urgency }
        }
        "liquidity_aware" => {
            let buffer = dict.get_item("target_buffer")?.map(|v| v.extract()).transpose()?.unwrap_or(100_000);
            let urgency = dict.get_item("urgency_threshold")?.map(|v| v.extract()).transpose()?.unwrap_or(10);
            orchestrator::PolicyConfig::LiquidityAware { 
                target_buffer: buffer,
                urgency_threshold: urgency
            }
        }
        _ => return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unknown policy: {}", policy_str)
        )),
    };
    
    // Parse arrival config (optional)
    let arrival_config = if let Some(arrival_py) = dict.get_item("arrival_config")? {
        Some(arrival_config_from_py(py, arrival_py.downcast::<PyDict>()?)?)
    } else {
        None
    };
    
    Ok(orchestrator::AgentConfig {
        id,
        opening_balance,
        credit_limit,
        policy,
        arrival_config,
    })
}

#[cfg(feature = "pyo3")]
fn arrival_config_from_py(py: Python, dict: &PyDict) -> PyResult<arrivals::ArrivalConfig> {
    // TODO: Parse arrival configuration
    // rate_per_tick, distribution, counterparty_weights, deadline_offset
    todo!()
}

#[cfg(feature = "pyo3")]
fn cost_rates_from_py(py: Python, dict: &PyDict) -> PyResult<orchestrator::CostRates> {
    // TODO: Parse cost rates
    todo!()
}

#[cfg(feature = "pyo3")]
fn lsm_config_from_py(py: Python, dict: &PyDict) -> PyResult<settlement::lsm::LsmConfig> {
    // TODO: Parse LSM config
    todo!()
}
```

**Deliverable:** Config parsing from Python dicts

---

#### Task 1.3: Rust → Python Conversion

```rust
#[cfg(feature = "pyo3")]
fn tick_result_to_py(py: Python, result: &orchestrator::TickResult) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    
    dict.set_item("tick", result.tick)?;
    dict.set_item("num_arrivals", result.num_arrivals)?;
    dict.set_item("num_settlements", result.num_settlements)?;
    dict.set_item("num_lsm_releases", result.num_lsm_releases)?;
    dict.set_item("total_cost", result.total_cost)?;
    
    Ok(dict.into())
}

#[cfg(feature = "pyo3")]
fn state_to_py(py: Python, state: &models::SimulationState) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    
    // Convert agents
    let agents_dict = PyDict::new(py);
    for (agent_id, agent) in state.agents() {
        let agent_dict = agent_to_py(py, agent)?;
        agents_dict.set_item(agent_id, agent_dict)?;
    }
    dict.set_item("agents", agents_dict)?;
    
    // Convert transactions
    let transactions_dict = PyDict::new(py);
    for (tx_id, tx) in state.transactions() {
        let tx_dict = transaction_to_py(py, tx)?;
        transactions_dict.set_item(tx_id, tx_dict)?;
    }
    dict.set_item("transactions", transactions_dict)?;
    
    // Queue info
    dict.set_item("queue_size", state.queue_size())?;
    dict.set_item("queue_value", state.queue_value())?;
    
    Ok(dict.into())
}

#[cfg(feature = "pyo3")]
fn agent_to_py(py: Python, agent: &models::Agent) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    
    dict.set_item("id", agent.id())?;
    dict.set_item("balance", agent.balance())?;
    dict.set_item("credit_limit", agent.credit_limit())?;
    dict.set_item("available_liquidity", agent.available_liquidity())?;
    dict.set_item("is_using_credit", agent.is_using_credit())?;
    dict.set_item("credit_used", agent.credit_used())?;
    dict.set_item("liquidity_pressure", agent.liquidity_pressure())?;
    dict.set_item("outgoing_queue_size", agent.outgoing_queue_size())?;
    
    Ok(dict.into())
}

#[cfg(feature = "pyo3")]
fn transaction_to_py(py: Python, tx: &models::Transaction) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    
    dict.set_item("id", tx.id())?;
    dict.set_item("sender_id", tx.sender_id())?;
    dict.set_item("receiver_id", tx.receiver_id())?;
    dict.set_item("amount", tx.amount())?;
    dict.set_item("remaining_amount", tx.remaining_amount())?;
    dict.set_item("arrival_tick", tx.arrival_tick())?;
    dict.set_item("deadline_tick", tx.deadline_tick())?;
    dict.set_item("priority", tx.priority())?;
    dict.set_item("is_fully_settled", tx.is_fully_settled())?;
    dict.set_item("is_split", tx.is_split())?;
    
    if let Some(parent_id) = tx.parent_id() {
        dict.set_item("parent_id", parent_id)?;
    }
    
    Ok(dict.into())
}
```

**Deliverable:** Complete type conversion layer

---

### **Day 4-5: Build & Test FFI**

#### Task 1.4: Build with Maturin
```bash
# Build Rust with PyO3
cd backend
cargo build --release --features pyo3

# Check for errors
cargo clippy --features pyo3

# Build Python wheel
cd ..
maturin develop --release

# Verify installation
python3 -c "import payment_simulator_core_rs; print('✅ FFI works')"
```

**Deliverable:** Importable Python module

---

#### Task 1.5: Write Basic FFI Tests
```python
# tests/ffi/test_basic_ffi.py
import pytest
from payment_simulator_core_rs import Orchestrator

def test_ffi_import():
    """Verify module imports successfully."""
    from payment_simulator_core_rs import Orchestrator
    assert Orchestrator is not None

def test_ffi_orchestrator_creation():
    """Create orchestrator from Python config."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": "BANK_A",
                "balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": "fifo",
            },
            {
                "id": "BANK_B",
                "balance": 1_500_000,
                "credit_limit": 750_000,
                "policy": "fifo",
            },
        ],
    }
    
    orchestrator = Orchestrator(config)
    assert orchestrator is not None
    assert orchestrator.current_tick() == 0
    assert orchestrator.current_day() == 0

def test_ffi_tick():
    """Run a tick via FFI."""
    orchestrator = create_test_orchestrator()
    
    result = orchestrator.tick()
    
    assert "tick" in result
    assert "num_arrivals" in result
    assert "num_settlements" in result
    assert result["tick"] == 0

def test_ffi_get_state():
    """Get state via FFI."""
    orchestrator = create_test_orchestrator()
    
    state = orchestrator.get_state()
    
    assert "agents" in state
    assert "transactions" in state
    assert len(state["agents"]) == 2

def test_ffi_money_is_int():
    """Verify money values are integers across FFI."""
    orchestrator = create_test_orchestrator()
    
    state = orchestrator.get_state()
    
    for agent_id, agent in state["agents"].items():
        assert isinstance(agent["balance"], int), f"Balance is {type(agent['balance'])}"
        assert isinstance(agent["credit_limit"], int), f"Credit limit is {type(agent['credit_limit'])}"

def test_ffi_determinism():
    """Same seed produces identical results across FFI."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "balance": 1_000_000, "credit_limit": 0, "policy": "fifo"},
            {"id": "B", "balance": 1_000_000, "credit_limit": 0, "policy": "fifo"},
        ],
    }
    
    orch1 = Orchestrator(config)
    orch2 = Orchestrator(config)
    
    results1 = [orch1.tick() for _ in range(10)]
    results2 = [orch2.tick() for _ in range(10)]
    
    assert results1 == results2, "Results must be identical with same seed"

def test_ffi_error_handling():
    """Rust errors propagate as Python exceptions."""
    config = {
        "ticks_per_day": 0,  # Invalid!
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [],
    }
    
    with pytest.raises(RuntimeError, match="ticks_per_day"):
        Orchestrator(config)


def create_test_orchestrator():
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "balance": 1_000_000, "credit_limit": 0, "policy": "fifo"},
            {"id": "BANK_B", "balance": 1_000_000, "credit_limit": 0, "policy": "fifo"},
        ],
    }
    return Orchestrator(config)
```

**Deliverable:** FFI test suite passing

---

### **Day 6-7: Python Wrapper Class**

#### Task 1.6: Create RustBackend Wrapper
```python
# api/payment_simulator/backends/rust_backend.py
from typing import Dict, Any
from payment_simulator_core_rs import Orchestrator as RustOrchestrator
import logging

logger = logging.getLogger(__name__)


class RustBackend:
    """Safe wrapper around Rust FFI."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Rust orchestrator with validated config.
        
        Args:
            config: Configuration dict (pre-validated by Pydantic)
        
        Raises:
            ValueError: If configuration is invalid
            RuntimeError: If Rust initialization fails
        """
        self._validate_config(config)
        
        try:
            self._orchestrator = RustOrchestrator(config)
            logger.info("Rust orchestrator initialized successfully")
        except ValueError as e:
            logger.error(f"Invalid configuration: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error initializing Rust: {e}")
            raise RuntimeError(f"Rust initialization failed: {e}")
    
    def tick(self) -> Dict[str, Any]:
        """Advance simulation by one tick.
        
        Returns:
            Dictionary with tick results (arrivals, settlements, costs)
        
        Raises:
            RuntimeError: If tick fails
        """
        try:
            return self._orchestrator.tick()
        except Exception as e:
            logger.error(f"Tick failed: {e}")
            raise RuntimeError(f"Simulation error: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current simulation state snapshot.
        
        Returns:
            Dictionary with agents, transactions, queues
        """
        try:
            return self._orchestrator.get_state()
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            raise RuntimeError(f"State retrieval failed: {e}")
    
    def current_tick(self) -> int:
        """Get current tick number."""
        return self._orchestrator.current_tick()
    
    def current_day(self) -> int:
        """Get current day number."""
        return self._orchestrator.current_day()
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]):
        """Pre-validate config before passing to Rust.
        
        Catches common mistakes early with helpful error messages.
        """
        # Check required fields
        required = ["ticks_per_day", "rng_seed", "agent_configs"]
        for key in required:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")
        
        # Validate money values are integers
        for agent in config["agent_configs"]:
            if "balance" in agent and not isinstance(agent["balance"], int):
                raise ValueError(
                    f"Agent {agent['id']} balance must be int (cents), "
                    f"got {type(agent['balance']).__name__}"
                )
            if "credit_limit" in agent and not isinstance(agent["credit_limit"], int):
                raise ValueError(
                    f"Agent {agent['id']} credit_limit must be int (cents), "
                    f"got {type(agent['credit_limit']).__name__}"
                )
```

**Deliverable:** Python wrapper class

---

#### Task 1.7: Test Wrapper
```python
# tests/unit/test_rust_backend.py
import pytest
from payment_simulator.backends.rust_backend import RustBackend

def test_rust_backend_creation():
    config = create_valid_config()
    backend = RustBackend(config)
    assert backend is not None

def test_rust_backend_validates_money():
    config = create_valid_config()
    config["agent_configs"][0]["balance"] = 1000.50  # Float!
    
    with pytest.raises(ValueError, match="must be int"):
        RustBackend(config)

def test_rust_backend_tick():
    backend = RustBackend(create_valid_config())
    result = backend.tick()
    
    assert isinstance(result, dict)
    assert "tick" in result
    assert result["tick"] == 0

def test_rust_backend_get_state():
    backend = RustBackend(create_valid_config())
    state = backend.get_state()
    
    assert isinstance(state, dict)
    assert "agents" in state
    assert len(state["agents"]) == 2

def create_valid_config():
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "balance": 1000000, "credit_limit": 500000, "policy": "fifo"},
            {"id": "BANK_B", "balance": 1500000, "credit_limit": 750000, "policy": "fifo"},
        ],
    }
```

**Deliverable:** Wrapper tests passing

---

## 🚧 Priority 2: Python FastAPI Server (Days 8-12)

**Current State:** Only documentation  
**Target:** Working HTTP API  
**Effort:** 4-5 days  
**Dependencies:** FFI must be complete

### **Day 8-9: FastAPI Routes**

#### Task 2.1: Implement Core Endpoints
```python
# api/payment_simulator/api/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from uuid import uuid4
import logging

from ..backends.rust_backend import RustBackend

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Payment Simulator API",
    description="High-performance payment settlement simulator",
    version="0.1.0",
)

# In-memory simulation registry
simulations: Dict[str, RustBackend] = {}


class SimulationConfig(BaseModel):
    """Simulation configuration."""
    ticks_per_day: int = Field(ge=1, le=1000, description="Ticks per business day")
    num_days: int = Field(ge=1, description="Number of days to simulate")
    rng_seed: int = Field(description="RNG seed for determinism")
    agent_configs: list = Field(min_length=2, description="Agent configurations")
    cost_rates: Optional[dict] = None
    lsm_config: Optional[dict] = None


@app.post("/api/simulations", status_code=201)
async def create_simulation(config: SimulationConfig):
    """Create new simulation instance.
    
    Returns:
        simulation_id: Unique identifier for the simulation
    """
    sim_id = str(uuid4())
    
    try:
        backend = RustBackend(config.dict())
        simulations[sim_id] = backend
        
        logger.info(f"Created simulation {sim_id}")
        
        return {
            "simulation_id": sim_id,
            "status": "created",
            "current_tick": backend.current_tick(),
        }
    except ValueError as e:
        logger.error(f"Invalid config: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create simulation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/simulations/{sim_id}/tick")
async def tick(sim_id: str):
    """Advance simulation by one tick.
    
    Returns:
        Tick results including arrivals, settlements, costs
    """
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    backend = simulations[sim_id]
    
    try:
        result = backend.tick()
        return result
    except Exception as e:
        logger.error(f"Tick failed for {sim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/simulations/{sim_id}/state")
async def get_state(sim_id: str):
    """Get current simulation state.
    
    Returns:
        State snapshot including agents, transactions, queues
    """
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    backend = simulations[sim_id]
    
    try:
        state = backend.get_state()
        return {
            "simulation_id": sim_id,
            "current_tick": backend.current_tick(),
            "current_day": backend.current_day(),
            "state": state,
        }
    except Exception as e:
        logger.error(f"Failed to get state for {sim_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/simulations/{sim_id}")
async def delete_simulation(sim_id: str):
    """Delete simulation instance."""
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    del simulations[sim_id]
    logger.info(f"Deleted simulation {sim_id}")
    
    return {"status": "deleted"}


@app.get("/api/simulations")
async def list_simulations():
    """List all active simulations."""
    return {
        "simulations": [
            {
                "simulation_id": sim_id,
                "current_tick": backend.current_tick(),
                "current_day": backend.current_day(),
            }
            for sim_id, backend in simulations.items()
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "active_simulations": len(simulations),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**Deliverable:** Working API server

---

### **Day 10-11: E2E API Tests**

#### Task 2.2: Write API Integration Tests
```python
# tests/e2e/test_api.py
from fastapi.testclient import TestClient
from payment_simulator.api.main import app

client = TestClient(app)


def test_simulation_lifecycle():
    """Complete simulation lifecycle via API."""
    # 1. Create simulation
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "balance": 1000000, "credit_limit": 0, "policy": "fifo"},
            {"id": "BANK_B", "balance": 1500000, "credit_limit": 0, "policy": "fifo"},
        ],
    }
    
    response = client.post("/api/simulations", json=config)
    assert response.status_code == 201
    sim_id = response.json()["simulation_id"]
    
    # 2. Run ticks
    for i in range(10):
        response = client.post(f"/api/simulations/{sim_id}/tick")
        assert response.status_code == 200
        result = response.json()
        assert result["tick"] == i
    
    # 3. Get state
    response = client.get(f"/api/simulations/{sim_id}/state")
    assert response.status_code == 200
    state = response.json()
    assert state["current_tick"] == 10
    assert len(state["state"]["agents"]) == 2
    
    # 4. Delete simulation
    response = client.delete(f"/api/simulations/{sim_id}")
    assert response.status_code == 200
    
    # 5. Verify deleted
    response = client.get(f"/api/simulations/{sim_id}/state")
    assert response.status_code == 404


def test_invalid_config():
    """Invalid config returns 400."""
    config = {
        "ticks_per_day": 0,  # Invalid!
        "rng_seed": 12345,
        "agent_configs": [],
    }
    
    response = client.post("/api/simulations", json=config)
    assert response.status_code == 400


def test_nonexistent_simulation():
    """Operations on nonexistent simulation return 404."""
    response = client.get("/api/simulations/nonexistent/state")
    assert response.status_code == 404


def test_list_simulations():
    """List all active simulations."""
    # Create 2 simulations
    config = create_test_config()
    
    response1 = client.post("/api/simulations", json=config)
    sim_id1 = response1.json()["simulation_id"]
    
    response2 = client.post("/api/simulations", json=config)
    sim_id2 = response2.json()["simulation_id"]
    
    # List
    response = client.get("/api/simulations")
    assert response.status_code == 200
    sims = response.json()["simulations"]
    assert len(sims) >= 2
    
    sim_ids = [s["simulation_id"] for s in sims]
    assert sim_id1 in sim_ids
    assert sim_id2 in sim_ids
    
    # Cleanup
    client.delete(f"/api/simulations/{sim_id1}")
    client.delete(f"/api/simulations/{sim_id2}")


def create_test_config():
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "balance": 1000000, "credit_limit": 0, "policy": "fifo"},
            {"id": "B", "balance": 1000000, "credit_limit": 0, "policy": "fifo"},
        ],
    }
```

**Deliverable:** E2E tests passing

---

### **Day 12: API Documentation**

#### Task 2.3: Generate OpenAPI Docs
```python
# api/payment_simulator/api/main.py

# Add detailed docstrings and examples
@app.post("/api/simulations", status_code=201,
    summary="Create Simulation",
    description="""
    Create a new simulation instance with the provided configuration.
    
    The simulation will be initialized with the specified agents, policies,
    and cost parameters. A unique simulation ID will be returned.
    """,
    response_description="Simulation created successfully",
)
async def create_simulation(config: SimulationConfig):
    # ... implementation
```

**Run server to view docs:**
```bash
uvicorn payment_simulator.api.main:app --reload

# Open browser to:
# http://localhost:8000/docs  (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

**Deliverable:** Auto-generated API documentation

---

## 🚧 Priority 3: CLI Tool (Days 13-15)

**Current State:** `Cargo.toml` only  
**Target:** Working command-line interface  
**Effort:** 2-3 days  
**Dependencies:** FFI complete (can use Rust orchestrator directly)

### **Day 13-14: CLI Implementation**

#### Task 3.1: Create CLI with Clap
```rust
// cli/src/main.rs
use clap::{Parser, Subcommand};
use payment_simulator_core_rs::{Orchestrator, OrchestratorConfig};
use serde_json;
use std::fs;
use std::path::Path;

#[derive(Parser)]
#[command(name = "payment-sim")]
#[command(about = "Payment Settlement Simulator CLI", version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Create a new simulation from configuration
    Create {
        /// Path to configuration JSON/YAML file
        #[arg(short, long)]
        config: String,
        
        /// Output path for simulation state (JSON)
        #[arg(short, long)]
        output: String,
    },
    
    /// Advance simulation by one tick
    Tick {
        /// Path to simulation state file
        #[arg(short, long)]
        state: String,
        
        /// Pretty-print output
        #[arg(short, long)]
        pretty: bool,
    },
    
    /// Display current simulation state
    State {
        /// Path to simulation state file
        #[arg(short, long)]
        state: String,
        
        /// Show detailed information
        #[arg(short, long)]
        verbose: bool,
    },
    
    /// Run multiple ticks
    Run {
        /// Path to simulation state file
        #[arg(short, long)]
        state: String,
        
        /// Number of ticks to run
        #[arg(short, long)]
        count: usize,
        
        /// Show progress
        #[arg(short, long)]
        progress: bool,
    },
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    
    match cli.command {
        Commands::Create { config, output } => {
            cmd_create(&config, &output)?;
        }
        Commands::Tick { state, pretty } => {
            cmd_tick(&state, pretty)?;
        }
        Commands::State { state, verbose } => {
            cmd_state(&state, verbose)?;
        }
        Commands::Run { state, count, progress } => {
            cmd_run(&state, count, progress)?;
        }
    }
    
    Ok(())
}

fn cmd_create(config_path: &str, output_path: &str) -> Result<(), Box<dyn std::error::Error>> {
    println!("Creating simulation from: {}", config_path);
    
    // Load config
    let config_json = fs::read_to_string(config_path)?;
    let config: OrchestratorConfig = serde_json::from_str(&config_json)?;
    
    // Create orchestrator
    let orchestrator = Orchestrator::new(config)?;
    
    // Serialize and save
    let state_json = serde_json::to_string_pretty(&orchestrator)?;
    fs::write(output_path, state_json)?;
    
    println!("✅ Simulation created: {}", output_path);
    Ok(())
}

fn cmd_tick(state_path: &str, pretty: bool) -> Result<(), Box<dyn std::error::Error>> {
    // Load orchestrator
    let mut orchestrator = load_orchestrator(state_path)?;
    
    // Run tick
    let result = orchestrator.tick()?;
    
    // Print result
    if pretty {
        println!("{}", serde_json::to_string_pretty(&result)?);
    } else {
        println!("{}", serde_json::to_string(&result)?);
    }
    
    // Save updated state
    save_orchestrator(state_path, &orchestrator)?;
    
    Ok(())
}

fn cmd_state(state_path: &str, verbose: bool) -> Result<(), Box<dyn std::error::Error>> {
    let orchestrator = load_orchestrator(state_path)?;
    
    println!("Simulation State");
    println!("================");
    println!("Current tick: {}", orchestrator.current_tick());
    println!("Current day:  {}", orchestrator.current_day());
    println!("Agents:       {}", orchestrator.num_agents());
    
    if verbose {
        let state = orchestrator.state();
        println!("\nDetailed State:");
        println!("{}", serde_json::to_string_pretty(&state)?);
    }
    
    Ok(())
}

fn cmd_run(
    state_path: &str,
    count: usize,
    progress: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut orchestrator = load_orchestrator(state_path)?;
    
    println!("Running {} ticks...", count);
    
    for i in 0..count {
        let result = orchestrator.tick()?;
        
        if progress {
            println!(
                "Tick {}: {} arrivals, {} settlements, {} cost",
                result.tick,
                result.num_arrivals,
                result.num_settlements,
                result.total_cost
            );
        }
    }
    
    save_orchestrator(state_path, &orchestrator)?;
    
    println!("✅ Completed {} ticks", count);
    Ok(())
}

fn load_orchestrator(path: &str) -> Result<Orchestrator, Box<dyn std::error::Error>> {
    let state_json = fs::read_to_string(path)?;
    let orchestrator = serde_json::from_str(&state_json)?;
    Ok(orchestrator)
}

fn save_orchestrator(
    path: &str,
    orchestrator: &Orchestrator,
) -> Result<(), Box<dyn std::error::Error>> {
    let state_json = serde_json::to_string_pretty(orchestrator)?;
    fs::write(path, state_json)?;
    Ok(())
}
```

**Deliverable:** Working CLI tool

---

### **Day 15: CLI Testing**

#### Task 3.2: Test CLI End-to-End
```bash
# Create example config
cat > /tmp/sim_config.json <<EOF
{
  "ticks_per_day": 100,
  "num_days": 1,
  "rng_seed": 12345,
  "agent_configs": [
    {"id": "BANK_A", "opening_balance": 1000000, "credit_limit": 0, "policy": "Fifo"},
    {"id": "BANK_B", "opening_balance": 1500000, "credit_limit": 0, "policy": "Fifo"}
  ],
  "cost_rates": {
    "overdraft_bps_per_tick": 0.0001,
    "delay_cost_per_tick_per_cent": 0.00001,
    "split_friction_cost": 50,
    "eod_penalty_per_transaction": 100000
  },
  "lsm_config": {
    "bilateral_offset_enabled": true,
    "cycle_detection_enabled": true,
    "max_cycle_length": 4
  }
}
EOF

# Test create
./target/release/payment-sim create \
    --config /tmp/sim_config.json \
    --output /tmp/sim_state.json

# Test state
./target/release/payment-sim state \
    --state /tmp/sim_state.json \
    --verbose

# Test tick
./target/release/payment-sim tick \
    --state /tmp/sim_state.json \
    --pretty

# Test run
./target/release/payment-sim run \
    --state /tmp/sim_state.json \
    --count 100 \
    --progress

# Verify final state
./target/release/payment-sim state \
    --state /tmp/sim_state.json
```

**Deliverable:** CLI working for all commands

---

## 🚧 Priority 4: Integration Testing (Days 16-18)

**Current State:** Minimal  
**Target:** Comprehensive test coverage  
**Effort:** 3-5 days  

### **Day 16: FFI Integration Tests**

```python
# tests/integration/test_ffi_integration.py
import pytest
from payment_simulator_core_rs import Orchestrator

def test_full_simulation_determinism():
    """100 ticks must be deterministic across FFI."""
    config = create_standard_config()
    
    orch1 = Orchestrator(config)
    orch2 = Orchestrator(config)
    
    results1 = [orch1.tick() for _ in range(100)]
    results2 = [orch2.tick() for _ in range(100)]
    
    for i, (r1, r2) in enumerate(zip(results1, results2)):
        assert r1 == r2, f"Tick {i} differs"

def test_balance_conservation():
    """Total balance must be conserved throughout simulation."""
    config = create_standard_config()
    orch = Orchestrator(config)
    
    initial_state = orch.get_state()
    initial_total = sum(a["balance"] for a in initial_state["agents"].values())
    
    for _ in range(100):
        orch.tick()
    
    final_state = orch.get_state()
    final_total = sum(a["balance"] for a in final_state["agents"].values())
    
    assert initial_total == final_total, "Balance not conserved"

def test_memory_stability():
    """Memory usage should stabilize (no leaks)."""
    import tracemalloc
    
    tracemalloc.start()
    
    config = create_standard_config()
    orch = Orchestrator(config)
    
    # Run many ticks
    for _ in range(1000):
        orch.tick()
    
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    # Peak memory should be reasonable (<100MB)
    assert peak < 100 * 1024 * 1024, f"Peak memory: {peak / 1024 / 1024:.1f} MB"

def test_error_propagation():
    """Rust errors must propagate cleanly to Python."""
    # Test various error conditions
    # - Invalid config
    # - Invalid operations
    # - Edge cases
    pass

def create_standard_config():
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "A", "balance": 1_000_000, "credit_limit": 500_000, "policy": "fifo"},
            {"id": "B", "balance": 1_500_000, "credit_limit": 750_000, "policy": "fifo"},
            {"id": "C", "balance": 2_000_000, "credit_limit": 1_000_000, "policy": "fifo"},
        ],
    }
```

---

### **Day 17: Performance Testing**

```python
# tests/performance/test_throughput.py
import time
from payment_simulator_core_rs import Orchestrator

def test_tick_throughput():
    """Measure ticks per second."""
    config = create_large_config(num_agents=10)
    orch = Orchestrator(config)
    
    num_ticks = 10_000
    start = time.time()
    
    for _ in range(num_ticks):
        orch.tick()
    
    elapsed = time.time() - start
    tps = num_ticks / elapsed
    
    print(f"\nThroughput: {tps:.0f} ticks/sec")
    print(f"Time per tick: {elapsed / num_ticks * 1000:.2f} ms")
    
    # Target: >1000 ticks/sec for 10 agents
    assert tps > 1000, f"Too slow: {tps:.0f} tps"

def test_scaling():
    """Test performance scaling with agent count."""
    for num_agents in [5, 10, 20, 50]:
        config = create_large_config(num_agents=num_agents)
        orch = Orchestrator(config)
        
        num_ticks = 1000
        start = time.time()
        
        for _ in range(num_ticks):
            orch.tick()
        
        elapsed = time.time() - start
        tps = num_ticks / elapsed
        
        print(f"{num_agents} agents: {tps:.0f} tps")

def create_large_config(num_agents: int):
    return {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {
                "id": f"AGENT_{i:02d}",
                "balance": 1_000_000,
                "credit_limit": 500_000,
                "policy": "fifo",
            }
            for i in range(num_agents)
        ],
    }
```

---

### **Day 18: Documentation**

#### Task 4.1: Update All Docs
```markdown
# DEVELOPMENT.md

## Setup

### Prerequisites
- Rust 1.70+
- Python 3.9+
- maturin

### Build

```bash
# Clone repository
git clone https://github.com/yourorg/payment-simulator
cd payment-simulator

# Build Rust core
cd backend
cargo build --release

# Build Python extension
cd ..
maturin develop --release

# Install Python package
cd api
pip install -e ".[dev]"
```

### Run Tests

```bash
# Rust tests
cd backend
cargo test

# Python tests
cd api
pytest

# All tests
./scripts/test-all.sh
```

### Run API Server

```bash
cd api
uvicorn payment_simulator.api.main:app --reload

# Open http://localhost:8000/docs
```

### Use CLI

```bash
# Build CLI
cd cli
cargo build --release

# Run
./target/release/payment-sim --help
```
```

**Deliverable:** Complete development documentation

---

## ✅ Final Completion Checklist

### **Rust Engine (DONE)** ✅
- [x] Core models (Agent, Transaction, State)
- [x] RTGS settlement
- [x] LSM (bilateral + cycles)
- [x] Two-queue architecture
- [x] Policy framework (5 policies)
- [x] Orchestrator tick loop
- [x] Arrival generation
- [x] Transaction splitting
- [x] Cost accounting
- [x] 60+ tests

### **Integration Layer (TO DO)** ⚠️
- [ ] PyO3 FFI bindings (Days 1-7)
- [ ] Python wrapper class (Days 6-7)
- [ ] FastAPI server (Days 8-12)
- [ ] CLI tool (Days 13-15)
- [ ] Integration tests (Days 16-18)
- [ ] Documentation (Day 18)

---

## 📊 Timeline Summary

| Week | Days | Focus | Deliverable |
|------|------|-------|-------------|
| **Week 1** | 1-7 | PyO3 FFI Bindings | Python can import and use Rust |
| **Week 2** | 8-12 | Python API | FastAPI server working |
| **Week 2-3** | 13-15 | CLI Tool | Command-line interface |
| **Week 3** | 16-18 | Testing & Docs | Integration tests + documentation |

**Total:** 18 days = **2.5-3 weeks**

---

## 🎯 Success Criteria

Foundation is complete when:

1. ✅ `pip install payment-simulator-core` works
2. ✅ Python can create orchestrator via FFI
3. ✅ FastAPI server handles requests
4. ✅ CLI tool runs simulations
5. ✅ All integration tests pass
6. ✅ Documentation is complete
7. ✅ Performance benchmarks met (>1000 tps)

---

## 🚀 Getting Started TODAY

### **Step 1: Verify Current State**
```bash
cd backend
cargo build --release --features pyo3
cargo test
```

### **Step 2: Start FFI Implementation**
```bash
# Edit backend/src/lib.rs
# Replace placeholder with PyOrchestrator wrapper
vim backend/src/lib.rs
```

### **Step 3: Test Build**
```bash
maturin develop --release
python3 -c "import payment_simulator_core_rs; print('✅')"
```

If this works, you're on the right track!

---

## 🎉 Conclusion

**The hard work is done.** The Rust simulation engine is production-ready with:
- Complete orchestrator tick loop (9 steps)
- Advanced settlement (RTGS + LSM)
- Sophisticated policies (including splitting)
- Comprehensive tests (60+)

**What's left:** 2-3 weeks of integration work to expose this powerful engine via:
- Python FFI (PyO3)
- HTTP API (FastAPI)
- Command-line tool

**Start today with FFI bindings** and you'll have a working foundation in 3 weeks!

---

*This plan reflects the TRUE state of the codebase after confirming that Phases 4b (Orchestrator) and 5 (Splitting) are ALREADY COMPLETE, despite the plan document saying otherwise.*