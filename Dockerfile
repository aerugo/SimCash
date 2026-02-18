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

# Ensure all Python subpackages are available (maturin wheel may not include all)
COPY api/payment_simulator/ /tmp/ps_src/
RUN cp -rn /tmp/ps_src/* /usr/local/lib/python3.13/site-packages/payment_simulator/ && rm -rf /tmp/ps_src

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
