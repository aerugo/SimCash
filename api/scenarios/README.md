# Payment Simulator - Scenario Library

This directory contains pre-configured simulation scenarios demonstrating different RTGS settlement behaviors.

## Available Scenarios

### 1. `realistic_demo.yaml` - Normal Liquidity Conditions

**Purpose**: Demonstrate healthy RTGS operation with well-capitalized banks.

**Characteristics**:
- 4 banks with medium to high liquidity ($150-$500 opening balance)
- Moderate transaction volume (~1.5 transactions/tick)
- Transaction sizes: $50 - $5,000
- Typical settlement rate: **95-100%**
- LSM activity: **Minimal** (0-5 releases)
- Costs: **Low** ($0 - $1,000)

**Use Cases**:
- Baseline performance testing
- Demonstrating normal RTGS behavior
- Testing parameter changes against a stable baseline
- AI model training on "healthy" system behavior

**Run It**:
```bash
payment-sim run --config scenarios/realistic_demo.yaml
```

**Expected Output**:
```
Arrivals: ~120-140
Settlements: ~120-140
Settlement Rate: 95-100%
LSM Releases: 0-5
Total Costs: $0-$1,000
```

---

### 2. `high_stress_gridlock.yaml` - Liquidity Crisis

**Purpose**: Stress-test the LSM's gridlock resolution capabilities.

**Characteristics**:
- 4 banks with low liquidity ($40-$60 opening balance)
- High transaction volume (~2.75 transactions/tick)
- Large transaction sizes relative to liquidity ($500 - $8,000)
- Circular payment patterns (A→B, B→A)
- Tight deadlines (10-30 ticks)
- Typical settlement rate: **65-75%**
- LSM activity: **High** (25-35 releases)
- Costs: **Very High** ($80,000 - $150,000)

**Use Cases**:
- Testing LSM bilateral offsetting
- Demonstrating cycle detection and resolution
- Showing cost accumulation under stress
- Training AI models on gridlock resolution strategies
- Policy optimization research

**Run It**:
```bash
payment-sim run --config scenarios/high_stress_gridlock.yaml
```

**Expected Output**:
```
Arrivals: ~250-270
Settlements: ~170-190
Settlement Rate: 65-75%
LSM Releases: 25-35 ← LSM actively resolving gridlock!
Total Costs: $80,000-$150,000 (penalties for unsettled)
```

---

## Running Scenarios

### Basic Run
```bash
payment-sim run --config scenarios/realistic_demo.yaml
```

### Quiet Mode (AI-friendly)
```bash
payment-sim run --config scenarios/realistic_demo.yaml --quiet | jq '.metrics'
```

### Streaming Mode
```bash
payment-sim run --config scenarios/high_stress_gridlock.yaml --stream
```

### Verbose Mode (Detailed Real-time Events)
```bash
# Show tick-by-tick events with balance changes and LSM activity
payment-sim run --config scenarios/high_stress_gridlock.yaml --verbose --ticks 20
```

**Verbose mode displays:**
- Tick-by-tick progress with visual separators
- Transaction arrivals and settlements
- LSM activity (bilateral offsetting, cycle detection)
- Balance changes per agent (color-coded: green=positive, red=overdraft)
- Cost accumulation
- Queue sizes
- Summary per tick

### Parameter Override
```bash
# Try different seed
payment-sim run --config scenarios/realistic_demo.yaml --seed 999

# Run for fewer ticks
payment-sim run --config scenarios/realistic_demo.yaml --ticks 10
```

---

## Comparison Demo

Run both scenarios side-by-side:
```bash
./demo_comparison.sh
```

This script:
- Runs both scenarios
- Compares settlement rates
- Shows LSM activity differences
- Displays cost differences
- Provides streaming view of first 5 ticks

---

## Scenario Configuration Structure

All scenarios follow this YAML structure:

```yaml
simulation:
  ticks_per_day: 100      # Ticks per simulated business day
  num_days: 1             # Number of days to simulate
  rng_seed: 42            # Random seed for reproducibility

agents:
  - id: "BANK_A"
    opening_balance: 5000000      # Initial balance in cents ($50,000)
    credit_limit: 2000000         # Overdraft limit in cents ($20,000)
    policy:
      type: "Fifo"                # Payment processing policy

    arrival_config:               # Automatic transaction generation
      rate_per_tick: 0.5          # Poisson λ (expected arrivals per tick)
      amount_distribution:
        type: "Uniform"
        min: 10000                # $100 minimum
        max: 500000               # $5,000 maximum
      counterparty_weights:
        BANK_B: 0.4               # 40% of payments go to BANK_B
        BANK_C: 0.3               # 30% to BANK_C
        BANK_D: 0.3               # 30% to BANK_D
      deadline_range: [10, 30]    # Deadline is 10-30 ticks after arrival
      priority: 5                 # Priority level (0-10)
      divisible: false            # Can transaction be split?

lsm_config:
  bilateral_offsetting: true      # Enable bilateral netting
  cycle_detection: true           # Enable cycle detection
  max_iterations: 5               # Max LSM passes per tick

cost_rates:
  overdraft_bps_per_tick: 10              # Overdraft cost (basis points/tick)
  delay_cost_per_tick_per_cent: 1         # Queue delay cost (cents/tick/cent)
  eod_penalty_per_transaction: 1000000    # EOD penalty ($10,000)
  deadline_penalty: 500000                # Deadline miss penalty ($5,000)
  split_friction_cost: 10000              # Cost to split transaction ($100)
```

---

## Creating Custom Scenarios

### Tips for Realistic Scenarios

1. **Opening Balance**: Should be 5-10x average transaction size for healthy operation
2. **Transaction Rate**: 0.3-0.8 per tick creates realistic patterns
3. **Amount Distribution**: Uniform is simplest, LogNormal is most realistic
4. **Counterparty Weights**: Create reciprocal flows (A→B, B→A) to test LSM
5. **Deadlines**: 10-40 ticks provides pressure without being impossible

### Tips for Stress Testing

1. **Low Liquidity**: Opening balance < 2x average transaction size
2. **High Rate**: 0.8-1.2 arrivals per tick
3. **Large Amounts**: Max amount > opening balance
4. **Circular Patterns**: Weighted flows creating cycles
5. **Tight Deadlines**: 5-20 ticks

---

## AI Integration Examples

### Parameter Sweep (Finding Optimal Seed)
```bash
for seed in $(seq 100 110); do
    rate=$(payment-sim run --config scenarios/high_stress_gridlock.yaml \
           --seed $seed --quiet | jq -r '.metrics.settlement_rate')
    echo "Seed $seed: $rate settlement rate"
done
```

### Comparing Multiple Configurations
```bash
# Test different liquidity levels
for balance in 500000 1000000 2000000; do
    # Create temp config with modified balance
    cat scenarios/realistic_demo.yaml | \
        sed "s/opening_balance: 5000000/opening_balance: $balance/" > /tmp/test.yaml

    rate=$(payment-sim run --config /tmp/test.yaml --quiet | \
           jq -r '.metrics.settlement_rate')
    echo "Balance $balance: $rate"
done
```

### Streaming Analysis
```bash
# Monitor settlement rate in real-time
payment-sim run --config scenarios/high_stress_gridlock.yaml --stream --quiet | \
    jq -r 'select(.tick % 10 == 0) | "Tick \(.tick): \(.settlements)/\(.arrivals) settled"'
```

---

## Metrics Guide

### Key Metrics to Track

- **Settlement Rate** = settlements / arrivals
  - Target: >95% for healthy system
  - Warning: <80% indicates gridlock issues
  - Critical: <60% requires intervention

- **LSM Releases** = transactions freed by offsetting
  - Normal: 0-10 releases
  - Stressed: 10-30 releases
  - Critical: >30 (system highly constrained)

- **Total Costs**
  - Overdraft: From negative balances
  - Delay: Queue time penalties
  - EOD: Unsettled at end-of-day
  - Deadline: Missed deadlines

- **Queue Sizes** = pending transactions
  - Healthy: <5 per bank
  - Stressed: 5-15 per bank
  - Gridlocked: >15 per bank

---

## Troubleshooting

### No Transaction Arrivals?
- Check `rate_per_tick` is > 0
- Verify `arrival_config` is present for each agent
- Try increasing `num_days` or `ticks_per_day`

### 100% Settlement Rate (Too Easy)?
- Reduce `opening_balance`
- Increase `rate_per_tick`
- Increase transaction amounts
- Create more circular payment patterns

### 0% Settlement Rate (Too Hard)?
- Increase `opening_balance`
- Increase `credit_limit`
- Reduce transaction amounts
- Loosen deadline constraints

---

## Performance Notes

- **Typical Performance**: 50,000-150,000 ticks/second
- **Factors Affecting Speed**:
  - Number of agents (linear scaling)
  - Transaction volume (linear scaling)
  - LSM iterations (exponential for complex cycles)
  - Queue sizes (logarithmic)

---

## Next Steps

- Explore the scenarios with different seeds
- Modify parameters to test hypotheses
- Create custom scenarios for your research
- Use scenarios as baselines for AI policy optimization

For more information, see:
- [CLI Tool Plan](../docs/cli_tool_plan.md)
- [Architecture Documentation](../docs/architecture.md)
- [Main Project README](../../README.md)
