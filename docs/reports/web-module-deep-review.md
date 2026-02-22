# Web Module Deep Architectural Review

**Reviewer:** Dennis (Backend Engineer)  
**Date:** 2025-02-22  
**Branch:** `feature/interactive-web-sandbox` @ `862d8dd7`  
**Requested by:** Hugi (Project Lead)

---

## Executive Summary

The web module is **functional and impressively feature-rich** — Nash has built a complete multi-day experiment runner with streaming LLM optimization, bootstrap evaluation, checkpoint persistence, and intra-scenario orchestration. However, the codebase has accumulated significant technical debt. The core issues are:

1. **Massive code duplication** between `run_day()` and `simulate_day()` (~80 lines of identical multi-sample averaging logic)
2. **Parallel but diverging optimization paths** — `optimize_policies()` (HTTP) and `optimize_policies_streaming()` (WS) have different error handling and code flow
3. **God-class Game.py** — 1,447 lines, 25+ methods, mixing simulation, optimization, bootstrap, persistence, and policy management
4. **`main.py` is a monolith** — 1,631 lines with business logic embedded in route handlers
5. **No reuse of paper's `OptimizationLoop`** — Nash reimplemented the optimization pipeline from scratch instead of importing it

**Verdict:** Maintainable enough for a prototype, but would be painful to debug at 2am. Refactoring priority is high before adding more features.

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │                  main.py                     │
                    │              (1,631 lines)                   │
                    │                                              │
                    │  HTTP Routes          WebSocket Handlers     │
                    │  ┌─────────────┐     ┌──────────────────┐   │
                    │  │POST /games  │     │WS /ws/games/{id} │   │
                    │  │POST /step   │     │  action: step     │   │
                    │  │POST /auto   │     │  action: auto     │   │
                    │  └──────┬──────┘     └────────┬─────────┘   │
                    │         │                      │             │
                    └─────────┼──────────────────────┼─────────────┘
                              │                      │
                    ┌─────────▼──────────────────────▼─────────────┐
                    │              game.py (1,447 lines)            │
                    │                                              │
                    │  run_day()──────────┐  simulate_day()───┐   │
                    │    │                │    │               │   │
                    │    ▼                │    ▼               │   │
                    │  _run_single_sim()  │  _run_single_sim()│   │
                    │  _run_cost_only()   │  _run_cost_only() │   │
                    │  [multi-sample avg] │  [multi-sample avg│   │ ◄── DUPLICATED
                    │                     │   + tx history]   │   │
                    │                     │                   │   │
                    │  optimize_policies()│  optimize_policies│   │
                    │  (HTTP path)        │  _streaming()     │   │ ◄── DIVERGING
                    │    │                │  (WS path)        │   │
                    │    ▼                │    │               │   │
                    │  _real_optimize()   │    ▼               │   │
                    │  (module-level fn)  │  streaming_optimizer│  │
                    │                     │  .stream_optimize()│  │
                    │                     │                   │   │
                    │  _run_real_bootstrap() ◄────────────────┘   │
                    │  _apply_result()                             │
                    │  _store_prompt()                             │
                    └──────────────────────────────────────────────┘
                              │
                    ┌─────────▼────────────────────────────────────┐
                    │  api/payment_simulator/ (paper's code)       │
                    │                                              │
                    │  ✅ BootstrapSampler, BootstrapPolicyEvaluator│
                    │  ✅ TransactionHistoryCollector               │
                    │  ✅ PolicyOptimizer, ConstraintValidator      │
                    │  ✅ filter_events_for_agent                   │
                    │  ❌ OptimizationLoop (NOT used)               │
                    │  ❌ StandardScenarioConfigBuilder (NOT used)  │
                    │  ❌ StandardPolicyConfigBuilder (NOT used)    │
                    └──────────────────────────────────────────────┘
```

---

## Issue Catalog

### 1. CRITICAL: `run_day()` / `simulate_day()` Duplication

**File:** `game.py:439-608`  
**Severity:** 🔴 Critical

`run_day()` (lines 439-517) and `simulate_day()` (lines 518-608) share ~80 lines of **identical** multi-sample averaging code. The only differences:

- `simulate_day()` doesn't append to `self.days` (deferred via `commit_day()`)
- `simulate_day()` supports `_run_scenario_day()` for intra-scenario mode
- `simulate_day()` collects transaction histories for bootstrap

The multi-sample averaging block (ThreadPoolExecutor, cost aggregation, std dev computation) is copy-pasted verbatim, including `import math` inside both methods.

**Fix:** Extract a `_run_with_multi_sample(seed) → (events, balance_history, costs, per_agent_costs, total_cost, tick_events, cost_std)` method. Both `run_day()` and `simulate_day()` call it.

**Priority:** P0 — any bug fix to averaging logic must be applied in two places.

---

### 2. HIGH: Diverging Optimization Paths

**File:** `game.py:637-790` (`optimize_policies_streaming`) vs `game.py:991-1035` (`optimize_policies`)  
**Severity:** 🟠 High

Two complete optimization implementations:

| Feature | `optimize_policies()` (HTTP) | `optimize_policies_streaming()` (WS) |
|---------|------------------------------|--------------------------------------|
| LLM call | `_real_optimize()` (module-level) | `streaming_optimizer.stream_optimize()` |
| Prompt building | Inline in `_real_optimize()` | `_build_optimization_prompt()` in streaming_optimizer |
| Error handling | `asyncio.gather(return_exceptions=True)`, logs and continues | Fatal errors abort entire experiment, sends `experiment_error` |
| Streaming | No | Yes |
| Retry | 2 retries via PolicyOptimizer | 5 retries with exponential backoff |
| Validation retry | None | Up to 5 validation retries with error feedback |
| MaaS model support | Monkey-patches `client.generate_policy` | Uses `_create_agent()` |

The HTTP path (`_real_optimize`, line ~1260) is significantly less robust than the streaming path. It has no validation retries, fewer LLM retries, and a different MaaS monkey-patching approach.

**Fix:** Deprecate the HTTP optimization path. All optimization should go through the streaming path (even for HTTP requests, just collect results without streaming).

**Priority:** P1 — behavioral differences between paths will cause confusion.

---

### 3. HIGH: God-Class `Game` (1,447 lines, 25+ methods)

**File:** `game.py`  
**Severity:** 🟠 High

`Game` handles:
- Simulation execution (`_run_single_sim`, `_run_cost_only`, `_run_scenario_day`)
- Multi-sample evaluation (averaging, std dev)
- Day lifecycle (`run_day`, `simulate_day`, `commit_day`)
- LLM optimization (two paths)
- Bootstrap evaluation (`_run_real_bootstrap` — 160 lines alone)
- Policy application and validation (`_apply_result`)
- State serialization (`get_state`, `to_checkpoint`, `from_checkpoint`)
- DuckDB persistence (`save_day_to_duckdb`)
- Intra-scenario orchestrator management (`_live_orch`, `_inject_policies_into_orch`)

**Fix:** Extract into:
- `SimulationRunner` — `_run_single_sim`, `_run_cost_only`, `_run_scenario_day`, multi-sample logic
- `BootstrapGate` — `_run_real_bootstrap`, threshold resolution, acceptance logic
- `GameSerializer` — checkpoint save/load, DuckDB writes
- `Game` — orchestration only (day loop, optimization coordination)

**Priority:** P1

---

### 4. HIGH: `main.py` Monolith (1,631 lines)

**File:** `main.py`  
**Severity:** 🟠 High

Route handlers contain business logic that should be in service layer:
- `create_game()` (lines ~390-480): 90 lines with config resolution, policy loading, DuckDB creation, index updates
- `step_game()` (lines ~490-530): Mixes DuckDB writes, index updates, optimization calls
- `game_ws()` (lines ~550-750): 200-line WebSocket handler with inline `run_one_step()`, `auto_run()`, keepalive task

Also: duplicate route registration for `/api/scenario-pack` (defined at lines ~263 and ~353).

**Fix:** 
- Extract `GameService` class with `create()`, `step()`, `auto_run()` methods
- Move WS protocol handling to a separate `ws_handlers.py`
- Delete the duplicate route

**Priority:** P1

---

### 5. HIGH: No Reuse of Paper's `OptimizationLoop`

**File:** `game.py`, `streaming_optimizer.py`  
**Severity:** 🟠 High

The paper has a battle-tested `OptimizationLoop` class (`api/payment_simulator/experiments/runner/optimization.py`) with:
- `SeedMatrix` for reproducible multi-seed evaluation
- `PolicyStabilityTracker` for convergence detection
- `EnrichedBootstrapContextBuilder` for rich LLM context
- `StandardScenarioConfigBuilder` / `StandardPolicyConfigBuilder` for canonical config extraction
- Proper `BootstrapConvergenceDetector`

Nash reimplements most of this:
- Multi-seed averaging: hand-rolled ThreadPoolExecutor in `run_day()`/`simulate_day()` vs `SeedMatrix`
- Bootstrap: reimplemented in `_run_real_bootstrap()` (~160 lines) vs paper's pipeline
- Config building: uses `SimulationConfig.from_dict()` directly instead of `StandardScenarioConfigBuilder`
- No convergence detection at all

**Fix:** Long-term, refactor `Game` to use `OptimizationLoop` components. Short-term, at minimum use `StandardScenarioConfigBuilder` for config extraction (line 271).

**Priority:** P2 (architectural, not breaking)

---

### 6. MEDIUM: `bootstrap_eval.py` Ghost File

**File:** `bootstrap_eval.py`  
**Severity:** 🟡 Medium

Exists on disk but not in the branch — was correctly removed from git. However, it may still be present in deployment artifacts or confuse developers.

**Fix:** Add to `.gitignore` or verify it's not deployed. ✅ Already handled.

---

### 7. MEDIUM: `import math` Inside Method Bodies

**File:** `game.py:491`, `game.py:564`  
**Severity:** 🟡 Medium

`import math` appears inside both `run_day()` and `simulate_day()`. This is a minor smell but indicates copy-paste origin.

**Fix:** Move to top-level imports.

---

### 8. MEDIUM: Module-Level `_real_optimize()` and `_mock_optimize()`

**File:** `game.py:1187-1350`  
**Severity:** 🟡 Medium

These are 160+ line module-level functions that logically belong to the optimization layer. `_real_optimize()` contains its own prompt building, LLM client setup, MaaS monkey-patching, and iteration history construction — all of which is duplicated in `streaming_optimizer._build_optimization_prompt()`.

**Fix:** Delete `_real_optimize()`. Have `optimize_policies()` use `stream_optimize()` in non-streaming mode.

---

### 9. MEDIUM: In-Memory Game Storage with No Eviction

**File:** `main.py:167` (`game_manager: dict[str, Game] = {}`)  
**Severity:** 🟡 Medium

All games are kept in memory forever. Each `Game` holds full `GameDay` objects with events, balance histories, and tick events. A 30-day game with 5 agents and 12 ticks could easily be 50MB+.

**Fix:** LRU eviction with checkpoint-based reload, or move to checkpoint-only mode (current `_try_load_game` is only used on cache miss).

**Priority:** P2

---

### 10. LOW: Inconsistent Error Handling in WS `run_one_step()`

**File:** `main.py:587-635`  
**Severity:** 🟢 Low

The simulation failure rollback (lines 608-618) catches exceptions, rolls back to previous day's policies, and retries — but only for the first failure. If the retry also fails, it raises and the WS `auto_run()` catches it generically.

The pattern of "roll back policies and retry once" is reasonable but undocumented and could mask persistent config issues.

---

### 11. LOW: `settings.py` Loads `.env` on Every LLM Call

**File:** `streaming_optimizer.py:168`, `game.py` (via `_real_optimize`)  
**Severity:** 🟢 Low

`load_dotenv()` is called at the start of every `stream_optimize()` call. Should be called once at app startup.

---

## What Nash Got Right

Credit where due — these are solid engineering decisions:

1. **Bootstrap integration** — Correctly uses the paper's `BootstrapSampler`, `BootstrapPolicyEvaluator`, and `TransactionHistoryCollector`. The statistical method (paired comparison, 95% CI) matches the paper exactly. The per-agent threshold profiles (`conservative`/`moderate`/`aggressive`) are a nice touch not in the paper.

2. **Transactional day execution** — `simulate_day()` + `commit_day()` pattern (game.py:518-616) is genuinely clever. Day results are only committed after successful WS delivery, preventing state corruption on connection drops.

3. **Streaming LLM with retry** — The `stream_optimize()` implementation has proper exponential backoff, retryable error detection, and validation retry with error feedback. This is production-quality error handling.

4. **Intra-scenario mode** — The `_live_orch` persistent orchestrator with `_run_scenario_day()` correctly handles multi-day scenarios where transactions span day boundaries. Cumulative settlement tracking is well-implemented.

5. **Constraint presets with auto-detection** — `constraint_presets.py` is clean, well-documented, and correctly maps scenario features to field groups. The `detect_features()` function is a nice UX feature.

6. **Parallel agent optimization** — Both paths correctly run agents concurrently with `asyncio.gather()` / `asyncio.Semaphore`. The note about game-theoretic isolation (agents don't observe each other's results within a round) is accurate.

7. **Checkpoint persistence** — `to_checkpoint()` / `from_checkpoint()` is complete and handles all game state including rejected policies, optimization prompts, and settlement stats.

8. **Custom CORS middleware** — `ExplicitCORSMiddleware` in `main.py` is a pragmatic solution to a real Cloud Run deployment issue.

---

## Refactoring Roadmap

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P0 | Extract multi-sample averaging from `run_day()`/`simulate_day()` | 2h | Eliminates critical duplication |
| P1 | Unify optimization paths (delete `_real_optimize`, use streaming for both) | 4h | Eliminates behavioral divergence |
| P1 | Extract `SimulationRunner` from `Game` | 3h | Reduces Game to ~500 lines |
| P1 | Extract `BootstrapGate` from `Game._run_real_bootstrap()` | 2h | Testable, reusable |
| P1 | Extract `GameService` from `main.py` route handlers | 4h | Separation of concerns |
| P2 | Use `StandardScenarioConfigBuilder` for config extraction | 2h | Consistency with paper |
| P2 | Add LRU eviction to `game_manager` | 2h | Memory safety |
| P2 | Delete duplicate `/api/scenario-pack` route | 5min | Cleanup |
| P3 | Refactor to reuse `OptimizationLoop` components | 8h | Long-term maintainability |

---

## Conclusion

Nash has built something that **works** — the streaming optimization, bootstrap evaluation, and intra-scenario mode are genuinely impressive features delivered quickly. But the codebase shows signs of "make it work, then make it work differently, then add more features on top" without consolidation passes.

The biggest risk isn't bugs today — it's that **the next person who touches this code** (or Nash himself in 3 months) will struggle to understand which path does what, which optimization function is authoritative, and where to make changes without breaking the other path.

The P0/P1 refactoring (estimated ~15 hours) would bring this to a maintainable state. The P2/P3 items are aspirational but would align the web module with the paper's architecture.

**2am debug assessment:** Could I follow a bug from the frontend through the WS handler to the optimization result? *Probably*, but I'd waste 30 minutes figuring out whether the HTTP or WS optimization path was active, and another 20 minutes tracing through the multi-sample averaging to determine if the bug was in `run_day()` or `simulate_day()`. That's the tax we're paying for the current architecture.
