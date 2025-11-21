# Priority System Redesign Plan

## Problem Statement

The current priority implementation has a fundamental design flaw:

1. **Priority is set per-agent** in arrival configs (e.g., `priority: 6`)
2. **All auto-generated transactions** from that agent get the **same priority**
3. **Queue 1 doesn't sort by priority** — it's just FIFO (`Vec<String>`)
4. **Result**: Priority is effectively useless for intra-agent ordering

The only current uses of priority are:
- Custom scenario events with explicit priority overrides
- Policy decision variables (but all txns from same agent have same value)
- Inter-agent comparisons (limited value)

## Real-World Context

### How Priority Works in TARGET2 (T2)

The ECB's TARGET2 system (which this simulator models) has a well-defined priority system:

| Priority | Name | Real-World Use Case |
|----------|------|---------------------|
| **Urgent (0)** | System-level | Central bank operations, CLS settlement |
| **High (1)** | Time-critical | Securities settlement (T2S), margin calls |
| **Normal (2)** | Standard | Regular interbank payments |

Key T2 behaviors:
- **Queue 2 processes by priority first**, then FIFO within priority
- Banks **assign priority at submission time** (not arrival)
- Priority affects **both Queue 1 release decisions AND Queue 2 processing order**
- Urgent payments may bypass certain LSM optimizations

### How Banks Actually Prioritize Payments

In reality, payment priority comes from **multiple sources**:

1. **Payment Type** — Securities settlement > Payroll > Interbank > Discretionary
2. **Client Tier** — VIP/institutional clients get priority handling
3. **Regulatory Deadlines** — CLS cut-offs, securities settlement windows
4. **Contractual SLAs** — Some clients pay for guaranteed same-day settlement
5. **Amount Thresholds** — Large payments may warrant special handling
6. **Dynamic Escalation** — Priority increases as deadline approaches

---

## Proposed Design

### Core Principle

> **Priority should vary at the transaction level, not the agent level.**

A bank processes many different payment types throughout the day. Some are urgent (securities settlement), some are routine (interbank liquidity), some are discretionary (treasury optimization). The priority system should reflect this heterogeneity.

### Component 1: Payment Types

Introduce a **payment type** concept that determines default characteristics:

```yaml
payment_types:
  SECURITIES_SETTLEMENT:
    default_priority: 9
    deadline_range: [10, 30]    # Tight deadlines
    weight: 0.05                # 5% of payments

  PAYROLL:
    default_priority: 8
    deadline_range: [20, 40]
    weight: 0.10

  INTERBANK_LIQUIDITY:
    default_priority: 5
    deadline_range: [30, 70]
    weight: 0.60                # Most common

  DISCRETIONARY:
    default_priority: 3
    deadline_range: [50, 100]
    weight: 0.25
```

**Benefits:**
- Transactions from the same agent have naturally different priorities
- Realistic distribution of payment urgency
- Scenario designers can tune payment mix per agent

### Component 2: Priority Distribution (Alternative/Complement)

For simpler configuration, allow **priority distributions** instead of fixed values:

```yaml
arrival_config:
  priority_distribution:
    type: "Categorical"
    values: [3, 5, 7, 9]
    weights: [0.2, 0.5, 0.2, 0.1]  # 10% urgent, 20% high, 50% normal, 20% low
```

Or continuous:
```yaml
arrival_config:
  priority_distribution:
    type: "Normal"
    mean: 5.0
    std_dev: 2.0
    min: 0
    max: 10
```

**Benefits:**
- Simple to configure
- Creates natural variation without payment type complexity
- Backward compatible (single value = degenerate distribution)

### Component 3: Queue 1 Priority Ordering

Make Queue 1 respect priority (optionally):

```rust
// Current: Vec<String> (FIFO)
// Proposed: BinaryHeap or sorted Vec with composite key

struct QueuedTransaction {
    tx_id: String,
    priority: u8,
    arrival_tick: i64,
    deadline_tick: i64,
}

impl Ord for QueuedTransaction {
    fn cmp(&self, other: &Self) -> Ordering {
        // Primary: priority (descending - higher first)
        // Secondary: deadline (ascending - sooner first)
        // Tertiary: arrival (ascending - FIFO tiebreaker)
        other.priority.cmp(&self.priority)
            .then(self.deadline_tick.cmp(&other.deadline_tick))
            .then(self.arrival_tick.cmp(&other.arrival_tick))
    }
}
```

**Configuration flag:**
```yaml
queue_config:
  queue1_ordering: "priority_deadline"  # or "fifo" for current behavior
```

**Benefits:**
- High-priority payments naturally surface to front of queue
- Policy still has final say (can skip high-priority if liquidity-constrained)
- Matches real-world bank behavior

### Component 4: T2 Priority Mode for Queue 2

Add optional T2-style priority processing at RTGS level:

```yaml
rtgs_config:
  priority_mode: true  # Default: false (current behavior)
```

When enabled:
- Queue 2 processes urgent (8-10) before normal (4-7) before low (0-3)
- Within each band, FIFO ordering preserved
- LSM considers priority in cycle selection

**Implementation:**
```rust
fn process_queue2(&mut self) {
    if self.config.priority_mode {
        // Process in priority bands
        self.process_priority_band(8..=10);  // Urgent
        self.process_priority_band(4..=7);   // Normal
        self.process_priority_band(0..=3);   // Low
    } else {
        // Current FIFO behavior
        self.process_fifo();
    }
}
```

### Component 5: Dynamic Priority Escalation

Enhance the policy system to support automatic priority escalation:

**New policy action:**
```json
{
  "type": "action",
  "action": "Reprioritize",
  "parameters": {
    "new_priority": {
      "compute": {
        "op": "min",
        "left": { "value": 10 },
        "right": {
          "op": "+",
          "left": { "field": "priority" },
          "right": {
            "compute": {
              "op": "/",
              "left": { "value": 5 },
              "right": { "field": "ticks_to_deadline" }
            }
          }
        }
      }
    }
  }
}
```

**Or a built-in escalation curve:**
```yaml
priority_escalation:
  enabled: true
  curve: "linear"  # or "exponential"
  start_escalating_at_ticks: 20
  max_boost: 3
```

This automatically increases priority as deadline approaches:
- 20 ticks remaining: +0 boost
- 10 ticks remaining: +1.5 boost
- 5 ticks remaining: +2.25 boost
- 1 tick remaining: +3 boost (capped)

### Component 6: Priority in Metrics & Analysis

Track priority-related metrics:

```python
@dataclass
class PriorityMetrics:
    settlements_by_priority: Dict[int, int]      # Count per priority level
    avg_delay_by_priority: Dict[int, float]      # Ticks in queue by priority
    priority_violations: int                      # Low-priority settled before high
    escalations_count: int                        # How often priority was boosted
```

Add to verbose output:
```
[Tick 50] Settlement: TX-123 (priority=9, waited=2 ticks) ✓
[Tick 50] Settlement: TX-456 (priority=3, waited=15 ticks) ✓
[Tick 50] Priority violation: TX-789 (p=3) settled before TX-790 (p=7)
```

---

## Implementation Phases

### Phase 1: Priority Distributions (Foundation)
**Effort: Small | Impact: High | Breaking: No**

1. Add `priority_distribution` to arrival config schema
2. Modify Rust arrival generation to sample from distribution
3. Default: single-value distribution (backward compatible)
4. Update example configs to demonstrate variation

**Files:**
- `api/payment_simulator/config/schemas.py` — Add distribution schema
- `backend/src/arrivals/mod.rs` — Sample priority from distribution
- `backend/src/models/config.rs` — Add distribution config

### Phase 2: Queue 1 Priority Ordering
**Effort: Medium | Impact: High | Breaking: Config flag**

1. Replace `Vec<String>` with priority-aware data structure
2. Add `queue1_ordering` config option
3. Default to FIFO for backward compatibility
4. Update queue iteration in policy evaluation

**Files:**
- `backend/src/models/agent.rs` — New queue data structure
- `backend/src/orchestrator/mod.rs` — Queue management
- `backend/src/core/config.rs` — New config field

### Phase 3: Payment Types (Optional Enhancement)
**Effort: Medium | Impact: Medium | Breaking: No**

1. Define payment type enum and characteristics
2. Add payment type to transaction model
3. Allow per-agent payment type mix configuration
4. Generate transactions with type-appropriate attributes

**Files:**
- `backend/src/models/payment_type.rs` — New module
- `backend/src/models/transaction.rs` — Add type field
- `backend/src/arrivals/mod.rs` — Type-based generation

### Phase 4: T2 Priority Mode for Queue 2
**Effort: Medium | Impact: Medium | Breaking: Config flag**

1. Add priority_mode to RTGS config
2. Implement priority-band processing
3. Update LSM to consider priority in cycle selection
4. Add priority-related events

**Files:**
- `backend/src/settlement/rtgs.rs` — Priority processing
- `backend/src/settlement/lsm.rs` — Priority-aware cycles
- `backend/src/core/config.rs` — New config

### Phase 5: Dynamic Escalation
**Effort: Small | Impact: Medium | Breaking: No**

1. Enhance Reprioritize action with computed values
2. Add optional auto-escalation config
3. Track escalation in events

**Files:**
- `backend/src/policy/actions.rs` — Enhanced reprioritize
- `backend/src/models/config.rs` — Escalation config

### Phase 6: Metrics & Analysis
**Effort: Small | Impact: Low | Breaking: No**

1. Add priority metrics to simulation results
2. Include priority in verbose output
3. Track priority violations

**Files:**
- `backend/src/metrics/mod.rs` — Priority metrics
- `api/payment_simulator/cli/display/` — Output updates

---

## Configuration Examples

### Minimal (Backward Compatible)
```yaml
# Current configs continue to work unchanged
agents:
  - id: "BANK_A"
    arrival_config:
      priority: 5  # Single value = all txns get priority 5
```

### Simple Distribution
```yaml
agents:
  - id: "BANK_A"
    arrival_config:
      priority_distribution:
        type: "Categorical"
        values: [3, 5, 7, 9]
        weights: [0.25, 0.50, 0.15, 0.10]
```

### Full Payment Types
```yaml
agents:
  - id: "BANK_A"
    arrival_config:
      payment_types:
        SECURITIES_SETTLEMENT: 0.05
        PAYROLL: 0.10
        INTERBANK: 0.60
        DISCRETIONARY: 0.25

payment_type_definitions:
  SECURITIES_SETTLEMENT:
    priority: 9
    deadline_range: [10, 30]
    amount_multiplier: 2.0
```

### With Queue Priority + T2 Mode
```yaml
queue_config:
  queue1_ordering: "priority_deadline"

rtgs_config:
  priority_mode: true
```

---

## Success Criteria

1. **Heterogeneous priorities**: Transactions from the same agent have varying priorities
2. **Meaningful ordering**: High-priority payments settle before low-priority (when liquidity allows)
3. **Policy relevance**: Priority becomes a useful decision variable in policies
4. **Realistic scenarios**: Can model T2-style priority handling
5. **Backward compatible**: Existing configs work unchanged
6. **Observable**: Priority effects visible in metrics and verbose output

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing configs | Default to current behavior; new features are opt-in |
| Performance impact of sorted queue | Use efficient data structure; benchmark before/after |
| Complexity for users | Provide sensible defaults; document clearly |
| Priority starvation (low-priority never settles) | Escalation mechanism + deadline penalties handle this |

---

## Questions for Stakeholder Review

1. **Phase 1 vs Phase 3**: Should we start with simple distributions or full payment types?
   - Distributions = faster to implement, sufficient for most scenarios
   - Payment types = richer modeling, more configuration complexity

2. **Queue 1 default**: Should new configs default to `priority_deadline` ordering?
   - Pro: More realistic behavior out-of-box
   - Con: Changes behavior from current FIFO

3. **T2 Priority Mode**: How closely should we model T2's actual priority rules?
   - T2 has complex rules around urgent payments and LSM bypass
   - Could implement simplified version first

4. **Escalation**: Automatic escalation or policy-only?
   - Automatic = simpler for users, more "game-like"
   - Policy-only = more control, matches agent decision-making model

---

## References

- [ECB TARGET2 User Detailed Functional Specifications](https://www.ecb.europa.eu/paym/target/target2/profuse/html/index.en.html)
- [T2 Priority and Timed Transactions](docs/game_concept_doc.md:87)
- Current implementation: `backend/src/models/transaction.rs:104-106`
- Policy variables: `docs/policy_overview.md:40`

---

## Implementation Status

### Phase 1: Priority Distributions ✅ COMPLETE

**Implemented 2024-11-21**

- Added `PriorityDistribution` types to Python schema (Fixed, Categorical, Uniform)
- Added `priority_distribution` field to `ArrivalConfig` (backward compatible)
- Implemented Rust `PriorityDistribution` enum with sampling logic
- Updated FFI parsing to handle new format
- **Tests**: 12 unit tests + 7 integration tests (all passing)
- **Files changed**:
  - `api/payment_simulator/config/schemas.py`
  - `backend/src/arrivals/mod.rs`
  - `backend/src/ffi/types.rs`
  - All Rust test files updated

### Phase 2: Queue 1 Priority Ordering 🔄 IN PROGRESS

**TDD Tests Written 2024-11-21**

- 8 integration tests written (`api/tests/integration/test_queue1_priority_ordering.py`)
- Tests verify:
  - Default FIFO behavior preserved
  - `queue1_ordering: "priority_deadline"` config accepted
  - Priority sorting (high priority first)
  - Deadline tiebreaker (soonest deadline first within same priority)
  - Policy evaluation respects queue order

**Next Steps**:
1. Add `queue1_ordering` to `OrchestratorConfig` (Rust)
2. Parse in FFI (`backend/src/ffi/types.rs`)
3. Modify queue iteration to sort when `priority_deadline` enabled

### Phase 3-6: Pending

Payment Types, T2 Priority Mode, Dynamic Escalation, and Metrics not yet started.
