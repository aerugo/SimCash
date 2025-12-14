"""PolicyConfigBuilder protocol for unified policy configuration extraction.

This module defines a Protocol-based abstraction for extracting agent configuration
from policy dictionaries. The goal is to ensure IDENTICAL policy interpretation
across all code paths (main simulation and bootstrap evaluation).

INVARIANT (Policy Evaluation Identity):
For any given (policy, agent_config) pair, the extracted configuration MUST be
byte-for-byte identical regardless of which code path calls the builder.

This is analogous to the Replay Identity invariant (INV-5) but for policy
configuration instead of display output.

Example:
    >>> builder = StandardPolicyConfigBuilder()
    >>> policy = {"parameters": {"initial_liquidity_fraction": 0.3}}
    >>> agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}
    >>> liquidity = builder.extract_liquidity_config(policy, agent_config)
    >>> liquidity["liquidity_allocation_fraction"]
    0.3
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

        Logic:
        1. opening_balance is always extracted (defaults to 0)
        2. If liquidity_pool exists in agent_config:
           - Extract liquidity_pool
           - Extract initial_liquidity_fraction (nested takes precedence over flat)
           - Default fraction to 0.5 if not specified

        Type coercion:
        - liquidity_pool: coerced to int
        - opening_balance: coerced to int
        - liquidity_allocation_fraction: coerced to float
        """
        result: LiquidityConfig = {}

        # 1. Extract opening_balance (always set, defaults to 0)
        opening_balance = agent_config.get("opening_balance", 0)
        result["opening_balance"] = int(opening_balance)

        # 2. Extract liquidity_pool from agent_config
        liquidity_pool = agent_config.get("liquidity_pool")
        if liquidity_pool is not None:
            result["liquidity_pool"] = int(liquidity_pool)

            # 3. Only extract fraction if liquidity_pool exists
            # Check nested parameters first (takes precedence)
            params = policy.get("parameters", {})
            fraction: float | int | str | None = None
            if params:
                fraction = params.get("initial_liquidity_fraction")

            # Fall back to flat structure
            if fraction is None:
                fraction = policy.get("initial_liquidity_fraction")

            # Default to 0.5 if not specified
            if fraction is None:
                fraction = 0.5

            result["liquidity_allocation_fraction"] = float(fraction)

        return result

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral config using canonical logic.

        Logic:
        1. Extract max_collateral_capacity from agent_config (if present)
        2. Extract initial_collateral_fraction from policy (nested takes precedence)
           - NO default value; only set if explicitly specified

        Type coercion:
        - max_collateral_capacity: coerced to int
        - initial_collateral_fraction: coerced to float
        """
        result: CollateralConfig = {}

        # 1. Extract max_collateral_capacity from agent_config
        max_collateral = agent_config.get("max_collateral_capacity")
        if max_collateral is not None:
            result["max_collateral_capacity"] = int(max_collateral)

        # 2. Extract initial_collateral_fraction from policy
        # Check nested parameters first (takes precedence)
        params = policy.get("parameters", {})
        fraction: float | int | str | None = None
        if params:
            fraction = params.get("initial_collateral_fraction")

        # Fall back to flat structure
        if fraction is None:
            fraction = policy.get("initial_collateral_fraction")

        if fraction is not None:
            result["initial_collateral_fraction"] = float(fraction)

        return result
