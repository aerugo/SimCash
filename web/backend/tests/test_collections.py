"""Tests for library curation: collections, visibility, and admin endpoints."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app import collections as coll_mod
from app.scenario_library import reset_cache as reset_scenario_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    """Reset caches between tests."""
    reset_scenario_cache()
    # Reset Firestore client cache
    coll_mod._fs_db = None
    yield
    reset_scenario_cache()
    coll_mod._fs_db = None


# ---------------------------------------------------------------------------
# 1. Collection metadata
# ---------------------------------------------------------------------------

def test_collections_list():
    resp = client.get("/api/collections")
    assert resp.status_code == 200
    data = resp.json()
    assert "collections" in data
    ids = [c["id"] for c in data["collections"]]
    assert "paper_experiments" in ids
    assert "getting_started" in ids
    assert "crisis_stress" in ids
    for c in data["collections"]:
        assert "scenario_count" in c


def test_collection_detail():
    resp = client.get("/api/collections/paper_experiments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "paper_experiments"
    assert "scenarios" in data
    assert len(data["scenarios"]) > 0


def test_collection_not_found():
    resp = client.get("/api/collections/nonexistent")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. Default visibility
# ---------------------------------------------------------------------------

def test_default_scenario_visibility():
    vis = coll_mod.DEFAULT_SCENARIO_VISIBILITY
    assert vis["preset_2bank_2tick"] is True
    assert vis["preset_2bank_12tick"] is True
    assert vis["bis_liquidity_delay_tradeoff"] is True
    # Archived
    assert vis["test_minimal_eod"] is False
    assert vis["test_near_deadline"] is False


def test_default_policy_visibility():
    vis = coll_mod.DEFAULT_POLICY_VISIBILITY
    assert vis["fifo"] is True
    assert vis["aggressive_market_maker"] is True
    assert vis["smart_splitter"] is True
    # Archived
    assert vis["cost_aware_test"] is False
    assert vis["mock_splitting"] is False


# ---------------------------------------------------------------------------
# 3. Visibility filtering on library endpoints
# ---------------------------------------------------------------------------

def test_scenario_library_filters_archived():
    """Default call should exclude archived scenarios."""
    resp = client.get("/api/scenarios/library")
    assert resp.status_code == 200
    scenarios = resp.json()["scenarios"]
    ids = [s["id"] for s in scenarios]
    # Visible ones present
    assert "preset_2bank_2tick" in ids
    # Archived ones absent
    assert "test_minimal_eod" not in ids


def test_scenario_library_include_archived():
    resp = client.get("/api/scenarios/library?include_archived=true")
    assert resp.status_code == 200
    scenarios = resp.json()["scenarios"]
    ids = [s["id"] for s in scenarios]
    assert "preset_2bank_2tick" in ids
    assert "test_minimal_eod" in ids
    # Check visible flag
    for s in scenarios:
        if s["id"] == "test_minimal_eod":
            assert s["visible"] is False
        if s["id"] == "preset_2bank_2tick":
            assert s["visible"] is True


def test_policy_library_filters_archived():
    resp = client.get("/api/policies/library")
    assert resp.status_code == 200
    policies = resp.json()["policies"]
    ids = [p["id"] for p in policies]
    assert "fifo" in ids
    assert "mock_splitting" not in ids


def test_policy_library_include_archived():
    resp = client.get("/api/policies/library?include_archived=true")
    assert resp.status_code == 200
    policies = resp.json()["policies"]
    ids = [p["id"] for p in policies]
    assert "fifo" in ids
    assert "mock_splitting" in ids


# ---------------------------------------------------------------------------
# 4. Scenario metadata includes collections
# ---------------------------------------------------------------------------

def test_scenario_has_collections_field():
    resp = client.get("/api/scenarios/library?include_archived=true")
    scenarios = resp.json()["scenarios"]
    bis = next(s for s in scenarios if s["id"] == "bis_liquidity_delay_tradeoff")
    assert "collections" in bis
    assert "paper_experiments" in bis["collections"]


# ---------------------------------------------------------------------------
# 5. Admin library endpoint
# ---------------------------------------------------------------------------

def test_admin_library():
    resp = client.get("/api/admin/library")
    assert resp.status_code == 200
    data = resp.json()
    assert "scenarios" in data
    assert "policies" in data
    assert len(data["scenarios"]) > 0
    assert len(data["policies"]) > 0


def test_admin_toggle_visibility_bad_type():
    resp = client.patch(
        "/api/admin/library/invalid/some_id",
        json={"visible": True},
    )
    assert resp.status_code == 400
