# SimCash Paper v2 - Lab Notes

**Started**: 2025-12-14
**Author**: Claude (Opus 4.5)

---

## Session Log

### 2025-12-14: Initial Setup

**Objective**: Begin v2 experiments with real bootstrap evaluation

**Background Materials Reviewed**:
- v1 draft paper: Experiments completed with Monte Carlo evaluation
- v1 lab notes: 7-12 iterations per experiment, convergence achieved
- Evaluation methodology: 3-agent sandbox, paired comparison, settlement_offset preservation
- Castro et al.: Theoretical predictions for Nash equilibria

**Key v1 Results (for reference only - not to be included in v2 paper)**:
| Experiment | BANK_A | BANK_B | Iterations | Cost Reduction |
|------------|--------|--------|------------|----------------|
| Exp1 | 0% | 25% | 7 | 64% |
| Exp2 | 4% | 1.35% | 10 | 93% |
| Exp3 | 21% | 20.5% | 12 | 58% |

**Castro et al. Theoretical Predictions**:
| Experiment | BANK_A | BANK_B |
|------------|--------|--------|
| Exp1 | 0% | 20% |
| Exp2 | Both reduce from 50%, in 10-30% bands |
| Exp3 | Both ~25% |

---

## Phase 1: Setup & Verification

### Sanity Check

*Status: Completed*

Verified experiment CLI works with exp1.yaml configuration. System initialized correctly.

---

## Experiment 1: 2-Period Deterministic

*Status: Completed*

### Configuration
- **Mode**: Deterministic (single evaluation per policy)
- **Samples**: 50 (for statistical rigor)
- **Ticks**: 2
- **Model**: openai:gpt-5.2 (temperature 0.5, reasoning_effort: high)
- **Convergence**: stability_window=5, stability_threshold=0.05, max_iterations=25
- **Master seed**: 42

### Final Results

| Metric | Value |
|--------|-------|
| Iterations | 15 |
| Converged | Yes |
| Convergence Reason | Stability achieved (5 consecutive stable iterations) |
| Final Total Cost | $57.50 |
| Cost Reduction | 59% (from $140 baseline) |
| BANK_A final policy | 15% (initial_liquidity_fraction = 0.15) |
| BANK_B final policy | 0% (initial_liquidity_fraction = 0.0) |

### Comparison to Predictions

| Source | BANK_A | BANK_B | Notes |
|--------|--------|--------|-------|
| **v2 Result** | 15% | 0% | Asymmetric equilibrium |
| Castro et al. | 0% | 20% | Reversed roles |
| v1 Result | 0% | 25% | Similar to Castro |

**Interpretation**: The LLM discovered an asymmetric Nash equilibrium where one bank provides liquidity (15%) while the other free-rides (0%). This matches Castro's theoretical prediction of an asymmetric equilibrium, but with reversed role assignment. The equilibrium is valid - BANK_A's 15% liquidity enables settlements, while BANK_B benefits without posting collateral.

### Complete Iteration History

| Iter | BANK_A | BANK_B | Cost | Notes |
|------|--------|--------|------|-------|
| 1 | 50%→20% ACC | 50%→0% ACC | $140→$70 | Initial dramatic reductions |
| 2 | 0.3 REJ | 0.01 REJ | $70 | Exploring alternatives |
| 3 | 0.2 REJ | 0.01 REJ | $70 | Rejected proposals |
| 4 | 0.25 REJ | 0.01 REJ | $70 | Rejected proposals |
| 5 | 0.2 REJ | 0.0 REJ | $70 | Rejected proposals |
| 6 | 20%→15% ACC | 0.0 REJ | $70→$65 | BANK_A refinement |
| 7 | 15%→12% ACC | 0.0 REJ | $65→$62 | Further reduction |
| 8 | REJ (503 error) | REJ (503 error) | $62 | LLM service error |
| 9 | 12%→15% ACC | 0.0 REJ | $62→$57.50 | Optimal found |
| 10 | 0.15 REJ | 0.5 REJ | $57.50 | Stable #1 |
| 11 | 0.15 REJ | 0.75 REJ | $57.50 | Stable #2 |
| 12 | 0.18 REJ | 0.0 REJ | $57.50 | Stable #3 |
| 13 | 0.15 REJ | 1e-6 REJ | $57.50 | Stable #4 |
| 14 | 0.15 REJ | 0.0001 REJ | $57.50 | Stable #5 → CONVERGED |

### Key Observations

1. **Rapid Initial Convergence**: Both agents immediately moved to extreme policies in iteration 1 - BANK_A reduced to 20%, BANK_B to 0%

2. **Asymmetric Equilibrium Discovery**: BANK_B discovered the free-rider strategy immediately (0% liquidity), while BANK_A gradually found the optimal liquidity provision level (15%)

3. **BANK_A Policy Trajectory**: 50% → 20% → 15% → 12% → 15% (oscillation before settling)

4. **BANK_B Consistency**: Remained at 0% throughout after iteration 1, consistently rejecting any increase

5. **503 Error Handling**: System gracefully handled LLM service error in iteration 8 by rejecting both proposals and continuing

6. **Cost Breakdown**: The $57.50 final cost represents BANK_A's collateral cost (~15% × cost_rate) balanced against avoiding delay penalties

### Raw Output Excerpts

**Iteration 1 - Initial Optimization**:
```
BANK_A: 50%→20%, Delta +$30.00, ACCEPTED
BANK_B: 50%→0%, Delta +$55.00, ACCEPTED
```

**Iteration 9 - Final Accepted Change**:
```
BANK_A: 12%→15%, Delta +$4.50, ACCEPTED
Evaluation: $62.00 → $57.50 (-7.3%)
```

**Convergence**:
```
Experiment completed!
  Iterations: 15
  Converged: True
  Reason: Stability achieved (5 consecutive stable iterations)
```

---

## Experiment 2: 12-Period Stochastic

*Status: Pending*

---

## Experiment 3: 3-Period Joint Optimization

*Status: Pending*

---

## Analysis Notes

*Status: Pending*
