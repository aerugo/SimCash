# Game Theory Primer

*Nash equilibria, coordination, and free-riding*

## The Coordination Game

RTGS liquidity management is a **coordination game**. Each bank's optimal
strategy depends on what other banks do. Unlike zero-sum games, there are mutual gains
from coordination — if all banks commit appropriate liquidity, everyone benefits from
faster settlement and lower delay costs.

## Nash Equilibrium

A Nash equilibrium is a strategy profile where no player can improve their outcome by
unilaterally changing their strategy. In payment systems, this means: given what every
other bank is doing, each bank's liquidity allocation is already optimal for them.

Castro et al. (2025) characterize the equilibria for several stylized scenarios. Our
experiments test whether LLM agents can *discover* these equilibria through
independent optimization without any explicit game-theoretic reasoning.

## Free-Riding

A persistent phenomenon in our experiments: when one bank commits lots of liquidity, its
payments to counterparties settle quickly, giving those counterparties incoming cash. The
counterparties can then get away with committing less of their own liquidity — they're
"free-riding" on the generous bank's reserves.

## Pareto Efficiency

A stable outcome isn't necessarily a *good* outcome. A Pareto-efficient allocation
means no one can be made better off without making someone worse off. Our coordination
failures in Experiment 3 show agents converging to Pareto-*dominated* outcomes —
both agents could be better off, but neither has an individual incentive to change.

## Stochastic Environments Help

> 💡 Stochastic payment arrivals + bootstrap evaluation seem to discourage free-riding.
> The statistical evaluation introduces a form of "noise" that makes greedy exploitation
> harder to sustain, pushing agents toward more symmetric, cooperative allocations.

## AI Agents as Game Players

SimCash's agents follow what Korinek (2025) describes as the core agent loop:
**Think → Act → Observe → Respond**. Each iteration, the LLM reasons
about its cost history (Think), proposes a new policy (Act), the simulation runs (Observe),
and results feed back into the next iteration (Respond). Unlike traditional game-theoretic
agents with explicit utility maximization, these agents reason in natural language —
making them both more flexible and more prone to the kinds of bounded rationality
that produce coordination failures.
