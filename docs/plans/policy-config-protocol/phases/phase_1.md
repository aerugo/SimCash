# Phase 1: Protocol Definition and Test Cases

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Define the `PolicyConfigBuilder` protocol and write comprehensive test cases **BEFORE** implementation. This follows strict TDD principles - tests are written first, then implementation makes them pass.

---

## Deliverables

1. **Protocol Definition File**: `api/payment_simulator/config/policy_config_builder.py`
   - `LiquidityConfig` TypedDict
   - `CollateralConfig` TypedDict
   - `PolicyConfigBuilder` Protocol
   - `StandardPolicyConfigBuilder` class (stub that raises NotImplementedError)

2. **Test File**: `api/tests/unit/test_policy_config_builder.py`
   - All test cases defined and implemented
   - Tests should FAIL initially (TDD red phase)

---

## Step-by-Step Implementation

### Step 1.1: Create Protocol Definition File (Stub)

Create `api/payment_simulator/config/policy_config_builder.py`:

```python
"""PolicyConfigBuilder protocol for unified policy configuration extraction.

This module defines a Protocol-based abstraction for extracting agent configuration
from policy dictionaries. The goal is to ensure IDENTICAL policy interpretation
across all code paths (main simulation and bootstrap evaluation).

INVARIANT (Policy Evaluation Identity):
For any given (policy, agent_config) pair, the extracted configuration MUST be
byte-for-byte identical regardless of which code path calls the builder.

This is analogous to the Replay Identity invariant (INV-5) but for policy
configuration instead of display output.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class LiquidityConfig(TypedDict, total=False):
    """Liquidity-related configuration extracted from policy.

    All fields are optional (total=False) to support partial extraction.

    Attributes:
        liquidity_pool: Pool size in cents (from agent_config).
        liquidity_allocation_fraction: Fraction of pool to allocate (from policy).
        opening_balance: Opening balance in cents (from agent_config).
    """

    liquidity_pool: int | None
    liquidity_allocation_fraction: float | None
    opening_balance: int


class CollateralConfig(TypedDict, total=False):
    """Collateral-related configuration extracted from policy.

    All fields are optional (total=False) to support partial extraction.

    Attributes:
        max_collateral_capacity: Maximum collateral in cents (from agent_config).
        initial_collateral_fraction: Fraction of capacity to post initially (from policy).
    """

    max_collateral_capacity: int | None
    initial_collateral_fraction: float | None


@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy.

    This interface ensures IDENTICAL policy interpretation
    across main simulation and bootstrap evaluation paths.

    Implementations MUST satisfy the Policy Evaluation Identity invariant:
    For any (policy, agent_config) pair, output MUST be identical regardless
    of which code path calls the builder.

    Example:
        >>> builder = StandardPolicyConfigBuilder()
        >>> policy = {"parameters": {"initial_liquidity_fraction": 0.3}}
        >>> agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}
        >>> liquidity = builder.extract_liquidity_config(policy, agent_config)
        >>> liquidity["liquidity_allocation_fraction"]
        0.3
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity configuration from policy.

        Handles both nested and flat policy structures:
        - Nested: policy["parameters"]["initial_liquidity_fraction"]
        - Flat: policy["initial_liquidity_fraction"]

        Nested takes precedence over flat if both exist.
        Default fraction is 0.5 if not specified but liquidity_pool exists.

        Args:
            policy: Policy dict (may have nested or flat structure)
            agent_config: Base agent config from scenario

        Returns:
            LiquidityConfig with computed values
        """
        ...

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral configuration from policy.

        Args:
            policy: Policy dict
            agent_config: Base agent config from scenario

        Returns:
            CollateralConfig with computed values
        """
        ...


class StandardPolicyConfigBuilder:
    """Standard implementation of PolicyConfigBuilder.

    Used by BOTH optimization.py AND sandbox_config.py to ensure
    IDENTICAL policy interpretation.

    This is the SINGLE SOURCE OF TRUTH for policy→config transformation.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity config using canonical logic.

        See Protocol docstring for behavior specification.
        """
        raise NotImplementedError("Phase 2: Implementation pending")

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral config using canonical logic.

        See Protocol docstring for behavior specification.
        """
        raise NotImplementedError("Phase 2: Implementation pending")
```

### Step 1.2: Create Test File

Create `api/tests/unit/test_policy_config_builder.py`:

```python
"""Tests for PolicyConfigBuilder protocol and StandardPolicyConfigBuilder.

These tests follow strict TDD principles:
1. Tests are written BEFORE implementation
2. Tests should FAIL initially
3. Implementation makes tests pass
4. Tests define the expected behavior, not the implementation
"""

import pytest

from payment_simulator.config.policy_config_builder import (
    CollateralConfig,
    LiquidityConfig,
    PolicyConfigBuilder,
    StandardPolicyConfigBuilder,
)


class TestLiquidityConfigExtraction:
    """Tests for extract_liquidity_config method."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_extracts_fraction_from_nested_parameters(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Nested policy["parameters"]["initial_liquidity_fraction"] is extracted."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.3}}
        agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.3

    def test_extracts_fraction_from_flat_policy(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Flat policy["initial_liquidity_fraction"] is extracted."""
        policy = {"initial_liquidity_fraction": 0.25}
        agent_config = {"liquidity_pool": 5_000_000, "opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.25

    def test_nested_takes_precedence_over_flat(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """If both nested and flat exist, nested wins."""
        policy = {
            "parameters": {"initial_liquidity_fraction": 0.8},
            "initial_liquidity_fraction": 0.2,  # Should be ignored
        }
        agent_config = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.8

    def test_default_fraction_when_not_specified(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Missing fraction defaults to 0.5 when liquidity_pool exists."""
        policy = {}  # No fraction specified
        agent_config = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.5

    def test_extracts_liquidity_pool_from_agent_config(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """liquidity_pool comes from agent_config, not policy."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.4}}
        agent_config = {"liquidity_pool": 20_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 20_000_000

    def test_no_fraction_when_no_liquidity_pool(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """No liquidity_allocation_fraction if no liquidity_pool in agent_config."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config = {"opening_balance": 100_000}  # No liquidity_pool

        result = builder.extract_liquidity_config(policy, agent_config)

        # Should not have liquidity_allocation_fraction
        assert "liquidity_allocation_fraction" not in result

    def test_opening_balance_passthrough(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """opening_balance is extracted from agent_config."""
        policy = {}
        agent_config = {"opening_balance": 500_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 500_000

    def test_opening_balance_defaults_to_zero(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """opening_balance defaults to 0 if not in agent_config."""
        policy = {}
        agent_config = {}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 0


class TestCollateralConfigExtraction:
    """Tests for extract_collateral_config method."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_extracts_max_collateral_capacity(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """max_collateral_capacity extracted from agent_config."""
        policy = {}
        agent_config = {"max_collateral_capacity": 5_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["max_collateral_capacity"] == 5_000_000

    def test_extracts_initial_collateral_fraction_nested(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """initial_collateral_fraction from nested policy structure."""
        policy = {"parameters": {"initial_collateral_fraction": 0.6}}
        agent_config = {"max_collateral_capacity": 3_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["initial_collateral_fraction"] == 0.6

    def test_extracts_initial_collateral_fraction_flat(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """initial_collateral_fraction from flat policy structure."""
        policy = {"initial_collateral_fraction": 0.4}
        agent_config = {"max_collateral_capacity": 2_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert result["initial_collateral_fraction"] == 0.4

    def test_no_collateral_fraction_if_not_specified(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """No initial_collateral_fraction if not in policy."""
        policy = {}
        agent_config = {"max_collateral_capacity": 1_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        # Should not have initial_collateral_fraction
        assert "initial_collateral_fraction" not in result


class TestEdgeCases:
    """Edge case handling tests."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_empty_policy_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Empty policy should return defaults."""
        policy: dict[str, object] = {}
        agent_config = {"opening_balance": 100_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 100_000

    def test_empty_agent_config(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Empty agent_config should handle gracefully."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config: dict[str, object] = {}

        result = builder.extract_liquidity_config(policy, agent_config)

        # No liquidity_pool, so no fraction
        assert "liquidity_allocation_fraction" not in result
        assert result["opening_balance"] == 0

    def test_none_liquidity_pool_handled(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """None value for liquidity_pool treated as absent."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config = {"liquidity_pool": None, "opening_balance": 50_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        # None liquidity_pool should not trigger fraction extraction
        assert "liquidity_allocation_fraction" not in result

    def test_type_coercion_liquidity_pool_string(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String liquidity_pool coerced to int."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config = {"liquidity_pool": "1000000"}  # String, not int

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_pool"] == 1_000_000
        assert isinstance(result["liquidity_pool"], int)

    def test_type_coercion_fraction_string(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """String fraction coerced to float."""
        policy = {"parameters": {"initial_liquidity_fraction": "0.75"}}
        agent_config = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 0.75
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_coercion_fraction_int(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Int fraction coerced to float."""
        policy = {"parameters": {"initial_liquidity_fraction": 1}}  # int, not float
        agent_config = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["liquidity_allocation_fraction"] == 1.0
        assert isinstance(result["liquidity_allocation_fraction"], float)

    def test_type_coercion_opening_balance_float(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """Float opening_balance coerced to int."""
        policy = {}
        agent_config = {"opening_balance": 100000.99}  # float, not int

        result = builder.extract_liquidity_config(policy, agent_config)

        assert result["opening_balance"] == 100000
        assert isinstance(result["opening_balance"], int)


class TestProtocolCompliance:
    """Tests verifying protocol compliance."""

    def test_standard_builder_implements_protocol(self) -> None:
        """StandardPolicyConfigBuilder implements PolicyConfigBuilder protocol."""
        builder = StandardPolicyConfigBuilder()

        assert isinstance(builder, PolicyConfigBuilder)

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol can be used with isinstance at runtime."""
        builder = StandardPolicyConfigBuilder()

        # This should not raise
        result = isinstance(builder, PolicyConfigBuilder)

        assert result is True


class TestTypeAnnotations:
    """Tests verifying TypedDict return types."""

    @pytest.fixture
    def builder(self) -> StandardPolicyConfigBuilder:
        """Create builder instance for tests."""
        return StandardPolicyConfigBuilder()

    def test_liquidity_config_is_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """LiquidityConfig return is a dict."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.5}}
        agent_config = {"liquidity_pool": 1_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)

        assert isinstance(result, dict)

    def test_collateral_config_is_dict(
        self, builder: StandardPolicyConfigBuilder
    ) -> None:
        """CollateralConfig return is a dict."""
        policy = {}
        agent_config = {"max_collateral_capacity": 1_000_000}

        result = builder.extract_collateral_config(policy, agent_config)

        assert isinstance(result, dict)
```

### Step 1.3: Verify Tests Fail

Run tests to confirm they fail (TDD red phase):

```bash
cd /home/user/SimCash/api
.venv/bin/python -m pytest tests/unit/test_policy_config_builder.py -v
```

Expected: All tests should fail with `NotImplementedError`.

---

## Verification Checklist

- [ ] Protocol file created at correct location
- [ ] Test file created at correct location
- [ ] All tests fail with NotImplementedError
- [ ] mypy passes on the new files
- [ ] ruff passes on the new files

---

## Exit Criteria

Phase 1 is complete when:
1. Protocol and TypedDict definitions are in place
2. All test cases are written and documented
3. Tests fail as expected (TDD red phase)
4. Type checking passes
5. Work notes updated

---

## Notes

- TypedDict with `total=False` allows optional fields
- `@runtime_checkable` enables isinstance checks
- Tests define the contract; implementation fulfills it
