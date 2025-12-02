# Deadline EOD Cap Implementation Plan

**Date**: 2025-12-02
**Feature Request**: `experiments/castro/docs/feature_request_deadline_eod_cap.md`
**Priority**: Medium (Important for Castro paper alignment)

---

## 1. Feature Overview

### 1.1 Current Behavior (Episode-End Cap)

When transactions are generated via the arrival system, their deadlines are calculated as:

```rust
// backend/src/arrivals/mod.rs:515-527
fn generate_deadline(&self, arrival_tick: usize, range: (usize, usize), rng: &mut RngManager) -> usize {
    let (min_offset, max_offset) = range;
    let offset = rng.range(min_offset as i64, max_offset as i64 + 1) as usize;
    let raw_deadline = arrival_tick + offset;

    // Cap deadline at episode end (Issue #6 fix)
    raw_deadline.min(self.episode_end_tick)
}
```

This means a transaction arriving on day 1 can have a deadline extending into day 2 or beyond (up to `episode_end_tick`).

### 1.2 Castro Model (EOD Cap)

In Castro et al. (2025) Section 3:
> "At the end of the day, banks must settle all payment demands."

All payments that arrive during a day must settle by end-of-day. There are no per-transaction "deadlines" that extend beyond the current day.

### 1.3 Implementation Goal

Add a configuration option `deadline_cap_at_eod: bool` (default: false) that:
- When **false**: Current behavior (deadline capped at episode end)
- When **true**: Deadlines capped at end of the current day

---

## 2. Edge Case Analysis

### 2.1 Transaction Arriving Mid-Day

**Scenario**: `ticks_per_day=12`, transaction arrives at tick 10 (day 1), `deadline_range=[3,8]`.

| Mode | Raw Deadline | Cap Applied | Final Deadline |
|------|--------------|-------------|----------------|
| Episode-End (current) | 18 | episode_end_tick | 18 (if episode=24) or 12 (if episode=12) |
| EOD Cap | 18 | day_end=12 | 12 |

**Key Insight**: With EOD cap, deadline shrinks from 8 ticks to 2 ticks, significantly changing cost dynamics.

### 2.2 Transaction Arriving at Day Start

**Scenario**: `ticks_per_day=12`, transaction arrives at tick 0 (day 1), `deadline_range=[3,8]`.

| Mode | Raw Deadline | Final Deadline |
|------|--------------|----------------|
| Episode-End | 0 + [3,8] = 3-8 | 3-8 (unchanged) |
| EOD Cap | 0 + [3,8] = 3-8 | 3-8 (unchanged) |

**Key Insight**: Early arrivals are unaffected since their deadline naturally falls within the day.

### 2.3 Multi-Day Simulation (Day Boundary)

**Scenario**: `ticks_per_day=12`, `num_days=3`, transaction arrives at tick 22 (day 2), `deadline_range=[5,10]`.

| Mode | Day 2 Range | Raw Deadline | Final Deadline |
|------|-------------|--------------|----------------|
| Episode-End | ticks 12-23 | 22 + [5,10] = 27-32 | min(32, 36) = 32 |
| EOD Cap | ticks 12-23 | 22 + [5,10] = 27-32 | min(32, 24) = 24 |

**Key Insight**: In multi-day simulations, EOD cap forces all transactions to settle within their arrival day.

### 2.4 Transaction at Last Tick of Day

**Scenario**: `ticks_per_day=12`, transaction arrives at tick 11 (last tick of day 1), `deadline_range=[1,5]`.

| Mode | Raw Deadline | Final Deadline |
|------|--------------|----------------|
| Episode-End | 11 + [1,5] = 12-16 | 12-16 |
| EOD Cap | 11 + [1,5] = 12-16 | 12 |

**Key Insight**: Last-tick arrivals get deadline exactly at day end (tick 12 = start of day 2, but cap at 12 means must settle by tick 11 or become overdue at tick 12).

### 2.5 Interaction with Overdue Status

With EOD cap, more transactions will become overdue earlier because:
1. Deadline is potentially much shorter
2. If transaction doesn't settle by capped deadline, it becomes `Overdue`
3. `overdue_delay_multiplier` (default 5x) applies

**Example Cost Impact**:
- Without EOD cap: Transaction has 8 ticks of normal delay cost, then overdue
- With EOD cap: Transaction has 2 ticks of normal delay cost, then 6 ticks of 5x overdue cost

### 2.6 Interaction with Deadline Penalty

The `deadline_penalty` is a one-time penalty when transaction becomes overdue:

```rust
// When transition to Overdue status:
Event::TransactionBecameOverdue { deadline_penalty, ... }
```

With EOD cap:
- More transactions hit deadline earlier
- More deadline penalties triggered earlier in simulation
- May significantly increase total costs

### 2.7 Interaction with EOD Penalty

The `eod_penalty_per_transaction` applies to transactions unsettled at end of day.

With EOD cap:
- If a transaction arrives late in day AND doesn't settle by EOD
- It incurs BOTH deadline penalty (transaction-specific) AND EOD penalty
- These are distinct costs that stack

### 2.8 Policy Behavior Changes

**DeadlinePolicy** with `urgency_threshold`:
- Policy submits if `ticks_to_deadline < urgency_threshold`
- With EOD cap, more transactions are "urgent" (closer to deadline)
- May cause more aggressive submission behavior

**LiquidityAware** policy:
- Trades off buffer protection vs deadline urgency
- With tighter deadlines, urgency wins more often

### 2.9 Per-Band Arrival Configuration

Each band has `deadline_offset_min` and `deadline_offset_max`:

```rust
ArrivalBandConfig {
    deadline_offset_min: 2,
    deadline_offset_max: 10,
    ...
}
```

With EOD cap, all bands are affected:
- **Urgent band** (typically tight deadlines): Minimal impact
- **Low band** (typically relaxed deadlines): Maximum impact

### 2.10 CustomTransactionArrival Scenario Events

Scenario events bypass the arrival generator:

```yaml
- type: CustomTransactionArrival
  from_agent: BANK_A
  to_agent: BANK_B
  amount: 100000
  deadline: 15  # Explicit deadline offset
  schedule:
    type: OneTime
    tick: 10
```

**Decision**: CustomTransactionArrival should also respect `deadline_cap_at_eod` when the event is processed. The explicit deadline becomes an offset that is then capped.

### 2.11 Configuration Hierarchy

Feature request suggests two levels:

1. **Global** (simulation level): `deadline_cap_at_eod: true`
2. **Per-agent** (arrival_config level): Override for specific agents

For simplicity, this implementation will use **global-only** configuration. Per-agent can be added later if needed.

### 2.12 Determinism

The EOD cap does not affect determinism:
1. RNG samples deadline offset (same as before)
2. Cap is applied deterministically based on arrival tick and ticks_per_day
3. Same seed + same config = same output

---

## 3. TDD Strategy

### 3.1 Test-First Development Phases

#### Phase 1: Core Capping Logic Tests (Acceptance Criterion)

```rust
#[test]
fn test_deadline_capped_at_eod_mid_day_arrival() {
    // THIS IS THE DEFINING TEST
    // ticks_per_day=12, num_days=2, episode_end=24
    // Transaction arrives at tick 10 with deadline_range=[3,8]
    // Raw deadline = 10 + offset (13-18)
    // With EOD cap: deadline capped at 12

    let mut generator = create_generator_with_eod_cap(
        ticks_per_day: 12,
        num_days: 2,
        deadline_cap_at_eod: true,
    );

    let arrivals = generator.generate_for_agent("BANK_A", 10, &mut rng);

    for tx in arrivals {
        assert!(
            tx.deadline_tick() <= 12,
            "Deadline should be capped at day 1 end (tick 12), got {}",
            tx.deadline_tick()
        );
    }
}
```

#### Phase 2: EOD Cap Disabled (Backward Compatibility)

```rust
#[test]
fn test_deadline_not_capped_when_eod_cap_disabled() {
    // Same scenario but deadline_cap_at_eod=false
    // Deadlines should extend into day 2

    let mut generator = create_generator_with_eod_cap(
        ticks_per_day: 12,
        num_days: 2,
        deadline_cap_at_eod: false,
    );

    // Force arrival at tick 10 with offset that would exceed day 1
    // Some transactions should have deadline > 12
}
```

#### Phase 3: Multi-Day Behavior

```rust
#[test]
fn test_deadline_capped_at_each_days_end() {
    // Day 1: ticks 0-11, day_end=12
    // Day 2: ticks 12-23, day_end=24

    // Transaction at tick 20 (day 2)
    // deadline_range=[5,10] -> raw=25-30
    // With EOD cap: capped at 24

    let arrivals_day2 = generator.generate_for_agent("BANK_A", 20, &mut rng);

    for tx in arrivals_day2 {
        assert!(tx.deadline_tick() <= 24);  // Day 2 end
    }
}
```

#### Phase 4: Day Boundary Edge Cases

```rust
#[test]
fn test_last_tick_of_day_arrival() {
    // Transaction at tick 11 (last tick of day 1)
    // deadline_range=[1,5]
    // With EOD cap: deadline = 12 (exactly at day end)
}

#[test]
fn test_first_tick_of_day_arrival() {
    // Transaction at tick 0
    // deadline_range=[3,8] -> deadlines 3-8
    // All within day 1, no cap applied
}
```

#### Phase 5: Per-Band Deadline Capping

```rust
#[test]
fn test_band_arrivals_respect_eod_cap() {
    // Each priority band should respect EOD cap
    let bands_config = ArrivalBandsConfig {
        urgent: Some(ArrivalBandConfig {
            deadline_offset_min: 2,
            deadline_offset_max: 5,
            ..
        }),
        normal: Some(ArrivalBandConfig {
            deadline_offset_min: 5,
            deadline_offset_max: 15,  // Would extend past day
            ..
        }),
        low: None,
    };

    // Verify normal band deadlines are capped
}
```

#### Phase 6: Cost Interaction Tests

```rust
#[test]
fn test_overdue_occurs_earlier_with_eod_cap() {
    // With EOD cap, transactions become overdue sooner
    // Verify overdue status transition happens at expected tick
}

#[test]
fn test_deadline_penalty_triggered_with_capped_deadline() {
    // Verify deadline penalty event emitted at correct tick
}

#[test]
fn test_delay_cost_accumulation_with_capped_deadline() {
    // Short deadline = fewer ticks of normal delay cost
    // But more ticks of overdue delay cost (5x multiplier)
}
```

#### Phase 7: Integration with Orchestrator

```rust
#[test]
fn test_orchestrator_passes_eod_cap_to_generator() {
    // Config has deadline_cap_at_eod=true
    // Arrivals generated during tick respect the cap
}
```

#### Phase 8: FFI and Python Integration

```python
def test_deadline_cap_at_eod_via_ffi():
    """Verify configuration reaches Rust correctly."""
    config = {
        "simulation": {
            "ticks_per_day": 12,
            "num_days": 1,
            "rng_seed": 42,
        },
        "deadline_cap_at_eod": True,
        "agents": [
            {"id": "A", "opening_balance": 1000000, ...},
            {"id": "B", "opening_balance": 1000000, ...},
        ],
    }

    orch = Orchestrator.new(config)
    # Generate arrivals, verify deadlines capped
```

#### Phase 9: Determinism Tests

```rust
#[test]
fn test_determinism_with_eod_cap() {
    // Same seed + same config = same deadlines
    let arrivals1 = generate_with_seed(42, eod_cap=true);
    let arrivals2 = generate_with_seed(42, eod_cap=true);
    assert_eq!(arrivals1, arrivals2);
}
```

### 3.2 Test Files to Create/Modify

1. **New test file**: `backend/tests/test_deadline_eod_cap.rs`
   - All core Rust tests for the feature

2. **Modify**: `backend/tests/arrival_bands_tests.rs`
   - Add tests for band-specific EOD cap behavior

3. **Python integration**: `api/tests/integration/test_deadline_eod_cap.py`
   - FFI passthrough tests
   - End-to-end verification

---

## 4. Implementation Phases

### Phase 1: Configuration (Rust)

**File: `backend/src/orchestrator/engine.rs`**

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct OrchestratorConfig {
    // ... existing fields ...

    /// Cap deadlines at end of current day (Castro-compatible)
    /// When true, all generated deadlines are capped at the current day's end
    #[serde(default)]
    pub deadline_cap_at_eod: bool,
}
```

### Phase 2: ArrivalGenerator Modification

**File: `backend/src/arrivals/mod.rs`**

Add new fields to `ArrivalGenerator`:

```rust
pub struct ArrivalGenerator {
    // ... existing fields ...

    /// Ticks per day (for EOD cap calculation)
    ticks_per_day: usize,

    /// Whether to cap deadlines at end of current day
    deadline_cap_at_eod: bool,
}
```

Update constructor signatures:

```rust
impl ArrivalGenerator {
    pub fn new(
        configs: HashMap<String, ArrivalConfig>,
        all_agent_ids: Vec<String>,
        episode_end_tick: usize,
        ticks_per_day: usize,        // NEW
        deadline_cap_at_eod: bool,   // NEW
    ) -> Self { ... }

    pub fn new_with_bands(
        band_configs: HashMap<String, ArrivalBandsConfig>,
        all_agent_ids: Vec<String>,
        episode_end_tick: usize,
        ticks_per_day: usize,        // NEW
        deadline_cap_at_eod: bool,   // NEW
    ) -> Self { ... }

    pub fn new_mixed(
        band_configs: HashMap<String, ArrivalBandsConfig>,
        legacy_configs: HashMap<String, ArrivalConfig>,
        all_agent_ids: Vec<String>,
        episode_end_tick: usize,
        ticks_per_day: usize,        // NEW
        deadline_cap_at_eod: bool,   // NEW
    ) -> Self { ... }
}
```

Modify `generate_deadline()`:

```rust
fn generate_deadline(
    &self,
    arrival_tick: usize,
    range: (usize, usize),
    rng: &mut RngManager,
) -> usize {
    let (min_offset, max_offset) = range;
    let offset = rng.range(min_offset as i64, max_offset as i64 + 1) as usize;
    let raw_deadline = arrival_tick + offset;

    // Cap at episode end (Issue #6 fix)
    let episode_capped = raw_deadline.min(self.episode_end_tick);

    // NEW: If deadline_cap_at_eod enabled, also cap at current day's end
    if self.deadline_cap_at_eod {
        let current_day = arrival_tick / self.ticks_per_day;
        let day_end_tick = (current_day + 1) * self.ticks_per_day;
        episode_capped.min(day_end_tick)
    } else {
        episode_capped
    }
}
```

### Phase 3: Orchestrator Integration

**File: `backend/src/orchestrator/engine.rs`**

Pass new parameters when creating ArrivalGenerator:

```rust
// In Orchestrator::new()
let arrival_generator = if has_any_arrivals {
    let episode_end_tick = config.num_days * config.ticks_per_day;
    Some(ArrivalGenerator::new_mixed(
        band_configs_map,
        arrival_configs_map,
        all_agent_ids,
        episode_end_tick,
        config.ticks_per_day,           // NEW
        config.deadline_cap_at_eod,      // NEW
    ))
} else {
    None
};
```

### Phase 4: Python Configuration

**File: `api/payment_simulator/config/schemas.py`**

```python
class SimulationConfig(BaseModel):
    # ... existing fields ...

    deadline_cap_at_eod: bool = Field(
        False,
        description=(
            "When true, all generated transaction deadlines are capped at the "
            "end of the current day (Castro-compatible mode). When false (default), "
            "deadlines are only capped at episode end."
        ),
    )
```

Update `to_ffi_dict()`:

```python
def to_ffi_dict(self) -> dict[str, Any]:
    result = {
        # ... existing fields ...
        "deadline_cap_at_eod": self.deadline_cap_at_eod,
    }
    return result
```

### Phase 5: FFI Types (if needed)

**File: `backend/src/ffi/types.rs`**

Ensure `deadline_cap_at_eod` is parsed from the config dict:

```rust
// In config parsing
let deadline_cap_at_eod = config_dict
    .get("deadline_cap_at_eod")
    .and_then(|v| v.extract::<bool>().ok())
    .unwrap_or(false);
```

---

## 5. Testing Checklist

### 5.1 Unit Tests (Rust)

- [ ] `test_deadline_capped_at_eod_mid_day_arrival` - Core capping logic
- [ ] `test_deadline_not_capped_when_disabled` - Backward compatibility
- [ ] `test_deadline_capped_at_each_days_end` - Multi-day behavior
- [ ] `test_last_tick_of_day_arrival` - Day boundary edge case
- [ ] `test_first_tick_of_day_arrival` - No-cap scenario
- [ ] `test_deadline_capped_at_episode_end_when_shorter` - Episode end takes precedence if earlier

### 5.2 Band Configuration Tests

- [ ] `test_urgent_band_with_eod_cap` - Tight deadlines minimally affected
- [ ] `test_normal_band_with_eod_cap` - Moderate deadlines may be capped
- [ ] `test_low_band_with_eod_cap` - Relaxed deadlines significantly affected
- [ ] `test_mixed_bands_with_eod_cap` - All bands respect cap

### 5.3 Cost Interaction Tests

- [ ] `test_overdue_status_with_capped_deadline` - Overdue triggers at capped deadline
- [ ] `test_deadline_penalty_with_capped_deadline` - Penalty at correct tick
- [ ] `test_delay_cost_with_shortened_deadline` - Cost accumulation correct
- [ ] `test_overdue_multiplier_with_capped_deadline` - 5x multiplier applies after cap

### 5.4 Policy Interaction Tests

- [ ] `test_deadline_policy_with_eod_cap` - Urgency threshold with shortened deadlines
- [ ] `test_liquidity_aware_with_eod_cap` - Buffer vs urgency tradeoff

### 5.5 Integration Tests (Python)

- [ ] `test_deadline_cap_at_eod_config_passed_via_ffi` - Config reaches Rust
- [ ] `test_deadline_cap_at_eod_default_false` - Backward compatible
- [ ] `test_deadline_cap_produces_expected_behavior` - End-to-end verification

### 5.6 Determinism Tests

- [ ] `test_determinism_with_eod_cap_enabled` - Same seed = same output
- [ ] `test_determinism_with_eod_cap_disabled` - Unchanged behavior

### 5.7 Edge Case Tests

- [ ] `test_single_day_simulation` - num_days=1 behavior
- [ ] `test_single_tick_per_day` - ticks_per_day=1 edge case
- [ ] `test_very_long_deadline_range` - deadline_range larger than day
- [ ] `test_deadline_range_exceeds_episode` - Combined caps

---

## 6. Risk Assessment

### 6.1 Backward Compatibility

- **Risk**: Existing simulations change behavior
- **Mitigation**: Default is `false` (current behavior preserved)

### 6.2 Performance Impact

- **Risk**: Additional computation in generate_deadline
- **Mitigation**: One additional division and comparison per transaction (negligible)

### 6.3 Constructor Signature Changes

- **Risk**: Breaking change for ArrivalGenerator constructors
- **Mitigation**: Update all call sites in same commit

### 6.4 Cost Calculation Correctness

- **Risk**: Costs not calculated correctly with early deadlines
- **Mitigation**: Existing cost logic unchanged; only deadline timing changes

### 6.5 Determinism

- **Risk**: Non-deterministic behavior
- **Mitigation**: Cap logic is purely deterministic (integer math)

---

## 7. Documentation Updates

### 7.1 Files to Update

- [ ] `CLAUDE.md` - Add deadline_cap_at_eod to configuration documentation
- [ ] `docs/game-design.md` - Document deadline behavior options
- [ ] `experiments/castro/README.md` - Document Castro-compatible mode usage

### 7.2 Example Configuration

```yaml
simulation:
  ticks_per_day: 12
  num_days: 1
  rng_seed: 12345

# Enable Castro-compatible deadline mode
deadline_cap_at_eod: true

cost_rates:
  delay_cost_per_tick_per_cent: 0.00167
  deadline_penalty: 0         # Castro model has no explicit deadline penalty
  overdue_delay_multiplier: 1.0
  eod_penalty_per_transaction: 0

agents:
  - id: BANK_A
    opening_balance: 10000000
    unsecured_cap: 10000000000  # Unlimited credit (Castro's central bank)
    arrival_config:
      rate_per_tick: 0.5
      deadline_range: [1, 12]   # Will be capped at current day's end
      # ...
```

---

## 8. Success Criteria

1. **Core Test Passes**: Transactions arriving mid-day have deadlines capped at EOD
2. **Backward Compatible**: Default `false` preserves current behavior
3. **Multi-Day Correct**: Each day's transactions respect their day's end
4. **Costs Accurate**: Overdue status and penalties trigger at correct times
5. **Determinism Maintained**: Same seed = same output
6. **All Tests Pass**: Both Rust and Python test suites green
7. **Documentation Complete**: Config option documented with examples

---

## 9. Implementation Order

1. Write failing tests in `backend/tests/test_deadline_eod_cap.rs`
2. Add `deadline_cap_at_eod` to `OrchestratorConfig`
3. Add fields to `ArrivalGenerator`
4. Update `ArrivalGenerator::new*` constructors
5. Modify `generate_deadline()` method
6. Update orchestrator to pass new parameters
7. Run Rust tests (should pass)
8. Add Python schema field
9. Update `to_ffi_dict()`
10. Run Python tests
11. Add integration tests
12. Update documentation
13. Commit and push
