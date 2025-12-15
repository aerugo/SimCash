"""ScenarioConfigBuilder protocol for unified scenario configuration extraction.

This module defines a Protocol-based abstraction for extracting agent configuration
from scenario YAML dictionaries. The goal is to ensure IDENTICAL scenario interpretation
across all code paths (deterministic simulation and bootstrap evaluation).

INVARIANT (INV-10: Scenario Config Interpretation Identity):
For any given (scenario, agent_id) pair, the extracted configuration MUST be
byte-for-byte identical regardless of which code path calls the builder.

This is analogous to:
- INV-5 (Replay Identity) for display output
- INV-9 (Policy Evaluation Identity) for policy parameters

Example:
    >>> scenario = {"agents": [{"id": "BANK_A", "opening_balance": 1000000}]}
    >>> builder = StandardScenarioConfigBuilder(scenario)
    >>> config = builder.extract_agent_config("BANK_A")
    >>> config.opening_balance
    1000000
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AgentScenarioConfig:
    """Canonical agent configuration extracted from scenario YAML.

    All monetary values are in integer cents (INV-1: Money is Always i64).
    This is a value object - immutable and hashable.

    Attributes:
        agent_id: Unique agent identifier.
        opening_balance: Opening balance in integer cents.
        credit_limit: Credit limit (unsecured_cap in YAML) in integer cents.
        max_collateral_capacity: Maximum collateral capacity in cents (optional).
            Required for policies using initial_collateral_fraction.
        liquidity_pool: External liquidity pool in cents (optional).
            Required for policies using initial_liquidity_fraction.

    Example:
        >>> config = AgentScenarioConfig(
        ...     agent_id="BANK_A",
        ...     opening_balance=10_000_000,  # $100,000
        ...     credit_limit=5_000_000,       # $50,000
        ...     max_collateral_capacity=2_000_000,
        ...     liquidity_pool=3_000_000,
        ... )
    """

    agent_id: str
    opening_balance: int
    credit_limit: int
    max_collateral_capacity: int | None
    liquidity_pool: int | None


@runtime_checkable
class ScenarioConfigBuilder(Protocol):
    """Protocol for extracting agent configuration from scenario.

    This interface ensures IDENTICAL scenario interpretation across all code paths
    (deterministic simulation vs bootstrap evaluation).

    Implementations MUST satisfy the Scenario Config Interpretation Identity (INV-10):
    For any (scenario, agent_id) pair, output MUST be identical regardless
    of which code path calls the builder.

    Example:
        >>> builder = StandardScenarioConfigBuilder(scenario_dict)
        >>> config = builder.extract_agent_config("BANK_A")
        >>> # Use config for BootstrapPolicyEvaluator, SandboxConfigBuilder, etc.
    """

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract all configuration for an agent.

        This is the PRIMARY method - extracts ALL agent properties at once.
        Prevents the "forgot to extract X" class of bugs.

        Args:
            agent_id: Agent ID to look up.

        Returns:
            AgentScenarioConfig with all extracted values.

        Raises:
            KeyError: If agent_id not found in scenario.
        """
        ...

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario.

        Returns:
            List of agent ID strings.
        """
        ...


class StandardScenarioConfigBuilder:
    """Canonical implementation of ScenarioConfigBuilder.

    Used by ALL code paths that need agent configuration from scenario YAML.
    This is the SINGLE SOURCE OF TRUTH for scenario → agent config extraction.

    Type coercion rules (INV-1: Money is Always i64):
    - All monetary values are coerced to int
    - String values like "1000000" are converted to int
    - Float values like 1000000.0 are converted to int (truncated)

    Default values:
    - opening_balance: 0 if not specified
    - credit_limit (unsecured_cap): 0 if not specified
    - max_collateral_capacity: None if not specified
    - liquidity_pool: None if not specified

    Example:
        >>> scenario = {"agents": [
        ...     {"id": "BANK_A", "opening_balance": 1000000, "unsecured_cap": 500000}
        ... ]}
        >>> builder = StandardScenarioConfigBuilder(scenario)
        >>> config = builder.extract_agent_config("BANK_A")
        >>> config.opening_balance
        1000000
        >>> config.credit_limit
        500000
    """

    def __init__(self, scenario_dict: dict[str, Any]) -> None:
        """Initialize with parsed scenario YAML.

        Args:
            scenario_dict: Scenario configuration dictionary. Expected to have
                an "agents" key with a list of agent configurations.
        """
        self._scenario = scenario_dict
        self._agents_by_id: dict[str, dict[str, Any]] = {
            agent["id"]: agent for agent in scenario_dict.get("agents", [])
        }

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract all configuration for an agent.

        Uses canonical type coercion (INV-1: money as integer cents).

        Args:
            agent_id: Agent ID to look up.

        Returns:
            AgentScenarioConfig with all extracted values.

        Raises:
            KeyError: If agent_id not found in scenario.
        """
        if agent_id not in self._agents_by_id:
            msg = f"Agent '{agent_id}' not found in scenario config"
            raise KeyError(msg)

        agent = self._agents_by_id[agent_id]

        return AgentScenarioConfig(
            agent_id=agent_id,
            opening_balance=self._coerce_int(agent.get("opening_balance", 0)),
            credit_limit=self._coerce_int(agent.get("unsecured_cap", 0)),
            max_collateral_capacity=self._coerce_optional_int(
                agent.get("max_collateral_capacity")
            ),
            liquidity_pool=self._coerce_optional_int(agent.get("liquidity_pool")),
        )

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario.

        Returns:
            List of agent ID strings.
        """
        return list(self._agents_by_id.keys())

    @staticmethod
    def _coerce_int(value: int | float | str) -> int:
        """Coerce value to integer (INV-1).

        Args:
            value: Value to coerce (int, float, or string representation).

        Returns:
            Integer value.

        Example:
            >>> StandardScenarioConfigBuilder._coerce_int("1000")
            1000
            >>> StandardScenarioConfigBuilder._coerce_int(1000.5)
            1000
        """
        return int(value)

    @staticmethod
    def _coerce_optional_int(value: int | float | str | None) -> int | None:
        """Coerce optional value to integer (INV-1).

        Args:
            value: Value to coerce (may be None).

        Returns:
            Integer value or None if input was None.

        Example:
            >>> StandardScenarioConfigBuilder._coerce_optional_int("1000")
            1000
            >>> StandardScenarioConfigBuilder._coerce_optional_int(None)
            None
        """
        if value is None:
            return None
        return int(value)
