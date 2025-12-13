# SimCash Paper v2 - Handover Prompt

## Context

We are writing a draft paper to be shared with our collaborators who authored Castro et al. (2025). The paper demonstrates how SimCash can reproduce their three experiments on reinforcement learning for payment system policy optimization.

**v1 is complete** - see `docs/plans/simcash-paper/v1/` for:
- `draft-paper.md` - Complete draft with methodology, results, and analysis
- `lab-notes.md` - Detailed iteration logs from experiment runs
- `research-plan.md` - Original research methodology

**Your task**: Produce v2 with improved experimental rigor following the protocol in v1's Appendix D.

---

## Your Assignment

### 1. Review v1 Work

Read the following files carefully:
- `docs/plans/simcash-paper/v1/draft-paper.md` - especially **Appendix D: Recommended Protocol for Experiment Replication**
- `docs/plans/simcash-paper/v1/lab-notes.md` - understand how experiments were run
- `experiments/castro/papers/castro_et_al.md` - the original paper we're replicating

### 2. Update Experiment Configurations

Before running experiments, modify the configurations to follow the v2 protocol:

**For ALL experiments (exp1, exp2, exp3):**
- Set `num_samples: 50` (was 1 for exp1/exp3, 10 for exp2)
- Keep `mode: bootstrap` for all

The experiment files are:
- `experiments/castro/experiments/exp1.yaml`
- `experiments/castro/experiments/exp2.yaml`
- `experiments/castro/experiments/exp3.yaml`

### 3. Run All Three Experiments

Run experiments using the CLI:
```bash
cd api
.venv/bin/payment-sim experiment run ../experiments/castro/experiments/exp1.yaml
.venv/bin/payment-sim experiment run ../experiments/castro/experiments/exp2.yaml
.venv/bin/payment-sim experiment run ../experiments/castro/experiments/exp3.yaml
```

**Important**: These will take longer than v1 due to 50 bootstrap samples per evaluation. Monitor progress and capture all terminal output for your lab notes. NEVER change the LLM model! Always use the exact model specified in the experiment config, even if it takes a long time to get responses.

### 4. Analyze Results Following Protocol

For each experiment, following Appendix D.2's post-experiment checklist:

- [ ] Compute confidence intervals on final policy values
- [ ] Run parameter sweep to characterize cost landscape (optional but recommended)
- [ ] Compare to theoretical predictions (absolute gap in pp, relative error in %)
- [ ] Document discrepancies with hypotheses

### 5. Write v2 Documentation

Create your work in `docs/plans/simcash-paper/v2/`:

1. **`lab-notes.md`** - Detailed logs including:
   - Configuration changes made
   - Iteration-by-iteration results for each experiment
   - Bootstrap statistics (mean, std, CI) for each evaluation
   - Any anomalies observed

2. **`draft-paper.md`** - Updated paper with:
   - Results from 50-sample bootstrap evaluation
   - Confidence intervals on all reported values
   - Statistical significance testing where applicable
   - Updated discrepancy analysis based on new results
   - Any methodology refinements

3. **`research-plan.md`** - Your approach and any deviations from v1 protocol

---

## Key Differences from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Bootstrap samples (exp1) | 1 | 50 |
| Bootstrap samples (exp2) | 10 | 50 |
| Bootstrap samples (exp3) | 1 | 50 |
| Confidence intervals | Not reported | Required |
| Statistical tests | None | Paired t-test for improvements |

---

## Expected Outcomes

With 50 bootstrap samples, you should be able to:

1. **Report confidence intervals** on final policy values (e.g., "BANK_A: 21% ± 2%")
2. **Detect smaller improvements** - more samples = lower variance in cost estimates
3. **Validate v1 findings** - do the same equilibria emerge with more rigorous evaluation?
4. **Identify any v1 artifacts** - were any v1 results due to noise in small samples?

---

## Replay and Audit Features

You can replay experiment output using:
```bash
.venv/bin/payment-sim experiment replay <experiment_id>
```

Use `--audit` flag for full LLM prompt/response (verbose - use with `--start N --end N` for single iteration).

List experiments with:
```bash
.venv/bin/payment-sim experiment list
```

See `docs/reference/cli/commands/experiment.md` for full CLI documentation.

---

## Questions to Answer in v2

1. Do the v1 equilibria (exp1: 0%/25%, exp2: 4%/1.35%, exp3: 21%/20.5%) remain stable with 50-sample evaluation?
2. Are the confidence intervals tight enough to distinguish from theoretical predictions?
3. Does increased statistical rigor change any conclusions about discrepancies?
4. What is the computational cost increase (time, LLM calls) for the improved protocol?

---

## Output Location

All v2 work goes in: `docs/plans/simcash-paper/v2/`

Do NOT modify v1 files - they serve as the baseline for comparison.
