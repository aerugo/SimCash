# SimCash Production Deployment Plan v2

**Date**: 2026-02-17  
**Author**: Nash  
**Status**: Draft  
**Supersedes**: `gcp-deployment-plan.md` (v1 — single-container research demo)

## What Changed Since v1

v1 assumed an ephemeral demo: in-memory game state, no users, scale-to-zero loses everything. Now we need:

1. **User accounts** — Firebase Auth (Google sign-in, email/password)
2. **Persistent simulation data** — saved games, results, policies per user
3. **DuckDB in production** — the existing codebase uses DuckDB extensively for analytical persistence; we should reuse it, not reinvent

The scope is still small: a handful of invited researchers, not a SaaS product. No tiers, no billing, no onboarding flows.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Cloud Run Service                  │
│                                                      │
│  FastAPI (Python 3.13 + Rust PyO3 extension)         │
│  ├── /api/*          REST + WebSocket endpoints      │
│  ├── /               Static React frontend           │
│  └── Firebase Admin   Token verification             │
│                                                      │
│  DuckDB (ephemeral)  Per-request analytical queries  │
└──────────────┬───────────────────┬───────────────────┘
               │                   │
     ┌─────────▼─────────┐  ┌─────▼──────┐
     │  Cloud Storage     │  │  Firebase   │
     │  (GCS Bucket)      │  │  Auth       │
     │                    │  │             │
     │  /users/{uid}/     │  │  Google     │
     │    games/          │  │  sign-in    │
     │    *.duckdb        │  │  Email/pw   │
     │    *.json          │  └─────────────┘
     └────────────────────┘
               │
     ┌─────────▼─────────┐
     │  Secret Manager    │
     │  - OpenAI key      │
     │  - Firebase SA key │
     └────────────────────┘
```

### Why This Shape

**Cloud Run (single service)** — same reasoning as v1. WebSocket support, scale to zero, simple. Still the right choice.

**Firebase Auth** — zero-effort auth. Google sign-in for researchers, no user database to manage. Firebase Admin SDK verifies ID tokens server-side. Free for our scale. No need for IAP or custom auth.

**Cloud Storage for DuckDB files** — this is the key decision, explained below.

---

## The DuckDB Question

The existing codebase stores all simulation data in DuckDB: events, transactions, metrics, policy snapshots, checkpoints. The schema is mature (Pydantic models → auto-generated DDL). The paper generator reads directly from DuckDB. The experiment runner writes to DuckDB.

### Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Cloud SQL (Postgres)** | Real database, concurrent access, managed | $7-30/month minimum even idle, schema migration needed, overkill |
| **Firestore** | Serverless, scales to zero, Firebase-native | Document DB — terrible fit for analytical queries, would rewrite persistence layer |
| **DuckDB on Cloud Storage** | Reuses existing schema/code, zero idle cost, analytical strength | Single-writer, requires download/upload cycle, not for concurrent writes |
| **DuckDB on persistent disk** | Fast local I/O | Cloud Run has no persistent disks (ephemeral filesystem only) |
| **SQLite on Cloud Storage** | Similar to DuckDB approach | Lose DuckDB's analytical features that the codebase depends on |

### Decision: DuckDB files on Cloud Storage

Each user gets a DuckDB file per game: `gs://simcash-data/users/{uid}/games/{game_id}.duckdb`

**How it works:**
1. User creates a game → backend creates a fresh DuckDB file in `/tmp/`, writes initial state
2. During gameplay → all reads/writes go to the local `/tmp/` copy (fast)
3. Game completes a day or user explicitly saves → upload DuckDB file to GCS
4. User returns later → download DuckDB file from GCS to `/tmp/`, resume
5. Periodic sync during long-running games (after each day completes)

**Why this works for us:**
- Single writer per game (one user, one Cloud Run instance via session affinity)
- DuckDB files are small: a 25-day, 5-agent game produces ~2-5 MB
- GCS is $0.02/GB/month — effectively free for our volume
- We reuse the entire existing DuckDB persistence layer unchanged
- No schema migration to a different database
- Analytical queries (paper generator, cross-game comparison) can download files and query locally

**Limitations we accept:**
- No cross-game queries in the cloud (each game is a separate file). Fine — researchers can download their data.
- Slight latency on game resume (~100-500ms to download from GCS). Fine — happens once.
- If Cloud Run instance crashes mid-day, unsaved progress is lost. Acceptable — we sync after each day.

### Game Metadata Index

We need a lightweight index to list a user's games without downloading every DuckDB file. Two options:

**Option A: JSON manifest per user** — `gs://simcash-data/users/{uid}/games/index.json`
```json
{
  "games": [
    {
      "game_id": "abc123",
      "scenario": "2bank_12tick",
      "created": "2026-02-17T15:00:00Z",
      "days_completed": 5,
      "status": "completed",
      "total_cost": 199200
    }
  ]
}
```
Updated after each day. Cheap, simple, no database.

**Option B: Firestore collection** — `users/{uid}/games/{game_id}` documents with metadata.

**Recommendation: Option A (JSON manifest)**. We're already using GCS. Adding Firestore just for an index is unnecessary complexity for <50 users. If we later need cross-user queries (leaderboards, aggregate stats), we can migrate to Firestore then.

---

## Firebase Auth Integration

### Setup

1. Create Firebase project (or attach to existing GCP project)
2. Enable Google sign-in provider (and optionally email/password)
3. No Firebase Hosting needed — we serve from Cloud Run

### Frontend

```typescript
// firebase.ts
import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider, signInWithPopup } from 'firebase/auth';

const app = initializeApp({
  apiKey: "...",           // Public — safe to embed
  authDomain: "simcash-xxx.firebaseapp.com",
  projectId: "simcash-xxx",
});

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();

// Sign in
export const signIn = () => signInWithPopup(auth, googleProvider);

// Get ID token for API calls
export const getIdToken = () => auth.currentUser?.getIdToken();
```

Every API call includes `Authorization: Bearer <idToken>`.

### Backend

```python
# auth.py
from firebase_admin import auth, initialize_app, credentials
from fastapi import Depends, HTTPException, Request

# Initialize once at startup
initialize_app(credentials.ApplicationDefault())

async def get_current_user(request: Request) -> str:
    """Extract and verify Firebase ID token. Returns uid."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, "Missing auth token")
    token = auth_header.split(" ", 1)[1]
    try:
        decoded = auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(401, "Invalid auth token")
```

Use as dependency: `uid: str = Depends(get_current_user)`.

### Access Control

No roles or permissions. If you can authenticate, you can use the platform. Games are private to each user (enforced by `uid` path prefix in GCS).

Optional: maintain an allowlist of permitted email addresses in a config file or environment variable. Reject auth for emails not on the list. Simple and sufficient for invited researchers.

---

## Storage Layer Implementation

```python
# storage.py
from google.cloud import storage
import tempfile
import shutil
from pathlib import Path

class GameStorage:
    def __init__(self, bucket_name: str = "simcash-data"):
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self._local_cache: dict[str, Path] = {}  # game_id → local path

    def _gcs_path(self, uid: str, game_id: str) -> str:
        return f"users/{uid}/games/{game_id}.duckdb"

    def _index_path(self, uid: str) -> str:
        return f"users/{uid}/games/index.json"

    def create_game(self, uid: str, game_id: str) -> Path:
        """Create a new local DuckDB file for a game."""
        local = Path(tempfile.mkdtemp()) / f"{game_id}.duckdb"
        self._local_cache[game_id] = local
        return local

    def save_game(self, uid: str, game_id: str):
        """Upload current DuckDB to GCS."""
        local = self._local_cache.get(game_id)
        if not local or not local.exists():
            raise ValueError(f"No local file for game {game_id}")
        blob = self.bucket.blob(self._gcs_path(uid, game_id))
        blob.upload_from_filename(str(local))

    def load_game(self, uid: str, game_id: str) -> Path:
        """Download DuckDB from GCS to local temp."""
        if game_id in self._local_cache:
            return self._local_cache[game_id]
        local = Path(tempfile.mkdtemp()) / f"{game_id}.duckdb"
        blob = self.bucket.blob(self._gcs_path(uid, game_id))
        blob.download_to_filename(str(local))
        self._local_cache[game_id] = local
        return local

    def list_games(self, uid: str) -> list[dict]:
        """Read the JSON index for a user."""
        blob = self.bucket.blob(self._index_path(uid))
        if not blob.exists():
            return []
        import json
        return json.loads(blob.download_as_text()).get("games", [])

    def update_index(self, uid: str, game_meta: dict):
        """Add/update a game entry in the user's index."""
        games = self.list_games(uid)
        games = [g for g in games if g["game_id"] != game_meta["game_id"]]
        games.append(game_meta)
        import json
        blob = self.bucket.blob(self._index_path(uid))
        blob.upload_from_string(json.dumps({"games": games}, indent=2))
```

### Cleanup

Cloud Run's `/tmp` is a tmpfs (memory-backed). Each instance has its allocated memory. With 1 GiB memory and DuckDB files at ~2-5 MB each, we can hold ~100 games in `/tmp` before memory pressure. For our scale this is fine. Add an LRU eviction policy if needed.

---

## Updated Docker Build

```dockerfile
# Stage 1: Rust extension (unchanged from v1)
FROM python:3.13-slim AS rust-builder
RUN apt-get update && apt-get install -y curl build-essential pkg-config
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install maturin[patchelf]
WORKDIR /build
COPY simulator/ simulator/
COPY api/ api/
COPY Cargo.toml Cargo.lock ./
RUN cd api && maturin build --release --out /wheels

# Stage 2: Frontend (unchanged)
FROM node:22-slim AS frontend-builder
WORKDIR /app
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ .
RUN npm run build

# Stage 3: Runtime
FROM python:3.13-slim
WORKDIR /app

COPY --from=rust-builder /wheels/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl

COPY web/backend/ web/backend/
RUN pip install \
    fastapi uvicorn[standard] pydantic-ai pyyaml httpx \
    firebase-admin google-cloud-storage

COPY --from=frontend-builder /app/dist/ web/frontend/dist/
COPY docs/papers/simcash-paper/paper_generator/configs/ configs/

ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--app-dir", "web/backend"]
```

Only two new pip packages: `firebase-admin` and `google-cloud-storage`.

---

## Deployment

```bash
# Project setup
gcloud config set project simcash-prod
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

# GCS bucket
gsutil mb -l europe-north1 gs://simcash-data

# Secrets
echo -n "$OPENAI_KEY" | gcloud secrets create openai-api-key --data-file=-

# Artifact Registry
gcloud artifacts repositories create simcash \
  --repository-format=docker --location=europe-north1

# Build
gcloud builds submit \
  --tag europe-north1-docker.pkg.dev/simcash-prod/simcash/web:latest \
  --timeout=600

# Deploy
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/simcash-prod/simcash/web:latest \
  --region europe-north1 \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest" \
  --set-env-vars="\
    SIMCASH_MOCK_DEFAULT=true,\
    SIMCASH_GCS_BUCKET=simcash-data,\
    FIREBASE_PROJECT_ID=simcash-prod" \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 3 \
  --session-affinity
```

**Note on `--allow-unauthenticated`**: This allows anyone to reach the Cloud Run URL (needed for the frontend to load). Auth is enforced at the application level via Firebase tokens. The only unauthenticated endpoint is `/api/health` and the static frontend.

---

## Cost Estimate

For ~10-20 invited researchers, light usage:

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run compute | ~$0-5 (light usage, scale to zero) |
| Cloud Storage | ~$0.01 (a few hundred MB of DuckDB files) |
| Firebase Auth | $0 (free tier: 10k verifications/month) |
| Secret Manager | $0 (free tier) |
| Artifact Registry | ~$0.10 |
| Cloud Build | $0 (free tier) |
| OpenAI API | $5-100 (depends on real LLM usage) |
| **Total** | **~$5-100/month** (dominated by OpenAI) |

---

## Implementation Phases

### Phase 1: Auth + Storage Layer (3-4 hours)
- Add `firebase-admin` + `google-cloud-storage` to backend deps
- Implement `auth.py` (token verification dependency)
- Implement `storage.py` (GCS-backed game persistence)
- Add `uid` parameter to all game CRUD operations
- Wire auth into existing endpoints
- Frontend: add Firebase SDK, login page, token in API calls
- Tests: mock Firebase tokens, mock GCS

### Phase 2: Dockerize + Deploy (2-3 hours)
- Write Dockerfile (multi-stage, as above)
- Static frontend serving from FastAPI
- Relative WebSocket URLs
- Environment-variable config
- `.dockerignore`
- Local Docker test
- Deploy to Cloud Run

### Phase 3: DuckDB Persistence (2-3 hours)
- Integrate existing DuckDB schema (`DatabaseManager`, `EventWriter`) into web game flow
- Write simulation results to DuckDB after each day
- Upload to GCS after each day
- Game resume: download from GCS, read state, continue
- Game listing page in frontend

### Phase 4: Polish (1-2 hours)
- Login/logout UI
- "My Games" dashboard
- Game sharing (optional: generate read-only link with signed GCS URL)
- Rate limiting on LLM endpoints
- Billing alerts ($10, $50, $100)

---

## Migration from v1

The current in-memory `game_manager: dict[str, Game]` stays as a hot cache. The storage layer wraps around it:

1. `POST /api/games` → create game in memory + create DuckDB file + upload to GCS
2. `POST /api/games/{id}/step` → run day in memory + write results to DuckDB + upload to GCS
3. `GET /api/games/{id}` → check memory cache first, then load from GCS if missing
4. `GET /api/games` → read user's JSON index from GCS

The `Game` class doesn't change. We add a persistence wrapper that syncs to GCS at checkpoints.

---

## Open Questions

1. **Firebase project**: Create new or attach to existing GCP project? Recommend same project for simplicity.
2. **Allowlist enforcement**: Hardcoded list of emails in env var, or a GCS config file?
3. **Game sharing**: Do researchers need to share results with each other? If so, add read-only signed URLs.
4. **Data export**: Should users be able to download their DuckDB files directly? Easy to add — signed GCS download URL.
5. **Custom domain**: `simcash.app`, `simcash.research`, or subdomain of existing?
6. **min-instances=1**: Pay ~$20-40/month to avoid cold starts + state loss, or accept ephemeral? For invited researchers who'll use it intermittently, `min-instances=0` with GCS persistence is fine — games survive scale-to-zero now.

---

## What We Decided NOT to Do

- **Firestore for game data** — wrong tool for analytical workloads. DuckDB is purpose-built for this.
- **Cloud SQL** — persistent relational DB is overkill and has idle costs. We have <50 users.
- **Firebase Hosting** — adds split-deploy complexity. Single Cloud Run service is simpler.
- **User roles/tiers** — not a product. Everyone gets the same access.
- **Managed Redis for caching** — in-memory dict on Cloud Run is sufficient at our scale.
- **Cloud Tasks for async simulation** — simulations complete in <1s. Only LLM calls are slow, and those stream via WebSocket already.
