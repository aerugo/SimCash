# Per-Agent Arrival Configurations

## Overview

Per-agent arrival configurations allow you to model **heterogeneous banks** in the payment simulator. Different banks can have:

1. **Different transaction volumes** (large vs small banks)
2. **Different transaction sizes** (investment banks vs retail banks)
3. **Different counterparty preferences** (correspondent relationships)
4. **Different time-of-day patterns** (morning rush, end-of-day spike)

This feature is essential for realistic payment network simulation and stress testing.

## Why This Matters

### Real-World Banking Heterogeneity

In real payment systems:
- **Large banks** (e.g., JPMorgan, Bank of America) dominate transaction volume
- **Small banks** send fewer, smaller payments
- **Investment banks** send sporadic but very large transactions
- **Correspondent banks** have specific relationship patterns

Without per-agent configurations, all agents would behave identically, which is unrealistic and limits the insights you can gain from simulation.

### Research Questions Enabled

With heterogeneous agents, you can explore:

1. **Concentration Risk**: How does the system behave when large banks delay payments?
2. **Vulnerability**: Are small banks more susceptible to gridlock?
3. **Network Effects**: How do counterparty preferences affect system throughput?
4. **Time Patterns**: What happens when all banks rush at end-of-day?
5. **Policy Impact**: Do different bank sizes respond differently to policy changes?

## Configuration Structure

### Basic Configuration

```yaml
agents:
  - id: LARGE_BANK
    balance: 10000000  # $100K in cents
    credit_limit: 5000000  # $50K
    arrival_config:
      agent_id: LARGE_BANK
      rate_per_tick: 8.0  # High volume: 8 transactions/tick on average
      distribution_type: lognormal
      amount_mean: 500000  # $5K average
      amount_std_dev: 200000  # $2K std dev
```

### Key Parameters

#### 1. Rate Per Tick
- **What**: Expected number of outgoing transactions per tick
- **Type**: Float (Poisson lambda parameter)
- **Examples**:
  - Large bank: 8.0 (very active)
  - Medium bank: 3.0 (moderate)
  - Small bank: 1.0 (quiet)
  - Investment bank: 0.5 (sporadic but large)

#### 2. Distribution Type
- **What**: How transaction amounts are distributed
- **Options**:
  - `normal`: Symmetric around mean (good for retail)
  - `lognormal`: Right-skewed with heavy tail (realistic for payments)
  - `uniform`: Equal probability in range (for testing)
  - `exponential`: Decaying probability (rare for payments)

#### 3. Amount Parameters
- **amount_mean**: Average transaction size (i64 cents)
- **amount_std_dev**: Variability around mean (i64 cents)
- **Note**: For uniform, use `amount_min` and `amount_max` instead
- **Note**: For exponential, use `exponential_lambda` instead

## Advanced Features

### Counterparty Preferences

Model correspondent banking relationships:

```yaml
arrival_config:
  agent_id: BANK_A
  rate_per_tick: 5.0
  amount_mean: 200000
  amount_std_dev: 50000
  distribution_type: normal
  # Weighted selection of receivers
  counterparty_weights:
    BANK_B: 0.6  # 60% of transactions go to BANK_B
    BANK_C: 0.3  # 30% to BANK_C
    BANK_D: 0.1  # 10% to BANK_D
```

**Use cases**:
- Correspondent banking (regional bank sends mostly to money-center bank)
- Trade relationships (two banks exchange high volumes)
- Testing concentration (what if everyone sends to one bank?)

### Time-of-Day Patterns

Model intraday variations:

```yaml
arrival_config:
  agent_id: BANK_D
  rate_per_tick: 2.0  # Base rate
  amount_mean: 1000000
  amount_std_dev: 300000
  distribution_type: lognormal
  # Rate multipliers by time window
  time_windows:
    - start_tick: 0
      end_tick: 30
      rate_multiplier: 1.5  # 50% more active in morning (3.0 effective rate)
    - start_tick: 30
      end_tick: 80
      rate_multiplier: 1.0  # Normal midday (2.0 rate)
    - start_tick: 80
      end_tick: 100
      rate_multiplier: 2.0  # End-of-day rush (4.0 rate)
```

**Use cases**:
- Morning opening spike
- Lunch lull
- End-of-day settlement rush
- Cut-off time behavior

## Example Scenarios

### Scenario 1: Size Heterogeneity

Model realistic bank size distribution:

```yaml
agents:
  # Top-tier bank: 50% of system volume
  - id: TIER1_BANK
    balance: 50000000
    arrival_config:
      rate_per_tick: 20.0  # Very high volume
      amount_mean: 1000000  # $10K average
      
  # Mid-tier banks: 30% of volume (3 banks × 10% each)
  - id: TIER2_BANK_A
    arrival_config:
      rate_per_tick: 6.7
      amount_mean: 500000  # $5K average
      
  # Many small banks: 20% of volume (10 banks × 2% each)
  - id: SMALL_BANK_1
    arrival_config:
      rate_per_tick: 1.3
      amount_mean: 200000  # $2K average
```

### Scenario 2: Stress Test - Large Bank Delays

```yaml
# Large bank with high volume
- id: SYSTEMIC_BANK
  arrival_config:
    rate_per_tick: 15.0
    amount_mean: 2000000
    # No counterparty weights - sends to everyone

# Small banks that depend on it
- id: SMALL_BANK_1
  arrival_config:
    rate_per_tick: 2.0
    amount_mean: 100000
    counterparty_weights:
      SYSTEMIC_BANK: 0.7  # 70% of payments expect from systemic bank
      OTHER: 0.3
```

**Test**: What happens when SYSTEMIC_BANK uses a "delay all" policy?

### Scenario 3: Investment Bank Behavior

```yaml
- id: INVESTMENT_BANK
  balance: 100000000  # Very large balance
  arrival_config:
    rate_per_tick: 0.8  # Low frequency
    distribution_type: lognormal
    amount_mean: 10000000  # $100K average
    amount_std_dev: 5000000  # High variance
    # Time pattern: sporadic large payments
    time_windows:
      - start_tick: 0
        end_tick: 50
        rate_multiplier: 1.0
      - start_tick: 50
        end_tick: 100
        rate_multiplier: 0.2  # Very quiet in afternoon
```

## Implementation Notes

### Rust Side

The `ArrivalGenerator` in Rust:
1. Samples from Poisson distribution for number of arrivals
2. For each arrival, samples amount from configured distribution
3. Selects receiver based on weights (or uniformly)
4. Creates `TransactionRequest` with sampled values
5. Returns vector of requests to orchestrator

**Key**: All amounts are **i64 in cents**. The distributions use f64 internally for sampling but immediately round to i64.

### Python Side

The `ArrivalConfig` Pydantic model:
1. Validates parameters (positive rates, valid distributions)
2. Checks counterparty weights sum properly
3. Converts to Rust-compatible dict
4. Embedded in `AgentConfig` or passed separately

### Determinism

Since arrivals use the seeded RNG:
- **Same seed → same arrival sequence**
- Each arrival advances RNG state
- Replay produces identical transactions

## Testing Strategies

### Unit Tests

Test individual components:

```python
def test_poisson_sampling():
    """Test Poisson sampling produces correct mean."""
    rng = RngManager(seed=12345)
    samples = [sample_poisson(lambda=5.0, rng) for _ in range(1000)]
    assert 4.5 < np.mean(samples) < 5.5  # Should be close to 5.0

def test_amount_distribution():
    """Test amount sampling stays in valid range."""
    config = ArrivalConfig(
        agent_id="A",
        rate_per_tick=1.0,
        amount_mean=100_000,
        amount_std_dev=20_000,
        distribution_type="normal",
    )
    for _ in range(100):
        amount = sample_amount(config, rng)
        assert amount > 0  # Must be positive
        assert isinstance(amount, int)  # Must be i64
```

### Integration Tests

Test full arrival generation:

```python
def test_heterogeneous_volume():
    """Large bank should generate more transactions than small bank."""
    configs = [
        ArrivalConfig(agent_id="LARGE", rate_per_tick=10.0, ...),
        ArrivalConfig(agent_id="SMALL", rate_per_tick=2.0, ...),
    ]
    
    generator = ArrivalGenerator(configs)
    
    # Run 100 ticks
    large_count = 0
    small_count = 0
    
    for tick in range(100):
        arrivals = generator.generate_arrivals(tick, rng, ["LARGE", "SMALL"])
        large_count += sum(1 for a in arrivals if a.sender_id == "LARGE")
        small_count += sum(1 for a in arrivals if a.sender_id == "SMALL")
    
    # Large bank should send ~5x more
    assert large_count > small_count * 4
    assert large_count < small_count * 6
```

### Determinism Tests

```python
def test_arrival_determinism():
    """Same seed produces same arrivals."""
    config = ArrivalConfig(agent_id="A", rate_per_tick=5.0, ...)
    
    def run_simulation(seed: int) -> list[TransactionRequest]:
        rng = RngManager(seed)
        generator = ArrivalGenerator([config])
        arrivals = []
        for tick in range(50):
            arrivals.extend(generator.generate_arrivals(tick, rng, ["A", "B"]))
        return arrivals
    
    results1 = run_simulation(seed=12345)
    results2 = run_simulation(seed=12345)
    
    # Should be identical
    assert len(results1) == len(results2)
    for a1, a2 in zip(results1, results2):
        assert a1.amount == a2.amount
        assert a1.sender_id == a2.sender_id
        assert a1.receiver_id == a2.receiver_id
```

## Configuration Best Practices

### Start Simple

```yaml
# Begin with uniform rates and simple distributions
agents:
  - id: A
    arrival_config:
      rate_per_tick: 3.0
      distribution_type: normal
      amount_mean: 200000
      amount_std_dev: 50000
```

### Add Complexity Gradually

```yaml
# Add heterogeneity
agents:
  - id: LARGE
    arrival_config:
      rate_per_tick: 8.0  # Different rate
      amount_mean: 500000  # Different mean
      
  - id: SMALL
    arrival_config:
      rate_per_tick: 2.0
      amount_mean: 100000
```

### Then Add Advanced Features

```yaml
# Add counterparty preferences, time patterns
agents:
  - id: LARGE
    arrival_config:
      rate_per_tick: 8.0
      amount_mean: 500000
      counterparty_weights:  # NEW
        SMALL: 0.7
        OTHER: 0.3
      time_windows:  # NEW
        - start_tick: 0
          end_tick: 50
          rate_multiplier: 1.5
```

## Common Pitfalls

### ❌ Rates Too High

```yaml
arrival_config:
  rate_per_tick: 100.0  # DON'T: Will flood system
```

**Problem**: System can't process 100 tx/tick from each agent
**Solution**: Start with rates < 10, scale up carefully

### ❌ Std Dev Too Large

```yaml
arrival_config:
  amount_mean: 100000
  amount_std_dev: 500000  # DON'T: 5x the mean
```

**Problem**: Generates many near-zero or huge amounts
**Solution**: Keep std_dev ≤ mean, typically < 0.5 × mean

### ❌ Forgetting Counterparty Weights Sum

```yaml
counterparty_weights:
  A: 0.5
  B: 0.3
  # Total: 0.8, not 1.0 - but that's OK!
```

**Note**: Weights don't need to sum to 1.0, they're normalized internally

### ❌ Time Windows Don't Cover Full Day

```yaml
time_windows:
  - start_tick: 0
    end_tick: 50
    rate_multiplier: 1.5
  # Ticks 50-100 will use base rate (no multiplier)
```

**Solution**: Either cover full day or accept base rate as default

## Metrics and Monitoring

Track arrival-related metrics:

```python
# In your monitoring code
arrival_stats = {
    "total_generated": 0,
    "by_agent": {},
    "by_hour": [0] * (ticks_per_day // (ticks_per_day // 24)),
    "amount_distribution": [],
}

for tick in range(ticks_per_day):
    arrivals = generator.generate_arrivals(tick, rng, agent_ids)
    
    arrival_stats["total_generated"] += len(arrivals)
    
    for arrival in arrivals:
        # Track by agent
        agent = arrival.sender_id
        arrival_stats["by_agent"][agent] = arrival_stats["by_agent"].get(agent, 0) + 1
        
        # Track amounts
        arrival_stats["amount_distribution"].append(arrival.amount)
```

## Summary

Per-agent arrival configurations are essential for:
- ✅ Realistic payment network simulation
- ✅ Modeling heterogeneous bank sizes and behaviors
- ✅ Stress testing system under various scenarios
- ✅ Understanding network effects and concentration risk
- ✅ Evaluating policy impacts across different agent types

Start simple, validate determinism, then add complexity gradually!