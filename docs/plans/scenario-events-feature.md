# Scenario Events Feature - Implementation Plan

## Overview

Add support for one-off and repeating events in scenario configurations that can modify simulation state at specific ticks. This enables modeling realistic scenarios like payroll dates, collateral adjustments, and dynamic arrival rate changes.

## Requirements

### Functional Requirements

1. **Event Types** (Phase 1 - Core Events):
   - `DirectTransfer`: Move money between agents at specific tick
   - `CollateralAdjustment`: Change agent's credit limit/collateral
   - `GlobalArrivalRateChange`: Modify arrival rates for all agents
   - `AgentArrivalRateChange`: Modify arrival rate for specific agent
   - `CounterpartyWeightChange`: Adjust agent's counterparty preferences
   - `DeadlineWindowChange`: Modify deadline generation parameters

2. **Scheduling**:
   - One-off events: Execute once at specified tick
   - Repeating events: Execute at regular intervals (every N ticks)
   - Event ordering: Deterministic execution order within a tick

3. **Configuration**:
   - YAML-based event definitions in scenario config
   - Clear validation with helpful error messages
   - Self-documenting schema

### Non-Functional Requirements

1. **Determinism**: Same config + same seed = identical results
2. **Replay Identity**: Events must appear identically in run vs replay
3. **FFI Safety**: Simple types across boundary, validation at entry
4. **Performance**: Minimal overhead (<1% tick time impact)
5. **Testability**: Full TDD with comprehensive test coverage

## Architecture Design

### Data Flow

```
YAML Config
    ↓
Python Pydantic Validation
    ↓
FFI Boundary (Simple Dicts)
    ↓
Rust Event Scheduler
    ↓
Tick Loop Event Processing
    ↓
State Mutations + Event Logging
    ↓
simulation_events Table (Replay)
```

### Core Components

#### 1. Rust Event System (`backend/src/events/`)

**File Structure**:
```
backend/src/events/
├── mod.rs              # Module exports
├── types.rs            # ScenarioEvent enum
├── scheduler.rs        # EventScheduler struct
└── handlers.rs         # Event execution logic
```

**Event Enum** (`types.rs`):
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ScenarioEvent {
    DirectTransfer {
        from_agent: String,
        to_agent: String,
        amount: i64,  // Integer cents
    },
    CollateralAdjustment {
        agent: String,
        delta: i64,  // Can be positive or negative
    },
    GlobalArrivalRateChange {
        multiplier: f64,  // OK to use float for rates, not money
    },
    AgentArrivalRateChange {
        agent: String,
        multiplier: f64,
    },
    CounterpartyWeightChange {
        agent: String,
        counterparty: String,
        new_weight: f64,  // Will be renormalized
        auto_balance_others: bool,  // Adjust other weights proportionally
    },
    DeadlineWindowChange {
        min_ticks_multiplier: Option<f64>,
        max_ticks_multiplier: Option<f64>,
    },
}
```

**Scheduled Event**:
```rust
#[derive(Debug, Clone)]
pub struct ScheduledEvent {
    pub event: ScenarioEvent,
    pub schedule: EventSchedule,
}

#[derive(Debug, Clone)]
pub enum EventSchedule {
    OneTime { tick: i64 },
    Repeating { start_tick: i64, interval: i64 },
}
```

**Event Scheduler** (`scheduler.rs`):
```rust
pub struct EventScheduler {
    events: Vec<ScheduledEvent>,
    // Pre-computed index for efficient lookup
    events_by_tick: HashMap<i64, Vec<usize>>,
}

impl EventScheduler {
    pub fn new(events: Vec<ScheduledEvent>) -> Self;
    pub fn get_events_for_tick(&self, tick: i64) -> Vec<&ScenarioEvent>;
    fn build_index(&mut self, max_tick: i64);
}
```

**Event Handlers** (`handlers.rs`):
```rust
pub fn execute_scenario_event(
    state: &mut SimulationState,
    event: &ScenarioEvent,
    tick: i64,
) -> Result<(), String> {
    match event {
        ScenarioEvent::DirectTransfer { from_agent, to_agent, amount } => {
            // Validate agents exist
            // Perform transfer (can go negative if allowed)
            // Log event to state.events
        },
        // ... other handlers
    }
}
```

#### 2. FFI Interface (`backend/src/ffi/orchestrator.rs`)

**Configuration Input**:
```rust
#[pyfunction]
pub fn new(config: HashMap<String, PyObject>) -> PyResult<Orchestrator> {
    // Extract "scenario_events" key
    let events = extract_scenario_events(&config)?;
    let scheduler = EventScheduler::new(events);
    // ... rest of initialization
}

fn extract_scenario_events(
    config: &HashMap<String, PyObject>
) -> PyResult<Vec<ScheduledEvent>> {
    // Parse from Python dicts
    // Validate structure
    // Return typed Rust events
}
```

**Event Logging** (existing system):
```rust
// Events are logged using existing Event enum
Event::ScenarioEventExecuted {
    tick: i64,
    event_type: String,
    details: serde_json::Value,  // Full event data
}
```

#### 3. Python Schema (`api/payment_simulator/config/schema.py`)

```python
from typing import Literal, Union, Optional
from pydantic import BaseModel, Field, field_validator

class DirectTransferEvent(BaseModel):
    """Direct transfer of funds between agents."""
    type: Literal["direct_transfer"]
    from_agent: str
    to_agent: str
    amount: int = Field(..., description="Amount in cents")

    @field_validator("amount")
    def amount_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

class CollateralAdjustmentEvent(BaseModel):
    """Adjust agent's credit limit/collateral."""
    type: Literal["collateral_adjustment"]
    agent: str
    delta: int = Field(..., description="Change in collateral (cents)")

class GlobalArrivalRateChangeEvent(BaseModel):
    """Change arrival rates for all agents."""
    type: Literal["global_arrival_rate_change"]
    multiplier: float = Field(..., gt=0, description="Rate multiplier")

class AgentArrivalRateChangeEvent(BaseModel):
    """Change arrival rate for specific agent."""
    type: Literal["agent_arrival_rate_change"]
    agent: str
    multiplier: float = Field(..., gt=0)

class CounterpartyWeightChangeEvent(BaseModel):
    """Adjust counterparty weights."""
    type: Literal["counterparty_weight_change"]
    agent: str
    counterparty: str
    new_weight: float = Field(..., ge=0)
    auto_balance_others: bool = True

class DeadlineWindowChangeEvent(BaseModel):
    """Change deadline window parameters."""
    type: Literal["deadline_window_change"]
    min_ticks_multiplier: Optional[float] = Field(None, gt=0)
    max_ticks_multiplier: Optional[float] = Field(None, gt=0)

ScenarioEventType = Union[
    DirectTransferEvent,
    CollateralAdjustmentEvent,
    GlobalArrivalRateChangeEvent,
    AgentArrivalRateChangeEvent,
    CounterpartyWeightChangeEvent,
    DeadlineWindowChangeEvent,
]

class EventSchedule(BaseModel):
    """When to execute an event."""
    at_tick: Optional[int] = Field(None, ge=0, description="One-time execution")
    start_tick: Optional[int] = Field(None, ge=0, description="Repeating start")
    interval: Optional[int] = Field(None, gt=0, description="Repeat every N ticks")

    @field_validator("interval")
    def interval_requires_start(cls, v, info):
        if v is not None and info.data.get("start_tick") is None:
            raise ValueError("interval requires start_tick")
        return v

    @field_validator("start_tick")
    def validate_schedule(cls, v, info):
        at_tick = info.data.get("at_tick")
        if at_tick is not None and v is not None:
            raise ValueError("Cannot specify both at_tick and start_tick")
        if at_tick is None and v is None:
            raise ValueError("Must specify either at_tick or start_tick")
        return v

class ScheduledScenarioEvent(BaseModel):
    """A scenario event with its schedule."""
    event: ScenarioEventType = Field(..., discriminator="type")
    schedule: EventSchedule

class SimulationConfig(BaseModel):
    # ... existing fields ...
    scenario_events: Optional[list[ScheduledScenarioEvent]] = Field(
        default=None,
        description="One-off or repeating events during simulation"
    )
```

#### 4. Event Display and Replay

**StateProvider Extension** (`api/payment_simulator/cli/execution/state_provider.py`):
```python
class StateProvider(Protocol):
    # ... existing methods ...

    def get_scenario_events_executed(self, tick: int) -> List[Dict]:
        """Get scenario events that executed at this tick."""
        ...

class OrchestratorStateProvider:
    def get_scenario_events_executed(self, tick: int) -> List[Dict]:
        # Filter events from get_tick_events()
        events = self.orchestrator.get_tick_events(tick)
        return [e for e in events if e["event_type"] == "scenario_event_executed"]

class DatabaseStateProvider:
    def get_scenario_events_executed(self, tick: int) -> List[Dict]:
        # Query simulation_events table
        return get_simulation_events(
            self.db, self.sim_id, tick=tick,
            event_type="scenario_event_executed"
        )
```

**Display Logic** (`api/payment_simulator/cli/display/verbose_output.py`):
```python
def display_scenario_events(events: List[Dict]):
    """Display executed scenario events."""
    if not events:
        return

    console.print("\n[bold cyan]📅 Scenario Events:[/bold cyan]")
    for event in events:
        details = event["details"]
        event_type = details.get("event_type", "unknown")

        if event_type == "direct_transfer":
            log_direct_transfer(details)
        elif event_type == "collateral_adjustment":
            log_collateral_adjustment(details)
        # ... other event types

def display_tick_verbose_output(provider: StateProvider, tick: int, events: List[Dict]):
    # ... existing display logic ...

    # Add scenario events display
    scenario_events = [e for e in events if e["event_type"] == "scenario_event_executed"]
    display_scenario_events(scenario_events)
```

### YAML Configuration Example

```yaml
simulation_config:
  ticks_per_day: 100
  total_days: 5
  seed: 12345

  agent_configs:
    - id: BANK_A
      opening_balance: 100000000  # $1M
      # ... other config
    - id: BANK_B
      opening_balance: 50000000
    - id: BANK_C
      opening_balance: 75000000

  scenario_events:
    # Monthly payroll - one-time at tick 33
    - event:
        type: direct_transfer
        from_agent: BANK_B
        to_agent: BANK_A
        amount: 20000000  # $200k
      schedule:
        at_tick: 33

    # Collateral expansion - one-time at tick 55
    - event:
        type: collateral_adjustment
        agent: BANK_C
        delta: 33000000  # +$330k
      schedule:
        at_tick: 55

    # Market open rush - repeating every day at tick 10
    - event:
        type: global_arrival_rate_change
        multiplier: 1.33  # 33% increase
      schedule:
        start_tick: 10
        interval: 100  # Every day

    # BANK_D specific changes
    - event:
        type: agent_arrival_rate_change
        agent: BANK_D
        multiplier: 1.33
      schedule:
        at_tick: 40

    - event:
        type: counterparty_weight_change
        agent: BANK_D
        counterparty: BANK_A
        new_weight: 0.5
        auto_balance_others: true  # Reduce others proportionally
      schedule:
        at_tick: 40

    # Deadline tightening - all banks at tick 55
    - event:
        type: deadline_window_change
        min_ticks_multiplier: 0.8  # Tighter minimum
        max_ticks_multiplier: 0.8  # Tighter maximum
      schedule:
        at_tick: 55
```

## Implementation Phases

### Phase 1: Rust Core (TDD)

**Step 1.1: Write Failing Tests** (`backend/tests/events_test.rs`)

```rust
#[test]
fn test_event_scheduler_one_time_event() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::DirectTransfer {
            from_agent: "A".to_string(),
            to_agent: "B".to_string(),
            amount: 100000,
        },
        schedule: EventSchedule::OneTime { tick: 10 },
    }];

    let scheduler = EventScheduler::new(events);

    // Should return event at tick 10
    let events_at_10 = scheduler.get_events_for_tick(10);
    assert_eq!(events_at_10.len(), 1);

    // Should return nothing at other ticks
    assert_eq!(scheduler.get_events_for_tick(9).len(), 0);
    assert_eq!(scheduler.get_events_for_tick(11).len(), 0);
}

#[test]
fn test_event_scheduler_repeating_event() {
    let events = vec![ScheduledEvent {
        event: ScenarioEvent::GlobalArrivalRateChange { multiplier: 1.5 },
        schedule: EventSchedule::Repeating { start_tick: 10, interval: 5 },
    }];

    let scheduler = EventScheduler::new(events);

    // Should trigger at start_tick
    assert_eq!(scheduler.get_events_for_tick(10).len(), 1);
    // And at intervals
    assert_eq!(scheduler.get_events_for_tick(15).len(), 1);
    assert_eq!(scheduler.get_events_for_tick(20).len(), 1);
    // But not in between
    assert_eq!(scheduler.get_events_for_tick(12).len(), 0);
}

#[test]
fn test_direct_transfer_execution() {
    let mut state = create_test_state();
    state.agents.insert("A".to_string(), Agent { balance: 100000, .. });
    state.agents.insert("B".to_string(), Agent { balance: 50000, .. });

    let event = ScenarioEvent::DirectTransfer {
        from_agent: "A".to_string(),
        to_agent: "B".to_string(),
        amount: 30000,
    };

    execute_scenario_event(&mut state, &event, 10).unwrap();

    assert_eq!(state.agents.get("A").unwrap().balance, 70000);
    assert_eq!(state.agents.get("B").unwrap().balance, 80000);
}

#[test]
fn test_collateral_adjustment() {
    let mut state = create_test_state();
    state.agents.insert("A".to_string(), Agent {
        credit_limit: 100000,
        ..
    });

    let event = ScenarioEvent::CollateralAdjustment {
        agent: "A".to_string(),
        delta: 50000,
    };

    execute_scenario_event(&mut state, &event, 10).unwrap();
    assert_eq!(state.agents.get("A").unwrap().credit_limit, 150000);

    // Test negative adjustment
    let event2 = ScenarioEvent::CollateralAdjustment {
        agent: "A".to_string(),
        delta: -30000,
    };
    execute_scenario_event(&mut state, &event2, 11).unwrap();
    assert_eq!(state.agents.get("A").unwrap().credit_limit, 120000);
}
```

**Step 1.2: Implement Rust Code**

Create the modules and implement to pass tests.

**Step 1.3: Integration with Tick Loop**

```rust
// In orchestrator/mod.rs
impl Orchestrator {
    pub fn tick(&mut self) -> TickResult {
        self.state.current_tick += 1;
        let tick = self.state.current_tick;

        // Execute scenario events FIRST (before arrivals)
        let scenario_events = self.event_scheduler.get_events_for_tick(tick);
        for event in scenario_events {
            if let Err(e) = execute_scenario_event(&mut self.state, event, tick) {
                // Log error but continue
                eprintln!("Error executing scenario event: {}", e);
            }
        }

        // Then proceed with normal tick logic
        // ... arrivals, settlement, etc.
    }
}
```

### Phase 2: FFI Layer (TDD)

**Step 2.1: Write Python Integration Tests** (`api/tests/integration/test_scenario_events_ffi.py`)

```python
def test_ffi_one_time_direct_transfer():
    """Verify direct transfer event works via FFI."""
    config = {
        "ticks_per_day": 100,
        "total_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000},
            {"id": "B", "opening_balance": 50000},
        ],
        "scenario_events": [
            {
                "event": {
                    "type": "direct_transfer",
                    "from_agent": "A",
                    "to_agent": "B",
                    "amount": 30000,
                },
                "schedule": {"at_tick": 10},
            }
        ],
    }

    orch = Orchestrator.new(config)

    # Advance to tick 10
    for _ in range(10):
        orch.tick()

    # Check balances changed
    balance_a = orch.get_agent_balance("A")
    balance_b = orch.get_agent_balance("B")

    assert balance_a == 70000  # 100000 - 30000
    assert balance_b == 80000  # 50000 + 30000

    # Verify event was logged
    events = orch.get_tick_events(10)
    scenario_events = [e for e in events if e["event_type"] == "scenario_event_executed"]
    assert len(scenario_events) == 1
    assert scenario_events[0]["details"]["event_type"] == "direct_transfer"
```

**Step 2.2: Implement FFI Code**

Implement event parsing and integration in `backend/src/ffi/orchestrator.rs`.

### Phase 3: Python Schema Validation (TDD)

**Step 3.1: Write Schema Tests** (`api/tests/unit/test_scenario_event_schema.py`)

```python
def test_direct_transfer_event_validation():
    """Test DirectTransferEvent schema validation."""
    # Valid event
    event = DirectTransferEvent(
        type="direct_transfer",
        from_agent="A",
        to_agent="B",
        amount=100000,
    )
    assert event.amount == 100000

    # Invalid: negative amount
    with pytest.raises(ValidationError):
        DirectTransferEvent(
            type="direct_transfer",
            from_agent="A",
            to_agent="B",
            amount=-100,
        )

def test_event_schedule_validation():
    """Test EventSchedule validation."""
    # Valid one-time
    schedule = EventSchedule(at_tick=10)
    assert schedule.at_tick == 10

    # Valid repeating
    schedule = EventSchedule(start_tick=10, interval=5)
    assert schedule.interval == 5

    # Invalid: both at_tick and start_tick
    with pytest.raises(ValidationError):
        EventSchedule(at_tick=10, start_tick=20)

    # Invalid: interval without start_tick
    with pytest.raises(ValidationError):
        EventSchedule(interval=5)
```

**Step 3.2: Implement Schemas**

Add schema classes to `api/payment_simulator/config/schema.py`.

### Phase 4: Replay Identity (TDD)

**Step 4.1: Write Gold Standard Tests** (`api/tests/integration/test_scenario_events_replay_identity.py`)

```python
def test_scenario_events_replay_identity():
    """Verify scenario events appear identically in run vs replay."""
    config = {
        "ticks_per_day": 100,
        "total_days": 1,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000},
            {"id": "B", "opening_balance": 50000},
        ],
        "scenario_events": [
            {
                "event": {"type": "direct_transfer", "from_agent": "A", "to_agent": "B", "amount": 30000},
                "schedule": {"at_tick": 10},
            },
            {
                "event": {"type": "collateral_adjustment", "agent": "A", "delta": 50000},
                "schedule": {"at_tick": 20},
            },
        ],
    }

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Run with persistence
        orch = Orchestrator.new(config)
        writer = EventWriter(db_path)
        sim_id = writer.start_simulation(config)

        for _ in range(30):
            result = orch.tick()
            events = orch.get_tick_events(orch.current_tick())
            writer.write_tick(sim_id, orch.current_tick(), events)

        writer.finalize_simulation(sim_id)

        # Verify scenario events are in database
        conn = duckdb.connect(db_path)
        scenario_events = conn.execute("""
            SELECT tick, details
            FROM simulation_events
            WHERE simulation_id = ? AND event_type = 'scenario_event_executed'
            ORDER BY tick
        """, [sim_id]).fetchall()

        assert len(scenario_events) == 2
        assert scenario_events[0][0] == 10  # tick
        assert scenario_events[1][0] == 20

        # Verify replay produces identical output
        # (This would use replay command and compare output)

    finally:
        os.unlink(db_path)
```

**Step 4.2: Implement Event Logging**

Ensure scenario events are logged to `simulation_events` table with all necessary data.

### Phase 5: E2E Tests

**Step 5.1: Complex Scenario Test** (`api/tests/e2e/test_scenario_events_complex.py`)

```python
def test_complex_scenario_with_multiple_events():
    """Test realistic scenario with various event types."""
    config = load_config("complex_scenario_events.yaml")

    orch = Orchestrator.new(config)

    # Run for multiple days
    for _ in range(config["ticks_per_day"] * config["total_days"]):
        orch.tick()

    # Verify expected outcomes
    metrics = orch.get_metrics()
    assert metrics["settlement_rate"] > 0.9

    # Verify determinism
    orch2 = Orchestrator.new(config)
    for _ in range(config["ticks_per_day"] * config["total_days"]):
        orch2.tick()

    metrics2 = orch2.get_metrics()
    assert metrics == metrics2  # Exact equality
```

## Testing Strategy

### Unit Tests (Rust)
- Event scheduler logic
- Individual event handlers
- Edge cases (negative balances, invalid agents, etc.)

### Integration Tests (Python)
- FFI boundary crossing
- Schema validation
- Event execution via orchestrator

### Gold Standard Tests
- Replay identity for each event type
- Complex multi-event scenarios

### E2E Tests
- Full simulations with realistic event patterns
- Determinism verification
- Performance benchmarks

## Error Handling

### Validation Errors
- Invalid agent IDs → Clear error message
- Invalid tick numbers → Validation error
- Conflicting schedules → Configuration error

### Runtime Errors
- Event execution failures → Log and continue (don't crash simulation)
- FFI errors → Return PyResult with descriptive error
- Database errors → Propagate to user

## Performance Considerations

1. **Event Index**: Pre-compute tick→events mapping during initialization
2. **Minimal Overhead**: Only check events on ticks where they're scheduled
3. **Batch Operations**: Execute all events for a tick together
4. **Memory**: Keep event definitions in memory (reasonable for 1000s of events)

## Migration Path

1. This is a new feature - no migration needed
2. Old configs without `scenario_events` continue to work (optional field)
3. New configs with events are backward compatible with old code (graceful degradation)

## Documentation Requirements

1. Update `docs/architecture.md` with event system design
2. Add example configurations to `examples/scenario_events/`
3. Update API documentation with event schemas
4. Add tutorial: "Creating Dynamic Scenarios"

## Success Criteria

- [ ] All event types implemented and tested
- [ ] FFI boundary handles events correctly
- [ ] Schema validation catches invalid configs
- [ ] Replay identity maintained (run == replay output)
- [ ] Performance impact < 1% for scenarios with 100 events
- [ ] Determinism verified (same seed = same results)
- [ ] Gold standard tests pass
- [ ] E2E tests pass
- [ ] Documentation complete

## Future Enhancements (Out of Scope)

- Conditional events (execute if balance > X)
- Event dependencies (event B after event A completes)
- Dynamic event generation (create events based on simulation state)
- Event cancellation/modification at runtime
- Stochastic events (happens with probability P)

## Timeline Estimate

- Phase 1 (Rust Core): 4-6 hours
- Phase 2 (FFI Layer): 2-3 hours
- Phase 3 (Python Schema): 2-3 hours
- Phase 4 (Replay Identity): 3-4 hours
- Phase 5 (E2E Tests): 2-3 hours
- **Total**: 13-19 hours

## References

- CLAUDE.md: Critical invariants (determinism, money as i64, FFI safety)
- `docs/replay-unified-architecture-implementation.md`: Replay identity patterns
- `backend/src/models/event.rs`: Existing event system
- `api/payment_simulator/config/schema.py`: Existing schema patterns
