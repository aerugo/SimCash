"""FastAPI app for SimCash Web Sandbox."""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import sys
import uuid
from typing import Any

# Ensure application logs are visible in Cloud Run (stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
# CORSMiddleware replaced by ExplicitCORSMiddleware below

from .auth import get_current_user, get_ws_user, get_admin_user, get_current_user_email, get_optional_user, get_optional_ws_user, get_effective_user, get_effective_optional_user, get_effective_ws_user, GuestCookieMiddleware

from .models import (
    CompareRequest,
    CreateGameRequest,
    CreateSimResponse,
    HumanDecision,
    PresetScenario,
    ScenarioConfig,
)
from .simulation import SimulationManager
from .game import Game
from .game_manager import GameManager
from .storage import GameStorage
from .scenario_pack import get_scenario_pack, get_scenario_by_id, SCENARIO_PACK
from .scenario_library import get_library, get_scenario_detail
from .policy_library import get_library as get_policy_library
from . import collections as coll_mod
from .policy_diff import diff_policies
from .payment_trace import build_payment_traces
from .policy_editor import router as policy_editor_router
from .export import router as export_router
from .docs_api import router as docs_router
from .scenario_editor import router as scenario_editor_router
from .api_v1 import router as api_v1_router
from .admin import user_manager
from .settings import settings_manager
from . import config as app_config
from pydantic import BaseModel as PydanticBaseModel

logger = logging.getLogger(__name__)

from .version import VERSION
app = FastAPI(title="SimCash Web Sandbox", version=VERSION)


async def _eviction_loop():
    """Periodically evict idle games (every 5 minutes)."""
    while True:
        await asyncio.sleep(300)
        try:
            evicted = game_manager.evict_idle(3600)
            if evicted:
                logger.info("Evicted %d idle game(s): %s", len(evicted), evicted)
        except Exception as e:
            logger.warning("Eviction loop error: %s", e)


@app.on_event("startup")
async def _start_eviction():
    """Start the background eviction task."""
    asyncio.create_task(_eviction_loop())


@app.on_event("startup")
def _seed_admin():
    """Ensure initial admin exists in Firestore."""
    if not app_config.is_auth_disabled():
        try:
            user_manager.seed_admin("hugi@sensestack.xyz")
        except Exception as e:
            logger.warning("Failed to seed admin: %s", e)

ALLOWED_ORIGINS = {
    "https://simcash-487714.web.app",
    "https://simcash-487714.firebaseapp.com",
    "https://simcash-997004209370.europe-north1.run.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


class ExplicitCORSMiddleware:
    """Custom CORS middleware that explicitly sets headers.

    Works around Starlette CORSMiddleware returning '*' in some environments.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from starlette.requests import Request as _Req
        req = _Req(scope)
        origin = req.headers.get("origin", "")

        # Handle preflight
        if req.method == "OPTIONS" and origin:
            from starlette.responses import Response
            headers = {}
            if origin in ALLOWED_ORIGINS:
                headers["access-control-allow-origin"] = origin
                headers["access-control-allow-credentials"] = "true"
                headers["access-control-allow-methods"] = "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT"
                headers["access-control-allow-headers"] = req.headers.get(
                    "access-control-request-headers", "*"
                )
                headers["access-control-max-age"] = "600"
                headers["vary"] = "Origin"
            resp = Response(status_code=200, headers=headers)
            await resp(scope, receive, send)
            return

        # For normal requests, inject CORS headers into response
        async def send_with_cors(message):
            if message["type"] == "http.response.start" and origin in ALLOWED_ORIGINS:
                headers = list(message.get("headers", []))
                # Remove any existing CORS headers
                headers = [
                    (k, v) for k, v in headers
                    if k.lower() not in (b"access-control-allow-origin", b"access-control-allow-credentials")
                ]
                headers.append((b"access-control-allow-origin", origin.encode()))
                headers.append((b"access-control-allow-credentials", b"true"))
                headers.append((b"vary", b"Origin"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_cors)
        except Exception:
            # If app raises, send a 500 response WITH CORS headers so the
            # browser can read the error instead of getting opaque CORS failure.
            if origin in ALLOWED_ORIGINS:
                from starlette.responses import JSONResponse
                resp = JSONResponse(
                    {"detail": "Internal Server Error"},
                    status_code=500,
                    headers={
                        "access-control-allow-origin": origin,
                        "access-control-allow-credentials": "true",
                        "vary": "Origin",
                    },
                )
                await resp(scope, receive, send)
            else:
                raise


app.add_middleware(ExplicitCORSMiddleware)
app.add_middleware(GuestCookieMiddleware)

app.include_router(scenario_editor_router)
app.include_router(policy_editor_router)
app.include_router(export_router)
app.include_router(docs_router)
app.include_router(api_v1_router)

manager = SimulationManager()
game_manager = GameManager()
game_locks: dict[str, asyncio.Lock] = {}
# Track active auto-run tasks per game for dedup across WS connections
game_auto_tasks: dict[str, asyncio.Task] = {}
# Track active WebSocket connections per game (for status visibility)
active_ws_connections: dict[str, int] = {}


def get_game_lock(game_id: str) -> asyncio.Lock:
    """Get or create a per-game asyncio lock to prevent concurrent execution."""
    if game_id not in game_locks:
        game_locks[game_id] = asyncio.Lock()
    return game_locks[game_id]
game_storage = GameStorage(
    bucket_name=app_config.GCS_BUCKET,
    storage_mode=app_config.STORAGE_MODE if app_config.STORAGE_MODE != "memory" else "local",
)

from .prompt_blocks import PromptProfile
saved_prompt_profiles: dict[str, PromptProfile] = {}


def _save_game_checkpoint(game: Game):
    """Save game checkpoint (non-blocking for async context). Skips guests."""
    uid = getattr(game, '_uid', 'dev-user')
    if uid.startswith("guest-"):
        return
    scenario_id = getattr(game, '_scenario_id', '')
    try:
        checkpoint = game.to_checkpoint(scenario_id=scenario_id, uid=uid)
        game_storage.save_checkpoint(uid, game.game_id, checkpoint)
        # Also update index
        game_storage.update_index(uid, {
            "game_id": game.game_id,
            "scenario_id": scenario_id,
            "scenario_name": getattr(game, '_scenario_name', ''),
            "optimization_model": getattr(game, '_optimization_model', ''),
            "status": checkpoint["status"],
            "current_day": game.current_day,
            "rounds": game.max_rounds,
            "total_days": game.total_days,
            "created_at": checkpoint.get("created_at", ""),
            "updated_at": checkpoint["updated_at"],
            "last_activity_at": getattr(game, 'last_activity_at', ''),
            "use_llm": game.use_llm,
            "simulated_ai": getattr(game, 'simulated_ai', True),
            "agent_count": len(game.agent_ids),
            "uid": uid,
        })
        # Update global registry with current status
        game_storage.register_experiment(game.game_id, uid, {
            "scenario_id": scenario_id,
            "scenario_name": getattr(game, '_scenario_name', ''),
            "status": checkpoint["status"],
            "current_round": getattr(game, 'current_round', 0),
            "rounds": game.max_rounds,
            "updated_at": checkpoint["updated_at"],
        })
    except Exception as e:
        logger.warning("Failed to save checkpoint for %s: %s", game.game_id, e)


def _try_load_game(game_id: str, uid: str = "") -> Game | None:
    """Try to load a game from checkpoint. Returns None if not found."""
    # Try all known uids if uid not specified
    uids_to_try = [uid] if uid else ["dev-user", "dev@localhost"]
    for try_uid in uids_to_try:
        data = game_storage.load_checkpoint(try_uid, game_id)
        if data:
            try:
                game = Game.from_checkpoint(data)
                game._uid = data.get("uid", try_uid)
                game._scenario_id = data.get("scenario_id", "")
                game_manager.add(game)
                logger.info("Loaded game %s from checkpoint (uid=%s, day=%d/%d)",
                            game_id, try_uid, game.current_day, game.total_days)
                return game
            except Exception as e:
                logger.warning("Failed to restore game %s from checkpoint: %s", game_id, e)
    return None


# ---- Health ----

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/version")
def get_version():
    from .version import version_info
    return version_info()


@app.get("/api/auth-mode")
def auth_mode():
    """Returns auth configuration so frontend can skip login in dev mode."""
    return {
        "auth_disabled": app_config.is_auth_disabled(),
        "dev_token_enabled": bool(app_config.DEV_TOKEN),
    }


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


# ---- Collections ----

@app.get("/api/collections")
def list_collections():
    """List scenario collections with scenario counts."""
    cols = coll_mod.get_collections()
    visibility = coll_mod.get_visibility("scenario")
    result = []
    for c in cols:
        visible_count = sum(1 for sid in c["scenario_ids"] if visibility.get(sid, True))
        result.append({**c, "scenario_count": visible_count})
    return {"collections": result}


@app.get("/api/collections/{collection_id}")
def get_collection_detail(collection_id: str):
    """Get collection detail with full scenario list."""
    col = coll_mod.get_collection(collection_id)
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")
    # Fetch scenario metadata for each scenario in the collection
    scenarios = []
    for sid in col["scenario_ids"]:
        detail = get_scenario_detail(sid)
        if detail:
            scenarios.append({k: v for k, v in detail.items() if k != "raw_config"})
    return {**col, "scenarios": scenarios}


# ---- Scenario Library (read-only, from example configs + presets) ----

@app.get("/api/scenarios/library")
def list_scenario_library(include_archived: bool = False):
    """List all scenarios from example configs + presets with metadata."""
    return {"scenarios": get_library(include_archived=include_archived)}


@app.get("/api/scenarios/library/{scenario_id}")
def get_scenario_library_item(scenario_id: str):
    """Get full scenario detail (metadata + raw config)."""
    detail = get_scenario_detail(scenario_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return detail


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


# ---- Multi-Day Games ----

@app.get("/api/games/scenarios")
def list_game_scenarios(uid: str = Depends(get_effective_optional_user)):
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


def _derive_scenario_name(scenario_id: str, raw_yaml: Any) -> str:
    """Derive a human-readable name for a scenario.

    For preset scenarios, returns the pack name. For custom scenarios,
    builds a descriptive name from the config (e.g. 'Custom · 6 banks · 12 ticks').
    """
    entry = get_scenario_by_id(scenario_id)
    if entry and isinstance(entry, dict):
        # Preset scenario — look up from pack metadata
        for s in SCENARIO_PACK:
            if s["id"] == scenario_id:
                return s.get("name", scenario_id)
        return entry.get("name", scenario_id)

    # Custom scenario — derive from config
    try:
        import yaml as _yaml
        parsed = _yaml.safe_load(raw_yaml) if isinstance(raw_yaml, str) else raw_yaml
        if not isinstance(parsed, dict):
            return scenario_id
        sim = parsed.get("simulation", {})
        agents = sim.get("agents", [])
        n_banks = len(agents)
        n_ticks = sim.get("num_ticks", "?")
        parts = ["Custom"]
        if n_banks:
            parts.append(f"{n_banks} banks")
        if n_ticks != "?":
            parts.append(f"{n_ticks} ticks")
        return " · ".join(parts)
    except Exception:
        return scenario_id


@app.post("/api/games")
async def create_game(config: CreateGameRequest = CreateGameRequest(), uid: str = Depends(get_effective_optional_user)):
    """Create a multi-day policy optimization game."""
    import copy

    # Guests can only run simulated AI
    if uid.startswith("guest-") and not config.simulated_ai:
        raise HTTPException(status_code=403, detail="Login required to run experiments with real AI")

    logger.info("User %s creating game", uid)
    game_id = str(uuid.uuid4())[:8]

    if config.inline_config:
        raw_yaml = copy.deepcopy(config.inline_config)
    else:
        raw_yaml = get_scenario_by_id(config.scenario_id)
        if not raw_yaml:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {config.scenario_id}")
        raw_yaml = copy.deepcopy(raw_yaml)

    # Resolve prompt profile: inline overrides or load saved profile by ID
    prompt_profile = config.prompt_profile
    if config.prompt_profile_id and not prompt_profile:
        saved = saved_prompt_profiles.get(config.prompt_profile_id)
        if saved:
            prompt_profile = saved.blocks

    logger.info("Creating game %s: use_llm=%s simulated_ai=%s constraint_preset=%s",
                game_id, config.use_llm, config.simulated_ai, config.constraint_preset)
    try:
        # For every_scenario_day mode, "Rounds" means full scenario passes.
        # Multiply by num_days so the game runs all days per round.
        total_days = config.rounds
        if config.optimization_schedule == "every_scenario_day":
            import yaml as _yaml
            try:
                parsed = _yaml.safe_load(raw_yaml) if isinstance(raw_yaml, str) else raw_yaml
                scenario_num_days = parsed.get("simulation", {}).get("num_days", 1)
                total_days = config.rounds * scenario_num_days
            except Exception:
                pass  # Fall back to raw rounds

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
    game._starting_policy_ids = config.starting_policy_ids or {}
    game._uid = uid
    from datetime import datetime, timezone
    game._created_at = datetime.now(timezone.utc).isoformat()
    game_manager.add(game)

    # Persist: create DuckDB + update index + save checkpoint (skip for guests)
    if not uid.startswith("guest-"):
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
            "current_round": 0,
            "rounds": config.rounds,
            "status": "created",
            "use_llm": config.use_llm,
            "simulated_ai": getattr(game, 'simulated_ai', True),
            "agent_count": len(game.agent_ids),
            "uid": uid,
        })
        _save_game_checkpoint(game)

        # Register in global experiment registry for public access
        game_storage.register_experiment(game_id, uid, {
            "scenario_id": config.scenario_id,
            "scenario_name": game._scenario_name,
            "created_at": game._created_at,
            "status": "created",
            "rounds": config.rounds,
            "use_llm": config.use_llm,
            "agent_count": len(game.agent_ids),
        })

    return {"game_id": game_id, "game": game.get_state()}


@app.get("/api/games")
def list_games(uid: str = Depends(get_effective_user)):
    """List all games for the current user (from checkpoints + in-memory)."""
    from datetime import datetime, timezone

    def derive_status(raw_status: str, gid: str, last_activity: str) -> str:
        """Derive display status from raw status + live signals."""
        if raw_status == "complete":
            return "complete"
        if raw_status == "created":
            return "created"
        has_ws = gid in active_ws_connections and active_ws_connections[gid] > 0
        if has_ws:
            return "running"
        # No active WS — check how stale
        if last_activity:
            try:
                last_dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                age_s = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if age_s < 120:
                    return "running"  # Recently active, WS may just be reconnecting
                return "stalled"
            except (ValueError, TypeError):
                pass
        return "paused"

    # Prefer checkpoint listing (richer data)
    checkpoints = game_storage.list_checkpoints(uid)
    checkpoint_ids = {c["game_id"] for c in checkpoints}
    # Add any in-memory games without checkpoints (only this user's games)
    for gid, game in game_manager.items():
        game_uid = getattr(game, '_uid', '')
        if gid not in checkpoint_ids and game_uid == uid:
            status = "stalled" if game.stalled else ("complete" if game.is_complete else "running")
            checkpoints.append({
                "game_id": gid,
                "scenario_id": getattr(game, '_scenario_id', ''),
                "status": status,
                "current_day": game.current_day,
                "rounds": game.max_rounds,
                "total_days": game.total_days,
                "use_llm": game.use_llm,
                "agent_count": len(game.agent_ids),
                "last_activity_at": getattr(game, 'last_activity_at', ''),
                "quality": game.quality,
                "stalled": game.stalled,
                "stall_reason": game.stall_reason,
            })

    # Enrich all entries with live status + resolve missing fields
    for entry in checkpoints:
        gid = entry["game_id"]
        last_act = entry.get("last_activity_at") or entry.get("updated_at", "")
        entry["has_active_ws"] = gid in active_ws_connections and active_ws_connections[gid] > 0
        entry["last_activity_at"] = last_act
        entry["display_status"] = derive_status(entry.get("status", ""), gid, last_act)
        # Normalize old field names
        if "current_day" not in entry and "days_completed" in entry:
            entry["current_day"] = entry.pop("days_completed")
        if "agent_count" not in entry and "num_agents" in entry:
            entry["agent_count"] = entry.pop("num_agents")
        # Resolve scenario name from library if missing or still ugly (custom:hash)
        sid = entry.get("scenario_id", "")
        sname = entry.get("scenario_name", "")
        if not sname or sname == sid or sname.startswith("custom:"):
            # Try preset pack first
            for s in SCENARIO_PACK:
                if s["id"] == sid:
                    entry["scenario_name"] = s.get("name", sid)
                    break
            else:
                # Custom scenario — derive from agent_count if available
                n_banks = entry.get("agent_count", 0)
                if n_banks and sid.startswith("custom:"):
                    entry["scenario_name"] = f"Custom · {n_banks} banks"
                elif sid.startswith("custom:"):
                    entry["scenario_name"] = "Custom Scenario"

    return {"games": checkpoints}


@app.get("/api/games/public")
def list_public_games(limit: int = Query(100, ge=1, le=500)):
    """List all public experiments (no auth required)."""
    experiments = game_storage.list_all_experiments(limit=limit)
    return {"games": experiments}


@app.get("/api/games/{game_id}")
def get_game(game_id: str, uid: str = Depends(get_effective_optional_user)):
    """Get game state. Checks memory first, then storage, then global registry."""
    game = game_manager.get(game_id)
    if not game:
        # Try loading from checkpoint for this user
        game = _try_load_game(game_id, uid)
    if not game:
        # Fall back to global registry lookup
        owner_uid = game_storage.lookup_experiment_owner(game_id)
        if owner_uid:
            game = _try_load_game(game_id, owner_uid)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.get_state()


@app.get("/api/games/{game_id}/days/{day_num}/replay")
def game_day_replay(game_id: str, day_num: int, uid: str = Depends(get_effective_optional_user)):
    """Get tick-by-tick replay data for a specific game day."""
    game = game_manager.get(game_id)
    if not game:
        game = _try_load_game(game_id, uid)
    if not game:
        owner_uid = game_storage.lookup_experiment_owner(game_id)
        if owner_uid:
            game = _try_load_game(game_id, owner_uid)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if day_num < 0 or day_num >= len(game.days):
        raise HTTPException(status_code=404, detail=f"Day {day_num} not found")

    day = game.days[day_num]
    tick_events = day.tick_events
    if not tick_events:
        tick_events = game.recompute_day_events(day_num)
    return {
        "day": day_num,
        "seed": day.seed,
        "num_ticks": len(tick_events),
        "ticks": [
            {
                "tick": i,
                "events": tick_evts,
                "balances": {aid: day.balance_history[aid][i] if i < len(day.balance_history.get(aid, [])) else 0 for aid in game.agent_ids},
            }
            for i, tick_evts in enumerate(tick_events)
        ],
        "policies": {
            aid: {"initial_liquidity_fraction": p["parameters"].get("initial_liquidity_fraction", 1.0)}
            for aid, p in day.policies.items()
        },
        "final_costs": day.costs,
    }


@app.post("/api/games/{game_id}/step")
async def step_game(game_id: str, uid: str = Depends(get_effective_optional_user)):
    """Run next day + optimize. Returns day results + reasoning."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.is_complete:
        raise HTTPException(status_code=400, detail="Game is complete")
    if game.stalled:
        raise HTTPException(status_code=400, detail=f"Game is stalled: {game.stall_reason}")

    async with get_game_lock(game_id):
        # Run CPU-heavy simulation in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        day = await loop.run_in_executor(None, game.run_day)

        # Persist day to DuckDB
        from datetime import datetime, timezone
        db_path = game_storage.get_db_path(uid, game_id)
        if db_path.exists():
            game.save_day_to_duckdb(db_path, day)
            game_storage.save_game(uid, game_id)
            games = game_storage.list_games(uid)
            meta = next((g for g in games if g["game_id"] == game_id), None)
            if meta:
                meta["current_day"] = game.current_day
                meta["current_round"] = game.current_round
                meta["updated_at"] = datetime.now(timezone.utc).isoformat()
                meta["last_activity_at"] = game.last_activity_at
                meta["status"] = "stalled" if game.stalled else ("complete" if game.is_complete else "running")
                meta["quality"] = game.quality
                game_storage.update_index(uid, meta)

        _save_game_checkpoint(game)

        reasoning = {}
        if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
            reasoning = await game.optimize_all_agents()
            day.optimized = True
            if not reasoning:
                day.optimization_failed = True
            _save_game_checkpoint(game)

        return {"day": day.to_summary_dict(), "reasoning": reasoning, "game": game.get_state()}


@app.post("/api/games/{game_id}/auto")
async def auto_run_game(game_id: str, uid: str = Depends(get_effective_optional_user)):
    """Run all remaining days."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    async with get_game_lock(game_id):
        loop = asyncio.get_event_loop()
        days = []
        all_reasoning = []
        while not game.is_complete and not game.stalled:
            # Run CPU-heavy simulation in a thread to avoid blocking the event loop
            day = await loop.run_in_executor(None, game.run_day)
            reasoning = {}
            if game.use_llm and not game.is_complete and game.should_optimize(day.day_num):
                reasoning = await game.optimize_all_agents()
                day.optimized = True
                if not reasoning:
                    day.optimization_failed = True
                # In intra-scenario mode, inject updated policies into the live Orchestrator
                if game.optimization_schedule == "every_scenario_day":
                    game._inject_policies_into_orch()
            days.append({"day": day.to_summary_dict(), "reasoning": reasoning})
            all_reasoning.append(reasoning)
            if game.stalled:
                break

        return {"days": days, "game": game.get_state()}


@app.get("/api/games/{game_id}/download")
def download_game(game_id: str, uid: str = Depends(get_effective_optional_user)):
    """Download the DuckDB file for a game."""
    from fastapi.responses import FileResponse
    db_path = game_storage.load_game(uid, game_id)
    if not db_path or not db_path.exists():
        raise HTTPException(status_code=404, detail="Game database not found")
    return FileResponse(str(db_path), filename=f"{game_id}.duckdb", media_type="application/octet-stream")


@app.delete("/api/games/{game_id}")
def delete_game(game_id: str, uid: str = Depends(get_effective_optional_user)):
    """Delete a game."""
    if game_id in game_manager:
        game_manager.remove(game_id)
    game_storage.delete_game(uid, game_id)
    game_storage.delete_checkpoint(uid, game_id)
    game_storage.remove_from_index(uid, game_id)
    game_storage.unregister_experiment(game_id)
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
    # Authenticate before accepting (guests allowed)
    try:
        uid = await get_effective_ws_user(websocket)
    except Exception:
        return
    logger.info("WS game connection from user %s for game %s", uid, game_id)

    await websocket.accept()

    game = game_manager.get(game_id)
    if not game:
        game = _try_load_game(game_id, uid)
    if not game:
        await websocket.send_json({"type": "error", "message": "Game not found"})
        await websocket.close()
        return

    # Short-circuit completed games — send state and close immediately.
    # Prevents reconnection storms from old browser tabs.
    if game.is_complete:
        await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        await websocket.close()
        return

    # Track WS connection
    active_ws_connections[game_id] = active_ws_connections.get(game_id, 0) + 1
    game.touch_activity()

    running = False
    speed_ms = 1000

    async def run_one_step():
        """Run one day + optimization, emitting structured messages.

        Uses transactional day execution: simulate first, only commit
        after successful WS delivery. Prevents skipped optimization
        if the WS dies mid-step. Protected by per-game lock to prevent
        concurrent execution from multiple connections.
        """
        async with get_game_lock(game_id):
            if game.is_complete:
                await websocket.send_json({"type": "game_complete", "data": game.get_state()})
                return

            await websocket.send_json({
                "type": "simulation_running",
                "day": game.current_day,
                "total_days": game.total_days,
            })

            try:
                # Run CPU-heavy simulation in a thread to avoid blocking the event loop
                # (which would prevent keepalive pings and kill the WS connection)
                loop = asyncio.get_event_loop()
                day = await loop.run_in_executor(None, game.simulate_day)
            except Exception as sim_err:
                logger.error("Simulation failed on day %d: %s — rolling back policies", game.current_day, sim_err)
                if game.days:
                    prev_policies = game.days[-1].policies
                    game.policies = copy.deepcopy(prev_policies)
                    logger.info("Rolled back to day %d policies, retrying", game.days[-1].day_num)
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Simulation error (rolling back policies): {sim_err}",
                    })
                    day = await loop.run_in_executor(None, game.simulate_day)
                else:
                    raise

            # Deliver day result to client BEFORE committing to state.
            # If WS send fails, the day is not committed and can be retried.
            try:
                await websocket.send_json({"type": "day_complete", "data": day.to_summary_dict()})
            except Exception:
                logger.warning("WS dead during day %d delivery — not committing", day.day_num)
                raise

            # Commit only after successful delivery
            game.commit_day(day)
            game.touch_activity()
            _save_game_checkpoint(game)

            logger.info("Post-day check: is_complete=%s, should_optimize(%d)=%s, use_llm=%s",
                        game.is_complete, day.day_num, game.should_optimize(day.day_num), game.use_llm)
            if not game.is_complete and game.should_optimize(day.day_num):
                logger.info("Starting LLM optimization for game %s day %d", game_id, day.day_num)
                opt_results = await game.optimize_all_agents(websocket.send_json)
                day.optimized = True
                if not opt_results:
                    day.optimization_failed = True
                # In intra-scenario mode, inject updated policies into the live Orchestrator
                if game.optimization_schedule == "every_scenario_day":
                    game._inject_policies_into_orch()
                logger.info("Optimization complete for game %s day %d", game_id, day.day_num)
                game.touch_activity()
                _save_game_checkpoint(game)

            await websocket.send_json({"type": "game_state", "data": game.get_state()})

    async def auto_run():
        nonlocal running
        logger.info("Auto-run started for game %s (speed_ms=%d)", game_id, speed_ms)
        error_occurred = False
        try:
            while running and not game.is_complete and not game.stalled:
                logger.info("Auto-run: starting step for day %d/%d", game.current_day, game.total_days)
                await run_one_step()
                logger.info("Auto-run: step complete, day now %d/%d", game.current_day, game.total_days)
                await asyncio.sleep(speed_ms / 1000.0)
            if game.stalled:
                await websocket.send_json({"type": "game_stalled", "data": game.get_state(), "stall_reason": game.stall_reason})
            elif game.is_complete:
                await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        except asyncio.CancelledError:
            logger.info("Auto-run cancelled for game %s (dedup or stop)", game_id)
            raise
        except Exception as e:
            error_occurred = True
            logger.error("Auto-run error for game %s: %s", game_id, e, exc_info=True)
            try:
                await websocket.send_json({
                    "type": "auto_run_ended",
                    "reason": "error",
                    "message": str(e),
                    "day": game.current_day,
                })
            except Exception:
                pass  # WS dead too
        finally:
            running = False
            # Clean up global task registry
            if game_auto_tasks.get(game_id) is asyncio.current_task():
                del game_auto_tasks[game_id]
            # Notify client that auto-run stopped (if not error — error already sent above)
            if not error_occurred and not game.is_complete:
                try:
                    await websocket.send_json({
                        "type": "auto_run_ended",
                        "reason": "stopped",
                        "day": game.current_day,
                    })
                except Exception:
                    pass
            logger.info("Auto-run ended for game %s", game_id)

    run_task: asyncio.Task | None = None

    async def keepalive():
        """Send periodic pings to prevent Cloud Run from dropping idle WS."""
        try:
            while True:
                await asyncio.sleep(20)
                await websocket.send_json({"type": "ping"})
        except Exception:
            pass  # WS closed, exit silently

    keepalive_task = asyncio.create_task(keepalive())

    try:
        await websocket.send_json({"type": "game_state", "data": game.get_state()})

        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")
            logger.info("WS game %s received action: %s (running=%s, complete=%s)",
                        game_id, action, running, game.is_complete)

            if action == "step":
                await run_one_step()

            elif action == "rerun":
                # Re-run the current (last) day with the same seed
                target_day = msg.get("day")
                if game.days:
                    # Pop the last day and restore policies from before it
                    popped = game.days.pop()
                    # Restore policies to what they were at that day
                    # (the day stored the policies used, so restore them)
                    game.policies = {aid: copy.deepcopy(p) for aid, p in popped.policies.items()}
                    await run_one_step()
                else:
                    await websocket.send_json({"type": "error", "message": "No days to re-run"})

            elif action == "auto":
                speed_ms = msg.get("speed_ms", 1000)
                # Cancel any existing auto-run for this game (from other connections)
                existing = game_auto_tasks.get(game_id)
                if existing and not existing.done():
                    logger.info("Cancelling existing auto-run task for game %s (dedup)", game_id)
                    existing.cancel()
                if game.is_complete:
                    await websocket.send_json({"type": "game_complete", "data": game.get_state()})
                elif not running:
                    running = True
                    run_task = asyncio.create_task(auto_run())
                    game_auto_tasks[game_id] = run_task

            elif action == "stop":
                running = False
                if run_task:
                    run_task.cancel()
                    run_task = None
                await websocket.send_json({"type": "game_state", "data": game.get_state()})

            elif action == "resume":
                if game.stalled:
                    game.stalled = False
                    game.stall_reason = ""
                    _save_game_checkpoint(game)
                    await websocket.send_json({"type": "game_state", "data": game.get_state()})
                else:
                    await websocket.send_json({"type": "error", "message": "Game is not stalled"})

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
    finally:
        keepalive_task.cancel()
        # Decrement WS connection count
        count = active_ws_connections.get(game_id, 1) - 1
        if count <= 0:
            active_ws_connections.pop(game_id, None)
        else:
            active_ws_connections[game_id] = count


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


@app.get("/api/admin/users/list-with-games")
async def admin_list_users_with_games(email: str = Depends(get_admin_user)):
    """List all users with their game counts."""
    import asyncio
    from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]
    users = user_manager.list_users()
    loop = asyncio.get_event_loop()

    async def enrich(u: dict) -> dict:
        uid = u.get("uid", "")
        if not uid and u.get("email"):
            try:
                fb_user = await loop.run_in_executor(None, fb_auth.get_user_by_email, u["email"])
                uid = fb_user.uid
            except Exception:
                uid = ""
        game_count = len(await loop.run_in_executor(None, game_storage.list_checkpoints, uid)) if uid else 0
        return {**u, "uid": uid, "game_count": game_count}

    result = await asyncio.gather(*(enrich(u) for u in users))
    return {"users": list(result)}


@app.post("/api/admin/invite")
async def admin_invite_user(req: InviteRequest, email: str = Depends(get_admin_user)):
    """Invite a user by email (admin only)."""
    user_manager.invite_user(req.email, invited_by=email)
    return {"status": "invited", "email": req.email}


@app.post("/api/admin/create-user")
async def admin_create_user(req: InviteRequest, email: str = Depends(get_admin_user)):
    """Create a Firebase Auth user with a generated passphrase (admin only)."""
    passphrase = user_manager.create_user_with_passphrase(req.email, invited_by=email)
    return {"status": "created", "email": req.email, "passphrase": passphrase}


@app.delete("/api/admin/users/{user_email:path}")
async def admin_revoke_user(user_email: str, email: str = Depends(get_admin_user)):
    """Revoke a user's access (admin only)."""
    user_manager.revoke_user(user_email)
    return {"status": "revoked", "email": user_email}


# ---- Admin Library Management ----

@app.get("/api/admin/library")
async def admin_library(email: str = Depends(get_admin_user)):
    """Get all scenarios and policies with visibility (admin only)."""
    scenarios = get_library(include_archived=True)
    lib = get_policy_library()
    policies = lib.list_all(include_archived=True)
    return {"scenarios": scenarios, "policies": policies}


class VisibilityUpdate(PydanticBaseModel):
    visible: bool


@app.patch("/api/admin/library/{item_type}/{item_id}")
async def admin_toggle_visibility(
    item_type: str,
    item_id: str,
    body: VisibilityUpdate,
    email: str = Depends(get_admin_user),
):
    """Toggle visibility of a scenario or policy (admin only)."""
    if item_type not in ("scenario", "policy"):
        raise HTTPException(status_code=400, detail="item_type must be 'scenario' or 'policy'")
    try:
        coll_mod.set_visibility(item_type, item_id, body.visible)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "updated", "item_type": item_type, "item_id": item_id, "visible": body.visible}


# ---- Admin: Collection Management ----


class CreateCollectionRequest(PydanticBaseModel):
    id: str
    name: str
    icon: str = "📁"
    description: str = ""
    scenario_ids: list[str] = []


class UpdateCollectionScenariosRequest(PydanticBaseModel):
    scenario_ids: list[str]


@app.post("/api/admin/collections")
async def admin_create_collection(
    body: CreateCollectionRequest,
    email: str = Depends(get_admin_user),
):
    """Create a new collection (admin only)."""
    try:
        coll = coll_mod.create_collection(
            body.id, body.name, body.icon, body.description, body.scenario_ids
        )
        return coll
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/admin/collections/{collection_id}/scenarios")
async def admin_update_collection_scenarios(
    collection_id: str,
    body: UpdateCollectionScenariosRequest,
    email: str = Depends(get_admin_user),
):
    """Update scenario membership for a collection (admin only)."""
    try:
        coll = coll_mod.update_collection_scenarios(collection_id, body.scenario_ids)
        return coll
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/admin/collections/{collection_id}")
async def admin_delete_collection(
    collection_id: str,
    email: str = Depends(get_admin_user),
):
    """Delete a custom collection (admin only). Cannot delete built-in ones."""
    try:
        coll_mod.delete_collection(collection_id)
        return {"status": "deleted", "id": collection_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---- Platform Settings (Model Selection) ----

class SettingsUpdate(PydanticBaseModel):
    optimization_model: str | None = None
    model_settings: dict | None = None


@app.get("/api/settings")
async def get_settings(email: str = Depends(get_admin_user)):
    """Get platform settings (admin only)."""
    s = settings_manager.get_settings()
    return {
        "optimization_model": s.optimization_model,
        "model_settings": s.model_settings,
        "available_models": s.available_models,
        "updated_by": s.updated_by,
        "updated_at": s.updated_at,
    }


@app.patch("/api/settings")
async def update_settings(req: SettingsUpdate, email: str = Depends(get_admin_user)):
    """Update platform settings (admin only)."""
    updates: dict = {}
    if req.optimization_model is not None:
        updates["optimization_model"] = req.optimization_model
    if req.model_settings is not None:
        updates["model_settings"] = req.model_settings
    try:
        s = settings_manager.update_settings(updates, email)
        return {
            "status": "updated",
            "optimization_model": s.optimization_model,
            "model_settings": s.model_settings,
            "updated_by": s.updated_by,
            "updated_at": s.updated_at,
        }
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/settings/models")
async def list_models():
    """List available optimization models (public)."""
    return {"models": settings_manager.get_available_models()}


# ---- Constraint Presets ----

@app.get("/api/constraint-presets")
def list_constraint_presets():
    """List available LLM optimization constraint presets."""
    from .constraint_presets import get_preset_metadata
    return {"presets": get_preset_metadata()}


@app.post("/api/constraint-presets/detect")
def detect_constraint_features(body: dict):
    """Detect scenario features and return auto-selected field groups.
    
    POST body: {"scenario_config": {...}}  (raw scenario YAML dict)
    
    Returns:
    {
        "features": {"lsm_enabled": true, "collateral_configured": false, ...},
        "auto_groups": ["core", "queue", "timing", "cost", "throughput"],
        "available_groups": ["core", "queue", ..., "counterparty"],
        "field_count": 42
    }
    """
    from .constraint_presets import detect_features
    config = body.get("scenario_config", {})
    return detect_features(config)


@app.get("/api/constraint-presets/groups")
def list_field_groups():
    """List all field groups and their fields."""
    from .constraint_presets import get_field_groups, ALWAYS_GROUPS
    groups = get_field_groups()
    return {
        "groups": {
            name: {
                "fields": fields,
                "always_on": name in ALWAYS_GROUPS,
            }
            for name, fields in groups.items()
        }
    }


# ---- Policy Library ----

@app.get("/api/policies/library")
def list_policy_library(include_archived: bool = False):
    """List all built-in policies with metadata."""
    lib = get_policy_library()
    return {"policies": lib.list_all(include_archived=include_archived)}


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


# ---- Payment Trace ----

@app.get("/api/games/{game_id}/days/{day_num}/payments")
def get_payment_traces(game_id: str, day_num: int, uid: str = Depends(get_effective_optional_user)):
    """Get payment lifecycle traces for a specific game day."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if day_num < 0 or day_num >= len(game.days):
        raise HTTPException(status_code=404, detail=f"Day {day_num} not found")

    day = game.days[day_num]
    events = day.events
    if not events:
        tick_events = game.recompute_day_events(day_num)
        events = [e for tick in tick_events for e in tick]
    payments = build_payment_traces(events)
    return {
        "day": day_num,
        "total_payments": len(payments),
        "payments": payments,
    }


# ---- Policy Evolution Endpoints ----

@app.get("/api/games/{game_id}/policy-history")
def get_policy_history(game_id: str, uid: str = Depends(get_effective_optional_user)):
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
    uid: str = Depends(get_effective_optional_user),
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


# ---- Prompt Anatomy API ----

@app.get("/api/games/{game_id}/prompts/{day_num}/{agent_id}")
def get_prompt(
    game_id: str,
    day_num: int,
    agent_id: str,
    uid: str = Depends(get_effective_optional_user),
):
    """Get the structured prompt for a specific optimization round/agent."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if day_num < 0 or day_num >= len(game.days):
        raise HTTPException(status_code=400, detail=f"day_num={day_num} out of range")
    day = game.days[day_num]
    if agent_id not in game.agent_ids:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_id}")
    prompt_data = day.optimization_prompts.get(agent_id)
    if not prompt_data:
        raise HTTPException(status_code=404, detail="No prompt data for this round/agent")
    return prompt_data


@app.get("/api/games/{game_id}/prompts")
def list_prompts(
    game_id: str,
    uid: str = Depends(get_effective_optional_user),
):
    """List all optimization prompts with metadata (no full content)."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    prompts = []
    for d in game.days:
        if d.optimization_prompts:
            for agent_id, prompt_data in d.optimization_prompts.items():
                prompts.append({
                    "day": d.day_num,
                    "agent_id": agent_id,
                    "total_tokens": prompt_data.get("total_tokens", 0),
                    "profile_hash": prompt_data.get("profile_hash", ""),
                    "num_blocks": len(prompt_data.get("blocks", [])),
                    "llm_response_tokens": prompt_data.get("llm_response_tokens", 0),
                })
    return {"prompts": prompts}


# ---- Prompt Profiles CRUD ----

# Default block registry: describes all available blocks with defaults
BLOCK_REGISTRY = [
    # --- System Prompt ---
    {"id": "sys_full", "name": "System Prompt", "category": "system", "source": "static",
     "description": "Complete system prompt with expert intro, domain explanation, schemas, and instructions.",
     "token_estimate": 3000, "enabled": True, "options": {},
     "sub_sections": [
         {"id": "sys_settlement_constraint", "name": "Settlement Constraint",
          "description": "Adds minimum settlement rate requirement (e.g., ≥95%) to system prompt. Part of Phase 2 settlement optimization.",
          "enabled": True, "configurable": True},
         {"id": "sys_tree_composition", "name": "Tree Composition Guidance",
          "description": "Adds structural guidance for decision tree design (condition types, nesting patterns). Phase 4 — experimental variable, defaults OFF.",
          "enabled": False, "configurable": True},
     ]},
    # --- User Prompt: Core ---
    {"id": "usr_header", "name": "Header", "category": "user", "source": "dynamic",
     "description": "Agent ID and iteration number.", "token_estimate": 150, "enabled": True, "options": {}},
    # --- User Prompt: Settlement Optimization (Phase 1) ---
    {"id": "usr_liquidity_context", "name": "Liquidity Context", "category": "user", "source": "dynamic",
     "description": "Per-tick balance trajectory with available liquidity and settlement feasibility ratio. Phase 1 settlement optimization — helps agents see when they're liquidity-constrained.",
     "token_estimate": 400, "enabled": True, "options": {}},
    {"id": "usr_current_state", "name": "Current State", "category": "user", "source": "dynamic",
     "description": "Current metrics and policy parameters.", "token_estimate": 250, "enabled": True, "options": {}},
    {"id": "usr_cost_analysis", "name": "Cost Analysis", "category": "user", "source": "dynamic",
     "description": "Cost breakdown with rates.", "token_estimate": 500, "enabled": True, "options": {}},
    {"id": "usr_optimization_guidance", "name": "Optimization Guidance", "category": "user", "source": "dynamic",
     "description": "Heuristic guidance based on cost structure.", "token_estimate": 200, "enabled": True, "options": {}},
    # --- User Prompt: Settlement Optimization (Phase 1) ---
    {"id": "usr_balance_trajectory", "name": "Balance Trajectory", "category": "user", "source": "dynamic",
     "description": "Per-tick balance with available_liquidity column and settlement feasibility ratio. Phase 1 — shows agents exactly when liquidity runs out.",
     "token_estimate": 300, "enabled": True, "options": {}},
    # --- User Prompt: Settlement Optimization (Phase 3) ---
    {"id": "usr_worst_case", "name": "Worst Case Analysis", "category": "user", "source": "dynamic",
     "description": "Crunch tradeoff detection and worst-seed summary. Phase 3 — highlights ticks where queued payments exceeded available liquidity.",
     "token_estimate": 200, "enabled": True, "options": {}},
    {"id": "usr_simulation_trace", "name": "Simulation Trace", "category": "user", "source": "dynamic",
     "description": "Tick-by-tick simulation events. Dominates token count (5k-150k tokens).",
     "token_estimate": 20000, "enabled": True,
     "options": {"verbosity": "full"},
     "available_options": {"verbosity": {"type": "enum", "values": ["full", "decisions_only", "summary", "costs_only"], "default": "full"}}},
    {"id": "usr_iteration_history", "name": "Iteration History", "category": "user", "source": "dynamic",
     "description": "History of all previous optimization iterations.",
     "token_estimate": 2000, "enabled": True,
     "options": {"format": "full"},
     "available_options": {"format": {"type": "enum", "values": ["full", "table_only", "last_n"], "default": "full"},
                           "last_n": {"type": "int", "default": 10, "description": "Number of recent iterations (when format=last_n)"}}},
    {"id": "usr_parameter_trajectories", "name": "Parameter Trajectories", "category": "user", "source": "dynamic",
     "description": "Parameter values over time.", "token_estimate": 200, "enabled": True, "options": {}},
    {"id": "usr_final_instructions", "name": "Final Instructions", "category": "user", "source": "static",
     "description": "Output format instructions and constraints.", "token_estimate": 500, "enabled": True, "options": {}},
    {"id": "usr_policy_section", "name": "Current Policy", "category": "user", "source": "dynamic",
     "description": "Current policy JSON for reference.", "token_estimate": 300, "enabled": True, "options": {}},
]


@app.get("/api/prompt-blocks")
def list_prompt_blocks():
    """List all available prompt blocks with defaults and descriptions."""
    return {"blocks": BLOCK_REGISTRY}


class CreatePromptProfileRequest(PydanticBaseModel):
    name: str
    description: str = ""
    blocks: dict[str, dict] = {}  # block_id → {enabled, options}


@app.get("/api/prompt-profiles")
def list_prompt_profiles():
    """List all saved prompt profiles."""
    return {"profiles": [
        {"id": p.id, "name": p.name, "description": p.description,
         "blocks": p.blocks, "created_at": p.created_at}
        for p in saved_prompt_profiles.values()
    ]}


@app.post("/api/prompt-profiles")
def create_prompt_profile(req: CreatePromptProfileRequest):
    """Create a new prompt profile."""
    from datetime import datetime, timezone
    profile_id = str(uuid.uuid4())[:8]
    profile = PromptProfile(
        id=profile_id,
        name=req.name,
        description=req.description,
        blocks=req.blocks,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    saved_prompt_profiles[profile_id] = profile
    return {"id": profile_id, "name": profile.name, "description": profile.description,
            "blocks": profile.blocks, "created_at": profile.created_at}


@app.get("/api/prompt-profiles/{profile_id}")
def get_prompt_profile(profile_id: str):
    """Get a saved prompt profile."""
    profile = saved_prompt_profiles.get(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"id": profile.id, "name": profile.name, "description": profile.description,
            "blocks": profile.blocks, "created_at": profile.created_at}


@app.delete("/api/prompt-profiles/{profile_id}")
def delete_prompt_profile(profile_id: str):
    """Delete a saved prompt profile."""
    if profile_id not in saved_prompt_profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    del saved_prompt_profiles[profile_id]
    return {"status": "deleted"}


# ---- Static Frontend Serving (must be LAST — catch-all mount) ----

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    # Serve static assets (JS, CSS, images, etc.)
    app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")

    # SPA catch-all: serve index.html for all non-API/non-WS/non-asset paths
    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Try to serve static file first
        file_path = frontend_dir / path
        if file_path.is_file() and ".." not in path:
            return FileResponse(str(file_path))
        # Fall back to index.html for SPA routing
        return FileResponse(str(frontend_dir / "index.html"))
