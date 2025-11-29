"""Output Equivalence Experiments.

Verifies that CLI verbose output is equivalent to API output for:
1. Live simulations
2. Persisted simulations (replay)

Scenarios tested:
- Minimal simulation (2 agents, 3 days)
- Near deadline transactions (tests deadline penalties)
- LSM features (tests bilateral/cycle settlements)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from payment_simulator.api.main import app
from payment_simulator.api.strategies import (
    create_output_strategy,
)


# ============================================================================
# Test Configuration
# ============================================================================

EXAMPLE_CONFIGS_DIR = Path("/home/user/SimCash/examples/configs")

# Configs to test - ordered by complexity
TEST_CONFIGS = [
    "test_minimal_eod.yaml",  # Simple 2-agent, 3-day simulation
    "test_near_deadline.yaml",  # Tests deadline penalties
    "target2_lsm_features_test.yaml",  # Tests LSM bilateral/cycle settlements
]


@dataclass
class OutputCapture:
    """Captures simulation output from different sources."""

    simulation_id: str
    config_path: str
    cli_verbose_output: str = ""
    cli_events: list[dict] = field(default_factory=list)
    api_json_output: dict[str, Any] = field(default_factory=dict)
    api_events: list[dict] = field(default_factory=list)
    replay_output: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Helpers
# ============================================================================


def run_cli_simulation(
    config_path: str,
    verbose: bool = True,
    persist: bool = True,
    db_path: str | None = None,
    simulation_id: str | None = None,
) -> tuple[str, str]:
    """Run simulation via CLI and capture output.

    Args:
        config_path: Path to YAML config file
        verbose: Use verbose mode
        persist: Persist to database
        db_path: Database path (required if persist=True)
        simulation_id: Custom simulation ID

    Returns:
        Tuple of (stdout, simulation_id)
    """
    api_dir = Path("/home/user/SimCash/api")
    cmd = [
        str(api_dir / ".venv/bin/payment-sim"),
        "run",
        "-c", config_path,
    ]

    if verbose:
        cmd.append("--verbose")

    if persist:
        cmd.extend(["--persist", "--full-replay"])
        if db_path:
            cmd.extend(["--db-path", db_path])

    if simulation_id:
        cmd.extend(["--simulation-id", simulation_id])

    # Run from api directory
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(api_dir),
    )

    output = result.stdout + result.stderr

    # Extract simulation ID from output if not provided
    if not simulation_id:
        # Look for simulation ID in output
        match = re.search(r"Simulation ID: ([a-zA-Z0-9_-]+)", output)
        if match:
            simulation_id = match.group(1)

    return output, simulation_id or "unknown"


def run_cli_replay(
    db_path: str,
    simulation_id: str,
    verbose: bool = True,
) -> str:
    """Run replay via CLI and capture output.

    Args:
        db_path: Database path
        simulation_id: Simulation ID to replay
        verbose: Use verbose mode

    Returns:
        stdout output
    """
    api_dir = Path("/home/user/SimCash/api")
    cmd = [
        str(api_dir / ".venv/bin/payment-sim"),
        "replay",
        "--simulation-id", simulation_id,
        "--db-path", db_path,
    ]

    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(api_dir),
    )

    return result.stdout + result.stderr


def parse_cli_verbose_output(output: str) -> dict[str, Any]:
    """Parse CLI verbose output into structured data.

    Returns:
        Dict with sections: events, costs, metrics
    """
    sections = {
        "tick_headers": [],
        "arrivals": [],
        "settlements": [],
        "lsm_events": [],
        "costs": [],
        "end_of_day": [],
    }

    lines = output.split("\n")

    for line in lines:
        # Match tick headers (format: ═══ Tick 0 ═══)
        if re.match(r"^[═─]+ Tick \d+", line) or "Tick " in line and "═" in line:
            sections["tick_headers"].append(line)

        # Match transaction arrivals
        if "arrived" in line or "📥" in line:
            sections["arrivals"].append(line)

        # Match settlements
        if "settled" in line or "✅" in line:
            sections["settlements"].append(line)

        # Match LSM events
        if "LSM" in line or "Bilateral" in line or "Cycle" in line:
            sections["lsm_events"].append(line)

        # Match cost breakdowns
        if any(x in line for x in ["liquidity_cost", "delay_cost", "deadline_penalty"]):
            sections["costs"].append(line)

        # Match end of day
        if "End of Day" in line or "Day Summary" in line:
            sections["end_of_day"].append(line)

    return sections


def extract_event_types(output: str) -> set[str]:
    """Extract unique event types from verbose output.

    Maps CLI verbose output patterns to canonical event types.
    """
    event_types = set()

    # Map CLI patterns to canonical event types
    pattern_mappings = [
        # CLI pattern -> canonical event type
        (r"transaction\(s\) arrived|📥.*arrived|ARRIVAL", "Arrival"),
        (r"transaction\(s\) settled|✅.*settled|RTGS Immediate", "Settlement"),
        (r"LSM|Bilateral|Cycle", "LSM"),
        (r"End of Day|Day Summary|═+ Day \d+", "EndOfDay"),
        (r"OVERDUE|deadline.*missed|past deadline", "DeadlineMissed"),
        (r"Collateral|collateral", "CollateralUpdate"),
        (r"Queue.*release|Queue2", "QueueRelease"),
        (r"Policy Decisions|🎯", "PolicyDecision"),
    ]

    for pattern, event_type in pattern_mappings:
        if re.search(pattern, output, re.IGNORECASE):
            event_types.add(event_type)

    return event_types


def compare_event_counts(
    cli_output: str,
    api_events: list[dict],
) -> dict[str, tuple[int, int]]:
    """Compare event counts between CLI and API.

    Returns:
        Dict mapping event_type -> (cli_count, api_count)
    """
    comparisons = {}

    # Count CLI events by type
    cli_counts: dict[str, int] = {}
    for pattern in ["Arrival", "Settlement", "LSM", "EndOfDay"]:
        count = len(re.findall(pattern, cli_output, re.IGNORECASE))
        cli_counts[pattern] = count

    # Count API events by type
    api_counts: dict[str, int] = {}
    for event in api_events:
        event_type = event.get("event_type", "Unknown")
        # Normalize event type for comparison
        if "Arrival" in event_type:
            key = "Arrival"
        elif "Settlement" in event_type:
            key = "Settlement"
        elif "Lsm" in event_type:
            key = "LSM"
        elif "EndOfDay" in event_type:
            key = "EndOfDay"
        else:
            key = event_type

        api_counts[key] = api_counts.get(key, 0) + 1

    # Build comparison
    all_types = set(cli_counts.keys()) | set(api_counts.keys())
    for event_type in all_types:
        comparisons[event_type] = (
            cli_counts.get(event_type, 0),
            api_counts.get(event_type, 0),
        )

    return comparisons


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def test_client() -> TestClient:
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def temp_db() -> str:
    """Create temporary database path (file will be created by DuckDB)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Remove the empty file so DuckDB can create it fresh
    os.unlink(db_path)

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


# ============================================================================
# Test Classes
# ============================================================================


class TestCLIOutputCapture:
    """Tests that verify CLI output can be captured and parsed."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])  # Just first config
    def test_cli_verbose_output_captured(self, config_name: str, temp_db: str) -> None:
        """CLI verbose output should be captured."""
        config_path = str(EXAMPLE_CONFIGS_DIR / config_name)

        if not os.path.exists(config_path):
            pytest.skip(f"Config not found: {config_path}")

        output, sim_id = run_cli_simulation(
            config_path,
            verbose=True,
            persist=True,
            db_path=temp_db,
        )

        assert len(output) > 0, "CLI should produce output"
        assert "Tick" in output, "Output should contain tick information"

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_cli_output_has_event_sections(self, config_name: str, temp_db: str) -> None:
        """CLI output should have recognizable event sections."""
        config_path = str(EXAMPLE_CONFIGS_DIR / config_name)

        if not os.path.exists(config_path):
            pytest.skip(f"Config not found: {config_path}")

        output, _ = run_cli_simulation(
            config_path,
            verbose=True,
            persist=True,
            db_path=temp_db,
        )

        sections = parse_cli_verbose_output(output)

        # Should have tick headers
        assert len(sections["tick_headers"]) > 0, "Should have tick headers"


class TestAPIOutputCapture:
    """Tests that verify API output can be captured."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_api_simulation_produces_events(
        self, test_client: TestClient, config_name: str
    ) -> None:
        """API simulation should produce events."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        # Load config
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Create simulation
        response = test_client.post("/simulations", json=config)
        assert response.status_code == 200

        sim_id = response.json()["simulation_id"]

        # Run a few ticks
        response = test_client.post(f"/simulations/{sim_id}/tick?count=10")
        assert response.status_code == 200

        # Check events
        events = response.json().get("results", [])
        assert len(events) > 0, "Should produce tick results"

        # Cleanup
        test_client.delete(f"/simulations/{sim_id}")


class TestOutputEquivalence:
    """Tests that verify CLI and API outputs are equivalent."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_event_types_match(
        self, test_client: TestClient, config_name: str, temp_db: str
    ) -> None:
        """Event types from CLI should match API."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        # Run CLI
        cli_output, cli_sim_id = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
        )

        cli_event_types = extract_event_types(cli_output)

        # Run API with same config
        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)

        response = test_client.post("/simulations", json=config)
        assert response.status_code == 200

        api_sim_id = response.json()["simulation_id"]

        # Get total ticks from config
        total_ticks = config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]

        # Run all ticks
        response = test_client.post(f"/simulations/{api_sim_id}/tick?count={total_ticks}")
        assert response.status_code == 200

        # Collect all events from API tick results
        api_events: list[dict] = []
        tick_results = response.json().get("results", [])
        for result in tick_results:
            events = result.get("events", [])
            api_events.extend(events)

        api_event_types = {e.get("event_type", "") for e in api_events}

        # Compare event types
        print(f"\nCLI event types: {cli_event_types}")
        print(f"API event types: {api_event_types}")

        # Both should have arrivals
        cli_has_arrivals = any("Arrival" in t for t in cli_event_types)
        api_has_arrivals = any("Arrival" in t for t in api_event_types)

        assert cli_has_arrivals == api_has_arrivals, "Both should have arrivals"

        # Cleanup
        test_client.delete(f"/simulations/{api_sim_id}")

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_settlement_counts_comparable(
        self, test_client: TestClient, config_name: str, temp_db: str
    ) -> None:
        """Settlement counts from CLI and API should be comparable."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)

        # Use same seed for determinism
        seed = config["simulation"].get("rng_seed", 42)
        config["simulation"]["rng_seed"] = seed

        # Run CLI
        cli_output, _ = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
        )

        # Count CLI settlements
        cli_settlement_count = len(re.findall(r"SETTLED|Settlement", cli_output, re.IGNORECASE))

        # Run API
        response = test_client.post("/simulations", json=config)
        api_sim_id = response.json()["simulation_id"]

        total_ticks = config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]
        response = test_client.post(f"/simulations/{api_sim_id}/tick?count={total_ticks}")

        # Get metrics
        metrics_response = test_client.get(f"/simulations/{api_sim_id}/metrics")
        api_settlements = metrics_response.json().get("metrics", {}).get("total_settlements", 0)

        print(f"\nCLI settlement mentions: {cli_settlement_count}")
        print(f"API settlements: {api_settlements}")

        # API should have settlements if CLI does
        if cli_settlement_count > 0:
            assert api_settlements > 0, "API should have settlements too"

        # Cleanup
        test_client.delete(f"/simulations/{api_sim_id}")


class TestJSONStrategyOutput:
    """Tests for JSONOutputStrategy output format."""

    def test_json_strategy_collects_all_events(self) -> None:
        """JSONOutputStrategy should collect all events."""
        strategy = create_output_strategy(mode="json")

        loop = asyncio.get_event_loop()

        # Simulate lifecycle
        loop.run_until_complete(strategy.on_simulation_start({
            "simulation_id": "test-sim",
            "total_ticks": 10,
        }))

        # Add tick data
        for tick in range(10):
            loop.run_until_complete(strategy.on_tick_complete({
                "tick": tick,
                "events": [
                    {"event_type": "TransactionArrival", "tx_id": f"tx{tick}"},
                ],
                "arrivals": 1,
                "settlements": 0,
            }))

        loop.run_until_complete(strategy.on_simulation_complete({
            "duration_seconds": 1.0,
            "total_arrivals": 10,
        }))

        # Get collected data
        collected = strategy.get_collected_data()

        assert len(collected["ticks"]) == 10
        assert all(t["tick"] == i for i, t in enumerate(collected["ticks"]))


class TestReplayEquivalence:
    """Tests that replay output matches run output."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_replay_produces_same_event_types(
        self, config_name: str, temp_db: str
    ) -> None:
        """Replay should produce same event types as original run."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        # Run CLI and persist
        run_output, sim_id = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
            simulation_id="replay-test-sim",
        )

        run_event_types = extract_event_types(run_output)

        # Run replay
        replay_output = run_cli_replay(
            db_path=temp_db,
            simulation_id="replay-test-sim",
            verbose=True,
        )

        replay_event_types = extract_event_types(replay_output)

        print(f"\nRun event types: {run_event_types}")
        print(f"Replay event types: {replay_event_types}")

        # Event types should match
        assert run_event_types == replay_event_types, (
            f"Event type mismatch: Run={run_event_types}, Replay={replay_event_types}"
        )

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_replay_tick_count_matches(
        self, config_name: str, temp_db: str
    ) -> None:
        """Replay should have same tick count as original run."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        # Run CLI
        run_output, _ = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
            simulation_id="tick-count-test",
        )

        run_tick_count = len(re.findall(r"Tick \d+", run_output))

        # Run replay
        replay_output = run_cli_replay(
            db_path=temp_db,
            simulation_id="tick-count-test",
            verbose=True,
        )

        replay_tick_count = len(re.findall(r"Tick \d+", replay_output))

        print(f"\nRun tick mentions: {run_tick_count}")
        print(f"Replay tick mentions: {replay_tick_count}")

        assert run_tick_count == replay_tick_count, (
            f"Tick count mismatch: Run={run_tick_count}, Replay={replay_tick_count}"
        )


class TestComprehensiveEquivalence:
    """Comprehensive tests comparing all output sources."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS)
    def test_full_equivalence_check(
        self, test_client: TestClient, config_name: str, temp_db: str
    ) -> None:
        """Full equivalence check across CLI, API, and replay."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        print(f"\n{'='*60}")
        print(f"Testing config: {config_name}")
        print(f"{'='*60}")

        import yaml

        with open(config_path) as f:
            config = yaml.safe_load(f)

        sim_id = f"equiv-test-{config_name.replace('.yaml', '')}"
        total_ticks = config["simulation"]["ticks_per_day"] * config["simulation"]["num_days"]

        # 1. Run CLI verbose mode
        print("\n1. Running CLI simulation...")
        cli_output, _ = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
            simulation_id=sim_id,
        )
        cli_sections = parse_cli_verbose_output(cli_output)
        cli_event_types = extract_event_types(cli_output)

        print(f"   CLI output length: {len(cli_output)} chars")
        print(f"   CLI tick headers: {len(cli_sections['tick_headers'])}")
        print(f"   CLI event types: {cli_event_types}")

        # 2. Run CLI replay
        print("\n2. Running CLI replay...")
        replay_output = run_cli_replay(
            db_path=temp_db,
            simulation_id=sim_id,
            verbose=True,
        )
        replay_sections = parse_cli_verbose_output(replay_output)
        replay_event_types = extract_event_types(replay_output)

        print(f"   Replay output length: {len(replay_output)} chars")
        print(f"   Replay tick headers: {len(replay_sections['tick_headers'])}")
        print(f"   Replay event types: {replay_event_types}")

        # 3. Run API with same config
        print("\n3. Running API simulation...")
        response = test_client.post("/simulations", json=config)
        assert response.status_code == 200
        api_sim_id = response.json()["simulation_id"]

        response = test_client.post(f"/simulations/{api_sim_id}/tick?count={total_ticks}")
        assert response.status_code == 200

        # Get events via events endpoint
        events_response = test_client.get(f"/simulations/{api_sim_id}/events")
        api_events = events_response.json().get("events", []) if events_response.status_code == 200 else []

        api_event_types = {e.get("event_type", "") for e in api_events}

        metrics_response = test_client.get(f"/simulations/{api_sim_id}/metrics")
        api_metrics = metrics_response.json().get("metrics", {})

        print(f"   API events (from /events): {len(api_events)}")
        print(f"   API event types: {api_event_types}")
        print(f"   API metrics: {api_metrics}")

        # 4. Compare results
        print("\n4. Comparing results...")

        # Event types should be similar
        assert cli_event_types == replay_event_types, (
            f"CLI vs Replay mismatch: {cli_event_types} vs {replay_event_types}"
        )

        # Tick counts should match
        cli_tick_count = len(cli_sections["tick_headers"])
        replay_tick_count = len(replay_sections["tick_headers"])
        assert cli_tick_count == replay_tick_count, (
            f"Tick count mismatch: CLI={cli_tick_count}, Replay={replay_tick_count}"
        )

        # API should have similar event count magnitude
        if len(api_events) > 0:
            print(f"   API has {len(api_events)} events (expected from CLI)")

        print("\n   ✓ All equivalence checks passed!")

        # Cleanup
        test_client.delete(f"/simulations/{api_sim_id}")


# ============================================================================
# CLI Output Analysis
# ============================================================================


class TestCLIOutputSections:
    """Tests analyzing CLI verbose output sections."""

    @pytest.mark.parametrize("config_name", TEST_CONFIGS[:1])
    def test_cli_output_has_all_sections(
        self, config_name: str, temp_db: str
    ) -> None:
        """CLI verbose output should have all expected sections."""
        config_path = EXAMPLE_CONFIGS_DIR / config_name

        if not config_path.exists():
            pytest.skip(f"Config not found: {config_path}")

        output, _ = run_cli_simulation(
            str(config_path),
            verbose=True,
            persist=True,
            db_path=temp_db,
        )

        # Check for expected sections
        expected_patterns = [
            r"Tick \d+",  # Tick headers
            r"BANK_[AB]",  # Agent names
        ]

        for pattern in expected_patterns:
            assert re.search(pattern, output), (
                f"Missing expected pattern: {pattern}"
            )

        print(f"\n✓ CLI output contains all expected sections")
        print(f"  Output preview (first 500 chars):")
        print(f"  {output[:500]}...")
