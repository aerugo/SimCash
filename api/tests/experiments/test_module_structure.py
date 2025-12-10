"""Tests for experiments module structure.

These tests verify that the experiments module has the expected
submodule structure.
"""

from __future__ import annotations


class TestExperimentsModuleStructure:
    """Tests that experiments module has expected structure."""

    def test_experiments_module_can_be_imported(self) -> None:
        """Experiments module can be imported."""
        import payment_simulator.experiments

        assert payment_simulator.experiments is not None

    def test_experiments_has_config_submodule(self) -> None:
        """Experiments has config submodule."""
        import payment_simulator.experiments.config

        assert payment_simulator.experiments.config is not None

    def test_experiments_has_runner_submodule(self) -> None:
        """Experiments has runner submodule."""
        import payment_simulator.experiments.runner

        assert payment_simulator.experiments.runner is not None

    def test_experiments_has_persistence_submodule(self) -> None:
        """Experiments has persistence submodule."""
        import payment_simulator.experiments.persistence

        assert payment_simulator.experiments.persistence is not None
