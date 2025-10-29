"""
Pytest configuration and shared fixtures for integration tests.

Provides database fixtures that:
- Use repo directory for easy debugging
- Keep databases on test failure
- Clean up on test success
- Support both local dev and CI environments
"""

import os
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def db_path(request, tmp_path) -> Generator[Path, None, None]:
    """Provide database path with intelligent cleanup.

    Behavior:
    - Local dev (default): Uses api/test_databases/ for easy inspection
    - CI environment: Uses tmp_path for isolation
    - Keeps database on test failure for debugging
    - Cleans up on test success

    Usage:
        def test_something(db_path):
            manager = DatabaseManager(db_path)
            # db_path will be in api/test_databases/ for easy inspection

    To inspect after test:
        $ duckdb api/test_databases/test_something.db
        D SELECT * FROM daily_agent_metrics;
    """
    # Detect CI environment
    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"

    if is_ci:
        # CI: Use temporary directory for isolation
        db_file = tmp_path / "test.db"
    else:
        # Local dev: Use repo directory for debugging
        test_db_dir = Path(__file__).parent.parent / "test_databases"
        test_db_dir.mkdir(exist_ok=True)

        # Use test name as filename
        test_name = request.node.name.replace("[", "_").replace("]", "")
        db_file = test_db_dir / f"{test_name}.db"

        # Clean up existing file before test
        if db_file.exists():
            db_file.unlink()
            # Also remove WAL file if exists
            wal_file = Path(str(db_file) + ".wal")
            if wal_file.exists():
                wal_file.unlink()

    yield db_file

    # Cleanup after test (only on success)
    if not is_ci and request.node.rep_call.passed:
        # Test passed - clean up
        if db_file.exists():
            db_file.unlink()
        wal_file = Path(str(db_file) + ".wal")
        if wal_file.exists():
            wal_file.unlink()
    # On test failure: keep the database for debugging


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Hook to make test results available to fixtures.

    This allows the db_path fixture to know if the test passed or failed.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
