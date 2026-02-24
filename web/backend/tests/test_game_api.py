"""Phase 2: Game API integration tests — TDD."""
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


@pytest.fixture
def client():
    return TestClient(app)


class TestGameCRUD:
    def test_create_game_default(self, client: TestClient) -> None:
        resp = client.post("/api/games", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        assert data["game"]["current_day"] == 0

    def test_create_game_with_scenario(self, client: TestClient) -> None:
        resp = client.post("/api/games", json={"scenario_id": "3bank_6tick"})
        assert resp.status_code == 200
        assert len(resp.json()["game"]["agent_ids"]) == 3

    def test_create_game_bad_scenario(self, client: TestClient) -> None:
        resp = client.post("/api/games", json={"scenario_id": "nonexistent"})
        assert resp.status_code == 400

    def test_get_game(self, client: TestClient) -> None:
        create = client.post("/api/games", json={}).json()
        gid = create["game_id"]
        resp = client.get(f"/api/games/{gid}")
        assert resp.status_code == 200
        assert resp.json()["game_id"] == gid

    def test_get_game_404(self, client: TestClient) -> None:
        resp = client.get("/api/games/nonexistent")
        assert resp.status_code == 404

    def test_delete_game(self, client: TestClient) -> None:
        gid = client.post("/api/games", json={}).json()["game_id"]
        resp = client.delete(f"/api/games/{gid}")
        assert resp.status_code == 200
        assert client.get(f"/api/games/{gid}").status_code == 404


class TestGameStep:
    def test_step_returns_day(self, client: TestClient) -> None:
        gid = client.post("/api/games", json={}).json()["game_id"]
        resp = client.post(f"/api/games/{gid}/step")
        assert resp.status_code == 200
        data = resp.json()
        assert "day" in data
        assert data["day"]["day"] == 0
        assert data["game"]["current_day"] == 1

    def test_step_with_mock_reasoning(self, client: TestClient) -> None:
        gid = client.post("/api/games", json={
            "use_llm": True, "simulated_ai": True, "rounds": 3
        }).json()["game_id"]
        resp = client.post(f"/api/games/{gid}/step")
        data = resp.json()
        assert "reasoning" in data
        # First step should have reasoning (since use_llm=True and not complete)
        assert len(data["reasoning"]) > 0

    def test_step_after_complete(self, client: TestClient) -> None:
        gid = client.post("/api/games", json={"rounds": 1}).json()["game_id"]
        client.post(f"/api/games/{gid}/step")  # day 0 → complete
        resp = client.post(f"/api/games/{gid}/step")
        assert resp.status_code == 400


class TestAutoRun:
    def test_auto_runs_to_completion(self, client: TestClient) -> None:
        gid = client.post("/api/games", json={"rounds": 3}).json()["game_id"]
        resp = client.post(f"/api/games/{gid}/auto")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["days"]) == 3
        assert data["game"]["is_complete"] is True


class TestScenarioPack:
    SCENARIO_IDS = [
        "2bank_2tick", "2bank_12tick", "2bank_3tick",
        "3bank_6tick", "4bank_8tick", "2bank_stress", "5bank_12tick",
    ]

    @pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
    def test_scenario_creates_and_runs(self, client: TestClient, scenario_id: str) -> None:
        resp = client.post("/api/games", json={"scenario_id": scenario_id, "rounds": 1})
        assert resp.status_code == 200, f"Failed to create {scenario_id}: {resp.text}"
        gid = resp.json()["game_id"]
        step = client.post(f"/api/games/{gid}/step")
        assert step.status_code == 200, f"Failed to step {scenario_id}: {step.text}"
        assert step.json()["day"]["total_cost"] >= 0
