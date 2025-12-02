# Experiment 2d: Castro-Equivalent 12-Period Stochastic Scenario

## Background

Our previous experiments (2, 2b, 2c) failed to achieve the cost reductions reported in Castro et al. (2025). After careful analysis of the paper, we identified **fundamental differences** between our SimCash model and Castro's model that explain the divergence.

## Key Finding: SimCash ≠ Castro's Model

### Castro's End-of-Day Treatment (Section 3, Table 1)

From the paper:
> "At the end of the day, banks must settle all payment demands. If liquidity is insufficient, banks can borrow from the central bank at a rate higher than the morning collateral cost."

Castro's cost function:
```
R = r_c·ℓ₀ + Σ P_t(1-x_t)·r_d + r_b·c_b
```

Where:
- `r_c·ℓ₀` = initial liquidity cost (collateral opportunity cost)
- `Σ P_t(1-x_t)·r_d` = cumulative delay costs
- `r_b·c_b` = **borrowing cost** (rate × amount borrowed)

**Critical insight**: In Castro's model:
1. Banks can **ALWAYS borrow** from the central bank at EOD
2. `c_b` is the **amount borrowed**, not a penalty count
3. **All payments settle** - some just cost more (via borrowing)
4. There are NO "unsettled" transactions

### SimCash's End-of-Day Treatment

Our experiments used:
```yaml
eod_penalty_per_transaction: 50000  # $500 per UNSETTLED transaction
unsecured_cap: 100000               # Only $1000 credit limit
```

This means:
1. Banks have **limited credit capacity**
2. If credit is exhausted → payments **remain unsettled**
3. Each unsettled transaction incurs a **flat $500 penalty**
4. This creates "failures" that **don't exist in Castro's model**

### Consequence

| Metric | Castro's Model | Our Experiments 2/2b/2c |
|--------|---------------|-------------------------|
| Can payments always settle? | Yes (via borrowing) | No (credit limits) |
| EOD penalty type | Rate × amount borrowed | Flat per-transaction |
| "Settlement rate" meaning | % on-time | % settled at all |
| Failures possible? | No | Yes (40% in our runs) |

## Experiment 2d: Corrected Castro-Equivalent Setup

### Design Rationale

To properly replicate Castro's 12-period experiment, we must:

1. **Remove credit limits** → Allow unlimited overdraft (like central bank lending)
2. **Remove EOD penalties** → Replace with overdraft cost (rate-based)
3. **Map costs correctly**:
   - `r_c = 0.1` → collateral opportunity cost per day
   - `r_d = 0.2` → delay cost per period
   - `r_b = 0.4` → borrowing/overdraft cost per day

### Cost Mapping

Castro uses **daily rates**. For T=12 periods, we convert:

| Castro Parameter | Daily Value | Per-Tick (÷12) | SimCash Parameter |
|-----------------|-------------|----------------|-------------------|
| r_c (liquidity) | 0.1 | 0.00833 | `collateral_cost_per_tick_bps: 83` |
| r_d (delay) | 0.2 | 0.01667 | `delay_cost_per_tick_per_cent: 0.00017` |
| r_b (borrowing) | 0.4 | 0.03333 | `overdraft_bps_per_tick: 333` |

### Key Configuration Changes

```yaml
# Castro-equivalent: Unlimited credit (like central bank lending)
agents:
  - id: BANK_A
    unsecured_cap: 10000000000  # $100M - effectively unlimited
    # This ensures ANY payment can settle via overdraft

# Castro-equivalent: No hard EOD penalty
cost_rates:
  eod_penalty_per_transaction: 0  # No flat penalty
  deadline_penalty: 0              # Castro uses delay costs instead

  # Overdraft cost = Castro's r_b (borrowing rate)
  overdraft_bps_per_tick: 333      # ~0.4/12 per tick
```

### What This Changes

| Aspect | Experiments 2/2b/2c | Experiment 2d |
|--------|---------------------|---------------|
| Credit limit | $1,000 | $100,000,000 (unlimited) |
| EOD penalty | $500 per unsettled | $0 |
| Overdraft cost | Low | ~r_b = 0.4/day |
| Settlement possible? | Sometimes no | Always yes |
| Cost for late settlement | Flat penalty | Rate × amount × time |

### Expected Behavior

With unlimited credit and no EOD penalty:
1. **All payments will settle** (possibly via overdraft)
2. **Cost = liquidity cost + delay cost + overdraft cost**
3. **Optimization target**: Minimize total cost, not maximize settlement rate
4. **No "failures"** - just varying costs

### Intraday Policy

Castro's 12-period experiment (Section 6.1) uses a **fixed intraday policy**:
> "Intraday policy: Fixed to 'send all possible payments,' i.e. no strategic delay."

However, for our LLM optimization, we allow the LLM to learn **both**:
1. Initial liquidity (collateral posting) decision
2. Intraday payment timing

This is more ambitious than Castro's setup but tests whether the LLM can discover optimal strategies.

### Baseline Comparison

Castro's RL achieved (Section 6.4, Figure 5):
- Convergence after ~60-100 episodes
- Final costs that minimize `r_c·ℓ₀ + delay + overdraft`
- **No settlement failures** (all payments clear)

Our Experiment 2d should:
- Achieve **100% settlement** (since unlimited credit)
- Find optimal liquidity-delay-overdraft trade-off
- Compare final costs against a baseline

## Baseline Calculation

For a naive "post nothing, pay everything immediately" strategy:
- Initial collateral: 0
- All payments go out immediately via overdraft
- Overdraft cost accumulates until incoming payments arrive

For "post full collateral upfront" strategy:
- Initial collateral: max available
- Collateral cost from tick 0
- Lower overdraft usage

The optimal is somewhere in between, balancing r_c vs r_b.

## Files

- Config: `experiments/castro/configs/castro_12period_castro_equiv.yaml`
- Policies: `experiments/castro/policies/exp2d_bank_a.json`, `exp2d_bank_b.json`
- Optimizer: Use V3 optimizer with verbose logs

## Success Criteria

1. **100% settlement rate** (no failures possible with unlimited credit)
2. **Cost convergence** over iterations
3. **LLM discovers** optimal liquidity-delay trade-off
4. **Comparable to Castro's RL** results (within same order of magnitude)

## References

- Castro et al. (2025), Section 3 (Payment System Environment)
- Castro et al. (2025), Section 6 (Initial Liquidity Policy Estimation)
- Castro et al. (2025), Table 1 (Timeline, decisions, and constraints)
