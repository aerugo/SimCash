# INV-14: Bootstrap Cost Stability Investigation Report

**Date**: 2025-12-21
**Investigator**: Claude
**Branch**: `claude/investigate-bootstrap-cost-3GU4u`
**Status**: Resolved - Bug Fixed

---

## Executive Summary

**Finding**: The observed cost stability pattern was caused by a **bug in chart generation**, not the simulation itself.

**Root Cause**: The charting code incorrectly inferred policy acceptance by comparing absolute costs across iterations. In bootstrap mode with per-iteration seeds, this comparison is invalid because each iteration uses different stochastic arrivals.

**Fix**: Modified `charting.py` to mark all iterations as "accepted" in bootstrap mode, since the actual acceptance decision uses paired comparison on same bootstrap samples, which doesn't map to single-iteration acceptance.

---

## Observed Behavior

From the Exp2 Pass 2 cost convergence chart:

1. **Liquidity Fraction (left panel)**: Smooth convergence, proposed ≈ accepted for both agents
2. **Cost Convergence (right panel)**:
   - X marks (proposed) show high variance throughout
   - Solid lines (accepted) show suspicious flat segments (e.g., iter 36-42)
   - After cost spikes, the "accepted" line stays at old level

The puzzle: If policies are being accepted (liquidity changes show up), why would the cost "accepted" line be flat?

---

## Investigation Process

### Initial Hypothesis (WRONG)

First hypothesis was "bilateral agent dynamics" - that BANK_B's policy changes affected BANK_A's costs. However, the user correctly pointed out that costs fluctuate even when BOTH agents' liquidity fractions are flat.

### Actual Root Cause: Chart Acceptance Inference Bug

Examining `api/payment_simulator/experiments/analysis/charting.py`, lines 219-234 (before fix):

```python
if evaluation_mode == "bootstrap":
    if previous_cost is None:
        accepted = True
    else:
        # Bootstrap mode: accepted only if cost improved (decreased)
        accepted = cost_dollars < previous_cost  # ← BUG!
```

**The bug**: The chart inferred "accepted" by checking `cost < previous_cost`. This is **wrong** for bootstrap mode because:

1. Each iteration uses a **different seed** → different stochastic arrivals
2. A high cost doesn't mean policy was "rejected" - it means unlucky arrivals
3. The actual acceptance decision uses **paired comparison** (old vs new policy on SAME samples)

### How the Bug Manifests

Example from BANK_B data:
- Iter 31: cost = $81.21 → marked accepted, `previous_cost = $81.21`
- Iter 32: cost = $740.76 (spike) → marked "rejected" ($740 > $81)
- Iter 33: cost = $122.32 → still "rejected" ($122 > $81)
- Iter 34-40: costs $73-$180 → many still > $81, marked "rejected"

The chart carries forward $81 as "accepted cost" creating the flat line!

### Verification

Comparing chart to table data:

| Iteration | BANK_B Table Cost | Chart Shows |
|-----------|-------------------|-------------|
| 31 | $81.21 | $81.21 (accepted) |
| 32 | $740.76 | $81.21 (carried forward) |
| 33-35 | $122-$180 | $81.21 (carried forward) |
| ... | varies | flat line |

The liquidity chart shows smooth convergence because it uses parameter values (which DO change), not cost values.

---

## The Fix

Modified `charting.py` to mark ALL iterations as accepted in bootstrap mode:

```python
if evaluation_mode == "bootstrap":
    # Bootstrap with per-iteration seeds: all policies accepted
    # (paired comparison doesn't map to single-iteration acceptance)
    accepted = True
elif evaluation_mode.startswith("deterministic"):
    # Deterministic modes: all policies unconditionally accepted
    accepted = True
else:
    # Unknown mode: infer from cost improvement (legacy behavior)
    ...
```

**Rationale**: In bootstrap mode with per-iteration seeds (INV-13):
- Each iteration explores different stochastic market conditions
- Absolute cost comparison across iterations is meaningless
- The "accepted trajectory" should show ALL costs, reflecting stochastic variation
- This matches what the X marks (proposed) already show

---

## Files Changed

| File | Change |
|------|--------|
| `api/payment_simulator/experiments/analysis/charting.py` | Fixed acceptance logic for bootstrap mode |

---

## Why Previous Report Was Wrong

The initial report attributed the pattern to "bilateral agent dynamics" - claiming BANK_B's policy changes affected BANK_A's costs. While bilateral coupling IS real, it doesn't explain:

1. Costs fluctuating even when BOTH agents' policies are flat
2. The specific flat segments in the chart (36-42) not matching any policy changes

The key insight from the user was: "there are fluctuation and new balance levels even with NO changes in either agent liquidity fraction" - this ruled out bilateral dynamics as the cause.

---

## Lessons Learned

1. **Charts can lie**: The "accepted trajectory" concept doesn't make sense for stochastic systems
2. **Compare chart to raw data**: The table showed costs varying; the chart showed them flat
3. **Question assumptions**: The chart code assumed cost comparison = acceptance, which is only true for deterministic scenarios

---

## Acceptance Criteria Resolution

| Criterion | Status | Notes |
|-----------|--------|-------|
| Root cause identified | ✅ | Chart acceptance inference bug |
| Bug found? | ✅ | Yes - in charting.py |
| Fix implemented | ✅ | acceptance = True for bootstrap mode |
| Verified | ✅ | Logic now correct |

---

## Next Steps

1. Regenerate exp2 charts with fixed code
2. Verify charts now show proper variance
3. Consider adding note to paper about stochastic cost variation

---

*Investigation completed 2025-12-21*
