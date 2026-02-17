"""Shared test fixtures for web backend tests."""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure api/ is on path for payment_simulator imports
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

# Ensure web/backend is on path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import pytest
from app.game import Game, DEFAULT_POLICY
from app.scenario_pack import get_scenario_by_id, generate_scenario


@pytest.fixture
def simple_scenario() -> dict:
    """2-bank, 2-tick scenario — fast to run."""
    return get_scenario_by_id("2bank_2tick")


@pytest.fixture
def stochastic_scenario() -> dict:
    """2-bank, 12-tick stochastic scenario — Castro exp2 style."""
    return get_scenario_by_id("2bank_12tick")


@pytest.fixture
def game(simple_scenario) -> Game:
    """A fresh game with default settings."""
    return Game(game_id="test-001", raw_yaml=simple_scenario, max_days=5)


@pytest.fixture
def game_stochastic(stochastic_scenario) -> Game:
    """A fresh game with stochastic scenario."""
    return Game(game_id="test-002", raw_yaml=stochastic_scenario, max_days=5)
