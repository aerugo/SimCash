# Research Proposal: Replicating Castro et al. (2025) Using LLM Policy Iteration in SimCash

**Version**: 1.0
**Date**: 2025-11-30
**Status**: Proposal

---

## Abstract

This research proposal outlines an experimental approach to replicate and extend the findings of Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" using SimCash with Large Language Model (LLM) policy iteration instead of traditional RL. Where Castro et al. use REINFORCE to learn neural network policies, we propose using a high-powered reasoning LLM to iteratively refine human-readable JSON decision tree policies based on simulation outcomes.

This approach offers several potential advantages:
1. **Interpretability**: JSON decision trees are fully explainable to regulators
2. **Sample efficiency**: LLMs can reason about cost trade-offs without millions of episodes
3. **Transferability**: Discovered policies are portable across scenarios
4. **Human-AI collaboration**: Policy structures can be seeded with domain expertise

---

## 1. Castro et al. (2025) Summary

### 1.1 Research Questions

Castro et al. address two fundamental bank decisions in High-Value Payment Systems (HVPS):

1. **Initial liquidity decision**: What fraction $x_0 \in [0,1]$ of available collateral $B$ to allocate as initial liquidity $\ell_0 = x_0 \cdot B$?
2. **Intraday payment timing**: What fraction $x_t \in [0,1]$ of payment demands $P_t$ to release in each period?

### 1.2 Environment Model

| Component | Castro et al. Model | SimCash Mapping |
|-----------|---------------------|-----------------|
| Time structure | $T$ discrete periods per day | `ticks_per_day` configuration |
| Agents | 2 banks with bilateral flows | 2-agent configuration |
| Payment arrivals | Exogenous $P_t$ per period | `arrival_config` with Poisson rate |
| Incoming payments | $R_t$ from other bank's releases | RTGS settlement mechanics |
| Settlement | RTGS (immediate if liquid) | Queue 2 RTGS engine |

### 1.3 Cost Structure

Castro et al. define three costs:

| Cost Type | Formula | SimCash Equivalent |
|-----------|---------|-------------------|
| Initial liquidity | $r_c \cdot \ell_0$ | `collateral_cost_per_tick_bps` |
| Delay penalty | $r_d \cdot P_t(1-x_t)$ per period | `delay_penalty_per_tick` |
| EOD borrowing | $r_b \cdot c_b$ where $c_b$ is shortfall | `eod_unsettled_penalty` |

**Baseline parameters**: $r_c = 0.1$, $r_d = 0.2$, $r_b = 0.4$

### 1.4 Key Results

1. **2-Period Analytical Solution**: Nash equilibrium exists and is unique
   - Best response: $\ell_0^i = P_1^i + \max(P_2^i - \min(\ell_0^{-i}, P_1^{-i}), 0)$

2. **RL Convergence**: REINFORCE agents converge to near-optimal policies within 50-100 episodes

3. **Delay Cost Sensitivity**: When $r_d < r_c$, agents delay more; when $r_d > r_c$, agents front-load liquidity

4. **Joint Learning**: Agents successfully learn both initial liquidity and intraday timing simultaneously

---

## 2. Mapping Castro et al. to SimCash

### 2.1 Conceptual Alignment

| Castro Concept | SimCash Implementation |
|----------------|------------------------|
| Initial liquidity $\ell_0$ | `opening_balance` + optional collateral posting via `strategic_collateral_tree` |
| Payment demand $P_t$ | Transaction arrivals via `arrival_config` with Poisson rate |
| Payment release fraction $x_t$ | `payment_tree` decisions: Release vs Hold |
| Incoming payments $R_t$ | Settlements from counterparty (automatic RTGS) |
| Liquidity constraint $P_t x_t \le \ell_{t-1}$ | `effective_liquidity >= remaining_amount` check |
| End-of-day borrowing $c_b$ | Transactions unsettled at EOD (penalty) |

### 2.2 Key Differences

| Aspect | Castro et al. | SimCash |
|--------|---------------|---------|
| Decision granularity | Continuous $x_t \in [0,1]$ | Binary Release/Hold per transaction |
| LSM | Not modeled | Available (can be disabled) |
| Priority system | Not modeled | RTGS priority levels available |
| Collateral dynamics | Static initial allocation | Dynamic posting/withdrawal |
| Credit limits | Implicit in borrowing | Explicit overdraft caps |

### 2.3 Alignment Strategy

To closely replicate Castro et al., we configure SimCash as follows:

```yaml
# Disable advanced features not in Castro model
lsm:
  enabled: false                    # No liquidity-saving mechanisms

policy_feature_toggles:
  include:
    - PaymentAction                 # Only Release/Hold
    - TransactionField              # amount, deadline, priority
    - AgentField                    # balance, effective_liquidity
    - TimeField                     # current_tick, ticks_to_deadline
    - CostField                     # cost rates for optimization
    - ComparisonOperator
    - LogicalOperator
    - BinaryArithmetic
```

**Divisible Transactions**: Castro et al. assume continuous $x_t$ (divisible payments). SimCash supports this via the `divisible: true` flag and splitting policies. However, for closer alignment, we treat this as a per-transaction binary decision, which approximates the continuous case when many small transactions are present.

---

## 3. Experimental Design

### 3.1 Scenario Specifications

#### Experiment 1: Two-Period Fixed Payments (Validation)

Replicates Castro et al. Section 6.3 with known payment demands.

```yaml
# castro_2period.yaml
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42

costs:
  collateral_cost_per_tick_bps: 1000.0   # r_c = 0.1 (10% per tick)
  delay_penalty_per_tick: 2000           # r_d = 0.2 equivalent
  eod_unsettled_penalty: 400000          # r_b = 0.4 equivalent
  overdraft_cost_bps: 0.0                # Not in Castro model
  deadline_penalty: 0                     # Simplified to EOD only
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0

lsm:
  enabled: false

agents:
  - id: BANK_A
    opening_balance: 0                   # Initial liquidity = 0 (to be optimized)
    max_collateral_capacity: 100000000   # Sufficient for any allocation
    policy:
      type: FromJson
      json_path: "policies/llm_castro_a.json"
    # Fixed payment profile: P^A = [0, 15000] (period 1: $0, period 2: $150)
    scenario_events:
      - type: TransactionInjection
        tick: 1
        transactions:
          - sender: BANK_A
            receiver: BANK_B
            amount: 15000
            deadline_tick: 2
            priority: 5

  - id: BANK_B
    opening_balance: 0
    max_collateral_capacity: 100000000
    policy:
      type: FromJson
      json_path: "policies/llm_castro_b.json"
    # Fixed payment profile: P^B = [15000, 5000] (period 1: $150, period 2: $50)
    scenario_events:
      - type: TransactionInjection
        tick: 0
        transactions:
          - sender: BANK_B
            receiver: BANK_A
            amount: 15000
            deadline_tick: 1
            priority: 5
      - type: TransactionInjection
        tick: 1
        transactions:
          - sender: BANK_B
            receiver: BANK_A
            amount: 5000
            deadline_tick: 2
            priority: 5
```

**Expected Equilibrium** (from Castro et al.):
- Bank A: $\ell_0^A = 0$ (waits for incoming from B)
- Bank B: $\ell_0^B = 20000$ (covers both periods)
- Costs: $R_A = 0$, $R_B = 2000$

#### Experiment 2: Twelve-Period with LVTS-Style Profiles

Replicates Castro et al. Section 6.4 with realistic payment distributions.

```yaml
# castro_12period.yaml
simulation:
  ticks_per_day: 12
  num_days: 1
  rng_seed: 42

costs:
  collateral_cost_per_tick_bps: 83.3     # r_c = 0.1 / 12 ticks
  delay_penalty_per_tick: 167            # r_d = 0.2 / 12 ticks
  eod_unsettled_penalty: 400000          # r_b = 0.4 equivalent
  overdraft_cost_bps: 0.0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0

lsm:
  enabled: false

agents:
  - id: BANK_A
    opening_balance: 0                   # To be optimized
    max_collateral_capacity: 100000000
    policy:
      type: FromJson
      json_path: "policies/llm_castro_a.json"
    arrival_config:
      rate_per_tick: 0.5                 # ~6 transactions/day
      amount_distribution:
        type: LogNormal
        mean: 11.51                      # ~$100k median
        std_dev: 0.9
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [3, 8]             # 3-8 ticks to deadline
      priority: 5
      divisible: false

  - id: BANK_B
    opening_balance: 0
    max_collateral_capacity: 100000000
    policy:
      type: FromJson
      json_path: "policies/llm_castro_b.json"
    arrival_config:
      rate_per_tick: 0.65                # Higher volume (asymmetric)
      amount_distribution:
        type: LogNormal
        mean: 11.8                       # ~$120k median
        std_dev: 1.0
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [2, 6]             # Tighter deadlines
      priority: 5
      divisible: false
```

#### Experiment 3: Joint Initial Liquidity + Intraday Timing

Replicates Castro et al. Section 7 with both decisions.

```yaml
# castro_joint_3period.yaml
simulation:
  ticks_per_day: 3
  num_days: 1
  rng_seed: 42

costs:
  collateral_cost_per_tick_bps: 333.3    # r_c = 0.1 / 3 ticks
  delay_penalty_per_tick: 667            # r_d = 0.2 / 3 ticks
  eod_unsettled_penalty: 400000
  overdraft_cost_bps: 0.0
  deadline_penalty: 0
  split_friction_cost: 0
  overdue_delay_multiplier: 1.0

lsm:
  enabled: false

agents:
  - id: BANK_A
    opening_balance: 0
    max_collateral_capacity: 100000000
    policy:
      type: FromJson
      json_path: "policies/llm_castro_joint.json"
    # Symmetric payment profile: P = [20000, 20000, 0]
    scenario_events:
      - type: TransactionInjection
        tick: 0
        transactions:
          - sender: BANK_A
            receiver: BANK_B
            amount: 20000
            deadline_tick: 1
            priority: 5
      - type: TransactionInjection
        tick: 1
        transactions:
          - sender: BANK_A
            receiver: BANK_B
            amount: 20000
            deadline_tick: 2
            priority: 5

  - id: BANK_B
    opening_balance: 0
    max_collateral_capacity: 100000000
    policy:
      type: FromJson
      json_path: "policies/llm_castro_joint.json"
    scenario_events:
      - type: TransactionInjection
        tick: 0
        transactions:
          - sender: BANK_B
            receiver: BANK_A
            amount: 20000
            deadline_tick: 1
            priority: 5
      - type: TransactionInjection
        tick: 1
        transactions:
          - sender: BANK_B
            receiver: BANK_A
            amount: 20000
            deadline_tick: 2
            priority: 5
```

### 3.2 Policy Structure for LLM Optimization

The LLM will optimize both **parameters** and **tree structure** of JSON policies.

#### Initial Liquidity Policy (via `strategic_collateral_tree`)

```json
{
  "version": "1.0",
  "policy_id": "castro_initial_liquidity",
  "description": "LLM-optimized initial liquidity allocation",
  "parameters": {
    "initial_liquidity_fraction": 0.5,
    "period1_coverage_factor": 1.0,
    "expected_inflow_discount": 0.8
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "tick_zero_check",
    "description": "Only allocate at start of day",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "post_initial",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        },
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "hold_later",
      "action": "HoldCollateral"
    }
  }
}
```

#### Intraday Payment Policy (via `payment_tree`)

```json
{
  "version": "1.0",
  "policy_id": "castro_intraday_timing",
  "description": "LLM-optimized payment release timing",
  "parameters": {
    "urgency_threshold": 3.0,
    "liquidity_buffer_fraction": 0.2
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "check_urgent",
    "description": "Release if deadline approaching",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "check_affordable",
      "description": "Release if sufficient buffer",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {
              "compute": {
                "op": "+",
                "left": {"value": 1.0},
                "right": {"param": "liquidity_buffer_fraction"}
              }
            }
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "release_affordable",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "hold",
        "action": "Hold"
      }
    }
  }
}
```

---

## 4. LLM Optimization Protocol

### 4.1 System Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    LLM Policy Iteration Loop                               │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────────────────────┐│
│  │ Castro      │───▶│ SimCash      │───▶│ Scenario YAML + Policy JSON    ││
│  │ Scenario    │    │ Config Gen   │    │ (Seed policy from heuristic)   ││
│  └─────────────┘    └──────────────┘    └───────────────┬────────────────┘│
│                                                         │                  │
│                                         ┌───────────────▼───────────────┐  │
│  ┌─────────────────────────────────────▶│  SimCash Simulation            │  │
│  │                                      │  (Multiple seeds: 1-10)        │  │
│  │                                      └───────────────┬───────────────┘  │
│  │                                                      │                  │
│  │  ┌────────────────────────────────┐  ┌───────────────▼───────────────┐  │
│  │  │  Updated Policy JSON           │  │  Cost Breakdown per Agent     │  │
│  │  │  (Parameters + Structure)      │◀─┤  - Collateral cost            │  │
│  │  └──────────────┬─────────────────┘  │  - Delay cost                 │  │
│  │                 │                    │  - EOD penalty                │  │
│  │  ┌──────────────▼─────────────────┐  │  - Settlement rate            │  │
│  │  │  validate-policy               │  └───────────────┬───────────────┘  │
│  │  │  --scenario castro.yaml        │                  │                  │
│  │  └──────────────┬─────────────────┘  ┌───────────────▼───────────────┐  │
│  │                 │                    │  Context Builder              │  │
│  │          ┌──────▼───────┐            │  + Schema Docs                │  │
│  │          │  Valid?      │            │  + Cost Analysis              │  │
│  │          └──────┬───────┘            │  + Iteration History          │  │
│  │                 │                    └───────────────┬───────────────┘  │
│  │          ┌──────▼───────────────────────────────────▼───────────────┐  │
│  └──────────│              Reasoning LLM (Claude Opus / GPT-4)          │  │
│             │  "Analyze costs, propose better policy, output JSON"      │  │
│             └───────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Prompt Template

```markdown
# SimCash Castro Replication - Iteration {iteration}

## Context
You are replicating the RL-based policy learning from Castro et al. (2025)
"Estimating Policy Functions in Payment Systems Using Reinforcement Learning."
Instead of gradient descent, you will reason about cost trade-offs and propose
improved policies.

## Castro et al. Model Summary
- Two banks exchange payments over {T} periods
- Each bank chooses:
  1. Initial liquidity ℓ₀ (fraction of collateral to allocate)
  2. Payment timing xₜ (fraction of payments to release each period)
- Costs:
  - Collateral cost: rᴄ × ℓ₀ (opportunity cost of posting)
  - Delay cost: rᴅ × Pₜ(1-xₜ) (penalty for holding payments)
  - EOD borrowing: rᵦ × shortfall (if insufficient liquidity at day end)
- Key insight: Waiting allows incoming payments to provide liquidity,
  but delay costs accumulate

## Cost Parameters in This Scenario
- rᴄ (collateral): {r_c} per tick
- rᴅ (delay): {r_d} per tick per cent
- rᵦ (EOD): {r_b} per unsettled transaction

## Available Policy Elements

### For Initial Liquidity (strategic_collateral_tree)
Actions: PostCollateral, HoldCollateral
Key Fields: system_tick_in_day, max_collateral_capacity, queue1_total_value

### For Payment Timing (payment_tree)
Actions: Release, Hold
Key Fields: ticks_to_deadline, effective_liquidity, remaining_amount,
            balance, day_progress_fraction

## Current Policies

### Bank A Policy
```json
{current_policy_a}
```

### Bank B Policy
```json
{current_policy_b}
```

## Simulation Results (Seeds 1-10)

### Cost Breakdown
| Agent | Total Cost | Collateral | Delay | EOD Penalty | Settlement Rate |
|-------|------------|------------|-------|-------------|-----------------|
| BANK_A | ${cost_a_mean} ± ${cost_a_std} | ${coll_a} | ${delay_a} | ${eod_a} | {rate_a}% |
| BANK_B | ${cost_b_mean} ± ${cost_b_std} | ${coll_b} | ${delay_b} | ${eod_b} | {rate_b}% |
| SYSTEM | ${total_mean} ± ${total_std} | ${coll_total} | ${delay_total} | ${eod_total} | {rate_total}% |

### Liquidity Dynamics
- Bank A: Average opening balance ${open_a}, End-of-day ${eod_bal_a}
- Bank B: Average opening balance ${open_b}, End-of-day ${eod_bal_b}
- Average incoming payments per tick: Bank A ${incoming_a}, Bank B ${incoming_b}

## Iteration History
| Iter | System Cost | Bank A Cost | Bank B Cost | Key Change |
|------|-------------|-------------|-------------|------------|
{history_table}

## Analysis Prompt
1. **Identify cost drivers**: Which cost component dominates? Why?
2. **Evaluate liquidity strategy**: Are banks over-allocating or under-allocating?
3. **Assess timing trade-off**: Are banks releasing too early (overdraft) or too late (delay)?
4. **Consider strategic interaction**: How does one bank's behavior affect the other?
5. **Propose improvements**: Modify parameters and/or tree structure

## Output Format
Provide:
1. Analysis (2-3 paragraphs)
2. Complete updated policy JSON for Bank A
3. Complete updated policy JSON for Bank B
4. Expected improvement and rationale
```

### 4.3 Optimization Algorithm

```python
class CastroPolicyOptimizer:
    """LLM-based policy optimizer replicating Castro et al. setup."""

    def __init__(
        self,
        scenario_path: str,
        llm_client: LLMClient,
        num_seeds: int = 10,
        max_iterations: int = 25
    ):
        self.scenario_path = scenario_path
        self.llm = llm_client
        self.num_seeds = num_seeds
        self.max_iterations = max_iterations
        self.history: list[IterationResult] = []

    def run_simulations(
        self,
        policy_a: dict,
        policy_b: dict,
        seeds: list[int]
    ) -> AggregatedMetrics:
        """Run simulations with policies across multiple seeds."""
        all_results = []

        for seed in seeds:
            # Write temporary policy files
            write_policy("llm_castro_a.json", policy_a)
            write_policy("llm_castro_b.json", policy_b)

            # Run simulation
            result = run_simcash(
                scenario=self.scenario_path,
                seed=seed,
                quiet=True
            )

            all_results.append(self.extract_metrics(result))

        return self.aggregate_metrics(all_results)

    def extract_metrics(self, result: SimResult) -> Metrics:
        """Extract Castro-relevant metrics from simulation."""
        return Metrics(
            bank_a=AgentMetrics(
                total_cost=result.costs["BANK_A"]["total"],
                collateral_cost=result.costs["BANK_A"]["collateral"],
                delay_cost=result.costs["BANK_A"]["delay"],
                eod_penalty=result.costs["BANK_A"]["eod"],
                settlement_rate=result.settlement_rate["BANK_A"],
                avg_opening_balance=result.balances["BANK_A"]["opening"],
                avg_incoming_per_tick=result.flows["BANK_A"]["incoming"]
            ),
            bank_b=AgentMetrics(...),
            system=SystemMetrics(
                total_cost=sum_costs,
                gridlock_ticks=result.gridlock_events
            )
        )

    def iterate(self) -> tuple[dict, dict]:
        """Run one iteration of policy optimization."""
        current_a = self.history[-1].policy_a if self.history else self.seed_policy()
        current_b = self.history[-1].policy_b if self.history else self.seed_policy()

        # Evaluate current policies
        metrics = self.run_simulations(
            current_a, current_b,
            seeds=list(range(1, self.num_seeds + 1))
        )

        # Build prompt with context
        prompt = self.build_prompt(current_a, current_b, metrics)

        # Get LLM response
        response = self.llm.generate(
            prompt,
            model="claude-opus-4-20250514",  # High-powered reasoning
            max_tokens=8000
        )

        # Parse new policies
        new_a, new_b = self.parse_policies(response)

        # Validate against feature toggles
        for policy, name in [(new_a, "A"), (new_b, "B")]:
            validation = validate_policy(policy, self.scenario_path)
            if not validation.valid:
                # Retry with error feedback
                retry_response = self.llm.generate(
                    self.build_retry_prompt(name, validation.errors)
                )
                if name == "A":
                    new_a = self.parse_single_policy(retry_response)
                else:
                    new_b = self.parse_single_policy(retry_response)

        self.history.append(IterationResult(
            iteration=len(self.history),
            policy_a=new_a,
            policy_b=new_b,
            metrics=metrics,
            llm_analysis=response
        ))

        return new_a, new_b

    def run_optimization(self) -> OptimizationResult:
        """Run full optimization loop."""
        for i in range(self.max_iterations):
            print(f"Iteration {i+1}/{self.max_iterations}")

            policy_a, policy_b = self.iterate()

            # Check convergence (cost change < 1% for 3 iterations)
            if self.has_converged():
                print(f"Converged at iteration {i+1}")
                break

        return OptimizationResult(
            best_policy_a=self.best_policy_a(),
            best_policy_b=self.best_policy_b(),
            history=self.history,
            convergence_iteration=len(self.history)
        )
```

---

## 5. Baselines and Evaluation

### 5.1 Baselines from Castro et al.

| Baseline | Initial Liquidity | Intraday Timing | Expected Behavior |
|----------|-------------------|-----------------|-------------------|
| Full liquidity | $\ell_0 = B$ (100%) | Release all immediately | High collateral cost, zero delay |
| Zero liquidity | $\ell_0 = 0$ | Hold until counterparty sends | High delay/EOD cost, gridlock risk |
| Period-1 coverage | $\ell_0 = P_1$ | Release as liquidity allows | Moderate both costs |
| Nash equilibrium | Computed analytically | Optimal given opponent | Theoretical minimum |

### 5.2 Additional Baselines

| Baseline | Description |
|----------|-------------|
| Grid search | Sweep `urgency_threshold` [1-10] × `buffer_fraction` [0-0.5] |
| Random search | 100 random parameter combinations |
| FIFO policy | SimCash built-in immediate release |
| LiquidityAware | SimCash built-in with target buffer |

### 5.3 Evaluation Metrics

#### Primary (Castro-aligned)
1. **Total system cost** (lower is better)
2. **Individual agent costs** (measure fairness)
3. **Convergence speed** (iterations to stable policy)

#### Secondary
1. **Settlement rate** (constraint: ≥95%)
2. **Generalization** (performance on held-out seeds 11-20)
3. **Policy complexity** (tree depth, node count)
4. **Interpretability** (human-readable decision rules)

### 5.4 Comparison Metrics

| Metric | Castro RL | LLM Iteration | Notes |
|--------|-----------|---------------|-------|
| Episodes to converge | 50-100 | 10-25 iterations | Measure sample efficiency |
| Final cost gap to Nash | ~0% | Target: <5% | Measure optimality |
| Policy interpretability | Black-box NN | JSON tree | Qualitative advantage |
| Generalization to new seeds | Untested | Explicit test | Robustness check |

---

## 6. Experimental Protocol

### 6.1 Experiment 1: Two-Period Validation

**Goal**: Verify LLM can find Nash equilibrium in simple case.

**Setup**:
- Fixed payment profile (as in Castro Section 6.3)
- 25 iterations maximum
- 10 seeds per iteration

**Success Criteria**:
- LLM discovers $\ell_0^A \approx 0$, $\ell_0^B \approx P^B$ (within 10%)
- System cost within 5% of Nash equilibrium
- Convergence within 15 iterations

### 6.2 Experiment 2: Twelve-Period with Stochastic Arrivals

**Goal**: Test LLM on realistic Castro-style scenario.

**Setup**:
- LVTS-style payment distributions
- Both agents optimize simultaneously
- 50 iterations maximum
- 10 seeds per iteration

**Success Criteria**:
- LLM achieves lower cost than grid search baseline
- Stable convergence (cost variance < 10% for last 5 iterations)
- Discovered policy generalizes to held-out seeds

### 6.3 Experiment 3: Joint Liquidity + Timing

**Goal**: Replicate Castro Section 7 joint learning.

**Setup**:
- 3-period symmetric payments
- Optimize both `strategic_collateral_tree` and `payment_tree`
- Test both $r_d < r_c$ and $r_d > r_c$ regimes

**Success Criteria**:
- LLM adapts timing to delay cost regime
- When $r_d > r_c$: Higher initial liquidity, faster release
- When $r_d < r_c$: Lower initial liquidity, more holding

### 6.4 Ablation Studies

1. **Model comparison**: Claude Opus vs Sonnet vs Haiku
2. **Iteration budget**: 5, 10, 25, 50 iterations
3. **Seed diversity**: 5, 10, 20 seeds per iteration
4. **Prompt strategy**: Full history vs. rolling 5 iterations

---

## 7. Expected Contributions

### 7.1 Methodological

1. **LLM-as-optimizer framework** for financial policy discovery
2. **Comparison methodology**: RL vs. LLM iteration
3. **Feature toggle integration** for controlled experiments

### 7.2 Empirical

1. **Quantitative comparison** of LLM vs. RL convergence
2. **Policy analysis**: What strategies do LLMs discover?
3. **Sensitivity analysis**: How do LLMs respond to cost parameters?

### 7.3 Practical

1. **Interpretable policies** for regulator review
2. **Transfer learning**: Policies generalizing across scenarios
3. **Human-AI collaboration**: LLM-assisted policy design

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM fails to converge | Medium | High | Use diverse prompt strategies; restart with different seed policies |
| Policies overfit to training seeds | Medium | Medium | Always evaluate on held-out seeds 11-20 |
| Feature toggles too restrictive | Low | Medium | Gradually enable features if needed |
| LLM generates invalid JSON | Low | Low | Automatic validation + retry with error feedback |
| Cost function misalignment | Medium | High | Validate against Castro's analytical 2-period solution first |

---

## 9. Timeline

| Week | Activity |
|------|----------|
| 1 | Configure SimCash scenarios matching Castro et al. |
| 2 | Implement LLM optimization harness and prompts |
| 3 | Run Experiment 1 (2-period validation) |
| 4 | Run Experiment 2 (12-period stochastic) |
| 5 | Run Experiment 3 (joint learning) |
| 6 | Ablation studies and robustness checks |
| 7 | Analysis and comparison with Castro RL results |
| 8 | Paper writing |

---

## 10. Future Extensions

1. **Multi-agent scaling**: Extend beyond 2 agents
2. **LSM integration**: Enable liquidity-saving mechanisms
3. **Adversarial training**: LLM vs. LLM competition
4. **Real-world calibration**: Use actual LVTS/TARGET2 data
5. **Hybrid approaches**: LLM-seeded RL fine-tuning

---

## References

1. Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). Estimating Policy Functions in Payment Systems Using Reinforcement Learning. *ACM Transactions on Economics and Computation*, 13(1), Article 1.

2. European Central Bank. TARGET2 Business Day Documentation.

3. Bank of Canada. Large Value Transfer System (LVTS) Documentation.

4. Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. *NeurIPS*.

5. Anthropic. (2024). Claude Model Documentation.

---

*Document generated for SimCash research initiative - Version 1.0*
