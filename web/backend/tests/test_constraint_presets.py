"""Tests for constraint presets."""
import pytest
from fastapi.testclient import TestClient


def test_preset_metadata():
    from app.constraint_presets import get_preset_metadata
    presets = get_preset_metadata()
    assert len(presets) == 3
    ids = [p["id"] for p in presets]
    assert "simple" in ids
    assert "standard" in ids
    assert "full" in ids
    for p in presets:
        assert "name" in p
        assert "description" in p
        assert "complexity" in p


def test_build_simple():
    from app.constraint_presets import build_constraints
    c = build_constraints("simple")
    assert c is not None
    assert len(c.allowed_parameters) == 1
    assert c.allowed_parameters[0].name == "initial_liquidity_fraction"


def test_build_standard():
    from app.constraint_presets import build_constraints
    c = build_constraints("standard")
    assert len(c.allowed_parameters) == 3
    names = [p.name for p in c.allowed_parameters]
    assert "initial_liquidity_fraction" in names
    assert "split_threshold" in names
    assert "Split" in c.allowed_actions.get("payment_tree", [])


def test_build_full():
    from app.constraint_presets import build_constraints
    c = build_constraints("full")
    assert len(c.allowed_parameters) >= 5
    assert len(c.allowed_fields) > 20
    payment_actions = c.allowed_actions.get("payment_tree", [])
    assert "Release" in payment_actions
    assert "Hold" in payment_actions
    assert "Split" in payment_actions


def test_build_unknown_raises():
    from app.constraint_presets import build_constraints
    with pytest.raises(ValueError, match="Unknown"):
        build_constraints("nonexistent")


def test_lsm_detection():
    from app.constraint_presets import build_constraints
    c = build_constraints("full", {"lsm_config": {"enabled": True}})
    assert c.lsm_enabled is True
    c2 = build_constraints("full", {})
    assert c2.lsm_enabled is False


def test_api_endpoint():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/api/constraint-presets")
    assert resp.status_code == 200
    data = resp.json()
    assert "presets" in data
    assert len(data["presets"]) == 3


def test_create_game_with_preset():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/games", json={
        "scenario_id": "2bank_12tick",
        "use_llm": False,
        "mock_reasoning": True,
        "max_days": 2,
        "constraint_preset": "standard",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "game_id" in data


def test_create_game_invalid_preset():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/games", json={
        "scenario_id": "2bank_12tick",
        "constraint_preset": "invalid",
    })
    assert resp.status_code == 422  # Pydantic validation error
