# SimCash Paper v2 - Research Plan

## Objective

Replicate the v1 experiments with improved statistical rigor by following the protocol established in v1 Appendix D.

## Key Changes from v1

| Aspect | v1 | v2 |
|--------|----|----|
| Bootstrap samples (exp1) | 1 (deterministic) | 50 |
| Bootstrap samples (exp2) | 10 | 50 |
| Bootstrap samples (exp3) | 1 (deterministic) | 50 |
| Evaluation mode | Mixed (deterministic/bootstrap) | All bootstrap |
| Confidence intervals | Not reported | Required |
| Statistical tests | None | Paired t-test for improvements |

## Configuration Changes Made

All three experiment files updated:
- `experiments/castro/experiments/exp1.yaml`: `mode: bootstrap`, `num_samples: 50`
- `experiments/castro/experiments/exp2.yaml`: `mode: bootstrap`, `num_samples: 50`
- `experiments/castro/experiments/exp3.yaml`: `mode: bootstrap`, `num_samples: 50`

**LLM Configuration (unchanged):**
- Model: `openai:gpt-5.2`
- Temperature: 0.5
- Reasoning effort: high
- Timeout: 900 seconds

## Experimental Protocol

### For Each Experiment:

1. **Run with verbose output** to capture all iteration details
2. **Log all policy proposals** (accepted and rejected)
3. **Record bootstrap statistics** for each evaluation:
   - Mean cost
   - Standard deviation
   - Confidence interval (95%)
4. **Track convergence** with stability window of 5 iterations

### Post-Experiment Analysis:

Following Appendix D.2 checklist:
- [ ] Compute confidence intervals on final policy values
- [ ] Compare to theoretical predictions (absolute gap in pp, relative error in %)
- [ ] Document discrepancies with hypotheses
- [ ] Record computational costs (time, LLM calls)

## Expected Outcomes

With 50 bootstrap samples, we expect:

1. **Tighter confidence intervals** - SE reduced by factor of ~2.2 vs n=10
2. **More reliable policy comparisons** - smaller variance in cost estimates
3. **Validation of v1 equilibria** - do the same values emerge?
4. **Detection of any v1 artifacts** - were results due to noise?

## v1 Baseline Results (for comparison)

| Experiment | Agent | v1 Result | Paper Prediction |
|------------|-------|-----------|------------------|
| exp1 | BANK_A | 0% | 0% |
| exp1 | BANK_B | 25% | 20% |
| exp2 | BANK_A | 4% | ~10-30% band |
| exp2 | BANK_B | 1.35% | ~10-30% band |
| exp3 | BANK_A | 21% | ~25% |
| exp3 | BANK_B | 20.5% | ~25% |

## Timeline

1. Run exp1 (~7-12 iterations expected, ~15-30 min per iteration with 50 samples)
2. Run exp2 (~10 iterations expected, similar timing)
3. Run exp3 (~12 iterations expected, similar timing)
4. Analyze all results
5. Write lab notes and draft paper

## Questions to Answer

1. Do the v1 equilibria remain stable with 50-sample evaluation?
2. Are the confidence intervals tight enough to distinguish from theoretical predictions?
3. Does increased statistical rigor change any conclusions about discrepancies?
4. What is the computational cost increase?

---

*Date: 2025-12-13*
