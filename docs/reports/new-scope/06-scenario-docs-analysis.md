# 06 — Scenario Documentation System Analysis

**Date**: 2025-02-17
**Source**: `docs/reference/scenario/` (13 files), `docs/reference/architecture/`

---

## 1. Complete Scenario Configuration Schema

The scenario configuration is a hierarchical YAML structure with the following top-level sections:

```
SimulationConfig (root)
├── simulation (required)
│   ├── ticks_per_day: int (>0)
│   ├── num_days: int (>0)
│   └── rng_seed: int
│
├── agents: List[AgentConfig] (required, min 1)
│
├── cost_rates: CostRates (optional, has defaults)
├── lsm_config: LsmConfig (optional, has defaults)
├── policy_feature_toggles: PolicyFeatureToggles (optional)
├── scenario_events: List[ScenarioEvent] (optional)
│
├── # Top-level advanced settings (all optional):
├── algorithm_sequencing: bool (default: false)
├── entry_disposition_offsetting: bool (default: false)
├── deferred_crediting: bool (default: false)
├── eod_rush_threshold: float (default: 0.8)
├── deadline_cap_at_eod: bool (default: false)
├── queue1_ordering: "Fifo" | "priority_deadline" (default: "Fifo")
├── priority_mode: bool (default: false)
└── priority_escalation: PriorityEscalationConfig (optional)
```

**Key invariant**: All monetary values are `i64` integer cents. No floats for money.

---

## 2. Settlement System Configurable Parameters

### Core Timing
| Parameter | Type | Required | Default |
|-----------|------|----------|---------|
| `ticks_per_day` | int | Yes | — |
| `num_days` | int | Yes | — |
| `rng_seed` | int | Yes | — |

### Queue & Processing
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `queue1_ordering` | string | `"Fifo"` | `"Fifo"` or `"priority_deadline"` |
| `priority_mode` | bool | `false` | TARGET2-style priority bands in Queue 2 |
| `algorithm_sequencing` | bool | `false` | Sequenced FIFO→Bilateral→Multilateral |
| `entry_disposition_offsetting` | bool | `false` | Bilateral offset check at Queue 2 entry |
| `deferred_crediting` | bool | `false` | Batch credits at end of tick |
| `eod_rush_threshold` | float | `0.8` | Fraction of day when EOD rush starts |
| `deadline_cap_at_eod` | bool | `false` | Cap all deadlines at end of current day |

### Priority Escalation
```yaml
priority_escalation:
  enabled: bool (default: false)
  curve: "linear" (only option)
  start_escalating_at_ticks: int (default: 20)
  max_boost: int (default: 3)
```

---

## 3. Payment Generation Options

### Option A: `arrival_config` (Single Configuration)
Poisson-driven stochastic generation with:
- `rate_per_tick`: float (Poisson λ)
- `amount_distribution`: Normal | LogNormal | Uniform | Exponential
- `counterparty_weights`: Dict[str, float] (normalized, empty = uniform)
- `deadline_range`: [min, max] ticks
- `priority`: int 0-10 (fixed) OR `priority_distribution` (variable)
- `divisible`: bool

### Option B: `arrival_bands` (Per-Priority-Band)
Separate config for `urgent` (priority 8-10), `normal` (4-7), `low` (0-3) bands. Each band has its own rate, amount distribution, deadline offsets, and counterparty weights. At least one band required.

### Option C: Deterministic Injection via `scenario_events`
`CustomTransactionArrival` events inject specific transactions at exact ticks. Used for BIS model replication and controlled experiments.

### Option D: No Arrivals
Agents with no `arrival_config` or `arrival_bands` are passive — only receive transactions.

**Mutual exclusivity**: `arrival_config` and `arrival_bands` cannot coexist on the same agent.

### Amount Distributions

| Type | Parameters | Typical Use |
|------|-----------|-------------|
| `Normal` | `mean` (cents), `std_dev` (cents) | Symmetric, testing |
| `LogNormal` | `mean` (log-scale), `std_dev` (log-scale) | **Recommended** for realistic sims |
| `Uniform` | `min` (cents), `max` (cents) | Simple testing |
| `Exponential` | `lambda` (rate, >0) | Many small, few large |

### Priority Distributions

| Type | Parameters |
|------|-----------|
| `Fixed` | `value` (0-10) |
| `Categorical` | `values` + `weights` (weighted random) |
| `Uniform` | `min`, `max` (range) |

---

## 4. Cost Model Configuration

### Per-Tick Recurring Costs

| Parameter | Default | Formula |
|-----------|---------|---------|
| `overdraft_bps_per_tick` | 0.001 | `|negative_balance| × rate / 10000` |
| `delay_cost_per_tick_per_cent` | 0.0001 | `amount × rate × priority_multiplier` |
| `collateral_cost_per_tick_bps` | 0.0002 | `posted_collateral × rate / 10000` |
| `liquidity_cost_per_tick_bps` | 0.0 | `allocated_liquidity × rate / 10000` |

### One-Time Penalties

| Parameter | Default | When Applied |
|-----------|---------|--------------|
| `eod_penalty_per_transaction` | 10000 ($100) | Each unsettled tx at day end |
| `deadline_penalty` | 50000 ($500) | When tx becomes overdue |
| `split_friction_cost` | 1000 ($10) | Per split operation |

### Multipliers

| Parameter | Default | Effect |
|-----------|---------|--------|
| `overdue_delay_multiplier` | 5.0 | Multiplies delay cost after deadline |
| `priority_delay_multipliers.urgent_multiplier` | 1.0 | For priority 8-10 |
| `priority_delay_multipliers.normal_multiplier` | 1.0 | For priority 4-7 |
| `priority_delay_multipliers.low_multiplier` | 1.0 | For priority 0-3 |

All cost rate fields are available to JSON policies as decision-tree fields (e.g., `cost_overdraft_bps_per_tick`).

---

## 5. Agent Configuration Options

Each agent has:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier |
| `opening_balance` | Yes | Starting balance (cents, can be negative) |
| `unsecured_cap` | No (0) | Unsecured overdraft capacity |
| `policy` | No (Fifo) | Decision-making strategy |
| `arrival_config` | No | Stochastic payment generation |
| `arrival_bands` | No | Per-priority-band generation |
| `posted_collateral` | No | Initial collateral |
| `collateral_haircut` | No | Discount on collateral value (0.0-1.0) |
| `limits.bilateral_limits` | No | Per-counterparty daily outflow caps |
| `limits.multilateral_limit` | No | Total daily outflow cap |
| `liquidity_pool` | No | External liquidity source |
| `liquidity_allocation_fraction` | No | Fraction of pool to allocate |

### Asymmetric Agents
Fully supported — each agent can have:
- Different opening balances and credit capacities
- Different policies (any of the 8 policy types)
- Different arrival configurations (rates, distributions, counterparty weights)
- Different limits and collateral settings
- Per-agent parameter overrides for JSON policies (`params` field)

---

## 6. LSM Configuration

```yaml
lsm_config:
  enable_bilateral: bool    # Default: true — A↔B offset detection
  enable_cycles: bool       # Default: true — A→B→C→A cycle detection
  max_cycle_length: int     # Default: 4, range 3-10 (O(n^k) complexity)
  max_cycles_per_tick: int  # Default: 10, range 1-100
```

LSM interacts with:
- `algorithm_sequencing`: When true, runs FIFO → Bilateral → Multilateral in sequence
- `entry_disposition_offsetting`: Bilateral check at Queue 2 entry
- `priority_mode`: Respects priority bands
- Agent `limits`: Limits can block otherwise-valid cycles

---

## 7. How the Rust Engine Processes Scenario Configs

### Flow: YAML → Python → Rust

```
YAML file
  → PyYAML loader
    → Pydantic validation (SimulationConfig)
      → .model_dump() → Python dict
        → FFI Bridge (PyO3)
          → extract_required/extract_optional helpers
            → Rust OrchestratorConfig struct
```

Key implementation details:
- **`api/payment_simulator/config/schemas.py`**: Pydantic models with validators (field-level and model-level)
- **`simulator/src/ffi/types.rs`**: `extract_required<T>()` and `extract_optional<T>()` helper functions parse PyDict fields into typed Rust structs
- **`simulator/src/ffi/orchestrator.rs`**: `Orchestrator::new()` receives config as PyDict, constructs internal state
- Policies: `FromJson` reads file, `Inline` serializes dict→JSON, `InlineJson` passes string directly
- RNG: xorshift64* PRNG, seed persisted after every call for determinism

### Tick Loop (9-step):
1. Arrivals → 2. Scenario events → 3. Policy evaluation (Q1) → 4. RTGS settlement (Q2) → 5. LSM optimization → 6. Deferred credits → 7. Cost accrual → 8. EOD processing → 9. Event emission

---

## 8. Validation Rules for Scenarios

### Pydantic-Level (Python)
- All required fields present (`simulation`, `agents` with min 1)
- Type checking (int vs float vs string)
- Range constraints (`ticks_per_day > 0`, `priority 0-10`, `haircut 0.0-1.0`)
- Distribution validation (Uniform `max > min`, Categorical `len(values) == len(weights)`)
- `max_cycle_length` in [3, 10], `max_cycles_per_tick` in [1, 100]

### Cross-Field Validation
- **Unique agent IDs**: All `id` values must be distinct
- **Counterparty references**: All referenced agent IDs must exist
- **Arrival exclusivity**: Cannot have both `arrival_config` AND `arrival_bands`
- **Feature toggle exclusivity**: Cannot specify both `include` AND `exclude`
- **Policy feature toggles**: `FromJson`/`Inline`/`InlineJson` policies validated against toggle restrictions

### Rust-Level
- `extract_required()` fails with `PyValueError` on missing fields
- Type conversion errors at FFI boundary

---

## 9. YAML Config → Python SimulationConfig → Rust FFI

| Stage | Technology | Role |
|-------|-----------|------|
| **YAML** | PyYAML | Human-readable scenario definition |
| **Python** | Pydantic `SimulationConfig` | Schema validation, defaults, cross-field checks |
| **Dict** | `.model_dump()` | Serializable intermediate form |
| **FFI** | PyO3 `Bound<'_, PyDict>` | Type-safe extraction into Rust structs |
| **Rust** | `OrchestratorConfig` + children | Engine-native types, no Python dependency |

**Important patterns:**
- Python owns lifecycle (create, configure, run); Rust owns state (balances, queues, RNG)
- FFI is thin: simple types only (int, float, string, list, dict)
- Policy `Inline` dict → JSON string → Rust `FromJson` parser (normalized at FFI boundary)
- Cost rates have Python defaults that mirror Rust defaults (defensive duplication)

---

## 10. What a "Scenario Library" Would Need

Based on the existing documentation and configuration system, a scenario library would need:

### Required Components

1. **Canonical YAML files** — One per scenario, self-contained, well-commented
2. **Metadata header** — Name, description, author, tags, difficulty level, research paper reference
3. **Category taxonomy**:
   - `minimal` — Simplest valid configs for testing
   - `bis-replication` — BIS Working Paper reproductions (Box 3 etc.)
   - `target2` — TARGET2-aligned configurations
   - `stress-test` — Crisis and systemic risk scenarios
   - `teaching` — Progressive complexity for education
   - `benchmark` — Standard scenarios for policy comparison

4. **Expected outcomes** — Documented expected behavior (settlement rate, costs, gridlock conditions)
5. **Prerequisite policies** — Referenced JSON policy files bundled with scenarios
6. **Validation test** — Each scenario should load and run without error (CI integration)
7. **Index/catalog** — Machine-readable index (YAML or JSON) listing all scenarios with metadata

### Design Considerations

- Scenarios should reference policies by relative path (portable)
- `scenario_events` enable fully deterministic scenarios (no stochastic arrivals needed)
- Feature toggles allow scenarios to restrict policy complexity (good for teaching)
- Agent asymmetry is first-class — scenarios should demonstrate varied agent configurations
- The existing `examples.md` already contains 5 complete annotated scenarios that could seed the library
- `deadline_cap_at_eod` and `deferred_crediting` enable distinct settlement regimes worth showcasing

### What's Already There

The documentation is **remarkably comprehensive**. All 13 files in `docs/reference/scenario/` cover every configurable aspect with schemas, field references, validation rules, examples, and cross-references. The documentation quality is production-grade — a scenario library primarily needs the scenarios themselves, not more docs.

---

## Summary

The SimCash scenario system is well-designed and thoroughly documented. It supports:
- **8 policy types** (from trivial Fifo to LLM-generated InlineJson)
- **4 payment generation modes** (Poisson, per-band, deterministic injection, passive)
- **5 cost components** with per-priority multipliers
- **7 scenario event types** for runtime dynamics
- **5 advanced TARGET2-alignment settings**
- **Full agent asymmetry** in balances, policies, arrivals, limits, and collateral

The config pipeline (YAML → Pydantic → Dict → PyO3 → Rust structs) is clean with validation at both Python and Rust boundaries. Determinism is guaranteed via seeded xorshift64* RNG.
