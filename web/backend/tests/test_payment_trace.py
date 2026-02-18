"""Tests for payment lifecycle trace feature."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from app.payment_trace import build_payment_traces


@pytest.fixture
def client():
    return TestClient(app)


class TestBuildPaymentTraces:
    """Unit tests for the trace builder."""

    def test_empty_events(self):
        assert build_payment_traces([]) == []

    def test_arrival_and_settlement(self):
        events = [
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "BANK_A", "receiver_id": "BANK_B", "amount": 1000, "deadline": 2},
            {"event_type": "RtgsSubmission", "tick": 0, "tx_id": "tx1",
             "sender": "BANK_A", "receiver": "BANK_B", "amount": 1000},
            {"event_type": "RtgsImmediateSettlement", "tick": 0, "tx_id": "tx1",
             "sender": "BANK_A", "receiver": "BANK_B", "amount": 1000},
        ]
        traces = build_payment_traces(events)
        assert len(traces) == 1
        p = traces[0]
        assert p["tx_id"] == "tx1"
        assert p["sender"] == "BANK_A"
        assert p["receiver"] == "BANK_B"
        assert p["amount"] == 1000
        assert p["arrival_tick"] == 0
        assert p["deadline_tick"] == 2
        assert p["settled_tick"] == 0
        assert p["status"] == "settled"
        assert len(p["lifecycle"]) == 3
        assert p["index"] == 0

    def test_unsettled_payment_is_failed(self):
        events = [
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "A", "receiver_id": "B", "amount": 500, "deadline": 1},
            {"event_type": "QueuedRtgs", "tick": 0, "tx_id": "tx1"},
        ]
        traces = build_payment_traces(events)
        assert traces[0]["status"] == "failed"
        assert traces[0]["settled_tick"] is None

    def test_delayed_settlement(self):
        events = [
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "A", "receiver_id": "B", "amount": 500, "deadline": 1},
            {"event_type": "RtgsImmediateSettlement", "tick": 3, "tx_id": "tx1",
             "sender": "A", "receiver": "B", "amount": 500},
        ]
        traces = build_payment_traces(events)
        assert traces[0]["status"] == "delayed"

    def test_multiple_payments_sorted(self):
        events = [
            {"event_type": "Arrival", "tick": 2, "tx_id": "tx2",
             "sender_id": "B", "receiver_id": "A", "amount": 200, "deadline": 4},
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "A", "receiver_id": "B", "amount": 100, "deadline": 2},
            {"event_type": "RtgsImmediateSettlement", "tick": 0, "tx_id": "tx1",
             "sender": "A", "receiver": "B", "amount": 100},
            {"event_type": "RtgsImmediateSettlement", "tick": 2, "tx_id": "tx2",
             "sender": "B", "receiver": "A", "amount": 200},
        ]
        traces = build_payment_traces(events)
        assert len(traces) == 2
        assert traces[0]["tx_id"] == "tx1"  # earlier arrival
        assert traces[1]["tx_id"] == "tx2"
        assert traces[0]["index"] == 0
        assert traces[1]["index"] == 1

    def test_events_without_tx_id_ignored(self):
        events = [
            {"event_type": "CostAccrual", "tick": 0, "agent_id": "BANK_A"},
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "A", "receiver_id": "B", "amount": 100, "deadline": 1},
            {"event_type": "RtgsImmediateSettlement", "tick": 0, "tx_id": "tx1",
             "sender": "A", "receiver": "B", "amount": 100},
        ]
        traces = build_payment_traces(events)
        assert len(traces) == 1

    def test_bilateral_offset_counts_as_settled(self):
        events = [
            {"event_type": "Arrival", "tick": 0, "tx_id": "tx1",
             "sender_id": "A", "receiver_id": "B", "amount": 100, "deadline": 3},
            {"event_type": "BilateralOffset", "tick": 1, "tx_id": "tx1",
             "sender": "A", "receiver": "B", "amount": 100},
        ]
        traces = build_payment_traces(events)
        assert traces[0]["status"] == "settled"
        assert traces[0]["settlement_type"] == "BilateralOffset"


class TestPaymentTraceAPI:
    """Integration tests for the API endpoint."""

    def test_get_payments_for_day(self, client: TestClient):
        # Create game and run a day
        resp = client.post("/api/games", json={"scenario_id": "2bank_2tick"})
        assert resp.status_code == 200
        gid = resp.json()["game_id"]

        resp = client.post(f"/api/games/{gid}/step")
        assert resp.status_code == 200

        # Get payment traces
        resp = client.get(f"/api/games/{gid}/days/0/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["day"] == 0
        assert data["total_payments"] > 0
        payments = data["payments"]
        assert len(payments) == data["total_payments"]

        # Check structure of first payment
        p = payments[0]
        assert "tx_id" in p
        assert "sender" in p
        assert "receiver" in p
        assert "amount" in p
        assert "arrival_tick" in p
        assert "deadline_tick" in p
        assert "status" in p
        assert p["status"] in ("settled", "delayed", "failed")
        assert "lifecycle" in p
        assert len(p["lifecycle"]) > 0
        assert "index" in p

    def test_get_payments_game_not_found(self, client: TestClient):
        resp = client.get("/api/games/nonexistent/days/0/payments")
        assert resp.status_code == 404

    def test_get_payments_day_not_found(self, client: TestClient):
        resp = client.post("/api/games", json={})
        gid = resp.json()["game_id"]
        resp = client.get(f"/api/games/{gid}/days/99/payments")
        assert resp.status_code == 404
