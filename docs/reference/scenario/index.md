# Scenario Configuration Reference

> YAML configuration format for defining simulation parameters

This reference documents every configurable aspect of SimCash scenario files, including agents, policies, arrivals, costs, and runtime events.

## Documentation

| Document | Description |
|----------|-------------|
| [simulation-settings](simulation-settings.md) | Core timing and seed configuration |
| [agents](agents.md) | Agent (bank) configuration |
| [policies](policies.md) | Built-in policy types |
| [arrivals](arrivals.md) | Transaction arrival generation |
| [distributions](distributions.md) | Amount and priority distributions |
| [cost-rates](cost-rates.md) | Cost and penalty configuration |
| [lsm-config](lsm-config.md) | Liquidity-Saving Mechanism settings |
| [scenario-events](scenario-events.md) | Dynamic runtime events |
| [priority-system](priority-system.md) | Priority bands, escalation, ordering |
| [advanced-settings](advanced-settings.md) | TARGET2 alignment and advanced features |
| [examples](examples.md) | Annotated example configurations |

## Quick Reference

```yaml
# === REQUIRED ===
simulation:                    # Core timing settings
  ticks_per_day: 100           # Integer > 0
  num_days: 10                 # Integer > 0
  rng_seed: 42                 # Integer (determinism seed)

agents:                        # List of agent configurations (min 1)
  - id: BANK_A                 # Required, unique identifier
    # ... see agents.md for full schema

# === OPTIONAL (with defaults) ===
cost_rates:                    # See cost-rates.md
  overdraft_bps_per_tick: 0.001
  # ...

lsm_config:                    # See lsm-config.md
  enable_bilateral: true
  # ...

scenario_events:               # See scenario-events.md
  - type: CustomTransactionArrival
    # ...
```

## Configuration Hierarchy

```
SimulationConfig (root)
├── simulation: SimulationSettings
│   ├── ticks_per_day: int
│   ├── num_days: int
│   └── rng_seed: int
│
├── agents: List[AgentConfig]
│   └── AgentConfig
│       ├── id: str
│       ├── opening_balance: int (cents)
│       ├── unsecured_cap: int (cents)
│       ├── policy: PolicyConfig
│       ├── arrival_config: Optional[ArrivalConfig]
│       ├── arrival_bands: Optional[ArrivalBandsConfig]
│       ├── posted_collateral: Optional[int]
│       ├── collateral_haircut: Optional[float]
│       ├── limits: Optional[Dict]
│       ├── liquidity_pool: Optional[int]
│       └── liquidity_allocation_fraction: Optional[float]
│
├── cost_rates: CostRates
│   ├── overdraft_bps_per_tick: float
│   ├── delay_cost_per_tick_per_cent: float
│   ├── collateral_cost_per_tick_bps: float
│   ├── eod_penalty_per_transaction: int
│   ├── deadline_penalty: int
│   ├── split_friction_cost: int
│   ├── overdue_delay_multiplier: float
│   ├── priority_delay_multipliers: Optional
│   └── liquidity_cost_per_tick_bps: float
│
├── lsm_config: LsmConfig
│   ├── enable_bilateral: bool
│   ├── enable_cycles: bool
│   ├── max_cycle_length: int
│   └── max_cycles_per_tick: int
│
└── scenario_events: Optional[List[ScenarioEvent]]
```

## Key Design Principles

### Money is Always Integer Cents

All monetary values are `i64` integers representing cents:

```yaml
# CORRECT
opening_balance: 10000000  # $100,000.00 in cents

# NEVER DO THIS
opening_balance: 100000.00  # Float - will cause validation error
```

### Determinism is Sacred

Same `rng_seed` + same configuration = identical results:

```yaml
simulation:
  rng_seed: 42  # Controls ALL randomness
```

## Default Values

### Simulation Defaults

| Setting | Default |
|---------|---------|
| `ticks_per_day` | *required* |
| `num_days` | *required* |
| `rng_seed` | *required* |

### Cost Rate Defaults

| Setting | Default |
|---------|---------|
| `overdraft_bps_per_tick` | `0.001` |
| `delay_cost_per_tick_per_cent` | `0.0001` |
| `collateral_cost_per_tick_bps` | `0.0002` |
| `eod_penalty_per_transaction` | `10000` |
| `deadline_penalty` | `50000` |
| `split_friction_cost` | `1000` |
| `overdue_delay_multiplier` | `5.0` |

### LSM Defaults

| Setting | Default |
|---------|---------|
| `enable_bilateral` | `true` |
| `enable_cycles` | `true` |
| `max_cycle_length` | `4` |
| `max_cycles_per_tick` | `10` |

## Validation Rules

| Rule | Description |
|------|-------------|
| Unique agent IDs | All agent `id` values must be unique |
| Counterparty references | Referenced agents must exist |
| Arrival exclusivity | Cannot have both `arrival_config` AND `arrival_bands` |
| Positive ticks | `ticks_per_day` and `num_days` must be > 0 |

## Implementation Locations

| Component | Python | Rust |
|-----------|--------|------|
| Schema Definitions | `api/payment_simulator/config/schemas.py` | `backend/src/orchestrator/engine.rs` |
| FFI Conversion | N/A | `backend/src/ffi/types.rs` |
| Config Loader | `api/payment_simulator/config/loader.py` | N/A |

## Related Documentation

- [CLI run command](../cli/commands/run.md) - Running simulations
- [Policy Reference](../policy/index.md) - Policy DSL for agent strategies
- [Architecture](../architecture/index.md) - System design

---

*Last updated: 2025-11-28*
