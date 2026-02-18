# LLM Optimization Deep Dive

*How AI agents learn, evaluate, and converge*

The LLM optimization system is the engine that drives policy improvement. It orchestrates
a multi-day loop where each agent independently analyzes its performance, proposes improved
policies, and statistically validates improvements before adoption.

## The Optimization Loop

Each iteration follows five phases:

1. **Simulate** — Run a full day with current policies. The Rust engine produces
   tick-by-tick events, cost breakdowns, and settlement outcomes.
2. **Evaluate** — Compute each agent's costs. In bootstrap mode, this means
   running the policy on 50 resampled transaction sets to get statistical estimates.
3. **Propose** — For each agent independently, build a 50,000+ token prompt
   with cost analysis, simulation traces, iteration history, and parameter trajectories.
   The LLM proposes a new policy JSON.
4. **Validate** — The proposed policy is checked against scenario constraints:
   parameter ranges, allowed fields, valid actions. Invalid policies get up to 3 retries
   with error feedback appended to the prompt.
5. **Accept or Reject** — Compare new vs old policy on the same samples
   (paired comparison). Accept only if the improvement is statistically significant.

```
Iteration 1: [Simulate] → [Evaluate] → [Propose A] → [Propose B] → [Accept/Reject]
Iteration 2: [Simulate] → [Evaluate] → [Propose A] → [Propose B] → [Accept/Reject]
...
Iteration N: [Simulate] → [Evaluate] → [Converged!]
```

## Bootstrap Evaluation

In stochastic scenarios, a single simulation run is unreliable — random payment arrivals
mean the same policy can look great or terrible depending on the draw. Bootstrap evaluation
solves this with **paired comparison**:

1. Generate N bootstrap samples (default: 50) by resampling from observed transactions
2. Run *both* the old and new policy on *each* sample
3. Compute the cost difference (delta) per sample
4. Accept if: mean delta > 0, 95% CI doesn't cross zero, and CV ≤ 0.5

> ℹ️ Using the **same samples** for both policies is crucial. It eliminates
> sample-to-sample variance — the only variation comes from the policy difference itself.
> This is far more sensitive than comparing means from independent samples.

Each agent is evaluated in a **3-agent sandbox**: SOURCE → AGENT → SINK.
The SOURCE generates transactions, the AGENT is the one being evaluated, and the SINK
absorbs outgoing payments. This isolation ensures that an agent's evaluation isn't
contaminated by other agents' changing policies.

## Multi-Agent Isolation

Agent isolation is enforced at every level of the system:

- **Event filtering** — Each agent's prompt contains only its own transactions, costs, and state changes. No counterparty balances or policies are revealed.
- **Separate history** — Each agent has its own iteration history, best-cost tracking, and parameter trajectories.
- **Independent seeds** — Each agent gets different RNG seeds per iteration via a SHA-256 seed matrix.
- **Isolated evaluation** — Bootstrap samples and sandbox simulations are per-agent.

This isolation is what enables Nash equilibrium finding. Each agent independently optimizes
against the current state of the world (which includes other agents' fixed policies).
If agents could see each other's strategies, they could game the optimization or coordinate
in ways that don't reflect real RTGS incentives.

## Nash Equilibrium and Convergence

In **deterministic-temporal** mode, convergence is detected when all agents'
policies remain unchanged for a stability window (typically 5 iterations). Since deterministic
evaluation gives identical costs for identical policies, stability means no agent can
improve — which is precisely the definition of a Nash equilibrium.

In **bootstrap** mode, convergence uses multiple signals:

- **Coefficient of variation (CV)** — When cost variance drops below a threshold, the policy is stable
- **Trend analysis** — Costs should be flat or declining, not oscillating
- **Regret** — How far the current cost is from the best-ever cost

> ⚠️ Convergence to a Nash equilibrium doesn't mean the outcome is *good*. In
> Experiment 3, agents reliably converge to stable profiles where one agent free-rides —
> a Nash equilibrium, but Pareto-dominated. Both agents would be better off at the
> symmetric equilibrium, but neither has an individual incentive to move there.

## Optimization Interval

By default, agents optimize after every simulated day. But you can configure the
**optimization interval** — how many days pass between optimization rounds.
With an interval of 5, the agent plays 5 days with its current policy, accumulates more
data, and then proposes a single improvement.

- **Interval = 1** — Fastest learning, but each decision is based on a single day's data
- **Interval = 5–10** — More data per decision, smoother convergence, less sensitive to single-day noise
- **Interval = N (large)** — Almost batch optimization; useful when you want agents to commit to strategies

## Three Evaluation Modes

| Mode | Acceptance Rule | Best For |
|------|----------------|----------|
| `bootstrap` | Statistical significance (95% CI) + variance check | Stochastic scenarios — rigorous comparison |
| `deterministic-pairwise` | new_cost < old_cost on same seed | Single-agent deterministic optimization |
| `deterministic-temporal` | Always accept; converge on policy stability | Multi-agent Nash equilibrium finding |

## What the LLM Sees (and Doesn't)

The system prompt includes a **filtered policy schema** — only the actions,
fields, and parameters that the scenario constraints allow. The LLM literally cannot
see documentation for elements it isn't allowed to use, preventing hallucinated references
to unavailable features.

The user prompt includes cost breakdowns with priority flags (🔴 dominant cost, 🟡 significant,
🟢 minor), automated trend detection (improving/worsening/oscillating), settlement rate
alerts, and full iteration history with acceptance status markers (⭐ BEST / ✅ KEPT / ❌ REJECTED).
