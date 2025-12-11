"""TDD tests for Castro infrastructure deletion.

Phase 13, Task 13.4: Delete Castro infrastructure files.

These tests verify that Castro now uses core infrastructure and the
Castro-specific infrastructure files have been deleted.

Write these tests FIRST, then delete the files to make them pass.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _get_castro_package_path() -> Path:
    """Get path to castro package."""
    return Path(__file__).parent.parent / "castro"


class TestCastroStateProviderDeleted:
    """Tests verifying castro/state_provider.py has been deleted."""

    def test_state_provider_file_does_not_exist(self) -> None:
        """castro/state_provider.py should not exist."""
        castro_path = _get_castro_package_path()
        state_provider_path = castro_path / "state_provider.py"

        assert not state_provider_path.exists(), (
            f"castro/state_provider.py should be deleted - "
            f"Castro now uses core ExperimentStateProviderProtocol"
        )

    def test_cannot_import_castro_state_provider(self) -> None:
        """from castro.state_provider should fail."""
        with pytest.raises(ImportError):
            from castro.state_provider import ExperimentStateProvider  # noqa: F401

    def test_cannot_import_castro_live_provider(self) -> None:
        """from castro.state_provider import LiveExperimentProvider should fail."""
        with pytest.raises(ImportError):
            from castro.state_provider import LiveExperimentProvider  # noqa: F401

    def test_cannot_import_castro_database_provider(self) -> None:
        """from castro.state_provider import DatabaseExperimentProvider should fail."""
        with pytest.raises(ImportError):
            from castro.state_provider import DatabaseExperimentProvider  # noqa: F401


class TestCastroPersistenceDeleted:
    """Tests verifying castro/persistence/ has been deleted."""

    def test_persistence_directory_does_not_exist(self) -> None:
        """castro/persistence/ directory should not exist."""
        castro_path = _get_castro_package_path()
        persistence_path = castro_path / "persistence"

        assert not persistence_path.exists(), (
            f"castro/persistence/ should be deleted - "
            f"Castro now uses core ExperimentRepository"
        )

    def test_persistence_models_does_not_exist(self) -> None:
        """castro/persistence/models.py should not exist."""
        castro_path = _get_castro_package_path()
        models_path = castro_path / "persistence" / "models.py"

        assert not models_path.exists(), (
            f"castro/persistence/models.py should be deleted"
        )

    def test_persistence_repository_does_not_exist(self) -> None:
        """castro/persistence/repository.py should not exist."""
        castro_path = _get_castro_package_path()
        repository_path = castro_path / "persistence" / "repository.py"

        assert not repository_path.exists(), (
            f"castro/persistence/repository.py should be deleted"
        )

    def test_cannot_import_castro_persistence(self) -> None:
        """from castro.persistence should fail."""
        with pytest.raises(ImportError):
            from castro.persistence import CastroRepository  # noqa: F401


class TestCastroEventCompatDeleted:
    """Tests verifying castro/event_compat.py has been deleted."""

    def test_event_compat_file_does_not_exist(self) -> None:
        """castro/event_compat.py should not exist."""
        castro_path = _get_castro_package_path()
        event_compat_path = castro_path / "event_compat.py"

        assert not event_compat_path.exists(), (
            f"castro/event_compat.py should be deleted - "
            f"Castro display now uses dict events from core"
        )

    def test_cannot_import_castro_event_compat(self) -> None:
        """from castro.event_compat should fail."""
        with pytest.raises(ImportError):
            from castro.event_compat import CastroEvent  # noqa: F401


class TestCoreImportsWork:
    """Tests verifying core imports work correctly after deletion."""

    def test_can_import_core_protocol(self) -> None:
        """Core ExperimentStateProviderProtocol should be importable."""
        from payment_simulator.experiments.runner import (
            ExperimentStateProviderProtocol,
        )

        assert ExperimentStateProviderProtocol is not None

    def test_can_import_core_live_provider(self) -> None:
        """Core LiveStateProvider should be importable."""
        from payment_simulator.experiments.runner import LiveStateProvider

        assert LiveStateProvider is not None

    def test_can_import_core_database_provider(self) -> None:
        """Core DatabaseStateProvider should be importable."""
        from payment_simulator.experiments.runner import DatabaseStateProvider

        assert DatabaseStateProvider is not None

    def test_can_import_core_repository(self) -> None:
        """Core ExperimentRepository should be importable."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        assert ExperimentRepository is not None
