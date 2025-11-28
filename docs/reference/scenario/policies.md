# Policy Configuration

Policies control **how agents decide when and how to release payments**. Each agent must have exactly one policy that determines its behavior.

---

## Policy Types Overview

| Type | Description | Use Case |
|:-----|:------------|:---------|
| `Fifo` | Submit all transactions immediately | Baseline, passive agents |
| `Deadline` | Submit when deadline approaches | Simple urgency-based |
| `LiquidityAware` | Maintain target balance buffer | Conservative liquidity management |
| `LiquiditySplitting` | Split large payments | High-value transaction handling |
| `MockSplitting` | Deterministic splits for testing | Unit tests |
| `FromJson` | JSON DSL decision tree | Advanced, customizable strategies |

---

## Policy Schema (Union Type)

```yaml
policy:
  type: <PolicyType>
  # Additional fields depend on type
```

The `type` field determines which policy is used and what additional parameters are required.

---

## `Fifo` Policy

**Type**: `Fifo`
**Parameters**: None
**Behavior**: Submit all transactions to Queue 2 immediately when evaluated.

### Schema

```yaml
policy:
  type: Fifo
```

### Implementation Details

**Python Schema** (`schemas.py:395-397`):
```python
class FifoPolicy(BaseModel):
    type: Literal["Fifo"]
```

**Rust** (`engine.rs:345-350`):
```rust
pub enum PolicyConfig {
    Fifo,
    // ...
}
```

### Behavior

1. Agent evaluates Queue 1 (internal queue)
2. All transactions are immediately submitted to Queue 2 (RTGS)
3. No holding, no splitting, no cost optimization

### Use Cases

- Baseline comparison
- Passive counterparty agents
- BIS model replication
- Testing LSM without policy interference

### Example

```yaml
agents:
  - id: COUNTERPARTY
    opening_balance: 10000000
    policy:
      type: Fifo
```

---

## `Deadline` Policy

**Type**: `Deadline`
**Parameters**: `urgency_threshold`
**Behavior**: Hold transactions until deadline approaches, then submit.

### Schema

```yaml
policy:
  type: Deadline
  urgency_threshold: <int>    # Required, ticks > 0
```

### Fields

#### `urgency_threshold`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`

Number of ticks before deadline when transaction becomes "urgent" and is released.

### Implementation Details

**Python Schema** (`schemas.py:400-403`):
```python
class DeadlinePolicy(BaseModel):
    type: Literal["Deadline"]
    urgency_threshold: int = Field(..., gt=0)
```

**Rust** (`engine.rs:352-356`):
```rust
Deadline { urgency_threshold: usize },
```

### Behavior

1. Calculate `ticks_to_deadline = deadline_tick - current_tick`
2. If `ticks_to_deadline <= urgency_threshold`: Release
3. Otherwise: Hold

### Use Cases

- Delay-minimizing strategies
- When agents want to wait for incoming payments
- Testing deadline-based behavior

### Example

```yaml
agents:
  - id: PATIENT_BANK
    policy:
      type: Deadline
      urgency_threshold: 15    # Release when <= 15 ticks to deadline
```

---

## `LiquidityAware` Policy

**Type**: `LiquidityAware`
**Parameters**: `target_buffer`, `urgency_threshold`
**Behavior**: Maintain minimum balance buffer, override when urgent.

### Schema

```yaml
policy:
  type: LiquidityAware
  target_buffer: <int>        # Required, cents >= 0
  urgency_threshold: <int>    # Required, ticks > 0
```

### Fields

#### `target_buffer`

**Type**: `int` (cents)
**Required**: Yes
**Constraint**: `>= 0`

Minimum balance to maintain after releasing a transaction.

#### `urgency_threshold`

**Type**: `int`
**Required**: Yes
**Constraint**: `> 0`

Ticks to deadline that overrides buffer requirement.

### Implementation Details

**Python Schema** (`schemas.py:406-410`):
```python
class LiquidityAwarePolicy(BaseModel):
    type: Literal["LiquidityAware"]
    target_buffer: int = Field(..., ge=0)
    urgency_threshold: int = Field(..., gt=0)
```

**Rust** (`engine.rs:358-363`):
```rust
LiquidityAware {
    target_buffer: i64,
    urgency_threshold: usize,
},
```

### Behavior

1. If `ticks_to_deadline <= urgency_threshold`: Release (urgent override)
2. If `balance - amount >= target_buffer`: Release (buffer maintained)
3. Otherwise: Hold

### Use Cases

- Conservative liquidity management
- Risk-averse agents
- Maintaining operational buffers

### Example

```yaml
agents:
  - id: CONSERVATIVE_BANK
    opening_balance: 10000000    # $100,000
    policy:
      type: LiquidityAware
      target_buffer: 500000      # Maintain $5,000 buffer
      urgency_threshold: 10      # Override buffer if <= 10 ticks to deadline
```

---

## `LiquiditySplitting` Policy

**Type**: `LiquiditySplitting`
**Parameters**: `max_splits`, `min_split_amount`
**Behavior**: Split large transactions that exceed available liquidity.

### Schema

```yaml
policy:
  type: LiquiditySplitting
  max_splits: <int>           # Required, 2-10
  min_split_amount: <int>     # Required, cents > 0
```

### Fields

#### `max_splits`

**Type**: `int`
**Required**: Yes
**Constraint**: `2 <= value <= 10`

Maximum number of parts to split a transaction into.

#### `min_split_amount`

**Type**: `int` (cents)
**Required**: Yes
**Constraint**: `> 0`

Minimum size for each split part.

### Implementation Details

**Python Schema** (`schemas.py:413-417`):
```python
class LiquiditySplittingPolicy(BaseModel):
    type: Literal["LiquiditySplitting"]
    max_splits: int = Field(..., ge=2, le=10)
    min_split_amount: int = Field(..., gt=0)
```

**Rust** (`engine.rs:365-370`):
```rust
LiquiditySplitting {
    max_splits: usize,
    min_split_amount: i64,
},
```

### Behavior

1. Check if transaction is divisible (`divisible: true` in arrival config)
2. If not divisible: Release or Hold based on liquidity
3. If divisible and `amount > available_liquidity`:
   - Calculate optimal split count (respecting `max_splits` and `min_split_amount`)
   - Create child transactions
   - Submit children that can be afforded

### Use Cases

- High-value transaction handling
- Gradual settlement of large payments
- Improving LSM matching opportunities

### Example

```yaml
agents:
  - id: LARGE_VALUE_BANK
    policy:
      type: LiquiditySplitting
      max_splits: 4              # Split into max 4 parts
      min_split_amount: 50000    # Each part at least $500
    arrival_config:
      divisible: true            # Transactions can be split
```

---

## `MockSplitting` Policy

**Type**: `MockSplitting`
**Parameters**: `num_splits`
**Behavior**: Always split transactions into exactly N parts (for testing).

### Schema

```yaml
policy:
  type: MockSplitting
  num_splits: <int>           # Required, 2-10
```

### Fields

#### `num_splits`

**Type**: `int`
**Required**: Yes
**Constraint**: `2 <= value <= 10`

Exact number of parts to split into.

### Implementation Details

**Python Schema** (`schemas.py:420-423`):
```python
class MockSplittingPolicy(BaseModel):
    type: Literal["MockSplitting"]
    num_splits: int = Field(..., ge=2, le=10)
```

**Rust** (`engine.rs:372-376`):
```rust
MockSplitting { num_splits: usize },
```

### Behavior

1. All divisible transactions are split into exactly `num_splits` parts
2. Non-divisible transactions are released immediately
3. No liquidity checking

### Use Cases

- Unit testing split mechanics
- Deterministic splitting for replay verification
- Testing LSM cycle behavior with splits

### Example

```yaml
agents:
  - id: TEST_SPLITTER
    policy:
      type: MockSplitting
      num_splits: 3              # Always split into 3 parts
```

---

## `FromJson` Policy

**Type**: `FromJson`
**Parameters**: `json_path`
**Behavior**: Load and execute a JSON DSL decision tree.

### Schema

```yaml
policy:
  type: FromJson
  json_path: <string>         # Required, path to JSON file
```

### Fields

#### `json_path`

**Type**: `str`
**Required**: Yes
**Constraint**: Valid file path

Path to JSON policy file, relative to `backend/policies/` or absolute.

### Implementation Details

**Python Schema** (`schemas.py:426-429`):
```python
class FromJsonPolicy(BaseModel):
    type: Literal["FromJson"]
    json_path: str
```

**Rust** (`engine.rs:378-382`):
```rust
FromJson { json: String },
```

### Behavior

1. JSON file is loaded and parsed at simulation start
2. Policy tree is evaluated for each transaction in Queue 1
3. Supports:
   - `payment_tree`: Per-transaction decisions
   - `bank_tree`: Per-tick agent-level decisions
   - `strategic_collateral_tree`: Pre-settlement collateral management
   - `end_of_tick_collateral_tree`: Post-settlement collateral management

### JSON Policy Structure

See [docs/policy_dsl_guide.md](../../policy_dsl_guide.md) for complete DSL reference.

```json
{
  "version": "1.0",
  "policy_id": "my_policy",
  "description": "Example policy",
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "root",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "release",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "hold",
      "action": "Hold"
    }
  }
}
```

### Parameter Overrides

Policy parameters can be overridden per-agent:

```yaml
agents:
  - id: AGGRESSIVE_BANK
    policy:
      type: FromJson
      json_path: "backend/policies/liquidity_aware.json"
      params:                    # Override JSON defaults
        urgency_threshold: 3.0   # More aggressive than default
        target_buffer: 50000.0   # Smaller buffer
```

### Available Decision Trees

| Tree | When Evaluated | Purpose |
|:-----|:---------------|:--------|
| `payment_tree` | Per transaction in Queue 1 | Release/Hold/Split decisions |
| `bank_tree` | Once per agent per tick | Set release budgets, state registers |
| `strategic_collateral_tree` | Before settlements | Proactive collateral posting |
| `end_of_tick_collateral_tree` | After settlements | Reactive collateral withdrawal |

### Use Cases

- Advanced strategy implementation
- Cost-aware optimization
- Time-based strategies
- State-dependent behavior
- Collateral management

### Example

```yaml
agents:
  - id: SOPHISTICATED_BANK
    policy:
      type: FromJson
      json_path: "backend/policies/adaptive_liquidity_manager.json"
      params:
        urgency_threshold: 5.0
        target_buffer: 200000.0
        collateral_safety_margin: 1.2
```

---

## Additional Rust-Only Policies

These policies exist in Rust but are not exposed via YAML configuration:

### `MockStaggerSplit`

**For testing only**. Splits transactions with staggered release timing.

```rust
MockStaggerSplit {
    num_splits: usize,
    stagger_first_now: bool,
    stagger_gap_ticks: usize,
    priority_boost_children: u8,
}
```

---

## Policy Selection Guide

| Scenario | Recommended Policy |
|:---------|:-------------------|
| Passive counterparty | `Fifo` |
| Simple urgency-based | `Deadline` |
| Conservative bank | `LiquidityAware` |
| High-value payments | `LiquiditySplitting` |
| Complex strategies | `FromJson` |
| Testing | `MockSplitting` |

---

## Implementation Location

| Component | File | Lines |
|:----------|:-----|:------|
| Python Policies | `api/payment_simulator/config/schemas.py` | 395-440 |
| Rust PolicyConfig | `backend/src/orchestrator/engine.rs` | 345-416 |
| FFI Parsing | `backend/src/ffi/types.rs` | 350-399 |
| JSON DSL Types | `backend/src/policy/tree/types.rs` | - |
| JSON Executor | `backend/src/policy/tree/executor.rs` | - |

---

## Navigation

**Previous**: [Agents](agents.md)
**Next**: [Arrivals](arrivals.md)
