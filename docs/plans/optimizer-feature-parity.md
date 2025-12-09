# Optimizer Feature Parity: ai_cash_mgmt vs Castro Experiments

**Date**: 2024-12-09
**Status**: Planning
**Priority**: High

## Executive Summary

The `ai_cash_mgmt` module and `experiments/new-castro` implementation are missing critical features that make the original Castro experiments effective at LLM-based policy optimization. This document details the gaps and provides a roadmap for achieving feature parity.

**Key Finding**: The original Castro experiments achieved policy improvements because they provided the LLM with **rich, structured context** including tick-by-tick simulation output, cost breakdowns, parameter trajectories, and optimization guidance. The new implementation provides almost none of this context, causing the LLM to "fly blind."

---

## Table of Contents

1. [Current State Comparison](#1-current-state-comparison)
2. [Critical Missing Features](#2-critical-missing-features)
3. [Implementation Roadmap](#3-implementation-roadmap)
4. [Code References](#4-code-references)
5. [API Token Budget](#5-api-token-budget)
6. [Testing Strategy](#6-testing-strategy)

---

## 1. Current State Comparison

### 1.1 Context Richness

| Feature | Old Castro | New ai_cash_mgmt | Gap Severity |
|---------|------------|------------------|--------------|
| Verbose tick-by-tick output | ✅ Best & worst seeds | ❌ None | **CRITICAL** |
| Cost breakdown by type | ✅ Delay, collateral, overdraft, EOD | ❌ Total only | **CRITICAL** |
| Parameter trajectories | ✅ Full history with trends | ❌ None | **HIGH** |
| Policy diffs | ✅ Shows what changed | ❌ None | **HIGH** |
| Optimization guidance | ✅ Context-aware recommendations | ❌ None | **HIGH** |
| Iteration history with acceptance | ✅ Full with rejection reasons | ❌ Basic cost list | **MEDIUM** |
| Cost rate configuration | ✅ Included in context | ❌ Not included | **MEDIUM** |
| Risk-adjusted metrics | ✅ Mean + std dev | ❌ Mean only | **MEDIUM** |

### 1.2 Token Budget

| Setting | Old Castro | New ai_cash_mgmt | Recommendation |
|---------|------------|------------------|----------------|
| Max output tokens | 50,000+ | 16,384 | **32,000+** |
| Context window utilization | ~100k tokens | ~2k tokens | **50k+ tokens** |

### 1.3 LLM Integration

| Feature | Old Castro | New ai_cash_mgmt | Gap Severity |
|---------|------------|------------------|--------------|
| PydanticAI structured output | ✅ RobustPolicyAgent | ❌ Raw JSON parsing | **HIGH** |
| Reasoning effort parameter | ✅ Configurable | ✅ Added (gpt-5.1) | Fixed |
| Extended thinking (Claude) | ✅ thinking_budget | ❌ Not supported | **MEDIUM** |
| Retry with validation errors | ✅ Shows errors in retry prompt | ❌ Silent retry | **MEDIUM** |

---

## 2. Critical Missing Features

### 2.1 Verbose Simulation Output (CRITICAL)

The old Castro captures and provides **complete tick-by-tick logs** from:
- **Best performing seed**: Shows what went RIGHT
- **Worst performing seed**: Shows what went WRONG

This gives the LLM concrete examples of policy behavior, not just aggregate numbers.

**Current new-castro behavior**: No simulation output is captured or provided to the LLM.

**Reference Implementation**:
- Context builder: [`experiments/castro/prompts/context.py:348-385`](../../../experiments/castro/prompts/context.py#L348-L385)
- SimulationContext dataclass: [`experiments/castro/prompts/context.py:52-78`](../../../experiments/castro/prompts/context.py#L52-L78)

```python
# From old Castro - what the LLM receives:
"""
### Best Performing Seed (#42, Cost: $1,200)
This is the OPTIMAL outcome from the current policy. Analyze what went right.

<best_seed_output>
```
Tick 0: BANK_A posts $25,000 collateral (InitialAllocation)
Tick 0: BANK_B posts $15,000 collateral (InitialAllocation)
Tick 1: TX-001 ($10,000) A→B: RELEASED (balance sufficient)
Tick 1: TX-002 ($8,000) B→A: HELD (urgency_threshold=5, ticks_to_deadline=8)
...
```
</best_seed_output>
"""
```

### 2.2 Cost Breakdown by Type (CRITICAL)

The old Castro breaks down costs into categories with percentages and priority indicators:

```
| Cost Type | Amount | % of Total | Priority |
|-----------|--------|------------|----------|
| delay | $5,000 | 45% | 🔴 HIGH |
| collateral | $3,000 | 27% | 🟡 MEDIUM |
| overdraft | $2,000 | 18% | 🟡 MEDIUM |
| eod_penalty | $1,000 | 10% | 🟢 LOW |
```

This tells the LLM **where to focus optimization efforts**.

**Reference Implementation**:
- Cost analysis builder: [`experiments/castro/prompts/context.py:244-273`](../../../experiments/castro/prompts/context.py#L244-L273)

### 2.3 Optimization Guidance (HIGH)

The old Castro analyzes the current state and provides specific, actionable guidance:

```python
# From context.py:275-346
if delay_pct > 40:
    guidance.append(
        "⚠️ **HIGH DELAY COSTS** - Payments are waiting too long in queue.\n"
        "   Consider: Lower urgency_threshold, reduce liquidity_buffer, "
        "release payments earlier."
    )
if collateral_pct > 40:
    guidance.append(
        "⚠️ **HIGH COLLATERAL COSTS** - Posting too much collateral.\n"
        "   Consider: Lower initial_collateral_fraction, withdraw collateral "
        "when queue is empty."
    )
```

**Reference Implementation**:
- Optimization guidance: [`experiments/castro/prompts/context.py:275-346`](../../../experiments/castro/prompts/context.py#L275-L346)

### 2.4 Parameter Trajectories (HIGH)

The old Castro tracks how each parameter evolved across iterations:

```
### initial_liquidity_fraction
| Iteration | Value |
|-----------|-------|
| 1 | 0.250 |
| 2 | 0.300 |
| 3 | 0.280 |
| 4 | 0.275 |

*Overall: increased 10.0% from 0.250 to 0.275*
```

This helps the LLM understand which parameter changes correlate with cost improvements.

**Reference Implementation**:
- Trajectory computation: [`experiments/castro/prompts/context.py:131-141`](../../../experiments/castro/prompts/context.py#L131-L141)
- Trajectory display: [`experiments/castro/prompts/context.py:487-528`](../../../experiments/castro/prompts/context.py#L487-L528)

### 2.5 Policy Diffs (HIGH)

The old Castro shows exactly what changed between iterations:

```python
# From context.py:85-128
def compute_policy_diff(old_policy, new_policy) -> list[str]:
    changes = []
    # Added parameters
    for key in set(new_params.keys()) - set(old_params.keys()):
        changes.append(f"Added parameter '{key}' = {new_params[key]}")
    # Changed parameters
    for key in common_keys:
        if old_params[key] != new_params[key]:
            delta = new_params[key] - old_params[key]
            direction = "↑" if delta > 0 else "↓"
            changes.append(f"Changed '{key}': {old} → {new} ({direction}{abs(delta):.2f})")
```

**Reference Implementation**:
- Policy diff: [`experiments/castro/prompts/context.py:85-128`](../../../experiments/castro/prompts/context.py#L85-L128)

### 2.6 Iteration History with Acceptance Status (HIGH)

The old Castro tracks whether each policy was ACCEPTED, REJECTED, or marked as BEST:

```
| Iter | Status | Mean Cost | Std Dev | Settlement |
|------|--------|-----------|---------|------------|
| 1 | ⭐ BEST | $15,000 | ±$500 | 100.0% |
| 2 | ✅ KEPT | $14,800 | ±$450 | 100.0% |
| 3 | ❌ REJECTED | $16,200 | ±$600 | 100.0% |
```

This teaches the LLM what NOT to do by showing rejected attempts.

**Reference Implementation**:
- Iteration history: [`experiments/castro/prompts/context.py:387-485`](../../../experiments/castro/prompts/context.py#L387-L485)
- IterationRecord dataclass: [`experiments/castro/prompts/context.py:32-48`](../../../experiments/castro/prompts/context.py#L32-L48)

### 2.7 Single-Agent Isolation (MEDIUM)

The old Castro has a separate `SingleAgentContextBuilder` that ensures each agent only sees its own data in multi-agent games:

```python
# From context.py:650-700
@dataclass
class SingleAgentContext:
    """CRITICAL ISOLATION: This context contains ONLY the specified agent's data.
    No other agent's policy, history, or metrics are included."""
    agent_id: str | None = None
    current_policy: dict[str, Any]  # Only THIS agent's policy
    iteration_history: list[SingleAgentIterationRecord]  # Only THIS agent's history
```

**Reference Implementation**:
- SingleAgentContext: [`experiments/castro/prompts/context.py:650-700`](../../../experiments/castro/prompts/context.py#L650-L700)
- SingleAgentContextBuilder: [`experiments/castro/prompts/context.py:702-1130`](../../../experiments/castro/prompts/context.py#L702-L1130)

---

## 3. Implementation Roadmap

### Phase 1: Core Context Infrastructure (Priority: CRITICAL)

#### 3.1.1 Port ExtendedContextBuilder

Create `api/payment_simulator/ai_cash_mgmt/context/extended_context.py`:

```python
@dataclass
class SimulationContext:
    current_iteration: int
    current_policy: dict[str, Any]
    current_metrics: dict[str, Any]
    iteration_history: list[IterationRecord]
    best_seed_output: str | None  # Full tick-by-tick logs
    worst_seed_output: str | None
    cost_breakdown: dict[str, int]  # By type
    cost_rates: dict[str, Any]

class ExtendedContextBuilder:
    def build(self) -> str:
        """Build 50k+ token context prompt."""
        sections = [
            self._build_current_state_summary(),
            self._build_cost_analysis(),
            self._build_optimization_guidance(),
            self._build_simulation_output_section(),
            self._build_iteration_history_section(),
            self._build_parameter_trajectory_section(),
            self._build_final_instructions(),
        ]
        return "\n\n".join(sections)
```

**Files to create**:
- `api/payment_simulator/ai_cash_mgmt/context/__init__.py`
- `api/payment_simulator/ai_cash_mgmt/context/extended_context.py`
- `api/payment_simulator/ai_cash_mgmt/context/single_agent_context.py`

#### 3.1.2 Capture Verbose Simulation Output

Modify `SimulationRunner` to capture verbose output:

```python
class SimulationResult:
    total_cost: int
    per_agent_costs: dict[str, int]
    settlement_rate: float
    verbose_output: str  # NEW: Full tick-by-tick log
    cost_breakdown: dict[str, int]  # NEW: By cost type
```

**Files to modify**:
- `experiments/new-castro/castro/simulation.py`
- `api/payment_simulator/ai_cash_mgmt/optimization/policy_evaluator.py`

#### 3.1.3 Compute Rich Metrics

Port the metrics computation from old Castro:

```python
def compute_metrics(results: list[SimulationResult]) -> AggregatedMetrics:
    return {
        "total_cost_mean": mean_cost,
        "total_cost_std": std_cost,
        "risk_adjusted_cost": mean_cost + std_cost,
        "settlement_rate_mean": mean_settlement,
        "failure_rate": failures / total,
        "best_seed": best_result.seed,
        "worst_seed": worst_result.seed,
        "best_seed_cost": min_cost,
        "worst_seed_cost": max_cost,
        "best_seed_output": best_result.verbose_output,  # NEW
        "worst_seed_output": worst_result.verbose_output,  # NEW
        "cost_breakdown": aggregate_cost_breakdown(results),  # NEW
    }
```

**Reference**: [`experiments/castro/castro/simulation/metrics.py`](../../../experiments/castro/castro/simulation/metrics.py)

### Phase 2: Policy Optimization Enhancements (Priority: HIGH)

#### 3.2.1 Update PolicyOptimizer to Use Extended Context

```python
class PolicyOptimizer:
    async def optimize(
        self,
        agent_id: str,
        current_policy: dict[str, Any],
        # NEW parameters for rich context
        iteration_history: list[IterationRecord],
        best_seed_output: str | None,
        worst_seed_output: str | None,
        cost_breakdown: dict[str, int],
        cost_rates: dict[str, Any],
    ) -> OptimizationResult:
        # Build extended context
        context = build_single_agent_context(
            current_iteration=len(iteration_history),
            current_policy=current_policy,
            iteration_history=iteration_history,
            best_seed_output=best_seed_output,
            worst_seed_output=worst_seed_output,
            cost_breakdown=cost_breakdown,
            cost_rates=cost_rates,
            agent_id=agent_id,
        )

        # Use extended context as prompt
        prompt = context  # 50k+ tokens of rich context
```

**Files to modify**:
- `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py`

#### 3.2.2 Track Iteration History with Acceptance Status

```python
@dataclass
class IterationRecord:
    iteration: int
    metrics: dict[str, Any]
    policy: dict[str, Any]
    policy_changes: list[str]  # Diff from previous
    was_accepted: bool
    is_best_so_far: bool
    comparison_to_best: str  # Why rejected (if applicable)
```

**Files to modify**:
- `api/payment_simulator/ai_cash_mgmt/persistence/models.py`

#### 3.2.3 Implement Policy Diff Computation

```python
def compute_policy_diff(old_policy: dict, new_policy: dict) -> list[str]:
    """Compute human-readable differences between policies."""
    changes = []

    old_params = old_policy.get("parameters", {})
    new_params = new_policy.get("parameters", {})

    for key in set(new_params) - set(old_params):
        changes.append(f"Added '{key}' = {new_params[key]}")

    for key in set(old_params) - set(new_params):
        changes.append(f"Removed '{key}'")

    for key in set(old_params) & set(new_params):
        if old_params[key] != new_params[key]:
            delta = new_params[key] - old_params[key]
            direction = "↑" if delta > 0 else "↓"
            changes.append(f"'{key}': {old_params[key]} → {new_params[key]} ({direction})")

    return changes
```

**Files to create**:
- `api/payment_simulator/ai_cash_mgmt/context/policy_diff.py`

### Phase 3: LLM Client Improvements (Priority: MEDIUM)

#### 3.3.1 Increase Max Output Tokens

```python
# In llm_client.py
if "gpt-5" in self._config.model:
    params["reasoning_effort"] = "high"
    params["max_completion_tokens"] = 32000  # Increased from 16384
```

#### 3.3.2 Add Extended Thinking Support for Claude

```python
if self._config.provider == LLMProviderType.ANTHROPIC:
    if self._config.thinking_budget:
        # Use extended thinking API
        response = await client.messages.create(
            model=self._config.model,
            max_tokens=self._config.thinking_budget,
            thinking={
                "type": "enabled",
                "budget_tokens": self._config.thinking_budget,
            },
            ...
        )
```

#### 3.3.3 Include Validation Errors in Retry Prompts

```python
def _build_user_prompt(self, prompt, current_policy, context, validation_errors=None):
    if validation_errors:
        prompt += "\n\nPREVIOUS ATTEMPT FAILED:\n"
        for error in validation_errors:
            prompt += f"  - {error}\n"
        prompt += "\nPlease fix these issues."
```

### Phase 4: Runner Integration (Priority: MEDIUM)

#### 3.4.1 Update ExperimentRunner to Collect Rich Data

```python
async def _evaluate_policies(self, iteration: int) -> EvaluationResult:
    results = []
    for seed in self._seeds:
        result = self._sim_runner.run_simulation(
            policy=policy,
            seed=seed,
            verbose=True,  # NEW: Capture verbose output
        )
        results.append(result)

    # Find best and worst
    best_result = min(results, key=lambda r: r.total_cost)
    worst_result = max(results, key=lambda r: r.total_cost)

    return EvaluationResult(
        total_cost=mean([r.total_cost for r in results]),
        per_agent_costs=aggregate_per_agent(results),
        best_seed_output=best_result.verbose_output,  # NEW
        worst_seed_output=worst_result.verbose_output,  # NEW
        cost_breakdown=aggregate_cost_breakdown(results),  # NEW
    )
```

#### 3.4.2 Pass Rich Context to Optimizer

```python
result = await self._optimizer.optimize(
    agent_id=agent_id,
    current_policy=self._policies[agent_id],
    # NEW: Rich context
    iteration_history=self._iteration_records[agent_id],
    best_seed_output=eval_result.best_seed_output,
    worst_seed_output=eval_result.worst_seed_output,
    cost_breakdown=eval_result.cost_breakdown,
    cost_rates=self._cost_rates,
)
```

---

## 4. Code References

### 4.1 Old Castro Implementation Files

| Component | File Path | Key Functions/Classes |
|-----------|-----------|----------------------|
| Extended Context Builder | [`experiments/castro/prompts/context.py`](../../../experiments/castro/prompts/context.py) | `ExtendedContextBuilder`, `SimulationContext` |
| Single-Agent Context | [`experiments/castro/prompts/context.py#L650`](../../../experiments/castro/prompts/context.py#L650) | `SingleAgentContextBuilder`, `SingleAgentContext` |
| Policy Diff | [`experiments/castro/prompts/context.py#L85`](../../../experiments/castro/prompts/context.py#L85) | `compute_policy_diff()` |
| Parameter Trajectories | [`experiments/castro/prompts/context.py#L131`](../../../experiments/castro/prompts/context.py#L131) | `compute_parameter_trajectory()` |
| Metrics Computation | [`experiments/castro/castro/simulation/metrics.py`](../../../experiments/castro/castro/simulation/metrics.py) | `compute_metrics()` |
| LLM Optimizer | [`experiments/castro/castro/experiment/optimizer.py`](../../../experiments/castro/castro/experiment/optimizer.py) | `LLMOptimizer`, `generate_policy()` |
| Robust Policy Agent | [`experiments/castro/generator/robust_policy_agent.py`](../../../experiments/castro/generator/robust_policy_agent.py) | `RobustPolicyAgent` |
| Prompt Templates | [`experiments/castro/prompts/templates.py`](../../../experiments/castro/prompts/templates.py) | Tree-specific context |

### 4.2 New Implementation Files to Modify

| Component | File Path | Changes Needed |
|-----------|-----------|----------------|
| LLM Client | `experiments/new-castro/castro/llm_client.py` | Add extended context support |
| Runner | `experiments/new-castro/castro/runner.py` | Collect rich metrics, pass to optimizer |
| Simulation | `experiments/new-castro/castro/simulation.py` | Capture verbose output |
| Policy Optimizer | `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py` | Accept rich context params |

### 4.3 New Files to Create

```
api/payment_simulator/ai_cash_mgmt/
├── context/
│   ├── __init__.py
│   ├── extended_context.py      # Port from castro/prompts/context.py
│   ├── single_agent_context.py  # Port SingleAgentContextBuilder
│   └── policy_diff.py           # Port compute_policy_diff()
```

---

## 5. API Token Budget

### 5.1 Recommended Token Allocation

For GPT-5.1 with 200k context window:

| Section | Estimated Tokens | Purpose |
|---------|------------------|---------|
| System prompt | ~500 | Policy schema, rules |
| Current state summary | ~1,000 | Metrics, current policy |
| Cost analysis | ~500 | Breakdown by type |
| Optimization guidance | ~500 | Actionable recommendations |
| Best seed output | ~15,000 | Full tick-by-tick logs |
| Worst seed output | ~15,000 | Full tick-by-tick logs |
| Iteration history | ~10,000 | All iterations with diffs |
| Parameter trajectories | ~2,000 | Evolution tables |
| Final instructions | ~500 | Output requirements |
| **Total Input** | **~45,000** | |
| **Output Budget** | **32,000** | For reasoning + policy JSON |

### 5.2 Configuration Changes

```python
# In LLMConfig
@dataclass
class LLMConfig:
    max_input_tokens: int = 100000  # NEW
    max_output_tokens: int = 32000  # Increased from 16384
    thinking_budget: int | None = 10000  # NEW: For Claude extended thinking
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
def test_extended_context_builder_includes_all_sections():
    """Verify context includes all required sections."""
    context = SimulationContext(...)
    builder = ExtendedContextBuilder(context)
    prompt = builder.build()

    assert "CURRENT STATE SUMMARY" in prompt
    assert "COST ANALYSIS" in prompt
    assert "OPTIMIZATION GUIDANCE" in prompt
    assert "SIMULATION OUTPUT" in prompt
    assert "ITERATION HISTORY" in prompt
    assert "PARAMETER TRAJECTORIES" in prompt

def test_policy_diff_detects_parameter_changes():
    """Verify policy diff correctly identifies changes."""
    old = {"parameters": {"threshold": 5.0}}
    new = {"parameters": {"threshold": 3.0}}

    diff = compute_policy_diff(old, new)

    assert any("threshold" in d and "5.0 → 3.0" in d for d in diff)

def test_single_agent_context_isolation():
    """Verify single-agent context contains no cross-agent data."""
    context = build_single_agent_context(agent_id="BANK_A", ...)

    assert "BANK_B" not in context
    assert "Bank B" not in context
```

### 6.2 Integration Tests

```python
async def test_optimizer_uses_extended_context():
    """Verify optimizer passes rich context to LLM."""
    optimizer = PolicyOptimizer(...)

    result = await optimizer.optimize(
        agent_id="BANK_A",
        iteration_history=history,
        best_seed_output="...",
        worst_seed_output="...",
        cost_breakdown={"delay": 5000, "collateral": 3000},
    )

    # Verify LLM received rich context
    assert len(optimizer._last_prompt) > 10000  # Substantial context
```

### 6.3 End-to-End Test

```python
async def test_experiment_achieves_cost_reduction():
    """Verify experiment with rich context achieves cost improvement."""
    exp = create_exp1(model='gpt-5.1')
    result = await run_experiment(exp)

    # With rich context, should see meaningful improvement
    assert result.final_cost < result.seed_cost * 0.9  # At least 10% improvement
```

---

## 7. Success Criteria

The implementation is complete when:

1. **Context Size**: LLM receives 40k+ tokens of structured context per optimization call
2. **Verbose Output**: Best and worst seed tick-by-tick logs are captured and included
3. **Cost Breakdown**: Costs are broken down by type (delay, collateral, overdraft, EOD)
4. **Optimization Guidance**: Context-aware recommendations are generated
5. **Parameter Tracking**: Full parameter trajectories are shown
6. **Policy Diffs**: Changes between iterations are clearly displayed
7. **Acceptance History**: Rejected policies are tracked with reasons
8. **Token Budget**: Max output tokens increased to 32k+
9. **Test Coverage**: All new code has unit tests
10. **Experiment Success**: Exp1, Exp2, Exp3 all achieve measurable cost improvements

---

## 8. Estimated Effort

| Phase | Estimated Time | Dependencies |
|-------|---------------|--------------|
| Phase 1: Core Context | 2-3 days | None |
| Phase 2: Optimization | 1-2 days | Phase 1 |
| Phase 3: LLM Client | 0.5-1 day | None |
| Phase 4: Runner | 1-2 days | Phase 1, 2 |
| Testing | 1-2 days | All phases |
| **Total** | **6-10 days** | |

---

## Appendix A: Example Extended Context Prompt

```markdown
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY OPTIMIZATION CONTEXT - BANK_A - ITERATION 5
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 1. CURRENT STATE SUMMARY

| Metric | Value |
|--------|-------|
| **Mean Total Cost** | $12,500 (↓8.2% from previous) |
| **Cost Std Dev** | ±$1,200 |
| **Settlement Rate** | 100.0% |
| **Best Seed** | #42 ($11,200) |
| **Worst Seed** | #17 ($14,800) |

### Current Policy Parameters (BANK_A)
```json
{
  "initial_liquidity_fraction": 0.28,
  "urgency_threshold": 4.5,
  "liquidity_buffer_factor": 1.2
}
```

## 2. COST ANALYSIS

| Cost Type | Amount | % of Total | Priority |
|-----------|--------|------------|----------|
| delay | $6,200 | 49.6% | 🔴 HIGH |
| collateral | $4,100 | 32.8% | 🟡 MEDIUM |
| overdraft | $1,500 | 12.0% | 🟢 LOW |
| eod_penalty | $700 | 5.6% | 🟢 LOW |

## 3. OPTIMIZATION GUIDANCE

⚠️ **HIGH DELAY COSTS** - Payments are waiting too long in queue.
   Consider: Lower urgency_threshold, reduce liquidity_buffer, release payments earlier.

✅ **IMPROVING TREND** - Costs decreasing consistently. Continue current direction.

## 4. SIMULATION OUTPUT (TICK-BY-TICK)

### Best Performing Seed (#42, Cost: $11,200)

<best_seed_output>
```
[Tick 0] BANK_A: Posted $28,000 collateral (InitialAllocation)
[Tick 0] Balance: $28,000, Queue: 0 payments
[Tick 1] TX-001 ($12,000 A→B, deadline=5): RELEASED immediately
[Tick 1] Balance: $16,000 after settlement
[Tick 2] TX-002 ($8,000 A→B, deadline=8): HELD (urgency=4.5, ticks_to_deadline=6)
[Tick 3] TX-002: RELEASED (ticks_to_deadline=5 <= urgency_threshold=4.5)
...
```
</best_seed_output>

### Worst Performing Seed (#17, Cost: $14,800)

<worst_seed_output>
```
[Tick 0] BANK_A: Posted $28,000 collateral (InitialAllocation)
[Tick 3] TX-005 ($15,000 A→B, deadline=4): HELD (insufficient balance $12,000)
[Tick 3] ⚠️ DELAY COST: $150 (1 tick × $15,000 × 0.01)
[Tick 4] TX-005: Still HELD (balance $12,000 < amount $15,000)
[Tick 4] ⚠️ DELAY COST: $300 cumulative
...
```
</worst_seed_output>

## 5. ITERATION HISTORY

| Iter | Status | Mean Cost | Std Dev | Settlement |
|------|--------|-----------|---------|------------|
| 1 | ✅ KEPT | $15,274 | ±$1,800 | 100.0% |
| 2 | ⭐ BEST | $14,200 | ±$1,500 | 100.0% |
| 3 | ❌ REJECTED | $15,800 | ±$2,100 | 100.0% |
| 4 | ✅ KEPT | $13,600 | ±$1,400 | 100.0% |
| 5 | ⭐ BEST | $12,500 | ±$1,200 | 100.0% |

### ❌ Iteration 3 (REJECTED)
**Why rejected:** Cost increased from $14,200 to $15,800 (+11.3%)
**Changes that failed:**
  - Changed 'urgency_threshold': 4.0 → 6.0 (↑2.0)
  - Changed 'initial_liquidity_fraction': 0.30 → 0.20 (↓0.10)

## 6. PARAMETER TRAJECTORIES

### urgency_threshold
| Iteration | Value |
|-----------|-------|
| 1 | 5.000 |
| 2 | 4.000 |
| 4 | 4.500 |
| 5 | 4.500 |

*Overall: decreased 10.0% from 5.000 to 4.500*

## 7. FINAL INSTRUCTIONS

Generate an improved policy for **BANK_A** that:
1. **Beats the current best** ($12,500) - must have LOWER cost
2. **Maintains 100% settlement rate**
3. **Addresses HIGH DELAY COSTS** - the main cost driver

⚠️ **AVOID**: Iteration 3 increased urgency_threshold to 6.0 which FAILED.
```

---

*Document created: 2024-12-09*
*Last updated: 2024-12-09*
