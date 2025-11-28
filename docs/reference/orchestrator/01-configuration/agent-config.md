# AgentConfig

**Location:** `backend/src/orchestrator/engine.rs:244-321`

Configuration for a single agent (bank) in the simulation. Defines initial state, cash manager policy, transaction generation patterns, collateral, and payment limits.

---

## Struct Definition

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AgentConfig {
    pub id: String,
    pub opening_balance: i64,
    pub unsecured_cap: i64,
    pub policy: PolicyConfig,
    pub arrival_config: Option<ArrivalConfig>,
    pub arrival_bands: Option<ArrivalBandsConfig>,
    pub posted_collateral: Option<i64>,
    pub collateral_haircut: Option<f64>,
    pub limits: Option<AgentLimitsConfig>,
    pub liquidity_pool: Option<i64>,
    pub liquidity_allocation_fraction: Option<f64>,
}
```

---

## Fields

### `id`

**Type:** `String`
**Required:** Yes
**Location:** `engine.rs:246`

Unique identifier for the agent.

**Description:**
Must be unique across all agents. Used as reference in counterparty weights, transaction sender/receiver IDs, and event logging.

**Constraints:**
- Must be non-empty
- Must be unique within configuration
- Typically uppercase (e.g., "BANK_A", "BANK_B")

**Example:**
```yaml
id: "BANK_A"
```

**Validation (Python):**
```python
@field_validator("id")
def validate_id(cls, v):
    if not v or not v.strip():
        raise ValueError("Agent ID cannot be empty")
    return v.strip()
```

---

### `opening_balance`

**Type:** `i64` (cents)
**Required:** Yes
**Location:** `engine.rs:249`

Initial balance in the central bank settlement account.

**Description:**
Starting reserves in cents/minor currency units. This is the agent's available liquidity at simulation start (before any liquidity pool allocation).

**CRITICAL:** Must be integer (cents), never float.

**Example Values:**
- `1_000_000` = $10,000.00
- `10_000_000` = $100,000.00
- `100_000_000` = $1,000,000.00

**Usage:**
```yaml
opening_balance: 1000000  # $10,000.00
```

**Related:**
- Combined with `liquidity_pool × liquidity_allocation_fraction` for final starting balance
- See [Agent Model](../02-models/agent.md) for balance management

---

### `unsecured_cap`

**Type:** `i64` (cents)
**Required:** Yes
**Location:** `engine.rs:251-255`

Maximum unsecured daylight overdraft capacity.

**Description:**
Intraday credit limit that does not require collateral. Allows agents to process payments even when temporarily below zero balance.

**Example:**
- `500_000` = $5,000 unsecured overdraft capacity
- `0` = No unsecured overdraft (must have collateral or positive balance)

**Usage:**
```yaml
unsecured_cap: 500000  # $5,000.00
```

**Credit Capacity Calculation:**
```rust
available_liquidity = balance + unsecured_cap + collateral_capacity()
```

**Related:**
- Overdraft costs apply when `balance < 0`
- See [Cost Calculations](../06-costs/cost-calculations.md)

---

### `policy`

**Type:** `PolicyConfig`
**Required:** Yes
**Location:** `engine.rs:258`

Cash manager policy for Queue 1 decisions.

**Description:**
Determines how the agent decides which transactions to release from Queue 1 to Queue 2 (RTGS).

**Available Policies:**

| Policy | Parameters | Description |
|--------|------------|-------------|
| `Fifo` | None | Submit all immediately |
| `Deadline` | `urgency_threshold` | Prioritize urgent transactions |
| `LiquidityAware` | `target_buffer`, `urgency_threshold` | Preserve liquidity buffer |
| `LiquiditySplitting` | `max_splits`, `min_split_amount` | Smart payment splitting |
| `MockSplitting` | `num_splits` | Testing: always split |
| `MockStaggerSplit` | Multiple | Testing: staggered release |
| `FromJson` | `json` | Custom JSON policy |

**Example:**
```yaml
policy:
  type: Deadline
  urgency_threshold: 5
```

**Related:**
- See [Policy Overview](../08-policies/policy-overview.md)
- See [PolicyConfig enum](#policyconfig-enum)

---

### `arrival_config`

**Type:** `Option<ArrivalConfig>`
**Default:** `None`
**Location:** `engine.rs:261`

Configuration for automatic transaction generation.

**Description:**
When present, the agent automatically generates outgoing transactions each tick based on Poisson arrival process with configurable amount distribution, counterparty weights, and deadline ranges.

**Mutual Exclusion:** Cannot be used together with `arrival_bands`.

**Example:**
```yaml
arrival_config:
  rate_per_tick: 5.0
  amount_distribution:
    type: Normal
    mean: 100000
    std_dev: 30000
  counterparty_weights:
    BANK_B: 0.5
    BANK_C: 0.5
  deadline_range: [5, 20]
  priority: 5
  divisible: false
```

**Related:**
- See [ArrivalConfig](arrival-config.md) for full details
- See [Arrival Generator](../03-generators/arrival-generator.md)

---

### `arrival_bands`

**Type:** `Option<ArrivalBandsConfig>`
**Default:** `None`
**Location:** `engine.rs:263-283`

Per-priority-band arrival configuration (Enhancement 11.3).

**Description:**
Alternative to `arrival_config` that allows different arrival characteristics per priority band:
- **Urgent (8-10):** Large, infrequent, tight deadlines
- **Normal (4-7):** Medium, standard frequency
- **Low (0-3):** Small, frequent, relaxed deadlines

**Mutual Exclusion:** Cannot be used together with `arrival_config`.

**Example:**
```yaml
arrival_bands:
  urgent:
    rate_per_tick: 0.1
    amount_distribution:
      type: LogNormal
      mean: 14.0
      std_dev: 0.5
    deadline_offset_min: 5
    deadline_offset_max: 15
  normal:
    rate_per_tick: 3.0
    amount_distribution:
      type: LogNormal
      mean: 11.0
      std_dev: 0.8
    deadline_offset_min: 20
    deadline_offset_max: 50
  low:
    rate_per_tick: 5.0
    amount_distribution:
      type: Normal
      mean: 50000
      std_dev: 15000
    deadline_offset_min: 40
    deadline_offset_max: 80
```

**Related:**
- See [ArrivalConfig](arrival-config.md#arrivalbandsconfig) for full details
- Models BIS payment heterogeneity

---

### `posted_collateral`

**Type:** `Option<i64>` (cents)
**Default:** `0`
**Location:** `engine.rs:285-287`

Initial collateral posted by the agent (Phase 8).

**Description:**
Collateral (securities, bonds) deposited with central bank that provides additional credit capacity. Subject to haircut.

**Example:**
```yaml
posted_collateral: 2000000  # $20,000.00
```

**Credit Capacity from Collateral:**
```rust
collateral_capacity = posted_collateral × (1 - collateral_haircut)
```

**Example with 2% haircut:**
- Posted: $20,000
- Capacity: $20,000 × 0.98 = $19,600

**Related:**
- See `collateral_haircut` field
- See [Collateral Events](../07-events/collateral-events.md)

---

### `collateral_haircut`

**Type:** `Option<f64>`
**Default:** `0.02` (2%)
**Location:** `engine.rs:289-293`

Discount rate applied to collateral value.

**Description:**
Represents the central bank's risk adjustment on accepted collateral. Higher quality collateral has lower haircut.

**Valid Values:** `0.0` to `1.0`

**Typical Values (T2/CLM range: 0%-10%):**
- `0.00` = No haircut (high quality government bonds)
- `0.02` = 2% haircut (default)
- `0.10` = 10% haircut (lower quality securities)

**Example:**
```yaml
collateral_haircut: 0.02  # 2%
```

**Calculation:**
```rust
effective_collateral = posted_collateral × (1.0 - haircut)
```

---

### `limits`

**Type:** `Option<AgentLimitsConfig>`
**Default:** `None`
**Location:** `engine.rs:295-298`

Bilateral and multilateral payment outflow limits.

**Description:**
TARGET2-style limits that restrict payment outflows:
- **Bilateral limits:** Maximum outflow to each specific counterparty per day
- **Multilateral limit:** Maximum total outflow to all participants per day

**Example:**
```yaml
limits:
  bilateral_limits:
    BANK_B: 5000000
    BANK_C: 3000000
  multilateral_limit: 10000000
```

**Behavior:**
- When limit exceeded, `BilateralLimitExceeded` or `MultilateralLimitExceeded` event emitted
- Transaction may be held in queue until limit resets (daily)

**Related:**
- See [AgentLimitsConfig](#agentlimitsconfig)
- See [Limit Events](../07-events/system-events.md#limits)

---

### `liquidity_pool`

**Type:** `Option<i64>` (cents)
**Default:** `None`
**Location:** `engine.rs:300-309`

External liquidity pool available for allocation (Enhancement 11.2).

**Description:**
Models the BIS Period 0 decision where agents choose how much external liquidity to bring into the settlement system. This is additive with `opening_balance`.

**Example:**
```yaml
liquidity_pool: 2000000  # $20,000.00 available externally
```

**Final Starting Balance:**
```
starting_balance = opening_balance + floor(liquidity_pool × allocation_fraction)
```

**Use Case:**
- BIS delay-liquidity tradeoff analysis
- Agents decide how much liquidity to commit vs. keep externally

**Related:**
- See `liquidity_allocation_fraction` field
- See [Priority Multipliers](../06-costs/priority-multipliers.md)

---

### `liquidity_allocation_fraction`

**Type:** `Option<f64>`
**Default:** `1.0` (100%)
**Location:** `engine.rs:311-320`

Fraction of `liquidity_pool` to actually allocate (0.0 to 1.0).

**Description:**
Determines how much of available external liquidity is brought into settlement. Allows modeling partial liquidity commitment.

**Valid Values:** `0.0` to `1.0`

**Example:**
```yaml
liquidity_pool: 1000000
liquidity_allocation_fraction: 0.5  # Allocate $5,000.00
```

**Calculation:**
```rust
allocated = floor(liquidity_pool × liquidity_allocation_fraction)
starting_balance = opening_balance + allocated
```

**Related:**
- Allocated liquidity incurs opportunity cost (`liquidity_cost_per_tick_bps`)
- See [Cost Rates](cost-rates.md#liquidity_cost_per_tick_bps)

---

## Related Types

### `AgentLimitsConfig`

**Location:** `engine.rs:323-339`

```rust
#[derive(Debug, Clone, Default)]
pub struct AgentLimitsConfig {
    /// Per-counterparty limits (counterparty_id -> max_outflow in cents)
    pub bilateral_limits: HashMap<String, i64>,

    /// Maximum total outflow per day (cents)
    pub multilateral_limit: Option<i64>,
}
```

**Example:**
```yaml
limits:
  bilateral_limits:
    BANK_B: 5000000   # Max $50k/day to BANK_B
    BANK_C: 3000000   # Max $30k/day to BANK_C
  multilateral_limit: 10000000  # Max $100k/day total
```

**Behavior:**
- Limits reset at start of each day
- Outflow tracking: `bilateral_outflows` and `total_outflow` fields in Agent

---

### `PolicyConfig` Enum

**Location:** `engine.rs:344-416`

```rust
pub enum PolicyConfig {
    /// Submit all immediately
    Fifo,

    /// Prioritize urgent transactions
    Deadline {
        urgency_threshold: usize,  // Ticks before deadline
    },

    /// Preserve liquidity buffer
    LiquidityAware {
        target_buffer: i64,        // Minimum balance to maintain (cents)
        urgency_threshold: usize,  // Override buffer when urgent
    },

    /// Smart payment splitting
    LiquiditySplitting {
        max_splits: usize,         // Maximum splits per transaction
        min_split_amount: i64,     // Minimum amount per split (cents)
    },

    /// Testing: always split
    MockSplitting {
        num_splits: usize,
    },

    /// Testing: staggered release
    MockStaggerSplit {
        num_splits: usize,
        stagger_first_now: usize,
        stagger_gap_ticks: usize,
        priority_boost_children: u8,
    },

    /// Custom JSON policy
    FromJson {
        json: String,
    },
}
```

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class AgentConfig(BaseModel):
    id: str
    opening_balance: int          # Cents (i64)
    unsecured_cap: int            # Cents (i64)
    policy: PolicyConfig
    arrival_config: Optional[ArrivalConfig] = None
    arrival_bands: Optional[ArrivalBandsConfig] = None
    posted_collateral: Optional[int] = None
    collateral_haircut: Optional[float] = None
    limits: Optional[Dict] = None
    liquidity_pool: Optional[int] = None
    liquidity_allocation_fraction: Optional[float] = None

    @model_validator(mode="after")
    def check_arrival_exclusivity(self):
        if self.arrival_config and self.arrival_bands:
            raise ValueError(
                "Cannot specify both arrival_config and arrival_bands"
            )
        return self
```

---

## Example Configurations

### Basic Agent (FIFO Policy)

```yaml
- id: "BANK_A"
  opening_balance: 1000000
  unsecured_cap: 500000
  policy:
    type: Fifo
  arrival_config:
    rate_per_tick: 5.0
    amount_distribution:
      type: Normal
      mean: 100000
      std_dev: 30000
    counterparty_weights:
      BANK_B: 1.0
    deadline_range: [5, 20]
    priority: 5
    divisible: false
```

### Advanced Agent (With Collateral & Limits)

```yaml
- id: "BANK_A"
  opening_balance: 5000000
  unsecured_cap: 1000000
  policy:
    type: LiquidityAware
    target_buffer: 500000
    urgency_threshold: 5
  arrival_config:
    rate_per_tick: 10.0
    amount_distribution:
      type: LogNormal
      mean: 11.5
      std_dev: 0.8
    counterparty_weights:
      BANK_B: 0.4
      BANK_C: 0.3
      BANK_D: 0.3
    deadline_range: [10, 40]
    priority_distribution:
      type: Categorical
      values: [3, 5, 8]
      weights: [0.3, 0.5, 0.2]
    divisible: true
  posted_collateral: 2000000
  collateral_haircut: 0.02
  limits:
    bilateral_limits:
      BANK_B: 5000000
      BANK_C: 3000000
    multilateral_limit: 10000000
  liquidity_pool: 2000000
  liquidity_allocation_fraction: 0.5
```

### BIS Model Agent (Per-Band Arrivals)

```yaml
- id: "BANK_A"
  opening_balance: 10000000
  unsecured_cap: 2000000
  policy:
    type: LiquiditySplitting
    max_splits: 3
    min_split_amount: 100000
  arrival_bands:
    urgent:
      rate_per_tick: 0.1
      amount_distribution:
        type: LogNormal
        mean: 14.0
        std_dev: 0.5
      deadline_offset_min: 5
      deadline_offset_max: 15
      counterparty_weights:
        BANK_B: 0.5
        BANK_C: 0.5
      divisible: false
    normal:
      rate_per_tick: 3.0
      amount_distribution:
        type: LogNormal
        mean: 11.0
        std_dev: 0.8
      deadline_offset_min: 20
      deadline_offset_max: 50
      divisible: true
    low:
      rate_per_tick: 5.0
      amount_distribution:
        type: Normal
        mean: 50000
        std_dev: 15000
      deadline_offset_min: 40
      deadline_offset_max: 80
      divisible: true
  liquidity_pool: 5000000
  liquidity_allocation_fraction: 0.7
```

---

## Validation Rules

### Python Validation (Pydantic)

1. **ID must be non-empty**
2. **Unique IDs** across all agents
3. **arrival_config and arrival_bands are mutually exclusive**
4. **Counterparty references must be valid agent IDs**
5. **Limits counterparty references must be valid**

### Rust Validation

1. **At least one agent required**
2. **IDs must be unique**
3. **Counterparty weights must reference existing agents**

---

## See Also

- [ArrivalConfig](arrival-config.md) - Transaction generation patterns
- [Policy Overview](../08-policies/policy-overview.md) - Cash manager policies
- [Agent Model](../02-models/agent.md) - Runtime agent state
- [OrchestratorConfig](orchestrator-config.md) - Top-level configuration

---

*Last Updated: 2025-11-28*
