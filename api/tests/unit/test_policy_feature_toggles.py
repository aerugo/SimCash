"""Tests for PolicyFeatureToggles schema (TDD - tests written first).

These tests validate the scenario configuration feature that allows
restricting which policy DSL features are available.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


class TestPolicyFeatureTogglesSchema:
    """Test PolicyFeatureToggles Pydantic model validation."""

    def test_include_list_valid(self) -> None:
        """Include list with valid categories parses correctly."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(
            include=["PaymentAction", "TransactionField", "AgentField"]
        )

        assert toggles.include == ["PaymentAction", "TransactionField", "AgentField"]
        assert toggles.exclude is None

    def test_exclude_list_valid(self) -> None:
        """Exclude list with valid categories parses correctly."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(
            exclude=["CollateralAction", "CollateralField"]
        )

        assert toggles.exclude == ["CollateralAction", "CollateralField"]
        assert toggles.include is None

    def test_include_and_exclude_mutual_exclusion(self) -> None:
        """Cannot have both include and exclude lists."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        with pytest.raises(ValueError, match="Cannot specify both"):
            PolicyFeatureToggles(
                include=["PaymentAction"],
                exclude=["CollateralAction"],
            )

    def test_empty_toggles_is_valid(self) -> None:
        """No toggles means all features allowed."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles()

        assert toggles.include is None
        assert toggles.exclude is None

    def test_empty_include_list_is_valid(self) -> None:
        """Empty include list is valid (means nothing allowed)."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(include=[])

        assert toggles.include == []
        assert toggles.exclude is None

    def test_empty_exclude_list_is_valid(self) -> None:
        """Empty exclude list is valid (means nothing excluded)."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(exclude=[])

        assert toggles.exclude == []
        assert toggles.include is None

    def test_invalid_category_in_include_rejected(self) -> None:
        """Unknown category names in include list are rejected."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        with pytest.raises(ValueError, match="Unknown category"):
            PolicyFeatureToggles(include=["InvalidCategory"])

    def test_invalid_category_in_exclude_rejected(self) -> None:
        """Unknown category names in exclude list are rejected."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        with pytest.raises(ValueError, match="Unknown category"):
            PolicyFeatureToggles(exclude=["NotARealCategory", "PaymentAction"])

    def test_all_valid_categories_accepted(self) -> None:
        """All documented categories are accepted."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        # These are all the categories from SchemaCategory enum
        all_categories = [
            "ComparisonOperator",
            "LogicalOperator",
            "BinaryArithmetic",
            "NaryArithmetic",
            "UnaryMath",
            "TernaryMath",
            "ValueType",
            "PaymentAction",
            "BankAction",
            "CollateralAction",
            "RtgsAction",
            "TransactionField",
            "AgentField",
            "QueueField",
            "CollateralField",
            "CostField",
            "TimeField",
            "LsmField",
            "ThroughputField",
            "StateRegisterField",
            "SystemField",
            "DerivedField",
            "NodeType",
            "TreeType",
        ]

        # Should not raise
        toggles = PolicyFeatureToggles(include=all_categories)
        assert len(toggles.include or []) == len(all_categories)


class TestSimulationConfigWithFeatureToggles:
    """Test integration of PolicyFeatureToggles in SimulationConfig."""

    def test_config_with_feature_toggles_include(self) -> None:
        """SimulationConfig correctly parses policy_feature_toggles with include."""
        from payment_simulator.config.schemas import SimulationConfig

        config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
            policy_feature_toggles={"include": ["PaymentAction", "TransactionField"]},
        )

        assert config.policy_feature_toggles is not None
        assert config.policy_feature_toggles.include == [
            "PaymentAction",
            "TransactionField",
        ]
        assert config.policy_feature_toggles.exclude is None

    def test_config_with_feature_toggles_exclude(self) -> None:
        """SimulationConfig correctly parses policy_feature_toggles with exclude."""
        from payment_simulator.config.schemas import SimulationConfig

        config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
            policy_feature_toggles={"exclude": ["CollateralAction"]},
        )

        assert config.policy_feature_toggles is not None
        assert config.policy_feature_toggles.exclude == ["CollateralAction"]
        assert config.policy_feature_toggles.include is None

    def test_config_without_feature_toggles(self) -> None:
        """SimulationConfig works without policy_feature_toggles."""
        from payment_simulator.config.schemas import SimulationConfig

        config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
        )

        assert config.policy_feature_toggles is None

    def test_config_rejects_both_include_and_exclude(self) -> None:
        """SimulationConfig rejects config with both include and exclude."""
        from payment_simulator.config.schemas import SimulationConfig

        with pytest.raises(ValueError, match="Cannot specify both"):
            SimulationConfig(
                simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
                agents=[
                    {
                        "id": "BANK_A",
                        "opening_balance": 1_000_000,
                        "policy": {"type": "Fifo"},
                    }
                ],
                policy_feature_toggles={
                    "include": ["PaymentAction"],
                    "exclude": ["CollateralAction"],
                },
            )


class TestFeatureTogglesYamlLoading:
    """Test loading feature toggles from YAML files."""

    def test_load_yaml_with_include_toggles(self) -> None:
        """Load scenario YAML with include feature toggles."""
        from payment_simulator.config import load_config

        config_dict = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
            "policy_feature_toggles": {
                "include": ["PaymentAction", "TransactionField", "TimeField"],
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_dict, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.policy_feature_toggles is not None
            assert config.policy_feature_toggles.include == [
                "PaymentAction",
                "TransactionField",
                "TimeField",
            ]
        finally:
            Path(config_path).unlink()

    def test_load_yaml_with_exclude_toggles(self) -> None:
        """Load scenario YAML with exclude feature toggles."""
        from payment_simulator.config import load_config

        config_dict = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
            "policy_feature_toggles": {
                "exclude": ["CollateralAction", "CollateralField", "StateRegisterField"],
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_dict, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.policy_feature_toggles is not None
            assert config.policy_feature_toggles.exclude == [
                "CollateralAction",
                "CollateralField",
                "StateRegisterField",
            ]
        finally:
            Path(config_path).unlink()

    def test_load_yaml_rejects_invalid_category(self) -> None:
        """Loading YAML with invalid category raises error."""
        from payment_simulator.config import load_config

        config_dict = {
            "simulation": {
                "ticks_per_day": 100,
                "num_days": 1,
                "rng_seed": 42,
            },
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 1_000_000,
                    "policy": {"type": "Fifo"},
                }
            ],
            "policy_feature_toggles": {
                "include": ["PaymentAction", "FakeCategory"],
            },
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_dict, f)
            config_path = f.name

        try:
            with pytest.raises(ValueError, match="Unknown category"):
                load_config(config_path)
        finally:
            Path(config_path).unlink()


class TestFeatureTogglesHelperMethods:
    """Test helper methods on PolicyFeatureToggles."""

    def test_is_category_allowed_with_include(self) -> None:
        """is_category_allowed returns True for included categories."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(include=["PaymentAction", "TransactionField"])

        assert toggles.is_category_allowed("PaymentAction") is True
        assert toggles.is_category_allowed("TransactionField") is True
        assert toggles.is_category_allowed("CollateralAction") is False
        assert toggles.is_category_allowed("AgentField") is False

    def test_is_category_allowed_with_exclude(self) -> None:
        """is_category_allowed returns False for excluded categories."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(exclude=["CollateralAction", "CollateralField"])

        assert toggles.is_category_allowed("PaymentAction") is True
        assert toggles.is_category_allowed("TransactionField") is True
        assert toggles.is_category_allowed("CollateralAction") is False
        assert toggles.is_category_allowed("CollateralField") is False

    def test_is_category_allowed_with_no_toggles(self) -> None:
        """is_category_allowed returns True when no toggles specified."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles()

        assert toggles.is_category_allowed("PaymentAction") is True
        assert toggles.is_category_allowed("CollateralAction") is True
        assert toggles.is_category_allowed("StateRegisterField") is True

    def test_get_allowed_categories_with_include(self) -> None:
        """get_allowed_categories returns include list when specified."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(include=["PaymentAction", "TransactionField"])

        allowed = toggles.get_allowed_categories()
        assert allowed == {"PaymentAction", "TransactionField"}

    def test_get_forbidden_categories_with_exclude(self) -> None:
        """get_forbidden_categories returns exclude list when specified."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(exclude=["CollateralAction", "StateRegisterField"])

        forbidden = toggles.get_forbidden_categories()
        assert forbidden == {"CollateralAction", "StateRegisterField"}

    def test_get_forbidden_categories_with_include(self) -> None:
        """get_forbidden_categories returns complement of include list."""
        from payment_simulator.config.schemas import PolicyFeatureToggles

        toggles = PolicyFeatureToggles(include=["PaymentAction"])

        forbidden = toggles.get_forbidden_categories()
        # Should include all categories except PaymentAction
        assert "PaymentAction" not in forbidden
        assert "CollateralAction" in forbidden
        assert "TransactionField" in forbidden
