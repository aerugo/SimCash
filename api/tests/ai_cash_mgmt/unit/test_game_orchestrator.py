"""Unit tests for GameOrchestrator - main game loop controller.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestGameOrchestratorCreation:
    """Test GameOrchestrator creation and initialization."""

    def test_orchestrator_creates_from_config(self) -> None:
        """GameOrchestrator should initialize from GameConfig."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount", "priority"],
            allowed_actions={"payment_tree": ["queue", "submit"]},
        )

        orchestrator = GameOrchestrator(
            config=config,
            constraints=constraints,
        )

        assert orchestrator.game_id == "test_game"
        assert orchestrator.master_seed == 42

    def test_orchestrator_creates_seed_manager(self) -> None:
        """GameOrchestrator should create SeedManager from master_seed."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=12345,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Seed manager should derive consistent seeds
        seed1 = orchestrator.seed_manager.sampling_seed(0, "BANK_A")
        seed2 = orchestrator.seed_manager.sampling_seed(0, "BANK_A")
        assert seed1 == seed2


class TestGameOrchestratorScheduling:
    """Test optimization scheduling logic."""

    def test_should_optimize_at_interval(self) -> None:
        """Should trigger optimization at configured tick intervals."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Should not optimize at tick 49
        assert not orchestrator.should_optimize_at_tick(49)

        # Should optimize at tick 50
        assert orchestrator.should_optimize_at_tick(50)

        # Should optimize at tick 100
        assert orchestrator.should_optimize_at_tick(100)

    def test_should_optimize_after_eod(self) -> None:
        """Should trigger optimization after end of day."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.AFTER_EOD,
                min_remaining_days=1,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Should optimize after end of day if remaining days >= 1
        assert orchestrator.should_optimize_after_eod(remaining_days=2)
        assert orchestrator.should_optimize_after_eod(remaining_days=1)
        assert not orchestrator.should_optimize_after_eod(remaining_days=0)


class TestGameOrchestratorOptimization:
    """Test optimization step execution."""

    @pytest.mark.asyncio
    async def test_run_optimization_step(self) -> None:
        """run_optimization_step should optimize all agents."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession
        from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import (
            OptimizationResult,
        )
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            HistoricalTransaction,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(num_samples=5),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue", "submit"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Mock the policy optimizer
        mock_optimizer = AsyncMock()
        mock_optimizer.optimize.return_value = OptimizationResult(
            agent_id="BANK_A",
            iteration=1,
            old_policy={"version": "1"},
            new_policy={"version": "2"},
            old_cost=1000.0,
            new_cost=800.0,
            was_accepted=True,
            validation_errors=[],
            llm_latency_seconds=1.5,
            tokens_used=500,
            llm_model="openai/gpt-5.1",
        )
        orchestrator._policy_optimizer = mock_optimizer

        # Mock the policy evaluator
        mock_evaluator = MagicMock()
        mock_evaluator.evaluate.return_value = EvaluationResult(
            agent_id="BANK_A",
            policy={"version": "2"},
            mean_cost=800.0,
            std_cost=50.0,
            min_cost=700.0,
            max_cost=900.0,
            sample_costs=[750.0, 800.0, 850.0],
            num_samples=3,
            settlement_rate=0.98,
        )
        orchestrator._policy_evaluator = mock_evaluator

        # Create a session with initial policy
        session = GameSession(config=config)
        session.set_policy("BANK_A", {"version": "1"})

        # Provide some historical transactions
        transactions = [
            HistoricalTransaction(
                tx_id="tx1",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                arrival_tick=10,
                deadline_tick=20,
                is_divisible=True,
            ),
        ]

        # Run optimization step
        results = await orchestrator.run_optimization_step(
            session=session,
            transactions=transactions,
            current_tick=50,
        )

        # Should have result for BANK_A
        assert len(results) == 1
        assert results[0].agent_id == "BANK_A"


class TestGameOrchestratorConvergence:
    """Test convergence detection integration."""

    def test_orchestrator_creates_convergence_detector(self) -> None:
        """Orchestrator should create ConvergenceDetector from config."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(
                stability_threshold=0.05,
                stability_window=3,
                max_iterations=50,
                improvement_threshold=0.01,
            ),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Convergence detector should be configured
        assert orchestrator.convergence_detector is not None

    def test_check_convergence_uses_detector(self) -> None:
        """check_convergence should use the ConvergenceDetector."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(
                stability_threshold=0.05,
                stability_window=3,
                max_iterations=50,
                improvement_threshold=0.01,
            ),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator = GameOrchestrator(config=config, constraints=constraints)

        # Record some metrics
        orchestrator.record_iteration_metric(1000.0)
        orchestrator.record_iteration_metric(990.0)
        orchestrator.record_iteration_metric(985.0)

        # Check convergence
        result = orchestrator.check_convergence()
        assert result is not None
        assert "is_converged" in result


class TestGameOrchestratorDeterminism:
    """Test determinism guarantees."""

    def test_same_seed_produces_same_sampling_seeds(self) -> None:
        """Same master_seed should produce identical sampling seeds."""
        from payment_simulator.ai_cash_mgmt.config.game_config import (
            ConvergenceCriteria,
            GameConfig,
            BootstrapConfig,
            OptimizationSchedule,
            OptimizationScheduleType,
        )
        from payment_simulator.ai_cash_mgmt.config.llm_config import (
            AgentOptimizationConfig,
        )
        from payment_simulator.ai_cash_mgmt.constraints.scenario_constraints import (
            ScenarioConstraints,
        )
        from payment_simulator.ai_cash_mgmt.core.game_orchestrator import (
            GameOrchestrator,
        )

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={"BANK_A": AgentOptimizationConfig()},
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["amount"],
            allowed_actions={"payment_tree": ["queue"]},
        )

        orchestrator1 = GameOrchestrator(config=config, constraints=constraints)
        orchestrator2 = GameOrchestrator(config=config, constraints=constraints)

        # Same iteration, same agent should produce same sampling seed
        seed1 = orchestrator1.get_sampling_seed(iteration=5, agent_id="BANK_A")
        seed2 = orchestrator2.get_sampling_seed(iteration=5, agent_id="BANK_A")

        assert seed1 == seed2
