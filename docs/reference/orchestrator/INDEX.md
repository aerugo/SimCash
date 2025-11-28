# Orchestrator System Reference

**Complete Technical Documentation for SimCash Payment Simulator**

---

## Overview

The Orchestrator is the central controller of the SimCash payment simulation system. It manages:

- **Time progression** through discrete ticks and business days
- **Transaction generation** via configurable arrival patterns
- **Queue management** across internal (Queue 1) and central (Queue 2) queues
- **Settlement processing** via RTGS and LSM mechanisms
- **Cost calculation** including overdraft, delay, and penalty costs
- **Event logging** for complete audit trails and replay

This documentation provides exhaustive reference material for every component.

---

## Quick Navigation

### Core Configuration
| Document | Description |
|----------|-------------|
| [OrchestratorConfig](01-configuration/orchestrator-config.md) | Main orchestrator settings |
| [AgentConfig](01-configuration/agent-config.md) | Per-agent configuration |
| [CostRates](01-configuration/cost-rates.md) | Cost calculation parameters |
| [LsmConfig](01-configuration/lsm-config.md) | LSM optimization settings |
| [ArrivalConfig](01-configuration/arrival-config.md) | Transaction arrival patterns |
| [ScenarioEvents](01-configuration/scenario-events.md) | Scheduled simulation events |

### Data Models
| Document | Description |
|----------|-------------|
| [Transaction](02-models/transaction.md) | Transaction structure and lifecycle |
| [Agent](02-models/agent.md) | Bank agent model |
| [SimulationState](02-models/simulation-state.md) | Complete simulation state |
| [Metrics](02-models/metrics.md) | System and daily metrics |

### Generators
| Document | Description |
|----------|-------------|
| [ArrivalGenerator](03-generators/arrival-generator.md) | Transaction generation engine |
| [AmountDistributions](03-generators/amount-distributions.md) | Amount sampling methods |
| [PriorityDistributions](03-generators/priority-distributions.md) | Priority assignment methods |
| [RngSystem](03-generators/rng-system.md) | Deterministic RNG (xorshift64*) |

### Queue System
| Document | Description |
|----------|-------------|
| [Queue1 (Internal)](04-queues/queue1-internal.md) | Agent internal queues |
| [Queue2 (RTGS)](04-queues/queue2-rtgs.md) | Central RTGS queue |
| [QueueIndex](04-queues/queue-index.md) | Performance optimization index |
| [QueueOrdering](04-queues/queue-ordering.md) | Ordering strategies |

### Settlement Engine
| Document | Description |
|----------|-------------|
| [RTGS Engine](05-settlement/rtgs-engine.md) | Real-time gross settlement |
| [LSM Bilateral](05-settlement/lsm-bilateral.md) | Bilateral offset algorithm |
| [LSM Cycles](05-settlement/lsm-cycles.md) | Cycle detection and settlement |
| [SettlementErrors](05-settlement/settlement-errors.md) | Error types and handling |

### Cost System
| Document | Description |
|----------|-------------|
| [CostAccumulator](06-costs/cost-accumulator.md) | Per-agent cost tracking |
| [CostBreakdown](06-costs/cost-breakdown.md) | Per-tick cost components |
| [CostCalculations](06-costs/cost-calculations.md) | Formulas and examples |
| [PriorityMultipliers](06-costs/priority-multipliers.md) | BIS model priority costs |

### Event System
| Document | Description |
|----------|-------------|
| [EventSystemOverview](07-events/event-system-overview.md) | EventLog architecture |
| [ArrivalEvents](07-events/arrival-events.md) | Arrival and policy events |
| [SettlementEvents](07-events/settlement-events.md) | RTGS and LSM events |
| [CostEvents](07-events/cost-events.md) | Cost accrual and penalties |
| [CollateralEvents](07-events/collateral-events.md) | Collateral management |
| [SystemEvents](07-events/system-events.md) | EOD and scenario events |

### Policy System
| Document | Description |
|----------|-------------|
| [PolicyOverview](08-policies/policy-overview.md) | Cash manager architecture |
| [FifoPolicy](08-policies/fifo-policy.md) | FIFO submission policy |
| [DeadlinePolicy](08-policies/deadline-policy.md) | Deadline-aware policy |
| [LiquidityAwarePolicy](08-policies/liquidity-aware-policy.md) | Buffer-maintaining policy |
| [LiquiditySplittingPolicy](08-policies/liquidity-splitting.md) | Smart splitting policy |
| [CustomPolicies](08-policies/custom-policies.md) | FromJson and testing |

### Time Management
| Document | Description |
|----------|-------------|
| [TimeManager](09-time/time-manager.md) | Time tracking struct |
| [TickLifecycle](09-time/tick-lifecycle.md) | Per-tick execution flow |
| [EodProcessing](09-time/eod-processing.md) | End-of-day handling |

### FFI Layer
| Document | Description |
|----------|-------------|
| [FFIOverview](10-ffi/ffi-overview.md) | PyO3 boundary design |
| [OrchestratorBindings](10-ffi/orchestrator-bindings.md) | Python method bindings |
| [TypeConversions](10-ffi/type-conversions.md) | Python ↔ Rust mapping |
| [StateProvider](10-ffi/state-provider.md) | StateProvider abstraction |

### CLI Interface
| Document | Description |
|----------|-------------|
| [RunCommand](11-cli/run-command.md) | payment-sim run |
| [ReplayCommand](11-cli/replay-command.md) | payment-sim replay |
| [OutputModes](11-cli/output-modes.md) | verbose, stream, event-stream |
| [Persistence](11-cli/persistence.md) | Database persistence |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Orchestrator                                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ TimeManager  │  │ ArrivalGen   │  │  RngManager  │           │
│  │ tick/day mgmt│  │ tx generation│  │ determinism  │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   SimulationState                         │   │
│  │  ┌─────────┐  ┌─────────────┐  ┌──────────────────────┐  │   │
│  │  │ Agents  │  │Transactions │  │ RTGS Queue (Queue 2) │  │   │
│  │  │ (Queue1)│  │   (all)     │  │   [tx_id, tx_id, ...] │  │   │
│  │  └─────────┘  └─────────────┘  └──────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ CashManager  │  │ Settlement   │  │  CostEngine  │           │
│  │  (policies)  │  │ (RTGS + LSM) │  │ (accrual)    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                      EventLog                             │   │
│  │   [Event, Event, Event, ...]                              │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ FFI (PyO3)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Layer                                  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ Config       │  │ CLI Commands │  │ Persistence  │           │
│  │ (Pydantic)   │  │ (Typer)      │  │ (DuckDB)     │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Money Representation
All monetary values are represented as `i64` integers in the smallest currency unit (cents for USD). **Never use floating point for money.**

```rust
let amount: i64 = 100000;  // $1,000.00
let fee: i64 = amount * 1 / 1000;  // 0.1% fee = $1.00 = 100 cents
```

### Determinism
Same seed + same configuration = identical results. All randomness flows through a seeded xorshift64* RNG.

```rust
let mut rng = RngManager::new(12345);
let value = rng.range(1, 100);  // Deterministic!
```

### Tick-Based Time
Time progresses in discrete "ticks". Each business day has a configurable number of ticks (e.g., 100 ticks/day = ~6 minutes per tick for 10-hour day).

### Two-Queue Architecture
- **Queue 1** (Internal): Each agent's pending outgoing transactions
- **Queue 2** (RTGS): Central queue for transactions submitted to settlement system

---

## File Locations

| Component | Rust Location | Python Location |
|-----------|---------------|-----------------|
| Orchestrator | `backend/src/orchestrator/engine.rs` | `api/payment_simulator/_core.py` |
| Transaction | `backend/src/models/transaction.rs` | - |
| Agent | `backend/src/models/agent.rs` | - |
| State | `backend/src/models/state.rs` | - |
| Events | `backend/src/models/event.rs` | - |
| Arrivals | `backend/src/arrivals/mod.rs` | - |
| Settlement | `backend/src/settlement/` | - |
| RNG | `backend/src/rng/xorshift.rs` | - |
| Config Schemas | - | `api/payment_simulator/config/schemas.py` |
| CLI Commands | - | `api/payment_simulator/cli/commands/` |
| Execution | - | `api/payment_simulator/cli/execution/` |

---

## Critical Invariants

1. **Money is always i64 cents** - No floating point for amounts
2. **Determinism is sacred** - Same seed = same results
3. **FFI boundary is minimal** - Only primitives cross
4. **Events are self-contained** - No lookups needed for replay
5. **Balance conservation** - Total balance unchanged during settlement

---

## Related Documentation

- [CLAUDE.md](../../../CLAUDE.md) - Main project instructions
- [backend/CLAUDE.md](../../../backend/CLAUDE.md) - Rust-specific guidance
- [api/CLAUDE.md](../../../api/CLAUDE.md) - Python-specific guidance
- [Policy DSL Guide](../../policy_dsl_guide.md) - Custom policy creation
- [Game Concept](../../game_concept_doc.md) - Domain model overview

---

*Documentation Version: 1.0*
*Last Updated: 2025-11-28*
