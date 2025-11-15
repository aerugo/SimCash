"""Test diagnostic endpoints for frontend (TDD - tests written first)."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from payment_simulator.api.main import app

    return TestClient(app)


@pytest.fixture
def client_with_db(tmp_path):
    """Create test client with database support."""
    from payment_simulator.api.main import app, manager
    from payment_simulator.persistence.connection import DatabaseManager

    # Create database
    db_path = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_path))
    db_manager.setup()

    # Set database manager
    manager.db_manager = db_manager

    yield TestClient(app)

    # Cleanup
    manager.db_manager = None


@pytest.fixture
def simple_config():
    """Simple simulation configuration."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 2,
            "rng_seed": 54321,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1_500_000,
                "unsecured_cap": 250_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def sample_simulation(client, simple_config):
    """Create a sample simulation with some activity."""
    # Create simulation
    response = client.post("/simulations", json=simple_config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # Submit a few transactions to create activity
    transactions = [
        {
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 100000,
            "deadline_tick": 50,
            "priority": 5,
        },
        {
            "sender": "BANK_B",
            "receiver": "BANK_C",
            "amount": 200000,
            "deadline_tick": 50,
            "priority": 7,
        },
        {
            "sender": "BANK_C",
            "receiver": "BANK_A",
            "amount": 150000,
            "deadline_tick": 50,
            "priority": 6,
        },
    ]

    for tx in transactions:
        client.post(f"/simulations/{sim_id}/transactions", json=tx)

    # Advance a few ticks
    client.post(f"/simulations/{sim_id}/tick", params={"count": 10})

    return sim_id


# ============================================================================
# Task 0: Simulation List Endpoint (for frontend)
# ============================================================================


def test_list_simulations_includes_active(client):
    """Test GET /simulations includes active in-memory simulations."""
    # Create a simulation
    config = {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    response = client.post("/simulations", json=config)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # List simulations
    response = client.get("/simulations")
    assert response.status_code == 200
    data = response.json()

    assert "simulations" in data
    assert len(data["simulations"]) >= 1

    # Find our simulation
    sim = next((s for s in data["simulations"] if s["simulation_id"] == sim_id), None)
    assert sim is not None
    assert sim["simulation_id"] == sim_id


def test_list_simulations_includes_database(client_with_db):
    """Test GET /simulations includes database-persisted simulations."""
    from datetime import datetime

    from payment_simulator.api.main import manager

    # Insert a simulation directly into database
    conn = manager.db_manager.get_connection()

    sim_id = "test-db-sim-001"
    conn.execute(
        """
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            status, started_at, completed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            sim_id,
            "test.yaml",
            "abc123",
            54321,
            100,
            5,
            3,
            "completed",
            datetime.now(),
            datetime.now(),
        ],
    )

    # List simulations
    response = client_with_db.get("/simulations")
    assert response.status_code == 200
    data = response.json()

    assert "simulations" in data
    assert len(data["simulations"]) >= 1

    # Find our database simulation
    sim = next((s for s in data["simulations"] if s["simulation_id"] == sim_id), None)
    assert sim is not None
    assert sim["simulation_id"] == sim_id
    assert "config_file" in sim or "status" in sim  # Has database fields


# ============================================================================
# Task 1.1: Simulation Metadata Endpoint
# ============================================================================


def test_get_simulation_metadata(client, sample_simulation):
    """Test GET /simulations/{sim_id} returns metadata with config and summary."""
    sim_id = sample_simulation
    response = client.get(f"/simulations/{sim_id}")

    assert response.status_code == 200
    data = response.json()

    # Should have simulation ID
    assert data["simulation_id"] == sim_id

    # Should have created_at timestamp
    assert "created_at" in data
    assert isinstance(data["created_at"], str)

    # Should have config section
    assert "config" in data
    config = data["config"]
    # For active simulations, config is normalized to flat structure
    assert config["ticks_per_day"] == 100
    assert config["num_days"] == 2
    assert len(config["agents"]) == 3

    # Should have summary section with metrics
    assert "summary" in data
    summary = data["summary"]
    assert "total_ticks" in summary
    assert summary["total_ticks"] == 10  # We advanced 10 ticks
    assert "total_transactions" in summary
    assert summary["total_transactions"] >= 3  # At least our 3 transactions
    assert "settlement_rate" in summary
    assert 0.0 <= summary["settlement_rate"] <= 1.0


def test_get_simulation_metadata_not_found(client):
    """Test GET /simulations/{sim_id} returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent-sim-id")
    assert response.status_code == 404


def test_get_simulation_metadata_from_database(client_with_db):
    """Test GET /simulations/{sim_id} works for database-persisted simulations.

    This test catches the bug where the endpoint tried to access non-existent
    database columns (config_json) and used dangerous eval().
    """
    from datetime import datetime

    from payment_simulator.api.main import manager

    # Insert a simulation directly into database using SimulationRecord schema
    conn = manager.db_manager.get_connection()

    sim_id = "sim-db-test-001"
    conn.execute(
        """
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            status, started_at, completed_at,
            total_arrivals, total_settlements, total_cost_cents,
            duration_seconds, ticks_per_second
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            sim_id,
            "test_config.yaml",
            "abc123hash",
            54321,
            100,
            5,
            3,
            "completed",
            datetime.now(),
            datetime.now(),
            1000,
            950,
            50000,
            120.5,
            8.3,
        ],
    )

    # Add some sample transactions to the database (include all required fields)
    conn.execute(
        """
        INSERT INTO transactions (
            simulation_id, tx_id, sender_id, receiver_id, amount,
            priority, is_divisible, arrival_tick, arrival_day,
            deadline_tick, status, amount_settled,
            queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost,
            settlement_tick, settlement_day
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            sim_id,
            "tx-001",
            "BANK_A",
            "BANK_B",
            100000,
            5,
            False,
            10,
            0,
            50,
            "settled",
            100000,
            0,
            0,
            0,
            0,
            15,
            0,
        ],
    )

    # Get simulation metadata
    response = client_with_db.get(f"/simulations/{sim_id}")

    # Should succeed (this would fail with the old buggy code)
    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert data["simulation_id"] == sim_id
    assert "created_at" in data
    assert isinstance(data["created_at"], str)

    # Verify config section (built from available database fields)
    assert "config" in data
    config = data["config"]
    assert config["config_file"] == "test_config.yaml"
    assert config["config_hash"] == "abc123hash"
    assert config["rng_seed"] == 54321
    assert config["ticks_per_day"] == 100
    assert config["num_days"] == 5
    assert config["num_agents"] == 3

    # Verify summary section
    assert "summary" in data
    summary = data["summary"]
    assert summary["total_ticks"] == 500  # ticks_per_day * num_days
    # API recalculates from actual transactions in database (we only inserted 1)
    assert summary["total_transactions"] == 1
    assert summary["settlement_rate"] == 1.0  # 1 settled / 1 total
    assert summary["total_cost_cents"] == 50000
    assert summary["duration_seconds"] == 120.5
    assert summary["ticks_per_second"] == 8.3


# ============================================================================
# Task 1.2: Agent List Endpoint
# ============================================================================


def test_get_agent_list(client, sample_simulation):
    """Test GET /simulations/{sim_id}/agents returns list of agents with summary."""
    sim_id = sample_simulation
    response = client.get(f"/simulations/{sim_id}/agents")

    assert response.status_code == 200
    data = response.json()

    # Should return agents array
    assert "agents" in data
    agents = data["agents"]
    assert len(agents) == 3

    # Check first agent has required fields
    agent = agents[0]
    assert "agent_id" in agent
    assert agent["agent_id"] in ["BANK_A", "BANK_B", "BANK_C"]
    assert "total_sent" in agent
    assert "total_received" in agent
    assert "total_settled" in agent
    assert "total_dropped" in agent
    assert "total_cost_cents" in agent
    assert "avg_balance_cents" in agent
    assert "peak_overdraft_cents" in agent
    assert "credit_limit_cents" in agent

    # Values should be integers
    assert isinstance(agent["total_sent"], int)
    assert isinstance(agent["total_cost_cents"], int)
    assert isinstance(agent["avg_balance_cents"], int)


def test_get_agent_list_not_found(client):
    """Test GET /simulations/{sim_id}/agents returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent-sim-id/agents")
    assert response.status_code == 404


# ============================================================================
# Task 1.3: Events Endpoint (Paginated)
# ============================================================================


def test_get_events_paginated(client, sample_simulation):
    """Test GET /simulations/{sim_id}/events returns paginated events."""
    sim_id = sample_simulation
    response = client.get(
        f"/simulations/{sim_id}/events", params={"limit": 10, "offset": 0}
    )

    assert response.status_code == 200
    data = response.json()

    # Should have pagination fields
    assert "events" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data

    # Check pagination values
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert isinstance(data["total"], int)
    assert len(data["events"]) <= 10

    # Check event structure if events exist
    if data["events"]:
        event = data["events"][0]
        assert "tick" in event
        assert "event_type" in event
        # timestamp is optional but useful
        assert isinstance(event["tick"], int)


def test_get_events_filtered_by_agent(client, sample_simulation):
    """Test GET /simulations/{sim_id}/events filters by agent_id."""
    sim_id = sample_simulation
    response = client.get(
        f"/simulations/{sim_id}/events", params={"agent_id": "BANK_A"}
    )

    assert response.status_code == 200
    data = response.json()

    # All events should involve BANK_A as sender or receiver
    for event in data["events"]:
        if "sender_id" in event or "receiver_id" in event:
            assert ("sender_id" in event and event["sender_id"] == "BANK_A") or (
                "receiver_id" in event and event["receiver_id"] == "BANK_A"
            )


def test_get_events_with_tick_range(client, sample_simulation):
    """Test GET /simulations/{sim_id}/events filters by tick range."""
    sim_id = sample_simulation
    response = client.get(
        f"/simulations/{sim_id}/events", params={"tick_min": 0, "tick_max": 5}
    )

    assert response.status_code == 200
    data = response.json()

    # All events should be within tick range
    for event in data["events"]:
        assert 0 <= event["tick"] <= 5


# ============================================================================
# Task 1.4: Agent Timeline Endpoint
# ============================================================================


def test_get_agent_timeline(client, sample_simulation):
    """Test GET /simulations/{sim_id}/agents/{agent_id}/timeline."""
    sim_id = sample_simulation
    response = client.get(f"/simulations/{sim_id}/agents/BANK_A/timeline")

    assert response.status_code == 200
    data = response.json()

    # Should have agent_id
    assert data["agent_id"] == "BANK_A"

    # Should have daily_metrics
    assert "daily_metrics" in data
    daily_metrics = data["daily_metrics"]
    assert len(daily_metrics) >= 1  # At least day 0

    # Check daily metric structure
    if daily_metrics:
        metric = daily_metrics[0]
        assert "day" in metric
        assert "opening_balance" in metric
        assert "closing_balance" in metric
        assert "min_balance" in metric
        assert "max_balance" in metric
        assert "transactions_sent" in metric
        assert "transactions_received" in metric
        assert "total_cost_cents" in metric

    # Should have collateral_events (may be empty)
    assert "collateral_events" in data
    assert isinstance(data["collateral_events"], list)


def test_get_agent_timeline_not_found_simulation(client):
    """Test agent timeline returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent/agents/BANK_A/timeline")
    assert response.status_code == 404


def test_get_agent_timeline_not_found_agent(client, sample_simulation):
    """Test agent timeline returns 404 for non-existent agent."""
    sim_id = sample_simulation
    response = client.get(f"/simulations/{sim_id}/agents/NONEXISTENT/timeline")
    assert response.status_code == 404


# ============================================================================
# Task 1.5: Transaction Lifecycle Endpoint
# ============================================================================


def test_get_transaction_lifecycle(client, sample_simulation):
    """Test GET /simulations/{sim_id}/transactions/{tx_id}/lifecycle."""
    sim_id = sample_simulation

    # Get a transaction ID from the list
    tx_response = client.get(f"/simulations/{sim_id}/transactions")
    assert tx_response.status_code == 200
    transactions = tx_response.json()["transactions"]
    assert len(transactions) > 0

    tx_id = transactions[0]["tx_id"]

    # Get lifecycle
    response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}/lifecycle")

    assert response.status_code == 200
    data = response.json()

    # Should have transaction details
    assert "transaction" in data
    tx = data["transaction"]
    assert tx["tx_id"] == tx_id
    assert "sender_id" in tx
    assert "receiver_id" in tx
    assert "amount" in tx
    assert "status" in tx

    # Should have events (at least Arrival)
    assert "events" in data
    events = data["events"]
    assert len(events) > 0
    assert events[0]["event_type"] == "Arrival"

    # Should have related_transactions (may be empty for non-split transactions)
    assert "related_transactions" in data
    assert isinstance(data["related_transactions"], list)


def test_get_transaction_lifecycle_not_found(client, sample_simulation):
    """Test transaction lifecycle returns 404 for non-existent transaction."""
    sim_id = sample_simulation
    response = client.get(
        f"/simulations/{sim_id}/transactions/nonexistent-tx/lifecycle"
    )
    assert response.status_code == 404
