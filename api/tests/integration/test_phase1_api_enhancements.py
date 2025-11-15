"""Phase 1 API Enhancements - Diagnostic Frontend Upgrade.

Tests for new endpoints to support enhanced diagnostic frontend capabilities.
Following strict TDD: tests written first, then implementation.

Endpoints tested:
1. GET /simulations/{id}/agents/{agentId}/queues - Agent queue contents
2. GET /simulations/{id}/transactions/near-deadline - Approaching deadline
3. GET /simulations/{id}/transactions/overdue - Currently overdue
4. GET /simulations/{id}/ticks/{tick}/state - Tick-specific state snapshot
"""

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
    db_manager.close()
    manager.db_manager = None


@pytest.fixture
def config_with_queue_activity():
    """Config designed to create queue activity."""
    return {
        "simulation": {
            "ticks_per_day": 100,
            "num_days": 1,
            "rng_seed": 42,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # Low balance to create queues
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 5_000_000,  # High balance
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }


@pytest.fixture
def simulation_with_queues(client, config_with_queue_activity):
    """Create simulation with queued transactions."""
    # Create simulation
    response = client.post("/simulations", json=config_with_queue_activity)
    assert response.status_code == 200
    sim_id = response.json()["simulation_id"]

    # Submit transactions that will queue (low liquidity)
    transactions = [
        {
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 80_000,  # Most of BANK_A's balance
            "deadline_tick": 50,
            "priority": 5,
        },
        {
            "sender": "BANK_A",
            "receiver": "BANK_C",
            "amount": 50_000,  # Will queue - insufficient balance
            "deadline_tick": 60,
            "priority": 7,
        },
        {
            "sender": "BANK_B",
            "receiver": "BANK_C",
            "amount": 90_000,
            "deadline_tick": 70,
            "priority": 6,
        },
    ]

    tx_ids = []
    for tx in transactions:
        response = client.post(f"/simulations/{sim_id}/transactions", json=tx)
        assert response.status_code == 200
        tx_ids.append(response.json()["transaction_id"])

    # Advance a few ticks to process some transactions
    client.post(f"/simulations/{sim_id}/tick", params={"count": 3})

    return {"sim_id": sim_id, "tx_ids": tx_ids}


# ============================================================================
# Endpoint 1: GET /simulations/{id}/agents/{agentId}/queues
# ============================================================================


def test_get_agent_queues_returns_queue_contents(client, simulation_with_queues):
    """Test that agent queues endpoint returns queue1 and queue2 contents."""
    sim_id = simulation_with_queues["sim_id"]

    # Get queues for BANK_A (should have some queued transactions)
    response = client.get(f"/simulations/{sim_id}/agents/BANK_A/queues")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "agent_id" in data
    assert data["agent_id"] == "BANK_A"
    assert "tick" in data
    assert "queue1" in data
    assert "queue2_filtered" in data

    # Verify queue1 structure (internal queue)
    queue1 = data["queue1"]
    assert "size" in queue1
    assert "transactions" in queue1
    assert "total_value" in queue1
    assert isinstance(queue1["transactions"], list)

    # If there are transactions, verify their structure
    if queue1["size"] > 0:
        tx = queue1["transactions"][0]
        assert "tx_id" in tx
        assert "receiver_id" in tx
        assert "amount" in tx
        assert "priority" in tx
        assert "deadline_tick" in tx

    # Verify queue2_filtered structure (RTGS queue filtered to this agent)
    queue2 = data["queue2_filtered"]
    assert "size" in queue2
    assert "transactions" in queue2
    assert "total_value" in queue2
    assert isinstance(queue2["transactions"], list)


def test_get_agent_queues_404_for_nonexistent_simulation(client):
    """Test that queues endpoint returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent-sim/agents/BANK_A/queues")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_agent_queues_404_for_nonexistent_agent(client, simulation_with_queues):
    """Test that queues endpoint returns 404 for non-existent agent."""
    sim_id = simulation_with_queues["sim_id"]

    response = client.get(f"/simulations/{sim_id}/agents/NONEXISTENT/queues")
    assert response.status_code == 404
    assert "agent" in response.json()["detail"].lower()


def test_get_agent_queues_calculates_total_value_correctly(
    client, simulation_with_queues
):
    """Test that total_value is calculated correctly from transaction amounts."""
    sim_id = simulation_with_queues["sim_id"]

    response = client.get(f"/simulations/{sim_id}/agents/BANK_A/queues")
    assert response.status_code == 200
    data = response.json()

    # Verify total_value matches sum of transaction amounts
    queue1 = data["queue1"]
    if queue1["size"] > 0:
        calculated_total = sum(tx["amount"] for tx in queue1["transactions"])
        assert queue1["total_value"] == calculated_total


# ============================================================================
# Endpoint 2: GET /simulations/{id}/transactions/near-deadline
# ============================================================================


def test_get_near_deadline_transactions_with_default_window(
    client, simulation_with_queues
):
    """Test near-deadline endpoint with default within_ticks=2."""
    sim_id = simulation_with_queues["sim_id"]

    response = client.get(f"/simulations/{sim_id}/transactions/near-deadline")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "simulation_id" in data
    assert "current_tick" in data
    assert "within_ticks" in data
    assert "threshold_tick" in data
    assert "transactions" in data
    assert "count" in data

    assert data["simulation_id"] == sim_id
    assert data["within_ticks"] == 2  # Default
    assert isinstance(data["transactions"], list)
    assert data["count"] == len(data["transactions"])


def test_get_near_deadline_transactions_with_custom_window(
    client, simulation_with_queues
):
    """Test near-deadline endpoint with custom within_ticks parameter."""
    sim_id = simulation_with_queues["sim_id"]

    response = client.get(
        f"/simulations/{sim_id}/transactions/near-deadline", params={"within_ticks": 50}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["within_ticks"] == 50
    assert data["threshold_tick"] == data["current_tick"] + 50


def test_near_deadline_transactions_have_correct_fields(
    client, simulation_with_queues
):
    """Test that near-deadline transactions include all required fields."""
    sim_id = simulation_with_queues["sim_id"]

    response = client.get(
        f"/simulations/{sim_id}/transactions/near-deadline", params={"within_ticks": 100}
    )

    assert response.status_code == 200
    data = response.json()

    # If there are transactions near deadline, verify structure
    if data["count"] > 0:
        tx = data["transactions"][0]
        assert "tx_id" in tx
        assert "sender_id" in tx
        assert "receiver_id" in tx
        assert "amount" in tx
        assert "remaining_amount" in tx
        assert "deadline_tick" in tx
        assert "ticks_until_deadline" in tx

        # Verify ticks_until_deadline is calculated correctly
        assert tx["ticks_until_deadline"] == tx["deadline_tick"] - data["current_tick"]


def test_near_deadline_transactions_excludes_settled(client, config_with_queue_activity):
    """Test that settled transactions are not included in near-deadline list."""
    # Create simulation
    response = client.post("/simulations", json=config_with_queue_activity)
    sim_id = response.json()["simulation_id"]

    # Submit transaction with very close deadline
    current_tick_response = client.get(f"/simulations/{sim_id}/state")
    current_tick = current_tick_response.json()["current_tick"]

    response = client.post(
        f"/simulations/{sim_id}/transactions",
        json={
            "sender": "BANK_C",  # High balance - will settle immediately
            "receiver": "BANK_A",
            "amount": 10_000,
            "deadline_tick": current_tick + 3,
            "priority": 10,
        },
    )
    tx_id = response.json()["transaction_id"]

    # Advance tick to settle
    client.post(f"/simulations/{sim_id}/tick")

    # Get near-deadline transactions
    response = client.get(
        f"/simulations/{sim_id}/transactions/near-deadline", params={"within_ticks": 10}
    )
    assert response.status_code == 200
    data = response.json()

    # Settled transaction should not appear
    tx_ids = [tx["tx_id"] for tx in data["transactions"]]
    assert tx_id not in tx_ids


def test_near_deadline_404_for_nonexistent_simulation(client):
    """Test near-deadline endpoint returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent/transactions/near-deadline")
    assert response.status_code == 404


# ============================================================================
# Endpoint 3: GET /simulations/{id}/transactions/overdue
# ============================================================================


def test_get_overdue_transactions_structure(client, config_with_queue_activity):
    """Test overdue transactions endpoint structure."""
    # Create simulation
    response = client.post("/simulations", json=config_with_queue_activity)
    sim_id = response.json()["simulation_id"]

    # Submit transaction with very short deadline
    response = client.post(
        f"/simulations/{sim_id}/transactions",
        json={
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 150_000,  # More than available - will queue
            "deadline_tick": 2,  # Will become overdue quickly
            "priority": 5,
        },
    )

    # Advance several ticks to make it overdue
    client.post(f"/simulations/{sim_id}/tick", params={"count": 5})

    # Get overdue transactions
    response = client.get(f"/simulations/{sim_id}/transactions/overdue")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "simulation_id" in data
    assert "current_tick" in data
    assert "transactions" in data
    assert "count" in data
    assert "total_overdue_cost" in data

    assert data["simulation_id"] == sim_id
    assert isinstance(data["transactions"], list)
    assert data["count"] == len(data["transactions"])


def test_overdue_transactions_have_cost_information(client, config_with_queue_activity):
    """Test that overdue transactions include cost breakdown."""
    # Create simulation
    response = client.post("/simulations", json=config_with_queue_activity)
    sim_id = response.json()["simulation_id"]

    # Submit transaction that will become overdue
    response = client.post(
        f"/simulations/{sim_id}/transactions",
        json={
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 150_000,
            "deadline_tick": 2,
            "priority": 5,
        },
    )

    # Make it overdue
    client.post(f"/simulations/{sim_id}/tick", params={"count": 5})

    # Get overdue transactions
    response = client.get(f"/simulations/{sim_id}/transactions/overdue")
    data = response.json()

    # If there are overdue transactions, verify cost fields
    if data["count"] > 0:
        tx = data["transactions"][0]
        assert "tx_id" in tx
        assert "sender_id" in tx
        assert "receiver_id" in tx
        assert "amount" in tx
        assert "remaining_amount" in tx
        assert "deadline_tick" in tx
        assert "overdue_since_tick" in tx
        assert "ticks_overdue" in tx
        assert "estimated_delay_cost" in tx
        assert "deadline_penalty_cost" in tx
        assert "total_overdue_cost" in tx

        # Verify ticks_overdue calculation
        assert tx["ticks_overdue"] == data["current_tick"] - tx["overdue_since_tick"]


def test_overdue_transactions_excludes_settled(client, config_with_queue_activity):
    """Test that settled overdue transactions are not included."""
    # Create simulation
    response = client.post("/simulations", json=config_with_queue_activity)
    sim_id = response.json()["simulation_id"]

    # Submit transaction with short deadline that will eventually settle
    response = client.post(
        f"/simulations/{sim_id}/transactions",
        json={
            "sender": "BANK_A",
            "receiver": "BANK_C",
            "amount": 50_000,
            "deadline_tick": 2,
            "priority": 5,
        },
    )
    tx_id = response.json()["transaction_id"]

    # Advance many ticks - transaction may become overdue then settle
    client.post(f"/simulations/{sim_id}/tick", params={"count": 20})

    # Get overdue transactions
    response = client.get(f"/simulations/{sim_id}/transactions/overdue")
    data = response.json()

    # Check if transaction is in the list
    # If it settled, it should not be in overdue list
    tx_ids = [tx["tx_id"] for tx in data["transactions"]]

    # Verify transaction status
    tx_response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}")
    tx_status = tx_response.json()["status"]

    if tx_status == "settled":
        assert tx_id not in tx_ids, "Settled transaction should not be in overdue list"


def test_overdue_404_for_nonexistent_simulation(client):
    """Test overdue endpoint returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent/transactions/overdue")
    assert response.status_code == 404


# ============================================================================
# Endpoint 4: GET /simulations/{id}/ticks/{tick}/state
# ============================================================================


def test_get_tick_state_snapshot_structure(client, simulation_with_queues):
    """Test tick state snapshot endpoint returns complete state."""
    sim_id = simulation_with_queues["sim_id"]

    # Get current tick
    state_response = client.get(f"/simulations/{sim_id}/state")
    current_tick = state_response.json()["current_tick"]

    # Get state snapshot for current tick
    response = client.get(f"/simulations/{sim_id}/ticks/{current_tick}/state")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "simulation_id" in data
    assert "tick" in data
    assert "day" in data
    assert "agents" in data
    assert "system" in data

    assert data["simulation_id"] == sim_id
    assert data["tick"] == current_tick
    assert isinstance(data["agents"], dict)
    assert isinstance(data["system"], dict)


def test_tick_state_includes_agent_details(client, simulation_with_queues):
    """Test that tick state includes detailed agent information."""
    sim_id = simulation_with_queues["sim_id"]

    state_response = client.get(f"/simulations/{sim_id}/state")
    current_tick = state_response.json()["current_tick"]

    response = client.get(f"/simulations/{sim_id}/ticks/{current_tick}/state")
    data = response.json()

    # Verify agent details
    agents = data["agents"]
    assert len(agents) > 0

    # Check first agent structure
    agent_id = list(agents.keys())[0]
    agent = agents[agent_id]

    assert "balance" in agent
    assert "credit_limit" in agent
    assert "liquidity" in agent
    assert "headroom" in agent
    assert "queue1_size" in agent
    assert "queue2_size" in agent
    assert "costs" in agent

    # Verify costs structure
    costs = agent["costs"]
    assert "liquidity_cost" in costs
    assert "delay_cost" in costs
    assert "collateral_cost" in costs
    assert "split_friction_cost" in costs
    assert "deadline_penalty" in costs
    assert "total_cost" in costs


def test_tick_state_includes_system_metrics(client, simulation_with_queues):
    """Test that tick state includes system-wide metrics."""
    sim_id = simulation_with_queues["sim_id"]

    state_response = client.get(f"/simulations/{sim_id}/state")
    current_tick = state_response.json()["current_tick"]

    response = client.get(f"/simulations/{sim_id}/ticks/{current_tick}/state")
    data = response.json()

    # Verify system metrics
    system = data["system"]
    assert "total_arrivals" in system
    assert "total_settlements" in system
    assert "settlement_rate" in system
    assert "queue1_total_size" in system
    assert "queue2_total_size" in system
    assert "total_system_cost" in system


def test_tick_state_404_for_nonexistent_simulation(client):
    """Test tick state returns 404 for non-existent simulation."""
    response = client.get("/simulations/nonexistent/ticks/1/state")
    assert response.status_code == 404


def test_tick_state_400_for_invalid_tick(client, simulation_with_queues):
    """Test tick state returns 400 for invalid tick number."""
    sim_id = simulation_with_queues["sim_id"]

    # Try to get state for tick -1 (invalid)
    response = client.get(f"/simulations/{sim_id}/ticks/-1/state")
    assert response.status_code == 400

    # Try to get state for future tick
    response = client.get(f"/simulations/{sim_id}/ticks/999999/state")
    assert response.status_code == 400


# ============================================================================
# Integration Tests: Database Support
# ============================================================================


def test_agent_queues_not_supported_for_database_simulations(client_with_db):
    """Test that agent queues endpoint indicates database simulations need live replay."""
    # For database-persisted simulations, queue contents require StateProvider
    # This test documents the expected behavior - may return 501 Not Implemented
    # or delegate to replay logic
    pass  # Placeholder - implementation depends on architecture decision


def test_near_deadline_works_with_database_simulations(client_with_db):
    """Test near-deadline endpoint works for database simulations."""
    # This should work by querying transactions table
    pass  # Placeholder - will implement after database support added


def test_overdue_works_with_database_simulations(client_with_db):
    """Test overdue endpoint works for database simulations."""
    # This should work by querying simulation_events for TransactionWentOverdue
    pass  # Placeholder - will implement after database support added


def test_tick_state_works_with_database_simulations(client_with_db):
    """Test tick state works for database simulations (requires agent_states table)."""
    # This requires querying agent_states, queue_snapshots tables
    pass  # Placeholder - will implement after database support added
