# Research Proposal: LLM-Driven Policy Optimization for Payment System Cash Management

**Version**: 1.0
**Date**: 2025-11-30
**Status**: Proposal

---

## Abstract

This research proposal outlines a novel approach to optimizing cash management policies in Real-Time Gross Settlement (RTGS) payment systems using Large Language Models (LLMs) as policy iterators. Inspired by the work of Bodislav et al. (2024) on integrating machine learning in central banks, we propose replacing traditional reinforcement learning (RL) with an LLM-in-the-loop system that iteratively refines JSON-based decision tree policies based on simulation outcomes. Using SimCash as our simulation environment, we aim to demonstrate that reasoning-capable LLMs can discover effective cash management strategies that minimize costs while maintaining settlement performance, providing interpretable policy artifacts that can inform real-world central bank operations.

---

## 1. Introduction

### 1.1 Background

Modern economies rely on Real-Time Gross Settlement (RTGS) systems for high-value interbank payments. These systems—including TARGET2 (Eurosystem), Fedwire (US), and RIX-RTGS (Sweden)—process trillions of dollars daily. Banks participating in these systems face a fundamental coordination problem: liquidity costs money (holding reserves ties up capital), but delays also cost money (client dissatisfaction, regulatory penalties, operational risk).

Bodislav et al. (2024) explore how artificial intelligence, particularly machine learning, can be integrated into central bank operations for economic forecasting, risk management, and policy optimization. Their work emphasizes the potential of neural networks, time series analysis, and natural language processing to improve monetary and fiscal policy decisions. However, traditional RL approaches to policy optimization have limitations:

- **Sample inefficiency**: RL requires millions of episodes to converge
- **Black-box policies**: Neural network policies are not interpretable
- **Reward engineering**: Designing reward functions is error-prone
- **Deployment barriers**: Regulators require explainable decision-making

### 1.2 Proposed Innovation

We propose a fundamentally different approach: using a high-powered reasoning LLM (e.g., Claude Opus, GPT-4, or specialized financial LLMs) to iteratively refine human-readable JSON policy trees based on simulation outcomes. This approach offers:

- **Sample efficiency**: LLMs leverage pre-trained knowledge of financial systems
- **Interpretability**: JSON decision trees are human-readable and auditable
- **Rapid iteration**: Each refinement cycle produces testable hypotheses
- **Domain knowledge integration**: LLMs can incorporate financial reasoning

### 1.3 Research Questions

1. Can LLMs effectively optimize payment system cash management policies through iterative simulation-and-refinement cycles?
2. How do LLM-optimized policies compare to hand-crafted heuristics and traditional RL baselines?
3. What policy structures and strategies emerge from LLM-driven optimization?
4. How many iteration cycles are required for convergence to effective policies?

---

## 2. Related Work

### 2.1 AI in Central Banking (Bodislav et al., 2024)

The foundational paper examines three AI techniques for central bank applications:

| Technique | Application | SimCash Analogue |
|-----------|-------------|------------------|
| Neural Networks | Non-linear pattern recognition, inflation forecasting | LSM cycle prediction, gridlock detection |
| Time Series Analysis | Trend identification, GDP forecasting | Intraday payment flow prediction |
| Natural Language Processing | Sentiment analysis, policy communication | (Out of scope for this proposal) |

Key insights from Bodislav et al. relevant to our work:

- **Predictive analytics for employment and inflation**: Analogous to predicting Queue 2 congestion and liquidity pressure
- **Interest rate optimization**: Analogous to collateral posting and withdrawal timing
- **Real-time data integration**: SimCash provides tick-by-tick state for immediate feedback
- **Risk assessment for financial stability**: Maps to gridlock detection and EOD settlement risk

### 2.2 RL in Payment Systems

Prior work on applying RL to payment systems includes:

- **Galbiati & Soramäki (2011)**: Agent-based modeling of payment systems
- **Denbee et al. (2021)**: RL for intraday liquidity management
- **BIS studies**: CPMI reports on AI in financial market infrastructure

Limitations of these approaches that we address:
- Black-box policies unsuitable for regulatory scrutiny
- High sample complexity (millions of episodes)
- Difficulty incorporating domain expertise

### 2.3 LLMs as Optimizers

Recent work has demonstrated LLMs' capability for optimization:

- **Prompt optimization**: LLMs iterating on prompts for task performance
- **Code generation with feedback**: LLMs refining code based on test results
- **AutoGPT-style agents**: Autonomous task completion with iterative refinement

Our approach extends this paradigm to financial policy optimization.

---

## 3. SimCash Environment

### 3.1 System Overview

SimCash is a high-fidelity payment system simulator implementing TARGET2-style mechanics:

```
┌─────────────────────────────────────────────────────────┐
│                    SimCash Environment                  │
├─────────────────────────────────────────────────────────┤
│  Agents (Banks)          │  Settlement Engine           │
│  ├─ Balance              │  ├─ RTGS Immediate           │
│  ├─ Credit Limit         │  ├─ Queue 2 (LSM)            │
│  ├─ Collateral           │  │   ├─ Algorithm 1: FIFO    │
│  ├─ Queue 1 (internal)   │  │   ├─ Algorithm 2: Bilatrl │
│  └─ Policy (JSON DSL)    │  │   └─ Algorithm 3: Cycles  │
│                          │  └─ Entry Disposition        │
├──────────────────────────┴──────────────────────────────┤
│  Cost Model: Overdraft | Delay | Deadline | Collateral  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Policy DSL

SimCash policies are defined as JSON decision trees with 140+ context fields:

```json
{
  "version": "1.0",
  "policy_id": "example_policy",
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0
  },
  "payment_tree": {
    "type": "condition",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {"type": "action", "action": "Release"},
    "on_false": {"type": "action", "action": "Hold"}
  }
}
```

### 3.3 Cost Model

The cost model creates a multi-objective optimization problem:

| Cost Type | Formula | Trade-off |
|-----------|---------|-----------|
| Overdraft | `bps × max(0, -balance) × (1/ticks_per_day)` | Liquidity vs. credit usage |
| Delay | `penalty_per_tick × queue1_wait_time` | Speed vs. liquidity conservation |
| Deadline | `fixed_penalty` (one-time) | Urgency handling |
| Overdue | `delay × 5.0` (multiplied after deadline) | Penalty escalation |
| Collateral | `bps × posted_amount × (1/ticks_per_day)` | Credit access vs. opportunity cost |
| EOD | `penalty × unsettled_count` | Settlement completion pressure |

### 3.4 Evaluation Metrics

The simulation produces rich metrics for policy evaluation:

```python
{
  "settlement_rate": 0.95,          # Fraction of transactions settled
  "total_cost": 125000,             # Total costs incurred (cents)
  "cost_breakdown": {
    "overdraft": 15000,
    "delay": 45000,
    "deadline_penalties": 30000,
    "collateral": 20000,
    "eod_penalties": 15000
  },
  "lsm_utilization": {
    "bilateral_offsets": 23,
    "multilateral_cycles": 5
  },
  "average_settlement_time": 12.3,  # Ticks from arrival to settlement
  "queue_metrics": {
    "max_queue1_size": 45,
    "max_queue2_size": 12
  }
}
```

---

## 4. Proposed Methodology

### 4.1 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Policy Optimization Loop                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│   │   Scenario  │───▶│  SimCash    │───▶│  Results Collector  │ │
│   │   Config    │    │  Simulator  │    │  (Metrics + Events) │ │
│   └─────────────┘    └─────────────┘    └──────────┬──────────┘ │
│                                                    │            │
│   ┌─────────────┐    ┌─────────────┐    ┌──────────▼──────────┐ │
│   │   Policy    │◀───│  Reasoning  │◀───│  Context Builder    │ │
│   │   JSON      │    │  LLM        │    │  (Structured Prompt)│ │
│   └─────────────┘    └─────────────┘    └─────────────────────┘ │
│         │                                                       │
│         └───────────────────────────────────────────────────────┤
│                          Iteration Loop                         │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Iteration Protocol

#### Phase 1: Baseline Establishment

1. Run simulation with naive FIFO policy
2. Collect comprehensive metrics as baseline
3. Identify cost breakdown and bottlenecks

#### Phase 2: LLM Policy Generation

The LLM receives a structured prompt containing:

```markdown
## Task
You are optimizing a cash management policy for a bank in an RTGS payment system.
Your goal is to minimize total costs while maintaining high settlement rates.

## Current Policy
{current_policy_json}

## Simulation Results (Last 5 Runs)
| Run | Total Cost | Settlement Rate | Overdraft | Delay | Deadline |
|-----|------------|-----------------|-----------|-------|----------|
| 1   | $1,250     | 95.2%           | $150      | $450  | $300     |
| ... | ...        | ...             | ...       | ...   | ...      |

## Cost Analysis
- Primary cost driver: Delay costs (36% of total)
- Suggestion: Consider earlier release for high-priority transactions
- LSM utilization: Only 23 bilateral offsets detected
- Queue 2 bottleneck detected at ticks 40-60

## Available Context Fields
{subset_of_relevant_fields}

## Policy DSL Syntax
{syntax_reference}

## Constraints
- Settlement rate must remain above 90%
- Policy must be valid JSON
- Maximum tree depth: 15 nodes

## Instructions
1. Analyze the current policy's weaknesses
2. Propose a refined policy addressing the identified issues
3. Explain your reasoning for each change
4. Output the complete new policy JSON
```

#### Phase 3: Policy Validation and Simulation

1. Validate generated policy JSON against schema
2. Run N simulations with different random seeds
3. Collect aggregate metrics

#### Phase 4: Comparative Analysis

1. Compare new policy to previous iteration
2. Determine if improvement threshold met
3. Update best-known policy if improved

#### Phase 5: Convergence Check

Continue iterations until:
- Cost improvement < 1% for 3 consecutive iterations
- Maximum iteration count reached (e.g., 50)
- Settlement rate drops below threshold

### 4.3 Prompt Engineering Strategies

#### Strategy A: Full Context

Provide complete simulation state including:
- All 140+ context fields
- Complete event log
- Tick-by-tick cost accrual

**Pros**: Maximum information for LLM
**Cons**: Token-heavy, may overwhelm context

#### Strategy B: Summarized Context

Provide aggregated metrics:
- Per-agent cost summaries
- Key bottleneck indicators
- High-level pattern analysis

**Pros**: Focused, efficient
**Cons**: May miss subtle patterns

#### Strategy C: Hierarchical Prompting

1. First prompt: High-level strategy selection
2. Second prompt: Detailed parameter tuning
3. Third prompt: Edge case handling

**Pros**: Structured reasoning
**Cons**: Higher latency

### 4.4 Multi-Agent Policy Optimization

SimCash supports heterogeneous policies across agents. We propose:

1. **Symmetric optimization**: All agents share the same policy
2. **Asymmetric optimization**: Different policies for different agent archetypes (conservative, aggressive, liquidity-rich, liquidity-constrained)
3. **Competitive optimization**: Policies optimized against adversarial counterparties

---

## 5. Experimental Design

### 5.1 Scenarios

We define four benchmark scenarios of increasing complexity:

#### Scenario 1: Bilateral Exchange (Simple)

```yaml
simulation:
  ticks_per_day: 100
  num_days: 5

agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 500000
  - id: BANK_B
    opening_balance: 1000000
    credit_limit: 500000

arrival_config:
  rate_per_tick: 0.5
  amount_distribution:
    type: Normal
    mean: 50000
    std_dev: 10000
```

**Objective**: Learn basic urgency-based release timing

#### Scenario 2: Three-Party Gridlock (LSM Focus)

```yaml
agents:
  - id: BANK_A  # Net payer to B
  - id: BANK_B  # Net payer to C
  - id: BANK_C  # Net payer to A

# Circular payment pattern that should trigger LSM cycles
```

**Objective**: Learn to exploit LSM bilateral/multilateral offsets

#### Scenario 3: Liquidity Crisis (Stress)

```yaml
# Low opening balances
# High payment volumes
# Tight credit limits
# Scenario events: liquidity shock at tick 50
```

**Objective**: Learn collateral management and crisis response

#### Scenario 4: Full System (Realistic)

```yaml
# 10 heterogeneous agents
# Mixed transaction sizes
# Varied urgency levels
# Realistic intraday patterns (morning slow, afternoon rush)
```

**Objective**: Comprehensive policy optimization

### 5.2 Baselines

We compare LLM-optimized policies against:

| Baseline | Description |
|----------|-------------|
| FIFO | Release all transactions immediately |
| Deadline-5 | Release when ≤5 ticks to deadline |
| LiquidityAware | Maintain 20% balance buffer |
| Hand-crafted Expert | Sophisticated multi-tree policy (e.g., `sophisticated_adaptive_bank.json`) |
| PPO-RL | Standard RL baseline with reward = -total_cost |
| Random Search | 1000 random policy variations |

### 5.3 Evaluation Metrics

Primary metrics:
- **Total Cost** (lower is better)
- **Settlement Rate** (higher is better, constraint ≥ 90%)
- **Pareto Efficiency** (cost vs. settlement trade-off curve)

Secondary metrics:
- **LSM Utilization**: Bilateral offsets + multilateral cycles
- **Queue Dynamics**: Max Q1 size, Q2 residence time
- **Collateral Efficiency**: Posted collateral vs. credit usage
- **Policy Complexity**: Decision tree depth, node count

Convergence metrics:
- **Iterations to Best**: How many cycles to reach best policy
- **Stability**: Variance across random seeds
- **Transferability**: Performance on unseen scenarios

### 5.4 Ablation Studies

1. **Model Comparison**: Claude Opus vs. Sonnet vs. GPT-4 vs. Gemini
2. **Prompt Strategy**: Full vs. Summarized vs. Hierarchical
3. **Feedback Granularity**: Aggregate metrics vs. tick-by-tick events
4. **Search Budget**: 10 vs. 25 vs. 50 vs. 100 iterations
5. **Ensemble Methods**: Multiple LLM-generated policies combined

---

## 6. Implementation Plan

### 6.1 Phase 1: Infrastructure (Weeks 1-2)

1. **Extend SimCash CLI** for batch evaluation mode
   ```bash
   payment-sim batch-eval \
     --policy policy.json \
     --scenario scenario.yaml \
     --seeds 1000 \
     --output metrics.json
   ```

2. **Create LLM interface module**
   ```python
   class PolicyOptimizer:
       def __init__(self, llm: LLMClient, scenario: ScenarioConfig):
           self.llm = llm
           self.scenario = scenario
           self.history: list[PolicyResult] = []

       def iterate(self) -> Policy:
           context = self.build_context()
           response = self.llm.generate(self.prompt_template.format(**context))
           policy = self.parse_policy(response)
           self.validate(policy)
           return policy
   ```

3. **Build result aggregation pipeline**
   - Parse simulation outputs
   - Compute summary statistics
   - Generate LLM-friendly reports

### 6.2 Phase 2: Prompt Engineering (Weeks 3-4)

1. Develop and test prompt templates
2. Iterate on context compression strategies
3. Build few-shot example library
4. Create policy explanation extraction

### 6.3 Phase 3: Experimentation (Weeks 5-8)

1. Run all scenarios with all baselines
2. Execute LLM optimization loops
3. Collect convergence data
4. Perform ablation studies

### 6.4 Phase 4: Analysis and Writing (Weeks 9-10)

1. Statistical analysis of results
2. Policy structure analysis (what patterns emerge?)
3. Paper writing
4. Visualization and presentation

---

## 7. Expected Contributions

### 7.1 Technical Contributions

1. **LLM-as-Optimizer Framework**: A reusable methodology for using LLMs to optimize domain-specific decision trees
2. **SimCash Extensions**: Batch evaluation mode, LLM integration APIs
3. **Benchmark Suite**: Standardized scenarios for payment system policy evaluation
4. **Policy Library**: Collection of LLM-discovered effective policies

### 7.2 Scientific Contributions

1. **Sample Efficiency Comparison**: Quantify LLM advantage over RL in low-sample regimes
2. **Interpretability Analysis**: Demonstrate auditable policy discovery
3. **Emergent Strategy Catalog**: Document strategies discovered by LLMs
4. **Transfer Learning**: Show policy generalization across scenarios

### 7.3 Practical Contributions

1. **Central Bank Guidance**: Recommendations for AI-assisted policy design
2. **Regulatory Considerations**: Explainability requirements for automated cash management
3. **Best Practices**: Prompt engineering for financial optimization

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates invalid JSON | Medium | Schema validation + retry with error feedback |
| LLM overfits to seed | High | Evaluate on held-out seed ranges |
| LLM plateaus early | Medium | Implement diverse prompt strategies |
| Computational cost | Low | Use efficient models for exploration, powerful for exploitation |
| Policy complexity explosion | Medium | Enforce tree depth limits, prefer simpler policies |
| Non-reproducibility | High | Log all prompts, responses, and random seeds |

---

## 9. Relationship to Bodislav et al. (2024)

Our work directly extends the vision of Bodislav et al. in several dimensions:

| Paper Concept | Our Implementation |
|---------------|-------------------|
| "AI for monetary policy optimization" | LLM optimizing payment release policies |
| "Neural networks for non-linear data processing" | LLM reasoning about complex cost trade-offs |
| "Real-time data integration" | Tick-by-tick simulation feedback |
| "Predictive analytics for inflation/employment" | Predicting Queue 2 congestion, liquidity pressure |
| "Risk assessment for financial stability" | Gridlock detection, EOD settlement risk |
| "Decision support systems" | Automated policy recommendation with human review |
| "Interdisciplinary collaboration" | Bridging AI, finance, and payment systems |
| "Transparent, ethical AI solutions" | Interpretable JSON policies with full audit trails |

Our approach addresses several limitations Bodislav et al. identify:

1. **Data quality**: SimCash provides perfect, deterministic data
2. **Algorithmic biases**: JSON policies are fully inspectable
3. **Regulatory considerations**: Policies are human-readable and auditable
4. **Interpretability requirements**: Decision trees are inherently explainable

---

## 10. Future Work

Beyond this proposal, we envision:

1. **Multi-objective optimization**: Pareto-front discovery for cost/speed trade-offs
2. **Adversarial robustness**: Policies that perform well against strategic counterparties
3. **Online adaptation**: Policies that update in real-time based on intraday conditions
4. **Cross-system transfer**: Policies trained on TARGET2 simulation applied to Fedwire
5. **Human-in-the-loop**: Interactive policy refinement with domain experts
6. **Formal verification**: Proving safety properties of discovered policies

---

## 11. Conclusion

This proposal outlines a novel approach to cash management policy optimization that leverages the reasoning capabilities of LLMs while maintaining the interpretability requirements of financial regulation. By using SimCash as our testbed, we can safely explore policy space and discover strategies that may inform real-world central bank operations.

The key innovation is treating policy optimization as a language generation task, where the LLM iteratively refines human-readable decision trees based on simulation feedback. This approach offers a compelling alternative to black-box RL methods, particularly in domains where explainability and auditability are paramount.

---

## References

1. Bodislav, D.A., Bran, F., Petrescu, I.E., & Gomboș, C.C. (2024). The Integration of Machine Learning in Central Banks: Implications and Innovations. *European Journal of Sustainable Development*, 13(4), 23-32.

2. European Central Bank. TARGET2 Business Day. ECB Documentation.

3. Bank for International Settlements. (2023). AI/ML in Financial Market Infrastructures. CPMI Reports.

4. Galbiati, M., & Soramäki, K. (2011). An agent-based model of payment systems. *Journal of Economic Dynamics and Control*, 35(6), 859-875.

5. OpenAI. (2024). GPT-4 Technical Report. arXiv preprint.

6. Anthropic. (2024). Claude 3 Model Card. Anthropic Research.

7. Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. *NeurIPS*.

---

## Appendix A: Example LLM Prompt Template

```markdown
# SimCash Policy Optimization - Iteration {iteration_number}

## Your Role
You are an expert cash manager at a major bank participating in a TARGET2-style
RTGS payment system. Your task is to optimize the payment release policy to
minimize costs while maintaining settlement performance.

## Current Policy Performance

### Aggregate Metrics (5 simulation runs, different seeds)
| Metric | Mean | Std Dev | Best | Worst |
|--------|------|---------|------|-------|
{metrics_table}

### Cost Breakdown
{cost_breakdown}

### Key Observations
{automated_observations}

## Current Policy
```json
{current_policy}
```

## Available Improvements
Based on analysis, consider:
{suggestions}

## Policy DSL Quick Reference
- Conditions: `op` can be `<`, `<=`, `>`, `>=`, `==`, `and`, `or`
- Fields: `ticks_to_deadline`, `effective_liquidity`, `remaining_amount`, `priority`
- Actions: `Release`, `Hold`, `Split`
- Parameters: Define in `parameters` block, reference with `{"param": "name"}`

## Constraints
- Settlement rate must stay above 90% (currently: {settlement_rate}%)
- Maximum tree depth: 15 nodes
- Must be valid JSON

## Output Format
1. First, explain your analysis (2-3 paragraphs)
2. Then output the complete new policy JSON in a code block
3. Finally, predict the expected improvement

BEGIN YOUR RESPONSE:
```

---

## Appendix B: Candidate Policy Structures

### Structure 1: Urgency-First

```
payment_tree:
├── IF ticks_to_deadline <= 5
│   └── THEN Release
└── ELSE
    ├── IF effective_liquidity >= remaining_amount + buffer
    │   └── THEN Release
    └── ELSE Hold
```

### Structure 2: LSM-Aware

```
payment_tree:
├── IF ticks_to_deadline <= 3 OR is_past_deadline
│   └── THEN Release
├── ELSE IF my_bilateral_net_q2 > threshold
│   └── THEN Release (exploit offset opportunity)
└── ELSE Hold
```

### Structure 3: Budget-Controlled

```
bank_tree:
└── SetReleaseBudget(max = 0.35 * effective_liquidity)

payment_tree:
├── IF release_budget_remaining >= remaining_amount
│   └── THEN Release
└── ELSE Hold (budget exhausted)
```

### Structure 4: Collateral-Integrated

```
strategic_collateral_tree:
├── IF queue1_liquidity_gap > min_buffer
│   └── THEN PostCollateral(gap * 0.6)
└── ELSE HoldCollateral

payment_tree:
├── (standard urgency/liquidity logic)
└── ...

end_of_tick_collateral_tree:
├── IF excess_collateral > threshold
│   └── THEN WithdrawCollateral(excess * 0.3)
└── ELSE HoldCollateral
```

---

*Document generated for SimCash research initiative*
