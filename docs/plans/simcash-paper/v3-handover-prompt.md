# SimCash Paper v3 - Handover Prompt

## Context

We are writing a draft paper to demonstrate how SimCash can reproduce the three experiments from Castro et al. (2025) on reinforcement learning for payment system policy optimization.

**v1 is complete** - Used Monte Carlo evaluation (not real bootstrap)
**v2 is complete** - Used real bootstrap evaluation with 50 samples

**Your task**: Produce v3 by re-running experiments with **Castro-compliant configuration**.

---

## 🔴 CRITICAL: v2 Discovered a Configuration Issue

v2 experiments completed successfully but analysis revealed that our configuration **does not match Castro's model**. The key finding:

### The Problem

| Aspect | Castro Model | v2 Configuration |
|--------|--------------|------------------|
| **Liquidity mechanism** | Collateral = direct balance | Collateral = credit headroom |
| **Hard constraint** | `P_t × x_t ≤ ℓ_{t-1}` | Soft: overdraft allowed |
| **Effect** | Can only pay if balance ≥ amount | Can go negative with collateral |

v2 used `max_collateral_capacity` + `posted_collateral` which provides **credit headroom** (ability to go negative), not **direct balance** as in Castro's model.

### The Solution (Already Documented)

SimCash already has the required features - **NO CODE CHANGES NEEDED**:

| Castro Requirement | SimCash Feature |
|-------------------|-----------------|
| Direct balance from collateral | `liquidity_pool` + `liquidity_allocation_fraction` |
| Opportunity cost r_c | `liquidity_cost_per_tick_bps` |
| Hard liquidity constraint | `unsecured_cap: 0` + no `posted_collateral` |

**Configuration Pattern**:
```yaml
agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0                      # No credit
    liquidity_pool: 100000                # Castro's B (replaces max_collateral_capacity)
    # liquidity_allocation_fraction controlled by policy optimization

cost_rates:
  liquidity_cost_per_tick_bps: 500        # r_c (replaces collateral_cost_per_tick_bps)
  collateral_cost_per_tick_bps: 0         # Disable collateral mode
```

See `docs/plans/simcash-paper/v2/lab-notes.md` section "Recommendations: Configuring SimCash to Match Castro Exactly" for full details.

---

## 🟢 What Was Accomplished in v2

### Experiments Run (All Converged)

| Experiment | BANK_A | BANK_B | Iterations | Cost Reduction | Matches Castro? |
|------------|--------|--------|------------|----------------|-----------------|
| Exp1 | 15% | 0% | 15 | 59% | **No** - Reversed roles |
| Exp2 | 0.8% | 1.65% | 8 | 95% | **No** - Much lower than 10-30% |
| Exp3 | 25% | 22% | 8 | 39% | **Yes** - ~25% as predicted |

### Key Findings

1. **Exp1 Role Reversal**: Found (A=15%, B=0%) instead of Castro's (A=0%, B=20%). Analysis showed this is due to configuration difference - both are valid equilibria in v2's model.

2. **Exp2 Aggressive Strategy**: Found <2% liquidity vs Castro's 10-30%. May or may not change with Castro-compliant config.

3. **Exp3 Match**: Already close to Castro's prediction. Symmetric payment structure makes it less sensitive to the liquidity mechanism difference.

### Documentation Created

- `docs/plans/simcash-paper/v2/draft-paper.md` - Complete draft with Sections 6.5-6.7 on model differences
- `docs/plans/simcash-paper/v2/lab-notes.md` - Detailed analysis including Castro-compliant configs for all experiments
- `docs/plans/simcash-paper/v2/research-plan.md` - Completed research phases

---

## 🟡 Your Task: v3 Experiments

### Phase 1: Update Experiment Configurations

Update the three experiment YAML files to use Castro-compliant configuration:

**Priority Order:**
1. **Exp1 (HIGH)** - Role reversal strongly suggests model difference matters
2. **Exp2 (MEDIUM)** - Large deviation may or may not be explained by model difference
3. **Exp3 (LOW)** - Already close; minimal change expected

**Changes Required for Each Config:**

Replace:
```yaml
agents:
  - id: BANK_A
    max_collateral_capacity: 100000
cost_rates:
  collateral_cost_per_tick_bps: 500
```

With:
```yaml
agents:
  - id: BANK_A
    liquidity_pool: 100000
cost_rates:
  liquidity_cost_per_tick_bps: 500
  collateral_cost_per_tick_bps: 0
```

See `docs/plans/simcash-paper/v2/lab-notes.md` section "Castro Compliance Analysis: All Experiments" for experiment-specific configurations.

### Phase 2: Verify Experiment Runner Compatibility

Before running experiments, verify that the experiment runner supports `liquidity_pool` mode:

1. Check if `initial_liquidity_fraction` parameter maps to `liquidity_allocation_fraction`
2. If not, update the policy injection mechanism
3. Test with a manual single-iteration run

### Phase 3: Run Experiments

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml
```

**NEVER change the LLM model!** Always use `openai:gpt-5.2` as specified.

### Phase 4: Compare Results

For each experiment, document:

1. **v2 Result** (collateral mode) vs **v3 Result** (liquidity_pool mode)
2. Whether v3 matches Castro's theoretical prediction
3. If Exp2's aggressive <2% equilibrium persists (genuine stochastic finding)

### Phase 5: Update Paper

Update `docs/plans/simcash-paper/v2/draft-paper.md`:

1. Add v3 results alongside v2 results
2. Update Sections 6.5-6.7 with empirical validation
3. Update Future Work to reflect completed Castro validation
4. Consider renaming to v3 or creating separate v3 draft

---

## Expected Outcomes

With Castro-compliant configuration:

| Experiment | v2 Result | Expected v3 Result |
|------------|-----------|-------------------|
| **Exp1** | A=15%, B=0% | A≈0%, B≈20% (exact Castro match) |
| **Exp2** | A=0.8%, B=1.65% | Either 10-30% (Castro match) OR <2% persists (genuine finding) |
| **Exp3** | A=25%, B=22% | ~25% (minimal change) |

---

## Key Files to Read

### Must Read
- `docs/plans/simcash-paper/v2/lab-notes.md` - Castro compliance analysis and configurations
- `docs/plans/simcash-paper/v2/draft-paper.md` - Current draft with model differences analysis
- `experiments/castro/papers/castro_et_al.md` - Castro's theoretical predictions

### Reference
- `docs/reference/scenario/agents.md` - `liquidity_pool` documentation
- `docs/reference/scenario/cost-rates.md` - `liquidity_cost_per_tick_bps` documentation
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Bootstrap evaluation methodology

### Experiment Configs to Update
- `experiments/castro/configs/exp1_2period.yaml`
- `experiments/castro/configs/exp2_12period.yaml`
- `experiments/castro/configs/exp3_joint.yaml`

---

## Output Location

All v3 work goes in: `docs/plans/simcash-paper/v3/`

Create:
- `research-plan.md` - Your phased approach
- `lab-notes.md` - Detailed experiment logs
- `draft-paper.md` - Updated paper (or update v2 draft in place)

Do NOT modify v1 files. You may update v2 files or create new v3 files.

---

## Questions to Answer in v3

1. **Does Exp1 match Castro exactly?** With `liquidity_pool` mode, does the LLM find A=0%, B=20%?

2. **Does Exp2's aggressive equilibrium persist?** If <2% equilibrium remains with Castro-compliant config, this is a genuine finding about stochastic vs deterministic game dynamics.

3. **Is Exp3 unchanged?** Symmetric structure should make it insensitive to the configuration change.

4. **Are there implementation issues?** Does the experiment runner need changes to support `liquidity_pool` mode?

---

## Checklist

Before starting experiments:
- [ ] Read v2 lab notes (especially Castro compliance sections)
- [ ] Verify `liquidity_pool` feature works with experiment runner
- [ ] Update all three config files
- [ ] Test with single iteration before full run

During experiments:
- [ ] Capture all verbose output
- [ ] Document any errors or unexpected behavior
- [ ] Compare iteration-by-iteration to v2 results

After experiments:
- [ ] Create comparison table: v2 vs v3 vs Castro predictions
- [ ] Update draft paper with findings
- [ ] Document whether Castro compliance resolved the deviations
