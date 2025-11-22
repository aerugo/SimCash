# Research: TARGET2 Priority Mechanisms and Cost Implications

## Overview

This document analyzes how TARGET2 (and its successor T2) handles payment priority levels and explores options for implementing realistic priority-related costs in our simulation.

## Key Finding: No Direct Priority Fees in TARGET2

Contrary to initial assumptions, **TARGET2/T2 does not charge different transaction fees based on priority level**. The ECB's pricing structure is based on:

1. **Fixed monthly fee + fixed transaction fee**, OR
2. **Higher fixed monthly fee + volume-based degressive transaction fee**

Priority (Highly Urgent, Urgent, Normal) does not directly affect the per-transaction cost.

Source: [ECB TARGET2 Fees](https://www.ecb.europa.eu/paym/target/target2/profuse/fees/html/index.en.html)

---

## How TARGET2 Actually Manages Priority

### 1. Three Priority Levels

TARGET2 provides three priority levels for payment processing:

| Priority | Description | Modifiable? |
|----------|-------------|-------------|
| **Highly Urgent** | Central bank operations, critical payments | No - locked once set |
| **Urgent** | Time-sensitive commercial payments | Yes - can switch to/from Normal |
| **Normal** | Standard payments | Yes - can switch to/from Urgent |

Each account maintains **three separate queues**, one per priority level.

Source: [Banque de France - Liquidity Management](https://www.banque-france.fr/en/financial-stability/market-infrastructure-and-payment-systems/target-2-banque-de-france/liquidity-management)

### 2. Liquidity Reservation Mechanism

This is the **primary cost mechanism** for priority usage:

> "Participants have the option of reserving liquidity for urgent and/or highly urgent payments, or for the settlement of ancillary systems."

**How it works:**
- Banks can reserve a portion of their liquidity specifically for Highly Urgent and Urgent payments
- This reserved liquidity is **not available** for Normal priority payments
- A payment can draw liquidity from its own reservation AND lower-level reservations

**Example:**
```
Bank A has €100M total liquidity
- Reserves €20M for Highly Urgent
- Reserves €30M for Urgent
- Remaining €50M available for Normal

A Highly Urgent payment can use: €20M + €30M + €50M = €100M
An Urgent payment can use:        €30M + €50M = €80M
A Normal payment can use:         €50M only
```

Source: [TARGET2 Wikipedia](https://en.wikipedia.org/wiki/TARGET2), [Bundesbank TARGET Services](https://www.bundesbank.de/en/tasks/payment-systems/target/target-services/target-services-626896)

### 3. Settlement Order and FIFO Bypass

Within TARGET2's RTGS model:

1. **Priority ordering**: Highly Urgent → Urgent → Normal
2. **FIFO within priority**: First-in-first-out applies within each priority level
3. **FIFO bypass for Normal**: Normal payments can be bypassed if insufficient liquidity; system tries next payment in queue

> "The FIFO bypass principle for normal payments means that submission time for normal payment is meaningless."

This creates an **implicit cost**: Normal priority payments face higher settlement risk and potential delays.

Source: [BIS Working Papers - Intraday Liquidity](https://www.bis.org/publ/work1089.pdf)

### 4. Bilateral and Multilateral Limits

Banks can set:
- **Bilateral limits**: Maximum outflow to a specific counterparty
- **Multilateral limits**: Maximum total outflow to all participants

These limits interact with priority—reserved liquidity for Highly Urgent may still be subject to limits.

---

## The "Costs" of Using Higher Priority in TARGET2

Although there's no direct fee, using higher priority has real costs:

### A. Opportunity Cost of Reserved Liquidity

If a bank reserves €30M for Urgent payments but doesn't use it all, that liquidity:
- Could have been invested overnight
- Could have earned returns in money markets
- Is "locked" until end of day or manual release

**Quantifiable as**: `reserved_amount × overnight_rate × time_held`

### B. Settlement Risk for Normal Payments

Normal payments face:
- Potential FIFO bypass (other normal payments settle first)
- Lower access to liquidity (only unreserved portion)
- Higher probability of end-of-day failure

**Quantifiable as**: Increased delay costs and EOD penalties

### C. Regulatory/Operational Scrutiny

Overuse of Highly Urgent priority may:
- Trigger central bank monitoring
- Indicate operational issues
- Draw compliance questions

**Not directly quantifiable** but represents reputational cost.

### D. Correspondent Banking Premiums

When using correspondent banks for cross-border payments:
- Urgent processing often incurs premium fees
- Same-day vs. next-day settlement pricing differs

**Quantifiable** but varies by bilateral agreement.

---

## Implementation Options for Our Simulation

### Option 1: Direct Priority Fees (Simplest)

Add explicit fees per priority level to `CostRates`:

```rust
pub struct CostRates {
    // Existing fields...

    /// Fee charged when submitting with HighlyUrgent priority (cents)
    pub highly_urgent_submission_fee: i64,  // e.g., 500 cents = $5

    /// Fee charged when submitting with Urgent priority (cents)
    pub urgent_submission_fee: i64,         // e.g., 100 cents = $1

    // Normal is free (baseline)
}
```

**Pros:**
- Simple to implement
- Clear cost signal for policies
- Easy to tune game balance

**Cons:**
- Not how TARGET2 actually works
- Doesn't model the liquidity tradeoff

**Recommendation**: Good for game balance, but document as "simplified model"

---

### Option 2: Liquidity Reservation System (Most Realistic)

Implement TARGET2's actual reservation mechanism:

```rust
pub struct AgentConfig {
    // Existing fields...

    /// Liquidity reserved for HighlyUrgent payments
    pub highly_urgent_liquidity_reserve: i64,

    /// Liquidity reserved for Urgent payments
    pub urgent_liquidity_reserve: i64,

    // Remaining liquidity available for Normal
}

// Settlement logic:
fn available_liquidity_for_priority(agent: &Agent, priority: RtgsPriority) -> i64 {
    let total = agent.balance + agent.credit_limit;
    match priority {
        HighlyUrgent => total,  // Can use everything
        Urgent => total - agent.highly_urgent_reserve,
        Normal => total - agent.highly_urgent_reserve - agent.urgent_reserve,
    }
}
```

**Add opportunity cost** for reserved liquidity:

```rust
pub struct CostRates {
    /// Opportunity cost rate for reserved liquidity (bps per tick)
    pub liquidity_reservation_opportunity_cost_bps: f64,
}

// Each tick, charge:
// (highly_urgent_reserve + urgent_reserve) × opportunity_cost_rate
```

**Pros:**
- Models TARGET2 accurately
- Creates strategic liquidity allocation decisions
- Policies must balance reservation vs. flexibility

**Cons:**
- More complex to implement
- Requires agent configuration changes
- Harder to explain to users

**Recommendation**: Best for realism, good research/training value

---

### Option 3: Priority-Based Delay Risk (Behavioral)

Model the FIFO bypass behavior where Normal payments have higher delay risk:

```rust
pub struct CostRates {
    /// Base delay cost per tick (for HighlyUrgent - lowest risk)
    pub delay_cost_per_tick_highly_urgent: f64,

    /// Delay cost multiplier for Urgent priority
    pub delay_cost_multiplier_urgent: f64,      // e.g., 1.5x

    /// Delay cost multiplier for Normal priority
    pub delay_cost_multiplier_normal: f64,      // e.g., 3.0x
}
```

**Rationale**: Normal payments face higher delay costs because:
- They're more likely to be bypassed
- They have lower effective liquidity access
- The "risk" of using normal priority is priced into delay cost

**Pros:**
- No new mechanisms needed
- Models the behavioral outcome
- Policies naturally prefer higher priority for urgent deadlines

**Cons:**
- Indirect (doesn't explain WHY normal is riskier)
- May not feel intuitive to users

**Recommendation**: Good middle ground, easy to implement

---

### Option 4: Hybrid Approach (Recommended)

Combine elements for both realism and playability:

```rust
pub struct CostRates {
    // === Existing costs ===
    pub delay_cost_per_tick_per_cent: f64,
    pub overdraft_bps_per_tick: f64,
    // ... etc ...

    // === NEW: Priority costs (game balance) ===
    /// One-time fee for HighlyUrgent submission (cents)
    pub highly_urgent_fee: i64,

    /// One-time fee for Urgent submission (cents)
    pub urgent_fee: i64,

    // === NEW: Liquidity reservation (realism) ===
    /// Opportunity cost of reserved liquidity (bps per tick)
    pub reservation_opportunity_cost_bps: f64,
}

pub struct AgentConfig {
    // === NEW: Liquidity reservation ===
    /// Liquidity reserved for HighlyUrgent (reduces Normal availability)
    pub highly_urgent_reserve: i64,

    /// Liquidity reserved for Urgent (reduces Normal availability)
    pub urgent_reserve: i64,
}
```

**Implementation phases:**

1. **Phase 1**: Add direct fees (quick win for game balance)
2. **Phase 2**: Add liquidity reservation (deeper strategy)
3. **Phase 3**: Add priority-based settlement ordering in Queue 2

---

## Configuration Examples

### Minimal (Direct Fees Only)
```yaml
cost_rates:
  highly_urgent_fee: 500        # $5 per HighlyUrgent submission
  urgent_fee: 100               # $1 per Urgent submission
  # Normal is free
```

### Realistic (Full Reservation Model)
```yaml
agents:
  - id: "ALPHA_BANK"
    opening_balance: 5000000
    highly_urgent_reserve: 1000000   # Reserve $10K for highly urgent
    urgent_reserve: 2000000          # Reserve $20K for urgent
    # $20K available for normal payments

cost_rates:
  reservation_opportunity_cost_bps: 0.0002  # 2 bps annualized
```

---

## Impact on Policies

With priority costs implemented, policies must make strategic decisions:

### Current State (No Priority Costs)
```
Policy decision: "Always use HighlyUrgent for faster settlement"
Result: Everyone uses HighlyUrgent, priority system meaningless
```

### With Priority Costs
```
Policy decision tree:
  IF deadline_critical AND amount_large:
    → Pay the HighlyUrgent fee for guaranteed fast settlement
  ELIF deadline_approaching:
    → Use Urgent (moderate cost, good priority)
  ELSE:
    → Use Normal (free, but may be bypassed)
```

This creates the **strategic tradeoff** that makes the priority system meaningful.

---

## Research References

1. [ECB T2 Overview](https://www.ecb.europa.eu/paym/target/t2/html/index.en.html) - Official T2 documentation
2. [ECB TARGET2 Fees](https://www.ecb.europa.eu/paym/target/target2/profuse/fees/html/index.en.html) - Pricing structure
3. [TARGET Services Pricing Guide (2024)](https://www.ecb.europa.eu/paym/target/coco/shared/docs/ecb.pricingcoco_target.en.pdf) - Detailed pricing
4. [Bundesbank TARGET Services](https://www.bundesbank.de/en/tasks/payment-systems/target/target-services/target-services-626896) - Liquidity management
5. [TARGET2 Wikipedia](https://en.wikipedia.org/wiki/TARGET2) - General overview
6. [BIS Working Papers - Intraday Liquidity](https://www.bis.org/publ/work1089.pdf) - FIFO bypass analysis
7. [ECB Economic Bulletin - Liquidity Distribution](https://www.ecb.europa.eu/press/economic-bulletin/articles/2020/html/ecb.ebart202005_03~4a20eae0c8.en.html) - Settlement patterns

---

## Recommendation

**Implement Option 4 (Hybrid Approach)** in two phases:

1. **Immediate**: Add `highly_urgent_fee` and `urgent_fee` to `CostRates`
   - Quick implementation
   - Immediate game balance improvement
   - Defaults to 0 for backward compatibility

2. **Future**: Add liquidity reservation system
   - Per-agent reserve configuration
   - Opportunity cost for reserves
   - Priority-aware available liquidity calculation

This gives us both playability (direct fees) and realism (reservation system) while maintaining backward compatibility.

---

*Document created: 2024-11-22*
*Author: Claude Code (research task)*
*Status: Draft - pending implementation decision*
