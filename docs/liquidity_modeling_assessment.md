# SimCash Liquidity Modeling Assessment for Smaller Banks
## Comprehensive Gap Analysis and Recommendations

**Date:** 2025-11-04
**Version:** 1.0
**Status:** Initial Assessment

---

## Executive Summary

This report evaluates how well the SimCash payment system simulator models liquidity considerations for smaller banks, particularly in the context of structural payment imbalances common in Real-Time Gross Settlement (RTGS) systems. We assess the codebase against a comprehensive framework derived from European payment system practices (TARGET2, RIX-RTGS, CHAPS) and identify gaps in modeling realistic liquidity dynamics.

**Key Finding:** SimCash has a **robust foundation** for RTGS simulation with strong LSM (liquidity-saving mechanisms), credit facilities, and cost-based optimization. However, it currently models a **stylized RTGS-only world** that does not fully capture how smaller banks avoid structural liquidity drains in real payment systems.

**Priority Gaps:**
1. ❌ **No ancillary system netting** (all payments hit RTGS gross)
2. ⚠️ **Partial intraday credit modeling** (no automatic EOD rollover to overnight)
3. ❌ **No active funding desk** (banks cannot pre-fund or adjust reserves dynamically)
4. ❌ **No tiered participation** (correspondent banking model missing)
5. ⚠️ **Limited counterflow modeling** (arrival system supports this but not explicitly scheduled)
6. ⚠️ **Soft throughput incentives only** (EOD penalties exist but no interim checkpoints)
7. ❌ **No LCR-style regulatory guardrails** (nothing prevents chronic deficits)

---

## Assessment Framework

We evaluate SimCash against **seven modules** recommended for realistic modeling of smaller bank liquidity in RTGS systems:

| Module | Description | Real-World Practice | SimCash Status |
|--------|-------------|---------------------|----------------|
| **A** | Ancillary system netting | EURO1/STEP2 → TARGET2; Bankgirot → RIX | ❌ Not Implemented |
| **B** | Intraday credit + EOD rollover | ECB/Riksbank collateralized ICL @ 0%, auto-roll to MLF | ⚠️ Partial |
| **C** | Daily funding desk | Repo, unsecured, standing facilities | ❌ Not Implemented |
| **D** | Tiering (correspondent banking) | TARGET2 tiered participation | ❌ Not Implemented |
| **E** | Scheduled counterflows | Payroll, pensions, gov disbursements | ⚠️ Supported but not explicit |
| **F** | Throughput nudges | CHAPS 50%/75% targets with soft penalties | ⚠️ Partial (EOD only) |
| **G** | LCR-style guardrail | Basel III HQLA/net outflows ≥ 100% | ❌ Not Implemented |

**Legend:**
✅ Fully Implemented | ⚠️ Partial/Foundational | ❌ Not Implemented

---

## Module-by-Module Analysis

### Module A: Ancillary System Netting ❌

**What Real Systems Do:**
Most retail and commercial payments are cleared in **ancillary systems** (e.g., EURO1, STEP2, Bankgirot) and only **net positions** settle in RTGS at scheduled windows (e.g., 10:00, 13:00, 16:00). This means a small bank sending €100M in consumer payments and receiving €95M shows a **€5M net** in RTGS, not €195M gross.

**What SimCash Does:**
```rust
// backend/src/arrivals/mod.rs:116
pub fn generate_for_agent(&mut self, agent_id: &str, tick: usize, rng: &mut RngManager)
    -> Vec<Transaction>
```
Every generated transaction becomes an **individual RTGS payment**. There is no concept of:
- Separate clearing rails (ACH, card networks, DNS)
- Net position calculation at scheduled windows
- Batching gross flows into net obligations

**Impact on Smaller Banks:**
In SimCash, a retail-heavy bank sending many small consumer payments faces **gross liquidity demands** that would be netted in reality. This **overstates** their RTGS queue size and overdraft usage.

**Example:**
Real world:
- SmallBank sends 1000 × €100 = €100k (retail)
- SmallBank receives 950 × €100 = €95k (retail)
- **Net to RTGS:** €5k outflow at 13:00 settlement window

SimCash:
- SmallBank sends 1000 individual RTGS payments = €100k
- SmallBank receives 950 individual RTGS payments = €95k
- **Gross RTGS exposure:** Up to €100k if sends happen before receives

**Recommendation:**
```
PRIORITY: HIGH
EFFORT: MODERATE (4-6 engineering days)

Implementation approach:
1. Create `AncillaryRail` struct with:
   - Rail type (ACH, card, DNS)
   - Settlement windows (vec of tick numbers)
   - Per-agent gross send/receive accumulators
2. Modify arrivals to route based on transaction type:
   - Retail/commercial → ancillary rail
   - High-value/urgent → direct RTGS
3. At settlement window ticks:
   - Compute per-agent net = gross_sent - gross_received
   - Inject net as single RTGS transaction
   - Clear accumulators
4. Add configuration:
   - `ancillary_rails`: list of rail definitions
   - Per-arrival config: rail assignment
```

**Code Locations:**
- `backend/src/arrivals/mod.rs` - arrival generation (needs rail router)
- `backend/src/orchestrator/engine.rs:tick()` - needs ancillary settlement step
- New module: `backend/src/ancillary/` for netting logic

---

### Module B: Intraday Credit + EOD Rollover ⚠️

**What Real Systems Do:**
Central banks provide **collateralized intraday credit** at 0% interest. If a bank has negative balance at end-of-day, the overdraft **automatically rolls to overnight** at the marginal lending facility rate (e.g., ECB MLF). Next morning, it converts back to intraday credit or must be repaid.

**What SimCash Does:**
```rust
// backend/src/models/agent.rs:67-72
/// Maximum intraday credit/overdraft allowed (i64 cents)
/// This is the absolute limit the agent can go negative
///
/// Represents collateralized intraday credit or priced overdraft facility
/// provided by the central bank.
credit_limit: i64,
```

SimCash **has** intraday credit (`balance + credit_limit = available liquidity`). Credit usage is priced:

```rust
// backend/src/orchestrator/engine.rs:221-223
pub struct CostRates {
    /// Overdraft cost in basis points per tick
    overdraft_bps_per_tick: f64,
```

Cost accrual works:
```rust
// backend/tests/test_cost_accrual.rs:72
// Balance is -200k
// Tick 0: -200k * 0.001 = 200 cents overdraft cost
```

**What's Missing:**
1. **No automatic EOD rollover mechanism** - negative balances persist as "intraday" indefinitely
2. **No distinction** between intraday (0% or cheap) vs. overnight (penalty rate) credit
3. **No morning repayment** - no concept of daily funding cycles

**Current Workaround:**
The `eod_penalty_per_transaction` creates indirect pressure to settle by EOD, but it penalizes **unsettled transactions**, not negative balances.

```rust
// backend/src/orchestrator/engine.rs:233-234
/// End-of-day penalty for each unsettled transaction (cents)
pub eod_penalty_per_transaction: i64,
```

**Recommendation:**
```
PRIORITY: MEDIUM
EFFORT: MODERATE (3-4 engineering days)

Implementation approach:
1. Split credit into two tiers in Agent:
   - `intraday_credit_limit`: collateralized, 0% rate
   - `overnight_credit_limit`: standing facility, penalty rate
2. Add EOD rollover in orchestrator end_of_day():
   if balance < 0 {
       overnight_loan = abs(balance);
       emit OvernightBorrowEvent { amount, rate };
   }
3. Add start-of-day repayment:
   - Convert overnight back to intraday (or keep if structural)
   - Accrue overnight cost at higher rate
4. Update CostRates:
   - `intraday_overdraft_bps_per_tick`: 0.0 (free)
   - `overnight_overdraft_bps_per_tick`: 10x higher
```

**Code Locations:**
- `backend/src/models/agent.rs` - add overnight loan tracking
- `backend/src/orchestrator/engine.rs:end_of_day()` - add rollover logic
- `backend/src/orchestrator/engine.rs:220` (CostRates) - split rates

---

### Module C: Daily Funding Desk ❌

**What Real Systems Do:**
Banks actively manage reserves through:
1. **Pre-opening funding decisions:** Repo, unsecured borrowing to reach target buffer
2. **Intraday adjustments:** Monitor position, borrow/lend in money markets
3. **Collateral management:** Post/release collateral to adjust credit headroom
4. **Standing facilities:** Last resort overnight lending (penalty rate)

**What SimCash Does:**
Agents are **passive recipients** of credit. They start with:
```rust
// backend/src/orchestrator/engine.rs:137-140
pub struct AgentConfig {
    pub opening_balance: i64,
    pub credit_limit: i64,
    // ...
}
```

These values are **static** throughout the day. There is no mechanism for an agent to:
- Borrow reserves before day starts
- Adjust collateral posting to increase `credit_limit`
- Target a specific liquidity buffer via funding

**Partial Support:**
Collateral can be posted:
```rust
// backend/src/models/agent.rs:100-105
/// Posted collateral amount (i64 cents) for Phase 8 cost model
/// Accrues opportunity cost per tick based on collateral_cost_per_tick_bps
posted_collateral: i64,
```

But this is **configuration-time only**, not a **dynamic decision** during simulation.

**Impact on Smaller Banks:**
Small banks in reality would **pre-fund** if expecting large outflows. SimCash banks just accept credit costs passively, which understates their agency and overstates their reliance on intraday credit.

**Recommendation:**
```
PRIORITY: MEDIUM-LOW
EFFORT: HIGH (6-8 engineering days)

Implementation approach:
1. Add pre-opening phase to orchestrator:
   - New step: evaluate_funding_policy()
   - Policies return FundingDecision:
     * BorrowRepo { amount, rate, term }
     * BorrowUnsecured { amount, rate }
     * PostCollateral { amount }
     * UseStandingFacility { amount }
2. Create FundingPolicy trait (parallel to CashManagerPolicy):
   - Context: current balance, expected flows, queue size
   - Returns: vector of funding actions
3. Track borrowed funds separately:
   - `repo_borrowed: Vec<(amount, rate, maturity_tick)>`
   - `unsecured_borrowed: i64`
   - `standing_facility_used: i64`
4. Add repayment at maturity/EOD
5. Extend cost model:
   - Repo cost = amount * rate * term
   - Standing facility = amount * penalty_rate
```

**Code Locations:**
- New module: `backend/src/funding/` for funding policies
- `backend/src/orchestrator/engine.rs` - add funding step to tick loop
- `backend/src/models/agent.rs` - add funding state fields

**Alternative (Lightweight):**
If full funding desk is too complex, add **one-time dynamic collateral posting** at start of day based on expected queue size:
```rust
fn start_of_day_collateral_decision(agent: &mut Agent, expected_outflows: i64) {
    let target_headroom = expected_outflows * 1.2; // 20% buffer
    let needed = target_headroom - agent.available_liquidity();
    if needed > 0 {
        agent.set_posted_collateral(min(needed, agent.remaining_collateral_capacity()));
    }
}
```

---

### Module D: Tiering (Correspondent Banking) ❌

**What Real Systems Do:**
Smaller banks often settle **indirectly** via a larger correspondent bank:
- Small bank has bilateral account with correspondent
- Correspondent executes RTGS leg on small bank's behalf
- Small bank's retail flows are **internalized** or arrive as netted obligations
- Correspondent charges fee + provides intraday credit line

**TARGET2 Example:**
ECB explicitly monitors "tiered participation arrangements" where <30% of participants are direct, rest are indirect via correspondents.

**What SimCash Does:**
All agents are **direct RTGS participants** with equal standing:
```rust
// backend/src/models/state.rs
pub struct SimulationState {
    pub agents: HashMap<String, Agent>,  // All are peers
    // ...
}
```

No concept of:
- Correspondent-respondent relationships
- Indirect settlement via an intermediary
- Bilateral credit limits between pairs
- Nostro account prefunding

**Impact on Smaller Banks:**
Overstates their direct RTGS liquidity burden. In reality, many small banks **don't see RTGS directly**—their correspondent handles it and bills them.

**Recommendation:**
```
PRIORITY: LOW (future enhancement)
EFFORT: HIGH (8-10 engineering days)

Implementation approach:
1. Add agent tier to AgentConfig:
   - tier: Direct | Indirect { correspondent_id: String }
2. For indirect agents:
   - Arrivals flow to correspondent, not RTGS
   - Correspondent tracks bilateral position with respondent
   - Bilateral position settles in RTGS
3. Add correspondent cost model:
   - Fee per transaction processed
   - Bilateral credit limit enforcement
   - Nostro prefunding requirement
4. Extend metrics to track tiering:
   - Direct vs. indirect settlement value
   - Correspondent concentration risk
```

**Code Locations:**
- `backend/src/models/agent.rs` - add `tier` enum
- `backend/src/settlement/rtgs.rs` - routing logic (direct vs. correspondent)
- New module: `backend/src/correspondent/` for bilateral tracking

**Note:**
This is marked LOW priority because it's a structural change that doesn't block current research. Can be added in Phase 12 (Multi-Rail) when cross-border corridors are introduced.

---

### Module E: Scheduled Counterflows ⚠️

**What Real Systems Do:**
Not all payments are consumer→merchant. Regular counterflows include:
- **Payroll** (corporates → consumers, typically last business day of month)
- **Pensions** (government → retirees, monthly)
- **Securities settlement** (DVP proceeds, daily cycles)
- **Tax collections** (consumers → government, quarterly spikes)

These **recycle liquidity** back to banks that are structural payers.

**What SimCash Does:**
The arrival system is **highly configurable**:
```rust
// backend/src/arrivals/mod.rs:42-59
pub struct ArrivalConfig {
    pub rate_per_tick: f64,
    pub amount_distribution: AmountDistribution,
    pub counterparty_weights: HashMap<String, f64>,  // ← Can model asymmetry
    pub deadline_range: (usize, usize),
    // ...
}
```

You **can** model counterflows by:
- Setting `counterparty_weights` for BigBank to send heavily to SmallBank
- Using different `rate_per_tick` per agent to create asymmetric flows
- Modeling time-of-day patterns via different configs per tick range

**What's Missing:**
No **explicit calendar** for scheduled events:
```yaml
# Desired feature:
counterflows:
  - type: payroll
    day_of_month: -1  # Last business day
    sender: CORP_BANK
    receiver_distribution: retail_banks
    amount: 50_000_000
```

**Current Workaround:**
Configure arrivals asymmetrically:
```yaml
agents:
  BIGBANK:
    arrival_config:
      counterparty_weights:
        SMALLBANK: 0.8  # 80% to small bank (payroll-like)
  SMALLBANK:
    arrival_config:
      counterparty_weights:
        BIGBANK: 0.7  # 70% to big bank (retail spending-like)
```

This creates **persistent bias** but not **scheduled events**.

**Recommendation:**
```
PRIORITY: LOW
EFFORT: LOW (2-3 engineering days)

Implementation approach:
1. Add CounterflowEvent to config:
   struct CounterflowEvent {
       trigger: TickNumber(usize) | DayOfMonth(i8) | Weekly(u8),
       sender: String,
       receiver_distribution: HashMap<String, f64>,
       amount_distribution: AmountDistribution,
   }
2. In orchestrator tick loop (step 1: arrivals):
   - Check if current tick/day matches any counterflow trigger
   - If yes, inject transactions according to spec
3. Add to OrchestratorConfig:
   pub counterflows: Vec<CounterflowEvent>
```

**Code Locations:**
- `backend/src/arrivals/mod.rs` - add counterflow injection
- `backend/src/orchestrator/engine.rs:90` (OrchestratorConfig) - add field

---

### Module F: Throughput Nudges (Soft Deadlines) ⚠️

**What Real Systems Do:**
RTGS operators enforce **intraday throughput targets** to prevent end-of-day gridlock:
- **CHAPS (UK):** ≥50% value by 12:00, ≥75% by 14:30, "Star Chamber" review if habitually miss
- **TARGET2 (EU):** Monitoring of back-loading behavior
- **Penalties:** Reputational (published in reports), operational (liquidity buffer requirements)

**What SimCash Does:**
Strong **end-of-day penalty**:
```rust
// backend/src/orchestrator/engine.rs:233-234
/// End-of-day penalty for each unsettled transaction (cents)
pub eod_penalty_per_transaction: i64,  // Default: 10,000 cents ($100)
```

Plus **EOD rush period signal** (Phase 9.5.2):
```rust
// backend/src/orchestrator/engine.rs:84-111
/// Fraction of day (0.0 to 1.0) when EOD rush period begins.
/// Default: 0.8 (last 20% of day)
pub eod_rush_threshold: f64,
```

Policies can check `is_eod_rush` to change behavior:
```rust
// Example policy evaluation context
if context.is_eod_rush {
    // Submit more aggressively
}
```

**What's Missing:**
No **intermediate checkpoints** with graduated penalties:
- No 50% by noon target
- No 75% by mid-afternoon target
- No tracking of habitual back-loading

**Current Capability:**
You can **approximate** throughput nudges via:
1. Custom policy that checks `tick / ticks_per_day`
2. Increase submission aggressiveness after 0.5, 0.75 thresholds
3. Add voluntary "throughput cost" based on cumulative unsettled value

But there's no **system-level enforcement** or **reputational penalty** tracked in metrics.

**Recommendation:**
```
PRIORITY: LOW
EFFORT: LOW (2-3 engineering days)

Implementation approach:
1. Add to CostRates:
   pub throughput_checkpoints: Vec<(f64, i64)>  // (day_fraction, penalty_per_tx)
   // Example: [(0.5, 100), (0.75, 500)]  // $1 at noon, $5 at 14:30
2. In orchestrator tick loop (step 6: costs):
   - Check if current_tick crosses a checkpoint
   - For each agent, count unsettled transactions at checkpoint
   - Apply penalty: num_unsettled * checkpoint_penalty
3. Track in metrics:
   - throughput_violations: Vec<(checkpoint, num_violations)>
```

**Code Locations:**
- `backend/src/orchestrator/engine.rs:220` (CostRates) - add checkpoints field
- `backend/src/orchestrator/engine.rs:tick()` - add checkpoint checking

**Alternative (even lighter):**
Add a **reputational cost** to metrics without direct penalty:
```rust
pub struct AgentDayMetrics {
    // ...
    pub throughput_50_pct_tick: Option<usize>,  // Tick when 50% settled
    pub throughput_75_pct_tick: Option<usize>,
    pub backload_score: f64,  // 0.0 (good) to 1.0 (all at EOD)
}
```

Policies could then use `backload_score` in multi-day scenarios to avoid reputational damage.

---

### Module G: LCR-Style Regulatory Guardrails ❌

**What Real Systems Do:**
Basel III **Liquidity Coverage Ratio (LCR)** requires:
```
HQLA (High-Quality Liquid Assets)
─────────────────────────────────── ≥ 100%
30-day Net Cash Outflows
```

This prevents banks from **chronically** relying on central bank credit to cover structural deficits.

**What SimCash Does:**
**Nothing** prevents an agent from:
- Starting with low `opening_balance` and high `credit_limit`
- Perpetually using credit every day
- Never adjusting funding to match structural outflows

Example exploitable config:
```yaml
agents:
  SMALLBANK:
    opening_balance: 100_000      # $1k
    credit_limit: 10_000_000      # $100k (100x balance!)
    arrival_config:
      rate_per_tick: 1.0          # Sending lots
      counterparty_weights:
        BIGBANK: 1.0              # All outflows
```

This agent would use credit **every tick** indefinitely. In reality, regulators would force them to raise capital or reduce activity.

**Current Pressure:**
Overdraft costs create **economic** pressure:
```rust
// backend/tests/test_cost_accrual.rs:79-83
// Tick 0: -200k * 0.001 = 200 cents overdraft cost
// Tick 1: -200k * 0.001 = 200 cents overdraft cost
// Total = 400 cents = $4
```

But with policy optimization, an agent might find that **chronic credit use** is optimal if arrival-driven revenue exceeds overdraft cost.

**Recommendation:**
```
PRIORITY: LOW (future enhancement for multi-day scenarios)
EFFORT: MODERATE (4-5 engineering days)

Implementation approach:
1. Track 30-tick rolling net outflows per agent:
   - rolling_outflows: VecDeque<i64>  // Last 30 ticks of (sent - received)
   - sum to get expected_30tick_deficit
2. Define HQLA proxy:
   - hqla = balance + posted_collateral (liquid, unencumbered)
3. Compute LCR:
   - lcr = hqla / max(1, expected_30tick_deficit)
4. Add step-cost if LCR < 1.0 for N consecutive ticks:
   - regulatory_penalty: 10,000 cents per day if LCR < 100% for >5 days
5. Track in metrics:
   - lcr: f64
   - days_below_lcr: usize
```

**Code Locations:**
- `backend/src/models/agent.rs` - add rolling window tracking
- `backend/src/orchestrator/engine.rs:end_of_day()` - check LCR, apply penalty
- `backend/src/orchestrator/engine.rs:220` (CostRates) - add `regulatory_penalty`

**Note:**
Only relevant for **multi-day simulations** where structural patterns emerge. For single-day, EOD penalties are sufficient.

---

## SimCash Strengths (What's Already Good)

Despite the gaps above, SimCash has **strong foundational features** that many simulators lack:

### ✅ 1. Sophisticated LSM Implementation
```rust
// backend/src/settlement/lsm.rs:193
pub fn bilateral_offset(state: &mut SimulationState, tick: usize) -> BilateralOffsetResult
```
- **Bilateral offsetting:** Nets A↔B flows, settles in one direction
- **Cycle detection:** Finds A→B→C→A cycles up to configurable length
- **Event tracking:** Emits `LsmCycleEvent` for every optimization

**This is rare.** Most RTGS simulators treat LSM as a black box. SimCash models it mechanistically.

### ✅ 2. Two-Queue Architecture
```rust
// Queue 1: Agent-level policy decisions
outgoing_queue: Vec<String>,  // backend/src/models/agent.rs:81

// Queue 2: RTGS central retry queue
rtgs_queue: Vec<String>,      // backend/src/models/state.rs
```
Clear separation between:
- **Strategic holds** (Queue 1, delay costs apply)
- **Liquidity waits** (Queue 2, no delay costs)

This models real **cash manager discretion** vs. **mechanical settlement constraints**.

### ✅ 3. Rich Cost Model (5 Components)
```rust
// backend/src/orchestrator/engine.rs:220-240
pub struct CostRates {
    pub overdraft_bps_per_tick: f64,
    pub delay_cost_per_tick_per_cent: f64,
    pub collateral_cost_per_tick_bps: f64,
    pub eod_penalty_per_transaction: i64,
    pub deadline_penalty: i64,
    pub split_friction_cost: i64,
}
```
Captures:
- Intraday liquidity costs (credit usage)
- Delay costs (time value of unsettled obligations)
- Collateral opportunity costs
- Deadline and EOD penalties
- Transaction splitting friction

### ✅ 4. Extensible Policy System
```rust
// backend/src/policy/ (4,880+ lines)
pub trait CashManagerPolicy {
    fn evaluate(&self, context: &PolicyContext) -> Vec<ReleaseDecision>;
}
```
- Built-in policies: FIFO, Deadline, LiquidityAware, Splitting
- JSON DSL for custom decision trees (Phase 9)
- Context includes: balance, queue, deadlines, EOD signal

### ✅ 5. Deterministic Simulation
```rust
// backend/src/rng/mod.rs
pub struct RngManager {
    // xorshift64* PRNG, fully deterministic
}
```
Same seed → same arrivals → same outcomes. Critical for:
- Debugging policy behavior
- Monte Carlo analysis
- Reproducible research

### ✅ 6. Transaction Splitting
```rust
// backend/src/policy/ (Phase 5)
SubmitPartial { num_splits: usize }
```
Agents can voluntarily split large payments to:
- Pace liquidity usage
- Reduce queue congestion
- Meet partial urgent deadlines

Incurs `split_friction_cost` to prevent overuse.

---

## Impact Analysis: How Gaps Affect Smaller Banks

### Current Simulation Dynamics

**Scenario:** SmallBank (retail-heavy, structural payer) vs. BigBank (corporate-heavy, structural receiver)

**What happens in SimCash:**
1. SmallBank generates Poisson(λ=1.0) arrivals per tick to BigBank
2. Every arrival is an **individual RTGS payment**
3. SmallBank's balance drains as payments settle
4. SmallBank goes into overdraft (uses `credit_limit`)
5. Overdraft costs accrue per tick: `-balance * overdraft_bps_per_tick`
6. Policy may hold some payments (Queue 1) to preserve buffer
7. EOD penalty forces settlement of remaining queue

**Problems:**
- **Overstated RTGS exposure:** Real SmallBank would net via ancillary rails
- **No funding relief:** Cannot pre-borrow reserves before day starts
- **No correspondent option:** Must participate directly despite size
- **Persistent credit use:** No penalty for structural (multi-day) overdraft

**Net Effect:**
SimCash makes smaller banks look **more liquidity-constrained** than they are in reality, because it models worst-case RTGS-only gross settlement.

### Real-World Dynamics (With All Modules)

**Same scenario with recommendations implemented:**

1. **Ancillary netting (Module A):**
   - 90% of SmallBank's retail volume nets via ACH
   - Only €5M net (not €50M gross) hits RTGS at 13:00

2. **Funding desk (Module C):**
   - SmallBank borrows €10M repo at open (cheap rate)
   - Increases buffer to avoid overdraft
   - Repays from incoming flows during day

3. **Scheduled counterflows (Module E):**
   - Monthly payroll: BigBank → SmallBank €20M
   - Recycles liquidity, reduces structural deficit

4. **Tiering (Module D):**
   - SmallBank settles indirectly via MidBank
   - MidBank absorbs intraday timing mismatches
   - SmallBank pays fee but reduces RTGS liquidity needs

**Net Effect:**
SmallBank uses **less intraday credit**, **lower costs**, and **more realistic settlement patterns**.

---

## Recommendations Summary

### Priority 1: Critical Gaps (Implement First)

| Module | What to Build | Estimated Effort | Expected Impact |
|--------|---------------|------------------|-----------------|
| **A - Ancillary Netting** | Add ACH/DNS rails with scheduled net settlement windows | 4-6 days | **HIGH** - Reduces gross RTGS exposure by 70-90% for retail banks |
| **B - EOD Rollover** | Split credit into intraday (free) and overnight (penalty rate); auto-roll negative balances | 3-4 days | **MEDIUM** - More realistic multi-day dynamics |

**Combined effort:** ~2 engineering weeks
**Impact:** Moves from "stylized RTGS-only" to "realistic multi-rail system"

### Priority 2: Important Enhancements

| Module | What to Build | Estimated Effort | Expected Impact |
|--------|---------------|------------------|-----------------|
| **C - Funding Desk** | Add pre-opening funding decisions (repo, collateral posting) | 6-8 days | **MEDIUM** - Models active liquidity management |
| **F - Throughput Nudges** | Add interim checkpoints (50%/75% by tick) with graduated penalties | 2-3 days | **LOW-MEDIUM** - Encourages intraday settlement |

**Combined effort:** ~2 engineering weeks
**Impact:** Banks become active participants, not passive cost-minimizers

### Priority 3: Future Extensions

| Module | What to Build | Estimated Effort | Expected Impact |
|--------|---------------|------------------|-----------------|
| **D - Tiering** | Correspondent banking with bilateral accounts and indirect settlement | 8-10 days | **MEDIUM** - Models realistic small bank participation |
| **E - Counterflows** | Scheduled calendar events (payroll, pensions) | 2-3 days | **LOW-MEDIUM** - Adds realism to flow dynamics |
| **G - LCR Guardrail** | 30-day rolling outflows vs. HQLA check with penalties | 4-5 days | **LOW** - Only matters for multi-day scenarios |

**Combined effort:** ~3 engineering weeks
**Impact:** Comprehensive model suitable for regulatory stress testing

---

## Implementation Roadmap

### Phase 1: Minimal Viable Realism (2 weeks)
**Goal:** Fix most glaring gap (ancillary netting) + improve credit model

**Tasks:**
1. ✅ Module A (Ancillary Netting):
   - Create `AncillaryRail` struct with settlement windows
   - Route retail/commercial traffic to ACH rail
   - Inject nets at scheduled ticks
   - Add rail config to YAML schemas

2. ✅ Module B (EOD Rollover):
   - Split CostRates into intraday/overnight
   - Add rollover logic in `end_of_day()`
   - Track overnight borrowing in agent state
   - Update cost accrual tests

**Deliverable:** Config like:
```yaml
ancillary_rails:
  - type: ACH
    windows: [30, 60, 90]  # Ticks for net settlement
cost_rates:
  intraday_overdraft_bps: 0.0
  overnight_overdraft_bps: 0.01  # 1 bp per tick = ~10% annualized
```

### Phase 2: Active Liquidity Management (2 weeks)
**Goal:** Add funding desk decisions

**Tasks:**
1. ✅ Module C (Funding Desk):
   - Create `FundingPolicy` trait
   - Add pre-opening funding step to tick loop
   - Implement basic policies:
     - `TargetBufferFunding`: Borrow to reach target
     - `CollateralOptimization`: Minimize collateral costs
   - Add funding costs to metrics

2. ✅ Module F (Throughput):
   - Add checkpoint penalties to CostRates
   - Implement checkpoint checking in tick loop
   - Track violations in metrics

**Deliverable:** Agents can execute:
```rust
FundingDecision::BorrowRepo {
    amount: 5_000_000,
    rate: 0.0005,  // 5 bps
    maturity: current_tick + 100
}
```

### Phase 3: Structural Extensions (3 weeks)
**Goal:** Tiering, counterflows, regulatory constraints

**Tasks:**
1. ✅ Module D (Tiering):
   - Add `tier` field to AgentConfig
   - Implement correspondent routing
   - Track bilateral positions
   - Add correspondent fees

2. ✅ Module E (Counterflows):
   - Create `CounterflowEvent` config
   - Add calendar-based injection
   - Test with payroll/pension scenarios

3. ✅ Module G (LCR):
   - Add 30-tick rolling window tracking
   - Implement LCR calculation
   - Add regulatory penalty for chronic violations

**Deliverable:** Full-featured multi-rail, multi-day simulator suitable for:
- Central bank policy analysis
- Liquidity stress testing
- Correspondent banking research

---

## Configuration Examples

### Current SimCash Config (Stylized)
```yaml
# sim_config_simple_example.yaml
agents:
  SMALLBANK:
    opening_balance: 1_000_000
    credit_limit: 500_000
    policy:
      type: LiquidityAware
      target_buffer: 500_000
    arrival_config:
      rate_per_tick: 0.5
      amount_distribution:
        type: LogNormal
        mean: 50_000
        std_dev: 20_000
      counterparty_weights:
        BIGBANK: 1.0

cost_rates:
  overdraft_bps_per_tick: 0.001  # 1 bp per tick
  delay_cost_per_tick_per_cent: 0.0001
```

### Recommended Config (Realistic)
```yaml
# sim_config_realistic_small_bank.yaml
ancillary_rails:  # ← NEW (Module A)
  - id: ACH
    type: netting
    windows: [30, 60, 90]  # 3x per day net settlements
    applicable_to: [SMALLBANK]  # Retail bank uses ACH

agents:
  SMALLBANK:
    opening_balance: 1_000_000
    credit_limit_intraday: 500_000  # ← SPLIT (Module B)
    credit_limit_overnight: 100_000
    funding_policy:  # ← NEW (Module C)
      type: TargetBuffer
      target_reserves: 2_000_000
      repo_access: true
      max_repo: 5_000_000
    policy:
      type: LiquidityAware
      target_buffer: 500_000
    arrival_config:
      rate_per_tick: 0.5
      rail: ACH  # ← Route to ancillary rail
      amount_distribution:
        type: LogNormal
        mean: 50_000
        std_dev: 20_000

  BIGBANK:
    tier: Direct  # ← NEW (Module D)
    # ... similar config

counterflows:  # ← NEW (Module E)
  - trigger: DayOfMonth(-1)  # Last business day
    type: payroll
    sender: BIGBANK
    receiver_distribution:
      SMALLBANK: 10_000_000  # $100k payroll

cost_rates:
  intraday_overdraft_bps: 0.0      # ← FREE (Module B)
  overnight_overdraft_bps: 0.01    # ← PENALTY
  throughput_checkpoints:          # ← NEW (Module F)
    - [0.5, 100]   # $1 per unsettled tx at noon
    - [0.75, 500]  # $5 per unsettled tx at 14:30
  lcr_penalty_per_day: 10_000      # ← NEW (Module G)
```

---

## Testing Strategy

### Unit Tests (Per Module)
```rust
// backend/tests/test_ancillary_netting.rs
#[test]
fn test_ach_net_settlement_window() {
    // 1. Generate 100 SmallBank → BigBank retail payments
    // 2. Generate 90 BigBank → SmallBank retail payments
    // 3. Reach settlement window tick
    // 4. Assert: Only net 10 payments (SmallBank → BigBank) in RTGS queue
    // 5. Assert: 190 payments marked as ancillary-settled
}

// backend/tests/test_eod_rollover.rs
#[test]
fn test_overnight_borrowing_auto_rollover() {
    // 1. Put agent into -100k balance via large payment
    // 2. Advance to EOD
    // 3. Assert: overnight_loan = 100k, intraday credit = 0
    // 4. Advance to next day start
    // 5. Assert: cost accrued at overnight_rate, not intraday_rate
}
```

### Integration Tests
```python
# api/tests/integration/test_realistic_small_bank.py
def test_small_bank_with_ancillary_rail():
    """Small bank using ACH should have lower RTGS exposure than direct RTGS."""
    config_direct_rtgs = load_config("small_bank_rtgs_only.yaml")
    config_with_ach = load_config("small_bank_with_ach.yaml")

    orch1 = Orchestrator.new(config_direct_rtgs)
    orch2 = Orchestrator.new(config_with_ach)

    for _ in range(100):  # Run full day
        orch1.tick()
        orch2.tick()

    metrics1 = orch1.get_agent_day_metrics("SMALLBANK", day=0)
    metrics2 = orch2.get_agent_day_metrics("SMALLBANK", day=0)

    # With ACH, peak overdraft should be much lower
    assert metrics2.peak_overdraft < metrics1.peak_overdraft * 0.3
    # And total costs lower
    assert metrics2.total_cost < metrics1.total_cost * 0.5
```

### Validation Against Real Data
If you have access to **anonymized RTGS data** (e.g., from central bank research):

```python
def test_settlement_patterns_match_real_data():
    """Compare SimCash output to real-world settlement timing distributions."""
    real_data = load_csv("riksbank_settlement_times_anonymized.csv")

    config = create_calibrated_config(real_data)
    orch = Orchestrator.new(config)

    # Run 100 simulated days
    sim_settlement_times = []
    for day in range(100):
        for tick in range(100):
            result = orch.tick()
            sim_settlement_times.extend(extract_settlement_times(result))

    # Compare distributions (KS test, chi-squared, etc.)
    assert kolmogorov_smirnov_test(real_data.settlement_times, sim_settlement_times) > 0.05
```

---

## Conclusion

**SimCash is a strong foundation** with sophisticated settlement mechanics, cost modeling, and policy infrastructure. However, it currently models a **stylized RTGS-only world** that overstates liquidity pressures on smaller banks.

**To model smaller banks realistically**, implement:

1. **Priority 1 (2 weeks):**
   - Module A: Ancillary netting (ACH/DNS rails)
   - Module B: EOD rollover (overnight credit penalty)

2. **Priority 2 (2 weeks):**
   - Module C: Funding desk (active reserve management)
   - Module F: Throughput nudges (interim checkpoints)

3. **Priority 3 (3 weeks):**
   - Module D: Tiering (correspondent banking)
   - Module E: Counterflows (scheduled events)
   - Module G: LCR guardrails (regulatory constraints)

**Expected Outcome:**
After Priority 1+2 (4 weeks total), SimCash will move from "research toy" to "policy-grade simulator" comparable to models used by ECB, Riksbank, and Bank of England for liquidity analysis.

---

## References

**European Central Bank (ECB):**
- TARGET2 Liquidity Management ([source][1])
- Standing Facilities Overview ([source][3])
- Tiered Participation Monitoring ([source][4])

**Riksbank (Sweden):**
- RIX-RTGS Instructions ([source][2])
- Settlement Account and Loan Account mechanics

**Bank of England:**
- CHAPS Throughput Guidelines ([source][5], [source][7])
- Star Chamber enforcement procedures

**Bank for International Settlements (BIS):**
- Basel III LCR Requirements ([source][6])

---

**Document Control:**
Author: Claude Code Assessment Agent
Reviewed: Pending
Next Review: After Priority 1 implementation
Version History: 1.0 (Initial), TBD (Post-implementation update)

[1]: https://www.ecb.europa.eu
[2]: https://www.riksbank.se
[3]: https://www.ecb.europa.eu
[4]: https://www.ecb.europa.eu
[5]: https://www.bankofengland.co.uk
[6]: https://www.bis.org
[7]: https://www.bankofengland.co.uk
[8]: https://www.bankgirot.se
