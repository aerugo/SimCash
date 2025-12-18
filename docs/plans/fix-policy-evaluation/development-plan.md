# Fix Policy Evaluation for Multi-Agent Convergence

**Status**: Completed
**Created**: 2025-12-18
**Completed**: 2025-12-18
**Branch**: claude/fix-policy-evaluation-JFl5g

## Summary

Fix the deterministic-temporal evaluation mode to properly handle multi-agent convergence. Currently, it accepts the "lowest found cost" without accounting for the fact that this cost may change as counterparty policies evolve. The new approach tracks policy stability across ALL agents and converges when BOTH agents have not changed their `initial_liquidity_fraction` for 5 consecutive iterations.

## Critical Invariants to Respect

- **INV-2**: Determinism is Sacred - Same seed + same config = identical outputs. The new convergence logic must be deterministic.
- **INV-9**: Policy Evaluation Identity - Policy parameter extraction must produce identical results regardless of code path.

## Problem Statement

### The Flaw in Current Implementation

In `deterministic-temporal` mode (`_optimize_agent_temporal()`), the current acceptance logic is:

```python
# Current: Accept if cost decreased vs previous iteration
accepted = current_cost <= previous_cost
if accepted:
    self._previous_iteration_costs[agent_id] = current_cost
```

**The Problem**: In a multi-agent game (e.g., 2 symmetric banks), both agents are optimizing simultaneously. When Agent B changes their policy:
1. The cost landscape for Agent A changes
2. A fraction that was "lowest cost" for Agent A may no longer be optimal
3. The "greedy hill climbing" approach gets stuck at local optima that aren't equilibria

### Example Scenario

```
Iteration 1: A=0.5, B=0.5 → cost_A=$100, cost_B=$100
Iteration 2: A=0.3, B=0.5 → cost_A=$80, cost_B=$120 ✓ A accepts (80<100)
Iteration 3: A=0.3, B=0.4 → cost_A=$95, cost_B=$85 ✓ B accepts (85<120)
                                                     ✗ A now sees higher cost than iter 2!
```

Agent A's "optimal" fraction of 0.3 was only optimal given B's old policy. When B changed, A's cost increased, but A is stuck at 0.3 because it was the "lowest found."

### Desired Behavior

1. **Continue exploring**: Don't stop at "lowest cost" - keep exploring until the LLM indicates it has found the optimal solution
2. **Policy stability convergence**: Converge when BOTH agents have not changed their `initial_liquidity_fraction` for 5 consecutive iterations
3. **Max iterations fallback**: Stop at max_iterations if convergence not reached

This matches the multi-agent game-theoretic notion of "Nash equilibrium" - no agent wants to unilaterally deviate.

## Solution Design

### Convergence Logic Change

```
OLD: Accept if current_cost <= previous_cost
     Converge on cost stability

NEW: Always accept LLM's proposed policy
     Converge when ALL agents' initial_liquidity_fraction unchanged for stability_window iterations
```

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   OptimizationRunner                         │
│                                                              │
│  _policy_stability_tracker: PolicyStabilityTracker           │
│                                                              │
│  for iteration in range(max_iterations):                     │
│    for agent_id in optimized_agents:                         │
│      1. Run simulation with current policies → cost          │
│      2. LLM generates new_policy                             │
│      3. Extract initial_liquidity_fraction                   │
│      4. Track fraction change in stability tracker           │
│      5. Always accept new policy (no cost comparison)        │
│                                                              │
│    if stability_tracker.all_agents_stable(window=5):         │
│      CONVERGED - all agents unchanged for 5 iterations       │
│      break                                                   │
└──────────────────────────────────────────────────────────────┘
```

### PolicyStabilityTracker

New class to track `initial_liquidity_fraction` history per agent:

```python
@dataclass
class PolicyStabilityTracker:
    """Tracks policy parameter stability across agents."""

    # History of initial_liquidity_fraction per agent
    # Key: agent_id, Value: list of (iteration, fraction) tuples
    _fraction_history: dict[str, list[tuple[int, float]]]

    def record_fraction(self, agent_id: str, iteration: int, fraction: float) -> None:
        """Record an agent's initial_liquidity_fraction for an iteration."""
        ...

    def agent_stable_for(self, agent_id: str, window: int) -> bool:
        """Check if agent's fraction has been unchanged for `window` iterations."""
        ...

    def all_agents_stable(self, agents: list[str], window: int) -> bool:
        """Check if ALL agents have been stable for `window` iterations."""
        return all(self.agent_stable_for(a, window) for a in agents)
```

### Key Design Decisions

1. **Always accept LLM's policy**: The LLM is now responsible for deciding when to stop changing. We track what it outputs and converge when it stops changing.

2. **Track `initial_liquidity_fraction` specifically**: This is the key parameter in Castro-style experiments. Other tree parameters are less relevant for convergence detection.

3. **Window-based stability**: Use `stability_window` from `ConvergenceConfig` (default 5) for consistency with existing config.

4. **Floating-point comparison tolerance**: Use small epsilon (e.g., 0.001) when comparing fractions to handle floating-point representation issues.

5. **Preserve cost logging**: Still log costs for analysis, just don't use them for acceptance decisions.

## Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/experiments/runner/optimization.py` | `_optimize_agent_temporal()` accepts/rejects based on cost | Always accept; track fraction stability |
| `api/payment_simulator/experiments/runner/policy_stability.py` | Does not exist | New file: PolicyStabilityTracker class |
| `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py` | Detects cost-based convergence | Add policy stability detection |
| `api/tests/experiments/runner/test_policy_stability.py` | Does not exist | Unit tests for PolicyStabilityTracker |
| `api/tests/experiments/e2e/test_multiagent_convergence.py` | Does not exist | E2E test for multi-agent convergence |

## Phase Overview

| Phase | Description | TDD Focus | Tests |
|-------|-------------|-----------|-------|
| 1 | Create PolicyStabilityTracker | Unit tests for tracking and stability detection | 8 tests |
| 2 | Modify `_optimize_agent_temporal()` | Integration tests for new acceptance logic | 6 tests |
| 3 | Wire convergence detection | E2E tests for multi-agent convergence | 4 tests |
| 4 | Documentation updates | Manual verification | - |

## Phase 1: Create PolicyStabilityTracker

**Goal**: Create a standalone class to track `initial_liquidity_fraction` history and detect stability.

### Deliverables

1. `api/payment_simulator/experiments/runner/policy_stability.py` - PolicyStabilityTracker class
2. `api/tests/experiments/runner/test_policy_stability.py` - Unit tests

### TDD Approach

1. Write failing tests for:
   - `record_fraction()` - stores fraction for agent/iteration
   - `agent_stable_for()` - detects single-agent stability
   - `all_agents_stable()` - detects multi-agent stability
   - Edge cases: first iteration, window larger than history, floating-point tolerance

2. Implement PolicyStabilityTracker

3. Verify tests pass

### Success Criteria

- [ ] `record_fraction()` correctly stores history
- [ ] `agent_stable_for()` returns True when fraction unchanged for window iterations
- [ ] `all_agents_stable()` returns True only when ALL agents are stable
- [ ] Floating-point tolerance handles minor representation differences
- [ ] All 8 unit tests pass

## Phase 2: Modify `_optimize_agent_temporal()`

**Goal**: Change the temporal optimization to always accept LLM's policy and track fraction stability.

### Deliverables

1. Modified `_optimize_agent_temporal()` method
2. Integration of PolicyStabilityTracker into OptimizationRunner
3. Extraction of `initial_liquidity_fraction` from LLM response

### Changes Required

```python
# OLD
async def _optimize_agent_temporal(self, agent_id: str, current_cost: int) -> None:
    should_accept = self._evaluate_temporal_acceptance(agent_id, current_cost)
    if not should_accept:
        # Revert to previous policy
        ...
    # Generate new policy via LLM
    ...

# NEW
async def _optimize_agent_temporal(self, agent_id: str, current_cost: int) -> None:
    # Generate new policy via LLM (always)
    new_policy = await self._generate_policy_via_llm(...)

    # Extract and track initial_liquidity_fraction
    fraction = new_policy.get("parameters", {}).get("initial_liquidity_fraction", 0.5)
    self._stability_tracker.record_fraction(agent_id, self._current_iteration, fraction)

    # Always accept the new policy
    self._policies[agent_id] = new_policy

    # Log for analysis but don't use for acceptance
    self._record_iteration_history(agent_id, new_policy, current_cost, was_accepted=True)
```

### Success Criteria

- [ ] LLM policy always accepted (no cost-based rejection)
- [ ] `initial_liquidity_fraction` extracted and tracked
- [ ] Costs still logged for analysis
- [ ] All existing tests still pass (backward compatibility for non-temporal modes)
- [ ] 6 integration tests pass

## Phase 3: Wire Convergence Detection

**Goal**: Integrate PolicyStabilityTracker into the main optimization loop for convergence detection.

### Deliverables

1. Convergence check after each iteration
2. Logging when convergence detected
3. E2E tests verifying multi-agent convergence

### Changes to Main Loop

```python
# In run_optimization() or equivalent
for iteration in range(max_iterations):
    # Run iteration for all agents
    for agent_id in self._optimized_agents:
        await self._optimize_agent_temporal(agent_id, costs[agent_id])

    # Check multi-agent convergence (after all agents processed)
    if self._config.evaluation.is_deterministic_temporal:
        if self._stability_tracker.all_agents_stable(
            list(self._optimized_agents),
            window=self._config.convergence.stability_window
        ):
            self._convergence_reason = "policy_stability"
            break
```

### Success Criteria

- [ ] Convergence detected when all agents stable for `stability_window` iterations
- [ ] Max iterations still enforced as fallback
- [ ] Convergence reason logged accurately
- [ ] E2E test with 2 agents converges correctly

## Phase 4: Documentation Updates

**Goal**: Update documentation to reflect new convergence behavior.

### Deliverables

1. Update `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
2. Update `docs/reference/experiments/configuration.md` if needed
3. Update `docs/reference/patterns-and-conventions.md` if introducing new invariant

### Documentation Changes

- Document new convergence criteria for temporal mode
- Explain multi-agent stability concept
- Update examples in evaluation methodology

## Testing Strategy

### Unit Tests (`test_policy_stability.py`)

1. `test_record_fraction_single_agent` - Basic recording
2. `test_record_fraction_multiple_agents` - Multiple agents
3. `test_agent_stable_exact_window` - Exact window match
4. `test_agent_stable_less_than_window` - History shorter than window
5. `test_agent_stable_with_change` - Fraction changed within window
6. `test_all_agents_stable_true` - All agents stable
7. `test_all_agents_stable_one_unstable` - One agent not stable
8. `test_floating_point_tolerance` - Minor floating-point differences

### Integration Tests

1. `test_temporal_always_accepts_policy` - No cost-based rejection
2. `test_temporal_tracks_fraction` - Fraction recorded correctly
3. `test_temporal_continues_on_cost_increase` - Doesn't reject on cost increase
4. `test_convergence_on_stability` - Converges when stable
5. `test_convergence_max_iterations` - Fallback to max iterations
6. `test_convergence_requires_all_agents` - Partial stability doesn't converge

### E2E Tests (`test_multiagent_convergence.py`)

1. `test_two_agent_convergence` - Both agents converge to stable fractions
2. `test_convergence_logged_correctly` - Reason appears in logs
3. `test_cost_still_logged` - Costs recorded despite no rejection
4. `test_determinism_preserved` - Same seed = same convergence

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates same fraction repeatedly without cost improvement | Experiment doesn't progress | Trust LLM; it will vary if costs are high |
| Floating-point precision issues in fraction comparison | False instability detection | Use tolerance-based comparison (epsilon=0.001) |
| Breaking existing deterministic-pairwise mode | Regression | Only change temporal mode; pairwise unchanged |
| Longer experiments if LLM keeps changing | Cost/time increase | Max iterations enforced |

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Completed | PolicyStabilityTracker created with 20 unit tests |
| Phase 2 | Completed | _optimize_agent_temporal() modified, 13 new tests |
| Phase 3 | Completed | Convergence wired into main loop, integration tests updated |
| Phase 4 | Completed | Documentation updated |
