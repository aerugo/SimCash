# Simulation Settings

The `simulation` block contains the **core timing and determinism settings** for the scenario. These three required fields control the fundamental structure of the simulation.

---

## Schema

```yaml
simulation:
  ticks_per_day: <int>    # Required, > 0
  num_days: <int>         # Required, > 0
  rng_seed: <int>         # Required
```

---

## Field Reference

### `ticks_per_day`

**Type**: `int`
**Required**: Yes
**Constraint**: Must be greater than 0
**Default**: None (required)

The number of discrete time units (ticks) in a single simulated business day.

#### Implementation Details

**Python Schema** (`schemas.py:569-571`):
```python
class SimulationSettings(BaseModel):
    ticks_per_day: int = Field(..., gt=0)
```

**Rust** (`engine.rs:102-105`):
```rust
pub struct OrchestratorConfig {
    pub ticks_per_day: usize,
    // ...
}
```

**FFI Validation** (`types.rs:134-141`):
```rust
let ticks_per_day: usize = extract_required(py_simulation, "ticks_per_day")?;
if ticks_per_day == 0 {
    return Err(PyValueError::new_err("ticks_per_day must be > 0"));
}
```

#### Use Cases

| Value | Scenario | Notes |
|:------|:---------|:------|
| `3` | BIS Box 3 model | 3 periods (morning/afternoon/EOD) |
| `100` | Standard simulation | ~5.76 minutes per tick (8-hour day) |
| `480` | Minute-level | 1 tick = 1 minute (8-hour day) |
| `1000` | High-resolution | Fine-grained timing analysis |

#### Example

```yaml
simulation:
  ticks_per_day: 100  # Each tick represents ~5 minutes of real time
```

#### Related Settings

- `eod_rush_threshold` (advanced): Controls when EOD rush behavior begins (default: 80% of day)
- `day_progress_fraction` (policy field): Available in policies as `current_tick / ticks_per_day`

---

### `num_days`

**Type**: `int`
**Required**: Yes
**Constraint**: Must be greater than 0
**Default**: None (required)

The total number of business days to simulate.

#### Implementation Details

**Python Schema** (`schemas.py:572`):
```python
num_days: int = Field(..., gt=0)
```

**Rust** (`engine.rs:106`):
```rust
pub num_days: usize,
```

#### Behavior

- Total ticks = `ticks_per_day × num_days`
- Day boundaries trigger:
  - EOD penalty assessment for unsettled transactions
  - State register resets (if using JSON policy)
  - Day-level metrics aggregation

#### Use Cases

| Value | Scenario | Notes |
|:------|:---------|:------|
| `1` | Single-day experiment | Quick testing, BIS model replication |
| `10` | Short-term stress | Testing policy adaptation |
| `25` | Multi-week crisis | Systemic risk analysis |
| `252` | One trading year | Long-term equilibrium analysis |

#### Example

```yaml
simulation:
  num_days: 25  # Simulate ~1 month of business days
```

---

### `rng_seed`

**Type**: `int`
**Required**: Yes
**Constraint**: None (any integer value)
**Default**: None (required)

The seed for the deterministic random number generator. This single value controls **all randomness** in the simulation.

#### Implementation Details

**Python Schema** (`schemas.py:573`):
```python
rng_seed: int
```

**Rust** (`engine.rs:107`):
```rust
pub rng_seed: u64,
```

**RNG Algorithm**: xorshift64* (deterministic, high-quality PRNG)

#### Determinism Guarantee

**CRITICAL INVARIANT**: Running the same configuration with the same `rng_seed` **must** produce byte-for-byte identical results.

```bash
# These must be identical
payment-sim run --config scenario.yaml > run1.txt
payment-sim run --config scenario.yaml > run2.txt
diff run1.txt run2.txt  # No differences
```

#### What the RNG Controls

| Component | Randomness Used For |
|:----------|:-------------------|
| Transaction arrivals | Poisson timing (when transactions arrive) |
| Amount sampling | Drawing from amount distributions |
| Priority sampling | Drawing from priority distributions |
| Counterparty selection | Weighted random choice of receiver |
| Deadline assignment | Uniform draw from deadline range |

#### Implementation Pattern

The Rust RNG follows a strict pattern that preserves determinism:

```rust
// Every RNG call updates the seed
let (random_value, new_seed) = rng_manager.next_u64(current_seed);
state.rng_seed = new_seed;  // CRITICAL: Always persist new seed
```

#### Use Cases

```yaml
# Reproducible experiments
simulation:
  rng_seed: 42

# Testing sensitivity
simulation:
  rng_seed: 12345  # Different seed = different randomness = different outcomes
```

#### Best Practices

1. **Document your seed**: Record which seed produced which results
2. **Use consistent seeds**: For A/B testing, only change the variable being tested
3. **Multiple runs**: Test with different seeds to understand variance
4. **Debugging**: Same seed reproduces bugs exactly

---

## Complete Example

```yaml
simulation:
  ticks_per_day: 100   # 100 ticks per day
  num_days: 10         # 10 business days
  rng_seed: 42         # Deterministic seed

# Total simulation: 1,000 ticks
# Each tick: approximately 4.8 minutes of an 8-hour business day
```

---

## Time Calculation Reference

| Metric | Formula | Example (100 ticks/day, 10 days) |
|:-------|:--------|:---------------------------------|
| Total ticks | `ticks_per_day × num_days` | 1,000 ticks |
| Real-time per tick | `480 min / ticks_per_day` | 4.8 minutes |
| EOD rush start | `ticks_per_day × eod_rush_threshold` | Tick 80 each day |
| Day of tick N | `N // ticks_per_day` | Tick 450 = Day 4 |
| Tick within day | `N % ticks_per_day` | Tick 450 = Tick 50 of day |

---

## Validation Errors

### Missing Required Field

```
Error: Field required
  simulation.ticks_per_day: field required
```

**Fix**: Ensure all three fields are present.

### Invalid Value

```
Error: Input should be greater than 0
  simulation.num_days: ensure this value is greater than 0
```

**Fix**: Use positive integers for `ticks_per_day` and `num_days`.

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python Schema | `api/payment_simulator/config/schemas.py` | 569-575 |
| Rust Config | `simulator/src/orchestrator/engine.rs` | 102-114 |
| FFI Parsing | `simulator/src/ffi/types.rs` | 130-145 |

---

## Navigation

**Previous**: [Index](index.md)
**Next**: [Agent Configuration](agents.md)
