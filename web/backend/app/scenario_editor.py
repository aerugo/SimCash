"""Scenario Editor — YAML validation and custom scenario management."""
from __future__ import annotations

import uuid
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from payment_simulator.config.schemas import SimulationConfig  # type: ignore[import-untyped]

from .auth import get_effective_user
from .user_content import UserContentStore

router = APIRouter(prefix="/api/scenarios", tags=["scenario-editor"])

_store = UserContentStore("custom_scenarios")


class ValidateRequest(BaseModel):
    yaml_string: str


class CustomScenarioRequest(BaseModel):
    name: str
    description: str
    yaml_string: str


def _extract_summary(config_dict: dict[str, Any], sim_config: SimulationConfig) -> dict[str, Any]:
    """Extract a human-readable summary from a validated config."""
    sim = sim_config.simulation
    agents = sim_config.agents
    cost = sim_config.cost_rates

    features: list[str] = []
    if sim_config.deferred_crediting:
        features.append("Deferred Crediting")
    if sim_config.deadline_cap_at_eod:
        features.append("Deadline Cap at EOD")
    lsm = sim_config.lsm_config
    if lsm and lsm.enable_bilateral:
        features.append("Bilateral LSM")
    if lsm and lsm.enable_cycles:
        features.append("Cycle LSM")
    if sim_config.scenario_events:
        event_types = {e.type for e in sim_config.scenario_events}
        for et in sorted(event_types):
            features.append(f"Event: {et}")

    return {
        "num_agents": len(agents),
        "agent_ids": [a.id for a in agents],
        "ticks_per_day": sim.ticks_per_day,
        "num_days": sim.num_days,
        "total_ticks": sim.ticks_per_day * sim.num_days,
        "features": features,
        "cost_config": {
            "delay_cost_per_tick_per_cent": cost.delay_cost_per_tick_per_cent,
            "eod_penalty": cost.eod_penalty.amount if hasattr(cost.eod_penalty, 'amount') else str(cost.eod_penalty),
            "eod_penalty_mode": cost.eod_penalty.mode if hasattr(cost.eod_penalty, 'mode') else "unknown",
            "deadline_penalty": cost.deadline_penalty.amount if hasattr(cost.deadline_penalty, 'amount') else str(cost.deadline_penalty),
            "deadline_penalty_mode": cost.deadline_penalty.mode if hasattr(cost.deadline_penalty, 'mode') else "unknown",
            "liquidity_cost_per_tick_bps": cost.liquidity_cost_per_tick_bps,
        },
    }


def _validate_yaml(yaml_string: str) -> tuple[dict[str, Any], SimulationConfig]:
    """Parse and validate YAML, returning (config_dict, SimulationConfig). Raises HTTPException on failure."""
    try:
        config_dict = yaml.safe_load(yaml_string)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    if not isinstance(config_dict, dict):
        raise HTTPException(status_code=400, detail="YAML must be a mapping")

    try:
        sim_config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}")

    return config_dict, sim_config


@router.post("/validate")
def validate_scenario(req: ValidateRequest):
    """Parse and validate a YAML scenario string."""
    # Step 1: parse YAML
    try:
        config_dict = yaml.safe_load(req.yaml_string)
    except yaml.YAMLError as e:
        return {"valid": False, "errors": [f"YAML parse error: {e}"]}

    if not isinstance(config_dict, dict):
        return {"valid": False, "errors": ["YAML must be a mapping (dict), not a scalar or list"]}

    # Step 2: validate via SimulationConfig
    try:
        sim_config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        errors = []
        err_str = str(e)
        if "validation error" in err_str.lower():
            for line in err_str.split("\n"):
                line = line.strip()
                if line and not line.startswith("For further") and line != str(type(e).__name__):
                    errors.append(line)
        if not errors:
            errors = [str(e)]
        return {"valid": False, "errors": errors}

    # Check for unknown top-level keys
    KNOWN_TOP_KEYS = {
        "simulation", "agents", "cost_rates", "lsm_config", "scenario_events",
        "queue_config", "rtgs_config", "priority_escalation", "policy_feature_toggles",
    }
    warnings: list[str] = []
    for key in config_dict:
        if key not in KNOWN_TOP_KEYS:
            if key.startswith("cost"):
                warnings.append(f"Unknown key '{key}' — did you mean 'cost_rates'?")
            elif key.startswith("lsm"):
                warnings.append(f"Unknown key '{key}' — did you mean 'lsm_config'?")
            else:
                warnings.append(f"Unknown key '{key}' will be ignored")

    summary = _extract_summary(config_dict, sim_config)
    return {"valid": True, "summary": summary, "warnings": warnings}


@router.post("/custom")
def save_custom_scenario(req: CustomScenarioRequest, uid: str = Depends(get_effective_user)):
    """Save a new custom scenario."""
    config_dict, sim_config = _validate_yaml(req.yaml_string)
    scenario_id = str(uuid.uuid4())[:8]
    summary = _extract_summary(config_dict, sim_config)

    entry = {
        "id": scenario_id,
        "name": req.name,
        "description": req.description,
        "yaml_string": req.yaml_string,
        "config": config_dict,
        "summary": summary,
    }
    return _store.save(uid, scenario_id, entry)


@router.get("/custom")
def list_custom_scenarios(uid: str = Depends(get_effective_user)):
    """List all custom scenarios for the current user."""
    return {"scenarios": _store.list(uid)}


@router.get("/custom/{scenario_id}")
def get_custom_scenario(scenario_id: str, uid: str = Depends(get_effective_user)):
    """Get a specific custom scenario."""
    item = _store.get(uid, scenario_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Custom scenario not found")
    return item


@router.put("/custom/{scenario_id}")
def update_custom_scenario(scenario_id: str, req: CustomScenarioRequest, uid: str = Depends(get_effective_user)):
    """Update an existing custom scenario."""
    existing = _store.get(uid, scenario_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Custom scenario not found")

    config_dict, sim_config = _validate_yaml(req.yaml_string)
    summary = _extract_summary(config_dict, sim_config)

    entry = {
        "id": scenario_id,
        "name": req.name,
        "description": req.description,
        "yaml_string": req.yaml_string,
        "config": config_dict,
        "summary": summary,
    }
    return _store.save(uid, scenario_id, entry)


@router.delete("/custom/{scenario_id}")
def delete_custom_scenario(scenario_id: str, uid: str = Depends(get_effective_user)):
    """Delete a custom scenario."""
    if not _store.delete(uid, scenario_id):
        raise HTTPException(status_code=404, detail="Custom scenario not found")
    return {"status": "deleted"}
