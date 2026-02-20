# Discussion & Conclusion

## How Do Results Compare to Theory?

| Experiment | Predicted | Observed | Alignment |
|------------|-----------|----------|-----------|
| Exp 1 (Asymmetric) | Asymmetric | Asymmetric (role varies) | Partial ✓ |
| Exp 2 (Stochastic) | Symmetric, 10–30% | Symmetric, 5.7%–8.5% | Partial (lower magnitude) |
| Exp 3 (Symmetric) | Symmetric | Asymmetric + coordination failure | Deviation ✗ |

### Experiment 1: Partial Match

Theory predicts Bank A free-rides (A ≈ 0%, B ≈ 20%). Passes 1–2 confirmed this exactly,
with total costs at an efficient $27–28. But Pass 3 flipped the roles — Bank B went to 0%,
Bank A held 1.8%, and total costs ballooned to $101.78 vs $27.10. The learning
dynamics support multiple stable outcomes with very different efficiency. Bank A assumed
the free-rider role in 2 of 3 passes.

### Experiment 2: Symmetric but Lower Than Expected

Theory predicts both agents in 10–30%. We found symmetric allocations (Bank A averaged
7.0%, Bank B averaged 6.1%) —
all 3 passes had liquidity ratios below 2×. This contrasts sharply with the
6×+ ratios in deterministic experiments. However, allocations fell *below* the predicted
10–30% range.

Interestingly, while liquidity was symmetric, **costs were not**: Bank B paid about
2.7× more than Bank A ($218.07 vs
$79.37). Similar reserves, very different outcomes — likely
due to payment timing exposure differences.

### Experiment 3: Systematic Coordination Failure

Every pass produced coordination failure. Total costs ranged from $190.96 to $410.92,
all worse than the $100 baseline. Bank A was the free-rider in 2 of 3 passes.
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

1. **Small sample size** — Only 9 total runs. The patterns are suggestive
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

Across 9 independent runs, LLM agents found stable strategies through
reasoning alone — no explicit game theory needed. Three findings stand out:

**1. Stability ≠ optimality.** In symmetric games, agents consistently converged to
coordination failures. Both sides ended up worse than baseline. Unconditional acceptance
lets agents follow improving gradients into globally worse outcomes.

**2. Early moves determine outcomes.** Who becomes the free-rider depends on who moves
first, not on structural advantages. Path dependence, not cost structure, drives
equilibrium selection.

**3. Uncertainty helps.** Stochastic environments with bootstrap evaluation avoided
the coordination collapse of deterministic settings. All 3 stochastic
passes produced symmetric outcomes (ratios below 2×) vs 6×+ in deterministic experiments.

For payment systems: decentralized LLM optimizers can find stable strategies, but
stability alone doesn't guarantee efficiency. Central banks should expect coordination
traps from algorithmic liquidity management.

For multi-agent AI: sequential LLM optimization without coordination mechanisms reliably
produces outcomes where everyone is worse off. This matters for any multi-agent LLM deployment.
