"""Unit tests for policy evolution service."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

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
def test_db(tmp_path: Path) -> Path:
    """Create a test database path."""
    return tmp_path / "test_experiments.db"


@pytest.fixture
def repo_with_data(test_db: Path) -> ExperimentRepository:
    """Create a repository with sample experiment data."""
    repo = ExperimentRepository(test_db)

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

    # Create iterations with policies
    for i in range(3):
        repo.save_iteration(
            IterationRecord(
                run_id="test-run-123",
                iteration=i,
                costs_per_agent={"BANK_A": 10000 - i * 1000, "BANK_B": 8000 - i * 500},
                accepted_changes={"BANK_A": True, "BANK_B": i > 0},
                policies={
                    "BANK_A": {"version": "2.0", "threshold": 100 + i * 10},
                    "BANK_B": {"version": "2.0", "threshold": 200 + i * 5},
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
                event_type="llm_call_complete",
                event_data={
                    "agent_id": "BANK_A",
                    "system_prompt": f"System prompt for iteration {i}",
                    "user_prompt": f"User prompt for iteration {i}",
                    "raw_response": f'{{"threshold": {100 + i * 10}}}',
                },
                timestamp=datetime.now().isoformat(),
            )
        )

    return repo


class TestPolicyEvolutionService:
    """Tests for PolicyEvolutionService."""

    def test_get_evolution_returns_all_agents(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify all agents are returned when no filter."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123")

        agent_ids = {evo.agent_id for evo in evolutions}
        assert agent_ids == {"BANK_A", "BANK_B"}

    def test_get_evolution_filters_by_agent(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify agent_filter works correctly."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        assert evolutions[0].agent_id == "BANK_A"

    def test_get_evolution_filters_by_iteration_range(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify start/end iteration filtering."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution(
            "test-run-123",
            start_iteration=2,
            end_iteration=2,
        )

        # Should only have iteration_2 (1-indexed)
        for evo in evolutions:
            assert "iteration_1" not in evo.iterations
            assert "iteration_2" in evo.iterations
            assert "iteration_3" not in evo.iterations

    def test_get_evolution_includes_llm_when_requested(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify LLM data is included with include_llm=True."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution(
            "test-run-123",
            include_llm=True,
            agent_filter="BANK_A",
        )

        assert len(evolutions) == 1
        iteration_1 = evolutions[0].iterations.get("iteration_1")
        assert iteration_1 is not None
        assert iteration_1.llm is not None
        assert "System prompt" in iteration_1.llm.system_prompt

    def test_get_evolution_excludes_llm_by_default(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify LLM data is NOT included by default."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123", include_llm=False)

        for evo in evolutions:
            for iter_evo in evo.iterations.values():
                assert iter_evo.llm is None

    def test_get_evolution_computes_diffs(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify diffs are computed between iterations."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        assert len(evolutions) == 1
        agent_evo = evolutions[0]

        # First iteration should have no diff (nothing to compare)
        iter_1 = agent_evo.iterations.get("iteration_1")
        assert iter_1 is not None
        assert iter_1.diff is None

        # Second iteration should have diff
        iter_2 = agent_evo.iterations.get("iteration_2")
        assert iter_2 is not None
        assert iter_2.diff is not None
        assert "threshold" in iter_2.diff

    def test_get_evolution_handles_first_iteration_no_diff(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify first iteration has no diff (nothing to compare)."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution(
            "test-run-123",
            start_iteration=1,
            end_iteration=1,
        )

        for evo in evolutions:
            iter_1 = evo.iterations.get("iteration_1")
            assert iter_1 is not None
            # First iteration has no previous to compare
            assert iter_1.diff is None

    def test_get_evolution_raises_for_invalid_run_id(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify ValueError for non-existent run."""
        service = PolicyEvolutionService(repo_with_data)

        with pytest.raises(ValueError, match="not found"):
            service.get_evolution("nonexistent-run")

    def test_get_evolution_iteration_numbers_are_1_indexed(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify output uses 1-indexed iteration numbers."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123")

        for evo in evolutions:
            # Should have iteration_1, iteration_2, iteration_3
            # NOT iteration_0, iteration_1, iteration_2
            assert "iteration_1" in evo.iterations
            assert "iteration_2" in evo.iterations
            assert "iteration_3" in evo.iterations
            assert "iteration_0" not in evo.iterations

    def test_get_evolution_includes_cost_and_accepted(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify cost and accepted fields are included."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution("test-run-123", agent_filter="BANK_A")

        iter_1 = evolutions[0].iterations["iteration_1"]
        assert iter_1.cost == 10000  # First iteration cost
        assert iter_1.accepted is True

    def test_get_evolution_returns_empty_for_nonexistent_agent(
        self, repo_with_data: ExperimentRepository
    ) -> None:
        """Verify empty result for agent that doesn't exist."""
        service = PolicyEvolutionService(repo_with_data)
        evolutions = service.get_evolution(
            "test-run-123",
            agent_filter="NONEXISTENT_AGENT",
        )

        assert evolutions == []

    def test_get_evolution_handles_empty_experiment(
        self, test_db: Path
    ) -> None:
        """Verify empty result for experiment with no iterations."""
        repo = ExperimentRepository(test_db)
        repo.save_experiment(
            ExperimentRecord(
                run_id="empty-run",
                experiment_name="empty",
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

        assert evolutions == []
        repo.close()
