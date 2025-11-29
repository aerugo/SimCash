# REST API Reference

**Version**: 1.0
**Last Updated**: 2025-11-29

---

## Overview

The Payment Simulator provides a REST API for creating, running, and analyzing simulations programmatically. It supports both **live simulation control** and **querying persisted simulation data**.

---

## Documentation

| Document | Description |
|----------|-------------|
| [Endpoints](endpoints.md) | Complete endpoint reference with examples |
| [Output Strategies](output-strategies.md) | API OutputStrategy pattern for streaming |
| [State Provider](state-provider.md) | Unified data access for live and persisted sims |
| [Models](models.md) | Request/response Pydantic models |

---

## Quick Start

### Start the API Server

```bash
cd api
uvicorn payment_simulator.api.main:app --reload
```

### Basic Operations

```bash
# Create a simulation
curl -X POST http://localhost:8000/simulations \
  -H "Content-Type: application/json" \
  -d @scenario.json

# Advance by one tick
curl -X POST http://localhost:8000/simulations/{sim_id}/tick

# Get current state
curl http://localhost:8000/simulations/{sim_id}/state

# Get metrics
curl http://localhost:8000/simulations/{sim_id}/metrics

# Get costs breakdown
curl http://localhost:8000/simulations/{sim_id}/costs
```

---

## Architecture

```mermaid
flowchart TB
    subgraph FastAPI["FastAPI Application"]
        direction TB
        E1["/simulations<br/>Lifecycle management"]
        E2["/simulations/{id}/tick<br/>Execution control"]
        E3["/simulations/{id}/state<br/>State queries"]
        E4["/simulations/{id}/costs<br/>Cost breakdown"]
        E5["/simulations/{id}/metrics<br/>System metrics"]
        E6["/simulations/{id}/events<br/>Event queries"]
    end

    subgraph Factory["State Provider Factory"]
        SPF["StateProviderFactory"]
    end

    subgraph Providers["State Providers"]
        OSP["OrchestratorStateProvider<br/>(Live FFI)"]
        DSP["DatabaseStateProvider<br/>(Persisted)"]
    end

    FastAPI --> Factory
    Factory --> OSP
    Factory --> DSP

    style FastAPI fill:#e3f2fd
    style Factory fill:#fff3e0
    style Providers fill:#e8f5e9
```

---

## Key Concepts

### Live vs Persisted Simulations

The API seamlessly handles both simulation modes through the StateProvider pattern:

```mermaid
flowchart LR
    subgraph Live["Live Simulations"]
        Create["POST /simulations"] --> Memory["In-Memory State"]
        Memory --> FFI["FFI Calls"]
    end

    subgraph Persisted["Persisted Simulations"]
        Load["Load from DB"] --> Query["SQL Queries"]
    end

    FFI --> Response["Identical<br/>Response Format"]
    Query --> Response

    style Live fill:#e8f5e9
    style Persisted fill:#e3f2fd
```

| Mode | Storage | Access Method | Use Case |
|------|---------|---------------|----------|
| **Live** | In-memory | FFI to Rust | Interactive control |
| **Persisted** | DuckDB | SQL queries | Analysis, replay |

### Output Consistency

API responses match CLI verbose output through shared contracts:

```mermaid
flowchart TB
    subgraph Contracts["Shared Data Contracts"]
        Canon["Canonical Field Names<br/>(deadline_penalty, not penalty_cost)"]
        Proto["StateProvider Protocol"]
        Service["DataService Layer"]
    end

    subgraph Outputs["Consistent Output"]
        API["API Response"]
        CLI["CLI Verbose"]
    end

    Canon --> API
    Canon --> CLI
    Proto --> API
    Proto --> CLI
    Service --> API
    Service --> CLI

    style Contracts fill:#fff3e0
    style Outputs fill:#e8f5e9
```

### Output Strategies

For real-time streaming, use the **APIOutputStrategy** pattern:

| Strategy | Use Case | Delivery |
|----------|----------|----------|
| `JSONOutputStrategy` | Standard REST responses | Synchronous |
| `WebSocketOutputStrategy` | Real-time tick streaming | Async push |
| `NullOutputStrategy` | Batch processing (no output) | None |

---

## Endpoint Summary

### Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Factory as StateProviderFactory
    participant Provider as StateProvider
    participant Engine as Rust Engine / DB

    Client->>API: HTTP Request
    API->>Factory: Get provider for sim_id
    Factory->>Factory: Check live or persisted
    Factory-->>API: StateProvider instance
    API->>Provider: Query data
    Provider->>Engine: FFI call or SQL query
    Engine-->>Provider: Raw data
    Provider-->>API: Formatted response
    API-->>Client: JSON Response
```

### Simulation Lifecycle

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulations` | POST | Create new simulation |
| `/simulations` | GET | List all simulations |
| `/simulations/{id}` | DELETE | Delete simulation |

### Execution

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulations/{id}/tick` | POST | Advance tick(s) |
| `/simulations/{id}/state` | GET | Get current state |
| `/simulations/{id}/ticks/{tick}/state` | GET | Get historical state |

### Diagnostics

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulations/{id}/costs` | GET | Cost breakdown by agent |
| `/simulations/{id}/metrics` | GET | System metrics |
| `/simulations/{id}/events` | GET | Query events |
| `/simulations/{id}/agents` | GET | Agent summaries |

### Checkpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/simulations/{id}/checkpoints` | POST | Save checkpoint |
| `/simulations/{id}/checkpoints` | GET | List checkpoints |
| `/simulations/{id}/checkpoints/{cp_id}/load` | POST | Load checkpoint |

---

## Response Format

All responses follow consistent JSON structure:

```mermaid
flowchart LR
    subgraph Success["Success Response (2xx)"]
        S1["simulation_id"]
        S2["tick"]
        S3["day"]
        S4["data: {...}"]
    end

    subgraph Error["Error Response (4xx/5xx)"]
        E1["detail: message"]
    end
```

**Success Response:**

```json
{
  "simulation_id": "sim-abc123",
  "tick": 50,
  "day": 0,
  "data": { ... }
}
```

**Error Response:**

```json
{
  "detail": "Simulation not found: sim-invalid"
}
```

---

## Authentication

Currently no authentication required (local development mode).

---

## Rate Limiting

No rate limiting in development mode.

---

## Related Documents

- [Endpoints](endpoints.md) - Complete endpoint reference
- [Output Strategies](output-strategies.md) - Streaming patterns
- [State Provider](state-provider.md) - Data access abstraction
- [CLI Reference](../cli/index.md) - Command-line interface
- [Scenario Configuration](../scenario/index.md) - YAML configuration format
- [Architecture](../architecture/index.md) - System architecture
- [Python API Layer](../architecture/03-python-api-layer.md) - Implementation details

---

*Next: [endpoints.md](endpoints.md) - Complete endpoint reference*
