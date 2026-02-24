"""Programmatic API v1 router for SimCash."""
from __future__ import annotations

import asyncio
import copy
import json
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
    """Create a new experiment (game).

    **rounds** = number of optimization rounds.
    Each round plays through all business days in the scenario. Business days
    are defined in the scenario config (num_days). For example, a scenario with
    25 business days and rounds=10 means the AI optimizes 10 times, playing
    through all 25 days each round.

    **optimization_model** = which LLM to use (e.g. "openai:gpt-4o").
    **constraint_preset** = "simple" (fraction only) or "full" (decision trees).
    **starting_fraction** = initial liquidity fraction (0.0-1.0) for all agents.
    **num_eval_samples** = bootstrap evaluation samples per optimization step.
    """
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
            # Try user's custom scenarios (by ID or custom:ID)
            from .scenario_editor import _store as scenario_store
            sid = config.scenario_id.removeprefix("custom:")
            try:
                custom = scenario_store.get(uid, sid)
                if custom and "config" in custom:
                    import yaml as _yaml
                    raw_yaml = _yaml.safe_load(custom["config"]) if isinstance(custom["config"], str) else custom["config"]
                    # Use the custom scenario name if not explicitly provided
                    if not config.scenario_name and custom.get("name"):
                        config.scenario_name = custom["name"]
                    # Ensure scenario_id has custom: prefix
                    config.scenario_id = f"custom:{sid}"
                elif custom and "raw_config" in custom:
                    raw_yaml = custom["raw_config"] if isinstance(custom["raw_config"], dict) else custom
                    if not config.scenario_name and custom.get("name"):
                        config.scenario_name = custom["name"]
                    config.scenario_id = f"custom:{sid}"
            except Exception:
                pass
        if not raw_yaml:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {config.scenario_id}")
        raw_yaml = copy.deepcopy(raw_yaml)

    # Resolve convenience aliases
    if config.optimization_model and not config.model_override:
        config.model_override = config.optimization_model

    # Convert starting_fraction to starting_policies for all agents
    if config.starting_fraction is not None and not config.starting_policies:
        import yaml as _yaml
        try:
            parsed = _yaml.safe_load(raw_yaml) if isinstance(raw_yaml, str) else raw_yaml
            agents = parsed.get("simulation", parsed).get("agents", [])
            frac = config.starting_fraction
            policy_json = json.dumps({
                "version": "2.0",
                "policy_id": "api-default",
                "parameters": {"initial_liquidity_fraction": frac},
                "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
                "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
            })
            config.starting_policies = {a["id"]: policy_json for a in agents if "id" in a}
        except Exception:
            pass

    prompt_profile = config.prompt_profile
    if config.prompt_profile_id and not prompt_profile:
        from .main import saved_prompt_profiles
        saved = saved_prompt_profiles.get(config.prompt_profile_id)
        if saved:
            prompt_profile = saved.blocks

    total_days = config.rounds
    if config.optimization_schedule == "every_scenario_day":
        import yaml as _yaml
        try:
            parsed = _yaml.safe_load(raw_yaml) if isinstance(raw_yaml, str) else raw_yaml
            scenario_num_days = parsed.get("simulation", {}).get("num_days", 1)
            total_days = config.rounds * scenario_num_days
        except Exception:
            pass

    try:
        game = Game(
            game_id=game_id,
            raw_yaml=raw_yaml,
            use_llm=config.use_llm,
            simulated_ai=config.simulated_ai,
            total_days=total_days,
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
    game._optimization_model = config.model_override or settings_manager.get_settings().optimization_model
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
        "current_round": 0,
        "rounds": config.rounds,
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
        "rounds": config.rounds,
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
            status = "stalled" if game.stalled else ("complete" if game.is_complete else "running")
            checkpoints.append({
                "game_id": gid,
                "scenario_id": getattr(game, '_scenario_id', ''),
                "status": status,
                "current_round": game.current_round,
                "rounds": game.max_rounds,
                "use_llm": game.use_llm,
                "agent_count": len(game.agent_ids),
                "quality": game.quality,
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
    status = "stalled" if game.stalled else ("complete" if game.is_complete else "running")
    return {
        "experiment_id": experiment_id,
        "status": status,
        "stalled": game.stalled,
        "stall_reason": game.stall_reason,
        "rate_limited": game._rate_limited,
        "current_round": game.current_round,
        "rounds": game.max_rounds,
        "agent_ids": game.agent_ids,
        "use_llm": game.use_llm,
        "costs_summary": state.get("costs", {}),
        "optimization_summary": game.optimization_summary,
        "quality": game.quality,
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
    days_out = []
    for d in game.days:
        day_dict = d.to_summary_dict()
        # Add settlement object
        total_arr = d._total_arrivals
        total_set = d._total_settled
        settlement: dict[str, Any] = {
            "system": {
                "settled": total_set,
                "total": total_arr,
                "rate": round(total_set / total_arr, 4) if total_arr else 0.0,
            },
            "per_bank": {},
        }
        for bank_id, stats in (d._event_summary or {}).items():
            arr = stats.get("arrivals", 0)
            stl = stats.get("settled", 0)
            settlement["per_bank"][bank_id] = {
                "settled": stl,
                "total": arr,
                "rate": round(stl / arr, 4) if arr else 0.0,
            }
        day_dict["settlement"] = settlement
        days_out.append(day_dict)
    status = "stalled" if game.stalled else ("complete" if game.is_complete else "running")
    return {
        "experiment_id": experiment_id,
        "status": status,
        "current_round": game.current_round,
        "rounds": game.max_rounds,
        "days": days_out,
        "policies": state.get("policies", {}),
        "policy_history": state.get("policy_history", []),
        "costs": state.get("costs", {}),
        "optimization_summary": game.optimization_summary,
        "quality": game.quality,
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
    if game.stalled:
        raise HTTPException(status_code=400, detail=f"Experiment is stalled: {game.stall_reason}. Use resume endpoint.")

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
        while not game.is_complete and not game.stalled:
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
            if game.stalled:
                break
        _save_game_checkpoint(game)
        return {"days": days, "game": game.get_state()}


@router.post("/experiments/{experiment_id}/resume")
async def resume_experiment(experiment_id: str, uid: str = Depends(get_api_or_firebase_user)):
    """Resume a stalled experiment."""
    from .main import game_manager, _try_load_game, _save_game_checkpoint
    game = game_manager.get(experiment_id)
    if not game:
        game = _try_load_game(experiment_id, uid)
    if not game:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if not game.stalled:
        raise HTTPException(status_code=400, detail="Experiment is not stalled")
    game.stalled = False
    game.stall_reason = ""
    _save_game_checkpoint(game)
    return {"status": "resumed", "experiment_id": experiment_id}


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
