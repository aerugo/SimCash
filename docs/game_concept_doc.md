# Payment System Simulation: Concept Document

## Purpose

This document describes the conceptual foundation of the payment simulator—a tool for studying strategic behavior in interbank payment systems. It connects the simulation to real-world payment infrastructure and serves as a reference for validating that new features and implementations accurately reflect the dynamics they're intended to model.

**Primary Use Cases:**
- Understand how banks coordinate (or fail to coordinate) intraday payment flows
- Study the effectiveness of liquidity-saving mechanisms under various conditions
- Train AI agents to make cash management decisions
- Explore policy questions around payment system design

---

## Real-World Context

### What We're Modeling

Modern economies rely on **Real-Time Gross Settlement (RTGS)** systems for high-value interbank payments. In these systems, banks hold accounts at the central bank, and payments settle immediately and individually when sufficient funds are available.

**Key real-world systems this simulation draws from:**
- **TARGET2 (T2)**: The Eurosystem's RTGS, processing over €1.7 trillion daily
- **Fedwire**: The US Federal Reserve's RTGS system
- **RIX-RTGS**: Sweden's Riksbank system (planning integration with T2)

### The Fundamental Tension

Banks face a core tradeoff every business day:

**Liquidity costs money.** Holding large reserves at the central bank ties up capital that could earn returns elsewhere. Borrowing intraday credit (whether collateralized or priced) has explicit costs.

**Delay costs money.** Client service agreements, regulatory deadlines, and reputational concerns create pressure to settle payments promptly.

This creates a **coordination problem**: if Bank A waits for incoming payments before sending outgoing ones, and Bank B does the same, both suffer delays even though cooperation (sending simultaneously) would benefit everyone. This is the "game" in our game design.

---

## Core Concepts

### Time Structure

The simulation divides each business day into discrete **ticks** (e.g., 60-100 per day). Each tick represents a decision point where banks can act and settlements can occur.

**Why discrete time?** Real payment systems process continuously, but decision-making happens at discrete intervals (treasury reviews, batch releases, scheduled settlements). Discrete ticks also enable deterministic simulation for research reproducibility.

### The Two-Queue Architecture

Payments flow through two conceptually distinct queues:

**Queue 1: Internal Bank Queue**
- Where a bank's outgoing payments wait before submission to the central system
- The "cash manager's desk"—decisions about *when* and *how* to release payments happen here
- Delay costs accrue here (representing client SLA pressure)

**Queue 2: Central RTGS Queue**
- The central bank's queue for payments awaiting sufficient liquidity
- No delay costs here—waiting for liquidity is expected system behavior
- Liquidity-Saving Mechanisms operate on this queue

**Why two queues?** This separation reflects reality: banks choose when to submit payments (strategic decision), but once submitted, payments either settle immediately or wait for liquidity (mechanical process). The distinction is crucial for understanding where AI agents can meaningfully intervene.

### Agents (Banks)

Each bank maintains:

**Settlement Account Balance**: Reserves held at the central bank. This is the actual money used for settlements.

**Credit Headroom**: Intraday credit available from the central bank, either:
- *Collateralized*: Requires posting securities as collateral (opportunity cost)
- *Priced*: Pays interest on overdraft usage (explicit cost)

**Payment Obligations**: Outgoing payments owed to other banks, each with an amount, deadline, and priority level.

### Transactions

Each payment has:

**Amount**: The value to transfer (always in integer cents—no floating point)

**Deadline**: Latest acceptable settlement time. Missing deadlines incurs penalties.

**Priority**: Urgency level (0-10). Higher priority payments may be processed first in certain queue configurations.

**Counterparties**: Sending and receiving banks.

---

## Settlement Mechanics

### Immediate Settlement (RTGS)

When a bank submits a payment:
1. System checks if sender's balance + credit headroom covers the amount
2. If yes: immediately debit sender, credit receiver—**final settlement**
3. If no: payment enters Queue 2, awaiting liquidity

**Finality** is the key property: once settled, a payment cannot be reversed by the system. This mirrors real RTGS behavior.

### Liquidity-Saving Mechanisms (LSM)

When payments sit in Queue 2, the system actively looks for opportunities to settle multiple payments together with less total liquidity:

**Bilateral Offset**
If Bank A owes Bank B $500k and Bank B owes Bank A $300k, both payments can settle simultaneously if Bank A can cover only the net $200k difference. Both payments settle at their full original amounts—only the liquidity requirement is reduced.

**Multilateral Cycles**
Three or more banks may form a cycle: A→B, B→C, C→A. If each bank's net position (inflows minus outflows) is fundable, all payments in the cycle settle simultaneously at full value.

**Why LSM matters:** In liquidity-constrained conditions, LSM dramatically reduces the reserves needed to achieve the same settlement throughput. Studies show LSM can reduce liquidity needs by 30-50% while decreasing delays.

### Important LSM Principles

1. **Full-value settlement**: Individual payments always settle at their original amount. LSM reduces liquidity requirements by smart *grouping*, not by *splitting* payments.

2. **Atomic execution**: Cycles settle all-or-nothing. If any participant lacks liquidity for their net position, the entire cycle fails and all payments remain queued.

3. **Conservation**: In any settled cycle, the sum of net positions equals zero (money in = money out).

---

## The Cash Manager's Decisions

The simulation models the decisions a bank's treasury/cash management function makes throughout the day:

### When to Release Payments

**Trade-off**: Release early to avoid delay costs and contribute to system liquidity, but risk running short of funds. Hold back to wait for incoming liquidity, but accumulate delay costs and contribute to gridlock.

**Real-world factors**: Client deadlines, expected incoming flows, current Queue 2 congestion, time until market close.

### How Much Liquidity to Access

**Trade-off**: Draw intraday credit to settle payments immediately, but pay liquidity costs. Or wait for incoming payments, saving liquidity costs but risking delays.

**Options**: Post collateral, draw overdraft, borrow in money markets.

### Whether to Split Large Payments

**Trade-off**: Splitting a $1B payment into four $250M payments may allow partial settlement when full liquidity isn't available. But splitting incurs operational costs and complexity.

**Real-world note**: T2 and most RTGS systems do not automatically split payments. Banks may choose to submit multiple smaller instructions as a strategic decision.

### Priority and Timing Flags

When supported by the settlement system, banks can mark payments as:
- **Urgent**: Processed before normal payments
- **Timed**: Scheduled for specific settlement windows

---

## Cost Structure

Costs in the simulation represent real economic pressures:

### Liquidity Costs

**What it represents**: The opportunity cost of capital, explicit interest on overdrafts, or collateral posting costs.

**Real-world parallel**: Banks optimize intraday liquidity usage because reserves earn less than alternative investments, and collateral/credit lines have real costs.

### Delay Costs (Queue 1 Only)

**What it represents**: Client dissatisfaction, SLA penalties, reputational damage from slow payment execution.

**Why only Queue 1**: Payments held *by the bank* create client-facing delays. Payments queued *at the central bank* are waiting for system-level liquidity—a different dynamic.

### Deadline Penalties

**What it represents**: Regulatory fines, failed settlement penalties, or severe client impact for missed critical payments.

**Real-world parallel**: Certain payments (securities settlement, margin calls, regulatory deadlines) have hard deadlines with severe consequences.

### End-of-Day Penalties

**What it represents**: The extreme undesirability of failing to settle obligations by market close.

**Real-world parallel**: Unsettled payments at day-end create credit risk, regulatory issues, and operational chaos.

---

## Emergent Phenomena

The simulation is designed to exhibit behaviors observed in real payment systems:

### Gridlock

When liquidity is scarce and banks all wait for incoming payments, a circular dependency can form where no one moves first. This "gridlock" wastes time even though cooperation would benefit everyone.

**LSM response**: Cycle detection breaks gridlock by finding groups of payments that can settle together.

### Morning Slowness / Afternoon Rush

Banks often delay payments in the morning (hoping for incoming liquidity) and rush to settle before cutoff. This creates predictable intraday patterns.

**Policy levers**: Throughput guidelines (e.g., "50% settled by noon") attempt to smooth this pattern.

### Free-Riding

A bank that delays while others pay promptly benefits from incoming liquidity without contributing. If everyone free-rides, gridlock occurs.

**Game theory**: This resembles a Prisoner's Dilemma or Stag Hunt, depending on parameters.

---

## Validation: Sanity-Checking New Features

When implementing new features, validate against these real-world expectations:

### Settlement Behavior

- [ ] RTGS settles immediately when liquidity is available
- [ ] Insufficient liquidity queues payments, doesn't reject them
- [ ] LSM bilateral offsets reduce liquidity usage, not payment values
- [ ] LSM cycles are atomic (all-or-nothing)
- [ ] Settlement is final and irreversible

### Queue Behavior

- [ ] Queue 1 represents bank-controlled delay (strategic)
- [ ] Queue 2 represents system-controlled waiting (mechanical)
- [ ] Delay costs only accrue in Queue 1
- [ ] LSM only operates on Queue 2

### Cost Behavior

- [ ] Liquidity costs scale with usage duration and amount
- [ ] Delay costs scale with waiting time in Queue 1
- [ ] End-of-day creates strong settlement pressure
- [ ] Higher priority payments receive preferential treatment when enabled

### Coordination Dynamics

- [ ] Low liquidity should increase gridlock risk
- [ ] LSM should reduce delays and liquidity usage vs. pure RTGS
- [ ] Strategic waiting should emerge when delay costs are low relative to liquidity costs
- [ ] Throughput guidelines should shift settlement timing patterns

### Determinism

- [ ] Same seed + same configuration = identical results
- [ ] All randomness comes from the seeded RNG
- [ ] No system time, network calls, or non-deterministic operations

---

## Research Questions

The simulation is designed to explore questions like:

**Liquidity Management**
- How much liquidity do banks need to achieve target settlement rates?
- How do collateralized vs. priced credit regimes affect behavior?
- What's the value of LSM under different liquidity conditions?

**Coordination**
- What policies encourage early payment release?
- How do throughput guidelines affect coordination?
- Can AI agents learn to coordinate better than rule-based strategies?

**System Design**
- How do priority features affect overall settlement efficiency?
- What's the optimal LSM algorithm design?
- How should regulators set intraday credit pricing?

**Stress Testing**
- How do systems behave during liquidity squeezes?
- What happens when a major participant has operational issues?
- How resilient is settlement to correlated shocks?

---

## Glossary

| Term | Definition |
|------|------------|
| **RTGS** | Real-Time Gross Settlement—payments settle individually and immediately |
| **LSM** | Liquidity-Saving Mechanism—algorithms that reduce liquidity needs through smart grouping |
| **Finality** | Irreversibility of settled payments |
| **Gridlock** | Circular dependency where all parties wait for each other |
| **Queue 1** | Bank's internal queue (strategic holding) |
| **Queue 2** | Central system queue (awaiting liquidity) |
| **Bilateral Offset** | Settling two opposing payments at net liquidity cost |
| **Multilateral Cycle** | Settling a ring of payments simultaneously |
| **Tick** | Discrete time unit in the simulation |
| **Credit Headroom** | Available intraday credit from central bank |

---

## References

The simulation draws on concepts from:

1. **European Central Bank** - TARGET2 documentation and business descriptions
2. **Nationalbanken** - "Gridlock Resolution in Payment Systems" research
3. **Riksbank** - RIX-RTGS documentation and T2 integration plans
4. **Bank for International Settlements** - CPMI reports on payment system design

For implementation details, see the technical documentation in `CLAUDE.md` and the architecture guide in `docs/architecture.md`.

---

*This document describes concepts and design intent. For configuration options and implementation specifics, see the CLAUDE.md files and API documentation.*
