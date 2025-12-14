# SimCash Paper v3 - Research Plan

**Started**: 2025-12-14
**Author**: Claude (Opus 4.5)
**Objective**: Reproduce Castro et al. (2025) experiments with Castro-compliant configuration

---

## Background

Previous v2 experiments used `posted_collateral` (credit headroom mode) instead of `liquidity_pool` (direct balance mode). This caused deviations from Castro's theoretical predictions:

| Experiment | v2 Result | Castro Prediction | Issue |
|------------|-----------|-------------------|-------|
| Exp1 | A=15%, B=0% | A=0%, B=20% | Role reversal |
| Exp2 | A=0.8%, B=1.65% | Both 10-30% | Much lower values |
| Exp3 | A=25%, B=22% | Both ~25% | Good match |

**Root Cause**: SimCash's `posted_collateral` provides credit headroom (ability to overdraft), not direct balance. Castro's model has a hard liquidity constraint where collateral provides direct balance.

---

## Phase 1: Setup & Verification

### 1.1 Modify Experiment Runner for liquidity_pool Mode

The optimization loop needs to inject `liquidity_allocation_fraction` into agent configs when `liquidity_pool` is used:

```python
# In _build_simulation_config:
for agent_config in scenario_dict["agents"]:
    agent_id = agent_config.get("id")
    if agent_id in self._policies:
        policy = self._policies[agent_id]

        # For liquidity_pool mode: inject allocation fraction
        if "liquidity_pool" in agent_config:
            params = policy.get("parameters", {})
            fraction = params.get("initial_liquidity_fraction", 0.5)
            agent_config["liquidity_allocation_fraction"] = fraction
```

### 1.2 Update Experiment Configs

Convert from collateral mode to liquidity_pool mode:

| Parameter | Before (Collateral Mode) | After (liquidity_pool Mode) |
|-----------|-------------------------|------------------------------|
| `max_collateral_capacity: 100000` | Remove | Replace with `liquidity_pool: 100000` |
| `collateral_cost_per_tick_bps: 500` | Remove | Replace with `liquidity_cost_per_tick_bps: 500` |
| `overdraft_bps_per_tick: 2000` | High | Set to `0` (no overdraft) |
| Policy action | `PostCollateral` | No-op (allocation at sim start) |

### 1.3 Sanity Check

Run exp1 with a single iteration to verify:
- Agents use `liquidity_pool` allocation
- No overdraft possible
- Costs reflect `liquidity_cost_per_tick_bps`

---

## Phase 2: Experiment Execution

### 2.1 Experiment 1: 2-Period Deterministic

**Config**: `experiments/castro/configs/exp1_2period.yaml`

**Expected Result**:
- BANK_A: 0% (free-rider)
- BANK_B: 20% (liquidity provider)

**Rationale**: With hard liquidity constraint, BANK_B must allocate to send tick-0 payment. BANK_A can use incoming payment.

### 2.2 Experiment 2: 12-Period Stochastic

**Config**: `experiments/castro/configs/exp2_12period.yaml`

**Expected Result**:
- Both agents: 10-30%

**Note**: May still show lower values if stochastic dynamics favor risk-tolerant strategies.

### 2.3 Experiment 3: 3-Period Joint Optimization

**Config**: `experiments/castro/configs/exp3_joint.yaml`

**Expected Result**:
- Both agents: ~25%

**Note**: Already close to Castro's prediction in v2.

---

## Phase 3: Analysis

### 3.1 Compare to Castro Predictions

| Experiment | v3 Result | Castro Prediction | Match? |
|------------|-----------|-------------------|--------|
| Exp1 | TBD | A=0%, B=20% | |
| Exp2 | TBD | Both 10-30% | |
| Exp3 | TBD | Both ~25% | |

### 3.2 Statistical Analysis

For each experiment:
- Mean policy values
- Standard deviation
- 95% confidence intervals
- Convergence trajectory

---

## Phase 4: Paper Writing

### 4.1 Structure

1. **Abstract**: SimCash reproduces Castro et al. with bootstrap evaluation
2. **Introduction**: Payment system policy optimization
3. **Methodology**: 3-agent sandbox, paired comparison, bootstrap sampling
4. **Results**: Three experiments with CI
5. **Discussion**: Comparison to Castro, methodological differences
6. **Conclusion**: SimCash validates RL approach

### 4.2 Key Figures

- Figure 1: Policy evolution over iterations
- Figure 2: Cost reduction over iterations
- Figure 3: Final policy comparison (v3 vs Castro)
- Table 1: Experiment summary with CI

---

## Phase 5: Deliverables

1. Updated experiment configs (Castro-compliant)
2. Modified optimization.py (liquidity_pool support)
3. Complete lab notes with iteration details
4. Draft paper with figures and tables
5. Committed and pushed changes

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Experiment runner doesn't support liquidity_pool | Modify _build_simulation_config |
| Exp2 still shows low values | Document as genuine finding about stochastic equilibria |
| LLM service errors | Retry logic already in place |

---

*Last updated: 2025-12-14*
