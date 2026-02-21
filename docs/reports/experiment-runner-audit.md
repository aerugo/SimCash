# Experiment Runner Optimization Loop — Detailed Audit

**Author:** Dennis (backend engineer audit)
**Date:** 2026-02-21
**Purpose:** Reference document for Nash's web implementation of the optimization loop.

---

## Table of Contents

1. [OptimizationLoop Overview](#1-optimizationloop-overview)
2. [PolicyOptimizer](#2-policyoptimizer)
3. [SystemPromptBuilder](#3-systempromptbuilder)
4. [SingleAgentContextBuilder (User Prompt)](#4-singleagentcontextbuilder)
5. [Bootstrap Support Structures](#5-bootstrap-support-structures)
6. [Experiment Config (exp2.yaml)](#6-experiment-config-exp2yaml)
7. [Key Differences for Web Implementation](#7-key-differences-for-web-implementation)

---

## 1. OptimizationLoop Overview

**File:** `experiments/runner/optimization.py` (~3257 lines)

### 1.1 Initialization

The `OptimizationLoop.__init__()` accepts:
- `config: ExperimentConfig` — all behavior is config-driven
- `config_dir` — for resolving relative scenario YAML paths
- `verbose_config`, `console` — optional logging
- `run_id` — auto-generated as `{name}-{timestamp}-{random_hex}`
- `repository` — optional persistence (SQLite)
- `persist_bootstrap` — flag to persist bootstrap sample sims

Key initialization steps:
1. **Convergence detector** — chosen by evaluation mode:
   - Bootstrap → `BootstrapConvergenceDetector(cv_threshold, window_size, regret_threshold, max_iterations)`
   - Deterministic → `ConvergenceDetector(stability_threshold, stability_window, max_iterations, improvement_threshold)`
2. **Constraints** from `config.get_constraints()` → `ScenarioConstraints`
3. **SeedMatrix** — pre-generates all seeds for the entire experiment:
   - `SeedMatrix(master_seed, max_iterations, agents, num_bootstrap_samples)`
   - Provides `get_iteration_seed(iteration_idx, agent_id)` and `get_bootstrap_seeds(iteration_idx, agent_id)`
4. **Per-agent iteration history** — `dict[str, list[SingleAgentIterationRecord]]` initialized empty for each optimized agent
5. **Per-agent best costs** — tracks `is_best_so_far` flag
6. **PolicyConfigBuilder** — `StandardPolicyConfigBuilder` for canonical parameter extraction
7. **ScenarioConfigBuilder** — lazy-initialized `StandardScenarioConfigBuilder`

### 1.2 Starting Policy / Fraction

**`_create_default_policy(agent_id)`** creates:
```python
{
    "version": "2.0",
    "policy_id": f"{agent_id}_default",
    "parameters": {
        "initial_liquidity_fraction": 0.5,  # ← THE STARTING FRACTION
    },
    "payment_tree": {
        "type": "action",
        "node_id": "default_release",
        "action": "Release",
    },
    "strategic_collateral_tree": {
        "type": "action",
        "node_id": "hold_collateral",
        "action": "HoldCollateral",
    },
}
```

**Critical:** The 0.5 starting fraction is **hardcoded** in `_create_default_policy()`. It's not in the experiment config. This is the starting point for ALL agents in ALL experiments. The LLM then optimizes from there.

The fraction is applied via `StandardPolicyConfigBuilder.extract_liquidity_config()` which reads `parameters.initial_liquidity_fraction` from the policy dict and sets it as `liquidity_allocation_fraction` on the agent config before simulation.

### 1.3 The Main Loop (`run()`)

```
while iteration < max_iterations:
    iteration++
    
    # Bootstrap mode: run context sim + create samples PER ITERATION
    if bootstrap:
        iteration_seed = seed_matrix.get_iteration_seed(iteration_idx, agents[0])
        initial_sim_result = _run_initial_simulation(seed=iteration_seed)
        _create_bootstrap_samples(seed=iteration_seed)
    
    # Evaluate current policies
    total_cost, per_agent_costs = _evaluate_policies()
    
    # Record metrics, check convergence
    convergence.record_metric(total_cost)
    iteration_history.append(total_cost)
    
    if converged: break
    
    # Optimize each agent
    for agent_id in optimized_agents:
        _optimize_agent(agent_id, per_agent_costs[agent_id])
    
    # Check multi-agent convergence (temporal mode)
    if temporal and _check_multiagent_convergence(): break
```

### 1.4 How It Calls the Optimizer

`_optimize_agent(agent_id, current_cost)` does:

1. Lazy-init `ExperimentLLMClient` and `PolicyOptimizer`
2. Get agent-specific customization from `config.prompt_customization.get_for_agent(agent_id)`
3. Build system prompt via `PolicyOptimizer.get_system_prompt(cost_rates, customization)`
4. Set system prompt on LLM client
5. Gather context:
   - `agent_context` from `_current_agent_contexts[agent_id]` (best/worst seed, stats)
   - `simulation_trace` — filtered events for this agent only (agent isolation)
   - `cost_breakdown` — aggregated from enriched results
   - `iteration_history` — from `_agent_iteration_history[agent_id]`
6. Call `PolicyOptimizer.optimize()` with all context
7. Call `_should_accept_policy()` for acceptance decision
8. Accept → update policy + record history; Reject → record rejection in history

### 1.5 Acceptance/Rejection Mechanism (`_should_accept_policy`)

Returns `(should_accept, old_cost, new_cost, deltas, delta_sum, evaluation, reason)`.

**Step 1:** Run paired evaluation via `_evaluate_policy_pair()`:
- Same seeds for old and new policy (paired comparison)
- Bootstrap mode: uses `BootstrapPolicyEvaluator.compute_paired_deltas(samples, policy_a, policy_b)`
- Deterministic mode: single seed, `old_cost - new_cost = delta`

**Step 2:** Check `delta_sum > 0` (mean improvement must be positive). If not → reject.

**Step 3:** If `acceptance.require_statistical_significance` is true:
- `_is_improvement_significant(evaluation)`:
  - Checks `confidence_interval_95[0] > 0` (CI lower bound strictly positive)
  - If CI lower bound ≤ 0 → reject ("95% CI includes zero")

**Step 4:** If `acceptance.max_coefficient_of_variation` is set:
- `_is_variance_acceptable(evaluation, max_cv)`:
  - Computes `CV = cost_std_dev / mean_new_cost`
  - If `CV > max_cv` → reject ("variance too high")

**Step 5:** All checks pass → accept.

**Temporal mode exception:** `_optimize_agent_temporal()` **always accepts** — no paired comparison. Convergence is detected by policy stability (all agents' `initial_liquidity_fraction` unchanged for `stability_window` iterations).

### 1.6 Seed Management

**SeedMatrix** is pre-generated at init:
- `master_seed` → derives all seeds deterministically
- `get_iteration_seed(iteration_idx, agent_id)` → per-iteration, per-agent seed
- `get_bootstrap_seeds(iteration_idx, agent_id)` → list of seeds for bootstrap samples

**INV-13: Bootstrap Seed Hierarchy:**
- Each iteration gets a fresh context simulation with iteration-specific seed
- Bootstrap samples are created from that iteration's context simulation
- Paired comparison uses the same samples for old and new policy

**Per-iteration bootstrap flow:**
1. `iteration_seed = seed_matrix.get_iteration_seed(iteration_idx, agents[0])`
2. `_run_initial_simulation(seed=iteration_seed)` — runs full sim, collects transaction history
3. `_create_bootstrap_samples(seed=iteration_seed)` — resamples from that history
4. `_evaluate_policies()` — evaluates current policy on bootstrap samples
5. `_evaluate_policy_pair()` — evaluates old vs new on same samples

### 1.7 Iteration History Tracking

`_record_iteration_history(agent_id, policy, cost, was_accepted)` creates a `SingleAgentIterationRecord`:
```python
SingleAgentIterationRecord(
    iteration=current_iteration,
    metrics={"total_cost_mean": cost},
    policy=policy.copy(),
    policy_changes=["Changed 'X': 0.5 → 0.3 (↓0.20)"],  # computed diff
    was_accepted=True/False,
    is_best_so_far=True/False,  # compared to agent_best_costs
    comparison_to_best="+$1.50 vs best" / "NEW BEST",
)
```

These records are passed to the LLM via `iteration_history` parameter — the LLM sees the full trajectory of accepted/rejected policies.

---

## 2. PolicyOptimizer

**File:** `ai_cash_mgmt/optimization/policy_optimizer.py`

### 2.1 Overview

`PolicyOptimizer` orchestrates the LLM call with retry logic:
- Builds the user prompt via `build_single_agent_context()`
- Appends the full policy section via `UserPromptBuilder`
- Validates response via `ConstraintValidator`
- Retries up to `max_retries` times on validation failure
- Adds validation errors to prompt on retry

### 2.2 System Prompt (cached)

Built once via `get_system_prompt(cost_rates, customization)`:
- Calls `build_system_prompt(constraints, cost_rates, customization)`
- Cache invalidated when `customization` changes or `set_cost_rates()` called
- Per-agent customization means the system prompt may be rebuilt per agent

### 2.3 User Prompt Construction

The `optimize()` method builds the user prompt:

```python
# 1. Build rich context (iteration history, metrics, simulation trace)
prompt = build_single_agent_context(
    current_iteration, current_policy, current_metrics,
    iteration_history, simulation_trace, sample_seed, sample_cost,
    mean_cost, cost_std, cost_breakdown, cost_rates, agent_id
)

# 2. Append full current policy tree
prompt += UserPromptBuilder(agent_id, current_policy)._build_policy_section()

# 3. On retry: append validation errors
if attempt > 0:
    prompt += "## VALIDATION ERROR - PLEASE FIX\n" + errors
```

### 2.4 Agent Isolation

Events are filtered before reaching the optimizer:
- If raw `events` are passed, they're filtered via `filter_events_for_agent(agent_id, events)`
- Only shows: outgoing transactions FROM agent, incoming TO agent, agent-specific state/costs
- Agent X never sees Agent Y's data

### 2.5 Iteration History Formatting

The history is passed as `list[SingleAgentIterationRecord]` and formatted by `SingleAgentContextBuilder._build_iteration_history_section()` into:
- Summary table with status icons (⭐ BEST, ✅ KEPT, ❌ REJECTED)
- Per-iteration details with parameter changes
- Policy parameters at each iteration as JSON

---

## 3. SystemPromptBuilder

**File:** `ai_cash_mgmt/prompts/system_prompt_builder.py`

### 3.1 Prompt Sections (in order)

1. **Expert Introduction** — "You are an expert in payment system optimization..."
2. **Experiment Customization** (if provided) — wrapped in `####` banner, from `config.prompt_customization`
3. **Domain Explanation** — RTGS, queuing, LSM (conditionally included based on `constraints.lsm_enabled`), key concepts
4. **Cost Objectives** — cost types (overdraft, delay, deadline, overdue, EOD), strategic considerations
5. **Policy Tree Architecture** — tree types filtered by `constraints.allowed_actions`, evaluation flow
6. **Optimization Process** — what data is provided, what to focus on, output requirements
7. **Pre-Generation Checklist** — mandatory checks (params defined, actions match trees, unique node_ids, etc.)
8. **Filtered Policy Schema** — `get_filtered_policy_schema(constraints)` — only shows allowed fields/actions
9. **Filtered Cost Schema** — `get_filtered_cost_schema(cost_rates)` — current cost rates
10. **Common Errors** — ERROR 1-5 (undefined param, wrong action, raw arithmetic, missing node_id, invalid field)
11. **Final Instructions** — generate complete JSON, keep trees 3-5 levels

### 3.2 Constraint-Aware Filtering

- Tree types only shown if they have allowed actions in constraints
- Evaluation flow steps only for enabled trees
- Common errors section only shows multi-tree examples if multiple tree types enabled
- LSM domain section only if `lsm_enabled`

---

## 4. SingleAgentContextBuilder

**File:** `ai_cash_mgmt/prompts/single_agent_context.py`

### 4.1 User Message Sections

The `SingleAgentContextBuilder.build()` produces 7 sections:

1. **Header** — agent ID, iteration number, table of contents
2. **Current State Summary** — table with mean cost, std dev, sample cost, settlement rate, failure rate; current policy parameters as JSON; delta from previous iteration
3. **Cost Analysis** — cost breakdown table (delay, collateral, overdraft, EOD) with percentages and priority indicators (🔴/🟡/🟢); cost rates config as JSON
4. **Optimization Guidance** — auto-generated based on cost analysis:
   - High delay → "Lower urgency_threshold, release payments earlier"
   - High collateral → "Lower initial_collateral_fraction"
   - High overdraft → "Increase liquidity_buffer"
   - High EOD → "Release aggressively near EOD"
   - Trend analysis (improving/worsening/oscillating)
   - Settlement rate warning if < 100%
5. **Simulation Output** — the representative simulation trace (tick-by-tick events) wrapped in `<simulation_trace>` tags
6. **Full Iteration History** — summary table + detailed per-iteration changes with:
   - Status (⭐ BEST / ✅ KEPT / ❌ REJECTED)
   - Metrics per iteration
   - Policy parameter changes (diffs)
   - Full parameters JSON per iteration
   - "Current Best Policy" highlight
7. **Parameter Trajectories** — per-parameter value table across iterations with trend analysis
8. **Final Instructions** — beat current best, maintain 100% settlement, incremental adjustments, learn from rejections

### 4.2 Data Flow

```
SingleAgentContext dataclass:
  agent_id: str
  current_iteration: int
  current_policy: dict
  current_metrics: dict  # total_cost_mean, settlement_rate_mean, etc.
  iteration_history: list[SingleAgentIterationRecord]
  simulation_trace: str | None  # tick-by-tick verbose output
  sample_seed: int
  sample_cost: int
  mean_cost: int
  cost_std: int
  cost_breakdown: dict[str, int]
  cost_rates: dict
```

---

## 5. Bootstrap Support Structures

**File:** `experiments/runner/bootstrap_support.py`

### 5.1 SimulationResult

Unified result from `_run_simulation()`:
- `seed`, `simulation_id`, `total_cost` (cents), `per_agent_costs`
- `events` (immutable tuple), `cost_breakdown` (CostBreakdown dataclass)
- `settlement_rate`, `avg_delay`, `verbose_output`

### 5.2 InitialSimulationResult

From `_run_initial_simulation()`:
- `events`, `agent_histories` (for bootstrap resampling)
- `total_cost`, `per_agent_costs`, `verbose_output`

### 5.3 BootstrapLLMContext

3 event streams for the LLM:
- **Stream 1:** Initial simulation (context sim)
- **Stream 2:** Best bootstrap sample (lowest cost)
- **Stream 3:** Worst bootstrap sample (highest cost)

Plus statistics: `mean_cost`, `cost_std`, `num_samples`

### 5.4 Paired Comparison (in _evaluate_policy_pair)

The actual paired comparison is done by `BootstrapPolicyEvaluator.compute_paired_deltas()`:
- Takes the same `BootstrapSample` list for both policies
- Evaluates each sample with old policy → `cost_a`
- Evaluates each sample with new policy → `cost_b`
- Returns `PairedDelta(sample_idx, seed, cost_a, cost_b, delta=cost_a - cost_b)`
- Positive delta = new policy is cheaper = improvement

The `PolicyPairEvaluation` aggregates:
- `delta_sum = sum(deltas)`
- `mean_old_cost`, `mean_new_cost`
- `cost_std_dev`, `confidence_interval_95` (computed from new policy costs)

---

## 6. Experiment Config (exp2.yaml)

**File:** `docs/papers/simcash-paper/paper_generator/configs/exp2.yaml`

### 6.1 All Fields

| Field | Value | Notes |
|-------|-------|-------|
| `name` | `exp2` | Experiment identifier |
| `description` | "12-Period Stochastic LVTS-Style" | |
| `scenario` | `./exp2_12period.yaml` | Relative path to scenario YAML |
| **evaluation** | | |
| `evaluation.mode` | `bootstrap` | Options: `bootstrap`, `deterministic-pairwise`, `deterministic-temporal` |
| `evaluation.num_samples` | `50` | Number of bootstrap samples |
| `evaluation.ticks` | `12` | Simulation length in ticks |
| `evaluation.acceptance.require_statistical_significance` | `true` | Reject if 95% CI crosses zero |
| `evaluation.acceptance.max_coefficient_of_variation` | `0.5` | Reject if CV > 50% |
| **convergence** | | |
| `convergence.max_iterations` | `25` | Hard cap on iterations |
| `convergence.stability_threshold` | `0.05` | For deterministic convergence detector |
| `convergence.stability_window` | `5` | Consecutive stable iterations needed |
| **llm** | | |
| `llm.model` | `openai:gpt-5.2` | |
| `llm.temperature` | `0.5` | |
| `llm.max_retries` | `3` | Validation retry attempts |
| `llm.timeout_seconds` | `900` | 15 minutes |
| `llm.reasoning_effort` | `high` | |
| `llm.reasoning_summary` | `detailed` | |
| **policy_constraints** | | |
| `policy_constraints.allowed_parameters` | `[initial_liquidity_fraction: float 0.0-1.0]` | Only one parameter! |
| `policy_constraints.allowed_fields` | `[system_tick_in_day, balance, amount, remaining_amount, ticks_to_deadline]` | Fields LLM can reference |
| `policy_constraints.allowed_actions` | `{payment_tree: [Release, Hold], bank_tree: [NoAction]}` | No strategic_collateral_tree |
| **prompt_customization** | | |
| `prompt_customization.all` | Long text about the fundamental tradeoff | Applied to ALL agents |
| **optimized_agents** | `[BANK_A, BANK_B]` | |
| **output** | | |
| `output.directory` | `results` | |
| `output.database` | `exp2.db` | |
| `output.verbose` | `true` | |
| **master_seed** | `42` | Root seed for all determinism |

### 6.2 Notable Config Details

- **`prompt_customization.all`** — applies to all agents. Can also have per-agent keys (e.g., `BANK_A:`)
- **No `strategic_collateral_tree`** in allowed_actions — liquidity_pool mode handles allocation at sim start
- **`acceptance` is nested under `evaluation`** — controls risk-adjusted acceptance
- **`convergence.stability_window: 5`** with bootstrap mode → `BootstrapConvergenceDetector` uses `window_size=5`
- **Bootstrap mode convergence** uses CV threshold, trend analysis, and regret threshold (from convergence config), NOT simple stability_threshold

---

## 7. Key Differences for Web Implementation

### 7.1 Starting Fraction

- **Backend:** Hardcoded `0.5` in `_create_default_policy()` — NOT configurable via experiment YAML
- **Web:** Should probably make this configurable, or at minimum match the 0.5 default
- **How it's applied:** `StandardPolicyConfigBuilder.extract_liquidity_config()` reads `parameters.initial_liquidity_fraction` and sets `liquidity_allocation_fraction` on agent config

### 7.2 Acceptance/Rejection

- **Backend:** 3-layer acceptance check:
  1. `delta_sum > 0` (always)
  2. CI lower bound > 0 (if `require_statistical_significance`)
  3. CV ≤ threshold (if `max_coefficient_of_variation` set)
- **Web must implement:** Paired comparison on same bootstrap samples. The `BootstrapPolicyEvaluator.compute_paired_deltas()` is the core — both policies evaluated on identical samples.
- **Temporal mode:** No acceptance check — always accepts. Convergence by policy stability.

### 7.3 Prompt Construction

- **System prompt:** Built once per agent per experiment (cached). Contains ~12 sections. Constraint-filtered (only shows allowed trees/actions/fields).
- **User prompt:** ~50k+ tokens. Built per LLM call. Contains: current metrics, cost analysis, optimization guidance, simulation trace, full iteration history with accept/reject status, parameter trajectories.
- **Web must pass:** `iteration_history` with `was_accepted` and `is_best_so_far` flags — the LLM uses these to avoid repeating rejected changes.

### 7.4 Experiment Config Fields

Fields the web must support or map:
- `evaluation.mode` — determines convergence detector type and evaluation flow
- `evaluation.acceptance.*` — risk-adjusted acceptance criteria
- `evaluation.num_samples` — number of bootstrap samples (50 for exp2)
- `convergence.*` — max_iterations, stability_window, stability_threshold
- `policy_constraints.*` — allowed_parameters (with min/max), allowed_fields, allowed_actions per tree
- `prompt_customization` — injected into system prompt, can be per-agent or `all`
- `master_seed` — root of all determinism

### 7.5 Seed Management

- **SeedMatrix** pre-generates ALL seeds at experiment start (not lazily)
- Seeds are per `(iteration, agent_id)` — agents get different seed streams
- Bootstrap samples per iteration are derived from iteration seed
- **Critical for reproducibility:** same master_seed → same seeds → same results
- **Web must:** Either use SeedMatrix or replicate its deterministic derivation

### 7.6 Bootstrap Flow Per Iteration

```
1. iteration_seed = SeedMatrix.get_iteration_seed(i, agent[0])
2. Run context simulation with iteration_seed → InitialSimulationResult
3. Collect transaction history from context sim
4. Bootstrap resample history → N samples
5. Evaluate current policy on N samples → mean cost (displayed cost)
6. For each agent:
   a. Build LLM context (filtered events, iteration history, cost breakdown)
   b. Call LLM → new_policy
   c. Evaluate old vs new policy on SAME N samples (paired)
   d. Accept/reject based on delta_sum, CI, CV
```

### 7.7 Agent Isolation

The experiment runner is strict about agent isolation:
- Events filtered via `filter_events_for_agent()` — only agent's own transactions
- Iteration history is per-agent (separate lists)
- LLM never sees other agents' policies or costs
- `SingleAgentContextBuilder` enforces this at the prompt level

### 7.8 Convergence Detection

Two modes:
- **BootstrapConvergenceDetector:** CV threshold, trend analysis, regret threshold, window
- **ConvergenceDetector:** Simple stability threshold (cost change < threshold for N iterations)
- **Temporal mode:** Policy stability (all agents' `initial_liquidity_fraction` unchanged for `stability_window` iterations)

---

## Summary for Nash

The core optimization loop is:
1. Start with `initial_liquidity_fraction = 0.5` for all agents
2. Each iteration: run context sim → bootstrap resample → evaluate → optimize each agent
3. LLM gets ~50k token context with full history, simulation trace, cost analysis
4. New policy accepted only if paired bootstrap shows statistically significant improvement
5. Repeat until converged or max iterations

The web implementation needs:
- `BootstrapPolicyEvaluator.compute_paired_deltas()` for acceptance
- `SeedMatrix` for deterministic seed management
- `SingleAgentContextBuilder` for prompt construction
- `SystemPromptBuilder` for system prompt with constraint filtering
- Iteration history tracking with accept/reject/best flags
- Agent isolation in all LLM context
