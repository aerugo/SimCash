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

### Priority System

The simulation implements TARGET2's **dual priority system**, separating internal bank priorities from RTGS queue priorities.

#### Internal Priority (0-10)

- The bank's own assessment of payment urgency
- Used for internal queue ordering in Queue 1
- Higher values mean more urgent to the sending bank
- Does not directly affect RTGS processing order

**Priority Bands**: Internal priorities map to three bands:
| Band | Priority Range | Typical Use |
|------|---------------|-------------|
| **Urgent** | 8-10 | Time-critical, high-value |
| **Normal** | 4-7 | Standard business payments |
| **Low** | 0-3 | Flexible timing, batch-eligible |

#### RTGS Declared Priority

When submitting to the central RTGS system (Queue 2), banks declare one of three priority levels:

- **Highly Urgent**: Processed before all other payments. Used for critical settlements (e.g., ancillary system settlements, time-critical obligations).
- **Urgent**: Processed before Normal payments. Used for important client payments or time-sensitive obligations.
- **Normal**: Standard processing order based on submission time (FIFO within priority).

**Why Two Priority Systems?**
This reflects TARGET2 reality: a bank may consider a payment internally critical (high internal priority) but submit it as Normal to the RTGS to avoid higher processing costs or queue competition. Conversely, a routine payment (low internal priority) might need Urgent RTGS status due to a client deadline.

Banks can **withdraw** payments from Queue 2 and **resubmit** with different RTGS priorities, but this resets their FIFO position within the new priority level.

#### Queue Ordering Modes

**Queue 1** supports two ordering modes:

- **FIFO** (default): Transactions processed in arrival order. Policy evaluates each in sequence.
- **Priority-Deadline**: Sorted by priority (descending), then deadline (ascending), then arrival (tie-breaker). Ensures urgent payments with tight deadlines are evaluated first.

**Queue 2** processes payments within each RTGS priority level in FIFO order. When T2 priority mode is enabled, all Highly Urgent payments process before any Urgent, and all Urgent before any Normal.

#### Priority Escalation

As deadlines approach, transaction priority can automatically increase to ensure timely processing:

```
escalated_priority = min(10, original_priority + max_boost × progress)
```

Where `progress` measures how close the deadline is (0.0 = just arrived, 1.0 = at deadline).

**Configuration**:
- `enabled`: Turn escalation on/off
- `start_escalating_at_ticks`: Begin escalation N ticks before deadline
- `max_boost`: Maximum priority increase (e.g., +3)
- `curve`: Escalation shape (linear, exponential)

**Real-world parallel**: Treasury systems often have escalation rules that automatically elevate payment priority as cutoff times approach, ensuring critical deadlines aren't missed due to queue position.

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

Costs in the simulation represent real economic pressures. Each cost type has explicit formulas to enable deterministic calculation.

### Overdraft Costs (Liquidity)

**What it represents**: Interest charged on negative balances (intraday credit usage).

**Formula**:
```
overdraft_cost = overdraft_cost_bps × |negative_balance| × (1 / ticks_per_day) / 10000
```

**Real-world parallel**: Central banks charge for intraday overdrafts, typically 10-50 basis points annualized. Banks optimize to minimize time spent in overdraft.

### Collateral Costs

**What it represents**: Opportunity cost of securities posted as collateral to secure credit lines.

**Formula**:
```
collateral_cost = collateral_cost_bps × posted_collateral × (1 / ticks_per_day) / 10000
```

**Real-world parallel**: Collateral tied up at the central bank cannot be used for repo, securities lending, or other yield-generating activities.

**Note**: Collateral costs are distinct from overdraft costs—posting collateral expands credit capacity but incurs its own carrying cost.

### Delay Costs (Queue 1 Only)

**What it represents**: Client dissatisfaction, SLA penalties, reputational damage from slow payment execution.

**Formula**:
```
delay_cost = delay_penalty_per_tick × (current_tick - arrival_tick)
```

**Why only Queue 1**: Payments held *by the bank* create client-facing delays. Payments queued *at the central bank* (Queue 2) are waiting for system-level liquidity—the bank has already submitted, so no further delay penalty applies.

**Priority multipliers**: Urgent payments may incur higher delay costs:
```
effective_delay_cost = delay_cost × priority_delay_multiplier
```
Where multipliers differ by priority band (e.g., 1.5× for Urgent, 1.0× for Normal).

### Deadline Penalties

**What it represents**: One-time penalty when a transaction's deadline passes without settlement.

**Formula**:
```
deadline_penalty = deadline_penalty_amount  (one-time charge when deadline exceeded)
```

**Real-world parallel**: Certain payments (securities settlement, margin calls, regulatory deadlines) have hard deadlines with severe consequences.

### Overdue Delay Costs

**What it represents**: Accelerated delay costs for transactions past their deadline but still pending.

**Formula**:
```
overdue_delay_cost = delay_penalty_per_tick × overdue_multiplier × ticks_overdue
```

**Default multiplier**: 5× (transactions past deadline cost 5× more per tick than normal delay).

**Real-world parallel**: Missing a deadline triggers escalation—more resources, management attention, and client remediation.

### Split Friction Costs

**What it represents**: Operational overhead of dividing a payment into multiple smaller instructions.

**Formula**:
```
split_cost = split_friction_cost × (num_parts - 1)
```

**Real-world parallel**: Each payment instruction requires message processing, reconciliation, and audit trail. Splitting multiplies this overhead.

### End-of-Day Penalties

**What it represents**: Severe penalty for transactions still unsettled at market close.

**Formula**:
```
eod_penalty = eod_unsettled_penalty × (remaining_amount / original_amount)
```

**Real-world parallel**: Unsettled payments at day-end create credit risk, regulatory reporting issues, and operational chaos. This penalty is typically much larger than other costs to strongly incentivize settlement.

### Cost Accumulation

Costs accrue **per tick** (for ongoing costs like overdraft and collateral) or **per event** (for penalties). Each agent tracks:
- Total cost breakdown by type
- Per-transaction cost attribution
- Running cost throughout the day

The cost model ensures that all financial trade-offs are quantifiable, enabling policy optimization.

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

## Policy System

Banks make decisions through **policies**—programs that evaluate context and choose actions. The simulation supports multiple policy representations, from simple rules to complex decision trees.

### Decision Tree Policies

The primary policy mechanism is a **JSON-based decision tree DSL** (Domain-Specific Language):

```
      ┌─────────────────┐
      │  Root Condition │
      │ balance > 50000 │
      └────────┬────────┘
               │
       ┌───────┴───────┐
       │               │
   ┌───▼───┐       ┌───▼───┐
   │ True  │       │ False │
   │release│       │ hold  │
   └───────┘       └───────┘
```

**Key characteristics**:
- **Condition nodes**: Evaluate expressions against current context (e.g., `balance > 50000`, `priority >= 8`)
- **Action nodes**: Specify what to do (`release`, `hold`, `split`, `post_collateral`)
- **Nested logic**: Trees can branch multiple levels deep for complex strategies

### Policy Tree Types

Different trees control different decisions:

| Tree Type | When Evaluated | Controls |
|-----------|----------------|----------|
| **payment_tree** | For each pending payment | Release, hold, or split this payment |
| **bank_tree** | Once per tick (before payments) | Bank-wide decisions, budget allocation |
| **strategic_collateral_tree** | Before settlement attempts | Whether to post/withdraw collateral |
| **end_of_tick_collateral_tree** | After all settlements | End-of-tick collateral adjustments |

### Policy Context

Policies evaluate against a rich context providing 140+ fields including:
- **Balance state**: `balance`, `available_liquidity`, `credit_headroom`
- **Queue state**: `queue1_size`, `queue1_value`, `queue2_size`
- **Transaction details**: `tx_amount`, `tx_priority`, `tx_deadline`, `ticks_to_deadline`
- **Time**: `current_tick`, `ticks_remaining_in_day`, `is_end_of_day`
- **Costs**: `total_cost_so_far`, `delay_cost_so_far`
- **Custom registers**: 10 numeric registers for policy memory across ticks

### Built-in Policies

For common strategies, pre-built policies are available:
- **Fifo**: Release payments in arrival order when funds available
- **Deadline**: Prioritize payments closest to deadline
- **LiquidityAware**: Consider balance and incoming flow before releasing
- **TreePolicy**: Custom decision tree (most flexible)

---

## Configuration Toggles

Several features can be enabled or disabled to model different RTGS system designs:

### Settlement Features

| Toggle | Default | Effect When Enabled |
|--------|---------|---------------------|
| `entry_disposition_offsetting` | false | Check for bilateral offset when payment enters Queue 2 |
| `algorithm_sequencing` | true | Run LSM algorithms in sequence: FIFO → Bilateral → Multilateral |
| `deferred_crediting` | false | Defer credit application to end of tick (prevents within-tick recycling) |

### Priority Features

| Toggle | Default | Effect When Enabled |
|--------|---------|---------------------|
| `priority_mode` | false | Process Queue 2 strictly by priority band (all Urgent before any Normal) |
| `priority_escalation.enabled` | false | Auto-boost priority as deadlines approach |
| `queue1_ordering` | "Fifo" | How Queue 1 is sorted ("Fifo" or "priority_deadline") |

### Deferred Crediting Mode

When enabled, settlement credits accumulate during a tick but only apply at tick end:

```
Without deferred crediting:
  Tick N: A pays B $100 → B's balance increases immediately
          B can use those funds for subsequent settlements in same tick

With deferred crediting:
  Tick N: A pays B $100 → Credit queued
          B cannot use funds until tick N+1
  End of tick: Credits applied
```

This prevents liquidity "recycling" within a tick, more closely modeling systems where settlement finality has processing delay.

---

## Policy Evaluation

The simulation enables AI-driven policy optimization through bootstrap evaluation. This section describes the conceptual foundations.

### The Single-Agent Perspective

When evaluating policy performance, we adopt a **single-agent perspective**. For a bank's AI cash manager:

**What the Agent Knows (Information Set):**
| Known (✓) | Unknown (✗) |
|-----------|-------------|
| Current balance at central bank | Future payment arrivals |
| Pending outgoing payments (amounts, deadlines, priorities) | Other banks' strategies |
| Historical pattern of incoming payments | Exact timing of incoming settlements |
| Cost parameters (overdraft rates, delay penalties) | |

**What the Agent Controls:**
- When to release outgoing transactions (Queue 1 → RTGS submission)
- Which priority to assign for RTGS processing
- Whether and how much collateral to post
- Whether to split large payments

**What is Exogenous (Fixed External Events):**
- When counterparties pay (incoming liquidity timing)
- Amounts of incoming payments
- System-wide congestion patterns

This separation is fundamental: the agent optimizes its decisions given the world it observes, but cannot control counterparty behavior within an evaluation period.

### The Liquidity Beats Concept

**Key insight**: Incoming settlements can be modeled as **"liquidity beats"**—fixed external events that define when an agent receives cash.

Consider Agent A receiving payments from other banks:
```
Tick:    0    1    2    3    4    5    6    7    8    9    10   11   12
         │    │    │    │    │    │    │    │    │    │    │    │    │
         │    │    │    ▼    │    │    ▼    │    │    │    ▼    │    │
         │    │    │  $50k   │    │  $30k   │    │    │  $80k   │    │
         └────┴────┴─────────┴────┴─────────┴────┴────┴─────────┴────┴──►

These "beats" define when Agent A receives liquidity.
Agent A's policy decides when to SPEND this liquidity.
```

Like a musical beat, these are the rhythmic moments when liquidity arrives. The AI cannot change when other banks pay—it can only decide how to respond.

**Why "beats" preserve system dynamics**: When historical transactions are used for policy evaluation, the **timing offsets are preserved**:

- `deadline_offset = deadline_tick - arrival_tick` (how long until deadline)
- `settlement_offset = settlement_tick - arrival_tick` (how long until settlement)

If a historical transaction took 5 ticks to settle (due to Queue 2 wait, LSM cycles, or gridlock), that 5-tick offset is preserved when the transaction is resampled. This implicitly captures:
- **LSM effects**: Quick settlements via bilateral offset
- **Queue 2 dynamics**: Wait times for liquidity
- **Gridlock effects**: Slow settlement days produce slow offset distributions

### The Coordination Game

The fundamental tension creates a coordination game between banks:

```
                      Bank B: Wait & See    |    Bank B: Pay Early
            ─────────────────────────────────┼─────────────────────────────
Bank A:     │                                │
Pay Early   │  B pays A's liquidity          │  Both settle quickly
            │  (A loses)                     │  (Mutual gain)
            ─────────────────────────────────┼─────────────────────────────
Bank A:     │                                │
Wait & See  │  GRIDLOCK                      │  A pays B's liquidity
            │  (Both suffer delays)          │  (B loses)
            ─────────────────────────────────┴─────────────────────────────
```

**Game-theoretic interpretations**:

**Stag Hunt** (when LSM is effective): If both cooperate (pay early), everyone benefits from quick settlement. If one defects (waits), the cooperator loses but the defector may benefit from recycling. The cooperative equilibrium is efficient but fragile.

**Prisoner's Dilemma** (when liquidity is scarce): Individual incentive to wait dominates collective benefit of paying early. Without LSM intervention, gridlock is the Nash equilibrium.

**Parameter sensitivity**: The game structure depends on the ratio of delay costs to liquidity costs:
- High delay costs → Pay early is dominant strategy
- Low delay costs, high liquidity costs → Wait is dominant strategy
- Balanced costs → Mixed strategies emerge, LSM becomes crucial

### Convergence Toward Equilibrium

When multiple agents optimize policies simultaneously:

1. **Day N**: Each agent uses policies optimized from Day N-1 observations
2. **Run simulation**: Agents interact, creating new transaction history
3. **Observe outcomes**: Each agent sees counterparty behavior reflected in settlement timing
4. **Update policies**: Each agent proposes improvements via bootstrap evaluation
5. **Repeat**: Policies converge toward approximate equilibrium

This **delayed best-response** dynamic is realistic—real treasury departments analyze yesterday's data to inform today's decisions, not react instantaneously.

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
- [x] Collateral costs are separate from overdraft costs
- [x] Delay costs scale with waiting time in Queue 1
- [x] Overdue transactions incur multiplied delay costs
- [x] End-of-day creates strong settlement pressure
- [x] Higher priority payments receive preferential treatment when enabled
- [x] Split friction costs apply per split operation

### Policy Behavior

- [x] Decision trees evaluate conditions against current context
- [x] Multiple tree types control different decisions (payment, bank, collateral)
- [x] Built-in policies (Fifo, Deadline, LiquidityAware) work correctly
- [x] Policy context provides accurate balance, queue, and cost information

### Deferred Crediting

- [x] When enabled, credits queue until end of tick
- [x] Agents cannot recycle within-tick liquidity when deferred
- [x] LSM bilateral offsets behave correctly under deferred crediting

### Priority Features

- [x] Priority escalation increases priority as deadline approaches
- [x] Priority bands (Urgent/Normal/Low) correctly classify priorities
- [x] Priority delay multipliers apply correct cost scaling
- [x] Queue ordering modes (FIFO vs priority-deadline) work correctly

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
| **Agent** | A bank participant in the simulation (holds settlement balance at central bank) |
| **Algorithm Sequencing** | Formal order of LSM algorithms: FIFO → Bilateral → Multilateral |
| **Arrival** | New payment order entering a bank's Queue 1 |
| **Available Liquidity** | Total funds available for settlement: `balance + credit_headroom` |
| **Balance** | Bank's settlement account balance at central bank (can go negative with credit) |
| **Best Response** | Optimal policy given fixed counterparty behaviors (building block for equilibrium) |
| **Bilateral Limit** | Maximum outflow to a specific counterparty per day |
| **Bilateral Offset** | Settling two opposing payments at net liquidity cost (Algorithm 2) |
| **Bootstrap** | Statistical resampling technique for estimating distributions from observed data (Efron, 1979) |
| **Cash Manager** | Treasury operations role making intraday payment decisions (modeled by policies) |
| **Collateral** | Assets posted to secure intraday credit (incurs opportunity cost) |
| **Collateral Cost** | Opportunity cost of securities posted to secure credit lines (distinct from overdraft cost) |
| **Credit Headroom** | Available intraday credit: `unsecured_cap + (posted_collateral × (1 - haircut))` |
| **Cycle** | Circular payment chain (A→B→C→A) settleable with net-zero liquidity |
| **Deadline** | Latest tick for transaction settlement (penalties apply if missed) |
| **Decision Tree** | Policy representation using condition/action nodes to make payment decisions |
| **Deferred Crediting** | Settlement mode where credits apply at tick end, preventing within-tick recycling |
| **Determinism** | Property that same seed produces identical outcomes (essential for replay) |
| **Entry Disposition** | Offset check performed when payment enters Queue 2 |
| **EOD Penalty** | Large penalty for transactions unsettled at end of day |
| **Episode** | Complete simulation run (one or more business days) |
| **Finality** | Irreversibility of settled payments |
| **Gridlock** | Circular dependency where all parties wait for each other |
| **Internal Priority** | Bank's own urgency rating (0-10) for internal queue ordering |
| **Liquidity Beats** | Sequence of incoming settlements as fixed external events in policy evaluation |
| **Liquidity Pressure** | Metric of how constrained an agent's liquidity is (0-1 scale) |
| **LSM** | Liquidity-Saving Mechanism—algorithms that reduce liquidity needs through smart grouping |
| **Multilateral Cycle** | Settling a ring of payments simultaneously (Algorithm 3) |
| **Multilateral Limit** | Maximum total outflow to all counterparties per day |
| **Overdue** | Transaction status when deadline has passed but settlement is still pending |
| **Overdue Multiplier** | Factor applied to delay costs after deadline passes (default 5×) |
| **Policy** | Decision-making program that evaluates context and chooses actions (release, hold, split) |
| **Priority Band** | Grouping of priorities: Urgent (8-10), Normal (4-7), Low (0-3) |
| **Priority Escalation** | Automatic priority boost as transaction deadline approaches |
| **Queue 1** | Bank's internal queue (strategic holding) |
| **Queue 2** | Central system queue (awaiting liquidity) |
| **Recycling** | Using incoming settlement proceeds to fund outgoing payments |
| **RTGS** | Real-Time Gross Settlement—payments settle individually and immediately |
| **RTGS Priority** | Declared priority for Queue 2: HighlyUrgent, Urgent, or Normal |
| **Split Friction** | Operational cost incurred when dividing a payment into multiple parts |
| **Splitting** | Voluntary division of large payment into N separate instructions (agent pacing) |
| **Throughput** | Cumulative value settled / cumulative value arrived (0-1 ratio) |
| **Tick** | Discrete time unit in the simulation |
| **Transaction Status** | Lifecycle state: Pending → PartiallySettled → Settled (or Overdue if deadline passed) |

---

## References

The simulation draws on concepts from:

### Academic Papers

1. **Efron, B. (1979)** - "Bootstrap methods: Another look at the jackknife" (*Annals of Statistics*) - Foundation for statistical resampling in policy evaluation
2. **Danmarks Nationalbank (2001)** - "Gridlock Resolution in Payment Systems" - Key result: LSM reduces gridlock duration by 40-60% under constrained liquidity
3. **ECB Economic Bulletin (2020)** - "Liquidity Distribution and Settlement in TARGET2" - Key result: Bilateral offsetting provides 30-40% liquidity savings in typical operations
4. **BIS Quarterly Review (2021)** - "Central Bank Digital Currency: Opportunities and Challenges" - RTGS design principles apply to CBDC settlement layers

### Technical Documentation

1. **European Central Bank** - TARGET2 documentation and business descriptions
2. **Riksbank** - RIX-RTGS documentation and T2 integration plans
3. **Bank for International Settlements** - CPMI-IOSCO Principles for Financial Market Infrastructures (2012)

For implementation details, see the technical documentation in `CLAUDE.md` and the architecture guide in `docs/architecture.md`.

---

*This document describes concepts and design intent. For configuration options and implementation specifics, see the CLAUDE.md files and API documentation.*
