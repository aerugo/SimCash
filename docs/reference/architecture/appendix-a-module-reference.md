# Appendix A: Module Reference

**Version**: 1.0
**Last Updated**: 2025-12-12

---

## Rust Backend (`simulator/src/`)

### Module Listing

| Module | File | Purpose |
|--------|------|---------|
| **lib.rs** | `lib.rs` | Entry point, PyO3 exports |
| **core** | `core/mod.rs` | Module exports |
| | `core/time.rs` | TimeManager |
| **models** | `models/mod.rs` | Module exports |
| | `models/agent.rs` | Agent struct |
| | `models/transaction.rs` | Transaction struct |
| | `models/state.rs` | SimulationState |
| | `models/event.rs` | Event enum |
| | `models/collateral_event.rs` | CollateralEvent |
| | `models/queue_index.rs` | AgentQueueIndex |
| **orchestrator** | `orchestrator/mod.rs` | Module exports |
| | `orchestrator/engine.rs` | Orchestrator, tick loop |
| | `orchestrator/checkpoint.rs` | State snapshots |
| **settlement** | `settlement/mod.rs` | Module exports |
| | `settlement/rtgs.rs` | RTGS settlement |
| | `settlement/lsm.rs` | LSM algorithms |
| | `settlement/lsm/graph.rs` | Cycle detection |
| | `settlement/lsm/pair_index.rs` | Bilateral pairs |
| **rng** | `rng/mod.rs` | Module exports |
| | `rng/xorshift.rs` | RngManager |
| **policy** | `policy/mod.rs` | Trait, exports |
| | `policy/tree/mod.rs` | Tree module |
| | `policy/tree/types.rs` | DecisionTreeDef |
| | `policy/tree/context.rs` | EvalContext |
| | `policy/tree/interpreter.rs` | Expression eval |
| | `policy/tree/executor.rs` | TreePolicy |
| | `policy/tree/factory.rs` | Policy creation |
| | `policy/tree/validation.rs` | Validation |
| **arrivals** | `arrivals/mod.rs` | ArrivalGenerator |
| **events** | `events/mod.rs` | Module exports |
| | `events/types.rs` | ScenarioEvent |
| | `events/handler.rs` | EventHandler |
| **ffi** | `ffi/mod.rs` | Module exports |
| | `ffi/orchestrator.rs` | PyOrchestrator |
| | `ffi/types.rs` | Type conversions |

---

## Python API (`api/payment_simulator/`)

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

### Rust Public Types

| Type | Module | Description |
|------|--------|-------------|
| `Orchestrator` | `orchestrator` | Main simulation controller |
| `OrchestratorConfig` | `orchestrator` | Configuration struct |
| `Agent` | `models` | Bank agent |
| `Transaction` | `models` | Payment transaction |
| `SimulationState` | `models` | Full simulation state |
| `Event` | `models` | Event enum |
| `RngManager` | `rng` | Deterministic RNG |
| `TimeManager` | `core::time` | Tick/day management |

### Python Imports

| Import | Purpose |
|--------|---------|
| `payment_simulator._core.Orchestrator` | Main orchestrator |
| `payment_simulator.config.SimulationConfig` | Configuration model |
| `payment_simulator.config.load_config` | YAML loader |
| `payment_simulator.persistence.DatabaseManager` | Database connection |
| `payment_simulator.cli.execution.SimulationRunner` | CLI runner |

---

## Related Documents

- [02-rust-core-engine.md](./02-rust-core-engine.md) - Rust details
- [03-python-api-layer.md](./03-python-api-layer.md) - Python details

---

*Next: [appendix-b-event-catalog.md](./appendix-b-event-catalog.md) - Event types*
