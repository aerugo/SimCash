# SimCash Platform Expansion — Master Implementation Plan

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: Draft  
**Branch**: `feature/interactive-web-sandbox`  
**Planning Protocol**: `web/PLANNING.md`  
**Research Reports**: `docs/reports/new-scope/00-07*.md`

---

## Vision

Transform SimCash from a narrow demo ("watch 2 AI agents tune one float") into a research platform that exposes the full power of the engine: 30+ policy types, 140+ context fields, 11+ scenario templates, custom events, LSM algorithms, and general-purpose LLM policy optimization.

## Governing Principles

### 1. Never Touch the Engine
All work stays in `web/`. We import from `simulator/` and `api/` — we never modify them. The engine is correct and complete; the web layer just needs to let it breathe.

### 2. The Economist Test
At every stage: "Would a researcher spot something fake?" If a policy says "Hold" but payments settle anyway — critical bug. If costs don't match the scenario's rates — critical bug. Display must match execution.

### 3. Progressive Disclosure
Simple by default, powerful on demand. A new user picks a scenario and clicks "Launch" in under 30 seconds. A researcher configures per-agent policies, constraint presets, optimization intervals, and custom events.

### 4. Build on What Exists
The engine has 30+ policies, 11 scenario configs, a complete prompt engineering system, constraint validation, and bootstrap evaluation. We surface these — we don't reinvent them.

### 5. Strict TDD
Every feature ships with automated tests (pytest + TypeScript), integration tests (engine roundtrips), and UI test protocols (browser click-throughs). Nothing is "done" until all three pass.

### 6. Ship in Waves
Each wave is independently deployable and valuable. Wave 1 makes the platform usable. Wave 4 makes it powerful. A researcher can do meaningful work after Wave 1.

---

## Plans

| # | Plan | Directory | Est. Time | Wave |
|---|------|-----------|-----------|------|
| 01 | Scenario Library | `01-scenario-library/` | 9h | 1 |
| 02 | Policy Library | `02-policy-library/` | 10h | 1 |
| 03 | UX Restructure | `03-ux-restructure/` | 7h | 1 |
| 04 | Policy Evolution Display | `04-policy-evolution/` | 9h | 2 |
| 05 | Optimization Configuration | `05-optimization-config/` | 6h | 3 |
| 06 | Scenario Editor | `06-scenario-editor/` | 13h | 4 |
| 07 | Policy Editor & Viewer | `07-policy-editor/` | 14h | 3+4 |
| 08 | Documentation Expansion | `08-docs-expansion/` | 19h | 2+3+4 |

**Total estimated**: ~87 hours across 4 waves (~6 weeks at moderate pace)

---

## Wave Structure

### Wave 1: Foundation (Plans 01, 02, 03) — ~26h

**Goal**: Make the platform usable with real breadth.

**What ships**:
- Scenario library with 14+ scenarios (11 examples + 3 paper)
- Policy library with 30+ policies
- Scenario-first UX flow: Browse → Configure → Launch
- Per-agent policy assignment
- "My Simulations" with saved games

**Why this first**: Everything else builds on having a scenario library and policy library. The UX restructure creates the navigation frame that subsequent waves populate.

**Dependencies**: None (builds on existing backend + frontend)

**Acceptance criteria**:
- Every library scenario creates and runs a game
- Every library policy validates through FFI
- Full UX flow works: Home → Library → Launch → Game → Home
- 35+ new backend tests, frontend builds clean
- UI protocols W1-Scenario-Library, W1-Policy-Library, W1-UX-Flow pass

### Wave 2: Visibility (Plans 04, 08 Tiers 1-2) — ~17h

**Goal**: Show what's happening inside the optimization.

**What ships**:
- Policy evolution timeline (versions per day, accept/reject status)
- Parameter trajectory charts
- Policy diff view (day-to-day changes)
- Docs: Core Concepts + Scenarios (Tiers 1-2)

**Why second**: Once users can run diverse scenarios with different policies, they need to see how policies evolve. The docs explain what they're looking at.

**Dependencies**: Wave 1 (scenario + policy libraries)

**Acceptance criteria**:
- Policy history endpoint returns all days with correct status
- Diff logic correctly identifies parameter and structural changes
- Docs cover all 7 cost types and all 7 event types
- 18+ new backend tests, frontend builds clean
- UI protocols W2-Policy-Evolution, W2-Docs pass

### Wave 3: Power Features (Plans 05, 07 Phase 1, 08 Tiers 3-4) — ~19h

**Goal**: Unlock the engine's full optimization potential.

**What ships**:
- Configurable optimization interval (every N days, manual)
- Constraint depth presets (Simple → Standard → Full)
- Policy tree viewer (visual flowcharts)
- Docs: Policies + Optimization (Tiers 3-4)

**Why third**: With libraries and visibility in place, researchers need control over the optimization process and the ability to inspect policy trees visually.

**Dependencies**: Wave 2 (policy evolution display)

**Acceptance criteria**:
- Optimization interval controls when LLM is called
- Wider constraints produce policies with conditions (not just Release-all)
- PolicyTreeViewer renders all 30+ library policies
- Docs cover all 16 actions and 140+ fields
- 26+ new backend tests, frontend builds clean
- UI protocols W3-Optimization-Config, W3-Policy-Viewer, W3-Docs pass

### Wave 4: Creation Tools (Plans 06, 07 Phases 2-5, 08 Tier 5) — ~25h

**Goal**: Let researchers create their own experiments.

**What ships**:
- Scenario editor with YAML + validation
- Event timeline builder
- Policy JSON editor with schema validation
- Field/action pickers
- Docs: Research Guides (Tier 5)

**Why last**: Creation tools are the most complex and least critical for initial use. Researchers can do meaningful work with the libraries + presets from Waves 1-3.

**Dependencies**: Wave 3 (policy viewer, optimization config)

**Acceptance criteria**:
- Custom scenarios validate through full pipeline
- Custom policies execute correctly in the engine
- Event timeline builder generates valid YAML
- Research guides have step-by-step instructions
- 18+ new backend tests, frontend builds clean
- UI protocols W4-Scenario-Editor, W4-Policy-Editor, W4-Docs pass

---

## Implementation Order Within Waves

### Wave 1 Ordering
```
01-scenario-library Phase 1-2 (backend)
    ↓
02-policy-library Phase 1-2 (backend)
    ↓
01-scenario-library Phase 3-4 (frontend + integration)
02-policy-library Phase 3-4 (frontend + integration)
    ↓  (can parallelize)
03-ux-restructure Phase 1-3 (frontend)
    ↓
Deploy + UI test protocols
```

Scenario and policy backends first (independent), then frontends (can parallelize), then UX restructure (depends on both libraries).

### Wave 2 Ordering
```
04-policy-evolution Phase 1 (backend)
    ↓
04-policy-evolution Phase 2-3 (frontend)
08-docs-expansion Phase 1-3 (Tiers 1-2)
    ↓  (parallelize)
Deploy + UI test protocols
```

### Wave 3 Ordering
```
05-optimization-config Phase 1-2 (backend)
07-policy-editor Phase 1 (PolicyTreeViewer — frontend only)
    ↓  (parallelize)
05-optimization-config Phase 3 (frontend)
08-docs-expansion Phase 4-5 (Tiers 3-4)
    ↓
Deploy + UI test protocols
```

### Wave 4 Ordering
```
06-scenario-editor Phase 1 (backend)
07-policy-editor Phase 2 (backend)
    ↓  (parallelize)
06-scenario-editor Phase 2-3 (frontend)
07-policy-editor Phase 3-4 (frontend)
    ↓  (parallelize)
06-scenario-editor Phase 4 (integration)
07-policy-editor Phase 5 (integration)
08-docs-expansion Phase 6 (Tier 5)
    ↓
Deploy + UI test protocols
```

---

## Testing Strategy (Cross-Wave)

### Per-Wave
- All automated tests pass (Layer 1)
- Integration tests with golden files pass (Layer 2)
- UI test protocols for this wave pass (Layer 3)
- ALL previous wave UI protocols re-run (regression)

### Cumulative Test Counts (estimated)

| After Wave | Backend Tests | New This Wave | UI Protocols |
|------------|---------------|---------------|-------------|
| Current | 114 | — | — |
| Wave 1 | ~150 | ~36 | 3 |
| Wave 2 | ~168 | ~18 | 2 (+3 regression) |
| Wave 3 | ~194 | ~26 | 3 (+5 regression) |
| Wave 4 | ~212 | ~18 | 3 (+8 regression) |

### Golden Files

After Wave 1, create golden files in `web/backend/tests/golden/`:
- `scenarios.json` — metadata for all library scenarios
- `scenario_costs.json` — seed-42 costs for each scenario (1 day)
- `policy_metadata.json` — metadata for all library policies

Update golden files only with explicit justification.

---

## Deployment

Each wave deploys independently:

```bash
# Test → Commit → Build → Deploy → Verify
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short --ignore=../web/backend/tests/test_real_llm.py
cd web/frontend && npx tsc -b && npm run build
git add -A && git commit -m "feat(web): wave N — <description>"
gcloud builds submit --tag europe-north1-docker.pkg.dev/simcash-487714/simcash/web:latest --timeout=900 --project=simcash-487714
gcloud run deploy simcash --image europe-north1-docker.pkg.dev/simcash-487714/simcash/web:latest --region europe-north1 --project simcash-487714 --set-env-vars="..." --memory 1Gi --cpu 1 --timeout 300 --concurrency 20 --session-affinity --min-instances 0 --max-instances 3 --port 8080
curl -s https://simcash-997004209370.europe-north1.run.app/api/health
# Run UI test protocols
```

---

## Sub-Agent Strategy

Waves parallelize well at the plan level. Within each wave, backend work can often be done by one sub-agent while frontend work is done by another.

Recommended sub-agent dispatch pattern:
1. One agent per plan's backend phases
2. One agent per plan's frontend phases (after backend is done)
3. Nash (me) handles integration phases, UI test protocols, and deploys

Always include in sub-agent tasks:
- Link to the specific plan file
- "Read `web/PLANNING.md` first"
- Test commands
- "All existing tests must still pass"
- "DO NOT modify files outside web/"

---

## What This Achieves

| Metric | Before | After Wave 1 | After Wave 4 |
|--------|--------|-------------|-------------|
| Scenarios available | 6 presets | 14+ library | 14+ library + custom |
| Policies available | 1 (FIFO) | 30+ library | 30+ library + custom |
| LLM optimization scope | 1 float | 1 float | Full decision trees |
| Optimization control | Every day, fixed | Every day, fixed | Configurable interval + constraints |
| Policy visibility | Reasoning text | Reasoning text | Tree viewer + timeline + diff |
| Documentation | 720 lines, narrow | 720 lines | 5-tier comprehensive |
| Scenario creation | None | Select from library | YAML editor + event builder |
| Policy creation | None | Select from library | JSON editor + field picker |
