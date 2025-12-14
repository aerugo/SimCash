# SimCash Paper v2 Research Plan

**Created**: 2025-12-14
**Author**: Claude (Opus 4.5)
**Status**: In Progress

## Overview

This document outlines the research plan for producing v2 of the SimCash paper demonstrating replication of Castro et al. (2025) experiments. The key change from v1 is the implementation of **real bootstrap evaluation** with paired comparison, replacing the parametric Monte Carlo approach used in v1.

### Key Methodological Changes (v1 → v2)

| Aspect | v1 (Monte Carlo) | v2 (Real Bootstrap) |
|--------|------------------|---------------------|
| Transaction generation | New random transactions each sample | Resampled from historical data |
| Paired comparison | Not possible | Enabled (same transactions for both policies) |
| Evaluation architecture | Full simulation per sample | 3-agent sandbox (SOURCE→AGENT→SINK) |
| Statistical efficiency | Low (high variance) | High (variance from policy differences only) |
| Sample size | 10 samples | 50 samples |

---

## Phase 1: Setup & Verification

- [x] Review v1 results and methodology
  - Read `docs/plans/simcash-paper/v1/draft-paper.md`
  - Read `docs/plans/simcash-paper/v1/lab-notes.md`
- [x] Read evaluation methodology documentation
  - Read `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
- [x] Verify experiment configurations are correct
  - Checked `experiments/castro/experiments/exp1.yaml`
  - Checked `experiments/castro/experiments/exp2.yaml`
  - Checked `experiments/castro/experiments/exp3.yaml`
- [ ] Run a quick sanity check (e.g., 1 iteration of exp1) to confirm system works

### Configuration Summary

All experiments use:
- **LLM Model**: openai:gpt-5.2 (as specified in configs - DO NOT CHANGE)
- **Temperature**: 0.5
- **Reasoning effort**: high
- **Max iterations**: 25
- **Bootstrap samples**: 50

---

## Phase 2: Experiment Execution

- [ ] **Exp1** (2-period deterministic) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml`
  - Expected: ~7 iterations to convergence
  - Target: BANK_A → 0%, BANK_B → 20% (Castro prediction)

- [ ] **Exp2** (12-period stochastic) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml`
  - Expected: ~10 iterations to convergence
  - Target: Both agents reduce liquidity, within 10-30% bands (Castro empirical)

- [ ] **Exp3** (3-period joint optimization) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml`
  - Expected: ~12 iterations to convergence
  - Target: Both agents → ~25% liquidity (Castro prediction when r_c < r_d)

- [ ] Document any errors, anomalies, or unexpected behavior in lab notes

---

## Phase 3: Results Analysis

- [ ] Extract final policy values for each experiment
- [ ] Explore replay outputs of chosen iterations to understand LLM decision-making
- [ ] For each experiment and each agent, compile complete history of policy changes
- [ ] Compute confidence intervals from bootstrap samples
- [ ] Compare to Castro et al. theoretical predictions
- [ ] Analyze paired delta distributions (new in v2)

### Analysis Questions

1. **Are paired deltas meaningful?** With sandbox evaluation, do the deltas correctly capture policy quality differences?
2. **How tight are confidence intervals?** Can we distinguish optimal from near-optimal policies?
3. **Do results match Castro et al. theoretical predictions?**
4. **How do v2 results compare to v1?** (for reference, not for paper inclusion)

---

## Phase 4: Paper Writing (Complete Rewrite)

- [ ] **Abstract**: Rewrite, keeping some elements from v1
- [ ] **Introduction**: Keep from v1, minor updates if needed
- [ ] **Methodology**: Document bootstrap methodology (exp2) and deterministic policy evaluation (exp1 & exp3)
  - Scratch all references to Monte Carlo methods
  - Document 3-agent sandbox architecture
  - Explain paired comparison statistical approach
- [ ] **Results**: Rewrite completely with v2 results
  - Include confidence intervals
  - Include paired delta analysis
  - No references to v1 results
- [ ] **Discussion**: Interpret differences to Castro et al.
- [ ] **Conclusion**: Complete rewrite

---

## Phase 5: Figures & Tables

- [ ] Scratch all old figures from v1
- [ ] Create new figures showing:
  - [ ] Final policy trees for each experiment
  - [ ] Mermaid diagrams of policy evolution
  - [ ] Plots of cost over iterations with confidence intervals
  - [ ] Bootstrap sample distributions (histograms)
  - [ ] Paired delta distributions
- [ ] Suggest additional figures drawing on Castro et al. for inspiration

---

## Protocol Notes

### Experiment Execution Protocol

1. **Command format**: Always run from `api/` directory with verbose flag
   ```bash
   cd /home/user/SimCash/api
   .venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/expN.yaml
   ```

2. **Output capture**: All terminal output will be recorded in lab-notes.md

3. **Progress monitoring**: Report on iteration progress, policy proposals, and cost reductions as they occur

### Recording Protocol

1. **lab-notes.md**: Raw data, iteration-by-iteration results, anomalies, verbose output excerpts
2. **draft-paper.md**: Polished prose, final results, tables, figures

### Failure Handling Protocol

1. **LLM timeouts**: Wait for retry (max_retries: 3 in config)
2. **Experiment crashes**: Document error, check logs, retry once
3. **Divergent results**: Document in lab notes, investigate with replay tool
4. **Invalid policy proposals**: Let the system handle (has validation)

### Figure Generation Protocol

1. **Policy trees**: Mermaid diagrams in markdown
2. **Cost plots**: Describe data for external plotting tool or inline ASCII
3. **Tables**: Markdown tables with results

---

## Expected Deliverables

By completion of this research plan:

1. `docs/plans/simcash-paper/v2/research-plan.md` - This document (updated with completion status)
2. `docs/plans/simcash-paper/v2/lab-notes.md` - Detailed experiment logs and raw data
3. `docs/plans/simcash-paper/v2/draft-paper.md` - Complete v2 paper draft

---

## Timeline Notes

**Important**: No time estimates. Work proceeds phase by phase until complete.

Experiments will be run sequentially (exp1 → exp2 → exp3) to allow for learning and adjustment between experiments if needed.
