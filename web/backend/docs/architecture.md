# Technical Architecture

*Rust, Python, and the FFI boundary*

## Stack Overview

```
┌─────────────────────────────────────────────┐
│  Web Frontend (React + TypeScript + Vite)   │
│  • Interactive UI, WebSocket streaming      │
└──────────────────┬──────────────────────────┘
                   │ HTTP/WS
┌──────────────────▼──────────────────────────┐
│  Web Backend (FastAPI)                      │
│  • Game orchestration, LLM calls            │
│  • PolicyOptimizer, bootstrap evaluation    │
└──────────────────┬──────────────────────────┘
                   │ PyO3 FFI
┌──────────────────▼──────────────────────────┐
│  Rust Simulation Engine                     │
│  • Tick loop, RTGS settlement, LSM          │
│  • Deterministic RNG, i64 arithmetic        │
└─────────────────────────────────────────────┘
```

## Design Principles

- **Rust owns state; Python orchestrates.** The simulation engine is a Rust library compiled as a Python extension via PyO3.
- **FFI boundary is minimal.** Only primitives cross the boundary. Policies enter as JSON strings, results come back as dicts.
- **Money is i64.** All monetary values are 64-bit integers representing cents. No floating-point arithmetic, no rounding errors.
- **Determinism is sacred.** Same seed = identical output, always. The RNG is xorshift64*, and seeds are persisted after each use.
- **Replay identity.** Running a simulation and replaying from checkpoint produce byte-identical output.

## Policy Pipeline

How an LLM decision becomes a simulated outcome:

1. LLM generates JSON policy (via PolicyOptimizer)
2. ConstraintValidator checks against scenario constraints
3. Extract `initial_liquidity_fraction` → set on agent config
4. Wrap policy tree → `{"type": "InlineJson", "json_string": "..."}`
5. `SimulationConfig.from_dict()` → `to_ffi_dict()`
6. `Orchestrator.new(ffi_config)` → run ticks

## LLM Configuration

The paper experiments used a large language model with reasoning effort `high`,
temperature 0.5, and up to 25 iterations per experiment pass. Each experiment
was run 3 times (independent passes) to assess reproducibility. The web sandbox
defaults to algorithmic mode for zero-cost exploration, with optional LLM mode
(currently Gemini 2.5 Flash via Google Vertex AI, admin-switchable).

## Performance

The Rust engine achieves 1,000+ ticks/second and has been tested at 200+ agents.
A typical 12-tick scenario with 2 banks runs in under 1ms. Bootstrap evaluation
(50 samples × 2 policies) completes in ~100ms.
