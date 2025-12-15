# SimCash Experiment Protocol

This document defines the protocol for running the Castro replication experiments.

---

## Overview

We run three experiments to replicate findings from Castro et al. (2025):

| Exp | Description | Mode | Expected Result |
|-----|-------------|------|-----------------|
| **exp1** | 2-Period Deterministic | deterministic | A=0%, B=20% (asymmetric) |
| **exp2** | 12-Period Stochastic | bootstrap | Both 10-30% |
| **exp3** | 3-Period Joint | deterministic | Both ~25% (symmetric) |

---

## Pre-Flight Checklist

Before running any experiment:

```bash
cd api

# 1. Ensure environment is set up
uv sync --extra dev

# 2. Verify CLI works
.venv/bin/payment-sim --help

# 3. Check experiment configs exist
ls ../experiments/castro/experiments/

# 4. Verify LLM API key is configured
echo $OPENAI_API_KEY | head -c 10  # Should show sk-...
```

---

## Phase 1: Sanity Check (Required First)

Run a truncated version of exp1 to verify the system works:

```bash
cd api

# Run exp1 with verbose output
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
```

**Expected behavior:**
- Experiment initializes without errors
- LLM calls succeed (watch for API errors)
- Iterations progress (you'll see iteration numbers)
- Results saved to `experiments/castro/results/exp1.db`

**If sanity check fails:**
- Check API key configuration
- Review error messages in output
- Verify config file syntax

---

## Phase 2: Full Experiment Runs

### Experiment 1: 2-Period Deterministic

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml 2>&1 | tee exp1_run.log
```

**Key parameters:**
- 2 ticks per day, 1 day
- Deterministic arrivals (no randomness)
- 25 max iterations
- Convergence threshold: 5%

**What to observe:**
- Initial policies start at some default
- Watch `initial_liquidity_fraction` evolve for both agents
- Expect asymmetric convergence (one agent ~ 0%, other ~ 20%)

**Capture run ID for later:**
```bash
# After run completes, find the run ID
.venv/bin/payment-sim experiment results
```

---

### Experiment 2: 12-Period Stochastic

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml 2>&1 | tee exp2_run.log
```

**Key parameters:**
- 12 ticks per day
- Bootstrap evaluation (50 samples)
- Poisson arrivals, LogNormal amounts
- 25 max iterations

**What to observe:**
- Bootstrap samples provide confidence intervals
- Higher variance in cost estimates (stochastic)
- Both agents should converge to 10-30% range

**Note:** This experiment takes longer due to bootstrap evaluation.

---

### Experiment 3: 3-Period Joint

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml 2>&1 | tee exp3_run.log
```

**Key parameters:**
- 3 ticks per day
- Symmetric payment demands (P^A = P^B = [0.2, 0.2, 0])
- Deterministic mode
- 25 max iterations

**What to observe:**
- Symmetric setup → expect symmetric equilibrium
- Both agents should converge to ~25%

---

## Phase 3: Results Collection

### List All Completed Runs

```bash
cd api
.venv/bin/payment-sim experiment results
```

This shows run IDs needed for replay and analysis.

### Replay an Experiment

```bash
# Standard replay (shows iteration summaries)
.venv/bin/payment-sim experiment replay <run-id>

# Replay with full LLM audit trail
.venv/bin/payment-sim experiment replay <run-id> --audit

# Replay specific iterations (e.g., iterations 1-5)
.venv/bin/payment-sim experiment replay <run-id> --audit --start 1 --end 5
```

### Export Policy Evolution (for Paper Appendices)

```bash
cd api

# Export full evolution with LLM prompts/responses
.venv/bin/payment-sim experiment policy-evolution <run-id> --llm > ../docs/plans/simcash-paper/appendices/exp1_policy_evolution.json

# Export specific agent
.venv/bin/payment-sim experiment policy-evolution <run-id> --agent BANK_A --llm > ../docs/plans/simcash-paper/appendices/exp1_bank_a.json
```

---

## Phase 4: Analysis & Comparison

### Record Final Policies

For each experiment, document:

| Experiment | Agent | Final `initial_liquidity_fraction` | Castro Prediction | Match? |
|------------|-------|-----------------------------------|-------------------|--------|
| exp1 | BANK_A | ___ | 0% | |
| exp1 | BANK_B | ___ | 20% | |
| exp2 | BANK_A | ___ | 10-30% | |
| exp2 | BANK_B | ___ | 10-30% | |
| exp3 | BANK_A | ___ | ~25% | |
| exp3 | BANK_B | ___ | ~25% | |

### Document Bootstrap Statistics (exp2)

For stochastic experiment:
- Mean cost per agent
- Standard deviation
- 95% confidence interval
- Number of bootstrap samples

### Capture Representative LLM Interaction

Use `--audit` to capture at least one full LLM prompt/response for the paper's methodology section:

```bash
# Capture iteration 5 of exp1 (mid-optimization)
.venv/bin/payment-sim experiment replay <exp1-run-id> --audit --start 5 --end 5 > exp1_iteration5_audit.txt
```

---

## Experiment Execution Order

**Recommended order:**

1. **exp2 first** - Stochastic case with bootstrap, most realistic scenario
2. **exp1 second** - Deterministic baseline, validates asymmetric equilibrium
3. **exp3 last** - Joint optimization, validates symmetric equilibrium

**Rationale:** Start with the most realistic scenario (stochastic arrivals), then validate edge cases.

---

## Troubleshooting

### LLM API Errors
- Check API key: `echo $OPENAI_API_KEY`
- Check rate limits (wait and retry)
- Review `max_retries` in config (default: 3)

### Convergence Issues
- Check `stability_threshold` (default: 0.05 = 5%)
- Review `stability_window` (default: 5 iterations)
- May need more iterations if not converging

### Policy Validation Failures
- LLM may generate invalid policies
- Check `max_retries` for retry behavior
- Review audit output to see what LLM returned

### Database Errors
- Ensure `results/` directory exists
- Check disk space
- Verify write permissions

---

## Output Artifacts

After running all experiments, you should have:

```
experiments/castro/results/
├── exp1.db              # Experiment 1 database
├── exp2.db              # Experiment 2 database
└── exp3.db              # Experiment 3 database

docs/plans/simcash-paper/
├── appendices/
│   ├── exp1_policy_evolution.json
│   ├── exp2_policy_evolution.json
│   └── exp3_policy_evolution.json
├── lab-notes.md         # Your detailed experiment log
└── draft-paper.md       # Paper with results
```

---

## Time Estimates

| Experiment | Iterations | Est. Time per Iteration | Total Est. |
|------------|------------|------------------------|------------|
| exp1 | 25 | 1-2 min | 25-50 min |
| exp2 | 25 | 3-5 min (bootstrap) | 75-125 min |
| exp3 | 25 | 1-2 min | 25-50 min |

**Total: ~2-4 hours** for all experiments

---

## Success Criteria

Experiments are successful if:

1. ✅ All three experiments complete without errors
2. ✅ Final policies are within reasonable range of Castro predictions
3. ✅ Policy evolution shows convergent behavior
4. ✅ Bootstrap confidence intervals are reasonable (exp2)
5. ✅ LLM audit captures show structured optimization process
6. ✅ All artifacts exported for paper appendices
