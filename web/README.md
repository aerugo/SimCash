# SimCash Web Platform

Interactive web sandbox for SimCash — a multi-day policy optimization game where AI agents learn to play a payment coordination game.

## Architecture

```
web/
├── backend/          FastAPI (Python 3.13 + Rust PyO3 extension)
│   └── app/
│       ├── main.py           API routes + WebSocket
│       ├── game.py           Multi-day game engine
│       ├── auth.py           Firebase Auth (token verification)
│       ├── storage.py        GCS-backed DuckDB persistence
│       ├── config.py         Environment config
│       ├── simulation.py     Single-run simulation wrapper
│       ├── streaming_optimizer.py  LLM policy optimization
│       └── bootstrap_eval.py Thread-parallel bootstrap evaluation
└── frontend/         React 19 + TypeScript + Vite + Tailwind v4
    └── src/
        ├── App.tsx           Root (auth gate + tab navigation)
        ├── firebase.ts       Firebase config + auth helpers
        ├── views/            Game, Home, Docs views
        └── hooks/            WebSocket, auth hooks
```

## Local Development

### Prerequisites

- Python 3.13+ with `uv`
- Rust toolchain (for building the PyO3 extension)
- Node.js 22+
- The Rust extension must be built first (see root README)

### Build Rust extension

```bash
cd api
PATH="/path/to/cargo:$HOME/Library/Python/3.9/bin:$PATH" uvx maturin develop --release --uv
```

### Start backend

```bash
cd web/backend
# Use .venv/bin/python directly (uv run clobbers the maturin .so)
../../api/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8642 --reload
```

### Start frontend

```bash
cd web/frontend
npm install
npm run dev    # Vite dev server on :5173, proxies /api → :8642
```

### Environment variables (local dev)

Create `web/backend/.env` or export:

```bash
SIMCASH_AUTH_DISABLED=true     # Skip Firebase auth (use fixed dev uid)
SIMCASH_STORAGE=local          # Store DuckDB files locally instead of GCS
SIMCASH_MOCK_DEFAULT=true      # Default to mock LLM (no OpenAI calls)
SIMCASH_CONFIGS_DIR=../../docs/papers/simcash-paper/paper_generator/configs/
```

For real LLM mode, also set `OPENAI_API_KEY` (or symlink from repo root `.env`).

## Production Deployment (Cloud Run)

### Overview

Single Cloud Run service serving both API and static frontend.

- **Auth**: Firebase Auth (Google sign-in)
- **Storage**: DuckDB files on Cloud Storage (`gs://simcash-data/users/{uid}/games/`)
- **Secrets**: OpenAI API key via Secret Manager
- **Region**: `europe-north1`

### Build + Deploy

```bash
# Build Docker image (multi-stage: Rust → frontend → slim runtime)
gcloud builds submit \
  --tag europe-north1-docker.pkg.dev/PROJECT/simcash/web:latest \
  --timeout=600

# Deploy
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/PROJECT/simcash/web:latest \
  --region europe-north1 \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest" \
  --set-env-vars="\
    SIMCASH_MOCK_DEFAULT=true,\
    SIMCASH_GCS_BUCKET=simcash-data,\
    SIMCASH_STORAGE=gcs,\
    FIREBASE_PROJECT_ID=simcash-prod" \
  --memory 1Gi --cpu 1 --timeout 300 \
  --concurrency 20 --session-affinity \
  --min-instances 0 --max-instances 3
```

### Required GCP Setup

```bash
# Enable APIs
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com storage.googleapis.com

# Create storage bucket
gsutil mb -l europe-north1 gs://simcash-data

# Store OpenAI key
echo -n "$OPENAI_KEY" | gcloud secrets create openai-api-key --data-file=-

# Create Artifact Registry repo
gcloud artifacts repositories create simcash \
  --repository-format=docker --location=europe-north1
```

### Firebase Setup

1. Create Firebase project (or link to existing GCP project)
2. Enable **Google** sign-in provider in Firebase Console → Authentication → Sign-in method
3. Add Cloud Run URL to authorized domains
4. Frontend Firebase config (public, safe to commit):
   ```typescript
   // web/frontend/src/firebase.ts
   const config = {
     apiKey: "...",
     authDomain: "PROJECT.firebaseapp.com",
     projectId: "PROJECT",
   };
   ```

### Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | For real LLM | — | OpenAI API key (use Secret Manager in prod) |
| `SIMCASH_MOCK_DEFAULT` | No | `true` | Default to mock LLM reasoning |
| `SIMCASH_GCS_BUCKET` | In prod | — | GCS bucket name for game storage |
| `SIMCASH_STORAGE` | No | `local` | `local` or `gcs` |
| `SIMCASH_AUTH_DISABLED` | No | `false` | Skip auth (local dev only!) |
| `SIMCASH_CONFIGS_DIR` | No | `configs/` | Path to scenario YAML configs |
| `SIMCASH_ALLOWED_EMAILS` | No | — | Comma-separated allowlist (empty = allow all) |
| `FIREBASE_PROJECT_ID` | In prod | — | Firebase/GCP project ID |
| `PORT` | No | `8080` | Server port (Cloud Run sets this) |

### Cost

~$5-100/month for light research use (dominated by OpenAI API calls). Cloud Run scales to zero when idle.

## Testing

```bash
# Backend tests (82 tests)
cd api && .venv/bin/python -m pytest ../web/backend/tests/ -v --tb=short \
  --ignore=../web/backend/tests/test_real_llm.py

# Frontend type check
cd web/frontend && npx tsc -b

# Frontend build
cd web/frontend && npm run build
```

## Key Design Decisions

- **DuckDB on GCS** — each game is a single `.duckdb` file, reuses existing persistence schema
- **No Firestore/Cloud SQL** — DuckDB is the right tool for analytical simulation data
- **Single Cloud Run service** — FastAPI serves both API and static frontend, no CORS needed
- **GIL-release FFI** — Rust simulation runs release the Python GIL for thread-parallel execution
- **Session affinity** — WebSocket connections stay pinned to the same instance

See `docs/reports/gcp-deployment-plan-v2.md` for full architectural rationale.
