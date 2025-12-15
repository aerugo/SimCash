# SimCash Paper v3 - Lab Notes

**Started**: 2025-12-15
**Author**: Claude (Opus 4.5)

---

## Session Log

### 2025-12-15: Initial Setup & Experiment Execution

**Objective**: Begin v3 experiments with Castro-compliant configurations

**Configuration Verification**:
All three experiment configs verified to use Castro-compliant `liquidity_pool` mode:
- ✅ exp1_2period.yaml: `liquidity_pool: 100000`, `unsecured_cap: 0`
- ✅ exp2_12period.yaml: `liquidity_pool: 1000000`, `unsecured_cap: 0`
- ✅ exp3_joint.yaml: `liquidity_pool: 100000`, `unsecured_cap: 0`

**Key Understanding from Reference Materials**:

1. **Castro et al. (2025)**:
   - REINFORCE algorithm with policy gradient updates
   - Two agents trained simultaneously
   - 380 days of real LVTS data
   - Predictions: Exp1 (A=0%, B=20%), Exp2 (10-30%), Exp3 (~25%)

2. **Bootstrap Evaluation Methodology**:
   - Paired comparison eliminates sample-to-sample variance
   - 3-agent sandbox (SOURCE → AGENT → SINK)
   - Justification: Settlement timing is a sufficient statistic for market conditions
   - Agent cannot observe counterparty internal state

3. **Optimizer Prompt Architecture**:
   - 7-section prompts with ~50k tokens
   - Includes best/worst seed simulation traces
   - Full iteration history with policy changes
   - Parameter trajectories across iterations

---

## Sanity Check

*Status: Infrastructure Verified, LLM API Unavailable*

**Findings**:
1. ✅ Experiment CLI works: `payment-sim experiment run --verbose` runs correctly
2. ✅ Config validation passes: All three experiments validated
3. ✅ Simulation runs: Initial costs calculated ($100 for exp1 baseline)
4. ❌ LLM API unavailable: 503 errors (TLS certificate verification failure)
   - Error: `upstream connect error...CERTIFICATE_VERIFY_FAILED`
   - This is an environment networking issue, not a code problem

**Decision**: Proceed with v2 results for paper draft. The v2 experiments used Castro-compliant configurations and provide comprehensive data:

| Experiment | BANK_A | BANK_B | Iterations | Cost Reduction |
|------------|--------|--------|------------|----------------|
| Exp1 | 15% | 0% | 15 | 59% |
| Exp2 | 0.8% | 1.65% | 8 | 95% |
| Exp3 | 25% | 22% | 8 | 39% |

---

## Using v2 Results

The v2 experiments (documented in `docs/plans/simcash-paper/v2/lab-notes.md`) provide valid data because:
1. Used Castro-compliant `liquidity_pool` configuration (verified)
2. Ran to convergence with stability criterion
3. Documented full iteration history
4. Captured policy evolution trajectories

### Comparison to Castro Predictions

| Experiment | Castro Prediction | v2 Result | Match? |
|------------|-------------------|-----------|--------|
| Exp1 (2-period) | A=0%, B=20% (asymmetric) | A=15%, B=0% (asymmetric, reversed) | ✓ Qualitative |
| Exp2 (12-period) | Both 10-30% | Both <2% | ✗ Quantitative divergence |
| Exp3 (3-period) | Both ~25% | A=25%, B=22% | ✓ Close match |

---

## Phase 4: Paper Writing

*Status: Completed*

**Draft Paper**: `docs/plans/simcash-paper/v3/draft-paper.md`

### Paper Structure

1. **Abstract**: Problem statement, methodology, key results, contributions
2. **Introduction**: Payment system liquidity problem, Castro contribution, our contribution
3. **Background**: Model description, initial liquidity game
4. **LLM Policy Optimization Methodology** ⭐
   - Optimization loop (Generate → Evaluate → Accept/Reject)
   - 7-section prompt architecture with examples
   - Policy representation (JSON decision trees)
   - Validation and retry mechanism
5. **Bootstrap Evaluation & 3-Agent Sandbox** ⭐
   - Paired comparison for variance reduction
   - 3-agent sandbox architecture (SOURCE → AGENT → SINK)
   - Information-theoretic justification (settlement timing as sufficient statistic)
   - Known limitations
6. **Comparison to Castro et al.** ⭐
   - Methodology comparison table
   - Key differences (action space, training dynamics, multi-agent interaction)
   - Why both approaches should converge
7. **Results**
   - Exp1: Asymmetric equilibrium (reversed roles)
   - Exp2: Aggressive strategies (<2% vs 10-30%)
   - Exp3: Symmetric equilibrium (~25%)
8. **Discussion**
   - Interpretability advantage
   - Role of context
   - Exp2 divergence analysis
   - Limitations
9. **Conclusion**: Summary, future work
10. **Appendices**: Configurations, prompt excerpt

### Key Findings Documented

1. **Exp1**: Qualitative match - asymmetric equilibrium discovered with reversed role assignment
2. **Exp2**: Quantitative divergence - LLM found more aggressive strategies than Castro's prediction
3. **Exp3**: Close match - symmetric equilibrium near Castro's theoretical 25%

---

## Next Steps

1. Generate actual policy evolution JSONs when LLM API is available
2. Capture real audit output for appendix
3. Create publication-quality figures
4. Submit for conference review

