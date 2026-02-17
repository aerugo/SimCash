# Web Sandbox Improvement — Meta Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Goal

Implement 5 improvement plans to bring the web sandbox from "working prototype" to "faithful interactive reproduction of the paper's experiments." The order matters — some plans depend on others, and some unlock more value earlier.

## Dependency Graph

```
[1] Game Setup ──────────────────────────────────┐
                                                  ├──▶ Playtest Checkpoint A
[2] WebSocket Streaming ─────────────────────────┘         │
        │                                                  │
        ├──▶ [5] Loading States                            │
        │                                                  │
[3] Bootstrap Evaluation ────────────────────────┐         │
        │                                        ├──▶ Playtest Checkpoint B
        └──▶ [4] Accept/Reject Display ──────────┘
```

- Plans 1 and 2 are **independent foundations** — can be built in parallel or either-first.
- Plan 3 is **independent of 1 and 2** on the backend, but benefits from WebSocket streaming for UX.
- Plan 4 **depends on Plan 3** — can't display accept/reject without bootstrap evaluation producing that data.
- Plan 5 **depends on Plan 2** — loading states are WebSocket progress events.

## Implementation Order

### Wave 1: Foundations (independent, do first)

| Order | Plan | Why First |
|-------|------|-----------|
| **1st** | [1] Game Setup | Immediate UX improvement. Users can't configure games without it. Self-contained. Fast to build (~1 day). |
| **2nd** | [2] WebSocket Streaming | Prerequisite for Plans 5 and good UX for Plan 3. Without it, LLM mode is unusable (60s+ freezes). (~1-2 days). |

**Playtest Checkpoint A**: After Wave 1, the sandbox should be usable end-to-end with mock reasoning. Users pick a scenario, configure it, run it with streaming day-by-day updates. Test this before moving on.

### Wave 2: Scientific Core (the hard part)

| Order | Plan | Why Now |
|-------|------|---------|
| **3rd** | [3] Bootstrap Evaluation | This is the scientific heart — the paper's methodology. Most complex plan. Must be correct. (~2-3 days). |
| **4th** | [4] Accept/Reject Display | Depends on Plan 3 output. Quick frontend work once the data exists. (~0.5-1 day). |

**Playtest Checkpoint B**: After Wave 2, the sandbox faithfully reproduces the paper's evaluation methodology. Run a full game with real LLM, verify that bootstrap acceptance/rejection matches experiment runner behavior. Compare converged fractions to paper results.

### Wave 3: Polish

| Order | Plan | Why Last |
|-------|------|----------|
| **5th** | [5] Loading States | Pure UX polish. Depends on Plan 2. Nice to have, not blocking scientific validity. (~0.5-1 day). |

## Estimated Timeline

| Wave | Plans | Est. Duration | Cumulative |
|------|-------|---------------|------------|
| Wave 1 | Setup + WebSocket | 2-3 days | 2-3 days |
| Wave 2 | Bootstrap + Accept/Reject | 2.5-4 days | 5-7 days |
| Wave 3 | Loading States | 0.5-1 day | 6-8 days |

Total: **~6-8 working days** if done sequentially. Waves 1 can overlap internally.

## Testing Strategy

Each plan has its own TDD phases, but at the meta level:

1. **After each plan**: Run full test suite (`uv run --directory api python -m pytest web/backend/tests/ -v`)
2. **After each wave**: Manual playtest in browser (http://localhost:5173)
3. **After Wave 2**: Cross-validate bootstrap results against experiment runner output — run the same scenario in both the web sandbox and `payment-sim experiment run` and compare acceptance decisions. This validates INV-GAME-3.
4. **Final validation**: Run exp2 scenario in web sandbox with real LLM, verify convergence to ~8-9% (A) and ~6-7% (B) matching paper results.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bootstrap eval diverges from experiment runner | High — undermines scientific validity | Phase 5 of Plan 3 is explicit cross-validation |
| LLM calls OOM the machine during bootstrap | Medium — 50 samples × 2 policies = 100 sims | Add configurable `num_samples` (default 10 for web, 50 for paper-faithful mode) |
| WebSocket protocol complexity | Low-Medium — state sync bugs | Phase 5 of Plan 2 tests message ordering |
| Real LLM costs during development | Low — testing is expensive | Use mock mode for development, real LLM only for validation checkpoints |

## Key Decision: Bootstrap Sample Count

The paper uses 50 bootstrap samples. For the web sandbox:
- **Default**: 10 samples (fast enough for interactive use, ~10s per evaluation)
- **Paper-faithful mode**: 50 samples (toggle in game setup, warns about duration)
- **Quick mode**: 1 sample (no bootstrap, just paired single-seed comparison — for rapid iteration)

This is configurable in Game Setup (Plan 1) and used by Bootstrap Evaluation (Plan 3).

## Files Overview

All plans live under `docs/plans/`:

```
docs/plans/
├── web-sandbox-meta-plan.md          ← this file
├── web-game-setup/
│   ├── development-plan.md
│   └── phases/phase_{1-5}.md
├── web-websocket-streaming/
│   ├── development-plan.md
│   └── phases/phase_{1-5}.md
├── web-bootstrap-evaluation/
│   ├── development-plan.md
│   └── phases/phase_{1-5}.md
├── web-accept-reject-display/
│   ├── development-plan.md
│   └── phases/phase_{1-5}.md
└── web-loading-states/
    ├── development-plan.md
    └── phases/phase_{1-5}.md
```

## Start Command

Begin with Plan 1, Phase 1: `docs/plans/web-game-setup/phases/phase_1.md`
