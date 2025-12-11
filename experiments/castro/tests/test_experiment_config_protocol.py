"""TDD tests for ExperimentConfigProtocol.

These tests define the interface that runner.py requires from experiment configs.
Write these tests FIRST, then implement the protocol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest


class TestExperimentConfigProtocolDefinition:
    """Tests that protocol exists and has required methods."""

    def test_protocol_importable(self) -> None:
        """ExperimentConfigProtocol should be importable."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert ExperimentConfigProtocol is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be @runtime_checkable for isinstance checks."""
        from castro.experiment_config import ExperimentConfigProtocol

        # runtime_checkable protocols have _is_runtime_protocol attr
        assert getattr(ExperimentConfigProtocol, "_is_runtime_protocol", False)


class TestExperimentConfigProtocolProperties:
    """Tests for required protocol properties."""

    def test_protocol_has_name_property(self) -> None:
        """Protocol should require 'name' property."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert "name" in dir(ExperimentConfigProtocol)

    def test_protocol_has_description_property(self) -> None:
        """Protocol should require 'description' property."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert "description" in dir(ExperimentConfigProtocol)

    def test_protocol_has_master_seed_property(self) -> None:
        """Protocol should require 'master_seed' property."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert "master_seed" in dir(ExperimentConfigProtocol)

    def test_protocol_has_scenario_path_property(self) -> None:
        """Protocol should require 'scenario_path' property."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert "scenario_path" in dir(ExperimentConfigProtocol)

    def test_protocol_has_optimized_agents_property(self) -> None:
        """Protocol should require 'optimized_agents' property."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert "optimized_agents" in dir(ExperimentConfigProtocol)


class TestExperimentConfigProtocolMethods:
    """Tests for required protocol methods."""

    def test_protocol_has_get_convergence_criteria(self) -> None:
        """Protocol should require get_convergence_criteria() method."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert hasattr(ExperimentConfigProtocol, "get_convergence_criteria")
        assert callable(
            getattr(ExperimentConfigProtocol, "get_convergence_criteria", None)
        )

    def test_protocol_has_get_bootstrap_config(self) -> None:
        """Protocol should require get_bootstrap_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert hasattr(ExperimentConfigProtocol, "get_bootstrap_config")
        assert callable(
            getattr(ExperimentConfigProtocol, "get_bootstrap_config", None)
        )

    def test_protocol_has_get_model_config(self) -> None:
        """Protocol should require get_model_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert hasattr(ExperimentConfigProtocol, "get_model_config")
        assert callable(getattr(ExperimentConfigProtocol, "get_model_config", None))

    def test_protocol_has_get_output_config(self) -> None:
        """Protocol should require get_output_config() method."""
        from castro.experiment_config import ExperimentConfigProtocol

        assert hasattr(ExperimentConfigProtocol, "get_output_config")
        assert callable(getattr(ExperimentConfigProtocol, "get_output_config", None))


class TestCastroExperimentImplementsProtocol:
    """Tests that existing CastroExperiment implements protocol."""

    def test_castro_experiment_is_protocol_instance(self) -> None:
        """CastroExperiment should implement ExperimentConfigProtocol."""
        from castro.experiment_config import ExperimentConfigProtocol
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
        )
        assert isinstance(exp, ExperimentConfigProtocol)

    def test_castro_experiment_has_all_properties(self) -> None:
        """CastroExperiment should have all required properties."""
        from castro.experiment_config import CastroExperiment

        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            master_seed=42,
            optimized_agents=["BANK_A", "BANK_B"],
        )

        assert exp.name == "test"
        assert exp.description == "Test experiment"
        assert exp.master_seed == 42
        assert isinstance(exp.scenario_path, Path)
        assert exp.optimized_agents == ["BANK_A", "BANK_B"]

    def test_castro_experiment_has_all_methods(self) -> None:
        """CastroExperiment should have all required methods."""
        from castro.experiment_config import CastroExperiment
        from payment_simulator.ai_cash_mgmt import (
            BootstrapConfig,
            ConvergenceCriteria,
            OutputConfig,
        )
        from payment_simulator.llm import LLMConfig

        # Use deterministic=True to avoid bootstrap validation errors
        exp = CastroExperiment(
            name="test",
            description="Test experiment",
            scenario_path=Path("configs/exp1_2period.yaml"),
            deterministic=True,  # Skip bootstrap validation
        )

        criteria = exp.get_convergence_criteria()
        assert isinstance(criteria, ConvergenceCriteria)

        bootstrap = exp.get_bootstrap_config()
        assert isinstance(bootstrap, BootstrapConfig)

        model = exp.get_model_config()
        assert isinstance(model, LLMConfig)

        output = exp.get_output_config()
        assert isinstance(output, OutputConfig)
