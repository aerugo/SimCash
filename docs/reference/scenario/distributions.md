# Distribution Configuration

Distributions control how values are sampled during transaction generation. There are two categories:

1. **Amount Distributions**: Sample transaction values (in cents)
2. **Priority Distributions**: Sample transaction priorities (0-10)

All distributions are **deterministic** when seeded - same `rng_seed` produces identical samples.

---

## Amount Distributions

Amount distributions determine transaction values. All amounts are in **integer cents**.

### `Normal` Distribution

Symmetric bell curve around mean.

#### Schema

```yaml
amount_distribution:
  type: Normal
  mean: <int>       # Required, cents
  std_dev: <int>    # Required, cents, > 0
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `mean` | `int` | None | Center of distribution (cents) |
| `std_dev` | `int` | `> 0` | Standard deviation (cents) |

#### Behavior

- ~68% of values within 1 std_dev of mean
- ~95% within 2 std_dev
- Can produce negative values (truncated to minimum)

#### Example

```yaml
amount_distribution:
  type: Normal
  mean: 500000       # $5,000 average
  std_dev: 100000    # $1,000 standard deviation
```

#### Use Cases

- Symmetric transaction distributions
- Testing with predictable ranges

---

### `LogNormal` Distribution

Right-skewed distribution. Many small values, few large values.

#### Schema

```yaml
amount_distribution:
  type: LogNormal
  mean: <float>      # Required, log-scale mean
  std_dev: <float>   # Required, log-scale std_dev, > 0
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `mean` | `float` | None | Mean of log(value) |
| `std_dev` | `float` | `> 0` | Std dev of log(value) |

#### Behavior

- Output = exp(Normal(mean, std_dev))
- Always positive
- Realistic for financial transaction sizes

#### Converting to Dollar Amounts

| Log Mean | Log Std | Median | ~95% Range |
|:---------|:--------|:-------|:-----------|
| `11.51` | `0.9` | ~$1,000 | $200 - $8,000 |
| `12.21` | `0.8` | ~$2,000 | $500 - $12,000 |
| `13.82` | `1.0` | ~$10,000 | $1,500 - $100,000 |

#### Example

```yaml
amount_distribution:
  type: LogNormal
  mean: 11.51        # Median ~$1,000
  std_dev: 0.9       # Moderate spread
```

#### Use Cases

- **Recommended for realistic simulations**
- Matches empirical payment size distributions
- Models "typical small, occasional large" pattern

---

### `Uniform` Distribution

Equal probability across range.

#### Schema

```yaml
amount_distribution:
  type: Uniform
  min: <int>         # Required, cents, >= 0
  max: <int>         # Required, cents, > min
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `min` | `int` | `>= 0` | Minimum value (cents) |
| `max` | `int` | `> min` | Maximum value (cents) |

#### Behavior

- Equal probability for any value in [min, max]
- Discrete sampling (integer cents)

#### Example

```yaml
amount_distribution:
  type: Uniform
  min: 100000        # $1,000 minimum
  max: 500000        # $5,000 maximum
```

#### Use Cases

- Simple testing scenarios
- Bounding transaction sizes
- When realistic distribution not needed

---

### `Exponential` Distribution

Many small values, exponentially fewer large values.

#### Schema

```yaml
amount_distribution:
  type: Exponential
  lambda: <float>    # Required, rate parameter, > 0
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `lambda` | `float` | `> 0` | Rate parameter (inverse of mean) |

Note: In YAML, use `lambda` (Python alias handles the reserved word).

#### Behavior

- Mean = 1/lambda
- Memoryless property
- Strong right skew

#### Converting to Dollar Amounts

| Lambda | Mean | Description |
|:-------|:-----|:------------|
| `0.0001` | $100 | Small transactions |
| `0.00001` | $1,000 | Medium transactions |
| `0.000001` | $10,000 | Large transactions |

#### Example

```yaml
amount_distribution:
  type: Exponential
  lambda: 0.00001    # Mean ~$1,000
```

#### Use Cases

- Modeling rare large payments
- Queue theory analysis
- When extreme values matter

---

## Priority Distributions

Priority distributions sample transaction priorities (0-10).

### `Fixed` Distribution

All transactions get the same priority.

#### Schema

```yaml
priority_distribution:
  type: Fixed
  value: <int>       # Required, 0-10
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `value` | `int` | `0-10` | Fixed priority value |

#### Example

```yaml
priority_distribution:
  type: Fixed
  value: 7           # All transactions priority 7
```

#### Use Cases

- Equivalent to using `priority` field
- Explicit about distribution type

---

### `Categorical` Distribution

Weighted selection from specific values.

#### Schema

```yaml
priority_distribution:
  type: Categorical
  values: [<int>, ...]      # Required, list of priorities (0-10)
  weights: [<float>, ...]   # Required, weights for each value
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `values` | `List[int]` | All 0-10 | Priority values to choose from |
| `weights` | `List[float]` | Same length, all > 0 | Selection weights |

#### Behavior

- Weights normalized to probabilities
- Random selection based on weights

#### Example

```yaml
priority_distribution:
  type: Categorical
  values: [3, 5, 7, 9]
  weights: [0.20, 0.50, 0.20, 0.10]
  # 10% urgent (9), 20% high (7), 50% normal (5), 20% low (3)
```

#### Use Cases

- **Recommended for realistic simulations**
- Models real payment priority distributions
- Customizable to specific scenarios

---

### `Uniform` Priority Distribution

Random priority within range.

#### Schema

```yaml
priority_distribution:
  type: Uniform
  min: <int>         # Required, 0-10
  max: <int>         # Required, 0-10, >= min
```

#### Fields

| Field | Type | Constraint | Description |
|:------|:-----|:-----------|:------------|
| `min` | `int` | `0-10` | Minimum priority |
| `max` | `int` | `0-10, >= min` | Maximum priority |

#### Example

```yaml
priority_distribution:
  type: Uniform
  min: 4
  max: 8             # Random priority 4-8
```

#### Use Cases

- Testing priority handling
- When specific values don't matter

---

## Priority Bands Reference

| Priority | Band | Typical Use |
|:---------|:-----|:------------|
| 9-10 | Urgent | Central bank operations, securities |
| 8 | Urgent | CLS, time-critical |
| 7 | Normal-High | Important interbank |
| 5-6 | Normal | Standard payments |
| 4 | Normal-Low | Less time-sensitive |
| 1-3 | Low | Discretionary |
| 0 | Low | Lowest priority |

---

## Complete Examples

### Realistic Bank Arrivals

```yaml
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
  divisible: true
```

### Testing Scenario

```yaml
arrival_config:
  rate_per_tick: 1.0
  amount_distribution:
    type: Uniform
    min: 100000
    max: 500000
  priority: 5
  deadline_range: [20, 40]
```

### BIS Model (Simple)

```yaml
# BIS-style uses scenario_events for deterministic transactions
# No arrival_config - controlled injections only
```

---

## Navigation

**Previous**: [Arrivals](arrivals.md)
**Next**: [Cost Rates](cost-rates.md)
