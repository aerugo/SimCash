"""Tests for the policy editor validation endpoint."""
import json
import pytest
from app.policy_editor import validate_policy_json

# ---- Templates (must all pass) ----

RELEASE_ALL = {
    "version": "2.0",
    "policy_id": "custom_release_all",
    "parameters": {"initial_liquidity_fraction": 1.0},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

BALANCE_HOLD = {
    "version": "2.0",
    "policy_id": "custom_balance_hold",
    "parameters": {"initial_liquidity_fraction": 0.5, "hold_threshold": 50000},
    "payment_tree": {
        "type": "condition", "node_id": "check_balance",
        "condition": {"op": ">=", "left": {"field": "balance"}, "right": {"param": "hold_threshold"}},
        "on_true": {"type": "action", "node_id": "release", "action": "Release"},
        "on_false": {
            "type": "condition", "node_id": "check_urgent",
            "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"value": 2}},
            "on_true": {"type": "action", "node_id": "release_urgent", "action": "Release"},
            "on_false": {"type": "action", "node_id": "hold", "action": "Hold"},
        },
    },
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

DEADLINE_DRIVEN = {
    "version": "2.0",
    "policy_id": "custom_deadline_driven",
    "parameters": {"initial_liquidity_fraction": 0.6, "urgent_threshold": 3},
    "payment_tree": {
        "type": "condition", "node_id": "check_deadline",
        "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgent_threshold"}},
        "on_true": {"type": "action", "node_id": "release_urgent", "action": "Release"},
        "on_false": {"type": "action", "node_id": "hold", "action": "Hold"},
    },
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}

SMART_SPLITTER = {
    "version": "2.0",
    "policy_id": "custom_smart_splitter",
    "parameters": {"initial_liquidity_fraction": 0.5, "split_threshold": 100000},
    "payment_tree": {
        "type": "condition", "node_id": "check_amount",
        "condition": {"op": ">=", "left": {"field": "amount"}, "right": {"param": "split_threshold"}},
        "on_true": {"type": "action", "node_id": "split", "action": "Split"},
        "on_false": {"type": "action", "node_id": "release", "action": "Release"},
    },
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}


class TestValidPolicy:
    def test_release_all_valid(self):
        r = validate_policy_json(json.dumps(RELEASE_ALL))
        assert r.valid is True
        assert r.errors == []

    def test_balance_hold_valid(self):
        r = validate_policy_json(json.dumps(BALANCE_HOLD))
        assert r.valid is True

    def test_deadline_driven_valid(self):
        r = validate_policy_json(json.dumps(DEADLINE_DRIVEN))
        assert r.valid is True

    def test_smart_splitter_valid(self):
        r = validate_policy_json(json.dumps(SMART_SPLITTER))
        assert r.valid is True


class TestInvalidJson:
    def test_parse_error(self):
        r = validate_policy_json("{not valid json")
        assert r.valid is False
        assert any("Invalid JSON" in e for e in r.errors)

    def test_not_object(self):
        r = validate_policy_json('"just a string"')
        assert r.valid is False
        assert any("JSON object" in e for e in r.errors)


class TestMissingFields:
    def test_missing_version(self):
        d = {k: v for k, v in RELEASE_ALL.items() if k != "version"}
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("version" in e for e in r.errors)

    def test_missing_payment_tree(self):
        d = {k: v for k, v in RELEASE_ALL.items() if k != "payment_tree"}
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("payment_tree" in e for e in r.errors)

    def test_missing_multiple(self):
        r = validate_policy_json(json.dumps({"version": "2.0"}))
        assert r.valid is False
        assert len(r.errors) >= 2


class TestInvalidActions:
    def test_unknown_action(self):
        d = {**RELEASE_ALL, "payment_tree": {"type": "action", "node_id": "x", "action": "Explode"}}
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("Explode" in e for e in r.errors)

    def test_missing_action_field(self):
        d = {**RELEASE_ALL, "payment_tree": {"type": "action", "node_id": "x"}}
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("missing" in e.lower() for e in r.errors)


class TestInvalidConditions:
    def test_invalid_operator(self):
        d = {
            **RELEASE_ALL,
            "payment_tree": {
                "type": "condition", "node_id": "c",
                "condition": {"op": "~=", "left": {"field": "balance"}, "right": {"value": 1}},
                "on_true": {"type": "action", "node_id": "a", "action": "Release"},
                "on_false": {"type": "action", "node_id": "b", "action": "Hold"},
            },
        }
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("~=" in e for e in r.errors)

    def test_missing_on_true(self):
        d = {
            **RELEASE_ALL,
            "payment_tree": {
                "type": "condition", "node_id": "c",
                "condition": {"op": ">=", "left": {"field": "balance"}, "right": {"value": 1}},
                "on_false": {"type": "action", "node_id": "b", "action": "Hold"},
            },
        }
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("on_true" in e for e in r.errors)

    def test_missing_on_false(self):
        d = {
            **RELEASE_ALL,
            "payment_tree": {
                "type": "condition", "node_id": "c",
                "condition": {"op": ">=", "left": {"field": "balance"}, "right": {"value": 1}},
                "on_true": {"type": "action", "node_id": "a", "action": "Release"},
            },
        }
        r = validate_policy_json(json.dumps(d))
        assert r.valid is False
        assert any("on_false" in e for e in r.errors)


class TestSummary:
    def test_summary_release_all(self):
        r = validate_policy_json(json.dumps(RELEASE_ALL))
        assert r.valid
        s = r.summary
        assert s is not None
        assert "payment_tree" in s["trees_present"]
        assert "bank_tree" in s["trees_present"]
        assert "Release" in s["actions_used"]
        assert "NoAction" in s["actions_used"]
        assert s["node_count"] == 2
        assert s["policy_id"] == "custom_release_all"

    def test_summary_balance_hold(self):
        r = validate_policy_json(json.dumps(BALANCE_HOLD))
        assert r.valid
        s = r.summary
        assert s is not None
        assert "balance" in s["fields_used"]
        assert "ticks_to_deadline" in s["fields_used"]
        assert s["node_count"] == 6  # 2 conditions + 3 actions in payment + 1 bank
        assert set(s["actions_used"]) == {"Release", "Hold", "NoAction"}

    def test_all_templates_pass(self):
        for name, template in [
            ("release_all", RELEASE_ALL),
            ("balance_hold", BALANCE_HOLD),
            ("deadline_driven", DEADLINE_DRIVEN),
            ("smart_splitter", SMART_SPLITTER),
        ]:
            r = validate_policy_json(json.dumps(template))
            assert r.valid, f"Template {name} failed: {r.errors}"
