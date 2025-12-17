"""Tests for CLI entry point - TDD RED phase."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


# =============================================================================
# Phase 5.4: CLI Tests
# =============================================================================


class TestCLI:
    """Test command-line interface."""

    @pytest.fixture
    def v5_dir(self) -> Path:
        """Get v5 directory path."""
        return Path(__file__).parent.parent

    def test_cli_generates_paper(self, tmp_path: Path, v5_dir: Path) -> None:
        """CLI should generate paper.tex."""
        result = subprocess.run(
            [
                "/home/user/SimCash/api/.venv/bin/python",
                "-m", "src.cli",
                "--data-dir", str(v5_dir / "data"),
                "--output-dir", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=v5_dir,
        )

        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert (tmp_path / "paper.tex").exists(), "paper.tex not created"

    def test_cli_prints_output_path(self, tmp_path: Path, v5_dir: Path) -> None:
        """CLI should print path to generated file."""
        result = subprocess.run(
            [
                "/home/user/SimCash/api/.venv/bin/python",
                "-m", "src.cli",
                "--data-dir", str(v5_dir / "data"),
                "--output-dir", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=v5_dir,
        )

        assert "paper.tex" in result.stdout, (
            f"Output path not printed. stdout: {result.stdout}"
        )

    def test_cli_creates_output_dir_if_missing(
        self, tmp_path: Path, v5_dir: Path
    ) -> None:
        """CLI should create output directory if it doesn't exist."""
        new_output = tmp_path / "new_output_dir"
        assert not new_output.exists()

        result = subprocess.run(
            [
                "/home/user/SimCash/api/.venv/bin/python",
                "-m", "src.cli",
                "--data-dir", str(v5_dir / "data"),
                "--output-dir", str(new_output),
            ],
            capture_output=True,
            text=True,
            cwd=v5_dir,
        )

        assert result.returncode == 0
        assert new_output.exists()
        assert (new_output / "paper.tex").exists()

    def test_cli_help(self, v5_dir: Path) -> None:
        """CLI should support --help flag."""
        result = subprocess.run(
            [
                "/home/user/SimCash/api/.venv/bin/python",
                "-m", "src.cli",
                "--help",
            ],
            capture_output=True,
            text=True,
            cwd=v5_dir,
        )

        assert result.returncode == 0
        assert "--data-dir" in result.stdout
        assert "--output-dir" in result.stdout
