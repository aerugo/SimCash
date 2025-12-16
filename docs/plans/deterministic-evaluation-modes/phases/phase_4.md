# Phase 4: Integration Tests

**Status**: Pending
**Started**:

---

## Objective

Verify end-to-end behavior of both evaluation modes with real experiment configurations. Ensure both modes are deterministic and produce valid optimization trajectories.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism is Sacred - Same seed must produce identical results
- **INV-9**: Policy Evaluation Identity - Consistent behavior across code paths

---

## TDD Steps

### Step 4.1: Write Failing Tests (RED)

Create `api/tests/experiments/integration/test_evaluation_modes_integration.py`:

**Test Cases**:
1. `test_pairwise_mode_end_to_end` - Full optimization run with pairwise mode
2. `test_temporal_mode_end_to_end` - Full optimization run with temporal mode
3. `test_pairwise_mode_determinism` - Same seed = same results (pairwise)
4. `test_temporal_mode_determinism` - Same seed = same results (temporal)

```python
"""Integration tests for deterministic evaluation modes.

Tests end-to-end behavior with real experiment configurations.
"""

from __future__ import annotations

import pytest
from pathlib import Path
import tempfile
import yaml

from payment_simulator.experiments.runner.experiment_runner import GenericExperimentRunner
from payment_simulator.experiments.config.experiment_config import ExperimentConfig


class TestEvaluationModesIntegration:
    """End-to-end integration tests for evaluation modes."""

    @pytest.fixture
    def minimal_scenario(self, tmp_path: Path) -> Path:
        """Create minimal scenario YAML for testing."""
        scenario = {
            "simulation": {
                "ticks_per_day": 2,
                "num_days": 1,
                "rng_seed": 42,
            },
            "cost_rates": {
                "delay_cost_per_tick_per_cent": 0.1,
                "overdraft_bps_per_tick": 100,
                "eod_penalty_per_transaction": 10000,
            },
            "agents": [
                {"id": "BANK_A", "opening_balance": 10000},
                {"id": "BANK_B", "opening_balance": 10000},
            ],
            "scenario_events": [
                {
                    "type": "CustomTransactionArrival",
                    "from_agent": "BANK_A",
                    "to_agent": "BANK_B",
                    "amount": 5000,
                    "priority": 5,
                    "deadline": 2,
                    "schedule": {"type": "OneTime", "tick": 0},
                },
            ],
        }
        scenario_path = tmp_path / "scenario.yaml"
        scenario_path.write_text(yaml.dump(scenario))
        return scenario_path

    @pytest.fixture
    def pairwise_experiment(self, minimal_scenario: Path, tmp_path: Path) -> Path:
        """Create experiment config with deterministic-pairwise mode."""
        experiment = {
            "name": "test_pairwise",
            "description": "Test pairwise evaluation",
            "scenario": str(minimal_scenario),
            "evaluation": {
                "mode": "deterministic-pairwise",
                "ticks": 2,
            },
            "convergence": {
                "max_iterations": 3,
            },
            "llm": {
                "model": "test:mock",  # Use mock LLM for testing
            },
            "optimized_agents": ["BANK_A"],
            "master_seed": 42,
        }
        exp_path = tmp_path / "exp_pairwise.yaml"
        exp_path.write_text(yaml.dump(experiment))
        return exp_path

    @pytest.fixture
    def temporal_experiment(self, minimal_scenario: Path, tmp_path: Path) -> Path:
        """Create experiment config with deterministic-temporal mode."""
        experiment = {
            "name": "test_temporal",
            "description": "Test temporal evaluation",
            "scenario": str(minimal_scenario),
            "evaluation": {
                "mode": "deterministic-temporal",
                "ticks": 2,
            },
            "convergence": {
                "max_iterations": 3,
            },
            "llm": {
                "model": "test:mock",
            },
            "optimized_agents": ["BANK_A"],
            "master_seed": 42,
        }
        exp_path = tmp_path / "exp_temporal.yaml"
        exp_path.write_text(yaml.dump(experiment))
        return exp_path

    @pytest.mark.asyncio
    async def test_pairwise_mode_end_to_end(
        self, pairwise_experiment: Path, tmp_path: Path
    ) -> None:
        """Pairwise mode should complete optimization successfully."""
        config = ExperimentConfig.from_yaml(pairwise_experiment)
        runner = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output",
        )

        # Should complete without error
        result = await runner.run()

        assert result is not None
        assert result.iterations_completed >= 1
        # Verify pairwise comparison was used (check logs or metrics)

    @pytest.mark.asyncio
    async def test_temporal_mode_end_to_end(
        self, temporal_experiment: Path, tmp_path: Path
    ) -> None:
        """Temporal mode should complete optimization successfully."""
        config = ExperimentConfig.from_yaml(temporal_experiment)
        runner = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output",
        )

        # Should complete without error
        result = await runner.run()

        assert result is not None
        assert result.iterations_completed >= 1
        # Verify temporal comparison was used

    @pytest.mark.asyncio
    async def test_pairwise_mode_determinism(
        self, pairwise_experiment: Path, tmp_path: Path
    ) -> None:
        """Pairwise mode must be deterministic - same seed = same results."""
        config = ExperimentConfig.from_yaml(pairwise_experiment)

        # Run 1
        runner1 = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output1",
        )
        result1 = await runner1.run()

        # Run 2 with same seed
        runner2 = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output2",
        )
        result2 = await runner2.run()

        # Results must be identical
        assert result1.iterations_completed == result2.iterations_completed
        assert result1.final_costs == result2.final_costs
        # INV-2: Determinism verified

    @pytest.mark.asyncio
    async def test_temporal_mode_determinism(
        self, temporal_experiment: Path, tmp_path: Path
    ) -> None:
        """Temporal mode must be deterministic - same seed = same results."""
        config = ExperimentConfig.from_yaml(temporal_experiment)

        # Run 1
        runner1 = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output1",
        )
        result1 = await runner1.run()

        # Run 2 with same seed
        runner2 = GenericExperimentRunner(
            config=config,
            output_dir=tmp_path / "output2",
        )
        result2 = await runner2.run()

        # Results must be identical
        assert result1.iterations_completed == result2.iterations_completed
        assert result1.final_costs == result2.final_costs
        # INV-2: Determinism verified

    @pytest.mark.asyncio
    async def test_mode_affects_acceptance_pattern(
        self, pairwise_experiment: Path, temporal_experiment: Path, tmp_path: Path
    ) -> None:
        """Different modes should produce different acceptance patterns.

        Pairwise: Compares old vs new on same seed
        Temporal: Compares across iterations

        With the same LLM output, these could produce different trajectories.
        """
        # This is a behavioral test to verify the modes are truly different
        # The exact assertion depends on mock LLM behavior
        pass
```

### Step 4.2: Implement to Pass Tests (GREEN)

Integration tests primarily validate existing implementation. May need:

1. Mock LLM provider for testing
2. Result object with `iterations_completed` and `final_costs`
3. Proper error handling for edge cases

### Step 4.3: Refactor

- Ensure test fixtures are reusable
- Add more comprehensive assertions
- Document expected behavior

---

## Implementation Details

### Mock LLM for Testing

Need a mock LLM that generates deterministic policies for testing:

```python
class MockLLMClient:
    """Deterministic mock LLM for testing."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    async def generate_policy(
        self, context: str, constraints: ScenarioConstraints
    ) -> dict[str, Any]:
        """Generate deterministic mock policy."""
        return {
            "payment_tree": {"action": "Release"},
            "initial_liquidity_fraction": self._rng.uniform(0.0, 1.0),
        }
```

### Result Object

Experiment runner should return a result object with:

```python
@dataclass
class ExperimentResult:
    iterations_completed: int
    final_costs: dict[str, int]  # per-agent final costs
    convergence_reason: str | None
    policy_trajectory: list[dict[str, Any]]  # policies per iteration
```

---

## Files

| File | Action |
|------|--------|
| `api/tests/experiments/integration/test_evaluation_modes_integration.py` | CREATE |
| `api/payment_simulator/experiments/runner/experiment_runner.py` | MODIFY (if needed for result object) |

---

## Verification

```bash
# Run integration tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/integration/test_evaluation_modes_integration.py -v

# Run all experiment tests
.venv/bin/python -m pytest tests/experiments/ -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/
```

---

## Completion Criteria

- [ ] Pairwise mode completes end-to-end
- [ ] Temporal mode completes end-to-end
- [ ] Both modes are deterministic (INV-2)
- [ ] Modes produce different acceptance patterns
- [ ] All existing tests still pass
- [ ] Type check passes
- [ ] Lint passes
