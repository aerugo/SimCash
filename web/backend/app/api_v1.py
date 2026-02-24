"""Programmatic API v1 router for SimCash."""
from __future__ import annotations

import asyncio
import copy
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import get_effective_user, get_api_or_firebase_user
from .api_keys import api_key_store
from .models import CreateGameRequest
from .scenario_pack import get_scenario_pack, get_scenario_by_id, SCENARIO_PACK

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["api-v1"])


# ---- Request/Response models ----

class CreateKeyRequest(BaseModel):
    name: str


# ---- Key Management (Firebase auth only) ----

@router.post("/keys")
async def create_api_key(body: CreateKeyRequest, uid: str = Depends(get_effective_user)):
    """Create a new API key. The raw key is shown only this once."""
    result = api_key_store.create_key(uid, body.name)
    return result


@router.get("/keys")
async def list_api_keys(uid: str = Depends(get_effective_user)):
    """List all API keys for the current user."""
    keys = api_key_store.list_keys(uid)
    return {"keys": keys}


@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str, uid: str = Depends(get_effective_user)):
    """Revoke an API key."""
    ok = api_key_store.revoke_key(uid, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"status": "revoked"}


# ---- Scenarios (API key or Firebase auth) ----

@router.get("/scenarios")
async def list_scenarios(uid: str = Depends(get_api_or_firebase_user)):
    """List all scenarios (built-in + user's custom)."""
    scenarios = []
    for entry in SCENARIO_PACK:
        scenarios.append({
            "id": entry["id"],
            "name": entry["name"],
            "description": entry["description"],
            "num_agents": entry["num_agents"],
            "ticks_per_day": entry["ticks_per_day"],
            "type": "builtin",
        })
    # Add user custom scenarios
    from .scenario_editor import _store as scenario_store
    try:
        custom = scenario_store.list(uid)
        for s in custom:
            scenarios.append({
                "id": s.get("id", ""),
                "name": s.get("name", "Custom"),
                "description": s.get("description", ""),
                "type": "custom",
            })
    except Exception:
        pass
    return {"scenarios": scenarios}


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Get scenario detail with raw config."""
    item = get_scenario_by_id(scenario_id)
    if item:
        return item
    # Try custom
    from .scenario_editor import _store as scenario_store
    try:
        custom = scenario_store.get(uid, scenario_id)
        if custom:
            return custom
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="Scenario not found")


# ---- Policies (API key or Firebase auth) ----

@router.get("/policies")
async def list_policies(uid: str = Depends(get_api_or_firebase_user)):
    """List user's custom policies."""
    from .policy_editor import _store as policy_store
    policies = policy_store.list(uid)
    return {"policies": policies}


@router.get("/policies/{policy_id}")
async def get_policy(policy_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Get a specific policy."""
    from .policy_editor import _store as policy_store
    policy = policy_store.get(uid, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


# ---- Experiments (API key or Firebase auth) ----

@router.post("/experiments")
async def create_experiment(
    config: CreateGameRequest = CreateGameRequest(),
    uid: str = Depends(get_api_or_firebase_user),
):
    """Create a new experiment (game)."""
    # Import from main module at runtime to avoid circular imports
    from .main import (
        game_manager, game_storage, _save_game_checkpoint, _derive_scenario_name,
    )
    from .game import Game
    from .settings import settings_manager

    game_id = str(uuid.uuid4())[:8]

    if config.inline_config:
        raw_yaml = copy.deepcopy(config.inline_config)
    else:
        raw_yaml = get_scenario_by_id(config.scenario_id)
        if not raw_yaml:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {config.scenario_id}")
        raw_yaml = copy.deepcopy(raw_yaml)

    prompt_profile = config.prompt_profile
    if config.prompt_profile_id and not prompt_profile:
        from .main import saved_prompt_profiles
        saved = saved_prompt_profiles.get(config.prompt_profile_id)
        if saved:
            prompt_profile = saved.blocks

    effective_max_days = config.max_days
    if config.optimization_schedule == "every_scenario_day":
        import yaml as _yaml
        try:
            parsed = _yaml.safe_load(raw_yaml) if isinstance(raw_yaml, str) else raw_yaml
            scenario_num_days = parsed.get("simulation", {}).get("num_days", 1)
            effective_max_days = config.max_days * scenario_num_days
        except Exception:
            pass

    try:
        game = Game(
            game_id=game_id,
            raw_yaml=raw_yaml,
            use_llm=config.use_llm,
            simulated_ai=config.simulated_ai,
            max_days=effective_max_days,
            num_eval_samples=config.num_eval_samples,
            optimization_interval=config.optimization_interval,
            constraint_preset=config.constraint_preset,
            include_groups=config.include_groups,
            exclude_groups=config.exclude_groups,
            starting_policies=config.starting_policies,
            optimization_schedule=config.optimization_schedule,
            prompt_profile=prompt_profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    game._scenario_id = config.scenario_id
    game._scenario_name = config.scenario_name or _derive_scenario_name(config.scenario_id, raw_yaml)
    game._optimization_model = config.model_override or settings_manager.settings.optimization_model
    game._uid = uid

    from datetime import datetime, timezone
    game._created_at = datetime.now(timezone.utc).isoformat()
    game_manager[game_id] = game

    game_storage.create_game_db(uid, game_id)
    game_storage.update_index(uid, {
        "game_id": game_id,
        "scenario_id": config.scenario_id,
        "scenario_name": game._scenario_name,
        "optimization_model": getattr(game, '_optimization_model', ''),
        "created_at": game._created_at,
        "updated_at": game._created_at,
        "last_activity_at": game.last_activity_at,
        "current_day": 0,
        "max_days": config.max_days,
        "status": "created",
        "use_llm": config.use_llm,
        "simulated_ai": getattr(game, 'simulated_ai', True),
        "agent_count": len(game.agent_ids),
        "uid": uid,
    })
    _save_game_checkpoint(game)

    return {
        "experiment_id": game_id,
        "status": "created",
        "scenario_id": config.scenario_id,
        "max_days": config.max_days,
        "agent_ids": game.agent_ids,
    }


@router.get("/experiments")
async def list_experiments(
    status: Optional[str] = Query(None),
    scenario_id: Optional[str] = Query(None),
    uid: str = Depends(get_api_or_firebase_user),
):
    """List experiments with optional filtering."""
    from .main import game_storage, game_manager
    checkpoints = game_storage.list_checkpoints(uid)
    # Add in-memory games not in checkpoints
    checkpoint_ids = {c["game_id"] for c in checkpoints}
    for gid, game in game_manager.items():
        if gid not in checkpoint_ids and getattr(game, '_uid', '') == uid:
            checkpoints.append({
                "game_id": gid,
                "scenario_id": getattr(game, '_scenario_id', ''),
                "status": "complete" if game.is_complete else "running",
                "current_day": game.current_day,
                "max_days": game.max_days,
                "use_llm": game.use_llm,
                "agent_count": len(game.agent_ids),
            })
    # Filter
    if status:
        checkpoints = [c for c in checkpoints if c.get("status") == status]
    if scenario_id:
        checkpoints = [c for c in checkpoints if c.get("scenario_id") == scenario_id]
    return {"experiments": checkpoints}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Get experiment status and summary."""
    from .main import game_manager, _try_load_game
    game = game_manager.get(experiment_id)
    if not game:
        game = _try_load_game(experiment_id, uid)
    if not game:
        raise HTTPException(status_code=404, detail="Experiment not found")
    state = game.get_state()
    return {
        "experiment_id": experiment_id,
        "status": "complete" if game.is_complete else "running",
        "current_day": game.current_day,
        "max_days": game.max_days,
        "agent_ids": game.agent_ids,
        "use_llm": game.use_llm,
        "costs_summary": state.get("costs", {}),
    }


@router.get("/experiments/{experiment_id}/results")
async def get_experiment_results(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Get full experiment results."""
    from .main import game_manager, _try_load_game
    game = game_manager.get(experiment_id)
    if not game:
        game = _try_load_game(experiment_id, uid)
    if not game:
        raise HTTPException(status_code=404, detail="Experiment not found")
    state = game.get_state()
    days = [d.to_summary_dict() for d in game.days]
    return {
        "experiment_id": experiment_id,
        "status": "complete" if game.is_complete else "running",
        "current_day": game.current_day,
        "max_days": game.max_days,
        "days": days,
        "policies": state.get("policies", {}),
        "policy_history": state.get("policy_history", []),
        "costs": state.get("costs", {}),
    }


# ---- Experiment Control ----

@router.post("/experiments/{experiment_id}/step")
async def step_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Run next day of experiment."""
    from .main import game_manager, _try_load_game, _save_game_checkpoint, get_game_lock
    game = game_manager.get(experiment_id)
    if not game:
        game = _try_load_game(experiment_id, uid)
    if not game:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if game.is_complete:
        raise HTTPException(status_code=400, detail="Experiment is complete")

    async with get_game_lock(experiment_id):
        loop = asyncio.get_event_loop()
        day = await loop.run_in_executor(None, game.run_day)
        _save_game_checkpoint(game)

        reasoning = {}
        if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
            reasoning = await game.optimize_all_agents()
            day.optimized = True
            if not reasoning:
                day.optimization_failed = True
            _save_game_checkpoint(game)

        return {"day": day.to_summary_dict(), "reasoning": reasoning}


@router.post("/experiments/{experiment_id}/auto")
async def auto_run_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Run all remaining days."""
    from .main import game_manager, _try_load_game, _save_game_checkpoint, get_game_lock
    game = game_manager.get(experiment_id)
    if not game:
        game = _try_load_game(experiment_id, uid)
    if not game:
        raise HTTPException(status_code=404, detail="Experiment not found")

    async with get_game_lock(experiment_id):
        loop = asyncio.get_event_loop()
        days = []
        while not game.is_complete:
            day = await loop.run_in_executor(None, game.run_day)
            reasoning = {}
            if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
                reasoning = await game.optimize_all_agents()
                day.optimized = True
                if not reasoning:
                    day.optimization_failed = True
                if game.optimization_schedule == "every_scenario_day":
                    game._inject_policies_into_orch()
            days.append({"day": day.to_summary_dict(), "reasoning": reasoning})
        _save_game_checkpoint(game)
        return {"days": days, "game": game.get_state()}


@router.post("/experiments/{experiment_id}/stop")
async def stop_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Stop/cancel an auto-running experiment."""
    from .main import game_auto_tasks
    task = game_auto_tasks.get(experiment_id)
    if task and not task.done():
        task.cancel()
        return {"status": "stopped"}
    return {"status": "not_running"}


@router.delete("/experiments/{experiment_id}")
async def delete_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Delete an experiment."""
    from .main import game_manager, game_storage
    if experiment_id in game_manager:
        del game_manager[experiment_id]
    game_storage.delete_game(uid, experiment_id)
    game_storage.delete_checkpoint(uid, experiment_id)
    game_storage.remove_from_index(uid, experiment_id)
    return {"status": "deleted"}
