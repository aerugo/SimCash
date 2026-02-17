# Production Deployment: Firebase Auth + DuckDB Persistence + Cloud Run

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: Draft  
**Branch**: `feature/interactive-web-sandbox`  
**Report**: `docs/reports/gcp-deployment-plan-v2.md`

## Goal

Deploy SimCash as a real multi-user platform on Google Cloud. Users sign in with Firebase Auth, games persist to Cloud Storage as DuckDB files, and the whole thing runs on Cloud Run with scale-to-zero economics.

Not a SaaS product — a research tool for invited researchers.

## Phases

| Phase | What | Est. Time | Dependencies |
|-------|------|-----------|--------------|
| 1 | Firebase Auth backend + frontend | 3h | Firebase project |
| 2 | Storage layer (GCS + DuckDB persistence) | 3h | Phase 1, GCS bucket |
| 3 | Dockerize + local validation | 2h | Phase 2 |
| 4 | Cloud Run deployment | 2h | Phase 3, GCP project |
| 5 | Polish + hardening | 2h | Phase 4 |

Total: ~12 hours of implementation.

## Pre-requisites

Before starting Phase 1:

1. **GCP project** — create or choose one (e.g., `simcash-prod`)
2. **Firebase project** — create in Firebase console, linked to the GCP project
3. **Firebase Auth** — enable Google sign-in provider
4. **GCS bucket** — `gsutil mb -l europe-north1 gs://simcash-data`
5. **Secret Manager** — store OpenAI key: `echo -n "$KEY" | gcloud secrets create openai-api-key --data-file=-`

Hugi needs to do steps 1-3 (requires project owner access). Steps 4-5 can be scripted.

## Constraints

- All new code in `web/` (core simulator untouched)
- Existing in-memory game flow must still work for local dev (no GCS required locally)
- Tests must pass with mocked Firebase + GCS
- Backend port stays 8642 for local dev
- Frontend Firebase config is public (API key, project ID) — safe to commit

---

## Phase 1: Firebase Auth

**File**: `phases/phase_1.md`

### Backend

New files:
- `web/backend/app/auth.py` — Firebase Admin SDK init, `get_current_user` dependency

Changes:
- `web/backend/app/main.py` — add auth dependency to all `/api/games/*` endpoints, keep `/api/health` and `/api/presets` public
- `web/backend/pyproject.toml` or requirements — add `firebase-admin`

### Frontend

New files:
- `web/frontend/src/firebase.ts` — Firebase config, auth init, sign-in/sign-out helpers
- `web/frontend/src/contexts/AuthContext.tsx` — React context providing user state
- `web/frontend/src/components/LoginPage.tsx` — simple sign-in page
- `web/frontend/src/hooks/useAuth.ts` — hook for current user + token

Changes:
- `web/frontend/src/App.tsx` — wrap in AuthContext, show LoginPage if not authenticated
- `web/frontend/src/hooks/useGameWebSocket.ts` — include auth token in WS connection (query param or first message)
- All API call sites — add `Authorization: Bearer <token>` header

### Auth flow

1. User opens app → Firebase checks auth state
2. Not signed in → show LoginPage with "Sign in with Google" button
3. Signed in → get ID token, include in all API requests
4. Backend verifies token with Firebase Admin SDK, extracts `uid`
5. All game operations scoped to `uid`

### Local dev mode

`SIMCASH_AUTH_DISABLED=true` env var skips token verification and uses a fixed dev `uid`. Default in local dev, never in production.

### Tests

- Mock `firebase_admin.auth.verify_id_token()` in conftest
- Test: unauthenticated request → 401
- Test: valid token → uid extracted correctly
- Test: expired/invalid token → 401

---

## Phase 2: Storage Layer (GCS + DuckDB Persistence)

**File**: `phases/phase_2.md`

### Backend

New files:
- `web/backend/app/storage.py` — `GameStorage` class (GCS upload/download, JSON index, local cache)

Changes:
- `web/backend/app/game.py` — add `save_to_duckdb()` method on `Game` class (writes day results using existing `EventWriter`/`DatabaseManager`)
- `web/backend/app/main.py` — wire storage into game lifecycle:
  - `POST /api/games` → create game + init DuckDB + update index
  - `POST /api/games/{id}/step` → run day + write to DuckDB + upload to GCS
  - `GET /api/games` → read user's index from GCS (or local cache)
  - `GET /api/games/{id}` → check memory, then load from GCS
  - `DELETE /api/games/{id}` → remove from memory + GCS + index

### DuckDB integration

Reuse existing persistence layer from `api/payment_simulator/persistence/`:
- `DatabaseManager` — creates tables, manages connection
- `EventWriter` — writes simulation events
- Schema from `api/payment_simulator/persistence/schemas/`

Each game gets its own `.duckdb` file. After each day:
1. Open DuckDB connection to local file
2. Write day's events, costs, policies using existing writers
3. Close connection
4. Upload file to GCS

### Game index

JSON manifest at `gs://simcash-data/users/{uid}/games/index.json`:
```json
{
  "games": [
    {
      "game_id": "abc123",
      "scenario_id": "2bank_12tick",
      "scenario_name": "2 Banks, 12 Ticks",
      "created_at": "2026-02-17T15:00:00Z",
      "updated_at": "2026-02-17T15:30:00Z",
      "days_completed": 5,
      "max_days": 25,
      "status": "in_progress",
      "use_llm": true
    }
  ]
}
```

### Local dev mode

`SIMCASH_STORAGE=local` — store DuckDB files in `web/backend/data/{uid}/` instead of GCS. Default for local dev.

### Tests

- Mock GCS client (or use `google-cloud-storage` testbench)
- Test: create game → DuckDB file exists
- Test: run day → events written to DuckDB
- Test: save + load roundtrip → game state intact
- Test: list games → index returns correct entries
- Test: delete game → removed from GCS + index

---

## Phase 3: Dockerize

**File**: `phases/phase_3.md`

### New files
- `Dockerfile` (repo root) — multi-stage build (Rust → frontend → runtime)
- `.dockerignore` — exclude `target/`, `node_modules/`, `.git/`, `*.db`, `.venv/`, `__pycache__/`

### Backend changes
- `web/backend/app/main.py` — mount static frontend from `web/frontend/dist/` if it exists (after all API routes)
- `web/backend/app/config.py` — centralize env var config (`PORT`, `SIMCASH_MOCK_DEFAULT`, `SIMCASH_GCS_BUCKET`, `SIMCASH_AUTH_DISABLED`, `SIMCASH_STORAGE`, `SIMCASH_CONFIGS_DIR`)

### Frontend changes
- `web/frontend/src/hooks/useGameWebSocket.ts` — relative WebSocket URL (`${protocol}//${window.location.host}/api/games/...`)
- `web/frontend/src/api.ts` (or wherever fetch calls live) — relative API URLs (no `localhost`)

### Validation
```bash
docker build -t simcash .
docker run -p 8080:8080 \
  -e SIMCASH_AUTH_DISABLED=true \
  -e SIMCASH_STORAGE=local \
  simcash
# Open http://localhost:8080, create a game, run a day
```

---

## Phase 4: Cloud Run Deployment

**File**: `phases/phase_4.md`

### Infrastructure setup
```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com
gcloud artifacts repositories create simcash --repository-format=docker --location=europe-north1
```

### Build + deploy
```bash
gcloud builds submit --tag europe-north1-docker.pkg.dev/simcash-prod/simcash/web:latest --timeout=600

gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/simcash-prod/simcash/web:latest \
  --region europe-north1 \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest" \
  --set-env-vars="SIMCASH_MOCK_DEFAULT=true,SIMCASH_GCS_BUCKET=simcash-data,FIREBASE_PROJECT_ID=simcash-prod,SIMCASH_STORAGE=gcs" \
  --memory 1Gi --cpu 1 --timeout 300 --concurrency 20 \
  --min-instances 0 --max-instances 3 --session-affinity
```

### Verify
1. Hit Cloud Run URL → frontend loads
2. Sign in with Google → success
3. Create game → game appears in list
4. Run a day (mock mode) → results display
5. Refresh page → game persists (loaded from GCS)
6. Scale to zero → wait → reopen → game still there

---

## Phase 5: Polish + Hardening

**File**: `phases/phase_5.md`

1. **Rate limiting** — per-uid limit on game creation (10/hour) and LLM calls (20/hour). In-memory counter, resets on instance restart. Good enough.
2. **Email allowlist** — `SIMCASH_ALLOWED_EMAILS=a@b.com,c@d.com` env var. If set, reject auth for unlisted emails. If unset, allow all.
3. **Health check** — `/api/health` already exists. Add GCS connectivity check.
4. **Billing alerts** — set up at $10, $50, $100/month in GCP console.
5. **CI/CD** — `cloudbuild.yaml` for auto-deploy on push to deploy branch.
6. **Custom domain** — optional. `gcloud run domain-mappings create --service simcash --domain simcash.example.com`
7. **Frontend "My Games" page** — list saved games, resume, delete.
8. **Cleanup cron** — Cloud Scheduler job to delete games older than 90 days (optional, cost is negligible).

---

## File Inventory

### New files
```
web/backend/app/auth.py
web/backend/app/storage.py
web/backend/app/config.py
web/frontend/src/firebase.ts
web/frontend/src/contexts/AuthContext.tsx
web/frontend/src/components/LoginPage.tsx
web/frontend/src/hooks/useAuth.ts
web/README.md
Dockerfile
.dockerignore
cloudbuild.yaml
```

### Modified files
```
web/backend/app/main.py          (auth deps, storage, static serving)
web/backend/app/game.py          (DuckDB persistence method)
web/frontend/src/App.tsx         (auth wrapper)
web/frontend/src/hooks/useGameWebSocket.ts  (relative WS URL, auth token)
web/frontend/package.json        (firebase dependency)
```

### NOT modified
```
simulator/                       (untouched)
api/                             (untouched — we import from it, don't change it)
```
