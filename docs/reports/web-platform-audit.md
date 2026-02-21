# Web Platform Audit: Optimization Implementation

**Author:** Dennis (backend engineer)  
**Date:** 2026-02-21  
**Scope:** How the web platform handles policy optimization vs the experiment runner

---

## 1. `game.py` — The Game Class

### Initialization
- `Game.__init__()` takes: `game_id`, `raw_yaml`, `use_llm`, `simulated_ai`, `max_days`, `num_eval_samples`, `optimization_interval`, `constraint_preset`, `starting_policies`
- All agents start with `DEFAULT_POLICY` (FIFO, fraction=1.0) unless `starting_policies` is provided
- `starting_policies` is a `dict[str, str]` mapping agent_id → policy JSON string

### DEFAULT_POLICY (line ~26)
```python
DEFAULT_POLICY = {
    "version": "2.0",
    "policy_id": "default_fifo",
    "parameters": {"initial_liquidity_fraction": 1.0},
    "bank_tree": {"type": "action", "node_id": "bank_root", "action": "NoAction"},
    "payment_tree": {"type": "action", "node_id": "pay_root", "action": "Release"},
}
```
**Key difference from experiment runner:** The experiment runner loads its starting policy from `ExperimentConfig.starting_policy` (which can be a full decision tree). The web platform defaults to fraction=1.0 (100% allocation) with trivial FIFO trees.

### How Rounds Work
- `run_day()` / `simulate_day()` runs one simulation with current policies at seed = `_base_seed + day_num`
- `simulate_day()` is a non-committing variant — caller must call `commit_day()` to persist
- After a day, `should_optimize(day_num)` checks if `(day_num + 1) % optimization_interval == 0`
- Optimization is triggered externally (by the WebSocket handler), not internally

### How `optimize_policies()` Is Called
Two paths:
1. **`optimize_policies_streaming(send_fn)`** — Primary path for WebSocket games. Streams LLM chunks to frontend. Runs all agents in parallel (up to 10 concurrent). Has retry/error handling. Falls back to mock in `simulated_ai` mode.
2. **`optimize_policies()`** — Non-streaming fallback. Also parallel via `asyncio.gather`.

Both paths:
- Build context from `self.days` (all past days)
- Call either `_mock_optimize()` or `_real_optimize()` / `stream_optimize()`
- Optionally run bootstrap evaluation if `num_eval_samples > 1`
- Apply result via `_apply_result()`

### Seed Management
- Base seed from `raw_yaml["simulation"]["rng_seed"]` (default 42)
- Day N uses seed = `base_seed + N`
- Extra eval samples use seed offsets: `seed + i * 1000` for i in 1..num_eval_samples
- Bootstrap evaluation uses `base_seed + current_day * 100 + i * 1000`

**Difference from experiment runner:** The experiment runner uses `SeedMatrix` with configurable seed strategies (sequential, random, Latin hypercube). The web platform uses simple linear offsets.

### How Costs Are Collected
- `_run_single_sim()`: Tick-by-tick loop, collects events, balance history, and costs via `orch.get_agent_accumulated_costs()`
- `_run_cost_only()`: Uses `orch.run_and_get_all_costs(ticks)` — GIL-releasing FFI for thread-parallel eval samples
- Cost breakdown: `liquidity_cost` (opportunity), `delay_cost`, `penalty_cost`, `total`
- When `num_eval_samples > 1`: runs representative sim + extra cost-only samples, averages costs

### How Policies Are Applied
- `_apply_result()` validates new policy by building a test config and creating a test Orchestrator
- If validation fails, reverts to old policy
- Records result in `reasoning_history[agent_id]`

### `_run_scenario_day` and `_run_eval_pass`
**These methods do NOT exist in game.py.** The web platform combines both into `run_day()` / `simulate_day()`. There is no separate "scenario day" vs "eval pass" distinction.

---

## 2. `streaming_optimizer.py` — The Streaming Optimizer

### `_build_optimization_prompt()`
Builds system + user prompt using the same infrastructure as the experiment runner:
- `PolicyOptimizer` for system prompt (with cost rates)
- `build_single_agent_context()` for iteration history, cost breakdown, simulation trace
- `UserPromptBuilder._build_policy_section()` for policy format instructions
- `filter_events_for_agent()` + `format_filtered_output()` for agent-isolated event traces

**Prompt structure:**
1. System prompt: from `PolicyOptimizer.get_system_prompt(cost_rates=...)` — same as experiment runner
2. User prompt: `build_single_agent_context(...)` + policy section + current policy JSON + "Generate improved policy"

### How It Formats Costs and Iteration History
- `cost_breakdown`: `delay_cost`, `overdraft_cost`, `deadline_penalty`, `eod_penalty=0`
- Iteration history: list of `SingleAgentIterationRecord` with `was_accepted=True` for ALL entries (temporal mode — no rejection tracking in history)
- `cost_std=0` always (no per-iteration variance info available)
- `mean_cost = agent_cost` (single value, not bootstrap mean)

### What Context It Sends to the LLM
- System prompt with cost rates and optimization instructions
- Per-agent filtered simulation trace (tick-by-tick events)
- Full iteration history (all past days)
- Current policy JSON
- Cost breakdown for last day

### How the LLM Response Is Parsed
`_parse_policy_response()`:
- Strips markdown code blocks
- Finds JSON braces
- `json.loads()`
- Adds `version: "2.0"` and random `policy_id` if missing

### Retry Logic
- Up to 5 retries with exponential backoff (2s → 60s max)
- Retryable: 429, 503, timeouts, connection resets
- 600s total timeout per call, 90s stall timeout
- Yields retry events to frontend for display

### Differences from Experiment Runner
1. **`cost_std` always 0** — experiment runner computes real standard deviation from bootstrap samples
2. **`was_accepted=True` for all history entries** — experiment runner tracks actual acceptance/rejection per iteration
3. **No `is_best_so_far` accuracy** — computed locally but based on `was_accepted=True` assumption
4. **No enriched bootstrap context** — experiment runner uses `EnrichedBootstrapContextBuilder` with per-seed best/worst analysis, `BootstrapEvent` details, `CostBreakdown` per sample
5. **No `DebugCallback`** — experiment runner supports debug callbacks for prompt inspection

---

## 3. `simulation.py` — The Simulation Runner

### How It Creates Orchestrators
- `SimulationManager.create()` builds config from preset YAML or custom `ScenarioConfig`
- Uses `SimulationConfig` → `to_ffi_dict()` → `Orchestrator.new()`
- Stores instance in `self.simulations` dict

### How It Runs Simulations
- **Tick-by-tick:** `do_tick()` / `do_tick_async()` — advances one tick, collects events/balances/costs
- **Policy optimization:** `run_optimization_step()` — builds trace from tick history, calls LLM, re-runs full sim with new policy, compares costs

### How It Collects Results
- Per-tick: balance history, cost history, events
- Per-optimization: old vs new total cost, acceptance decision

### `run_optimization_step()` Details
- Builds simulation trace from `tick_history` (crude: tick number + balance/queue/cost per agent + first 10 events)
- Calls `optimize_policy_with_llm()` from `policy_runner.py` or mock
- Re-runs entire simulation with new policy via `run_with_policy()`
- **Has a basic acceptance mechanism:** `accepted = improved or self.iteration <= 2` (accept first 2 iterations unconditionally, then only if cost improves)

**This is a SEPARATE optimization path from `game.py`.** `simulation.py` is the older tick-by-tick simulation mode; `game.py` is the newer multi-day game mode. They coexist but serve different UI flows.

---

## 4. `llm_agent.py` — The LLM Agent

### How It Calls the LLM
- `get_llm_decision()`: Per-tick reasoning (NOT policy optimization)
- Uses `pydantic-ai` Agent via `_create_agent()` from `streaming_optimizer.py`
- Model comes from `settings_manager.get_llm_config()` (admin-configurable)
- Supports Vertex AI with thinking config

### What Model It Uses
- Configurable via platform settings (admin UI)
- Supports Google Vertex (Gemini), MaaS models (GLM-5), and standard OpenAI-compatible providers
- Falls back to mock on any error

### Purpose
This is for **per-tick LLM reasoning** (Release/Hold decisions, liquidity allocation), NOT for policy optimization. It's used in the tick-by-tick simulation mode, not the multi-day game mode.

---

## 5. Gap Analysis: What's Missing vs Experiment Runner

### ❌ No Proper Acceptance/Rejection Mechanism (in Game mode)
- **Experiment runner:** Paired bootstrap comparison — run old + new policy on same N seeds, compute deltas, check statistical significance (95% CI), CV threshold, mean improvement
- **Web platform (game.py):** Bootstrap evaluation EXISTS via `WebBootstrapEvaluator` BUT only when `num_eval_samples > 1`. When `num_eval_samples == 1` (the default), there is NO acceptance gate — every LLM proposal is accepted unconditionally.
- **Web platform (simulation.py):** Has crude acceptance: `improved or iteration <= 2`

### ❌ Paired Bootstrap Comparison Is Simplified
- `WebBootstrapEvaluator` exists and does proper paired comparison with CV + CI checks
- BUT it's only invoked when `num_eval_samples > 1`, which must be explicitly configured
- The default game creation path likely uses `num_eval_samples=1` unless the frontend passes it
- Missing: enriched per-seed analysis, best/worst seed identification, `BootstrapEvent` tracking

### ❌ Experiment Config Fields Ignored
The web platform does NOT use `ExperimentConfig` at all. These fields are absent:

| Field | Experiment Runner | Web Platform |
|-------|------------------|-------------|
| `evaluation.mode` | bootstrap / deterministic / pairwise | Not configurable (always temporal-style) |
| `evaluation.num_samples` | From config | `num_eval_samples` param (default 1) |
| `evaluation.acceptance.require_statistical_significance` | Configurable | Hardcoded in `WebBootstrapEvaluator` |
| `evaluation.acceptance.max_coefficient_of_variation` | Configurable | Hardcoded 0.5 |
| `starting_policy` | Full policy from YAML | `DEFAULT_POLICY` (fraction=1.0, FIFO) |
| `optimization.convergence` | BootstrapConvergenceDetector | None — runs for `max_days` |
| `optimization.max_no_improvement` | Early stopping | None |
| `optimization.policy_stability` | PolicyStabilityTracker | None |
| `seed_strategy` | SeedMatrix (sequential/random/LHS) | Linear offset |
| `verbose` | Tick-by-tick output capture | Events captured but not in same format |

### ❌ Starting Policy Differs
- **Experiment runner:** Loads from `ExperimentConfig.starting_policy` — can be a complex decision tree with conditions, thresholds, queue-based logic
- **Web platform:** `DEFAULT_POLICY` = FIFO (Release all, NoAction on bank tree) with fraction=1.0. Starting policies CAN be overridden via `starting_policies` param but must be passed as JSON strings by the frontend.

### ❌ Prompt Differences
- **Experiment runner:** Uses `EnrichedBootstrapContextBuilder` which provides:
  - Per-seed cost breakdowns with best/worst identification
  - `BootstrapEvent` objects with settlement details
  - Real `cost_std` from bootstrap samples
  - Accurate `was_accepted` flags in iteration history
  - `is_best_so_far` tracking with proper acceptance gating
- **Web platform:** Uses same `build_single_agent_context()` BUT with degraded inputs:
  - `cost_std=0` always
  - `was_accepted=True` for all history entries (even if bootstrap rejected)
  - `mean_cost = agent_cost` (single sample, not bootstrap mean)
  - No enriched per-seed analysis

### ❌ No Convergence Detection
- Experiment runner has `BootstrapConvergenceDetector` and `PolicyStabilityTracker`
- Web platform runs for exactly `max_days` iterations with no early stopping

### ❌ No Audit Trail
- Experiment runner has `ExperimentRepository` for persistent result storage with full provenance
- Web platform has checkpoint persistence but no structured audit format

### ✅ What IS Present
- Core optimization loop (iterate: simulate → optimize → apply)
- Same `PolicyOptimizer` and system prompts
- Same event filtering (`filter_events_for_agent`)
- Same `SingleAgentIterationRecord` history tracking
- Bootstrap paired evaluation (when configured)
- Policy validation before application
- Parallel agent optimization
- Retry with exponential backoff
- Streaming LLM output to frontend

---

## 6. Summary

The web platform has two distinct code paths:

1. **`game.py` + `streaming_optimizer.py`** — The multi-day game mode. This is the primary path for the web UI. It reuses experiment runner infrastructure (`PolicyOptimizer`, `build_single_agent_context`, event filtering) but with simplified evaluation (no bootstrap by default, no convergence detection, degraded prompt context).

2. **`simulation.py` + `llm_agent.py`** — The older tick-by-tick mode. Has its own crude optimization (`run_optimization_step`) with basic acceptance logic. Largely superseded by game mode.

**The biggest gaps are:**
1. Default `num_eval_samples=1` means no bootstrap evaluation — every LLM proposal is accepted
2. Iteration history always shows `was_accepted=True`, giving the LLM false context
3. `cost_std=0` removes variance information from LLM prompts
4. No convergence detection or early stopping
5. No enriched bootstrap context (best/worst seed analysis)
6. Starting policy is always FIFO@1.0 unless explicitly overridden
