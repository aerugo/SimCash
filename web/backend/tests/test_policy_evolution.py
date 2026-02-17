"""Tests for policy evolution endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app, game_manager
from app.game import Game, GameDay, DEFAULT_POLICY

import copy


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Bypass auth for tests."""
    return {}


@pytest.fixture(autouse=True)
def disable_auth():
    """Disable Firebase auth for all tests in this module."""
    with patch("app.auth.get_current_user", return_value="test-user"):
        yield


@pytest.fixture
def game_with_days():
    """Create a game with 3 days of data in game_manager."""
    game_id = "test-evolution"

    # Build minimal game manually
    game = MagicMock(spec=Game)
    game.game_id = game_id
    game.agent_ids = ["BANK_A", "BANK_B"]

    # Build policies for each day with different fractions
    day0_policies = {
        "BANK_A": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 1.0}},
        "BANK_B": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 1.0}},
    }
    day1_policies = {
        "BANK_A": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 0.85}},
        "BANK_B": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 0.90}},
    }
    day2_policies = {
        "BANK_A": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 0.72},
                    "payment_tree": {"type": "condition", "node_id": "cond1", "field": "balance",
                                     "operator": ">", "value": 50000,
                                     "true_branch": {"type": "action", "node_id": "release", "action": "Release"},
                                     "false_branch": {"type": "action", "node_id": "hold", "action": "Hold"}}},
        "BANK_B": {**copy.deepcopy(DEFAULT_POLICY), "parameters": {"initial_liquidity_fraction": 0.80}},
    }

    days = [
        MagicMock(spec=GameDay, day_num=0, policies=day0_policies,
                  per_agent_costs={"BANK_A": 12000, "BANK_B": 15000}),
        MagicMock(spec=GameDay, day_num=1, policies=day1_policies,
                  per_agent_costs={"BANK_A": 9000, "BANK_B": 11000}),
        MagicMock(spec=GameDay, day_num=2, policies=day2_policies,
                  per_agent_costs={"BANK_A": 7500, "BANK_B": 9500}),
    ]
    game.days = days

    game.reasoning_history = {
        "BANK_A": [
            {"reasoning": "Initial run", "accepted": True, "old_fraction": 1.0, "new_fraction": 0.85},
            {"reasoning": "Reduced liquidity", "accepted": True, "old_fraction": 0.85, "new_fraction": 0.72},
            {"reasoning": "Added condition", "accepted": False, "old_fraction": 0.72, "new_fraction": 0.65},
        ],
        "BANK_B": [
            {"reasoning": "Initial run B", "accepted": True, "old_fraction": 1.0, "new_fraction": 0.90},
            {"reasoning": "Reduced B", "accepted": True, "old_fraction": 0.90, "new_fraction": 0.80},
            {"reasoning": "Keep B", "accepted": True, "old_fraction": 0.80, "new_fraction": 0.75},
        ],
    }

    game_manager[game_id] = game
    yield game_id
    game_manager.pop(game_id, None)


def test_policy_history_structure(client, game_with_days):
    """Test policy history endpoint returns correct structure."""
    res = client.get(f"/api/games/{game_with_days}/policy-history")
    assert res.status_code == 200
    data = res.json()

    assert data["agent_ids"] == ["BANK_A", "BANK_B"]
    assert len(data["days"]) == 3

    # Check first day
    d0 = data["days"][0]
    assert d0["day"] == 0
    assert d0["costs"]["BANK_A"] == 12000
    assert d0["policies"]["BANK_A"]["parameters"]["initial_liquidity_fraction"] == 1.0
    assert d0["accepted"]["BANK_A"] is True
    assert "Initial run" in d0["reasoning"]["BANK_A"]

    # Check rejected day
    d2 = data["days"][2]
    assert d2["accepted"]["BANK_A"] is False

    # Check parameter trajectories
    traj = data["parameter_trajectories"]
    assert traj["BANK_A"]["initial_liquidity_fraction"] == [1.0, 0.85, 0.72]
    assert traj["BANK_B"]["initial_liquidity_fraction"] == [1.0, 0.90, 0.80]


def test_policy_history_not_found(client):
    """Test 404 for non-existent game."""
    with patch("app.auth.get_current_user", return_value="test-user"):
        res = client.get("/api/games/nonexistent/policy-history")
        assert res.status_code == 404


def test_policy_diff_with_changes(client, game_with_days):
    """Test diff endpoint with known policy changes."""
    res = client.get(
        f"/api/games/{game_with_days}/policy-diff",
        params={"day1": 0, "day2": 2, "agent": "BANK_A"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["agent"] == "BANK_A"
    assert data["day1"] == 0
    assert data["day2"] == 2

    # Parameter changes
    param_changes = data["parameter_changes"]
    assert len(param_changes) >= 1
    frac_change = next(p for p in param_changes if p["param"] == "initial_liquidity_fraction")
    assert frac_change["old"] == 1.0
    assert frac_change["new"] == 0.72

    # Tree changes — day 2 has a condition node added
    tree = data["tree_changes"]["payment_tree"]
    assert len(tree["added_nodes"]) > 0 or len(tree["modified_nodes"]) > 0

    # Summary should be non-empty
    assert len(data["summary"]) > 0


def test_policy_diff_identical(client, game_with_days):
    """Test diff with identical policies returns empty changes."""
    res = client.get(
        f"/api/games/{game_with_days}/policy-diff",
        params={"day1": 0, "day2": 0, "agent": "BANK_A"},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["parameter_changes"] == []
    assert data["tree_changes"]["payment_tree"]["added_nodes"] == []
    assert data["tree_changes"]["payment_tree"]["removed_nodes"] == []
    assert data["tree_changes"]["payment_tree"]["modified_nodes"] == []
    assert data["summary"] == "No changes."


def test_policy_diff_bad_day(client, game_with_days):
    """Test diff with out-of-range day returns 400."""
    res = client.get(
        f"/api/games/{game_with_days}/policy-diff",
        params={"day1": 0, "day2": 99, "agent": "BANK_A"},
    )
    assert res.status_code == 400


def test_policy_diff_bad_agent(client, game_with_days):
    """Test diff with unknown agent returns 400."""
    res = client.get(
        f"/api/games/{game_with_days}/policy-diff",
        params={"day1": 0, "day2": 1, "agent": "BANK_Z"},
    )
    assert res.status_code == 400
