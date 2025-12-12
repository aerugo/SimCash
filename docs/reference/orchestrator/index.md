# Orchestrator Reference

> Central controller documentation for the SimCash simulation engine

The Orchestrator manages time progression, transaction generation, queue management, settlement processing, cost calculation, and event logging for the payment simulation system.

## Documentation

### Configuration

For configuration reference, see [Scenario Configuration](../scenario/index.md).

### Models

| Document | Description |
|----------|-------------|
| [transaction](02-models/transaction.md) | Transaction structure and lifecycle |
| [agent](02-models/agent.md) | Bank agent model |

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

## Key Concepts

### Money Representation

All monetary values are `i64` integers in cents:

```rust
let amount: i64 = 100000;  // $1,000.00
let fee: i64 = amount * 1 / 1000;  // 0.1% fee = $1.00
```

### Determinism

Same seed + same configuration = identical results:

```rust
let mut rng = RngManager::new(12345);
let value = rng.range(1, 100);  // Deterministic!
```

### Two-Queue Architecture

- **Queue 1** (Internal): Each agent's pending outgoing transactions
- **Queue 2** (RTGS): Central queue for transactions submitted to settlement

## Critical Invariants

1. **Money is always i64 cents** - No floating point for amounts
2. **Determinism is sacred** - Same seed = same results
3. **FFI boundary is minimal** - Only primitives cross
4. **Events are self-contained** - No lookups needed for replay
5. **Balance conservation** - Total balance unchanged during settlement

## Related Documentation

- [Scenario Configuration](../scenario/index.md) - YAML configuration format
- [Architecture Reference](../architecture/index.md) - System architecture
- [Policy Reference](../policy/index.md) - Policy DSL documentation

---

*Last updated: 2025-11-28*
