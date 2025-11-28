# Scenario Configuration Reference

This comprehensive reference documents **every configurable aspect** of the SimCash payment simulation scenario system. Use this guide to understand all available fields, their types, default values, validation rules, and implementation details.

## Document Structure

| Document | Description |
|:---------|:------------|
| [**index.md**](index.md) | This document - overview and quick reference |
| [**simulation-settings.md**](simulation-settings.md) | Core timing and seed configuration |
| [**agents.md**](agents.md) | Agent (bank) configuration |
| [**policies.md**](policies.md) | Built-in policy types |
| [**arrivals.md**](arrivals.md) | Transaction arrival generation |
| [**distributions.md**](distributions.md) | Amount and priority distributions |
| [**cost-rates.md**](cost-rates.md) | Cost and penalty configuration |
| [**lsm-config.md**](lsm-config.md) | Liquidity-Saving Mechanism settings |
| [**scenario-events.md**](scenario-events.md) | Dynamic runtime events |
| [**priority-system.md**](priority-system.md) | Priority bands, escalation, ordering |
| [**advanced-settings.md**](advanced-settings.md) | TARGET2 alignment and advanced features |
| [**examples.md**](examples.md) | Annotated example configurations |

---

## Configuration File Format

Scenario configurations use **YAML format**. The configuration is validated through two layers:

1. **Python (Pydantic)**: Type validation, constraints, cross-field validation
2. **Rust (FFI)**: Runtime parsing with additional defaults

**Configuration Location**: `api/payment_simulator/config/schemas.py`

---

## Quick Reference: Top-Level Structure

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

# === ADVANCED (Rust-only settings) ===
algorithm_sequencing: false    # See advanced-settings.md
entry_disposition_offsetting: false
priority_escalation:
  enabled: false
  # ...
```

---

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
│       │   └── Union[Fifo, Deadline, LiquidityAware, ...]
│       ├── arrival_config: Optional[ArrivalConfig]
│       │   ├── rate_per_tick: float
│       │   ├── amount_distribution: AmountDistribution
│       │   ├── counterparty_weights: Dict[str, float]
│       │   ├── deadline_range: [int, int]
│       │   ├── priority OR priority_distribution
│       │   └── divisible: bool
│       ├── arrival_bands: Optional[ArrivalBandsConfig]
│       │   ├── urgent: Optional[ArrivalBandConfig]
│       │   ├── normal: Optional[ArrivalBandConfig]
│       │   └── low: Optional[ArrivalBandConfig]
│       ├── posted_collateral: Optional[int]
│       ├── collateral_haircut: Optional[float]
│       ├── limits: Optional[Dict]
│       │   ├── bilateral_limits: Dict[str, int]
│       │   └── multilateral_limit: Optional[int]
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
│   ├── priority_delay_multipliers: Optional[PriorityDelayMultipliers]
│   │   ├── urgent_multiplier: float
│   │   ├── normal_multiplier: float
│   │   └── low_multiplier: float
│   └── liquidity_cost_per_tick_bps: float
│
├── lsm_config: LsmConfig
│   ├── enable_bilateral: bool
│   ├── enable_cycles: bool
│   ├── max_cycle_length: int
│   └── max_cycles_per_tick: int
│
└── scenario_events: Optional[List[ScenarioEvent]]
    └── Union[7 event types] with EventSchedule
```

---

## Key Design Principles

### 1. Money is Always Integer Cents

**CRITICAL INVARIANT**: All monetary values are `i64` integers representing **cents** (smallest currency unit).

```yaml
# CORRECT
opening_balance: 10000000  # $100,000.00 in cents

# NEVER DO THIS
opening_balance: 100000.00  # Float - will cause validation error
```

**Why**: Floating-point arithmetic introduces rounding errors that compound over millions of transactions. Financial systems require exact integer arithmetic.

### 2. Determinism is Sacred

The simulation must be **perfectly reproducible**. Same `rng_seed` + same configuration = identical results.

```yaml
simulation:
  rng_seed: 42  # This seed controls ALL randomness
```

**Implementation**: All randomness flows through a seeded xorshift64* RNG. The seed is persisted and updated after each random draw.

### 3. FFI Boundary Validation

Configuration crosses from Python to Rust via PyO3 FFI. Both layers validate:

| Layer | Location | Role |
|:------|:---------|:-----|
| Python (Pydantic) | `api/payment_simulator/config/schemas.py` | Type validation, constraints |
| Rust (FFI) | `backend/src/ffi/types.rs` | Runtime parsing, defaults |

---

## Default Values Quick Reference

### Simulation Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `ticks_per_day` | *required* | No default |
| `num_days` | *required* | No default |
| `rng_seed` | *required* | No default |

### Agent Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `unsecured_cap` | `0` | No overdraft |
| `policy` | *required* | No default |
| `arrival_config` | `None` | No automatic transactions |
| `arrival_bands` | `None` | Mutually exclusive with arrival_config |
| `posted_collateral` | `None` | No initial collateral |
| `collateral_haircut` | `None` | No haircut |
| `liquidity_pool` | `None` | No external pool |
| `liquidity_allocation_fraction` | `None` | No pool allocation |

### Arrival Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `priority` | `5` | Middle priority |
| `divisible` | `false` | Transactions cannot be split |
| `deadline_range` | `[10, 50]` | FFI default (Python requires explicit) |
| `counterparty_weights` | `{}` | Empty = uniform distribution |

### Cost Rate Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `overdraft_bps_per_tick` | `0.001` | 0.1 basis points |
| `delay_cost_per_tick_per_cent` | `0.0001` | Per cent of tx value |
| `collateral_cost_per_tick_bps` | `0.0002` | Opportunity cost |
| `eod_penalty_per_transaction` | `10000` | $100.00 per unsettled tx |
| `deadline_penalty` | `50000` | $500.00 one-time penalty |
| `split_friction_cost` | `1000` | $10.00 per split |
| `overdue_delay_multiplier` | `5.0` | 5x delay cost when overdue |
| `liquidity_cost_per_tick_bps` | `0.0` | No opportunity cost (Enhancement 11.2) |

### LSM Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `enable_bilateral` | `true` | A↔B offsetting enabled |
| `enable_cycles` | `true` | Cycle detection enabled |
| `max_cycle_length` | `4` | Up to 4 agents in cycle |
| `max_cycles_per_tick` | `10` | Max cycles resolved per tick |

### Priority System Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `queue1_ordering` | `Fifo` | FIFO (not priority-based) |
| `priority_mode` | `false` | No T2 priority bands |
| `priority_escalation.enabled` | `false` | No dynamic escalation |
| `priority_escalation.curve` | `"linear"` | Linear boost curve |
| `priority_escalation.start_escalating_at_ticks` | `20` | Begin at 20 ticks to deadline |
| `priority_escalation.max_boost` | `3` | Max +3 priority boost |

### Advanced Settings Defaults

| Setting | Default | Notes |
|:--------|:--------|:------|
| `algorithm_sequencing` | `false` | No sequenced LSM algorithms |
| `entry_disposition_offsetting` | `false` | No entry-time offset check |
| `eod_rush_threshold` | `0.8` | EOD rush at 80% of day |

---

## Validation Rules Summary

### Cross-Field Validation

| Rule | Location | Description |
|:-----|:---------|:------------|
| Unique agent IDs | `agents` list | All agent `id` values must be unique |
| Counterparty references | `counterparty_weights` | Referenced agents must exist |
| Event agent references | `scenario_events` | `from_agent`, `to_agent` must exist |
| Arrival exclusivity | `AgentConfig` | Cannot have both `arrival_config` AND `arrival_bands` |
| Band requirement | `ArrivalBandsConfig` | At least one band (urgent/normal/low) required |

### Field Constraints

| Field | Constraint | Description |
|:------|:-----------|:------------|
| `ticks_per_day` | `> 0` | Must be positive |
| `num_days` | `> 0` | Must be positive |
| `opening_balance` | any `i64` | Can be negative (debt) |
| `unsecured_cap` | `>= 0` | Non-negative |
| `priority` | `0-10` | Valid priority range |
| `deadline_range` | exactly 2 elements | `[min, max]` with `max >= min` |
| `rate_per_tick` | `>= 0` | Non-negative Poisson λ |
| `collateral_haircut` | `0.0-1.0` | Percentage as fraction |
| `liquidity_allocation_fraction` | `0.0-1.0` | Percentage as fraction |
| `max_cycle_length` | `3-10` | Valid cycle bounds |
| `max_cycles_per_tick` | `1-100` | Valid cycle count |

---

## Implementation Locations

| Component | Python | Rust |
|:----------|:-------|:-----|
| **Schema Definitions** | `api/payment_simulator/config/schemas.py` | `backend/src/orchestrator/engine.rs` |
| **FFI Conversion** | N/A | `backend/src/ffi/types.rs` |
| **Config Loader** | `api/payment_simulator/config/loader.py` | N/A |
| **Arrival Generation** | N/A | `backend/src/arrivals/mod.rs` |
| **LSM Engine** | N/A | `backend/src/settlement/lsm.rs` |
| **Priority Escalation** | N/A | `backend/src/orchestrator/engine.rs` |

---

## Version History

| Version | Date | Changes |
|:--------|:-----|:--------|
| 1.0 | 2025-11-28 | Initial comprehensive documentation |

---

## Navigation

**Next**: [Simulation Settings](simulation-settings.md) - Core timing and seed configuration
