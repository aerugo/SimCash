# ============================================================
# Stage 1: Build Rust extension (payment_simulator wheel)
# ============================================================
FROM python:3.13-slim AS rust-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config && \
    rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir "maturin[patchelf]"

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY simulator/ simulator/
COPY api/ api/

RUN cd api && maturin build --release --out /wheels

# ============================================================
# Stage 2: Build React frontend
# ============================================================
FROM node:22-slim AS frontend-builder

WORKDIR /app
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci

COPY web/frontend/ ./

# Firebase config via build args
# These are client-side browser keys (not secret) — safe to embed in JS bundles
ARG VITE_FIREBASE_API_KEY="AIzaSyAT_IULl1kAW804XTIhoLhASDXIlv21Kas"
ARG VITE_FIREBASE_APP_ID="1:997004209370:web:bc69475748ca89ceb289e3"
ARG VITE_FIREBASE_MEASUREMENT_ID="G-FQ44MJ91Q3"
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
ENV VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID
ENV VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID

RUN npm run build

# ============================================================
# Stage 3: Runtime
# ============================================================
FROM python:3.13-slim AS runtime

WORKDIR /app

# Install the Rust wheel
COPY --from=rust-builder /wheels/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Install Python dependencies
RUN pip install --no-cache-dir \
    "fastapi" \
    "uvicorn[standard]" \
    "pydantic-ai" \
    "pyyaml" \
    "httpx" \
    "firebase-admin" \
    "google-cloud-storage" \
    "duckdb"

# Copy Python subpackages not included in the maturin wheel
COPY api/payment_simulator/ /tmp/ps_src/
RUN SITE=$(python -c "import payment_simulator, os; print(os.path.dirname(payment_simulator.__file__))") && \
    cp -r /tmp/ps_src/* "$SITE/" && rm -rf /tmp/ps_src && \
    python -c "from payment_simulator.experiments.runner.llm_client import ExperimentLLMClient; print('OK: experiments')" && \
    python -c "from payment_simulator.ai_cash_mgmt.optimization.policy_optimizer import PolicyOptimizer; print('OK: ai_cash_mgmt')"

# Copy backend
COPY web/backend/ web/backend/

# Copy built frontend
COPY --from=frontend-builder /app/dist/ web/frontend/dist/

# Copy scenario configs
COPY docs/papers/simcash-paper/paper_generator/configs/ configs/

# Copy example configs and policies for the libraries
COPY examples/configs/ examples/configs/
COPY simulator/policies/ simulator/policies/

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--app-dir", "web/backend"]
