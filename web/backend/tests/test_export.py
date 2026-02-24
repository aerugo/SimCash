"""Tests for game data export (CSV / JSON)."""
from __future__ import annotations

import csv
import io
import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def game_with_days(client):
    """Create a game and run 2 days, return game_id."""
    res = client.post("/api/games", json={"scenario_id": "2bank_2tick", "rounds": 5, "use_llm": False})
    assert res.status_code == 200
    game_id = res.json()["game_id"]
    # Run 2 days
    client.post(f"/api/games/{game_id}/step")
    client.post(f"/api/games/{game_id}/step")
    return game_id


def test_export_csv(client, game_with_days):
    game_id = game_with_days
    res = client.get(f"/api/games/{game_id}/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers.get("content-disposition", "")

    reader = csv.DictReader(io.StringIO(res.text))
    rows = list(reader)
    # 2 days × 2 agents = 4 rows
    assert len(rows) == 4
    # Check columns
    assert "day" in rows[0]
    assert "agent" in rows[0]
    assert "total_cost" in rows[0]
    assert "settlement_rate" in rows[0]
    assert "initial_liquidity_fraction" in rows[0]
    # Day numbers are 1-indexed
    days = sorted(set(r["day"] for r in rows))
    assert days == ["1", "2"]


def test_export_json(client, game_with_days):
    game_id = game_with_days
    res = client.get(f"/api/games/{game_id}/export?format=json")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]

    data = json.loads(res.text)
    assert data["game_id"] == game_id
    assert len(data["days"]) == 2
    assert "agent_ids" in data


def test_export_not_found(client):
    res = client.get("/api/games/nonexistent/export?format=csv")
    assert res.status_code == 404


def test_export_no_days(client):
    res = client.post("/api/games", json={"scenario_id": "2bank_2tick", "rounds": 5, "use_llm": False})
    game_id = res.json()["game_id"]
    res = client.get(f"/api/games/{game_id}/export?format=csv")
    assert res.status_code == 400


def test_export_invalid_format(client, game_with_days):
    res = client.get(f"/api/games/{game_with_days}/export?format=xml")
    assert res.status_code == 422
