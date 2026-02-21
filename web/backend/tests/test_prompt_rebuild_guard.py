"""Test that _build_optimization_prompt only rebuilds prompts when a profile is active.

Regression test for rev 102 bug (commit c8b2424f) where unconditional prompt
rebuild corrupted user prompts even without a prompt profile.
"""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure api/ is on path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))


def _make_mock_day(agent_id: str, cost: float = 100.0, seed: int = 42):
    """Create a minimal mock GameDay."""
    day = MagicMock()
    day.per_agent_costs = {agent_id: cost}
    day.costs = {agent_id: {"delay_cost": 50, "liquidity_cost": 30, "penalty_cost": 20}}
    day.per_agent_cost_std = {agent_id: 10.0}
    day.policies = {agent_id: _make_policy()}
    day.events = []
    day.seed = seed
    return day


def _make_policy(fraction: float = 0.5):
    return {
        "version": "2.0",
        "policy_id": "test",
        "parameters": {"initial_liquidity_fraction": fraction},
        "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
        "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
    }


def _make_raw_yaml():
    return {"cost_rates": {"delay": 1, "liquidity": 1, "penalty": 100}}


class TestPromptRebuildGuard:
    """Verify prompt rebuild only happens with an explicit prompt_profile."""

    def test_no_profile_preserves_original_prompt(self):
        """Without a prompt_profile, user_prompt should be the original build
        (ending with 'Output ONLY the JSON policy'), not a block-rebuilt version."""
        from app.streaming_optimizer import _build_optimization_prompt

        agent_id = "BANK_A"
        policy = _make_policy(0.5)
        last_day = _make_mock_day(agent_id)
        all_days = [last_day]

        _sys, user_prompt, _ctx = _build_optimization_prompt(
            agent_id, policy, last_day, all_days, _make_raw_yaml(),
            prompt_profile=None,
        )

        # The original prompt ends with the generate instruction
        assert "Output ONLY the JSON policy" in user_prompt
        # And should contain the current policy JSON
        assert json.dumps(policy, indent=2) in user_prompt

        # Count occurrences of the policy JSON — should appear exactly once
        policy_json = json.dumps(policy, indent=2)
        assert user_prompt.count(policy_json) == 1, (
            "Policy JSON should appear exactly once without a profile"
        )

    def test_with_profile_rebuilds_from_blocks(self):
        """With a prompt_profile, user_prompt should be rebuilt from enabled blocks."""
        from app.streaming_optimizer import _build_optimization_prompt

        agent_id = "BANK_A"
        policy = _make_policy(0.5)
        last_day = _make_mock_day(agent_id)
        all_days = [last_day]

        # Empty profile (all blocks stay enabled by default)
        profile: dict = {}

        _sys, user_prompt_with_profile, _ctx = _build_optimization_prompt(
            agent_id, policy, last_day, all_days, _make_raw_yaml(),
            prompt_profile=profile,
        )

        # With a profile active, the prompt is rebuilt from blocks
        # It should NOT have the duplicate "Output ONLY" appended
        count = user_prompt_with_profile.count("Output ONLY the JSON policy")
        assert count <= 1, (
            f"'Output ONLY' should not be duplicated in rebuilt prompt (found {count}×)"
        )
