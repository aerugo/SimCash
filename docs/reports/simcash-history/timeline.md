# SimCash Development Timeline

## Overview
- **Total commits:** 2,181
- **Date range:** 2025-10-27 to 2026-02-28 (4 months)
- **Contributors:** aerugo/Hugi (human), Claude (Claude Code via PR branches), nash4cash/Ned (Nash agent), Stefan (Stefan agent)

## Commit Authorship
| Author | Commits | Role |
|--------|---------|------|
| Claude | 1,050 | Claude Code (PR branches, `claude/` prefix) |
| nash4cash | 456 | Nash agent (OpenClaw, multi-agent era) |
| Hugi | 437 | Human developer (direct commits + PR merges) |
| aerugo | 220 | Human developer (early era, same person as Hugi) |
| Ned | 18 | Nash agent (alternate identity) |

---

## Era 1: "The Sprint" — Solo Human + Claude Code (Oct 27 – Nov 3, 2025)
**~125 commits in 8 days. Author: aerugo (Hugi).**

The entire Rust simulation engine was built in a single intense sprint. Every commit is by `aerugo`. Claude Code is clearly being used (commit messages follow TDD patterns, structured phases), but there are no PR branches yet — Hugi is committing directly to main.

### Key milestones:
- **Oct 27:** Phases 1-4b complete in ONE DAY (13 commits). Core models, RTGS+LSM settlement, queue policies, orchestrator tick loop.
- **Oct 28:** CLI tool, README, Grand Plan updates
- **Oct 29:** Collateral management (3-tree architecture), persistence layer with DuckDB, FFI bridge via PyO3 — **31 commits in one day**
- **Oct 30:** API cost/metrics endpoints, enhanced verbose CLI
- **Oct 31-Nov 1:** Replay system, Phase 9.5 cost-aware policy DSL
- **Nov 2:** Diagnostic dashboard frontend (first React code)
- **Nov 3:** Event timeline, SimulationRunner architecture — 27 commits

**Architecture born in this era:**
- Rust core engine (`simulator/src/` — originally `backend/`)
- Python API layer (`api/`)
- PyO3 FFI bridge
- DuckDB persistence
- Policy DSL (decision tree JSON)
- RTGS + LSM settlement engines

---

## Era 2: "Claude Code Takes the Wheel" — PR-based Development (Nov 4 – Nov 22, 2025)
**~650 commits. Claude becomes primary author via PR branches.**

Starting Nov 4, `Claude` appears as an author for the first time. The pattern shifts: Claude creates branches (`claude/feature-name-hash`), Hugi merges via PR. This is classic Claude Code workflow — human directs, AI executes.

### Sub-phases:

#### Nov 4-6: Replay Determinism Obsession (~60 commits)
The project becomes obsessed with "replay identity" — making replayed simulation output byte-identical to the original run. This drives deep refactoring of the output system.

#### Nov 9-10: Scenario Events & Performance (~80 commits)
- Scenario events system (liquidity shocks, rate changes)
- Performance optimization (AgentQueueIndex, EvalContext caching)
- LSM deterministic redesign

#### Nov 11-14: Policy System Expansion (~230 commits, peak intensity)
- **Nov 13 alone: 88 commits** — the single most productive day
- Policy-scenario testing architecture (54 TDD tests)
- Policy system v2: state registers, budget system, collateral timers, decision path auditing
- TARGET2 LSM alignment
- Collateral headroom invariants

#### Nov 15-16: Replay Identity War (~100 commits)
- Massive effort to achieve perfect replay identity
- Deprecation of `credit_limit` in favor of `unsecured_cap`
- Cost timeline visualization

#### Nov 17-22: Maturation (~75 commits)
- Agent policy comparison experiments
- Priority system redesign (T2-compliant)
- 201 EvalContext TDD tests
- TARGET2 LSM alignment complete
- Game design doc refactored

---

## Era 3: "The Research Pivot" — BIS Model & Castro Experiments (Nov 27 – Dec 5, 2025)
**~350 commits. Focus shifts from engine building to research.**

### Nov 27-28: BIS Model Integration (~70 commits)
- Research on BIS AI cash management RTGS model
- Priority-based delay cost multipliers
- Liquidity pool allocation
- Comprehensive documentation overhaul
- mypy/ruff typing enforcement
- Frontend module removed

### Nov 29-Dec 1: API Consistency & First Experiments (~90 commits)
- API output consistency refactoring
- StateProvider protocol
- **First LLM experiment:** policy optimizer with GPT integration
- Castro et al. paper replication begins
- Structured output via PydanticAI

### Dec 2-5: Castro Replication Sprint (~95 commits)
- Deferred crediting mode
- `backend/` renamed to `simulator/`
- ai_cash_mgmt module born
- Multiple LLM providers (OpenAI, Gemini, Anthropic)
- Agent isolation in LLM optimization
- Experiment reproducibility framework

---

## Era 4: "The Great Refactor" — Architecture Overhaul (Dec 8 – Dec 15, 2025)
**~500 commits in 8 days. The most intense period.**

### Dec 8-9: Foundation (~160 commits)
- ai_cash_mgmt module: TransactionSampler, ConvergenceDetector, PolicyOptimizer, GameOrchestrator
- 18 refactor phases planned and executed
- Castro code migrated to core infrastructure

### Dec 10-11: Bootstrap & Experiments Framework (~170 commits)
- Bootstrap evaluation system
- YAML-only experiments architecture
- Generic experiment runner
- Phase 18: Delete all Castro Python code
- Documentation navigator agent added (first "agent" concept in codebase)

### Dec 12-15: Optimizer Prompt & Paper (~170 commits)
- Self-documenting cost types
- New optimizer prompt system
- SimCash paper v1-v3 drafted
- Experiment chart generation
- Paper generator infrastructure
- **Dec 15: CLAUDE.md files for requests/plans structure** — formalization of the development workflow

---

## Era 5: "The Paper Machine" — Automated Paper Generation (Dec 16 – Dec 22, 2025)
**~350 commits. Paper generator becomes a first-class system.**

### Key developments:
- Policy evaluation metrics persistence
- Programmatic paper generation system (LaTeX, TDD with 130+ tests)
- Paper v4 and v5 with data-driven content
- Bootstrap seed fixes (INV-13)
- LLM reasoning summary capture
- Peer review feedback addressed
- Experiment databases stored via Git LFS

**The paper was literally generated by code from experiment databases.**

---

## Dormant Period (Dec 23, 2025 – Feb 16, 2026)
**Only 2 commits (Jan 15 README updates). ~8 weeks of silence.**

---

## Era 6: "The Multi-Agent Explosion" — Web Platform & Nash/Stefan (Feb 17 – Feb 28, 2026)
**~475 commits in 12 days. Entirely new development paradigm.**

### The Big Bang — Feb 17 (56 commits, all nash4cash)
In a single day, Nash agent creates the entire web platform:
- Backend + frontend
- Interactive sandbox with tabbed UI
- AI agent reasoning visualization
- Multi-day policy optimization game
- WebSocket streaming
- Bootstrap paired evaluation
- Loading states, policy history
- UX reviews and improvements
- GCP deployment plan
- GIL-release FFI for thread-parallel simulation
- Firebase Auth
- Docker containerization

### Feb 18-19: Platform Hardening (~120 commits)
- Admin system, invites, magic link sign-in
- Scenario & policy libraries
- Policy evolution visibility
- Constraint presets
- Cloud Run deployment
- Blog posts
- Multi-model support (Gemini 3, GLM-5, GPT-5.2)
- Mobile responsiveness
- Onboarding tour
- Light mode theme

### Feb 20-22: Production Polish (~175 commits)
- Public access without login
- Guest mode, API keys
- Password auth
- Per-game model selection
- Admin impersonation
- Custom scenario/policy CRUD
- Bootstrap evaluation wired into web
- Daily liquidity reallocation cycle
- Game module refactor (6 phases)

### Feb 23-26: Scale & Observability (~100 commits)
- Programmatic API v1
- Dynamic concurrency throttling
- Version tracking and prompt manifests
- Memory optimizations
- 130+ experiments run (Q1 2026 campaign)

### Feb 27-28: Stefan Agent Arrives (~45 commits)
- **Stefan** appears as a named agent running experiments
- Onboarding tour v2
- Experiment showcase page
- Q1 2026 campaign paper with 111+ experiment links
- All data points linked to source experiments

---

## Key Pattern: Contributor Evolution

```
Oct 27-Nov 3:   aerugo only (human + Claude Code, direct commits)
Nov 4-Dec 22:   Claude + Hugi (PR branches, human-directed AI)
                aerugo occasional (human manual commits)
Jan 15:         Hugi (2 quick updates)
Feb 17-28:      nash4cash dominates (456 commits in 12 days!)
                Ned (18 commits, same agent)
                Stefan appears (named agent, experiments)
                Hugi (1 commit)
```

## Commit Velocity
| Date | Commits | Era |
|------|---------|-----|
| Nov 13 | 88 | Peak Claude Code day |
| Dec 11 | 93 | Peak refactor day |
| Feb 18 | 65 | Peak Nash agent day |
| Feb 17 | 56 | Web platform birth |

The shift from ~50 commits/day with Claude Code to similar velocity with Nash represents a fundamental change: from human-directed AI to autonomous AI agents.
