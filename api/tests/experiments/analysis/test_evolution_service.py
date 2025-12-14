"""Tests for PolicyEvolutionService.

TDD tests for the service layer that orchestrates policy evolution extraction.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    LLMInteractionData,
)
from payment_simulator.experiments.analysis.evolution_service import (
    PolicyEvolutionService,
)
from payment_simulator.experiments.persistence import (
    EventRecord,
    ExperimentRecord,
    ExperimentRepository,
    IterationRecord,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_experiments.db"


@pytest.fixture
def sample_repo(temp_db: Path) -> ExperimentRepository:
    """Create repository with sample experiment data."""
    repo = ExperimentRepository(temp_db)

    # Create experiment
    repo.save_experiment(
        ExperimentRecord(
            run_id="test-run-123",
            experiment_name="test_exp",
            experiment_type="generic",
            config={},
            created_at=datetime.now().isoformat(),
            completed_at=datetime.now().isoformat(),
            num_iterations=3,
            converged=True,
            convergence_reason="stability_reached",
        )
    )

    # Create iterations with policies (0-indexed internally)
    for i in range(3):
        repo.save_iteration(
            IterationRecord(
                run_id="test-run-123",
                iteration=i,
                costs_per_agent={"BANK_A": 10000 - i * 1000, "BANK_B": 8000 - i * 500},
                accepted_changes={"BANK_A": True, "BANK_B": i > 0},
                policies={
                    "BANK_A": {"version": "2.0", "parameters": {"threshold": 100 + i * 10}},
                    "BANK_B": {"version": "2.0", "parameters": {"threshold": 200 + i * 5}},
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    # Create LLM events
    for i in range(3):
        repo.save_event(
            EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_interaction",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": f"System prompt for iteration {i}",
                    "user_prompt": f"User prompt for iteration {i}",
                    "raw_response": f'{{"threshold": {100 + i * 10}}}',
                },
                timestamp=datetime.now().isoformat(),
            )
        )
        repo.save_event(
            EventRecord(
                run_id="test-run-123",
                iteration=i,
                event_type="llm_interaction",
                event_data={
                    "agent_id": "BANK_B",
                    "system_prompt": f"System prompt B for iteration {i}",
                    "user_prompt": f"User prompt B for iteration {i}",
                    "raw_response": f'{{"threshold": {200 + i * 5}}}',
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    return repo


class TestPolicyEvolutionService:
    """Tests for PolicyEvolutionService class."""

    def test_get_evolution_returns_all_agents(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify all agents are returned when no filter."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123")

        assert len(evolutions) == 2
        agent_ids = {e.agent_id for e in evolutions}
        assert "BANK_A" in agent_ids
        assert "BANK_B" in agent_ids

    def test_get_evolution_filters_by_agent(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify agent_filter works correctly."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        assert evolutions[0].agent_id == "BANK_A"

    def test_get_evolution_filters_by_iteration_range(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify start/end iteration filtering."""
        service = PolicyEvolutionService(sample_repo)

        # Request iterations 2-3 (1-indexed user input, 1-2 internally 0-indexed)
        evolutions = service.get_evolution(
            "test-run-123",
            start_iteration=2,
            end_iteration=3,
        )

        assert len(evolutions) > 0
        for agent in evolutions:
            # Should only have iteration_2 and iteration_3
            assert "iteration_1" not in agent.iterations
            assert "iteration_2" in agent.iterations
            assert "iteration_3" in agent.iterations

    def test_get_evolution_includes_llm_when_requested(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify LLM data is included with include_llm=True."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution(
            "test-run-123",
            include_llm=True,
            agent_filter="BANK_A",
        )

        assert len(evolutions) == 1
        agent = evolutions[0]

        # Check that LLM data is present
        for iteration in agent.iterations.values():
            assert iteration.llm is not None
            assert isinstance(iteration.llm, LLMInteractionData)
            assert "System prompt" in iteration.llm.system_prompt
            assert "User prompt" in iteration.llm.user_prompt

    def test_get_evolution_excludes_llm_by_default(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify LLM data is NOT included by default."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        agent = evolutions[0]

        # LLM data should NOT be present
        for iteration in agent.iterations.values():
            assert iteration.llm is None

    def test_get_evolution_computes_diffs(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify diffs are computed between iterations."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        agent = evolutions[0]

        # First iteration has no diff
        assert agent.iterations["iteration_1"].diff == ""

        # Subsequent iterations have diff showing threshold change
        iteration_2_diff = agent.iterations["iteration_2"].diff or ""
        assert "threshold" in iteration_2_diff or iteration_2_diff == ""

    def test_get_evolution_handles_first_iteration_no_diff(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify first iteration has no diff (nothing to compare)."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution(
            "test-run-123",
            agent_filter="BANK_A",
            start_iteration=1,
            end_iteration=1,
        )

        assert len(evolutions) == 1
        agent = evolutions[0]

        # First iteration should have empty diff
        assert "iteration_1" in agent.iterations
        assert agent.iterations["iteration_1"].diff == ""

    def test_get_evolution_raises_for_invalid_run_id(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify ValueError for non-existent run."""
        service = PolicyEvolutionService(sample_repo)

        with pytest.raises(ValueError, match="not found"):
            service.get_evolution("nonexistent-run")

    def test_get_evolution_iteration_numbers_are_1_indexed(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify output uses 1-indexed iteration numbers."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        agent = evolutions[0]

        # Keys should be iteration_1, iteration_2, iteration_3 (not iteration_0)
        assert "iteration_0" not in agent.iterations
        assert "iteration_1" in agent.iterations
        assert "iteration_2" in agent.iterations
        assert "iteration_3" in agent.iterations

    def test_get_evolution_includes_cost_and_accepted(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify cost and accepted fields are included."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        agent = evolutions[0]

        # First iteration: cost=10000, accepted=True
        iter1 = agent.iterations["iteration_1"]
        assert iter1.cost == 10000
        assert iter1.accepted is True

        # Second iteration: cost=9000, accepted=True
        iter2 = agent.iterations["iteration_2"]
        assert iter2.cost == 9000
        assert iter2.accepted is True

    def test_get_evolution_handles_agent_not_in_experiment(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify filtering by nonexistent agent returns empty."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution(
            "test-run-123",
            agent_filter="NONEXISTENT_AGENT",
        )

        assert evolutions == []

    def test_get_evolution_start_iteration_clipping(
        self, sample_repo: ExperimentRepository
    ) -> None:
        """Verify start_iteration > max returns empty."""
        service = PolicyEvolutionService(sample_repo)

        evolutions = service.get_evolution(
            "test-run-123",
            start_iteration=100,  # Way beyond available iterations
        )

        # Should return agents but with no iterations (all filtered out)
        for agent in evolutions:
            assert len(agent.iterations) == 0


class TestPolicyEvolutionServiceEdgeCases:
    """Edge case tests for PolicyEvolutionService."""

    def test_handles_experiment_with_no_iterations(self, temp_db: Path) -> None:
        """Verify handling of experiment with no iterations."""
        repo = ExperimentRepository(temp_db)

        # Create experiment with no iterations
        repo.save_experiment(
            ExperimentRecord(
                run_id="empty-run",
                experiment_name="empty_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=None,
                num_iterations=0,
                converged=False,
                convergence_reason=None,
            )
        )

        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution("empty-run")

        # Should return empty list (no agents to report)
        assert evolutions == []

    def test_handles_missing_llm_events(self, temp_db: Path) -> None:
        """Verify handling when LLM events are missing."""
        repo = ExperimentRepository(temp_db)

        # Create experiment with iteration but NO LLM events
        repo.save_experiment(
            ExperimentRecord(
                run_id="no-llm-run",
                experiment_name="no_llm_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                num_iterations=1,
                converged=True,
                convergence_reason="done",
            )
        )
        repo.save_iteration(
            IterationRecord(
                run_id="no-llm-run",
                iteration=0,
                costs_per_agent={"BANK_A": 5000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": {"version": "1.0"}},
                timestamp=datetime.now().isoformat(),
            )
        )

        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution("no-llm-run", include_llm=True)

        # Should work, just with None for LLM data
        assert len(evolutions) == 1
        assert evolutions[0].iterations["iteration_1"].llm is None

    def test_handles_single_iteration(self, temp_db: Path) -> None:
        """Verify handling of experiment with single iteration."""
        repo = ExperimentRepository(temp_db)

        repo.save_experiment(
            ExperimentRecord(
                run_id="single-iter",
                experiment_name="single_exp",
                experiment_type="generic",
                config={},
                created_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                num_iterations=1,
                converged=True,
                convergence_reason="done",
            )
        )
        repo.save_iteration(
            IterationRecord(
                run_id="single-iter",
                iteration=0,
                costs_per_agent={"BANK_A": 5000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": {"version": "1.0", "parameters": {"x": 1}}},
                timestamp=datetime.now().isoformat(),
            )
        )

        service = PolicyEvolutionService(repo)
        evolutions = service.get_evolution("single-iter")

        assert len(evolutions) == 1
        agent = evolutions[0]
        assert "iteration_1" in agent.iterations
        # Single iteration should have no diff
        assert agent.iterations["iteration_1"].diff == ""
