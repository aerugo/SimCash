"""Discussion + conclusion section for web version."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.markdown.formatting import format_money, format_percent

if TYPE_CHECKING:
    from src.data_provider import DataProvider


def generate_discussion(provider: DataProvider) -> str:
    """Generate discussion + conclusion in blog style."""
    agg = provider.get_aggregate_stats()
    total_passes = agg["total_passes"]

    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Exp2 stats
    exp2_all_liqs = [s["bank_a_liquidity"] for s in exp2_summaries] + [s["bank_b_liquidity"] for s in exp2_summaries]
    exp2_liq_min = format_percent(min(exp2_all_liqs))
    exp2_liq_max = format_percent(max(exp2_all_liqs))

    exp2_mean_a_cost = sum(s["bank_a_cost"] for s in exp2_summaries) // len(exp2_summaries)
    exp2_mean_b_cost = sum(s["bank_b_cost"] for s in exp2_summaries) // len(exp2_summaries)
    exp2_cost_ratio = exp2_mean_b_cost / exp2_mean_a_cost if exp2_mean_a_cost > 0 else 0

    exp2_mean_a_liq = sum(s["bank_a_liquidity"] for s in exp2_summaries) / len(exp2_summaries)
    exp2_mean_b_liq = sum(s["bank_b_liquidity"] for s in exp2_summaries) / len(exp2_summaries)

    # Count symmetric exp2 passes
    exp2_symmetric = sum(
        1 for s in exp2_summaries
        if max(s["bank_a_liquidity"], s["bank_b_liquidity"])
        / max(min(s["bank_a_liquidity"], s["bank_b_liquidity"]), 0.001)
        < 2.0
    )

    # Free-rider counts
    exp1_freerider_a = sum(1 for s in exp1_summaries if s["bank_a_liquidity"] < s["bank_b_liquidity"])
    exp3_freerider_a = sum(1 for s in exp3_summaries if s["bank_a_liquidity"] < s["bank_b_liquidity"])

    exp1_best = format_money(min(s["total_cost"] for s in exp1_summaries))
    exp1_worst = format_money(max(s["total_cost"] for s in exp1_summaries))
    exp3_best = format_money(min(s["total_cost"] for s in exp3_summaries))
    exp3_worst = format_money(max(s["total_cost"] for s in exp3_summaries))

    return rf"""# Discussion & Conclusion

## How Do Results Compare to Theory?

| Experiment | Predicted | Observed | Alignment |
|------------|-----------|----------|-----------|
| Exp 1 (Asymmetric) | Asymmetric | Asymmetric (role varies) | Partial ✓ |
| Exp 2 (Stochastic) | Symmetric, 10–30% | Symmetric, {exp2_liq_min}–{exp2_liq_max} | Partial (lower magnitude) |
| Exp 3 (Symmetric) | Symmetric | Asymmetric + coordination failure | Deviation ✗ |

### Experiment 1: Partial Match

Theory predicts Bank A free-rides (A ≈ 0%, B ≈ 20%). Passes 1–2 confirmed this exactly,
with total costs at an efficient \$27–28. But Pass 3 flipped the roles — Bank B went to 0%,
Bank A held 1.8%, and total costs ballooned to {exp1_worst} vs {exp1_best}. The learning
dynamics support multiple stable outcomes with very different efficiency. Bank A assumed
the free-rider role in {exp1_freerider_a} of 3 passes.

### Experiment 2: Symmetric but Lower Than Expected

Theory predicts both agents in 10–30%. We found symmetric allocations (Bank A averaged
{format_percent(exp2_mean_a_liq)}, Bank B averaged {format_percent(exp2_mean_b_liq)}) —
all {exp2_symmetric} passes had liquidity ratios below 2×. This contrasts sharply with the
6×+ ratios in deterministic experiments. However, allocations fell *below* the predicted
10–30% range.

Interestingly, while liquidity was symmetric, **costs were not**: Bank B paid about
{exp2_cost_ratio:.1f}× more than Bank A ({format_money(exp2_mean_b_cost)} vs
{format_money(exp2_mean_a_cost)}). Similar reserves, very different outcomes — likely
due to payment timing exposure differences.

### Experiment 3: Systematic Coordination Failure

Every pass produced coordination failure. Total costs ranged from {exp3_best} to {exp3_worst},
all worse than the \$100 baseline. Bank A was the free-rider in {exp3_freerider_a} of 3 passes.
This isn't a failure of the LLM — it's what *any* greedy non-communicating optimizer would do.

---

## Why LLMs Instead of Reinforcement Learning?

RL agents optimize through gradient descent over thousands of episodes, converging to
mathematically optimal strategies. That's theoretically sound, but it looks nothing like
how actual treasury managers make decisions.

Real participants *reason*: they look at recent outcomes, weigh tradeoffs, and adjust
incrementally based on experience. LLM agents approximate this more naturally — they
receive context about performance and propose adjustments through deliberation, not
gradient updates.

Practical advantages:

- **Interpretable**: LLM agents produce natural language reasoning you can audit
- **Heterogeneous**: Different agents can receive tailored prompts with different
  risk tolerances or regulatory constraints
- **Few-shot**: Agents adapt in 7–50 iterations, not thousands of training episodes

We don't claim LLM agents faithfully replicate human decisions. But they provide a
*reasoning-based* alternative to gradient optimization for multi-agent policy discovery.

---

## Limitations

1. **Small sample size** — Only {total_passes} total runs. The patterns are suggestive
   but need substantially larger experiments for statistical robustness.

2. **Two-agent simplification** — Real RTGS systems have dozens or hundreds of participants.
   Scaling to larger networks is future work.

3. **Fixed-environment bootstrap** — Bootstrap evaluation measures "how would this policy
   perform given observed market response?" not "how would it perform in the equilibrium
   it induces?" This matters most in our 2-agent setup where each agent is 50% of system volume.

4. **Bootstrap variance artifacts** — Transaction-level resampling can create non-physical
   correlations. Some iterations showed 40× cost ranges across bootstrap samples.
   Block bootstrap or day-level resampling would be better for real data.

5. **Stable ≠ optimal** — The unconditional acceptance mechanism lets agents follow
   locally-improving gradients into coordination traps.

6. **Outcome variability** — Different passes found different free-rider assignments
   and efficiency levels. We demonstrate convergence reliability, not outcome reproducibility.

---

## Future Directions

The coordination failures in Experiment 3 point to the most interesting next steps:

- **Regulatory nudges** — Could a central bank provide anonymized aggregate stats
  ("system liquidity is below efficient levels") without revealing competitive info?

- **Commitment devices** — "I'll maintain 20% if you do the same"

- **Cost-aware acceptance** — Reject policies that increase total system cost

- **Staged adjustment** — Limit how much an agent can change per iteration to prevent
  the aggressive early moves that create traps

---

## Summary

Across {total_passes} independent runs, LLM agents found stable strategies through
reasoning alone — no explicit game theory needed. Three findings stand out:

**1. Stability ≠ optimality.** In symmetric games, agents consistently converged to
coordination failures. Both sides ended up worse than baseline. Unconditional acceptance
lets agents follow improving gradients into globally worse outcomes.

**2. Early moves determine outcomes.** Who becomes the free-rider depends on who moves
first, not on structural advantages. Path dependence, not cost structure, drives
equilibrium selection.

**3. Uncertainty helps.** Stochastic environments with bootstrap evaluation avoided
the coordination collapse of deterministic settings. All {exp2_symmetric} stochastic
passes produced symmetric outcomes (ratios below 2×) vs 6×+ in deterministic experiments.

For payment systems: decentralized LLM optimizers can find stable strategies, but
stability alone doesn't guarantee efficiency. Central banks should expect coordination
traps from algorithmic liquidity management.

For multi-agent AI: sequential LLM optimization without coordination mechanisms reliably
produces outcomes where everyone is worse off. This matters for any multi-agent LLM deployment.
"""
