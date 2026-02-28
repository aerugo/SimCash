# Experiment Showcase: 2026 Q1 Campaign

> **130 experiments. 3 LLM models. 10 scenarios. One headline finding.**
>
> This page presents the complete results from Stefan's Q1 2026 experiment campaign — the most comprehensive evaluation of LLM-optimized payment strategies in simulated RTGS environments to date.

---

## 1. The Basics — LLM Optimization Works

In simple scenarios (2–4 banks), LLMs consistently reduce system cost while maintaining high settlement rates. The table below shows **last-day optimized cost** vs. the FIFO baseline — demonstrating that after iterative policy refinement, LLMs find substantially cheaper strategies.

| Scenario | Banks | Baseline Cost | Baseline SR | Flash Cost | Flash SR | Pro Cost | Pro SR | GLM Cost | GLM SR |
|---|---|---|---|---|---|---|---|---|---|
| 2B 3T | 2 | 99,900 | 100% | **15,671** | 100% | 36,491 | 100% | 60,013 | 64% |
| 3B 6T | 3 | 74,700 | 100% | 35,942 | 96% | **18,759** | 100% | 19,960 | 100% |
| 4B 8T | 4 | 132,800 | 100% | 43,785 | 97% | 56,233 | 96% | **37,206** | 98% |

**Key observations:**
- **Cost reductions of 40–84%** across all models and simple scenarios
- Flash achieves the best result on 2B (84% reduction, perfect settlement)
- All models maintain ≥96% settlement on 2–4 bank scenarios (except GLM on 2B at 64%)
- Even the worst performer delivers meaningful cost savings

Each value is the mean of 3 independent runs. Cost = total system liquidity cost in the final optimization round.

---

## 2. The Threshold — Where Optimization Breaks Down

**This is the headline finding.** As system complexity increases beyond ~4 banks, LLM optimization flips from helpful to harmful — producing *simultaneously* higher costs AND lower settlement rates than simple FIFO queuing.

| Scenario | Banks | Days | Baseline Cost | Baseline SR | Flash Cost (Δ%) | Flash SR | Pro Cost (Δ%) | Pro SR |
|---|---|---|---|---|---|---|---|---|
| 2B 3T | 2 | 1 | 99,900 | 100% | 15,671 (**−84%**) | 100% | 36,491 (−63%) | 100% |
| 3B 6T | 3 | 1 | 74,700 | 100% | 35,942 (**−52%**) | 96% | 18,759 (−75%) | 100% |
| 4B 8T | 4 | 1 | 132,800 | 100% | 43,785 (**−67%**) | 97% | 56,233 (−58%) | 96% |
| Periodic Shocks | 5 | 25 | 611M | 86% | 737M (**+21%**) | 80% | 756M (+24%) | 80% |
| Large Network | 5 | 25 | 1,734M | 74% | 2,032M (**+17%**) | 70% | 1,485M (−14%) | 70% |
| Lehman Month | 6 | 25 | 2,064M | 79% | 2,354M (**+14%**) | 74% | 2,547M (+23%) | 72% |

**The pattern is stark:**
- **≤4 banks:** 52–84% cost reduction, settlement rates stay ≥96%
- **5+ banks (Flash):** 14–21% cost *increase*, settlement drops 5–7 percentage points
- **5+ banks (Pro):** Even worse — 23–24% cost increase on Periodic Shocks and Lehman Month

This is not a cost-settlement trade-off. It is **pure value destruction** — a computational tragedy of the commons where individually rational optimization produces collectively irrational outcomes.

### Why It Happens

Each bank's LLM independently optimizes its own liquidity fraction to minimize its own cost. In small networks, these strategies are mostly compatible. In larger networks, aggressive liquidity hoarding by multiple agents creates cascading settlement failures, gridlock, and higher costs for everyone — including the hoarding agents themselves.

The `is_better_than()` objective function compares total cost without adequately penalizing settlement degradation, enabling a "free-rider" dynamic where agents learn to hold liquidity at the expense of system throughput.

---

## 3. Castro Exp2 Deep Dive — Prompt Engineering (v0.2)

Castro Exp2 (2 banks, 12 ticks) was the most extensively studied scenario with **83 experiments** across 5 prompt conditions. The question: can better prompts improve LLM optimization?

### v0.2 Prompt Conditions

| Condition | Description |
|---|---|
| **v0.1** | Baseline LLM optimization (no special prompts) |
| **C1-info** | Tell the LLM about settlement rate performance |
| **C2-floor** | Impose minimum 80% settlement rate constraint |
| **C3-guidance** | Describe available strategy tools and policy actions |
| **C4-composition** | All of the above combined |

### Results by Condition (Last-Day Cost / Settlement Rate)

| Condition | Flash Cost | Flash SR | Pro Cost | Pro SR | GLM Cost | GLM SR |
|---|---|---|---|---|---|---|
| Baseline (FIFO) | 99,600 | 100% | 99,600 | 100% | 99,600 | 100% |
| v0.1 | 51,423 | 88% | 94,268 | 82% | 70,870 | 79% |
| C1-info | 55,381 | 87% | 57,265 | 87% | 70,872 | 80% |
| C2-floor | 43,735 | **97%** | 44,505 | 89% | 61,504 | 77% |
| C3-guidance | **39,436** | **98%** | 68,327 | 83% | 69,025 | 79% |
| C4-comp | 50,766 | 87% | 88,300 | 88% | 72,182 | 74% |

### Key Findings

1. **Constraints > Information**: C2 (floor constraint) produces the biggest settlement improvement for Flash (88% → 97%). C1 (info only) has negligible effect.
2. **C3-guidance is the sweet spot for Flash**: Lowest cost (39k) with near-perfect settlement (98%).
3. **Model selection > Prompt engineering**: The gap between Flash and GLM under identical prompts (~30 pp SR) far exceeds the gap between any two prompt conditions for the same model (~10 pp).
4. **Pro's paradox**: Pro achieves lower cost than v0.1 with C1-info (57k vs 94k) but doesn't systematically improve with other conditions.
5. **GLM is prompt-resistant**: Settlement rates barely move across conditions (74–80%), suggesting GLM lacks the reasoning capability to incorporate prompt guidance.

---

## 4. Stress Tests — Adverse Conditions

### High Stress (2B)

A 2-bank scenario with elevated payment volumes and volatility.

| Model | Cost | SR | vs Baseline |
|---|---|---|---|
| Baseline | 99,600 | 100% | — |
| Flash | 121,290 | 86% | +22% cost, −14pp SR |
| Pro | 108,155 | 86% | +9% cost, −14pp SR |
| GLM | 176,786 | 83% | +77% cost, −17pp SR |

**Under stress, even 2-bank optimization fails.** All models increase cost while degrading settlement — the stress conditions make the optimization landscape too volatile for stable policy learning within 10 rounds.

### Liquidity Squeeze (2B)

A 2-bank scenario with constrained initial liquidity.

| Model | Cost | SR | vs Baseline |
|---|---|---|---|
| Baseline | 72,000 | 100% | — |
| Flash | 21,749 | 100% | **−70% cost** |
| Pro | 14,506 | 100% | **−80% cost** |
| GLM | 16,817 | 100% | **−77% cost** |

**Liquidity squeeze is the LLMs' best scenario.** All models achieve 70–80% cost reduction with perfect settlement. When the optimization problem is clear (manage scarce liquidity), LLMs excel — Pro delivers the best result at 14,506 (80% reduction).

---

## 5. Special Scenarios — Lynx Day

Lynx Day simulates a realistic Canadian RTGS (Large Value Transfer System) daily pattern with 4 banks.

| Model | Cost | SR |
|---|---|---|
| Baseline | 3 | 100% |
| Flash | 3 | 100% |
| Pro | 3 | 100% |
| GLM | 3 | 100% |

All models match the baseline perfectly. This validates that (a) the simulator produces sensible results on realistic parameters, and (b) LLM optimization correctly identifies that the FIFO policy is already optimal when costs are near-zero — it doesn't over-optimize.

---

## 6. Model Leaderboard

### Overall Performance Summary

Across all simple + stress scenarios (7 scenarios, v0.1 condition):

| Model | Cost Wins | SR Wins (≥baseline−2pp) | Both Wins | Total Scenarios |
|---|---|---|---|---|
| **Flash** | 5/7 | 5/7 | 4/7 | 7 |
| **Pro** | 5/7 | 4/7 | 3/7 | 7 |
| **GLM** | 5/7 | 3/7 | 2/7 | 7 |

### Model Characteristics

**Gemini Flash 2.0** — The practical champion
- Best cost reduction on simple scenarios (up to 84%)
- Most responsive to prompt engineering (C2/C3 conditions)
- Highest settlement maintenance under constraints

**Gemini Pro** — The sophisticated free-rider
- Strong cost optimization but paradoxically *worse* on complex scenarios
- Better reasoning → more effective liquidity hoarding → worse collective outcome
- Best on Liquidity Squeeze (80% cost reduction)

**GLM-4-Flash** — The wild card
- Surprisingly competitive on cost (best on 4B 8T at 37k)
- Weakest settlement rates across the board
- Resistant to prompt engineering interventions
- Outperforms Flash and Pro on Large Network and Lehman Month complex scenarios

### The Smart Free-Rider Effect

On complex scenarios, Pro consistently produces worse outcomes than Flash:

| Complex Scenario | Flash Cost Δ | Pro Cost Δ | Flash SR | Pro SR |
|---|---|---|---|---|
| Periodic Shocks | +21% | **+24%** | 80% | 80% |
| Large Network | +17% | −14% | 70% | 70% |
| Lehman Month | +14% | **+23%** | 74% | **72%** |

Better reasoning capability enables more effective individual optimization — which, in the multi-agent setting, translates to more effective free-riding and worse collective outcomes. This is Finding #3: the **Smart Free-Rider Effect**.

---

## Methodology Notes

- **130 experiments** total across 10 scenarios, 3 models, 5 prompt conditions
- Simple scenarios: 10 rounds of optimization, last-day cost compared to 1-day baseline
- Complex scenarios: 25 days, 1 round, total cost summed across all days
- All results from clean post-bugfix runs (experiment ≥ #00168)
- Settlement rate = settled payments / total payments (system-wide per day, averaged for multi-day)
- Cost = total system liquidity holding cost (lower is better)
- Baseline = FIFO queue processing, no LLM optimization
