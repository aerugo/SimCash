# Example Configurations

This document provides **complete, annotated example configurations** for common scenarios. Each example includes comments explaining why settings are chosen.

---

## Minimal Configuration

The simplest possible valid configuration.

```yaml
# Minimal Configuration
# Two passive agents, basic FIFO settlement

simulation:
  ticks_per_day: 100          # 100 ticks = 1 business day
  num_days: 1                 # Single day simulation
  rng_seed: 42                # Deterministic seed

agents:
  # First agent - generates no transactions
  - id: BANK_A
    opening_balance: 10000000 # $100,000 in cents
    policy:
      type: Fifo              # Submit everything immediately

  # Second agent - also passive
  - id: BANK_B
    opening_balance: 10000000
    policy:
      type: Fifo

# No cost_rates = defaults
# No lsm_config = defaults (bilateral/cycles enabled)
# No scenario_events = no injected transactions
```

**Use case**: Testing infrastructure, baseline comparisons.

---

## Active Two-Bank Scenario

Two banks generating transactions with realistic distributions.

```yaml
# Active Two-Bank Scenario
# Realistic transaction generation with standard costs

simulation:
  ticks_per_day: 100
  num_days: 10                # 10-day simulation
  rng_seed: 42

agents:
  - id: BANK_A
    opening_balance: 15000000 # $150,000
    unsecured_cap: 5000000    # $50,000 overdraft allowed
    policy:
      type: LiquidityAware
      target_buffer: 500000   # Maintain $5,000 buffer
      urgency_threshold: 10   # Release if <= 10 ticks to deadline
    arrival_config:
      rate_per_tick: 0.5      # ~50 transactions/day
      amount_distribution:
        type: LogNormal       # Realistic right-skewed
        mean: 11.51           # Median ~$1,000
        std_dev: 0.9
      counterparty_weights:
        BANK_B: 1.0           # All transactions to BANK_B
      deadline_range: [30, 60]
      priority: 5
      divisible: false

  - id: BANK_B
    opening_balance: 15000000
    unsecured_cap: 5000000
    policy:
      type: LiquidityAware
      target_buffer: 500000
      urgency_threshold: 10
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [30, 60]
      priority: 5
      divisible: false

cost_rates:
  overdraft_bps_per_tick: 0.01      # More expensive overdraft
  delay_cost_per_tick_per_cent: 0.0001
  eod_penalty_per_transaction: 10000

lsm_config:
  enable_bilateral: true
  enable_cycles: false              # Only 2 banks, no cycles
```

**Use case**: Basic policy testing, understanding two-party dynamics.

---

## BIS Box 3: Liquidity-Delay Trade-off

Replicates the BIS Working Paper 1310 Box 3 experiment.

```yaml
# BIS Box 3: Liquidity-Delay Trade-off
# Three-period model testing optimal liquidity allocation

simulation:
  ticks_per_day: 3            # 3 periods (BIS model)
  num_days: 1                 # Single experiment
  rng_seed: 42

# ============================================================================
# Disable non-BIS features
# ============================================================================
lsm_config:
  enable_bilateral: true      # Allow bilateral netting
  enable_cycles: false        # No multilateral
  max_cycle_length: 3
  max_cycles_per_tick: 1

# ============================================================================
# BIS Cost Model
# ============================================================================
cost_rates:
  # Active BIS costs
  delay_cost_per_tick_per_cent: 0.01    # 1% base delay
  priority_delay_multipliers:
    urgent_multiplier: 1.5              # Urgent: 1.5% delay
    normal_multiplier: 1.0              # Normal: 1.0% delay
    low_multiplier: 0.5                 # Low: 0.5% delay
  liquidity_cost_per_tick_bps: 150      # 1.5% opportunity cost

  # Disabled (not in BIS model)
  overdraft_bps_per_tick: 0
  collateral_cost_per_tick_bps: 0
  eod_penalty_per_transaction: 0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0

# ============================================================================
# Agents
# ============================================================================
agents:
  # FOCAL_BANK: Makes liquidity allocation decisions
  - id: FOCAL_BANK
    opening_balance: 0                   # Start at zero
    unsecured_cap: 0                     # No credit
    liquidity_pool: 1000000              # $10,000 pool
    liquidity_allocation_fraction: 0.5   # Allocate 50% = $5,000 (optimal)
    policy:
      type: Fifo

  # COUNTERPARTY: Provides incoming payments
  - id: COUNTERPARTY
    opening_balance: 10000000            # $100,000
    unsecured_cap: 0
    policy:
      type: Fifo

# ============================================================================
# Deterministic Payment Injections
# ============================================================================
scenario_events:
  # Period 1 (Tick 0): Incoming payments
  - type: CustomTransactionArrival
    from_agent: COUNTERPARTY
    to_agent: FOCAL_BANK
    amount: 500000                       # $5,000
    priority: 5
    deadline: 5
    schedule:
      type: OneTime
      tick: 0

  - type: CustomTransactionArrival
    from_agent: COUNTERPARTY
    to_agent: FOCAL_BANK
    amount: 500000
    priority: 5
    deadline: 5
    schedule:
      type: OneTime
      tick: 0

  # Period 2 (Tick 1): Small outgoing
  - type: CustomTransactionArrival
    from_agent: FOCAL_BANK
    to_agent: COUNTERPARTY
    amount: 500000
    priority: 5
    deadline: 4
    schedule:
      type: OneTime
      tick: 1

  # Period 3 (Tick 2): Large urgent outgoing
  - type: CustomTransactionArrival
    from_agent: FOCAL_BANK
    to_agent: COUNTERPARTY
    amount: 1000000                      # $10,000
    priority: 9                          # Urgent
    deadline: 4
    schedule:
      type: OneTime
      tick: 2
```

**Use case**: Research replication, understanding trade-offs.

---

## TARGET2 Crisis Scenario

Multi-day systemic risk test with all T2 features.

```yaml
# TARGET2 Crisis Scenario
# 25-day test of limit cascades and policy impact

simulation:
  ticks_per_day: 100
  num_days: 25
  rng_seed: 42

# ============================================================================
# TARGET2 LSM Alignment
# ============================================================================
algorithm_sequencing: true              # FIFO → Bilateral → Multilateral
entry_disposition_offsetting: true      # Check offsets at entry

# ============================================================================
# Priority Escalation
# ============================================================================
priority_escalation:
  enabled: true
  curve: "linear"
  start_escalating_at_ticks: 25         # Start at 25 ticks to deadline
  max_boost: 4                          # Up to +4 priority

# ============================================================================
# Agents with Limits
# ============================================================================
agents:
  - id: BIG_BANK_A
    opening_balance: 15000000           # $150,000
    unsecured_cap: 5000000              # $50,000 credit
    limits:
      bilateral_limits:
        SMALL_BANK_A: 4000000           # $40k max to SBA
        BIG_BANK_B: 6000000             # $60k max to BBB
        SMALL_BANK_B: 5000000           # $50k max to SBB
      multilateral_limit: 12000000      # $120k total daily
    policy:
      type: FromJson
      json_path: "backend/policies/target2_priority_aware.json"
    arrival_config:
      rate_per_tick: 0.65
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.9
      counterparty_weights:
        SMALL_BANK_A: 0.25
        BIG_BANK_B: 0.35
        SMALL_BANK_B: 0.40
      deadline_range: [35, 70]
      priority: 5
      divisible: true

  - id: BIG_BANK_B
    opening_balance: 14000000
    unsecured_cap: 4500000
    limits:
      bilateral_limits:
        BIG_BANK_A: 5000000
        SMALL_BANK_A: 3500000
        SMALL_BANK_B: 5500000
      multilateral_limit: 11000000
    policy:
      type: FromJson
      json_path: "backend/policies/target2_limit_aware.json"
    arrival_config:
      rate_per_tick: 0.60
      amount_distribution:
        type: LogNormal
        mean: 11.51
        std_dev: 0.85
      counterparty_weights:
        BIG_BANK_A: 0.30
        SMALL_BANK_A: 0.25
        SMALL_BANK_B: 0.45
      deadline_range: [30, 65]
      priority: 6
      divisible: true

  - id: SMALL_BANK_A
    opening_balance: 12000000
    unsecured_cap: 4000000
    limits:
      bilateral_limits:
        BIG_BANK_A: 3000000
        BIG_BANK_B: 2500000
        SMALL_BANK_B: 4000000
      multilateral_limit: 8500000
    policy:
      type: FromJson
      json_path: "backend/policies/target2_limit_aware.json"
    arrival_config:
      rate_per_tick: 0.55
      amount_distribution:
        type: Uniform
        min: 80000
        max: 350000
      counterparty_weights:
        BIG_BANK_A: 0.30
        BIG_BANK_B: 0.25
        SMALL_BANK_B: 0.45
      deadline_range: [30, 70]
      priority: 5
      divisible: true

  - id: SMALL_BANK_B
    opening_balance: 10000000           # Constrained
    unsecured_cap: 3000000
    limits:
      bilateral_limits:
        BIG_BANK_A: 3000000
        BIG_BANK_B: 3500000
        SMALL_BANK_A: 2500000
      multilateral_limit: 7500000       # Tight limit
    policy:
      type: FromJson
      json_path: "backend/policies/target2_crisis_proactive_manager.json"
    arrival_config:
      rate_per_tick: 0.58
      amount_distribution:
        type: Uniform
        min: 100000
        max: 400000
      counterparty_weights:
        BIG_BANK_A: 0.35
        BIG_BANK_B: 0.35
        SMALL_BANK_A: 0.30
      deadline_range: [35, 75]
      priority: 6
      divisible: true

# ============================================================================
# LSM Configuration
# ============================================================================
lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
  max_cycles_per_tick: 20

# ============================================================================
# Crisis Cost Rates
# ============================================================================
cost_rates:
  delay_cost_per_tick_per_cent: 0.00035
  overdraft_bps_per_tick: 0.50
  collateral_cost_per_tick_bps: 0.0003
  eod_penalty_per_transaction: 25000
  deadline_penalty: 12000
  overdue_delay_multiplier: 5.0
  split_friction_cost: 8000

# ============================================================================
# Scenario Events (abbreviated - see full config for complete)
# ============================================================================
scenario_events:
  # Day 1: Offset opportunity
  - type: CustomTransactionArrival
    from_agent: BIG_BANK_A
    to_agent: SMALL_BANK_B
    amount: 900000
    priority: 7
    deadline: 35
    schedule:
      type: OneTime
      tick: 15

  # Day 10: Activity surge
  - type: GlobalArrivalRateChange
    multiplier: 2.0
    schedule:
      type: OneTime
      tick: 920

  - type: GlobalArrivalRateChange
    multiplier: 1.0
    schedule:
      type: OneTime
      tick: 980

  # Day 16: Emergency collateral
  - type: CollateralAdjustment
    agent: BIG_BANK_A
    delta: 4000000
    schedule:
      type: OneTime
      tick: 1560
```

**Use case**: Systemic risk research, policy comparison studies.

---

## Per-Band Arrivals

Using Enhancement 11.3 per-priority-band configuration.

```yaml
# Per-Band Arrivals Example
# Different arrival characteristics per priority band

simulation:
  ticks_per_day: 100
  num_days: 5
  rng_seed: 42

queue1_ordering: "priority_deadline"
priority_mode: true

agents:
  - id: BANK_A
    opening_balance: 20000000
    unsecured_cap: 5000000
    policy:
      type: FromJson
      json_path: "backend/policies/priority_aware.json"
    arrival_bands:
      # Urgent band (priority 8-10)
      # Few, large, tight deadline
      urgent:
        rate_per_tick: 0.05           # ~5/day
        amount_distribution:
          type: Uniform
          min: 1000000                # $10k-$50k
          max: 5000000
        deadline_offset_min: 8        # Very tight
        deadline_offset_max: 20
        divisible: false              # Must settle whole

      # Normal band (priority 4-7)
      # Moderate frequency, standard size
      normal:
        rate_per_tick: 0.3            # ~30/day
        amount_distribution:
          type: LogNormal
          mean: 11.51
          std_dev: 0.9
        deadline_offset_min: 25
        deadline_offset_max: 50
        counterparty_weights:
          BANK_B: 0.6
          BANK_C: 0.4
        divisible: true

      # Low band (priority 0-3)
      # High frequency, small transactions
      low:
        rate_per_tick: 0.5            # ~50/day
        amount_distribution:
          type: Exponential
          lambda: 0.00005             # Mean ~$200
        deadline_offset_min: 40
        deadline_offset_max: 80
        divisible: true

  - id: BANK_B
    opening_balance: 15000000
    policy:
      type: LiquidityAware
      target_buffer: 300000
      urgency_threshold: 15
    arrival_bands:
      normal:
        rate_per_tick: 0.4
        amount_distribution:
          type: LogNormal
          mean: 11.0
          std_dev: 1.0
        deadline_offset_min: 30
        deadline_offset_max: 60

  - id: BANK_C
    opening_balance: 12000000
    policy:
      type: Fifo

cost_rates:
  delay_cost_per_tick_per_cent: 0.0001
  priority_delay_multipliers:
    urgent_multiplier: 3.0            # 3x delay cost for urgent
    normal_multiplier: 1.0
    low_multiplier: 0.3               # 0.3x for low priority
```

**Use case**: Modeling realistic priority distributions.

---

## Policy Splitting Scenario

Testing transaction splitting behavior.

```yaml
# Policy Splitting Scenario
# Large transactions split for gradual settlement

simulation:
  ticks_per_day: 100
  num_days: 5
  rng_seed: 42

agents:
  - id: LARGE_SENDER
    opening_balance: 50000000         # $500k - can't afford all at once
    unsecured_cap: 0                  # No credit
    policy:
      type: LiquiditySplitting
      max_splits: 4                   # Split into max 4 parts
      min_split_amount: 50000         # Each part at least $500
    arrival_config:
      rate_per_tick: 0.1
      amount_distribution:
        type: Uniform
        min: 2000000                  # Large transactions
        max: 10000000                 # $20k - $100k
      counterparty_weights:
        RECEIVER: 1.0
      deadline_range: [40, 80]
      priority: 5
      divisible: true                 # REQUIRED for splitting

  - id: RECEIVER
    opening_balance: 10000000
    policy:
      type: Fifo
    arrival_config:
      rate_per_tick: 0.2
      amount_distribution:
        type: Uniform
        min: 100000
        max: 500000
      counterparty_weights:
        LARGE_SENDER: 1.0
      deadline_range: [30, 60]
      priority: 5
      divisible: false

cost_rates:
  split_friction_cost: 5000           # $50 per split
  delay_cost_per_tick_per_cent: 0.0002
```

**Use case**: Testing splitting policies, high-value payment handling.

---

## Configuration Templates

### Template: Add Your Own Agent

```yaml
agents:
  - id: YOUR_BANK_ID                  # Unique identifier
    opening_balance: 10000000         # Starting balance (cents)
    unsecured_cap: 0                  # Overdraft capacity (cents)

    # Choose ONE policy type:
    policy:
      type: Fifo
      # OR
      type: Deadline
      urgency_threshold: 10
      # OR
      type: LiquidityAware
      target_buffer: 500000
      urgency_threshold: 10
      # OR
      type: FromJson
      json_path: "path/to/policy.json"

    # Choose ONE arrival method (or omit for no arrivals):
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: Uniform
        min: 100000
        max: 500000
      deadline_range: [30, 60]
      priority: 5
    # OR
    arrival_bands:
      normal:
        rate_per_tick: 0.5
        amount_distribution:
          type: Uniform
          min: 100000
          max: 500000
        deadline_offset_min: 30
        deadline_offset_max: 60

    # Optional fields:
    posted_collateral: 1000000        # Initial collateral
    collateral_haircut: 0.1           # 10% haircut
    limits:
      bilateral_limits:
        OTHER_BANK: 5000000
      multilateral_limit: 10000000
    liquidity_pool: 5000000           # External pool
    liquidity_allocation_fraction: 0.5
```

---

## Navigation

**Previous**: [Advanced Settings](advanced-settings.md)
**Back to Index**: [Scenario Reference](index.md)
