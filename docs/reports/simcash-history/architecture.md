# Architectural Evolution

## Component Birth Timeline

### simulator/src/ (originally backend/src/) — The Rust Engine
**Born:** Oct 27, 2025 (commit 48f5a019)
**Renamed:** Dec 8, 2025 (backend/ → simulator/)

The first code written. Built in a 7-day sprint:
- Day 1 (Oct 27): Time, RNG, Agent, Transaction, RTGS, LSM, Queue, Policies, Orchestrator
- Day 2 (Oct 28): CLI
- Day 3 (Oct 29): Collateral (3-tree architecture), FFI bridge
- Week 2+: Policy DSL expansion, performance optimization, TARGET2 alignment

Key architectural decisions:
- **i64 for all money** (no floats, ever)
- **Deterministic RNG** (xorshift64*, seeded)
- **Event-sourced** simulation (complete event log for replay)
- **Decision tree policies** (JSON DSL, not hardcoded logic)
- **PyO3 FFI** for Python interop

Evolution milestones:
- Nov 11: LSM deterministic redesign (PairIndex, graph-based cycle detection)
- Nov 13: Policy system v2 (state registers, budget, timers, decision path auditing)
- Nov 21: Priority system (T2-compliant dual priority)
- Nov 22: TARGET2 LSM alignment (entry disposition offsetting)
- Nov 27: BIS model enhancements (priority-based delay costs, liquidity pool)
- Dec 10: Integer-only cost calculations (replacing floats)
- Feb 17: GIL-release FFI methods for thread-parallel simulation
- Feb 19: PenaltyMode enum (fixed/rate variants)
- Feb 21: update_agent_policy for mid-simulation policy swaps

### api/ (Python API Layer)
**Born:** Oct 29, 2025 (commit fc882cbb — Pydantic models for persistence)

Built on the same day as the FFI bridge. The Python layer grew from simple persistence to a full application:

Layers added over time:
1. **Persistence** (Oct 29): DuckDB, migration system
2. **CLI** (Oct 28-30): run, replay, verbose modes
3. **REST API** (Oct 30): FastAPI endpoints
4. **Schemas** (Nov 10): Pydantic validation
5. **Services** (Nov 29): Extracted service layer
6. **LLM integration** (Dec 1): PydanticAI, policy optimizer
7. **ai_cash_mgmt** (Dec 8): Game orchestrator, bootstrap evaluation
8. **Experiments** (Dec 9-11): YAML-only experiment framework
9. **LLM module** (Dec 10): Provider-agnostic LLM client

Key refactors:
- Nov 29: Extract services and routers
- Dec 8: ai_cash_mgmt module (6 phases in 2 days)
- Dec 9-11: Castro migration to core infrastructure (19 phases!)
- Dec 12: Reference documentation overhaul

### web/ (Interactive Web Platform)
**Born:** Feb 17, 2026 (commit e5a0df4b)
**Author:** nash4cash (Nash agent)

Created entirely by the Nash agent in a single burst. The web module represents the multi-agent era's signature achievement.

Architecture:
- **Backend:** FastAPI + WebSocket (app/main.py, game engine)
- **Frontend:** React + TypeScript + Vite
- **Auth:** Firebase Auth (Google sign-in, magic links, password auth)
- **Storage:** GCS for checkpoints, DuckDB for simulation data
- **Deployment:** Docker multi-stage → Cloud Run + Firebase Hosting
- **Models:** Multi-provider LLM (Gemini, GPT, Claude, GLM)

Built in waves:
1. Feb 17: Core sandbox (tabbed UI, game engine, WebSocket streaming)
2. Feb 18: Auth, deployment, scenario/policy libraries, UX improvements
3. Feb 19: Light mode, onboarding tour, docs section, PenaltyMode
4. Feb 20: Public access, guest mode, paper embedding, Firebase Hosting
5. Feb 21: Intra-scenario optimization, custom scenario CRUD, prompt anatomy
6. Feb 22: Bootstrap evaluation, admin features, per-game model selection
7. Feb 24: Programmatic API v1, dynamic concurrency throttling
8. Feb 26: Version tracking, memory optimizations, experiment registry
9. Feb 27: Onboarding tour v2, experiment showcase
10. Feb 28: Q1 campaign paper with 111+ experiment links

### experiments/ (originally experiments/castro/)
**Born:** Dec 1, 2025 (commit 1056b72b)

Started as a Castro et al. paper replication experiment framework:
- Dec 1-5: Original Castro experiment scripts (Python)
- Dec 8-9: Migrated to ai_cash_mgmt module
- Dec 9-11: Refactored to YAML-only (all Python code deleted)
- Dec 12-15: Integrated into core experiment framework
- Feb 26: Q1 2026 experiment campaign (130+ experiments)

The experiments directory evolved from custom Python scripts to pure YAML configuration — one of the project's key architectural achievements.

---

## Architectural Decision Trace

### Decision 1: Rust + Python (Oct 27)
**Why:** Performance + developer ergonomics. The grand plan specified "10-100x performance improvement over pure Python." PyO3/Maturin chosen for FFI.

**Impact:** This decision was never revisited. The two-tier architecture proved extremely durable.

### Decision 2: Decision Tree Policies (Oct 27)
**Why:** Auditability. From the grand plan: "a small, auditable program that determines payment timing." Trees can be inspected, compared, and version-controlled.

**Impact:** This enabled the entire LLM optimization framework — LLMs generate tree structures, not opaque neural network weights.

### Decision 3: Event-Sourced Simulation (Nov 3)
**Why:** Replay identity. The ability to reconstruct exact simulation output from stored events.

**Impact:** Led to a 3-week "replay identity war" (Nov 6-22) but resulted in a rock-solid replay system that enabled bootstrap evaluation and the web platform's replay features.

### Decision 4: DuckDB for Persistence (Oct 29)
**Why:** Embedded analytical database, no server needed. Fast columnar queries for experiment analysis.

**Impact:** Persisted through every era. Used for simulation data, experiment results, and paper generation.

### Decision 5: YAML-Only Experiments (Dec 11)
**Why:** Eliminate custom code per experiment. Castro experiments had too much bespoke Python.

**Impact:** Made experiments purely declarative — anyone (or any agent) could define and run experiments by editing YAML files.

### Decision 6: Bootstrap Evaluation (Dec 10)
**Why:** Proper statistical comparison of policy changes. The LLM needed to know whether a new policy was actually better.

**Impact:** Became the core evaluation mechanism in both the CLI experiment framework and the web platform.

### Decision 7: WebSocket Streaming (Feb 17)
**Why:** Real-time experiment visibility. Users needed to see LLM reasoning and simulation results as they happened.

**Impact:** Enabled the interactive experiment experience — watching AI agents reason about payment strategies in real time.

### Decision 8: Firebase + Cloud Run (Feb 17-18)
**Why:** Managed infrastructure. Nash agent chose GCP services that could be deployed without managing servers.

**Impact:** Production deployment achieved in 2 days. Firebase Hosting for frontend, Cloud Run for backend.

---

## Codebase Size Evolution

| Date | Rust LOC (approx) | Python LOC (approx) | TypeScript LOC (approx) |
|------|-------------------|---------------------|------------------------|
| Oct 27 | 2,000 | 0 | 0 |
| Oct 29 | 5,000 | 2,000 | 0 |
| Nov 3 | 8,000 | 5,000 | 2,000 (dashboard) |
| Nov 22 | 15,000 | 10,000 | 0 (frontend removed) |
| Dec 15 | 20,000 | 25,000 | 0 |
| Feb 17 | 22,000 | 30,000 | 15,000 (web platform) |
| Feb 28 | 23,000 | 35,000 | 25,000 |

The Python codebase surpassed Rust around Dec 1 when the experiment framework was added, and the TypeScript frontend grew rapidly during the web platform era.
