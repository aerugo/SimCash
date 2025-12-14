# SimCash Paper v3 - Handover Prompt

## Context

We are writing a paper to demonstrate how SimCash can reproduce the three experiments from Castro et al. (2025) on reinforcement learning for payment system policy optimization.

**Your task**: Write the SimCash paper using **Castro-compliant configuration**.

---

## 🔴 CRITICAL: Use Castro-Compliant Configuration

Previous work identified that SimCash has two liquidity mechanisms:

| Mechanism | Effect | Use Case |
|-----------|--------|----------|
| `posted_collateral` + `max_collateral_capacity` | Provides credit headroom (overdraft) | General payment systems |
| `liquidity_pool` + `liquidity_allocation_fraction` | Provides direct balance | **Castro replication** |

**For Castro replication, you MUST use `liquidity_pool` mode.** This matches Castro's model where:
- Collateral provides direct balance (not credit)
- Hard liquidity constraint: `P_t × x_t ≤ ℓ_{t-1}`
- No intraday overdraft

---

## 🟢 Configuration Pattern

All experiment configs should use this pattern:

```yaml
agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0                      # No credit
    liquidity_pool: 100000                # Castro's B
    # liquidity_allocation_fraction controlled by policy optimization

cost_rates:
  liquidity_cost_per_tick_bps: 500        # r_c
  collateral_cost_per_tick_bps: 0         # Disable collateral mode
  overdraft_bps_per_tick: 0               # No overdraft
```

See `docs/plans/simcash-paper/v2/lab-notes.md` section "Castro Compliance Analysis: All Experiments" for complete experiment-specific configurations.

---

## Your Assignment

### Phase 1: Setup & Verification

- [ ] Review Castro et al. paper: `experiments/castro/papers/castro_et_al.md`
- [ ] Review evaluation methodology: `docs/reference/ai_cash_mgmt/evaluation-methodology.md`
- [ ] Update experiment configs to use `liquidity_pool` pattern:
  - `experiments/castro/configs/exp1_2period.yaml`
  - `experiments/castro/configs/exp2_12period.yaml`
  - `experiments/castro/configs/exp3_joint.yaml`
- [ ] Verify experiment runner supports `liquidity_allocation_fraction` optimization
- [ ] Run sanity check (1 iteration of exp1)

### Phase 2: Experiment Execution

Run experiments using the CLI with verbose output:

```bash
cd api
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp1.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp2.yaml
.venv/bin/payment-sim experiment run --verbose ../experiments/castro/experiments/exp3.yaml
```

**NEVER change the LLM model!** Always use `openai:gpt-5.2` as specified.

- [ ] Run exp1 (2-period deterministic)
- [ ] Run exp2 (12-period stochastic)
- [ ] Run exp3 (3-period joint optimization)
- [ ] Document any errors or unexpected behavior

### Phase 3: Results Analysis

For each experiment:
- [ ] Record final policy values
- [ ] Compare to Castro et al. theoretical predictions
- [ ] Document bootstrap statistics (mean, std, CI)
- [ ] Analyze paired delta distributions

### Phase 4: Paper Writing

Write fresh documentation in `docs/plans/simcash-paper/v3/`:

1. **`research-plan.md`** - Your phased approach
2. **`lab-notes.md`** - Detailed experiment logs
3. **`draft-paper.md`** - Complete paper including:
   - Abstract
   - Introduction
   - Methodology (bootstrap evaluation, 3-agent sandbox)
   - Results with confidence intervals
   - Comparison to Castro et al. predictions
   - Discussion and conclusion

### Phase 5: Figures & Tables

- [ ] Policy evolution diagrams
- [ ] Cost over iterations with confidence intervals
- [ ] Final policy comparison table vs Castro predictions

---

## Expected Outcomes

With Castro-compliant configuration, results should match Castro's theoretical predictions:

| Experiment | Castro Prediction | Notes |
|------------|-------------------|-------|
| **Exp1** | A=0%, B=20% | Asymmetric equilibrium |
| **Exp2** | Both 10-30% | Stochastic case |
| **Exp3** | Both ~25% | Symmetric equilibrium |

---

## Key Files

### Must Read
- `experiments/castro/papers/castro_et_al.md` - Castro's theoretical predictions
- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Bootstrap evaluation
- `docs/reference/scenario/agents.md` - `liquidity_pool` documentation
- `docs/reference/scenario/cost-rates.md` - `liquidity_cost_per_tick_bps` documentation

### Reference (Background)
- `docs/plans/simcash-paper/v2/lab-notes.md` - Contains Castro-compliant configs for all experiments

### Experiment Configs to Update
- `experiments/castro/configs/exp1_2period.yaml`
- `experiments/castro/configs/exp2_12period.yaml`
- `experiments/castro/configs/exp3_joint.yaml`

---

## CLI Reference

```bash
# Run experiment
.venv/bin/payment-sim experiment run --verbose <config.yaml>

# List experiments
.venv/bin/payment-sim experiment list

# Replay experiment
.venv/bin/payment-sim experiment replay <experiment_id>

# Audit iteration (LLM prompts/responses)
.venv/bin/payment-sim experiment replay <experiment_id> --audit --start N --end N
```

---

## Output Location

All work goes in: `docs/plans/simcash-paper/v3/`

---

## Checklist

Before starting:
- [ ] Configs updated to use `liquidity_pool` pattern
- [ ] Experiment runner verified to support `liquidity_allocation_fraction`
- [ ] Sanity check passed

During experiments:
- [ ] Capture all verbose output
- [ ] Document iteration-by-iteration progress in lab notes

After experiments:
- [ ] Results compared to Castro predictions
- [ ] Draft paper complete with all sections
- [ ] Figures and tables included
