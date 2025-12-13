# SimCash Paper v2 - Handover Prompt

## Context

We are writing a draft paper to be shared with our collaborators who authored Castro et al. (2025). The paper demonstrates how SimCash can reproduce their three experiments on reinforcement learning for payment system policy optimization.

**v1 is complete** - see `docs/plans/simcash-paper/v1/` for:
- `draft-paper.md` - Complete draft with methodology, results, and analysis
- `lab-notes.md` - Detailed iteration logs from experiment runs

**Your task**: Produce v2 with the newly implemented **real bootstrap evaluation**.

---

## 🔴 CRITICAL: Bootstrap Evaluation Has Changed

Between v1 and v2, we completely rewrote the bootstrap evaluation system. **v1 results used parametric Monte Carlo (generating new random transactions each evaluation), NOT true bootstrap resampling.**

### What Changed

| Aspect | v1 ("bootstrap") | v2 (Real Bootstrap) |
|--------|------------------|---------------------|
| Transaction generation | New random transactions each sample | Resampled from historical data |
| Paired comparison | Not possible (different transactions) | Enabled (same transactions for both policies) |
| Evaluation architecture | Full simulation per sample | 3-agent sandbox (SOURCE→AGENT→SINK) |
| Statistical efficiency | Low (high variance from transaction noise) | High (variance from policy differences only) |

### Key New Documentation

**Read these before running experiments:**
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Statistical justification for sandbox approach
- `docs/plans/bootstrap/work_notes.md` - Implementation history and technical decisions

### The 3-Agent Sandbox Architecture

The new bootstrap evaluation uses an isolated sandbox:

```
SOURCE → AGENT → SINK
  ↓                 ↑
  └─────liquidity───┘
```

- **SOURCE**: Sends "incoming settlements" (liquidity beats) at historically-observed times
- **AGENT**: The agent being evaluated with the test policy
- **SINK**: Receives AGENT's outgoing transactions (infinite capacity)

**Why this is correct**: Settlement timing is a "sufficient statistic" for the liquidity environment. The agent cannot observe the full market state, only when their payments settle. By preserving `settlement_offset` from historical data, resampled scenarios present statistically equivalent liquidity conditions.

See `docs/reference/ai_cash_mgmt/evaluation-methodology.md` for the full statistical argument.

---

## Your Assignment

### 1. Review Background Materials

Read these files carefully:
- `docs/plans/simcash-paper/v1/draft-paper.md` - Previous results (remember: these used Monte Carlo, not real bootstrap)
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Statistical foundations of new evaluation
- `experiments/castro/papers/castro_et_al.md` - The original paper we're replicating

### 2. Verify Experiment Configurations

The experiment configurations have already been updated for v2:
- `experiments/castro/experiments/exp1.yaml` - 50 samples, bootstrap mode
- `experiments/castro/experiments/exp2.yaml` - 50 samples, bootstrap mode
- `experiments/castro/experiments/exp3.yaml` - 50 samples, bootstrap mode

**Verify these settings before running:**
```yaml
evaluation:
  mode: bootstrap
  num_samples: 50
```

### 3. Run All Three Experiments

Run experiments using the CLI, always with verbose output:
```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml
```

Run the experiments one at a time. Always report back on progress from verbose logs as the simulation is running.

**Important**: These will take longer than v1 due to 50 bootstrap samples per evaluation. Monitor progress and capture all terminal output for your lab notes. NEVER change the LLM model! Always use the exact model specified in the experiment config, even if it takes a long time to get responses.

### 4. Analyze Results

For each experiment:

- [ ] Record final policy values with confidence intervals
- [ ] Compare to theoretical predictions from Castro et al.
- [ ] Document whether paired comparison shows statistically significant improvements
- [ ] Note any behavioral differences from v1 (new evaluation may produce different equilibria!)
- [ ] Use `experiment replay` and `replay` CLI tools for debugging if needed

**Key question**: With real bootstrap (paired comparison), do the LLM-discovered policies converge to the theoretical Nash equilibria?

### 5. Write v2 Documentation

Create your work in `docs/plans/simcash-paper/v2/`:

1. **`lab-notes.md`** - Detailed logs including:
   - Iteration-by-iteration results for each experiment
   - Bootstrap statistics (mean, std, CI) for each evaluation
   - Paired delta statistics (this is new in v2!)
   - Any anomalies observed

2. **`draft-paper.md`** - Updated paper with:
   - Results from real bootstrap evaluation
   - Confidence intervals on all reported values
   - Comparison of v1 (Monte Carlo) vs v2 (bootstrap) if results differ
   - Updated discrepancy analysis

---

## What's Different About Real Bootstrap

### Paired Comparison (NEW in v2)

The new system evaluates both policies on the **same** bootstrap samples:

```python
deltas = [
    cost(policy_A, sample_i) - cost(policy_B, sample_i)
    for i in range(N)
]
improvement = mean(deltas)
```

This eliminates transaction-to-transaction variance, making policy differences much clearer.

**Acceptance criterion**: Accept new policy if `mean(delta) > 0` (new policy is cheaper).

### Bootstrap Samples Come From Initial Simulation

1. The system runs ONE initial simulation with arrival configurations
2. Collects all transaction records with their `settlement_offset` (time to settle)
3. Resamples from this history for each bootstrap sample
4. Both policies are evaluated on the SAME resampled transactions

### What You Should See in Verbose Output

The verbose output now shows:
- Initial simulation results (Stream 1 for LLM)
- Bootstrap sample evaluation with paired deltas
- Best and worst samples identified

---

## Key Differences: v1 vs v2

| Aspect | v1 | v2 |
|--------|----|----|
| Bootstrap samples | 1-10 | 50 |
| Evaluation method | Monte Carlo (new txns) | Real bootstrap (resampled) |
| Paired comparison | No | Yes |
| Statistical power | Low | High |
| Confidence intervals | Not reported | Required |
| Sandbox architecture | Full simulation | 3-agent isolated |

---

## Expected Outcomes

With real bootstrap evaluation, you should observe:

1. **Lower variance in cost estimates** - paired comparison eliminates transaction noise
2. **Faster convergence** - clearer signal about which policy is better
3. **Potentially different equilibria** - v1 results had high noise, may have settled at local optima
4. **Tighter confidence intervals** - can distinguish smaller policy differences

---

## Questions to Answer in v2

1. **Do results change with real bootstrap?** The v1 equilibria (exp1: 0%/25%, exp2: 4%/1.35%, exp3: 21%/20.5%) may be different now that we're using proper paired comparison.

2. **Are paired deltas meaningful?** With sandbox evaluation, do the deltas correctly capture policy quality differences?

3. **How tight are confidence intervals?** Can we distinguish optimal from near-optimal policies?

4. **Do v2 results match Castro et al. theoretical predictions better than v1?**

---

## Replay and Audit Features

```bash
# List all experiments
.venv/bin/payment-sim experiment list

# Replay experiment output
.venv/bin/payment-sim experiment replay <experiment_id>

# Audit specific iteration (shows LLM prompts/responses)
.venv/bin/payment-sim experiment replay <experiment_id> --audit --start N --end N
```

See `docs/reference/cli/commands/experiment.md` for full CLI documentation.

---

## Output Location

All v2 work goes in: `docs/plans/simcash-paper/v2/`

Do NOT modify v1 files - they serve as the baseline for comparison.
