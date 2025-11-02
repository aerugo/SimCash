"""
E2E test for diagnostic dashboard with real simulation data.

This test runs the 12-bank 4-policy comparison scenario and creates a real database,
then verifies the API endpoints return correct data for the diagnostic dashboard.
"""

import json
import subprocess
import time
from pathlib import Path

import pytest
from payment_simulator.persistence.connection import DatabaseManager


@pytest.fixture(scope="module")
def simulation_database(tmp_path_factory):
    """
    Run the 12-bank scenario and create a real test database.

    This fixture:
    1. Runs the simulation with --persist flag
    2. Returns the database path and simulation ID
    3. Cleans up after tests complete
    """
    # Create a temporary directory for this test module
    db_dir = tmp_path_factory.mktemp("diagnostic_e2e")
    db_path = db_dir / "test_12_bank.db"

    # Path to the 12-bank config
    config_path = (
        Path(__file__).parents[3]
        / "examples"
        / "configs"
        / "12_bank_4_policy_comparison.yaml"
    )

    if not config_path.exists():
        pytest.skip(f"Config file not found: {config_path}")

    # Run the simulation with persistence
    # Use a small number of ticks for faster testing (override the 1000 ticks in config)
    cmd = [
        "python",
        "-m",
        "payment_simulator.cli.main",
        "run",
        "--config",
        str(config_path),
        "--persist",
        "--db-path",
        str(db_path),
        "--quiet",
        "--ticks",
        "100",  # Just 100 ticks for faster testing
        "--seed",
        "42",  # Fixed seed for determinism
    ]

    print(f"\n🔧 Running simulation: {' '.join(cmd)}")
    start_time = time.time()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,  # 2 minute timeout
    )

    duration = time.time() - start_time
    print(f"✅ Simulation completed in {duration:.2f}s")

    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        pytest.fail(f"Simulation failed with return code {result.returncode}")

    # Parse the output to get simulation ID
    try:
        output_data = json.loads(result.stdout)
        sim_id = output_data["simulation"]["simulation_id"]
        print(f"📊 Simulation ID: {sim_id}")
    except (json.JSONDecodeError, KeyError) as e:
        print("Failed to parse simulation output:", result.stdout)
        pytest.fail(f"Failed to extract simulation ID: {e}")

    # Verify database was created
    if not db_path.exists():
        pytest.fail(f"Database was not created at {db_path}")

    # Verify database has data
    db_manager = DatabaseManager(str(db_path))

    # Check we have simulation record
    sim_count = db_manager.conn.execute(
        "SELECT COUNT(*) FROM simulations WHERE simulation_id = ?", [sim_id]
    ).fetchone()[0]

    if sim_count == 0:
        pytest.fail(f"No simulation record found for ID {sim_id}")

    # Check we have transactions
    tx_count = db_manager.conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE simulation_id = ?", [sim_id]
    ).fetchone()[0]

    print(f"📈 Database contains {tx_count} transactions")

    if tx_count == 0:
        pytest.fail("No transactions found in database")

    yield {
        "db_path": str(db_path),
        "simulation_id": sim_id,
        "db_manager": db_manager,
    }

    # Cleanup handled by tmp_path_factory


@pytest.mark.e2e
def test_simulation_metadata_endpoint(simulation_database):
    """Test that simulation metadata endpoint returns correct data."""
    from fastapi.testclient import TestClient
    from payment_simulator.api.main import app

    db_path = simulation_database["db_path"]
    sim_id = simulation_database["simulation_id"]

    # Override database path for API
    import os

    os.environ["DATABASE_PATH"] = db_path

    client = TestClient(app)

    # Test GET /simulations/{sim_id}
    response = client.get(f"/api/simulations/{sim_id}")
    assert response.status_code == 200

    data = response.json()
    assert data["simulation_id"] == sim_id
    assert "config" in data
    assert "summary" in data

    # Verify config structure
    config = data["config"]
    assert "simulation" in config
    assert config["simulation"]["rng_seed"] == 42
    assert "agents" in config
    assert len(config["agents"]) == 12  # 12 banks

    # Verify summary structure
    summary = data["summary"]
    assert "total_ticks" in summary
    assert "total_transactions" in summary
    assert "settlement_rate" in summary
    assert summary["total_transactions"] > 0


@pytest.mark.e2e
def test_agent_list_endpoint(simulation_database):
    """Test that agent list endpoint returns correct data."""
    from fastapi.testclient import TestClient
    from payment_simulator.api.main import app

    db_path = simulation_database["db_path"]
    sim_id = simulation_database["simulation_id"]

    import os

    os.environ["DATABASE_PATH"] = db_path

    client = TestClient(app)

    # Test GET /simulations/{sim_id}/agents
    response = client.get(f"/api/simulations/{sim_id}/agents")
    assert response.status_code == 200

    data = response.json()
    assert "agents" in data

    agents = data["agents"]
    assert len(agents) == 12  # 12 banks

    # Verify agent structure
    agent = agents[0]
    assert "agent_id" in agent
    assert "total_sent" in agent
    assert "total_received" in agent
    assert "total_cost_cents" in agent

    # Verify we have the expected agent IDs
    agent_ids = {a["agent_id"] for a in agents}
    expected_ids = {
        "ALM_CONSERVATIVE",
        "ALM_BALANCED",
        "ALM_AGGRESSIVE",
        "ARB_LARGE_REGIONAL",
        "ARB_MEDIUM_REGIONAL",
        "ARB_SMALL_REGIONAL",
        "GNB_TIER1_BEHEMOTH",
        "GNB_MAJOR_NATIONAL",
        "GNB_REGIONAL_NATIONAL",
        "MIB_PRIME_BROKER",
        "MIB_HEDGE_FUND_DESK",
        "MIB_PROP_TRADING",
    }
    assert agent_ids == expected_ids


@pytest.mark.e2e
def test_transactions_endpoint(simulation_database):
    """Test that transactions endpoint returns paginated data."""
    from fastapi.testclient import TestClient
    from payment_simulator.api.main import app

    db_path = simulation_database["db_path"]
    sim_id = simulation_database["simulation_id"]

    import os

    os.environ["DATABASE_PATH"] = db_path

    client = TestClient(app)

    # Test GET /simulations/{sim_id}/transactions
    response = client.get(f"/api/simulations/{sim_id}/transactions?limit=10")
    assert response.status_code == 200

    data = response.json()
    assert "transactions" in data
    assert len(data["transactions"]) <= 10

    # Verify transaction structure
    if data["transactions"]:
        tx = data["transactions"][0]
        assert "tx_id" in tx
        assert "sender_id" in tx
        assert "receiver_id" in tx
        assert "amount" in tx


@pytest.mark.e2e
def test_simulation_list_endpoint(simulation_database):
    """Test that simulation list endpoint includes our simulation."""
    from fastapi.testclient import TestClient
    from payment_simulator.api.main import app

    db_path = simulation_database["db_path"]
    sim_id = simulation_database["simulation_id"]

    import os

    os.environ["DATABASE_PATH"] = db_path

    client = TestClient(app)

    # Test GET /simulations
    response = client.get("/api/simulations")
    assert response.status_code == 200

    data = response.json()
    assert "simulations" in data

    # Find our simulation
    sims = data["simulations"]
    our_sim = next((s for s in sims if s["simulation_id"] == sim_id), None)

    assert our_sim is not None
    assert our_sim["num_agents"] == 12
    assert our_sim["status"] == "completed"


@pytest.mark.e2e
def test_daily_metrics_data(simulation_database):
    """Test that daily metrics are available for agents."""
    db_manager = simulation_database["db_manager"]
    sim_id = simulation_database["simulation_id"]

    # Query daily agent metrics
    result = db_manager.conn.execute(
        """
        SELECT agent_id, day, opening_balance, closing_balance, 
               transactions_sent, transactions_received
        FROM daily_agent_metrics
        WHERE simulation_id = ?
        ORDER BY agent_id, day
        LIMIT 10
        """,
        [sim_id],
    ).fetchall()

    assert len(result) > 0, "No daily agent metrics found"

    # Verify structure
    for row in result:
        agent_id, day, opening, closing, sent, received = row
        assert isinstance(agent_id, str)
        assert isinstance(day, int)
        assert opening is not None
        assert closing is not None


@pytest.mark.e2e
def test_transaction_data_quality(simulation_database):
    """Test that transaction data is complete and consistent."""
    db_manager = simulation_database["db_manager"]
    sim_id = simulation_database["simulation_id"]

    # Check for transactions with all required fields
    result = db_manager.conn.execute(
        """
        SELECT tx_id, sender_id, receiver_id, amount, 
               arrival_tick, deadline_tick, status
        FROM transactions
        WHERE simulation_id = ?
        LIMIT 10
        """,
        [sim_id],
    ).fetchall()

    assert len(result) > 0, "No transactions found"

    for row in result:
        tx_id, sender_id, receiver_id, amount, arrival, deadline, status = row
        assert tx_id is not None
        assert sender_id is not None
        assert receiver_id is not None
        assert amount > 0
        assert arrival is not None
        assert status in ["settled", "dropped", "pending"]


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v", "-s"])
