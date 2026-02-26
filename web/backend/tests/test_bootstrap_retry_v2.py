"""Tests for bootstrap retry robustness — v2 (TDD).

These tests cover the ACTUAL bugs found in production:
1. Retry LLM call fails (504 timeout) → result loses original metadata
2. Retry failure is silent — no visibility in optimization thread
3. Retry should preserve original proposal's metadata for audit trail

Written BEFORE the fix. All new tests should FAIL initially.
"""
from __future__ import annotations

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Test fixtures ─────────────────────────────────────────────────────

VALID_POLICY = {
    "version": "2.0",
    "policy_id": "test_policy",
    "parameters": {"initial_liquidity_fraction": 0.5},
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
    day.per_agent_costs = {"BANK_A": 1000}
    day.per_agent_cost_std = {"BANK_A": 100}
    day.costs = {"BANK_A": {"delay_cost": 100, "liquidity_cost": 200, "penalty_cost": 50, "total": 1000}}
    day.events = []
    day.seed = 42
    day.policies = {"BANK_A": CURRENT_POLICY}
    day.agent_histories = {"BANK_A": MagicMock()}
    day.rejected_policies = {}
    return day


def _make_accepted_result():
    return {
        "new_policy": VALID_POLICY,
        "old_policy": CURRENT_POLICY,
        "reasoning": "LLM proposed fraction change",
        "old_fraction": 0.8,
        "new_fraction": 0.5,
        "accepted": True,
        "mock": False,
        "raw_response": json.dumps(VALID_POLICY),
        "thinking": "deep thoughts",
        "usage": {"input_tokens": 5000, "output_tokens": 800},
        "latency_seconds": 12.3,
        "model": "openai:gpt-5.2",
        "structured_prompt": {"system": "...", "user": "..."},
        "validation_attempts": 1,
    }


def _make_bootstrap_reject_result(base_result=None):
    """What BootstrapGate.evaluate() returns on rejection."""
    r = base_result or _make_accepted_result()
    return {
        **r,
        "new_policy": None,
        "new_fraction": None,
        "accepted": False,
        "rejection_reason": "No improvement: delta_sum=-500",
        "rejected_policy": r["new_policy"],
        "rejected_fraction": r["new_fraction"],
        "bootstrap": BOOTSTRAP_STATS,
        "reasoning": r["reasoning"] + " [REJECTED: No improvement]",
    }


async def _collect_events(async_gen):
    events = []
    async for event in async_gen:
        events.append(event)
    return events


def _mock_stream_optimize_events(result_data, messages=None):
    async def _gen(*args, **kwargs):
        yield {"type": "model_info", "model": "openai:gpt-5.2", "provider": "openai"}
        yield {"type": "chunk", "text": "thinking..."}
        if messages is not None:
            yield {"type": "messages", "data": messages}
        else:
            yield {"type": "messages", "data": [{"role": "user", "content": "prompt"}, {"role": "assistant", "content": "response"}]}
        yield {"type": "result", "data": result_data}
    return _gen


# ═══════════════════════════════════════════════════════════════════════
# BUG 1: When retry LLM call fails, result loses original metadata
# ═══════════════════════════════════════════════════════════════════════


class TestRetryFailurePreservesMetadata:
    """When the retry LLM call fails (504, timeout, etc.), the final result
    should still contain the original proposal's metadata for audit trail."""

    @pytest.mark.asyncio
    async def test_retry_llm_failure_preserves_model(self):
        """Result should contain original LLM model name even when retry fails."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("status_code: 504, DEADLINE_EXCEEDED"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        result = results[0]["data"]
        # Should preserve original LLM metadata
        assert result.get("model") == "openai:gpt-5.2", f"model lost: {result.get('model')}"
        assert result.get("latency_seconds") == 12.3, f"latency lost: {result.get('latency_seconds')}"

    @pytest.mark.asyncio
    async def test_retry_llm_failure_preserves_usage(self):
        """Result should contain original token usage even when retry fails."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        result = results[0]["data"]
        assert result.get("usage") == {"input_tokens": 5000, "output_tokens": 800}

    @pytest.mark.asyncio
    async def test_retry_llm_failure_preserves_validation_attempts(self):
        """Result should contain original validation_attempts."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("timeout"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        result = results[0]["data"]
        assert result.get("validation_attempts") == 1


# ═══════════════════════════════════════════════════════════════════════
# BUG 2: Retry failure is invisible — no event tells the client
# ═══════════════════════════════════════════════════════════════════════


class TestRetryFailureVisibility:
    """When retry fails, it should emit a visible event so the client
    and API can show what happened."""

    @pytest.mark.asyncio
    async def test_retry_failure_emits_error_chunk(self):
        """Should yield a chunk event explaining the retry failure."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("status_code: 504"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        chunk_texts = [e["text"] for e in events if e["type"] == "chunk"]
        retry_error_chunks = [t for t in chunk_texts if "504" in t or "Retry failed" in t.lower() or "retry failed" in t.lower()]
        assert len(retry_error_chunks) >= 1, f"No retry failure chunk found. Chunks: {chunk_texts}"

    @pytest.mark.asyncio
    async def test_retry_failure_result_has_retry_error_field(self):
        """Result should have a field indicating retry was attempted and failed."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("status_code: 504"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        result = results[0]["data"]
        assert result.get("retry_failed") is True, f"Missing retry_failed flag. Keys: {list(result.keys())}"
        assert "504" in str(result.get("retry_error", "")), f"retry_error should contain error details"


# ═══════════════════════════════════════════════════════════════════════
# BUG 3: Stale test expectations (defaults changed from 1→2)
# ═══════════════════════════════════════════════════════════════════════


class TestGameDefaultsV2:
    """Updated tests for current default (2, not 1)."""

    def test_game_default_max_policy_proposals_is_2(self):
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id
        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5)
        assert game.max_policy_proposals == 2

    def test_checkpoint_without_field_defaults_to_2(self):
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id
        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test", raw_yaml=scenario, total_days=5)
        cp = game.to_checkpoint()
        cp.pop("max_policy_proposals", None)
        if "settings" in cp:
            cp["settings"].pop("max_policy_proposals", None)
        restored = Game.from_checkpoint(cp)
        assert restored.max_policy_proposals == 2


# ═══════════════════════════════════════════════════════════════════════
# BUG 4: bootstrap_gate.evaluate() strips metadata from result
# The BootstrapGate copies the result, sets new_policy=None, but
# doesn't preserve model/latency/usage/validation_attempts consistently.
# ═══════════════════════════════════════════════════════════════════════


class TestRetryTimeout:
    """Retry LLM call should timeout after 120s."""

    @pytest.mark.asyncio
    async def test_retry_timeout_yields_retry_failed(self):
        """If retry LLM takes >120s, it should timeout and yield retry_failed."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_accepted_result()
        bootstrap_gate = MagicMock()
        bootstrap_gate.evaluate.return_value = _make_bootstrap_reject_result(result_data)

        mock_agent = MagicMock()

        async def _slow_run(*args, **kwargs):
            await asyncio.sleep(999)  # Will be cancelled by timeout

        mock_agent.run = _slow_run

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize_events(result_data)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=bootstrap_gate, max_proposals=2,
                )
            )

        results = [e for e in events if e["type"] == "result"]
        assert len(results) == 1
        result = results[0]["data"]
        assert result.get("retry_failed") is True
        assert result["accepted"] is False


class TestBootstrapGatePreservesMetadata:
    """BootstrapGate.evaluate() should preserve LLM call metadata."""

    def test_rejected_result_preserves_model(self):
        """Even when rejected, the result dict should keep model info."""
        from app.bootstrap_gate import BootstrapGate

        raw_yaml = {
            "agents": [{"id": "BANK_A", "opening_balance": 100000, "liquidity_pool": 100000}],
        }
        gate = BootstrapGate(
            raw_yaml=raw_yaml,
            agent_ids=["BANK_A"],
            ticks_per_day=12,
            base_seed=42,
            policies={"BANK_A": CURRENT_POLICY},
        )

        result = _make_accepted_result()
        # Need agent_histories for bootstrap to run
        day = _make_mock_day()
        day.agent_histories["BANK_A"].outgoing = [MagicMock()]
        day.agent_histories["BANK_A"].incoming = [MagicMock()]

        # Mock the sampler/evaluator to force rejection
        with patch("app.bootstrap_gate.BootstrapSampler") as mock_sampler, \
             patch("app.bootstrap_gate.BootstrapPolicyEvaluator") as mock_eval:
            mock_sampler.return_value.generate_samples.return_value = []
            mock_delta = MagicMock()
            mock_delta.delta = -100
            mock_delta.cost_a = 10000
            mock_delta.cost_b = 10100
            mock_delta.settlement_rate = 1.0
            mock_eval.return_value.compute_paired_deltas.return_value = [mock_delta] * 50
            
            out = gate.evaluate("BANK_A", day, copy.deepcopy(result))

        assert out["accepted"] is False
        # These should survive bootstrap rejection:
        assert out.get("model") == "openai:gpt-5.2", f"model lost after bootstrap: {out.get('model')}"
        assert out.get("latency_seconds") == 12.3, f"latency lost: {out.get('latency_seconds')}"
        assert out.get("usage") == {"input_tokens": 5000, "output_tokens": 800}, f"usage lost: {out.get('usage')}"
        assert out.get("validation_attempts") == 1, f"validation_attempts lost: {out.get('validation_attempts')}"
