# LSM Configuration

The `lsm_config` block configures the **Liquidity-Saving Mechanism** - the algorithm that finds and settles offsetting payments to reduce liquidity needs.

---

## Overview

LSM finds payments that can offset each other:

- **Bilateral Offsets**: A owes B $100, B owes A $80 → Net: A pays B $20
- **Multilateral Cycles**: A→B→C→A chains that net to zero

This reduces liquidity requirements and speeds settlement.

---

## Schema

```yaml
lsm_config:
  enable_bilateral: <bool>      # Default: true
  enable_cycles: <bool>         # Default: true
  max_cycle_length: <int>       # Default: 4, range 3-10
  max_cycles_per_tick: <int>    # Default: 10, range 1-100
```

---

## Field Reference

### `enable_bilateral`

**Type**: `bool`
**Required**: No
**Default**: `true`

Enable bilateral (A↔B) offset detection.

#### Implementation Details

**Python Schema** (`schemas.py:557-558`):
```python
enable_bilateral: bool = True
```

**Rust** (`settlement/lsm.rs:85-86`):
```rust
pub enable_bilateral: bool,
```

#### Behavior

When enabled, LSM scans for pairs of payments:
- Transaction 1: A → B for amount X
- Transaction 2: B → A for amount Y
- Result: Settle both, transferring only |X - Y|

#### Example

```yaml
lsm_config:
  enable_bilateral: true    # Find A↔B offsets
```

---

### `enable_cycles`

**Type**: `bool`
**Required**: No
**Default**: `true`

Enable multilateral cycle detection.

#### Implementation Details

**Python Schema** (`schemas.py:559-560`):
```python
enable_cycles: bool = True
```

**Rust** (`settlement/lsm.rs:88-89`):
```rust
pub enable_cycles: bool,
```

#### Behavior

When enabled, LSM searches for circular payment chains:
- A → B → C → A (3-cycle)
- A → B → C → D → A (4-cycle)
- etc.

All payments in a cycle can settle simultaneously with minimal liquidity.

#### Example

```yaml
lsm_config:
  enable_cycles: true       # Find multilateral cycles
```

---

### `max_cycle_length`

**Type**: `int`
**Required**: No
**Constraint**: `3 <= value <= 10`
**Default**: `4`

Maximum number of participants in a settlement cycle.

#### Implementation Details

**Python Schema** (`schemas.py:561-562`):
```python
max_cycle_length: int = Field(default=4, ge=3, le=10)
```

**Rust** (`settlement/lsm.rs:92-93`):
```rust
pub max_cycle_length: usize,
```

#### Trade-offs

| Value | Pros | Cons |
|:------|:-----|:-----|
| `3` | Fast search | May miss larger offsets |
| `4` | Good balance | Default |
| `5-6` | More offsets found | Slower search |
| `7+` | Maximum offsets | Computationally expensive |

#### Cycle Search Complexity

Cycle detection is O(n^k) where k = max_cycle_length. Keep k reasonable.

#### Example

```yaml
lsm_config:
  max_cycle_length: 3      # Only 3-way cycles (faster)
```

---

### `max_cycles_per_tick`

**Type**: `int`
**Required**: No
**Constraint**: `1 <= value <= 100`
**Default**: `10`

Maximum number of cycles to settle per tick.

#### Implementation Details

**Python Schema** (`schemas.py:563`):
```python
max_cycles_per_tick: int = Field(default=10, ge=1, le=100)
```

**Rust** (`settlement/lsm.rs:96-97`):
```rust
pub max_cycles_per_tick: usize,
```

#### Behavior

- LSM continues finding cycles until limit reached
- Prevents runaway computation on large queues
- Remaining cycles deferred to next tick

#### Trade-offs

| Value | Use Case |
|:------|:---------|
| `1` | Minimal LSM (BIS model) |
| `10` | Default balance |
| `20` | Active netting |
| `100` | Aggressive netting |

#### Example

```yaml
lsm_config:
  max_cycles_per_tick: 20    # More aggressive netting
```

---

## Complete Examples

### Default Configuration

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 10
```

### Bilateral Only (BIS-Style)

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: false        # No multilateral cycles
  max_cycle_length: 3         # Not used, but required
  max_cycles_per_tick: 1      # Minimal
```

### Aggressive Netting

```yaml
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 5         # Find larger cycles
  max_cycles_per_tick: 20     # More per tick
```

### LSM Disabled

```yaml
lsm_config:
  enable_bilateral: false
  enable_cycles: false
  # Payments settle only via RTGS
```

---

## LSM Algorithm Sequence

When `algorithm_sequencing: true` (see [advanced-settings.md](advanced-settings.md)):

```
Each Tick:
  1. FIFO settlement attempt (RTGS)
  2. Bilateral offset detection
  3. Multilateral cycle detection
```

Without sequencing, LSM runs as part of RTGS processing.

---

## Event Types

LSM generates specific events:

| Event | Description |
|:------|:------------|
| `LsmBilateralOffset` | Two-party offset settled |
| `LsmCycleSettlement` | Multilateral cycle settled |

Events include:
- Participant agents
- Transaction IDs
- Amounts
- Net positions
- Total value settled

---

## Interaction with Other Settings

### Entry Disposition Offsetting

When `entry_disposition_offsetting: true`:
- LSM checks for bilateral offset when payment **enters** Queue 2
- Immediate netting opportunity detection

### Priority Mode

When `priority_mode: true`:
- LSM respects priority bands
- Urgent payments prioritized for netting
- Low-priority may wait longer

### Agent Limits

- LSM respects bilateral/multilateral limits
- Limits can block otherwise-valid cycles
- Limit breaches logged as events

---

## Performance Considerations

### Queue Size Impact

| Queue Size | LSM Performance |
|:-----------|:----------------|
| < 100 | Fast |
| 100-500 | Moderate |
| 500+ | May need lower `max_cycle_length` |

### Tuning for Performance

```yaml
# Faster (less comprehensive)
lsm_config:
  enable_cycles: true
  max_cycle_length: 3
  max_cycles_per_tick: 5

# More thorough (slower)
lsm_config:
  enable_cycles: true
  max_cycle_length: 5
  max_cycles_per_tick: 20
```

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python LsmConfig | `api/payment_simulator/config/schemas.py` | 556-563 |
| Rust LsmConfig | `simulator/src/settlement/lsm.rs` | 84-107 |
| FFI Parsing | `simulator/src/ffi/types.rs` | 872-898 |
| LSM Engine | `simulator/src/settlement/lsm.rs` | - |

---

## Navigation

**Previous**: [Cost Rates](cost-rates.md)
**Next**: [Scenario Events](scenario-events.md)
