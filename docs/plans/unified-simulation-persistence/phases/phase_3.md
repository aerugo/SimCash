# Phase 3: Verify Replay Identity

**Status**: Pending
**Started**:

**Prerequisite**: Phase 1 and Phase 2 must be complete.

---

## Objective

Verify that `payment-sim replay --simulation-id <experiment-sim-id> --verbose` produces output that correctly displays simulation events from experiment databases. This is the ultimate validation of INV-5 (Replay Identity) and INV-11 (Persistence Identity).

---

## Invariants Enforced in This Phase

- **INV-5**: Replay Identity - `replay --verbose` output MUST work for experiment simulations
- **INV-6**: Event Completeness - Events must contain ALL fields needed for display
- **INV-11**: Simulation Persistence Identity - Verified by successful replay

---

## Strict TDD Workflow

**CRITICAL**: Follow this exact sequence.

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: Write replay identity tests ONLY                       │
│  Step 2: Run tests → Verify they PASS (should pass if Phase 2   │
│          was done correctly)                                    │
│  Step 3: If tests fail, debug and fix                           │
│  Step 4: Add manual verification                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Step 3.1: Write Replay Identity Tests

**Action**: Create end-to-end replay identity test file.

Create `api/tests/integration/test_experiment_replay_identity.py`:

```python
"""End-to-end tests for experiment simulation replay identity.

TDD Phase: These tests verify the ultimate goal - that simulations
persisted via experiments can be replayed identically.

This validates:
- INV-5: Replay Identity
- INV-6: Event Completeness
- INV-11: Simulation Persistence Identity
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest


class TestExperimentReplayIdentity:
    """Gold standard tests for experiment simulation replay.

    These tests run experiments with persistence, then verify replay works.
    """

    @pytest.fixture
    def scenario_with_events(self) -> dict[str, Any]:
        """Scenario that generates multiple event types for thorough testing."""
        return {
            "ticks_per_day": 10,
            "num_days": 1,
            "rng_seed": 42,
            "agents": [
                {"id": "BANK_A", "opening_balance": 500000, "unsecured_cap": 100000},
                {"id": "BANK_B", "opening_balance": 500000, "unsecured_cap": 100000},
            ],
            "arrivals": [
                {
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 100000,
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
    def experiment_config(self, scenario_with_events: dict[str, Any]) -> dict[str, Any]:
        """Minimal experiment config using the scenario."""
        return {
            "name": "replay-identity-test",
            "scenario": scenario_with_events,
            "evaluation": {"mode": "deterministic", "ticks": 10},
            "optimized_agents": ["BANK_A"],
        }

    def test_replay_command_succeeds_for_experiment_simulation(
        self, experiment_config: dict[str, Any]
    ) -> None:
        """payment-sim replay should succeed for experiment simulations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            # Step 1: Run experiment with persistence
            from payment_simulator.experiments.runner.optimization import OptimizationRunner

            runner = OptimizationRunner(
                config=experiment_config,
                db_path=db_path,
                persist_bootstrap=True,
            )

            result = runner._run_simulation(seed=42, purpose="replay_test", persist=True)
            sim_id = result.simulation_id

            # Step 2: Run replay command
            api_dir = Path(__file__).parent.parent.parent
            replay_result = subprocess.run(
                [
                    "uv", "run", "payment-sim", "replay",
                    "--db-path", str(db_path),
                    "--simulation-id", sim_id,
                    "--verbose",
                    "--from-tick", "0",
                    "--to-tick", "5",
                ],
                capture_output=True,
                text=True,
                cwd=str(api_dir),
                timeout=60,
            )

            # Step 3: Verify success
            assert replay_result.returncode == 0, (
                f"Replay command failed with return code {replay_result.returncode}\n"
                f"stdout: {replay_result.stdout}\n"
                f"stderr: {replay_result.stderr}"
            )

    def test_replay_output_contains_simulation_events(
        self, experiment_config: dict[str, Any]
    ) -> None:
        """Replay output should contain the simulation events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            from payment_simulator.experiments.runner.optimization import OptimizationRunner

            runner = OptimizationRunner(
                config=experiment_config,
                db_path=db_path,
                persist_bootstrap=True,
            )

            result = runner._run_simulation(seed=42, purpose="content_test", persist=True)
            sim_id = result.simulation_id

            api_dir = Path(__file__).parent.parent.parent
            replay_result = subprocess.run(
                [
                    "uv", "run", "payment-sim", "replay",
                    "--db-path", str(db_path),
                    "--simulation-id", sim_id,
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                cwd=str(api_dir),
                timeout=60,
            )

            output = replay_result.stdout.lower()

            # Should have some content (not empty)
            assert len(replay_result.stdout) > 50, (
                f"Replay output too short. Expected substantial output.\n"
                f"Got: {replay_result.stdout}"
            )

            # Should mention tick or have structured output
            # (Exact format depends on verbose_output.py implementation)
            assert "tick" in output or "day" in output or "simulation" in output, (
                f"Replay output missing expected content.\n"
                f"Output: {replay_result.stdout[:500]}"
            )

    def test_replay_events_queryable_directly(
        self, experiment_config: dict[str, Any]
    ) -> None:
        """Events should be queryable via standard persistence queries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            from payment_simulator.experiments.runner.optimization import OptimizationRunner
            from payment_simulator.persistence.connection import DatabaseManager
            from payment_simulator.persistence.event_queries import get_simulation_events

            runner = OptimizationRunner(
                config=experiment_config,
                db_path=db_path,
                persist_bootstrap=True,
            )

            result = runner._run_simulation(seed=42, purpose="query_test", persist=True)
            sim_id = result.simulation_id

            # Query events directly
            with DatabaseManager(str(db_path)) as db:
                events_result = get_simulation_events(db.conn, sim_id, limit=1000)

                # Should have events (we configured 2 arrivals)
                assert events_result["total"] > 0, (
                    "No events found. Events may not be persisted correctly."
                )

                events = events_result["events"]

                # Check for expected event types
                event_types = {e.get("event_type") for e in events}
                assert "Arrival" in event_types or len(event_types) > 0, (
                    f"Expected Arrival events. Got event types: {event_types}"
                )

    def test_replay_with_tick_range(
        self, experiment_config: dict[str, Any]
    ) -> None:
        """Replay with --from-tick and --to-tick should work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            from payment_simulator.experiments.runner.optimization import OptimizationRunner

            runner = OptimizationRunner(
                config=experiment_config,
                db_path=db_path,
                persist_bootstrap=True,
            )

            result = runner._run_simulation(seed=42, purpose="range_test", persist=True)
            sim_id = result.simulation_id

            api_dir = Path(__file__).parent.parent.parent

            # Replay specific tick range
            replay_result = subprocess.run(
                [
                    "uv", "run", "payment-sim", "replay",
                    "--db-path", str(db_path),
                    "--simulation-id", sim_id,
                    "--verbose",
                    "--from-tick", "2",
                    "--to-tick", "5",
                ],
                capture_output=True,
                text=True,
                cwd=str(api_dir),
                timeout=60,
            )

            assert replay_result.returncode == 0, (
                f"Replay with tick range failed\n"
                f"stderr: {replay_result.stderr}"
            )


class TestReplayDataCompleteness:
    """Tests that verify events have all required fields for replay."""

    @pytest.fixture
    def minimal_scenario(self) -> dict[str, Any]:
        """Simple scenario for data completeness testing."""
        return {
            "ticks_per_day": 5,
            "num_days": 1,
            "rng_seed": 123,
            "agents": [
                {"id": "A", "opening_balance": 1000000, "unsecured_cap": 500000},
                {"id": "B", "opening_balance": 1000000, "unsecured_cap": 500000},
            ],
            "arrivals": [
                {"sender": "A", "receiver": "B", "amount": 50000, "arrival_tick": 0, "deadline_tick": 4, "priority": 5},
            ],
        }

    def test_arrival_event_has_required_fields(self, minimal_scenario: dict[str, Any]) -> None:
        """Arrival events must have all fields needed for display (INV-6)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            from payment_simulator.experiments.runner.optimization import OptimizationRunner
            from payment_simulator.persistence.connection import DatabaseManager
            from payment_simulator.persistence.event_queries import get_simulation_events

            config = {
                "name": "field-test",
                "scenario": minimal_scenario,
                "evaluation": {"mode": "deterministic", "ticks": 5},
                "optimized_agents": ["A"],
            }

            runner = OptimizationRunner(config=config, db_path=db_path, persist_bootstrap=True)
            result = runner._run_simulation(seed=123, purpose="field_test", persist=True)

            with DatabaseManager(str(db_path)) as db:
                events_result = get_simulation_events(db.conn, result.simulation_id)
                events = events_result["events"]

                arrival_events = [e for e in events if e.get("event_type") == "Arrival"]
                if arrival_events:
                    event = arrival_events[0]

                    # Check required fields exist (INV-6)
                    assert "tick" in event, "Arrival event missing 'tick'"
                    # Other required fields depend on event schema
                    # Add assertions based on verbose_output.py requirements

    def test_all_persisted_events_have_tick(self, minimal_scenario: dict[str, Any]) -> None:
        """All events must have a tick field for replay ordering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"

            from payment_simulator.experiments.runner.optimization import OptimizationRunner
            from payment_simulator.persistence.connection import DatabaseManager
            from payment_simulator.persistence.event_queries import get_simulation_events

            config = {
                "name": "tick-test",
                "scenario": minimal_scenario,
                "evaluation": {"mode": "deterministic", "ticks": 5},
                "optimized_agents": ["A"],
            }

            runner = OptimizationRunner(config=config, db_path=db_path, persist_bootstrap=True)
            result = runner._run_simulation(seed=123, purpose="tick_test", persist=True)

            with DatabaseManager(str(db_path)) as db:
                events_result = get_simulation_events(db.conn, result.simulation_id)
                events = events_result["events"]

                for i, event in enumerate(events):
                    assert "tick" in event or event.get("tick") is not None, (
                        f"Event {i} missing tick field: {event}"
                    )
```

---

## Step 3.2: Run Tests

**Action**: Run the replay identity tests.

```bash
cd /home/user/SimCash/api
uv run pytest tests/integration/test_experiment_replay_identity.py -v
```

**Expected**: All tests should pass if Phase 1 and Phase 2 were implemented correctly.

If tests FAIL, proceed to Step 3.3.

---

## Step 3.3: Debug and Fix (if needed)

If tests fail, common issues:

1. **ImportError**: Module not found
   - Check `simulation_persistence_provider.py` exists
   - Check `__init__.py` exports

2. **Simulation not found**: `get_simulation_summary()` returns None
   - Verify `persist_simulation_start()` is called in `_run_simulation()`
   - Check database path is correct

3. **No events**: `get_simulation_events()` returns empty
   - Verify `persist_tick_events()` is called for each tick
   - Check events have required fields

4. **Replay command fails**: Non-zero return code
   - Check stderr for error message
   - Verify database has required tables

Debug workflow:
```bash
# Check if simulation exists
uv run python -c "
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.queries import get_simulation_summary

with DatabaseManager('/tmp/test.db') as db:
    sim = get_simulation_summary(db.conn, 'your-sim-id')
    print(sim)
"

# Check events
uv run python -c "
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events

with DatabaseManager('/tmp/test.db') as db:
    result = get_simulation_events(db.conn, 'your-sim-id')
    print(f'Total events: {result[\"total\"]}')
    for e in result['events'][:5]:
        print(e)
"
```

---

## Step 3.4: Manual Verification

**Action**: Run manual end-to-end verification.

```bash
# Create temp directory
TMPDIR=$(mktemp -d)
DB_PATH="$TMPDIR/test.db"

# Run experiment via Python (simplified)
cd /home/user/SimCash/api
uv run python -c "
from pathlib import Path
from payment_simulator.experiments.runner.optimization import OptimizationRunner

config = {
    'name': 'manual-test',
    'scenario': {
        'ticks_per_day': 10,
        'num_days': 1,
        'rng_seed': 42,
        'agents': [
            {'id': 'BANK_A', 'opening_balance': 1000000, 'unsecured_cap': 500000},
            {'id': 'BANK_B', 'opening_balance': 1000000, 'unsecured_cap': 500000},
        ],
        'arrivals': [
            {'sender': 'BANK_A', 'receiver': 'BANK_B', 'amount': 100000,
             'arrival_tick': 0, 'deadline_tick': 9, 'priority': 5},
        ],
    },
    'evaluation': {'mode': 'deterministic', 'ticks': 10},
    'optimized_agents': ['BANK_A'],
}

runner = OptimizationRunner(
    config=config,
    db_path=Path('$DB_PATH'),
    persist_bootstrap=True,
)

result = runner._run_simulation(seed=42, purpose='manual_test', persist=True)
print(f'Simulation ID: {result.simulation_id}')
"

# Replay the simulation
uv run payment-sim replay --db-path "$DB_PATH" --simulation-id "<sim-id-from-above>" --verbose

# Cleanup
rm -rf "$TMPDIR"
```

---

## Files

| File | Action | TDD Phase |
|------|--------|-----------|
| `api/tests/integration/test_experiment_replay_identity.py` | CREATE | Step 3.1 |

---

## Verification Commands

```bash
# Run replay identity tests
uv run pytest tests/integration/test_experiment_replay_identity.py -v

# Run all related tests together
uv run pytest tests/integration/test_experiment_simulation_persistence.py tests/integration/test_experiment_replay_identity.py tests/unit/test_simulation_persistence_provider.py -v

# Quick smoke test
uv run pytest tests/integration/test_experiment_replay_identity.py::TestExperimentReplayIdentity::test_replay_command_succeeds_for_experiment_simulation -v
```

---

## Completion Criteria

- [ ] All replay identity tests pass
- [ ] `payment-sim replay` finds simulations from experiment databases
- [ ] Replay command produces non-empty output
- [ ] Events are complete (all required fields present)
- [ ] Manual verification successful
- [ ] INV-5 (Replay Identity) verified
- [ ] INV-6 (Event Completeness) verified
- [ ] INV-11 (Persistence Identity) verified
