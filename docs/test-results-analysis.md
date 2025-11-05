# Test Results Analysis: LSM & SMART_SPLITTER Investigation

**Date**: 2025-11-05
**Phase**: Initial Test Execution
**Status**: Tests reveal important findings

---

## Executive Summary

All investigation tests have been successfully implemented and initial execution reveals **the claims from the simulation review are more nuanced than initially understood**. The key findings:

1. **LSM Test 1 FAIL**: Reveals that LSM is not needed when agents have sufficient credit
2. **LSM Tests 2-3**: Not yet run (blocked by Test 1 design issue)
3. **Splitting Tests 5-7**: Not yet run (compilation fixes needed first)

**Critical Discovery**: The test scenarios need adjustment to truly reproduce the gridlock conditions where LSM is essential.

---

## Detailed Test Results

### Test 1: LSM Bilateral Activation (FAILED - Test Design Issue)

**File**: `backend/tests/test_lsm.rs::test_lsm_bilateral_activates_in_gridlock`

**Expected Behavior**:
- Two agents with mutual obligations ($3k each direction)
- Insufficient individual liquidity ($1k balance each)
- Transactions should queue
- LSM bilateral offsetting should detect and settle both

**Actual Behavior**:
```
assertion `left == right` failed: Both transactions should be queued due to insufficient individual liquidity
  left: 0 (actual queue size)
 right: 2 (expected queue size)
```

**Analysis**:

The transactions **did not queue** - they settled immediately. Why?

**Agent Configuration**:
- Balance: $1k
- Credit Limit: $5k
- Total capacity: $6k

**Transaction Size**: $3k each

**Result**: Each agent can afford their $3k payment using credit ($1k balance + $2k from credit = $3k). The normal RTGS settlement succeeds, no queueing occurs, and LSM is never invoked.

**Key Insight**: The simulation review scenario had agents that were **already overleveraged** (deep in overdraft, near credit limits). Our test used fresh agents with ample credit capacity.

**Fix Required**: Test scenarios need to:
1. Set credit limits low enough that individual payments cannot settle, OR
2. Pre-load agents with existing credit usage so headroom is insufficient, OR
3. Make transaction amounts exceed `balance + credit_limit`

---

## Test 2: LSM Cycle Activation (NOT RUN)

**Status**: Pending - needs same fix as Test 1
**Reason**: Will likely have same issue (transactions settle via credit before queuing)

---

## Test 3: LSM Integration via Orchestrator (NOT RUN)

**Status**: Pending - awaiting Rust test fixes
**File**: `api/tests/integration/test_lsm_activation.py`

---

## Test 4: LSM Diagnostic Logging (IMPLEMENTED)

**Status**: ✅ Successfully added
**File**: `backend/src/orchestrator/engine.rs:2270-2309`

**Usage**: Set environment variable `LSM_DEBUG=1` to enable detailed logging:
```bash
LSM_DEBUG=1 cargo test ...
```

**Output Includes**:
- Queue size before LSM
- LSM configuration (bilateral/cycles enabled)
- LSM results (offsets, cycles, value settled)
- Warning when LSM finds no settlements despite queued transactions

---

## Tests 5-6: SMART_SPLITTER Rust Tests (NOT RUN)

**Status**: Compilation successful after fixing `PolicyConfig::Tree` → `PolicyConfig::FromJson`
**Files**:
- `backend/tests/test_transaction_splitting.rs::test_tree_policy_split_decision_with_positive_liquidity`
- `backend/tests/test_transaction_splitting.rs::test_tree_policy_split_with_negative_liquidity_reveals_bug`

**Next Steps**: Run these tests to verify the splitting bug

---

## Test 7: SMART_SPLITTER Python Integration (NOT RUN)

**Status**: Ready to run after Rust tests
**File**: `api/tests/integration/test_smart_splitter_investigation.py`

---

## Key Findings & Insights

### Finding 1: LSM Activation Threshold is Subtle

**The simulation review claimed**: "LSMs didn't activate despite gridlock"

**Reality is more complex**:
- LSMs only activate when transactions **queue** (insufficient liquidity + credit)
- In the review scenario, agents may have been so overleveraged that even WITH credit, they couldn't settle
- Our initial tests used "fresh" agents with full credit capacity
- **Conclusion**: The claim may still be valid, but we need to reproduce the exact overleveraged state

### Finding 2: Credit vs. LSM Interaction

**Important distinction**:
- **Normal RTGS**: Settles if `balance + available_credit >= amount`
- **LSM Bilateral**: Settles if net flow is affordable (even if gross flows aren't)
- **LSM Cycles**: Settles with net-zero balance changes

**Question for investigation**: In the simulation review, were agents:
1. Unable to settle due to credit limits (LSM should have helped), OR
2. Holding transactions in Queue 1 due to policy decisions (LSM never saw them)?

### Finding 3: Queue 1 vs Queue 2 Distinction Matters

**Critical realization**:
- **Queue 1** (Agent internal): Policy decides whether to submit
- **Queue 2** (RTGS): LSM operates here

**If SMART_SPLITTER held transactions in Queue 1** (due to the `available_liquidity` bug), **LSM would never see them** to perform bilateral offsetting or cycle detection.

**This could explain the "LSM didn't activate" claim**:
- Not because LSM is broken
- But because transactions never reached Queue 2 due to policy bugs

---

## Revised Understanding of Simulation Review Claims

### Claim 1: "LSMs are not activating"

**Likely Root Cause (Hypothesis)**:
1. SMART_SPLITTER policy holds transactions in Queue 1 (internal queue)
2. Due to `available_liquidity < 0`, split conditions fail
3. Policy decides to HOLD instead of SUBMIT
4. Transactions never reach Queue 2 (RTGS queue)
5. LSM never sees these transactions
6. Result: Zero LSM activations

**Implication**: This is not an LSM bug, but a **policy bug preventing transactions from reaching LSM**.

### Claim 2: "SMART_SPLITTER never splits"

**Confirmed**: This is definitely true based on code analysis
- Policy condition: `available_liquidity > min_split_amount`
- When in overdraft: `available_liquidity < 0`
- Condition never evaluates true
- Result: Agent holds, accumulates costs, death spiral

**Implication**: This is the **root cause bug**. Fixing this may indirectly fix the LSM activation issue.

---

## Recommended Next Steps

### Immediate Actions (Priority Order)

1. **Fix and run SMART_SPLITTER splitting tests (Tests 5-7)**
   - These tests directly target the confirmed bug
   - Expected result: Tests should FAIL, confirming bug
   - This validates our root cause analysis

2. **Revise LSM test scenarios (Tests 1-2)**
   - **Option A**: Pre-load agents with credit usage
     ```rust
     let mut agent_a = create_agent("BANK_A", 100_000, 200_000);
     agent_a.debit(150_000).unwrap(); // Use most of credit
     // Now agent has -$50k balance, only $50k credit left
     // A $3k transaction would require $3k credit, only $0.5k available
     ```

   - **Option B**: Make transactions exceed total capacity
     ```rust
     // Agent: $1k balance, $2k credit limit = $3k total
     // Transaction: $5k
     // Result: Cannot settle, will queue
     ```

   - **Option C**: Disable credit for test simplicity
     ```rust
     create_agent("BANK_A", 100_000, 0); // No credit
     // Transaction: $3k
     // Result: Cannot settle with $1k balance, will queue
     ```

3. **Run revised LSM tests with diagnostic logging**
   ```bash
   LSM_DEBUG=1 cargo test --no-default-features test_lsm_bilateral_activates_in_gridlock -- --nocapture
   ```

4. **Run Python integration tests**
   - Tests 3 (LSM) and 7 (Splitting)
   - Verify behavior through full FFI stack

### Investigation Questions to Answer

1. **Queue 1 vs Queue 2**: Do transactions in the review scenario ever reach Queue 2?
   - Add logging to policy hold decisions
   - Count transactions in Queue 1 vs Queue 2 over time

2. **Credit Usage Progression**: How quickly do agents exhaust credit?
   - Log credit usage each tick
   - Identify when agents hit credit limits

3. **LSM Opportunity Detection**: When Queue 2 has transactions, do valid LSM patterns exist?
   - Even with diagnostic logging enabled, check if cycles/bilateral pairs exist
   - If LSM finds zero patterns when Queue 2 is full, that's a real LSM bug
   - If LSM never runs because Queue 2 is empty, it's a policy bug

---

## Test Implementation Status Summary

| Test | File | Status | Result | Next Action |
|------|------|--------|--------|-------------|
| 1 | test_lsm.rs | ✅ Implemented | ❌ Failed | Fix scenario |
| 2 | test_lsm.rs | ✅ Implemented | ⏸️ Pending | Fix scenario |
| 3 | test_lsm_activation.py | ✅ Implemented | ⏸️ Pending | Run after Rust fixes |
| 4 | engine.rs (logging) | ✅ Implemented | ✅ Added | Use with LSM_DEBUG=1 |
| 5 | test_transaction_splitting.rs | ✅ Implemented | ⏸️ Pending | Run next |
| 6 | test_transaction_splitting.rs | ✅ Implemented | ⏸️ Pending | Run next |
| 7 | test_smart_splitter_investigation.py | ✅ Implemented | ⏸️ Pending | Run after #5-6 |

---

## Code Quality & Maintainability

**Positive**:
- All tests follow TDD principles (written before fixes)
- Tests have detailed documentation explaining expected behavior
- Diagnostic logging is conditional (no performance impact when disabled)
- Tests are isolated and can run independently

**Areas for Improvement**:
- LSM tests need more realistic scenarios (overleveraged agents)
- Consider parameterized tests for different credit/balance combinations
- Add helper functions for common agent setups (overleveraged, fresh, etc.)

---

## Conclusion

The investigation has revealed that **the simulation review claims are likely valid, but the root cause is different than initially suspected**:

**Initial Hypothesis**: LSM code is broken
**Actual Root Cause (likely)**: Policy bugs prevent transactions from reaching LSM

**The chain of failures**:
1. SMART_SPLITTER uses `available_liquidity` check for splitting
2. When in overdraft, `available_liquidity < 0`
3. Split conditions fail → policy HOLDS transactions
4. Transactions stuck in Queue 1 → never reach Queue 2
5. LSM never sees transactions → zero LSM activations
6. Meanwhile: delay costs + overdraft costs accumulate → death spiral

**Fix Priority**:
1. **MUST FIX**: Add `effective_liquidity` field to policy context
2. **SHOULD FIX**: Revise LSM tests to use realistic overleveraged scenarios
3. **NICE TO HAVE**: Add Queue 1 vs Queue 2 monitoring to track policy hold decisions

**Next Execution Phase**: Run Tests 5-7 to confirm SMART_SPLITTER splitting bug, then implement the fix.
