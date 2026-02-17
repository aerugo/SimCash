"""Tests for the policy library module."""
import pytest
from pathlib import Path
from app.policy_library import (
    PolicyLibrary,
    count_nodes,
    extract_actions,
    extract_fields,
    calculate_complexity,
    build_metadata,
    POLICY_DIR,
    TREE_KEYS,
)

POLICY_FILES = sorted(POLICY_DIR.glob("*.json"))


@pytest.fixture(scope="module")
def library():
    return PolicyLibrary()


class TestPolicyLoading:
    def test_policy_dir_exists(self):
        assert POLICY_DIR.exists()

    def test_all_policy_files_load(self, library):
        assert len(library.list_all()) == len(POLICY_FILES)
        assert len(library.list_all()) >= 25  # at least 25 policies

    def test_all_metadata_fields_populated(self, library):
        for meta in library.list_all():
            assert isinstance(meta["id"], str) and meta["id"]
            assert isinstance(meta["name"], str) and meta["name"]
            assert isinstance(meta["description"], str)
            assert isinstance(meta["version"], str)
            assert meta["complexity"] in ("simple", "moderate", "complex")
            assert meta["category"] in ("Simple", "Adaptive", "Crisis-Resilient", "Specialized")
            assert isinstance(meta["trees_used"], list)
            assert isinstance(meta["actions_used"], list)
            assert isinstance(meta["parameters"], dict)
            assert isinstance(meta["context_fields_used"], list)
            assert isinstance(meta["total_nodes"], int)
            assert meta["total_nodes"] >= 1


class TestHelpers:
    def test_count_nodes_single_action(self):
        tree = {"type": "action", "node_id": "A1", "action": "Release"}
        assert count_nodes(tree) == 1

    def test_count_nodes_condition(self):
        tree = {
            "type": "condition",
            "condition": {"op": ">", "left": {"field": "x"}, "right": {"value": 1}},
            "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
            "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
        }
        assert count_nodes(tree) == 3

    def test_count_nodes_none(self):
        assert count_nodes(None) == 0

    def test_extract_actions_simple(self):
        tree = {"type": "action", "node_id": "A1", "action": "Release"}
        assert extract_actions(tree) == {"Release"}

    def test_extract_actions_condition(self):
        tree = {
            "type": "condition",
            "condition": {},
            "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
            "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
        }
        assert extract_actions(tree) == {"Release", "Hold"}

    def test_extract_fields_simple(self):
        tree = {
            "type": "condition",
            "condition": {"op": ">", "left": {"field": "balance"}, "right": {"value": 100}},
            "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
            "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
        }
        assert extract_fields(tree) == {"balance"}

    def test_extract_fields_compute(self):
        tree = {
            "type": "condition",
            "condition": {
                "op": "<",
                "left": {"compute": {"op": "*", "left": {"field": "a"}, "right": {"field": "b"}}},
                "right": {"field": "c"},
            },
            "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
            "on_false": {"type": "action", "node_id": "A2", "action": "Hold"},
        }
        assert extract_fields(tree) == {"a", "b", "c"}

    def test_complexity_simple(self):
        assert calculate_complexity(1, 1, 1) == "simple"
        assert calculate_complexity(3, 2, 1) == "simple"

    def test_complexity_moderate(self):
        assert calculate_complexity(10, 3, 2) == "moderate"

    def test_complexity_complex(self):
        assert calculate_complexity(20, 5, 3) == "complex"


class TestSpecificPolicies:
    def test_fifo_is_simple(self, library):
        meta = next(m for m in library.list_all() if m["id"] == "fifo")
        assert meta["complexity"] == "simple"
        assert "Release" in meta["actions_used"]
        assert meta["category"] == "Simple"

    def test_smart_splitter_has_split(self, library):
        meta = next(m for m in library.list_all() if m["id"] == "smart_splitter")
        assert "Split" in meta["actions_used"]
        assert "Release" in meta["actions_used"]
        assert meta["total_nodes"] > 5

    def test_smart_splitter_context_fields(self, library):
        meta = next(m for m in library.list_all() if m["id"] == "smart_splitter")
        assert "effective_liquidity" in meta["context_fields_used"]
        assert "remaining_amount" in meta["context_fields_used"]

    def test_get_unknown_returns_none(self, library):
        assert library.get("nonexistent_policy_xyz") is None

    def test_get_returns_raw(self, library):
        result = library.get("fifo")
        assert result is not None
        assert "raw" in result
        assert "payment_tree" in result["raw"]

    def test_get_trees(self, library):
        result = library.get_trees("fifo")
        assert result is not None
        assert "trees" in result
        assert "payment_tree" in result["trees"]


class TestAPIEndpoints:
    @pytest.fixture(scope="class")
    def client(self):
        import os
        os.environ["SIMCASH_AUTH_DISABLED"] = "1"
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_list_policies(self, client):
        resp = client.get("/api/policies/library")
        assert resp.status_code == 200
        data = resp.json()
        assert "policies" in data
        assert len(data["policies"]) >= 25

    def test_get_policy_detail(self, client):
        resp = client.get("/api/policies/library/fifo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "fifo"
        assert "raw" in data

    def test_get_policy_tree(self, client):
        resp = client.get("/api/policies/library/fifo/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "fifo"
        assert "payment_tree" in data["trees"]

    def test_unknown_policy_404(self, client):
        resp = client.get("/api/policies/library/nonexistent_xyz")
        assert resp.status_code == 404

    def test_unknown_policy_tree_404(self, client):
        resp = client.get("/api/policies/library/nonexistent_xyz/tree")
        assert resp.status_code == 404
