# Overview

*What is SimCash and why does it exist?*

SimCash is an interactive research sandbox for exploring how AI agents learn to manage
liquidity in payment systems. It models the fundamental coordination problem that banks
face every day: **how much cash should you keep ready?**

## The Problem

In a Real-Time Gross Settlement (RTGS) system, banks settle payments individually in real
time. Each bank must decide how much liquidity to commit at the start of each day. This
creates a strategic tradeoff:

- **Too much liquidity** → expensive (opportunity cost of idle capital)
- **Too little liquidity** → payments queue up, delays accumulate, deadlines are missed

What makes this interesting is that each bank's optimal strategy depends on what other
banks do. If your counterparty commits lots of liquidity, their payments to you settle
quickly, giving you incoming cash to fund your own outgoing payments. This is a
*coordination game*.

## The Experiment

We let AI agents (powered by an LLM) play this game repeatedly. Each day, the Rust
simulation engine runs the payment system with the agents' current policies. At the end
of each day, each agent independently analyzes its own results — costs incurred, payments
settled, delays suffered — and proposes an improved policy for the next day.

Over many days, we watch whether these independently-optimizing agents converge to stable
strategies, and whether those strategies resemble the game-theoretic equilibria predicted
by economic theory.

## Key Insight

> 💡 **Stability does not imply optimality.** In our experiments, LLM agents
> reliably converge to *stable* policy profiles, but these aren't always
> Pareto-efficient. In deterministic scenarios, we observe *coordination failures*
> where one agent free-rides on the other's liquidity — the free-rider benefits while
> the exploited bank is worse off, and the system as a whole is less efficient than it
> could be. Stochastic environments with statistical evaluation produce more symmetric,
> near-optimal outcomes.

## Context

SimCash was created by Hugi Aegisberg as a research tool for studying multi-agent
coordination in payment systems. It implements and extends the experimental scenarios
from the BIS Working Paper No. 1310, *"AI agents for cash management in payment
systems"* (2025), which demonstrated that general-purpose LLMs can replicate key
cash management practices even without domain-specific training.

Where the BIS paper tested a single LLM agent's ability to make prudent liquidity
decisions, SimCash asks the next question: what happens when *multiple* AI agents
interact strategically? The answer involves coordination games, free-riding, and the
surprising role of statistical evaluation in promoting cooperation.

The simulation engine is built in Rust for speed and determinism, with a Python
orchestration layer using PyO3 FFI. This work sits at the intersection of AI agents
for economic research (Korinek, 2025) and computational game theory.
