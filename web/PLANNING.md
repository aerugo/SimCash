# Web Platform Planning Protocol

**Version**: 1.0  
**Last Updated**: 2026-02-17

This document governs how we plan, build, test, and deploy changes to the SimCash web platform (`web/backend/` and `web/frontend/`). It inherits principles from `docs/plans/CLAUDE.md` and `docs/reference/patterns-and-conventions.md` but is specialized for web development.

---

## Golden Rules

1. **Never modify files outside `web/`** — the Rust simulator and Python API are untouched. We import from them, never change them.
2. **Policies must be real** — if the UI says an agent uses a policy, the engine must execute that policy. Display without execution is a critical bug.
3. **The economist test** — at every stage, ask: "Would a researcher using this spot something fake?" If yes, fix it before shipping.
4. **Progressive disclosure** — simple by default, powerful on demand. A new user should be productive in 30 seconds; a researcher should have full control.

---

## Invariants (Web-Specific)

These extend the core INV-1 through INV-8 from `docs/reference/patterns-and-conventions.md`.

### WEB-INV-1: Policy Reality

Every policy displayed in the UI MUST be the policy the Rust engine actually executed. Verified by:
- Assigning a Hold-heavy policy → unsettled payments exist
- Assigning a Split policy → split events in the log
- FIFO baseline costs ≠ non-trivial policy costs

### WEB-INV-2: Agent Isolation

Each agent's reasoning, costs, and events are scoped to that agent only. No agent sees another's data in the UI or in the LLM prompt.

### WEB-INV-3: Scenario Integrity

Every scenario served by the library MUST load via `SimulationConfig.from_dict()` without error. Every scenario's metadata (agent count, tick count, features) MUST match the actual config content.

### WEB-INV-4: Cost Consistency

`sum(per_agent_costs) == total_cost` always. No rounding drift, no missing components. If delay cost > 0, held payments must exist in the event log.

### WEB-INV-5: Auth Gate

All game and admin endpoints require authentication. Only `/api/health`, `/api/presets`, and static frontend are public. `SIMCASH_AUTH_DISABLED=true` bypasses this for local dev only.

### WEB-INV-6: Dark Mode Only

The UI is dark mode (#0f172a background, slate colors). No light mode toggle, no white backgrounds.

### WEB-INV-7: Relative URLs

All API and WebSocket URLs are relative (`/api/...`, not `http://localhost:8642/api/...`). This ensures the app works behind any proxy or domain.

---

## Plan Structure

### Small changes (< 2 hours)
No plan needed. Just implement, test, commit with a clear message.

### Medium changes (2-8 hours)
Single markdown file in `docs/plans/web-<feature-name>.md` with:
- Goal
- Files to create/modify
- Tests to write
- Success criteria

### Large changes (> 8 hours)
Full plan directory:

```
docs/plans/web-<feature-name>/
├── development-plan.md      # Required: phases, invariants, files, tests
├── phases/
│   ├── phase_1.md           # Detailed phase plans
│   └── ...
└── work_notes.md            # Progress tracking (optional for sub-agents)
```

---

## Development Plan Template (Large Changes)

```markdown
# <Feature Name> - Development Plan

**Status**: Draft | In Progress | Complete
**Date**: YYYY-MM-DD
**Branch**: feature/interactive-web-sandbox

## Goal
<1-2 sentences: what this accomplishes and why it matters>

## Web Invariants
<List which WEB-INV-* apply and how>

## Files

### New
| File | Purpose |
|------|---------|
| `web/backend/app/...` | ... |
| `web/frontend/src/...` | ... |

### Modified
| File | Changes |
|------|---------|
| ... | ... |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only, don't change |

## Phases

| Phase | What | Est. Time | Tests |
|-------|------|-----------|-------|
| 1 | ... | Xh | N tests |
| 2 | ... | Xh | N tests |

## Phase 1: <Name>

### Backend
- New/modified files with descriptions

### Frontend  
- New/modified files with descriptions

### Tests
- Specific test cases (name + what they verify)
- Backend: `web/backend/tests/test_<feature>.py`
- Frontend: `npx tsc -b` + `npm run build` (must pass)

### Verification
```bash
# Backend tests
cd api && .venv/bin/python -m pytest web/backend/tests/ -v --tb=short

# Frontend
cd web/frontend && npx tsc -b && npm run build
```

### UI Test Protocol
```
1. Open the app
2. Navigate to <page>
3. VERIFY: <expected state>
4. Click <element>
5. VERIFY: <expected result>
```

## Success Criteria
- [ ] All existing tests still pass
- [ ] N new tests pass
- [ ] UI test protocol passes
- [ ] WEB-INV-* verified
```

---

## Testing Requirements

Every change ships with THREE layers:

### Layer 1: Automated Tests (required, blocks merge)

**Backend** (`web/backend/tests/`):
- Test file per feature: `test_<feature>.py`
- Use existing `conftest.py` (sets `SIMCASH_AUTH_DISABLED=true`, `SIMCASH_STORAGE_MODE=local`)
- Mock external services (Firestore, GCS, LLM) — never require credentials in tests
- Test both happy path and error cases
- For engine-touching features: verify costs are non-zero, event counts are plausible

**Frontend** (TypeScript strict):
- `npx tsc -b` must pass with zero errors
- `npm run build` must succeed
- All new types properly typed (no `any` escapes)

**Run command**:
```bash
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short \
  --ignore=../web/backend/tests/test_real_llm.py
cd web/frontend && npx tsc -b && npm run build
```

### Layer 2: Integration Tests (required for engine-touching features)

When a feature changes how scenarios or policies enter the engine:
- Run every affected scenario for 1 day with seed 42
- Verify agent count, tick count, non-zero costs
- Compare against golden values (stored in `web/backend/tests/golden/`)
- If golden values change, review and update with justification

### Layer 3: UI Test Protocols (required for UI-facing features)

Written as numbered steps with explicit VERIFY assertions. Executed via browser tool after deploy.

Template:
```
Protocol: <Name>
Wave: <which wave this belongs to>

1. Open https://simcash-997004209370.europe-north1.run.app
2. Sign in
3. Navigate to <page>
4. VERIFY: <expected state with specific details>
5. Perform <action>
6. VERIFY: <expected result>
7. ...

PASS if all VERIFY steps succeed.
FAIL if any VERIFY step fails — document which step and what was observed.
```

Results logged in `memory/ui-test-results-YYYY-MM-DD.md`.

---

## Frontend Conventions

### Stack
- React 19, TypeScript strict, Vite, Tailwind v4
- recharts for charts
- No component library — custom components matching dark theme

### Styling
- Background: `#0f172a` (slate-950)
- Text: slate-100 to slate-400
- Accents: blue-400 to blue-600
- Borders: slate-700 to slate-800
- No light mode

### State Management
- React state + context (no Redux/Zustand)
- `AuthContext` for user state
- `useGameWebSocket` hook for real-time game state
- `authFetch()` from `api.ts` for all authenticated API calls

### File Organization
```
web/frontend/src/
├── api.ts              # All API calls (authFetch wrapper)
├── firebase.ts         # Firebase config + auth helpers
├── types.ts            # Shared TypeScript types
├── App.tsx             # Root: auth gate + tab navigation
├── contexts/           # React contexts (Auth)
├── hooks/              # Custom hooks (useAuth, useGameWebSocket)
├── components/         # Reusable UI components
└── views/              # Full-page views (Home, Game, Docs, etc.)
```

### API Pattern
```typescript
// All game API calls go through authFetch
export async function authFetch(path: string, options?: RequestInit) {
  const token = await getIdToken();
  return fetch(path, {
    ...options,
    headers: { ...options?.headers, Authorization: `Bearer ${token}` },
  });
}
```

---

## Backend Conventions

### Stack
- FastAPI, Python 3.13, PyO3 (Rust FFI)
- firebase-admin for auth
- google-cloud-storage for persistence
- duckdb for game data
- pydantic-ai for LLM calls

### File Organization
```
web/backend/app/
├── main.py             # FastAPI app, all routes
├── config.py           # Environment variable config
├── auth.py             # Firebase auth dependencies
├── admin.py            # Firestore-backed user management
├── storage.py          # GCS + local game storage
├── game.py             # Multi-day game engine (Game, GameDay)
├── simulation.py       # Single-run simulation wrapper
├── scenario_pack.py    # Scenario metadata + configs
├── streaming_optimizer.py  # LLM optimization with WS streaming
├── bootstrap_eval.py   # Thread-parallel bootstrap evaluation
├── models.py           # Pydantic request/response models
└── presets.py          # Legacy preset scenarios
```

### Route Pattern
```python
@app.post("/api/games")
async def create_game(
    config: CreateGameRequest,
    uid: str = Depends(get_current_user),
):
    # Auth via dependency injection
    # uid available for storage scoping
    ...
```

### Config Pattern
All configuration via environment variables, centralized in `config.py`:
```python
AUTH_DISABLED = _bool_env("SIMCASH_AUTH_DISABLED")
STORAGE_MODE = os.getenv("SIMCASH_STORAGE_MODE", "memory")
FIRESTORE_DATABASE = os.getenv("SIMCASH_FIRESTORE_DB", "(default)")
```

---

## Deployment Protocol

### Build + Deploy
```bash
# 1. Run tests
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short \
  --ignore=../web/backend/tests/test_real_llm.py
cd web/frontend && npx tsc -b && npm run build

# 2. Commit
cd SimCash && git add -A && git commit -m "feat(web): <description>"

# 3. Build Docker image (~10 min on Cloud Build)
gcloud builds submit \
  --tag europe-north1-docker.pkg.dev/simcash-487714/simcash/web:latest \
  --timeout=900 --project=simcash-487714

# 4. Deploy to Cloud Run
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/simcash-487714/simcash/web:latest \
  --region europe-north1 --project simcash-487714 \
  --set-env-vars="SIMCASH_MOCK_DEFAULT=true,SIMCASH_GCS_BUCKET=simcash-data,SIMCASH_STORAGE=gcs,SIMCASH_CONFIGS_DIR=configs/,SIMCASH_FIRESTORE_DB=simcash-platform" \
  --memory 1Gi --cpu 1 --timeout 300 --concurrency 20 --session-affinity \
  --min-instances 0 --max-instances 3 --port 8080

# 5. Verify health
curl -s https://simcash-997004209370.europe-north1.run.app/api/health

# 6. Run UI test protocols for the deployed wave
```

### Pre-Deploy Checklist
- [ ] All backend tests pass
- [ ] Frontend TypeScript compiles clean
- [ ] Frontend builds successfully
- [ ] No files outside `web/` modified (except Dockerfile, .dockerignore, .gcloudignore)
- [ ] Commit message follows `feat(web): ...` / `fix(web): ...` convention

### Post-Deploy Checklist
- [ ] `/api/health` returns 200
- [ ] Sign-in works (Google)
- [ ] Can create and run a game
- [ ] UI test protocols for this wave pass
- [ ] Previous wave protocols still pass (regression)

---

## Sub-Agent Dispatch Protocol

When spawning sub-agents for web platform work:

1. **Always include** in the task description:
   - Repo path: `/Users/ned/.openclaw/workspace-nash/SimCash`
   - Branch: `feature/interactive-web-sandbox`
   - "DO NOT modify files outside web/"
   - Test commands (pytest + tsc + build)
   - "Read existing files before modifying"
   - "All existing tests must still pass"

2. **Always include** the relevant plan/phase file to read

3. **Always verify** after completion:
   - Did it follow the plan?
   - Are all tests passing?
   - Were web invariants respected?
   - Did it modify files outside web/?

---

## Patterns

### Pattern W-1: Scenario Loading

All scenarios enter the engine through the same path:
```python
yaml_dict = load_scenario_yaml(path_or_string)
config = SimulationConfig.from_dict(yaml_dict)
ffi_dict = config.to_ffi_dict()
orchestrator = Orchestrator.new(ffi_dict)
```
Never bypass `SimulationConfig.from_dict()`. It validates and normalizes.

### Pattern W-2: Policy Assignment

Policies enter the engine via InlineJson:
```python
agent["policy"] = {"type": "InlineJson", "json_string": json.dumps(policy_json)}
agent["liquidity_allocation_fraction"] = policy_json["parameters"]["initial_liquidity_fraction"]
```
Both the fraction AND the tree must be set. The fraction controls initial liquidity; the tree controls per-tick decisions.

### Pattern W-3: Game State Lifecycle

```
POST /api/games → Game created (in-memory + DuckDB + GCS index)
POST /api/games/{id}/step → Day simulated → results written to DuckDB → uploaded to GCS
GET /api/games/{id} → Check memory cache first, then load from GCS
DELETE /api/games/{id} → Remove from memory + DuckDB + GCS + index
```

### Pattern W-4: Auth Flow

```
Frontend: Firebase sign-in → get ID token
API call: Authorization: Bearer <token>
Backend: verify_id_token() → uid → check is_allowed() → proceed or 403
WebSocket: token as ?token= query param
Dev mode: SIMCASH_AUTH_DISABLED=true → fixed "dev-user" uid
```
