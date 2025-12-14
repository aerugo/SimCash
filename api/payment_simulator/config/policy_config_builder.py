"""Policy configuration builder for unified agent config construction.

This module provides a Protocol and implementation for extracting
agent configuration from policy dictionaries. Used by both:
- optimization.py (main simulation config building)
- sandbox_config.py (bootstrap evaluation config building)

This ensures identical policy interpretation across all evaluation contexts,
preventing subtle bugs where policies behave differently in simulation vs evaluation.

Design follows the StateProvider pattern from cli/execution/state_provider.py.
"""

from __future__ import annotations

from typing import Any, Protocol, TypedDict, runtime_checkable


class AgentLiquidityConfig(TypedDict, total=False):
    """Liquidity-related fields extracted from policy for agent config.

    All fields are optional since not all agents use all features.

    Attributes:
        liquidity_pool: External liquidity pool available for allocation (cents).
        liquidity_allocation_fraction: Fraction of pool to allocate (0.0-1.0).
        max_collateral_capacity: Max collateral capacity override (cents).
        opening_balance: Opening balance for agent (cents).
    """

    liquidity_pool: int | None
    liquidity_allocation_fraction: float | None
    max_collateral_capacity: int | None
    opening_balance: int


@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy.

    This interface ensures identical policy interpretation
    across main simulation and bootstrap evaluation.

    Implementations must handle:
    - Both nested (parameters.X) and flat (X) policy structures
    - Default values for missing parameters
    - Type conversion (str -> float, etc.)

    Example:
        ```python
        builder = StandardPolicyConfigBuilder()
        policy = {"initial_liquidity_fraction": 0.25}
        agent_config = {"liquidity_pool": 10_000_000}

        result = builder.extract_liquidity_config(policy, agent_config)
        # result["liquidity_allocation_fraction"] == 0.25
        ```
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> AgentLiquidityConfig:
        """Extract liquidity configuration from policy.

        Args:
            policy: Policy dict (may have nested or flat structure).
                Nested: {"parameters": {"initial_liquidity_fraction": 0.25}}
                Flat: {"initial_liquidity_fraction": 0.25}
            agent_config: Base agent config from scenario, containing
                liquidity_pool, max_collateral_capacity, opening_balance, etc.

        Returns:
            AgentLiquidityConfig with computed values ready for AgentConfig.
        """
        ...


class StandardPolicyConfigBuilder:
    """Standard implementation of PolicyConfigBuilder.

    Used by both optimization.py and sandbox_config.py to ensure
    identical policy interpretation.

    This implementation:
    - Supports both liquidity_pool mode (Castro-compliant) and
      max_collateral_capacity mode (collateral-based)
    - Handles nested and flat policy structures identically
    - Provides consistent default values (0.5 for fraction)
    - Performs proper type conversion

    Thread-safe: No mutable state, safe for concurrent use.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> AgentLiquidityConfig:
        """Extract liquidity config using canonical logic.

        Handles both liquidity_pool mode (Castro-compliant direct balance)
        and max_collateral_capacity mode (collateral-based credit headroom).

        Args:
            policy: Policy dict, supports both formats:
                - Nested: {"parameters": {"initial_liquidity_fraction": 0.25}}
                - Flat: {"initial_liquidity_fraction": 0.25}
            agent_config: Base agent config containing:
                - liquidity_pool (int, optional)
                - max_collateral_capacity (int, optional)
                - opening_balance (int, optional, defaults to 0)

        Returns:
            AgentLiquidityConfig with all relevant fields populated.
        """
        result: AgentLiquidityConfig = {}

        # Extract liquidity_pool from agent config (Castro-compliant mode)
        liquidity_pool = agent_config.get("liquidity_pool")
        if liquidity_pool is not None:
            result["liquidity_pool"] = int(liquidity_pool)

            # Extract initial_liquidity_fraction from policy
            # CRITICAL: Check both nested (parameters.X) and flat (X) structure
            # LLM may return either format depending on model/prompt
            fraction = self._extract_fraction_from_policy(policy)

            result["liquidity_allocation_fraction"] = fraction

        # Extract max_collateral_capacity from agent config (collateral mode)
        max_collateral = agent_config.get("max_collateral_capacity")
        if max_collateral is not None:
            result["max_collateral_capacity"] = int(max_collateral)

        # Opening balance passthrough
        opening_balance = agent_config.get("opening_balance", 0)
        result["opening_balance"] = int(opening_balance)

        return result

    def _extract_fraction_from_policy(self, policy: dict[str, Any]) -> float:
        """Extract initial_liquidity_fraction from policy.

        Checks both nested and flat structures, returns default if not found.

        Args:
            policy: Policy dict in either format.

        Returns:
            Float fraction between 0.0 and 1.0, defaults to 0.5.
        """
        # Check nested structure first: policy["parameters"]["initial_liquidity_fraction"]
        params = policy.get("parameters", {})
        fraction = params.get("initial_liquidity_fraction")

        # Fallback to flat structure: policy["initial_liquidity_fraction"]
        if fraction is None:
            fraction = policy.get("initial_liquidity_fraction")

        # Default to 0.5 (50%) if not specified
        if fraction is None:
            return 0.5

        return float(fraction)


# Module-level singleton for convenience
# Use this in most cases to avoid creating multiple instances
default_policy_config_builder = StandardPolicyConfigBuilder()
