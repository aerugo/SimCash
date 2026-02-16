# Interactive Web Sandbox - Initial Findings

**Date**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Current State of Web Code

### Backend (`web/backend/`)
Fully working FastAPI app wrapping the Rust Orchestrator via PyO3.

**Files:**
- `app/main.py` — REST endpoints + WebSocket for live streaming
- `app/simulation.py` — `SimulationManager` + `SimulationInstance` wrapping `Orchestrator`
- `app/models.py` — Pydantic models (ScenarioConfig, AgentState, TickResult, etc.)
- `app/llm_agent.py` — GPT-5.2 integration (scaffolded, not wired into tick loop)
- `app/presets.py` — Unused (preset data is inline in main.py)

**Endpoints:**
- `GET /api/health`
- `GET /api/presets` — returns 3 hardcoded presets
- `POST /api/simulations` — create sim from preset or custom config
- `GET /api/simulations/{id}` — get state
- `POST /api/simulations/{id}/tick` — execute one tick
- `POST /api/simulations/{id}/run` — run all remaining ticks
- `DELETE /api/simulations/{id}`
- `WS /ws/simulations/{id}` — live streaming (tick/run/pause/state)

**Key Design:**
- Uses `SimulationConfig.to_ffi_dict()` from existing codebase for proper FFI conversion
- Tracks `balance_history` and `cost_history` per tick in memory
- WebSocket supports auto-run with configurable speed, pause, and step

**Port:** Backend runs on 8642 (matching vite proxy config).

### Frontend (`web/frontend/`)
React + TypeScript + Vite + Tailwind CSS scaffold with basic components.

**Files:**
- `src/App.tsx` — Single-page app with preset selection → dashboard view
- `src/types.ts` — TypeScript interfaces (AgentState, SimulationState, TickResult, etc.)
- `src/api.ts` — REST + WebSocket client functions
- `src/components/AgentCards.tsx` — Bank status cards (balance, liquidity, costs)
- `src/components/BalanceChart.tsx` — Line chart of balances over time (recharts)
- `src/components/CostChart.tsx` — Bar chart of cost breakdown per agent
- `src/components/Controls.tsx` — Play/Pause/Step/Reset + speed slider
- `src/components/EventLog.tsx` — Tick-grouped event log with icons and formatting

**Stack:** React 19, Vite, Tailwind CSS v4, recharts. Dark mode default (#0f172a).
**Proxy:** Vite proxies `/api` and `/ws` to `localhost:8642`.

### What Works
- Creating simulations from presets (exp1/exp2/exp3)
- Tick-by-tick execution via REST and WebSocket
- Balance and cost tracking over time
- Event log with formatted output
- Play/pause/step controls with speed adjustment

### What's Missing (Scope for This Feature)
1. **No custom scenario builder** — only 3 hardcoded presets
2. **No replay** — can't go back to earlier ticks after completing
3. **No comparison** — can't run same scenario with different policies
4. **No policy management** — can't create/edit/test manual policies
5. **No config inspection** — can't see the full FFI config
6. **No export** — can't save simulation data
7. **No analysis view** — no post-completion summary or deep metrics
8. **No human player mode** — can't play as a bank
9. **LLM agents not wired** — GPT-5.2 module exists but isn't used in tick loop
10. **Single page** — no tabs/views for different aspects
11. **No keyboard shortcuts**
12. **No error handling/toast notifications**

## Applicable Invariants

- **INV-1**: Money is i64 — backend already handles this correctly (cents everywhere), frontend displays as dollars
- **INV-2**: Determinism — we pass seeds through; same preset + same seed = same result
- **INV-3**: FFI Minimal — we use `SimulationConfig.to_ffi_dict()` which is the blessed path
- **INV-5**: Replay Identity — our replay will be in-memory tick history, not DB replay (different from CLI replay)
- **INV-6**: Event Completeness — we consume events from `orch.get_tick_events()` which are already enriched

## Existing Experiment Configs (Reference)

- **exp1** (`exp1_2period.yaml`): 2 banks, 2 ticks/day, 1 day. Deterministic payments. Validates Nash equilibrium.
- **exp2** (`exp2_12period.yaml`): 2 banks, 12 ticks/day, stochastic arrivals. Tests adaptive behavior.
- **exp3** (`exp3_joint.yaml`): 2 banks, 3 ticks/day. Joint liquidity+timing optimization.

## Key FFI Surface Used

```python
from payment_simulator._core import Orchestrator
from payment_simulator.config.schemas import SimulationConfig

# Create
orch = Orchestrator.new(ffi_config_dict)

# Query
orch.current_tick()
orch.current_day()
orch.get_agent_ids()
orch.get_agent_state(agent_id)  # -> {balance, available_liquidity, queue1_size, posted_collateral}
orch.get_agent_balance(agent_id)
orch.get_agent_accumulated_costs(agent_id)  # -> {liquidity_cost, delay_cost, penalty_cost, ...}
orch.get_tick_events(tick)  # -> list of event dicts

# Execute
orch.tick()  # -> dict with results
```
