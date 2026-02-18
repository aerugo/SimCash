"""Policy JSON editor — validation + custom policy save endpoints for the web UI."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/policies", tags=["policy-editor"])

VALID_ACTIONS = frozenset({
    "Release", "Hold", "Split", "Delay", "NoAction",
    "PostCollateral", "WithdrawCollateral", "HoldCollateral", "ReleaseWithCredit",
})

COMPARISON_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})
COMPOUND_OPS = frozenset({"and", "or", "not"})
VALID_OPS = COMPARISON_OPS | COMPOUND_OPS

REQUIRED_TOP_LEVEL = {"version", "policy_id", "parameters", "payment_tree"}

# In-memory store for custom policies
_custom_policies: dict[str, dict[str, Any]] = {}


class ValidateRequest(BaseModel):
    json_string: str


class SavePolicyRequest(BaseModel):
    json_string: str
    name: str = ""
    description: str = ""


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []
    summary: dict[str, Any] | None = None


def _validate_value(val: Any, path: str, errors: list[str], fields: set[str]) -> None:
    """Validate a Value (left/right) in a condition expression."""
    if isinstance(val, (int, float, str)):
        return  # raw literal
    if isinstance(val, dict):
        if "field" in val:
            fields.add(val["field"])
        elif "param" in val:
            pass  # parameter reference
        elif "value" in val:
            pass  # literal value wrapper
        elif "compute" in val:
            pass  # computed value
        else:
            errors.append(f"{path}: unrecognized value object with keys {sorted(val.keys())}. "
                          f"Expected 'field', 'param', 'value', or 'compute'")
        return
    if val is None:
        errors.append(f"{path}: value is missing")
        return
    errors.append(f"{path}: unexpected value type {type(val).__name__}")


def _validate_condition(cond: dict, path: str, errors: list[str], fields: set[str]) -> None:
    """Validate a condition expression (comparison or compound)."""
    op = cond.get("op")
    if op is None:
        # Provide helpful error suggesting correct format
        keys = sorted(cond.keys())
        # Check if any key looks like an operator
        possible_ops = [k for k in keys if k in COMPARISON_OPS or k in COMPOUND_OPS]
        if possible_ops:
            suggestion = possible_ops[0]
            errors.append(
                f"{path}: condition object must have an 'op' field with one of: "
                f"{', '.join(sorted(VALID_OPS))}. Got keys: {keys}. "
                f'Did you mean {{"op": "{suggestion}", "left": ..., "right": ...}}?'
            )
        else:
            errors.append(
                f"{path}: condition object must have an 'op' field with one of: "
                f"{', '.join(sorted(VALID_OPS))}. Got keys: {keys}"
            )
        return

    if op not in VALID_OPS:
        errors.append(f"{path}: invalid operator '{op}'. Valid: {sorted(VALID_OPS)}")
        return

    if op in COMPARISON_OPS:
        _validate_value(cond.get("left"), f"{path}.left", errors, fields)
        _validate_value(cond.get("right"), f"{path}.right", errors, fields)
    elif op in ("and", "or"):
        conditions = cond.get("conditions")
        if not isinstance(conditions, list):
            errors.append(f"{path}: '{op}' expression requires a 'conditions' array")
        else:
            for i, sub in enumerate(conditions):
                if not isinstance(sub, dict):
                    errors.append(f"{path}.conditions[{i}]: expected object, got {type(sub).__name__}")
                else:
                    _validate_condition(sub, f"{path}.conditions[{i}]", errors, fields)
    elif op == "not":
        sub = cond.get("condition")
        if not isinstance(sub, dict):
            errors.append(f"{path}: 'not' expression requires a 'condition' object")
        else:
            _validate_condition(sub, f"{path}.condition", errors, fields)


def _validate_tree(node: Any, path: str, errors: list[str], actions: set[str], fields: set[str]) -> int:
    """Recursively validate a decision tree node. Returns node count."""
    if not isinstance(node, dict):
        errors.append(f"{path}: expected object, got {type(node).__name__}")
        return 0

    node_type = node.get("type")
    if node_type == "action":
        action = node.get("action")
        if not action:
            errors.append(f"{path}: action node missing 'action' field")
        elif action not in VALID_ACTIONS:
            errors.append(f"{path}: unknown action '{action}'. Valid: {sorted(VALID_ACTIONS)}")
        else:
            actions.add(action)
        return 1

    elif node_type == "condition":
        count = 1
        cond = node.get("condition")
        if not isinstance(cond, dict):
            errors.append(f"{path}: condition node missing 'condition' object")
        else:
            _validate_condition(cond, f"{path}.condition", errors, fields)

        if "on_true" not in node:
            errors.append(f"{path}: condition node missing 'on_true'")
        else:
            count += _validate_tree(node["on_true"], f"{path}.on_true", errors, actions, fields)

        if "on_false" not in node:
            errors.append(f"{path}: condition node missing 'on_false'")
        else:
            count += _validate_tree(node["on_false"], f"{path}.on_false", errors, actions, fields)

        return count

    else:
        errors.append(f"{path}: unknown node type '{node_type}'. Expected 'action' or 'condition'")
        return 1


def validate_policy_json(json_string: str) -> ValidationResult:
    """Parse and validate a policy JSON string."""
    # Parse JSON
    try:
        data = json.loads(json_string)
    except json.JSONDecodeError as e:
        return ValidationResult(valid=False, errors=[f"Invalid JSON: {e}"])

    if not isinstance(data, dict):
        return ValidationResult(valid=False, errors=["Policy must be a JSON object"])

    errors: list[str] = []

    # Check required fields
    for field in REQUIRED_TOP_LEVEL:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")

    if errors:
        return ValidationResult(valid=False, errors=errors)

    # Validate trees
    actions: set[str] = set()
    fields: set[str] = set()
    trees_present: list[str] = []
    total_nodes = 0

    for tree_key in ("payment_tree", "bank_tree", "collateral_tree"):
        if tree_key in data:
            trees_present.append(tree_key)
            total_nodes += _validate_tree(data[tree_key], tree_key, errors, actions, fields)

    if errors:
        return ValidationResult(valid=False, errors=errors)

    summary = {
        "trees_present": trees_present,
        "actions_used": sorted(actions),
        "fields_used": sorted(fields),
        "node_count": total_nodes,
        "parameters": data.get("parameters", {}),
        "policy_id": data.get("policy_id", ""),
        "version": data.get("version", ""),
    }

    return ValidationResult(valid=True, summary=summary)


@router.post("/editor/validate", response_model=ValidationResult)
def validate_policy_endpoint(req: ValidateRequest):
    """Validate a policy JSON string from the editor."""
    return validate_policy_json(req.json_string)


@router.post("/custom")
def save_custom_policy(req: SavePolicyRequest):
    """Save a custom policy. Validates first."""
    result = validate_policy_json(req.json_string)
    if not result.valid:
        raise HTTPException(400, detail=f"Invalid policy: {'; '.join(result.errors)}")
    data = json.loads(req.json_string)
    policy_id = data.get("policy_id") or f"custom_{uuid4().hex[:8]}"
    entry = {
        "id": policy_id,
        "name": req.name or policy_id,
        "description": req.description,
        "json_string": req.json_string,
        "summary": result.summary,
    }
    _custom_policies[policy_id] = entry
    return entry


@router.get("/custom")
def list_custom_policies():
    """List all saved custom policies."""
    return {"policies": list(_custom_policies.values())}


@router.get("/custom/{policy_id}")
def get_custom_policy(policy_id: str):
    """Get a specific custom policy by ID."""
    if policy_id not in _custom_policies:
        raise HTTPException(404, detail="Not found")
    return _custom_policies[policy_id]
