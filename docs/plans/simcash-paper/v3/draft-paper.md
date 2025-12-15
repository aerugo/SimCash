# LLM-Based Policy Optimization for High-Value Payment Systems: Replicating and Extending Castro et al.

**Authors**: [To be determined]

**Abstract**

High-value payment systems (HVPS) present complex liquidity management challenges where banks must balance initial liquidity costs against delay penalties. Castro et al. (2025) demonstrated that reinforcement learning agents can discover optimal policies in these environments. We present SimCash, a payment system simulator that uses large language model (LLM) based optimization instead of neural network reinforcement learning. Our approach replaces policy gradient methods with structured prompt engineering, enabling interpretable policy representation through explicit JSON decision trees rather than opaque neural network weights. We replicate three experiments from Castro et al.: a 2-period deterministic scenario, a 12-period stochastic scenario with LVTS-style payment data, and a 3-period joint optimization scenario. Our results demonstrate that LLM-based optimization achieves comparable outcomes to Castro's theoretical predictions, particularly for symmetric equilibria. We document our methodology including the bootstrap evaluation framework, 3-agent sandbox architecture, and the 7-section prompt structure that provides rich context to the LLM. This work establishes LLM-based policy optimization as a viable alternative to traditional RL for payment system research.

---

## 1. Introduction

High-value payment systems form critical financial infrastructure, with systems like Canada's LVTS processing payment values equivalent to annual GDP every five business days (Castro et al., 2025). Banks participating in these systems face a fundamental tradeoff: providing liquidity upfront incurs opportunity costs, but delaying payments to await incoming liquidity creates timing penalties.

Castro et al. (2025) framed this as a multi-agent reinforcement learning problem and showed that RL agents using the REINFORCE algorithm can discover Nash equilibrium policies without complete knowledge of the environment. Their work demonstrated that machine learning can solve liquidity management problems that lack closed-form analytical solutions.

We extend this line of research by replacing neural network reinforcement learning with large language model (LLM) based optimization. Our approach, implemented in the SimCash payment system simulator, offers several potential advantages:

1. **Interpretable Policies**: Instead of opaque neural network weights, policies are represented as explicit JSON decision trees that can be inspected and understood.

2. **Structured Reasoning**: LLMs receive rich contextual information including cost breakdowns, simulation traces, and iteration history, enabling informed policy improvements.

3. **Reduced Sample Complexity**: LLMs leverage pre-trained knowledge about optimization, potentially requiring fewer iterations than gradient-based methods.

4. **Flexible Policy Representation**: Decision trees can express complex conditional logic without architectural constraints.

This paper makes the following contributions:

- We demonstrate that LLM-based policy optimization can replicate key findings from Castro et al., including asymmetric equilibria in deterministic settings and symmetric equilibria in joint optimization scenarios.

- We document a novel bootstrap evaluation methodology using a 3-agent sandbox architecture, justified by information-theoretic arguments about settlement timing as a sufficient statistic.

- We provide detailed documentation of the prompt engineering approach, including the 7-section context structure that enables effective LLM optimization.

- We compare our approach systematically to Castro's RL methodology, discussing theoretical and practical differences.

---

## 2. Background: The Payment System Environment

### 2.1 Model Description

Following Castro et al. (2025), we model a real-time gross settlement (RTGS) payment system with the following characteristics:

- **Time Structure**: Each day is an episode divided into discrete ticks (periods). At the start of day (t=0), agents choose what fraction of available collateral to allocate as initial liquidity.

- **Liquidity Dynamics**: At each tick t, agent i has liquidity ℓ_t that evolves as:
  ```
  ℓ_t = ℓ_{t-1} - P_t × x_t + R_t
  ```
  where P_t is payment demand, x_t ∈ [0,1] is the fraction sent, and R_t is incoming payments.

- **Hard Liquidity Constraint**: Settlements require sufficient liquidity:
  ```
  P_t × x_t ≤ ℓ_{t-1}
  ```

- **Cost Structure**: Agents minimize total cost:
  ```
  R = r_c × ℓ_0 + Σ_t r_d × P_t × (1 - x_t) + r_b × c_b
  ```
  where r_c is liquidity cost, r_d is delay cost, and r_b is end-of-day borrowing cost.

### 2.2 The Initial Liquidity Game

The key decision is what fraction x_0 ∈ [0,1] of collateral B to allocate as initial liquidity:
```
ℓ_0 = x_0 × B
```

Castro et al. derive Nash equilibrium conditions for the 2-period case and show that optimal strategies depend on the ordering r_c < r_d < r_b and the payment profile asymmetries between agents.

---

## 3. LLM Policy Optimization Methodology

### 3.1 Optimization Loop

Our approach replaces gradient-based policy updates with an iterative LLM consultation process:

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐      │
│  │ Generate    │───▶│ Evaluate    │───▶│ Accept/     │      │
│  │ Candidate   │    │ via         │    │ Reject      │      │
│  │ Policy      │    │ Simulation  │    │             │      │
│  └─────────────┘    └─────────────┘    └──────┬──────┘      │
│        ▲                                       │             │
│        │                                       │             │
│        └───────────────────────────────────────┘             │
│                    (iterate until convergence)               │
└──────────────────────────────────────────────────────────────┘
```

**Algorithm 1: LLM-Based Policy Optimization**

```
Input: Initial policies π_0 for each agent, max_iterations, stability_window
Output: Final policies π*

for iteration = 1 to max_iterations:
    # Evaluate current policies
    cost_current = evaluate_policies(π_current)

    for each agent a:
        # Build context prompt (Section 3.2)
        prompt = build_context(a, π_current, iteration_history)

        # Query LLM for candidate policy
        π_candidate = llm_generate_policy(prompt)

        # Validate policy against constraints
        if not validate(π_candidate):
            retry with error feedback (up to max_retries)

        # Evaluate candidate
        cost_candidate = evaluate_policy(π_candidate)

        # Accept if improvement
        if cost_candidate < cost_current[a]:
            π_current[a] = π_candidate
            mark as ACCEPTED
        else:
            mark as REJECTED

    # Check convergence (stability_window consecutive stable iterations)
    if stable_for(stability_window):
        return π_current

return π_current
```

### 3.2 Prompt Architecture: The 7-Section Context

The LLM receives comprehensive context through a structured prompt of approximately 50,000 tokens. This rich context enables informed policy decisions:

#### Section 1: Header
Identifies the agent and iteration, sets expectations:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY OPTIMIZATION CONTEXT - BANK_A - ITERATION 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TABLE OF CONTENTS:
1. Current State Summary
2. Cost Analysis
3. Optimization Guidance
...
```

#### Section 2: Current State Summary
Performance metrics and current policy parameters:
```
### Performance Metrics (Iteration 5)

| Metric | Value |
|--------|-------|
| **Mean Total Cost** | $12,500 (↓15.2% from previous) |
| **Settlement Rate** | 100.0% |
| **Best Seed** | #1847592 ($8,200) |
| **Worst Seed** | #9283746 ($18,400) |

### Current Policy Parameters (BANK_A)
{
  "initial_liquidity_fraction": 0.5,
  ...
}
```

#### Section 3: Cost Analysis
Breakdown by cost type with configuration:
```
| Cost Type | Amount | % of Total | Priority |
|-----------|--------|------------|----------|
| delay | $6,000 | 48.0% | 🔴 HIGH |
| collateral | $4,000 | 32.0% | 🟡 MEDIUM |
| overdraft | $1,500 | 12.0% | 🟢 LOW |
```

#### Section 4: Optimization Guidance
Actionable recommendations based on cost patterns:
```
⚠️ **HIGH DELAY COSTS** - Payments are waiting too long in queue.
   Consider: Lower urgency_threshold, release payments earlier.

✅ **IMPROVING TREND** - Costs decreasing consistently.
   Continue current optimization direction.
```

#### Section 5: Simulation Output
Tick-by-tick event traces from best and worst performing bootstrap samples:
```
### Best Performing Seed (#1847592, Cost: $8,200)

<best_seed_output>
[tick 0] Arrival: tx_id=tx_001, amount=$1,000.00
[tick 0] PolicyDecision: tx_id=tx_001, action=Release
[tick 1] RtgsImmediateSettlement: tx_id=tx_001, amount=$1,000.00
...
</best_seed_output>

### Worst Performing Seed (#9283746, Cost: $18,400)
...
```

This allows the LLM to analyze what strategies succeeded (best seed) and what patterns led to failures (worst seed).

#### Section 6: Iteration History
Full history with acceptance status and policy changes:
```
| Iter | Status | Mean Cost | Settlement |
|------|--------|-----------|------------|
| 1 | ⭐ BEST | $15,000 | 95.0% |
| 2 | ❌ REJECTED | $16,500 | 92.0% |
| 3 | ✅ KEPT | $14,200 | 98.0% |
...

### Detailed Changes Per Iteration

#### ❌ Iteration 2 (REJECTED)
**BANK_A Changes:**
  - Changed 'urgency_threshold': 8 → 10 (↑2.00)
```

#### Section 7: Parameter Trajectories
How each parameter evolved across iterations:
```
### initial_liquidity_fraction

| Iteration | Value |
|-----------|-------|
| 1 | 0.500 |
| 2 | 0.300 |
| 3 | 0.250 |
...

*Overall: decreased 50% from 0.500 to 0.250*
```

#### Section 8: Final Instructions
Output requirements and warnings:
```
⚠️ **IMPORTANT**: 2 previous policy attempts were REJECTED because they
performed worse. Review the rejected policies and avoid similar changes.

📌 **Current Best**: Iteration 5 with mean cost $12,500.
Your goal is to beat this.
```

### 3.3 Policy Representation

Unlike neural network policies that map states to action probabilities, our policies are explicit JSON structures:

```json
{
  "initial_liquidity_fraction": 0.25,
  "payment_tree": {
    "node_type": "leaf",
    "action": "Release"
  }
}
```

For the Castro replication experiments, the key parameter is `initial_liquidity_fraction`, which directly corresponds to x_0 in Castro's model. This explicit representation enables:

1. **Transparency**: Policy logic can be inspected and understood
2. **Validation**: Policies can be checked against constraints before evaluation
3. **Debugging**: Failed policies can be analyzed to understand LLM reasoning

### 3.4 Validation and Retry

LLM responses are validated against a constraint schema:

```yaml
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
```

Invalid policies trigger retry with error feedback, allowing the LLM to correct mistakes:

```
Validation errors:
1. initial_liquidity_fraction: value -0.1 below minimum 0.0

Please generate a corrected policy addressing these errors.
```

---

## 4. Bootstrap Evaluation and the 3-Agent Sandbox

### 4.1 The Evaluation Challenge

Evaluating whether a candidate policy improves upon the current policy is complicated by variance from stochastic transaction arrivals. A single simulation comparison is unreliable because differences in transaction patterns may dominate true policy effects.

### 4.2 Paired Comparison Bootstrap

We use paired comparison on bootstrap samples:

1. Generate N bootstrap samples from historical transaction data
2. Run **both** policies on the **same** N samples
3. Compute delta = cost(policy_current) - cost(policy_candidate) for each sample
4. Accept new policy if mean(delta) > 0

**Why Paired Comparison?**

Standard (unpaired) comparison:
```
cost_A = [simulate(policy_A, sample_i) for i in range(N)]
cost_B = [simulate(policy_B, sample_j) for j in range(N)]
difference = mean(cost_A) - mean(cost_B)
```
Problem: High variance from different samples masks true policy differences.

Paired comparison:
```
deltas = [
    simulate(policy_A, sample_i) - simulate(policy_B, sample_i)
    for i in range(N)
]
difference = mean(deltas)
```

By evaluating both policies on the same sample, we eliminate sample-to-sample variance. The variance of the paired difference is:
```
Var(delta) = Var(A) + Var(B) - 2×Cov(A,B)
```

When A and B are positively correlated (same sample → similar challenges), the covariance term significantly reduces variance.

### 4.3 The 3-Agent Sandbox Architecture

For policy evaluation, we use an isolated 3-agent sandbox:

```
                    ┌─────────────────────────────┐
                    │                             │
   ┌────────┐       │      ┌─────────┐            │      ┌────────┐
   │        │ incoming     │         │  outgoing       │        │
   │ SOURCE │──────────────│  AGENT  │─────────────────│  SINK  │
   │        │  settlements │         │  payments       │        │
   │   ∞    │       │      │ (test   │            │      │   ∞    │
   └────────┘       │      │ policy) │            │      └────────┘
                    │      └─────────┘            │
                    │                             │
                    └─────────────────────────────┘
```

- **SOURCE**: Infinite liquidity, sends "incoming settlements" to AGENT at historically-observed times
- **AGENT**: Target agent with test policy being evaluated
- **SINK**: Infinite capacity, receives AGENT's outgoing transactions

### 4.4 Information-Theoretic Justification

The sandbox design follows from a fundamental constraint: **agents cannot observe the internal state of other agents**.

**What an Agent Observes:**
From any single agent's perspective, they can only observe:
1. Their own policy and decision state
2. When their payments settle (or fail)
3. When liquidity arrives from counterparties

They **cannot observe**:
- Other agents' policies or decision rules
- Other agents' queue states or liquidity positions
- LSM cycle formation dynamics
- Market-wide liquidity conditions

**Settlement Timing as a Sufficient Statistic:**

This information asymmetry leads to a key insight: settlement timing is a sufficient statistic for the liquidity environment.

When an agent sends a payment to counterparty B:
- If B has abundant liquidity → payment settles quickly
- If B is liquidity-constrained → payment queues, settles later
- If system-wide gridlock occurs → settlement delays further

The settlement time encapsulates all of this complexity. The agent doesn't need to know *why* settlement took 5 ticks — only that it did. From their perspective, "the market" is an abstract entity characterized by settlement timing distributions.

**Formal Argument:**

Let:
- π = agent's policy
- X = transaction characteristics (amount, priority, deadline)
- T = settlement timing (the sufficient statistic)
- C = agent's cost

The agent's optimization problem is:
```
minimize E[C | π, X, T]
```

Note that C depends on T (settlement timing), not on the underlying market state M that produces T. Since T is observable and M is not, T is a sufficient statistic for the agent's decision problem.

### 4.5 When the Approximation is Valid

The sandbox approach is valid when settlement timing T is exogenous to the agent's policy π:
```
P(T | π) ≈ P(T)  (agent's policy doesn't significantly affect market settlement times)
```

This holds when:
- **Agent is small**: Their transaction volume doesn't materially affect system liquidity
- **Policy decisions are local**: About releasing own transactions, not coordinating
- **No strategic counterparty response**: Counterparties don't condition behavior on this agent
- **Diverse counterparty set**: Liquidity comes from many sources

### 4.6 Known Limitations

The sandbox has specific limitations:

1. **No bilateral feedback loop**: When agent A releases payment to B, this gives B liquidity to release payments back to A. The sandbox doesn't model this circulation.

2. **Settlement timing is fixed**: The settlement_offset from historical data is preserved, but a different policy might produce different settlement times in reality.

3. **No multilateral LSM**: The sandbox supports bilateral offsets but not N-agent cycle formation.

For the Castro replication experiments, these limitations are acceptable because:
- The 2-agent symmetric setup means bilateral feedback is captured in historical settlement times
- The focus is on initial liquidity optimization, not intraday strategic interaction

---

## 5. Comparison to Castro et al.

### 5.1 Methodology Comparison

| Aspect | Castro et al. (2025) | SimCash |
|--------|---------------------|---------|
| **Learning Algorithm** | REINFORCE (policy gradient RL) | LLM-based prompt optimization |
| **Policy Representation** | Neural network weights | Explicit JSON decision trees |
| **Training Process** | Episodes × gradient updates | Iteration × LLM call × accept/reject |
| **Exploration** | Softmax action probabilities | LLM's inherent variability + structured prompts |
| **State Representation** | Vector input to neural net | Structured text with simulation traces |
| **Interpretability** | Black-box neural network | Transparent decision rules |
| **Prior Knowledge** | Learns from scratch | LLM has pre-trained optimization knowledge |

### 5.2 Key Differences

**1. Action Space:**
- Castro: 21-point discretization of [0,1] for liquidity fraction
- SimCash: Continuous values, any floating-point in [0,1]

**2. Training Dynamics:**
- Castro: Hundreds of episodes with gradient updates, policies evolve smoothly
- SimCash: ~10-15 iterations, each producing a complete new policy, accept/reject mechanism

**3. Multi-Agent Interaction:**
- Castro: Two agents train simultaneously, affecting each other's environment (non-stationary)
- SimCash: Agents optimized sequentially within each iteration, bootstrap evaluation uses fixed historical samples

**4. Payment Demand:**
- Castro: 380 days of real LVTS data, random sampling per episode
- SimCash: Configurable arrival patterns (Poisson with LogNormal amounts), bootstrap resampling

**5. Costs:**
- Castro: r_c=0.1, r_d=0.2, r_b=0.4 (normalized)
- SimCash: Basis points per tick, converted to match Castro's ratios

### 5.3 Why Both Approaches Should Converge

Despite methodological differences, both approaches should converge to similar equilibrium policies because:

1. **Same Optimization Objective**: Both minimize payment processing cost
2. **Same Cost Structure**: Liquidity-delay tradeoff creates identical incentives
3. **Same Constraints**: Hard liquidity constraint P_t × x_t ≤ ℓ_{t-1}
4. **Nash Equilibrium Existence**: Castro's theoretical analysis shows unique equilibria exist for the test scenarios

---

## 6. Experimental Results

### 6.1 Experiment 1: 2-Period Deterministic

**Setup:**
- 2 ticks per day, 1 day
- Payment schedule: A sends 15,000 at t=1; B sends 15,000 at t=0, 5,000 at t=1
- Cost parameters: r_c < r_d < r_b (liquidity_cost_per_tick_bps: 500)

**Castro Prediction:**
Due to asymmetric payment timing, Bank B must provide liquidity first (to send 15,000 at t=0), while Bank A can wait for incoming funds:
- BANK_A: 0% (free-rider)
- BANK_B: 20% (liquidity provider)

**SimCash Results:**

| Metric | Value |
|--------|-------|
| Final BANK_A | 4% |
| Final BANK_B | 20% |
| Iterations to converge | 16 |
| Final Cost | $24.00 |
| Convergence reason | Stability achieved (5 consecutive stable iterations) |

**Analysis:**
The LLM discovered the asymmetric equilibrium that **closely matches** Castro's prediction:

1. **Correct Role Assignment**: BANK_B acts as liquidity provider (20%), BANK_A as free-rider (4%)
2. **Near-Optimal**: BANK_A at 4% is close to Castro's theoretical 0%
3. **Strong Validation**: This experiment provides strong support for LLM-based optimization

**Policy Trajectory:**

| Iteration | BANK_A | BANK_B | Total Cost | Status |
|-----------|--------|--------|------------|--------|
| 0 | 50% | 50% | Baseline | Initial |
| 1 | Accepted | Accepted | Improved | Both reduced |
| 16 | 4% | 20% | $24.00 | Converged |

### 6.2 Experiment 2: 12-Period Stochastic

**Setup:**
- 12 ticks per day, 1 day
- Stochastic arrivals: Poisson(λ=2.0), LogNormal amounts (μ=10,000, σ=5,000)
- Bootstrap evaluation with 50 samples

**Castro Prediction:**
Both agents should converge to 10-30% liquidity allocation.

**SimCash Results:**

| Metric | Value |
|--------|-------|
| Final BANK_A | 11% |
| Final BANK_B | 11.5% |
| Iterations to converge | 12 |
| Final Cost | $266.24 |
| Convergence reason | Stability achieved (5 consecutive stable iterations) |

**Analysis:**
The LLM agents discovered a **symmetric equilibrium within Castro's predicted range**:

1. **Within Predicted Range**: Both agents at ~11% falls squarely within Castro's 10-30% prediction

2. **Symmetric Solution**: Both agents converged to nearly identical policies, demonstrating the game's symmetric nature

3. **Stable Convergence**: After 12 iterations, the policies remained stable with both agents rejecting proposals that deviated from ~11%

**Why This Result?**

The symmetric equilibrium at ~11% represents a balanced solution:
- Low enough to minimize liquidity costs
- High enough to avoid excessive delay penalties from queuing
- Both agents reaching similar values suggests this is a true Nash equilibrium

### 6.3 Experiment 3: 3-Period Joint Optimization

**Setup:**
- 3 ticks per day, 1 day
- Symmetric payments: Both agents send 20,000 at t=0 and t=1
- Joint optimization of initial liquidity and payment timing

**Castro Prediction:**
Symmetric equilibrium with both agents at approximately 25%.

**SimCash Results:**

| Metric | Value |
|--------|-------|
| Final BANK_A | 20% |
| Final BANK_B | 20% |
| Iterations to converge | 7 |
| Final Cost | $39.96 |
| Convergence reason | Stability achieved (5 consecutive stable iterations) |

**Analysis:**
This experiment demonstrates a **symmetric equilibrium close to Castro's prediction**:

1. **Perfect Symmetry**: Both agents converged to exactly 20%, demonstrating the symmetric nature of the game
2. **Fast Convergence**: Only 7 iterations needed, the fastest of all experiments
3. **Stable Equilibrium**: After iteration 1, both agents maintained 20% with all subsequent proposals rejected

**Policy Trajectory:**

| Iteration | BANK_A | BANK_B | Total Cost | Status |
|-----------|--------|--------|------------|--------|
| 0 | 50% | 50% | $99.90 | Baseline |
| 1 | 20% | 20% | $39.96 | Both accepted |
| 2-7 | 20% | 20% | $39.96 | Stable (proposals rejected) |

**Why 20% instead of 25%?**

The 5% difference from Castro's ~25% prediction may be due to:
- Slight differences in cost parameterization
- Different effective discount rates between SimCash and Castro's model
- The LLM finding a local optimum that is acceptable but not globally optimal

### 6.4 Summary of Results

| Experiment | Castro Prediction | SimCash Result | Qualitative Match |
|------------|-------------------|----------------|-------------------|
| Exp1 (2-period) | A=0%, B=20% | A=4%, B=20% | ✓ Close match |
| Exp2 (12-period) | Both 10-30% | Both ~11% | ✓ Within range |
| Exp3 (3-period) | Both ~25% | Both 20% | ✓ Close match |

**Key Finding**: All three experiments produced results that closely match or fall within Castro's theoretical predictions. This provides strong validation of LLM-based policy optimization as a viable alternative to neural network reinforcement learning.

---

## 7. Discussion

### 7.1 Interpretability Advantage

A key benefit of LLM-based optimization is policy transparency. Consider the converged policy from Experiment 3:

```json
{
  "initial_liquidity_fraction": 0.20,
  "payment_tree": {
    "node_type": "leaf",
    "action": "Release"
  }
}
```

This explicitly states: "Allocate 20% of available liquidity at day start, release all payments immediately." Contrast with a neural network policy where the same behavior is encoded in thousands of weights with no direct interpretation.

### 7.2 The Role of Context

The 50,000-token prompt provides context that would be unavailable to standard RL agents:

1. **Explicit Cost Breakdown**: The LLM sees which cost types dominate and can reason about targeted improvements
2. **Historical Rejected Policies**: Previous failures inform what to avoid
3. **Best/Worst Simulation Traces**: Direct observation of what succeeds and fails

This rich context enables few-shot learning behavior, where the LLM improves policies based on a small number of examples rather than gradient-based credit assignment.

### 7.3 Experiment Consistency

All three experiments produced results consistent with Castro's theoretical predictions:

1. **Exp1**: BANK_A=4%, BANK_B=20% closely matches Castro's A=0%, B=20% prediction for asymmetric equilibria

2. **Exp2**: Both agents at ~11% falls within Castro's 10-30% predicted range for stochastic scenarios

3. **Exp3**: Both agents at 20% is close to Castro's ~25% prediction for symmetric games

This consistency across different experimental setups (deterministic vs. stochastic, asymmetric vs. symmetric) provides strong evidence that:

- LLM-based optimization can reliably discover Nash equilibria
- The methodology generalizes across different game structures
- GPT-5.2 has sufficient optimization capability for this domain

### 7.4 Limitations

1. **LLM Dependency**: Results depend on the specific LLM used (GPT-5.2 in our experiments). Different models may converge to different equilibria.

2. **Computational Cost**: LLM API calls are more expensive per iteration than neural network forward passes, though fewer iterations may be needed.

3. **Determinism**: LLM outputs have inherent stochasticity; we use temperature 0.5 and reasoning_effort "high" for reproducibility.

4. **Sandbox Approximation**: The 3-agent sandbox is valid for small agents but may not generalize to large market participants.

---

## 8. Conclusion

We have demonstrated that LLM-based policy optimization is a viable approach for payment system liquidity management research. Our SimCash system successfully replicates key findings from Castro et al. (2025):

- **Asymmetric equilibria** in deterministic settings: Exp1 produced A=4%, B=20%, closely matching Castro's A=0%, B=20% prediction
- **Symmetric equilibria** in stochastic settings: Exp2 produced ~11% for both agents, within Castro's 10-30% range
- **Symmetric equilibria** in joint optimization: Exp3 produced 20% for both agents, close to Castro's ~25% prediction

The LLM approach offers distinct advantages:
- **Interpretable policies** through explicit JSON representation
- **Rich contextual reasoning** through structured prompts
- **Rapid convergence** through pre-trained optimization knowledge

We have also documented novel methodological contributions:
- **Bootstrap paired comparison** for high-variance environments
- **3-agent sandbox** with information-theoretic justification
- **7-section prompt architecture** for effective LLM optimization

### Future Work

1. **Multi-Agent Scaling**: Extend beyond 2 agents to realistic payment networks
2. **Intraday Strategy Learning**: Allow LLM to optimize payment timing, not just initial liquidity
3. **Model Comparison**: Systematically compare across different LLMs
4. **Real Data Integration**: Test with actual LVTS transaction data
5. **Bilateral Evaluation**: Implement full bilateral simulation for strategic interaction

---

## References

1. Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). Estimating Policy Functions in Payment Systems Using Reinforcement Learning. *ACM Transactions on Economics and Computation*, 13(1), Article 1.

2. Bech, M. L., & Garratt, R. (2003). The intraday liquidity management game. *Journal of Economic Theory*, 109(2), 198-219.

3. Sutton, R. S., & Barto, A. G. (2018). *Reinforcement Learning: An Introduction*. MIT Press.

4. Williams, R. J. (1992). Simple statistical gradient-following algorithms for connectionist reinforcement learning. *Machine Learning*, 8(3-4), 229-256.

5. Efron, B. (1979). Bootstrap Methods: Another Look at the Jackknife. *Annals of Statistics*, 7(1), 1-26.

6. Galbiati, M., & Soramäki, K. (2011). An agent-based model of payment systems. *Journal of Economic Dynamics and Control*, 35(6), 859-875.

---

## Appendix A: Experiment Configurations

### A.1 Experiment 1: 2-Period Deterministic

```yaml
simulation:
  ticks_per_day: 2
  num_days: 1

cost_rates:
  liquidity_cost_per_tick_bps: 500    # r_c
  delay_cost_per_tick_per_cent: 0.2   # r_d
  overdraft_bps_per_tick: 0           # Hard liquidity constraint

agents:
  - id: BANK_A
    liquidity_pool: 100000
    unsecured_cap: 0
  - id: BANK_B
    liquidity_pool: 100000
    unsecured_cap: 0
```

### A.2 Experiment 2: 12-Period Stochastic

```yaml
simulation:
  ticks_per_day: 12
  num_days: 1

cost_rates:
  liquidity_cost_per_tick_bps: 83
  delay_cost_per_tick_per_cent: 0.2

agents:
  - id: BANK_A
    liquidity_pool: 1000000
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
```

### A.3 Experiment 3: 3-Period Joint

```yaml
simulation:
  ticks_per_day: 3
  num_days: 1

cost_rates:
  liquidity_cost_per_tick_bps: 333
  delay_cost_per_tick_per_cent: 0.2

agents:
  - id: BANK_A
    liquidity_pool: 100000
  - id: BANK_B
    liquidity_pool: 100000
```

---

## Appendix B: Representative LLM Prompt Excerpt

The following shows a condensed excerpt from an actual optimization prompt:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY OPTIMIZATION CONTEXT - BANK_A - ITERATION 9
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. CURRENT STATE SUMMARY

| Metric | Value |
|--------|-------|
| **Mean Total Cost** | $57.50 |
| **Settlement Rate** | 100.0% |

### Current Policy Parameters (BANK_A)
{
  "initial_liquidity_fraction": 0.15
}

## 2. COST ANALYSIS

| Cost Type | Amount | % of Total |
|-----------|--------|------------|
| delay | $0.00 | 0.0% |
| liquidity | $57.50 | 100.0% |

## 3. OPTIMIZATION GUIDANCE

✅ All payments settling - good!
⚠️ Liquidity cost dominates - consider reducing allocation

## 4. SIMULATION OUTPUT

### Best Seed (#42, Cost: $57.50)
[tick 0] Balance: BANK_A $15,000.00
[tick 0] Arrival: tx_001, BANK_A→BANK_B, $150.00
[tick 1] Settlement: tx_001 settled via RTGS
...

## 5. ITERATION HISTORY

| Iter | Status | Cost |
|------|--------|------|
| 1 | ✅ KEPT | $70.00 |
| 6 | ✅ KEPT | $65.00 |
| 9 | ⭐ BEST | $57.50 |

## 6. FINAL INSTRUCTIONS

Generate improved policy. Current best: $57.50.
```

---

*Paper Version: 3.0*
*Last Updated: 2025-12-15*
