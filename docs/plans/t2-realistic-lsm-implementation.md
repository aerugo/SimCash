# T2-Realistic LSM Implementation Plan

**Status**: Planning
**Priority**: High
**Complexity**: Medium
**Estimated Effort**: 3-5 days
**Date**: 2025-11-05

---

## Executive Summary

Our current LSM implementation partially models T2 behavior but has critical gaps in handling **unequal payment values in multilateral cycles**. This plan brings our LSM into full alignment with T2 RTGS specifications.

**Key Finding from T2 Research**: T2 supports "partial netting of unequal payment values" - cycles can settle groups of transactions without requiring exact value matching, as long as each participant can cover their net position. Individual payments are NEVER split - they settle in full or not at all.

---

## Current Implementation Analysis

### ✅ What's Correct

**Bilateral Offsetting** (lines 193-381 in `lsm.rs`):
- ✅ Correctly handles unequal amounts (A→B 500k, B→A 300k)
- ✅ Settles ALL transactions in both directions
- ✅ Checks if net sender can cover net difference (line 316-322)
- ✅ Uses adjust_balance for coordinated settlement
- **Verdict**: Fully compliant with T2 specs

**Basic Cycle Detection** (lines 403-507):
- ✅ DFS-based cycle detection
- ✅ Finds simple cycles (no repeated nodes)
- ✅ Limits cycle length for performance
- **Verdict**: Algorithm is sound

### ❌ What's Missing

**1. Cycle Settlement with Unequal Amounts** (lines 523-581):

Current behavior:
```rust
// settle_cycle() settles only MIN amount on cycle
let settle_amount = cycle.min_amount;  // Line 528
```

Problem: If cycle has payments [500k, 800k, 700k], we only settle 500k from each, leaving partial amounts in queue. This is NOT how T2 works.

**T2 behavior**:
- Settle FULL amount of each transaction in the cycle
- Each participant sends and receives DIFFERENT amounts
- Net position per participant must be covered by available liquidity
- All-or-nothing: If ANY participant can't cover their net, NONE of the cycle settles

**2. Net Position Calculation**:

Current: Assumes net-zero (line 549 comment)
```rust
// IMPORTANT: Use adjust_balance instead of debit/credit because cycle settlement
// is net-zero - each agent sends and receives the same amount around the cycle
```

Problem: This is only true for EQUAL amounts. For unequal amounts, each participant has a NON-ZERO net position.

**T2 behavior**:
```
Cycle: A→B (500k), B→C (800k), C→A (700k)
Net positions:
- A: sends 500k, receives 700k → net +200k (inflow)
- B: sends 800k, receives 500k → net -300k (outflow, needs liquidity!)
- C: sends 700k, receives 800k → net +100k (inflow)

Settlement check: Can B cover -300k with balance + credit? If yes, settle ALL three payments. If no, cycle fails.
```

**3. All-or-Nothing Execution**:

Current: Settles transactions one-by-one (lines 550-574), commits as it goes

Problem: If transaction #3 in cycle fails, transactions #1-2 are already settled. Violates atomicity.

**T2 behavior**: Check if entire cycle is feasible BEFORE making any balance changes. Only commit if all checks pass.

---

## T2 LSM Specification Summary

From `docs/lsm-in-t2.md`:

### Key Principles

1. **No Partial Settlement of Individual Payments** (line 5):
   > "T2 does not split or partially execute individual payment instructions – each payment order is settled in full or not at all"

2. **Bilateral Offsetting with Unequal Values** (line 9):
   > "If a counter-payment exists, T2 will attempt to settle both payments together, thereby offsetting their values and reducing the net liquidity needed. This is done even if the two payments are not exactly equal – any difference (net debit) must be covered by the owing bank's available balance or credit line"

3. **Multilateral Cycles with Unequal Values** (line 19):
   > "T2's multilateral LSM does not require exact value matching of payments; it supports offsetting among unequal payment values by using available liquidity to cover any net imbalances. In other words, the algorithm seeks to maximize settlement volume with minimal liquidity by allowing partial netting of obligations, as long as each bank's net outgoing amount in the group is fully funded"

4. **All-or-Nothing Cycle Settlement** (line 24):
   > "When a multilateral optimisation is successful, all selected payments settle simultaneously on a gross basis (within the same logical second). If one transfer fails due to insufficient funds or limit breach, then none of the grouped payments are executed in that attempt"

---

## Implementation Plan

### Phase 1: Net Position Calculation (1 day)

**Goal**: Calculate each participant's net position in a multilateral cycle

**Approach**:
```rust
/// Calculate net position for each agent in a cycle
///
/// Net position = sum(incoming) - sum(outgoing) for each agent
/// Positive = net inflow, Negative = net outflow (needs liquidity)
fn calculate_cycle_net_positions(
    state: &SimulationState,
    cycle: &Cycle,
) -> HashMap<String, i64> {
    let mut net_positions: HashMap<String, i64> = HashMap::new();

    // Build flows from cycle transactions
    for tx_id in &cycle.transactions {
        let tx = state.get_transaction(tx_id).unwrap();
        let sender = tx.sender_id();
        let receiver = tx.receiver_id();
        let amount = tx.remaining_amount();

        // Sender has outflow
        *net_positions.entry(sender.to_string()).or_insert(0) -= amount;
        // Receiver has inflow
        *net_positions.entry(receiver.to_string()).or_insert(0) += amount;
    }

    net_positions
}
```

**Validation**:
- Sum of all net positions must equal zero (conservation)
- Test with examples from T2 docs

**Files to modify**:
- `backend/src/settlement/lsm.rs`: Add helper function

---

### Phase 2: Cycle Feasibility Check (1 day)

**Goal**: Verify all participants can cover their net positions BEFORE settlement

**Approach**:
```rust
/// Check if cycle can settle given agent liquidity constraints
///
/// Returns Ok(()) if all agents with net outflow can cover it
/// Returns Err(reason) with first blocking agent
fn check_cycle_feasibility(
    state: &SimulationState,
    cycle: &Cycle,
    net_positions: &HashMap<String, i64>,
) -> Result<(), CycleFeasibilityError> {
    for (agent_id, net_position) in net_positions {
        if *net_position < 0 {
            // Agent has net outflow - check liquidity
            let agent = state.get_agent(agent_id)
                .ok_or(CycleFeasibilityError::AgentNotFound)?;

            let available_liquidity = agent.balance() + (agent.credit_limit() as i64);
            let required_liquidity = net_position.abs();

            if available_liquidity < required_liquidity {
                return Err(CycleFeasibilityError::InsufficientLiquidity {
                    agent_id: agent_id.clone(),
                    required: required_liquidity,
                    available: available_liquidity,
                });
            }
        }
    }

    Ok(())
}

#[derive(Debug)]
enum CycleFeasibilityError {
    AgentNotFound,
    InsufficientLiquidity {
        agent_id: String,
        required: i64,
        available: i64,
    },
}
```

**Tests**:
- Cycle with sufficient liquidity for all net outflows → Ok
- Cycle with one agent lacking liquidity → Err with agent ID
- Cycle with perfect net-zero positions → Ok

**Files to modify**:
- `backend/src/settlement/lsm.rs`: Add feasibility check function and error type

---

### Phase 3: Two-Phase Cycle Settlement (1-2 days)

**Goal**: Atomic all-or-nothing cycle settlement

**Approach**:

Replace current `settle_cycle()` with two-phase commit:

```rust
/// Settle cycle with unequal payment values (T2-compliant)
///
/// Phase 1: Feasibility check (no state changes)
/// Phase 2: Atomic settlement (all or nothing)
pub fn settle_cycle_t2(
    state: &mut SimulationState,
    cycle: &Cycle,
    tick: usize,
) -> Result<CycleSettlementResult, SettlementError> {
    // Phase 1: Calculate net positions
    let net_positions = calculate_cycle_net_positions(state, cycle);

    // Validate conservation (net positions sum to zero)
    let sum: i64 = net_positions.values().sum();
    if sum != 0 {
        return Err(SettlementError::InvalidCycle {
            reason: format!("Net positions don't sum to zero: {}", sum),
        });
    }

    // Phase 1: Check feasibility BEFORE any changes
    check_cycle_feasibility(state, cycle, &net_positions)?;

    // Phase 2: All checks passed - commit settlement atomically
    let mut transactions_settled = 0;
    let mut total_value = 0i64;

    for tx_id in &cycle.transactions {
        let tx = state.get_transaction(tx_id).unwrap();
        let sender_id = tx.sender_id().to_string();
        let receiver_id = tx.receiver_id().to_string();
        let amount = tx.remaining_amount(); // FULL amount, not min

        // Settle full transaction amount
        state.get_agent_mut(&sender_id).unwrap()
            .adjust_balance(-(amount as i64));
        state.get_agent_mut(&receiver_id).unwrap()
            .adjust_balance(amount as i64);
        state.get_transaction_mut(tx_id).unwrap()
            .settle(amount, tick)?;

        // Remove from Queue 2
        state.rtgs_queue_mut().retain(|id| id != tx_id);

        transactions_settled += 1;
        total_value += amount;
    }

    Ok(CycleSettlementResult {
        cycle_length: cycle.agents.len() - 1,
        settled_value: total_value, // Sum of all transaction values
        transactions_affected: transactions_settled,
        net_positions: net_positions, // NEW: Track for analysis
    })
}
```

**Key Changes**:
1. Settle FULL transaction amounts (not min)
2. Check feasibility before ANY state changes
3. Return net positions for metrics/logging

**Backward Compatibility**:
- Keep old `settle_cycle()` for comparison tests
- Add feature flag: `lsm_t2_compliant` (default true)
- Gradual migration path

**Tests**:
- Cycle with equal amounts → same behavior as before
- Cycle with unequal amounts → settles full values
- Cycle where one agent can't cover net → no settlements, all remain in queue
- Determinism: Same seed → same cycle selection → same results

**Files to modify**:
- `backend/src/settlement/lsm.rs`: Rewrite `settle_cycle()` → `settle_cycle_t2()`
- `backend/src/settlement/lsm.rs`: Update `LsmConfig` with `t2_compliant: bool` flag
- `backend/src/settlement/lsm.rs`: Update `run_lsm_pass()` to call new function

---

### Phase 4: Enhanced Metrics & Logging (0.5 days)

**Goal**: Track LSM efficacy with unequal payment cycles

**New Metrics**:
```rust
#[derive(Debug, Clone, PartialEq)]
pub struct CycleSettlementResult {
    pub cycle_length: usize,
    pub settled_value: i64,
    pub transactions_affected: usize,

    // NEW: Net position tracking
    pub net_positions: HashMap<String, i64>,
    pub max_net_outflow: i64,  // Largest net outflow in cycle
    pub liquidity_saved: i64,  // Gross value - max net outflow
}

#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct LsmCycleEvent {
    // ... existing fields ...

    // NEW: Unequal payment tracking
    pub payment_amounts: Vec<i64>,  // Individual payment values
    pub net_positions: HashMap<String, i64>,  // Net per agent
    pub max_net_outflow: i64,
    pub liquidity_efficiency: f64,  // (gross - net) / gross
}
```

**Logging Enhancements**:
```rust
// Log cycle details with net positions
tracing::info!(
    "LSM: Settled {}-agent cycle, total value {}k, max net outflow {}k, efficiency {:.1}%",
    cycle.agents.len() - 1,
    result.settled_value / 1000,
    result.max_net_outflow / 1000,
    result.liquidity_efficiency * 100.0
);
```

**Files to modify**:
- `backend/src/settlement/lsm.rs`: Enhance result types
- `backend/src/orchestrator/engine.rs`: Log enhanced metrics

---

### Phase 5: Comprehensive Testing (1 day)

**Test Scenarios**:

**5.1 Bilateral Offsetting (Sanity Check)**:
```rust
#[test]
fn test_bilateral_offset_unequal_amounts_already_works() {
    // A→B 500k, B→A 300k
    // Should settle both, net 200k A→B
    // Already implemented correctly - verify behavior unchanged
}
```

**5.2 Multilateral Cycle - Equal Amounts**:
```rust
#[test]
fn test_cycle_equal_amounts_backward_compatible() {
    // A→B→C→A, all 500k
    // Net positions all zero
    // Should settle identical to old implementation
}
```

**5.3 Multilateral Cycle - Unequal Amounts (NEW)**:
```rust
#[test]
fn test_cycle_unequal_amounts_t2_compliant() {
    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),    // balance 0, credit 500k
        ("B", 300_000, 0),    // balance 300k, credit 0
        ("C", 0, 200_000),    // balance 0, credit 200k
    ]);

    // Create cycle: A→B (500k), B→C (800k), C→A (700k)
    let tx1 = create_queued_transaction("A", "B", 500_000);
    let tx2 = create_queued_transaction("B", "C", 800_000);
    let tx3 = create_queued_transaction("C", "A", 700_000);

    // Calculate expected net positions:
    // A: -500k + 700k = +200k (net inflow)
    // B: -800k + 500k = -300k (net outflow, needs 300k liquidity)
    // C: -700k + 800k = +100k (net inflow)

    // B has 300k balance, so can cover -300k net → cycle should settle

    let cycle = Cycle {
        agents: vec!["A", "B", "C", "A"],
        transactions: vec![tx1.id(), tx2.id(), tx3.id()],
        min_amount: 500_000,  // Min is now irrelevant
        total_value: 2_000_000,
    };

    let result = settle_cycle_t2(&mut state, &cycle, 5).unwrap();

    // Verify ALL transactions settled at FULL value
    assert_eq!(result.transactions_affected, 3);
    assert_eq!(result.settled_value, 2_000_000); // Sum of all

    // Verify net positions
    assert_eq!(result.net_positions["A"], 200_000);
    assert_eq!(result.net_positions["B"], -300_000);
    assert_eq!(result.net_positions["C"], 100_000);

    // Verify final balances match net positions
    assert_eq!(state.get_agent("A").unwrap().balance(), 200_000);
    assert_eq!(state.get_agent("B").unwrap().balance(), 0);
    assert_eq!(state.get_agent("C").unwrap().balance(), 100_000);
}
```

**5.4 Cycle Feasibility Failure**:
```rust
#[test]
fn test_cycle_insufficient_liquidity_fails() {
    let mut state = create_test_state_with_agents(vec![
        ("A", 0, 500_000),
        ("B", 200_000, 0),    // Only 200k, needs 300k
        ("C", 0, 200_000),
    ]);

    // Same cycle as above: B needs 300k but only has 200k
    let cycle = create_unequal_cycle();

    let result = settle_cycle_t2(&mut state, &cycle, 5);

    // Should fail due to B's insufficient liquidity
    assert!(matches!(result, Err(SettlementError::AgentError(_))));

    // Verify NO transactions settled (atomicity)
    assert_eq!(state.rtgs_queue().len(), 3); // All still queued
}
```

**5.5 Complex Cycle (4+ agents)**:
```rust
#[test]
fn test_four_agent_cycle_unequal() {
    // A→B (1M), B→C (1.2M), C→D (800k), D→A (900k)
    // Net: A=+900-1000=-100k, B=+1000-1200=-200k, C=+1200-800=+400k, D=+800-900=-100k
    // All net outflows are small, should settle with minimal liquidity
}
```

**5.6 Determinism**:
```rust
#[test]
fn test_lsm_determinism_with_unequal_cycles() {
    // Run simulation twice with same seed
    // Verify identical cycle detection and settlement order
}
```

**Files to create**:
- `backend/tests/test_lsm_t2_compliant.rs`: New test file (200+ lines)

---

## Success Criteria

### Functional Requirements

- ✅ Bilateral offsetting with unequal amounts (already works)
- ✅ Multilateral cycles settle FULL transaction values (not min)
- ✅ Net position calculation correct for all participants
- ✅ Feasibility check BEFORE any state changes
- ✅ All-or-nothing atomicity (no partial cycle settlements)
- ✅ Conservation invariant (net positions sum to zero)
- ✅ Credit limit enforcement for agents with net outflow

### Performance Requirements

- No significant slowdown vs. current implementation
- Cycle detection remains O(V × E) with pruning
- Feasibility check is O(participants) - negligible

### Testing Requirements

- All existing tests pass (backward compatibility)
- 8+ new tests for unequal cycle scenarios
- Determinism verified across 100 runs
- Edge cases covered (single-agent cycles, self-loops, etc.)

---

## Risks & Mitigations

### Risk 1: Breaking Existing Behavior

**Mitigation**:
- Keep old implementation as `settle_cycle_legacy()`
- Add feature flag for gradual migration
- Run both implementations in parallel (compare results)

### Risk 2: Performance Degradation

**Mitigation**:
- Profile before/after with realistic workloads
- Optimize net position calculation (single pass)
- Cache feasibility checks for repeated cycles

### Risk 3: Introducing Non-Determinism

**Mitigation**:
- No new HashMap iteration (already using Vec for cycles)
- No floating-point arithmetic in core logic
- Extensive determinism tests

---

## Integration Points

### Phase 10 (Persistence)

LsmCycleEvent will be persisted to `lsm_cycles` table:
```sql
CREATE TABLE lsm_cycles (
    simulation_id TEXT,
    tick INTEGER,
    day INTEGER,
    cycle_type TEXT,  -- 'bilateral' or 'multilateral'
    cycle_length INTEGER,
    agents TEXT,  -- JSON array
    transactions TEXT,  -- JSON array
    payment_amounts TEXT,  -- NEW: JSON array of individual amounts
    net_positions TEXT,  -- NEW: JSON object {agent: net_value}
    settled_value INTEGER,
    total_value INTEGER,
    liquidity_saved INTEGER,  -- NEW: total_value - max_net_outflow
    PRIMARY KEY (simulation_id, tick, cycle_type, cycle_length)
);
```

### Phase 11 (LLM Manager)

Enhanced LSM metrics enable policy learning:
- "Your policy waited for liquidity, but LSM could have settled via 3-agent cycle with only 200k net outflow"
- "Submit to RTGS earlier - your payments are blocking a potential offsetting cycle"

---

## Documentation Updates

### Files to Update

1. **`docs/grand_plan.md`**:
   - Part II, Section 2.6: Update LSM description
   - Add: "LSM Settlement with Unequal Payment Values (T2-Compliant)" subsection

2. **`docs/game_concept_doc.md`**:
   - Section 4.3 (Central RTGS engine): Update LSM description
   - Add example of unequal cycle settlement
   - Clarify: No transaction splitting at RTGS level

3. **`backend/src/settlement/lsm.rs`**:
   - Update module-level doc comment
   - Add T2 compliance references
   - Link to `docs/lsm-in-t2.md`

4. **`CHANGELOG.md`**:
   - Add entry for Phase 3.5: "T2-Compliant LSM with Unequal Payment Values"

---

## Timeline

| Phase | Task | Duration | Dependencies |
|-------|------|----------|--------------|
| 1 | Net Position Calculation | 1 day | None |
| 2 | Cycle Feasibility Check | 1 day | Phase 1 |
| 3 | Two-Phase Cycle Settlement | 1-2 days | Phase 2 |
| 4 | Enhanced Metrics & Logging | 0.5 days | Phase 3 |
| 5 | Comprehensive Testing | 1 day | Phase 3, 4 |
| 6 | Documentation Updates | 0.5 days | Phase 5 |

**Total**: 5-6 days (1 full work week)

---

## Next Steps

1. ✅ Review this plan with stakeholders
2. Create feature branch: `feature/lsm-t2-compliant`
3. Implement Phase 1 (net positions)
4. Implement Phase 2 (feasibility check)
5. Implement Phase 3 (two-phase settlement)
6. Run full test suite + new tests
7. Update documentation
8. Merge to main with feature flag enabled

---

## References

1. **Primary Source**: `docs/lsm-in-t2.md` - T2 RTGS LSM behavior research
2. **Current Code**: `backend/src/settlement/lsm.rs` - lines 193-698
3. **Game Design**: `docs/game_concept_doc.md` - Section 4.3
4. **ECB T2 Docs**: User Requirements Document v3.0 (cited in lsm-in-t2.md)
5. **BIS Working Paper 1089**: Intraday liquidity around the world

---

*Plan Version: 1.0*
*Author: Claude Code*
*Last Updated: 2025-11-05*
