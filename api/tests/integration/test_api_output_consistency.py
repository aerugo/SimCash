"""API Output Consistency Tests.

Phase 0: Test Infrastructure for API-CLI-StateProvider consistency.

These tests verify that the API returns IDENTICAL data for:
1. Live simulations vs. persisted simulations
2. API responses vs. CLI output

TDD: These tests are written FIRST, will fail, and drive implementation.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from payment_simulator._core import Orchestrator
from payment_simulator.cli.execution.persistence import PersistenceManager
from payment_simulator.cli.execution.runner import SimulationConfig, SimulationRunner
from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider
from payment_simulator.cli.execution.strategies import QuietOutputStrategy
from payment_simulator.config.loader import SimulationConfig as PySimConfig
from payment_simulator.persistence.connection import DatabaseManager

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def api_config() -> dict[str, Any]:
    """API-style configuration (nested format used by API endpoints)."""
    return {
        "simulation": {
            "ticks_per_day": 50,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 500_000_00,  # $500k in cents
                "unsecured_cap": 200_000_00,
                "collateral_pledged": 50_000_00,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000_00,
                        "max": 50_000_00,
                    },
                    "counterparty_weights": {"BANK_B": 1.0},
                    "deadline_range": [10, 30],
                    "priority": 5,
                    "divisible": True,
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 500_000_00,
                "unsecured_cap": 200_000_00,
                "collateral_pledged": 50_000_00,
                "policy": {"type": "Fifo"},
                "arrival_config": {
                    "rate_per_tick": 0.5,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": 10_000_00,
                        "max": 50_000_00,
                    },
                    "counterparty_weights": {"BANK_A": 1.0},
                    "deadline_range": [10, 30],
                    "priority": 5,
                    "divisible": True,
                },
            },
        ],
        "costs": {
            "overdraft_bps_per_day": 100,
            "collateral_opportunity_bps_per_day": 50,
            "queue1_delay_per_tick": 100,
            "split_fee": 500,
            "deadline_base_penalty": 10_000,
            "deadline_penalty_per_tick": 1_000,
        },
    }


@pytest.fixture
def ffi_config(api_config: dict[str, Any]) -> dict[str, Any]:
    """Convert API config to FFI format."""
    sim_config = PySimConfig.from_dict(api_config)
    return sim_config.to_ffi_dict()


@pytest.fixture
def client() -> TestClient:
    """Create test client."""
    from payment_simulator.api.main import app

    return TestClient(app)


@pytest.fixture
def client_with_db(
    tmp_path: Path,
) -> Generator[tuple[TestClient, DatabaseManager], None, None]:
    """Create test client with database support."""
    from payment_simulator.api.main import app, manager

    # Create database
    db_path = tmp_path / "test_consistency.db"
    db_manager = DatabaseManager(str(db_path))
    db_manager.setup()

    # Set database manager
    manager.db_manager = db_manager

    yield TestClient(app), db_manager

    # Cleanup
    manager.db_manager = None


@pytest.fixture
def live_simulation(client: TestClient, api_config: dict[str, Any]) -> str:
    """Create a live simulation and run some ticks."""
    # Create simulation
    response = client.post("/simulations", json=api_config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # Run ticks to generate costs
    client.post(f"/simulations/{sim_id}/tick", params={"count": 30})

    return sim_id


@pytest.fixture
def persisted_simulation(
    client_with_db: tuple[TestClient, DatabaseManager],
    ffi_config: dict[str, Any],
    api_config: dict[str, Any],
    tmp_path: Path,
) -> tuple[str, DatabaseManager]:
    """Create a simulation and persist it to database.

    Returns simulation_id and database manager.
    """
    import uuid

    _test_client, db_manager = client_with_db

    # Create orchestrator directly
    orch = Orchestrator.new(ffi_config)

    ticks_per_day = api_config["simulation"]["ticks_per_day"]
    num_days = api_config["simulation"]["num_days"]

    # Generate unique sim_id
    sim_id = f"test-persist-{uuid.uuid4().hex[:8]}"

    # Insert simulation record directly (following pattern from other tests)
    conn = db_manager.get_connection()
    conn.execute(
        """
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents, config_json,
            status, started_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        [
            sim_id,
            "test.yaml",
            "test-hash",
            api_config["simulation"]["rng_seed"],
            ticks_per_day,
            num_days,
            len(api_config["agents"]),
            json.dumps(api_config),
            "completed",
        ],
    )

    # Create simulation config
    sim_config = SimulationConfig(
        total_ticks=ticks_per_day * num_days,
        ticks_per_day=ticks_per_day,
        num_days=num_days,
        persist=True,
        full_replay=True,
    )

    # Create persistence manager
    persistence = PersistenceManager(db_manager, sim_id, full_replay=True)

    # Create quiet output strategy
    output = QuietOutputStrategy()

    # Run simulation with persistence
    with patch("sys.stdout", new_callable=StringIO):
        runner = SimulationRunner(orch, sim_config, output, persistence)
        runner.run()

    return sim_id, db_manager


# ============================================================================
# Phase 0.1: Costs Endpoint Live vs Persisted Parity
# ============================================================================


class TestCostsLiveVsPersistedParity:
    """Tests verifying costs endpoint returns identical data for live and persisted."""

    def test_costs_persisted_returns_200(
        self, client_with_db, persisted_simulation
    ) -> None:
        """GET /costs should return 200 for persisted simulation."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/costs")

        assert response.status_code == 200, (
            f"Expected 200 for persisted simulation costs, got {response.status_code}: "
            f"{response.text}"
        )

    def test_costs_persisted_has_all_agents(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Persisted costs should include all agents."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        assert "agents" in data
        assert "BANK_A" in data["agents"]
        assert "BANK_B" in data["agents"]

    def test_costs_persisted_uses_canonical_field_names(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Persisted costs should use canonical field names.

        The canonical name is 'deadline_penalty', not 'deadline_penalty_cost'.

        CRITICAL: This test exposes the field name inconsistency between live
        and persisted. The database query returns 'deadline_penalty_cost' but
        it should map to 'deadline_penalty'.
        """
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/costs")
        data = response.json()

        agent_costs = data["agents"]["BANK_A"]

        # All canonical fields must be present
        canonical_fields = {
            "liquidity_cost",
            "delay_cost",
            "collateral_cost",
            "deadline_penalty",  # NOT deadline_penalty_cost
            "split_friction_cost",
            "total_cost",
        }

        actual_fields = set(agent_costs.keys())
        missing = canonical_fields - actual_fields

        assert not missing, (
            f"Persisted costs missing canonical fields: {missing}. "
            f"Available: {actual_fields}"
        )

    def test_costs_live_and_persisted_structure_identical(
        self, client, client_with_db, api_config, ffi_config, tmp_path
    ) -> None:
        """Live and persisted costs should have identical JSON structure.

        This test creates a simulation, gets costs while live, persists it,
        then gets costs again and compares structure.
        """
        test_client, db_manager = client_with_db

        # Create live simulation via API
        response = test_client.post("/simulations", json=api_config)
        assert response.status_code == 200
        live_sim_id = response.json()["simulation_id"]

        # Run some ticks
        test_client.post(f"/simulations/{live_sim_id}/tick", params={"count": 30})

        # Get costs while live
        live_response = test_client.get(f"/simulations/{live_sim_id}/costs")
        assert live_response.status_code == 200
        live_costs = live_response.json()

        # Now create a persisted simulation with same config
        import uuid

        orch = Orchestrator.new(ffi_config)
        ticks_per_day = api_config["simulation"]["ticks_per_day"]
        num_days = api_config["simulation"]["num_days"]
        persisted_sim_id = f"test-persist-{uuid.uuid4().hex[:8]}"

        # Insert simulation record directly
        conn = db_manager.get_connection()
        conn.execute(
            """
            INSERT INTO simulations (
                simulation_id, config_file, config_hash, rng_seed,
                ticks_per_day, num_days, num_agents, config_json,
                status, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                persisted_sim_id,
                "test.yaml",
                "test-hash",
                api_config["simulation"]["rng_seed"],
                ticks_per_day,
                num_days,
                len(api_config["agents"]),
                json.dumps(api_config),
                "completed",
            ],
        )

        sim_config = SimulationConfig(
            total_ticks=ticks_per_day * num_days,
            ticks_per_day=ticks_per_day,
            num_days=num_days,
            persist=True,
            full_replay=True,
        )
        persistence = PersistenceManager(db_manager, persisted_sim_id, full_replay=True)
        output = QuietOutputStrategy()

        with patch("sys.stdout", new_callable=StringIO):
            runner = SimulationRunner(orch, sim_config, output, persistence)
            runner.run()

        # Get costs from persisted
        persisted_response = test_client.get(f"/simulations/{persisted_sim_id}/costs")
        assert persisted_response.status_code == 200
        persisted_costs = persisted_response.json()

        # Compare structure (field names)
        live_agent_fields = set(live_costs["agents"]["BANK_A"].keys())
        persisted_agent_fields = set(persisted_costs["agents"]["BANK_A"].keys())

        assert live_agent_fields == persisted_agent_fields, (
            f"Field name mismatch between live and persisted costs!\n"
            f"Live fields: {sorted(live_agent_fields)}\n"
            f"Persisted fields: {sorted(persisted_agent_fields)}"
        )


# ============================================================================
# Phase 0.2: Metrics Endpoint for Persisted Simulations
# ============================================================================


class TestMetricsPersistedSupport:
    """Tests verifying metrics endpoint works for persisted simulations.

    CURRENT STATE: /metrics returns 404 for persisted simulations.
    These tests will fail until we implement database fallback.
    """

    def test_metrics_persisted_returns_200(
        self, client_with_db, persisted_simulation
    ) -> None:
        """GET /metrics should return 200 for persisted simulation.

        FAILING: Currently returns 404 because metrics endpoint
        doesn't have database fallback.
        """
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/metrics")

        assert response.status_code == 200, (
            f"Expected 200 for persisted simulation metrics, got {response.status_code}. "
            f"This fails because /metrics has no database fallback."
        )

    def test_metrics_persisted_has_settlement_rate(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Persisted metrics should include settlement_rate."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/metrics")

        # Skip if 404 (expected to fail until implemented)
        if response.status_code == 404:
            pytest.skip("Metrics endpoint not implemented for persisted simulations")

        data = response.json()
        assert "metrics" in data
        assert "settlement_rate" in data["metrics"]

    def test_metrics_persisted_has_all_fields(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Persisted metrics should have all standard metric fields."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        response = test_client.get(f"/simulations/{sim_id}/metrics")

        if response.status_code == 404:
            pytest.skip("Metrics endpoint not implemented for persisted simulations")

        data = response.json()
        metrics = data["metrics"]

        required_fields = {
            "total_arrivals",
            "total_settlements",
            "settlement_rate",
            "avg_delay_ticks",
            "max_delay_ticks",
            "queue1_total_size",
            "queue2_total_size",
            "peak_overdraft",
            "agents_in_overdraft",
        }

        missing = required_fields - set(metrics.keys())
        assert not missing, f"Persisted metrics missing fields: {missing}"


# ============================================================================
# Phase 0.3: API vs CLI State Provider Consistency
# ============================================================================


class TestAPIStateProviderConsistency:
    """Tests verifying API uses same data retrieval as CLI StateProvider.

    The CLI uses StateProvider to abstract data access.
    API should use the SAME StateProvider to ensure consistency.
    """

    def test_api_costs_match_state_provider_costs(
        self, client, api_config, ffi_config
    ) -> None:
        """API costs should match StateProvider.get_agent_accumulated_costs().

        This verifies the API gets data through the same path as CLI.
        """
        # Create live simulation via API
        response = client.post("/simulations", json=api_config)
        sim_id = response.json()["simulation_id"]

        # Run some ticks
        client.post(f"/simulations/{sim_id}/tick", params={"count": 20})

        # Get costs via API
        api_response = client.get(f"/simulations/{sim_id}/costs")
        api_costs = api_response.json()["agents"]["BANK_A"]

        # Get costs via StateProvider directly
        # We need to access the orchestrator from the simulation service
        from payment_simulator.api.dependencies import container

        orch = container.simulation_service.get_simulation(sim_id)
        provider = OrchestratorStateProvider(orch)
        provider_costs = provider.get_agent_accumulated_costs("BANK_A")

        # Compare values
        assert api_costs["liquidity_cost"] == provider_costs["liquidity_cost"], (
            f"liquidity_cost mismatch: API={api_costs['liquidity_cost']}, "
            f"Provider={provider_costs['liquidity_cost']}"
        )
        assert api_costs["delay_cost"] == provider_costs["delay_cost"]
        assert api_costs["collateral_cost"] == provider_costs["collateral_cost"]
        assert api_costs["deadline_penalty"] == provider_costs["deadline_penalty"]
        assert api_costs["total_cost"] == provider_costs["total_cost"]

    def test_api_should_use_state_provider_for_persisted(
        self, client_with_db, persisted_simulation
    ) -> None:
        """API should use DatabaseStateProvider for persisted simulations.

        This tests that we can eventually verify API uses the correct provider type.
        For now, just verify the endpoint works and returns correct structure.
        """
        sim_id, _db_manager = persisted_simulation
        test_client, _ = client_with_db

        # Get costs
        response = test_client.get(f"/simulations/{sim_id}/costs")
        assert response.status_code == 200

        data = response.json()

        # Verify it has correct structure (same as live)
        assert "simulation_id" in data
        assert "tick" in data
        assert "day" in data
        assert "agents" in data
        assert "total_system_cost" in data


# ============================================================================
# Phase 0.4: Data Contract Compliance
# ============================================================================


class TestDataContractCompliance:
    """Tests verifying API responses comply with shared data contracts."""

    def test_costs_response_matches_cost_breakdown_contract(
        self, client, api_config
    ) -> None:
        """API costs should match CostBreakdownContract fields exactly."""
        from payment_simulator.shared.data_contracts import CostBreakdownContract

        # Create and run simulation
        response = client.post("/simulations", json=api_config)
        sim_id = response.json()["simulation_id"]
        client.post(f"/simulations/{sim_id}/tick", params={"count": 10})

        # Get costs
        costs_response = client.get(f"/simulations/{sim_id}/costs")
        api_agent_costs = costs_response.json()["agents"]["BANK_A"]

        # Get contract fields
        contract_fields = set(CostBreakdownContract.__dataclass_fields__.keys())

        # API should have all contract fields (plus total_cost which is a property)
        for field in contract_fields:
            assert field in api_agent_costs, (
                f"API costs missing contract field '{field}'. "
                f"API fields: {list(api_agent_costs.keys())}"
            )

    def test_api_model_from_contract_round_trip(self) -> None:
        """AgentCostBreakdown.from_contract() should preserve all values."""
        from payment_simulator.api.models.costs import AgentCostBreakdown
        from payment_simulator.shared.data_contracts import CostBreakdownContract

        # Create contract with test values
        contract = CostBreakdownContract(
            liquidity_cost=1000,
            delay_cost=2000,
            collateral_cost=500,
            deadline_penalty=5000,
            split_friction_cost=100,
        )

        # Convert to API model
        model = AgentCostBreakdown.from_contract(contract)

        # Verify all values preserved
        assert model.liquidity_cost == 1000
        assert model.delay_cost == 2000
        assert model.collateral_cost == 500
        assert model.deadline_penalty == 5000
        assert model.split_friction_cost == 100
        assert model.total_cost == 8600  # Sum


# ============================================================================
# Phase 0.5: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge case tests for API output consistency."""

    def test_costs_at_tick_zero(self, client, api_config) -> None:
        """Costs at tick 0 should all be zero."""
        # Create simulation (starts at tick 0)
        response = client.post("/simulations", json=api_config)
        sim_id = response.json()["simulation_id"]

        # Get costs immediately (no ticks run)
        costs_response = client.get(f"/simulations/{sim_id}/costs")
        data = costs_response.json()

        # All costs should be zero at tick 0
        for agent_id, costs in data["agents"].items():
            assert costs["total_cost"] == 0, (
                f"Agent {agent_id} has non-zero costs at tick 0: {costs['total_cost']}"
            )

    def test_persisted_simulation_not_in_memory(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Persisted simulation should not be in memory simulation list.

        This ensures we're actually testing the database fallback path.
        """
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        from payment_simulator.api.dependencies import container

        # Simulation should NOT be in memory
        assert not container.simulation_service.has_simulation(sim_id), (
            f"Simulation {sim_id} should not be in memory after persistence"
        )

        # But costs should still be retrievable (from DB)
        response = test_client.get(f"/simulations/{sim_id}/costs")
        assert response.status_code == 200


# ============================================================================
# Phase 5: Historical State Support
# ============================================================================


class TestHistoricalTickState:
    """Tests for historical tick state queries on persisted simulations.

    These tests verify that `/ticks/{tick}/state` works for any historical
    tick in persisted simulations.
    """

    def test_historical_tick_state_returns_200(
        self, client_with_db, persisted_simulation
    ) -> None:
        """GET /ticks/{tick}/state should return 200 for any historical tick.

        FAILING: Currently returns 404 because tick state endpoint
        doesn't have database fallback for non-current ticks.
        """
        sim_id, _ = persisted_simulation
        test_client, db_manager = client_with_db

        # Get the total ticks from the simulation
        conn = db_manager.get_connection()
        result = conn.execute(
            "SELECT ticks_per_day * num_days FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()
        total_ticks = result[0] if result else 20

        # Query a tick in the middle of the simulation
        mid_tick = total_ticks // 2

        response = test_client.get(f"/simulations/{sim_id}/ticks/{mid_tick}/state")

        assert response.status_code == 200, (
            f"Expected 200 for historical tick {mid_tick}, got {response.status_code}. "
            f"This fails because /ticks/{{tick}}/state has no database fallback."
        )

    def test_historical_tick_state_has_agent_data(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Historical tick state should include agent state data."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        mid_tick = 5  # Query tick 5

        response = test_client.get(f"/simulations/{sim_id}/ticks/{mid_tick}/state")

        if response.status_code == 404:
            pytest.skip("Historical tick state not implemented for persisted simulations")

        data = response.json()

        # Should have agents dict
        assert "agents" in data
        assert len(data["agents"]) > 0

        # Each agent should have balance, queue sizes
        for agent_id, agent_state in data["agents"].items():
            assert "balance" in agent_state
            assert "queue1_size" in agent_state

    def test_historical_tick_state_correct_tick(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Historical tick state should report correct tick number."""
        sim_id, _ = persisted_simulation
        test_client, _ = client_with_db

        requested_tick = 5  # Specific tick to query

        response = test_client.get(f"/simulations/{sim_id}/ticks/{requested_tick}/state")

        if response.status_code == 404:
            pytest.skip("Historical tick state not implemented for persisted simulations")

        data = response.json()
        assert data["tick"] == requested_tick, (
            f"Response tick ({data['tick']}) doesn't match requested tick ({requested_tick})"
        )

    def test_tick_state_final_tick_persisted(
        self, client_with_db, persisted_simulation
    ) -> None:
        """Should be able to query final tick state for persisted simulation."""
        sim_id, _ = persisted_simulation
        test_client, db_manager = client_with_db

        # Get the total ticks from the simulation
        conn = db_manager.get_connection()
        result = conn.execute(
            "SELECT ticks_per_day * num_days FROM simulations WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()
        total_ticks = result[0] if result else 20

        # Query the final tick
        final_tick = total_ticks - 1

        response = test_client.get(f"/simulations/{sim_id}/ticks/{final_tick}/state")

        assert response.status_code == 200, (
            f"Expected 200 for final tick {final_tick}, got {response.status_code}"
        )
