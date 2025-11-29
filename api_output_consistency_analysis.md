# API Layer Output Consistency Analysis

## Executive Summary

The API layer handles simulation output through a **fundamentally different approach** than the CLI layer, creating significant **architectural inconsistency** and **missed abstraction opportunities**. 

**Key Finding**: The API layer **does NOT use the StateProvider pattern** that the CLI employs for unified output consistency. Instead, it directly queries both Orchestrator (for live simulations) and database (for persisted simulations) separately in each endpoint.

This document details the current architecture, identifies consistency gaps, and outlines the architectural mismatch with the CLAUDE.md invariants.

---

## Architecture Overview

### CLI Layer Pattern (StateProvider)

```
┌─────────────────────────────────────────────────┐
│  display_tick_verbose_output()                  │
│  (Single Source of Truth for Display)           │
└────────────────┬───────────────────────────────┘
                 │ StateProvider abstraction
         ┌───────┴────────────────────────────┐
         │                                    │
         ▼                                    ▼
┌──────────────────────────┐      ┌─────────────────────────┐
│ OrchestratorStateProvider│      │ DatabaseStateProvider   │
│ (Live via FFI)          │      │ (Replay via DuckDB)    │
│                         │      │                        │
│ Methods:                │      │ Methods:              │
│ - get_agent_balance()   │      │ - get_agent_balance()  │
│ - get_overdue_txs()     │      │ - get_overdue_txs()   │
│ - get_queue_contents()  │      │ - get_queue_contents() │
│ - get_transaction_details│      │ - get_transaction_details│
│ ... etc                 │      │ ... etc               │
└──────────────────────────┘      └─────────────────────────┘
```

**Key Property**: Both implementations satisfy the same Protocol, so `display_tick_verbose_output()` works identically whether the data comes from live Rust FFI or database replay.

### API Layer Pattern (Direct Querying)

```
┌────────────────────────────────────────────────┐
│  GET /simulations/{sim_id}/costs               │
│  GET /simulations/{sim_id}/agents              │
│  GET /simulations/{sim_id}/events              │
│  etc.                                          │
└────────────────┬───────────────────────────────┘
                 │
         ┌───────┴─────────────────────┐
         │                             │
         ▼                             ▼
┌──────────────────┐      ┌──────────────────┐
│ Active Service   │      │ Direct DB Query  │
│ (get_simulation) │      │ (conn.execute)   │
│ Orchestrator.fn()│      │                  │
└──────────────────┘      └──────────────────┘
```

**Problem**: Each endpoint independently decides whether to query Orchestrator or database, with no abstraction layer between them. Code duplication and potential consistency gaps.

---

## Architectural Differences

### 1. CLI Uses Protocol Abstraction (StateProvider)

**File**: `/api/payment_simulator/cli/execution/state_provider.py`

```python
@runtime_checkable
class StateProvider(Protocol):
    """Abstraction for accessing simulation state."""
    
    def get_agent_balance(self, agent_id: str) -> int: ...
    def get_overdue_transactions(self) -> list[OverdueTransaction]: ...
    def get_transaction_details(self, tx_id: str) -> TransactionDetails | None: ...
    # ... 11+ methods total
```

**Implementation 1: Live Execution**
```python
class OrchestratorStateProvider:
    def __init__(self, orch: Orchestrator):
        self.orch = orch
    
    def get_agent_balance(self, agent_id: str) -> int:
        return self.orch.get_agent_balance(agent_id) or 0
```

**Implementation 2: Replay**
```python
class DatabaseStateProvider:
    def __init__(self, conn, sim_id, tick, tx_cache, agent_states, queue_snapshots):
        self._tx_cache = tx_cache
        self._agent_states = agent_states
    
    def get_agent_balance(self, agent_id: str) -> int:
        return int(self._agent_states.get(agent_id, {}).get("balance", 0))
```

**Usage in Display**:
```python
def display_tick_verbose_output(provider: StateProvider, ...):
    """Works identically whether provider is Orchestrator or Database."""
    balance = provider.get_agent_balance(agent_id)  # Abstracted!
    overdue = provider.get_overdue_transactions()   # Abstracted!
    # ... display uses abstraction, never knows actual source
```

### 2. API Directly Queries Both Sources

**File**: `/api/payment_simulator/api/routers/diagnostics.py` (line 61-170)

```python
@router.get("/simulations/{sim_id}/costs")
def get_simulation_costs(sim_id: str, service: SimulationService, db_manager: Any):
    try:
        # TRY ORCHESTRATOR FIRST
        orchestrator = service.get_simulation(sim_id)
        
        # Direct Orchestrator call
        costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)
        
    except SimulationNotFoundError:
        # FALLBACK TO DATABASE
        if not db_manager:
            raise HTTPException(status_code=404)
        
        conn = db_manager.get_connection()
        
        # Direct SQL query
        df = get_cost_breakdown_by_agent(conn, sim_id)
        for row in df.iter_rows(named=True):
            breakdown = AgentCostBreakdown(
                liquidity_cost=row["liquidity_cost"],
                # ... manual field mapping
            )
```

**Similar Pattern in All Endpoints**:
- `/simulations/{sim_id}/costs` - Direct Orchestrator calls OR SQL
- `/simulations/{sim_id}/metrics` - Direct Orchestrator calls ONLY
- `/simulations/{sim_id}/agents` - Direct Orchestrator calls OR SQL
- `/simulations/{sim_id}/agents/{agent_id}/queues` - Direct Orchestrator calls ONLY
- `/simulations/{sim_id}/events` - SQL query ONLY

---

## Consistency Gaps and Risks

### 1. Code Duplication

**Example 1: Queue Size Calculation**

CLI (StateProvider):
```python
# In OrchestratorStateProvider.get_queue2_size()
def get_queue2_size(self, agent_id: str) -> int:
    rtgs_queue = self.orch.get_rtgs_queue_contents()
    count = 0
    for tx_id in rtgs_queue:
        tx = self.orch.get_transaction_details(tx_id)
        if tx and tx.get("sender_id") == agent_id:
            count += 1
    return count

# In DatabaseStateProvider.get_queue2_size()
def get_queue2_size(self, agent_id: str) -> int:
    rtgs_queue = self.get_rtgs_queue_contents()
    count = 0
    for tx_id in rtgs_queue:
        tx_details = self.get_transaction_details(tx_id)
        if tx_details and tx_details.get("sender_id") == agent_id:
            count += 1
    return count
```

API (Duplicated in Each Endpoint):
```python
# In diagnostics.py get_agent_queues()
rtgs_tx_ids = orch.get_rtgs_queue_contents()
queue2_transactions = []
for tx_id in rtgs_tx_ids:
    tx = orch.get_transaction_details(tx_id)
    if tx and tx["sender_id"] == agent_id:
        queue2_transactions.append(...)
        queue2_total_value += tx["amount"]
```

**Result**: If queue calculation logic changes, CLI StateProvider gets updated in ONE place, but API endpoints must be updated in MULTIPLE places.

### 2. Divergent Data Retrieval Patterns

**Active Simulation (In-Memory)**:
- CLI: Uses `OrchestratorStateProvider` (unified)
- API: Direct calls: `orch.get_agent_balance()`, `orch.get_queue1_size()`, etc.

**Database Simulation**:
- CLI: Uses `DatabaseStateProvider` (unified)
- API: Each endpoint writes its own SQL: `conn.execute(...)`, parses results manually

### 3. No Abstraction for Consistency

**In API diagnostics.py**:

```python
# Three different ways to handle missing simulations:

# Pattern 1 (costs endpoint)
try:
    orchestrator = service.get_simulation(sim_id)
    # ... use orchestrator
except SimulationNotFoundError:
    if not db_manager:
        raise HTTPException(...)
    # ... use db

# Pattern 2 (metrics endpoint)
try:
    orchestrator = service.get_simulation(sim_id)
    # ... use orchestrator ONLY
except SimulationNotFoundError:
    raise HTTPException(...)  # No database fallback!

# Pattern 3 (tick_state endpoint)
orch = service.get_simulation(sim_id)  # No exception handling
# ... assume it exists
```

**Result**: Different endpoints have different fallback behavior, leading to inconsistent API responses.

---

## Current Data Flow

### CLI: Unified Path

```
┌─────────────────────────────────────────┐
│ display_tick_verbose_output()           │
│ (Single Display Logic)                  │
└────────────┬────────────────────────────┘
             │
    ┌────────▼────────────┐
    │ StateProvider       │
    │ (Abstraction)       │
    └────────┬────────────┘
             │
    ┌────────┴─────────────────┐
    │                          │
┌───▼──────────────┐    ┌──────▼─────────────┐
│ Orchestrator FFI │    │ Database (DuckDB)  │
│ (Live)           │    │ (Replay)           │
└──────────────────┘    └────────────────────┘
```

**Single source of truth**: `display_tick_verbose_output()` always produces identical output.

### API: Fragmented Paths

```
┌──────────────────────────┐
│ GET /simulations/{id}/   │
│ costs                    │
└────────────┬─────────────┘
             │
    ┌────────┴──────────────────┐
    │                           │
┌───▼──────────────┐    ┌──────▼──────────┐
│ Orchestrator     │    │ SQL Query +     │
│ .get_agent_      │    │ Manual parsing  │
│ accumulated_     │    │                 │
│ costs()          │    │ conn.execute()  │
└──────────────────┘    └─────────────────┘

┌──────────────────────────┐
│ GET /simulations/{id}/   │
│ agents                   │
└────────────┬─────────────┘
             │
    ┌────────┴──────────────────┐
    │                           │
┌───▼──────────────┐    ┌──────▼──────────┐
│ Orchestrator     │    │ SQL Query +     │
│ .get_agent_ids()│    │ Manual parsing   │
│ + foreach       │    │                 │
└──────────────────┘    └─────────────────┘

... (one pattern per endpoint) ...
```

**Multiple sources of truth**: Each endpoint independently implements query logic, potential for divergence.

---

## CLAUDE.md Principle Violations

### Violation 1: "FFI Boundary is Minimal and Safe"

**CLAUDE.md Requirement**:
> Minimize boundary crossings (batch operations)

**API Problem**: Each endpoint makes MULTIPLE FFI calls:

```python
# get_simulation_costs()
for agent_config in agent_configs:
    agent_id = agent_config["id"]
    # THIS IS AN FFI CALL
    costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)
    # Multiple calls in a loop!
```

**Better** (as CLI does):
```python
# Single abstraction handles multiple calls
provider.get_agent_accumulated_costs(agent_id)
```

### Violation 2: "Python Orchestrates; Rust Computes"

**CLAUDE.md Requirement**:
> Keep FFI minimal, validate early

**API Problem**: Validation and business logic scattered across endpoints:

```python
# In diagnostics.py:
# - Each endpoint has its own try/except for FFI
# - Each endpoint has its own fallback logic
# - No centralized validation
```

**Better** (as CLI does):
```python
# StateProvider abstracts away which source provides data
# Orchestrator vs Database is an implementation detail
```

### Violation 3: "Output Consistency Invariant"

**CLAUDE.md Specification**:
> The simulation_events table is the ONLY source of events for replay.
> Both run and replay must produce identical output.

**API Status**:
- CLI: ✅ Uses `DatabaseStateProvider` which implements this correctly
- API: ⚠️ Events endpoint uses `get_simulation_events()` correctly, but other endpoints (costs, metrics, agents) do NOT use event-based data
- **Gap**: No guarantee that cost calculations in API match what's in `simulation_events`

---

## Specific Endpoint Analysis

### ✅ `/simulations/{sim_id}/events` - CORRECT

**Code**: diagnostics.py line 865-992

```python
# Uses database-first approach (correct!)
from payment_simulator.persistence.event_queries import get_simulation_events

result = get_simulation_events(
    conn=conn,
    simulation_id=sim_id,
    tick=tick,
    # ... filters
)
```

**Why Correct**:
- Only queries database
- Uses `simulation_events` table (single source of truth)
- No attempt to merge with Orchestrator data
- ✅ Follows output consistency invariant

### ⚠️ `/simulations/{sim_id}/costs` - PARTIALLY CORRECT

**Code**: diagnostics.py line 61-170

```python
try:
    # Live mode: Direct Orchestrator calls
    orchestrator = service.get_simulation(sim_id)
    costs_dict = orchestrator.get_agent_accumulated_costs(agent_id)
except SimulationNotFoundError:
    # Replay mode: SQL query
    df = get_cost_breakdown_by_agent(conn, sim_id)
```

**Problems**:
- Two different code paths (no abstraction)
- Orchestrator version only works for ACTIVE simulations
- No StateProvider pattern (unlike CLI)

**Missing**: Protocol to abstract both implementations

### ⚠️ `/simulations/{sim_id}/agents` - INCONSISTENT FALLBACK

**Code**: diagnostics.py line 546-637

```python
try:
    # Live mode: Direct Orchestrator calls
    orch = service.get_simulation(sim_id)
    for agent_id in orch.get_agent_ids():
        agents.append(AgentSummary(...))
except SimulationNotFoundError:
    # Replay mode: SQL query, DIFFERENT calculation
    query = "SELECT ... FROM daily_agent_metrics ..."
```

**Data Inconsistency**:
- Live mode: Current state (balance, costs, etc.)
- Replay mode: Daily aggregated state (different metrics!)

### ❌ `/simulations/{sim_id}/metrics` - LIVE ONLY

**Code**: diagnostics.py line 324-355

```python
try:
    orchestrator = service.get_simulation(sim_id)
    metrics_dict = orchestrator.get_system_metrics()
except SimulationNotFoundError:
    raise HTTPException(status_code=404)  # No database fallback!
```

**Problem**: 
- Cannot query metrics for database simulations
- Live simulations only (artificial limitation)

### ⚠️ `/simulations/{sim_id}/ticks/{tick}/state` - LIVE ONLY + HISTORICAL LIMITATION

**Code**: diagnostics.py line 1137-1242

```python
orch = service.get_simulation(sim_id)
current_tick = orch.current_tick()

if tick > current_tick:
    raise HTTPException(...)  # Can't query future ticks

if tick != current_tick:
    raise HTTPException(...)  # Can't query historical ticks!
```

**Problem**:
- Only supports current tick for live simulations
- Cannot query historical state (unlike StateProvider)
- No database fallback for replay data

---

## StateProvider Design Opportunities

### How StateProvider Solves This

**Current CLI Usage** (StateProvider correctly abstracts):

```python
# display_tick_verbose_output() receives a StateProvider
# It doesn't care if data comes from Orchestrator or DB

def display_tick_verbose_output(provider: StateProvider, ...):
    # These calls work the same for both implementations:
    provider.get_agent_balance(agent_id)
    provider.get_overdue_transactions()
    provider.get_transaction_details(tx_id)
    provider.get_queue1_contents(agent_id)
    # ... etc
```

### Missing API Integration

The API could use a similar abstraction:

```python
# Hypothetical API StateProvider integration:

def get_agent_state_provider(sim_id: str, service, db_manager):
    """Factory to get appropriate StateProvider."""
    if service.has_simulation(sim_id):
        orch = service.get_simulation(sim_id)
        return OrchestratorStateProvider(orch)
    elif db_manager:
        # Load database state for this sim at current tick
        return DatabaseStateProvider(conn, sim_id, final_tick, ...)
    else:
        raise SimulationNotFoundError(sim_id)

@router.get("/simulations/{sim_id}/costs")
def get_simulation_costs(sim_id: str, service, db_manager):
    provider = get_agent_state_provider(sim_id, service, db_manager)
    
    # Now use StateProvider instead of direct calls
    agent_costs = {}
    for agent_id in service.get_agent_ids(sim_id):
        accumulated_costs = provider.get_agent_accumulated_costs(agent_id)
        agent_costs[agent_id] = AgentCostBreakdown(**accumulated_costs)
    
    return CostResponse(agents=agent_costs, ...)
```

**Benefits**:
1. Single code path for both live and replay
2. Reusable abstraction (no duplication)
3. Future-proof (new data source? Just implement StateProvider)
4. Type-safe (Protocol ensures contract)
5. Testable (mock StateProvider for unit tests)

---

## Comparison Matrix

| Aspect | CLI | API | Gap |
|--------|-----|-----|-----|
| **Abstraction** | StateProvider Protocol | Direct queries | ❌ No abstraction in API |
| **Code paths** | 1 unified path | Multiple paths per endpoint | ❌ Duplication risk |
| **Live support** | ✅ OrchestratorStateProvider | ✅ Direct Orchestrator | ✅ Both work |
| **Replay support** | ✅ DatabaseStateProvider | ⚠️ Partial (events only) | ⚠️ Incomplete |
| **Cost data** | Via StateProvider | Direct Orchestrator FFI | ⚠️ Inconsistent paths |
| **Metrics data** | Via StateProvider | Orchestrator only | ❌ No database support |
| **Queue data** | Via StateProvider | Direct FFI calls | ⚠️ Duplicated logic |
| **Events data** | Via StateProvider + Replay | SQL (simulation_events) | ⚠️ Different sources |
| **Consistency check** | Guaranteed (1 source of truth) | Partial (multiple sources) | ⚠️ Risk of divergence |

---

## Risk Assessment

### HIGH RISK: Cost Data Divergence

**Scenario**: Cost calculation changes in Rust.

**CLI Impact**: Single change in StateProvider OR Rust, displays automatically consistent.

**API Impact**: 
1. Update Rust code
2. Update OrchestratorStateProvider
3. Update database persistence
4. Update `/costs` endpoint Orchestrator path
5. Update `/costs` endpoint database path
6. Update `/agents` endpoint
7. Update any other endpoint that displays costs

**If any step is missed**: API shows inconsistent costs for same simulation.

### MEDIUM RISK: Queue Size Calculation Divergence

**Current**: Each endpoint implements queue filtering independently.

**Risk**: Bug in one endpoint's queue calculation doesn't affect others, but creates data inconsistency.

**Example**: If `get_agent_queues` has a bug filtering Queue 2, users might see different queue sizes in different endpoints.

### MEDIUM RISK: Missing Replay Features

**Metrics endpoint has NO database support**:
- Active simulations only
- Cannot query historical metrics from replay
- Users must keep simulations active to get metrics

**State endpoint has LIMITED replay support**:
- Cannot query historical tick states
- Only current tick works
- Artificial API limitation

---

## Recommendations

### Short Term (Consistency Improvement)

1. **Extract common patterns into APIStateProvider**
   - Wrap StateProvider in API-specific types
   - Use `@router` decorators to apply provider injection
   - Eliminate endpoint-specific FFI calls

2. **Audit costs consistency**
   - Verify live and replay paths calculate same costs
   - Add integration test comparing both paths
   - Document any intentional differences

3. **Add replay support to metrics endpoint**
   - Implement metrics calculation from database
   - Use StateProvider abstraction if created

### Long Term (Architecture Alignment)

1. **Adopt StateProvider pattern in API**
   - Create `APIStateProvider` factory
   - Use in all data retrieval endpoints
   - Guarantee consistency across live and replay

2. **Unify event retrieval**
   - Both CLI and API use same event source (simulation_events)
   - StateProvider can expose event lists
   - Display functions shared between CLI and API

3. **Historical state support**
   - Extend DatabaseStateProvider to load state at any tick
   - Endpoints can query `/simulations/{sim_id}/ticks/{tick}/state` for replays
   - Remove current tick limitation

4. **Consider API data layer abstraction**
   - Create service layer between routers and data sources
   - Similar to how runner.py uses OutputStrategy
   - Cleaner separation of concerns

---

## Files to Review

### CLI (StateProvider Pattern - Use as Reference)
- `/api/payment_simulator/cli/execution/state_provider.py` - StateProvider Protocol (11+ methods)
- `/api/payment_simulator/cli/execution/display.py` - Uses StateProvider (unified display)
- `/api/payment_simulator/cli/execution/strategies.py` - VerboseModeOutput creates OrchestratorStateProvider
- `/api/payment_simulator/cli/commands/replay.py` - Creates DatabaseStateProvider

### API (Current Implementation)
- `/api/payment_simulator/api/routers/diagnostics.py` - Multiple endpoints with different patterns
- `/api/payment_simulator/api/routers/simulations.py` - Simulation lifecycle (uses SimulationService)
- `/api/payment_simulator/api/services/simulation_service.py` - Service layer (FFI wrapper)
- `/api/payment_simulator/api/dependencies.py` - Dependency injection (no StateProvider)

### Persistence (Database Source)
- `/api/payment_simulator/persistence/event_queries.py` - Event retrieval (correct usage)
- `/api/payment_simulator/persistence/queries.py` - Legacy queries (for other endpoints)

---

## Conclusion

The API layer and CLI layer use fundamentally different approaches to handling simulation output:

- **CLI**: Unified through StateProvider Protocol → guaranteed consistency
- **API**: Direct querying → risk of divergence

While both work correctly today, the API's approach **violates the CLAUDE.md principle** that "the FFI boundary should be minimal and output should be consistent." The duplication of logic across endpoints and the lack of abstraction create maintenance burden and consistency risks.

**Recommendation**: Adopt the StateProvider pattern (or similar abstraction) in the API layer to achieve architectural consistency with the CLI and guarantee output consistency between live and replay modes.

