"""Policy library: loads, parses, and serves metadata for simulator policy JSONs."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

POLICY_DIR = Path(__file__).resolve().parents[3] / "simulator" / "policies"

TREE_KEYS = ["payment_tree", "bank_tree", "strategic_collateral_tree", "end_of_tick_collateral_tree"]


def count_nodes(tree: dict | None) -> int:
    if not tree or not isinstance(tree, dict):
        return 0
    count = 1
    if tree.get("type") == "condition":
        count += count_nodes(tree.get("on_true"))
        count += count_nodes(tree.get("on_false"))
    return count


def extract_actions(tree: dict | None) -> set[str]:
    if not tree or not isinstance(tree, dict):
        return set()
    actions: set[str] = set()
    if tree.get("type") == "action":
        action = tree.get("action")
        if action:
            actions.add(action)
    elif tree.get("type") == "condition":
        actions |= extract_actions(tree.get("on_true"))
        actions |= extract_actions(tree.get("on_false"))
    return actions


def _extract_fields_from_condition(cond: dict | None) -> set[str]:
    if not cond or not isinstance(cond, dict):
        return set()
    fields: set[str] = set()
    # Compound conditions (and/or)
    if "conditions" in cond:
        for sub in cond["conditions"]:
            fields |= _extract_fields_from_condition(sub)
        return fields
    for side in ("left", "right"):
        val = cond.get(side)
        if isinstance(val, dict):
            if "field" in val:
                fields.add(val["field"])
            if "compute" in val:
                fields |= _extract_fields_from_compute(val["compute"])
    return fields


def _extract_fields_from_compute(comp: dict | None) -> set[str]:
    if not comp or not isinstance(comp, dict):
        return set()
    fields: set[str] = set()
    for side in ("left", "right"):
        val = comp.get(side)
        if isinstance(val, dict):
            if "field" in val:
                fields.add(val["field"])
            if "compute" in val:
                fields |= _extract_fields_from_compute(val["compute"])
    return fields


def extract_fields(tree: dict | None) -> set[str]:
    if not tree or not isinstance(tree, dict):
        return set()
    fields: set[str] = set()
    if tree.get("type") == "condition":
        fields |= _extract_fields_from_condition(tree.get("condition"))
        fields |= extract_fields(tree.get("on_true"))
        fields |= extract_fields(tree.get("on_false"))
    return fields


def calculate_complexity(total_nodes: int, num_actions: int, num_trees: int) -> str:
    if total_nodes <= 5 and num_actions <= 2:
        return "simple"
    if total_nodes <= 15 or (num_actions <= 4 and num_trees <= 2):
        return "moderate"
    return "complex"


def _categorize(policy_data: dict, actions: set[str], fields: set[str], total_nodes: int) -> str:
    has_memory = any("memory" in f or "historical" in f for f in fields)
    has_crisis = any("crisis" in f or "stress" in f for f in fields)
    policy_id = policy_data.get("policy_id", "")
    desc = policy_data.get("description", "").lower()

    if has_crisis or "crisis" in policy_id or "crisis" in desc:
        return "Crisis-Resilient"
    if has_memory or "memory" in policy_id or "adaptive" in policy_id or "adaptive" in desc:
        return "Adaptive"
    if total_nodes <= 5:
        return "Simple"
    return "Specialized"


def _humanize(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def build_metadata(file_path: Path, data: dict) -> dict[str, Any]:
    policy_id = file_path.stem
    trees_used = []
    total_nodes = 0
    all_actions: set[str] = set()
    all_fields: set[str] = set()

    for tk in TREE_KEYS:
        tree = data.get(tk)
        if tree and isinstance(tree, dict):
            trees_used.append(tk)
            total_nodes += count_nodes(tree)
            all_actions |= extract_actions(tree)
            all_fields |= extract_fields(tree)

    actions_list = sorted(all_actions)
    fields_list = sorted(all_fields)
    complexity = calculate_complexity(total_nodes, len(all_actions), len(trees_used))
    category = _categorize(data, all_actions, all_fields, total_nodes)

    return {
        "id": policy_id,
        "name": _humanize(data.get("policy_id", policy_id)),
        "description": data.get("description", ""),
        "version": data.get("version", ""),
        "complexity": complexity,
        "category": category,
        "trees_used": trees_used,
        "actions_used": actions_list,
        "parameters": data.get("parameters", {}),
        "context_fields_used": fields_list,
        "total_nodes": total_nodes,
    }


class PolicyLibrary:
    def __init__(self, policy_dir: Path | None = None):
        self._dir = policy_dir or POLICY_DIR
        self._policies: dict[str, dict[str, Any]] = {}  # id -> {metadata, raw}
        self._load_all()

    def _load_all(self):
        for fp in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(fp.read_text())
                meta = build_metadata(fp, data)
                self._policies[meta["id"]] = {"metadata": meta, "raw": data}
            except Exception:
                pass

    def list_all(self, include_archived: bool = False) -> list[dict[str, Any]]:
        from .collections import get_visibility
        visibility = get_visibility("policy")
        results = []
        for p in self._policies.values():
            entry = dict(p["metadata"])
            entry["visible"] = visibility.get(entry["id"], True)
            if include_archived or entry["visible"]:
                results.append(entry)
        return results

    def get(self, policy_id: str) -> dict[str, Any] | None:
        entry = self._policies.get(policy_id)
        if not entry:
            return None
        return {**entry["metadata"], "raw": entry["raw"]}

    def get_trees(self, policy_id: str) -> dict[str, Any] | None:
        entry = self._policies.get(policy_id)
        if not entry:
            return None
        raw = entry["raw"]
        trees = {}
        for tk in TREE_KEYS:
            if tk in raw and raw[tk] and isinstance(raw[tk], dict):
                trees[tk] = raw[tk]
        return {"id": policy_id, "trees": trees}


# Singleton
_library: PolicyLibrary | None = None


def get_library() -> PolicyLibrary:
    global _library
    if _library is None:
        _library = PolicyLibrary()
    return _library
