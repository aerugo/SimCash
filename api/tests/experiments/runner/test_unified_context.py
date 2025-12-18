"""Tests for unified LLM context across all evaluation modes (INV-12).

CRITICAL INVARIANT (INV-12): LLM Context Identity
All evaluation modes must provide identical simulation output formatting.
Only mode-specific evaluation metadata may differ.

This test file verifies that bootstrap, deterministic-pairwise, and
deterministic-temporal modes all produce the same context format.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
    AgentSimulationContext,
)
from payment_simulator.experiments.runner.bootstrap_support import BootstrapLLMContext
from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_config(mode: str, master_seed: int = 42) -> MagicMock:
    """Create a mock ExperimentConfig for testing."""
    mock_config = MagicMock()
    mock_config.name = f"test_{mode}"
    mock_config.master_seed = master_seed

    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = 10
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = mode
    mock_config.evaluation.num_samples = 50 if mode == "bootstrap" else 1
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_deterministic_temporal = mode == "deterministic-temporal"
    mock_config.evaluation.is_deterministic_pairwise = mode in ("deterministic", "deterministic-pairwise")
    mock_config.evaluation.is_bootstrap = mode == "bootstrap"

    mock_config.optimized_agents = ("BANK_A",)
    mock_config.llm = LLMConfig(model="test:mock")

    mock_constraints = MagicMock()
    mock_constraints.allowed_parameters = []
    mock_constraints.allowed_actions = {}
    mock_constraints.allowed_fields = []
    mock_config.get_constraints.return_value = mock_constraints

    mock_config.prompt_customization = None

    return mock_config


def _create_agent_context(agent_id: str = "BANK_A") -> AgentSimulationContext:
    """Create AgentSimulationContext with simulation output."""
    return AgentSimulationContext(
        agent_id=agent_id,
        best_seed=42,
        best_seed_cost=1000,
        best_seed_output="[tick 0] PolicyDecision: action=Release\n[tick 1] Settlement: amount=$100.00",
        worst_seed=99,
        worst_seed_cost=2000,
        worst_seed_output="[tick 0] PolicyDecision: action=Hold\n[tick 1] DelayCost: cost=$50.00",
        mean_cost=1500,
        cost_std=500,
    )


def _create_bootstrap_llm_context(agent_id: str = "BANK_A") -> BootstrapLLMContext:
    """Create BootstrapLLMContext with initial simulation output."""
    return BootstrapLLMContext(
        agent_id=agent_id,
        # Stream 1: Initial simulation (should be ignored after simplification)
        initial_simulation_output="[tick 0] Arrival: tx_id=tx1\n[tick 1] Settlement: amount=$200.00",
        initial_simulation_cost=1200,
        # Stream 2: Best sample
        best_seed=42,
        best_seed_cost=1000,
        best_seed_output="[tick 0] PolicyDecision: action=Release\n[tick 1] Settlement: amount=$100.00",
        # Stream 3: Worst sample
        worst_seed=99,
        worst_seed_cost=2000,
        worst_seed_output="[tick 0] PolicyDecision: action=Hold\n[tick 1] DelayCost: cost=$50.00",
        # Statistics
        mean_cost=1500,
        cost_std=500,
        num_samples=50,
    )


class TestUnifiedContextAcrossModes:
    """Tests verifying all modes produce identical context format (INV-12)."""

    @pytest.mark.asyncio
    async def test_bootstrap_mode_does_not_include_initial_simulation_header(self) -> None:
        """Bootstrap mode should NOT include 'INITIAL SIMULATION' section.

        INV-12 requires identical context across modes. The initial simulation
        is stale after iteration 1 and creates inconsistency with deterministic modes.
        Bootstrap should just show best_seed_output like deterministic modes.
        """
        mock_config = _create_config("bootstrap")
        loop = OptimizationLoop(config=mock_config)

        loop._constraints = mock_config.get_constraints()

        # Set up agent context (from bootstrap samples)
        agent_context = _create_agent_context("BANK_A")
        loop._current_agent_contexts = {"BANK_A": agent_context}
        loop._current_enriched_results = []

        # Set up bootstrap LLM context (initial simulation - should be ignored)
        bootstrap_llm_context = _create_bootstrap_llm_context("BANK_A")
        loop._bootstrap_llm_contexts = {"BANK_A": bootstrap_llm_context}

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

        # Call the optimization (bootstrap uses _optimize_agent)
        await loop._optimize_agent("BANK_A", current_cost=1000)

        call_kwargs = mock_optimizer.optimize.call_args.kwargs
        best_output = call_kwargs.get("best_seed_output")

        # INV-12: Should NOT contain initial simulation header
        assert best_output is not None
        assert "INITIAL SIMULATION" not in best_output, (
            "INV-12 VIOLATION: Bootstrap mode should not include 'INITIAL SIMULATION' section. "
            "All modes should show only best_seed_output for consistency."
        )
        assert "BEST BOOTSTRAP SAMPLE" not in best_output, (
            "INV-12 VIOLATION: Bootstrap mode should not include 'BEST BOOTSTRAP SAMPLE' header. "
            "Just show the events directly like deterministic modes."
        )

    @pytest.mark.asyncio
    async def test_all_modes_produce_same_output_format(self) -> None:
        """All three modes should produce identical best_seed_output format.

        INV-12: The simulation output formatting should be identical across modes.
        """
        modes = ["bootstrap", "deterministic-pairwise", "deterministic-temporal"]
        outputs: dict[str, str | None] = {}

        for mode in modes:
            mock_config = _create_config(mode)
            loop = OptimizationLoop(config=mock_config)

            loop._constraints = mock_config.get_constraints()

            # Same agent context for all modes
            agent_context = _create_agent_context("BANK_A")
            loop._current_agent_contexts = {"BANK_A": agent_context}
            loop._current_enriched_results = []

            # Bootstrap has extra context that should be ignored
            if mode == "bootstrap":
                bootstrap_llm_context = _create_bootstrap_llm_context("BANK_A")
                loop._bootstrap_llm_contexts = {"BANK_A": bootstrap_llm_context}

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

            # Call appropriate optimization method
            if mode == "deterministic-temporal":
                await loop._optimize_agent_temporal("BANK_A", current_cost=1000)
            else:
                await loop._optimize_agent("BANK_A", current_cost=1000)

            call_kwargs = mock_optimizer.optimize.call_args.kwargs
            outputs[mode] = call_kwargs.get("best_seed_output")

        # All outputs should be identical
        bootstrap_output = outputs["bootstrap"]
        pairwise_output = outputs["deterministic-pairwise"]
        temporal_output = outputs["deterministic-temporal"]

        assert bootstrap_output == pairwise_output, (
            f"INV-12 VIOLATION: Bootstrap and pairwise outputs differ.\n"
            f"Bootstrap: {bootstrap_output}\n"
            f"Pairwise: {pairwise_output}"
        )
        assert pairwise_output == temporal_output, (
            f"INV-12 VIOLATION: Pairwise and temporal outputs differ.\n"
            f"Pairwise: {pairwise_output}\n"
            f"Temporal: {temporal_output}"
        )
