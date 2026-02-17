"""Scenario Editor — YAML validation and custom scenario management."""
from __future__ import annotations

import uuid
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from payment_simulator.config.schemas import SimulationConfig  # type: ignore[import-untyped]

router = APIRouter(prefix="/api/scenarios", tags=["scenario-editor"])

# In-memory store for custom scenarios
_custom_scenarios: dict[str, dict[str, Any]] = {}


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
            "eod_penalty_per_transaction": cost.eod_penalty_per_transaction,
            "deadline_penalty": cost.deadline_penalty,
            "liquidity_cost_per_tick_bps": cost.liquidity_cost_per_tick_bps,
        },
    }


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
        # Extract readable error messages from pydantic validation
        errors = []
        err_str = str(e)
        if "validation error" in err_str.lower():
            # Pydantic v2 errors — extract individual messages
            for line in err_str.split("\n"):
                line = line.strip()
                if line and not line.startswith("For further") and line != str(type(e).__name__):
                    errors.append(line)
        if not errors:
            errors = [str(e)]
        return {"valid": False, "errors": errors}

    summary = _extract_summary(config_dict, sim_config)
    return {"valid": True, "summary": summary}


@router.post("/custom")
def save_custom_scenario(req: CustomScenarioRequest):
    """Save a custom scenario to in-memory store."""
    # Validate first
    try:
        config_dict = yaml.safe_load(req.yaml_string)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    if not isinstance(config_dict, dict):
        raise HTTPException(status_code=400, detail="YAML must be a mapping")

    try:
        sim_config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Validation failed: {e}")

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
    _custom_scenarios[scenario_id] = entry
    return entry


@router.get("/custom")
def list_custom_scenarios():
    """List all saved custom scenarios."""
    return {"scenarios": list(_custom_scenarios.values())}


@router.get("/custom/{scenario_id}")
def get_custom_scenario(scenario_id: str):
    """Get a specific custom scenario."""
    if scenario_id not in _custom_scenarios:
        raise HTTPException(status_code=404, detail="Custom scenario not found")
    return _custom_scenarios[scenario_id]
