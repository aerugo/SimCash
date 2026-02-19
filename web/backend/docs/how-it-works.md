# How the Simulator Works

*Ticks, queues, settlement engines, and the cost of waiting*

## Overview

SimCash is a discrete-time simulator for interbank payment systems. It models banks (called **agents**) settling payments through a central bank, using Real-Time Gross Settlement (RTGS) with optional Liquidity-Saving Mechanisms (LSM). The simulator is built as a high-performance Rust engine, invoked from Python via FFI.

The core question it explores: *how should a bank decide when to release payments, given that liquidity is expensive but delay is costly?*

---

## Time Structure: Days and Ticks

Time is divided into **business days**, each subdivided into a configurable number of **ticks** (typically 12–100 per day). A tick is the smallest discrete time unit — one cycle of the simulation loop where arrivals happen, policies execute, settlements attempt, and costs accrue.

| Concept | Meaning |
|---------|---------|
| **Tick** | One simulation step (~minutes of real time) |
| **Day** | One business day, consisting of N ticks |
| **tick_within_day** | Position within the current day (0-indexed) |
| **End of Day** | Final tick triggers forced settlement attempts and penalties |

The `TimeManager` tracks the global tick counter and derives the current day, intra-day position, and ticks remaining until close.

---

## The Tick Loop

Every call to `tick()` on the orchestrator executes a **10-step pipeline**. This is the heartbeat of the simulation:

### Step 1 — Advance Time
Increment the global tick counter.

### Step 2 — End-of-Day Check
If this is the last tick of a day: force-settle remaining Queue 2 transactions, apply end-of-day penalties to anything still unsettled, reset daily budgets and counters, and emit an `EndOfDay` event.

### Step 3 — Generate Arrivals
For each agent, sample from a Poisson distribution to determine how many new payments arrive this tick. Each arrival gets a random amount (from a configurable distribution: normal, log-normal, uniform, or exponential), a random counterparty (weighted), a deadline, and a priority. New transactions enter the agent's **Queue 1** (internal queue).

### Step 4 — Entry Disposition Offsetting
Before payments enter the central queue, the engine checks: does the counterparty already have an opposing payment queued? If so, both can settle immediately via bilateral offset at entry time, bypassing the queue entirely. This is an optional feature modeled after TARGET2's entry disposition mechanism.

### Step 5 — Policy Evaluation
For each agent, the engine evaluates the agent's **policy trees** against the current state. Policies are JSON-defined decision trees that inspect balance, queue depth, deadlines, time-of-day, and 140+ other context fields to decide what to do with each queued payment:

- **bank_tree** — Evaluated once per tick. Sets bank-wide parameters like release budgets and state registers.
- **strategic_collateral_tree** — Decides whether to post or withdraw collateral before settlement attempts.
- **payment_tree** — Evaluated for each transaction in Queue 1. Produces a decision: **Submit** (release to RTGS), **Hold** (keep waiting), **Split** (divide into smaller payments), or **Drop**.

Queue 1 can be processed in FIFO order or sorted by priority-then-deadline, depending on configuration.

### Step 6 — RTGS Processing
Payments submitted by policies enter the RTGS engine. For each payment:

1. Check if the sender's **available liquidity** (balance + unsecured credit cap + collateral-backed credit) covers the amount.
2. If yes: **atomically** debit the sender, credit the receiver, mark the transaction as settled. This is immediate, final settlement.
3. If no: the payment enters **Queue 2** (the central RTGS queue), waiting for liquidity.

The engine also retries previously queued payments in FIFO order, settling any that now have sufficient liquidity.

### Step 7 — LSM Optimization
If LSM is enabled, the engine runs up to three algorithms on Queue 2, in sequence:

- **Algorithm 1 (FIFO retry)** — Process the queue in order, settling anything with sufficient liquidity.
- **Algorithm 2 (Bilateral offsetting)** — Find pairs of banks with opposing payments (A owes B, B owes A). If the net payer can cover just the net difference, all payments in the pair settle simultaneously. Example: A→B $100k and B→A $80k both settle if A can pay the $20k net.
- **Algorithm 3 (Multilateral cycle detection)** — Find circular chains (A→B→C→A) using DFS on an aggregated payment graph. If every participant can fund their net position, the entire cycle settles atomically. A $300k gross cycle might require only $20k of actual liquidity movement.

The algorithms run in sequence: if Algorithm 1 makes progress, restart from Algorithm 1. If Algorithm 2 succeeds, restart from 1. Continue until no further progress.

Bilateral and multilateral limits (per-counterparty and total outflow caps) are enforced — offsets and cycles that would exceed limits are skipped.

### Step 7b — Apply Deferred Credits (optional)
When `deferred_crediting` mode is enabled, credits from settlements accumulate during the tick but only apply to balances here. This prevents "within-tick recycling" of liquidity and matches academic models where incoming funds aren't available until the next period.

### Step 8 — Cost Accrual
The engine calculates and records costs for each agent:

| Cost Type | What It Represents | When It Accrues |
|-----------|-------------------|-----------------|
| **Overdraft (liquidity)** | Interest on negative balance | Per tick, proportional to overdraft amount |
| **Collateral** | Opportunity cost of posted securities | Per tick, proportional to posted collateral |
| **Delay** | Client dissatisfaction from holding payments | Per tick per transaction in Queue 1 |
| **Deadline penalty** | Hard penalty for missing a deadline | One-time, when deadline tick passes |
| **Overdue delay** | Accelerated delay cost (default 5×) | Per tick for overdue transactions |

An optional **end_of_tick_collateral_tree** is also evaluated here for reactive collateral adjustments.

### Step 9 — Event Logging and Return
All events generated during the tick are collected. The engine returns a `TickResult` containing the tick number, day, arrival count, settlement count, Queue 2 size, total costs, and the full event list.

---

## The Two-Queue Architecture

This design separates **strategic** from **mechanical** waiting:

**Queue 1 (Internal Bank Queue)** — The cash manager's desk. Payments sit here while the bank decides when to release them. Delay costs accrue here because the bank is choosing to wait. Policy trees operate on this queue.

**Queue 2 (Central RTGS Queue)** — The central bank's settlement queue. Payments are here because they've been submitted but lack liquidity to settle. No delay costs accrue — the bank has already acted. LSM algorithms operate on this queue.

This separation is critical: it cleanly distinguishes the decisions an agent controls (when to submit) from the mechanics it doesn't (when liquidity becomes available).

---

## Settlement Engines

### RTGS (Real-Time Gross Settlement)
Each payment settles individually and immediately when funds are available. Settlement is **atomic** (debit and credit happen together) and **final** (irreversible). If the sender can't pay, the payment queues rather than failing.

Available liquidity = balance + unsecured credit cap + (posted collateral × (1 − haircut)).

### LSM (Liquidity-Saving Mechanisms)
LSM reduces the liquidity needed to achieve the same settlement volume by finding smart groupings:

**Bilateral offsetting** identifies pairs of banks with mutual obligations. Instead of each paying gross, only the net difference moves. If Bank A owes Bank B $100k and Bank B owes Bank A $80k, both payments settle with only $20k of actual liquidity flow — an 89% reduction.

**Multilateral cycle detection** extends this to rings of three or more banks. The engine builds a directed graph from Queue 2 transactions, runs DFS to find cycles up to a configurable maximum length, and settles them atomically. Each participant only needs to fund their net position. A three-bank cycle with $300k gross value might settle with just $20k of net flow.

Both mechanisms settle payments at their **full original amounts** — LSM reduces liquidity requirements through netting, not by reducing payment values. All cycle settlements are atomic: if any participant can't fund their net position, the entire cycle is skipped.

---

## The Event System

SimCash uses an **event-sourced architecture**. Every meaningful action — arrivals, policy decisions, settlements, cost charges, LSM offsets — emits an immutable event. The system generates 50+ event types providing a complete audit trail.

Events are:
- **Self-contained** — each event includes all data needed to understand it, no external lookups required
- **Immutable** — append-only, never modified after creation
- **Deterministic** — same simulation produces identical event streams

Key event categories:

| Category | Examples |
|----------|---------|
| Arrivals | `Arrival` |
| Policy | `PolicySubmit`, `PolicyHold`, `PolicySplit`, `BankBudgetSet` |
| Settlement | `RtgsImmediateSettlement`, `QueuedRtgs`, `Queue2LiquidityRelease` |
| LSM | `LsmBilateralOffset`, `LsmCycleSettlement`, `AlgorithmExecution` |
| Costs | `CostAccrual`, `TransactionWentOverdue` |
| Collateral | `CollateralPost`, `CollateralWithdraw` |
| System | `EndOfDay`, `ScenarioEventExecuted` |

Events flow from the Rust engine through FFI to Python, where they can be displayed in real-time, persisted to DuckDB, or analyzed after the run.

---

## Determinism

SimCash is **fully deterministic**. Given the same seed and configuration, it produces byte-identical output across runs. This is achieved through:

- **Seeded RNG** — All randomness flows through a single xorshift64* generator
- **Integer arithmetic** — All money is represented as `i64` cents, never floating point
- **Ordered data structures** — `BTreeMap` (not `HashMap`) ensures iteration order is deterministic
- **No external state** — No system time, no network calls, no OS-dependent behavior

This property is essential for reproducible research, replay systems, and policy comparison.

---

## Balance Conservation

The system enforces a strict invariant: the **total balance across all agents is conserved** by settlement operations. Every debit has an equal credit. LSM cycles are net-zero by construction. This mirrors the closed-system property of real central bank settlement: money moves between accounts but is never created or destroyed by the settlement process.
