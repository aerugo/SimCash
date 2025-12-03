"""
Pytest fixtures for Castro experiment tests.

Provides reusable fixtures for loading configs, creating orchestrators,
and setting up test databases.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Generator

import pytest
import yaml


# Add parent paths to enable imports
CASTRO_ROOT = Path(__file__).parent.parent
SIMCASH_ROOT = CASTRO_ROOT.parent.parent
API_PATH = SIMCASH_ROOT / "api"

sys.path.insert(0, str(API_PATH))

from payment_simulator._core import Orchestrator
from payment_simulator.config import SimulationConfig


# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture
def castro_root() -> Path:
    """Return path to experiments/castro directory."""
    return CASTRO_ROOT


@pytest.fixture
def configs_dir(castro_root: Path) -> Path:
    """Return path to Castro configs directory."""
    return castro_root / "configs"


@pytest.fixture
def policies_dir(castro_root: Path) -> Path:
    """Return path to Castro policies directory."""
    return castro_root / "policies"


# ============================================================================
# Config Loading Fixtures
# ============================================================================


@pytest.fixture
def exp1_config_path(configs_dir: Path) -> Path:
    """Path to Experiment 1 config (2-period)."""
    return configs_dir / "castro_2period_aligned.yaml"


@pytest.fixture
def exp2_config_path(configs_dir: Path) -> Path:
    """Path to Experiment 2 config (12-period stochastic)."""
    return configs_dir / "castro_12period_aligned.yaml"


@pytest.fixture
def exp3_config_path(configs_dir: Path) -> Path:
    """Path to Experiment 3 config (3-period joint)."""
    return configs_dir / "castro_joint_aligned.yaml"


@pytest.fixture
def seed_policy_path(policies_dir: Path) -> Path:
    """Path to seed policy JSON."""
    return policies_dir / "seed_policy.json"


@pytest.fixture
def exp1_config_dict(exp1_config_path: Path) -> dict[str, Any]:
    """Load Experiment 1 config as dict."""
    with open(exp1_config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def exp2_config_dict(exp2_config_path: Path) -> dict[str, Any]:
    """Load Experiment 2 config as dict."""
    with open(exp2_config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def exp3_config_dict(exp3_config_path: Path) -> dict[str, Any]:
    """Load Experiment 3 config as dict."""
    with open(exp3_config_path) as f:
        return yaml.safe_load(f)


@pytest.fixture
def seed_policy_dict(seed_policy_path: Path) -> dict[str, Any]:
    """Load seed policy as dict."""
    with open(seed_policy_path) as f:
        return json.load(f)


# ============================================================================
# Orchestrator Fixtures
# ============================================================================


def _config_to_ffi(config_dict: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw config dict to FFI-compatible format."""
    sim_config = SimulationConfig.from_dict(config_dict)
    return sim_config.to_ffi_dict()


@pytest.fixture
def exp1_orchestrator(exp1_config_dict: dict[str, Any]) -> Orchestrator:
    """Create Orchestrator for Experiment 1."""
    ffi_config = _config_to_ffi(exp1_config_dict)
    return Orchestrator.new(ffi_config)


@pytest.fixture
def exp2_orchestrator(exp2_config_dict: dict[str, Any]) -> Orchestrator:
    """Create Orchestrator for Experiment 2."""
    ffi_config = _config_to_ffi(exp2_config_dict)
    return Orchestrator.new(ffi_config)


@pytest.fixture
def exp3_orchestrator(exp3_config_dict: dict[str, Any]) -> Orchestrator:
    """Create Orchestrator for Experiment 3."""
    ffi_config = _config_to_ffi(exp3_config_dict)
    return Orchestrator.new(ffi_config)


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path() -> Generator[Path, None, None]:
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    # Cleanup
    if path.exists():
        path.unlink()


# ============================================================================
# Castro Cost Rate Constants
# ============================================================================


@pytest.fixture
def castro_daily_rates() -> dict[str, float]:
    """Castro et al. daily cost rates from the paper.

    r_c = 0.1 (10% per day - collateral opportunity cost)
    r_d = 0.2 (20% per day - delay cost)
    r_b = 0.4 (40% per day - borrowing/overdraft cost)
    """
    return {
        "r_c": 0.1,  # Collateral cost per day
        "r_d": 0.2,  # Delay cost per day
        "r_b": 0.4,  # Borrowing/overdraft cost per day
    }


@pytest.fixture
def exp1_expected_rates(castro_daily_rates: dict[str, float]) -> dict[str, float]:
    """Expected per-tick rates for Experiment 1 (2 periods/day)."""
    ticks_per_day = 2
    return {
        "collateral_cost_per_tick_bps": int(castro_daily_rates["r_c"] / ticks_per_day * 10000),
        "delay_cost_per_tick_per_cent": castro_daily_rates["r_d"] / ticks_per_day / 100,
        "overdraft_bps_per_tick": int(castro_daily_rates["r_b"] / ticks_per_day * 10000),
    }


@pytest.fixture
def exp2_expected_rates(castro_daily_rates: dict[str, float]) -> dict[str, float]:
    """Expected per-tick rates for Experiment 2 (12 periods/day)."""
    ticks_per_day = 12
    return {
        # 0.1 / 12 * 10000 = 83.33, rounded to 83
        "collateral_cost_per_tick_bps": 83,
        # 0.2 / 12 / 100 = 0.000167
        "delay_cost_per_tick_per_cent": round(castro_daily_rates["r_d"] / ticks_per_day / 100, 5),
        # 0.4 / 12 * 10000 = 333.33, rounded to 333
        "overdraft_bps_per_tick": 333,
    }


@pytest.fixture
def exp3_expected_rates(castro_daily_rates: dict[str, float]) -> dict[str, float]:
    """Expected per-tick rates for Experiment 3 (3 periods/day)."""
    ticks_per_day = 3
    return {
        # 0.1 / 3 * 10000 = 333.33
        "collateral_cost_per_tick_bps": 333,
        # 0.2 / 3 / 100 = 0.000667
        "delay_cost_per_tick_per_cent": round(castro_daily_rates["r_d"] / ticks_per_day / 100, 5),
        # 0.4 / 3 * 10000 = 1333.33
        "overdraft_bps_per_tick": 1333,
    }
