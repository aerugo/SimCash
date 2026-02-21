"""Tests for the Prompt Anatomy system (Phase 1)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure web backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Ensure api is importable
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))

from app.prompt_blocks import PromptBlock, StructuredPrompt, PromptProfile


class TestPromptBlock:
    def test_creation_and_serialization(self):
        block = PromptBlock(
            id="sys_full",
            name="System Prompt",
            category="system",
            source="static",
            content="You are an expert.",
            token_estimate=5,
        )
        d = block.to_dict()
        assert d["id"] == "sys_full"
        assert d["name"] == "System Prompt"
        assert d["category"] == "system"
        assert d["content"] == "You are an expert."
        assert d["token_estimate"] == 5
        assert d["enabled"] is True
        assert d["options"] == {}

    def test_summary_dict_small_content(self):
        block = PromptBlock(
            id="test", name="Test", category="user",
            source="dynamic", content="short", token_estimate=1,
        )
        d = block.to_summary_dict()
        assert d["content"] == "short"
        assert "truncated" not in d

    def test_summary_dict_large_content_truncated(self):
        large_content = "x" * 60_000
        block = PromptBlock(
            id="test", name="Test", category="user",
            source="dynamic", content=large_content,
            token_estimate=15000,
        )
        d = block.to_summary_dict()
        assert d.get("truncated") is True
        assert d["content_length"] == 60_000
        assert len(d["content"]) < 2000
        assert "content_hash" in d


class TestStructuredPrompt:
    def _make_blocks(self):
        return [
            PromptBlock(id="sys_full", name="System", category="system",
                        source="static", content="sys content", token_estimate=3),
            PromptBlock(id="usr_header", name="Header", category="user",
                        source="dynamic", content="header content", token_estimate=4),
        ]

    def test_to_dict(self):
        blocks = self._make_blocks()
        sp = StructuredPrompt(
            blocks=blocks,
            system_prompt="sys content",
            user_prompt="header content",
            total_tokens=7,
            profile_hash="abc123",
        )
        d = sp.to_dict()
        assert len(d["blocks"]) == 2
        assert d["total_tokens"] == 7
        assert d["profile_hash"] == "abc123"
        assert d["llm_response"] is None
        assert d["system_prompt"] == "sys content"
        assert d["user_prompt"] == "header content"

    def test_to_summary_dict(self):
        blocks = self._make_blocks()
        sp = StructuredPrompt(
            blocks=blocks,
            system_prompt="sys",
            user_prompt="usr",
            total_tokens=7,
            profile_hash="abc123",
            llm_response="policy json",
            llm_response_tokens=3,
        )
        d = sp.to_summary_dict()
        assert "system_prompt" not in d  # summary excludes full text
        assert d["total_tokens"] == 7
        assert d["llm_response_tokens"] == 3

    def test_compute_profile_hash(self):
        blocks = self._make_blocks()
        h1 = StructuredPrompt.compute_profile_hash(blocks)
        assert len(h1) == 16

        # Same blocks = same hash
        h2 = StructuredPrompt.compute_profile_hash(blocks)
        assert h1 == h2

        # Different enabled state = different hash
        blocks[0].enabled = False
        h3 = StructuredPrompt.compute_profile_hash(blocks)
        assert h3 != h1

    def test_with_llm_response(self):
        blocks = self._make_blocks()
        sp = StructuredPrompt(
            blocks=blocks,
            system_prompt="sys",
            user_prompt="usr",
            total_tokens=7,
            profile_hash="abc",
            llm_response='{"version": "2.0"}',
            llm_response_tokens=5,
        )
        d = sp.to_dict()
        assert d["llm_response"] == '{"version": "2.0"}'
        assert d["llm_response_tokens"] == 5


class TestPromptProfile:
    def test_creation(self):
        profile = PromptProfile(
            id="test-profile",
            name="Test Profile",
            description="A test",
            blocks={"usr_simulation_trace": {"enabled": True, "options": {"verbosity": "full"}}},
        )
        assert profile.id == "test-profile"
        assert profile.blocks["usr_simulation_trace"]["options"]["verbosity"] == "full"


class TestBuildBlocks:
    """Test that SingleAgentContextBuilder.build_blocks() produces correct blocks."""

    def test_build_blocks_produces_blocks(self):
        from payment_simulator.ai_cash_mgmt.prompts.context_types import SingleAgentContext
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import SingleAgentContextBuilder

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            current_policy={"parameters": {"initial_liquidity_fraction": 0.5}},
            current_metrics={"total_cost_mean": 10000},
            iteration_history=[],
            simulation_trace="tick 0: arrival",
            sample_seed=42,
            sample_cost=10000,
            mean_cost=10000,
            cost_std=500,
            cost_breakdown={"delay": 3000, "collateral": 5000, "overdraft": 2000},
            cost_rates={"delay_rate": 0.01},
        )
        builder = SingleAgentContextBuilder(context)
        blocks = builder.build_blocks()

        # Should have multiple blocks
        assert len(blocks) >= 4

        # Check block IDs
        block_ids = [b.id for b in blocks]
        assert "usr_header" in block_ids
        assert "usr_current_state" in block_ids
        assert "usr_simulation_trace" in block_ids
        assert "usr_final_instructions" in block_ids

        # All blocks should have content and token estimates
        for b in blocks:
            assert b.content
            assert b.token_estimate > 0
            assert b.category == "user"

    def test_build_blocks_matches_build(self):
        """build_blocks() content should match build() output."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import SingleAgentContext
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import SingleAgentContextBuilder

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"initial_liquidity_fraction": 0.5}},
            current_metrics={"total_cost_mean": 5000},
            iteration_history=[],
            simulation_trace="tick 0: test",
            sample_seed=1,
            sample_cost=5000,
            mean_cost=5000,
            cost_std=0,
            cost_breakdown={"delay": 2000},
            cost_rates={},
        )
        builder = SingleAgentContextBuilder(context)

        full_text = builder.build()
        blocks = builder.build_blocks()

        # Each block's content should appear in the full text
        for b in blocks:
            assert b.content in full_text, f"Block {b.id} content not found in build() output"
