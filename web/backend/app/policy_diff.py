"""Policy diff logic for comparing policies across days."""
from __future__ import annotations

from typing import Any


def diff_parameters(old_policy: dict, new_policy: dict) -> list[dict[str, Any]]:
    """Compare parameter dicts and return list of changes."""
    old_params = old_policy.get("parameters", {})
    new_params = new_policy.get("parameters", {})
    all_keys = sorted(set(old_params.keys()) | set(new_params.keys()))
    changes = []
    for key in all_keys:
        old_val = old_params.get(key)
        new_val = new_params.get(key)
        if old_val != new_val:
            changes.append({"param": key, "old": old_val, "new": new_val})
    return changes


def _collect_nodes(tree: dict | None) -> dict[str, dict]:
    """Flatten a tree into {node_id: node_dict}."""
    if not tree or not isinstance(tree, dict):
        return {}
    nodes: dict[str, dict] = {}
    node_id = tree.get("node_id", "unknown")
    nodes[node_id] = tree
    # Recurse into children
    for child_key in ("true_branch", "false_branch", "children", "left", "right"):
        child = tree.get(child_key)
        if isinstance(child, dict):
            nodes.update(_collect_nodes(child))
        elif isinstance(child, list):
            for c in child:
                if isinstance(c, dict):
                    nodes.update(_collect_nodes(c))
    return nodes


def diff_tree(old_tree: dict | None, new_tree: dict | None) -> dict[str, list]:
    """Diff two decision trees, returning added/removed/modified nodes."""
    old_nodes = _collect_nodes(old_tree)
    new_nodes = _collect_nodes(new_tree)
    old_ids = set(old_nodes.keys())
    new_ids = set(new_nodes.keys())

    added = [{"node_id": nid, **new_nodes[nid]} for nid in sorted(new_ids - old_ids)]
    removed = [{"node_id": nid, **old_nodes[nid]} for nid in sorted(old_ids - new_ids)]
    modified = []
    for nid in sorted(old_ids & new_ids):
        if old_nodes[nid] != new_nodes[nid]:
            modified.append({
                "node_id": nid,
                "old": old_nodes[nid],
                "new": new_nodes[nid],
            })

    return {"added_nodes": added, "removed_nodes": removed, "modified_nodes": modified}


def diff_policies(old_policy: dict, new_policy: dict) -> dict[str, Any]:
    """Full structural diff between two policies."""
    param_changes = diff_parameters(old_policy, new_policy)

    tree_changes = {}
    for tree_key in ("payment_tree", "bank_tree"):
        tree_changes[tree_key] = diff_tree(
            old_policy.get(tree_key),
            new_policy.get(tree_key),
        )

    # Build summary
    parts = []
    for pc in param_changes:
        old_v = pc["old"]
        new_v = pc["new"]
        if isinstance(old_v, float) and isinstance(new_v, float):
            parts.append(f"Changed {pc['param']} from {old_v:.1%} to {new_v:.1%}.")
        else:
            parts.append(f"Changed {pc['param']} from {old_v} to {new_v}.")

    for tree_key, tc in tree_changes.items():
        if tc["added_nodes"]:
            parts.append(f"Added {len(tc['added_nodes'])} node(s) to {tree_key}.")
        if tc["removed_nodes"]:
            parts.append(f"Removed {len(tc['removed_nodes'])} node(s) from {tree_key}.")
        if tc["modified_nodes"]:
            parts.append(f"Modified {len(tc['modified_nodes'])} node(s) in {tree_key}.")

    summary = " ".join(parts) if parts else "No changes."

    return {
        "parameter_changes": param_changes,
        "tree_changes": tree_changes,
        "summary": summary,
    }
