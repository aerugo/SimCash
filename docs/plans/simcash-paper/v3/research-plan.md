# SimCash Paper v3 - Research Plan

**Started**: 2025-12-15
**Author**: Claude (Opus 4.5)
**Objective**: Write a conference paper demonstrating how SimCash replicates Castro et al. (2025) experiments using LLM-based policy optimization

---

## Executive Summary

This research plan outlines a systematic approach to:
1. Replicate three experiments from Castro et al. (2025) using SimCash
2. Document the LLM-based policy optimization methodology
3. Compare our approach to Castro's neural network RL approach
4. Produce a conference-quality paper with appendices

---

## Phase 1: Setup & Verification (Complete)

### 1.1 Literature Review ✅
- **Castro et al. (2025)**: "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
  - Key finding: RL agents can learn Nash equilibrium policies without complete environment knowledge
  - Three experiments: 2-period deterministic, 12-period stochastic, 3-period joint optimization
  - Theoretical predictions provide ground truth for validation

### 1.2 Methodology Review ✅
- **Evaluation Methodology**: Bootstrap paired comparison with 3-agent sandbox
  - Statistical justification: paired comparison reduces variance by eliminating sample-to-sample noise
  - Information-theoretic justification: settlement timing is a sufficient statistic for market conditions
  - 3-agent sandbox (SOURCE → AGENT → SINK) is the correct abstraction given agent information constraints

- **Optimizer Prompt Architecture**: 7-section structured prompts (~50k tokens)
  1. Header: Agent ID, iteration number
  2. Current State: Performance metrics, policy parameters
  3. Cost Analysis: Breakdown by type with rates
  4. Optimization Guidance: Recommendations based on cost patterns
  5. Simulation Output: Best/worst seed event traces
  6. Iteration History: Full history with acceptance status
  7. Parameter Trajectories: Evolution across iterations
  8. Final Instructions: Output requirements

### 1.3 Configuration Verification ✅
All experiment configs verified to use Castro-compliant `liquidity_pool` mode:

| Experiment | Config File | liquidity_pool | unsecured_cap | overdraft_bps |
|------------|-------------|----------------|---------------|---------------|
| Exp1 | exp1_2period.yaml | 100,000 | 0 | 0 |
| Exp2 | exp2_12period.yaml | 1,000,000 | 0 | 0 |
| Exp3 | exp3_joint.yaml | 100,000 | 0 | 0 |

**Key configuration points**:
- `liquidity_pool` provides direct balance (matches Castro's collateral)
- `unsecured_cap: 0` prevents overdraft (matches Castro's hard liquidity constraint)
- `liquidity_cost_per_tick_bps` models opportunity cost r_c
- `deferred_crediting: true` matches Castro's ℓ_t = ℓ_{t-1} - P_t×x_t + R_t

---

## Phase 2: Experiment Execution

### 2.1 Experiment 1: 2-Period Deterministic

**Configuration**:
- Mode: Deterministic
- Ticks: 2
- Agents: BANK_A, BANK_B
- Payment schedule: A sends 15k at t=1, B sends 15k at t=0 and 5k at t=1

**Castro Prediction**: BANK_A ≈ 0%, BANK_B ≈ 20% (asymmetric equilibrium)

**Execution**:
```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
```

### 2.2 Experiment 2: 12-Period Stochastic

**Configuration**:
- Mode: Bootstrap (paired comparison)
- Ticks: 12
- Agents: BANK_A, BANK_B with stochastic arrivals
- Arrivals: Poisson(λ=2.0), LogNormal amounts (μ=10k, σ=5k)

**Castro Prediction**: Both agents 10-30% (equilibrium with variance)

**Execution**:
```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml
```

### 2.3 Experiment 3: 3-Period Joint Optimization

**Configuration**:
- Mode: Deterministic
- Ticks: 3
- Agents: BANK_A, BANK_B
- Payment schedule: Symmetric - both send 20k at t=0 and t=1

**Castro Prediction**: Both agents ≈ 25% (symmetric equilibrium)

**Execution**:
```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml
```

---

## Phase 3: Results Analysis & Artifact Generation

### 3.1 Policy Evolution Export

For each experiment, export JSON files for paper appendices:

```bash
# After exp1 completes (get run-id from experiment results)
.venv/bin/payment-sim experiment policy-evolution <run-id> --llm > ../docs/plans/simcash-paper/v3/appendices/exp1_policy_evolution.json

# Similarly for exp2 and exp3
```

### 3.2 LLM Audit Capture

Capture representative LLM prompt/response for methodology section:

```bash
# Replay specific iteration with full audit
.venv/bin/payment-sim experiment replay <run-id> --audit --start 3 --end 3 > ../docs/plans/simcash-paper/v3/appendices/exp1_audit_sample.txt
```

### 3.3 Results Comparison Table

| Experiment | Castro Prediction | SimCash Result | Match? |
|------------|-------------------|----------------|--------|
| Exp1 | A=0%, B=20% | TBD | TBD |
| Exp2 | Both 10-30% | TBD | TBD |
| Exp3 | Both ~25% | TBD | TBD |

---

## Phase 4: Paper Writing

### Required Sections

#### 4.1 Abstract
- Brief problem statement
- Methodology overview (LLM-based policy optimization)
- Key results
- Contribution statement

#### 4.2 Introduction
- Payment system liquidity management problem
- Castro et al. contribution (RL approach)
- Our contribution (LLM-based approach)
- Paper structure

#### 4.3 LLM Policy Optimization Methodology ⭐ KEY SECTION
**Must explain**:
1. Optimization loop: Generate → Evaluate → Accept/Reject → Iterate
2. Prompt structure (7 sections with examples)
3. What the LLM receives (~50k tokens of context)
4. What the LLM returns (policy JSON)
5. Validation and retry mechanism

**Include**: Representative prompt excerpt from audit output

#### 4.4 Bootstrap Evaluation & 3-Agent Sandbox ⭐ KEY SECTION
**Must explain**:
1. The problem: variance from stochastic transactions
2. Solution: paired comparison bootstrap
3. 3-agent sandbox architecture (SOURCE → AGENT → SINK)
4. Information-theoretic justification (settlement timing as sufficient statistic)
5. When the approximation is valid (small agent, local decisions)
6. Known limitations (no bilateral feedback, no multilateral LSM)

**Include**: 3-agent sandbox diagram

#### 4.5 Comparison to Castro et al. ⭐ KEY SECTION
**Must include**:
1. Comparison table (RL vs LLM approach)
2. Key differences:
   - Learning algorithm (REINFORCE vs LLM optimization)
   - Policy representation (neural network vs JSON decision trees)
   - Training dynamics (gradient updates vs accept/reject)
   - Interpretability (black-box vs transparent)
3. Why both approaches should converge to similar equilibria

#### 4.6 Results
- Per-experiment results with confidence intervals
- Comparison to Castro predictions
- Policy evolution trajectories
- Cost reduction analysis

#### 4.7 Discussion
- What worked well
- Limitations
- Implications for payment system research

#### 4.8 Conclusion
- Summary of findings
- Future work directions

#### 4.9 Appendices
- A: Policy evolution JSON files (exp1, exp2, exp3)
- B: Representative LLM prompt and response
- C: Experiment configuration details

---

## Phase 5: Figures & Tables

### Required Figures

1. **LLM Optimization Loop Diagram**
   - Shows: Generate → Evaluate → Accept/Reject cycle
   - Highlights: Where prompts go in, policies come out

2. **7-Section Prompt Structure Diagram**
   - Visual representation of prompt components
   - Token counts per section

3. **3-Agent Sandbox Architecture**
   ```
   SOURCE → AGENT → SINK
     ↓                 ↑
     └─────liquidity───┘
   ```

4. **Policy Evolution Plots** (one per experiment)
   - X-axis: Iteration
   - Y-axis: initial_liquidity_fraction
   - Lines: BANK_A, BANK_B
   - Show: acceptance/rejection markers

5. **Cost Evolution Plots** (one per experiment)
   - X-axis: Iteration
   - Y-axis: Mean cost with confidence intervals
   - Show: Convergence trajectory

### Required Tables

1. **Comparison Table: Castro RL vs SimCash LLM**
   - Columns: Aspect, Castro et al., SimCash
   - Rows: Algorithm, Policy representation, Training, etc.

2. **Results Summary Table**
   - Columns: Experiment, Castro Prediction, SimCash Result, Iterations, Cost Reduction
   - Rows: Exp1, Exp2, Exp3

3. **Configuration Summary Table**
   - Key parameters for each experiment
   - Cost rates, tick counts, etc.

---

## Timeline & Milestones

| Phase | Task | Status |
|-------|------|--------|
| 1 | Setup & Verification | ✅ Complete |
| 2 | Run Experiments | 🔄 Next |
| 3 | Results Analysis | Pending |
| 4 | Paper Writing | Pending |
| 5 | Figures & Tables | Pending |

---

## Key Resources

### Documentation
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
- `docs/reference/ai_cash_mgmt/optimizer-prompt.md`
- `experiments/castro/papers/castro_et_al.md`

### CLI Commands
```bash
# Run experiment
payment-sim experiment run --verbose <config.yaml>

# List experiments and runs
payment-sim experiment list
payment-sim experiment results

# Export policy evolution
payment-sim experiment policy-evolution <run-id> --llm

# Audit LLM interactions
payment-sim experiment replay <run-id> --audit
```

### Output Locations
- Research plan: `docs/plans/simcash-paper/v3/research-plan.md` (this file)
- Lab notes: `docs/plans/simcash-paper/v3/lab-notes.md`
- Draft paper: `docs/plans/simcash-paper/v3/draft-paper.md`
- Appendices: `docs/plans/simcash-paper/v3/appendices/`

---

*Last updated: 2025-12-15*
