"""Integration tests for temporal mode in optimization loop.

Phase 5 of deterministic-evaluation-modes implementation.

Tests verify that temporal mode is properly wired into the optimization loop:
- Temporal mode skips paired evaluation
- Uses _evaluate_temporal_acceptance for decisions
- Properly handles policy revert on cost increase
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payment_simulator.experiments.config.experiment_config import EvaluationConfig
from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_mock_config(
    mode: str = "deterministic-temporal",
    master_seed: int = 42,
    max_iterations: int = 5,
) -> MagicMock:
    """Create mock ExperimentConfig for testing."""
    mock_config = MagicMock()
    mock_config.name = f"test_{mode}"
    mock_config.master_seed = master_seed

    # Convergence
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Use real EvaluationConfig for proper property behavior
    mock_config.evaluation = EvaluationConfig(ticks=2, mode=mode, num_samples=1)

    mock_config.optimized_agents = ("BANK_A",)
    mock_config.llm = LLMConfig(model="test:mock")
    mock_config.get_constraints.return_value = None

    return mock_config


class TestTemporalModeIntegration:
    """Tests for temporal mode integration into optimization loop."""

    @pytest.mark.asyncio
    async def test_temporal_mode_calls_evaluate_temporal_acceptance(self) -> None:
        """In temporal mode, _evaluate_temporal_acceptance should be called."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Track method calls
        temporal_called = False
        original_temporal = loop._evaluate_temporal_acceptance

        def tracking_temporal(agent_id: str, current_cost: int) -> bool:
            nonlocal temporal_called
            temporal_called = True
            return original_temporal(agent_id, current_cost)

        # Set up loop state
        loop._current_iteration = 1
        loop._policies["BANK_A"] = {"policy_id": "test"}

        # Mock LLM client
        mock_llm = AsyncMock()
        mock_llm.generate_policy = AsyncMock(return_value={"policy_id": "new_policy"})
        loop._llm_client = mock_llm

        # Mock _run_simulation_with_events to return controlled result
        mock_enriched = MagicMock()
        mock_enriched.total_cost = 1000
        mock_enriched.events = []

        with patch.object(loop, "_evaluate_temporal_acceptance", tracking_temporal):
            with patch.object(loop, "_run_simulation_with_events", return_value=mock_enriched):
                with patch.object(loop, "_build_agent_contexts", return_value={}):
                    with patch.object(loop, "_save_llm_interaction_event"):
                        with patch.object(loop, "_save_policy_evaluation"):
                            with patch.object(loop, "_record_iteration_history"):
                                await loop._optimize_agent("BANK_A", current_cost=1000)

        assert temporal_called, "_evaluate_temporal_acceptance should be called in temporal mode"

    @pytest.mark.asyncio
    async def test_temporal_mode_skips_should_accept_policy(self) -> None:
        """In temporal mode, _should_accept_policy should NOT be called."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Track if _should_accept_policy is called
        should_accept_called = False

        async def tracking_should_accept(*args: Any, **kwargs: Any) -> tuple:
            nonlocal should_accept_called
            should_accept_called = True
            raise AssertionError("_should_accept_policy should not be called in temporal mode")

        loop._current_iteration = 1
        loop._policies["BANK_A"] = {"policy_id": "test"}

        mock_llm = AsyncMock()
        mock_llm.generate_policy = AsyncMock(return_value={"policy_id": "new"})
        loop._llm_client = mock_llm

        mock_enriched = MagicMock()
        mock_enriched.total_cost = 1000
        mock_enriched.events = []

        with patch.object(loop, "_should_accept_policy", tracking_should_accept):
            with patch.object(loop, "_run_simulation_with_events", return_value=mock_enriched):
                with patch.object(loop, "_build_agent_contexts", return_value={}):
                    with patch.object(loop, "_save_llm_interaction_event"):
                        with patch.object(loop, "_save_policy_evaluation"):
                            with patch.object(loop, "_record_iteration_history"):
                                await loop._optimize_agent("BANK_A", current_cost=1000)

        assert not should_accept_called, "_should_accept_policy should NOT be called in temporal mode"

    @pytest.mark.asyncio
    async def test_pairwise_mode_does_not_call_temporal_acceptance(self) -> None:
        """In pairwise mode, _evaluate_temporal_acceptance should NOT be called."""
        mock_config = _create_mock_config(mode="deterministic-pairwise")
        loop = OptimizationLoop(config=mock_config)

        temporal_called = False

        def tracking_temporal(*args: Any, **kwargs: Any) -> bool:
            nonlocal temporal_called
            temporal_called = True
            return True

        loop._current_iteration = 1
        loop._policies["BANK_A"] = {"policy_id": "test"}

        # Pairwise mode requires constraints for optimization
        # Without constraints, it returns early
        # This test verifies temporal acceptance is NOT called in pairwise mode
        with patch.object(loop, "_evaluate_temporal_acceptance", tracking_temporal):
            await loop._optimize_agent("BANK_A", current_cost=1000)

        assert not temporal_called, "_evaluate_temporal_acceptance should NOT be called in pairwise mode"


class TestTemporalPolicyRevert:
    """Tests for policy revert behavior in temporal mode."""

    @pytest.mark.asyncio
    async def test_temporal_stores_previous_policy_before_acceptance(self) -> None:
        """Temporal mode should store current policy before generating new one."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        original_policy = {"policy_id": "original", "version": "1.0"}
        loop._current_iteration = 1
        loop._policies["BANK_A"] = original_policy.copy()

        mock_llm = AsyncMock()
        mock_llm.generate_policy = AsyncMock(return_value={"policy_id": "new"})
        loop._llm_client = mock_llm

        mock_enriched = MagicMock()
        mock_enriched.total_cost = 1000
        mock_enriched.events = []

        with patch.object(loop, "_run_simulation_with_events", return_value=mock_enriched):
            with patch.object(loop, "_build_agent_contexts", return_value={}):
                with patch.object(loop, "_save_llm_interaction_event"):
                    with patch.object(loop, "_save_policy_evaluation"):
                        with patch.object(loop, "_record_iteration_history"):
                            await loop._optimize_agent("BANK_A", current_cost=1000)

        # Should have stored the original policy
        assert "BANK_A" in loop._previous_policies
        assert loop._previous_policies["BANK_A"]["policy_id"] == "original"

    @pytest.mark.asyncio
    async def test_temporal_reverts_policy_on_cost_increase(self) -> None:
        """If cost increases in temporal mode, should revert to previous policy."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Set up: previous iteration had cost 1000
        loop._previous_iteration_costs["BANK_A"] = 1000
        previous_policy = {"policy_id": "previous_good"}
        loop._previous_policies["BANK_A"] = previous_policy.copy()
        current_policy = {"policy_id": "current_bad"}
        loop._policies["BANK_A"] = current_policy.copy()
        loop._current_iteration = 2

        mock_llm = AsyncMock()
        loop._llm_client = mock_llm

        mock_enriched = MagicMock()
        mock_enriched.total_cost = 1000
        mock_enriched.events = []

        with patch.object(loop, "_run_simulation_with_events", return_value=mock_enriched):
            with patch.object(loop, "_build_agent_contexts", return_value={}):
                with patch.object(loop, "_save_llm_interaction_event"):
                    with patch.object(loop, "_save_policy_evaluation"):
                        with patch.object(loop, "_record_iteration_history"):
                            # Current cost 1200 > previous 1000 -> should reject
                            await loop._optimize_agent("BANK_A", current_cost=1200)

        # Policy should be reverted to previous
        assert loop._policies["BANK_A"]["policy_id"] == "previous_good"
        # LLM should NOT have been called (rejected before generation)
        mock_llm.generate_policy.assert_not_called()


class TestTemporalFirstIteration:
    """Tests for temporal mode first iteration behavior."""

    @pytest.mark.asyncio
    async def test_temporal_first_iteration_always_accepts(self) -> None:
        """First iteration in temporal mode should always accept and store cost."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # First iteration - no previous costs
        loop._current_iteration = 1
        loop._previous_iteration_costs = {}  # Empty!
        loop._policies["BANK_A"] = {"policy_id": "initial"}

        # Even without LLM, temporal acceptance should work
        # (LLM requires constraints which we don't set in this test)

        # Call the optimization
        await loop._optimize_agent("BANK_A", current_cost=99999)

        # Should have accepted and stored cost via _evaluate_temporal_acceptance
        assert loop._previous_iteration_costs.get("BANK_A") == 99999
        # Should have stored previous policy for potential revert
        assert loop._previous_policies.get("BANK_A") is not None
        # Accepted changes flag should be set
        assert loop._accepted_changes.get("BANK_A") is True

    @pytest.mark.asyncio
    async def test_temporal_first_iteration_stores_cost_even_with_high_value(self) -> None:
        """First iteration stores cost regardless of how high it is."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        loop._current_iteration = 1
        loop._previous_iteration_costs = {}
        loop._policies["BANK_A"] = {"policy_id": "test"}

        # Very high cost - should still be accepted (first iteration)
        await loop._optimize_agent("BANK_A", current_cost=999999999)

        # Cost should be stored
        assert loop._previous_iteration_costs["BANK_A"] == 999999999
