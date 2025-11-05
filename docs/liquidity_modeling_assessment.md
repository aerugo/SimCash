# SimCash Liquidity Modeling Assessment for Smaller Banks
## Comprehensive Gap Analysis and Recommendations

**Date:** 2025-11-04
**Version:** 2.0
**Status:** Revised Assessment

---

## Executive Summary

This report evaluates how well the SimCash payment system simulator models liquidity considerations for smaller banks. We assess the codebase against a framework derived from European payment system practices and provide recommendations for a lean, high-impact approach to improving realism.

**Key Finding:** SimCash has a **robust foundation** for RTGS simulation. The core challenge is that its pure RTGS model, with gross flows, can overstate the liquidity pressures on smaller banks, leading to a "small banks bleed reserves forever" pathology. The original assessment proposed detailed microstructure simulation to fix this. This revised plan adopts a **leaner, RTGS-centric approach**, focusing on modeling the **net effects** of upstream systems at the RTGS boundary—precisely where a bank's cash manager operates.

**Priority Gaps & Lean Solutions:**
1.  ❌ **No ancillary system netting:** Solved by injecting **exogenous net settlement flows** at scheduled windows instead of simulating retail rails.
2.  ⚠️ **Incomplete credit lifecycle:** Solved by implementing **automatic EOD rollover** of intraday credit to a priced overnight loan.
3.  ❌ **No active funding:** Solved by adding a **minimal pre-open funding stage** where agents borrow to meet a target reserve, rather than a complex intraday desk.
4.  ❌ **No tiered participation:** Modeled as a **simple parameter** (a "knob") affecting credit headroom and costs, not a complex new system.

This revised strategy delivers maximum realism for cash management decisions with minimum new complexity, keeping the simulation focused on its core RTGS strengths.

---

## Assessment Framework

We evaluate SimCash against **seven modules** recommended for realistic modeling of smaller bank liquidity, updated with lean, RTGS-centric recommendations.

| Module | Description | Real-World Practice | SimCash Status & Lean Recommendation |
| :--- | :--- | :--- | :--- |
| **A** | Ancillary system netting | EURO1/STEP2 → TARGET2 | ❌ **Rec:** Inject scheduled **exogenous net flows**; avoid simulating upstream rails. |
| **B** | Intraday credit + EOD rollover | ECB/Riksbank collateralized ICL, auto-roll to MLF | ⚠️ **Rec:** Implement **automatic EOD rollover** to a priced overnight facility. |
| **C** | Daily funding desk | Repo, unsecured, standing facilities | ❌ **Rec:** Add a **minimal pre-open funding stage** for agents to hit a target buffer. |
| **D** | Tiering (correspondent banking) | TARGET2 tiered participation | ❌ **Rec:** Model as a **simple "knob"** (multiplier on headroom + fee), not a new system. |
| **E** | Scheduled counterflows | Payroll, pensions, gov disbursements | ⚠️ **Rec:** Integrate into **Module A** as calendar-based shocks in the net flow calculation. |
| **F** | Throughput nudges | CHAPS 50%/75% targets | ⚠️ **Rec:** Keep as a **soft reputational cost** in metrics; no new mechanics needed. |
| **G** | LCR-style guardrail | Basel III HQLA/net outflows ≥ 100% | ❌ **Rec:** De-prioritize; EOD rollover (Module B) provides a more direct economic penalty. |

**Legend:**
✅ Fully Implemented | ⚠️ Partial/Foundational | ❌ Not Implemented

---

## Module-by-Module Analysis (Revised Lean Approach)

### Module A: Ancillary System Netting (Lean Approach) ❌

**The Problem:** SimCash treats every payment as a gross RTGS transaction. In reality, retail/commercial flows are netted in ancillary systems, and only the final net position hits RTGS. This makes SimCash's small banks look far more liquidity-constrained than they really are.

**Lean Solution: Exogenous Net-Settlement Flow**
Instead of building a detailed ancillary rail simulator, we treat its output as an exogenous input to the RTGS system.

**Recommendation:**
```
PRIORITY: HIGH
EFFORT: LOW (2-3 engineering days)

Implementation approach:
1.  **Introduce a `NetFlow` object:** This represents the compressed result of upstream rails. It's a single scheduled net debit or credit.
    - `NetFlow_i,t = μ_i + σ_i * ε_t + calendar_shock_t`
    - `μ_i` represents a bank's structural drift (payer/receiver). The sum across all banks must be zero.
    - `σ_i` adds daily variance.
    - `calendar_shock_t` models events like payroll or tax days.
2.  **Add `net_flow_schedule` to config:** Define 1-3 settlement windows per day (e.g., `[30, 60, 90]`).
3.  **Modify orchestrator tick loop:** At a scheduled window, inject the `NetFlow` for each agent as a single, normal-priority RTGS payment (positive or negative amount).

**Impact:** This perfectly captures the signal a real cash manager sees—a scheduled net debit/credit they must plan for—without adding complex, out-of-scope simulation logic.
```

**Code Locations:**
*   `backend/src/arrivals/mod.rs`: Add a function to inject `NetFlow` transactions.
*   `backend/src/orchestrator/engine.rs:tick()`: Add a check for `t in ancillary_windows` to trigger the injection.
*   `backend/src/orchestrator/engine.rs` (Config): Add `net_flow_schedule` to `OrchestratorConfig`.

---

### Module B: Intraday Credit + EOD Rollover ⚠️

**The Problem:** SimCash has intraday credit and charges an overdraft cost per tick. However, it doesn't distinguish between free intraday credit and costly overnight borrowing. A negative balance at EOD just persists indefinitely as an "intraday" overdraft.

**Lean Solution: EOD Rollover to Penalty Rate**
Implement the real-world mechanic where EOD overdrafts are automatically converted to overnight loans at a penalty rate.

**Recommendation:**
```
PRIORITY: HIGH
EFFORT: LOW (2-3 engineering days)

Implementation approach:
1.  **Update `CostRates`:**
    - `intraday_overdraft_bps_per_tick`: Set to **0.0** (collateralized intraday credit is free).
    - `overnight_overdraft_bps_per_tick`: Set to a high penalty rate (e.g., policy rate + 100bps).
2.  **Modify `end_of_day()` in orchestrator:**
    - If `agent.balance < 0`:
        - Create an `OvernightLoan` record for the agent.
        - Accrue cost for this loan at the `overnight_overdraft_bps_per_tick` rate.
        - Reset the agent's opening balance for the next day to **0** (or to their pre-funded amount from Module C).
3.  **Update `agent.rs`:** Add a field to track `overnight_loan_amount`.
```

**Impact:** Creates a strong economic incentive for banks to be flat by EOD. This correctly models the primary daily liquidity management goal and forces a realistic funding cycle.

**Code Locations:**
*   `backend/src/models/agent.rs`: Add `overnight_loan_amount: i64`.
*   `backend/src/orchestrator/engine.rs:end_of_day()`: Implement the rollover logic.
*   `backend/src/orchestrator/engine.rs` (CostRates): Adjust rate structure.

---

### Module C: Daily Funding Desk (Lean Approach) ❌

**The Problem:** SimCash agents are passive. They cannot actively manage their reserves by borrowing or adjusting collateral. A real bank would pre-fund its account if it expected a day of net outflows.

**Lean Solution: Minimal Pre-Open Funding Stage**
Give agents a single, simple funding decision at the start of each day.

**Recommendation:**```
PRIORITY: MEDIUM
EFFORT: MODERATE (3-4 engineering days)

Implementation approach:
1.  **Add a `funding_policy` to `AgentConfig`:**
    - `type: TargetBuffer`
    - `target_reserves: i64` (The balance the agent wants to start the day with).
2.  **Add a pre-open funding stage to the orchestrator:**
    - Before tick 0 of each day, loop through agents.
    - Calculate `needed = target_reserves - agent.balance`.
    - If `needed > 0`, simulate borrowing (e.g., repo) by simply increasing the agent's balance by `needed`.
    - Accrue a simple funding cost (`needed * repo_rate`).
3.  **Optional:** Allow agents to adjust posted collateral in this stage to change their intraday headroom (`H_i`).
```

**Impact:** Empowers agents to act on expectations, preventing structural payers from immediately defaulting to costly overdrafts. This is the key tool for managing the `NetFlow` debits from Module A.

**Code Locations:**
*   New module/logic in `backend/src/funding/`.
*   `backend/src/orchestrator/engine.rs`: Add the pre-open funding step before the tick loop for each day.
*   `backend/src/models/agent.rs`: Add fields for funding state if needed.

---

### Other Modules (Lean Summary)

*   **Module D (Tiering):** Instead of a full correspondent banking system, model it as a "knob." Add an optional `tiering_multiplier: f64` and `correspondent_fee_bps: f64` to `AgentConfig`. The multiplier increases effective headroom, and the fee adds a small cost to every settled transaction.
*   **Module F (Throughput):** The current approach is sufficient. Keep it as a soft, reputational cost tracked in agent metrics (e.g., `backload_score`) that advanced policies can use as an input. No new mechanics are needed.

---

## SimCash Strengths (What's Already Good)

Despite the gaps above, SimCash has **strong foundational features** that many simulators lack:

✅ **1. Sophisticated LSM Implementation:** Mechanistic bilateral and cycle detection is a core strength.
✅ **2. Two-Queue Architecture:** The separation of strategic holds (Queue 1) from liquidity waits (Queue 2) correctly models cash manager discretion.
✅ **3. Rich Cost Model:** The 5-component cost model is an excellent base for economic optimization.
✅ **4. Extensible Policy System:** The JSON DSL is powerful and safe for experimentation.
✅ **5. Deterministic Simulation:** Crucial for reproducible research.
✅ **6. Transaction Splitting:** A valuable, realistic tool for liquidity management.

---

## Revised Implementation Roadmap

### Phase 1: The Core Fix (2 Weeks)
**Goal:** Implement the two most critical features to solve the "small bank bleed" problem and create a realistic daily cycle.

**Tasks:**
1.  ✅ **Module A (NetFlow):**
    *   Introduce `NetFlow` config with scheduled windows.
    *   Modify orchestrator to inject a single net payment at specified ticks.
2.  ✅ **Module B & C (EOD Rollover & Funding):**
    *   Implement automatic EOD rollover to an overnight loan at a penalty rate.
    *   Add a simple pre-open funding stage where agents borrow to meet a `target_reserves` buffer.

**Deliverable:** A simulator where banks face realistic net shocks and have the basic tools (funding, credit) to manage them in a daily cycle.

### Phase 2: Polish & Refinement (1 Week)
**Goal:** Add secondary realism factors.

**Tasks:**
1.  ✅ **Module D (Tiering Knob):** Implement tiering as a simple multiplier on headroom and a fee.
2.  ✅ **Module F (Throughput Metrics):** Enhance `DailyMetrics` to include a `backload_score` without adding hard penalties.

**Deliverable:** A more nuanced model where not all banks are equal, and policy performance can be judged on throughput efficiency.

---

## Conclusion

**SimCash is a strong foundation.** By adopting a leaner, RTGS-centric approach, we can achieve high-fidelity modeling of cash manager decisions with minimal complexity. The original assessment was correct in its diagnosis but overly complex in its prescription.

This revised plan, centered on **exogenous net flows** and a **realistic credit/funding cycle**, will efficiently transform SimCash into a policy-grade simulator suitable for analyzing real-world liquidity dynamics for banks of all sizes.