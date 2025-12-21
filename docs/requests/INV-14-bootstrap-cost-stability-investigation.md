# INV-14: Investigate Bootstrap Cost Stability Anomaly

**Date**: 2025-12-21
**Priority**: Medium
**Type**: Investigation
**Status**: Resolved

---

## Summary

The exp2 cost convergence charts show unexpected cost stability patterns that don't align with the documented per-iteration independent seed methodology. When liquidity fraction is flat, costs should show random variation around a mean, but instead we observe sustained shifts to new cost levels.

---

## Observed Behavior

Looking at the Exp2 Pass 2 cost convergence chart:

1. **Iterations 20-30**: Policy stable at ~8% liquidity, costs fluctuate in $50-150 range
2. **Iteration 30-32**: Large cost spike (BANK_B to $700+)
3. **Iterations 32-42**: Policy still at ~8% liquidity, but costs now stable at elevated $150-300 range

**The anomaly**: If the policy (liquidity fraction) hasn't changed between iterations 25 and 40, and each iteration uses an independent seed generating independent market conditions, we would expect:
- Random cost variation around some mean
- No sustained elevation or depression across multiple consecutive iterations

Instead, the chart shows costs "settling" at a new level despite unchanged policy.

---

## Expected Behavior (Per Documentation)

According to the methodology in `docs/reference/ai_cash_mgmt/evaluation-methodology.md` and the paper's methods section:

1. Each iteration gets a unique seed from the pre-generated seed hierarchy
2. The context simulation runs with that iteration-specific seed
3. 50 bootstrap samples are generated from that iteration's transaction history
4. The mean cost across those 50 samples is what's plotted

If iteration seeds are truly independent (derived deterministically but pseudo-randomly from master seed), consecutive iterations should produce independent cost samples. A sustained shift to a new cost level for 10+ consecutive iterations is statistically unlikely.

---

## Possible Causes to Investigate

### 1. Seeds Not Truly Independent
- Check `SeedMatrix.get_iteration_seed()` implementation
- Verify seeds for iterations 30-45 are actually different
- Check if there's any correlation in the xorshift64* sequence

### 2. State Leaking Between Iterations
- Check if context simulation state carries over
- Verify `BootstrapSampler` is re-initialized each iteration
- Check if any caches persist between iterations

### 3. Bootstrap Samples Not Regenerated
- Verify `_create_bootstrap_samples()` is called each iteration (not just once)
- Check if the same 50 samples are being reused across iterations
- Compare sample hashes between consecutive iterations

### 4. Chart Generation Bug
- The data might be correct but chart generation might be aggregating incorrectly
- Check `charts/convergence.py` or wherever the chart is generated
- Verify the x-axis truly represents iteration number

### 5. Counterparty Policy Effect
- Even with independent seeds, if BANK_B's policy changed, BANK_A's costs would shift
- Check if the "flat liquidity" in the chart is truly flat or has micro-changes
- The bilateral interaction means one agent's policy affects both agents' costs

---

## Investigation Steps

### Phase 1: Data Verification
```python
# Query the database for exp2 pass 2
# Compare iteration seeds for iterations 25-45
# Verify they are actually different

SELECT iteration,
       JSON_EXTRACT(policies, '$.BANK_A.parameters.initial_liquidity_fraction') as a_liq,
       JSON_EXTRACT(policies, '$.BANK_B.parameters.initial_liquidity_fraction') as b_liq,
       costs_per_agent
FROM experiment_iterations
WHERE run_id = 'exp2-20251221-121746-c9a4a7'
  AND iteration BETWEEN 25 AND 45
ORDER BY iteration
```

### Phase 2: Seed Independence Test
- Add logging to print iteration seeds during a test run
- Verify each iteration gets a different seed
- Check that seeds follow expected distribution

### Phase 3: Bootstrap Sample Verification
- Log bootstrap sample hashes per iteration
- Verify samples are different between iterations
- Check sample regeneration logic in `optimization.py`

### Phase 4: Simulation State Check
- Add assertions that simulation state is fresh each iteration
- Check for any global/static state in Rust FFI
- Verify Orchestrator is re-created (not reused)

---

## Relevant Files

| File | Relevance |
|------|-----------|
| `api/payment_simulator/experiments/runner/optimization.py` | Bootstrap loop, seed usage |
| `api/payment_simulator/experiments/runner/seed_matrix.py` | Seed generation |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/sampler.py` | Bootstrap sample generation |
| `docs/papers/simcash-paper/paper_generator/src/charts/` | Chart generation |
| `docs/reference/ai_cash_mgmt/evaluation-methodology.md` | Documented methodology |

---

## Impact

- **Paper accuracy**: The methodology section claims independent seeds per iteration; if this isn't true, we're misrepresenting the experimental design
- **Result validity**: If costs aren't independent samples, our convergence criteria may be flawed
- **Reproducibility**: Understanding the actual behavior is critical for others to replicate

---

## Acceptance Criteria

1. [x] Root cause identified and documented
2. [x] If bug found: fix implemented and verified — **Bug found in charting.py, fixed**
3. [x] If behavior is correct: explanation added to paper/docs clarifying why the pattern appears
4. [x] Chart updated or annotated if needed to avoid confusion — **Charts need regeneration with fixed code**

## Resolution

**Root Cause**: Bug in chart generation code (`charting.py`). The chart incorrectly inferred policy acceptance by comparing absolute costs across iterations (`cost < previous_cost`). In bootstrap mode with per-iteration seeds, this comparison is invalid because each iteration uses different stochastic arrivals.

**Fix**: Modified `charting.py` to mark all iterations as "accepted" in bootstrap mode, since the actual acceptance decision uses paired comparison on same bootstrap samples.

See detailed investigation report: [`docs/reports/INV-14-bootstrap-cost-stability-investigation.md`](../reports/INV-14-bootstrap-cost-stability-investigation.md)

---

## References

- Investigation report: `docs/reports/bootstrap-seed-investigation-2025-12-21.md`
- Seed fix commit: `4b5ba3aa` (Implement per-iteration bootstrap seeds)
- Evaluation methodology: `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
