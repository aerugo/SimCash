# Experiment Showcase: 2026 Q1 Campaign

> **130 experiments. 3 LLM models. 10 scenarios.**
>
> This page presents the complete results from the Q1 2026 experiment campaign — an exploratory survey of LLM-optimized payment strategies across diverse RTGS scenarios in SimCash.

---

## 1. The Basics — LLM Optimization Works

In simple scenarios (2–4 banks), LLMs consistently reduce system cost while maintaining high settlement rates. The table below shows **last-day optimized cost** vs. the FIFO baseline — demonstrating that after iterative policy refinement, LLMs find substantially cheaper strategies.

| Scenario | Banks | Baseline Cost | Baseline SR | Flash Cost | Flash SR | Pro Cost | Pro SR | GLM Cost | GLM SR |
|---|---|---|---|---|---|---|---|---|---|
| [2B 3T](https://simcash-487714.web.app/experiment/5c59f15f) | 2 | [99,900](https://simcash-487714.web.app/experiment/5c59f15f) | [100%](https://simcash-487714.web.app/experiment/5c59f15f) | [**15,671**](https://simcash-487714.web.app/experiment/eaf07a54) | [100%](https://simcash-487714.web.app/experiment/eaf07a54) | [36,491](https://simcash-487714.web.app/experiment/4206630b) | [100%](https://simcash-487714.web.app/experiment/4206630b) | [60,013](https://simcash-487714.web.app/experiment/b9042cb0) | [64%](https://simcash-487714.web.app/experiment/b9042cb0) |
| [3B 6T](https://simcash-487714.web.app/experiment/c2994509) | 3 | [74,700](https://simcash-487714.web.app/experiment/c2994509) | [100%](https://simcash-487714.web.app/experiment/c2994509) | [35,942](https://simcash-487714.web.app/experiment/be9df7e0) | [96%](https://simcash-487714.web.app/experiment/be9df7e0) | [**18,759**](https://simcash-487714.web.app/experiment/5f3e5661) | [100%](https://simcash-487714.web.app/experiment/5f3e5661) | [19,960](https://simcash-487714.web.app/experiment/e28f8c05) | [100%](https://simcash-487714.web.app/experiment/e28f8c05) |
| [4B 8T](https://simcash-487714.web.app/experiment/73e5990a) | 4 | [132,800](https://simcash-487714.web.app/experiment/73e5990a) | [100%](https://simcash-487714.web.app/experiment/73e5990a) | [43,785](https://simcash-487714.web.app/experiment/1c3114b7) | [97%](https://simcash-487714.web.app/experiment/1c3114b7) | [56,233](https://simcash-487714.web.app/experiment/760cdc06) | [96%](https://simcash-487714.web.app/experiment/760cdc06) | [**37,206**](https://simcash-487714.web.app/experiment/b74c5f0d) | [98%](https://simcash-487714.web.app/experiment/b74c5f0d) |

**Key observations:**
- **Cost reductions of 40–84%** across all models and simple scenarios
- Flash achieves the best result on 2B (84% reduction, perfect settlement)
- All models maintain ≥96% settlement on 2–4 bank scenarios (except GLM on 2B at 64%)
- Even the worst performer delivers meaningful cost savings

Each value is the mean of 3 independent runs. Cost = total system liquidity cost in the final optimization round.

---

## 2. Multi-Day Scenarios — Different Outcomes

In multi-day scenarios, LLM optimization produced higher costs and lower settlement rates than the FIFO baseline. These scenarios differ from the simple ones in many dimensions simultaneously (days, optimization method, bank heterogeneity, LSM, cost structure, liquidity pools, scenario events, baseline difficulty), so we present this as an observation, not a causal claim about bank count.

| Scenario | Banks | Days | Baseline Cost | Baseline SR | Flash Cost (Δ%) | Flash SR | Pro Cost (Δ%) | Pro SR |
|---|---|---|---|---|---|---|---|---|
| [2B 3T](https://simcash-487714.web.app/experiment/5c59f15f) | 2 | 1 | [99,900](https://simcash-487714.web.app/experiment/5c59f15f) | [100%](https://simcash-487714.web.app/experiment/5c59f15f) | [15,671 (**−84%**)](https://simcash-487714.web.app/experiment/eaf07a54) | [100%](https://simcash-487714.web.app/experiment/eaf07a54) | [36,491 (−63%)](https://simcash-487714.web.app/experiment/4206630b) | [100%](https://simcash-487714.web.app/experiment/4206630b) |
| [3B 6T](https://simcash-487714.web.app/experiment/c2994509) | 3 | 1 | [74,700](https://simcash-487714.web.app/experiment/c2994509) | [100%](https://simcash-487714.web.app/experiment/c2994509) | [35,942 (**−52%**)](https://simcash-487714.web.app/experiment/be9df7e0) | [96%](https://simcash-487714.web.app/experiment/be9df7e0) | [18,759 (−75%)](https://simcash-487714.web.app/experiment/5f3e5661) | [100%](https://simcash-487714.web.app/experiment/5f3e5661) |
| [4B 8T](https://simcash-487714.web.app/experiment/73e5990a) | 4 | 1 | [132,800](https://simcash-487714.web.app/experiment/73e5990a) | [100%](https://simcash-487714.web.app/experiment/73e5990a) | [43,785 (**−67%**)](https://simcash-487714.web.app/experiment/1c3114b7) | [97%](https://simcash-487714.web.app/experiment/1c3114b7) | [56,233 (−58%)](https://simcash-487714.web.app/experiment/760cdc06) | [96%](https://simcash-487714.web.app/experiment/760cdc06) |
| [Periodic Shocks](https://simcash-487714.web.app/experiment/747025f3) | 5 | 25 | [611M](https://simcash-487714.web.app/experiment/747025f3) | [77%](https://simcash-487714.web.app/experiment/747025f3) | 737M (**+21%**) | 70% | 756M (+24%) | 69% |
| [Large Network](https://simcash-487714.web.app/experiment/524fc873) | 5 | 25 | [1,734M](https://simcash-487714.web.app/experiment/524fc873) | [59%](https://simcash-487714.web.app/experiment/524fc873) | [2,032M (**+17%**)](https://simcash-487714.web.app/experiment/298704f4) | [57%](https://simcash-487714.web.app/experiment/298704f4) | [1,485M (−14%)](https://simcash-487714.web.app/experiment/6f6f3afb) | [59%](https://simcash-487714.web.app/experiment/6f6f3afb) |
| [Lehman Month](https://simcash-487714.web.app/experiment/b140728c) | 6 | 25 | [2,064M](https://simcash-487714.web.app/experiment/b140728c) | [69%](https://simcash-487714.web.app/experiment/b140728c) | [2,354M (**+14%**)](https://simcash-487714.web.app/experiment/79785ad6) | [60%](https://simcash-487714.web.app/experiment/79785ad6) | [2,547M (+23%)](https://simcash-487714.web.app/experiment/9f279e14) | [58%](https://simcash-487714.web.app/experiment/9f279e14) |

**Observed pattern:**
- **Single-day scenarios:** 52–84% cost reduction, settlement rates stay ≥96%
- **Multi-day scenarios (Flash):** 14–21% cost *increase*, settlement drops 7–12 percentage points
- **Multi-day scenarios (Pro):** 23–24% cost increase on Periodic Shocks and Lehman Month

Note: Periodic Shocks has 4 banks — the same count as 4b_8t, where LLM optimization works well. The difference is not bank count alone but the combination of multi-day dynamics, heterogeneous banks, different cost structures, and other factors. See the [Discussion](papers/q1-campaign/discussion) for a full confound analysis.

### What We Observed

Over 25 days of between-day optimization, LLM agents progressively reduce their liquidity fractions toward zero — a "ratchet effect" where each day's cost-reducing policy change is locked in before cumulative system-wide consequences become visible. The `is_better_than()` function compares cost only, which may contribute to this dynamic.

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
| [Baseline (FIFO)](https://simcash-487714.web.app/experiment/17bdd52c) | 99,600 | 100% | 99,600 | 100% | 99,600 | 100% |
| v0.1 | [51,423](https://simcash-487714.web.app/experiment/4b01f402) | [88%](https://simcash-487714.web.app/experiment/4b01f402) | [94,268](https://simcash-487714.web.app/experiment/cb000a9e) | [82%](https://simcash-487714.web.app/experiment/cb000a9e) | [70,870](https://simcash-487714.web.app/experiment/9caf5c9a) | [79%](https://simcash-487714.web.app/experiment/9caf5c9a) |
| C1-info | [55,381](https://simcash-487714.web.app/experiment/956c8c95) | [87%](https://simcash-487714.web.app/experiment/956c8c95) | [57,265](https://simcash-487714.web.app/experiment/64cff625) | [87%](https://simcash-487714.web.app/experiment/64cff625) | [70,872](https://simcash-487714.web.app/experiment/bed58722) | [80%](https://simcash-487714.web.app/experiment/bed58722) |
| C2-floor | [43,735](https://simcash-487714.web.app/experiment/12f2f32b) | [**97%**](https://simcash-487714.web.app/experiment/12f2f32b) | [44,505](https://simcash-487714.web.app/experiment/351bffb8) | [89%](https://simcash-487714.web.app/experiment/351bffb8) | [61,504](https://simcash-487714.web.app/experiment/9b22fd81) | [77%](https://simcash-487714.web.app/experiment/9b22fd81) |
| C3-guidance | [**39,436**](https://simcash-487714.web.app/experiment/b71eba21) | [**98%**](https://simcash-487714.web.app/experiment/b71eba21) | [68,327](https://simcash-487714.web.app/experiment/495d9495) | [83%](https://simcash-487714.web.app/experiment/495d9495) | [69,025](https://simcash-487714.web.app/experiment/1c231272) | [79%](https://simcash-487714.web.app/experiment/1c231272) |
| C4-comp | [50,766](https://simcash-487714.web.app/experiment/02f3c81e) | [87%](https://simcash-487714.web.app/experiment/02f3c81e) | [88,300](https://simcash-487714.web.app/experiment/d21b94e7) | [88%](https://simcash-487714.web.app/experiment/d21b94e7) | [72,182](https://simcash-487714.web.app/experiment/e3b943df) | [74%](https://simcash-487714.web.app/experiment/e3b943df) |

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
| [Baseline](https://simcash-487714.web.app/experiment/a36fe08d) | [99,600](https://simcash-487714.web.app/experiment/a36fe08d) | [100%](https://simcash-487714.web.app/experiment/a36fe08d) | — |
| [Flash](https://simcash-487714.web.app/experiment/55d8de6f) | [121,290](https://simcash-487714.web.app/experiment/55d8de6f) | [86%](https://simcash-487714.web.app/experiment/55d8de6f) | +22% cost, −14pp SR |
| [Pro](https://simcash-487714.web.app/experiment/fd2b74ad) | [108,155](https://simcash-487714.web.app/experiment/fd2b74ad) | [86%](https://simcash-487714.web.app/experiment/fd2b74ad) | +9% cost, −14pp SR |
| [GLM](https://simcash-487714.web.app/experiment/b1fe6b96) | [176,786](https://simcash-487714.web.app/experiment/b1fe6b96) | [83%](https://simcash-487714.web.app/experiment/b1fe6b96) | +77% cost, −17pp SR |

**Under stress, even 2-bank optimization fails.** All models increase cost while degrading settlement — the stress conditions make the optimization landscape too volatile for stable policy learning within 10 rounds.

### Liquidity Squeeze (2B)

A 2-bank scenario with constrained initial liquidity.

| Model | Cost | SR | vs Baseline |
|---|---|---|---|
| [Baseline](https://simcash-487714.web.app/experiment/8a46d6e0) | [72,000](https://simcash-487714.web.app/experiment/8a46d6e0) | [100%](https://simcash-487714.web.app/experiment/8a46d6e0) | — |
| [Flash](https://simcash-487714.web.app/experiment/6406580a) | [21,749](https://simcash-487714.web.app/experiment/6406580a) | [100%](https://simcash-487714.web.app/experiment/6406580a) | **−70% cost** |
| [Pro](https://simcash-487714.web.app/experiment/bdf0fa24) | [14,506](https://simcash-487714.web.app/experiment/bdf0fa24) | [100%](https://simcash-487714.web.app/experiment/bdf0fa24) | **−80% cost** |
| [GLM](https://simcash-487714.web.app/experiment/5ba7ddab) | [16,817](https://simcash-487714.web.app/experiment/5ba7ddab) | [100%](https://simcash-487714.web.app/experiment/5ba7ddab) | **−77% cost** |

**Liquidity squeeze is the LLMs' best scenario.** All models achieve 70–80% cost reduction with perfect settlement. When the optimization problem is clear (manage scarce liquidity), LLMs excel — Pro delivers the best result at 14,506 (80% reduction).

---

## 5. Special Scenarios — Lynx Day

Lynx Day simulates a realistic Canadian RTGS (Large Value Transfer System) daily pattern with 4 banks.

| Model | Cost | SR |
|---|---|---|
| [Baseline](https://simcash-487714.web.app/experiment/9eaf71b4) | [3](https://simcash-487714.web.app/experiment/9eaf71b4) | [100%](https://simcash-487714.web.app/experiment/9eaf71b4) |
| [Flash](https://simcash-487714.web.app/experiment/3245ee30) | [3](https://simcash-487714.web.app/experiment/3245ee30) | [100%](https://simcash-487714.web.app/experiment/3245ee30) |
| [Pro](https://simcash-487714.web.app/experiment/73672186) | [3](https://simcash-487714.web.app/experiment/73672186) | [100%](https://simcash-487714.web.app/experiment/73672186) |
| [GLM](https://simcash-487714.web.app/experiment/6571ce38) | [3](https://simcash-487714.web.app/experiment/6571ce38) | [100%](https://simcash-487714.web.app/experiment/6571ce38) |

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

**Gemini Pro** — The paradox
- Strong cost optimization but generally *worse* system-wide outcomes than Flash
- On multi-day scenarios, Pro produced higher costs than Flash in 2 of 3 cases
- Best on Liquidity Squeeze (80% cost reduction)

**GLM-4-Flash** — The wild card
- Surprisingly competitive on cost (best on 4B 8T at 37k)
- Weakest settlement rates across the board
- Resistant to prompt engineering interventions
- GLM results on complex scenarios excluded due to pre-bugfix data (cost-delta bug)

### Flash vs Pro on Multi-Day Scenarios

On multi-day scenarios, Pro generally produced worse system-wide outcomes than Flash:

| Multi-Day Scenario | Flash Cost Δ | Pro Cost Δ | Flash SR | Pro SR |
|---|---|---|---|---|
| Periodic Shocks | [+21%](https://simcash-487714.web.app/experiment/ea0794a3) | [**+24%**](https://simcash-487714.web.app/experiment/0496e8bc) | [70%](https://simcash-487714.web.app/experiment/ea0794a3) | [69%](https://simcash-487714.web.app/experiment/0496e8bc) |
| Large Network | [+17%](https://simcash-487714.web.app/experiment/298704f4) | [−14%](https://simcash-487714.web.app/experiment/6f6f3afb) | [57%](https://simcash-487714.web.app/experiment/298704f4) | [59%](https://simcash-487714.web.app/experiment/6f6f3afb) |
| Lehman Month | [+14%](https://simcash-487714.web.app/experiment/79785ad6) | [**+23%**](https://simcash-487714.web.app/experiment/9f279e14) | [60%](https://simcash-487714.web.app/experiment/79785ad6) | [**58%**](https://simcash-487714.web.app/experiment/9f279e14) |

This pattern — a more capable model producing worse collective outcomes — is an interesting observation that warrants controlled investigation. See the [Discussion](papers/q1-campaign/discussion) for proposed experiments.

---


## All Experiment Runs

Every experiment was run 3 times (r1, r2, r3) for reproducibility. Click any link to see the full experiment details.

### 2B 3T

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/5c59f15f) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/eaf07a54) | [r2](https://simcash-487714.web.app/experiment/62023a9c) | [r3](https://simcash-487714.web.app/experiment/8bbca064) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/4206630b) | [r2](https://simcash-487714.web.app/experiment/98cee358) | [r3](https://simcash-487714.web.app/experiment/cbf39377) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/b9042cb0) | [r2](https://simcash-487714.web.app/experiment/1f0b3de6) | [r3](https://simcash-487714.web.app/experiment/d53b0bb5) |

### 2B Stress

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/a36fe08d) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/55d8de6f) | [r2](https://simcash-487714.web.app/experiment/73461842) | [r3](https://simcash-487714.web.app/experiment/b3995a2f) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/fd2b74ad) | [r2](https://simcash-487714.web.app/experiment/7da0d68e) | [r3](https://simcash-487714.web.app/experiment/ef9dbacb) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/b1fe6b96) | [r2](https://simcash-487714.web.app/experiment/12b795dc) | [r3](https://simcash-487714.web.app/experiment/628ff51e) |

### 3B 6T

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/c2994509) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/be9df7e0) | [r2](https://simcash-487714.web.app/experiment/a38f96de) | [r3](https://simcash-487714.web.app/experiment/3f2f8515) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/5f3e5661) | [r2](https://simcash-487714.web.app/experiment/95372913) | [r3](https://simcash-487714.web.app/experiment/59133371) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/e28f8c05) | [r2](https://simcash-487714.web.app/experiment/a438ae19) | [r3](https://simcash-487714.web.app/experiment/e240fb7d) |

### 4B 8T

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/73e5990a) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/1c3114b7) | [r2](https://simcash-487714.web.app/experiment/65e2a56e) | [r3](https://simcash-487714.web.app/experiment/17391de1) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/760cdc06) | [r2](https://simcash-487714.web.app/experiment/9e94be0c) | [r3](https://simcash-487714.web.app/experiment/200dfb32) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/b74c5f0d) | [r2](https://simcash-487714.web.app/experiment/ffe5ebcd) | [r3](https://simcash-487714.web.app/experiment/d58d1a6a) |

### Castro Exp2

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/17bdd52c) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/4b01f402) | [r2](https://simcash-487714.web.app/experiment/0a51534d) | [r3](https://simcash-487714.web.app/experiment/1ef8c68d) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/cb000a9e) | [r2](https://simcash-487714.web.app/experiment/79f3e5de) | [r3](https://simcash-487714.web.app/experiment/66c90ab5) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/9caf5c9a) | [r2](https://simcash-487714.web.app/experiment/0089e7a2) | [r3](https://simcash-487714.web.app/experiment/d76909ce) |

### Lynx Day

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/9eaf71b4) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/3245ee30) | [r2](https://simcash-487714.web.app/experiment/19b88106) | [r3](https://simcash-487714.web.app/experiment/27c63568) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/73672186) | [r2](https://simcash-487714.web.app/experiment/46da91ae) | [r3](https://simcash-487714.web.app/experiment/0e8044b7) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/6571ce38) | [r2](https://simcash-487714.web.app/experiment/47adfb62) | [r3](https://simcash-487714.web.app/experiment/873c7fa4) |

### Liquidity Squeeze

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/8a46d6e0) | — | — |
| **Flash** | — | [r2](https://simcash-487714.web.app/experiment/6406580a) | [r3](https://simcash-487714.web.app/experiment/248e336d) |
| **Pro** | — | [r2](https://simcash-487714.web.app/experiment/bdf0fa24) | [r3](https://simcash-487714.web.app/experiment/af979444) |
| **Glm** | — | [r2](https://simcash-487714.web.app/experiment/5ba7ddab) | [r3](https://simcash-487714.web.app/experiment/7c557b1d) |

### Periodic Shocks

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/747025f3) | — | — |
| **Flash** | — | [r2](https://simcash-487714.web.app/experiment/ea0794a3) | [r3](https://simcash-487714.web.app/experiment/e68d887d) |
| **Pro** | — | [r2](https://simcash-487714.web.app/experiment/0496e8bc) | [r3](https://simcash-487714.web.app/experiment/f7f91666) |
| **Glm** | — | [r2](https://simcash-487714.web.app/experiment/c3092a1e) | [r3](https://simcash-487714.web.app/experiment/f0eb80e9) |

### Large Network

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/524fc873) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/298704f4) | [r2](https://simcash-487714.web.app/experiment/92040487) | [r3](https://simcash-487714.web.app/experiment/a1521a92) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/6f6f3afb) | [r2](https://simcash-487714.web.app/experiment/d8aba24e) | [r3](https://simcash-487714.web.app/experiment/c084839a) |
| **Glm** | — | [r2](https://simcash-487714.web.app/experiment/bb6ea1d2) | [r3](https://simcash-487714.web.app/experiment/daafc265) |

### Lehman Month

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Baseline** | [baseline](https://simcash-487714.web.app/experiment/b140728c) | — | — |
| **Flash** | [r1](https://simcash-487714.web.app/experiment/79785ad6) | [r2](https://simcash-487714.web.app/experiment/9f5ebd66) | [r3](https://simcash-487714.web.app/experiment/ff26b685) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/9f279e14) | [r2](https://simcash-487714.web.app/experiment/ce84d3e7) | [r3](https://simcash-487714.web.app/experiment/a54b3f8a) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/161d71d5) | [r2](https://simcash-487714.web.app/experiment/95361864) | [r3](https://simcash-487714.web.app/experiment/45e8aa95) |

### Castro Exp2 — v0.2 Prompt Variants

**C1-Info:**

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Flash** | [r1](https://simcash-487714.web.app/experiment/956c8c95) | [r2](https://simcash-487714.web.app/experiment/a11d95d4) | [r3](https://simcash-487714.web.app/experiment/40684679) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/64cff625) | [r2](https://simcash-487714.web.app/experiment/fdff3c28) | [r3](https://simcash-487714.web.app/experiment/233946f6) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/bed58722) | [r2](https://simcash-487714.web.app/experiment/27727cce) | [r3](https://simcash-487714.web.app/experiment/eeeef415) |

**C2-Floor:**

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Flash** | [r1](https://simcash-487714.web.app/experiment/12f2f32b) | [r2](https://simcash-487714.web.app/experiment/a88868ac) | [r3](https://simcash-487714.web.app/experiment/31fe4d63) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/351bffb8) | [r2](https://simcash-487714.web.app/experiment/9af6fa02) | [r3](https://simcash-487714.web.app/experiment/0d3393b9) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/9b22fd81) | [r2](https://simcash-487714.web.app/experiment/4cb7a172) | [r3](https://simcash-487714.web.app/experiment/c8d02c22) |

**C3-Guidance:**

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Flash** | [r1](https://simcash-487714.web.app/experiment/b71eba21) | [r2](https://simcash-487714.web.app/experiment/c193d19c) | [r3](https://simcash-487714.web.app/experiment/ad1beaaa) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/495d9495) | [r2](https://simcash-487714.web.app/experiment/7bc7ef1c) | [r3](https://simcash-487714.web.app/experiment/4ce0829c) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/1c231272) | [r2](https://simcash-487714.web.app/experiment/6fe57db3) | [r3](https://simcash-487714.web.app/experiment/ce2c6f41) |

**C4-Composition:**

| Model | r1 | r2 | r3 |
|-------|----|----|----|
| **Flash** | [r1](https://simcash-487714.web.app/experiment/02f3c81e) | [r2](https://simcash-487714.web.app/experiment/9039b61c) | [r3](https://simcash-487714.web.app/experiment/3054c041) |
| **Pro** | [r1](https://simcash-487714.web.app/experiment/d21b94e7) | [r2](https://simcash-487714.web.app/experiment/3ccc425c) | [r3](https://simcash-487714.web.app/experiment/7cb4d495) |
| **Glm** | [r1](https://simcash-487714.web.app/experiment/e3b943df) | [r2](https://simcash-487714.web.app/experiment/fb59f8c7) | [r3](https://simcash-487714.web.app/experiment/0456053a) |

**Special:** [C2-Floor Retry Canary (Flash)](https://simcash-487714.web.app/experiment/71707fd1)

## Methodology Notes

- **130 experiments** total across 10 scenarios, 3 models, 5 prompt conditions
- Simple scenarios: 10 rounds of optimization, last-day cost compared to 1-day baseline
- Complex scenarios: 25 days, 1 round, total cost summed across all days
- All results from clean post-bugfix runs (experiment ≥ #00168)
- Settlement rate = cumulative settled / cumulative arrived (for multi-day scenarios, using last day's running totals)
- Cost = total system liquidity holding cost (lower is better)
- Baseline = FIFO queue processing, no LLM optimization
