# Appendix A: Module Reference

**Version**: 1.0
**Last Updated**: 2025-11-28

---

## Rust Backend (`simulator/src/`)

### Statistics
- **Total Files**: 31
- **Total Lines**: ~19,445
- **Modules**: 8 core modules + submodules

### Module Listing

| Module | File | Lines | Purpose |
|--------|------|-------|---------|
| **lib.rs** | `lib.rs` | ~100 | Entry point, PyO3 exports |
| **core** | `core/mod.rs` | ~20 | Module exports |
| | `core/time.rs` | ~100 | TimeManager |
| **models** | `models/mod.rs` | ~50 | Module exports |
| | `models/agent.rs` | ~500 | Agent struct |
| | `models/transaction.rs` | ~400 | Transaction struct |
| | `models/state.rs` | ~300 | SimulationState |
| | `models/event.rs` | ~800 | Event enum (50+ variants) |
| | `models/collateral_event.rs` | ~100 | CollateralEvent |
| | `models/queue_index.rs` | ~150 | AgentQueueIndex |
| **orchestrator** | `orchestrator/mod.rs` | ~50 | Module exports |
| | `orchestrator/engine.rs` | ~2000 | Orchestrator, tick loop |
| | `orchestrator/checkpoint.rs` | ~200 | State snapshots |
| **settlement** | `settlement/mod.rs` | ~100 | Module exports |
| | `settlement/rtgs.rs` | ~400 | RTGS settlement |
| | `settlement/lsm.rs` | ~600 | LSM algorithms |
| | `settlement/lsm/graph.rs` | ~300 | Cycle detection |
| | `settlement/lsm/pair_index.rs` | ~200 | Bilateral pairs |
| **rng** | `rng/mod.rs` | ~20 | Module exports |
| | `rng/xorshift.rs` | ~200 | RngManager |
| **policy** | `policy/mod.rs` | ~100 | Trait, exports |
| | `policy/tree/mod.rs` | ~50 | Tree module |
| | `policy/tree/types.rs` | ~400 | DecisionTreeDef |
| | `policy/tree/context.rs` | ~800 | EvalContext |
| | `policy/tree/interpreter.rs` | ~600 | Expression eval |
| | `policy/tree/executor.rs` | ~400 | TreePolicy |
| | `policy/tree/factory.rs` | ~200 | Policy creation |
| | `policy/tree/validation.rs` | ~300 | Validation |
| **arrivals** | `arrivals/mod.rs` | ~800 | ArrivalGenerator |
| **events** | `events/mod.rs` | ~20 | Module exports |
| | `events/types.rs` | ~400 | ScenarioEvent |
| | `events/handler.rs` | ~400 | EventHandler |
| **ffi** | `ffi/mod.rs` | ~50 | Module exports |
| | `ffi/orchestrator.rs` | ~600 | PyOrchestrator |
| | `ffi/types.rs` | ~500 | Type conversions |

---

## Python API (`api/payment_simulator/`)

### Statistics
- **Total Files**: 34
- **Test Files**: 200+

### Module Listing

| Module | File | Purpose |
|--------|------|---------|
| **root** | `__init__.py` | Package init |
| | `_core.py` | FFI shim |
| **cli** | `cli/__init__.py` | CLI package |
| | `cli/main.py` | Typer app |
| | `cli/output.py` | Console output |
| | `cli/filters.py` | EventFilter |
| **cli/commands** | `commands/__init__.py` | Commands package |
| | `commands/run.py` | Run command |
| | `commands/replay.py` | Replay command |
| | `commands/checkpoint.py` | Checkpoint commands |
| | `commands/db.py` | DB commands |
| **cli/execution** | `execution/__init__.py` | Execution package |
| | `execution/runner.py` | SimulationRunner |
| | `execution/strategies.py` | OutputStrategy impls |
| | `execution/state_provider.py` | StateProvider |
| | `execution/display.py` | Verbose output |
| | `execution/persistence.py` | PersistenceManager |
| | `execution/stats.py` | SimulationStats |
| **config** | `config/__init__.py` | Config package |
| | `config/schemas.py` | Pydantic models |
| | `config/loader.py` | YAML loader |
| **persistence** | `persistence/__init__.py` | Persistence package |
| | `persistence/connection.py` | DatabaseManager |
| | `persistence/models.py` | DB models |
| | `persistence/schema_generator.py` | DDL generation |
| | `persistence/migrations.py` | MigrationRunner |
| | `persistence/writers.py` | Batch writers |
| | `persistence/event_writer.py` | Event persistence |
| | `persistence/event_queries.py` | Event queries |
| | `persistence/queries.py` | Analytical queries |
| | `persistence/policy_tracking.py` | Policy snapshots |
| | `persistence/checkpoint.py` | CheckpointManager |
| **api** | `api/__init__.py` | API package |
| | `api/main.py` | FastAPI app |

---

## Key Type Exports

### Rust Public API

```rust
// From lib.rs
pub use orchestrator::{Orchestrator, OrchestratorConfig, AgentConfig};
pub use models::{Agent, Transaction, SimulationState, Event};
pub use settlement::{SettlementError, LsmConfig};
pub use policy::{CashManagerPolicy, ReleaseDecision};
pub use arrivals::{ArrivalConfig, AmountDistribution};
pub use rng::RngManager;
pub use core::time::TimeManager;
```

### Python Imports

```python
# Main orchestrator
from payment_simulator._core import Orchestrator

# Configuration
from payment_simulator.config import SimulationConfig, load_config

# Persistence
from payment_simulator.persistence import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events

# CLI execution
from payment_simulator.cli.execution import SimulationRunner, OutputStrategy
```

---

## Related Documents

- [02-rust-core-engine.md](./02-rust-core-engine.md) - Rust details
- [03-python-api-layer.md](./03-python-api-layer.md) - Python details

---

*Next: [appendix-b-event-catalog.md](./appendix-b-event-catalog.md) - Event types*
