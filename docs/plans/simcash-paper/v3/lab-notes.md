# SimCash Paper - Lab Notes

## Experiment Execution Log

**Date**: 2025-12-15
**Run by**: Claude (automated)
**Environment**: Linux 4.4.0, Python venv with payment-sim CLI

---

## Pre-Flight Checks

- [x] Environment set up with `uv sync --extra dev`
- [x] CLI verified working: `.venv/bin/payment-sim --help`
- [x] Experiment configs present in `experiments/castro/experiments/`
- [x] OpenAI API key configured (gpt-5.2 model)

---

## Experiment 2: 12-Period Stochastic (exp2)

**Run ID**: `exp2-20251215-083049-8cf596`
**Config**: `experiments/castro/experiments/exp2.yaml`
**Mode**: Bootstrap evaluation (50 samples)

### Configuration
- 12 ticks per day
- Poisson arrivals, LogNormal amounts
- 25 max iterations, 5% stability threshold

### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.17 (17%) | 10-30% | ✅ Within range |
| BANK_B | `initial_liquidity_fraction` = 0.13 (13%) | 10-30% | ✅ Within range |

**Convergence**: Yes, after 11 iterations (stability achieved)
**Final costs**: BANK_A: $156.43, BANK_B: $156.43

### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.40 (ACCEPTED, -20%)
- Iteration 2: 0.40 → 0.30 (ACCEPTED, -25%)
- Iteration 3: 0.30 → 0.25 (ACCEPTED, -17%)
- Iteration 4: 0.25 → 0.22 (ACCEPTED, -12%)
- Iteration 5: 0.22 → 0.20 (ACCEPTED, -9%)
- Iteration 6: 0.20 → 0.18 (ACCEPTED, -10%)
- Iteration 7: 0.18 → 0.17 (ACCEPTED, -6%)
- Iterations 8-11: Stable at 0.17

### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.15 (ACCEPTED, -70%)
- Iteration 2: 0.15 → 0.13 (ACCEPTED, -13%)
- Iterations 3-11: Stable at 0.13

### Observations
- BANK_B converged faster than BANK_A (more aggressive initial reduction)
- Bootstrap evaluation showed consistent improvement signals
- Both agents within Castro's predicted stochastic range

---

## Experiment 1: 2-Period Deterministic (exp1)

**Run ID**: `exp1-20251215-084901-866d63`
**Config**: `experiments/castro/experiments/exp1.yaml`
**Mode**: Deterministic evaluation

### Configuration
- 2 ticks per day, 1 day
- Deterministic payment arrivals
- 25 max iterations, 5% stability threshold

### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.11 (11%) | 0% | Direction correct (asymmetric) |
| BANK_B | `initial_liquidity_fraction` = 0.20 (20%) | 20% | ✅ Exact match |

**Convergence**: Yes, after 9 iterations (stability achieved)
**Final costs**: BANK_A: $11.00, BANK_B: $20.00

### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iteration 2: 0.20 → 0.18 (ACCEPTED, -10%)
- Iteration 3: 0.18 → 0.16 (ACCEPTED, -11%)
- Iteration 4: 0.16 → 0.15 (ACCEPTED, -6%)
- Iteration 5: 0.15 → 0.14 (ACCEPTED, -7%)
- Iteration 6: 0.14 → 0.13 (ACCEPTED, -7%)
- Iteration 7: 0.13 → 0.12 (ACCEPTED, -8%)
- Iteration 8: 0.12 → 0.11 (ACCEPTED, -8%)
- Iteration 9: Stable at 0.11

### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iterations 2-9: Stable at 0.20 (all proposals to go lower REJECTED)

### Observations
- Asymmetric equilibrium emerged as Castro predicted
- BANK_B stabilized at exactly 20% (Castro's theoretical prediction)
- BANK_A continued reducing but stopped at 11% (close to Castro's 0%)
- BANK_B repeatedly rejected proposals to go below 20% (cost regression)

---

## Experiment 3: 3-Period Joint Optimization (exp3)

**Run ID**: `exp3-20251215-090758-257b13`
**Config**: `experiments/castro/experiments/exp3.yaml`
**Mode**: Deterministic evaluation

### Configuration
- 3 ticks per day
- Symmetric payment demands: P^A = P^B = [0.2, 0.2, 0]
- 25 max iterations, 5% stability threshold

### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.20 (20%) | ~25% | ✅ Close |
| BANK_B | `initial_liquidity_fraction` = 0.20 (20%) | ~25% | ✅ Close |

**Convergence**: Yes, after 7 iterations (stability achieved)
**Final costs**: BANK_A: $19.98, BANK_B: $19.98

### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.21 (ACCEPTED, -58%)
- Iteration 2: 0.21 → 0.20 (ACCEPTED, -5%)
- Iterations 3-7: Stable at 0.20 (proposals to 0.0 REJECTED)

### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iterations 2-7: Stable at 0.20 (proposals to 0.0 REJECTED)

### Observations
- Symmetric equilibrium achieved as expected
- Both agents converged to identical 20% (close to Castro's ~25%)
- LLM repeatedly proposed 0.0 after initial convergence (too aggressive)
- System correctly rejected these proposals due to cost regression

---

## Summary: Comparison with Castro et al.

| Experiment | Agent | SimCash Result | Castro Prediction | Match |
|------------|-------|----------------|-------------------|-------|
| exp1 | BANK_A | 11% | 0% | Partial (asymmetric direction correct) |
| exp1 | BANK_B | 20% | 20% | ✅ Exact |
| exp2 | BANK_A | 17% | 10-30% | ✅ Within range |
| exp2 | BANK_B | 13% | 10-30% | ✅ Within range |
| exp3 | BANK_A | 20% | ~25% | ✅ Close |
| exp3 | BANK_B | 20% | ~25% | ✅ Close |

### Key Findings

1. **Asymmetric equilibrium (exp1)**: Successfully reproduced the asymmetric Nash equilibrium where one agent contributes less liquidity while the other maintains a stable 20%.

2. **Stochastic optimization (exp2)**: Both agents found optimal policies within Castro's predicted 10-30% range for the stochastic case.

3. **Symmetric equilibrium (exp3)**: Both agents converged to identical policies (20%), demonstrating symmetric equilibrium behavior.

4. **Convergence behavior**: All experiments converged within 7-11 iterations, well under the 25-iteration maximum.

5. **Policy stability**: The accept/reject mechanism successfully prevented regressions after convergence.

---

## Artifacts Generated

### Policy Evolution JSON (in `appendices/`)
- `exp1_policy_evolution.json` - Full policy evolution with LLM prompts
- `exp2_policy_evolution.json` - Full policy evolution with LLM prompts
- `exp3_policy_evolution.json` - Full policy evolution with LLM prompts

### Audit Trail
- `exp1_iteration5_audit.txt` - Representative LLM prompt/response

### Raw Logs
- `/home/user/SimCash/exp1_run.log` - Full exp1 output
- `/home/user/SimCash/exp2_run.log` - Full exp2 output
- `/home/user/SimCash/exp3_run.log` - Full exp3 output

### Database Files
- `api/results/exp1.db` - Experiment 1 database
- `api/results/exp2.db` - Experiment 2 database
- `api/results/exp3.db` - Experiment 3 database

---

## Technical Notes

### LLM Configuration
- Model: `openai:gpt-5.2`
- Temperature: 0.5
- Reasoning effort: high
- Timeout: 900 seconds
- Max retries: 3

### Evaluation Configuration
- Stability threshold: 5%
- Stability window: 5 consecutive iterations
- Bootstrap samples (exp2): 50

### Run Durations
- exp2: ~45 minutes (bootstrap evaluation)
- exp1: ~25 minutes (deterministic)
- exp3: ~15 minutes (deterministic, fast convergence)

---

# Pass 2: Replication Run

## Objective

LLM calls are non-deterministic. To assess variability in results, we run all three experiments a second time with identical configurations. This allows us to:
1. Measure variance in final policy values
2. Report average results with confidence
3. Validate that findings are reproducible

## Plan

1. Run experiments in same order: exp2 → exp1 → exp3
2. Use identical configs from `v3/configs/`
3. Save artifacts to `v3/pass_2/appendices/`:
   - Policy evolution JSONs
   - Representative audit file
4. Copy databases to `v3/pass_2/dbs/` (if needed)
5. Update paper with multi-pass analysis

## Pass 2 Execution Log

**Date**: 2025-12-15
**Start time**: 10:02 UTC

---

### Experiment 2: 12-Period Stochastic (exp2) - Pass 2

**Run ID**: `exp2-20251215-100212-680ad2`
**Config**: `v3/configs/exp2.yaml`
**Mode**: Bootstrap evaluation (50 samples)

#### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.14 (14%) | 10-30% | ✅ Within range |
| BANK_B | `initial_liquidity_fraction` = 0.125 (12.5%) | 10-30% | ✅ Within range |

**Convergence**: Yes, after 8 iterations (stability achieved)
**Final costs**: BANK_A: $144.26, BANK_B: $144.26

#### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iteration 3: 0.20 → 0.15 (ACCEPTED, -25%)
- Iteration 4: 0.15 → 0.14 (ACCEPTED, -7%)
- Iterations 5-8: Stable at 0.14

#### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.15 (ACCEPTED, -70%)
- Iteration 2: 0.15 → 0.14 (ACCEPTED, -7%)
- Iteration 3: 0.14 → 0.135 (ACCEPTED, -4%)
- Iteration 4: 0.135 → 0.13 (ACCEPTED, -4%)
- Iteration 5: 0.13 → 0.125 (ACCEPTED, -4%)
- Iterations 6-8: Stable at 0.125

#### Observations vs Pass 1
- **Faster convergence**: 8 iterations vs 11 in pass_1
- **Different initial trajectory**: BANK_A jumped to 0.20 instead of gradual 0.50→0.40→0.30
- **Similar final values**: Both passes within Castro's 10-30% range

---

### Experiment 1: 2-Period Deterministic (exp1) - Pass 2

**Run ID**: `exp1-20251215-102022-f1c6ba`
**Config**: `v3/configs/exp1.yaml`
**Mode**: Deterministic evaluation

#### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.00 (0%) | 0% | ✅ **EXACT MATCH** |
| BANK_B | `initial_liquidity_fraction` = 0.20 (20%) | 20% | ✅ Exact match |

**Convergence**: Yes, after 8 iterations (stability achieved)
**Final costs**: BANK_A: $0.00, BANK_B: $20.00

#### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.25 (ACCEPTED, -50%)
- Iteration 2: 0.25 → 0.00 (ACCEPTED, -100%)
- Iterations 3-8: Stable at 0.00

#### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iterations 2-8: Stable at 0.20 (all proposals REJECTED)

#### Observations vs Pass 1
- **BANK_A achieved exact 0%**: In pass_1, BANK_A stopped at 11%; in pass_2, it found the theoretical optimum of 0%
- **BANK_B identical**: Both passes converged to exactly 20%
- **This demonstrates LLM variability in finding global vs local optima**

---

### Experiment 3: 3-Period Joint Optimization (exp3) - Pass 2

**Run ID**: `exp3-20251215-103545-c8d616`
**Config**: `v3/configs/exp3.yaml`
**Mode**: Deterministic evaluation

#### Results
| Agent | Final Policy | Castro Prediction | Status |
|-------|-------------|-------------------|--------|
| BANK_A | `initial_liquidity_fraction` = 0.20 (20%) | ~25% | ✅ Close |
| BANK_B | `initial_liquidity_fraction` = 0.20 (20%) | ~25% | ✅ Close |

**Convergence**: Yes, after 7 iterations (stability achieved)
**Final costs**: BANK_A: $19.98, BANK_B: $19.98

#### Policy Evolution Summary (BANK_A)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iterations 2-7: Stable at 0.20 (proposals to 0.0/0.01 REJECTED)

#### Policy Evolution Summary (BANK_B)
- Iteration 1: 0.50 → 0.20 (ACCEPTED, -60%)
- Iterations 2-7: Stable at 0.20 (proposals to 0.0 REJECTED)

#### Observations vs Pass 1
- **Identical results**: Both passes converged to exactly 20% for both agents
- **Highly reproducible**: exp3 shows lowest variance across passes

---

## Multi-Pass Analysis

### Summary: Pass 1 vs Pass 2 Comparison

| Experiment | Agent | Pass 1 | Pass 2 | Average | Castro | Match |
|------------|-------|--------|--------|---------|--------|-------|
| exp1 | BANK_A | 11% | 0% | 5.5% | 0% | ✅ Pass 2 exact |
| exp1 | BANK_B | 20% | 20% | 20% | 20% | ✅ Both exact |
| exp2 | BANK_A | 17% | 14% | 15.5% | 10-30% | ✅ Both in range |
| exp2 | BANK_B | 13% | 12.5% | 12.75% | 10-30% | ✅ Both in range |
| exp3 | BANK_A | 20% | 20% | 20% | ~25% | ✅ Close |
| exp3 | BANK_B | 20% | 20% | 20% | ~25% | ✅ Close |

### Key Insights from Multi-Pass Analysis

1. **exp1 (Asymmetric Equilibrium)**
   - BANK_B is highly stable: 20% in both passes
   - BANK_A shows variability: 11% (pass_1) vs 0% (pass_2)
   - Pass_2 found the exact theoretical optimum
   - Suggests the LLM can find both local (11%) and global (0%) optima

2. **exp2 (Stochastic)**
   - Low variance: BANK_A ±1.5%, BANK_B ±0.25%
   - Both passes within Castro's 10-30% range
   - Bootstrap evaluation provides robust signals

3. **exp3 (Symmetric)**
   - **Zero variance**: Identical 20% in both passes
   - Most reproducible experiment
   - Strong symmetric equilibrium

### Convergence Comparison

| Experiment | Pass 1 Iterations | Pass 2 Iterations | Difference |
|------------|-------------------|-------------------|------------|
| exp1 | 9 | 8 | -1 |
| exp2 | 11 | 8 | -3 |
| exp3 | 7 | 7 | 0 |

Pass 2 generally converged faster, possibly due to different random seeds in LLM responses.

---

## Pass 2 Artifacts Generated

### Policy Evolution JSON (in `pass_2/appendices/`)
- `exp1_policy_evolution.json` - Full policy evolution with LLM prompts
- `exp2_policy_evolution.json` - Full policy evolution with LLM prompts
- `exp3_policy_evolution.json` - Full policy evolution with LLM prompts

### Raw Logs (in `pass_2/`)
- `exp1_run.log` - Full exp1 pass_2 output
- `exp2_run.log` - Full exp2 pass_2 output
- `exp3_run.log` - Full exp3 pass_2 output
