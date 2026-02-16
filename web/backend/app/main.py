"""FastAPI app for SimCash Web Sandbox."""
from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .models import CreateSimResponse, HumanDecision, PresetScenario, ScenarioConfig
from .simulation import SimulationManager

app = FastAPI(title="SimCash Web Sandbox", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = SimulationManager()


# ---- REST Endpoints ----

@app.get("/api/health")
def health():
    return {"status": "ok"}


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
                # Can't easily reset — tell client to create new
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
