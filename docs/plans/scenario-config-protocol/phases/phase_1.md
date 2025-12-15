# Phase 1: Core Protocol and Implementation

**Goal**: Create ScenarioConfigBuilder protocol and StandardScenarioConfigBuilder with comprehensive tests.

**TDD Approach**: Tests are written FIRST, then implementation.

## 1. Test Specification (Write First)

### 1.1 Basic Extraction Tests

```python
def test_extract_opening_balance():
    """Opening balance MUST be extracted as integer cents."""
    scenario = {"agents": [{"id": "BANK_A", "opening_balance": 1_000_000}]}
    builder = StandardScenarioConfigBuilder(scenario)
    config = builder.extract_agent_config("BANK_A")
    assert config.opening_balance == 1_000_000

def test_extract_credit_limit_from_unsecured_cap():
    """Credit limit MUST be extracted from unsecured_cap field."""
    scenario = {"agents": [{"id": "BANK_A", "unsecured_cap": 500_000, "opening_balance": 0}]}
    builder = StandardScenarioConfigBuilder(scenario)
    config = builder.extract_agent_config("BANK_A")
    assert config.credit_limit == 500_000
```

### 1.2 Optional Field Tests

```python
def test_extract_optional_max_collateral_capacity():
    """max_collateral_capacity is optional (None if not present)."""
    # With value
    scenario = {"agents": [{"id": "A", "opening_balance": 0, "max_collateral_capacity": 2_000_000}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.max_collateral_capacity == 2_000_000

    # Without value
    scenario2 = {"agents": [{"id": "A", "opening_balance": 0}]}
    config2 = StandardScenarioConfigBuilder(scenario2).extract_agent_config("A")
    assert config2.max_collateral_capacity is None

def test_extract_optional_liquidity_pool():
    """liquidity_pool is optional (None if not present)."""
    # With value
    scenario = {"agents": [{"id": "A", "opening_balance": 0, "liquidity_pool": 5_000_000}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.liquidity_pool == 5_000_000

    # Without value
    scenario2 = {"agents": [{"id": "A", "opening_balance": 0}]}
    config2 = StandardScenarioConfigBuilder(scenario2).extract_agent_config("A")
    assert config2.liquidity_pool is None
```

### 1.3 Type Coercion Tests (INV-1)

```python
def test_type_coercion_string_to_int():
    """String values MUST be coerced to int (INV-1: money as integer cents)."""
    scenario = {"agents": [{"id": "A", "opening_balance": "1000000"}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.opening_balance == 1000000
    assert isinstance(config.opening_balance, int)

def test_type_coercion_float_to_int():
    """Float values MUST be coerced to int (INV-1)."""
    scenario = {"agents": [{"id": "A", "opening_balance": 1000000.0}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.opening_balance == 1000000
    assert isinstance(config.opening_balance, int)
```

### 1.4 Error Handling Tests

```python
def test_agent_not_found_raises_keyerror():
    """Requesting unknown agent MUST raise KeyError."""
    scenario = {"agents": [{"id": "BANK_A", "opening_balance": 0}]}
    builder = StandardScenarioConfigBuilder(scenario)
    with pytest.raises(KeyError):
        builder.extract_agent_config("BANK_B")

def test_empty_agents_list():
    """Empty agents list should work (list_agent_ids returns empty)."""
    scenario = {"agents": []}
    builder = StandardScenarioConfigBuilder(scenario)
    assert builder.list_agent_ids() == []
```

### 1.5 Default Value Tests

```python
def test_default_opening_balance_zero():
    """Missing opening_balance defaults to 0."""
    scenario = {"agents": [{"id": "A"}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.opening_balance == 0

def test_default_credit_limit_zero():
    """Missing unsecured_cap defaults to 0."""
    scenario = {"agents": [{"id": "A", "opening_balance": 100}]}
    config = StandardScenarioConfigBuilder(scenario).extract_agent_config("A")
    assert config.credit_limit == 0
```

### 1.6 list_agent_ids Tests

```python
def test_list_agent_ids():
    """list_agent_ids returns all agent IDs."""
    scenario = {"agents": [
        {"id": "BANK_A", "opening_balance": 0},
        {"id": "BANK_B", "opening_balance": 0},
        {"id": "BANK_C", "opening_balance": 0},
    ]}
    builder = StandardScenarioConfigBuilder(scenario)
    ids = builder.list_agent_ids()
    assert set(ids) == {"BANK_A", "BANK_B", "BANK_C"}
```

### 1.7 Dataclass Tests

```python
def test_agent_scenario_config_is_frozen():
    """AgentScenarioConfig MUST be immutable."""
    config = AgentScenarioConfig(
        agent_id="A",
        opening_balance=100,
        credit_limit=50,
        max_collateral_capacity=None,
        liquidity_pool=None,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.opening_balance = 200
```

### 1.8 Protocol Compliance Tests

```python
def test_standard_builder_is_protocol_compliant():
    """StandardScenarioConfigBuilder MUST satisfy Protocol."""
    from payment_simulator.config.scenario_config_builder import (
        ScenarioConfigBuilder,
        StandardScenarioConfigBuilder,
    )
    scenario = {"agents": []}
    builder = StandardScenarioConfigBuilder(scenario)
    assert isinstance(builder, ScenarioConfigBuilder)
```

## 2. Implementation Structure

### File: `api/payment_simulator/config/scenario_config_builder.py`

```python
"""ScenarioConfigBuilder protocol for unified scenario configuration extraction.

This module defines a Protocol-based abstraction for extracting agent configuration
from scenario YAML dictionaries. The goal is to ensure IDENTICAL scenario interpretation
across all code paths (deterministic simulation and bootstrap evaluation).

INVARIANT (INV-10: Scenario Config Interpretation Identity):
For any given (scenario, agent_id) pair, the extracted configuration MUST be
byte-for-byte identical regardless of which code path calls the builder.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class AgentScenarioConfig:
    """Canonical agent configuration extracted from scenario YAML.

    All monetary values are in integer cents (INV-1).
    This is a value object - immutable and hashable.

    Attributes:
        agent_id: Unique agent identifier.
        opening_balance: Opening balance in integer cents.
        credit_limit: Credit limit (unsecured_cap) in integer cents.
        max_collateral_capacity: Maximum collateral capacity in cents (optional).
        liquidity_pool: External liquidity pool in cents (optional).
    """

    agent_id: str
    opening_balance: int
    credit_limit: int
    max_collateral_capacity: int | None
    liquidity_pool: int | None


@runtime_checkable
class ScenarioConfigBuilder(Protocol):
    """Protocol for extracting agent configuration from scenario.

    Implementations MUST satisfy the Scenario Config Interpretation Identity (INV-10):
    For any (scenario, agent_id) pair, output MUST be identical regardless
    of which code path calls the builder.
    """

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract all configuration for an agent.

        Args:
            agent_id: Agent ID to look up.

        Returns:
            AgentScenarioConfig with all extracted values.

        Raises:
            KeyError: If agent_id not found in scenario.
        """
        ...

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario."""
        ...


class StandardScenarioConfigBuilder:
    """Canonical implementation of ScenarioConfigBuilder.

    Used by ALL code paths that need agent configuration from scenario YAML.
    This is the SINGLE SOURCE OF TRUTH for scenario → agent config extraction.

    Example:
        >>> scenario = {"agents": [{"id": "BANK_A", "opening_balance": 1000000}]}
        >>> builder = StandardScenarioConfigBuilder(scenario)
        >>> config = builder.extract_agent_config("BANK_A")
        >>> config.opening_balance
        1000000
    """

    def __init__(self, scenario_dict: dict[str, Any]) -> None:
        """Initialize with parsed scenario YAML.

        Args:
            scenario_dict: Scenario configuration dictionary.
        """
        self._scenario = scenario_dict
        self._agents_by_id: dict[str, dict[str, Any]] = {
            agent["id"]: agent
            for agent in scenario_dict.get("agents", [])
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
            raise KeyError(f"Agent '{agent_id}' not found in scenario config")

        agent = self._agents_by_id[agent_id]

        return AgentScenarioConfig(
            agent_id=agent_id,
            opening_balance=self._coerce_int(agent.get("opening_balance", 0)),
            credit_limit=self._coerce_int(agent.get("unsecured_cap", 0)),
            max_collateral_capacity=self._coerce_optional_int(
                agent.get("max_collateral_capacity")
            ),
            liquidity_pool=self._coerce_optional_int(
                agent.get("liquidity_pool")
            ),
        )

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario."""
        return list(self._agents_by_id.keys())

    @staticmethod
    def _coerce_int(value: int | float | str) -> int:
        """Coerce value to integer (INV-1).

        Args:
            value: Value to coerce.

        Returns:
            Integer value.
        """
        return int(value)

    @staticmethod
    def _coerce_optional_int(value: int | float | str | None) -> int | None:
        """Coerce optional value to integer (INV-1).

        Args:
            value: Value to coerce (may be None).

        Returns:
            Integer value or None.
        """
        if value is None:
            return None
        return int(value)
```

## 3. Verification Checklist

After implementation:

- [ ] All tests pass: `pytest api/tests/unit/test_scenario_config_builder.py -v`
- [ ] mypy passes: `mypy api/payment_simulator/config/scenario_config_builder.py`
- [ ] ruff passes: `ruff check api/payment_simulator/config/scenario_config_builder.py`
- [ ] Protocol is runtime_checkable
- [ ] AgentScenarioConfig is frozen (immutable)
- [ ] All monetary values are int (INV-1)

## 4. Files to Create/Modify

### Create
- `api/payment_simulator/config/scenario_config_builder.py`
- `api/tests/unit/test_scenario_config_builder.py`

### No modifications needed in Phase 1 (pure TDD)

## 5. Exit Criteria

Phase 1 is complete when:
1. All unit tests pass
2. mypy and ruff pass
3. Protocol is properly defined
4. AgentScenarioConfig is a frozen dataclass
5. All type coercion follows INV-1
