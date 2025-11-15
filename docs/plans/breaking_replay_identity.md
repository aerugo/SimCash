# Breaking Replay Identity: Comprehensive Discrepancy Catalog

**Date:** 2025-11-15
**Status:** CRITICAL - Replay fundamentally broken
**Goal:** Achieve byte-for-byte identical outputs between `run` and `replay` (modulo timing)

---

## Executive Summary

Replay output differs from run output in **13 major categories**, indicating fundamental architectural issues. The replay system is:

1. **Reconstructing state** instead of using persisted events
2. **Querying partial data** (single tick instead of full simulation)
3. **Recalculating metrics** instead of using persisted values
4. **Missing display blocks** that appear in run mode

**Critical Principle:** Replay must be a **pure playback** of persisted events, not a reconstruction.

---

## Comparison Context

* **Run** = `uv run payment-sim run --config ... --persist --verbose` (sim-ee9bb36b)
* **Replay** = `uv run payment-sim replay --simulation-id sim-ee9bb36b --from-tick 299 --to-tick 299 --verbose`

Below lists only *actual differences*; identical sections are omitted.

---

## DISCREPANCY #1: Near-Deadline Transaction Status

**Location:** "Transactions Near Deadline (within 2 ticks)" block at tick 299

**Issue:** Same transactions show different "ticks away" counts.

**Run:**
```
Deadline: Tick 300 (0 ticks away)
```

**Replay:**
```
Deadline: Tick 300 (1 tick away)
```

**Analysis:**
- Same TX IDs appear in both
- Run shows 0 ticks away, replay shows 1 tick away
- One of them is calculating current_tick incorrectly

**Root Cause:** Likely replay using wrong reference tick for "ticks away" calculation.

**Impact:** Minor display issue, no data corruption.

---

## DISCREPANCY #2: Settlement Count Header

**Location:** Tick 299 settlement summary header

**Issue:** Different settlement counts reported.

### 2.1 Per-tick settlement header

**Run:**
```
✅ 10 transaction(s) settled:
```

**Replay:**
```
✅ 15 transaction(s) settled:
```

**Analysis:**
- Replay shows 50% more settlements (15 vs 10)
- Likely counting same settlements multiple times OR
- Including settlements from different event categories

### 2.2 Tick summary line

**Run:**
```
Summary: 6 in | 10 settled | 3 LSM | 79 queued
```

**Replay:**
```
Summary: 6 in | 15 settled | 1 LSM | 79 queued
```

**Analysis:**
- `settled`: **10** vs **15** (matches header discrepancy)
- `LSM`: **3** vs **1** (replay missing 2 LSM cycles)
- `6 in` and `79 queued` are correct

**Root Cause:** Replay likely counting Legacy + RTGS + Queue2 settlements, while run deduplicates.

**Impact:** HIGH - Settlement metrics are core performance indicators.

---

## DISCREPANCY #3: Missing Settlement Detail Blocks

**Location:** Tick 299 settlement breakdown

**Issue:** Replay missing RTGS and Queue2 settlement detail blocks.

**Run shows:**
```
RTGS Immediate (4)
  • TX 4ea47d7f: CORRESPONDENT_HUB → REGIONAL_TRUST | $3,158.67
    Balance: $-41,593.35 → $-44,752.02
  [... 3 more ...]

Queue 2 Releases (3)
  • TX 8e0a0854: CORRESPONDENT_HUB → REGIONAL_TRUST | $5,000.00
    Queued for 2 ticks | Released: liquidity_available
  [... 2 more ...]

Legacy Settlements (7)
  [same 7 TXs as above]

LSM Bilateral Offset (1)
  TX unknown ⟷ TX unknown: $31,598.35
```

**Replay shows:**
```
Legacy Settlements (7)
  [same 7 TXs]

LSM Bilateral Offset (1)
  TX  ⟷ TX : $31,598.35
```

**Analysis:**
- Replay **completely missing** "RTGS Immediate" and "Queue 2 Releases" blocks
- Only showing Legacy (which duplicates them) + LSM
- LSM TX IDs also missing ("unknown" vs blank)

**Root Cause:** Display code in replay.py not loading/displaying RTGS and Queue2 events.

**Impact:** HIGH - Critical settlement detail missing from replay.

---

## DISCREPANCY #4: Missing Cost Accrual Summary

**Location:** Tick 299 cost summary

**Issue:** Replay missing entire "Costs Accrued This Tick" block.

**Run shows:**
```
💰 Costs Accrued This Tick: $5,863.10

   CORRESPONDENT_HUB: $3,133.47
   • Liquidity: $265.00
   • Delay: $2,868.47

   REGIONAL_TRUST: $2,729.63
   • Liquidity: $276.95
   • Delay: $2,452.68
```

**Replay:** This entire block is **missing**.

**Analysis:**
- Replay loads individual CostAccrual events (confirmed in "💰 Cost Accruals (4)" block)
- But doesn't aggregate/display the per-tick summary

**Root Cause:** Display code in replay.py not showing cost summary block.

**Impact:** MEDIUM - Cost visibility reduced in replay.

---

## DISCREPANCY #5: End-of-Day Unsettled Count

**Location:** End-of-day banner at tick 299

**Issue:** Completely different unsettled counts.

**Run:**
```
🌙 End of Day 2 - 110 unsettled, $395,000.00 in penalties
```

**Replay:**
```
🌙 End of Day 2 - 0 unsettled, $0.00 in penalties
```

**Analysis:**
- Replay shows **0 unsettled** vs run's **110 unsettled**
- Replay shows **$0 penalties** vs run's **$395,000**

### 5.1 EOD System-wide metrics

**Run:**
```
Total Transactions: 278
Settled: 194 (69.8%)
Unsettled: 84 (30.2%)
LSM Settled: 13 (6.7% of settlements)
Settlement Rate: 69.8%
```

**Replay:**
```
Total Transactions: 6
Settled: 15 (250.0%)
Unsettled: -9 (-150.0%)
LSM Settled: 1 (6.7% of settlements)
Settlement Rate: 250.0%
```

**Analysis:**
- Replay showing **only tick 299 stats** (6 arrivals that tick)
- Replay confusing "display range" with "simulation totals"
- Negative unsettled count is nonsensical
- >100% settlement rate is impossible

**Root Cause:** Replay querying only tick 299 events instead of full Day 2 (or full simulation).

**Impact:** CRITICAL - End-of-day reporting completely broken.

---

## DISCREPANCY #6: Agent Queue Sizes

**Location:** Multiple places - text output and JSON

### 6.1 Text output: Agent financial stats

**Both run and replay show:**
- CORRESPONDENT_HUB: Queue 1 (38), Queue 2 (16)
- REGIONAL_TRUST: Queue 1 (41), Queue 2 (15)

✅ Text output is correct in both.

### 6.2 JSON output: agents array

**Run:**
```json
{
  "id": "CORRESPONDENT_HUB",
  "final_balance": -4159335,
  "queue1_size": 38
}
```

**Replay:**
```json
{
  "id": "CORRESPONDENT_HUB",
  "final_balance": -4159335,
  "queue1_size": 0
}
```

**Analysis:**
- Replay's JSON claims `queue1_size: 0` for all agents
- But replay's **text output** correctly shows 38/41
- **Internal inconsistency** within replay output itself

**Root Cause:** JSON serialization using wrong state source (snapshot at tick 299 only, not end state).

**Impact:** HIGH - JSON output unreliable for programmatic access.

---

## DISCREPANCY #7: Overdue Transaction Metrics

**Location:** "🔥 Overdue Transactions" list at tick 299

**Issue:** Same overdue TXs with different tick counts and delay costs.

### 7.1 Example: TX eb5f484e

**Run:**
```
TX eb5f484e: CORRESPONDENT_HUB → REGIONAL_TRUST | $3,387.91
  Overdue: 58 ticks
  Penalty $2,500.00 + Delay $231.78 = $2,731.78
```

**Replay:**
```
TX eb5f484e: CORRESPONDENT_HUB → REGIONAL_TRUST | $3,387.91
  Overdue: 57 ticks
  Penalty $2,500.00 + Delay $14,250.00 = $16,750.00
```

**Analysis:**
- Same TX ID, direction, amount
- **Overdue ticks differ by 1** (58 vs 57)
- **Delay cost wildly different:**
  - Run: $231.78 (≈ $4/tick)
  - Replay: $14,250.00 (= 57 × $250/tick)

### 7.2 Total overdue cost

**Run:** Total Overdue Cost: `$77,363.66`
**Replay:** Total Overdue Cost: `$221,500.00`

**Difference:** Replay shows **2.86× higher** overdue costs.

**Root Cause:**
1. Overdue tick count off-by-one (likely deadline vs current_tick calculation)
2. Delay cost formula different:
   - Run uses actual persisted delay costs (small incremental)
   - Replay recalculating with wrong formula (57 × $250 base rate × overdue_multiplier)

**Impact:** CRITICAL - Cost metrics fundamentally wrong in replay.

---

## DISCREPANCY #8: Credit Utilization Percentage

**Location:** EOD Agent Performance block

**Issue:** REGIONAL_TRUST credit utilization differs.

**Run:**
```
REGIONAL_TRUST:
  Credit Utilization: 171%
```

**Replay:**
```
REGIONAL_TRUST:
  Credit Utilization: 98%
```

**Analysis:**
- Final balance identical: $-40,912.90
- Queue sizes identical in text (41/15)
- But utilization % differs: **171% vs 98%**
- Formula: `(abs(negative_balance) / credit_limit) × 100`
- Suggests different credit_limit values being used

**Root Cause:** Replay using wrong credit_limit (possibly initial instead of final, or vice versa).

**Impact:** MEDIUM - Compliance metric misreported.

---

## DISCREPANCY #9: Global LSM Count

**Location:** Final JSON metrics

**Issue:** Total LSM releases differ drastically.

**Run:**
```json
"metrics": {
  "total_lsm_releases": 18
}
```

**Replay:**
```json
"metrics": {
  "total_lsm_releases": 1
}
```

**Analysis:**
- Run shows **18 LSM releases** across full simulation
- Replay shows **1 LSM release** (only from tick 299)
- Again, replay using single-tick scope instead of full simulation

**Root Cause:** Metrics aggregation querying only displayed tick range, not full simulation.

**Impact:** HIGH - LSM performance metrics wrong.

---

## DISCREPANCY #10: Settlement Rate Precision

**Location:** Final JSON metrics

**Issue:** Different precision in settlement rate.

**Run:**
```json
"settlement_rate": 0.7996357012750456
```

**Replay:**
```json
"settlement_rate": 0.7996
```

**Analysis:**
- Same value, but replay rounds to 4 decimal places
- Both calculate correctly (439/549 = 0.7996...)

**Root Cause:** Different formatting/precision in replay JSON serialization.

**Impact:** LOW - Minor formatting inconsistency.

---

## DISCREPANCY #11: Agent Ordering

**Location:** Multiple blocks - financial stats, EOD performance

**Issue:** Agent display order differs.

**Run order:**
1. CORRESPONDENT_HUB
2. METRO_CENTRAL
3. MOMENTUM_CAPITAL
4. REGIONAL_TRUST

**Replay order:**
1. METRO_CENTRAL
2. REGIONAL_TRUST
3. MOMENTUM_CAPITAL
4. CORRESPONDENT_HUB

**Analysis:**
- Content per agent is identical
- Only display order differs
- Not deterministic between run and replay

**Root Cause:** Likely database query without ORDER BY, or different iteration order.

**Impact:** LOW - Cosmetic only, no data corruption.

---

## DISCREPANCY #12: LSM Transaction ID Display

**Location:** LSM bilateral offset block

**Issue:** LSM TX IDs shown differently.

**Run:**
```
LSM Bilateral Offset (1)
  TX unknown ⟷ TX unknown: $31,598.35
```

**Replay:**
```
LSM Bilateral Offset (1)
  TX  ⟷ TX : $31,598.35
```

**Analysis:**
- Run shows "unknown" placeholder
- Replay shows blank (no text)
- Amount is correct in both

**Root Cause:** LSM events not storing TX IDs, or display code handling missing IDs differently.

**Impact:** LOW - Cosmetic, but LSM traceability reduced.

---

## DISCREPANCY #13: Config File Path

**Location:** Final JSON simulation object

**Issue:** Different path formats.

**Run:**
```json
"config_file": "../examples/configs/advanced_policy_crisis.yaml"
```

**Replay:**
```json
"config_file": "advanced_policy_crisis.yaml"
```

**Analysis:**
- Run shows relative path from execution directory
- Replay shows basename only (stored in database)

**Root Cause:** Database stores basename; run uses command-line arg directly.

**Impact:** LOW - Cosmetic path difference.

---

## Summary of Critical Issues

### High-Priority Fixes (Data Corruption)

1. **Settlement counts wrong** (#2) - Replay overcounting or run undercounting
2. **EOD metrics wrong** (#5) - Replay using single-tick scope instead of full simulation
3. **Overdue costs wrong** (#7) - Replay recalculating with wrong formula
4. **Queue sizes wrong in JSON** (#6.2) - JSON using wrong state snapshot
5. **LSM count wrong** (#9) - Single-tick scope issue

### Medium-Priority Fixes (Missing Information)

6. **Missing RTGS/Queue2 blocks** (#3) - Replay not displaying key settlement details
7. **Missing cost summary** (#4) - Replay not showing per-tick cost breakdown
8. **Credit utilization wrong** (#8) - Using wrong credit limit value

### Low-Priority Fixes (Cosmetic)

9. **Near-deadline tick count** (#1) - Off-by-one in calculation
10. **Settlement rate precision** (#10) - Rounding difference
11. **Agent ordering** (#11) - Non-deterministic display order
12. **LSM TX IDs** (#12) - Missing vs "unknown" label
13. **Config path** (#13) - Relative vs basename

---

## Architectural Root Causes

### 1. **Scope Confusion**
Replay queries events for displayed tick range (299-299) but tries to show full simulation metrics. This causes:
- EOD metrics showing only 6 transactions
- LSM count showing only 1 cycle
- Impossible settlement rates (>100%)

**Fix:** Separate "display range" from "metrics scope". Always compute metrics over full simulation.

### 2. **Recalculation Instead of Replay**
Replay recalculates metrics (overdue costs, credit utilization) instead of using persisted values. This causes:
- Different delay cost formulas
- Different credit utilization %
- Potential for formula changes breaking replay

**Fix:** Persist calculated values in events; replay displays persisted values only.

### 3. **Missing Event Types**
Some display blocks (RTGS details, cost summary) are reconstructed from live state in run mode, but not available in replay. This causes:
- Missing settlement detail blocks
- Missing cost accrual summary

**Fix:** Ensure all display-worthy information is captured in events and persisted.

### 4. **Dual Code Paths**
Run and replay use different code for displaying the same information. This causes:
- Formatting differences
- Missing blocks in replay
- Different calculation logic

**Fix:** Unify display code using StateProvider abstraction - single display function for both modes.

### 5. **Incomplete Event Enrichment**
Events stored without full display context (LSM TX IDs, settlement breakdown categories). This causes:
- LSM showing blank TX IDs
- Cannot distinguish RTGS from Queue2 settlements in replay

**Fix:** Enrich events with ALL fields needed for display before persisting.

---

## Next Steps

1. **Write failing tests** for each discrepancy (see `test-plan.md`)
2. **Implement StateProvider pattern** to unify run/replay display
3. **Enrich all event types** with complete display data
4. **Fix metrics aggregation** to use correct scope
5. **Eliminate recalculation** - replay only displays persisted data

**Success Criteria:** `diff <(run output) <(replay output)` shows ONLY timing differences.

---

**Last Updated:** 2025-11-15
**Next Review:** After test implementation
