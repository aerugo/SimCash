# From FIFO to Nash: The Evolution of Payment Strategies

*How payment processing strategies evolved from simple queues to AI-discovered equilibria*

## FIFO: The Reliable Baseline

First In, First Out. It's the simplest possible payment processing strategy: payments
arrive, they go into a queue, and they're processed in order. No prioritization, no
strategic timing, no adaptation. FIFO is what happens when you don't make a decision —
and in many real RTGS systems, it's essentially what banks do by default.

FIFO has real virtues. It's predictable — every participant knows exactly how the queue
behaves. It's fair — no payment gets special treatment. It's easy to implement, easy to
audit, and easy to reason about. For decades, this was good enough.

But "good enough" isn't optimal. FIFO treats a €10 million time-critical CLS settlement
the same as a €500 internal transfer. It doesn't account for incoming payments that might
arrive in the next tick and provide the liquidity needed to clear the queue naturally. It
can't distinguish between a temporary liquidity shortage (where delaying briefly would be
costless) and a genuine funding gap (where delay compounds into failure). FIFO is a strategy
that ignores all available information — and in a system where information is abundant,
that's leaving money on the table.

## The Strategy Space

SimCash's policy engine reveals just how much room there is beyond FIFO. At every decision
point — each time a payment could be processed or a bank-level action could be taken — an
agent chooses from **16 distinct actions**:

- **Payment actions:** Release (process immediately), Delay (hold for later),
  Queue (add to back of queue), Prioritize (move to front), Split (partial release), and
  several conditional variants that depend on current state.
- **Bank actions:** NoAction (do nothing), RequestLiquidity (ask the central
  bank for more), ReturnLiquidity (give back excess), AdjustReserves (rebalance), and others
  that manage the bank's overall position.

Each decision is informed by over **140 context fields** — the complete state
of the world as the agent sees it. Current balance, queue depth, queue value, time of day,
payments pending, incoming payment history, liquidity ratio, cost accumulation rates,
deadline proximity for each queued payment, counterparty reliability scores, and dozens more.
This isn't a toy state space — it mirrors the information a real cash manager has on their
screens.

Strategies are expressed as **decision trees**: nested if-then-else structures
that examine context fields and select actions. A tree might say: "If the queue value
exceeds 50% of available balance AND the highest-priority payment's deadline is within 2
ticks, then Release. Otherwise, if incoming payment velocity is above average, Delay.
Otherwise, Queue." These trees can be shallow (3-4 decisions) or deep (dozens of branches),
creating an enormous space of possible strategies.

## When Does Sophistication Pay Off?

This is the question that surprised us most. You'd expect more complex policies to always
outperform simpler ones — more information, more conditions, better decisions. But that's
not what happens.

In our experiments, the relationship between policy complexity and performance follows a
curve. Very simple policies (FIFO, or a tree with 2-3 nodes) leave significant value on
the table. They can't respond to the state of the system at all. But very complex policies
(deep trees with 20+ branches) often *overfit* to specific payment patterns. They
perform brilliantly on the scenarios they were designed for and terribly on everything else.

The sweet spot turns out to be **moderate complexity**: trees with 5-10
decision nodes that focus on the most informative context fields. Queue depth, liquidity
ratio, time-of-day, and deadline proximity carry most of the signal. Adding branches for
obscure context fields (third-derivative of incoming payment velocity, say) adds noise
faster than it adds value.

This mirrors a well-known result in machine learning — the bias-variance tradeoff — but
seeing it play out in a financial simulation is striking. The best payment strategies
aren't the cleverest. They're the ones that focus on the right signals and ignore the rest.

## The Policy Library

SimCash ships with a curated library of pre-built strategies spanning the full spectrum
from conservative to aggressive:

- **FIFO Baseline:** Pure queue-order processing. The control group.
- **Cautious:** Holds extra liquidity reserves, delays non-urgent payments,
  prioritizes avoiding deadline failures above all else. Low variance, moderate cost.
- **Balanced:** Adapts liquidity commitment based on queue pressure. Releases
  payments when funded, delays when tight. The "sensible middle ground."
- **Aggressive:** Commits minimal liquidity upfront, relies heavily on
  incoming payments for funding. High reward when it works, high penalty when it doesn't.
- **Deadline-Driven:** Ignores queue order entirely, processes payments
  by deadline proximity. Minimizes failure costs at the expense of potentially higher delays.
- **Adaptive:** Changes behavior based on the current phase of the day —
  conservative early (when incoming flows are uncertain), aggressive late (when remaining
  obligations are known).

Each policy in the library has been tested across hundreds of random seeds and multiple
scenarios. The documentation includes expected cost ranges, failure rates, and performance
profiles so you know what you're getting before you deploy one in an experiment.

## Building Custom Policies

The policy editor lets you construct decision trees visually. You start with a root node,
add conditions (pick a context field, choose a comparator, set a threshold), and assign
actions to the leaves. The editor validates your tree in real-time — it'll warn you about
unreachable branches, missing edge cases, or conditions that are always true.

You can also start from a library policy and modify it. Take the Balanced strategy, add a
crisis-response branch ("if liquidity ratio drops below 20%, switch to aggressive release"),
and you've got a custom policy that handles normal operations sensibly and responds to
shocks without freezing up. Save it, name it, run it against the originals.

For power users, policies can also be written directly in JSON — the same format the LLM
agents produce. This means any strategy an AI discovers can be extracted, inspected, edited,
and redeployed as a static policy. The boundary between human-designed and AI-discovered
strategies is deliberately blurry.

## How AI Discovers Better Strategies

When an LLM agent optimizes a policy, it doesn't search the tree space randomly. It starts
with a simple policy (often FIFO or a basic tree), runs simulations, reads the performance
reports, and makes targeted modifications. The reasoning looks remarkably like what a human
expert would do:

*"Delay costs are 3x liquidity costs. I'm over-committing liquidity. Let me reduce
initial_liquidity_fraction from 0.65 to 0.50 and add a condition: if queue depth exceeds 5,
release the highest-value payment regardless of order."*

Each proposed change is validated by bootstrap paired comparison — the new policy must
outperform the old one across 50 resampled scenarios with 95% confidence. This prevents
the agent from chasing noise. Over 15-20 rounds, the policy evolves from simple to
moderately complex, accumulating the decision branches that actually improve performance
and discarding the ones that don't survive statistical validation.

The result is a policy that no human designed but that any human can read. Decision trees
are inherently interpretable — you can trace every branch, understand every condition, and
debate whether the logic makes sense. This is a crucial advantage over black-box approaches.

## The Nash Equilibrium Question

The deepest question in multi-agent payment strategy isn't "what's the best policy?" —
it's "what happens when everyone optimizes simultaneously?"

In game theory, a **Nash equilibrium** is a set of strategies where no player
can improve their outcome by changing their own strategy alone. In SimCash, this means a
configuration where every bank's policy is the best response to every other bank's policy.
Nobody wants to deviate.

Our multi-agent experiments show that LLM agents do converge — but not always to the same
equilibrium. In symmetric games (identical banks, identical payment flows), the agents
typically find an equilibrium within 10-15 rounds. But the equilibrium they find depends
on the path they take to get there. Early aggressive moves by one agent can push the system
toward an asymmetric equilibrium where one bank free-rides on the other's liquidity
provision.

This is the Prisoner's Dilemma playing out in real-time payment systems. The cooperative
outcome (both banks commit moderate liquidity, both benefit from smooth settlement) is
Pareto-optimal but unstable. The Nash equilibrium (one bank commits high liquidity, the
other free-rides) is stable but inefficient. Both agents know this. Neither can fix it
unilaterally.

Understanding when agents converge, what they converge to, and whether the equilibrium is
socially efficient — these are the questions that connect SimCash to decades of game theory
research. And now, instead of solving them on a whiteboard, you can watch them unfold in a
simulated payment system with realistic costs, realistic constraints, and agents that reason
about their decisions in plain English.

The journey from FIFO to Nash isn't just about better payment processing. It's about
understanding the fundamental tension in any shared financial infrastructure: individual
optimization vs. collective welfare. SimCash makes that tension visible, measurable, and
explorable.
