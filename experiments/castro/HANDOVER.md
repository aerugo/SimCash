# Castro Experiment Handover Note

**Date**: 2025-12-02
**Prepared by**: Claude (AI Research Assistant)
**Status**: Ready for LLM optimization experiments

---

## Summary

The Castro et al. (2025) replication experiments have been restructured to align with the paper's payment system model. Two critical features (`deferred_crediting` and `deadline_cap_at_eod`) were implemented in SimCash and the experiment configurations have been updated to use them.

**Previous experiments have been archived** because they used immediate crediting and multi-day deadlines, which created fundamentally different equilibrium dynamics than Castro's model.

---

## What Was Done

### 1. Archived Pre-Alignment Experiments
- **Location**: `experiments/castro/archive/pre-castro-alignment/`
- Contains all previous configs, policies, and documentation
- See `archive/pre-castro-alignment/README.md` for details on why these are invalid

### 2. Created Castro-Aligned Configurations
Three new configuration files with alignment features enabled:

| Config | Description |
|--------|-------------|
| `configs/castro_2period_aligned.yaml` | Experiment 1: 2-period Nash equilibrium validation |
| `configs/castro_12period_aligned.yaml` | Experiment 2: 12-period stochastic LVTS-style |
| `configs/castro_joint_aligned.yaml` | Experiment 3: 3-period joint learning |

**Key settings in all configs:**
```yaml
deferred_crediting: true      # Credits applied at end of tick
deadline_cap_at_eod: true     # All deadlines capped at day end
```

### 3. Updated Seed Policy
- **Location**: `policies/seed_policy.json`
- Version 2.0 with conservative parameters for deferred crediting
- `initial_liquidity_fraction: 0.25` (higher than before since recycling disabled)

### 4. Updated Experiment Infrastructure
- `scripts/reproducible_experiment.py` - Points to new configs
- `scripts/README.md` - Documents Castro alignment requirements

### 5. Documented in LAB_NOTES.md
- Section "Model Alignment Review and Archive" (2025-12-02)
- Section "New Experiment Plan: Castro-Aligned" (2025-12-02)
- Details alignment issues found and expected outcomes

---

## Baseline Results (Seed Policy)

Ran baseline experiments to validate configs work:

| Experiment | Mean Cost | Settlement | Notes |
|------------|-----------|------------|-------|
| Exp 1 (2-period) | $290.00 | 100% | Deterministic, single seed |
| Exp 2 (12-period) | $498,026.45 ± $22.44 | 100% | High cost due to large collateral capacity |
| Exp 3 (joint) | $249.78 | 100% | Deterministic (symmetric payments) |

**Note**: These baseline costs are with the seed policy. LLM optimization should significantly reduce them.

---

## What Needs To Be Done

### 1. Set OpenAI API Key
```bash
export OPENAI_API_KEY="your-key-here"
```

### 2. Run LLM Optimization Experiments

```bash
cd /home/user/SimCash/experiments/castro/scripts

# Experiment 1: Two-Period (quick validation)
python reproducible_experiment.py --experiment exp1 --output results/exp1.db

# Experiment 2: Twelve-Period Stochastic
python reproducible_experiment.py --experiment exp2 --output results/exp2.db

# Experiment 3: Joint Learning
python reproducible_experiment.py --experiment exp3 --output results/exp3.db
```

### 3. Expected Outcomes to Verify

**Experiment 1 (Critical Test)**:
- With deferred crediting, LLM should discover **asymmetric equilibrium**:
  - Bank A: ℓ₀ = 0 (posts no collateral)
  - Bank B: ℓ₀ = $200 (posts collateral)
- This differs from pre-alignment results which found symmetric equilibrium

**Experiment 2**:
- Should achieve ~100% settlement with reasonable costs
- Compare convergence speed to Castro's RL results (~50-100 episodes)

**Experiment 3**:
- Near-zero cost through coordination
- Tests joint liquidity + timing optimization

### 4. Update Research Paper
After experiments complete:
- Update `RESEARCH_PAPER.md` with new results
- Compare LLM vs RL performance
- Document whether asymmetric equilibrium was discovered

---

## File Locations

```
experiments/castro/
├── HANDOVER.md                 ← You are here
├── LAB_NOTES.md                ← Detailed research log
├── RESEARCH_PAPER.md           ← Draft paper (needs updating)
├── configs/
│   ├── castro_2period_aligned.yaml
│   ├── castro_12period_aligned.yaml
│   └── castro_joint_aligned.yaml
├── policies/
│   └── seed_policy.json        ← Starting policy for optimization
├── scripts/
│   ├── README.md               ← Script documentation
│   └── reproducible_experiment.py  ← Main experiment runner
├── results/                    ← Output databases go here
├── archive/
│   └── pre-castro-alignment/   ← Old experiments (don't use)
└── papers/
    └── castro_et_al.md         ← Original paper reference
```

---

## Key References

- **Castro Paper**: `papers/castro_et_al.md` - Full text of original paper
- **Feature Documentation**:
  - `docs/reference/scenario/advanced-settings.md` - deferred_crediting, deadline_cap_at_eod
- **Implementation**:
  - `backend/src/orchestrator/engine.rs` - deferred_crediting logic
  - `backend/src/arrivals/mod.rs` - deadline_cap_at_eod logic

---

## Troubleshooting

### "max_collateral_capacity ignored" Issue
The `max_collateral_capacity` config field is computed as `10 × unsecured_cap`, not read from config. Adjust `initial_liquidity_fraction` in policies accordingly.

For Exp2 with `unsecured_cap: 10000000000`:
- Actual max_collateral_capacity = $100B
- Use very small fractions (e.g., 0.000025 for $250k collateral)

### Verifying Deferred Crediting Works
Check for `DeferredCreditsApplied` events in verbose output. If Bank A can use Bank B's payment within the same tick, deferred crediting is NOT working.

---

## Questions?

- Check `LAB_NOTES.md` for detailed experiment history
- Original Castro paper is in `papers/castro_et_al.md`
- SimCash documentation in `/docs/reference/`

Good luck with the experiments!
