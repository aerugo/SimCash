"""Verification tests for dead code removal in Phase 1.

These tests document that the Castro audit tables (llm_interaction_log,
policy_diffs, iteration_context) are not used by the experiment framework.

The experiment framework uses experiment_events table for LLM interaction
tracking via _save_llm_interaction_event() which calls repository.save_event().
"""

import ast
import pathlib


def test_game_repository_not_used_in_experiments() -> None:
    """Verify GameRepository is not imported in experiments module."""
    experiments_dir = pathlib.Path(__file__).parent.parent.parent / "payment_simulator" / "experiments"

    for py_file in experiments_dir.rglob("*.py"):
        content = py_file.read_text()
        # Check for GameRepository import
        assert "GameRepository" not in content, (
            f"GameRepository found in {py_file}. "
            "Experiments should use ExperimentRepository, not GameRepository."
        )


def test_save_llm_interaction_not_called_in_production() -> None:
    """Verify save_llm_interaction is not called in production code."""
    payment_simulator_dir = (
        pathlib.Path(__file__).parent.parent.parent / "payment_simulator"
    )

    for py_file in payment_simulator_dir.rglob("*.py"):
        # Skip test files and the repository definition itself
        if "test" in str(py_file) or "repository.py" in str(py_file):
            continue

        content = py_file.read_text()
        assert ".save_llm_interaction(" not in content, (
            f"save_llm_interaction() called in {py_file}. "
            "This method should be dead code."
        )


def test_save_policy_diff_not_called_in_production() -> None:
    """Verify save_policy_diff is not called in production code."""
    payment_simulator_dir = (
        pathlib.Path(__file__).parent.parent.parent / "payment_simulator"
    )

    for py_file in payment_simulator_dir.rglob("*.py"):
        if "test" in str(py_file) or "repository.py" in str(py_file):
            continue

        content = py_file.read_text()
        assert ".save_policy_diff(" not in content, (
            f"save_policy_diff() called in {py_file}. "
            "This method should be dead code."
        )


def test_save_iteration_context_not_called_in_production() -> None:
    """Verify save_iteration_context is not called in production code."""
    payment_simulator_dir = (
        pathlib.Path(__file__).parent.parent.parent / "payment_simulator"
    )

    for py_file in payment_simulator_dir.rglob("*.py"):
        if "test" in str(py_file) or "repository.py" in str(py_file):
            continue

        content = py_file.read_text()
        assert ".save_iteration_context(" not in content, (
            f"save_iteration_context() called in {py_file}. "
            "This method should be dead code."
        )


def test_llm_interactions_use_experiment_events() -> None:
    """Verify experiments store LLM interactions in experiment_events."""
    optimization_path = (
        pathlib.Path(__file__).parent.parent.parent
        / "payment_simulator"
        / "experiments"
        / "runner"
        / "optimization.py"
    )

    content = optimization_path.read_text()

    # Should have _save_llm_interaction_event method
    assert "_save_llm_interaction_event" in content, (
        "optimization.py should have _save_llm_interaction_event method"
    )

    # Should call repository.save_event (not GameRepository methods)
    assert "self._repository.save_event" in content, (
        "LLM interactions should be saved via repository.save_event()"
    )
