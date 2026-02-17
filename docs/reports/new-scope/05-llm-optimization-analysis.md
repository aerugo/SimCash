# LLM Optimization System Analysis

> Deep analysis of the AI Cash Management module: architecture, capabilities, current usage, and extension potential.

**Date**: 2025-02-17
**Status**: Complete analysis of `api/payment_simulator/ai_cash_mgmt/` and `experiments/runner/`

---

## Table of Contents

1. [End-to-End Optimization Loop](#1-end-to-end-optimization-loop)
2. [What the LLM Actually Optimizes](#2-what-the-llm-actually-optimizes)
3. [Prompt Engineering System](#3-prompt-engineering-system)
4. [Constraint Validation System](#4-constraint-validation-system)
5. [Bootstrap Evaluation System](#5-bootstrap-evaluation-system)
6. [Experiment Configuration](#6-experiment-configuration)
7. [Experiment Comparison: exp1, exp2, exp3](#7-experiment-comparison)
8. [PolicyOptimizer Class](#8-policyoptimizer-class)
9. [What the LLM CAN Optimize vs What It Currently DOES](#9-can-vs-does)
10. [Extension to Complex Policies](#10-extension-to-complex-policies)
11. [Multi-Agent Isolation](#11-multi-agent-isolation)

---

## 1. End-to-End Optimization Loop

The optimization loop is implemented in `OptimizationLoop` (`experiments/runner/optimization.py`, ~3200 lines). The flow differs by evaluation mode but follows this general structure:

### Loop Structure

```
For each iteration (up to max_iterations):
  1. CONTEXT SIMULATION
     - Run a full simulation with iteration-specific seed (from SeedMatrix)
     - Capture all events tick-by-tick
     - Collect transaction history for bootstrap resampling
     
  2. EVALUATE CURRENT POLICIES
     - Bootstrap mode: Resample transactions, evaluate on N samples → mean cost
     - Deterministic mode: Single simulation → exact cost
     - Build per-agent contexts (best/worst seed, cost breakdown)
     
  3. CHECK CONVERGENCE
     - Bootstrap: BootstrapConvergenceDetector (CV threshold, trend, regret)
     - Deterministic: ConvergenceDetector (stability threshold over window)
     - If converged → break
     
  4. FOR EACH AGENT:
     a. Build system prompt (schema-filtered, constraint-aware)
     b. Build user prompt (50k+ tokens of context)
     c. Call LLM → get proposed policy JSON
     d. Validate against ScenarioConstraints (retry up to max_retries)
     e. Evaluate old vs new policy on SAME samples (paired comparison)
     f. Accept if statistically significant improvement (bootstrap)
        or if new_cost < old_cost (deterministic-pairwise)
        or always accept (deterministic-temporal)
     g. Record iteration history for future LLM context
```

### Seed Hierarchy (INV-13)

All randomness flows through `SeedMatrix`:
```
master_seed (42)
├── iteration_seed[i, agent] = SHA-256(master_seed, iter=i, agent=A)
│   ├── context simulation runs with this seed
│   └── bootstrap samples seeded from this
└── Guarantees: same master_seed → identical trajectory
```

### Three Evaluation Modes

| Mode | Acceptance | Convergence | Use Case |
|------|-----------|-------------|----------|
| `bootstrap` | Statistical significance (95% CI) + variance check | CV threshold + trend + regret | Stochastic scenarios |
| `deterministic-pairwise` | `new_cost < old_cost` on same seed | Cost stability window | Single-agent deterministic |
| `deterministic-temporal` | Always accept | Policy stability (all agents unchanged for N iterations) | Multi-agent Nash equilibrium |

---

## 2. What the LLM Actually Optimizes

### Current State: Narrow

In all three experiments (exp1, exp2, exp3), the LLM optimizes **exactly one parameter**: `initial_liquidity_fraction` — a float ∈ [0.0, 1.0] representing what fraction of the liquidity pool to allocate at the start of the simulated day.

The payment tree is guided to remain a trivial "Release all" action. The bank tree is fixed to "NoAction". No collateral trees are used (liquidity_pool mode replaces collateral).

**The prompt customization explicitly tells the LLM:**
> "Focus your optimization on the `initial_liquidity_fraction` parameter. The payment_tree should remain a simple Release action."

### What It Produces

The LLM outputs a complete policy JSON:
```json
{
  "version": "2.0",
  "policy_id": "...",
  "parameters": {"initial_liquidity_fraction": 0.45},
  "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
  "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"}
}
```

The `initial_liquidity_fraction` parameter is extracted by `StandardPolicyConfigBuilder.extract_liquidity_config()` and applied as the agent's `liquidity_allocation_fraction` in the scenario config before simulation.

### What It CAN Produce

The system is architecturally capable of much more — the LLM can generate **full decision trees** with:
- **Condition nodes**: Compare fields against parameters or values using any operator
- **Nested branches**: Arbitrary depth (recommended 3-5 levels)
- **Multiple tree types**: payment_tree, bank_tree, strategic_collateral_tree, end_of_tick_collateral_tree
- **Rich conditions**: Using any combination of allowed fields (balance, ticks_to_deadline, queue state, etc.)
- **Arithmetic**: Compute expressions like `balance * 0.5` wrapped in `{"compute": {...}}`
- **Multiple parameters**: Any number of tunable numeric or enum parameters

---

## 3. Prompt Engineering System

The prompt system has two layers: a **system prompt** (built once per session, ~10-15k tokens) and a **user prompt** (built per-iteration, ~50k+ tokens).

### System Prompt (`system_prompt_builder.py`)

Built by `SystemPromptBuilder` with these sections:

1. **Expert Introduction** — "You are an expert in payment system optimization"
2. **Experiment Customization** — Injected from YAML `prompt_customization` field
3. **Domain Explanation** — RTGS, queuing, LSM (conditionally included based on `lsm_enabled`)
4. **Cost Objectives** — What costs exist and why optimization is non-trivial
5. **Policy Tree Architecture** — Condition/action node structure, tree types (filtered by constraints)
6. **Optimization Process** — What the LLM receives and what it should output
7. **Pre-generation Checklist** — Mandatory validation items
8. **Filtered Policy Schema** — From Rust engine via `get_policy_schema()`, filtered to only show allowed elements
9. **Filtered Cost Schema** — From Rust engine via `get_cost_schema()`, with actual cost rates
10. **Common Errors** — Context-aware error examples (only for enabled tree types)
11. **Final Instructions** — Output requirements

### Schema Filtering (`schema_injection.py`)

**Critical design**: The system retrieves the full policy schema from the Rust engine (`get_policy_schema()`) and **filters it** based on `ScenarioConstraints`:
- Only allowed parameters are documented (with bounds)
- Only allowed fields are listed
- Only allowed actions per tree type are shown
- Only enabled tree types get error examples

This prevents LLM hallucination — it literally cannot see documentation for elements it's not allowed to use.

### User Prompt (`single_agent_context.py`)

Built by `SingleAgentContextBuilder` with 7 sections:

1. **Header** — Agent ID, iteration number, table of contents
2. **Current State Summary** — Mean cost, std dev, sample cost, settlement rate, current parameters
3. **Cost Analysis** — Breakdown by type (delay, collateral, overdraft, eod) with priority flags (🔴/🟡/🟢)
4. **Optimization Guidance** — Automated analysis: trend detection (improving/worsening/oscillating), dominant cost warnings, settlement rate alerts
5. **Simulation Output** — Tick-by-tick event trace from representative sample (filtered for agent isolation)
6. **Iteration History** — Full table of all iterations with status (⭐ BEST / ✅ KEPT / ❌ REJECTED), per-iteration parameter diffs
7. **Parameter Trajectories** — Tables showing how each parameter evolved, with trend analysis
8. **Final Instructions** — Beat current best, maintain 100% settlement, learn from rejections

### Event Filtering (`event_filter.py`)

Events are filtered per-agent for isolation:
- **Outgoing**: Arrivals where agent is sender, policy decisions, RTGS settlements
- **Incoming**: Settlements where agent is receiver, queue releases
- **Own state**: Collateral posts/withdrawals, cost accruals, budget sets
- **General**: End-of-day, scenario events
- **Excluded**: All other agents' internal events

Formatted with rich emoji indicators (📤 Outgoing, 💰 Received, ✅ Settled, ⚠️ Overdue, etc.)

---

## 4. Constraint Validation System

### ScenarioConstraints (`constraints/scenario_constraints.py`)

Defines the policy search space with three dimensions:

| Dimension | Purpose | Example |
|-----------|---------|---------|
| `allowed_parameters` | List of `ParameterSpec` with name, type, bounds | `initial_liquidity_fraction: float [0.0, 1.0]` |
| `allowed_fields` | Context fields for conditions | `balance`, `ticks_to_deadline`, `queue1_total_value` |
| `allowed_actions` | Actions per tree type | `payment_tree: [Release, Hold]` |

### ParameterSpec (`constraints/parameter_spec.py`)

Each parameter has:
- `name`, `param_type` (int/float/enum)
- `min_value`, `max_value` for numeric
- `allowed_values` for enum
- `description` for LLM context
- `validate_value()` → `(is_valid, error_message)`

### ConstraintValidator (`optimization/constraint_validator.py`)

Validates LLM output recursively:
- Checks all parameters are known and within bounds
- Checks all field references are allowed
- Checks all actions match their tree type
- Checks nested branches recursively
- Returns `ValidationResult(is_valid, errors)`

### Retry Loop

On validation failure, errors are appended to the prompt:
```
## VALIDATION ERROR - PLEASE FIX
Your previous attempt failed validation:
  - Unknown parameter: foo
  - Invalid action 'Split' for payment_tree. Allowed: ['Release', 'Hold']
Please fix these issues in your response.
```

Up to `max_retries` (default 3) attempts before giving up.

### Pre-defined Constraint Sets

| Set | Parameters | Actions | Use Case |
|-----|-----------|---------|----------|
| `CASTRO_CONSTRAINTS` | liquidity_fraction, urgency_threshold, buffer | Release/Hold only | Paper replication |
| `MINIMAL_CONSTRAINTS` | urgency_threshold only | Release/Hold only | Simple experiments |
| `STANDARD_CONSTRAINTS` | 4 parameters | + Split, Borrow/Repay | Typical experiments |
| `FULL_CONSTRAINTS` | 10+ parameters | All actions | Maximum flexibility |

---

## 5. Bootstrap Evaluation System

### Paired Comparison Design

The bootstrap system evaluates policies using **paired comparison** — the key statistical insight:

```
For each of N bootstrap samples:
  old_cost[i] = simulate(old_policy, sample_i)
  new_cost[i] = simulate(new_policy, sample_i)  ← SAME sample!
  delta[i] = old_cost[i] - new_cost[i]

Accept if mean(delta) > 0 AND statistically significant
```

By using the **same samples** for both policies, sample-to-sample variance is eliminated. The variance of the paired difference is:
```
Var(delta) = Var(A) + Var(B) - 2*Cov(A,B)
```
Since A and B are positively correlated (same market conditions), Cov(A,B) is large, making Var(delta) small.

### 3-Agent Sandbox Architecture

Policy evaluation uses an isolated sandbox:
```
SOURCE → AGENT → SINK
```
- **SOURCE**: Infinite liquidity, sends transactions to AGENT
- **AGENT**: The agent being evaluated
- **SINK**: Receives AGENT's outgoing payments

**Justification**: Settlement timing is a **sufficient statistic** for the agent's decision problem. The agent can't observe other agents' internal state, only the timing of incoming settlements. The sandbox preserves `settlement_offset` from historical data, providing statistically equivalent conditions.

**Limitation**: Breaks down when agent's policy materially affects system liquidity (large market share, bilateral concentration, strategic counterparties).

### Statistical Acceptance Criteria (Bootstrap Mode)

Two-gate acceptance:

1. **Statistical Significance** (`_is_improvement_significant`):
   - Mean delta must be positive
   - 95% confidence interval lower bound must be > 0
   - If CI crosses zero → reject (improvement might be noise)

2. **Variance Check** (`_is_variance_acceptable`):
   - Coefficient of variation (CV = std_dev / mean) must be ≤ `max_cv` (default 0.5)
   - Prevents accepting low-mean but high-variance policies

### Convergence Detection

**BootstrapConvergenceDetector**: Uses CV threshold, trend analysis, and regret threshold.

**ConvergenceDetector** (deterministic): Cost must change by less than `stability_threshold` for `stability_window` consecutive iterations. Since deterministic evaluation gives identical cost for identical policy, this effectively means "no accepted policy changes for N iterations."

---

## 6. Experiment Configuration

### YAML Structure

```yaml
name: exp1                           # Experiment identifier
description: "..."                   # Human description
scenario: ./exp1_2period.yaml        # Scenario config (relative path)

evaluation:
  mode: bootstrap|deterministic-temporal|deterministic-pairwise
  num_samples: 50                    # Bootstrap samples
  ticks: 12                          # Simulation length
  acceptance:                        # Bootstrap only
    require_statistical_significance: true
    max_coefficient_of_variation: 0.5

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5

llm:
  model: "openai:gpt-5.2"
  temperature: 0.5
  max_retries: 3
  timeout_seconds: 900
  reasoning_effort: "high"
  reasoning_summary: "detailed"

policy_constraints:                  # Inline ScenarioConstraints
  allowed_parameters: [...]
  allowed_fields: [...]
  allowed_actions: {...}

prompt_customization:                # Injected into system prompt
  all: |
    This scenario tests...

optimized_agents: [BANK_A, BANK_B]

output:
  directory: results
  database: exp1.db

master_seed: 42
```

### Key Configuration Decisions

- **`evaluation.mode`** determines the entire acceptance/convergence strategy
- **`policy_constraints`** defines the policy search space (what the LLM can generate)
- **`prompt_customization`** provides domain-specific guidance without revealing the answer
- **`master_seed`** guarantees reproducibility via SeedMatrix hierarchy

---

## 7. Experiment Comparison: exp1, exp2, exp3

| Aspect | exp1 | exp2 | exp3 |
|--------|------|------|------|
| **Name** | 2-Period Deterministic | 12-Period Stochastic | Three-Period Dummy |
| **Ticks** | 2 | 12 | 3 |
| **Arrivals** | Deterministic | Poisson/LogNormal stochastic | Deterministic |
| **Eval Mode** | `deterministic-temporal` | `bootstrap` | `deterministic-temporal` |
| **Samples** | 50 (unused for acceptance) | 50 (paired comparison) | 50 (unused for acceptance) |
| **Agents** | BANK_A, BANK_B | BANK_A, BANK_B | BANK_A, BANK_B |
| **Optimized Param** | `initial_liquidity_fraction` | `initial_liquidity_fraction` | `initial_liquidity_fraction` |
| **Allowed Actions** | Release, Hold / NoAction | Release, Hold / NoAction | Release, Hold / NoAction |
| **Extra Fields** | — | amount, remaining_amount | queue1_total_value, outgoing_queue_size |
| **Purpose** | Nash equilibrium validation | Realistic LVTS-style | Joint liquidity & timing |
| **Convergence** | Policy stability | Statistical (CI, CV, regret) | Policy stability |
| **Expected Result** | Nash equilibrium fraction | Both agents 10-30% range | Joint optimization |

### Key Differences

1. **exp1** validates the simplest case — 2 ticks, deterministic, testing if LLM finds Nash equilibrium
2. **exp2** is the realistic case — stochastic arrivals, bootstrap evaluation, statistical acceptance
3. **exp3** adds queue state fields (`queue1_total_value`, `outgoing_queue_size`) to potentially enable payment timing decisions beyond just liquidity allocation, but the prompt customization still directs focus to `initial_liquidity_fraction`

All three experiments are essentially **the same optimization problem** (tune one float parameter) in different scenario configurations.

---

## 8. PolicyOptimizer Class

**File**: `ai_cash_mgmt/optimization/policy_optimizer.py`

### Architecture

```
PolicyOptimizer
├── _constraints: ScenarioConstraints
├── _validator: ConstraintValidator
├── _system_prompt: str (cached, rebuilt on customization change)
├── _cost_rates: dict (for system prompt)
│
├── get_system_prompt(cost_rates, customization) → str
│   └── Calls build_system_prompt() with schema filtering
│
├── set_cost_rates(rates) → invalidates cache
│
└── optimize(agent_id, current_policy, ...) → OptimizationResult
    ├── Build user prompt via build_single_agent_context()
    ├── Append full policy section via UserPromptBuilder
    ├── Append validation errors if retry
    ├── Call llm_client.generate_policy()
    ├── Validate via ConstraintValidator
    ├── Retry loop (up to max_retries)
    └── Return OptimizationResult
```

### Key Design Features

1. **System prompt caching**: Built once, invalidated when customization changes
2. **Agent isolation**: Events filtered by `filter_events_for_agent()` before reaching prompt
3. **Retry with feedback**: Validation errors included in subsequent attempts
4. **Debug callbacks**: Protocol-based hooks for verbose logging
5. **Backward compatibility**: Old parameter names (best_seed_output, etc.) still accepted

### OptimizationResult

```python
@dataclass
class OptimizationResult:
    agent_id: str
    iteration: int
    old_policy: dict
    new_policy: dict | None        # None if all retries failed
    old_cost: float
    new_cost: float | None         # Not evaluated at this stage
    was_accepted: bool             # True = passed validation
    validation_errors: list[str]
    llm_latency_seconds: float
    tokens_used: int
    llm_model: str
```

Note: `was_accepted` at this stage means "passed validation", NOT "passed cost comparison." The cost-based acceptance happens later in `_optimize_agent()`.

---

## 9. What the LLM CAN Optimize vs What It Currently DOES

### Currently DOES Optimize

| Aspect | Current State |
|--------|---------------|
| Parameter | `initial_liquidity_fraction` (1 float) |
| Payment tree | Trivial "Release" action (no conditions) |
| Bank tree | Fixed "NoAction" |
| Collateral trees | Not used (liquidity_pool mode) |
| Decision complexity | None — just tuning a scalar |

### CAN Optimize (Architecture Supports)

| Aspect | Capability |
|--------|-----------|
| **Multiple parameters** | Any number of named parameters with type/range constraints |
| **Payment decision trees** | Full condition/action trees: when to Release vs Hold vs Split based on balance, urgency, queue pressure, time of day |
| **Bank-level decisions** | Borrow, Repay, NoAction — liquidity management strategy |
| **Strategic collateral** | PostCollateral, WithdrawCollateral, HoldCollateral — collateral optimization |
| **End-of-tick collateral** | Fine-grained collateral adjustments per tick |
| **Nested conditions** | Arbitrary depth (3-5 levels recommended) with AND/OR/NOT logic |
| **Arithmetic expressions** | `balance * 0.5`, `amount + liquidity_buffer`, `min(a, b)` |
| **14+ context fields** | balance, effective_liquidity, credit_limit, ticks_to_deadline, amount, priority, queue state, collateral state, time |
| **Rich actions** | Split with configurable count, ReleaseWithCredit, priority-based routing |

### The Gap

The system is a **general-purpose policy optimization engine** being used as a **scalar parameter tuner**. The entire prompt engineering system (50k+ tokens of simulation traces, cost breakdowns, iteration histories) is dramatically overengineered for finding a single float — but it's perfectly designed for the much harder problem of optimizing full decision trees.

---

## 10. Extension to Complex Policies

### Path 1: Expand the Allowed Set (Minimal Code Changes)

To optimize full payment decision trees, only YAML configuration changes are needed:

```yaml
policy_constraints:
  allowed_parameters:
    - name: initial_liquidity_fraction
      param_type: float
      min_value: 0.0
      max_value: 1.0
    - name: urgency_threshold
      param_type: int
      min_value: 0
      max_value: 20
      description: "Ticks before deadline when payment becomes urgent"
    - name: liquidity_buffer
      param_type: float
      min_value: 0.5
      max_value: 3.0
      description: "Multiplier for required balance buffer"

  allowed_fields:
    - system_tick_in_day
    - ticks_remaining_in_day
    - balance
    - effective_liquidity
    - ticks_to_deadline
    - remaining_amount
    - amount
    - priority
    - queue1_total_value
    - outgoing_queue_size

  allowed_actions:
    payment_tree:
      - Release
      - Hold
      - Split
    bank_tree:
      - Borrow
      - Repay
      - NoAction
    strategic_collateral_tree:
      - PostCollateral
      - WithdrawCollateral
      - HoldCollateral
```

The system prompt builder will automatically:
- Document all allowed parameters with bounds
- Show all allowed fields
- Show allowed actions per tree type with descriptions from Rust schema
- Include relevant error examples
- Filter out everything else

**No Python code changes needed.** The PolicyOptimizer, ConstraintValidator, and schema injection already handle arbitrary constraint sets.

### Path 2: Richer Prompt Customization

The `prompt_customization` field in YAML supports per-agent and global guidance:

```yaml
prompt_customization:
  all: |
    General guidance for all agents...
  BANK_A: |
    Agent-specific guidance...
```

For complex policy optimization, the customization could explain the strategic tradeoffs without revealing the optimal solution:
- "Large payments near deadline should generally be released even at overdraft risk"
- "Consider holding small non-urgent payments when queue pressure is high"
- "Collateral posting is expensive but prevents overdraft costs"

### Path 3: Castro Paper Alignment Mode

The system has a `castro_mode` flag and pre-built Castro constraints with specific rules:
- Initial liquidity decision at t=0 only (collateral tree guarded by `tick == 0`)
- Release/Hold payment decisions for t=1,...,T-1
- Cost structure: r_c < r_d < r_b (collateral < delay < borrowing)

This demonstrates the system's ability to enforce structural policy constraints beyond just parameter bounds.

### Path 4: Full Simulation Features

The Rust engine supports features not currently exercised by any experiment:
- **LSM bilateral/multilateral offsets** — netting between agents
- **Priority escalation** — automatic urgency increase near deadline
- **Split payments** — dividing large transactions
- **Credit limits** — daylight overdraft management
- **Multi-day simulations** — end-of-day settlements and overnight positions

Enabling these requires:
1. Scenario config changes (enable LSM, credit limits, etc.)
2. Wider constraint sets (more actions, fields)
3. Potentially more evaluation samples (more variance sources)

---

## 11. Multi-Agent Isolation

### Design Principle

Each agent's LLM call sees **only their own data**. This is enforced at multiple levels:

### Level 1: SingleAgentContextBuilder

The `build_single_agent_context()` function takes only ONE agent's data:
```python
# CRITICAL ISOLATION: This function creates a context that contains ONLY
# the specified agent's data.
```

- `current_policy`: Only this agent's policy
- `iteration_history`: Only this agent's history (separate `_agent_iteration_history` dict)
- `current_metrics`: Aggregated from this agent's samples

### Level 2: Event Filtering

`filter_events_for_agent()` enforces per-event filtering:
- Outgoing transactions: only where `sender_id == agent_id`
- Incoming settlements: only where `receiver_id == agent_id`
- State changes: only where `agent_id` matches
- Cost accruals: only this agent's costs

### Level 3: Bootstrap Evaluation

Each agent gets separate bootstrap samples:
```python
for agent_id in self.optimized_agents:
    samples = self._bootstrap_sampler.generate_samples(
        agent_id=agent_id, ...)
    self._bootstrap_samples[agent_id] = samples
```

Seeds are agent-specific: `SeedMatrix.get_iteration_seed(iteration, agent_id)` — different agents get different seeds for the same iteration.

### Level 4: Iteration History Tracking

Per-agent history is maintained separately:
```python
self._agent_iteration_history: dict[str, list[SingleAgentIterationRecord]] = {
    agent_id: [] for agent_id in config.optimized_agents
}
```

Each `SingleAgentIterationRecord` contains only that agent's metrics, policy, policy_changes, and acceptance status.

### Level 5: Per-Agent Best Cost Tracking

```python
self._agent_best_costs: dict[str, int] = {}
```

The `is_best_so_far` flag in history records is computed per-agent, not globally.

### Why This Matters

Multi-agent isolation is essential for the Nash equilibrium finding property in temporal mode. Each agent independently optimizes against the current state of the world (which includes other agents' policies as part of the environment). If agents could see each other's policies, they could game the optimization or converge to coordinated solutions that aren't Nash equilibria.

---

## Summary: Key Findings

### 1. Massive Under-Utilization
The LLM optimization system is architecturally capable of optimizing **full decision trees with multiple parameters, conditional logic, arithmetic expressions, and multiple tree types**. Currently it's being used to tune **one float parameter**. This is like using a Formula 1 car to go grocery shopping.

### 2. Zero Code Changes for Extension
Expanding what the LLM optimizes requires only YAML configuration changes (wider `policy_constraints`). The entire prompt engineering, validation, and evaluation pipeline is generic.

### 3. Robust Statistical Foundation
The bootstrap paired comparison with statistical significance testing and variance checks is genuinely well-designed for policy evaluation. The 3-agent sandbox with sufficient statistic justification is theoretically sound for the current use case.

### 4. Production-Grade Prompt Engineering
The 50k+ token prompt system with schema filtering, event filtering, iteration history, parameter trajectories, and automated guidance is sophisticated. It would be highly effective for complex decision tree optimization — it's just not being exercised.

### 5. Clean Multi-Agent Architecture
Agent isolation is enforced at 5 levels, enabling Nash equilibrium finding via independent optimization. The temporal mode's policy stability convergence is a reasonable approximation of Nash equilibrium.

### 6. Ready for Complex Experiments
To test the system's full potential, the next step is an experiment that allows the LLM to optimize **payment timing decisions** (not just initial liquidity), using wider constraint sets and richer scenarios. The infrastructure is ready — only the YAML config needs to change.
