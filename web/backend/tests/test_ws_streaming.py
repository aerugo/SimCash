"""Tests for WebSocket game streaming protocol."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestWSMessageTypes:
    """Verify WebSocket message protocol."""

    def test_step_emits_day_complete(self):
        resp = client.post("/api/games", json={"max_days": 3})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "game_state"

            ws.send_json({"action": "step"})

            msg = ws.receive_json()
            assert msg["type"] == "day_complete"
            assert "data" in msg
            assert msg["data"]["day"] == 0

            # Collect remaining messages until game_state
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "game_state":
                    break

    def test_auto_streams_all_days(self):
        resp = client.post("/api/games", json={"max_days": 3})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "game_state"

            ws.send_json({"action": "auto", "speed_ms": 0})

            day_completes = []
            game_complete = None
            for _ in range(50):
                msg = ws.receive_json()
                if msg["type"] == "day_complete":
                    day_completes.append(msg)
                elif msg["type"] == "game_complete":
                    game_complete = msg
                    break

            assert len(day_completes) == 3
            assert game_complete is not None
            assert game_complete["data"]["is_complete"] is True

    def test_optimization_messages_per_agent(self):
        resp = client.post("/api/games", json={"max_days": 2})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state

            ws.send_json({"action": "step"})

            messages = []
            for _ in range(20):
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "game_state":
                    break

            types = [m["type"] for m in messages]
            assert "day_complete" in types
            assert "optimization_start" in types
            assert "optimization_complete" in types

    def test_step_complete_game_sends_game_complete(self):
        resp = client.post("/api/games", json={"max_days": 1})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state

            # First step completes the game
            ws.send_json({"action": "step"})
            msgs = []
            for _ in range(10):
                msg = ws.receive_json()
                msgs.append(msg)
                if msg["type"] in ("game_state", "game_complete"):
                    break

            # Step again — should get game_complete
            ws.send_json({"action": "step"})
            msg = ws.receive_json()
            assert msg["type"] == "game_complete"
