"""Tests for CLI commands."""

import json
import subprocess
import pytest
from pathlib import Path


@pytest.fixture
def test_config(tmp_path):
    """Create a minimal test configuration."""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text("""
simulation:
  ticks_per_day: 10
  num_days: 1
  rng_seed: 42

agents:
  - id: "BANK_A"
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: "Fifo"

  - id: "BANK_B"
    opening_balance: 1000000
    credit_limit: 500000
    policy:
      type: "Fifo"

lsm_config:
  bilateral_offsetting: true
  cycle_detection: true
  max_iterations: 3
""")
    return config_file


def run_cli(args, check=True):
    """Helper to run CLI command and capture output."""
    import os
    import sys

    # Use the venv's payment-sim if it exists, otherwise fall back to system PATH
    venv_bin = Path(sys.prefix) / "bin" / "payment-sim"
    if venv_bin.exists():
        cli_cmd = str(venv_bin)
    else:
        cli_cmd = "payment-sim"

    # Set PYTHONPATH to include the api directory so the package can be imported
    env = os.environ.copy()
    api_dir = str(Path(__file__).parent.parent)
    current_pythonpath = env.get('PYTHONPATH', '')
    if current_pythonpath:
        env['PYTHONPATH'] = f"{api_dir}:{current_pythonpath}"
    else:
        env['PYTHONPATH'] = api_dir

    result = subprocess.run(
        [cli_cmd] + args,
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )
    return result


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_help_command(self):
        """Test --help flag."""
        result = run_cli(["--help"])
        assert result.returncode == 0
        assert "Payment Simulator" in result.stdout
        assert "run" in result.stdout

    def test_version_command(self):
        """Test --version flag."""
        result = run_cli(["--version"], check=False)
        assert "Payment Simulator" in result.stderr

    def test_run_help(self):
        """Test run command help."""
        result = run_cli(["run", "--help"])
        assert result.returncode == 0
        assert "--config" in result.stdout
        assert "--quiet" in result.stdout
        assert "--stream" in result.stdout


class TestRunCommand:
    """Test the run command."""

    def test_basic_run(self, test_config):
        """Test basic simulation run."""
        result = run_cli(["run", "--config", str(test_config)])
        assert result.returncode == 0

        # Verify JSON output on stdout
        output = json.loads(result.stdout)
        assert "simulation" in output
        assert "metrics" in output
        assert "agents" in output
        assert output["simulation"]["seed"] == 42
        assert output["simulation"]["ticks_executed"] == 10

        # Verify logs on stderr
        assert "Loading configuration" in result.stderr
        # Output format shows "✓ Simulation created" and progress bar, not "Completed"
        assert ("Simulation created" in result.stderr or "Running simulation" in result.stderr)

    def test_quiet_mode(self, test_config):
        """Test quiet mode suppresses logs."""
        result = run_cli(["run", "--config", str(test_config), "--quiet"])
        assert result.returncode == 0

        # stdout should have JSON only
        output = json.loads(result.stdout)
        assert "simulation" in output

        # stderr should be empty or minimal
        assert "Loading configuration" not in result.stderr

    def test_stdout_stderr_separation(self, test_config):
        """Test that JSON goes to stdout, logs to stderr."""
        result = run_cli(["run", "--config", str(test_config)])

        # stdout should be valid JSON
        stdout_data = json.loads(result.stdout)
        assert isinstance(stdout_data, dict)

        # stderr should have logs (not JSON)
        assert "{" not in result.stderr  # No JSON in logs

    def test_seed_override(self, test_config):
        """Test --seed parameter override."""
        result = run_cli(["run", "--config", str(test_config), "--seed", "999", "--quiet"])
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert output["simulation"]["seed"] == 999

    def test_ticks_override(self, test_config):
        """Test --ticks parameter override."""
        result = run_cli(["run", "--config", str(test_config), "--ticks", "5", "--quiet"])
        assert result.returncode == 0

        output = json.loads(result.stdout)
        assert output["simulation"]["ticks_executed"] == 5

    def test_streaming_mode(self, test_config):
        """Test streaming JSONL output."""
        result = run_cli(["run", "--config", str(test_config), "--stream", "--quiet"])
        assert result.returncode == 0

        # Parse JSONL output
        lines = result.stdout.strip().split("\n")
        assert len(lines) == 10  # 10 ticks

        # Each line should be valid JSON
        for i, line in enumerate(lines):
            tick_data = json.loads(line)
            assert tick_data["tick"] == i
            assert "arrivals" in tick_data
            assert "settlements" in tick_data

    def test_determinism(self, test_config):
        """Test that same seed produces identical results."""
        result1 = run_cli(["run", "--config", str(test_config), "--seed", "12345", "--quiet"])
        result2 = run_cli(["run", "--config", str(test_config), "--seed", "12345", "--quiet"])

        output1 = json.loads(result1.stdout)
        output2 = json.loads(result2.stdout)

        # Sort agents by ID for consistent comparison (HashMap iteration order is non-deterministic)
        output1["agents"] = sorted(output1["agents"], key=lambda x: x["id"])
        output2["agents"] = sorted(output2["agents"], key=lambda x: x["id"])

        # Compare simulation results (excluding performance metrics which depend on wall-clock time)
        assert output1["metrics"] == output2["metrics"]
        assert output1["agents"] == output2["agents"]
        assert output1["costs"] == output2["costs"]
        assert output1["simulation"]["seed"] == output2["simulation"]["seed"]
        assert output1["simulation"]["ticks_executed"] == output2["simulation"]["ticks_executed"]

    def test_invalid_config(self, tmp_path):
        """Test error handling for invalid config."""
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("invalid: yaml: : :")

        result = run_cli(["run", "--config", str(bad_config)], check=False)
        assert result.returncode != 0
        assert "Error" in result.stderr

    def test_verbose_mode(self, test_config):
        """Test verbose mode shows detailed events."""
        result = run_cli(["run", "--config", str(test_config), "--verbose", "--ticks", "5"])
        assert result.returncode == 0

        # Verbose mode does NOT output JSON - it only shows verbose stderr logs
        # The stdout will be empty or minimal in verbose mode

        # Verify verbose logs on stderr
        assert "═══ Tick" in result.stderr  # Tick separators
        assert "Summary:" in result.stderr  # Tick summaries
        # May or may not have arrivals/settlements depending on RNG

        # Verify configuration was loaded
        assert "Creating simulation" in result.stderr


class TestAIIntegration:
    """Test patterns for AI integration."""

    def test_jq_compatibility(self, test_config):
        """Test that output can be piped to jq."""
        import os
        import sys

        # Use the venv's payment-sim if it exists
        venv_bin = Path(sys.prefix) / "bin" / "payment-sim"
        if venv_bin.exists():
            cli_cmd = str(venv_bin)
        else:
            cli_cmd = "payment-sim"

        # Set PYTHONPATH for subprocess
        env = os.environ.copy()
        api_dir = str(Path(__file__).parent.parent)
        current_pythonpath = env.get('PYTHONPATH', '')
        if current_pythonpath:
            env['PYTHONPATH'] = f"{api_dir}:{current_pythonpath}"
        else:
            env['PYTHONPATH'] = api_dir

        # Run with quiet mode for clean JSON
        result = subprocess.run(
            f"{cli_cmd} run --config {test_config} --quiet | jq -r '.metrics.settlement_rate'",
            shell=True,
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        # Output should be a number (0.0 in this case since no transactions)
        assert result.stdout.strip() == "0.0"

    def test_parameter_sweep(self, test_config):
        """Test parameter sweep pattern for optimization."""
        seeds = [42, 123, 456]
        results = []

        for seed in seeds:
            result = run_cli(["run", "--config", str(test_config), "--seed", str(seed), "--quiet"])
            output = json.loads(result.stdout)
            results.append(output["performance"]["ticks_per_second"])

        # All results should be positive numbers
        assert all(tps > 0 for tps in results)

    def test_streaming_real_time_monitoring(self, test_config):
        """Test streaming mode for real-time monitoring."""
        import os

        # Set PYTHONPATH for subprocess
        env = os.environ.copy()
        api_dir = str(Path(__file__).parent.parent)
        current_pythonpath = env.get('PYTHONPATH', '')
        if current_pythonpath:
            env['PYTHONPATH'] = f"{api_dir}:{current_pythonpath}"
        else:
            env['PYTHONPATH'] = api_dir

        # Use subprocess.Popen to simulate streaming
        proc = subprocess.Popen(
            ["uv", "run", "payment-sim", "run", "--config", str(test_config), "--stream", "--quiet"],
            stdout=subprocess.PIPE,
            text=True,
            env=env,
            cwd=api_dir,
        )

        # Read first 3 ticks
        ticks_seen = []
        for _ in range(3):
            line = proc.stdout.readline()
            tick_data = json.loads(line)
            ticks_seen.append(tick_data["tick"])

        proc.kill()

        # Should see ticks 0, 1, 2
        assert ticks_seen == [0, 1, 2]
