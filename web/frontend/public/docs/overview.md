# Overview

*Can AI agents learn to coordinate in payment systems?*

SimCash is a research platform for simulating strategic behavior in interbank payment systems. It models the real-world coordination problem at the heart of every Real-Time Gross Settlement (RTGS) system: banks must balance the cost of holding liquidity against the cost of delaying payments — and every bank's optimal strategy depends on what the others do.

## The Coordination Problem

In systems like TARGET2, Fedwire, and RIX-RTGS, banks hold accounts at the central bank and settle high-value payments individually in real time. Every business day, each bank's cash management function faces a fundamental tension:

- **Holding liquidity is expensive** — capital sitting in reserve accounts has opportunity cost
- **Delaying payments is expensive** — client SLAs, regulatory deadlines, and reputational pressure demand timely settlement
- **If everyone waits for incoming funds before releasing outgoing ones, the system gridlocks**

This creates a multi-player coordination game. Cooperation (paying early) benefits the system, but each individual bank has an incentive to wait and free-ride on others' liquidity.

## What SimCash Simulates

The simulation engine models a complete RTGS business day at tick-level granularity:

### Two-Queue Architecture

Payments flow through two distinct queues that mirror real RTGS design:

- **Queue 1 (Internal)** — the bank's own holding queue, where strategic timing decisions happen. Delay costs accrue here.
- **Queue 2 (Central RTGS)** — the central bank's settlement queue, where payments wait for sufficient liquidity. LSM algorithms operate here.

This separation captures the key distinction: banks *choose* when to submit (strategic), but once submitted, settlement depends on available liquidity (mechanical).

### Liquidity-Saving Mechanisms

When payments sit in Queue 2, the engine can optionally run LSM algorithms in sequence:

1. **FIFO Settlement** — process queued payments in submission order
2. **Bilateral Offsetting** — if Bank A owes Bank B and vice versa, settle both at the net liquidity cost
3. **Multilateral Cycle Detection** — find rings of three or more banks where all payments can settle simultaneously

An **entry disposition** check also runs at payment submission: if an immediate bilateral offset exists, both payments settle on the spot. These mechanisms can reduce liquidity needs by 30–50% while decreasing delays.

### Rich Cost Model

The simulation tracks six categories of cost — overdraft interest, collateral opportunity cost, delay penalties, deadline penalties, split friction, and end-of-day unsettled penalties — each with explicit formulas that create quantifiable tradeoffs for policy optimization.

## Policy Decision Trees

Banks make decisions through a **JSON-based decision tree DSL** — a structured policy language that is both human-readable and LLM-editable. Each agent's policy consists of up to four trees:

| Tree | Controls |
|------|----------|
| **payment_tree** | Per-payment decisions: release, hold, delay, split, change priority |
| **bank_tree** | Bank-wide decisions each tick: set budgets, allocate liquidity |
| **strategic_collateral_tree** | Pre-settlement: post or withdraw collateral |
| **end_of_tick_collateral_tree** | Post-settlement: adjust collateral positions |

### 8 Available Actions

Agents can choose from eight distinct actions, each with configurable parameters:

- **Release** / **Hold** / **Delay** — timing control for outgoing payments
- **Split** — divide large payments into smaller parts for partial settlement
- **PostCollateral** / **WithdrawCollateral** — manage credit headroom
- **SetBudget** — allocate a liquidity budget for the tick
- **NoAction** — explicitly do nothing

### 140+ Context Fields

Policy conditions evaluate against a rich information set including balance state, queue depths, transaction details, time pressure, cost accumulation, counterparty exposure, and 10 persistent state registers that let policies maintain memory across ticks. This gives AI agents a detailed view of the system state at every decision point.

## The AI Optimization Loop

SimCash connects the simulation engine to an LLM-powered optimization cycle:

1. **Simulate** — run a complete business day (all ticks) with each agent's current policy trees
2. **Evaluate** — each agent independently analyzes its costs, settlement rates, delays, and liquidity usage
3. **Optimize** — an LLM proposes an improved decision tree based on the agent's results and the full context field vocabulary
4. **Repeat** — run the next day with updated policies

All optimization happens *between* simulated business days — never during a day. Within a day, the policy tree executes deterministically tick by tick with no AI involvement. This separation is by design: the engine guarantees reproducible, auditable execution within each day, while the AI operates only at day boundaries where results can be fully evaluated.

Over multiple rounds, independently-optimizing agents explore the strategy space. The central question: **do they converge to stable strategies, and are those strategies efficient?**

### Multi-Agent Game Theory

When multiple agents optimize simultaneously, the system exhibits classic game-theoretic dynamics:

- **Delayed best-response** — each agent optimizes against yesterday's observed counterparty behavior
- **Convergence patterns** — agents typically find stable policy profiles, but stability doesn't guarantee optimality
- **Coordination failures** — free-riding emerges when one agent exploits another's liquidity commitment
- **LSM as mechanism design** — liquidity-saving mechanisms reshape incentives

## What You Can Explore

- **Liquidity management** — how much reserve do banks need under different conditions?
- **Mechanism design** — how do LSM algorithms, priority rules, and credit pricing affect outcomes?
- **AI coordination** — can LLM agents learn to cooperate, or do they settle into inefficient equilibria?
- **Stress testing** — what happens during liquidity squeezes or operational disruptions?
- **Policy engineering** — which decision tree structures produce robust strategies across scenarios?
