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

When payments sit in Queue 2, the system actively looks for opportunities to settle multiple payments together with less total liquidity. The simulation implements TARGET2's formal algorithm sequence:

#### Algorithm Sequence

The LSM runs three algorithms in a defined order:

**Algorithm 1: FIFO Queue Processing**
Attempts to settle queued payments in submission order (respecting RTGS priority levels). Payments settle individually if sufficient liquidity exists.

**Algorithm 2: Bilateral Offsetting**
If Bank A owes Bank B $500k and Bank B owes Bank A $300k, both payments can settle simultaneously if Bank A can cover only the net $200k difference. Both payments settle at their full original amounts—only the liquidity requirement is reduced.

**Algorithm 3: Multilateral Cycle Detection**
Three or more banks may form a cycle: A→B, B→C, C→A. If each bank's net position (inflows minus outflows) is fundable, all payments in the cycle settle simultaneously at full value.

**Sequencing Behavior:**
- Algorithms cannot run simultaneously
- If Algorithm 1 settles payments, repeat from Algorithm 1
- If Algorithm 2 succeeds, return to Algorithm 1
- If Algorithm 2 fails, try Algorithm 3
- If Algorithm 3 succeeds, return to Algorithm 1
- Process continues until no progress is made

#### Entry Disposition Offsetting

Before a payment enters Queue 2, the system performs an **offsetting check**: does the receiving bank have a queued payment back to the sender that could form an immediate bilateral offset?

If yes, both payments settle immediately at entry time, bypassing the normal queue. This "entry disposition" mechanism prevents queue buildup when offsetting opportunities exist.

**Why this matters:** In TARGET2, this check happens at payment entry, not just during periodic LSM runs. This reduces queue depth and accelerates settlement for naturally offsetting flows.

#### Why LSM Matters

In liquidity-constrained conditions, LSM dramatically reduces the reserves needed to achieve the same settlement throughput. Studies show LSM can reduce liquidity needs by 30-50% while decreasing delays.

### Important LSM Principles

1. **Full-value settlement**: Individual payments always settle at their original amount. LSM reduces liquidity requirements by smart *grouping*, not by *splitting* payments.

2. **Atomic execution**: Cycles settle all-or-nothing. If any participant lacks liquidity for their net position, the entire cycle fails and all payments remain queued.

3. **Conservation**: In any settled cycle, the sum of net positions equals zero (money in = money out).

4. **Limit Awareness**: LSM algorithms respect bilateral and multilateral limits. A potential offset or cycle that would exceed a participant's limits is not executed.

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

The simulation implements TARGET2's **dual priority system**, separating internal bank priorities from RTGS queue priorities:

**Internal Priority (0-10)**
- The bank's own assessment of payment urgency
- Used for internal queue ordering in Queue 1
- Higher values mean more urgent to the sending bank
- Does not affect RTGS processing order

**RTGS Declared Priority**
When submitting to the central RTGS system (Queue 2), banks declare one of three priority levels:

- **Highly Urgent**: Processed before all other payments. Used for critical settlements (e.g., ancillary system settlements, time-critical obligations).
- **Urgent**: Processed before Normal payments. Used for important client payments or time-sensitive obligations.
- **Normal**: Standard processing order based on submission time (FIFO within priority).

**Why Two Priority Systems?**
This reflects TARGET2 reality: a bank may consider a payment internally critical (high internal priority) but submit it as Normal to the RTGS to avoid higher processing costs or queue competition. Conversely, a routine payment (low internal priority) might need Urgent RTGS status due to a client deadline.

Banks can **withdraw** payments from Queue 2 and **resubmit** with different RTGS priorities, but this resets their FIFO position within the new priority level.

### Bilateral and Multilateral Limits

Banks can configure exposure limits that constrain payment flows:

**Bilateral Limits**
Maximum cumulative outflow to a specific counterparty within a business day. Once reached, payments to that counterparty queue until the limit resets (typically at day-end) or incoming payments reduce net exposure.

**Multilateral Limits**
Maximum total outflow to all counterparties combined. This caps overall liquidity depletion regardless of counterparty mix.

**Why Limits Matter:**
- **Risk Management**: Prevents excessive exposure to a single counterparty
- **Liquidity Conservation**: Ensures reserves aren't depleted beyond comfort levels
- **Strategic Behavior**: Limits can force payments into LSM cycles rather than immediate settlement

When limits are exceeded, payments queue rather than fail—they await capacity under the limit or LSM settlement.

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

- [x] RTGS settles immediately when liquidity is available
- [x] Insufficient liquidity queues payments, doesn't reject them
- [x] LSM bilateral offsets reduce liquidity usage, not payment values
- [x] LSM cycles are atomic (all-or-nothing)
- [x] Settlement is final and irreversible

### Queue Behavior

- [x] Queue 1 represents bank-controlled delay (strategic)
- [x] Queue 2 represents system-controlled waiting (mechanical)
- [x] Delay costs only accrue in Queue 1
- [x] LSM only operates on Queue 2

### Cost Behavior

- [x] Liquidity costs scale with usage duration and amount
- [x] Delay costs scale with waiting time in Queue 1
- [x] End-of-day creates strong settlement pressure
- [x] Higher priority payments receive preferential treatment when enabled

### Coordination Dynamics

- [x] Low liquidity should increase gridlock risk
- [x] LSM should reduce delays and liquidity usage vs. pure RTGS
- [x] Strategic waiting should emerge when delay costs are low relative to liquidity costs
- [ ] Throughput guidelines should shift settlement timing patterns

### TARGET2 Alignment

- [x] Dual priority system: internal (0-10) vs RTGS (HighlyUrgent/Urgent/Normal)
- [x] Bilateral limits constrain per-counterparty outflows
- [x] Multilateral limits constrain total outflows
- [x] Algorithm sequencing: FIFO → Bilateral → Multilateral
- [x] Entry disposition offsetting checks at payment entry
- [x] Payments can be withdrawn and resubmitted with new RTGS priority
- [x] Limits respected by LSM algorithms

### Determinism

- [x] Same seed + same configuration = identical results
- [x] All randomness comes from the seeded RNG
- [x] No system time, network calls, or non-deterministic operations

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
| **Bilateral Offset** | Settling two opposing payments at net liquidity cost (Algorithm 2) |
| **Multilateral Cycle** | Settling a ring of payments simultaneously (Algorithm 3) |
| **Tick** | Discrete time unit in the simulation |
| **Credit Headroom** | Available intraday credit from central bank |
| **Internal Priority** | Bank's own urgency rating (0-10) for internal queue ordering |
| **RTGS Priority** | Declared priority for Queue 2: Highly Urgent, Urgent, or Normal |
| **Bilateral Limit** | Maximum outflow to a specific counterparty per day |
| **Multilateral Limit** | Maximum total outflow to all counterparties per day |
| **Entry Disposition** | Offset check performed when payment enters Queue 2 |
| **Algorithm Sequencing** | Formal order of LSM algorithms: FIFO → Bilateral → Multilateral |

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
