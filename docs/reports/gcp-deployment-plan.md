# SimCash GCP Deployment Plan

**Date**: 2026-02-17
**Author**: Nash
**Status**: Draft

## Overview

Deploy the SimCash web sandbox (FastAPI backend + React frontend) to Google Cloud so it's publicly accessible. The main challenge: the backend depends on a Rust native extension (`payment_simulator_core_rs`) compiled via PyO3/maturin. This rules out simple source-based deploys — we need a Docker container with a multi-stage build.

## Architecture Decision: Cloud Run (Single Service)

**Recommendation: One Cloud Run service serving both API and static frontend.**

Why Cloud Run:
- Fully managed, scales to zero (no cost when idle)
- WebSocket support (needed for streaming LLM reasoning)
- Free tier: 2M requests/month, 360k vCPU-seconds, 180k GiB-seconds
- No cluster management (vs GKE)
- Custom Docker images supported

Why single service (not separate frontend/backend):
- Simpler — no CORS config needed, no separate CDN setup
- FastAPI serves the built React static files at `/`
- API routes at `/api/*` and WebSocket at `/api/games/{id}/ws`
- Frontend is only ~700KB — trivial to serve from the same container
- Can split later if traffic warrants it

### Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Cloud Run (chosen)** | Scales to zero, simple, WebSocket support | Cold starts (~5s with Rust extension) |
| Cloud Run + Cloud CDN | Better static asset performance | Extra complexity, overkill for research tool |
| GKE | Full control, persistent containers | Expensive baseline, operational overhead |
| App Engine Flex | Managed containers | More expensive than Cloud Run, slower deploys |
| Compute Engine VM | Full control, always on | Manual ops, pay even when idle |
| Firebase Hosting + Cloud Run | CDN for frontend, Run for API | Split deploy, CORS config needed |

## Docker Build Strategy

Multi-stage build to compile the Rust extension and produce a slim final image:

```dockerfile
# Stage 1: Build Rust extension
FROM python:3.13-slim AS rust-builder

RUN apt-get update && apt-get install -y curl build-essential pkg-config
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install maturin
RUN pip install maturin[patchelf]

# Copy Rust source + Python project
WORKDIR /build
COPY simulator/ simulator/
COPY api/ api/
COPY Cargo.toml Cargo.lock ./

# Build the wheel
RUN cd api && maturin build --release --out /wheels

# Stage 2: Build frontend
FROM node:22-slim AS frontend-builder

WORKDIR /app
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend/ .
RUN npm run build

# Stage 3: Final runtime image
FROM python:3.13-slim

WORKDIR /app

# Install the built wheel
COPY --from=rust-builder /wheels/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl

# Install web backend deps
COPY web/backend/ web/backend/
RUN pip install fastapi uvicorn[standard] pydantic-ai pyyaml httpx

# Copy built frontend
COPY --from=frontend-builder /app/dist/ web/frontend/dist/

# Copy configs/scenarios needed at runtime
COPY docs/papers/simcash-paper/paper_generator/configs/ configs/

# Expose port
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--app-dir", "web/backend"]
```

### Key Build Considerations

1. **Rust compilation takes ~3-5 minutes** in Docker. Use BuildKit cache mounts for `~/.cargo/registry` and `target/` to speed up rebuilds.
2. **Final image ~200-300MB** (Python 3.13-slim + compiled extension + frontend assets). No Rust toolchain in final image.
3. **Platform**: Build for `linux/amd64` (Cloud Run default). Can add `linux/arm64` later if needed.

## Backend Changes Required

### 1. Serve Static Frontend from FastAPI

Add to `web/backend/app/main.py`:

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# After all API routes are registered:
frontend_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
```

### 2. Environment-Based Configuration

```python
import os

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
MOCK_BY_DEFAULT = os.environ.get("SIMCASH_MOCK_DEFAULT", "true").lower() == "true"
```

- Default to mock mode in production (no API key burn for casual visitors)
- Real LLM mode opt-in via UI toggle (requires valid API key)

### 3. Config Path Resolution

The scenario configs currently reference relative paths. Need to make these configurable:

```python
CONFIGS_DIR = os.environ.get("SIMCASH_CONFIGS_DIR", "configs/")
```

## Secrets Management

**Use Google Secret Manager** for the OpenAI API key:

```bash
# Create secret
gcloud secrets create openai-api-key --data-file=-
# Enter key, Ctrl+D

# Grant Cloud Run access
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Reference in Cloud Run
gcloud run deploy simcash \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest"
```

Cost: Essentially free (6 free secret versions, 10k free access ops/month).

## Deployment Commands

```bash
# One-time setup
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Create Artifact Registry repo
gcloud artifacts repositories create simcash \
  --repository-format=docker \
  --location=europe-north1

# Build and push
gcloud builds submit \
  --tag europe-north1-docker.pkg.dev/YOUR_PROJECT/simcash/web:latest \
  --timeout=600

# Deploy
gcloud run deploy simcash \
  --image europe-north1-docker.pkg.dev/YOUR_PROJECT/simcash/web:latest \
  --region europe-north1 \
  --allow-unauthenticated \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest" \
  --set-env-vars="SIMCASH_MOCK_DEFAULT=true" \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 20 \
  --min-instances 0 \
  --max-instances 3 \
  --session-affinity
```

### Key Settings Explained

| Setting | Value | Reason |
|---------|-------|--------|
| `--region` | `europe-north1` (Finland) | Low latency from Sweden, low carbon |
| `--memory` | 1Gi | Rust engine + Python + LLM responses in memory |
| `--cpu` | 1 | Sufficient for simulation workloads |
| `--timeout` | 300s | LLM optimization can take 30-60s per agent |
| `--concurrency` | 20 | Multiple users, but each game uses CPU |
| `--session-affinity` | enabled | WebSocket connections stay on same instance |
| `--min-instances` | 0 | Scale to zero when idle (cost savings) |
| `--max-instances` | 3 | Cap costs for a research demo |

## WebSocket Considerations

Cloud Run supports WebSocket but with caveats:
- **Timeout**: WebSocket connections are subject to the request timeout (300s default, max 3600s). Long-running games may need reconnection logic — which we already have (`useGameWebSocket` with auto-reconnect).
- **Session affinity**: Enabled to keep WS connections on the same instance.
- **Idle timeout**: Connections idle for >10 minutes may be dropped. The frontend should send periodic pings.

### Required Frontend Change

Update the WebSocket URL to be relative (not `localhost`):

```typescript
// Current:
const ws = new WebSocket(`ws://localhost:8642/api/games/${gameId}/ws`);

// Change to:
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${protocol}//${window.location.host}/api/games/${gameId}/ws`);
```

## Cost Estimate

For a research demo with light usage (~100 visitors/month, ~20 game sessions/month):

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run compute | **~$0** (within free tier for light usage) |
| Artifact Registry | ~$0.10 (storage for Docker image) |
| Secret Manager | **$0** (within free tier) |
| Cloud Build | **$0** (120 free build-minutes/day) |
| Egress | **$0** (1 GiB free/month) |
| OpenAI API (GPT-5.2) | **$5-50** (depends on real LLM usage) |
| **Total** | **~$5-50/month** (dominated by OpenAI) |

For heavier usage, Cloud Run costs scale linearly. At 1000 game sessions/month with real LLM, expect ~$200-500/month (mostly OpenAI).

## CI/CD Pipeline (Optional)

Set up Cloud Build trigger on the GitHub repo:

```yaml
# cloudbuild.yaml
steps:
  # Build Docker image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', '${_IMAGE}', '.']
  
  # Push to Artifact Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', '${_IMAGE}']
  
  # Deploy to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    args:
      - 'gcloud'
      - 'run'
      - 'deploy'
      - 'simcash'
      - '--image=${_IMAGE}'
      - '--region=europe-north1'
      - '--allow-unauthenticated'

substitutions:
  _IMAGE: 'europe-north1-docker.pkg.dev/${PROJECT_ID}/simcash/web:${COMMIT_SHA}'

images:
  - '${_IMAGE}'
```

This auto-deploys on push to `main` (or a deploy branch).

## Implementation Steps

### Phase 1: Dockerize (2-3 hours)
1. Write `Dockerfile` at repo root
2. Add static file serving to FastAPI
3. Make WebSocket URL relative in frontend
4. Make config paths environment-variable based
5. Add `.dockerignore` (exclude `target/`, `node_modules/`, `.git/`, `*.db`)
6. Test locally: `docker build -t simcash . && docker run -p 8080:8080 simcash`

### Phase 2: Deploy (1-2 hours)
1. Create GCP project (or use existing)
2. Enable APIs (Cloud Run, Artifact Registry, Secret Manager)
3. Store OpenAI key in Secret Manager
4. Build and push image via Cloud Build
5. Deploy to Cloud Run
6. Verify: hit the URL, create a game, run mock mode

### Phase 3: Polish (1-2 hours)
1. Custom domain (optional)
2. Add health check endpoint (`/api/health`)
3. Add request logging / Cloud Logging integration
4. Rate limiting on LLM endpoints (prevent API key abuse)
5. Add `cloudbuild.yaml` for CI/CD

## Security Notes

- **OpenAI API key**: Never in Docker image or env vars visible in console. Use Secret Manager.
- **Rate limiting**: Add per-IP rate limiting on `/api/games` (create) and LLM-using endpoints to prevent abuse.
- **Mock default**: Production defaults to mock mode. Users must explicitly enable real LLM.
- **No auth required for viewing**: The sandbox is a research demo. Consider adding optional auth if costs become a concern.
- **CORS**: Not needed with single-service setup (same origin).

## Open Questions

1. **Custom domain?** Could use `simcash.app` or a subdomain of an existing domain.
2. **Rate limiting strategy?** Cloud Run doesn't have built-in rate limiting — could use Cloud Armor ($7/month) or application-level limiting.
3. **Monitoring?** Cloud Run has built-in metrics. Worth setting up billing alerts at $10, $50, $100.
4. **Multi-region?** Not needed initially. `europe-north1` is fine for a research tool.
5. **Persistent storage?** Current in-memory game state is lost on scale-to-zero. Acceptable for a demo — games are ephemeral. Could add Firestore later if persistence matters.
