# LSM & Transaction Splitting Investigation Plan

**Date**: 2025-11-05
**Status**: Investigation Phase
**Priority**: Critical

## Executive Summary

A thorough simulation review identified two critical issues:
1. **LSMs not activating** despite gridlock conditions and explicit configuration
2. **SMART_SPLITTER agent never splits** payments, leading to catastrophic costs ($25M+)

This document outlines a TDD-principled approach to:
1. Verify these claims with targeted tests
2. Diagnose root causes
3. Implement fixes if confirmed

---

## Claim #1: LSMs Are Not Activating

### Evidence from Review
- Scenario configured with `enable_bilateral: true` and `enable_cycles: true`
- Starting at Tick 34, transactions began queuing in RTGS (Queue 2)
- Circular payment flows designed specifically to trigger LSM
- **End result: 0 bilateral offsets, 0 cycles settled**

### Hypothesis Tree

#### H1.1: LSM is disabled in configuration (UNLIKELY)
- **Test**: Read simulation config, verify LSM flags
- **Expected**: Both flags are `true` per review
- **If False**: Configuration error, fix config

#### H1.2: LSM code never executes (POSSIBLE)
- **Test**: Add logging/instrumentation to `run_lsm_pass` entry point
- **Expected**: Function is called every tick when queue is non-empty
- **If False**: Orchestrator bug, fix call site in `engine.rs:2267-2276`

#### H1.3: LSM sees empty queue despite transactions existing (LIKELY)
- **Test**: Log queue size at LSM entry vs orchestrator view
- **Expected**: Queue sizes should match
- **If False**: State synchronization bug between orchestrator and settlement module

#### H1.4: Bilateral/cycle detection logic fails to find valid patterns (POSSIBLE)
- **Test**: Unit test with known gridlock pattern (3-agent cycle, bilateral pair)
- **Expected**: Detection should succeed (existing tests pass, so unlikely)
- **If False**: Bug in detection algorithm

#### H1.5: Credit limit checks reject LSM settlements (LIKELY)
- **Test**: Check if `settle_bilateral_pair` credit validation (lines 315-321) rejects all pairs
- **Expected**: Net sender can handle net flow within credit limits
- **If False**: All agents are so overleveraged that even net flows exceed credit

### Test Plan: LSM Activation

#### Test 1: Minimal Bilateral Scenario (Rust)
```rust
#[test]
fn test_lsm_bilateral_activates_in_gridlock() {
    // Setup: A and B with mutual obligations, insufficient individual liquidity
    let agents = vec![
        create_agent("A", 100_000, 500_000), // $1k balance, $5k credit
        create_agent("B", 100_000, 500_000),
    ];
    let mut state = SimulationState::new(agents);

    // A→B $3k, B→A $3k (should net to zero)
    let tx_ab = create_transaction("A", "B", 300_000, 0, 100);
    let tx_ba = create_transaction("B", "A", 300_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_ba, 2).unwrap();

    assert_eq!(state.queue_size(), 2, "Both queued due to insufficient individual liquidity");

    // Run LSM pass
    let lsm_config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &lsm_config, 5, 100);

    // CRITICAL ASSERTIONS
    assert!(result.bilateral_offsets >= 1, "Should detect bilateral pair");
    assert_eq!(state.queue_size(), 0, "Both should settle via bilateral offset");
}
```

**Success Criteria**: Test passes → LSM works in isolation
**Failure**: Test fails → Root cause in LSM logic (investigate H1.4)

#### Test 2: Minimal Cycle Scenario (Rust)
```rust
#[test]
fn test_lsm_cycle_activates_in_ring() {
    // Setup: A→B→C→A cycle, each lacks individual liquidity
    let agents = vec![
        create_agent("A", 50_000, 500_000),
        create_agent("B", 50_000, 500_000),
        create_agent("C", 50_000, 500_000),
    ];
    let mut state = SimulationState::new(agents);

    // Create ring: A→B→C→A, each $2k
    let tx_ab = create_transaction("A", "B", 200_000, 0, 100);
    let tx_bc = create_transaction("B", "C", 200_000, 0, 100);
    let tx_ca = create_transaction("C", "A", 200_000, 0, 100);

    submit_transaction(&mut state, tx_ab, 1).unwrap();
    submit_transaction(&mut state, tx_bc, 2).unwrap();
    submit_transaction(&mut state, tx_ca, 3).unwrap();

    assert_eq!(state.queue_size(), 3, "All queued");

    // Run LSM
    let lsm_config = LsmConfig::default();
    let result = run_lsm_pass(&mut state, &lsm_config, 5, 100);

    // CRITICAL ASSERTIONS
    assert!(result.cycles_settled >= 1, "Should detect 3-agent cycle");
    assert_eq!(state.queue_size(), 0, "Cycle should settle all via net-zero flows");
}
```

**Success Criteria**: Test passes → LSM cycle detection works
**Failure**: Test fails → Bug in cycle settlement (investigate H1.4)

#### Test 3: Full Orchestrator LSM Integration (Python)
```python
def test_lsm_bilateral_offset_via_orchestrator():
    """Integration test: LSM through full orchestrator stack."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "lsm_config": {
            "enable_bilateral": True,
            "enable_cycles": False,  # Test bilateral only
        },
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 100_000,  # $1k
                "credit_limit": 500_000,      # $5k credit
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 100_000,
                "credit_limit": 500_000,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Submit mutual obligations
    tx_ab = orch.submit_transaction(
        sender="BANK_A",
        receiver="BANK_B",
        amount=300_000,  # $3k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    tx_ba = orch.submit_transaction(
        sender="BANK_B",
        receiver="BANK_A",
        amount=300_000,  # $3k
        deadline_tick=50,
        priority=5,
        divisible=False,
    )

    # Run one tick to process submissions
    result = orch.tick()

    # CRITICAL ASSERTIONS
    assert result["num_settlements"] > 0, "LSM should have settled transactions"
    assert orch.get_queue2_size() == 0, "Queue should be empty after LSM"

    # Verify net-zero balance changes (bilateral offsetting)
    balance_a = orch.get_agent_balance("BANK_A")
    balance_b = orch.get_agent_balance("BANK_B")
    assert balance_a == 100_000, "A net zero (sent $3k, received $3k)"
    assert balance_b == 100_000, "B net zero (sent $3k, received $3k)"
```

**Success Criteria**: Test passes → LSM works end-to-end
**Failure**: Test fails → Integration bug (investigate H1.2, H1.3, H1.5)

#### Test 4: LSM Logging Instrumentation (Diagnostic)
Add temporary logging to `backend/src/orchestrator/engine.rs` at line 2267:
```rust
// STEP 5: LSM COORDINATOR
eprintln!("[LSM DEBUG] Queue size before LSM: {}", self.state.queue_size());
eprintln!("[LSM DEBUG] LSM config: bilateral={}, cycles={}",
    self.lsm_config.enable_bilateral,
    self.lsm_config.enable_cycles
);

let lsm_result = lsm::run_lsm_pass(...);

eprintln!("[LSM DEBUG] LSM result: bilateral_offsets={}, cycles_settled={}, queue_after={}",
    lsm_result.bilateral_offsets,
    lsm_result.cycles_settled,
    self.state.queue_size()
);
```

**Run**: Execute problematic scenario with logging
**Expected**: See LSM being called with non-empty queue
**If Not**: Confirms H1.2 or H1.3

---

## Claim #2: SMART_SPLITTER Never Splits

### Evidence from Review
- Zero `SPLIT` decisions across all 50 ticks
- Policy defines `split_threshold: $3,000`, transactions range $500-$8,000
- Agent accumulates $25M+ in overdraft costs
- All transactions remain unsettled at EOD

### Root Cause Analysis

#### Confirmed Design Flaw (from policy JSON analysis)

**Policy Logic** (`smart_splitter.json` lines 62-64, 165-168):
```json
{
  "op": "and",
  "conditions": [
    {"op": ">", "left": {"field": "remaining_amount"}, "right": {"param": "split_threshold"}},
    {"op": ">", "left": {"field": "available_liquidity"}, "right": {"param": "min_split_amount"}}
  ]
}
```

**Problem**: `available_liquidity = balance + credit_headroom - credit_used`
- Once agent goes negative, `available_liquidity` becomes negative
- Condition `available_liquidity > $750` can NEVER be true when in overdraft
- Agent enters death spiral:
  1. Goes into overdraft (negative balance)
  2. Can't split (fails liquidity check)
  3. HOLDs transactions in Queue 1 (accrues delay costs)
  4. Remains in overdraft (accrues liquidity costs)
  5. Never recovers

**Why the other agents don't hit this**:
- `AGGRESSIVE_TRADER`, `COST_OPTIMIZER`, `DEADLINE_TRADER`: Policies likely release transactions using credit
- `CAUTIOUS_PRESERVER`: Explicitly designed to avoid credit, holds proactively
- `SMART_SPLITTER`: Tries to be clever, but logic breaks under severe stress

### Test Plan: Transaction Splitting

#### Test 5: Splitting with Positive Liquidity (Rust - Baseline)
```rust
#[test]
fn test_split_decision_with_positive_liquidity() {
    // Setup: Agent with some liquidity, large transaction
    let agents = vec![
        create_agent("SPLITTER", 200_000, 500_000), // $2k balance, $5k credit
        create_agent("RECEIVER", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Large transaction: $5k (exceeds available balance)
    let tx = create_transaction("SPLITTER", "RECEIVER", 500_000, 0, 100);
    state.insert_transaction(tx.clone());

    // Load smart_splitter policy
    let policy = TreePolicy::from_file("backend/policies/smart_splitter.json").unwrap();

    // Evaluate policy decision
    let agent = state.get_agent("SPLITTER").unwrap();
    let decision = policy.evaluate(agent, &tx, &state, 5, &cost_rates, 100, 90);

    // CRITICAL ASSERTION
    match decision {
        PolicyDecision::SubmitPartial { num_splits, .. } => {
            assert!(num_splits >= 2, "Should decide to split");
        }
        _ => panic!("Expected Split decision, got: {:?}", decision),
    }
}
```

**Success Criteria**: Test passes → Splitting works when liquidity is positive
**Failure**: Test fails → Bug in splitting logic itself

#### Test 6: Splitting with Negative Liquidity (Reveals Bug)
```rust
#[test]
fn test_split_decision_with_negative_liquidity_and_credit() {
    // Setup: Agent in overdraft but with remaining credit
    let agents = vec![
        create_agent("SPLITTER", -300_000, 500_000), // -$3k balance, $5k credit → $2k headroom
        create_agent("RECEIVER", 100_000, 0),
    ];
    let mut state = SimulationState::new(agents);

    // Mark agent as having used some credit
    state.get_agent_mut("SPLITTER").unwrap().debit(300_000).unwrap();

    // Transaction: $4k (agent has $2k effective liquidity via credit)
    let tx = create_transaction("SPLITTER", "RECEIVER", 400_000, 0, 100);
    state.insert_transaction(tx.clone());

    // Load policy
    let policy = TreePolicy::from_file("backend/policies/smart_splitter.json").unwrap();

    // Evaluate
    let agent = state.get_agent("SPLITTER").unwrap();
    let decision = policy.evaluate(agent, &tx, &state, 5, &cost_rates, 100, 90);

    // CURRENT BEHAVIOR (BUG)
    // available_liquidity = -300_000 + 0 = -300_000 (negative!)
    // Condition `available_liquidity > min_split_amount` fails
    // Result: HOLD decision

    match decision {
        PolicyDecision::Hold => {
            // This is the BUG - demonstrates the issue
            eprintln!("BUG CONFIRMED: Policy holds when it should split using credit");
            assert!(true, "Bug reproduced");
        }
        PolicyDecision::SubmitPartial { num_splits, .. } => {
            // This is what SHOULD happen (after fix)
            assert!(num_splits >= 2, "Should split using credit headroom");
        }
        _ => panic!("Unexpected decision: {:?}", decision),
    }
}
```

**Success Criteria**: Test FAILS initially (confirms bug), PASSES after fix

#### Test 7: Full Orchestrator Splitting Scenario (Python)
```python
def test_smart_splitter_splits_under_stress():
    """Integration test: SMART_SPLITTER should split when liquidity-constrained."""
    config = {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 42,
        "agent_configs": [
            {
                "id": "SMART_SPLITTER",
                "opening_balance": 200_000,  # $2k
                "credit_limit": 500_000,     # $5k credit
                "policy": {
                    "type": "Tree",
                    "file_path": "backend/policies/smart_splitter.json",
                },
            },
            {
                "id": "RECEIVER",
                "opening_balance": 1_000_000,  # Sufficient liquidity
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
        "cost_rates": {
            "split_friction_cost": 1_000,  # $10 per split
        },
    }

    orch = Orchestrator.new(config)

    # Submit large transaction: $5k (exceeds balance but within credit)
    tx_id = orch.submit_transaction(
        sender="SMART_SPLITTER",
        receiver="RECEIVER",
        amount=500_000,  # $5k
        deadline_tick=50,
        priority=5,
        divisible=True,  # MUST be divisible
    )

    # Run one tick
    result = orch.tick()

    # CRITICAL ASSERTIONS (will fail initially due to bug)
    # After fix, SMART_SPLITTER should split the transaction
    assert result["num_settlements"] > 0, "Should have settled at least one chunk"

    # Check if splitting occurred (need FFI method to query this)
    # For now, check that balance changed (something settled)
    balance = orch.get_agent_balance("SMART_SPLITTER")
    assert balance != 200_000, "Balance should change due to partial settlement"
```

**Success Criteria**: Test FAILS initially, PASSES after fix

---

## Remediation Plans

### Fix #1: LSM Activation (Conditional)

**IF** Tests 1-2 pass but Test 3 fails:

#### Root Cause: Integration Bug
- **Location**: `backend/src/orchestrator/engine.rs:2267-2276`
- **Likely Issue**: Queue state not synchronized before LSM call
- **Fix**: Ensure `pending_settlements` are fully processed and queue updated before LSM
- **Implementation**:
  ```rust
  // After STEP 4 (process_queue), ensure queue is finalized
  self.state.finalize_queue(); // If such method exists

  // THEN run LSM
  let lsm_result = lsm::run_lsm_pass(...);
  ```

**IF** Tests 1-2 fail:

#### Root Cause: LSM Logic Bug
- **Investigate**: Lines 315-321 in `lsm.rs` (credit limit check in bilateral offset)
- **Hypothesis**: Credit check is too strict, rejecting valid net flows
- **Fix**:
  ```rust
  // Current code (line 315-321):
  if projected_balance < -(sender.credit_limit() as i64) {
      return 0; // Rejects entire bilateral pair
  }

  // Proposed fix: Check if net flow is affordable with current credit usage
  let credit_used = sender.credit_used();
  let credit_available = (sender.credit_limit() as i64) - credit_used;
  if net_amount > sender.balance() + credit_available {
      return 0; // Only reject if truly unaffordable
  }
  ```

### Fix #2: SMART_SPLITTER Policy (Confirmed Bug)

#### Root Cause: Negative `available_liquidity` Breaks Logic
- **Location**: `backend/policies/smart_splitter.json` lines 62-64, 165-168
- **Problem**: Condition checks `available_liquidity > min_split_amount`
- **When**: Agent in overdraft, `available_liquidity` is negative

#### Solution: Redefine Split Eligibility Condition

**Option A: Use Credit Headroom Instead of Available Liquidity**
```json
{
  "op": "and",
  "conditions": [
    {"op": ">", "left": {"field": "remaining_amount"}, "right": {"param": "split_threshold"}},
    {"op": ">", "left": {"field": "headroom"}, "right": {"param": "min_split_amount"}}
  ]
}
```
- **Pros**: Simple fix, uses existing field
- **Cons**: Doesn't account for current balance, might over-split

**Option B: Compute Effective Liquidity (Balance + Headroom)**
```json
{
  "op": "and",
  "conditions": [
    {"op": ">", "left": {"field": "remaining_amount"}, "right": {"param": "split_threshold"}},
    {
      "op": ">",
      "left": {
        "compute": {
          "op": "+",
          "left": {"field": "available_liquidity"},
          "right": {"field": "headroom"}
        }
      },
      "right": {"param": "min_split_amount"}
    }
  ]
}
```
- **Pros**: Accurate, considers both balance and credit
- **Cons**: More complex, requires `compute` support in policy engine

**Option C: Add New Field `effective_liquidity`**
Add to policy context:
```rust
// In policy evaluation context
effective_liquidity: agent.balance() + agent.headroom()
```

Update policy JSON:
```json
{"op": ">", "left": {"field": "effective_liquidity"}, "right": {"param": "min_split_amount"}}
```
- **Pros**: Clean, semantically correct
- **Cons**: Requires code change + policy change

**RECOMMENDED**: Option C (most correct, clearest semantics)

#### Implementation Steps
1. Add `effective_liquidity` to policy context in `backend/src/policy/tree.rs`
2. Update `smart_splitter.json` to use new field
3. Add test case (Test 6 above) to verify fix
4. Re-run problematic scenario to confirm improved behavior

---

## Success Metrics

### LSM Fix Success
- ✅ Unit tests (Test 1-2) pass
- ✅ Integration test (Test 3) passes
- ✅ Scenario re-run shows `bilateral_offsets > 0` or `cycles_settled > 0`
- ✅ Queue sizes decrease after LSM passes
- ✅ Settlement rate improves (target: >95%)

### Splitting Fix Success
- ✅ Test 5 passes (baseline)
- ✅ Test 6 passes after fix
- ✅ Test 7 passes after fix
- ✅ SMART_SPLITTER scenario shows:
  - At least one `SPLIT` decision in logs
  - Costs < $1M (down from $25M)
  - Settlement rate > 50% (up from 0%)
  - No extreme overdraft accumulation

---

## Execution Timeline

### Phase 1: Investigation (Day 1 - 2 hours)
- [ ] Implement Test 1-4 (LSM tests)
- [ ] Implement Test 5-7 (Splitting tests)
- [ ] Run all tests, document failures
- [ ] Analyze logs and test outputs

### Phase 2: LSM Fix (Day 1-2 - conditional, 2-4 hours)
- [ ] IF tests reveal bug, implement fix
- [ ] Re-run tests to verify
- [ ] Update LSM documentation if needed

### Phase 3: Splitting Fix (Day 2 - 3 hours)
- [ ] Implement `effective_liquidity` field (Rust + policy context)
- [ ] Update `smart_splitter.json` policy
- [ ] Re-run Test 6-7 to verify
- [ ] Document policy design pattern for future policies

### Phase 4: Validation (Day 2-3 - 2 hours)
- [ ] Re-run original problematic scenario
- [ ] Compare metrics: settlement rates, costs, LSM activations
- [ ] Update simulation review document with findings
- [ ] Write post-mortem for future reference

---

## Risk Assessment

### LSM Investigation
- **Risk**: High (Critical feature not working as designed)
- **Confidence in Fix**: Medium-High (issue is likely environmental/integration, not algorithmic)
- **Blast Radius**: Low (LSM is additive, disabling it degrades performance but doesn't break correctness)

### Splitting Fix
- **Risk**: Medium (Policy design flaw, not system bug)
- **Confidence in Fix**: High (root cause clearly identified)
- **Blast Radius**: Low (only affects SMART_SPLITTER policy, other agents unaffected)

---

## Open Questions

1. **LSM Credit Limits**: Should bilateral offsetting be allowed when net sender would exceed credit limit? Current code (line 315-321) says no. Is this correct per GDD?

2. **Policy Robustness**: Should all policies be audited for similar "negative liquidity breaks logic" bugs?

3. **Split Friction Cost**: Is $10 per split realistic? This seems low compared to $1,000 deadline penalties. Should be reviewed.

4. **Overdue Transaction Handling**: Review mentions SMART_SPLITTER transactions became overdue. Should overdue transactions be eligible for LSM settlement?

---

## References

- Game Design Document: `docs/game-design.md`
- LSM Implementation: `backend/src/settlement/lsm.rs`
- Orchestrator: `backend/src/orchestrator/engine.rs`
- SMART_SPLITTER Policy: `backend/policies/smart_splitter.json`
- Existing LSM Tests: `backend/tests/test_lsm.rs`
- Integration Test Pattern: `api/tests/integration/test_overdue_transactions.py`
