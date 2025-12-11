"""TDD tests for Castro test file imports.

Phase 13, Task 13.5: Update all Castro test imports.

Verifies that no test files import from deleted Castro infrastructure modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


def _get_tests_dir() -> Path:
    """Get path to castro tests directory."""
    return Path(__file__).parent


def _get_all_test_files() -> list[Path]:
    """Get all test files in castro tests directory.

    Excludes test_castro_infrastructure_deleted.py which legitimately
    uses import statements inside pytest.raises to verify imports fail.
    """
    tests_dir = _get_tests_dir()
    test_files = list(tests_dir.glob("test_*.py"))
    # Exclude infrastructure deletion test (it tests that imports fail)
    return [
        f for f in test_files
        if f.name != "test_castro_infrastructure_deleted.py"
    ]


def _get_imports_from_file(file_path: Path) -> list[str]:
    """Extract all import statements from a Python file.

    Returns list of module paths imported.
    """
    source = file_path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


class TestNoDeletedInfrastructureImports:
    """Tests verifying no test files import deleted infrastructure."""

    def test_no_imports_from_castro_state_provider(self) -> None:
        """No test files should import from castro.state_provider."""
        test_files = _get_all_test_files()

        violations = []
        for test_file in test_files:
            imports = _get_imports_from_file(test_file)
            for imp in imports:
                if imp.startswith("castro.state_provider"):
                    violations.append(f"{test_file.name}: imports {imp}")

        assert not violations, (
            f"Test files still import from deleted castro.state_provider:\n"
            + "\n".join(violations)
        )

    def test_no_imports_from_castro_persistence(self) -> None:
        """No test files should import from castro.persistence."""
        test_files = _get_all_test_files()

        violations = []
        for test_file in test_files:
            imports = _get_imports_from_file(test_file)
            for imp in imports:
                if imp.startswith("castro.persistence"):
                    violations.append(f"{test_file.name}: imports {imp}")

        assert not violations, (
            f"Test files still import from deleted castro.persistence:\n"
            + "\n".join(violations)
        )

    def test_no_imports_from_castro_event_compat(self) -> None:
        """No test files should import from castro.event_compat."""
        test_files = _get_all_test_files()

        violations = []
        for test_file in test_files:
            imports = _get_imports_from_file(test_file)
            for imp in imports:
                if imp.startswith("castro.event_compat"):
                    violations.append(f"{test_file.name}: imports {imp}")

        assert not violations, (
            f"Test files still import from deleted castro.event_compat:\n"
            + "\n".join(violations)
        )


class TestAllTestFilesCompile:
    """Tests verifying all test files can be imported without errors."""

    def test_all_test_files_have_valid_syntax(self) -> None:
        """All test files should have valid Python syntax."""
        test_files = _get_all_test_files()

        errors = []
        for test_file in test_files:
            source = test_file.read_text()
            try:
                ast.parse(source)
            except SyntaxError as e:
                errors.append(f"{test_file.name}: {e}")

        assert not errors, (
            f"Test files with syntax errors:\n" + "\n".join(errors)
        )


class TestCoreImportsAvailable:
    """Tests verifying core imports are available for test migration."""

    def test_core_experiment_record_available(self) -> None:
        """ExperimentRecord should be importable from core."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        assert ExperimentRecord is not None

    def test_core_event_record_available(self) -> None:
        """EventRecord should be importable from core."""
        from payment_simulator.experiments.persistence import EventRecord

        assert EventRecord is not None

    def test_core_experiment_repository_available(self) -> None:
        """ExperimentRepository should be importable from core."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        assert ExperimentRepository is not None

    def test_core_database_state_provider_available(self) -> None:
        """DatabaseStateProvider should be importable from core."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        assert DatabaseStateProvider is not None

    def test_core_live_state_provider_available(self) -> None:
        """LiveStateProvider should be importable from core."""
        from payment_simulator.experiments.runner import LiveStateProvider

        assert LiveStateProvider is not None
