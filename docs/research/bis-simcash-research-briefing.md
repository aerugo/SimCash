# Research Briefing: BIS AI Cash Management and SimCash Integration

**Date:** November 2025
**Status:** Planning Phase
**Related Documents:**
- `../plans/bis-model-enhancements-tdd-implementation.md`

**Source:** BIS Working Paper No. 1310, "AI agents for cash management in payment systems" (Aldasoro & Desai, November 2025)

---

## Executive Summary

This briefing compares the RTGS model from BIS Working Paper 1310 ("AI agents for cash management in payment systems") with SimCash's payment simulator, identifies key architectural differences, and outlines three enhancements that will enable SimCash to run BIS-style experiments.

**Key Finding:** SimCash already implements most BIS model features but requires three enhancements:
1. **Priority-Based Delay Cost Multipliers** - Different delay costs for urgent vs. normal payments
2. **Liquidity Pool and Allocation** - Explicit pre-day liquidity allocation decisions with opportunity cost
3. **Per-Band Arrival Functions** - Different arrival characteristics (rate, amount, deadline) per priority band

---

## Part 1: The BIS RTGS Model

### Overview

The BIS Working Paper (Aldasoro & Desai, 2025) presents a simplified RTGS model designed to test whether generative AI agents can perform high-level intraday liquidity management in wholesale payment systems.

### Core Design Philosophy

The BIS model is intentionally stylized:
- **Single-agent perspective**: One bank makes decisions; other participants are probabilistic payment sources
- **2-3 discrete periods**: Not continuous time
- **Simple cost structure**: Three cost types rather than complex fee schedules
- **Focus on trade-offs**: Tests fundamental cash management heuristics

### Two Critical Decisions

Cash managers face two fundamental choices (per Bech and Garratt, 2003):

| Decision | Description | Trade-off |
|----------|-------------|-----------|
| **Liquidity Allocation** | How much collateralized liquidity to secure at day start | Higher allocation = fewer delays but higher opportunity cost |
| **Payment Timing** | When to process queued payments | Earlier = lower delay cost but less liquidity for urgent payments |

### Cost Structure

| Cost Type | Rate | Applied When |
|-----------|------|--------------|
| Liquidity allocation | 1.5% | Pre-period (opportunity cost of pledging collateral) |
| Delay (non-urgent) | 1.0% | Per period while payment is queued |
| Delay (urgent) | 1.5% | Per period while urgent payment is queued |
| Emergency borrowing | >1.5% | End-of-day if liquidity short |

### Experimental Scenarios

The paper tests three scenarios of increasing complexity:

#### Scenario 1: Precautionary Decision
- **Setup**: $10 liquidity, two $1 pending payments, potential $10 urgent payment next period
- **Optimal behavior**: Delay $1 payments to preserve liquidity for potential urgent payment
- **Tests**: Precautionary behavior under uncertainty

#### Scenario 2: Navigating Priorities
- **Setup**: $10 liquidity, $1 and $2 pending, 90% chance of $2 inflow, 50% chance of urgent $10
- **Optimal behavior**: Process only $1 payment; wait to see if $2 inflow arrives
- **Tests**: Balancing current needs against anticipated obligations

#### Scenario 3: Liquidity-Delay Trade-off
- **Setup**: Pre-period allocation decision, $5 payment (1% delay), high-probability inflows
- **Optimal behavior**: Allocate $5 initially, rely on incoming payments for subsequent obligations
- **Tests**: Minimizing opportunity cost while accepting minimal risk

---

## Part 2: The SimCash RTGS Model

### Overview

SimCash is a high-performance payment simulator implementing a sophisticated multi-agent RTGS system with liquidity constraints, queuing mechanisms, and liquidity-saving mechanisms (LSM).

### Core Architecture

```
┌─────────────────────────────────────────────────────┐
│              Orchestrator Engine                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Arrivals  │  │   Policies  │  │  Settlement │ │
│  │  Generator  │  │   Engine    │  │   Engine    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │              Simulation State                │   │
│  │  ┌─────────┐  ┌─────────────┐  ┌─────────┐  │   │
│  │  │ Agents  │  │ Transactions │  │ Queues  │  │   │
│  │  └─────────┘  └─────────────┘  └─────────┘  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Multi-agent** | N banks with independent policies |
| **Two-queue architecture** | Queue 1 (internal policy) + Queue 2 (central liquidity retry) |
| **LSM** | Bilateral offsetting + multilateral cycle detection |
| **11 priority levels** | 0-10 scale with T2-compliant bands (Urgent 8-10, Normal 4-7, Low 0-3) |
| **Deterministic replay** | Seeded RNG enables exact reproduction |
| **Tick-based time** | Configurable ticks per day |

### Cost Model

| Cost Type | Default Rate | Description |
|-----------|--------------|-------------|
| Overdraft | 0.001 (1 bp/tick) | Cost of negative balance |
| Delay | 0.0001 (0.1 bp/tick/cent) | Cost per queued transaction |
| Collateral | 0.0002 (0.2 bp/tick) | Opportunity cost of pledged collateral |
| Deadline penalty | $500 | One-time when deadline missed |
| EOD penalty | $100 | Per unsettled transaction at day end |
| Overdue multiplier | 5.0x | Applied to delay cost after deadline |

### Settlement Flow

Each tick executes:
1. Generate arrivals (Poisson sampling)
2. Evaluate policies (Queue 1 decisions)
3. Execute RTGS settlements
4. Process Queue 2 (liquidity retry)
5. Run LSM coordinator
6. Accrue costs
7. Handle end-of-day if needed

---

## Part 3: Key Differences Between BIS and SimCash

### Architectural Comparison

| Aspect | BIS Model | SimCash | Gap |
|--------|-----------|---------|-----|
| **Perspective** | Single-agent | Multi-agent | Configurable (use 2 agents) |
| **Time** | 2-3 discrete periods | Configurable ticks | Compatible |
| **Priority** | Binary (urgent/normal) | 11 levels (0-10) | Mappable |
| **Settlement** | Immediate or queued | RTGS + LSM | LSM can be disabled |
| **Costs** | 3 types | 6 types | Configurable |

### Critical Gaps Requiring Enhancement

#### Gap 1: Priority-Based Delay Costs

| BIS Model | SimCash Current |
|-----------|-----------------|
| Urgent payments: 1.5% delay cost | All payments: same base rate |
| Normal payments: 1.0% delay cost | `overdue_delay_multiplier` applies to overdue, not urgent |

**Impact**: Cannot model the core BIS insight that urgent payments have higher delay costs.

#### Gap 2: Liquidity Allocation Decision

| BIS Model | SimCash Current |
|-----------|-----------------|
| Agent decides initial liquidity at 1.5% cost | Fixed `opening_balance` configuration |
| Trade-off: more liquidity = fewer delays but higher cost | No allocation decision point |
| Dynamic based on expected payments | Static configuration |

**Impact**: Cannot model the fundamental liquidity allocation vs. delay trade-off.

#### Gap 3: Per-Band Arrival Characteristics

| BIS Model | SimCash Current |
|-----------|-----------------|
| Urgent payments: rare but large | Single `arrival_config` with shared `amount_distribution` |
| Normal payments: common and varied | Priority assigned via `priority_distribution` weights |
| Implicit different characteristics per urgency | Cannot have different amount/rate per priority band |

**Impact**: Cannot realistically model payment systems where urgent payments have fundamentally different characteristics than normal payments.

### Features Where SimCash Exceeds BIS

| Feature | BIS Model | SimCash |
|---------|-----------|---------|
| Multi-agent dynamics | No | Yes |
| LSM (bilateral/multilateral) | No | Yes |
| Divisible payments | No | Yes |
| Arrival rate modeling | No | Yes (Poisson, distributions) |
| Policy DSL | No | Yes |
| Deterministic replay | No | Yes |
| Multiple priority levels | 2 | 11 |

---

## Part 4: Planned Enhancements

### Enhancement 1: Priority-Based Delay Cost Multipliers

**Purpose**: Enable different delay costs for transactions based on priority level, matching the BIS model where urgent payments (priority 8-10) have 1.5x delay costs compared to normal payments (priority 4-7).

**Design**:

```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01  # Base rate (1%)
  priority_delay_multipliers:
    urgent_multiplier: 1.5   # Urgent (8-10): 1.5%
    normal_multiplier: 1.0   # Normal (4-7): 1.0%
    low_multiplier: 0.5      # Low (0-3): 0.5% (optional)
```

**Implementation**:
1. Add `PriorityDelayMultipliers` struct to `CostRates`
2. Add `PriorityBand` enum (Urgent, Normal, Low)
3. Modify delay cost calculation to apply priority multiplier
4. Expose in policy context as `priority_delay_multiplier_for_this_tx`

**Test Coverage**: 3 test categories covering config parsing, band boundaries, and cost calculation.

---

### Enhancement 2: Liquidity Pool and Allocation

**Purpose**: Enable agents to allocate liquidity from an external pool into the payment system at day start, with associated opportunity cost. This models the BIS Period 0 decision.

**Conceptual Distinction**:

| Aspect | Liquidity Allocation | Collateral Posting |
|--------|---------------------|-------------------|
| **Source** | External liquidity pool | Pledged assets |
| **Provides** | Positive cash balance | Credit capacity (overdraft) |
| **Effect** | `balance += allocated` | `credit_limit += posted` |
| **Cost** | `liquidity_cost_per_tick_bps` | `collateral_cost_per_tick_bps` |

**Design**:

```yaml
agent_configs:
  - id: BANK_A
    liquidity_pool: 2_000_000         # Total external liquidity available
    liquidity_allocation_fraction: 0.5 # Allocate 50% at day start
    # Result: balance = 1,000,000

cost_rates:
  liquidity_cost_per_tick_bps: 15     # 1.5% annualized opportunity cost
```

**Lifecycle Flow**:

```
┌─────────────────────────────────────────────────────┐
│                  DAY START (Tick 0)                  │
├─────────────────────────────────────────────────────┤
│ Step 0: Liquidity Allocation                         │
│   For each agent with liquidity_pool:                │
│     1. Calculate: allocated = pool × fraction        │
│     2. Set: agent.balance += allocated               │
│     3. Emit: LiquidityAllocation event               │
├─────────────────────────────────────────────────────┤
│ Step 1.5+: Normal tick processing continues...       │
└─────────────────────────────────────────────────────┘
```

**Test Coverage**: 6 test categories with 40+ tests covering:
- Configuration parsing and validation
- Basic allocation mechanics
- Multi-day behavior and reallocation
- Event generation and replay identity
- Policy context integration
- Edge cases and error handling

---

### Enhancement 3: Per-Band Arrival Functions

**Purpose**: Enable different arrival characteristics (rate, amount distribution, deadline) for each priority band, allowing realistic modeling where urgent payments are rare but large, and normal payments are common but smaller.

**Design**:

```yaml
agent_configs:
  - id: BANK_A
    arrival_bands:                        # NEW: Replaces arrival_config
      urgent:                             # Priority 8-10
        rate_per_tick: 0.1                # Rare
        amount_distribution:
          type: log_normal
          mean: 1_000_000                 # Large ($10k average)
        deadline_offset:
          min_ticks: 5
          max_ticks: 15

      normal:                             # Priority 4-7
        rate_per_tick: 3.0                # Common
        amount_distribution:
          type: log_normal
          mean: 50_000                    # Medium ($500 average)

      low:                                # Priority 0-3
        rate_per_tick: 5.0                # Frequent
        amount_distribution:
          type: log_normal
          mean: 10_000                    # Small ($100 average)
```

**Backwards Compatibility**: Existing `arrival_config` continues to work. New `arrival_bands` is an alternative.

**Test Coverage**: 3 test categories covering config parsing, generation per band, and determinism.

---

## Part 5: Configuring BIS Scenarios in SimCash

Once enhancements are implemented, BIS scenarios can be configured as follows:

### Scenario 1: Precautionary Liquidity Allocation

```yaml
# bis-scenario-1.yaml
ticks_per_day: 2
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01

agent_configs:
  - id: BANK_A
    liquidity_pool: 2_000_000              # NEW: External pool
    liquidity_allocation_fraction: 0.5     # NEW: Agent decides this
    credit_limit: 0
  - id: BANK_B
    liquidity_pool: 2_000_000
    liquidity_allocation_fraction: 0.5
    credit_limit: 0

scenario_events:
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500_000
      priority: 5                          # Normal priority
    schedule:
      tick: 0

lsm_config:
  enable_bilateral: false                  # Disable for pure BIS behavior
  enable_cycles: false
```

**Analysis approach**: Run simulations with different `liquidity_allocation_fraction` values, measure total costs (simulation costs + allocation opportunity cost), find optimal allocation.

---

### Scenario 2: Priority-Based Delay Costs

```yaml
# bis-scenario-2.yaml
ticks_per_day: 2
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01       # Base: 1%
  priority_delay_multipliers:               # NEW
    urgent_multiplier: 1.5                 # Urgent: 1.5%
    normal_multiplier: 1.0                 # Normal: 1.0%

agent_configs:
  - id: BANK_A
    opening_balance: 1_000_000
    credit_limit: 0
  - id: BANK_B
    opening_balance: 1_000_000
    credit_limit: 0

scenario_events:
  # Urgent payment
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500_000
      priority: 9                          # Urgent band
    schedule:
      tick: 0
  # Normal payment
  - event:
      type: custom_transaction_arrival
      from_agent: BANK_A
      to_agent: BANK_B
      amount: 500_000
      priority: 5                          # Normal band
    schedule:
      tick: 0

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

**Expected behavior**: Agent policy should prioritize urgent payment (higher delay cost) over normal payment when liquidity is constrained.

---

### Scenario 3: Realistic Monte Carlo with Per-Band Arrivals

```yaml
# bis-scenario-3-monte-carlo.yaml
ticks_per_day: 100
num_days: 5
seed: 12345  # Vary for Monte Carlo

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0
  liquidity_cost_per_tick_bps: 15

agent_configs:
  - id: BANK_A
    liquidity_pool: 5_000_000
    liquidity_allocation_fraction: 0.5
    # NEW: Per-band arrival functions
    arrival_bands:
      urgent:                             # Rare, large, tight deadlines
        rate_per_tick: 0.1
        amount_distribution:
          type: log_normal
          mean: 1_000_000
          std: 500_000
        deadline_offset:
          min_ticks: 5
          max_ticks: 15
      normal:                             # Common, medium amounts
        rate_per_tick: 2.0
        amount_distribution:
          type: log_normal
          mean: 50_000
          std: 30_000
      low:                                # Frequent, small, flexible
        rate_per_tick: 5.0
        amount_distribution:
          type: log_normal
          mean: 10_000
          std: 8_000

  - id: BANK_B
    liquidity_pool: 5_000_000
    liquidity_allocation_fraction: 0.5
    arrival_bands:
      urgent:
        rate_per_tick: 0.1
        amount_distribution: {type: log_normal, mean: 1_000_000, std: 500_000}
      normal:
        rate_per_tick: 2.0
        amount_distribution: {type: log_normal, mean: 50_000, std: 30_000}
      low:
        rate_per_tick: 5.0
        amount_distribution: {type: log_normal, mean: 10_000, std: 8_000}

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

**Use case**: Run hundreds of simulations with different seeds to analyze:
- Distribution of total costs across different allocation strategies
- Frequency of liquidity crunches when urgent payments arrive
- Optimal allocation fraction under realistic payment patterns

---

### Combined Scenario: Full BIS Model

```yaml
# bis-full-scenario.yaml
ticks_per_day: 3
num_days: 1
seed: 12345

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0
  liquidity_cost_per_tick_bps: 15          # 1.5% opportunity cost

agent_configs:
  - id: FOCAL_BANK
    liquidity_pool: 1_000_000              # $10,000 available
    liquidity_allocation_fraction: 0.5     # Decision variable to optimize
    credit_limit: 0
    policy:
      type: "liquidity_aware"
      target_buffer: 500_000               # Reserve for urgent

  - id: COUNTERPARTY
    opening_balance: 10_000_000            # Passive, large balance
    policy:
      type: "fifo"
    arrival_config:
      rate_per_tick: 0.99                  # 99% chance of incoming payment
      amount_distribution:
        type: "fixed"
        value: 500_000                     # $5,000 expected inflow

scenario_events:
  # Period 1: $5,000 outgoing (normal)
  - event:
      type: custom_transaction_arrival
      from_agent: FOCAL_BANK
      to_agent: COUNTERPARTY
      amount: 500_000
      priority: 5
    schedule:
      tick: 0

  # Period 2: Potential $10,000 urgent payment
  - event:
      type: custom_transaction_arrival
      from_agent: FOCAL_BANK
      to_agent: COUNTERPARTY
      amount: 1_000_000
      priority: 10
    schedule:
      tick: 1

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

---

### Monte Carlo Analysis Workflow

```python
import itertools
from payment_simulator.backends.rust import Orchestrator

# Parameter grid
allocations = [0.0, 0.25, 0.5, 0.75, 1.0]  # Fraction of pool
liquidity_cost_rate = 0.015  # 1.5%

results = []

for alloc_fraction in allocations:
    replication_costs = []

    for seed in range(100):  # 100 replications
        config = load_config("bis-full-scenario.yaml")
        config['seed'] = seed
        config['agent_configs'][0]['liquidity_allocation_fraction'] = alloc_fraction

        orch = Orchestrator.new(config)
        orch.run_to_completion()

        # Get simulation costs
        metrics = orch.get_metrics()
        sim_cost = metrics['agents']['FOCAL_BANK']['total_cost']

        # Add allocation opportunity cost
        pool = config['agent_configs'][0]['liquidity_pool']
        allocated = pool * alloc_fraction
        alloc_cost = allocated * liquidity_cost_rate

        total = sim_cost + alloc_cost
        replication_costs.append(total)

    results.append({
        'allocation_fraction': alloc_fraction,
        'mean_cost': np.mean(replication_costs),
        'std_cost': np.std(replication_costs),
    })

# Find optimal allocation
optimal = min(results, key=lambda x: x['mean_cost'])
print(f"Optimal allocation: {optimal['allocation_fraction']*100}%")
print(f"Expected cost: ${optimal['mean_cost']/100:.2f}")
```

---

## Summary

### What SimCash Can Do Today
- Multi-agent RTGS simulation with configurable agents
- Discrete time matching BIS periods (`ticks_per_day: 2-3`)
- Priority mapping (urgent=8-10, normal=4-7)
- Configurable cost rates
- LSM disable for pure RTGS behavior
- Scenario event injection for deterministic payment patterns
- Deterministic replay for reproducible research

### What Requires Enhancement
1. **Priority-Based Delay Cost Multipliers**: Different delay rates by priority band
2. **Liquidity Pool and Allocation**: Pre-simulation allocation with opportunity cost
3. **Per-Band Arrival Functions**: Different rate/amount distributions per priority band

### Implementation Timeline
1. Enhancement 1 (Priority Costs): Lower complexity, no tick loop changes
2. Enhancement 2 (Liquidity Pool): Higher complexity, adds new tick lifecycle step
3. Enhancement 3 (Per-Band Arrivals): Extends arrival generator, backwards compatible

### Success Criteria
- BIS Scenario 1 runnable with liquidity allocation decisions
- BIS Scenario 2 runnable with priority-differentiated delay costs
- Realistic Monte Carlo with per-band arrival patterns
- Replay identity maintained for all new events

---

## References

- Aldasoro, I. & Desai, A. (2025). "AI agents for cash management in payment systems." BIS Working Papers No. 1310.
- Bech, M.L. & Garratt, R. (2003). "The intraday liquidity management game." Journal of Economic Theory 109(2), 198-219.
- SimCash Documentation: `/docs/research/simcash-rtgs-model.md`
- Implementation Plan: `/docs/plans/bis-model-enhancements-tdd-implementation.md`

---

*Document created: November 2025*
