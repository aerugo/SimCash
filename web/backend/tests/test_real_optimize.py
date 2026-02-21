"""Tests for _real_optimize to prevent silent type-mismatch failures.

The _maas_generate_policy override previously returned LLMResponse instead of
dict, causing 100% silent validation failure. These tests ensure the contract
between generate_policy and PolicyOptimizer is maintained.
"""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.game import Game, GameDay, _real_optimize


@pytest.fixture
def scenario():
    return {
        "simulation": {"ticks_per_day": 2, "num_days": 1, "rng_seed": 42},
        "agents": [
            {"id": "BANK_A", "opening_balance": 100000},
            {"id": "BANK_B", "opening_balance": 100000},
        ],
        "cost_rates": {
            "liquidity_cost_per_tick_bps": 500,
            "delay_cost_per_tick_per_cent": 0.2,
        },
    }


@pytest.fixture
def game_day():
    return GameDay(
        day_num=1,
        seed=42,
        policies={
            "BANK_A": {
                "version": "2.0",
                "policy_id": "default",
                "parameters": {"initial_liquidity_fraction": 0.5},
                "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
                "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
            }
        },
        costs={"BANK_A": {"delay_cost": 1000, "liquidity_cost": 500, "penalty_cost": 0, "total": 1500}},
        events=[],
        balance_history={},
        total_cost=1500,
        per_agent_costs={"BANK_A": 1500},
    )


VALID_POLICY = {
    "version": "2.0",
    "policy_id": "bank_a_v2",
    "parameters": {"initial_liquidity_fraction": 0.3},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}


@pytest.mark.asyncio
async def test_real_optimize_returns_dict_policy(scenario, game_day):
    """_real_optimize must return a result with new_policy as dict, not LLMResponse."""
    current_policy = game_day.policies["BANK_A"]

    # Mock the LLM to return a valid policy JSON
    mock_generate = AsyncMock(return_value=VALID_POLICY)

    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import OptimizationResult

    mock_result = OptimizationResult(
        agent_id="BANK_A",
        iteration=1,
        old_policy=current_policy,
        new_policy=VALID_POLICY,
        old_cost=1500,
        new_cost=None,
        was_accepted=True,
        validation_errors=[],
        llm_latency_seconds=1.0,
        tokens_used=100,
        llm_model="test",
    )

    mock_optimizer = MagicMock()
    mock_optimizer.optimize = AsyncMock(return_value=mock_result)
    mock_optimizer.get_system_prompt = MagicMock(return_value="system prompt")

    mock_client = MagicMock()
    mock_client.system_prompt = ""
    mock_client.set_system_prompt = MagicMock()

    with patch("payment_simulator.ai_cash_mgmt.optimization.policy_optimizer.PolicyOptimizer", return_value=mock_optimizer), \
         patch("payment_simulator.experiments.runner.llm_client.ExperimentLLMClient", return_value=mock_client):

        result = await _real_optimize(
            "BANK_A", current_policy, game_day, [game_day], scenario
        )

        assert result["accepted"] is True
        assert result["new_policy"] is not None
        assert isinstance(result["new_policy"], dict), \
            f"new_policy must be dict, got {type(result['new_policy'])}"
        assert result["new_fraction"] == 0.3


@pytest.mark.asyncio
async def test_real_optimize_propagates_validation_errors(scenario, game_day):
    """When optimization fails, validation_errors should be in the result."""
    current_policy = game_day.policies["BANK_A"]

    from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import OptimizationResult

    mock_result = OptimizationResult(
        agent_id="BANK_A",
        iteration=1,
        old_policy=current_policy,
        new_policy=None,
        old_cost=1500,
        new_cost=None,
        was_accepted=False,
        validation_errors=["Invalid field reference: 'nonexistent_field'"],
        llm_latency_seconds=1.0,
        tokens_used=100,
        llm_model="test",
    )

    mock_optimizer = MagicMock()
    mock_optimizer.optimize = AsyncMock(return_value=mock_result)
    mock_optimizer.get_system_prompt = MagicMock(return_value="system prompt")

    mock_client = MagicMock()
    mock_client.system_prompt = ""
    mock_client.set_system_prompt = MagicMock()

    with patch("payment_simulator.ai_cash_mgmt.optimization.policy_optimizer.PolicyOptimizer", return_value=mock_optimizer), \
         patch("payment_simulator.experiments.runner.llm_client.ExperimentLLMClient", return_value=mock_client):

        result = await _real_optimize(
            "BANK_A", current_policy, game_day, [game_day], scenario
        )

        assert result["accepted"] is False
        assert result["new_policy"] is None
        assert "validation_errors" in result
        assert len(result["validation_errors"]) > 0


def test_maas_override_returns_dict_not_llminteraction():
    """The _maas_generate_policy type check should catch non-dict returns."""
    from payment_simulator.experiments.runner.llm_client import LLMInteraction

    bad_return = LLMInteraction(
        system_prompt="test",
        user_prompt="test",
        raw_response='{"version": "2.0"}',
        parsed_policy=None,
        parsing_error=None,
        prompt_tokens=0,
        completion_tokens=0,
        latency_seconds=1.0,
    )

    # LLMInteraction is not a dict — the type guard in _maas_generate_policy should catch this
    assert not isinstance(bad_return, dict), \
        "LLMInteraction should NOT be a dict — if it is, the type guard won't catch the bug"
