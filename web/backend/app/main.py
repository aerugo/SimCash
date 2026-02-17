"""FastAPI app for SimCash Web Sandbox."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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
from .scenario_pack import get_scenario_pack, get_scenario_by_id, SCENARIO_PACK

app = FastAPI(title="SimCash Web Sandbox", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SimulationManager()
game_manager: dict[str, Game] = {}

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
def list_game_scenarios():
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
async def create_game(config: CreateGameRequest = CreateGameRequest()):
    """Create a multi-day policy optimization game."""
    import copy

    game_id = str(uuid.uuid4())[:8]

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
    )
    game_manager[game_id] = game
    return {"game_id": game_id, "game": game.get_state()}


@app.get("/api/games/{game_id}")
def get_game(game_id: str):
    """Get game state."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game.get_state()


@app.post("/api/games/{game_id}/step")
async def step_game(game_id: str):
    """Run next day + optimize. Returns day results + reasoning."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if game.is_complete:
        raise HTTPException(status_code=400, detail="Game is complete")

    day = game.run_day()
    reasoning = {}
    if game.use_llm and not game.is_complete:
        reasoning = await game.optimize_policies()

    return {"day": day.to_dict(), "reasoning": reasoning, "game": game.get_state()}


@app.post("/api/games/{game_id}/auto")
async def auto_run_game(game_id: str):
    """Run all remaining days."""
    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    days = []
    all_reasoning = []
    while not game.is_complete:
        day = game.run_day()
        reasoning = {}
        if game.use_llm and not game.is_complete:
            reasoning = await game.optimize_policies()
        days.append({"day": day.to_dict(), "reasoning": reasoning})
        all_reasoning.append(reasoning)

    return {"days": days, "game": game.get_state()}


@app.delete("/api/games/{game_id}")
def delete_game(game_id: str):
    """Delete a game."""
    if game_id not in game_manager:
        raise HTTPException(status_code=404, detail="Game not found")
    del game_manager[game_id]
    return {"status": "deleted"}


# ---- Game WebSocket ----

@app.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str):
    """WebSocket for live game streaming."""
    await websocket.accept()

    game = game_manager.get(game_id)
    if not game:
        await websocket.send_json({"error": "Game not found"})
        await websocket.close()
        return

    running = False
    speed_ms = 1000

    async def auto_run():
        nonlocal running
        while running and not game.is_complete:
            day = game.run_day()
            await websocket.send_json({"type": "day", "data": day.to_dict()})
            reasoning = {}
            if game.use_llm and not game.is_complete:
                await websocket.send_json({"type": "optimizing", "day": day.day_num})
                reasoning = await game.optimize_policies()
                await websocket.send_json({"type": "reasoning", "data": reasoning})
            await websocket.send_json({"type": "game_state", "data": game.get_state()})
            await asyncio.sleep(speed_ms / 1000.0)
        if game.is_complete:
            await websocket.send_json({"type": "complete", "data": game.get_state()})
        running = False

    run_task: asyncio.Task | None = None

    try:
        await websocket.send_json({"type": "game_state", "data": game.get_state()})

        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "step":
                if not game.is_complete:
                    day = game.run_day()
                    await websocket.send_json({"type": "day", "data": day.to_dict()})
                    reasoning = {}
                    if game.use_llm and not game.is_complete:
                        await websocket.send_json({"type": "optimizing", "day": day.day_num})
                        reasoning = await game.optimize_policies()
                        await websocket.send_json({"type": "reasoning", "data": reasoning})
                    await websocket.send_json({"type": "game_state", "data": game.get_state()})
                else:
                    await websocket.send_json({"type": "complete", "data": game.get_state()})

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
