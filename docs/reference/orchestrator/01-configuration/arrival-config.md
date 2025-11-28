# ArrivalConfig

**Location:** `backend/src/arrivals/mod.rs`

Configuration for automatic transaction generation. Defines how agents generate outgoing payments based on Poisson arrival processes with configurable amounts, counterparties, deadlines, and priorities.

---

## Legacy ArrivalConfig

**Location:** `arrivals/mod.rs:62-82`

Standard per-agent arrival configuration used when all transactions should follow the same pattern regardless of priority.

### Struct Definition

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ArrivalConfig {
    pub rate_per_tick: f64,
    pub amount_distribution: AmountDistribution,
    pub counterparty_weights: HashMap<String, f64>,
    pub deadline_range: (usize, usize),
    pub priority_distribution: PriorityDistribution,
    pub divisible: bool,
}
```

### Fields

#### `rate_per_tick`

**Type:** `f64`
**Required:** Yes

Expected number of arrivals per tick (Poisson λ parameter).

**Description:**
Each tick, the number of generated transactions is sampled from a Poisson distribution with this mean. Higher values mean more transactions.

**Example Values:**
- `0.5` = Average 0.5 transactions/tick (1 every 2 ticks)
- `5.0` = Average 5 transactions/tick
- `10.0` = Average 10 transactions/tick (high volume)

**Example:**
```yaml
arrival_config:
  rate_per_tick: 5.0
```

---

#### `amount_distribution`

**Type:** `AmountDistribution`
**Required:** Yes

Distribution for sampling transaction amounts.

**Variants:**
| Type | Parameters | Use Case |
|------|------------|----------|
| `Uniform` | `min`, `max` | Equal probability range |
| `Normal` | `mean`, `std_dev` | Bell curve around mean |
| `LogNormal` | `mean`, `std_dev` | Heavy-tailed (realistic) |
| `Exponential` | `rate` | Exponential decay |

**Example:**
```yaml
amount_distribution:
  type: Normal
  mean: 100000    # $1,000.00 mean
  std_dev: 30000  # $300.00 std dev
```

**Related:**
- See [Amount Distributions](../03-generators/amount-distributions.md)

---

#### `counterparty_weights`

**Type:** `HashMap<String, f64>`
**Required:** Yes (at least one entry)

Weighted probabilities for selecting receivers.

**Description:**
Each weight determines the relative probability of selecting that counterparty. Weights don't need to sum to 1.0 - they're normalized internally.

**Example:**
```yaml
counterparty_weights:
  BANK_B: 0.5   # 50% probability
  BANK_C: 0.3   # 30% probability
  BANK_D: 0.2   # 20% probability
```

**Selection Algorithm:**
1. Sum all weights
2. Generate random value in [0, total_weight)
3. Accumulate weights until random value exceeded
4. Select that counterparty

**Note:** The sender is automatically excluded from selection.

---

#### `deadline_range`

**Type:** `(usize, usize)` - (min_offset, max_offset)
**Required:** Yes

Range for deadline offset from arrival tick.

**Description:**
When a transaction arrives at tick T, its deadline is: `T + uniform(min_offset, max_offset)`.

**Constraints:**
- `min_offset > 0` (deadline must be after arrival)
- `max_offset >= min_offset`
- Deadline capped at `episode_end_tick` (Issue #6 fix)

**Example:**
```yaml
deadline_range: [5, 20]  # Deadline 5-20 ticks after arrival
```

**Example Timeline:**
- Arrival at tick 10
- Min offset 5, max offset 20
- Deadline: tick 15-30 (random within range)

---

#### `priority_distribution`

**Type:** `PriorityDistribution`
**Required:** Yes (legacy `priority` field also accepted)

Distribution for sampling transaction priority (0-10).

**Variants:**
| Type | Parameters | Description |
|------|------------|-------------|
| `Fixed` | `value` | All transactions same priority |
| `Categorical` | `values`, `weights` | Discrete distribution |
| `Uniform` | `min`, `max` | Random in range |

**Example (Fixed):**
```yaml
priority: 5  # Legacy format, single value
```

**Example (Categorical):**
```yaml
priority_distribution:
  type: Categorical
  values: [3, 5, 8]
  weights: [0.3, 0.5, 0.2]  # 30% low, 50% normal, 20% urgent
```

**Example (Uniform):**
```yaml
priority_distribution:
  type: Uniform
  min: 3
  max: 7
```

**Related:**
- See [Priority Distributions](../03-generators/priority-distributions.md)

---

#### `divisible`

**Type:** `bool`
**Default:** `false`

Whether generated transactions can be split.

**Description:**
When `true`, transactions may be split into smaller parts by policies like `LiquiditySplitting`. When `false`, transactions must settle atomically.

**Example:**
```yaml
arrival_config:
  divisible: true
```

---

## Per-Band Arrival Configuration (Enhancement 11.3)

**Location:** `arrivals/mod.rs:110-178`

Alternative to legacy `ArrivalConfig` that allows different arrival characteristics per priority band.

### ArrivalBandConfig

**Location:** `arrivals/mod.rs:110-130`

Configuration for a single priority band.

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ArrivalBandConfig {
    pub rate_per_tick: f64,
    pub amount_distribution: AmountDistribution,
    pub deadline_offset_min: usize,
    pub deadline_offset_max: usize,
    pub counterparty_weights: HashMap<String, f64>,
    pub divisible: bool,
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `rate_per_tick` | `f64` | Poisson λ for this band |
| `amount_distribution` | `AmountDistribution` | Amount sampling for band |
| `deadline_offset_min` | `usize` | Minimum deadline offset |
| `deadline_offset_max` | `usize` | Maximum deadline offset |
| `counterparty_weights` | `HashMap<String, f64>` | Optional per-band weights |
| `divisible` | `bool` | Can transactions be split |

**Priority Assignment:**
Priority is sampled uniformly within the band's range:
- Urgent: 8-10
- Normal: 4-7
- Low: 0-3

---

### ArrivalBandsConfig

**Location:** `arrivals/mod.rs:144-156`

Container for per-band configurations.

```rust
#[derive(Debug, Clone, Default, serde::Serialize, serde::Deserialize)]
pub struct ArrivalBandsConfig {
    pub urgent: Option<ArrivalBandConfig>,
    pub normal: Option<ArrivalBandConfig>,
    pub low: Option<ArrivalBandConfig>,
}
```

**Validation:** At least one band must be configured.

---

### PriorityBand Enum

**Location:** `arrivals/mod.rs:160-178`

```rust
pub enum PriorityBand {
    Urgent,  // Priority 8-10
    Normal,  // Priority 4-7
    Low,     // Priority 0-3
}

impl PriorityBand {
    pub fn priority_range(&self) -> (u8, u8) {
        match self {
            PriorityBand::Urgent => (8, 10),
            PriorityBand::Normal => (4, 7),
            PriorityBand::Low => (0, 3),
        }
    }
}
```

---

## Amount Distributions

**Location:** `arrivals/mod.rs:86-98`

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum AmountDistribution {
    Uniform { min: i64, max: i64 },
    Normal { mean: f64, std_dev: f64 },
    LogNormal { mean: f64, std_dev: f64 },
    Exponential { rate: f64 },
}
```

### Uniform

Equal probability across range.

**Parameters:**
- `min` - Minimum amount (cents)
- `max` - Maximum amount (cents)

**Sampling:** `amount = rng.range(min, max + 1)`

**Example:**
```yaml
amount_distribution:
  type: Uniform
  min: 50000   # $500
  max: 150000  # $1,500
```

---

### Normal

Gaussian (bell curve) distribution.

**Parameters:**
- `mean` - Center of distribution (cents)
- `std_dev` - Standard deviation (cents)

**Sampling:** Box-Muller transform, clipped to minimum 1 cent

**Example:**
```yaml
amount_distribution:
  type: Normal
  mean: 100000    # $1,000 mean
  std_dev: 30000  # $300 std dev
```

**Note:** Values can be negative before clipping; use with appropriate mean/std_dev.

---

### LogNormal

Heavy-tailed distribution (realistic for payments).

**Parameters:**
- `mean` - Log-normal μ parameter
- `std_dev` - Log-normal σ parameter

**Sampling:** `amount = exp(Z × std_dev + mean)` where Z is standard normal

**Example:**
```yaml
amount_distribution:
  type: LogNormal
  mean: 11.5    # exp(11.5) ≈ $1,000
  std_dev: 0.8  # Creates heavy tail
```

**Typical Values:**
| mean | Approximate Center |
|------|-------------------|
| 9.2 | $100 |
| 11.5 | $1,000 |
| 13.8 | $10,000 |
| 14.5 | $20,000 |

---

### Exponential

Exponential decay distribution.

**Parameters:**
- `rate` - Exponential rate parameter (λ)

**Sampling:** `amount = -ln(U) / rate` where U is uniform(0,1)

**Example:**
```yaml
amount_distribution:
  type: Exponential
  lambda: 0.00001  # Mean = 1/λ = 100,000 cents ($1,000)
```

---

## Priority Distributions

**Location:** `arrivals/mod.rs:40-52`

```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum PriorityDistribution {
    Fixed { value: u8 },
    Categorical { values: Vec<u8>, weights: Vec<f64> },
    Uniform { min: u8, max: u8 },
}
```

### Fixed

All transactions receive same priority.

**Example:**
```yaml
priority_distribution:
  type: Fixed
  value: 5
```

### Categorical

Discrete distribution with specified probabilities.

**Example:**
```yaml
priority_distribution:
  type: Categorical
  values: [3, 5, 8]
  weights: [0.3, 0.5, 0.2]
```

### Uniform

Random priority in range (inclusive).

**Example:**
```yaml
priority_distribution:
  type: Uniform
  min: 3
  max: 7
```

---

## Python Configuration

**Location:** `api/payment_simulator/config/schemas.py`

```python
class ArrivalConfig(BaseModel):
    rate_per_tick: float
    amount_distribution: AmountDistribution
    counterparty_weights: Dict[str, float]
    deadline_range: List[int]  # [min, max]
    priority: int = 5  # Legacy single value
    priority_distribution: Optional[PriorityDistribution] = None
    divisible: bool = False

    def get_effective_priority_config(self) -> dict:
        """Convert to FFI format."""
        if self.priority_distribution:
            return self.priority_distribution.to_ffi_dict()
        return {"type": "Fixed", "value": self.priority}

class ArrivalBandConfig(BaseModel):
    rate_per_tick: float
    amount_distribution: AmountDistribution
    deadline_offset_min: int
    deadline_offset_max: int
    counterparty_weights: Dict[str, float] = {}
    divisible: bool = False

class ArrivalBandsConfig(BaseModel):
    urgent: Optional[ArrivalBandConfig] = None
    normal: Optional[ArrivalBandConfig] = None
    low: Optional[ArrivalBandConfig] = None

    @model_validator(mode="after")
    def at_least_one_band(self):
        if not any([self.urgent, self.normal, self.low]):
            raise ValueError("At least one band must be configured")
        return self
```

---

## Example Configurations

### Simple Arrival (Fixed Priority)

```yaml
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

### Categorical Priority Distribution

```yaml
arrival_config:
  rate_per_tick: 8.0
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
```

### BIS Model Per-Band Arrivals

```yaml
arrival_bands:
  urgent:
    rate_per_tick: 0.1           # Rare
    amount_distribution:
      type: LogNormal
      mean: 14.0                 # Large (~$1.2M)
      std_dev: 0.5
    deadline_offset_min: 5       # Tight deadlines
    deadline_offset_max: 15
    counterparty_weights:
      BANK_B: 0.5
      BANK_C: 0.5
    divisible: false             # Cannot split urgent

  normal:
    rate_per_tick: 3.0           # Common
    amount_distribution:
      type: LogNormal
      mean: 11.0                 # Medium (~$60k)
      std_dev: 0.8
    deadline_offset_min: 20      # Moderate deadlines
    deadline_offset_max: 50
    counterparty_weights:
      BANK_B: 0.33
      BANK_C: 0.33
      BANK_D: 0.34
    divisible: true

  low:
    rate_per_tick: 5.0           # Frequent
    amount_distribution:
      type: Normal
      mean: 50000                # Small (~$500)
      std_dev: 15000
    deadline_offset_min: 40      # Relaxed deadlines
    deadline_offset_max: 80
    divisible: true
```

---

## See Also

- [Arrival Generator](../03-generators/arrival-generator.md) - Generation engine
- [Amount Distributions](../03-generators/amount-distributions.md) - Amount sampling
- [Priority Distributions](../03-generators/priority-distributions.md) - Priority sampling
- [AgentConfig](agent-config.md) - Parent configuration
- [Transaction Model](../02-models/transaction.md) - Generated transaction structure

---

*Last Updated: 2025-11-28*
