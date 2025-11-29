# API State Provider

> Unified data access for live and persisted simulations

The API uses the **StateProvider pattern** to ensure consistent data access regardless of whether a simulation is live (in-memory) or persisted (database). This enables **Replay Identity** for API responses.

## Overview

```
┌─────────────────────────────────────────────────────────┐
│          APIStateProviderFactory                        │
│          (Creates appropriate provider)                 │
└────────────────┬───────────────────────────────────────┘
                 │ create(sim_id, db_manager)
                 │
         ┌───────┴────────┐
         │ StateProvider  │  ← Protocol (interface)
         │   Protocol     │
         └───────┬────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ Orchestrator   │      │ Database         │
│ StateProvider  │      │ StateProvider    │
│ (Live FFI)     │      │ (Replay)         │
└────────────────┘      └──────────────────┘
```

## Problem Solved

Without StateProvider, API endpoints would need separate code paths:

```python
# ❌ BAD: Duplicate code paths
@router.get("/simulations/{sim_id}/costs")
def get_costs(sim_id: str):
    if sim_id in active_simulations:
        # Live: query via FFI
        orch = get_orchestrator(sim_id)
        costs = orch.get_agent_accumulated_costs(agent_id)
    else:
        # Persisted: query database
        costs = db.query("SELECT * FROM costs WHERE sim_id = ?", sim_id)
    return costs
```

With StateProvider:

```python
# ✅ GOOD: Unified code path
@router.get("/simulations/{sim_id}/costs")
def get_costs(sim_id: str, factory: APIStateProviderFactory):
    provider = factory.create(sim_id, db_manager)
    costs = provider.get_agent_accumulated_costs(agent_id)
    return costs
```

## APIStateProviderFactory

**Source:** `api/payment_simulator/api/services/state_provider_factory.py`

```python
class APIStateProviderFactory:
    """Factory for creating StateProvider instances in API context."""

    def __init__(
        self,
        simulation_service: SimulationService,
        db_manager: DatabaseManager | None = None,
    ) -> None:
        self._sim_service = simulation_service
        self._db_manager = db_manager

    def create(
        self,
        simulation_id: str,
        tick: int | None = None,
    ) -> StateProvider:
        """Create appropriate StateProvider for simulation.

        Returns:
            OrchestratorStateProvider for live simulations
            DatabaseStateProvider for persisted simulations
        """
        if self._sim_service.has_simulation(simulation_id):
            orch = self._sim_service.get_simulation(simulation_id)
            return OrchestratorStateProvider(orch)

        if self._db_manager:
            return self._create_database_provider(simulation_id, tick)

        raise SimulationNotFoundError(simulation_id)
```

## StateProvider Protocol

**Source:** `api/payment_simulator/cli/execution/state_provider.py`

```python
class StateProvider(Protocol):
    """Protocol for abstracting state access."""

    def get_transaction_details(self, tx_id: str) -> dict | None: ...
    def get_agent_balance(self, agent_id: str) -> int | None: ...
    def get_agent_unsecured_cap(self, agent_id: str) -> int | None: ...
    def get_agent_collateral_posted(self, agent_id: str) -> int: ...
    def get_agent_accumulated_costs(self, agent_id: str) -> dict | None: ...
    def get_queue1_size(self, agent_id: str) -> int: ...
    def get_queue2_size(self, agent_id: str) -> int: ...
    def get_agent_queue1_contents(self, agent_id: str) -> list[str]: ...
    def get_rtgs_queue_contents(self) -> list[str]: ...
    def get_transactions_near_deadline(self, within_ticks: int) -> list[dict]: ...
    def get_overdue_transactions(self) -> list[dict]: ...
```

## Implementations

### OrchestratorStateProvider

For live simulations, delegates to FFI calls:

```python
class OrchestratorStateProvider:
    """StateProvider backed by live Orchestrator (FFI)."""

    def __init__(self, orch: Orchestrator) -> None:
        self._orch = orch

    def get_agent_balance(self, agent_id: str) -> int | None:
        return self._orch.get_agent_balance(agent_id)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict | None:
        return self._orch.get_agent_accumulated_costs(agent_id)
```

### DatabaseStateProvider

For persisted simulations, uses SQL queries:

```python
class DatabaseStateProvider:
    """StateProvider backed by DuckDB queries."""

    def __init__(
        self,
        conn: DuckDBConnection,
        simulation_id: str,
        tick: int,
        tx_cache: dict,
        agent_states: dict,
    ) -> None:
        self._conn = conn
        self._sim_id = simulation_id
        self._tick = tick
        self._tx_cache = tx_cache
        self._agent_states = agent_states

    def get_agent_balance(self, agent_id: str) -> int | None:
        if agent_id in self._agent_states:
            return self._agent_states[agent_id]["balance"]
        return None
```

## API Usage

### As FastAPI Dependency

```python
from fastapi import Depends
from payment_simulator.api.services.state_provider_factory import (
    APIStateProviderFactory,
    get_state_provider_factory,
)

@router.get("/simulations/{sim_id}/costs")
def get_costs(
    sim_id: str,
    factory: APIStateProviderFactory = Depends(get_state_provider_factory),
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> CostResponse:
    provider = factory.create(sim_id, db_manager)
    agent_ids = factory.get_agent_ids(sim_id)

    costs = {}
    for agent_id in agent_ids:
        agent_costs = provider.get_agent_accumulated_costs(agent_id)
        costs[agent_id] = AgentCostBreakdown(**agent_costs)

    return CostResponse(simulation_id=sim_id, agents=costs)
```

### Historical State Queries

For persisted simulations, query state at any tick:

```python
@router.get("/simulations/{sim_id}/ticks/{tick}/state")
def get_historical_state(
    sim_id: str,
    tick: int,
    factory: APIStateProviderFactory = Depends(get_state_provider_factory),
) -> TickStateResponse:
    # Factory creates provider for specific tick
    provider = factory.create(sim_id, db_manager, tick=tick)

    # Query state at that historical tick
    agent_states = {}
    for agent_id in factory.get_agent_ids(sim_id):
        agent_states[agent_id] = {
            "balance": provider.get_agent_balance(agent_id),
            "queue1_size": provider.get_queue1_size(agent_id),
        }

    return TickStateResponse(tick=tick, agents=agent_states)
```

## DataService Layer

**Source:** `api/payment_simulator/api/services/data_service.py`

DataService wraps StateProvider for higher-level operations:

```python
class DataService:
    """Unified data access through StateProvider."""

    def __init__(self, provider: StateProvider) -> None:
        self._provider = provider

    def get_costs(self, agent_ids: list[str]) -> dict[str, AgentCostBreakdown]:
        """Get costs for all agents using canonical field names."""
        costs = {}
        for agent_id in agent_ids:
            raw_costs = self._provider.get_agent_accumulated_costs(agent_id)
            costs[agent_id] = AgentCostBreakdown(
                liquidity_cost=raw_costs["liquidity_cost"],
                delay_cost=raw_costs["delay_cost"],
                collateral_cost=raw_costs["collateral_cost"],
                deadline_penalty=raw_costs["deadline_penalty"],  # Canonical name
                split_friction_cost=raw_costs["split_friction_cost"],
                total_cost=raw_costs["total_cost"],
            )
        return costs

    def get_agent_state(self, agent_id: str) -> AgentStateSnapshot:
        """Get complete state for an agent."""
        return AgentStateSnapshot(
            balance=self._provider.get_agent_balance(agent_id),
            unsecured_cap=self._provider.get_agent_unsecured_cap(agent_id),
            queue1_size=self._provider.get_queue1_size(agent_id),
            queue2_size=self._provider.get_queue2_size(agent_id),
            costs=self.get_costs([agent_id])[agent_id],
        )
```

## Factory Helper Methods

### get_transaction_stats

For metrics computation:

```python
def get_transaction_stats(
    self,
    simulation_id: str,
    db_manager: DatabaseManager | None = None,
) -> dict[str, Any]:
    """Get transaction statistics for metrics computation."""
    if self._is_live_simulation(simulation_id):
        return self._get_live_transaction_stats(simulation_id)
    if db_manager is not None:
        return self._get_persisted_transaction_stats(simulation_id, db_manager)
    raise SimulationNotFoundError(simulation_id)
```

### get_agent_ids

Returns agent IDs for a simulation:

```python
def get_agent_ids(self, simulation_id: str) -> list[str]:
    """Get all agent IDs for a simulation."""
    if self._is_live_simulation(simulation_id):
        orch = self._sim_service.get_simulation(simulation_id)
        return orch.get_agent_ids()
    # Query from database...
```

## Replay Identity Guarantee

The same display code works for both live and replay:

```python
# Both produce identical output
def display_costs(provider: StateProvider, agent_ids: list[str]):
    for agent_id in agent_ids:
        costs = provider.get_agent_accumulated_costs(agent_id)
        print(f"{agent_id}: ${costs['total_cost']/100:.2f}")

# Live simulation
display_costs(OrchestratorStateProvider(orch), ["BANK_A", "BANK_B"])

# Persisted simulation (same output!)
display_costs(DatabaseStateProvider(conn, sim_id, tick), ["BANK_A", "BANK_B"])
```

## Error Handling

```python
try:
    provider = factory.create(simulation_id, db_manager)
except SimulationNotFoundError:
    raise HTTPException(status_code=404, detail=f"Simulation not found: {sim_id}")
```

## Testing

```python
def test_factory_returns_orchestrator_provider_for_live():
    """Factory returns OrchestratorStateProvider for active simulation."""
    service = SimulationService()
    sim_id = service.create_simulation(config)

    factory = APIStateProviderFactory(service, None)
    provider = factory.create(sim_id)

    assert isinstance(provider, OrchestratorStateProvider)


def test_factory_returns_database_provider_for_persisted():
    """Factory returns DatabaseStateProvider for persisted simulation."""
    # Persist a simulation
    persist_simulation(db_manager, config)

    factory = APIStateProviderFactory(SimulationService(), db_manager)
    provider = factory.create("sim-persisted-123")

    assert isinstance(provider, DatabaseStateProvider)
```

## Related Documentation

- [API Index](index.md) - API overview
- [Output Strategies](output-strategies.md) - Output handling
- [Architecture: StateProvider](../architecture/03-python-api-layer.md#stateprovider-pattern) - Full pattern docs
- [CLI: State Provider](../cli/output-modes.md) - CLI implementation

---

*Last updated: 2025-11-29*
