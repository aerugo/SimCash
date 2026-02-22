# Bootstrap Code Audit

**Date:** 2026-02-22  
**Author:** Dennis (SimCash backend engineer)

---

## 1. `bootstrap/sampler.py` — BootstrapSampler

### Class: `BootstrapSampler(seed: int)`

**Purpose:** Generates bootstrap samples by resampling transaction histories with replacement and remapping arrival times uniformly.

### Key Methods

#### `generate_sample(agent_id, sample_idx, outgoing_records, incoming_records, total_ticks) → BootstrapSample`

**Data flow:**
- **Input:** Agent ID, sample index, tuples of `TransactionRecord` (outgoing and incoming), total ticks
- **Output:** `BootstrapSample` containing remapped outgoing txns and incoming settlements

**Algorithm:**
1. **Seed derivation:** `SHA-256(f"{base_seed}:sample:{sample_idx}")` → first 8 bytes → mod 2³¹. This gives each sample a unique, deterministic seed.
2. **Outgoing resampling:** For each of N records, pick random index (with replacement) via xorshift64*, assign uniform random arrival tick in `[0, total_ticks)`.
3. **Incoming filtering:** Only settled incoming records are included (`was_settled == True`).
4. **Incoming resampling:** Same bootstrap-with-replacement + uniform arrival remapping as outgoing.
5. **Unique tx_ids:** Each remapped transaction gets `f"{original_tx_id}:{prefix}:{i}"` to avoid collisions.

**Key design decisions:**
- Resampling preserves the *distribution* of transaction sizes/priorities but **destroys temporal correlation** — arrivals become uniform random.
- Deadline and settlement offsets are preserved via `record.remap_to_tick()` — only the arrival tick changes.
- Uses custom `_Xorshift64Star` RNG matching the Rust simulation core for cross-language determinism.

#### `generate_samples(agent_id, n_samples, ...) → list[BootstrapSample]`

Simple loop calling `generate_sample` for `i in range(n_samples)`.

### RNG: `_Xorshift64Star`

- Standard xorshift64* algorithm
- `next_int(max_val)` uses modulo (biased for large ranges, acceptable for this use case)
- Matches Rust FFI implementation

---

## 2. `bootstrap/evaluator.py` — BootstrapPolicyEvaluator

### Class: `BootstrapPolicyEvaluator(opening_balance, credit_limit, cost_rates?, max_collateral_capacity?, liquidity_pool?)`

**Purpose:** Evaluates policies on bootstrap samples using **single-agent sandbox isolation** (3-agent setup via `SandboxConfigBuilder`).

### Key Methods

#### `evaluate_sample(sample: BootstrapSample, policy: dict) → EvaluationResult`

**Data flow:**
1. `SandboxConfigBuilder.build_config()` → creates 3-agent sandbox (SOURCE/TARGET/SINK)
2. `Orchestrator.new(ffi_config)` → creates simulation
3. Runs tick-by-tick for `sample.total_ticks` ticks
4. Extracts agent metrics via `orchestrator.get_agent_accumulated_costs(agent_id)` and `orchestrator.get_agent_state(agent_id)`

**Output:** `EvaluationResult(sample_idx, seed, total_cost, settlement_rate, avg_delay, cost_breakdown)`

- `total_cost` is **integer cents** (project invariant INV-1)
- `CostBreakdown` has: `delay_cost`, `overdraft_cost`, `deadline_penalty`, `eod_penalty` (eod_penalty always 0 from FFI)

#### `compute_paired_deltas(samples, policy_a, policy_b) → list[PairedDelta]`

**Algorithm:**
1. Evaluate policy_a on ALL samples → `results_a`
2. Evaluate policy_b on ALL samples → `results_b`
3. For each pair: `delta = cost_a - cost_b`

**Delta convention:** `delta = cost_a - cost_b`. **Positive delta = policy_a is MORE expensive** (policy_b is better).

> ⚠️ This is the **paper/API convention**. In the optimization loop, policy_a = old, policy_b = new. So **positive delta = new policy is cheaper = improvement**.

#### `compute_mean_cost(results) → float` / `compute_mean_delta(deltas) → float`

Simple arithmetic means.

### Key Architecture: Single-Agent Isolation

The evaluator uses `SandboxConfigBuilder` to create a **3-agent sandbox** where the target agent operates in isolation. This is the **paper's approach** — evaluate one agent at a time without counterparty interference.

---

## 3. `bootstrap/sandbox_config.py` — SandboxConfigBuilder

### Class: `SandboxConfigBuilder()`

**Purpose:** Creates isolated 3-agent simulation environments for evaluating a single agent's policy.

### Architecture: SOURCE → TARGET → SINK

| Agent | Opening Balance | Credit Limit | Policy | Role |
|-------|----------------|-------------|--------|------|
| `SOURCE` | 10B cents ($100M) | 0 | FIFO | Sends scheduled payments to TARGET (liquidity inflow) |
| `TARGET` | Configurable | Configurable | Test policy | Agent being evaluated |
| `SINK` | 0 | 10B cents | FIFO | Receives all outgoing payments from TARGET |

### Key Method: `build_config(sample, target_policy, opening_balance, credit_limit, ...) → SimulationConfig`

**Data flow:**
1. Build 3 agents (SOURCE, TARGET, SINK)
2. Convert bootstrap sample transactions to scenario events:
   - **Outgoing txns** → `CustomTransactionArrivalEvent` (TARGET → SINK)
   - **Incoming settlements** → `ScheduledSettlementEvent` (SOURCE → TARGET)
3. Uses `StandardPolicyConfigBuilder` for canonical parameter extraction (liquidity fraction, collateral config)
4. Returns full `SimulationConfig` with `ticks_per_day = sample.total_ticks`, `num_days = 1`

### Event Mapping

- **Outgoing:** `RemappedTransaction` → `CustomTransactionArrivalEvent(from=agent_id, to="SINK", amount, priority, deadline, schedule=OneTimeSchedule(tick=arrival_tick))`
- **Incoming:** `RemappedTransaction` → `ScheduledSettlementEvent(from="SOURCE", to=agent_id, amount, schedule=OneTimeSchedule(tick=settlement_tick))`

> **Critical design note:** Incoming uses `ScheduledSettlement` (not `DirectTransfer`) so it goes through the real RTGS engine and emits `RtgsImmediateSettlement` events. This is necessary for bootstrap correctness — the policy can observe these events.

### Policy Parsing

Handles three policy formats:
1. `"Fifo"` → `FifoPolicy()`
2. `"LiquidityAware"` → `LiquidityAwarePolicy(target_buffer, urgency_threshold)`
3. Tree policies (detected by `payment_tree`/`bank_tree`/etc. keys) → `InlineJsonPolicy(json_string=json.dumps(...))`

---

## 4. `experiments/runner/optimization.py` — `_evaluate_policy_pair()` and `_should_accept_policy()`

### `_evaluate_policy_pair(agent_id, old_policy, new_policy) → PolicyPairEvaluation`

**Two modes:**

#### Deterministic Mode (single sample)
1. Get seed from `SeedMatrix.get_iteration_seed(iteration_idx, agent_id)`
2. Run simulation with old_policy → `old_cost` (via `_run_single_simulation`)
3. Run simulation with new_policy → `new_cost` (via `_run_simulation` for extended metrics)
4. `delta = old_cost - new_cost` (**positive = improvement**)
5. **Restore old policy** after evaluation — caller sets new if accepted

#### Bootstrap Mode (multiple samples)
1. Uses **pre-computed bootstrap samples** from `self._bootstrap_samples[agent_id]`
2. Creates `BootstrapPolicyEvaluator` with agent config from `StandardScenarioConfigBuilder`
3. Calls `evaluator.compute_paired_deltas(samples, policy_a=old_policy, policy_b=new_policy)`
4. Builds `SampleEvaluationResult` list: `delta = pd.delta` (which is `cost_a - cost_b = old - new`)
5. Computes `cost_std_dev` and `confidence_interval_95` via `compute_cost_statistics()`

**Delta convention in optimization.py:** `delta = old_cost - new_cost`. **Positive = improvement** (new is cheaper).

> This is consistent with the evaluator's `cost_a - cost_b` where a=old, b=new.

### `_should_accept_policy(agent_id, old_policy, new_policy, current_cost) → (bool, old_cost, new_cost, deltas, delta_sum, evaluation, reason)`

**Acceptance flow:**

```
1. Call _evaluate_policy_pair() → PolicyPairEvaluation

2. Check: delta_sum > 0?
   NO  → REJECT ("delta_sum ≤ 0")
   YES → continue

3. If acceptance_config.require_statistical_significance:
   Call _is_improvement_significant(evaluation)
   - Checks evaluation.confidence_interval_95
   - CI lower bound must be > 0
   FAIL → REJECT (reason from function)

4. If acceptance_config.max_coefficient_of_variation is not None:
   Call _is_variance_acceptable(evaluation, max_cv)
   - Computes CV = cost_std_dev / mean_new_cost
   - CV must be ≤ max_cv
   FAIL → REJECT (reason from function)

5. All checks passed → ACCEPT
   reason = "passed: delta_sum > 0, CI > 0, CV ≤ {threshold}"
```

### Helper Functions

#### `_is_improvement_significant(evaluation) → (bool, str)`
- If `delta_sum ≤ 0` → False
- If no CI data → True (fall back to mean-only)
- If `ci_lower > 0` → True (significant)
- Else → False (CI includes zero)

#### `_is_variance_acceptable(evaluation, max_cv=0.5) → (bool, str)`
- If no std_dev data → True (skip check)
- If `mean_new_cost ≤ 0` → True (skip)
- `CV = cost_std_dev / mean_new_cost`
- `CV ≤ max_cv` → True, else False

### Temporal Mode (`_optimize_agent_temporal`)

Completely different flow:
- **Always accepts** new policies (no paired comparison)
- Convergence detected by **policy stability** — all agents' `initial_liquidity_fraction` unchanged for `stability_window` iterations
- Designed for multi-agent scenarios where the cost landscape shifts as counterparties change

---

## 5. `web/backend/app/bootstrap_eval.py` — WebBootstrapEvaluator

### Class: `WebBootstrapEvaluator(num_samples=10, cv_threshold=0.5)`

**Purpose:** Paired bootstrap evaluation for the **web game**. Simpler than the paper implementation.

### Key Differences from Paper Implementation

| Aspect | Paper (`evaluator.py` + `sandbox_config.py`) | Web (`bootstrap_eval.py`) |
|--------|----------------------------------------------|--------------------------|
| **Isolation** | 3-agent sandbox (SOURCE/TARGET/SINK) | **Full multi-agent scenario** |
| **Resampling** | Bootstrap resampling of transaction arrivals | **Seed variation only** (`base_seed + i * 1000`) |
| **Delta convention** | `old - new` (positive = improvement) | **`new - old` (negative = improvement)** |
| **Acceptance: delta** | `delta_sum > 0` | `delta_sum < 0` |
| **Acceptance: CI** | CI lower > 0 | **CI upper < 0** |
| **Acceptance: CV** | CV ≤ max_cv (on new policy costs) | CV ≤ cv_threshold (**on deltas**) |
| **Parallelism** | Sequential | **ThreadPoolExecutor** (GIL-releasing FFI) |
| **Policy injection** | Via SandboxConfigBuilder | **Direct YAML mutation** with `InlineJson` wrapping |
| **Other agents** | N/A (sandbox) | Can pass `other_policies` for multi-agent |
| **Special case** | N/A | `delta_sum == 0` → accept (no harm) |

### `evaluate(raw_yaml, agent_id, old_policy, new_policy, base_seed, other_policies?) → EvaluationResult`

**Algorithm:**
1. Generate seeds: `[base_seed, base_seed + 1000, ..., base_seed + (N-1)*1000]`
2. For each seed, run full simulation with old policy → `old_costs`
3. For each seed, run full simulation with new policy → `new_costs`
4. `deltas[i] = new_costs[i] - old_costs[i]` (**negative = improvement**)
5. Compute `delta_sum`, `mean_delta`, `cv` (of deltas), `ci_lower`/`ci_upper`

**Acceptance criteria (all must pass):**
```
delta_sum == 0  → ACCEPT (no change, no harm)
delta_sum >= 0  → REJECT ("No improvement")
cv > threshold  → REJECT ("CV too high")
ci_upper >= 0   → REJECT ("Not significant: CI crosses zero")
Otherwise       → ACCEPT
```

### `_run_sim_fast(raw_yaml, agent_id, policy, seed, other_policies?) → int`

1. Deep-copy raw YAML scenario
2. For each agent in scenario:
   - If target agent: inject test policy
   - If in `other_policies`: inject that policy
   - Extract `initial_liquidity_fraction` → set `liquidity_allocation_fraction`
   - Wrap policy in `InlineJson` format
3. Set `rng_seed = seed`
4. Convert to `SimulationConfig` → FFI dict → `Orchestrator.new()`
5. Call `orch.run_and_get_total_cost(agent_id, ticks)` — GIL-releasing, thread-safe

### CV Calculation Difference

- **Paper:** CV = `cost_std_dev / mean_new_cost` (coefficient of variation of absolute costs)
- **Web:** CV = `stdev(deltas) / abs(mean_delta)` (coefficient of variation of **deltas**)

The web's CV measures stability of the *improvement signal*, not stability of absolute costs. This is arguably more appropriate for acceptance decisions.

---

## Summary: Critical Observations

### 1. Delta Convention Mismatch
- **Paper/API:** `delta = old - new` → positive = improvement
- **Web:** `delta = new - old` → negative = improvement

These are **mathematically equivalent** but use **opposite sign conventions**. The acceptance logic is consistent within each codebase (paper checks `> 0`, web checks `< 0`).

### 2. Single-Agent vs Multi-Agent
- **Paper:** Strict single-agent isolation via 3-agent sandbox. The target agent's counterparties are replaced by infinite-liquidity SOURCE and infinite-capacity SINK.
- **Web:** Full multi-agent simulation. The target agent is evaluated alongside all other agents with their current policies. The `other_policies` parameter allows fixing counterparty behavior.

**Implication:** The paper's approach measures policy quality in isolation (no strategic interaction effects). The web's approach captures cross-agent effects but introduces noise from counterparty behavior.

### 3. Resampling vs Seed Variation
- **Paper:** True bootstrap resampling — draws transactions with replacement, remaps arrivals uniformly. Creates genuinely different scenarios from the same historical data.
- **Web:** Seed variation only (`base_seed + i * 1000`). Each seed produces a different random realization, but the scenario structure is identical (same agents, same arrival distributions, same parameters). This is **Monte Carlo with different seeds**, not bootstrap resampling.

**Implication:** The paper's approach tests robustness to different transaction mixes. The web's approach tests robustness to different random realizations of the same distribution.

### 4. Per-Iteration Context Simulation (Paper Only)
The paper runs a fresh "context simulation" each iteration (INV-13: Bootstrap Seed Hierarchy), then resamples from that iteration's transaction history. This means bootstrap samples change each iteration, exploring different stochastic regimes. The web evaluator uses fixed seed offsets — no context simulation or resampling.
