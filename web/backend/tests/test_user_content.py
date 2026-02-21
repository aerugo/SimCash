"""Tests for user content CRUD (custom scenarios and policies)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Minimal valid scenario YAML (must match SimulationConfig schema)
VALID_YAML = """
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42
agents:
  - id: BANK_A
    opening_balance: 0
    liquidity_pool: 1000000
    unsecured_cap: 0
    payment_generation:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_B: 1.0
      deadline_range:
        min_ticks: &dr 1
        max_ticks: 4
  - id: BANK_B
    opening_balance: 0
    liquidity_pool: 1000000
    unsecured_cap: 0
    payment_generation:
      rate_per_tick: 2.0
      amount_distribution:
        type: LogNormal
        mean: 10000
        std_dev: 5000
      counterparty_weights:
        BANK_A: 1.0
      deadline_range:
        min_ticks: *dr
        max_ticks: 4
cost_rates:
  delay_cost_per_tick_per_cent: 0.2
  eod_penalty_per_transaction: 100000
  deadline_penalty: 50000
  liquidity_cost_per_tick_bps: 500
"""

# Minimal valid policy JSON
VALID_POLICY = json.dumps({
    "version": "2.0",
    "policy_id": "test_pol",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
})


class TestScenarioCRUD:
    def test_save_and_list_scenarios(self):
        # Save two scenarios
        for i in range(2):
            r = client.post("/api/scenarios/custom", json={
                "name": f"Scenario {i}",
                "description": f"Desc {i}",
                "yaml_string": VALID_YAML,
            })
            assert r.status_code == 200, r.text

        r = client.get("/api/scenarios/custom")
        assert r.status_code == 200
        scenarios = r.json()["scenarios"]
        assert len(scenarios) >= 2

    def test_get_scenario(self):
        r = client.post("/api/scenarios/custom", json={
            "name": "Get Test",
            "description": "desc",
            "yaml_string": VALID_YAML,
        })
        sid = r.json()["id"]

        r = client.get(f"/api/scenarios/custom/{sid}")
        assert r.status_code == 200
        assert r.json()["name"] == "Get Test"

    def test_update_scenario(self):
        r = client.post("/api/scenarios/custom", json={
            "name": "Original",
            "description": "desc",
            "yaml_string": VALID_YAML,
        })
        sid = r.json()["id"]

        r = client.put(f"/api/scenarios/custom/{sid}", json={
            "name": "Updated",
            "description": "new desc",
            "yaml_string": VALID_YAML,
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Updated"

        # Verify timestamps
        data = r.json()
        assert "created_at" in data
        assert "updated_at" in data

    def test_delete_scenario(self):
        r = client.post("/api/scenarios/custom", json={
            "name": "ToDelete",
            "description": "desc",
            "yaml_string": VALID_YAML,
        })
        sid = r.json()["id"]

        r = client.delete(f"/api/scenarios/custom/{sid}")
        assert r.status_code == 200

        r = client.get(f"/api/scenarios/custom/{sid}")
        assert r.status_code == 404

    def test_save_invalid_scenario_rejected(self):
        r = client.post("/api/scenarios/custom", json={
            "name": "Bad",
            "description": "desc",
            "yaml_string": "not: valid: yaml: [",
        })
        assert r.status_code == 400

    def test_delete_nonexistent_returns_404(self):
        r = client.delete("/api/scenarios/custom/nonexistent")
        assert r.status_code == 404


class TestPolicyCRUD:
    def test_save_and_list_policies(self):
        for i in range(2):
            policy = json.dumps({
                "version": "2.0",
                "policy_id": f"test_pol_{i}",
                "parameters": {"initial_liquidity_fraction": 0.5},
                "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
            })
            r = client.post("/api/policies/custom", json={
                "name": f"Policy {i}",
                "description": f"Desc {i}",
                "json_string": policy,
            })
            assert r.status_code == 200, r.text

        r = client.get("/api/policies/custom")
        assert r.status_code == 200
        policies = r.json()["policies"]
        assert len(policies) >= 2

    def test_update_policy(self):
        r = client.post("/api/policies/custom", json={
            "name": "Original Pol",
            "description": "desc",
            "json_string": VALID_POLICY,
        })
        pid = r.json()["id"]

        r = client.put(f"/api/policies/custom/{pid}", json={
            "name": "Updated Pol",
            "description": "new desc",
            "json_string": VALID_POLICY,
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Pol"

    def test_delete_policy(self):
        r = client.post("/api/policies/custom", json={
            "name": "ToDelete",
            "description": "desc",
            "json_string": VALID_POLICY,
        })
        pid = r.json()["id"]

        r = client.delete(f"/api/policies/custom/{pid}")
        assert r.status_code == 200

        r = client.get(f"/api/policies/custom/{pid}")
        assert r.status_code == 404

    def test_save_invalid_policy_rejected(self):
        r = client.post("/api/policies/custom", json={
            "name": "Bad",
            "description": "desc",
            "json_string": '{"not": "valid policy"}',
        })
        assert r.status_code == 400


class TestUserIsolation:
    def test_user_isolation(self):
        """With auth disabled, all requests use 'dev-user' so isolation
        is tested at the store level directly."""
        from app.user_content import UserContentStore
        store = UserContentStore("test_isolation")

        store.save("user-a", "item1", {"name": "A's item"})
        store.save("user-b", "item2", {"name": "B's item"})

        a_items = store.list("user-a")
        b_items = store.list("user-b")

        assert len(a_items) == 1
        assert a_items[0]["name"] == "A's item"
        assert len(b_items) == 1
        assert b_items[0]["name"] == "B's item"

        # user-a can't see user-b's item
        assert store.get("user-a", "item2") is None
