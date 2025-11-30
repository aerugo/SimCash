# Research Proposal: LLM-Driven Policy Optimization for Payment System Cash Management

**Version**: 2.1
**Date**: 2025-11-30
**Status**: Proposal

---

## Abstract

This research proposal outlines a novel approach to optimizing cash management policies in Real-Time Gross Settlement (RTGS) payment systems using Large Language Models (LLMs) as policy iterators. Inspired by the work of Bodislav et al. (2024) on integrating machine learning in central banks, we propose replacing traditional reinforcement learning (RL) with an LLM-in-the-loop system that iteratively refines JSON-based decision tree policies based on simulation outcomes.

Using SimCash as our simulation environment, we leverage its **policy feature toggles** to create a controlled experimental setup, and its **policy-schema generator** to create precise documentation for the LLM. This approach enables interpretable policy discovery that can inform real-world central bank operations.

---

## 1. Introduction

### 1.1 Background

Modern economies rely on Real-Time Gross Settlement (RTGS) systems for high-value interbank payments. These systems—including TARGET2 (Eurosystem), Fedwire (US), and RIX-RTGS (Sweden)—process trillions of dollars daily. Banks participating in these systems face a fundamental coordination problem: **liquidity costs money** (holding reserves ties up capital), but **delays also cost money** (client dissatisfaction, regulatory penalties, operational risk).

Bodislav et al. (2024) explore how artificial intelligence, particularly machine learning, can be integrated into central bank operations for economic forecasting, risk management, and policy optimization. Their conceptual framework emphasizes the potential of AI to improve monetary and fiscal policy decisions. However, traditional RL approaches to policy optimization have significant limitations in financial contexts:

- **Sample inefficiency**: RL requires millions of episodes to converge
- **Black-box policies**: Neural network policies are not interpretable
- **Reward engineering**: Designing reward functions is error-prone
- **Deployment barriers**: Regulators require explainable decision-making

### 1.2 Proposed Innovation

We propose using a high-powered reasoning LLM (e.g., Claude Opus, GPT-4) to iteratively refine human-readable JSON policy trees based on simulation outcomes. Key enablers:

1. **Policy Feature Toggles**: SimCash's feature toggle system restricts the policy DSL to a controlled subset, ensuring comparable results
2. **Policy Schema Generator**: The `policy-schema` command generates context-aware documentation showing exactly what fields, actions, and operators are available
3. **Deterministic Simulation**: Same seed always produces identical results, enabling precise A/B comparisons

### 1.3 Research Questions

1. Can an LLM discover the optimal urgency threshold faster than parameter grid search?
2. Does the LLM find non-obvious parameter combinations or policy structures?
3. How does LLM performance scale with iteration count (5, 10, 25, 50)?
4. Does the LLM generalize policies across different random seeds?

---

## 2. Mapping Bodislav et al. to SimCash

Bodislav et al. (2024) is a conceptual/review paper discussing AI applications in central banking. We map their key concepts to our SimCash experimental setup:

| Bodislav Concept | SimCash Implementation |
|------------------|------------------------|
| "Holding reserves ties up capital" | Overdraft cost when balance goes negative |
| "Delay costs from slow execution" | Delay penalty per tick in Queue 1 |
| "Deadline-driven obligations" | Transaction deadlines with penalties |
| "Optimizing policy decisions" | Choosing when to Release vs. Hold |
| "Risk assessment for stability" | EOD settlement pressure |
| "Real-time data integration" | Tick-by-tick simulation feedback |
| "Predictive analytics" | LLM reasoning about cost trade-offs |
| "Interpretable AI solutions" | JSON decision trees with full audit trails |

### Core Trade-off

The fundamental tension in both Bodislav's monetary policy context and our SimCash model:

```
                    LIQUIDITY COST
                         ↑
                         |
     Release early  ←----+----→  Hold payments
     (use credit)        |       (wait for inflows)
                         ↓
                    DELAY COST
```

This mirrors the central bank trade-off between maintaining reserves (opportunity cost) and ensuring timely settlement (service quality).

---

## 3. Experimental Design

### 3.1 Design Philosophy

We isolate the fundamental timing optimization problem by using a controlled subset of SimCash features:

| Feature | Status | Rationale |
|---------|--------|-----------|
| RTGS Settlement | **Enabled** | Core mechanic |
| Queue 1 (internal) | **Enabled** | Strategic holding |
| Queue 2 (RTGS) | **Enabled** | Liquidity waiting |
| LSM Bilateral/Multilateral | **Disabled** | Focus on timing, not offset exploitation |
| Collateral Posting | **Disabled** | Single optimization dimension |
| Transaction Splitting | **Disabled** | Binary Release/Hold decisions |
| Budget Management (bank_tree) | **Disabled** | payment_tree suffices |
| State Registers | **Disabled** | Stateless policies |
| Heterogeneous Agents | **Disabled** | Symmetric setup for comparability |

This controlled setup ensures:
- **Comparability**: All baselines and LLM experiments face identical constraints
- **Interpretability**: Policies are simple decision trees
- **Focus**: Pure timing optimization without confounding factors

### 3.2 Feature Toggle Configuration

SimCash's `policy_feature_toggles` enforces these restrictions:

```yaml
# research_scenario.yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 42

# Restrict policy DSL to controlled subset
policy_feature_toggles:
  include:
    # Actions: Only Release and Hold
    - PaymentAction

    # Fields: Core timing and liquidity
    - TransactionField    # amount, priority, deadline
    - AgentField          # balance, effective_liquidity
    - TimeField           # ticks_to_deadline, is_eod_rush
    - CostField           # cost_delay_this_tx_one_tick

    # Operators: Basic comparisons and arithmetic
    - ComparisonOperator  # <, <=, >, >=, ==
    - LogicalOperator     # and, or
    - BinaryArithmetic    # +, -, *, /

# Disable LSM for controlled experiment
lsm:
  enabled: false

# Cost structure matching Bodislav's trade-offs
costs:
  overdraft_cost_bps: 10.0           # Liquidity cost
  delay_penalty_per_tick: 100        # Delay cost
  deadline_penalty: 10000            # $100 for missing deadline
  overdue_delay_multiplier: 5.0      # Escalation after deadline
  collateral_cost_per_tick_bps: 0.0  # Disabled
  split_friction_cost: 0             # Disabled
  eod_unsettled_penalty: 50000       # Strong EOD pressure

agents:
  - id: BANK_A
    opening_balance: 500000          # $5,000
    credit_limit: 200000             # $2,000 overdraft capacity
    policy:
      type: FromJson
      json_path: "policies/llm_optimized.json"
    arrival_config:
      rate_per_tick: 0.3             # ~30 transactions/day
      counterparty_weights:
        BANK_B: 1.0
      amount_distribution:
        type: Normal
        mean: 25000
        std_dev: 5000
      deadline_offset:
        type: Uniform
        min: 20
        max: 60
      priority_distribution:
        type: Uniform
        min: 1
        max: 10
      divisible: false

  - id: BANK_B
    opening_balance: 500000
    credit_limit: 200000
    policy:
      type: FromJson
      json_path: "policies/llm_optimized.json"  # Same policy (symmetric)
    arrival_config:
      rate_per_tick: 0.3
      counterparty_weights:
        BANK_A: 1.0
      amount_distribution:
        type: Normal
        mean: 25000
        std_dev: 5000
      deadline_offset:
        type: Uniform
        min: 20
        max: 60
      priority_distribution:
        type: Uniform
        min: 1
        max: 10
      divisible: false
```

### 3.3 Generating LLM Documentation

The policy-schema generator creates precise documentation for the LLM, filtered by the scenario's feature toggles:

```bash
# Generate schema showing ONLY categories allowed by the scenario
payment-sim policy-schema --scenario research_scenario.yaml --format json

# Or markdown for human review
payment-sim policy-schema --scenario research_scenario.yaml --format markdown
```

This produces documentation like:

```json
{
  "actions": [
    {
      "name": "Release",
      "description": "Submit transaction to RTGS for immediate settlement",
      "valid_in": ["payment_tree"]
    },
    {
      "name": "Hold",
      "description": "Keep transaction in Queue 1, do not release this tick",
      "valid_in": ["payment_tree"],
      "parameters": {
        "reason": "Optional string explaining hold decision"
      }
    }
  ],
  "fields": [
    {"name": "ticks_to_deadline", "type": "f64", "description": "Ticks until deadline (can be negative)"},
    {"name": "effective_liquidity", "type": "f64", "description": "Balance + credit headroom"},
    {"name": "remaining_amount", "type": "f64", "description": "Payment amount to settle"},
    {"name": "priority", "type": "f64", "description": "Transaction priority (1-10)"},
    {"name": "is_past_deadline", "type": "bool", "description": "Already overdue?"},
    {"name": "balance", "type": "f64", "description": "Current account balance"},
    {"name": "day_progress_fraction", "type": "f64", "description": "Progress through day (0-1)"}
  ],
  "operators": {
    "comparison": ["<", "<=", ">", ">=", "==", "!="],
    "logical": ["and", "or"],
    "arithmetic": ["+", "-", "*", "/"]
  }
}
```

### 3.4 Policy Structure

With the restricted DSL, policies have a simple, interpretable structure:

```json
{
  "version": "1.0",
  "policy_id": "simple_timing",
  "description": "Simple release timing policy",
  "parameters": {
    "urgency_threshold": 10.0,
    "liquidity_buffer": 50000.0
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "check_urgent",
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
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "+",
            "left": {"field": "remaining_amount"},
            "right": {"param": "liquidity_buffer"}
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
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM Policy Optimization Loop                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────┐    ┌─────────────────┐    ┌──────────────────┐  │
│  │   Scenario    │───▶│  policy-schema  │───▶│  Schema JSON     │  │
│  │   YAML        │    │  --scenario X   │    │  (for LLM)       │  │
│  └───────────────┘    └─────────────────┘    └────────┬─────────┘  │
│                                                       │            │
│  ┌───────────────┐    ┌─────────────────┐    ┌────────▼─────────┐  │
│  │   Policy      │───▶│  validate-      │───▶│  Valid?          │  │
│  │   JSON        │    │  policy --scen  │    │  (toggles check) │  │
│  └───────────────┘    └─────────────────┘    └────────┬─────────┘  │
│         ▲                                             │            │
│         │                                             ▼            │
│  ┌──────┴────────┐    ┌─────────────────┐    ┌──────────────────┐  │
│  │   Reasoning   │◀───│  Context        │◀───│  SimCash Run     │  │
│  │   LLM         │    │  Builder        │    │  (N seeds)       │  │
│  └───────────────┘    └─────────────────┘    └──────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Iteration Workflow

```python
class PolicyOptimizer:
    def __init__(self, scenario_path: str, llm_client: LLMClient):
        self.scenario_path = scenario_path
        self.llm = llm_client

        # Generate restricted schema documentation
        self.schema_docs = self._generate_schema_docs()

        # Track iteration history
        self.history: list[IterationResult] = []

    def _generate_schema_docs(self) -> str:
        """Generate policy schema filtered by scenario's feature toggles."""
        result = subprocess.run([
            "payment-sim", "policy-schema",
            "--scenario", self.scenario_path,
            "--format", "json"
        ], capture_output=True, text=True)
        return result.stdout

    def _validate_policy(self, policy_json: str) -> ValidationResult:
        """Validate policy against scenario's feature toggles."""
        with tempfile.NamedTemporaryFile(suffix=".json") as f:
            f.write(policy_json.encode())
            f.flush()

            result = subprocess.run([
                "payment-sim", "validate-policy",
                f.name,
                "--scenario", self.scenario_path
            ], capture_output=True, text=True)

            return ValidationResult(
                valid=result.returncode == 0,
                errors=result.stderr
            )

    def _run_simulations(self, policy_path: str, seeds: list[int]) -> Metrics:
        """Run simulations with multiple seeds and aggregate results."""
        all_metrics = []
        for seed in seeds:
            result = subprocess.run([
                "payment-sim", "run",
                "--config", self.scenario_path,
                "--seed", str(seed),
                "--quiet"
            ], capture_output=True, text=True)
            metrics = json.loads(result.stdout)
            all_metrics.append(metrics)

        return aggregate_metrics(all_metrics)

    def iterate(self) -> Policy:
        """Run one iteration of the optimization loop."""
        prompt = self._build_prompt()

        response = self.llm.generate(prompt)
        policy_json = self._extract_policy_json(response)

        # Validate against feature toggles
        validation = self._validate_policy(policy_json)
        if not validation.valid:
            retry_prompt = self._build_retry_prompt(validation.errors)
            response = self.llm.generate(retry_prompt)
            policy_json = self._extract_policy_json(response)

        metrics = self._run_simulations(policy_json, seeds=range(1, 11))

        self.history.append(IterationResult(
            iteration=len(self.history),
            policy=policy_json,
            metrics=metrics
        ))

        return policy_json
```

### 4.3 Prompt Template

```markdown
# SimCash Policy Optimization - Iteration {iteration}

## Your Role
You are an expert cash manager optimizing payment release timing in an RTGS
payment system. Your goal: minimize total costs while maintaining settlement
performance.

## Available Policy Elements (Restricted Schema)

{schema_docs}

**IMPORTANT**: You may ONLY use the actions, fields, and operators listed above.
The scenario has feature toggles that will reject policies using other elements.

## Current Policy
```json
{current_policy}
```

## Simulation Results (10 seeds)

| Metric | Mean | Std Dev | Min | Max |
|--------|------|---------|-----|-----|
| Total Cost | ${total_cost_mean} | ${total_cost_std} | ... | ... |
| Settlement Rate | {rate_mean}% | {rate_std}% | ... | ... |
| Overdraft Cost | ${overdraft_mean} | ... | ... | ... |
| Delay Cost | ${delay_mean} | ... | ... | ... |
| Deadline Penalties | ${deadline_mean} | ... | ... | ... |

## Cost Analysis
{automated_analysis}

## Previous Iterations
| Iter | Total Cost | Settlement Rate | Change |
|------|------------|-----------------|--------|
{iteration_history}

## Constraints
- Settlement rate must stay above 90%
- Maximum tree depth: 10 nodes
- Use ONLY elements from the schema above

## Instructions
1. Analyze the current policy's weaknesses
2. Propose a refined policy addressing the issues
3. Explain your reasoning
4. Output the complete new policy JSON

---

BEGIN YOUR RESPONSE:
```

---

## 5. Baselines and Evaluation

### 5.1 Baselines

| Baseline | Description | Expected Performance |
|----------|-------------|---------------------|
| FIFO | Release everything immediately | High overdraft, low delay |
| Deadline-5 | Release when ≤5 ticks to deadline | Low delay, moderate overdraft |
| Deadline-10 | Release when ≤10 ticks to deadline | Balance point |
| LiquidityAware-20% | Maintain 20% buffer before release | Conservative |
| Grid Search | Sweep urgency_threshold [1-20] × buffer [0-100k] | Exhaustive |

### 5.2 Evaluation Metrics

**Primary**:
- Total Cost (lower is better)
- Settlement Rate (constraint: ≥90%)

**Secondary**:
- Iterations to best policy
- Policy complexity (tree depth, node count)
- Generalization across seeds (train seeds vs. held-out seeds)

### 5.3 Ablation Studies

1. **Model Comparison**: Claude Opus vs Sonnet vs Haiku vs GPT-4
2. **Prompt Strategy**: Full history vs. rolling window vs. summarized
3. **Iteration Budget**: 5, 10, 25, 50 iterations
4. **Schema Detail**: Verbose vs. compact schema documentation

---

## 6. Implementation Plan

### Week 1-2: Infrastructure

1. **Create optimization harness**
   - Python script wrapping SimCash CLI
   - LLM API integration (Anthropic, OpenAI)
   - Result aggregation and logging

2. **Develop prompt templates**
   - Schema documentation formatting
   - Result summarization
   - Retry with error feedback

### Week 3-4: Baseline Experiments

1. Run all baselines on the scenario
2. Establish performance bounds
3. Characterize cost trade-off surface
4. Validate experimental setup

### Week 5-6: LLM Experiments

1. Run optimization loops with different models
2. Collect convergence data
3. Analyze discovered policies
4. Compare to baselines

### Week 7-8: Analysis & Writing

1. Statistical analysis of results
2. Policy structure analysis (what patterns emerge?)
3. Paper writing

---

## 7. Expected Contributions

1. **Methodology**: LLM-as-optimizer framework for interpretable policy discovery in financial systems
2. **Tooling**: Integration pattern using SimCash feature toggles and schema generator
3. **Empirical Results**: Quantitative comparison of LLM optimization vs. grid search and heuristic baselines
4. **Policy Analysis**: Catalog of strategies discovered by LLMs and their characteristics

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM generates invalid policy | `validate-policy --scenario` catches violations; retry with error feedback |
| LLM overfits to training seeds | Evaluate on held-out seed ranges (seeds 1-10 for training, 11-20 for test) |
| LLM plateaus early | Try diverse prompt strategies; increase iteration budget |
| High variance across runs | Run multiple independent optimization trials; report confidence intervals |

---

## References

1. Bodislav, D.A., Bran, F., Petrescu, I.E., & Gomboș, C.C. (2024). The Integration of Machine Learning in Central Banks: Implications and Innovations. *European Journal of Sustainable Development*, 13(4), 23-32.

2. European Central Bank. TARGET2 Business Day. ECB Documentation.

3. Bank for International Settlements. (2023). AI/ML in Financial Market Infrastructures. CPMI Reports.

4. Wei, J., et al. (2022). Chain-of-thought prompting elicits reasoning in large language models. *NeurIPS*.

---

## Appendix A: Full LLM Prompt Example

```markdown
# SimCash Policy Optimization - Iteration 3

## Your Role
You are an expert cash manager optimizing payment release timing in an RTGS
payment system. Your goal: minimize total costs while maintaining settlement
performance.

## Available Policy Elements (Restricted Schema)

### Actions (payment_tree only)
- **Release**: Submit transaction to RTGS for immediate settlement
- **Hold**: Keep transaction in Queue 1, parameters: {reason: string}

### Fields
| Field | Type | Description |
|-------|------|-------------|
| ticks_to_deadline | f64 | Ticks until deadline (can be negative) |
| effective_liquidity | f64 | Balance + credit headroom |
| remaining_amount | f64 | Payment amount to settle |
| priority | f64 | Transaction priority (1-10) |
| is_past_deadline | f64 | 1.0 if overdue, else 0.0 |
| balance | f64 | Current account balance |
| day_progress_fraction | f64 | Progress through day (0.0-1.0) |
| is_eod_rush | f64 | 1.0 if in EOD rush period |

### Operators
- Comparison: <, <=, >, >=, ==, !=
- Logical: and, or
- Arithmetic: +, -, *, /

## Current Policy
```json
{
  "version": "1.0",
  "policy_id": "iter2",
  "parameters": {"urgency_threshold": 8.0, "buffer": 30000.0},
  "payment_tree": {
    "type": "condition",
    "node_id": "root",
    "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgency_threshold"}},
    "on_true": {"type": "action", "node_id": "release", "action": "Release"},
    "on_false": {
      "type": "condition",
      "node_id": "check_liq",
      "condition": {"op": ">=", "left": {"field": "effective_liquidity"}, "right": {"compute": {"op": "+", "left": {"field": "remaining_amount"}, "right": {"param": "buffer"}}}},
      "on_true": {"type": "action", "node_id": "rel2", "action": "Release"},
      "on_false": {"type": "action", "node_id": "hold", "action": "Hold"}
    }
  }
}
```

## Simulation Results (10 seeds)

| Metric | Mean | Std Dev |
|--------|------|---------|
| Total Cost | $892 | $45 |
| Settlement Rate | 96.2% | 1.1% |
| Overdraft Cost | $312 | $28 |
| Delay Cost | $380 | $32 |
| Deadline Penalties | $200 | $15 |

## Cost Analysis
- Delay costs are 43% of total - still significant
- Deadline penalties suggest some transactions barely miss deadlines
- Lowering urgency_threshold from 8 to 6 might reduce deadline penalties

## Previous Iterations
| Iter | Total Cost | Settlement Rate | Notes |
|------|------------|-----------------|-------|
| 0 | $1,450 | 94.1% | Baseline FIFO |
| 1 | $1,020 | 95.8% | Added urgency check |
| 2 | $892 | 96.2% | Added liquidity buffer |

## Instructions
1. Analyze weaknesses in current policy
2. Propose refined policy
3. Explain reasoning
4. Output complete JSON

---

BEGIN:
```

---

*Document generated for SimCash research initiative - Version 2.1*
