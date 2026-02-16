# Interactive Web Sandbox - Development Plan

**Status**: In Progress
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Summary

Build a full-featured interactive web sandbox for SimCash that lets users create scenarios, run simulations with AI or manual policies, watch real-time results, replay completed runs, compare outcomes, and export data — all in a polished dark-mode browser UI.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all backend values in integer cents; frontend converts to dollars for display only
- **INV-2**: Determinism — same seed + config = same output; expose seed in UI
- **INV-3**: FFI Minimal — use `SimulationConfig.to_ffi_dict()` exclusively; no new FFI surface
- **INV-5**: Replay Identity — in-memory tick history for web replay (not CLI DB replay)
- **INV-6**: Event Completeness — consume enriched events from `orch.get_tick_events()`

No new invariants introduced.

## Current State Analysis

Working backend (FastAPI + Rust Orchestrator) and scaffolded frontend (React + Tailwind + recharts). See `initial_findings.md` for details. Missing: custom scenarios, replay, comparison, policy management, analysis, human mode, LLM wiring, multi-tab UI.

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/main.py` | 3 presets, basic CRUD + WS | Add scenario CRUD, replay, comparison, config, export endpoints |
| `web/backend/app/simulation.py` | SimulationManager + SimulationInstance | Add replay from tick history, policy support |
| `web/backend/app/models.py` | Basic Pydantic models | Add scenario builder models, policy models, comparison models |
| `web/backend/app/llm_agent.py` | Scaffolded GPT-5.2 | Wire into simulation tick loop (opt-in) |
| `web/frontend/src/App.tsx` | Single page | Multi-tab layout with routing |
| `web/frontend/src/api.ts` | Basic REST + WS | Full API client for all new endpoints |
| `web/frontend/src/types.ts` | Basic types | Extended types for all new features |
| `web/frontend/src/components/*.tsx` | 5 basic components | 15+ components for all views |

## Solution Design

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (React + Tailwind + recharts)                      │
│                                                              │
│  Tabs: [Home] [Dashboard] [Events] [Config] [Replay]       │
│        [Analysis] [Scenarios]                                │
│                                                              │
│  Home: Preset selection + custom scenario builder            │
│  Dashboard: Live sim with charts, agent cards, controls      │
│  Events: Full event log with filtering                       │
│  Config: FFI config inspector + payment schedule timeline    │
│  Replay: Post-completion scrubber to any tick                │
│  Analysis: Cost breakdown, payment flows, efficiency metrics │
│  Scenarios: CRUD for custom scenarios                        │
└──────────────────┬──────────────────────────────────────────┘
                   │ REST + WebSocket (proxy via Vite)
┌──────────────────▼──────────────────────────────────────────┐
│  FastAPI Backend (port 8642)                                 │
│                                                              │
│  /api/simulations — CRUD + tick/run/replay/export            │
│  /api/scenarios — custom scenario CRUD                       │
│  /api/presets — built-in presets                              │
│  /ws/simulations/{id} — live streaming                       │
│                                                              │
│  SimulationManager holds active sims + tick history           │
│  ScenarioStore holds custom scenarios (in-memory)            │
└──────────────────┬──────────────────────────────────────────┘
                   │ PyO3 FFI
┌──────────────────▼──────────────────────────────────────────┐
│  Rust Orchestrator (unchanged)                               │
└─────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **In-memory storage**: Scenarios and simulations stored in Python dicts. No database needed — this is an interactive sandbox, not a persistence layer.
2. **Tab-based UI without router**: Simple React state-driven tab switching. No need for react-router.
3. **Replay from tick history**: SimulationInstance already records tick_history. Replay reads from this array.
4. **No new FFI surface**: All new features use existing Orchestrator methods.
5. **LLM opt-in**: AI agents are toggled per simulation, not always-on.

## Phase Overview

| Phase | Description | Estimated Effort |
|-------|-------------|------------------|
| 1 | Backend: Scenario CRUD, config inspector, export, replay | Medium |
| 2 | Frontend: Multi-tab layout + Home/Scenarios views | Medium |
| 3 | Frontend: Enhanced Dashboard + Events + Config views | Large |
| 4 | Frontend: Replay + Analysis views | Medium |
| 5 | Integration: LLM agents wired into tick loop | Small |
| 6 | Polish: Keyboard shortcuts, toasts, error handling, responsive | Small |

## Phase 1: Backend Enhancements

**Goal**: Complete REST API for all sandbox features.

### Deliverables
1. Scenario CRUD endpoints (in-memory store)
2. Config inspector endpoint (returns full FFI config)
3. Export endpoint (full JSON dump of completed sim)
4. Replay endpoint (state at any tick from history)
5. Scenario events endpoint (parsed payment schedule)

### Success Criteria
- [ ] `POST /api/scenarios` creates custom scenario
- [ ] `GET /api/scenarios` lists all scenarios
- [ ] `GET /api/simulations/{id}/config` returns FFI config
- [ ] `GET /api/simulations/{id}/export` returns full JSON dump
- [ ] `GET /api/simulations/{id}/replay/{tick}` returns state at tick N
- [ ] `GET /api/simulations/{id}/events` returns all events with filtering
- [ ] All existing endpoints still work

## Phase 2: Frontend Multi-Tab Layout + Home + Scenarios

**Goal**: Replace single-page layout with tabbed interface. Build Home (scenario selection + builder) and Scenario Library views.

### Deliverables
1. Tab bar component with navigation
2. Home view: preset cards + "Custom" option
3. Scenario Builder form: banks, costs, payments, RNG seed
4. Scenario Library: list/create/edit/delete custom scenarios

### Success Criteria
- [ ] Tab navigation between all views
- [ ] Can select preset and launch
- [ ] Can build custom scenario with form
- [ ] Can save/load/delete custom scenarios
- [ ] Form validates inputs (e.g., costs satisfy r_c < r_d)

## Phase 3: Enhanced Dashboard + Events + Config

**Goal**: Upgrade the simulation dashboard with richer visualizations and add full Events and Config inspector views.

### Deliverables
1. Enhanced balance chart (area fills, toggleable agents)
2. Cost progression line chart (over time, not just final bar)
3. Queue visualization (pending payments per agent)
4. Live tick detail panel
5. Full-page event log with filtering (by type, agent, tick range)
6. Config inspector view (formatted config + payment timeline)

### Success Criteria
- [ ] Balance chart shows area fills and agent toggles
- [ ] Cost chart shows progression over time
- [ ] Can see queue sizes visually
- [ ] Event log is filterable and searchable
- [ ] Config view shows full scenario setup

## Phase 4: Replay + Analysis

**Goal**: Post-completion replay scrubber and analysis dashboard.

### Deliverables
1. Replay view with tick scrubber slider
2. Analysis: cost breakdown pie charts per agent
3. Analysis: payment flow table (all payments + settlement status)
4. Analysis: efficiency metrics (settlement rate, avg delay, etc.)
5. Simulation summary card on completion

### Success Criteria
- [ ] Can scrub to any tick after completion
- [ ] Charts update to show state at scrubbed tick
- [ ] Cost breakdown shown per agent
- [ ] All payments listed with final status
- [ ] Key metrics displayed on completion

## Phase 5: LLM Agent Integration

**Goal**: Wire GPT-5.2 into the simulation tick loop.

### Deliverables
1. Toggle "AI mode" when creating simulation
2. LLM calls for initial_liquidity_fraction before first tick
3. Display LLM reasoning in agent cards
4. Fallback to FIFO if LLM fails

### Success Criteria
- [ ] Can toggle AI agents on/off per simulation
- [ ] LLM makes liquidity decisions (shown in UI)
- [ ] Graceful fallback on API errors

## Phase 6: Polish

**Goal**: Production-quality UX.

### Deliverables
1. Keyboard shortcuts (Space=play/pause, →=step, R=reset)
2. Toast notifications (created, completed, error)
3. Loading states and error boundaries
4. Responsive layout (tablet+)
5. Professional header/branding

### Success Criteria
- [ ] Keyboard shortcuts work
- [ ] Errors show user-friendly messages
- [ ] Layout works on 768px+ screens

## Testing Strategy

### Backend
- Manual curl/httpie testing of each endpoint
- Verify preset simulations produce expected results (determinism)
- Verify custom scenarios with known configs match existing experiment outputs

### Frontend
- Build succeeds (`npm run build`)
- No TypeScript errors
- Manual testing of all views and interactions

### Integration
- Full flow: create scenario → launch → play → complete → replay → export
- WebSocket streaming works with play/pause/step

## Documentation Updates

After implementation:
- [ ] Update README with web sandbox instructions
- [ ] Add `docs/reference/web-sandbox.md` describing the architecture
- [ ] No changes to `patterns-and-conventions.md` (no new invariants)

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| Phase 3 | Pending | |
| Phase 4 | Pending | |
| Phase 5 | Pending | |
| Phase 6 | Pending | |
