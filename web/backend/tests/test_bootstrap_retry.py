"""Tests for bootstrap rejection retry via multi-turn conversation.

TDD: Tests written first, then implementation.

Covers:
- _build_bootstrap_retry_prompt() formatting
- stream_optimize_with_retries() core logic
- game.py integration with max_policy_proposals
"""
from __future__ import annotations

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch, ANY

import pytest

VALID_POLICY = {
    "version": "2.0",
    "policy_id": "test_policy",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

REVISED_POLICY = {
    "version": "2.0",
    "policy_id": "revised_policy",
    "parameters": {"initial_liquidity_fraction": 0.6},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

CURRENT_POLICY = {
    "version": "2.0",
    "policy_id": "current",
    "parameters": {"initial_liquidity_fraction": 0.8},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

AGENT_ID = "BANK_A"

BOOTSTRAP_STATS = {
    "delta_sum": -500,
    "mean_delta": -50,
    "cv": 0.15,
    "ci_lower": -120,
    "ci_upper": 20,
    "num_samples": 50,
    "old_mean_cost": 10000,
    "new_mean_cost": 10500,
    "rejection_reason": "No improvement: delta_sum=-500 (old=10,000, new=10,500)",
    "profile": "moderate",
    "cv_threshold": 0.5,
    "require_significance": True,
}


def _make_mock_day():
    day = MagicMock()
    day.day_num = 0
    day.per_agent_costs = {"BANK_A": 1000, "BANK_B": 500}
    day.per_agent_cost_std = {"BANK_A": 100, "BANK_B": 50}
    day.costs = {"BANK_A": {"delay_cost": 100, "liquidity_cost": 200, "penalty_cost": 50, "total": 1000}}
    day.events = []
    day.seed = 42
    day.policies = {"BANK_A": CURRENT_POLICY}
    day.agent_histories = {"BANK_A": MagicMock()}
    day.rejected_policies = {}
    return day


def _make_accepted_result(policy=None):
    """A stream_optimize result that passed validation."""
    p = policy or VALID_POLICY
    return {
        "new_policy": p,
        "old_policy": CURRENT_POLICY,
        "reasoning": "LLM proposed fraction change",
        "old_fraction": 0.8,
        "new_fraction": p["parameters"]["initial_liquidity_fraction"],
        "accepted": True,
        "mock": False,
        "raw_response": json.dumps(p),
        "thinking": "",
        "usage": {"input_tokens": 100, "output_tokens": 50},
        "latency_seconds": 1.5,
        "model": "openai:test",
        "structured_prompt": None,
    }


def _make_failed_result():
    """A stream_optimize result where no policy was produced."""
    return {
        "new_policy": None,
        "old_policy": CURRENT_POLICY,
        "reasoning": "Parse failed",
        "old_fraction": 0.8,
        "new_fraction": None,
        "accepted": False,
        "mock": False,
        "raw_response": "garbage",
        "thinking": "",
        "usage": {},
        "latency_seconds": 1.0,
        "model": "openai:test",
        "structured_prompt": None,
    }


def _make_bootstrap_reject_result(policy=None):
    """What BootstrapGate.evaluate() returns on rejection."""
    p = policy or VALID_POLICY
    return {
        "new_policy": None,
        "old_policy": CURRENT_POLICY,
        "reasoning": "LLM proposed fraction change [REJECTED: No improvement]",
        "old_fraction": 0.8,
        "new_fraction": None,
        "accepted": False,
        "rejection_reason": "No improvement: delta_sum=-500",
        "rejected_policy": p,
        "rejected_fraction": p["parameters"]["initial_liquidity_fraction"],
        "bootstrap": BOOTSTRAP_STATS,
        "mock": False,
        "raw_response": json.dumps(p),
        "thinking": "",
        "usage": {},
        "latency_seconds": 1.0,
        "model": "openai:test",
        "structured_prompt": None,
    }


def _make_bootstrap_accept_result(policy=None):
    """What BootstrapGate.evaluate() returns on acceptance."""
    p = policy or VALID_POLICY
    return {
        "new_policy": p,
        "old_policy": CURRENT_POLICY,
        "reasoning": "LLM proposed fraction change",
        "old_fraction": 0.8,
        "new_fraction": p["parameters"]["initial_liquidity_fraction"],
        "accepted": True,
        "bootstrap": {
            **BOOTSTRAP_STATS,
            "delta_sum": 500,
            "mean_delta": 50,
            "rejection_reason": "",
        },
        "mock": False,
        "raw_response": json.dumps(p),
        "thinking": "",
        "usage": {},
        "latency_seconds": 1.0,
        "model": "openai:test",
        "structured_prompt": None,
    }


async def _collect_events(async_gen):
    events = []
    async for event in async_gen:
        events.append(event)
    return events


# ═══════════════════════════════════════════════════════════════════════
# Phase 1: _build_bootstrap_retry_prompt()
# ═══════════════════════════════════════════════════════════════════════


class TestBuildBootstrapRetryPrompt:
    """Tests for the retry prompt builder."""

    def test_contains_rejection_reason(self):
        from app.streaming_optimizer import _build_bootstrap_retry_prompt

        prompt = _build_bootstrap_retry_prompt(BOOTSTRAP_STATS)
        assert "No improvement" in prompt
        assert "REJECTED" in prompt

    def test_contains_cost_statistics(self):
        from app.streaming_optimizer import _build_bootstrap_retry_prompt

        prompt = _build_bootstrap_retry_prompt(BOOTSTRAP_STATS)
        assert "10,000" in prompt or "10000" in prompt  # old_mean_cost
        assert "10,500" in prompt or "10500" in prompt  # new_mean_cost
        assert "50" in prompt  # num_samples

    def test_contains_ci(self):
        from app.streaming_optimizer import _build_bootstrap_retry_prompt

        prompt = _build_bootstrap_retry_prompt(BOOTSTRAP_STATS)
        assert "-120" in prompt  # ci_lower
        assert "20" in prompt    # ci_upper

    def test_mentions_false_option(self):
        from app.streaming_optimizer import _build_bootstrap_retry_prompt

        prompt = _build_bootstrap_retry_prompt(BOOTSTRAP_STATS)
        assert "False" in prompt

    def test_mentions_revised_policy(self):
        from app.streaming_optimizer import _build_bootstrap_retry_prompt

        prompt = _build_bootstrap_retry_prompt(BOOTSTRAP_STATS)
        # Should ask for a new policy JSON
        assert "policy" in prompt.lower()
        assert "JSON" in prompt or "json" in prompt.lower()


# ═══════════════════════════════════════════════════════════════════════
# Phase 2: stream_optimize_with_retries()
# ═══════════════════════════════════════════════════════════════════════


def _mock_stream_optimize_events(result_data, extra_events=None):
    """Create an async generator that mimics stream_optimize() output."""
    async def _gen(*args, **kwargs):
        if extra_events:
            for ev in extra_events:
                yield ev
        yield {"type": "model_info", "model": "openai:test", "provider": "openai"}
        yield {"type": "chunk", "text": "thinking..."}
        yield {"type": "messages", "data": [{"role": "user", "content": "prompt"}, {"role": "assistant", "content": "response"}]}
        yield {"type": "result", "data": result_data}
    return _gen


class TestStreamOptimizeWithRetries:
    """Tests for the retry wrapper around stream_optimize + bootstrap."""

    @pytest.mark.asyncio
    async def test_accept_on_first_try(self):
        """No retry needed — bootstrap accepts first proposal."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_accept_result()

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"]["accepted"] is True
        assert results[0]["data"]["new_policy"] is not None
        # Bootstrap was called once
        assert bootstrap_gate.evaluate.call_count == 1
        # Should have bootstrap_accepted event
        accepted_events = [e for e in events if e["type"] == "bootstrap_accepted"]
        assert len(accepted_events) == 1
        assert accepted_events[0]["proposal"] == 1

    @pytest.mark.asyncio
    async def test_reject_then_accept_on_retry(self):
        """Bootstrap rejects first, agent revises, second accepted."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.side_effect = [
            _make_bootstrap_reject_result(),
            _make_bootstrap_accept_result(REVISED_POLICY),
        ]

        # Mock the retry LLM call
        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(REVISED_POLICY)
        mock_run_result.data = json.dumps(REVISED_POLICY)
        mock_run_result.all_messages.return_value = [{"role": "user"}, {"role": "assistant"}]
        mock_run_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=20)
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=REVISED_POLICY), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value=None):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"]["accepted"] is True

        # Should have retry events
        retry_events = [e for e in events if e["type"] == "bootstrap_retry"]
        assert len(retry_events) == 1
        assert retry_events[0]["proposal"] == 1

        rejected_events = [e for e in events if e["type"] == "bootstrap_rejected"]
        assert len(rejected_events) == 1

        # Bootstrap called twice
        assert bootstrap_gate.evaluate.call_count == 2

    @pytest.mark.asyncio
    async def test_reject_then_agent_declines(self):
        """Agent responds with 'False' — keeps old policy."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result()

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = "False"
        mock_run_result.data = "False"
        mock_run_result.all_messages.return_value = []
        mock_run_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=5)
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        # Agent declined — old policy kept
        assert results[0]["data"]["new_policy"] is None
        assert results[0]["data"]["accepted"] is False
        # Bootstrap only called once (first proposal)
        assert bootstrap_gate.evaluate.call_count == 1

    @pytest.mark.asyncio
    async def test_reject_twice_max_proposals_2(self):
        """Both proposals rejected — gives up after max_proposals=2."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.side_effect = [
            _make_bootstrap_reject_result(),
            _make_bootstrap_reject_result(REVISED_POLICY),
        ]

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(REVISED_POLICY)
        mock_run_result.data = json.dumps(REVISED_POLICY)
        mock_run_result.all_messages.return_value = []
        mock_run_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=20)
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=REVISED_POLICY), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value=None):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"]["accepted"] is False
        assert results[0]["data"]["new_policy"] is None
        assert bootstrap_gate.evaluate.call_count == 2

    @pytest.mark.asyncio
    async def test_max_proposals_1_no_retry(self):
        """max_proposals=1 means no retry — backward compatible."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result()

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=1,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"]["accepted"] is False
        # No retry events
        retry_events = [e for e in events if e["type"] == "bootstrap_retry"]
        assert len(retry_events) == 0
        # Bootstrap called once
        assert bootstrap_gate.evaluate.call_count == 1

    @pytest.mark.asyncio
    async def test_message_history_passed_on_retry(self):
        """Verify pydantic-ai gets conversation history on retry."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        fake_messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "optimize"},
            {"role": "assistant", "content": json.dumps(VALID_POLICY)},
        ]

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.side_effect = [
            _make_bootstrap_reject_result(),
            _make_bootstrap_accept_result(REVISED_POLICY),
        ]

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(REVISED_POLICY)
        mock_run_result.data = json.dumps(REVISED_POLICY)
        mock_run_result.all_messages.return_value = []
        mock_run_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=20)
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        # Use messages event to pass history
        async def _gen_with_messages(*args, **kwargs):
            yield {"type": "model_info", "model": "openai:test", "provider": "openai"}
            yield {"type": "chunk", "text": "thinking..."}
            yield {"type": "messages", "data": fake_messages}
            yield {"type": "result", "data": result_data}

        with patch("app.streaming_optimizer.stream_optimize", _gen_with_messages), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=REVISED_POLICY), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value=None):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        # Verify agent.run was called with message_history
        mock_agent.run.assert_called_once()
        call_kwargs = mock_agent.run.call_args
        assert "message_history" in call_kwargs.kwargs
        assert call_kwargs.kwargs["message_history"] == fake_messages

    @pytest.mark.asyncio
    async def test_no_policy_produced_no_bootstrap(self):
        """If stream_optimize produces no policy, skip bootstrap entirely."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_failed_result()
        bootstrap_gate = MagicMock()

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"]["new_policy"] is None
        # Bootstrap never called
        assert bootstrap_gate.evaluate.call_count == 0

    @pytest.mark.asyncio
    async def test_bootstrap_evaluating_event_emitted(self):
        """Should emit bootstrap_evaluating before each evaluation."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_accept_result()

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        eval_events = [e for e in events if e["type"] == "bootstrap_evaluating"]
        assert len(eval_events) == 1
        assert eval_events[0]["proposal"] == 1


# ═══════════════════════════════════════════════════════════════════════
# Phase 3: game.py integration
# ═══════════════════════════════════════════════════════════════════════


class TestGameIntegration:
    """Test that GameSession passes max_policy_proposals through."""

    def test_game_default_max_policy_proposals(self):
        """New games default to max_policy_proposals=2."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5)
        assert game.max_policy_proposals == 2

    def test_game_custom_max_policy_proposals(self):
        """max_policy_proposals can be set on game creation."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5, max_policy_proposals=3)
        assert game.max_policy_proposals == 3

    def test_game_clamps_max_policy_proposals(self):
        """max_policy_proposals is clamped to 1-5."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5, max_policy_proposals=0)
        assert game.max_policy_proposals == 1
        game2 = Game(game_id="test2", raw_yaml=scenario, total_days=5, max_policy_proposals=10)
        assert game2.max_policy_proposals == 5

    def test_checkpoint_preserves_max_policy_proposals(self):
        """Checkpoint round-trip preserves max_policy_proposals."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5, max_policy_proposals=3)
        cp = game.to_checkpoint()
        restored = Game.from_checkpoint(cp)
        assert restored.max_policy_proposals == 3

    def test_checkpoint_without_field_defaults_to_2(self):
        """Old checkpoints without max_policy_proposals default to 2."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5)
        cp = game.to_checkpoint()
        # Simulate old checkpoint without the field
        cp.pop("max_policy_proposals", None)
        if "settings" in cp:
            cp["settings"].pop("max_policy_proposals", None)
        restored = Game.from_checkpoint(cp)
        assert restored.max_policy_proposals == 2


class TestIsRetryDecline:
    """Tests for _is_retry_decline()."""

    def test_explicit_false(self):
        from app.streaming_optimizer import _is_retry_decline
        assert _is_retry_decline("False") is True
        assert _is_retry_decline("false") is True
        assert _is_retry_decline('"False"') is True
        assert _is_retry_decline("false.") is True

    def test_no_json(self):
        from app.streaming_optimizer import _is_retry_decline
        assert _is_retry_decline("I don't think I can improve further.") is True
        assert _is_retry_decline("No changes needed.") is True

    def test_has_json(self):
        from app.streaming_optimizer import _is_retry_decline
        assert _is_retry_decline('Here is my revised policy: {"version": "2.0"}') is False

    def test_whitespace_and_backticks(self):
        from app.streaming_optimizer import _is_retry_decline
        assert _is_retry_decline("  `False`  ") is True
        assert _is_retry_decline("  ``` false ```  ") is True

    def test_decline_keywords(self):
        from app.streaming_optimizer import _is_retry_decline
        assert _is_retry_decline("no") is True
        assert _is_retry_decline("decline") is True
        assert _is_retry_decline("pass") is True


class TestRetryValidation:
    """Tests for constraint and engine validation on retry proposals."""

    @pytest.mark.asyncio
    async def test_retry_constraint_validation_failure(self):
        """Retry proposal that fails constraint validation is rejected gracefully."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result()

        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(REVISED_POLICY)
        mock_run_result.data = mock_run_result.output
        mock_run_result.all_messages.return_value = []

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=REVISED_POLICY), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value="fraction must be between 0.01 and 1.0"):
            events = await _collect_events(stream_optimize_with_retries(
                AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                {}, bootstrap_gate, max_proposals=2,
            ))

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"].get("retry_validation_failed") is True
        assert "fraction" in results[0]["data"].get("retry_validation_errors", "")

    @pytest.mark.asyncio
    async def test_retry_decline_no_json(self):
        """Agent responds with text but no JSON — treated as decline."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()

        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result()

        mock_run_result = MagicMock()
        mock_run_result.output = "I don't think I can improve the policy further given these constraints."
        mock_run_result.data = mock_run_result.output
        mock_run_result.all_messages.return_value = []

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(stream_optimize_with_retries(
                AGENT_ID, CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                {}, bootstrap_gate, max_proposals=2,
            ))

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        assert results[0]["data"].get("retry_declined") is True


class TestValidateRetryPolicy:
    """Tests for _validate_retry_policy()."""

    def test_valid_policy_returns_none(self):
        from app.streaming_optimizer import _validate_retry_policy
        with patch("app.constraint_presets.build_constraints", return_value=[]), \
             patch("payment_simulator.ai_cash_mgmt.optimization.constraint_validator.ConstraintValidator") as mock_cv, \
             patch("payment_simulator.config.SimulationConfig") as mock_sc, \
             patch("payment_simulator._core.Orchestrator"):
            mock_cv.return_value.validate.return_value = MagicMock(is_valid=True)
            mock_sc.from_dict.return_value.to_ffi_dict.return_value = {}
            result = _validate_retry_policy(VALID_POLICY, AGENT_ID, {"agents": [{"id": AGENT_ID}]}, "simple", None, None)
        assert result is None

    def test_constraint_failure_returns_error(self):
        from app.streaming_optimizer import _validate_retry_policy
        with patch("app.constraint_presets.build_constraints", return_value=[]), \
             patch("payment_simulator.ai_cash_mgmt.optimization.constraint_validator.ConstraintValidator") as mock_cv:
            mock_cv.return_value.validate.return_value = MagicMock(is_valid=False, errors=["bad field"])
            result = _validate_retry_policy(VALID_POLICY, AGENT_ID, {"agents": [{"id": AGENT_ID}]}, "simple", None, None)
        assert result == "bad field"

    def test_engine_failure_returns_error(self):
        from app.streaming_optimizer import _validate_retry_policy
        with patch("app.constraint_presets.build_constraints", return_value=[]), \
             patch("payment_simulator.ai_cash_mgmt.optimization.constraint_validator.ConstraintValidator") as mock_cv, \
             patch("payment_simulator.config.SimulationConfig") as mock_sc:
            mock_cv.return_value.validate.return_value = MagicMock(is_valid=True)
            mock_sc.from_dict.side_effect = ValueError("invalid config")
            result = _validate_retry_policy(VALID_POLICY, AGENT_ID, {"agents": [{"id": AGENT_ID}]}, "simple", None, None)
        assert "Engine validation failed" in result
        assert "invalid config" in result
