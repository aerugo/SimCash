# Handover: Bootstrap Evaluation — Use the Existing Code

**From:** Dennis (Rust engine / Python orchestrator)
**To:** Nash (web sandbox)
**Date:** 2025-07-11

Nash — your `WebBootstrapEvaluator` works but it's solving a different problem than the paper. Here's how to use the existing bootstrap code instead of reinventing it.

---

## The Core Difference

**Paper's approach (what you need):**
1. Run ONE context simulation with the current policy
2. Collect the transaction histories (who sent what, when, to whom)
3. **Resample** those histories with replacement → N synthetic transaction schedules
4. Build a **single-agent sandbox** (SOURCE → TARGET → SINK) for each sample
5. Evaluate old vs new policy on the **same** N sandboxes (paired comparison)

**Your current approach:**
1. Pick N different RNG seeds
2. Run the **full multi-agent scenario** with each seed (different arrivals, different interactions)
3. Compare old vs new costs

The paper's approach is statistically superior because:
- **Paired comparison on identical transaction schedules** eliminates scenario variance
- **Single-agent sandbox** isolates the target agent — other agents can't confound the result
- **Resampling from observed history** preserves the real distribution of transactions

Your approach re-randomizes everything, which adds noise and makes it harder to detect real policy improvements.

---

## The Existing Code You Should Use

Everything lives in `api/payment_simulator/ai_cash_mgmt/bootstrap/`. Here's the pipeline:

### Step 1: Collect Transaction History

**`history_collector.py`** → `TransactionHistoryCollector`

After running a context simulation, collect what happened:
```python
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector

collector = TransactionHistoryCollector()
# Feed it the events from your context simulation
history = collector.collect(agent_id="BANK_A", events=tick_events)
# Returns: outgoing_records, incoming_records (tuples of TransactionRecord)
```

### Step 2: Generate Bootstrap Samples

**`sampler.py`** → `BootstrapSampler`

Resample the history with replacement to create N synthetic scenarios:
```python
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

sampler = BootstrapSampler(seed=iteration_seed)
samples = sampler.generate_samples(
    agent_id="BANK_A",
    n_samples=50,  # paper uses 50
    outgoing_records=history.outgoing,
    incoming_records=history.incoming,
    total_ticks=ticks_per_day,
)
# Returns: list[BootstrapSample] — each is a synthetic transaction schedule
```

Each `BootstrapSample` contains:
- `outgoing_txns` — resampled outgoing transactions with randomized arrival ticks
- `incoming_settlements` — resampled incoming settlements (liquidity beats)
- Deterministic: same seed → same samples (xorshift64* RNG)

### Step 3: Evaluate with Paired Comparison

**`evaluator.py`** → `BootstrapPolicyEvaluator`

Run old and new policy on the **same** samples:
```python
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator

evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,
    credit_limit=agent_config.unsecured_cap,
    liquidity_pool=agent_config.liquidity_pool,
)

# Paired comparison
deltas = evaluator.compute_paired_deltas(
    samples=samples,
    policy_a=old_policy,   # current best
    policy_b=new_policy,   # LLM proposal
)
# Returns: list[PairedDelta] where delta = cost_a - cost_b
# Positive delta = new policy is cheaper = improvement
```

### Step 4: Acceptance Decision

**`sandbox_config.py`** → `SandboxConfigBuilder` (used internally by evaluator)

The evaluator uses `SandboxConfigBuilder` to create a 3-agent sandbox for each sample:
- **SOURCE** — infinite liquidity, sends scheduled payments to TARGET
- **TARGET** — the agent being tested, with the candidate policy
- **SINK** — infinite capacity, receives all outgoing payments

This isolates the target agent completely. No cross-agent interference.

### Step 5: Apply Acceptance Criteria

From the paired deltas, apply the same 3-layer check as the experiment runner:

```python
delta_values = [d.delta for d in deltas]
delta_sum = sum(delta_values)

# Layer 1: Mean improvement must be positive
if delta_sum <= 0:
    reject("No improvement")

# Layer 2: Statistical significance (optional, from experiment config)
if require_statistical_significance:
    import statistics, math
    std = statistics.stdev(delta_values)
    se = std / math.sqrt(len(delta_values))
    ci_lower = (delta_sum / len(delta_values)) - 1.96 * se
    if ci_lower <= 0:
        reject("95% CI includes zero")

# Layer 3: CV threshold (optional)
mean_new = statistics.mean(r.cost_b for r in deltas)
if mean_new != 0:
    cv = statistics.stdev(r.cost_b for r in deltas) / abs(mean_new)
    if cv > max_cv:
        reject("Variance too high")
```

**Note the delta convention:** Paper uses `cost_a - cost_b` (positive = improvement). Your `WebBootstrapEvaluator` uses `cost_new - cost_old` (negative = improvement). Stick with the paper convention when using the paper's code.

---

## What to Change in `game.py`

### Before optimization (collect history)

After running a day's simulation, collect the transaction history from the events:

```python
# After simulate_day() completes, for each agent:
collector = TransactionHistoryCollector()
history = collector.collect(agent_id=aid, events=day_events)
self._agent_histories[aid] = history
```

### During optimization (evaluate proposals)

Replace the `WebBootstrapEvaluator` call with the paper's evaluator:

```python
sampler = BootstrapSampler(seed=self._base_seed + self.current_day)
samples = sampler.generate_samples(
    agent_id=aid, n_samples=50,
    outgoing_records=self._agent_histories[aid].outgoing,
    incoming_records=self._agent_histories[aid].incoming,
    total_ticks=ticks_per_day,
)

evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_cfg.opening_balance,
    credit_limit=agent_cfg.unsecured_cap,
    liquidity_pool=agent_cfg.liquidity_pool,
)

deltas = evaluator.compute_paired_deltas(samples, old_policy, new_policy)
delta_sum = sum(d.delta for d in deltas)

accepted = delta_sum > 0  # + CI/CV checks as needed
```

### After optimization (record real acceptance)

Pass the real `was_accepted` value to the iteration history:

```python
record = SingleAgentIterationRecord(
    was_accepted=accepted,          # NOT hardcoded True
    is_best_so_far=is_new_best,     # only True if accepted AND cheaper than running best
    ...
)
```

---

## What to Do with `WebBootstrapEvaluator`

You have two options:

**Option A (recommended): Replace it.** Use `BootstrapSampler` + `BootstrapPolicyEvaluator` from the `api/` package. They handle single-agent isolation, paired comparison, and deterministic resampling correctly. Your `WebBootstrapEvaluator` becomes dead code.

**Option B: Keep it as a fast fallback.** Your seed-variation approach is faster (no resampling overhead) and might be useful for quick sanity checks. But don't use it for the paper reproduction path — the statistical properties are different.

---

## Performance Note

The paper's bootstrap runs 2 × 50 = 100 single-agent sandbox simulations per agent per iteration. These are tiny (3 agents, ~100 ticks each) and much faster than your current approach of running the full multi-agent scenario 2 × N times. The sandbox approach should actually be **faster** than `WebBootstrapEvaluator` for realistic N.

The evaluator already uses `Orchestrator.tick()` in a sequential loop. If you want to parallelize, each `evaluate_sample()` call is independent and can run in a thread (with GIL release on the Rust side).

---

## Summary

| Step | Existing Code | Location |
|------|--------------|----------|
| Collect history | `TransactionHistoryCollector` | `ai_cash_mgmt/bootstrap/history_collector.py` |
| Resample | `BootstrapSampler` | `ai_cash_mgmt/bootstrap/sampler.py` |
| Build sandbox | `SandboxConfigBuilder` | `ai_cash_mgmt/bootstrap/sandbox_config.py` |
| Evaluate paired | `BootstrapPolicyEvaluator` | `ai_cash_mgmt/bootstrap/evaluator.py` |
| Models | `BootstrapSample`, `TransactionRecord`, `PairedDelta` | `ai_cash_mgmt/bootstrap/models.py` |

Don't rewrite these. Wire them in.

---

## Reference

- `docs/reports/bootstrap-code-audit.md` — Detailed code audit of both implementations
- `docs/reports/experiment-runner-audit.md` — Full experiment runner trace
- `docs/reports/experiment-runner-vs-web-comparison.md` — Gap analysis
