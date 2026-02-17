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

## Concurrency: Multiple Simultaneous Users

### Current Architecture

The app stores all game state in a Python process-global dict (`game_manager: dict[str, Game] = {}`). There is no database, no session persistence, no locking. This has several implications:

**Memory per game**: A 25-day game with 2 agents is ~150 KB of state (events, costs, balance histories, reasoning). A 50-day game with 5 agents is ~1-2 MB. With 1 GiB container memory, we can comfortably hold **~200-500 concurrent games** before memory becomes a concern.

**CPU contention (the real issue)**: The Rust simulation calls go through PyO3 and **hold the Python GIL**. This means:
- While one user's simulation is running, all other users' HTTP requests and WebSocket messages are blocked
- FastAPI's async framework can't help — the GIL serializes all Rust calls
- A single bootstrap evaluation (50 samples × 2 policies = 100 sims) takes ~71ms for 2-bank/12-tick scenarios — tolerable
- But LLM optimization calls take 10-60 seconds. During that time, the GIL is NOT held (pydantic-ai is async/HTTP), so other users can still interact

**WebSocket connections**: Each active game maintains a WebSocket. Cloud Run supports this but each connection holds an HTTP/2 stream. With `--concurrency 20`, one instance serves up to 20 simultaneous WebSocket connections.

### Scaling Behavior

Cloud Run autoscales based on request concurrency. Here's what happens:

| Concurrent Users | Instances | Behavior |
|-----------------|-----------|----------|
| 1-5 | 1 | Fine. Simulations are fast enough (~1-3ms each). GIL contention negligible. |
| 5-20 | 1-2 | Occasional ~100ms stalls during bootstrap eval. Acceptable. |
| 20-50 | 2-5 | Multiple instances needed. **Session affinity** keeps WebSocket connections pinned. |
| 50+ | 5+ | Need to consider costs. Each instance is 1 vCPU + 1 GiB. |

**Critical issue: scale-to-zero loses all game state.** If the last user disconnects and the instance scales down, all games are lost. For a research demo this is acceptable (games are ephemeral experiments), but users should be warned.

### Mitigations

1. **Short-term (deploy as-is)**: The architecture works fine for 1-20 concurrent users. Bootstrap evals are fast, GIL contention is brief, and LLM calls don't hold the GIL.

2. **Medium-term (if popular)**:
   - Add `min-instances=1` to prevent scale-to-zero (costs ~$20-40/month)
   - Move Rust calls to `asyncio.to_thread()` to release the event loop during GIL-held work
   - Consider `--cpu 2` for heavier scenarios

3. **Long-term (if many users)**:
   - Add Firestore/Redis for game state persistence
   - Use Cloud Tasks to queue simulation work
   - Release GIL in Rust via `py.allow_threads()` in the PyO3 bindings (would require core simulator changes — violates the "don't touch outside web/" rule)

## Compute Analysis: Can Cloud Run Handle It?

### Benchmark Results (Apple M1, single-core)

| Scenario | Per Simulation | Bootstrap-50 (100 sims) |
|----------|---------------|------------------------|
| 2 banks, 12 ticks | 0.71ms | 71ms |
| 5 banks, 20 ticks | 3.42ms | 342ms |
| 5 banks, 20 ticks, LSM ON | 3.49ms | 349ms |

### Cloud Run vCPU Performance

Cloud Run's 1 vCPU is a **shared-tenancy x86 core** (AMD EPYC or Intel Xeon, varies). Typical single-thread performance is roughly **2-4× slower** than an Apple M1 core for compiled Rust workloads. This is because:
- Shared tenancy means CPU is not dedicated (can be throttled)
- x86 vs ARM ISA differences
- Cloud Run allocates CPU only during request processing (by default)

**Adjusted estimates for Cloud Run 1 vCPU:**

| Scenario | Per Simulation | Bootstrap-50 | Acceptable? |
|----------|---------------|-------------|-------------|
| 2 banks, 12 ticks | ~2ms | ~200ms | ✅ Very fast |
| 5 banks, 20 ticks | ~10ms | ~1s | ✅ Fine |
| 5 banks, 20 ticks, LSM | ~10ms | ~1s | ✅ Fine |
| 10 banks, 20 ticks (projected) | ~30ms | ~3s | ✅ Acceptable |
| 10 banks, 20 ticks, LSM (projected) | ~50ms | ~5s | ⚠️ Noticeable |

### The Real Bottleneck: LLM Calls, Not Simulation

A single optimization step involves:
1. **Simulation**: ~200ms for bootstrap-50 with 2 banks ✅
2. **LLM call**: 10-60 seconds for GPT-5.2 with reasoning ⚠️
3. **Bootstrap evaluation**: ~200ms ✅

The LLM call is **50-300× slower** than all simulation work combined. Cloud Run's CPU is irrelevant during LLM calls (it's waiting on network I/O). The 300-second request timeout is the real constraint — a 25-day game with 2 agents and real LLM could take:
- 25 days × 2 agents × ~30s per LLM call = ~25 minutes total
- Well within the 3600s max timeout, but needs the WebSocket connection to stay alive

### LSM Specifically

LSM (bilateral offsetting + cycle detection) adds negligible overhead in our benchmarks. The cycle detection algorithm is O(V+E) per tick and with 5 agents the graph is tiny. Even projected to 10+ agents with dense payment networks, LSM won't be the bottleneck. The Rust engine was designed for this — it handles 200+ agents at 1000+ ticks/second.

### Recommendation

**1 vCPU + 1 GiB is sufficient** for the expected use case (research demo, 1-20 concurrent users, 2-5 bank scenarios). The simulation engine is absurdly fast relative to the LLM bottleneck.

If we ever need to support heavy scenarios (10+ banks, 50-tick days, full LSM) with many concurrent users, bump to `--cpu 2 --memory 2Gi`. But that's an optimization we can defer.

## Open Questions

1. **Custom domain?** Could use `simcash.app` or a subdomain of an existing domain.
2. **Rate limiting strategy?** Cloud Run doesn't have built-in rate limiting — could use Cloud Armor ($7/month) or application-level limiting.
3. **Monitoring?** Cloud Run has built-in metrics. Worth setting up billing alerts at $10, $50, $100.
4. **Multi-region?** Not needed initially. `europe-north1` is fine for a research tool.
5. **Persistent storage?** Current in-memory game state is lost on scale-to-zero. Acceptable for a demo — games are ephemeral. Could add Firestore later if persistence matters.
