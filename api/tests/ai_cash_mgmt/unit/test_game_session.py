"""Unit tests for GameSession - single game session state management.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

from typing import Any

import pytest


class TestGameSessionCreation:
    """Test game session creation and initialization."""

    def test_game_session_creates_with_config(self) -> None:
        """GameSession should initialize from GameConfig."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

        config = GameConfig(
            game_id="test_game_001",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        session = GameSession(config=config)

        assert session.game_id == "test_game_001"
        assert session.master_seed == 42
        assert session.current_iteration == 0
        assert not session.is_converged
        assert session.status == "initialized"

    def test_game_session_generates_unique_session_id(self) -> None:
        """Each GameSession should have a unique session ID."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session1 = GameSession(config=config)
        session2 = GameSession(config=config)

        assert session1.session_id != session2.session_id


class TestGameSessionPolicyTracking:
    """Test policy tracking in game session."""

    def test_session_tracks_current_policies(self) -> None:
        """Session should track current policies per agent."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        session = GameSession(config=config)

        policy_a: dict[str, Any] = {"payment_tree": {"type": "action", "action": "queue"}}
        policy_b: dict[str, Any] = {"payment_tree": {"type": "action", "action": "submit"}}

        session.set_policy("BANK_A", policy_a)
        session.set_policy("BANK_B", policy_b)

        assert session.get_policy("BANK_A") == policy_a
        assert session.get_policy("BANK_B") == policy_b

    def test_session_tracks_best_policies(self) -> None:
        """Session should track best policies and their costs."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session = GameSession(config=config)

        policy1: dict[str, Any] = {"version": "1"}
        policy2: dict[str, Any] = {"version": "2"}

        session.record_evaluation("BANK_A", policy1, mean_cost=1000.0, iteration=1)
        session.record_evaluation("BANK_A", policy2, mean_cost=800.0, iteration=2)
        session.record_evaluation("BANK_A", policy1, mean_cost=900.0, iteration=3)

        best = session.get_best_policy("BANK_A")
        assert best is not None
        assert best["policy"] == policy2
        assert best["cost"] == 800.0
        assert best["iteration"] == 2


class TestGameSessionIterationTracking:
    """Test iteration tracking in game session."""

    def test_session_increments_iteration(self) -> None:
        """Session should track iteration count."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session = GameSession(config=config)
        assert session.current_iteration == 0

        session.start_iteration()
        assert session.current_iteration == 1

        session.complete_iteration()
        session.start_iteration()
        assert session.current_iteration == 2

    def test_session_tracks_iteration_history(self) -> None:
        """Session should track history of all iterations."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session = GameSession(config=config)

        session.start_iteration()
        session.record_iteration_result(
            total_cost=1000.0,
            per_agent_costs={"BANK_A": 1000.0},
            settlement_rate=0.95,
        )
        session.complete_iteration()

        session.start_iteration()
        session.record_iteration_result(
            total_cost=800.0,
            per_agent_costs={"BANK_A": 800.0},
            settlement_rate=0.98,
        )
        session.complete_iteration()

        history = session.get_iteration_history()
        assert len(history) == 2
        assert history[0]["total_cost"] == 1000.0
        assert history[1]["total_cost"] == 800.0


class TestGameSessionStatusManagement:
    """Test session status management."""

    def test_session_status_transitions(self) -> None:
        """Session should track status transitions."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session = GameSession(config=config)
        assert session.status == "initialized"

        session.start()
        assert session.status == "running"

        session.mark_converged("Stability achieved")
        assert session.status == "completed"
        assert session.is_converged
        assert session.convergence_reason == "Stability achieved"

    def test_session_can_be_marked_failed(self) -> None:
        """Session should be able to be marked as failed."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

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

        session = GameSession(config=config)
        session.start()
        session.mark_failed("LLM API error")

        assert session.status == "failed"
        assert session.failure_reason == "LLM API error"


class TestGameSessionAgentHistory:
    """Test per-agent history filtering."""

    def test_get_agent_history_returns_filtered_history(self) -> None:
        """get_agent_history should return only specified agent's data."""
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
        from payment_simulator.ai_cash_mgmt.core.game_session import GameSession

        config = GameConfig(
            game_id="test_game",
            scenario_config="scenarios/test.yaml",
            master_seed=42,
            optimized_agents={
                "BANK_A": AgentOptimizationConfig(),
                "BANK_B": AgentOptimizationConfig(),
            },
            optimization_schedule=OptimizationSchedule(
                type=OptimizationScheduleType.EVERY_X_TICKS,
                interval_ticks=50,
            ),
            bootstrap=BootstrapConfig(),
            convergence=ConvergenceCriteria(),
        )

        session = GameSession(config=config)

        # Record evaluations for both agents
        policy_a: dict[str, Any] = {"agent": "A"}
        policy_b: dict[str, Any] = {"agent": "B"}

        session.record_evaluation("BANK_A", policy_a, mean_cost=1000.0, iteration=1)
        session.record_evaluation("BANK_B", policy_b, mean_cost=1200.0, iteration=1)
        session.record_evaluation("BANK_A", policy_a, mean_cost=900.0, iteration=2)

        history_a = session.get_agent_history("BANK_A")
        history_b = session.get_agent_history("BANK_B")

        # Agent A should have 2 entries
        assert len(history_a) == 2
        assert all(h["agent_id"] == "BANK_A" for h in history_a)

        # Agent B should have 1 entry
        assert len(history_b) == 1
        assert history_b[0]["agent_id"] == "BANK_B"
