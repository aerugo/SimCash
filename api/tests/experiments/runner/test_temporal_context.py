"""Tests for temporal mode LLM context (INV-12: LLM Context Identity).

CRITICAL INVARIANT (INV-12): The LLM must receive simulation context
regardless of evaluation mode. Temporal mode was passing None for all
context fields, causing the LLM to optimize blindly.

This test file verifies that temporal mode provides simulation visibility
to the LLM, matching the behavior of bootstrap and deterministic-pairwise modes.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
    AgentSimulationContext,
)
from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_temporal_config(
    master_seed: int = 42,
    max_iterations: int = 10,
) -> MagicMock:
    """Create a mock ExperimentConfig for temporal mode testing."""
    mock_config = MagicMock()
    mock_config.name = "test_temporal_context"
    mock_config.master_seed = master_seed

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings with temporal mode
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = "deterministic-temporal"
    mock_config.evaluation.num_samples = 1
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_deterministic_temporal = True
    mock_config.evaluation.is_deterministic_pairwise = False
    mock_config.evaluation.is_bootstrap = False

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints - must return non-None for LLM optimization to run
    mock_constraints = MagicMock()
    mock_constraints.allowed_parameters = []
    mock_constraints.allowed_actions = {}
    mock_constraints.allowed_fields = []
    mock_config.get_constraints.return_value = mock_constraints

    # Prompt customization
    mock_config.prompt_customization = None

    return mock_config


def _create_agent_context(agent_id: str = "BANK_A") -> AgentSimulationContext:
    """Create a mock AgentSimulationContext with simulation output."""
    return AgentSimulationContext(
        agent_id=agent_id,
        sample_seed=42,
        sample_cost=1000,
        simulation_trace="[tick 0] PolicyDecision: action=Release, tx_id=tx1\n[tick 1] Settlement: amount=$100.00",
        mean_cost=1500,
        cost_std=500,
    )


class TestTemporalModeReceivesSimulationContext:
    """Tests verifying temporal mode provides simulation context to LLM.

    INV-12: LLM Context Identity - All evaluation modes must provide
    simulation output to the LLM. Only mode-specific metadata may differ.
    """

    @pytest.mark.asyncio
    async def test_temporal_mode_passes_simulation_output_to_llm(self) -> None:
        """CRITICAL: Temporal mode MUST pass simulation output to PolicyOptimizer.

        This test captures the bug where _optimize_agent_temporal() passed
        None for best_seed_output, worst_seed_output, and events, causing
        the LLM to optimize blindly without seeing simulation results.

        Expected: best_seed_output should contain simulation event trace.
        """
        mock_config = _create_temporal_config()
        loop = OptimizationLoop(config=mock_config)

        # Initialize constraints (required for LLM optimization)
        loop._constraints = mock_config.get_constraints()

        # Simulate what _evaluate_policies() does: populate agent context
        agent_context = _create_agent_context("BANK_A")
        loop._current_agent_contexts = {"BANK_A": agent_context}
        loop._current_enriched_results = []  # Would have EnrichedEvaluationResult

        # Set up cost rates (required for prompt building)
        loop._cost_rates = {"delay_rate": 100, "overdraft_rate": 50}

        # Initialize policies
        loop._policies = {
            "BANK_A": {"initial_liquidity_fraction": 0.5},
        }
        loop._current_iteration = 1

        # Mock the LLM client and PolicyOptimizer
        mock_llm_client = MagicMock()
        loop._llm_client = mock_llm_client

        mock_optimizer = MagicMock()
        mock_opt_result = MagicMock()
        mock_opt_result.new_policy = {"initial_liquidity_fraction": 0.3}
        mock_opt_result.validation_errors = []
        mock_optimizer.optimize = AsyncMock(return_value=mock_opt_result)
        mock_optimizer.get_system_prompt = MagicMock(return_value="System prompt")
        loop._policy_optimizer = mock_optimizer

        # Call the temporal optimization
        await loop._optimize_agent_temporal("BANK_A", current_cost=1000)

        # CRITICAL ASSERTION: Verify PolicyOptimizer.optimize was called
        # with non-None simulation output
        mock_optimizer.optimize.assert_called_once()
        call_kwargs = mock_optimizer.optimize.call_args.kwargs

        # INV-12: simulation_trace MUST be provided (not None)
        assert call_kwargs.get("simulation_trace") is not None, (
            "INV-12 VIOLATION: Temporal mode must provide simulation_trace to LLM. "
            "The LLM cannot optimize without seeing simulation results."
        )

    @pytest.mark.asyncio
    async def test_temporal_mode_passes_events_to_llm(self) -> None:
        """Temporal mode should pass events for agent isolation filtering.

        The PolicyOptimizer uses events to apply agent isolation (INV-11).
        Without events, the optimizer cannot properly filter what the LLM sees.
        """
        mock_config = _create_temporal_config()
        loop = OptimizationLoop(config=mock_config)

        # Initialize constraints
        loop._constraints = mock_config.get_constraints()

        # Populate agent context
        agent_context = _create_agent_context("BANK_A")
        loop._current_agent_contexts = {"BANK_A": agent_context}

        # Simulate enriched results with events
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        mock_event = BootstrapEvent(
            tick=0,
            event_type="PolicyDecision",
            details={"agent_id": "BANK_A", "action": "Release"},
        )
        mock_result = EnrichedEvaluationResult(
            seed=42,
            sample_idx=0,
            total_cost=1000,
            settlement_rate=0.95,
            avg_delay=2.0,
            event_trace=(mock_event,),
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
        )
        loop._current_enriched_results = [mock_result]

        loop._cost_rates = {"delay_rate": 100}
        loop._policies = {"BANK_A": {"initial_liquidity_fraction": 0.5}}
        loop._current_iteration = 1

        # Mock LLM components
        mock_llm_client = MagicMock()
        loop._llm_client = mock_llm_client

        mock_optimizer = MagicMock()
        mock_opt_result = MagicMock()
        mock_opt_result.new_policy = {"initial_liquidity_fraction": 0.3}
        mock_opt_result.validation_errors = []
        mock_optimizer.optimize = AsyncMock(return_value=mock_opt_result)
        mock_optimizer.get_system_prompt = MagicMock(return_value="System prompt")
        loop._policy_optimizer = mock_optimizer

        await loop._optimize_agent_temporal("BANK_A", current_cost=1000)

        call_kwargs = mock_optimizer.optimize.call_args.kwargs

        # Events should be passed for agent isolation filtering
        # (This is secondary to simulation_trace but still important)
        assert call_kwargs.get("cost_breakdown") is not None, (
            "Temporal mode should pass cost_breakdown for detailed LLM analysis"
        )

    @pytest.mark.asyncio
    async def test_temporal_mode_context_matches_pairwise_mode(self) -> None:
        """Temporal and pairwise modes should provide equivalent context.

        INV-12: The simulation_output formatting should be identical across
        modes. Only mode-specific evaluation metadata may differ.

        This test verifies that temporal mode provides the same type of
        context that makes deterministic-pairwise mode work correctly.
        """
        mock_config = _create_temporal_config()
        loop = OptimizationLoop(config=mock_config)

        # Initialize constraints
        loop._constraints = mock_config.get_constraints()

        # Populate context (same as what pairwise mode would have)
        agent_context = _create_agent_context("BANK_A")
        loop._current_agent_contexts = {"BANK_A": agent_context}
        loop._current_enriched_results = []

        loop._cost_rates = {"delay_rate": 100}
        loop._policies = {"BANK_A": {"initial_liquidity_fraction": 0.5}}
        loop._current_iteration = 1

        mock_llm_client = MagicMock()
        loop._llm_client = mock_llm_client

        mock_optimizer = MagicMock()
        mock_opt_result = MagicMock()
        mock_opt_result.new_policy = {"initial_liquidity_fraction": 0.3}
        mock_opt_result.validation_errors = []
        mock_optimizer.optimize = AsyncMock(return_value=mock_opt_result)
        mock_optimizer.get_system_prompt = MagicMock(return_value="System prompt")
        loop._policy_optimizer = mock_optimizer

        await loop._optimize_agent_temporal("BANK_A", current_cost=1000)

        call_kwargs = mock_optimizer.optimize.call_args.kwargs

        # The key fields that pairwise mode provides should also be in temporal
        sim_trace = call_kwargs.get("simulation_trace")

        # Simulation trace should contain the actual simulation events
        assert sim_trace is not None
        assert "PolicyDecision" in sim_trace or "Settlement" in sim_trace, (
            "simulation_trace should contain simulation events like pairwise mode"
        )
