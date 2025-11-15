# Breaking Replay Identity Issues - Critical Bug Report

**Date:** 2025-11-15
**Severity:** CRITICAL
**Status:** Under investigation

## Executive Summary

The replay identity guarantee is **fundamentally broken**. Running `payment-sim replay` produces drastically different output compared to `payment-sim run` for the same simulation data, violating the core invariant that replay output must be byte-for-byte identical (modulo timing).

This document catalogs every discrepancy found between run and replay outputs for tick 299 of simulation `sim-2f2d8de4`.

## Critical Architecture Violation

The CLAUDE.md states:

> **RULE**: `payment-sim replay` output MUST be byte-for-byte identical to `payment-sim run` output (modulo timing information).

This is **completely violated**. The discrepancies are not minor formatting issues—they represent fundamental reconstruction failures.

---

## Detailed Discrepancy Catalog

### 1. Transaction Settlement Counts

#### 1.1 Per-Tick Settlement Header
- **Run:** `✅ 15 transaction(s) settled:`
- **Replay:** `✅ 8 transaction(s) settled:`
- **Discrepancy:** Different counts (15 vs 8)

#### 1.2 Tick Summary Line
- **Run:** `Summary: 6 in | 10 settled | 3 LSM | 79 queued`
- **Replay:** `Summary: 6 in | 15 settled | 1 LSM | 79 queued`
- **Discrepancy:**
  - `settled`: 10 vs 15
  - `LSM`: 3 vs 1
  - **Internal inconsistency:** Run header says 15 settled but summary says 10
  - **Internal inconsistency:** Replay header says 8 settled but summary says 15

### 2. RTGS Queue Status

#### 2.1 Queued Transactions Display
- **Run:** Shows block:
  ```
  📋 1 transaction(s) queued in RTGS:
     • TX 485d8a80: CORRESPONDENT_HUB | Insufficient balance
  ```
- **Replay:** **No "queued in RTGS" block at all**
- **Discrepancy:** Entire section missing in replay

### 3. Overdue Transaction Handling

#### 3.1 "Transaction Went Overdue" Events
- **Run:** Shows explicit overdue events:
  ```
  ❌ Transaction Went Overdue: TX 098e8f44...
     CORRESPONDENT_HUB → REGIONAL_TRUST | $1,702.23
     Deadline: Tick 298 | Current: Tick 299 | 1 tick late
     💸 Deadline Penalty Charged: $2,500.00

  ❌ Transaction Went Overdue: TX 00003d11...
     REGIONAL_TRUST → METRO_CENTRAL | $3,820.25
     Deadline: Tick 298 | Current: Tick 299 | 1 tick late
     💸 Deadline Penalty Charged: $2,500.00
  ```
- **Replay:** **No "Transaction Went Overdue" messages at all**
- **Discrepancy:** Entire event type missing in replay

#### 3.2 Overdue Transaction List - TX 486c46c0
- **Run:**
  - Overdue: **58 ticks**
  - Delay cost: **$231.78**
  - Total: **$2,731.78**
- **Replay:**
  - Overdue: **57 ticks**
  - Delay cost: **$14,250.00**
  - Total: **$16,750.00**
- **Discrepancy:** Different overdue tick counts and drastically different delay costs

#### 3.3 Overdue Transaction List - TX 00003d11
- **Run:** In "Transaction Went Overdue" block: **1 tick late** with $2,500 penalty; not visible in "Overdue Transactions" snippet
- **Replay:** In "Overdue Transactions" list as **Overdue: 0 ticks**, penalty $2,500, delay $0
- **Discrepancy:** Different status (1 tick late vs 0 ticks overdue)

#### 3.4 Overdue Transaction List - TX 098e8f44
- **Run:** Explicitly both "went overdue" and listed in "Overdue Transactions"
- **Replay:** Not visible in overdue snippet at all
- **Discrepancy:** Transaction missing from replay output

#### 3.5 Total Overdue Cost
- **Run:** `Total Overdue Cost: $77,363.66`
- **Replay:** `Total Overdue Cost: $221,500.00`
- **Discrepancy:** Difference of $144,136.34 (187% higher in replay)

### 4. Cost Accruals

#### 4.1 "Costs Accrued This Tick" Summary Block
- **Run:** Shows block:
  ```
  💰 Costs Accrued This Tick: $5,863.10

     CORRESPONDENT_HUB: $3,133.47
     • Liquidity: $265.00
     • Delay: $2,868.47

     REGIONAL_TRUST: $2,729.63
     • Liquidity: $276.95
     • Delay: $2,452.68
  ```
- **Replay:** **Block missing entirely**
- **Discrepancy:** Entire summary section missing

### 5. End-of-Day State

#### 5.1 End-of-Day Banner
- **Run:** `🌙 End of Day 2 - 110 unsettled, $395,000.00 in penalties`
- **Replay:** `🌙 End of Day 2 - 0 unsettled, $0.00 in penalties`
- **Discrepancy:**
  - Unsettled: 110 vs 0
  - Penalties: $395,000 vs $0

#### 5.2 System-Wide Metrics (Day 2 Summary)
- **Run:**
  - Total Transactions: **278**
  - Settled: **194 (69.8%)**
  - Unsettled: **84 (30.2%)**
  - LSM Settled: **13 (6.7% of settlements)**
  - Settlement Rate: **69.8%**
- **Replay:**
  - Total Transactions: **6**
  - Settled: **15 (250.0%)**
  - Unsettled: **-9 (-150.0%)**
  - LSM Settled: **1 (6.7% of settlements)**
  - Settlement Rate: **250.0%**
- **Discrepancy:**
  - All metrics completely different
  - Replay shows **nonsensical values** (250% settlement rate, -9 unsettled transactions)
  - Only LSM percentage (6.7%) matches

#### 5.3 Total Costs
- **Run:** `💰 COSTS: • Total: $508,363.10`
- **Replay:** `💰 COSTS: • Total: $508,363.10`
- **Note:** This line matches, but contradicts JSON costs below

### 6. Agent-Level Metrics

#### 6.1 CORRESPONDENT_HUB
- **Run:**
  - Queue 2: **16 transactions**
- **Replay:**
  - Queue 2: **0 transactions**
- **Discrepancy:** Queue 2 discrepancy (16 vs 0)
- **Note:** Final balance, Queue 1, Credit Utilization, and Total Costs match

#### 6.2 REGIONAL_TRUST
- **Run:**
  - Credit Utilization: **171%**
  - Queue 2: **15 transactions**
- **Replay:**
  - Credit Utilization: **98%**
  - Queue 2: **0 transactions**
- **Discrepancy:**
  - Credit utilization differs (171% vs 98%)
  - Queue 2 discrepancy (15 vs 0)

### 7. JSON Output Discrepancies

#### 7.1 Simulation Metadata
- **Run:**
  - `config_file`: `"../examples/configs/advanced_policy_crisis.yaml"`
  - `ticks_executed`: **300**
  - `duration_seconds`: **5.993**
  - `ticks_per_second`: **53.4**
- **Replay:**
  - `config_file`: `"advanced_policy_crisis.yaml"`
  - `ticks_executed`: **1**
  - `duration_seconds`: **0.224**
  - `ticks_per_second`: **4.46**
- **Discrepancy:**
  - Different config_file path format
  - Ticks executed: 300 vs 1 (replay only replayed tick 299)
  - Performance metrics differ (expected for replay, but still a difference)

#### 7.2 Metrics Object
- **Run:**
  ```json
  {
    "total_arrivals": 549,
    "total_settlements": 439,
    "total_lsm_releases": 18,
    "settlement_rate": 0.7996357012750456
  }
  ```
- **Replay:**
  ```json
  {
    "total_arrivals": 6,
    "total_settlements": 15,
    "total_lsm_releases": 1,
    "settlement_rate": 2.5
  }
  ```
- **Discrepancy:** All four fields differ drastically

#### 7.3 Agents Array - Queue Sizes
- **Run:**
  ```json
  { "id": "CORRESPONDENT_HUB", "queue1_size": 38 }
  { "id": "REGIONAL_TRUST", "queue1_size": 41 }
  ```
- **Replay:**
  ```json
  { "id": "CORRESPONDENT_HUB", "queue1_size": 0 }
  { "id": "REGIONAL_TRUST", "queue1_size": 0 }
  ```
- **Discrepancy:** Replay shows **no queue1** for any agent, contradicting textual output
- **Note:** Final balances match for all agents

#### 7.4 Costs Object
- **Run:**
  ```json
  { "total_cost": 63899349 }
  ```
- **Replay:**
  ```json
  { "total_cost": 0 }
  ```
- **Discrepancy:** Run shows $638,993.49 in costs, replay shows $0

---

## Root Cause Analysis

### Primary Hypothesis: Replay is Not Reconstructing Full State

The replay appears to be:
1. **Only processing tick 299 in isolation** rather than understanding the full simulation context
2. **Not loading accumulated state** from previous ticks (queue sizes, overdue statuses)
3. **Recalculating metrics incorrectly** (showing 6 total transactions instead of 549)
4. **Missing entire event types** (overdue events, queue status, cost summaries)

### Evidence:
- JSON shows `ticks_executed: 1` in replay vs `300` in run
- Replay metrics show only 6 arrivals (the arrivals for tick 299) instead of full simulation's 549
- Queue sizes are zero in replay JSON despite textual output showing queues
- Settlement rate of 250% is mathematically impossible and suggests incorrect aggregation

### Secondary Issues:
1. **Internal inconsistencies** even within run mode (header says 15 settled, summary says 10)
2. **StateProvider abstraction not properly implemented** for all metrics
3. **Event persistence may be incomplete** (missing "Transaction Went Overdue" events)
4. **Replay using different calculation logic** than run (different delay costs for same transaction)

---

## Impact Assessment

### User Impact: CRITICAL
- **Replay is completely unreliable** for auditing or debugging
- Users cannot trust replay output to match what actually happened
- Compliance and research validation requirements are violated

### System Integrity: CRITICAL
- Core invariant (determinism + replay identity) is broken
- The StateProvider pattern is not being followed
- Database persistence may be incomplete

### Technical Debt: HIGH
- Indicates fundamental architectural issues
- Will require significant refactoring to fix
- Every new feature risks making the problem worse

---

## Required Fixes

### Immediate (Critical Path):
1. **Fix replay to load full simulation context**, not just single tick
2. **Ensure all event types are persisted and reconstructed**
3. **Make replay use identical display logic** to run (StateProvider pattern)
4. **Fix metric aggregation** to show cumulative totals, not per-tick

### Architectural (Medium-term):
1. **Enforce StateProvider pattern** for all display code
2. **Add replay identity tests** to CI/CD
3. **Validate event completeness** at persistence time
4. **Unify run and replay code paths** more tightly

### Validation (Before closing):
1. **Byte-for-byte replay identity** restored (modulo timing)
2. **All discrepancies cataloged here** are resolved
3. **New tests prevent regression**
4. **Documentation updated** to reflect working replay system

---

## Test Strategy

Each discrepancy above should have:
1. A **specific failing test** that reproduces it
2. A **fix** that makes the test pass
3. A **regression test** that ensures it stays fixed

See implementation plan in follow-up documentation.

---

## References

- **Architecture Doc:** `CLAUDE.md` - "Critical Invariant: Replay Identity"
- **StateProvider Protocol:** `api/payment_simulator/cli/execution/state_provider.py`
- **Replay Implementation:** `api/payment_simulator/cli/commands/replay.py`
- **Gold Standard Tests:** `api/tests/integration/test_replay_identity_gold_standard.py`

---

**Next Steps:** Create comprehensive test suite and architectural fix plan.
