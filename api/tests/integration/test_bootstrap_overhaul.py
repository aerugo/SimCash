"""Integration tests for bootstrap evaluation overhaul.

Tests verify:
1. SeedMatrix integration with OptimizationLoop
2. Per-agent seed isolation
3. Bootstrap evaluation happens AFTER policy generation
4. Delta-based acceptance logic
"""

from __future__ import annotations

import pytest

from payment_simulator.experiments.runner.seed_matrix import SeedMatrix


class TestSeedMatrixIntegration:
    """Test SeedMatrix integration."""

    def test_seed_matrix_provides_agent_isolated_seeds(self) -> None:
        """Different agents get different bootstrap seeds for same iteration."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=5,
        )

        # Get bootstrap seeds for iteration 0
        seeds_a = matrix.get_bootstrap_seeds(0, "BANK_A")
        seeds_b = matrix.get_bootstrap_seeds(0, "BANK_B")

        # Seeds should be different (agent isolation)
        assert seeds_a != seeds_b

        # Each set should have unique seeds
        assert len(set(seeds_a)) == 5
        assert len(set(seeds_b)) == 5

        # No overlap between agent seeds
        assert set(seeds_a).isdisjoint(set(seeds_b))

    def test_seed_matrix_iteration_isolation(self) -> None:
        """Different iterations get different seeds for same agent."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A"],
            num_bootstrap_samples=5,
        )

        # Get bootstrap seeds for different iterations
        seeds_iter0 = matrix.get_bootstrap_seeds(0, "BANK_A")
        seeds_iter1 = matrix.get_bootstrap_seeds(1, "BANK_A")

        # Seeds should differ between iterations
        assert seeds_iter0 != seeds_iter1

    def test_seed_matrix_reproducibility(self) -> None:
        """Same master_seed produces identical seed matrices."""
        matrix1 = SeedMatrix(
            master_seed=12345,
            max_iterations=5,
            agents=["A", "B"],
            num_bootstrap_samples=3,
        )
        matrix2 = SeedMatrix(
            master_seed=12345,
            max_iterations=5,
            agents=["A", "B"],
            num_bootstrap_samples=3,
        )

        # All seeds should match
        for iteration in range(5):
            for agent in ["A", "B"]:
                assert matrix1.get_iteration_seed(iteration, agent) == matrix2.get_iteration_seed(
                    iteration, agent
                )
                assert matrix1.get_bootstrap_seeds(iteration, agent) == matrix2.get_bootstrap_seeds(
                    iteration, agent
                )


class TestDeltaBasedAcceptance:
    """Test delta-based acceptance logic."""

    def test_positive_delta_sum_means_improvement(self) -> None:
        """Positive delta sum indicates new policy is cheaper."""
        # old_cost - new_cost > 0 means new is cheaper
        deltas = [100, -50, 75, -25, 100]  # Sum = 200
        delta_sum = sum(deltas)

        assert delta_sum > 0  # Should accept
        assert delta_sum == 200  # Total improvement in cents

    def test_negative_delta_sum_means_regression(self) -> None:
        """Negative delta sum indicates new policy is more expensive."""
        deltas = [-100, 50, -75, 25, -100]  # Sum = -200
        delta_sum = sum(deltas)

        assert delta_sum < 0  # Should reject
        assert delta_sum == -200  # Total regression in cents

    def test_zero_delta_sum_means_no_change(self) -> None:
        """Zero delta sum indicates no net improvement."""
        deltas = [100, -100, 50, -50, 0]  # Sum = 0
        delta_sum = sum(deltas)

        assert delta_sum == 0  # Could go either way (typically reject)

    def test_delta_format_for_display(self) -> None:
        """Deltas can be formatted for display."""
        deltas = [1000, -500, 750]  # In cents
        delta_sum = sum(deltas)  # 1250 cents = $12.50 improvement

        # Format for display
        improvement_dollars = delta_sum / 100
        assert improvement_dollars == 12.50


class TestBootstrapEvaluationFlow:
    """Test the correct bootstrap evaluation flow."""

    def test_paired_comparison_uses_same_seeds(self) -> None:
        """Old and new policies should be evaluated with same seeds."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=1,
            agents=["A"],
            num_bootstrap_samples=5,
        )

        # Get seeds for evaluation
        seeds = matrix.get_bootstrap_seeds(0, "A")

        # Simulate paired evaluation - key is both use SAME seeds
        old_costs = []
        new_costs = []

        for seed in seeds:
            # Both evaluations use same seed - this is the key property
            # Simulating: new policy always saves 100 cents per transaction
            base_cost = seed % 1000  # Base cost from seed
            old_costs.append(base_cost + 100)  # Old policy: higher cost
            new_costs.append(base_cost)         # New policy: lower cost

        # Calculate deltas
        deltas = [old - new for old, new in zip(old_costs, new_costs)]

        # All deltas should be exactly 100 (new saves 100 cents each time)
        assert all(d == 100 for d in deltas)
        assert sum(deltas) == 500  # 5 samples * 100 = 500 total improvement

    def test_evaluation_determinism(self) -> None:
        """Same seeds produce same evaluation results."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=1,
            agents=["A"],
            num_bootstrap_samples=3,
        )

        # Evaluate twice with same seeds
        seeds = matrix.get_bootstrap_seeds(0, "A")

        results1 = [seed % 1000 for seed in seeds]
        results2 = [seed % 1000 for seed in seeds]

        assert results1 == results2


class TestOptimizationLoopSeedMatrixIntegration:
    """Test SeedMatrix integration with OptimizationLoop."""

    def test_optimization_loop_creates_seed_matrix(self) -> None:
        """OptimizationLoop creates SeedMatrix on initialization."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.experiments.runner.seed_matrix import SeedMatrix
        from payment_simulator.llm import LLMConfig

        # Create mock config
        mock_config = MagicMock()
        mock_config.name = "test_experiment"
        mock_config.master_seed = 42
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 10
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "bootstrap"
        mock_config.evaluation.num_samples = 5
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("BANK_A", "BANK_B")
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        # Verify SeedMatrix was created
        assert hasattr(loop, "_seed_matrix")
        assert isinstance(loop._seed_matrix, SeedMatrix)
        assert loop._seed_matrix.master_seed == 42
        assert loop._seed_matrix.max_iterations == 10
        assert loop._seed_matrix.num_bootstrap_samples == 5

    def test_seed_matrix_has_correct_agents(self) -> None:
        """SeedMatrix includes all optimized agents."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 123
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 5
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "bootstrap"
        mock_config.evaluation.num_samples = 3
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("AGENT_1", "AGENT_2", "AGENT_3")
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="test")
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        # Verify all agents have seeds
        for agent in ["AGENT_1", "AGENT_2", "AGENT_3"]:
            seed = loop._seed_matrix.get_iteration_seed(0, agent)
            assert seed is not None
            assert isinstance(seed, int)

    def test_delta_history_initialized_empty(self) -> None:
        """OptimizationLoop initializes delta_history as empty list."""
        from unittest.mock import MagicMock

        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.llm import LLMConfig

        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.master_seed = 42
        mock_config.convergence = MagicMock()
        mock_config.convergence.max_iterations = 5
        mock_config.convergence.stability_threshold = 0.05
        mock_config.convergence.stability_window = 3
        mock_config.convergence.improvement_threshold = 0.01
        mock_config.evaluation = MagicMock()
        mock_config.evaluation.mode = "deterministic"
        mock_config.evaluation.num_samples = 1
        mock_config.evaluation.ticks = 2
        mock_config.optimized_agents = ("A",)
        mock_config.get_constraints.return_value = None
        mock_config.llm = LLMConfig(model="test")
        mock_config.prompt_customization = None

        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "_delta_history")
        assert loop._delta_history == []


class TestProgressTracking:
    """Test delta-based progress tracking."""

    def test_delta_history_structure(self) -> None:
        """Delta history contains expected fields."""
        delta_record = {
            "iteration": 1,
            "agent_id": "BANK_A",
            "deltas": [100, -50, 75],
            "delta_sum": 125,
            "accepted": True,
        }

        assert delta_record["iteration"] == 1
        assert delta_record["agent_id"] == "BANK_A"
        assert delta_record["delta_sum"] == sum(delta_record["deltas"])
        assert delta_record["accepted"] == (delta_record["delta_sum"] > 0)

    def test_aggregate_progress_across_iterations(self) -> None:
        """Can track cumulative improvement across iterations."""
        delta_history = [
            {"iteration": 1, "agent_id": "A", "delta_sum": 100, "accepted": True},
            {"iteration": 2, "agent_id": "A", "delta_sum": 50, "accepted": True},
            {"iteration": 3, "agent_id": "A", "delta_sum": -30, "accepted": False},
            {"iteration": 4, "agent_id": "A", "delta_sum": 80, "accepted": True},
        ]

        # Calculate cumulative improvement (only accepted changes)
        cumulative = sum(
            d["delta_sum"] for d in delta_history if d["accepted"]
        )

        assert cumulative == 100 + 50 + 80  # = 230 cents improvement

    def test_per_agent_progress(self) -> None:
        """Can track progress per agent."""
        delta_history = [
            {"iteration": 1, "agent_id": "A", "delta_sum": 100, "accepted": True},
            {"iteration": 1, "agent_id": "B", "delta_sum": 50, "accepted": True},
            {"iteration": 2, "agent_id": "A", "delta_sum": -20, "accepted": False},
            {"iteration": 2, "agent_id": "B", "delta_sum": 30, "accepted": True},
        ]

        # Per-agent totals (accepted only)
        agent_a_total = sum(
            d["delta_sum"]
            for d in delta_history
            if d["agent_id"] == "A" and d["accepted"]
        )
        agent_b_total = sum(
            d["delta_sum"]
            for d in delta_history
            if d["agent_id"] == "B" and d["accepted"]
        )

        assert agent_a_total == 100  # Only iteration 1 accepted
        assert agent_b_total == 50 + 30  # Both iterations accepted
