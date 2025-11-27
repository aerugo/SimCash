# BIS vs SimCash RTGS Model Comparison

## Overview

This document compares the simplified RTGS model from the BIS Working Paper "AI agents for cash management in payment systems" (Aldasoro & Desai, 2025) with the SimCash payment simulator. It provides guidance on configuring SimCash to replicate BIS-style experiments and identifies gaps that would require SimCash enhancements.

---

## Executive Summary

| Aspect | BIS Model | SimCash | Gap Analysis |
|--------|-----------|---------|--------------|
| **Agents** | Single-agent perspective | Multi-agent simulation | ✅ Configurable |
| **Time** | 2-3 discrete periods | Configurable ticks | ✅ Compatible |
| **Priority** | Binary (urgent/normal) | 11 levels (0-10) | ✅ Mappable |
| **Costs** | 3 types (liquidity, delay, borrow) | 6 types | ✅ Configurable |
| **Settlement** | Immediate or queued | RTGS + LSM | ✅ LSM can be disabled |
| **Incoming Payments** | Probabilistic expectations | Deterministic generation | ⚠️ Partial gap |
| **Liquidity Allocation** | Explicit pre-period decision | Fixed opening balance | ⚠️ Enhancement needed |
| **Agent Reasoning** | Probabilistic decision-making | Policy-based rules | ⚠️ Enhancement needed |

**Verdict**: SimCash can approximate BIS scenarios with configuration, but full replication of the BIS decision-making model requires enhancements to support probabilistic reasoning and explicit liquidity allocation decisions.

---

## Detailed Comparison

### 1. Agent Perspective

#### BIS Model
- **Single-agent focus**: One bank makes decisions while other participants are modeled as probabilistic payment sources
- **Information set**: Current liquidity, queue state, probability of incoming/outgoing payments
- **Optimization goal**: Minimize own costs (liquidity + delay + penalties)

#### SimCash
- **Multi-agent simulation**: All N banks are active participants with their own policies
- **Information set**: Each agent sees own balance, queue, policies; no explicit probability model for counterparty behavior
- **Optimization goal**: Each agent minimizes own costs independently

#### Bridging Strategy
```yaml
# Configure SimCash with 2 agents: focal bank + passive counterparty
agent_configs:
  - id: "FOCAL_BANK"  # The agent we analyze (BIS "cash manager")
    opening_balance: 1_000_000  # $10,000 = 1M cents
    policy:
      type: "manual"  # Or custom policy for experiments

  - id: "COUNTERPARTY"  # Represents "other participants"
    opening_balance: 10_000_000  # Large balance (passive)
    policy:
      type: "fifo"  # Simple behavior
```

---

### 2. Time Model

#### BIS Model
- **Periods**: 2-3 discrete decision points
- **Structure**: Pre-period (allocation) → Period 1 → Period 2 → Period 3 (settlement)
- **Horizon**: Single day, few decision points

#### SimCash
- **Ticks**: Configurable discrete time steps (e.g., 100 ticks/day)
- **Structure**: Continuous tick loop with settlement attempts each tick
- **Horizon**: Multiple days possible

#### Bridging Strategy
```yaml
# Match BIS 3-period model
ticks_per_day: 3
num_days: 1

# Tick mapping:
# - Tick 0 = Period 1
# - Tick 1 = Period 2
# - Tick 2 = Period 3 (EOD)
```

---

### 3. Priority System

#### BIS Model
- **Binary**: Urgent vs. non-urgent payments
- **Cost differential**: Urgent has higher delay cost (1.5% vs 1.0%)
- **Behavioral impact**: Agent preserves liquidity for urgent payments

#### SimCash
- **11 levels**: Priority 0-10
- **T2 bands**: Urgent (8-10), Normal (4-7), Low (0-3)
- **Priority escalation**: Optional automatic boost near deadline

#### Bridging Strategy
```yaml
# Map BIS binary priority to SimCash
# - Urgent payments: priority = 10
# - Non-urgent payments: priority = 5

# Disable priority escalation for pure BIS behavior
priority_escalation:
  enabled: false

# Use priority mode for T2-style band processing
priority_mode: true
```

**Transaction generation mapping**:
```yaml
arrival_config:
  priority_distribution:
    type: "discrete"
    values:
      - value: 10  # Urgent
        weight: 0.1
      - value: 5   # Non-urgent
        weight: 0.9
```

---

### 4. Cost Model

#### BIS Model

| Cost Type | Rate | When Applied |
|-----------|------|--------------|
| Liquidity allocation | 1.5% | Pre-period (opportunity cost) |
| Delay (non-urgent) | 1.0% | Per period while queued |
| Delay (urgent) | 1.5% | Per period while queued |
| Emergency borrowing | >1.5% | Period 3 if short |

**Key insight**: BIS costs are percentages of payment amounts, applied per period.

#### SimCash

| Cost Type | Default Rate | Unit |
|-----------|--------------|------|
| Overdraft | 0.001 (1 bp) | Per tick, on negative balance |
| Delay | 0.0001 (0.1 bp) | Per tick, per cent queued |
| Collateral | 0.0002 (0.2 bp) | Per tick, on posted collateral |
| Deadline penalty | $500 | One-time, when deadline missed |
| EOD penalty | $100 | Per unsettled transaction |
| Split friction | $10 | Per split operation |

#### Bridging Strategy

To match BIS cost structure, we need to convert percentages to SimCash basis points:

**BIS → SimCash Cost Mapping**:

```yaml
cost_rates:
  # BIS: 1.5% liquidity cost per period
  # SimCash: overdraft_bps_per_tick × 10000 = percentage per tick
  # For 3 ticks/day: 1.5% / 3 = 0.5% per tick = 50 bps = 0.005
  overdraft_bps_per_tick: 0.005

  # BIS: 1.0% delay cost for non-urgent (per period)
  # SimCash: delay_cost_per_tick_per_cent
  # 1.0% per period = 0.01 / amount, so per cent = 0.01
  # But SimCash formula: cost = amount × rate, so rate = 0.01
  delay_cost_per_tick_per_cent: 0.01

  # BIS: 1.5% delay for urgent = 1.5x non-urgent
  # SimCash: overdue_delay_multiplier (but this is for overdue, not urgent)
  # Need custom handling - see "Gaps" section
  overdue_delay_multiplier: 1.5

  # BIS: Higher borrowing cost at EOD
  # SimCash: EOD penalty (flat fee, not percentage)
  # Approximate: Set high to discourage EOD failures
  eod_penalty_per_transaction: 1_000_000  # $10,000

  # Disable split friction (not in BIS model)
  split_friction_cost: 0

  # Disable deadline penalty (BIS uses delay cost escalation instead)
  deadline_penalty: 0
```

**Gap**: SimCash's delay cost doesn't differentiate by priority - all queued transactions use the same rate. The `overdue_delay_multiplier` applies to transactions past deadline, not urgent transactions.

---

### 5. Settlement Mechanism

#### BIS Model
- **Simple binary**: Transaction either settles (if liquidity available) or waits
- **No LSM**: No bilateral/multilateral offsetting described
- **Recycling**: Incoming payments explicitly replenish available liquidity

#### SimCash
- **RTGS + Queue**: Immediate settlement attempt, then queue if insufficient liquidity
- **LSM**: Bilateral offsetting and multilateral cycle detection
- **Implicit recycling**: Incoming payments increase balance automatically

#### Bridging Strategy
```yaml
# Disable LSM for pure BIS-style behavior
lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

This makes SimCash behave like BIS: transactions either settle immediately or wait in queue until liquidity becomes available through incoming payments.

---

### 6. Incoming Payment Model

#### BIS Model
- **Probabilistic expectations**: "90% chance of receiving $2 payment"
- **Agent reasoning**: Decisions based on expected value of incoming flows
- **Recycling**: Incoming payments can be used for outgoing transactions

**Example from BIS Box 2**:
> "There is a 90% probability that you will receive a $2 payment from another participant in the first period, which can be recycled as liquidity."

#### SimCash
- **Deterministic generation**: Arrivals generated from Poisson process with configured rate
- **No explicit probability model**: Agent policies don't reason about "probability of incoming payment"
- **Automatic balance update**: Incoming settlements increase balance

#### Gap Analysis

This is a **significant conceptual gap**:

| Aspect | BIS | SimCash |
|--------|-----|---------|
| Agent's knowledge | Knows probabilities | Knows current state |
| Decision basis | Expected value calculation | Policy rules |
| Uncertainty | Explicit in decision model | Implicit in simulation |

**Bridging options**:

1. **Scenario-based approximation**: Run multiple SimCash simulations with different incoming payment realizations, analyze focal agent's behavior

2. **Policy enhancement**: Create a custom policy that implements probabilistic reasoning:
   ```python
   # Conceptual policy (not currently supported)
   class BisStylePolicy:
       def evaluate(self, state, expected_inflows):
           prob_inflow = expected_inflows['probability']
           amount_inflow = expected_inflows['amount']
           expected_liquidity = state.balance + prob_inflow * amount_inflow
           # Make decision based on expected liquidity...
   ```

3. **Fixed arrival pattern**: Configure deterministic arrivals that match BIS scenarios:
   ```yaml
   # Counterparty sends payment in tick 0 with 90% chance
   # Approximate by running 10 simulations, 9 with arrival, 1 without
   scenario_events:
     - tick: 0
       event_type: "inject_transaction"
       sender: "COUNTERPARTY"
       receiver: "FOCAL_BANK"
       amount: 200  # $2 = 200 cents
   ```

---

### 7. Liquidity Allocation Decision

#### BIS Model
- **Explicit pre-period decision**: "How much initial liquidity to allocate at 1.5% cost?"
- **Trade-off**: Higher allocation → lower delay risk, higher opportunity cost
- **Dynamic**: Agent chooses allocation based on expected payments

**Example from BIS Box 3**:
> "Before the first period you need to allocate liquidity at cost of 1.5%."

#### SimCash
- **Fixed opening balance**: Configured at simulation start, not a decision
- **No allocation cost**: Balance exists at no explicit cost (overdraft has cost when negative)
- **Collateral decision**: Agent can post/withdraw collateral, but this is reactive, not pre-planned

#### Gap Analysis

This is a **fundamental modeling difference**:

| Aspect | BIS | SimCash |
|--------|-----|---------|
| Initial liquidity | Decision variable | Configuration parameter |
| Allocation cost | Explicit (1.5%) | Implicit (collateral opportunity cost) |
| Timing | Pre-simulation | Start of each day |

**Bridging options**:

1. **Multi-run analysis**: Run SimCash with different `opening_balance` values, compute total costs, find optimal allocation
   ```python
   results = []
   for allocation in [500, 1000, 1500, 2000]:  # Test different allocations
       config['agent_configs'][0]['opening_balance'] = allocation
       sim = run_simulation(config)
       # Add allocation cost: allocation × 0.015
       total_cost = sim.costs['FOCAL_BANK'] + allocation * 0.015
       results.append((allocation, total_cost))
   optimal = min(results, key=lambda x: x[1])
   ```

2. **Policy-based allocation** (enhancement needed): Add policy hook for start-of-day liquidity decision
   ```yaml
   # Proposed enhancement
   agent_configs:
     - id: "FOCAL_BANK"
       liquidity_allocation:
         type: "decision"  # Agent decides
         cost_rate: 0.015  # 1.5% opportunity cost
         min_allocation: 0
         max_allocation: 10000
   ```

---

## Running BIS Scenarios in SimCash

### Scenario 1: Precautionary Decision

**BIS Setup**:
- Liquidity limit: $10
- Queue: Two $1 payments pending
- Potential urgent $10 payment next period

**SimCash Configuration**:

```yaml
# bis_scenario_1.yaml
ticks_per_day: 2
num_days: 1
rng_seed: 12345

agent_configs:
  - id: "FOCAL_BANK"
    opening_balance: 1000  # $10 = 1000 cents
    credit_limit: 0
    policy:
      type: "liquidity_aware"
      target_buffer: 1000  # Preserve for urgent payment
      urgency_threshold: 1

  - id: "COUNTERPARTY"
    opening_balance: 100000
    policy:
      type: "fifo"

# Pre-inject the two $1 payments in queue
scenario_events:
  - tick: 0
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 100  # $1
    priority: 5
    deadline: 2

  - tick: 0
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 100  # $1
    priority: 5
    deadline: 2

  # Potential urgent payment (inject with 50% scenarios)
  - tick: 1
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 1000  # $10
    priority: 10  # Urgent
    deadline: 2

cost_rates:
  overdraft_bps_per_tick: 0.005
  delay_cost_per_tick_per_cent: 0.01
  eod_penalty_per_transaction: 100000

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

**Expected Behavior**: With `liquidity_aware` policy and `target_buffer: 1000`, the agent should hold the $1 payments to preserve liquidity for the potential $10 urgent payment.

---

### Scenario 2: Navigating Priorities

**BIS Setup**:
- Liquidity limit: $10
- Queue: $1 and $2 payments pending
- 90% chance of receiving $2 (recyclable)
- 50% chance of urgent $10 payment in period 2

**SimCash Configuration**:

```yaml
# bis_scenario_2.yaml
ticks_per_day: 2
num_days: 1
rng_seed: 12345

agent_configs:
  - id: "FOCAL_BANK"
    opening_balance: 1000  # $10
    credit_limit: 0
    policy:
      type: "priority_deadline"  # Process by priority, then deadline

  - id: "COUNTERPARTY"
    opening_balance: 100000
    policy:
      type: "fifo"
    # Generate incoming payment (simulating 90% probability)
    arrival_config:
      rate_per_tick: 0.9  # 90% chance per tick
      amount_distribution:
        type: "fixed"
        value: 200  # $2
      receiver_weights:
        FOCAL_BANK: 1.0

scenario_events:
  # Queue $1 payment (non-urgent)
  - tick: 0
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 100  # $1
    priority: 5
    deadline: 2

  # Queue $2 payment (non-urgent)
  - tick: 0
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 200  # $2
    priority: 5
    deadline: 2

  # Potential urgent payment in period 2 (50% scenario)
  - tick: 1
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 1000  # $10
    priority: 10
    deadline: 2

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  eod_penalty_per_transaction: 100000

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

**Limitation**: SimCash's policy doesn't reason about the 90% probability of incoming payment. The arrival is either generated or not based on RNG. To fully replicate BIS behavior, run multiple simulations and analyze aggregate behavior.

---

### Scenario 3: Liquidity-Delay Trade-off

**BIS Setup**:
- Pre-period: Allocate liquidity at 1.5% cost
- Period 1: $5 payment (1% delay), 99% chance of $5 inflow
- Period 2: 90% chance of urgent $10 (1.5% delay), 99% chance of $5 inflow
- Period 3: Clear queue, borrow at >1.5% if needed

**SimCash Approximation**:

```yaml
# bis_scenario_3.yaml
ticks_per_day: 3
num_days: 1
rng_seed: 12345

agent_configs:
  - id: "FOCAL_BANK"
    # Test different allocations: 0, 500, 1000, 1500
    opening_balance: 500  # $5 allocation (optimal per BIS)
    credit_limit: 0
    policy:
      type: "fifo"

  - id: "COUNTERPARTY"
    opening_balance: 1000000
    policy:
      type: "fifo"
    arrival_config:
      rate_per_tick: 0.99  # 99% chance of incoming
      amount_distribution:
        type: "fixed"
        value: 500  # $5
      receiver_weights:
        FOCAL_BANK: 1.0

scenario_events:
  # $5 payment in period 1
  - tick: 0
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 500
    priority: 5
    deadline: 3

  # Potential $10 urgent payment in period 2 (90% scenario)
  - tick: 1
    event_type: "inject_transaction"
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 1000
    priority: 10
    deadline: 3

cost_rates:
  overdraft_bps_per_tick: 0.005  # ~1.5%/3
  delay_cost_per_tick_per_cent: 0.01
  eod_penalty_per_transaction: 500000  # High EOD borrowing cost

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

**Multi-run analysis required**:
```python
# Python analysis script
allocations = [0, 250, 500, 750, 1000, 1500]
allocation_cost_rate = 0.015  # 1.5%

for alloc in allocations:
    config['agent_configs'][0]['opening_balance'] = alloc
    results = run_simulation(config)

    sim_costs = results.get_agent_costs('FOCAL_BANK')
    allocation_cost = alloc * allocation_cost_rate
    total_cost = sim_costs['total'] + allocation_cost

    print(f"Allocation ${alloc/100}: Sim cost ${sim_costs['total']/100}, "
          f"Alloc cost ${allocation_cost/100}, Total ${total_cost/100}")
```

---

## Proposed SimCash Enhancements

To fully support BIS-style experiments, the following enhancements are recommended:

### Enhancement 1: Priority-Based Delay Costs

**Current behavior**: All queued transactions incur the same delay cost rate.

**Proposed change**: Allow delay cost to vary by priority.

```rust
// backend/src/orchestrator/engine.rs

pub struct CostRates {
    // ... existing fields ...

    /// Delay cost multipliers by priority band
    /// Maps priority threshold to multiplier
    /// e.g., [(8, 1.5), (4, 1.0)] means:
    ///   - Priority 8-10: 1.5x delay cost
    ///   - Priority 4-7: 1.0x delay cost
    ///   - Priority 0-3: 1.0x delay cost (default)
    pub priority_delay_multipliers: Vec<(u8, f64)>,
}
```

**Configuration**:
```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01  # Base: 1%
  priority_delay_multipliers:
    - [8, 1.5]   # Urgent (8-10): 1.5%
    - [4, 1.0]   # Normal (4-7): 1.0%
    # Low (0-3): uses base rate
```

### Enhancement 2: Liquidity Allocation Decision

**Current behavior**: `opening_balance` is a fixed configuration parameter.

**Proposed change**: Add pre-simulation liquidity allocation as a policy decision.

```rust
// backend/src/orchestrator/engine.rs

pub struct AgentConfig {
    // ... existing fields ...

    /// Liquidity allocation configuration (optional)
    /// If present, agent decides initial liquidity instead of using opening_balance
    pub liquidity_allocation: Option<LiquidityAllocationConfig>,
}

pub struct LiquidityAllocationConfig {
    /// Cost rate for allocated liquidity (e.g., 0.015 = 1.5%)
    pub cost_rate: f64,

    /// Minimum allocation allowed
    pub min_allocation: i64,

    /// Maximum allocation allowed
    pub max_allocation: i64,

    /// Allocation strategy
    pub strategy: AllocationStrategy,
}

pub enum AllocationStrategy {
    /// Fixed allocation amount
    Fixed { amount: i64 },

    /// Policy-driven decision based on expected payments
    PolicyDriven,

    /// Grid search to find optimal (for analysis)
    GridSearch { step_size: i64 },
}
```

### Enhancement 3: Probabilistic Reasoning for Policies

**Current behavior**: Policies make decisions based on current state, not probabilistic expectations.

**Proposed change**: Add expected value calculations to policy context.

```rust
// backend/src/policy/context.rs

pub struct PolicyContext {
    // ... existing fields ...

    /// Expected incoming payments this tick
    /// Based on counterparty arrival configurations
    pub expected_inflows: Vec<ExpectedPayment>,

    /// Expected outgoing payment requests
    pub expected_outflows: Vec<ExpectedPayment>,
}

pub struct ExpectedPayment {
    pub counterparty: String,
    pub amount: i64,
    pub probability: f64,
    pub priority: Option<u8>,
}
```

**Policy implementation**:
```rust
impl Policy for BisStylePolicy {
    fn evaluate(&self, ctx: &PolicyContext) -> Vec<PolicyDecision> {
        let current_liquidity = ctx.balance + ctx.credit_available;

        // Calculate expected liquidity after probable inflows
        let expected_inflow: f64 = ctx.expected_inflows.iter()
            .map(|p| p.amount as f64 * p.probability)
            .sum();

        let expected_liquidity = current_liquidity as f64 + expected_inflow;

        // Reserve for potential urgent payments
        let urgent_reserve: f64 = ctx.expected_outflows.iter()
            .filter(|p| p.priority.unwrap_or(0) >= 8)
            .map(|p| p.amount as f64 * p.probability)
            .sum();

        // Make decisions based on expected values
        // ...
    }
}
```

### Enhancement 4: Scenario Probability Annotations

**Current behavior**: Scenario events are deterministic (always execute at specified tick).

**Proposed change**: Add probability to scenario events for Monte Carlo analysis.

```yaml
# Proposed configuration
scenario_events:
  - tick: 1
    event_type: "inject_transaction"
    probability: 0.5  # NEW: 50% chance of this event
    sender: "FOCAL_BANK"
    receiver: "COUNTERPARTY"
    amount: 1000
```

**Implementation**: When `probability < 1.0`, SimCash would:
1. Sample from RNG to decide if event fires
2. In analysis mode, run multiple replications automatically
3. Report statistics across probability-weighted outcomes

---

## Recommended Workflow for BIS-Style Analysis

### Step 1: Configure Base Scenario

```yaml
# bis_experiment.yaml
ticks_per_day: 3  # Match BIS periods
num_days: 1
rng_seed: 12345

agent_configs:
  - id: "FOCAL_BANK"
    opening_balance: 1000  # Will vary
    credit_limit: 0
    policy:
      type: "custom"
      config: "bis_style"

lsm_config:
  enable_bilateral: false
  enable_cycles: false
```

### Step 2: Run Monte Carlo Analysis

```python
import itertools
from payment_simulator import Orchestrator

# Parameter grid
allocations = [0, 500, 1000, 1500, 2000]
urgent_probs = [0.0, 0.5, 0.9]
inflow_probs = [0.5, 0.9, 0.99]

results = []

for alloc, urgent_p, inflow_p in itertools.product(allocations, urgent_probs, inflow_probs):
    # Run N replications for stochastic scenarios
    replication_costs = []

    for seed in range(100):  # 100 replications
        config = load_config("bis_experiment.yaml")
        config['rng_seed'] = seed
        config['agent_configs'][0]['opening_balance'] = alloc

        # Inject events based on probabilities
        if random.random() < urgent_p:
            inject_urgent_payment(config, tick=1, amount=1000)
        if random.random() < inflow_p:
            inject_incoming_payment(config, tick=0, amount=500)

        orch = Orchestrator.new(config)
        orch.run_to_completion()

        sim_cost = orch.get_agent_accumulated_costs("FOCAL_BANK")['total']
        alloc_cost = alloc * 0.015  # 1.5% allocation cost
        total = sim_cost + alloc_cost
        replication_costs.append(total)

    results.append({
        'allocation': alloc,
        'urgent_prob': urgent_p,
        'inflow_prob': inflow_p,
        'mean_cost': np.mean(replication_costs),
        'std_cost': np.std(replication_costs),
    })

# Find optimal allocation for each scenario
df = pd.DataFrame(results)
optimal = df.loc[df.groupby(['urgent_prob', 'inflow_prob'])['mean_cost'].idxmin()]
print(optimal)
```

### Step 3: Compare with BIS Results

| Scenario | BIS Optimal | SimCash Optimal | Match? |
|----------|-------------|-----------------|--------|
| Box 1: Precautionary | Hold $1 payments | TBD | |
| Box 2: Navigate priorities | Process $1 only | TBD | |
| Box 3: Trade-off | Allocate $5 | TBD | |

---

## Summary

### What Works Today

1. **Multi-agent simulation** with focal bank analysis
2. **Discrete time** matching BIS periods
3. **Priority mapping** (urgent=10, normal=5)
4. **Cost rate configuration** (with some approximation)
5. **LSM disable** for pure RTGS behavior
6. **Scenario injection** for deterministic payment patterns

### What Requires Workarounds

1. **Probabilistic scenarios**: Run multiple simulations, aggregate results
2. **Liquidity allocation decision**: Test multiple `opening_balance` values, compute optimal
3. **Priority-based delay costs**: Use `overdue_delay_multiplier` as approximation

### What Requires Enhancements

1. **Priority-based delay cost multipliers**: Different delay rates by priority
2. **Explicit liquidity allocation decision**: Pre-simulation allocation with cost
3. **Probabilistic policy reasoning**: Expected value calculations in policy context
4. **Probabilistic scenario events**: Automatic Monte Carlo with probability-weighted events

---

## References

- BIS Working Paper 1310: "AI agents for cash management in payment systems"
- SimCash documentation: `/docs/research/simcash-rtgs-model.md`
- BIS model summary: `/docs/research/bis-ai-cash-management-rtgs-model.md`

---

*Document created: November 2025*
