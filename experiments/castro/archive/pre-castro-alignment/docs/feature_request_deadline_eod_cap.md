# Feature Request: Force Deadlines to End-of-Day Cap

## Summary

Add a configuration flag `deadline_cap_at_eod: true` that forces all transaction deadlines to be at most the end of the current day, regardless of the configured `deadline_range`.

## Motivation

### Castro Paper Alignment

The Castro et al. (2025) paper models a payment system where:
- All payments that arrive during a day **must settle by end-of-day**
- There are no per-transaction "deadlines" that extend beyond the current day
- Banks can always borrow from the central bank at EOD to settle remaining payments

Current SimCash behavior:
- Deadlines are capped at `episode_end_tick` (end of entire simulation)
- A transaction arriving on day 1 can have a deadline extending into day 2 or beyond
- This fundamentally changes the optimization problem from Castro's model

### Example Discrepancy

With current config:
```yaml
simulation:
  ticks_per_day: 12
  num_days: 1

arrival_config:
  deadline_range: [3, 8]  # Offset from arrival
```

A transaction arriving at tick 10 could have:
- `deadline = 10 + 8 = 18` (extends beyond day end at tick 12)
- Currently capped at `episode_end_tick = 12`

But conceptually, we want to enforce that **within each day**, all transactions have deadlines at most at that day's end.

For multi-day simulations:
- Transaction arrives at tick 10 (day 1)
- With `deadline_range: [3, 8]`, raw deadline = 18
- Current: capped at episode_end (e.g., tick 24 for 2 days) = 18
- Desired with EOD cap: capped at day 1 end = tick 12

## Proposed Solution

### Configuration Schema

Add to `SimulationConfig`:

```yaml
simulation:
  ticks_per_day: 12
  num_days: 1
  deadline_cap_at_eod: true  # NEW: Force deadlines to current day EOD
```

Or at the arrival config level for per-agent control:

```yaml
arrival_config:
  rate_per_tick: 0.5
  deadline_range: [3, 8]
  deadline_cap_at_eod: true  # NEW: Per-agent override
```

### Behavior

When `deadline_cap_at_eod: true`:

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

    // Existing: Cap at episode end
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

### Default Behavior

- `deadline_cap_at_eod: false` (default) - existing behavior preserved
- `deadline_cap_at_eod: true` - deadlines capped at current day's EOD

## Implementation Notes

### Files to Modify

1. **`backend/src/arrivals/mod.rs`**
   - Add `deadline_cap_at_eod: bool` and `ticks_per_day: usize` to `ArrivalGenerator`
   - Modify `generate_deadline()` to apply EOD cap when enabled

2. **`backend/src/orchestrator/engine.rs`**
   - Pass `deadline_cap_at_eod` flag from config to `ArrivalGenerator`

3. **`api/payment_simulator/config/schemas.py`**
   - Add `deadline_cap_at_eod: bool = False` to simulation config schema

4. **`backend/src/ffi/types.rs`**
   - Add field to FFI config if needed

### Test Cases

```rust
#[test]
fn test_deadline_capped_at_eod() {
    let mut generator = ArrivalGenerator::new_with_eod_cap(
        configs,
        all_agents,
        episode_end_tick: 24,  // 2 days
        ticks_per_day: 12,
        deadline_cap_at_eod: true,
    );

    // Transaction arriving at tick 10 (day 1)
    let txs = generator.generate_for_agent("BANK_A", 10, &mut rng);

    for tx in txs {
        // Deadline must be <= 12 (day 1 end), not 18
        assert!(tx.deadline_tick() <= 12);
    }
}

#[test]
fn test_deadline_not_capped_when_disabled() {
    let mut generator = ArrivalGenerator::new_with_eod_cap(
        configs,
        all_agents,
        episode_end_tick: 24,
        ticks_per_day: 12,
        deadline_cap_at_eod: false,  // Disabled
    );

    // Transaction arriving at tick 10 with deadline_range [3, 8]
    // Can have deadline up to 18 (capped at episode_end=24)
    let txs = generator.generate_for_agent("BANK_A", 10, &mut rng);

    // Some transactions may have deadline > 12
    // (depends on RNG, but should be allowed)
}
```

## Use Case: Castro Replication

With this feature, Castro-equivalent config becomes:

```yaml
simulation:
  ticks_per_day: 12
  num_days: 1
  deadline_cap_at_eod: true  # All payments due by EOD

cost_rates:
  delay_cost_per_tick_per_cent: 0.00167
  deadline_penalty: 0
  overdue_delay_multiplier: 1.0
  eod_penalty_per_transaction: 0

agents:
  - id: BANK_A
    unsecured_cap: 10000000000  # Unlimited credit (Castro's central bank lending)
    arrival_config:
      deadline_range: [1, 12]   # Will be capped to EOD anyway
```

This ensures the optimization problem matches Castro's:
- All payments have implicit EOD deadline
- No intraday deadline events that don't exist in Castro's model
- Delay costs accumulate until settlement (like Castro's r_d per period)

## Priority

Medium - Important for research paper alignment but not blocking current experiments.

## Related Issues

- Issue #6: Deadline capping at episode end (already fixed)
- Castro paper replication experiments (experiments/castro/)

## References

- Castro et al. (2025), Section 3: "At the end of the day, banks must settle all payment demands."
- `backend/src/arrivals/mod.rs:515-527` - Current deadline generation logic
- `experiments/castro/docs/experiment_2d_design.md` - Castro equivalence analysis
