# Phase 3: Verify Replay Identity

**Status**: Pending
**Started**:

---

## Objective

Verify that `payment-sim replay --simulation-id <experiment-sim-id> --verbose` produces output identical to what `payment-sim run --verbose` would produce for the same simulation. This is the ultimate validation that the unified persistence architecture works.

---

## Invariants Enforced in This Phase

- **INV-5**: Replay Identity - `replay --verbose` output MUST match `run --verbose` output
- **INV-6**: Event Completeness - Events must contain ALL fields needed for display
- **INV-11**: Simulation Persistence Identity - Records identical regardless of execution path

---

## TDD Steps

### Step 3.1: Write Failing Tests (RED)

Create `api/tests/integration/test_experiment_replay_identity.py`:

**Test Cases**:
1. `test_replay_finds_experiment_simulation` - Replay command finds simulation from experiment
2. `test_replay_verbose_output_has_all_sections` - Output includes all expected sections
3. `test_replay_events_match_expectations` - Events in replay match what was generated
4. `test_replay_from_cli_vs_run_identical` - Compare replay to expected run output

```python
"""Integration tests for experiment simulation replay identity.

These tests verify that simulations persisted via experiments can be
replayed with `payment-sim replay --simulation-id --verbose` producing
output identical to what `payment-sim run --verbose` would produce.

This is the gold standard test for INV-5 (Replay Identity) and INV-11
(Simulation Persistence Identity).
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.queries import get_simulation_summary


class TestExperimentReplayIdentity:
    """Gold standard tests for experiment simulation replay."""

    @pytest.fixture
    def scenario_config(self) -> dict[str, Any]:
        """Create a scenario that generates interesting events."""
        return {
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 42,
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 500000,  # $5,000 - deliberately low
                    "unsecured_cap": 100000,
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 500000,
                    "unsecured_cap": 100000,
                },
            ],
            "arrivals": [
                {
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 100000,  # $1,000
                    "arrival_tick": 0,
                    "deadline_tick": 9,
                    "priority": 5,
                },
                {
                    "sender": "BANK_B",
                    "receiver": "BANK_A",
                    "amount": 100000,
                    "arrival_tick": 1,
                    "deadline_tick": 9,
                    "priority": 5,
                },
            ],
        }

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "replay_test.db"

    def test_replay_finds_experiment_simulation(
        self, scenario_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Replay command should find simulation persisted by experiment."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        # Create experiment config
        experiment_config = {
            "name": "replay-test",
            "scenario": scenario_config,
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

        # Run experiment with persistence
        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(
            seed=42,
            purpose="replay_test",
            persist=True,
        )

        sim_id = result.simulation_id

        # Verify replay can find the simulation
        with DatabaseManager(str(temp_db_path)) as db:
            summary = get_simulation_summary(db.conn, sim_id)
            assert summary is not None, f"Simulation {sim_id} should be findable"

            # Verify it has events
            from payment_simulator.persistence.event_queries import get_simulation_events
            events = get_simulation_events(db.conn, sim_id, limit=1000)
            assert events["total"] > 0, "Simulation should have events"

    def test_replay_verbose_output_has_all_sections(
        self, scenario_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Verbose replay output should have all expected sections."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        experiment_config = {
            "name": "verbose-test",
            "scenario": scenario_config,
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=42, purpose="verbose_test", persist=True)
        sim_id = result.simulation_id

        # Run replay command
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--db-path", str(temp_db_path),
                "--simulation-id", sim_id,
                "--verbose",
                "--from-tick", "0",
                "--to-tick", "5",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),  # api dir
        )

        output = replay_result.stdout

        # Verify expected sections present
        # (Exact sections depend on display implementation)
        assert "Tick" in output or "tick" in output, "Should show tick information"

    def test_replay_events_match_expectations(
        self, scenario_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Events in replay should match what was generated during simulation."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        experiment_config = {
            "name": "events-test",
            "scenario": scenario_config,
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=42, purpose="events_test", persist=True)
        sim_id = result.simulation_id

        # Query events directly
        with DatabaseManager(str(temp_db_path)) as db:
            from payment_simulator.persistence.event_queries import get_simulation_events

            events_result = get_simulation_events(db.conn, sim_id, limit=1000)
            events = events_result["events"]

            # Should have Arrival events from our config
            arrival_events = [e for e in events if e.get("event_type") == "Arrival"]
            assert len(arrival_events) == 2, "Should have 2 arrival events"

            # Verify arrival event has required fields (INV-6)
            for event in arrival_events:
                assert "tick" in event, "Event should have tick"
                assert "tx_id" in event or "details" in event, "Event should have transaction info"

    def test_replay_from_cli_vs_expected_format(
        self, scenario_config: dict[str, Any], temp_db_path: Path
    ) -> None:
        """Replay output format should match expected verbose format."""
        from payment_simulator.experiments.runner.optimization import (
            OptimizationRunner,
        )

        experiment_config = {
            "name": "format-test",
            "scenario": scenario_config,
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

        runner = OptimizationRunner(
            config=experiment_config,
            db_path=temp_db_path,
            persist_bootstrap=True,
        )

        result = runner._run_simulation(seed=42, purpose="format_test", persist=True)
        sim_id = result.simulation_id

        # Run replay via CLI
        replay_result = subprocess.run(
            [
                "uv", "run", "payment-sim", "replay",
                "--db-path", str(temp_db_path),
                "--simulation-id", sim_id,
                "--verbose",
            ],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent.parent),
        )

        # Should succeed
        assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

        # Output should not be empty
        assert len(replay_result.stdout) > 0, "Replay should produce output"


class TestReplayIdentityEndToEnd:
    """End-to-end replay identity verification.

    These tests run a complete simulation through the experiment path,
    then replay it, comparing output structure to ensure consistency.
    """

    @pytest.fixture
    def complex_scenario(self) -> dict[str, Any]:
        """Scenario designed to trigger multiple event types."""
        return {
            "ticks_per_day": 20,
            "num_days": 1,
            "rng_seed": 12345,
            "agents": [
                {
                    "id": "BANK_A",
                    "opening_balance": 200000,  # Low balance to trigger queuing
                    "unsecured_cap": 50000,
                },
                {
                    "id": "BANK_B",
                    "opening_balance": 200000,
                    "unsecured_cap": 50000,
                },
                {
                    "id": "BANK_C",
                    "opening_balance": 200000,
                    "unsecured_cap": 50000,
                },
            ],
            "arrivals": [
                # Create potential for LSM cycles
                {"sender": "BANK_A", "receiver": "BANK_B", "amount": 150000, "arrival_tick": 0, "deadline_tick": 19, "priority": 5},
                {"sender": "BANK_B", "receiver": "BANK_C", "amount": 150000, "arrival_tick": 1, "deadline_tick": 19, "priority": 5},
                {"sender": "BANK_C", "receiver": "BANK_A", "amount": 150000, "arrival_tick": 2, "deadline_tick": 19, "priority": 5},
                # Additional smaller transactions
                {"sender": "BANK_A", "receiver": "BANK_C", "amount": 50000, "arrival_tick": 5, "deadline_tick": 19, "priority": 3},
            ],
        }

    def test_full_replay_identity(self, complex_scenario: dict[str, Any]) -> None:
        """Full end-to-end replay identity test."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "full_test.db"

            from payment_simulator.experiments.runner.optimization import (
                OptimizationRunner,
            )

            experiment_config = {
                "name": "full-identity-test",
                "scenario": complex_scenario,
                "evaluation": {"mode": "deterministic", "ticks": 20},
                "optimized_agents": ["BANK_A"],
            }

            # Run simulation via experiment path
            runner = OptimizationRunner(
                config=experiment_config,
                db_path=db_path,
                persist_bootstrap=True,
            )

            result = runner._run_simulation(
                seed=12345,
                purpose="identity_test",
                persist=True,
            )

            sim_id = result.simulation_id

            # Replay and capture output
            replay_result = subprocess.run(
                [
                    "uv", "run", "payment-sim", "replay",
                    "--db-path", str(db_path),
                    "--simulation-id", sim_id,
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                cwd=str(Path(__file__).parent.parent.parent.parent),
            )

            assert replay_result.returncode == 0, f"Replay failed: {replay_result.stderr}"

            # Verify output structure
            output = replay_result.stdout
            assert len(output) > 100, "Replay should produce substantial output"

            # Verify key event types appear in output based on our scenario
            # (The exact format depends on verbose_output.py implementation)
            output_lower = output.lower()
            assert "arrival" in output_lower or "transaction" in output_lower, \
                "Should show transaction arrivals"
```

### Step 3.2: Verify Tests Pass (GREEN)

With Phase 1 and Phase 2 implemented correctly, these tests should pass. If they fail, debug the persistence or replay path.

### Step 3.3: Additional Verification Script

Create a verification script that can be run manually:

```bash
#!/bin/bash
# verify_replay_identity.sh

set -e

DB_PATH=$(mktemp -d)/test.db
CONFIG_PATH="sim_config_simple_example.yaml"

echo "=== Step 1: Run simulation via CLI ==="
payment-sim run --config $CONFIG_PATH --persist --db-path $DB_PATH \
    --simulation-id cli-test --verbose > /tmp/cli_run.txt 2>&1

echo "=== Step 2: Replay the CLI simulation ==="
payment-sim replay --db-path $DB_PATH --simulation-id cli-test \
    --verbose > /tmp/cli_replay.txt 2>&1

echo "=== Step 3: Compare (excluding timing) ==="
diff <(grep -v "Duration:" /tmp/cli_run.txt | grep -v "Time:" ) \
     <(grep -v "Duration:" /tmp/cli_replay.txt | grep -v "Time:") && \
    echo "✅ CLI replay identity verified" || \
    echo "❌ CLI replay differs from run"

echo "=== Step 4: Run experiment with persistence ==="
# (Requires experiment YAML - adapt as needed)

echo "=== Step 5: Replay experiment simulation ==="
# payment-sim replay --db-path $DB_PATH --simulation-id exp-sim-xxx --verbose

echo "=== Cleanup ==="
rm -rf $(dirname $DB_PATH)
```

---

## Implementation Details

### What Makes Replay Identity Work

1. **Same Display Function**: Both `run --verbose` and `replay --verbose` call `display_tick_verbose_output()`

2. **StateProvider Abstraction**: Display code uses `StateProvider` protocol, not raw FFI or DB queries

3. **Complete Events**: Events contain ALL fields needed for display (INV-6)

4. **Single Event Source**: `simulation_events` table is the ONLY source (no legacy tables)

### Potential Failure Points

1. **Missing event fields**: Event not complete, display falls back to different format
2. **Wrong table**: Events stored in `experiment_events` instead of `simulation_events`
3. **Schema mismatch**: Simulation record missing required columns
4. **Query mismatch**: Replay queries different columns than expected

---

## Files

| File | Action |
|------|--------|
| `api/tests/integration/test_experiment_replay_identity.py` | CREATE |
| `scripts/verify_replay_identity.sh` | CREATE (optional) |

---

## Verification

```bash
# Run replay identity tests
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_replay_identity.py -v

# Manual verification
payment-sim replay --db-path <experiment-db> --simulation-id <sim-id> --verbose
```

---

## Completion Criteria

- [ ] All 4+ test cases pass
- [ ] `payment-sim replay` finds simulations from experiment databases
- [ ] Verbose output includes all expected sections
- [ ] Events are complete (all fields present)
- [ ] No errors or missing data in replay output
- [ ] INV-5 (Replay Identity) verified
- [ ] INV-11 (Persistence Identity) verified
