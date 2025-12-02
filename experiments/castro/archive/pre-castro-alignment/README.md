# Pre-Castro-Alignment Archive

**Archived**: 2025-12-02
**Reason**: Model alignment issues discovered

## Summary

This archive contains all experimental runs, configurations, and policies from the initial Castro et al. (2025) replication attempt. These experiments were conducted before two critical alignment features were implemented:

1. **`deferred_crediting`**: Credits are now batched and applied at end of tick (Castro-compatible mode)
2. **`deadline_cap_at_eod`**: Deadlines are capped at end of current business day

## Key Alignment Issues Found

### 1. Immediate vs Deferred Crediting

**Castro Model**: Incoming payments \( R_t \) only become available in period \( t+1 \)

**SimCash (Old)**: Credits applied immediately within the same tick

**Impact**: SimCash allowed "within-tick recycling" equilibria that are impossible in Castro's model. This made direct comparison invalid.

### 2. Multi-Day Deadlines

**Castro Model**: All payments must settle by end of same business day

**SimCash (Old)**: Deadlines could extend into future days

**Impact**: Payment timing pressure was artificially reduced in SimCash, changing optimal policy structure.

### 3. Credit Limits vs Unlimited Borrowing

**Castro Model**: Unlimited central bank borrowing at rate \( r_b \)

**SimCash (Old)**: Hard credit limits with flat EOD penalties

**Impact**: Experiments 2/2b/2c showed ~40% settlement failures due to hitting credit limits

## Archived Contents

### Configs (7 files)
- `castro_2period.yaml` - Experiment 1: deterministic validation
- `castro_12period.yaml` - Experiment 2: base stochastic
- `castro_12period_v2.yaml` - Experiment 2: variant B
- `castro_12period_v3.yaml` - Experiment 2: variant C
- `castro_12period_castro_equiv.yaml` - Attempted Castro-equivalent (incomplete)
- `castro_12period_castro_equiv_fixed.yaml` - Fixed collateral capacity
- `castro_joint.yaml` - Experiment 3: joint learning

### Policies (16 files)
- `seed_policy.json` - Initial seed policy
- `exp1_bank_{a,b}.json` - 2-period optimized policies
- `exp2_bank_{a,b}.json` - 12-period variants
- `exp2b_bank_{a,b}.json`, `exp2c_bank_{a,b}.json` - Further variants
- `exp2d_bank_{a,b}.json`, `exp2d_fixed_bank_{a,b}.json` - Castro-equiv attempts
- `exp3_bank_{a,b}.json`, `exp3_joint.json` - Joint learning policies

### Documentation (3 files)
- `experiment_2d_design.md` - Castro-equivalent scenario design
- `feature_request_deadline_eod_cap.md` - Deadline capping feature request
- `feature_request_deferred_crediting.md` - Deferred crediting feature request

## Results Summary (Before Alignment Fix)

| Experiment | Mean Cost | Settlement | Notes |
|------------|-----------|------------|-------|
| 1: Two-Period | $80.52/day | 100% | Found symmetric equilibrium (differs from Castro) |
| 2: Twelve-Period | $52,445 ± $2,244/day | 100% | With fixed collateral config |
| 3: Joint Learning | ~$500 | 100% | Symmetric outcome |

**Key Finding**: LLM found a symmetric equilibrium (both banks post minimal collateral) instead of Castro's predicted asymmetric equilibrium (Bank B pays, Bank A free-rides). This difference is likely due to the immediate crediting allowing different strategic interactions.

## What Changed

After implementing `deferred_crediting` and `deadline_cap_at_eod`, the simulation environment now matches Castro et al. (2025) more closely. New experiments should be run with these features enabled.

## How to Restore

If needed, these files can be copied back to their original locations:

```bash
# Restore configs
cp archive/pre-castro-alignment/configs/*.yaml configs/

# Restore policies
cp archive/pre-castro-alignment/policies/*.json policies/

# Restore docs
cp archive/pre-castro-alignment/docs/*.md docs/
```

## References

- Castro et al. (2025): "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
- Feature implementations:
  - `backend/src/orchestrator/engine.rs` - deferred_crediting logic
  - `backend/src/arrivals/mod.rs` - deadline_cap_at_eod logic
- Documentation:
  - `docs/reference/scenario/advanced-settings.md`
