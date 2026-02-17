"""FastAPI app for SimCash Web Sandbox."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .auth import get_current_user, get_ws_user, get_admin_user, get_current_user_email

from .models import (
    CompareRequest,
    CreateGameRequest,
    CreateSimResponse,
    HumanDecision,
    ManualPolicy,
    PolicyRule,
    PresetScenario,
    SavedScenario,
    ScenarioConfig,
)
from .simulation import SimulationManager
from .game import Game
from .storage import GameStorage
from .scenario_pack import get_scenario_pack, get_scenario_by_id, SCENARIO_PACK
from .scenario_library import get_library, get_scenario_detail
from .policy_library import get_library as get_policy_library
from .policy_diff import diff_policies
from .policy_editor import router as policy_editor_router
from .scenario_editor import router as scenario_editor_router
from .admin import user_manager
from . import config as app_config
from pydantic import BaseModel as PydanticBaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="SimCash Web Sandbox", version="0.2.0")


@app.on_event("startup")
def _seed_admin():
    """Ensure initial admin exists in Firestore."""
    if not app_config.is_auth_disabled():
        try:
            user_manager.seed_admin("hugi@sensestack.xyz")
        except Exception as e:
            logger.warning("Failed to seed admin: %s", e)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenario_editor_router)

app.include_router(policy_editor_router)

manager = SimulationManager()
game_manager: dict[str, Game] = {}
game_storage = GameStorage(
    bucket_name=app_config.GCS_BUCKET,
    storage_mode=app_config.STORAGE_MODE if app_config.STORAGE_MODE != "memory" else "local",
)

# In-memory stores
saved_scenarios: dict[str, SavedScenario] = {}
saved_policies: dict[str, ManualPolicy] = {}


# ---- Health ----

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- Presets ----

@app.get("/api/presets")
def list_presets():
    """List available scenario presets."""
    return {
        "presets": [
            {
                "id": "exp1",
                "name": "2-Period Deterministic",
                "description": "2 banks, 2 ticks. Validates Nash equilibrium with deferred crediting.",
                "ticks_per_day": 2,
                "num_agents": 2,
            },
            {
                "id": "exp2",
                "name": "12-Period Stochastic",
                "description": "2 banks, 12 ticks with stochastic arrivals.",
                "ticks_per_day": 12,
                "num_agents": 2,
            },
            {
                "id": "exp3",
                "name": "3-Period Joint Optimization",
                "description": "2 banks, 3 ticks. Joint liquidity & timing decisions.",
                "ticks_per_day": 3,
                "num_agents": 2,
            },
        ]
    }


# ---- Simulations CRUD ----

@app.post("/api/simulations", response_model=CreateSimResponse)
def create_simulation(config: ScenarioConfig):
    """Create a new simulation."""
    try:
        sim_id = manager.create(config)
        sim = manager.get(sim_id)
        return CreateSimResponse(
            sim_id=sim_id,
            config=sim.raw_config if sim else {},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/simulations/{sim_id}")
def get_simulation(sim_id: str):
    """Get current simulation state."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim.get_state()


@app.post("/api/simulations/{sim_id}/tick")
def tick_simulation(sim_id: str):
    """Execute one tick."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return sim.do_tick()


@app.post("/api/simulations/{sim_id}/run")
def run_simulation(sim_id: str):
    """Run all remaining ticks."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    results = []
    while not sim.is_complete:
        results.append(sim.do_tick())
    return {"ticks": results, "final_state": sim.get_state()}


@app.delete("/api/simulations/{sim_id}")
def delete_simulation(sim_id: str):
    """Delete a simulation."""
    if manager.delete(sim_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Simulation not found")


# ---- Config Inspector ----

@app.get("/api/simulations/{sim_id}/config")
def get_simulation_config(sim_id: str):
    """Get the full FFI config for a simulation."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {
        "raw_config": sim.raw_config,
        "ffi_config": sim.ffi_config,
    }


# ---- Export ----

@app.get("/api/simulations/{sim_id}/export")
def export_simulation(sim_id: str):
    """Export full simulation data as JSON."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {
        "sim_id": sim.sim_id,
        "raw_config": sim.raw_config,
        "ffi_config": sim.ffi_config,
        "total_ticks": sim.total_ticks,
        "is_complete": sim.is_complete,
        "current_tick": sim.orch.current_tick(),
        "tick_history": sim.tick_history,
        "balance_history": sim.balance_history,
        "cost_history": sim.cost_history,
    }


# ---- Replay ----

@app.get("/api/simulations/{sim_id}/replay/{tick}")
def replay_tick(sim_id: str, tick: int):
    """Get simulation state at a specific tick from recorded history."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if tick < 0 or tick >= len(sim.tick_history):
        raise HTTPException(status_code=400, detail=f"Tick {tick} not in history (0-{len(sim.tick_history)-1})")
    return sim.tick_history[tick]


@app.get("/api/simulations/{sim_id}/replay")
def replay_info(sim_id: str):
    """Get replay metadata."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {
        "sim_id": sim.sim_id,
        "total_recorded_ticks": len(sim.tick_history),
        "is_complete": sim.is_complete,
    }


# ---- Reasoning ----

@app.get("/api/simulations/{sim_id}/reasoning")
def get_reasoning(sim_id: str):
    """Get all reasoning traces for a simulation."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {"reasoning": sim.reasoning_history}


# ---- Scenario Events ----

@app.get("/api/simulations/{sim_id}/events")
def get_scenario_events(sim_id: str):
    """Get all events from tick history."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    all_events = []
    for tick_data in sim.tick_history:
        all_events.extend(tick_data.get("events", []))
    return {"events": all_events, "total": len(all_events)}


# ---- Comparison ----

@app.post("/api/compare")
def compare_runs(req: CompareRequest):
    """Run multiple scenario+policy combos and compare results."""
    results = []
    for run in req.runs:
        try:
            sim_id = manager.create(run.scenario)
            sim = manager.get(sim_id)
            if not sim:
                results.append({"error": "Failed to create"})
                continue
            # Run to completion
            while not sim.is_complete:
                sim.do_tick()
            state = sim.get_state()
            results.append({
                "sim_id": sim_id,
                "config": sim.raw_config,
                "final_state": state,
                "total_cost": sum(
                    a["costs"]["total"] for a in state["agents"].values()
                ),
            })
        except Exception as e:
            results.append({"error": str(e)})
    return {"results": results}


# ---- Scenario Library (read-only, from example configs + presets) ----

@app.get("/api/scenarios/library")
def list_scenario_library():
    """List all scenarios from example configs + presets with metadata."""
    return {"scenarios": get_library()}


@app.get("/api/scenarios/library/{scenario_id}")
def get_scenario_library_item(scenario_id: str):
    """Get full scenario detail (metadata + raw config)."""
    detail = get_scenario_detail(scenario_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return detail


# ---- Scenario Library CRUD ----

@app.get("/api/scenarios")
def list_scenarios():
    return {"scenarios": list(saved_scenarios.values())}


@app.post("/api/scenarios")
def create_scenario(scenario: SavedScenario):
    scenario.id = str(uuid.uuid4())[:8]
    saved_scenarios[scenario.id] = scenario
    return scenario


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    if scenario_id not in saved_scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return saved_scenarios[scenario_id]


@app.put("/api/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, scenario: SavedScenario):
    if scenario_id not in saved_scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    scenario.id = scenario_id
    saved_scenarios[scenario_id] = scenario
    return scenario


@app.delete("/api/scenarios/{scenario_id}")
def delete_scenario(scenario_id: str):
    if scenario_id not in saved_scenarios:
        raise HTTPException(status_code=404, detail="Scenario not found")
    del saved_scenarios[scenario_id]
    return {"status": "deleted"}


# ---- Policy Management ----

@app.get("/api/policies")
def list_policies():
    return {"policies": list(saved_policies.values())}


@app.post("/api/policies")
def create_policy(policy: ManualPolicy):
    policy.id = str(uuid.uuid4())[:8]
    saved_policies[policy.id] = policy
    return policy


@app.post("/api/policies/validate")
def validate_policy(policy: ManualPolicy):
    """Validate policy rules syntax."""
    errors = []
    valid_operators = ["<", ">", "<=", ">=", "==", "!="]
    valid_fields = ["balance", "tick", "queue_size", "available_liquidity", "amount"]
    for i, rule in enumerate(policy.rules):
        # Simple validation: condition should be "field op value"
        parts = rule.condition.strip().split()
        if len(parts) != 3:
            errors.append(f"Rule {i}: Expected 'field operator value', got '{rule.condition}'")
            continue
        field, op, val = parts
        if field not in valid_fields:
            errors.append(f"Rule {i}: Unknown field '{field}'. Valid: {valid_fields}")
        if op not in valid_operators:
            errors.append(f"Rule {i}: Unknown operator '{op}'. Valid: {valid_operators}")
        try:
            float(val)
        except ValueError:
            errors.append(f"Rule {i}: Value '{val}' is not a number")
    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


@app.delete("/api/policies/{policy_id}")
def delete_policy(policy_id: str):
    if policy_id not in saved_policies:
        raise HTTPException(status_code=404, detail="Policy not found")
    del saved_policies[policy_id]
    return {"status": "deleted"}


# ---- Policy Optimization ----

@app.get("/api/simulations/{sim_id}/policy")
def get_policy(sim_id: str):
    """Get the current policy for a simulation."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return {
        "policies": sim.policies,
        "iteration": sim.iteration,
        "optimization_history": sim.optimization_history,
        "policy_cost_history": sim.policy_cost_history,
    }


@app.post("/api/simulations/{sim_id}/optimize")
async def optimize_simulation(sim_id: str):
    """Run one LLM optimization iteration."""
    sim = manager.get(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")
    if not sim.is_complete:
        raise HTTPException(status_code=400, detail="Run simulation to completion first")
    try:
        result = await sim.run_optimization_step()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Scenario Pack ----

@app.get("/api/scenario-pack")
def list_scenario_pack():
    """List all built-in scenarios with varying complexity."""
    return {"scenarios": get_scenario_pack()}


@app.get("/api/scenario-pack/{scenario_id}")
def get_scenario_pack_item(scenario_id: str):
    """Get a specific scenario pack item."""
    item = get_scenario_by_id(scenario_id)
    if not item:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return item


# ---- WebSocket for live streaming ----

@app.websocket("/ws/simulations/{sim_id}")
async def simulation_ws(websocket: WebSocket, sim_id: str):
    """WebSocket for live simulation streaming.

    Commands:
    - {"action": "tick"} — execute one tick
    - {"action": "run", "speed_ms": 500} — auto-run with delay between ticks
    - {"action": "pause"} — pause auto-run
    - {"action": "state"} — get current state
    - {"action": "human_decision", ...} — submit human player decision
    """
    await websocket.accept()

    sim = manager.get(sim_id)
    if not sim:
        await websocket.send_json({"error": "Simulation not found"})
        await websocket.close()
        return

    running = False
    speed_ms = 500

    async def auto_run():
        nonlocal running
        while running and not sim.is_complete:
            if sim.use_llm:
                result = await sim.do_tick_async()
            else:
                result = sim.do_tick()
            await websocket.send_json({"type": "tick", "data": result})
            await asyncio.sleep(speed_ms / 1000.0)
        if sim.is_complete:
            await websocket.send_json({
                "type": "complete",
                "data": sim.get_state(),
            })
        running = False

    run_task: asyncio.Task | None = None

    try:
        # Send initial state
        await websocket.send_json({"type": "state", "data": sim.get_state()})

        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "tick":
                if not sim.is_complete:
                    if sim.use_llm:
                        result = await sim.do_tick_async()
                    else:
                        result = sim.do_tick()
                    await websocket.send_json({"type": "tick", "data": result})
                else:
                    await websocket.send_json({"type": "complete", "data": sim.get_state()})

            elif action == "run":
                speed_ms = msg.get("speed_ms", 500)
                if not running and not sim.is_complete:
                    running = True
                    run_task = asyncio.create_task(auto_run())

            elif action == "pause":
                running = False
                if run_task:
                    run_task.cancel()
                    run_task = None
                await websocket.send_json({"type": "paused", "data": sim.get_state()})

            elif action == "state":
                await websocket.send_json({"type": "state", "data": sim.get_state()})

            elif action == "reset":
                # Re-create the simulation with same config
                old_config = sim.raw_config
                manager.delete(sim_id)
                await websocket.send_json({"type": "reset_required"})

    except WebSocketDisconnect:
        running = False
        if run_task:
            run_task.cancel()
    except Exception as e:
        running = False
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ---- Scenario Pack ----

@app.get("/api/scenario-pack")
def list_scenario_pack():
    """List available scenario pack entries."""
    return {"scenarios": get_scenario_pack()}


# ---- Multi-Day Games ----

@app.get("/api/games/scenarios")
def list_game_scenarios(uid: str = Depends(get_current_user)):
    """List scenarios available for game creation with preview metadata."""
    scenarios = []
    for entry in SCENARIO_PACK:
        scenario_data = entry["scenario"]
        cost_rates = scenario_data.get("cost_rates", {})
        scenarios.append({
            "id": entry["id"],
            "name": entry["name"],
            "description": entry["description"],
            "num_agents": entry["num_agents"],
            "ticks_per_day": entry["ticks_per_day"],
            "cost_rates": cost_rates,
        })
    return {"scenarios": scenarios}


@app.post("/api/games")
async def create_game(config: CreateGameRequest = CreateGameRequest(), uid: str = Depends(get_current_user)):
    """Create a multi-day policy optimization game."""
    import copy

    logger.info("User %s creating game", uid)
    game_id = str(uuid.uuid4())[:8]

    if config.inline_config:
        raw_yaml = copy.deepcopy(config.inline_config)
    else:
        raw_yaml = get_scenario_by_id(config.scenario_id)
        if not raw_yaml:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {config.scenario_id}")
        raw_yaml = copy.deepcopy(raw_yaml)

    game = Game(
        game_id=game_id,
        raw_yaml=raw_yaml,
        use_llm=config.use_llm,
        mock_reasoning=config.mock_reasoning,
        max_days=config.max_days,
        num_eval_samples=config.num_eval_samples,
        optimization_interval=config.optimization_interval,
        constraint_preset=config.constraint_preset,
    )
    game_manager[game_id] = game

    # Persist: create DuckDB + update index
    from datetime import datetime, timezone
    game_storage.create_game_db(uid, game_id)
    scenario_entry = get_scenario_by_id(config.scenario_id) or {}
    game_storage.update_index(uid, {
        "game_id": game_id,
        "scenario_id": config.scenario_id,
        "scenario_name": scenario_entry.get("name", config.scenario_id) if isinstance(scenario_entry, dict) else config.scenario_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "days_completed": 0,
        "max_days": config.max_days,
        "status": "created",
        "use_llm": config.use_llm,
        "num_agents": len(game.agent_ids),
        "ticks_per_day": raw_yaml.get("simulation", {}).get("ticks_per_day", 0),
        "uid": uid,
    })

    return {"game_id": game_id, "game": game.get_state()}


@app.get("/api/games")
def list_games(uid: str = Depends(get_current_user)):
    """List all games for the current user (persisted + in-memory)."""
    persisted = game_storage.list_games(uid)
    # Add any in-memory games not in the index
    persisted_ids = {g["game_id"] for g in persisted}
    for gid, game in game_manager.items():
        if gid not in persisted_ids:
            persisted.append({
                "game_id": gid,
                "scenario_id": "unknown",
                "days_completed": game.current_day,
                "max_days": game.max_days,
                "status": "complete" if game.is_complete else "in_progress",
            })
    return {"games": persisted}


@app.get("/api/games/{game_id}")
def get_game(game_id: str, uid: str = Depends(get_current_user)):
    """Get game state. Checks memory first, then storage."""
    game = game_manager.get(game_id)
    if not game:
        # Check if it exists in storage index
        games = game_storage.list_games(uid)
        meta = next((g for g in games if g["game_id"] == game_id), None)
        if not meta:
            raise HTTPException(status_code=404, detail="Game not found")
        # Return index metadata (game not in memory, can't get full state)
        return {"game_id": game_id, "persisted": True, **meta}
    return game.get_state()


@app.get("/api/games/{game_id}/days/{day_num}/replay")
def game_day_replay(game_id: str, day_num: int, uid: str = Depends(get_current_user)):
    """Get tick-by-tick replay data for a specific game day."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if day_num < 0 or day_num >= len(game.days):
        raise HTTPException(status_code=404, detail=f"Day {day_num} not found")

    day = game.days[day_num]
    return {
        "day": day_num,
        "seed": day.seed,
        "num_ticks": len(day.tick_events),
        "ticks": [
            {
                "tick": i,
                "events": tick_evts,
                "balances": {aid: day.balance_history[aid][i] if i < len(day.balance_history.get(aid, [])) else 0 for aid in game.agent_ids},
            }
            for i, tick_evts in enumerate(day.tick_events)
        ],
        "policies": {
            aid: {"initial_liquidity_fraction": p["parameters"].get("initial_liquidity_fraction", 1.0)}
            for aid, p in day.policies.items()
        },
        "final_costs": day.costs,
    }


@app.post("/api/games/{game_id}/step")
async def step_game(game_id: str, uid: str = Depends(get_current_user)):
    """Run next day + optimize. Returns day results + reasoning."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.is_complete:
        raise HTTPException(status_code=400, detail="Game is complete")

    day = game.run_day()

    # Persist day to DuckDB
    from datetime import datetime, timezone
    db_path = game_storage.get_db_path(uid, game_id)
    if db_path.exists():
        game.save_day_to_duckdb(db_path, day)
        game_storage.save_game(uid, game_id)
        # Update index
        games = game_storage.list_games(uid)
        meta = next((g for g in games if g["game_id"] == game_id), None)
        if meta:
            meta["days_completed"] = game.current_day
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            meta["status"] = "complete" if game.is_complete else "in_progress"
            game_storage.update_index(uid, meta)

    reasoning = {}
    if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
        reasoning = await game.optimize_policies()
        day.optimized = True

    return {"day": day.to_dict(), "reasoning": reasoning, "game": game.get_state()}


@app.post("/api/games/{game_id}/auto")
async def auto_run_game(game_id: str, uid: str = Depends(get_current_user)):
    """Run all remaining days."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    days = []
    all_reasoning = []
    while not game.is_complete:
        day = game.run_day()
        reasoning = {}
        if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
            reasoning = await game.optimize_policies()
            day.optimized = True
        days.append({"day": day.to_dict(), "reasoning": reasoning})
        all_reasoning.append(reasoning)

    return {"days": days, "game": game.get_state()}


@app.get("/api/games/{game_id}/download")
def download_game(game_id: str, uid: str = Depends(get_current_user)):
    """Download the DuckDB file for a game."""
    from fastapi.responses import FileResponse
    db_path = game_storage.load_game(uid, game_id)
    if not db_path or not db_path.exists():
        raise HTTPException(status_code=404, detail="Game database not found")
    return FileResponse(str(db_path), filename=f"{game_id}.duckdb", media_type="application/octet-stream")


@app.delete("/api/games/{game_id}")
def delete_game(game_id: str, uid: str = Depends(get_current_user)):
    """Delete a game."""
    if game_id in game_manager:
        del game_manager[game_id]
    game_storage.delete_game(uid, game_id)
    game_storage.remove_from_index(uid, game_id)
    return {"status": "deleted"}


# ---- Game WebSocket ----

@app.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str):
    """WebSocket for live game streaming with structured message protocol.

    Message types sent:
      game_state          — full game state snapshot
      day_complete        — one simulation day finished (data = day dict)
      optimization_start  — LLM optimization beginning for an agent
      optimization_complete — LLM optimization done for an agent
      game_complete       — all days finished
      error               — something went wrong
    """
    # Authenticate before accepting
    try:
        uid = await get_ws_user(websocket)
    except Exception:
        return
    logger.info("WS game connection from user %s for game %s", uid, game_id)

    await websocket.accept()

    game = game_manager.get(game_id)
    if not game:
        await websocket.send_json({"type": "error", "message": "Game not found"})
        await websocket.close()
        return

    running = False
    speed_ms = 1000

    async def run_one_step():
        """Run one day + optimization, emitting structured messages."""
        if game.is_complete:
            await websocket.send_json({"type": "game_complete", "data": game.get_state()})
            return

        await websocket.send_json({
            "type": "simulation_running",
            "day": game.current_day,
            "max_days": game.max_days,
        })

        day = game.run_day()
        await websocket.send_json({"type": "day_complete", "data": day.to_dict()})

        if not game.is_complete and game.should_optimize(day.day_num):
            # Use streaming optimization — sends optimization_start,
            # optimization_chunk (text deltas), and optimization_complete
            # directly via the websocket
            await game.optimize_policies_streaming(websocket.send_json)
            day.optimized = True

        await websocket.send_json({"type": "game_state", "data": game.get_state()})

    async def auto_run():
        nonlocal running
        while running and not game.is_complete:
            await run_one_step()
            await asyncio.sleep(speed_ms / 1000.0)
        if game.is_complete:
            await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        running = False

    run_task: asyncio.Task | None = None

    try:
        await websocket.send_json({"type": "game_state", "data": game.get_state()})

        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "step":
                await run_one_step()

            elif action == "auto":
                speed_ms = msg.get("speed_ms", 1000)
                if not running and not game.is_complete:
                    running = True
                    run_task = asyncio.create_task(auto_run())

            elif action == "stop":
                running = False
                if run_task:
                    run_task.cancel()
                    run_task = None
                await websocket.send_json({"type": "game_state", "data": game.get_state()})

            elif action == "state":
                await websocket.send_json({"type": "game_state", "data": game.get_state()})

    except WebSocketDisconnect:
        running = False
        if run_task:
            run_task.cancel()
    except Exception as e:
        running = False
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


# ---- Admin endpoints ----

class InviteRequest(PydanticBaseModel):
    email: str


@app.get("/api/admin/me")
async def admin_me(email: str = Depends(get_current_user_email)):
    """Check if current user is admin."""
    is_admin = user_manager.is_admin(email)
    return {"email": email, "is_admin": is_admin}


@app.get("/api/admin/users")
async def admin_list_users(email: str = Depends(get_admin_user)):
    """List all allowed users (admin only)."""
    return {"users": user_manager.list_users()}


@app.post("/api/admin/invite")
async def admin_invite_user(req: InviteRequest, email: str = Depends(get_admin_user)):
    """Invite a user by email (admin only)."""
    user_manager.invite_user(req.email, invited_by=email)
    return {"status": "invited", "email": req.email}


@app.delete("/api/admin/users/{user_email:path}")
async def admin_revoke_user(user_email: str, email: str = Depends(get_admin_user)):
    """Revoke a user's access (admin only)."""
    user_manager.revoke_user(user_email)
    return {"status": "revoked", "email": user_email}


# ---- Constraint Presets ----

@app.get("/api/constraint-presets")
def list_constraint_presets():
    """List available LLM optimization constraint presets."""
    from .constraint_presets import get_preset_metadata
    return {"presets": get_preset_metadata()}


# ---- Policy Library ----

@app.get("/api/policies/library")
def list_policy_library():
    """List all built-in policies with metadata."""
    lib = get_policy_library()
    return {"policies": lib.list_all()}


@app.get("/api/policies/library/{policy_id}")
def get_policy_library_item(policy_id: str):
    """Get full policy detail including raw JSON."""
    lib = get_policy_library()
    result = lib.get(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


@app.get("/api/policies/library/{policy_id}/tree")
def get_policy_library_tree(policy_id: str):
    """Get just the tree structure for visualization."""
    lib = get_policy_library()
    result = lib.get_trees(policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


# ---- Policy Evolution Endpoints ----

@app.get("/api/games/{game_id}/policy-history")
def get_policy_history(game_id: str, uid: str = Depends(get_current_user)):
    """Get full policy evolution data for a game."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    days_data = []
    for day in game.days:
        day_num = day.day_num
        policies = {aid: p for aid, p in day.policies.items()}
        costs = day.per_agent_costs
        # Determine accepted status from reasoning_history
        accepted: dict[str, bool] = {}
        reasoning_text: dict[str, str] = {}
        for aid in game.agent_ids:
            history = game.reasoning_history.get(aid, [])
            if day_num < len(history):
                entry = history[day_num]
                accepted[aid] = entry.get("accepted", True)
                reasoning_text[aid] = entry.get("reasoning", "")
            else:
                accepted[aid] = True
                reasoning_text[aid] = ""

        days_data.append({
            "day": day_num,
            "policies": policies,
            "costs": costs,
            "accepted": accepted,
            "reasoning": reasoning_text,
        })

    # Build parameter trajectories
    param_trajectories: dict[str, dict[str, list]] = {}
    for aid in game.agent_ids:
        params_over_time: dict[str, list] = {}
        for day in game.days:
            policy = day.policies.get(aid, {})
            for key, val in policy.get("parameters", {}).items():
                params_over_time.setdefault(key, []).append(val)
        param_trajectories[aid] = params_over_time

    return {
        "agent_ids": game.agent_ids,
        "days": days_data,
        "parameter_trajectories": param_trajectories,
    }


@app.get("/api/games/{game_id}/policy-diff")
def get_policy_diff(
    game_id: str,
    day1: int = Query(...),
    day2: int = Query(...),
    agent: str = Query(...),
    uid: str = Depends(get_current_user),
):
    """Get structural diff between policies on two days for an agent."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    if day1 < 0 or day1 >= len(game.days):
        raise HTTPException(status_code=400, detail=f"day1={day1} out of range")
    if day2 < 0 or day2 >= len(game.days):
        raise HTTPException(status_code=400, detail=f"day2={day2} out of range")
    if agent not in game.agent_ids:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent}")

    old_policy = game.days[day1].policies.get(agent, {})
    new_policy = game.days[day2].policies.get(agent, {})

    result = diff_policies(old_policy, new_policy)
    return {
        "agent": agent,
        "day1": day1,
        "day2": day2,
        **result,
    }


# ---- Static Frontend Serving (must be LAST — catch-all mount) ----

from fastapi.staticfiles import StaticFiles
from pathlib import Path

frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
