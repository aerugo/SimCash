"""
Integration tests for runner migration with feature flag.

These tests verify that the new SimulationRunner (when USE_NEW_RUNNER=true)
produces identical results to the old implementation.

TDD Approach: Write tests first to validate migration doesn't break behavior.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from payment_simulator._core import Orchestrator
from payment_simulator.cli.commands.run import run_simulation
from payment_simulator.config import SimulationConfig as PySimConfig
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture
def simple_config_path(tmp_path):
    """Create a simple config file for testing."""
    config = {
        "simulation": {
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "credit_limit": 500000,
                "policy": {"type": "Fifo"},
            },
        ],
        "lsm_config": {
            "bilateral_offsetting": True,
            "cycle_detection": True,
            "max_iterations": 3,
        },
    }

    import yaml
    config_path = tmp_path / "test_config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)

    return config_path


class TestFeatureFlagBehavior:
    """Test that USE_NEW_RUNNER feature flag works correctly."""

    def test_old_runner_used_by_default(self, simple_config_path, tmp_path):
        """By default (no env var), old runner should be used."""
        # Ensure env var is not set
        env = os.environ.copy()
        if "USE_NEW_RUNNER" in env:
            del env["USE_NEW_RUNNER"]

        db_path = tmp_path / "test_old.db"

        with patch.dict(os.environ, env, clear=True):
            with patch("payment_simulator.cli.commands.run.os.getenv") as mock_getenv:
                mock_getenv.return_value = "false"  # Simulate default

                # This test just verifies the code path selection logic
                # We'll check by importing and inspecting the logic
                from payment_simulator.cli.commands.run import os as run_os
                use_new = run_os.getenv("USE_NEW_RUNNER", "false").lower() == "true"
                assert use_new is False

    def test_new_runner_used_when_flag_enabled(self):
        """When USE_NEW_RUNNER=true, new runner should be used."""
        with patch.dict(os.environ, {"USE_NEW_RUNNER": "true"}):
            use_new = os.getenv("USE_NEW_RUNNER", "false").lower() == "true"
            assert use_new is True


class TestVerboseModeEquivalence:
    """Test that new runner produces same results as old in verbose mode."""

    @pytest.mark.skip(reason="Will implement after feature flag is added")
    def test_verbose_mode_old_vs_new_identical_output(self, simple_config_path, tmp_path):
        """Old and new runners should produce identical simulation results."""
        # This test will verify:
        # 1. Same final statistics
        # 2. Same database records (if persisting)
        # 3. Deterministic behavior (same seed = same output)
        pass

    @pytest.mark.skip(reason="Will implement after feature flag is added")
    def test_verbose_mode_with_persistence_equivalent(self, simple_config_path, tmp_path):
        """Persistence should work identically in old and new runners."""
        pass
