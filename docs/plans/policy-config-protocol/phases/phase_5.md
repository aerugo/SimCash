# Phase 5: Policy Evaluation Identity Tests

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Create comprehensive tests that **enforce** the Policy Evaluation Identity invariant:

**For any policy P and scenario S:**
```
extraction(optimization_path, P, S) == extraction(sandbox_path, P, S)
```

This ensures that transactions are evaluated identically regardless of which code path processes them.

---

## Test Categories

### Category 1: Direct Builder Identity Tests

Test that both code paths use the same `StandardPolicyConfigBuilder` and produce identical results.

```python
class TestPolicyEvaluationIdentity:
    """
    CRITICAL: These tests enforce the Policy Evaluation Identity invariant.

    Any failure indicates a potential divergence between:
    - Deterministic evaluation (optimization.py)
    - Bootstrap evaluation (sandbox_config.py)
    """

    def test_same_builder_instance_type():
        """Both paths use StandardPolicyConfigBuilder."""

    def test_identical_fraction_extraction_nested():
        """Nested policy structure extracts identically."""

    def test_identical_fraction_extraction_flat():
        """Flat policy structure extracts identically."""

    def test_default_fraction_identical():
        """Default 0.5 applied identically in both paths."""
```

### Category 2: Integration Tests

Test that configs built by both paths are equivalent for the same inputs.

```python
class TestConfigBuildingIdentity:
    """Test that built configs are equivalent."""

    def test_liquidity_allocation_fraction_in_built_config():
        """Built configs have correct liquidity_allocation_fraction."""

    def test_sandbox_vs_optimization_config_identical():
        """Sandbox and optimization produce equivalent agent configs."""
```

### Category 3: Property-Based Tests (Optional)

Use Hypothesis to test across a wide range of inputs.

---

## Test Implementation

### File: `api/tests/integration/test_policy_evaluation_identity.py`

This file will contain the gold standard identity tests that MUST pass for any change to be accepted.

---

## Exit Criteria

Phase 5 is complete when:
1. Identity tests are created and documented
2. All tests pass
3. Tests are marked as critical (failure = build break)
4. mypy passes
5. ruff passes
