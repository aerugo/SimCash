"""Test FastAPI transaction endpoints (TDD - tests written first)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from payment_simulator.api.main import app
    return TestClient(app)


@pytest.fixture
def simulation_with_agents(client):
    """Create a simulation with two agents."""
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
                "unsecured_cap": 500_000,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 2_000_000,
                "unsecured_cap": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    response = client.post("/simulations", json=config)
    return response.json()["simulation_id"]


def test_submit_transaction(client, simulation_with_agents):
    """Test submitting a transaction."""
    sim_id = simulation_with_agents

    # Submit transaction
    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 100_000,
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)

    assert response.status_code == 200
    data = response.json()

    # Should return transaction ID
    assert "transaction_id" in data
    assert isinstance(data["transaction_id"], str)
    assert len(data["transaction_id"]) > 0


def test_submit_transaction_invalid_sender(client, simulation_with_agents):
    """Test submitting transaction with invalid sender."""
    sim_id = simulation_with_agents

    tx_data = {
        "sender": "BANK_X",  # Doesn't exist
        "receiver": "BANK_B",
        "amount": 100_000,
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
    assert response.status_code == 400  # Bad request


def test_submit_transaction_invalid_amount(client, simulation_with_agents):
    """Test submitting transaction with invalid amount."""
    sim_id = simulation_with_agents

    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": -100,  # Negative amount
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
    assert response.status_code == 400


def test_get_transaction_status(client, simulation_with_agents):
    """Test querying transaction status."""
    sim_id = simulation_with_agents

    # Submit transaction
    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 100_000,
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    submit_response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
    tx_id = submit_response.json()["transaction_id"]

    # Query transaction
    response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}")

    assert response.status_code == 200
    data = response.json()

    # Verify transaction details
    assert data["transaction_id"] == tx_id
    assert data["sender"] == "BANK_A"
    assert data["receiver"] == "BANK_B"
    assert data["amount"] == 100_000
    assert "status" in data
    assert data["status"] in ["pending", "settled", "dropped"]


def test_transaction_lifecycle(client, simulation_with_agents):
    """Test complete transaction lifecycle: submit → tick → settled."""
    sim_id = simulation_with_agents

    # Submit transaction
    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 100_000,
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    submit_response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
    tx_id = submit_response.json()["transaction_id"]

    # Initially should be pending (in Queue 1)
    tx_response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}")
    tx_data_before = tx_response.json()
    # Status might be pending or already processing

    # Advance simulation
    for _ in range(5):
        client.post(f"/simulations/{sim_id}/tick")

    # Check transaction status
    tx_response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}")
    tx_data_after = tx_response.json()

    # Should be settled now (FIFO policy, sufficient funds)
    assert tx_data_after["status"] == "settled"

    # Verify balances changed
    state_response = client.get(f"/simulations/{sim_id}/state")
    state = state_response.json()

    # BANK_A should have less money
    bank_a_balance = state["agents"]["BANK_A"]["balance"]
    assert bank_a_balance < 1_000_000

    # BANK_B should have more money
    bank_b_balance = state["agents"]["BANK_B"]["balance"]
    assert bank_b_balance > 2_000_000


def test_list_transactions(client, simulation_with_agents):
    """Test listing all transactions in a simulation."""
    sim_id = simulation_with_agents

    # Submit multiple transactions
    tx_ids = []
    for i in range(3):
        tx_data = {
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 50_000 + (i * 10_000),
            "deadline_tick": 50,
            "priority": 5,
            "divisible": False,
        }
        response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
        tx_ids.append(response.json()["transaction_id"])

    # List transactions
    response = client.get(f"/simulations/{sim_id}/transactions")

    assert response.status_code == 200
    data = response.json()

    assert "transactions" in data
    assert len(data["transactions"]) >= 3

    # Verify our transaction IDs are in the list
    listed_ids = [tx["transaction_id"] for tx in data["transactions"]]
    for tx_id in tx_ids:
        assert tx_id in listed_ids


def test_transaction_with_insufficient_funds(client, simulation_with_agents):
    """Test transaction that can't settle due to insufficient funds."""
    sim_id = simulation_with_agents

    # Submit large transaction that exceeds available liquidity
    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 2_000_000,  # More than BANK_A has (even with credit)
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    submit_response = client.post(f"/simulations/{sim_id}/transactions", json=tx_data)
    tx_id = submit_response.json()["transaction_id"]

    # Advance simulation
    for _ in range(10):
        client.post(f"/simulations/{sim_id}/tick")

    # Check transaction status
    tx_response = client.get(f"/simulations/{sim_id}/transactions/{tx_id}")
    tx_data_result = tx_response.json()

    # Should still be pending (in Queue 2 waiting for liquidity)
    assert tx_data_result["status"] in ["pending", "queued"]


def test_nonexistent_transaction(client, simulation_with_agents):
    """Test querying non-existent transaction."""
    sim_id = simulation_with_agents

    response = client.get(f"/simulations/{sim_id}/transactions/nonexistent-id")
    assert response.status_code == 404


def test_submit_to_nonexistent_simulation(client):
    """Test submitting transaction to non-existent simulation."""
    tx_data = {
        "sender": "BANK_A",
        "receiver": "BANK_B",
        "amount": 100_000,
        "deadline_tick": 50,
        "priority": 5,
        "divisible": False,
    }

    response = client.post("/simulations/nonexistent-id/transactions", json=tx_data)
    assert response.status_code == 404


def test_transaction_filtering_by_status(client, simulation_with_agents):
    """Test filtering transactions by status."""
    sim_id = simulation_with_agents

    # Submit multiple transactions
    for i in range(5):
        tx_data = {
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 50_000,
            "deadline_tick": 50,
            "priority": 5,
            "divisible": False,
        }
        client.post(f"/simulations/{sim_id}/transactions", json=tx_data)

    # Settle some by advancing ticks
    for _ in range(3):
        client.post(f"/simulations/{sim_id}/tick")

    # Get only settled transactions
    response = client.get(f"/simulations/{sim_id}/transactions", params={"status": "settled"})

    assert response.status_code == 200
    data = response.json()

    # All returned transactions should be settled
    for tx in data["transactions"]:
        assert tx["status"] == "settled"


def test_transaction_filtering_by_agent(client, simulation_with_agents):
    """Test filtering transactions by sender/receiver."""
    sim_id = simulation_with_agents

    # Submit transactions in both directions
    for _ in range(3):
        client.post(
            f"/simulations/{sim_id}/transactions",
            json={
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 50_000,
                "deadline_tick": 50,
                "priority": 5,
                "divisible": False,
            },
        )

    # Get transactions involving BANK_A
    response = client.get(f"/simulations/{sim_id}/transactions", params={"agent": "BANK_A"})

    assert response.status_code == 200
    data = response.json()

    # All returned transactions should involve BANK_A
    for tx in data["transactions"]:
        assert tx["sender"] == "BANK_A" or tx["receiver"] == "BANK_A"
