# Interactive Web Sandbox - Work Notes

**Project**: Full-featured interactive web sandbox for SimCash
**Started**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

---

## Session Log

### 2026-02-17 - Initial Build + Planning

**Context Review Completed**:
- Read `CLAUDE.md` — understood all invariants (INV-1 through INV-11)
- Read `docs/reference/patterns-and-conventions.md` — understood patterns
- Read all existing web code (backend + frontend)
- Studied experiment configs (exp1/2/3)
- Tested Orchestrator FFI surface

**Applicable Invariants**:
- INV-1: Money is i64 — backend uses integer cents, frontend displays dollars
- INV-2: Determinism — seeds passed through to Orchestrator
- INV-3: FFI Minimal — use SimulationConfig.to_ffi_dict() only
- INV-5/6: Event completeness — consume enriched events from FFI

**Key Insights**:
- `SimulationConfig.to_ffi_dict()` is the blessed path for config conversion
- FFI expects flat event format, not nested YAML
- `agent_configs` needs `policy` field (default `{"type": "Fifo"}`)
- Backend port must be 8642 (matches vite proxy)
- recharts was listed as devDep — needs to be regular dep

**Completed**:
- [x] Backend created and tested (commits e5a0df4b, db29ac50)
- [x] Frontend scaffolded with basic components
- [x] Verified Orchestrator works with preset configs
- [x] Created development plan per project planning guide
- [x] Created initial findings doc

**Next Steps**:
1. Execute Phase 1: Backend enhancements
2. Execute Phase 2: Frontend multi-tab layout
3. Continue through phases 3-6

---

## Phase Progress

### Phase 1: Backend Enhancements
**Status**: Pending

### Phase 2: Frontend Multi-Tab Layout
**Status**: Pending

### Phase 3: Enhanced Dashboard
**Status**: Pending

### Phase 4: Replay + Analysis
**Status**: Pending

### Phase 5: LLM Integration
**Status**: Pending

### Phase 6: Polish
**Status**: Pending

---

## Key Decisions

### Decision 1: In-Memory Storage
**Rationale**: This is an interactive sandbox, not a persistence layer. Scenarios and sim data stored in Python dicts. Fast, simple, stateless-friendly.

### Decision 2: Tab-Based UI Without Router
**Rationale**: No need for URL routing in an interactive game. Simple React state switching between views keeps complexity low.

### Decision 3: Replay from Tick History
**Rationale**: SimulationInstance already records tick_history array. No need for DB-based replay (that's the CLI's job per INV-5). Web replay just indexes into the array.

---

## Files Modified

### Created
- `web/backend/app/main.py` — FastAPI endpoints
- `web/backend/app/simulation.py` — SimulationManager
- `web/backend/app/models.py` — Pydantic models
- `web/backend/app/llm_agent.py` — LLM agent module
- `web/backend/app/presets.py` — (unused, presets inline in main.py)
- `web/frontend/src/App.tsx` — Main app component
- `web/frontend/src/types.ts` — TypeScript types
- `web/frontend/src/api.ts` — API client
- `web/frontend/src/components/AgentCards.tsx`
- `web/frontend/src/components/BalanceChart.tsx`
- `web/frontend/src/components/Controls.tsx`
- `web/frontend/src/components/CostChart.tsx`
- `web/frontend/src/components/EventLog.tsx`
