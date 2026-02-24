"""Tests for starting policy selection in game creation."""
from __future__ import annotations

import json
import copy
import pytest
from app.game import Game, DEFAULT_POLICY
from app.scenario_pack import get_scenario_by_id


SAMPLE_POLICY = {
    "version": "2.0",
    "policy_id": "test_hold_policy",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
    "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Hold"},
}


@pytest.fixture
def scenario():
    return get_scenario_by_id("2bank_12tick")


def test_create_game_with_starting_policy(scenario):
    """Game uses custom policy on day 1."""
    starting_policies = {"BANK_A": json.dumps(SAMPLE_POLICY)}
    game = Game(game_id="sp-1", raw_yaml=scenario, total_days=3,
                starting_policies=starting_policies)

    assert game.policies["BANK_A"]["policy_id"] == "test_hold_policy"
    assert game.policies["BANK_A"]["parameters"]["initial_liquidity_fraction"] == 0.5
    # BANK_B should still be default
    assert game.policies["BANK_B"]["parameters"]["initial_liquidity_fraction"] == 0.5

    # Run a day — should not crash
    day = game.run_day()
    assert day.total_cost >= 0


def test_create_game_default_policy(scenario):
    """Game without starting_policies uses fraction=0.5."""
    game = Game(game_id="sp-2", raw_yaml=scenario, total_days=3)
    for aid in game.agent_ids:
        assert game.policies[aid]["parameters"]["initial_liquidity_fraction"] == 0.5

    day = game.run_day()
    assert day.total_cost >= 0


def test_create_game_partial_starting_policies(scenario):
    """Mix of custom + default."""
    starting_policies = {"BANK_A": json.dumps(SAMPLE_POLICY)}
    game = Game(game_id="sp-3", raw_yaml=scenario, total_days=3,
                starting_policies=starting_policies)

    assert game.policies["BANK_A"]["parameters"]["initial_liquidity_fraction"] == 0.5
    assert game.policies["BANK_B"]["parameters"]["initial_liquidity_fraction"] == 0.5


def test_create_game_invalid_starting_policy_rejected(scenario):
    """Bad JSON returns error."""
    with pytest.raises(ValueError, match="Invalid policy JSON"):
        Game(game_id="sp-4", raw_yaml=scenario, total_days=3,
             starting_policies={"BANK_A": "not valid json {{"})


def test_create_game_unknown_agent_rejected(scenario):
    """Policy for non-existent agent returns error."""
    with pytest.raises(ValueError, match="Unknown agent ID"):
        Game(game_id="sp-5", raw_yaml=scenario, total_days=3,
             starting_policies={"BANK_Z": json.dumps(SAMPLE_POLICY)})


def test_starting_policy_affects_costs(scenario):
    """Day 1 with Hold policy produces different costs than default FIFO."""
    # Game with default (FIFO, fraction=0.5)
    game_default = Game(game_id="sp-6a", raw_yaml=copy.deepcopy(scenario), total_days=1)
    day_default = game_default.run_day()

    # Game with Hold policy at fraction=0.5
    starting_policies = {
        "BANK_A": json.dumps(SAMPLE_POLICY),
        "BANK_B": json.dumps(SAMPLE_POLICY),
    }
    game_custom = Game(game_id="sp-6b", raw_yaml=copy.deepcopy(scenario), total_days=1,
                       starting_policies=starting_policies)
    day_custom = game_custom.run_day()

    # Costs should differ because policies are fundamentally different
    assert day_default.total_cost != day_custom.total_cost, (
        f"Expected different costs: default={day_default.total_cost}, "
        f"custom={day_custom.total_cost}"
    )
