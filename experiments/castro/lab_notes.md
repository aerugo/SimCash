# Castro Experiments - Laboratory Notebook

**Principal Investigator:** AI Research Assistant
**Date Started:** 2025-12-09
**Model Used:** gpt-5.1 (OpenAI, high reasoning effort)
**Branch:** claude/castro-experiments-0193F3V6ULV1G99rG1K62nXh

---

## Study Overview

### Objective
Replicate and evaluate Castro et al. (2025) experiments on LLM-based policy optimization for high-value payment system (HVPS) liquidity management.

### Reference
Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"

### Hypotheses Under Test

| ID | Hypothesis | Experiment |
|----|------------|------------|
| H1 | Nash Equilibrium Convergence | exp1 |
| H2 | Liquidity-Delay Tradeoff Learning | exp2 |
| H3 | Joint Policy Optimization | exp3 |

---

## Experimental Protocol

### Phase 1: Environment Verification
- [ ] Confirm OpenAI API key availability
- [ ] Verify castro module installation
- [ ] Validate experiment configurations
- [ ] Test model availability (gpt-5.1)

### Phase 2: Experiment Execution
- [ ] Run exp1 (2-period deterministic)
- [ ] Run exp2 (12-period stochastic)
- [ ] Run exp3 (joint optimization)

### Phase 3: Analysis
- [ ] Extract metrics from DuckDB
- [ ] Generate visualization charts
- [ ] Evaluate against hypotheses
- [ ] Document anomalies

---

## Session Log

### Entry 1: Setup and Configuration Review
**Time:** 2025-12-09 (Session Start)

**Environment Check:**
- Working directory: /home/user/SimCash/experiments/castro
- OpenAI API key: CONFIRMED (164 characters)
- Model: gpt-5.1 with high reasoning effort

**Configuration Review:**

| Experiment | Ticks/Day | Samples | Max Iter | Description |
|------------|-----------|---------|----------|-------------|
| exp1 | 2 | 1 | 25 | Deterministic Nash equilibrium |
| exp2 | 12 | 10 | 25 | Stochastic LVTS-style |
| exp3 | 3 | 10 | 25 | Joint optimization |

**Cost Rate Parameters (exp1):**
- Collateral cost: 500 bps/day (r_c)
- Delay cost: 0.1 cents/tick/cent (r_d = 0.001)
- Overdraft: 2000 bps/tick (r_b) - punitive
- Cost ordering: r_c < r_d < r_b (as per Castro paper)

**Expected Outcomes (exp1 - Nash Equilibrium):**
- Bank A: initial_liquidity_fraction = 0.0 (posts 0 collateral)
- Bank B: initial_liquidity_fraction = 0.20 (posts 20,000 collateral)
- Bank A cost: ~$0.00
- Bank B cost: ~$20.00

**Transaction Schedule (exp1):**
```
Tick 0: B -> A: $150.00 (deadline: tick 1)
Tick 1: A -> B: $150.00 (deadline: tick 2)
Tick 1: B -> A: $50.00 (deadline: tick 2)
```

---

## Experiment Runs

### [PENDING] Experiment 1: 2-Period Deterministic Nash Equilibrium
**Start Time:** TBD
**Command:** `uv run castro run exp1 --model gpt-5.1`
**Status:** Not yet started

### [PENDING] Experiment 2: 12-Period Stochastic LVTS-Style
**Start Time:** TBD
**Command:** `uv run castro run exp2 --model gpt-5.1`
**Status:** Not yet started

### [PENDING] Experiment 3: Joint Optimization
**Start Time:** TBD
**Command:** `uv run castro run exp3 --model gpt-5.1`
**Status:** Not yet started

---

## Observations and Notes

### Pre-Run Notes
1. The llm_client.py already has special handling for gpt-5.1:
   - Sets `reasoning_effort = "high"`
   - Sets `max_completion_tokens = 16384` for verbose output
2. Deferred crediting is enabled (Castro paper requirement)
3. LSM is disabled for all experiments (pure Castro model)

### Potential Issues to Monitor
- LLM response parsing (markdown code blocks)
- Policy validation against CASTRO_CONSTRAINTS
- Convergence detection stability
- Monte Carlo variance in exp2/exp3

---

## Appendix: Raw Command Outputs

*Outputs will be appended as experiments are run*

---

**Last Updated:** 2025-12-09 (Session Start)
