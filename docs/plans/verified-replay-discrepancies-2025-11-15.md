# Verified Replay Identity Discrepancies - Live Test Results

**Date:** 2025-11-15
**Test:** sim-842fec0e, tick 299
**Config:** advanced_policy_crisis.yaml

## CONFIRMED DISCREPANCIES

### ✅ DISCREPANCY #1: Near-Deadline Section Missing in Replay
**Run:** Shows "⚠️ Transactions Near Deadline (within 2 ticks)" section with list
**Replay:** Section completely missing
**Impact:** HIGH - Users lose visibility into urgent transactions

### ✅ DISCREPANCY #2: Settlement Count Mismatch
**Run:** `✅ 10 transaction(s) settled:`
**Replay:** `✅ 15 transaction(s) settled:`
**Tick Summary - Run:** `6 in | 10 settled | 3 LSM | 79 queued`
**Tick Summary - Replay:** `6 in | 15 settled | 1 LSM` (missing queue count!)
**Impact:** CRITICAL - Core metrics differ

### ✅ DISCREPANCY #3: Missing Settlement Detail Blocks
**Run has:**
- RTGS Immediate (4)
- Queue 2 Releases (3)
- Legacy Settlements (7)
- LSM Bilateral Offset (1)

**Replay has:**
- Legacy Settlements (7)
- LSM Bilateral Offset (1)

**Impact:** HIGH - Missing RTGS and Queue2 settlement details

### ✅ DISCREPANCY #4: Cost Accrual Summary Missing
**Run:** Shows "💰 Costs Accrued This Tick: $5,863.10" with breakdown
**Replay:** Completely missing
**Impact:** MEDIUM - Cost visibility reduced

### ✅ DISCREPANCY #5: EOD Metrics Completely Wrong
**Run:**
- End of Day 2 - 110 unsettled, $395,000.00 in penalties
- Total Transactions: 278
- Settled: 194 (69.8%)
- LSM Settled: 13 (6.7% of settlements)

**Replay:**
- End of Day 2 - 0 unsettled, $0.00 in penalties  
- Total Transactions: 6 (only tick 299!)
- Settled: 15 (250.0% - impossible!)
- LSM Settled: 1 (6.7% of settlements)

**Impact:** CRITICAL - Replay showing only tick 299 stats instead of full day

### ✅ DISCREPANCY #9: LSM Count in JSON
**Run:** `"total_lsm_releases": 18`
**Replay:** `"total_lsm_releases": 1`
**Impact:** HIGH - LSM performance metrics wrong

### ✅ DISCREPANCY #10: Settlement Rate Precision
**Run:** `"settlement_rate": 0.7996357012750456`
**Replay:** `"settlement_rate": 0.7996`
**Impact:** LOW - Minor precision difference

## FIXED/NOT REPRODUCED

### ✓ Queue Sizes in JSON
**User Reported:** queue1_size: 0 in replay
**Actual:** queue1_size: 38 in both run and replay
**Status:** FIXED - JSON now shows correct queue sizes

### ✓ Total Arrivals/Settlements in JSON  
**User Reported:** Different totals
**Actual:** Both show 549 arrivals, 439 settlements
**Status:** FIXED - JSON metrics now correct for full simulation

### ? Queue Details in Verbose Output
**Run:** Shows "Queue 1 (38 transactions, $97,945.92 total)"
**Replay:** Missing queue detail sections
**Impact:** MEDIUM - Queue visualization missing, but JSON has data

## ROOT CAUSES IDENTIFIED

1. **Scope Confusion** - Replay EOD uses tick 299 scope instead of full day
2. **Missing Display Blocks** - RTGS, Queue2, Cost Summary, Near-Deadline
3. **LSM Aggregation** - Only counting tick 299 LSM events instead of full simulation
4. **Settlement Counting** - Different logic between run and replay

## NEXT STEPS

1. Write failing tests for each confirmed discrepancy
2. Fix scope confusion (EOD metrics)
3. Add missing display blocks to replay
4. Fix LSM aggregation scope
5. Unify settlement counting logic
