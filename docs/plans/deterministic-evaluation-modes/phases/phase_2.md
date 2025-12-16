# Phase 2: Add Evaluation Mode Parsing

**Status**: Pending
**Started**:

---

## Objective

Extend `EvaluationConfig` to accept `deterministic-temporal` and `deterministic-pairwise` as valid evaluation modes, with backward compatibility for plain `deterministic`.

---

## Invariants Enforced in This Phase

- **INV-2**: Determinism is Sacred - Mode parsing doesn't affect determinism, but must be correctly validated

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Create/extend `api/tests/experiments/config/test_evaluation_config.py`:

**Test Cases**:
1. `test_deterministic_pairwise_mode_accepted` - `mode: deterministic-pairwise` is valid
2. `test_deterministic_temporal_mode_accepted` - `mode: deterministic-temporal` is valid
3. `test_plain_deterministic_treated_as_pairwise` - `mode: deterministic` → treated as pairwise
4. `test_invalid_mode_raises_error` - `mode: invalid` raises ValueError
5. `test_mode_helper_properties` - `is_bootstrap`, `is_deterministic_pairwise`, `is_deterministic_temporal`

```python
"""Tests for evaluation mode parsing in ExperimentConfig."""

from __future__ import annotations

import pytest

from payment_simulator.experiments.config.experiment_config import EvaluationConfig


class TestEvaluationModes:
    """Tests for evaluation mode validation and helper properties."""

    def test_bootstrap_mode_accepted(self) -> None:
        """Bootstrap mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="bootstrap", num_samples=20)
        assert config.mode == "bootstrap"
        assert config.is_bootstrap is True
        assert config.is_deterministic_pairwise is False
        assert config.is_deterministic_temporal is False

    def test_deterministic_pairwise_mode_accepted(self) -> None:
        """deterministic-pairwise mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="deterministic-pairwise")
        assert config.mode == "deterministic-pairwise"
        assert config.is_bootstrap is False
        assert config.is_deterministic_pairwise is True
        assert config.is_deterministic_temporal is False

    def test_deterministic_temporal_mode_accepted(self) -> None:
        """deterministic-temporal mode should be accepted."""
        config = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        assert config.mode == "deterministic-temporal"
        assert config.is_bootstrap is False
        assert config.is_deterministic_pairwise is False
        assert config.is_deterministic_temporal is True

    def test_plain_deterministic_treated_as_pairwise(self) -> None:
        """Plain 'deterministic' should be treated as 'deterministic-pairwise' for backward compat."""
        config = EvaluationConfig(ticks=10, mode="deterministic")
        # Mode is normalized to deterministic-pairwise
        assert config.is_deterministic_pairwise is True
        assert config.is_deterministic_temporal is False

    def test_invalid_mode_raises_error(self) -> None:
        """Invalid mode should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid evaluation mode"):
            EvaluationConfig(ticks=10, mode="invalid")

    def test_is_deterministic_property(self) -> None:
        """is_deterministic should be True for both deterministic modes."""
        pairwise = EvaluationConfig(ticks=10, mode="deterministic-pairwise")
        temporal = EvaluationConfig(ticks=10, mode="deterministic-temporal")
        bootstrap = EvaluationConfig(ticks=10, mode="bootstrap")

        assert pairwise.is_deterministic is True
        assert temporal.is_deterministic is True
        assert bootstrap.is_deterministic is False
```

### Step 2.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/experiments/config/experiment_config.py`:

```python
@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation mode configuration.

    Controls how policies are evaluated (bootstrap vs deterministic).

    Attributes:
        ticks: Number of simulation ticks per evaluation.
        mode: Evaluation mode. Valid values:
            - 'bootstrap': N samples with different seeds, paired comparison
            - 'deterministic': Alias for 'deterministic-pairwise' (backward compat)
            - 'deterministic-pairwise': Same iteration, compare old vs new on same seed
            - 'deterministic-temporal': Compare cost across iterations
        num_samples: Number of bootstrap samples (for bootstrap mode).
    """

    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    # Valid modes
    VALID_MODES = frozenset({
        "bootstrap",
        "deterministic",
        "deterministic-pairwise",
        "deterministic-temporal",
    })

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.mode not in self.VALID_MODES:
            msg = f"Invalid evaluation mode: {self.mode}. Valid modes: {sorted(self.VALID_MODES)}"
            raise ValueError(msg)

    @property
    def is_bootstrap(self) -> bool:
        """Check if using bootstrap evaluation mode."""
        return self.mode == "bootstrap"

    @property
    def is_deterministic(self) -> bool:
        """Check if using any deterministic evaluation mode."""
        return self.mode in ("deterministic", "deterministic-pairwise", "deterministic-temporal")

    @property
    def is_deterministic_pairwise(self) -> bool:
        """Check if using deterministic-pairwise mode.

        Note: Plain 'deterministic' is treated as 'deterministic-pairwise'.
        """
        return self.mode in ("deterministic", "deterministic-pairwise")

    @property
    def is_deterministic_temporal(self) -> bool:
        """Check if using deterministic-temporal mode."""
        return self.mode == "deterministic-temporal"
```

### Step 2.3: Refactor

- Add docstrings explaining each mode
- Ensure VALID_MODES is documented
- Run mypy and ruff

---

## Implementation Details

### Mode Semantics

| Mode | Description | Comparison |
|------|-------------|------------|
| `bootstrap` | N samples, paired comparison | delta_sum > 0 |
| `deterministic-pairwise` | Same seed, old vs new in same iteration | new_cost < old_cost |
| `deterministic-temporal` | Compare cost across iterations | cost_N < cost_{N-1} |
| `deterministic` | Alias for `deterministic-pairwise` | (backward compat) |

### Edge Cases

- Empty mode string: Should fail validation
- Case sensitivity: Modes are case-sensitive (lowercase only)

---

## Files

| File | Action |
|------|--------|
| `api/tests/experiments/config/test_evaluation_config.py` | CREATE or MODIFY |
| `api/payment_simulator/experiments/config/experiment_config.py` | MODIFY |

---

## Verification

```bash
# Run tests
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/experiments/config/test_evaluation_config.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/config/experiment_config.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/config/experiment_config.py
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] `deterministic-pairwise` mode accepted
- [ ] `deterministic-temporal` mode accepted
- [ ] Plain `deterministic` works (backward compat)
- [ ] Invalid modes raise ValueError
- [ ] Helper properties work correctly
- [ ] Type check passes
- [ ] Lint passes
