# Priority System

The priority system controls **how payments are ordered and processed** based on urgency. It includes priority bands, queue ordering, and dynamic escalation.

---

## Overview

Priorities range from 0 (lowest) to 10 (highest), divided into bands:

| Band | Priority Range | Description |
|:-----|:---------------|:------------|
| **Urgent** | 8-10 | Critical: securities, CLS, central bank |
| **Normal** | 4-7 | Standard interbank payments |
| **Low** | 0-3 | Discretionary, deferrable |

---

## Priority Configuration Points

| Setting | Location | Purpose |
|:--------|:---------|:--------|
| `priority` | `arrival_config` | Fixed priority |
| `priority_distribution` | `arrival_config` | Variable priorities |
| `arrival_bands` | Agent config | Per-band arrivals |
| `queue1_ordering` | Top-level | Queue 1 sort order |
| `priority_mode` | Top-level | T2 priority bands in Queue 2 |
| `priority_escalation` | Top-level | Dynamic priority boost |
| `priority_delay_multipliers` | `cost_rates` | Per-band delay costs |

---

## Transaction Priority

### Fixed Priority

Set in arrival config:

```yaml
arrival_config:
  priority: 5              # All transactions priority 5
```

### Priority Distribution

Variable priorities per transaction:

```yaml
arrival_config:
  priority_distribution:
    type: Categorical
    values: [3, 5, 7, 9]
    weights: [0.2, 0.5, 0.2, 0.1]
```

See [distributions.md](distributions.md) for distribution types.

---

## Queue 1 Ordering

**Setting**: `queue1_ordering`
**Location**: Top-level config
**Type**: `"Fifo"` or `"priority_deadline"`
**Default**: `"Fifo"`

Controls how Queue 1 (internal agent queue) is sorted.

### Schema

```yaml
queue1_ordering: <string>    # "Fifo" or "priority_deadline"
```

### Implementation

**Rust** (`engine.rs:230-237`):
```rust
pub enum Queue1Ordering {
    Fifo,
    PriorityDeadline,
}
```

### `Fifo` Mode

Default behavior. Transactions processed in arrival order.

```yaml
queue1_ordering: "Fifo"
```

### `PriorityDeadline` Mode

Transactions sorted by:
1. **Priority** (descending) - higher first
2. **Deadline** (ascending) - sooner first
3. **Arrival** (ascending) - FIFO tiebreaker

```yaml
queue1_ordering: "priority_deadline"
```

### Impact

- Policy evaluates transactions in sorted order
- High-priority transactions considered first
- Release budgets apply to sorted sequence

---

## T2 Priority Mode

**Setting**: `priority_mode`
**Location**: Top-level config
**Type**: `bool`
**Default**: `false`

Enables TARGET2-style priority band processing in Queue 2.

### Schema

```yaml
priority_mode: true
```

### Implementation

**Rust** (`engine.rs:166`):
```rust
pub priority_mode: bool,
```

### Behavior

When enabled:
- Queue 2 processes **all Urgent** (8-10) before **all Normal** (4-7) before **all Low** (0-3)
- FIFO within each band
- Models T2's actual priority handling

When disabled:
- Pure FIFO in Queue 2
- Priority only affects sorting if `queue1_ordering: "priority_deadline"`

### Example

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10

queue1_ordering: "priority_deadline"
priority_mode: true
```

---

## Priority Escalation

**Setting**: `priority_escalation`
**Location**: Top-level config
**Type**: Object
**Default**: Disabled

Automatically boosts priority as deadlines approach, preventing priority starvation.

### Schema

```yaml
priority_escalation:
  enabled: <bool>                    # Default: false
  curve: <string>                    # Default: "linear"
  start_escalating_at_ticks: <int>   # Default: 20
  max_boost: <int>                   # Default: 3
```

### Fields

#### `enabled`

**Type**: `bool`
**Default**: `false`

Enable/disable escalation.

#### `curve`

**Type**: `str`
**Default**: `"linear"`

Boost curve type. Currently supported: `"linear"`.

#### `start_escalating_at_ticks`

**Type**: `int`
**Default**: `20`

Begin escalating when `ticks_to_deadline <= start_escalating_at_ticks`.

#### `max_boost`

**Type**: `int`
**Default**: `3`

Maximum priority boost applied.

### Implementation

**Rust** (`engine.rs:188-214`):
```rust
pub struct PriorityEscalationConfig {
    pub enabled: bool,
    pub curve: String,
    pub start_escalating_at_ticks: usize,
    pub max_boost: u8,
}
```

### Escalation Formula (Linear)

```
progress = 1 - (ticks_remaining / start_escalating_at_ticks)
boost = max_boost × progress
new_priority = min(10, original_priority + boost)
```

### Example Progression

With `start_escalating_at_ticks: 20` and `max_boost: 3`:

| Ticks Remaining | Progress | Boost | Original 5 → |
|:----------------|:---------|:------|:-------------|
| 20 | 0.00 | 0.0 | 5 |
| 15 | 0.25 | 0.75 | 5.75 → 6 |
| 10 | 0.50 | 1.5 | 6.5 → 7 |
| 5 | 0.75 | 2.25 | 7.25 → 7 |
| 1 | 0.95 | 2.85 | 7.85 → 8 |
| 0 | 1.00 | 3.0 | 8 |

### Events

Escalation generates `PriorityEscalated` events with:
- Transaction ID
- Original priority
- New priority
- Ticks remaining

### Example Configuration

```yaml
priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 25
  max_boost: 4
```

---

## Priority Delay Multipliers

**Setting**: `priority_delay_multipliers`
**Location**: `cost_rates` block
**Type**: Object
**Default**: None (no per-band adjustment)

Adjusts delay costs based on transaction priority band.

### Schema

```yaml
cost_rates:
  priority_delay_multipliers:
    urgent_multiplier: <float>   # Default: 1.0
    normal_multiplier: <float>   # Default: 1.0
    low_multiplier: <float>      # Default: 1.0
```

### Implementation

See [cost-rates.md](cost-rates.md) for details.

### Behavior

Delay cost multiplied by band multiplier:

```
effective_delay = base_delay × band_multiplier
```

### BIS Model Example

```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5    # 1.5% for urgent
    normal_multiplier: 1.0    # 1.0% for normal
    low_multiplier: 0.5       # 0.5% for low
```

---

## Arrival Bands

Per-band arrival configuration generates transactions with appropriate priority ranges.

### Schema

```yaml
arrival_bands:
  urgent:
    rate_per_tick: 0.1
    # ... urgent band config
  normal:
    rate_per_tick: 0.4
    # ... normal band config
  low:
    rate_per_tick: 0.2
    # ... low band config
```

See [arrivals.md](arrivals.md) for complete reference.

### Priority Assignment

| Band | Priority Range |
|:-----|:---------------|
| `urgent` | Uniform random 8-10 |
| `normal` | Uniform random 4-7 |
| `low` | Uniform random 0-3 |

---

## Policy Integration

Priority available in JSON policies:

| Field | Description |
|:------|:------------|
| `priority` | Current priority (may be escalated) |
| `original_priority` | Priority at arrival (before escalation) |

### Example Policy Pattern

```json
{
  "type": "condition",
  "condition": {
    "op": ">=",
    "left": {"field": "priority"},
    "right": {"value": 8.0}
  },
  "on_true": {
    "type": "action",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "action": "Hold"
  }
}
```

---

## Complete Examples

### T2-Style Configuration

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10
  rng_seed: 42

queue1_ordering: "priority_deadline"
priority_mode: true

priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 15
  max_boost: 2

cost_rates:
  delay_cost_per_tick_per_cent: 0.0001
  priority_delay_multipliers:
    urgent_multiplier: 2.0
    normal_multiplier: 1.0
    low_multiplier: 0.5

agents:
  - id: BANK_A
    arrival_bands:
      urgent:
        rate_per_tick: 0.1
        amount_distribution:
          type: Uniform
          min: 500000
          max: 2000000
        deadline_offset_min: 10
        deadline_offset_max: 25
      normal:
        rate_per_tick: 0.4
        amount_distribution:
          type: LogNormal
          mean: 11.0
          std_dev: 1.0
        deadline_offset_min: 30
        deadline_offset_max: 60
```

### Priority Distribution (Single Config)

```yaml
agents:
  - id: BANK_A
    arrival_config:
      rate_per_tick: 0.65
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      priority_distribution:
        type: Categorical
        values: [3, 5, 7, 9]
        weights: [0.25, 0.50, 0.15, 0.10]
      deadline_range: [35, 70]
```

### Minimal Priority (FIFO Everything)

```yaml
queue1_ordering: "Fifo"      # or omit (default)
priority_mode: false          # or omit (default)
# priority_escalation: disabled by default

agents:
  - id: BANK_A
    arrival_config:
      priority: 5             # All same priority
```

---

## Priority Band Reference

| Priority | Band | Typical Use Case |
|:---------|:-----|:-----------------|
| 10 | Urgent | Central bank operations |
| 9 | Urgent | Securities settlement (T2S) |
| 8 | Urgent | CLS, time-critical |
| 7 | Normal | Important interbank |
| 6 | Normal | Standard commercial |
| 5 | Normal | Regular payments |
| 4 | Normal | Less urgent standard |
| 3 | Low | Deferrable payments |
| 2 | Low | Discretionary |
| 1 | Low | Lowest active |
| 0 | Low | Minimum priority |

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Priority Distributions | `api/payment_simulator/config/schemas.py` | 60-111 |
| Queue1Ordering | `backend/src/orchestrator/engine.rs` | 230-237 |
| PriorityEscalationConfig | `backend/src/orchestrator/engine.rs` | 188-214 |
| PriorityBand | `backend/src/orchestrator/engine.rs` | 427-435 |
| FFI Parsing | `backend/src/ffi/types.rs` | 637-701 |

---

## Navigation

**Previous**: [Scenario Events](scenario-events.md)
**Next**: [Advanced Settings](advanced-settings.md)
