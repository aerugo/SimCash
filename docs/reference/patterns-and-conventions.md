# Patterns, Invariants, and Conventions

**Version**: 2.1
**Last Updated**: 2025-12-14

This document consolidates all architectural patterns, critical invariants, coding conventions, and styleguides for SimCash. This serves as the authoritative reference for Claude Code agents and contributors.

---

## Table of Contents

1. [Critical Invariants (Never Violate)](#critical-invariants)
2. [Architectural Patterns](#architectural-patterns)
3. [Code Style Conventions](#code-style-conventions)
4. [CLI Conventions](#cli-conventions)
5. [Testing Requirements](#testing-requirements)
6. [Documentation Requirements](#documentation-requirements)
7. [Checklists](#checklists)

---

## Critical Invariants

These invariants are **non-negotiable**. Violating any of these will cause correctness or reproducibility failures.

### INV-1: Money is Always i64 (Integer Cents)

**Rule**: Every monetary value MUST be `i64` representing the smallest currency unit (cents for USD).

```rust
// ✅ CORRECT
let amount: i64 = 100000; // $1,000.00 in cents
let fee: i64 = amount * 1 / 1000; // Integer arithmetic

// ❌ NEVER DO THIS
let amount: f64 = 1000.00; // NO FLOATS FOR MONEY
let fee = (amount as f64 * 0.001) as i64; // Float contamination
```

**Rationale**: Floating point arithmetic introduces rounding errors that compound over millions of transactions. Financial systems demand exact arithmetic.

**Where it applies**:
- All amounts, balances, costs, and fees in Rust
- All Pydantic model fields representing money in Python
- All database columns storing monetary values

### INV-2: Determinism is Sacred

**Rule**: The simulation MUST be perfectly reproducible. Same seed + same config = byte-for-byte identical outputs.

```rust
// ✅ CORRECT - Seeded RNG, state updated
let value = self.rng.range(0, 100); // RNG state auto-updated

// ❌ NEVER DO THIS
use std::time::SystemTime;
let random = SystemTime::now().duration_since(UNIX_EPOCH).unwrap();
```

**Requirements**:
- ALL randomness via seeded xorshift64* RNG
- NEVER use system time, hardware RNG, or thread IDs
- NEVER use non-deterministic hash iteration (use `BTreeMap` for sorted iteration)
- ALWAYS sort collections before iterating when order matters

### INV-3: FFI Boundary is Minimal and Safe

**Rule**: Cross FFI as infrequently as possible, with simple types only.

```python
# ✅ CORRECT - Simple types at boundary
orchestrator = Orchestrator.new({
    "ticks_per_day": 100,
    "seed": 12345,
})

# ❌ NEVER DO THIS
orchestrator.process(my_python_dataclass)  # Complex Python object
```

**Requirements**:
- Pass only primitives, strings, and simple dicts/lists
- Validate ALL inputs at the boundary
- Rust returns `PyResult<T>`, Python catches as exceptions
- NEVER return references to Rust objects from Python
- NEVER cache Rust state in Python (always query fresh)
- Batch operations to minimize crossings

### INV-4: Balance Conservation

**Rule**: Money is never created or destroyed within the simulation.

```
∀ tick: sum(all_agent_balances) == sum(initial_balances) + external_transfers
```

Settlement moves money between agents but never changes the total. Any imbalance indicates a bug.

### INV-5: Replay Identity

**Rule**: `payment-sim replay --verbose` output MUST be byte-for-byte identical to `payment-sim run --verbose` output (excluding timing information).

**Requirements**:
- Same display function for both run and replay
- Events contain ALL data needed for display (self-contained)
- `simulation_events` table is the ONLY source for replay
- No legacy tables, no manual reconstruction

### INV-6: Event Completeness

**Rule**: Events are self-contained and include ALL fields needed for display.

```rust
// ✅ CORRECT - Complete event
Event::LsmBilateralOffset {
    tick,
    agent_a: "BANK_A".to_string(),
    agent_b: "BANK_B".to_string(),
    amount_a: 1000,
    amount_b: 2000,
    net_flow: 1000,
    tx_ids: vec!["tx1", "tx2"],
}

// ❌ WRONG - Incomplete, requires lookup
Event::LsmBilateralOffset {
    tick,
    tx_ids: vec!["tx1", "tx2"],  // Missing agent/amount info!
}
```

### INV-7: Queue Validity

**Rule**: All transaction IDs in queues must reference existing transactions.

```
∀ tx_id ∈ agent.outgoing_queue: transactions.contains(tx_id) == true
∀ tx_id ∈ state.rtgs_queue: transactions.contains(tx_id) == true
```

### INV-8: Atomicity

**Rule**: Settlement is all-or-nothing. Either complete success with all state updates, or complete failure with no state changes.

### INV-9: Policy Evaluation Identity

**Rule**: For any policy P and scenario S, policy parameter extraction MUST produce identical results regardless of which code path processes them.

```python
# Both paths MUST use StandardPolicyConfigBuilder
extraction(optimization_path, P, S) == extraction(bootstrap_path, P, S)
```

**Requirements**:
- ALL code paths that apply policies to agents MUST use `StandardPolicyConfigBuilder`
- Parameter extraction logic (e.g., `initial_liquidity_fraction`) MUST be in one place
- Default values MUST be consistent across all paths
- Type coercion MUST be consistent across all paths

**Where it applies**:
- `optimization.py._build_simulation_config()` - deterministic policy evaluation
- `sandbox_config.py._build_target_agent()` - bootstrap policy evaluation

**Rationale**: Without this invariant, the same policy could produce different behavior in the main simulation vs bootstrap evaluation, leading to incorrect policy comparisons.

### INV-10: Scenario Config Interpretation Identity

**Rule**: For any scenario S and agent A, scenario configuration extraction MUST produce identical results regardless of which code path processes them.

```python
# Both paths MUST use StandardScenarioConfigBuilder
extraction(optimization_path, S, A) == extraction(bootstrap_path, S, A)
```

**Requirements**:
- ALL code paths that extract agent configuration from scenario YAML MUST use `StandardScenarioConfigBuilder`
- Agent configuration extraction logic MUST be in one place (single extraction point)
- Default values MUST be consistent across all paths
- Type coercion MUST follow INV-1 (money as integer cents)
- ALL fields extracted at once (prevents "forgot to pass X" bugs)

**Where it applies**:
- `optimization.py._get_scenario_builder()` - deterministic and bootstrap evaluation
- `BootstrapPolicyEvaluator` - receives `AgentScenarioConfig` fields

**Rationale**: Without this invariant, the same scenario could produce different agent configurations in different code paths. The bug that motivated this invariant (commit `c06a880`) occurred when `liquidity_pool` was extracted separately and forgotten in one path.

**Related**: INV-9 (Policy Evaluation Identity) solves the same problem for policy parameters.

### INV-11: Agent Isolation (LLM Prompts)

**Rule**: An LLM optimizing Agent X may ONLY see information belonging to Agent X. Counterparty information is strictly forbidden in LLM prompts.

**What Agent X MAY see**:
- Outgoing transactions FROM Agent X (amounts, recipients, timing)
- Incoming liquidity events TO Agent X (amount only, no sender balance)
- Agent X's own policy and state changes
- Agent X's own cost breakdown (not system-wide aggregate)

**What Agent X must NEVER see**:
- Any other agent's balance (before/after settlement)
- Counterparty's specific amounts in LSM offsets
- Net positions revealing other agents' liquidity stress
- System-wide cost aggregates that reveal market conditions

```python
# ✅ CORRECT - Only show balance to sender
def _format_settlement_event(self, event: BootstrapEvent) -> str:
    sender = event.details.get("sender")
    if sender == self._agent_id:  # Only if WE are the sender
        # Show our balance change
        ...

# ❌ WRONG - Shows sender balance to everyone
def _format_settlement_event(self, event: BootstrapEvent) -> str:
    # Balance shown unconditionally - LEAKS information!
    balance_before = event.details.get("sender_balance_before")
    ...
```

**Where it applies**:
- `context_builder.py._format_settlement_event()` - Settlement balance display
- `context_builder.py._format_lsm_bilateral()` - LSM bilateral offset formatting
- `context_builder.py._format_lsm_cycle()` - LSM cycle settlement formatting
- `event_filter.py.filter_events_for_agent()` - Event filtering (which events to show)

**Two-Layer Enforcement**:
1. **Filtering Layer**: `filter_events_for_agent()` decides WHICH events to include
2. **Formatting Layer**: `_format_*` methods decide WHAT fields to show within included events

Both layers must enforce isolation. Filtering alone is insufficient—even events relevant to an agent may contain counterparty data that must be redacted.

**Rationale**: Payment policy optimization involves LLMs making decisions for individual banks. If Bank A's LLM can see Bank B's liquidity position, it could exploit this information unfairly. This creates competitive information asymmetry that wouldn't exist in real interbank systems.

**Related Files**:
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` - Event formatting
- `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` - Event filtering
- `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` - Isolation tests

---

## Architectural Patterns

### Pattern 1: StateProvider

**Purpose**: Abstract data access so the same display code works for both live (run) and persisted (replay) modes.

```python
@runtime_checkable
class StateProvider(Protocol):
    """Abstraction for accessing simulation state."""

    def get_agent_balance(self, agent_id: str) -> int: ...
    def get_pending_transactions(self, agent_id: str) -> list[dict[str, str | int]]: ...
    def get_events_for_tick(self, tick: int) -> list[dict[str, str | int | float]]: ...
```

**Implementations**:
- `OrchestratorStateProvider`: Wraps live Rust FFI
- `DatabaseStateProvider`: Wraps DuckDB queries

**Usage**:
```python
# Same display function, works for both run and replay
def display_tick_verbose_output(provider: StateProvider, tick: int) -> None:
    events = provider.get_events_for_tick(tick)
    for event in events:
        display_event(event)
```

### Pattern 2: OutputStrategy (CLI)

**Purpose**: Decouple output formatting from simulation execution.

```python
class OutputStrategy(Protocol):
    """Strategy for handling simulation output."""

    def on_simulation_start(self, config: SimulationRunConfig) -> None: ...
    def on_tick_complete(self, result: TickResult, provider: StateProvider) -> None: ...
    def on_day_complete(self, day: int, stats: DayStats) -> None: ...
    def on_simulation_complete(self, stats: SimulationStats) -> None: ...
```

**Implementations**:
- `QuietOutputStrategy`: Minimal output (default)
- `VerboseModeOutput`: Rich console output with progress
- `StreamModeOutput`: JSONL streaming
- `EventStreamOutput`: Event filtering

### Pattern 3: APIOutputStrategy (HTTP/WebSocket)

**Purpose**: Async version of OutputStrategy for API endpoints.

```python
class APIOutputStrategy(Protocol):
    """Async strategy for API output."""

    async def on_simulation_start(self, config: SimulationRunConfig) -> None: ...
    async def on_tick_complete(self, result: TickResult, provider: StateProvider) -> None: ...
    async def on_simulation_complete(self, stats: SimulationStats) -> None: ...
```

**Implementations**:
- `JSONOutputStrategy`: Collects results for HTTP response
- `WebSocketOutputStrategy`: Real-time streaming
- `NullOutputStrategy`: No output (background execution)

### Pattern 4: Event-Sourced Persistence

**Purpose**: All simulation activity is recorded as immutable events.

```
Run Mode:     Rust Events → FFI → Python → simulation_events table
Replay Mode:  simulation_events table → Python → Display
```

**Key Tables**:
- `simulations`: Simulation metadata
- `simulation_events`: ALL events (the single source of truth)
- `agent_snapshots`: Balance snapshots per tick

**Anti-patterns**:
- ❌ Creating legacy event-specific tables
- ❌ Manual reconstruction from multiple tables
- ❌ Storing partial event data

### Pattern 5: YAML-Only Experiments

**Purpose**: Experiments are defined entirely in YAML—no Python code required.

```yaml
# Inline system prompt and policy constraints
name: exp1
scenario: configs/exp1.yaml

llm:
  model: "anthropic:claude-sonnet-4-5"
  system_prompt: |
    You are an expert in payment system optimization.
    Generate valid JSON policies...

policy_constraints:
  allowed_parameters:
    - name: urgency_threshold
      param_type: int
      min_value: 0
      max_value: 20
  allowed_fields:
    - system_tick_in_day
    - balance
  allowed_actions:
    payment_tree:
      - Release
      - Hold

optimized_agents:
  - BANK_A
  - BANK_B
```

**Key Components**:
- `ExperimentConfig.from_yaml()`: Loads all configuration including inline prompts/constraints
- `GenericExperimentRunner`: Runs any YAML experiment, no experiment-specific code needed
- `VerboseConfig`: Structured verbose logging control

**Anti-patterns**:
- ❌ Creating experiment-specific Python code
- ❌ External constraint modules (use inline `policy_constraints`)
- ❌ External prompt files (use inline `system_prompt`)

### Pattern 6: Workflow for Adding New Events

When adding a new event type that should appear in verbose output:

1. **Define enriched event in Rust** (`simulator/src/models/event.rs`)
   - Include ALL fields needed for display
   - Don't store just IDs - store full display data

2. **Generate event at source** (wherever event occurs)
   - Create with ALL data at creation time

3. **Serialize via FFI** (`simulator/src/ffi/orchestrator.rs`)
   - Serialize EVERY field to dict

4. **Verify persistence** (usually automatic via EventWriter)
   - Complex nested structures may need verification

5. **Add display logic** (`api/payment_simulator/cli/display/verbose_output.py`)
   - Single function receives events from both run and replay

6. **Write TDD tests** (`api/tests/integration/test_replay_identity_gold_standard.py`)
   - Verify all fields exist

7. **Test replay identity**
   ```bash
   payment-sim run --config test.yaml --persist --simulation-id my-test --verbose > run.txt
   payment-sim replay --simulation-id my-test --verbose > replay.txt
   diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
   ```

### Pattern 7: PolicyConfigBuilder

**Purpose**: Ensure identical policy parameter extraction across all code paths (INV-9: Policy Evaluation Identity).

```python
@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy."""

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity configuration from policy."""
        ...

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral configuration from policy."""
        ...
```

**Implementations**:
- `StandardPolicyConfigBuilder`: The single source of truth for extraction

**Usage**:
```python
# In optimization.py
builder = StandardPolicyConfigBuilder()
liquidity_config = builder.extract_liquidity_config(policy, agent_config)
agent_config["liquidity_allocation_fraction"] = liquidity_config.get(
    "liquidity_allocation_fraction"
)

# In sandbox_config.py
builder = StandardPolicyConfigBuilder()
liquidity_config = builder.extract_liquidity_config(policy, agent_config)
# Use extracted values for AgentConfig
```

**Key Features**:
- Nested takes precedence: `policy.parameters.x` wins over `policy.x`
- Default fraction: 0.5 when `liquidity_pool` exists but fraction not specified
- Type coercion: String/int values coerced to appropriate types

**Anti-patterns**:
- ❌ Duplicating extraction logic in multiple files
- ❌ Different default values in different code paths
- ❌ Direct policy parameter access without using builder

### Pattern 8: ScenarioConfigBuilder

**Purpose**: Ensure identical agent configuration extraction from scenario YAML across all code paths (INV-10: Scenario Config Interpretation Identity).

```python
@dataclass(frozen=True)
class AgentScenarioConfig:
    """Canonical agent configuration extracted from scenario YAML.

    All monetary values are in integer cents (INV-1).
    """
    agent_id: str
    opening_balance: int
    credit_limit: int
    max_collateral_capacity: int | None
    liquidity_pool: int | None


@runtime_checkable
class ScenarioConfigBuilder(Protocol):
    """Protocol for extracting agent configuration from scenario."""

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract ALL configuration for an agent at once."""
        ...

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario."""
        ...
```

**Implementations**:
- `StandardScenarioConfigBuilder`: The single source of truth for scenario → agent config extraction

**Usage**:
```python
# In optimization.py
builder = self._get_scenario_builder()  # Returns StandardScenarioConfigBuilder
agent_config = builder.extract_agent_config(agent_id)

# Use all fields - can't forget any!
evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,
    credit_limit=agent_config.credit_limit,
    max_collateral_capacity=agent_config.max_collateral_capacity,
    liquidity_pool=agent_config.liquidity_pool,  # Now CANNOT be forgotten
)
```

**Key Features**:
- Single extraction point: ALL agent fields extracted at once
- Immutable: `AgentScenarioConfig` is a frozen dataclass
- Type coercion: All monetary values coerced to int (INV-1)
- Default values: `opening_balance=0`, `credit_limit=0`, optionals are `None`

**Anti-patterns**:
- ❌ Extracting fields one at a time (e.g., `_get_agent_opening_balance()`, `_get_agent_credit_limit()`)
- ❌ Duplicating extraction logic in multiple files
- ❌ Different default values in different code paths
- ❌ Bypassing the builder for direct scenario dict access

**Related Files**:
- `api/payment_simulator/config/scenario_config_builder.py` - Protocol and implementation
- `api/tests/unit/test_scenario_config_builder.py` - Unit tests
- `api/tests/integration/test_scenario_config_identity.py` - Identity tests

---

## Code Style Conventions

### Python Conventions

#### Type System (Mandatory)

Every function MUST have complete type annotations:

```python
# ✅ CORRECT
def process(items: list[str], lookup: dict[str, int]) -> list[int]:
    return [lookup[item] for item in items]

def find_user(user_id: str) -> User | None:
    return users.get(user_id)

# ❌ WRONG - legacy typing imports
from typing import List, Dict, Optional
def process(items: List[str]) -> List[int]: ...
def find_user(user_id: str) -> Optional[User]: ...

# ❌ WRONG - bare generics
def get_events() -> list[dict]:  # What's in the dict?
    ...
```

**Rules**:
- Use native Python types: `list[str]`, `dict[str, int]`, `str | None`
- Never import `List`, `Dict`, `Optional`, `Union` from `typing`
- Specify type arguments for ALL generics
- Use `-> None` for void functions
- Private methods need return types too

#### Composition Over Inheritance

```python
# ✅ CORRECT - Protocol + composition
class Handler(Protocol):
    def handle(self) -> None: ...

class SpecialHandler:
    def __init__(self, helper: Helper) -> None:
        self._helper = helper

    def handle(self) -> None:
        self._helper.do_work()

# ❌ WRONG - deep inheritance
class BaseHandler: ...
class ExtendedHandler(BaseHandler): ...
class SpecialHandler(ExtendedHandler): ...
```

#### Match Statements for Union Types

```python
# ✅ CORRECT
def convert_policy(policy: PolicyConfig) -> dict[str, str | int]:
    match policy:
        case FifoPolicy():
            return {"type": "Fifo"}
        case DeadlinePolicy(urgency_threshold=threshold):
            return {"type": "Deadline", "threshold": threshold}
        case _:
            raise ValueError(f"Unknown policy: {type(policy)}")
```

#### Typer CLI Commands

Use the `Annotated` pattern:

```python
from typing import Annotated
from pathlib import Path
import typer

def run_command(
    config: Annotated[Path, typer.Argument(help="Path to YAML config file")],
    persist: Annotated[Path | None, typer.Option("--persist", "-p")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run a payment simulation."""
    ...
```

#### Pydantic Models

Use Pydantic v2 with Field descriptions:

```python
from pydantic import BaseModel, ConfigDict, Field

class AgentConfig(BaseModel):
    model_config = ConfigDict(strict=True)

    id: str = Field(..., pattern=r"^[A-Z0-9_]+$", description="Agent identifier")
    balance: int = Field(..., ge=0, description="Opening balance in cents")
```

### Rust Conventions

#### Money Handling

```rust
// ✅ CORRECT
pub struct Transaction {
    pub amount: i64,           // Cents
    pub remaining_amount: i64, // Cents
}

// Convert for display ONLY
pub fn cents_to_dollars_string(cents: i64) -> String {
    format!("${}.{:02}", cents / 100, cents.abs() % 100)
}
```

#### PyO3 FFI

```rust
#[pymethods]
impl Orchestrator {
    pub fn tick(&mut self) -> PyResult<PyObject> {
        let events = self.state.advance_tick()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Tick failed: {}", e)
            ))?;

        Python::with_gil(|py| {
            let result = PyDict::new(py);
            result.set_item("events", events.into_py(py))?;
            Ok(result.into())
        })
    }
}
```

**Rules**:
- Use `PyResult<T>` for all fallible operations
- NEVER panic at FFI boundary (no `.unwrap()` in `#[pymethods]`)
- Return simple types: `PyDict`, `PyList`, primitives

#### Deterministic Iteration

```rust
// ✅ CORRECT - sorted iteration
let mut agent_ids: Vec<_> = state.agents.keys().collect();
agent_ids.sort();

for agent_id in agent_ids {
    // Process in deterministic order
}

// Or use BTreeMap for automatic sorting
use std::collections::BTreeMap;
pub agents: BTreeMap<String, Agent>
```

---

## CLI Conventions

### stdout vs stderr

| Stream | Content | Format |
|--------|---------|--------|
| **stdout** | Machine-readable data | JSON, JSONL |
| **stderr** | Human-readable logs | Rich formatting |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Configuration error |
| 2 | Simulation error |
| 3 | Database error |

### Output Modes

| Mode | Flag | Description |
|------|------|-------------|
| Quiet | (default) | Minimal output |
| Verbose | `-v, --verbose` | Rich progress + events |
| Stream | `--stream` | JSONL to stdout |

---

## Testing Requirements

### Determinism Testing

Run tests multiple times with the same seed to verify identical results:

```bash
# Must produce identical results
for i in {1..10}; do
    payment-sim run --config test.yaml --seed 12345 > run_$i.txt
done
diff run_1.txt run_2.txt  # Should be empty
```

### Replay Identity Testing

```bash
# Run and persist
payment-sim run --config test.yaml --persist --simulation-id my-test --verbose > run.txt

# Replay from database
payment-sim replay --simulation-id my-test --verbose > replay.txt

# Compare (excluding timing)
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
```

### Build and Test Commands

```bash
# Rust tests (--no-default-features required)
cd simulator
cargo test --no-default-features

# Python tests
cd api
.venv/bin/python -m pytest

# Type checking
.venv/bin/python -m mypy payment_simulator/
.venv/bin/python -m ruff check payment_simulator/

# After Rust changes
uv sync --extra dev --reinstall-package payment-simulator
```

---

## Documentation Requirements

### Before Starting Work

**ALWAYS read the relevant reference docs first:**
- Adding CLI command → `docs/reference/cli/commands/<command>.md`
- Working on policies → `docs/reference/policy/index.md`
- Changing orchestrator → `docs/reference/orchestrator/`
- Modifying config → `docs/reference/scenario/`

### After Completing Work

**ALWAYS update the relevant reference docs:**
- Changed function signatures → Update reference doc
- Added CLI options → Update command doc
- Modified event types → Update orchestrator docs
- Changed config schema → Update scenario docs

### Commit Together

```bash
git add api/payment_simulator/cli/commands/run.py docs/reference/cli/commands/run.md
git commit -m "feat: Add --foo option to run command"
```

---

## Checklists

### Before Committing (Rust)

- [ ] No `f32` or `f64` for money calculations
- [ ] All public functions have doc comments
- [ ] Tests pass: `cargo test --no-default-features`
- [ ] No warnings: `cargo clippy -- -D warnings`
- [ ] Formatted: `cargo fmt`
- [ ] FFI functions return `PyResult`
- [ ] No panic in FFI boundary (no `.unwrap()` in `#[pymethods]`)
- [ ] Deterministic iteration (sorted or BTreeMap)

### Before Committing (Python)

- [ ] All functions have complete type annotations
- [ ] No bare `list`, `dict`, `set` generics
- [ ] No `Any` where type is known
- [ ] Using `str | None` not `Optional[str]`
- [ ] Using `list[str]` not `List[str]`
- [ ] Typer commands use `Annotated` pattern
- [ ] mypy passes
- [ ] ruff passes
- [ ] Tests pass
- [ ] All money values are `int` (cents)

### Before Committing (Documentation)

- [ ] Read relevant reference docs before starting
- [ ] Updated reference docs to reflect changes
- [ ] Code and docs committed together

### Adding New Event Type

- [ ] Event enum has ALL display fields
- [ ] FFI serializes ALL fields to dict
- [ ] Test verifies all fields exist
- [ ] Manual run+replay produces identical output
- [ ] No new legacy tables created
- [ ] No manual reconstruction in replay
- [ ] Display code uses StateProvider
- [ ] Integration test added

---

## Quick Reference

### Key Source Files

| Area | Rust | Python |
|------|------|--------|
| State | `simulator/src/models/state.rs` | N/A |
| Events | `simulator/src/models/event.rs` | `cli/execution/stats.py` |
| FFI | `simulator/src/lib.rs` | `_core.py` |
| StateProvider | N/A | `cli/execution/state_provider.py` |
| OutputStrategy | N/A | `cli/execution/strategies.py` |
| Display | N/A | `cli/display/verbose_output.py` |
| PolicyConfigBuilder | N/A | `config/policy_config_builder.py` |

### Key Documentation

| Topic | Location |
|-------|----------|
| System Overview | `docs/reference/architecture/01-system-overview.md` |
| Experiments | `docs/reference/experiments/index.md` |
| CLI Reference | `docs/reference/cli/index.md` |
| LLM Module | `docs/reference/llm/index.md` |
| Castro Experiments | `docs/reference/castro/index.md` |
| StateProvider | `docs/reference/api/state-provider.md` |
| OutputStrategies | `docs/reference/api/output-strategies.md` |
| Event System | `docs/reference/architecture/08-event-system.md` |
| Tick Loop | `docs/reference/architecture/11-tick-loop-anatomy.md` |

---

*This document should be updated whenever patterns or conventions change.*
