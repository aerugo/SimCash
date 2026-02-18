# Teaching AI to Play the Liquidity Game

*How LLM agents learn to optimize cash allocation — and discover Nash equilibria along the way*

## The Game

Every morning, banks face a deceptively simple question: *how much cash should we set aside
for today's payments?*

In a Real-Time Gross Settlement (RTGS) system, payments settle individually and immediately —
no netting, no batching, no safety net. A bank must commit liquidity at the start of the day
to fund its outgoing obligations. Commit too much and you're paying opportunity costs on idle
capital all day. Commit too little and payments queue up, deadlines are missed, and penalty
costs pile up fast.

What makes this truly interesting is that it's not a solo optimization problem — it's a
**coordination game**. If Bank B commits generous liquidity, its payments to
Bank A settle quickly, giving A incoming cash to fund its own outgoing payments. Bank A
can then get away with committing less. Each bank's optimal strategy depends on what the
other bank does, but neither bank can observe the other's decision.

This is exactly the kind of problem that has clean theoretical solutions on paper but is
fiendishly hard in practice. So we asked: can AI agents figure it out?

## The Experiment

We set up two AI agents — BANK_A and BANK_B — each powered by a large language model (currently Gemini 2.5 Flash) with high
reasoning effort. Each agent controls a single parameter: `initial_liquidity_fraction`,
the fraction of its available liquidity pool to commit at the start of each simulated trading day.
The value ranges from 0% (commit nothing, extremely risky) to 100% (commit everything,
extremely expensive).

The loop works like a real cash manager doing end-of-day review:

1. The day starts. Each bank commits liquidity according to its current policy.
2. Our Rust simulation engine runs a full 12-tick trading day with stochastic payment arrivals
   (Poisson-distributed, ~2 payments per tick, log-normally distributed amounts).
3. The day ends. Costs are tallied — liquidity costs, delay penalties, deadline failures.
4. Each agent independently reviews its own performance: what went wrong, what went right,
   how much each cost component contributed.
5. Each agent proposes a new `initial_liquidity_fraction` for tomorrow.
6. The new policy is statistically validated via bootstrap paired comparison (50 resampled
   scenarios, 95% confidence interval). Only accepted if the improvement is real, not noise.

Critically, the agents are **information-isolated**. Each agent sees only its own
costs, its own settlement history, its own iteration trajectory. No counterparty balances, no
opponent policies, no shared state. The only signal about the other bank comes indirectly
through the timing of incoming payments — just like in a real RTGS system.

## What Happens: The Convergence Pattern

We ran this experiment multiple times (3 independent passes of up to 25 iterations each), and
a consistent pattern emerged:

**Day 0 — The expensive default.** Both agents start at 100% allocation. Every cent
of available liquidity is committed. Payments settle instantly (great!), but the liquidity cost
is enormous. Total costs are at their peak.

**Days 1–3 — The big drop.** Agents rapidly discover that they're massively
over-allocating. The LLM sees the cost breakdown, notices that liquidity cost dominates
everything else, and proposes dramatic cuts. Fractions drop from 100% to somewhere in the
20–40% range. Costs fall by 60–80%. This is the "obvious wins" phase — the agent doesn't
need sophisticated reasoning to see that 100% is wasteful.

**Days 4–7 — Fine-tuning.** Now it gets interesting. The agents are in the right
ballpark, but each adjustment is smaller and more nuanced. Cut too aggressively and delay
costs spike. The LLM starts reasoning about the tradeoff explicitly: "reducing from 15% to
12% saved X in liquidity costs but caused Y in additional delays." Adjustments shrink to
1–3 percentage points per iteration.

**Days 8–10+ — Near-equilibrium.** Policies stabilize. Proposed changes are tiny
(fractions of a percent) and many are rejected by the bootstrap validator — the improvement
isn't statistically significant. The agents have found their groove.

> 💡 The final converged values from our Experiment 2 replication: **BANK_A ≈ 8.8%,
> BANK_B ≈ 5.2%**. The BIS paper's analytical result for the same scenario:
> A = 8.5%, B = 6.3%. Different runs produce slightly different numbers (A ranges 5.7–8.8%,
> B ranges 5.2–6.3% across passes), but they consistently land in the same neighborhood.
> The agents are finding the right answer.

## The Cool Part: Emergent Coordination

Here's what makes this more than a parameter search: it's a **multi-agent game**.
BANK_A's optimal liquidity fraction depends on what BANK_B does, and vice versa. If B
commits more, A can commit less (because B's payments to A provide incoming liquidity).
The "right answer" isn't a fixed number — it's a *pair* of strategies that are
mutually best responses.

That's a Nash equilibrium. And our agents find it.

Neither agent knows the other exists as an optimizer. Neither agent can see the other's
policy or cost function. They're independently hill-climbing in a shared environment,
and the environment shifts under them as the other agent adapts. Despite this, they
converge to a stable pair of strategies where neither has an incentive to deviate — the
textbook definition of Nash equilibrium.

The convergence isn't always smooth. In some runs, we see brief oscillations where one
agent cuts liquidity, causing the other to experience more delays, prompting *that*
agent to increase its commitment, which then lets the first agent cut further. But these
oscillations dampen, and the system settles.

## What It Means

This result has implications beyond payment systems:

- **LLMs can discover game-theoretic equilibria through repeated play.** Without
  any explicit game theory in their training objective or prompts, these agents converge to
  Nash equilibria by independently optimizing against observed outcomes. The equilibrium
  emerges from the interaction, not from computation.
- **Statistical evaluation matters.** Our bootstrap paired comparison (50 samples,
  95% CI) prevents agents from chasing noise. Without it, agents in stochastic environments
  oscillate endlessly, accepting "improvements" that are just lucky draws. The statistical
  rigor is what makes convergence possible.
- **The gap between stability and optimality is real.** In our symmetric
  Experiment 3 (different from the stochastic Experiment 2 discussed here), agents converge
  to *stable but suboptimal* outcomes — one free-rides while the other overcommits.
  It's a Nash equilibrium, but both would be better off at the symmetric solution. Convergence
  doesn't mean the outcome is good.
- **Implications for policy testing.** If LLM agents can discover equilibria
  in simulated payment systems, regulators could use this approach to stress-test policy
  changes before deployment. What happens to bank behavior if you change the cost structure?
  The delay penalty? The deadline rules? Let the agents play it out and see where they land.

## Try It Yourself

SimCash is built for exploration. You can run the convergence experiment yourself right here
on this platform — configure a scenario, set the number of iterations, and watch the agents
learn in real time. Start with the Experiment 2 preset (12-tick stochastic, bootstrap
evaluation) and see how quickly the agents find the equilibrium.

Or try breaking it: crank up the delay costs, make the payment distributions wildly
asymmetric, or give one agent a much larger liquidity pool. The equilibrium shifts, and
watching the agents adapt is half the fun.

The code is open source on [GitHub](https://github.com/aerugo/SimCash).
We'd love to see what you discover.
