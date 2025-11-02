"""Integration tests for diagnostic transactions endpoint.

Tests that transactions are properly persisted and the GET /simulations/{sim_id}/transactions
endpoint returns transaction data correctly.
"""

import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
from payment_simulator.api.main import app, manager
from payment_simulator.persistence.connection import DatabaseManager


def test_get_transactions_from_database():
    """Test that transactions are returned from database."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        sim_id = "sim-tx-test"

        # Insert simulation
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
                "abc",
                42,
                100,
                1,
                2,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Insert transactions
        transactions = [
            {
                "tx_id": "tx-001",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "is_divisible": False,
                "arrival_tick": 10,
                "arrival_day": 0,
                "deadline_tick": 50,
                "settlement_tick": 15,
                "settlement_day": 0,
                "status": "settled",
                "amount_settled": 100000,
            },
            {
                "tx_id": "tx-002",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_A",
                "amount": 200000,
                "priority": 7,
                "is_divisible": True,
                "arrival_tick": 20,
                "arrival_day": 0,
                "deadline_tick": 80,
                "settlement_tick": 25,
                "settlement_day": 0,
                "status": "settled",
                "amount_settled": 200000,
            },
            {
                "tx_id": "tx-003",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 150000,
                "priority": 3,
                "is_divisible": False,
                "arrival_tick": 30,
                "arrival_day": 0,
                "deadline_tick": 100,
                "settlement_tick": None,
                "settlement_day": None,
                "status": "pending",
                "amount_settled": 0,
            },
        ]

        for tx in transactions:
            conn.execute(
                """
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id,
                    amount, priority, is_divisible,
                    arrival_tick, arrival_day, deadline_tick,
                    settlement_tick, settlement_day,
                    status, amount_settled,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    sim_id,
                    tx["tx_id"],
                    tx["sender_id"],
                    tx["receiver_id"],
                    tx["amount"],
                    tx["priority"],
                    tx["is_divisible"],
                    tx["arrival_tick"],
                    tx["arrival_day"],
                    tx["deadline_tick"],
                    tx["settlement_tick"],
                    tx["settlement_day"],
                    tx["status"],
                    tx["amount_settled"],
                    0,
                    0,
                    0,
                    0,
                ],
            )

        # Query API - GET /simulations/{sim_id}/events
        # (The frontend "View Transactions" button actually links to events page)
        client = TestClient(app)
        response = client.get(f"/simulations/{sim_id}/events")

        assert response.status_code == 200
        data = response.json()

        # Should return events (transactions are shown as Arrival events)
        assert "events" in data
        assert "total" in data
        assert data["total"] == 3  # 3 transactions = 3 arrival events

        # Verify events contain transaction data
        events = data["events"]
        assert len(events) == 3

        # Check first event
        assert events[0]["tx_id"] == "tx-001"
        assert events[0]["sender_id"] == "BANK_A"
        assert events[0]["receiver_id"] == "BANK_B"
        assert events[0]["amount"] == 100000


def test_get_transactions_with_filters():
    """Test that transaction filtering works."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        sim_id = "sim-filter-test"

        # Insert simulation
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
                "abc",
                42,
                100,
                1,
                3,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Insert multiple transactions across different ticks and agents
        for i in range(20):
            conn.execute(
                """
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id,
                    amount, priority, is_divisible,
                    arrival_tick, arrival_day, deadline_tick,
                    status, amount_settled,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    sim_id,
                    f"tx-{i:03d}",
                    f"BANK_{i % 3}",
                    f"BANK_{(i + 1) % 3}",
                    100000 + (i * 10000),
                    5,
                    False,
                    i * 5,
                    0,
                    100,
                    "settled" if i % 3 != 0 else "pending",
                    100000 + (i * 10000) if i % 3 != 0 else 0,
                    0,
                    0,
                    0,
                    0,
                ],
            )

        client = TestClient(app)

        # Test 1: Filter by agent
        response = client.get(f"/simulations/{sim_id}/events?agent_id=BANK_0")
        assert response.status_code == 200
        data = response.json()

        # Should only return events involving BANK_0
        for event in data["events"]:
            assert (
                event["sender_id"] == "BANK_0" or event["receiver_id"] == "BANK_0"
            ), f"Event {event['tx_id']} does not involve BANK_0"

        # Test 2: Filter by tick range
        response = client.get(f"/simulations/{sim_id}/events?tick_min=20&tick_max=40")
        assert response.status_code == 200
        data = response.json()

        # Should only return events in tick range [20, 40]
        for event in data["events"]:
            assert (
                20 <= event["tick"] <= 40
            ), f"Event at tick {event['tick']} outside range [20, 40]"

        # Test 3: Pagination
        response = client.get(f"/simulations/{sim_id}/events?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 5
        assert data["offset"] == 0
        assert len(data["events"]) == 5

        # Test 4: Second page
        response = client.get(f"/simulations/{sim_id}/events?limit=5&offset=5")
        assert response.status_code == 200
        data = response.json()

        assert data["offset"] == 5
        assert len(data["events"]) == 5


def test_get_transaction_lifecycle():
    """Test that transaction lifecycle endpoint works."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        sim_id = "sim-lifecycle-test"

        # Insert simulation
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
                "abc",
                42,
                100,
                1,
                2,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        # Insert parent transaction
        conn.execute(
            """
            INSERT INTO transactions (
                simulation_id, tx_id, sender_id, receiver_id,
                amount, priority, is_divisible,
                arrival_tick, arrival_day, deadline_tick,
                settlement_tick, settlement_day,
                status, amount_settled,
                queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            [
                sim_id,
                "tx-parent",
                "BANK_A",
                "BANK_B",
                300000,
                5,
                True,
                10,
                0,
                50,
                None,
                None,
                "settled",  # Parent marked as settled because children settled
                300000,
                0,
                0,
                0,
                0,
            ],
        )

        # Insert child transactions (split from parent)
        for i in range(3):
            conn.execute(
                """
                INSERT INTO transactions (
                    simulation_id, tx_id, sender_id, receiver_id,
                    amount, priority, is_divisible,
                    arrival_tick, arrival_day, deadline_tick,
                    settlement_tick, settlement_day,
                    status, amount_settled,
                    queue1_ticks, queue2_ticks, total_delay_ticks, delay_cost,
                    parent_tx_id, split_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    sim_id,
                    f"tx-child-{i}",
                    "BANK_A",
                    "BANK_B",
                    100000,
                    5,
                    False,
                    10,
                    0,
                    50,
                    15 + i,
                    0,
                    "settled",
                    100000,
                    0,
                    0,
                    0,
                    0,
                    "tx-parent",
                    i + 1,
                ],
            )

        client = TestClient(app)

        # Test parent transaction lifecycle
        response = client.get(f"/simulations/{sim_id}/transactions/tx-parent/lifecycle")
        assert response.status_code == 200
        data = response.json()

        # Should have transaction details
        assert "transaction" in data
        assert data["transaction"]["tx_id"] == "tx-parent"
        assert data["transaction"]["amount"] == 300000

        # Should have related transactions (children)
        assert "related_transactions" in data
        assert len(data["related_transactions"]) == 3

        # Verify relationships
        for related in data["related_transactions"]:
            assert related["relationship"] in ["split_from", "split_to"]

        # Should have events
        assert "events" in data
        assert len(data["events"]) > 0


def test_empty_transactions_returns_404():
    """Test that querying non-existent simulation returns 404."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        client = TestClient(app)

        # Query non-existent simulation
        response = client.get("/simulations/nonexistent/events")
        assert response.status_code == 404


def test_simulation_with_zero_transactions():
    """Test that simulation with no transactions returns empty list, not error."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db_manager = DatabaseManager(str(db_path))
        db_manager.initialize_schema()

        app.state.db_manager = db_manager
        manager.db_manager = db_manager

        conn = db_manager.get_connection()

        sim_id = "sim-empty"

        # Insert simulation with no transactions
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
                "empty.yaml",
                "empty123",
                42,
                100,
                1,
                2,
                "completed",
                datetime.now(),
                datetime.now(),
            ],
        )

        client = TestClient(app)

        # Should return 404 because no transactions means simulation wasn't properly run
        response = client.get(f"/simulations/{sim_id}/events")
        assert response.status_code == 404
