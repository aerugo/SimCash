# Phase 6: End-to-End Proof of Correctness

**Status**: Pending
**Depends on**: Phase 5

---

## Objective

Create comprehensive end-to-end tests that prove beyond doubt:
1. Both modes (pairwise and temporal) produce valid optimization trajectories
2. Both modes are deterministic (INV-2)
3. The modes behave differently as expected
4. Mode selection actually affects the optimization behavior

---

## Key Properties to Prove

### Property 1: Determinism (INV-2)
Running the same experiment twice with the same seed MUST produce identical:
- Cost trajectories
- Policy acceptance/rejection decisions
- Final policies

### Property 2: Mode Behavioral Difference
Pairwise and temporal modes MUST produce different behavior:
- Pairwise: Compares old vs new policy on same seed (within iteration)
- Temporal: Compares cost across iterations

With identical LLM outputs, these modes will make different acceptance decisions
because pairwise re-evaluates the old policy while temporal uses stored cost.

### Property 3: Temporal Mode Efficiency
Temporal mode runs fewer simulations:
- Pairwise: 3 simulations per iteration (context + old + new evaluation)
- Temporal: 1 simulation per iteration (just context)

### Property 4: Acceptance Logic Correctness
- Pairwise accepts if: `new_cost < old_cost` (same seed, same iteration)
- Temporal accepts if: `current_cost <= previous_iteration_cost`

---

## TDD Steps

### Step 6.1: Write Failing Tests (RED)

**Test File**: `api/tests/experiments/e2e/test_evaluation_modes_e2e.py`

**Test Cases**:

```python
class TestDeterminismProof:
    """Prove INV-2: Same seed = identical results."""

    async def test_pairwise_mode_determinism(self):
        """Two pairwise runs with same seed produce identical results."""
        result1 = await run_experiment(mode="deterministic-pairwise", seed=42)
        result2 = await run_experiment(mode="deterministic-pairwise", seed=42)

        assert result1.cost_trajectory == result2.cost_trajectory
        assert result1.acceptance_decisions == result2.acceptance_decisions
        assert result1.final_policies == result2.final_policies

    async def test_temporal_mode_determinism(self):
        """Two temporal runs with same seed produce identical results."""
        result1 = await run_experiment(mode="deterministic-temporal", seed=42)
        result2 = await run_experiment(mode="deterministic-temporal", seed=42)

        assert result1.cost_trajectory == result2.cost_trajectory
        assert result1.acceptance_decisions == result2.acceptance_decisions

    async def test_different_seeds_produce_different_results(self):
        """Different seeds should produce different optimization paths."""
        result1 = await run_experiment(mode="deterministic-pairwise", seed=42)
        result2 = await run_experiment(mode="deterministic-pairwise", seed=999)

        # At minimum, iteration seeds should differ
        assert result1.iteration_seeds != result2.iteration_seeds


class TestModeBehavioralDifference:
    """Prove modes behave differently."""

    async def test_modes_can_make_different_decisions(self):
        """Pairwise and temporal CAN make different acceptance decisions.

        This is because:
        - Pairwise: Runs old_policy again, gets fresh cost
        - Temporal: Uses stored cost from previous iteration

        If policy didn't change but simulation has any variance (even deterministic
        variance from different seeds), these will diverge.
        """
        # Use scenario where modes WILL diverge
        pairwise = await run_experiment(mode="deterministic-pairwise", seed=42)
        temporal = await run_experiment(mode="deterministic-temporal", seed=42)

        # With iteration-varying seeds, the re-evaluation of old policy
        # in pairwise mode will produce different baseline than temporal's
        # stored cost from previous iteration
        # At some point, decisions will differ


class TestSimulationEfficiency:
    """Prove temporal mode is more efficient."""

    async def test_temporal_runs_fewer_simulations(self):
        """Temporal mode runs 1 sim per iteration, pairwise runs more."""
        pairwise = await run_experiment(mode="deterministic-pairwise", seed=42)
        temporal = await run_experiment(mode="deterministic-temporal", seed=42)

        # Count total simulations run
        assert temporal.total_simulations < pairwise.total_simulations


class TestAcceptanceLogicProof:
    """Prove acceptance logic matches specification."""

    async def test_pairwise_accepts_when_new_cheaper_than_old(self):
        """Pairwise accepts if new_cost < old_cost on same seed."""
        # Create controlled scenario with known costs
        ...

    async def test_temporal_accepts_when_cheaper_than_previous_iteration(self):
        """Temporal accepts if current_cost <= previous_iteration_cost."""
        # Create controlled scenario with known costs
        ...

    async def test_temporal_rejects_when_more_expensive_than_previous(self):
        """Temporal rejects if current_cost > previous_iteration_cost."""
        ...

    async def test_temporal_first_iteration_always_accepts(self):
        """Temporal's first iteration always accepts (no baseline)."""
        ...
```

### Step 6.2: Create Test Infrastructure

Need helper infrastructure:
- `MockLLMClient` that produces deterministic, controlled policy outputs
- `run_experiment()` helper that configures and runs optimization
- Result capture that records cost trajectory, decisions, simulation count

### Step 6.3: Run Tests and Verify

All tests must pass, proving the implementation is correct.

---

## Test Infrastructure Design

```python
@dataclass
class ExperimentResult:
    """Captured results from running an experiment."""
    cost_trajectory: list[int]  # Cost at each iteration
    acceptance_decisions: list[bool]  # Accept/reject at each iteration
    final_policies: dict[str, dict]  # Final policy per agent
    iteration_seeds: list[int]  # Seed used at each iteration
    total_simulations: int  # Total simulation runs
    mode: str  # Evaluation mode used


class MockLLMClient:
    """Deterministic mock LLM for controlled testing."""

    def __init__(self, policy_sequence: list[dict]) -> None:
        """Initialize with predetermined policy sequence."""
        self._policies = policy_sequence
        self._call_count = 0

    async def generate_policy(self, **kwargs) -> dict:
        """Return next policy in sequence."""
        policy = self._policies[self._call_count % len(self._policies)]
        self._call_count += 1
        return policy


async def run_experiment(
    mode: str,
    seed: int,
    max_iterations: int = 5,
    policy_sequence: list[dict] | None = None,
) -> ExperimentResult:
    """Run optimization and capture results for testing."""
    # Create config with specified mode and seed
    # Use MockLLMClient with controlled policy sequence
    # Run optimization loop
    # Capture and return results
    ...
```

---

## Files to Create/Modify

| File | Purpose |
|------|---------|
| `tests/experiments/e2e/test_evaluation_modes_e2e.py` | E2E proof tests |
| `tests/experiments/fixtures/mock_llm.py` | MockLLMClient |
| `tests/experiments/fixtures/experiment_runner.py` | run_experiment helper |

---

## Completion Criteria

- [ ] Pairwise mode determinism proven (same seed = same results)
- [ ] Temporal mode determinism proven
- [ ] Modes demonstrably behave differently
- [ ] Temporal runs fewer simulations
- [ ] Acceptance logic matches specification
- [ ] All tests pass reliably (no flakiness)
