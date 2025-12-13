# Phase 7b: Complete Bootstrap Integration

**Status**: In Progress
**Started**: 2025-12-13
**Parent Plan**: `../development-plan.md`
**Continues**: `phase_7.md`

## Objective

Complete the wiring of bootstrap infrastructure into OptimizationLoop. Phase 7 added the initial simulation infrastructure; this phase completes the evaluation wiring.

## ⚠️ Design Decision: No Fallback to Monte Carlo

**Decision**: Use ONLY real bootstrap for evaluation. Do NOT keep the old parametric Monte Carlo as a fallback.

**Rationale**:
- Reduces code complexity (no multiple branches)
- Ensures consistent behavior (always real bootstrap)
- Makes testing simpler (single code path)

**Implementation Approach**:
1. First, get everything working with bootstrap branch taking priority
2. Verify all tests pass
3. THEN remove the old Monte Carlo fallback code (Phase 7c cleanup)

## What's Already Done (Phase 7)

- [x] `InitialSimulationResult` dataclass
- [x] `BootstrapLLMContext` dataclass
- [x] `_run_initial_simulation()` method
- [x] `_create_bootstrap_samples()` method
- [x] Initial simulation call in `run()` for bootstrap mode

## What Remains (This Phase)

1. Helper methods for agent config extraction
2. Update `_evaluate_policy_pair()` to use `BootstrapPolicyEvaluator`
3. Wire `BootstrapLLMContext` into LLM context building

## TDD Approach

### Step 1: Write Failing Tests (RED)

Add tests to `api/tests/integration/test_real_bootstrap_evaluation.py`:

```python
class TestEvaluatePolicyPairUsesBootstrapSamples:
    """Test that _evaluate_policy_pair uses pre-computed bootstrap samples."""

    def test_evaluate_policy_pair_uses_bootstrap_evaluator(self) -> None:
        """When bootstrap samples exist, use BootstrapPolicyEvaluator."""
        # Setup: Create OptimizationLoop with bootstrap samples
        # Action: Call _evaluate_policy_pair()
        # Assert: BootstrapPolicyEvaluator.compute_paired_deltas was used
        pass

    def test_evaluate_policy_pair_same_samples_for_both_policies(self) -> None:
        """Old and new policies evaluated on identical samples."""
        pass


class TestAgentConfigHelpers:
    """Test helper methods for agent config extraction."""

    def test_get_agent_opening_balance(self) -> None:
        """Extract opening_balance from scenario config."""
        pass

    def test_get_agent_credit_limit(self) -> None:
        """Extract credit_limit (unsecured_cap) from scenario config."""
        pass
```

### Step 2: Implement to Pass Tests (GREEN)

#### 2.1 Add Helper Methods

Location: `api/payment_simulator/experiments/runner/optimization.py`

```python
def _get_agent_opening_balance(self, agent_id: str) -> int:
    """Get opening balance for an agent from scenario config.

    Args:
        agent_id: Agent ID to look up.

    Returns:
        Opening balance in integer cents (INV-1).
    """
    scenario = self._load_scenario_config()
    for agent in scenario.get("agents", []):
        if agent.get("id") == agent_id:
            return int(agent.get("opening_balance", 0))
    return 0

def _get_agent_credit_limit(self, agent_id: str) -> int:
    """Get credit limit for an agent from scenario config.

    Args:
        agent_id: Agent ID to look up.

    Returns:
        Credit limit in integer cents (INV-1).
    """
    scenario = self._load_scenario_config()
    for agent in scenario.get("agents", []):
        if agent.get("id") == agent_id:
            return int(agent.get("unsecured_cap", 0))
    return 0
```

#### 2.2 Update `_evaluate_policy_pair()`

Add bootstrap branch at the start of the method (after deterministic mode check):

```python
def _evaluate_policy_pair(
    self,
    agent_id: str,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
) -> tuple[list[int], int]:
    """Evaluate old vs new policy with paired bootstrap samples."""

    # ... existing deterministic mode handling ...

    # NEW: Real bootstrap mode - use pre-computed samples
    if self._bootstrap_samples and agent_id in self._bootstrap_samples:
        samples = self._bootstrap_samples[agent_id]
        if samples:
            evaluator = BootstrapPolicyEvaluator(
                opening_balance=self._get_agent_opening_balance(agent_id),
                credit_limit=self._get_agent_credit_limit(agent_id),
                cost_rates=self._cost_rates,
            )
            paired_deltas = evaluator.compute_paired_deltas(
                samples=samples,
                policy_a=old_policy,
                policy_b=new_policy,
            )
            deltas = [d.delta for d in paired_deltas]
            return deltas, sum(deltas)

    # Fall back to existing Monte Carlo behavior
    # ... existing code ...
```

#### 2.3 Wire BootstrapLLMContext

Update `_build_agent_contexts()` to include initial simulation output:

```python
def _build_agent_contexts(
    self, enriched_results: list[EnrichedEvaluationResult]
) -> dict[str, AgentSimulationContext]:
    """Build per-agent contexts for LLM optimization."""

    # ... existing code ...

    # If we have initial simulation result, include it
    if self._initial_sim_result is not None:
        for agent_id in agent_contexts:
            # Enhance context with initial simulation info
            # This provides Stream 1 for LLM
            pass

    return agent_contexts
```

### Step 3: Refactor (REFACTOR)

- Run mypy to verify types
- Run ruff to verify code style
- Ensure all tests pass

## Implementation Order

1. **Write tests first** (test_real_bootstrap_evaluation.py)
2. **Add helper methods** (_get_agent_opening_balance, _get_agent_credit_limit)
3. **Update _evaluate_policy_pair()** with bootstrap branch
4. **Verify with tests**
5. **Type check and lint**

## Acceptance Criteria

- [x] `_evaluate_policy_pair()` uses `BootstrapPolicyEvaluator` when samples available
- [x] Helper methods correctly extract agent config
- [x] Same bootstrap samples used for old and new policy comparison
- [x] All costs are integers (INV-1)
- [ ] Wire initial simulation output into LLM context (Stream 1)
- [ ] Tests pass
- [ ] mypy passes
- [ ] ruff passes
- [ ] Phase 7c: Remove Monte Carlo fallback (deferred cleanup)

## Files to Modify

1. `api/tests/integration/test_real_bootstrap_evaluation.py` - Add tests
2. `api/payment_simulator/experiments/runner/optimization.py` - Add helpers and bootstrap branch

---

*Created: 2025-12-13*
