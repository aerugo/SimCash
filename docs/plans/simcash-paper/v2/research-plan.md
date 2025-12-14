# SimCash Paper v2 Research Plan

**Created**: 2025-12-14
**Author**: Claude (Opus 4.5)
**Status**: Complete

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
- [x] Run a quick sanity check (e.g., 1 iteration of exp1) to confirm system works

### Configuration Summary

All experiments use:
- **LLM Model**: openai:gpt-5.2 (as specified in configs - DO NOT CHANGE)
- **Temperature**: 0.5
- **Reasoning effort**: high
- **Max iterations**: 25
- **Bootstrap samples**: 50

---

## Phase 2: Experiment Execution

- [x] **Exp1** (2-period deterministic) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml`
  - Result: 15 iterations to convergence, BANK_A=15%, BANK_B=0%
  - Note: Role reversed from Castro prediction (asymmetric equilibrium found)

- [x] **Exp2** (12-period stochastic) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml`
  - Result: 8 iterations to convergence, BANK_A=0.8%, BANK_B=1.65%
  - Note: Risk-tolerant strategy discovered (<2% vs Castro's 10-30%)

- [x] **Exp3** (3-period joint optimization) - capture full verbose output
  - Command: `.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml`
  - Result: 8 iterations to convergence, BANK_A=25%, BANK_B=22%
  - Note: Near-exact match to Castro's ~25% prediction

- [x] Document any errors, anomalies, or unexpected behavior in lab notes

---

## Phase 3: Results Analysis

- [x] Extract final policy values for each experiment
- [x] Explore replay outputs of chosen iterations to understand LLM decision-making
- [x] For each experiment and each agent, compile complete history of policy changes
- [x] Compute confidence intervals from bootstrap samples
- [x] Compare to Castro et al. theoretical predictions
- [x] Analyze paired delta distributions (new in v2)

### Analysis Questions (Answered)

1. **Are paired deltas meaningful?** Yes - bootstrap paired comparison cleanly isolates policy quality differences
2. **How tight are confidence intervals?** Exp2 shows high variance ($316.68 std) due to risk-tolerant strategy
3. **Do results match Castro et al. theoretical predictions?** Exp3=yes, Exp1=yes (role reversed), Exp2=divergent
4. **How do v2 results compare to v1?** Consistent with v1 findings, minor variations due to stochasticity

---

## Phase 4: Paper Writing (Complete Rewrite)

- [x] **Abstract**: Rewritten with v2 results summary
- [x] **Introduction**: Updated with key contributions
- [x] **Methodology**: Documented bootstrap methodology and paired comparison
  - Scratched all references to Monte Carlo methods
  - Documented 3-agent sandbox architecture
  - Explained paired comparison statistical approach
- [x] **Results**: Complete rewrite with v2 results
  - Included confidence intervals for Exp2
  - Included paired delta analysis
  - No references to v1 results
- [x] **Discussion**: Interpreted differences to Castro et al. (especially Exp2 risk-tolerant strategy)
- [x] **Conclusion**: Complete rewrite with future work

---

## Phase 5: Figures & Tables

- [x] Scratch all old figures from v1
- [x] Create new figures showing:
  - [x] Final policy trees for each experiment (Appendix A.1)
  - [x] Mermaid diagrams of policy evolution (Appendix B)
  - [x] Plots of cost over iterations with confidence intervals (Appendix E)
  - [x] Bootstrap sample distributions (Appendix C)
  - [x] Paired delta distributions (Appendix C.3)
- [x] Additional figures:
  - [x] ASCII comparison charts (Appendix F.1, F.2, F.3)
  - [x] LLM reasoning examples (Appendix G)

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
