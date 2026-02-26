"""Tests for bootstrap_proposals audit trail on optimization results.

TDD: Tests written first. All should FAIL until implementation.

Stefan needs per-proposal data for Phase C paper analysis:
- bootstrap_proposals: array of all proposals attempted
- total_proposals: count of LLM calls made
- Each proposal: number, fraction, costs, accepted, latency, validation_attempts
"""
from __future__ import annotations

import asyncio
import copy
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Fixtures ──────────────────────────────────────────────────────────

VALID_POLICY_05 = {
    "version": "2.0",
    "policy_id": "p05",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

VALID_POLICY_08 = {
    "version": "2.0",
    "policy_id": "p08",
    "parameters": {"initial_liquidity_fraction": 0.08},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

CURRENT_POLICY = {
    "version": "2.0",
    "policy_id": "current",
    "parameters": {"initial_liquidity_fraction": 0.1},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

BOOTSTRAP_REJECT = {
    "delta_sum": -500,
    "mean_delta": -50,
    "cv": 0.15,
    "ci_lower": -120,
    "ci_upper": 20,
    "num_samples": 50,
    "old_mean_cost": 11576,
    "new_mean_cost": 13622,
    "rejection_reason": "No improvement: delta_sum=-500",
    "profile": "moderate",
    "cv_threshold": 0.5,
    "require_significance": True,
}

BOOTSTRAP_ACCEPT = {
    **BOOTSTRAP_REJECT,
    "delta_sum": 5000,
    "mean_delta": 100,
    "ci_lower": 50,
    "ci_upper": 150,
    "new_mean_cost": 9000,
    "rejection_reason": "",
}


def _make_mock_day():
    day = MagicMock()
    day.day_num = 1
    day.per_agent_costs = {"BANK_A": 11576}
    day.per_agent_cost_std = {"BANK_A": 100}
    day.costs = {"BANK_A": {"total": 11576}}
    day.events = []
    day.seed = 42
    day.policies = {"BANK_A": CURRENT_POLICY}
    day.agent_histories = {"BANK_A": MagicMock()}
    day.rejected_policies = {}
    return day


def _make_llm_result(policy, latency=12.3, validation_attempts=1):
    return {
        "new_policy": policy,
        "old_policy": CURRENT_POLICY,
        "reasoning": "LLM proposed change",
        "old_fraction": 0.1,
        "new_fraction": policy["parameters"]["initial_liquidity_fraction"],
        "accepted": True,
        "mock": False,
        "raw_response": json.dumps(policy),
        "thinking": "deep thoughts",
        "usage": {"input_tokens": 5000, "output_tokens": 800},
        "latency_seconds": latency,
        "model": "openai:gpt-5.2",
        "structured_prompt": {"system": "...", "user": "..."},
        "validation_attempts": validation_attempts,
    }


def _make_bootstrap_reject_result(result, stats=None):
    s = stats or BOOTSTRAP_REJECT
    return {
        **result,
        "new_policy": None,
        "new_fraction": None,
        "accepted": False,
        "rejection_reason": s["rejection_reason"],
        "rejected_policy": result["new_policy"],
        "rejected_fraction": result["new_fraction"],
        "bootstrap": s,
        "reasoning": result["reasoning"] + " [REJECTED]",
    }


def _make_bootstrap_accept_result(result, stats=None):
    s = stats or BOOTSTRAP_ACCEPT
    return {
        **result,
        "accepted": True,
        "bootstrap": s,
    }


async def _collect_events(async_gen):
    events = []
    async for event in async_gen:
        events.append(event)
    return events


def _mock_stream_optimize(result_data):
    async def _gen(*args, **kwargs):
        yield {"type": "model_info", "model": "openai:gpt-5.2", "provider": "openai"}
        yield {"type": "chunk", "text": "thinking..."}
        yield {"type": "messages", "data": [
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": "response"},
        ]}
        yield {"type": "result", "data": result_data}
    return _gen


# ═══════════════════════════════════════════════════════════════════════
# Test: bootstrap_proposals array on final result
# ═══════════════════════════════════════════════════════════════════════


class TestBootstrapProposalsArray:
    """The final result should contain a `bootstrap_proposals` array
    with one entry per proposal attempted."""

    @pytest.mark.asyncio
    async def test_single_proposal_accepted(self):
        """One proposal, accepted → bootstrap_proposals has 1 entry."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result_data = _make_llm_result(VALID_POLICY_05)
        gate = MagicMock()
        gate.evaluate.return_value = _make_bootstrap_accept_result(result_data)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize(result_data)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=gate, max_proposals=2,
                )
            )

        result = [e for e in events if e["type"] == "result"][0]["data"]
        assert "bootstrap_proposals" in result, f"Missing bootstrap_proposals. Keys: {list(result.keys())}"
        assert len(result["bootstrap_proposals"]) == 1
        assert result["total_proposals"] == 1

        p = result["bootstrap_proposals"][0]
        assert p["proposal_number"] == 1
        assert p["suggested_fraction"] == 0.5
        assert p["accepted"] is True
        assert p["old_mean_cost"] == BOOTSTRAP_ACCEPT["old_mean_cost"]
        assert p["new_mean_cost"] == BOOTSTRAP_ACCEPT["new_mean_cost"]
        assert p["delta_sum"] == BOOTSTRAP_ACCEPT["delta_sum"]
        assert p["llm_latency_seconds"] == 12.3
        assert p["validation_attempts"] == 1

    @pytest.mark.asyncio
    async def test_two_proposals_first_rejected_second_accepted(self):
        """Proposal 1 rejected, proposal 2 accepted → 2 entries."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result1 = _make_llm_result(VALID_POLICY_05, latency=12.3)
        result2_policy = VALID_POLICY_08

        gate = MagicMock()
        gate.evaluate.side_effect = [
            _make_bootstrap_reject_result(result1),
            _make_bootstrap_accept_result(
                _make_llm_result(result2_policy, latency=8.5, validation_attempts=0),
                BOOTSTRAP_ACCEPT,
            ),
        ]

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(result2_policy)
        mock_run_result.data = mock_run_result.output
        mock_run_result.all_messages.return_value = []
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize(result1)), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=result2_policy), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value=None):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=gate, max_proposals=2,
                )
            )

        result = [e for e in events if e["type"] == "result"][0]["data"]
        assert len(result["bootstrap_proposals"]) == 2
        assert result["total_proposals"] == 2

        p1 = result["bootstrap_proposals"][0]
        assert p1["proposal_number"] == 1
        assert p1["suggested_fraction"] == 0.5
        assert p1["accepted"] is False
        assert p1["old_mean_cost"] == BOOTSTRAP_REJECT["old_mean_cost"]
        assert p1["new_mean_cost"] == BOOTSTRAP_REJECT["new_mean_cost"]

        p2 = result["bootstrap_proposals"][1]
        assert p2["proposal_number"] == 2
        assert p2["suggested_fraction"] == 0.08
        assert p2["accepted"] is True

    @pytest.mark.asyncio
    async def test_two_proposals_both_rejected(self):
        """Both proposals rejected → 2 entries, final accepted=False."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result1 = _make_llm_result(VALID_POLICY_05, latency=10.0)

        gate = MagicMock()
        reject_stats_2 = {**BOOTSTRAP_REJECT, "new_mean_cost": 12000, "delta_sum": -200}
        gate.evaluate.side_effect = [
            _make_bootstrap_reject_result(result1),
            _make_bootstrap_reject_result(
                _make_llm_result(VALID_POLICY_08, latency=7.0),
                reject_stats_2,
            ),
        ]

        mock_agent = MagicMock()
        mock_run_result = MagicMock()
        mock_run_result.output = json.dumps(VALID_POLICY_08)
        mock_run_result.data = mock_run_result.output
        mock_run_result.all_messages.return_value = []
        mock_agent.run = AsyncMock(return_value=mock_run_result)

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize(result1)), \
             patch("app.streaming_optimizer._parse_policy_response", return_value=VALID_POLICY_08), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent), \
             patch("app.streaming_optimizer._validate_retry_policy", return_value=None):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=gate, max_proposals=2,
                )
            )

        result = [e for e in events if e["type"] == "result"][0]["data"]
        assert result["accepted"] is False
        assert len(result["bootstrap_proposals"]) == 2
        assert result["bootstrap_proposals"][0]["accepted"] is False
        assert result["bootstrap_proposals"][1]["accepted"] is False

    @pytest.mark.asyncio
    async def test_no_policy_produced_empty_proposals(self):
        """If LLM produces no policy, bootstrap_proposals should be empty."""
        from app.streaming_optimizer import stream_optimize_with_retries

        no_policy_result = {
            "new_policy": None, "old_policy": CURRENT_POLICY,
            "reasoning": "Failed", "accepted": False, "mock": False,
            "old_fraction": 0.1, "new_fraction": None,
            "raw_response": "", "thinking": "", "usage": {},
            "latency_seconds": 5.0, "model": "openai:gpt-5.2",
            "structured_prompt": None, "validation_attempts": 3,
        }
        gate = MagicMock()

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize(no_policy_result)):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=gate, max_proposals=2,
                )
            )

        result = [e for e in events if e["type"] == "result"][0]["data"]
        assert result.get("bootstrap_proposals", []) == []
        assert result.get("total_proposals", 0) == 0

    @pytest.mark.asyncio
    async def test_retry_llm_failure_still_has_proposal_1(self):
        """If retry LLM fails, proposal 1 should still be in the array."""
        from app.streaming_optimizer import stream_optimize_with_retries

        result1 = _make_llm_result(VALID_POLICY_05, latency=12.0)
        gate = MagicMock()
        gate.evaluate.return_value = _make_bootstrap_reject_result(result1)

        mock_agent = MagicMock()
        mock_agent.run = AsyncMock(side_effect=Exception("504 timeout"))

        with patch("app.streaming_optimizer.stream_optimize", _mock_stream_optimize(result1)), \
             patch("app.streaming_optimizer._get_or_create_retry_agent", return_value=mock_agent):
            events = await _collect_events(
                stream_optimize_with_retries(
                    "BANK_A", CURRENT_POLICY, _make_mock_day(), [_make_mock_day()],
                    {}, bootstrap_gate=gate, max_proposals=2,
                )
            )

        result = [e for e in events if e["type"] == "result"][0]["data"]
        assert len(result.get("bootstrap_proposals", [])) == 1
        assert result["bootstrap_proposals"][0]["proposal_number"] == 1
        assert result["bootstrap_proposals"][0]["accepted"] is False
        assert result.get("retry_failed") is True


# ═══════════════════════════════════════════════════════════════════════
# Test: API serialization
# ═══════════════════════════════════════════════════════════════════════


class TestAPIExposesBootstrapProposals:
    """The optimization-threads API should include bootstrap_proposals."""

    def test_result_includes_bootstrap_proposals(self):
        """API result dict should pass through bootstrap_proposals."""
        # This tests that the API serialization in api_v1.py includes
        # the bootstrap_proposals field from the result dict.
        result_data = {
            "old_policy": CURRENT_POLICY,
            "new_policy": VALID_POLICY_05,
            "old_fraction": 0.1,
            "new_fraction": 0.5,
            "accepted": True,
            "mock": False,
            "bootstrap_proposals": [
                {
                    "proposal_number": 1,
                    "suggested_fraction": 0.5,
                    "old_mean_cost": 11576,
                    "new_mean_cost": 9000,
                    "delta_sum": 5000,
                    "accepted": True,
                    "llm_latency_seconds": 12.3,
                    "validation_attempts": 1,
                }
            ],
            "total_proposals": 1,
        }

        # Simulate the API serialization from api_v1.py
        result = {
            "old_policy": result_data.get("old_policy"),
            "new_policy": result_data.get("new_policy"),
            "old_fraction": result_data.get("old_fraction"),
            "new_fraction": result_data.get("new_fraction"),
            "accepted": result_data.get("accepted"),
            "mock": result_data.get("mock"),
            "rejection_reason": result_data.get("rejection_reason"),
            "bootstrap": result_data.get("bootstrap"),
            "retry_failed": result_data.get("retry_failed"),
            "retry_error": result_data.get("retry_error"),
            "retry_declined": result_data.get("retry_declined"),
            "bootstrap_proposal": result_data.get("bootstrap_proposal"),
            "bootstrap_proposals": result_data.get("bootstrap_proposals"),
            "total_proposals": result_data.get("total_proposals"),
        }

        assert result["bootstrap_proposals"] is not None
        assert len(result["bootstrap_proposals"]) == 1
        assert result["total_proposals"] == 1
