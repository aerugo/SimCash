"""Tests for the scenario library module."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.scenario_library import (
    get_library,
    get_scenario_detail,
    reset_cache,
    _load_example_configs,
    _load_preset_scenarios,
    _validate_config,
    _SIM_CONFIG_FIELDS,
)
from app.main import app


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear library cache before each test."""
    reset_cache()
    yield
    reset_cache()


@pytest.fixture
def client():
    return TestClient(app)


# ---- Loading tests ----

class TestExampleConfigsLoad:
    def test_all_example_configs_load(self):
        """All example YAML configs should load without error."""
        configs = _load_example_configs()
        assert len(configs) == 11, f"Expected 11 example configs, got {len(configs)}"

    def test_all_preset_scenarios_load(self):
        """All preset scenarios from scenario_pack should load."""
        presets = _load_preset_scenarios()
        assert len(presets) == 7, f"Expected 7 preset scenarios, got {len(presets)}"

    def test_full_library_loads(self):
        """Full library = examples + presets."""
        library = get_library()
        assert len(library) == 18  # 11 + 7


# ---- Metadata tests ----

class TestMetadata:
    def test_all_metadata_fields_populated(self):
        """Every scenario should have all required metadata fields."""
        required_fields = {
            "id", "name", "description", "category", "tags",
            "num_agents", "ticks_per_day", "num_days", "difficulty",
            "features_used", "cost_config",
        }
        for scenario in get_library():
            for field in required_fields:
                assert field in scenario, f"Missing {field} in {scenario['id']}"

    def test_metadata_types(self):
        """Metadata fields should have correct types."""
        for s in get_library():
            assert isinstance(s["id"], str)
            assert isinstance(s["name"], str)
            assert isinstance(s["description"], str)
            assert isinstance(s["category"], str)
            assert isinstance(s["tags"], list)
            assert isinstance(s["num_agents"], int)
            assert isinstance(s["ticks_per_day"], int)
            assert isinstance(s["num_days"], int)
            assert isinstance(s["difficulty"], str)
            assert isinstance(s["features_used"], list)
            assert isinstance(s["cost_config"], dict)

    def test_category_values(self):
        """Categories should be from the allowed set."""
        allowed = {"Paper Experiments", "Crisis & Stress", "LSM Exploration", "Custom"}
        for s in get_library():
            assert s["category"] in allowed, f"{s['id']} has invalid category: {s['category']}"

    def test_difficulty_values(self):
        """Difficulty should be beginner/intermediate/advanced."""
        allowed = {"beginner", "intermediate", "advanced"}
        for s in get_library():
            assert s["difficulty"] in allowed, f"{s['id']} has invalid difficulty: {s['difficulty']}"

    def test_unique_ids(self):
        """All scenario IDs should be unique."""
        ids = [s["id"] for s in get_library()]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[i for i in ids if ids.count(i) > 1]}"

    def test_num_agents_matches_config(self):
        """num_agents should match actual agent count in raw config."""
        for example in _load_example_configs():
            raw = example["raw_config"]
            assert example["num_agents"] == len(raw["agents"]), \
                f"{example['id']}: metadata says {example['num_agents']} agents, config has {len(raw['agents'])}"

    def test_ticks_per_day_matches_config(self):
        """ticks_per_day should match config."""
        for example in _load_example_configs():
            raw = example["raw_config"]
            expected = raw["simulation"]["ticks_per_day"]
            assert example["ticks_per_day"] == expected, \
                f"{example['id']}: metadata says {example['ticks_per_day']} ticks, config has {expected}"

    def test_num_days_matches_config(self):
        """num_days should match config."""
        for example in _load_example_configs():
            raw = example["raw_config"]
            expected = raw["simulation"].get("num_days", 1)
            assert example["num_days"] == expected, \
                f"{example['id']}: metadata says {example['num_days']} days, config has {expected}"


# ---- Validation tests ----

class TestValidation:
    def test_each_example_validates(self):
        """Each example config should validate via SimulationConfig."""
        for example in _load_example_configs():
            raw = example["raw_config"]
            filtered = {k: v for k, v in raw.items() if k in _SIM_CONFIG_FIELDS}
            # Should not raise
            _validate_config(filtered)

    def test_each_preset_validates(self):
        """Each preset scenario should validate via SimulationConfig."""
        for preset in _load_preset_scenarios():
            raw = preset["raw_config"]
            _validate_config(raw)


# ---- API tests ----

class TestAPI:
    def test_list_library(self, client):
        """GET /api/scenarios/library returns all scenarios."""
        resp = client.get("/api/scenarios/library")
        assert resp.status_code == 200
        data = resp.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) == 18
        # Should not include raw_config in list
        for s in data["scenarios"]:
            assert "raw_config" not in s

    def test_get_scenario_detail(self, client):
        """GET /api/scenarios/library/{id} returns full detail."""
        # Get first scenario id
        library = get_library()
        first_id = library[0]["id"]
        resp = client.get(f"/api/scenarios/library/{first_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == first_id
        assert "raw_config" in data
        assert "agents" in data["raw_config"]

    def test_unknown_scenario_404(self, client):
        """GET /api/scenarios/library/nonexistent returns 404."""
        resp = client.get("/api/scenarios/library/nonexistent_scenario_xyz")
        assert resp.status_code == 404

    def test_preset_scenarios_in_library(self, client):
        """Preset scenarios should appear in the library."""
        resp = client.get("/api/scenarios/library")
        ids = [s["id"] for s in resp.json()["scenarios"]]
        assert "preset_2bank_2tick" in ids
        assert "preset_5bank_12tick" in ids

    def test_example_configs_in_library(self, client):
        """Example configs should appear in the library."""
        resp = client.get("/api/scenarios/library")
        ids = [s["id"] for s in resp.json()["scenarios"]]
        assert "target2_crisis_25day" in ids
        assert "test_minimal_eod" in ids
