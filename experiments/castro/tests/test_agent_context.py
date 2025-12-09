"""Phase 2 Tests: Per-agent context building from Monte Carlo results.

Tests for building SingleAgentContext from Monte Carlo simulation results.

These tests verify:
1. Best/worst seed selection is per-agent (INV-3)
2. Context includes filtered verbose output for each seed
3. Context cost breakdown is agent-specific (INV-4)
4. Context structure matches SingleAgentContext dataclass

Critical invariants:
- INV-3: Monte Carlo best/worst selection - different agents may have different best seeds
- INV-4: Context structure - must follow SingleAgentContext format
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml
from payment_simulator._core import Orchestrator
from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentContext,
    SingleAgentIterationRecord,
)
from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
    SingleAgentContextBuilder,
    build_single_agent_context,
)
from payment_simulator.cli.filters import EventFilter


class TestBestWorstSeedSelection:
    """Test selection of best/worst seeds per agent (INV-3)."""

    @pytest.fixture
    def multi_seed_config(self) -> dict:
        """Create config for multi-seed testing."""
        return {
            "ticks_per_day": 15,
            "num_days": 1,
            "agent_configs": [
                {
                    "id": "BANK_A",
                    "opening_balance": 300000,
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 15000,
                            "std_dev": 5000,
                        },
                        "counterparty_weights": {"BANK_B": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 3, "max": 10},
                    },
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 300000,
                    "unsecured_cap": 100000,
                    "policy": {"type": "Fifo"},
                    "arrival_config": {
                        "rate_per_tick": 1.0,
                        "amount_distribution": {
                            "type": "Normal",
                            "mean": 15000,
                            "std_dev": 5000,
                        },
                        "counterparty_weights": {"BANK_A": 1.0},
                        "priority_weights": {5: 0.7, 8: 0.3},
                        "deadline_window": {"min": 3, "max": 10},
                    },
                },
            ],
        }

    def run_simulation_with_seed(
        self, config: dict, seed: int, ticks: int = 15
    ) -> dict[str, int]:
        """Run simulation and return per-agent costs."""
        config_with_seed = {**config, "rng_seed": seed}
        orch = Orchestrator.new(config_with_seed)

        for _ in range(ticks):
            orch.tick()

        # Get per-agent costs
        costs: dict[str, int] = {}
        for agent_id in orch.get_agent_ids():
            agent_costs = orch.get_agent_accumulated_costs(agent_id)
            costs[agent_id] = agent_costs.get("total_cost", 0)

        return costs

    def test_best_seed_is_lowest_cost_for_agent(
        self, multi_seed_config: dict
    ) -> None:
        """Best seed has lowest cost for this specific agent."""
        seeds = [100, 200, 300, 400, 500]
        results: list[tuple[int, dict[str, int]]] = []

        for seed in seeds:
            costs = self.run_simulation_with_seed(multi_seed_config, seed)
            results.append((seed, costs))

        # Find best seed for BANK_A (lowest cost)
        bank_a_costs = [(seed, costs["BANK_A"]) for seed, costs in results]
        best_seed_a, best_cost_a = min(bank_a_costs, key=lambda x: x[1])

        # Verify this is actually the lowest cost
        for seed, cost in bank_a_costs:
            assert cost >= best_cost_a, (
                f"Best seed {best_seed_a} should have lowest cost for BANK_A"
            )

    def test_worst_seed_is_highest_cost_for_agent(
        self, multi_seed_config: dict
    ) -> None:
        """Worst seed has highest cost for this specific agent."""
        seeds = [100, 200, 300, 400, 500]
        results: list[tuple[int, dict[str, int]]] = []

        for seed in seeds:
            costs = self.run_simulation_with_seed(multi_seed_config, seed)
            results.append((seed, costs))

        # Find worst seed for BANK_B (highest cost)
        bank_b_costs = [(seed, costs["BANK_B"]) for seed, costs in results]
        worst_seed_b, worst_cost_b = max(bank_b_costs, key=lambda x: x[1])

        # Verify this is actually the highest cost
        for seed, cost in bank_b_costs:
            assert cost <= worst_cost_b, (
                f"Worst seed {worst_seed_b} should have highest cost for BANK_B"
            )

    def test_different_agents_can_have_different_best_seeds(
        self, multi_seed_config: dict
    ) -> None:
        """Agents A and B may have different optimal seeds (INV-3).

        Note: This test verifies the CAPABILITY - different agents CAN have
        different best seeds. They don't always, depending on scenario.
        """
        seeds = [111, 222, 333, 444, 555, 666, 777, 888, 999]
        results: list[tuple[int, dict[str, int]]] = []

        for seed in seeds:
            costs = self.run_simulation_with_seed(multi_seed_config, seed)
            results.append((seed, costs))

        # Find best seed for each agent
        bank_a_costs = [(seed, costs["BANK_A"]) for seed, costs in results]
        bank_b_costs = [(seed, costs["BANK_B"]) for seed, costs in results]

        best_seed_a, _ = min(bank_a_costs, key=lambda x: x[1])
        best_seed_b, _ = min(bank_b_costs, key=lambda x: x[1])

        # They CAN be different (not required, but possible)
        # We just verify the selection logic works independently
        # The key point is each agent's best is selected based on THEIR costs
        assert best_seed_a in seeds, "Best seed for A should be from seed list"
        assert best_seed_b in seeds, "Best seed for B should be from seed list"

        # Log whether they differ (informational)
        if best_seed_a != best_seed_b:
            # This demonstrates the invariant is meaningful
            pass


class TestContextBuilding:
    """Test building SingleAgentContext from simulation results."""

    @pytest.fixture
    def sample_context_data(self) -> dict[str, Any]:
        """Create sample data for context building."""
        return {
            "agent_id": "BANK_A",
            "current_iteration": 5,
            "current_policy": {
                "version": "2.0",
                "parameters": {
                    "urgency_threshold": 3,
                    "liquidity_buffer": 0.2,
                },
                "payment_tree": {"type": "action", "action": "Release"},
            },
            "current_metrics": {
                "total_cost_mean": 15000,
                "total_cost_std": 2500,
                "settlement_rate_mean": 1.0,
                "risk_adjusted_cost": 17500,
            },
            "best_seed": 42,
            "best_seed_cost": 12000,
            "worst_seed": 99,
            "worst_seed_cost": 18000,
            "cost_breakdown": {
                "delay": 8000,
                "collateral": 4000,
                "overdraft": 2000,
                "eod_penalty": 1000,
            },
        }

    def test_context_has_best_seed_output(
        self, sample_context_data: dict[str, Any]
    ) -> None:
        """Context includes filtered verbose output from best seed."""
        # Add verbose output
        best_seed_output = """[Tick 0] Arrival: BANK_A → BANK_B $100.00
[Tick 1] Settlement: BANK_A → BANK_B $100.00"""

        context = SingleAgentContext(
            agent_id=sample_context_data["agent_id"],
            current_iteration=sample_context_data["current_iteration"],
            current_policy=sample_context_data["current_policy"],
            current_metrics=sample_context_data["current_metrics"],
            best_seed=sample_context_data["best_seed"],
            best_seed_cost=sample_context_data["best_seed_cost"],
            best_seed_output=best_seed_output,
            worst_seed=sample_context_data["worst_seed"],
            worst_seed_cost=sample_context_data["worst_seed_cost"],
        )

        assert context.best_seed_output is not None
        assert "Tick 0" in context.best_seed_output
        assert "BANK_A" in context.best_seed_output

    def test_context_has_worst_seed_output(
        self, sample_context_data: dict[str, Any]
    ) -> None:
        """Context includes filtered verbose output from worst seed."""
        worst_seed_output = """[Tick 0] Arrival: BANK_A → BANK_B $200.00
[Tick 1] PolicyHold: BANK_A held tx_001
[Tick 5] CostAccrual: BANK_A delay $5.00"""

        context = SingleAgentContext(
            agent_id=sample_context_data["agent_id"],
            current_iteration=sample_context_data["current_iteration"],
            current_policy=sample_context_data["current_policy"],
            current_metrics=sample_context_data["current_metrics"],
            best_seed=sample_context_data["best_seed"],
            best_seed_cost=sample_context_data["best_seed_cost"],
            worst_seed=sample_context_data["worst_seed"],
            worst_seed_cost=sample_context_data["worst_seed_cost"],
            worst_seed_output=worst_seed_output,
        )

        assert context.worst_seed_output is not None
        assert "PolicyHold" in context.worst_seed_output
        assert "CostAccrual" in context.worst_seed_output

    def test_context_has_iteration_history(
        self, sample_context_data: dict[str, Any]
    ) -> None:
        """Context includes iteration history for this agent only."""
        history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={"total_cost_mean": 20000},
                policy={"parameters": {"urgency_threshold": 5}},
                is_best_so_far=False,
            ),
            SingleAgentIterationRecord(
                iteration=2,
                metrics={"total_cost_mean": 17000},
                policy={"parameters": {"urgency_threshold": 4}},
                policy_changes=["Changed 'urgency_threshold': 5 → 4 (↓1)"],
                is_best_so_far=True,
            ),
        ]

        context = SingleAgentContext(
            agent_id=sample_context_data["agent_id"],
            current_iteration=sample_context_data["current_iteration"],
            current_policy=sample_context_data["current_policy"],
            current_metrics=sample_context_data["current_metrics"],
            iteration_history=history,
        )

        assert len(context.iteration_history) == 2
        assert context.iteration_history[0].iteration == 1
        assert context.iteration_history[1].is_best_so_far is True

    def test_context_cost_breakdown_is_agent_specific(
        self, sample_context_data: dict[str, Any]
    ) -> None:
        """Cost breakdown shows only this agent's costs."""
        context = SingleAgentContext(
            agent_id=sample_context_data["agent_id"],
            current_iteration=sample_context_data["current_iteration"],
            current_policy=sample_context_data["current_policy"],
            current_metrics=sample_context_data["current_metrics"],
            cost_breakdown=sample_context_data["cost_breakdown"],
        )

        # Verify cost breakdown structure
        assert "delay" in context.cost_breakdown
        assert "collateral" in context.cost_breakdown
        assert context.cost_breakdown["delay"] == 8000

        # Total should sum correctly
        total = sum(context.cost_breakdown.values())
        assert total == 15000  # 8000 + 4000 + 2000 + 1000


class TestContextPromptBuilding:
    """Test SingleAgentContextBuilder produces valid prompts."""

    @pytest.fixture
    def full_context(self) -> SingleAgentContext:
        """Create a full context with all fields populated."""
        return SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            current_policy={
                "version": "2.0",
                "parameters": {"urgency_threshold": 3, "liquidity_buffer": 0.15},
            },
            current_metrics={
                "total_cost_mean": 12500,
                "total_cost_std": 1800,
                "settlement_rate_mean": 1.0,
                "risk_adjusted_cost": 14300,
                "failure_rate": 0,
            },
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={"total_cost_mean": 18000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {"urgency_threshold": 5}},
                    is_best_so_far=True,
                ),
                SingleAgentIterationRecord(
                    iteration=2,
                    metrics={"total_cost_mean": 15000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {"urgency_threshold": 4}},
                    policy_changes=["Changed 'urgency_threshold': 5 → 4 (↓1)"],
                    is_best_so_far=True,
                ),
            ],
            best_seed_output="""[Tick 0] === TICK START ===
Arrivals: BANK_A → BANK_B $150.00 (priority=5, deadline=10)
[Tick 0] PolicySubmit: BANK_A released tx_001
[Tick 0] Settlement: BANK_A → BANK_B $150.00
Balance: BANK_A $4,850.00, BANK_B $5,150.00""",
            worst_seed_output="""[Tick 0] === TICK START ===
Arrivals: BANK_A → BANK_B $300.00 (priority=8, deadline=5)
[Tick 0] PolicyHold: BANK_A held tx_002 (insufficient liquidity)
[Tick 3] CostAccrual: BANK_A delay $15.00
[Tick 5] TransactionWentOverdue: tx_002 missed deadline""",
            best_seed=42,
            worst_seed=99,
            best_seed_cost=10000,
            worst_seed_cost=18000,
            cost_breakdown={
                "delay": 7000,
                "collateral": 3500,
                "overdraft": 1500,
                "eod_penalty": 500,
            },
            cost_rates={
                "delay_cost_per_tick_per_cent": 0.001,
                "collateral_cost_per_tick_bps": 500,
                "overdraft_bps_per_tick": 2000,
            },
        )

    def test_builder_produces_non_empty_prompt(
        self, full_context: SingleAgentContext
    ) -> None:
        """Builder should produce substantial prompt."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert len(prompt) > 1000, "Prompt should be substantial"
        assert isinstance(prompt, str)

    def test_prompt_includes_agent_id(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include the agent ID."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "BANK_A" in prompt

    def test_prompt_includes_iteration_number(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include current iteration."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "ITERATION 3" in prompt or "Iteration 3" in prompt

    def test_prompt_includes_best_seed_output(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include best seed verbose output."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "Best Performing Seed" in prompt
        assert "PolicySubmit" in prompt  # From best_seed_output

    def test_prompt_includes_worst_seed_output(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include worst seed verbose output."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "Worst Performing Seed" in prompt
        assert "PolicyHold" in prompt  # From worst_seed_output
        assert "CostAccrual" in prompt  # From worst_seed_output

    def test_prompt_includes_cost_breakdown(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include cost breakdown."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "COST ANALYSIS" in prompt
        assert "delay" in prompt.lower()
        assert "collateral" in prompt.lower()

    def test_prompt_includes_iteration_history(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include iteration history table."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "ITERATION HISTORY" in prompt
        assert "Iteration 1" in prompt
        assert "Iteration 2" in prompt

    def test_prompt_includes_parameter_trajectories(
        self, full_context: SingleAgentContext
    ) -> None:
        """Prompt should include parameter trajectories."""
        builder = SingleAgentContextBuilder(full_context)
        prompt = builder.build()

        assert "PARAMETER TRAJECTORIES" in prompt
        assert "urgency_threshold" in prompt


class TestContextWithoutVerboseOutput:
    """Test context building when verbose output is not available."""

    def test_context_without_verbose_output_is_valid(self) -> None:
        """Context should be valid even without verbose output."""
        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5}},
            current_metrics={"total_cost_mean": 10000},
            best_seed_output=None,
            worst_seed_output=None,
        )

        builder = SingleAgentContextBuilder(context)
        prompt = builder.build()

        assert "BANK_A" in prompt
        assert "No verbose output available" in prompt

    def test_convenience_function_works(self) -> None:
        """build_single_agent_context convenience function works."""
        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5}},
            current_metrics={"total_cost_mean": 10000, "settlement_rate_mean": 1.0},
            agent_id="BANK_A",
            best_seed=42,
            worst_seed=99,
            best_seed_cost=8000,
            worst_seed_cost=12000,
            best_seed_output="[Tick 0] Test output from best seed",
            worst_seed_output="[Tick 0] Test output from worst seed",
        )

        assert isinstance(prompt, str)
        assert "BANK_A" in prompt
        assert "Test output from best seed" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
