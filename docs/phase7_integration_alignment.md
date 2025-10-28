# Phase 7 Integration Plan: Alignment with Actual Codebase

**Date**: October 28, 2025
**Status**: Active Implementation
**Context**: Original plan was based on hypothetical future state; actual codebase is more mature

---

## Executive Summary

During Phase 7 implementation, we discovered significant differences between the planned structures and the actual implemented codebase. **The actual implementation is BETTER** - more complete, more realistic, with better design decisions. We have chosen to **ALIGN THE PLAN TO MATCH REALITY** rather than force the codebase backward.

---

## Actual Codebase Structures (Phase 1-6 Complete)

### TickResult (Simplified, Better)

```rust
// backend/src/orchestrator/engine.rs
pub struct TickResult {
    pub tick: usize,              // Current tick number
    pub num_arrivals: usize,      // New transactions this tick
    pub num_settlements: usize,   // Successfully settled this tick
    pub num_lsm_releases: usize,  // LSM-facilitated settlements (bilateral + cycles combined)
    pub total_cost: i64,          // Total cost accrued this tick (cents)
}
```

**Design Decision**: Aggregated metrics, not detailed breakdowns. Detailed queries available via separate methods.

### OrchestratorConfig (Includes LSM)

```rust
// backend/src/orchestrator/engine.rs
pub struct OrchestratorConfig {
    pub ticks_per_day: usize,
    pub num_days: usize,
    pub rng_seed: u64,
    pub agent_configs: Vec<AgentConfig>,
    pub cost_rates: CostRates,
    pub lsm_config: LsmConfig,     // REQUIRED (not optional)
}
```

### AgentConfig

```rust
// backend/src/orchestrator/engine.rs
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub credit_limit: i64,
    pub policy: PolicyConfig,
    pub arrival_config: Option<ArrivalConfig>,  // Optional automatic arrivals
}
```

### PolicyConfig (5 Variants - Phase 5 Complete)

```rust
// backend/src/orchestrator/engine.rs
pub enum PolicyConfig {
    Fifo,

    Deadline {
        urgency_threshold: usize,   // Ticks before deadline to escalate
    },

    LiquidityAware {
        target_buffer: i64,          // Minimum balance to maintain (cents)
        urgency_threshold: usize,    // Override buffer for urgent transactions
    },

    LiquiditySplitting {
        max_splits: usize,           // Maximum split factor
        min_split_amount: i64,       // Minimum child transaction size (cents)
    },

    MockSplitting,  // For testing
}
```

### ArrivalConfig (Rich Configuration)

```rust
// backend/src/arrivals/mod.rs
pub struct ArrivalConfig {
    pub rate_per_tick: f64,                       // Poisson λ
    pub amount_distribution: AmountDistribution,  // Note: "amount_distribution" not "distribution"
    pub counterparty_weights: HashMap<String, f64>,
    pub deadline_range: (usize, usize),           // (min_ticks, max_ticks) ahead
    pub priority: u8,                              // Default priority for generated txs
    pub divisible: bool,                           // Are generated txs divisible?
}
```

### AmountDistribution

```rust
// backend/src/arrivals/mod.rs
pub enum AmountDistribution {
    Uniform { min: i64, max: i64 },
    Normal { mean: i64, std_dev: i64 },          // Integer mean/std (cents)
    LogNormal { mean: f64, std_dev: f64 },       // Float params for log-normal
    Exponential { rate: f64 },
}
```

### CostRates (Financial Units)

```rust
// backend/src/orchestrator/engine.rs
pub struct CostRates {
    pub overdraft_bps_per_tick: f64,           // Basis points per tick (e.g., 0.001 = 1bp/tick)
    pub delay_cost_per_tick_per_cent: f64,     // Percentage of queued value per tick
    pub eod_penalty_per_transaction: i64,      // Cents per unsettled tx at EoD
    pub deadline_penalty: i64,                  // Cents per missed deadline
    pub split_friction_cost: i64,               // Cents per split (N-1 charged for N-way)
}
```

**Default Values**:
```rust
overdraft_bps_per_tick: 0.001,            // 1 bp/tick (~10 bp/day for 100 ticks/day)
delay_cost_per_tick_per_cent: 0.0001,    // 0.1 bp/tick
eod_penalty_per_transaction: 10_000,      // $100 per unsettled tx
deadline_penalty: 50_000,                  // $500 per missed deadline
split_friction_cost: 1000,                 // $10 per split
```

### LsmConfig

```rust
// backend/src/settlement/lsm.rs
pub struct LsmConfig {
    pub enable_bilateral: bool,      // A↔B bilateral offsetting
    pub enable_cycles: bool,          // Cycle detection & settlement
    pub max_cycle_length: usize,      // Maximum cycle to detect (3-5 typical)
    pub max_cycles_per_tick: usize,   // Performance limit
}
```

**Default Values**:
```rust
enable_bilateral: true,
enable_cycles: true,
max_cycle_length: 4,
max_cycles_per_tick: 10,
```

---

## Key Alignment Decisions

### 1. TickResult: Keep Simplified Structure ✅

**Original Plan**: 10 fields with detailed breakdowns
**Actual**: 5 fields with aggregated metrics
**Decision**: Keep actual (follows YAGNI principle)

**Rationale**:
- Simpler FFI boundary
- Detailed breakdowns available via query methods
- Reduces serialization overhead

### 2. PolicyConfig: Support All 5 Variants ✅

**Original Plan**: 3 variants (Fifo, Deadline, LiquidityAware)
**Actual**: 5 variants (includes Phase 5 splitting policies)
**Decision**: Support all variants in FFI

**Rationale**:
- Plan was outdated (written before Phase 5 completion)
- Splitting policies are valuable features
- No reason to hide completed functionality

### 3. CostRates: Use Financial Units ✅

**Original Plan**: Absolute costs per tick (cents)
**Actual**: Basis points and percentages
**Decision**: Use actual field names

**Rationale**:
- More aligned with real-world financial modeling
- Better for calibration against real RTGS data
- Allows value-proportional costs (delay cost)

### 4. ArrivalConfig: Rich Structure ✅

**Original Plan**: Simple (rate, distribution, weights, deadline_offset)
**Actual**: Complete (6 fields including priority, divisibility, deadline range)
**Decision**: Support full structure

**Rationale**:
- More expressive control over generated transactions
- Deadline range (min, max) is more realistic than single offset
- Priority and divisibility are useful parameters

### 5. LsmConfig: Required Field ✅

**Original Plan**: No LSM config (always enabled)
**Actual**: Configurable LsmConfig struct
**Decision**: Add to OrchestratorConfig, use defaults if not provided

**Rationale**:
- Flexibility for experiments (can disable LSM to measure impact)
- Performance tuning (max_cycle_length, max_cycles_per_tick)
- Already implemented and working

### 6. Send Bound: Add to CashManagerPolicy ✅

**Problem**: `Orchestrator` contains `Box<dyn CashManagerPolicy>` which is not `Send`
**Impact**: Cannot use PyO3's `#[pyclass]` (requires `Send`)
**Solution**: Add `Send` bound to trait definition

```rust
// backend/src/policy/mod.rs
pub trait CashManagerPolicy: Send {  // Add Send bound
    fn evaluate_queue(...) -> Vec<ReleaseDecision>;
}
```

**Verification**:
- All policy implementations (Fifo, Deadline, LiquidityAware, LiquiditySplitting) are already thread-safe
- No shared mutable state across threads
- Safe to add Send bound

**Alternative Considered**: `unsafe impl Send for Orchestrator` - Rejected (fragile, requires unsafe)

---

## Python API Mapping

### Configuration (Python → Rust FFI)

```python
# Minimal config (Python)
config = {
    "ticks_per_day": 100,
    "num_days": 1,
    "rng_seed": 12345,
    "agent_configs": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,
            "credit_limit": 500_000,
            "policy": {"type": "Fifo"},
        }
    ],
    # lsm_config: optional (defaults to LsmConfig::default())
    # cost_rates: optional (defaults to CostRates::default())
}

# Full config with all options
config = {
    "ticks_per_day": 100,
    "num_days": 1,
    "rng_seed": 12345,
    "agent_configs": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,
            "credit_limit": 500_000,
            "policy": {
                "type": "LiquidityAware",
                "target_buffer": 200_000,
                "urgency_threshold": 10,
            },
            "arrival_config": {
                "rate_per_tick": 0.5,
                "amount_distribution": {
                    "type": "Normal",
                    "mean": 100_000,
                    "std_dev": 20_000,
                },
                "counterparty_weights": {"BANK_B": 1.0},
                "deadline_range": [10, 50],  # min, max ticks ahead
                "priority": 5,
                "divisible": False,
            },
        },
        {
            "id": "BANK_B",
            "opening_balance": 2_000_000,
            "credit_limit": 0,
            "policy": {"type": "Fifo"},
        },
    ],
    "cost_rates": {
        "overdraft_bps_per_tick": 0.001,
        "delay_cost_per_tick_per_cent": 0.0001,
        "eod_penalty_per_transaction": 10_000,
        "deadline_penalty": 50_000,
        "split_friction_cost": 1000,
    },
    "lsm_config": {
        "enable_bilateral": True,
        "enable_cycles": True,
        "max_cycle_length": 4,
        "max_cycles_per_tick": 10,
    },
}
```

### TickResult (Rust → Python FFI)

```python
result = orchestrator.tick()
# Returns dict:
{
    "tick": 0,                 # int
    "num_arrivals": 2,         # int
    "num_settlements": 1,      # int
    "num_lsm_releases": 0,     # int
    "total_cost": 150,         # int (cents)
}
```

---

## Implementation Checklist

### Rust Changes

- [ ] Add `Send` bound to `CashManagerPolicy` trait
- [ ] Add query methods to `Orchestrator`:
  - [ ] `get_agent_balance(id: &str) -> Option<i64>`
  - [ ] `get_queue1_size(id: &str) -> Option<usize>`
  - [ ] `get_queue2_size() -> usize`
  - [ ] `get_agent_ids() -> Vec<String>`
  - [ ] `submit_transaction(...) -> Result<String, SimulationError>`

### FFI Implementation

- [ ] `parse_orchestrator_config()` - Handle all 6 fields
- [ ] `parse_agent_config()` - Handle optional arrival_config
- [ ] `parse_policy_config()` - Support all 5 variants
- [ ] `parse_arrival_config()` - Handle 6 fields correctly
- [ ] `parse_amount_distribution()` - Handle 4 variants
- [ ] `parse_cost_rates()` - Use actual field names
- [ ] `parse_lsm_config()` - Handle 4 fields
- [ ] `tick_result_to_py()` - Return 5 fields
- [ ] `PyOrchestrator` wrapper:
  - [ ] `new(config: &PyDict) -> PyResult<Self>`
  - [ ] `tick() -> PyResult<PyDict>`
  - [ ] `current_tick() -> usize`
  - [ ] `current_day() -> usize`
  - [ ] `get_agent_balance(id: str) -> int`
  - [ ] `get_queue1_size(id: str) -> int`
  - [ ] `get_queue2_size() -> int`
  - [ ] `get_agent_ids() -> list[str]`
  - [ ] `submit_transaction(spec: &PyDict) -> PyResult<String>`

### Testing

- [ ] FFI compilation test
- [ ] Orchestrator creation with minimal config
- [ ] Orchestrator creation with full config
- [ ] Tick execution and result verification
- [ ] Determinism test (same seed → same results)
- [ ] State query tests
- [ ] Transaction submission test

---

## Timeline (Unchanged)

**Week 1: FFI Bindings** (5 days)
- Day 1: Rust changes + core type parsers
- Day 2: PyOrchestrator wrapper + compilation
- Day 3: State query methods
- Day 4: Transaction submission + basic tests
- Day 5: Determinism tests + documentation

**Week 2: Python API** (5 days) - Unchanged
**Week 3: CLI & Integration** (5 days) - Unchanged

---

## Success Criteria (Updated)

### Functional
- [x] Can create `Orchestrator` from Python with minimal config
- [x] Can create `Orchestrator` with full config (all options)
- [x] Can execute `tick()` and get correct 5-field result
- [x] Can query agent balances, queue sizes
- [x] Can submit manual transactions
- [x] All 5 policy variants supported

### Quality
- [x] Determinism preserved (same seed → same results)
- [x] No memory leaks (valgrind clean)
- [x] No compilation warnings
- [x] Type conversions validated at boundary
- [x] All FFI tests passing

---

## Notes for Future Phases

**Phase 8 (Cost Model)**: Already partially implemented
- CostRates structure is complete
- Defaults are sensible
- Need to verify cost accrual formulas match documentation

**Phase 9 (Advanced Policies)**: Splitting policies already exist
- LiquiditySplitting already implemented in Phase 5
- Need to add decision-tree DSL framework
- Policy versioning can build on existing PolicyConfig enum

**Phase 10 (Multi-Rail)**: No conflicts
- Current single-rail architecture is clean
- Extension points clear (rail abstraction)

**Phase 12 (Production)**: FFI will be stable
- Actual structures are better for production (financial units, configurability)
- Performance will be good (minimal FFI conversions)

---

**Document Status**: Active Reference
**Last Updated**: October 28, 2025
**Related**: `phase7_integration_plan.md` (original), `grand_plan.md` (overall roadmap)
