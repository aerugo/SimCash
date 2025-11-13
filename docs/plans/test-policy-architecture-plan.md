# Test-Specific Policy Architecture Plan

**Status**: In Progress
**Goal**: Create minimal test policies to verify policy engine correctness using strict TDD principles
**Complements**: Production policy trace tests (test_trace_*.py files)

---

## Motivation

### Problem: Production Policies Are Hard to Test Deterministically

Current trace tests for production policies (CautiousLiquidityPreserver, BalancedCostOptimizer) revealed:

1. **Cascading Conditions**: Complex decision trees make it hard to reach specific branches
   - Expected: EOD + past deadline → force release
   - Actual: Liquidity check blocks EOD branch, transaction held

2. **Unpredictable Interactions**: Multiple conditions interact in unexpected ways
   - Expected: Weak buffer → hold
   - Actual: Other conditions (urgency, time-of-day) override buffer check

3. **Limited Field Visibility**: Can't verify individual field calculations in isolation
   - Is `effective_liquidity` calculated correctly?
   - Is `day_progress_fraction` accurate?
   - Are cost computations correct?

### Solution: Test Policies for Unit Testing

Create **minimal, focused policies** that test one feature at a time:

- **Baseline policies**: Verify action execution (always release, always hold)
- **Single-feature policies**: Verify one condition in isolation
- **Field validation policies**: Test field calculations
- **Interaction policies**: Test two features together
- **Edge case policies**: Test boundary conditions

**Separation of Concerns**:
- **Unit tests** (test policies): Verify engine correctness ← **THIS PLAN**
- **Integration tests** (production policies): Verify real-world behavior ← **EXISTING**

---

## TDD Principles for This Work

### Strict TDD Workflow

**Phase 1: RED** - Write failing test
1. Define expected behavior in test docstring
2. Create scenario that should trigger behavior
3. Write assertion for expected outcome
4. Run test → MUST FAIL (no policy exists yet)

**Phase 2: GREEN** - Minimal implementation
1. Create simplest policy JSON that makes test pass
2. Run test → MUST PASS
3. No optimization, no extra features

**Phase 3: REFACTOR** - Improve without changing behavior
1. Clean up policy structure if needed
2. Add comments explaining logic
3. Run test → MUST STILL PASS

**Phase 4: DOCUMENT** - Record findings
1. Update this plan with results
2. Note any engine bugs discovered
3. Document field behavior observed

### Test Structure

Each test follows this pattern:

```python
def test_feature_name_expected_behavior(self):
    """
    Policy: test_feature_name
    Feature: [Single feature being tested]

    Scenario: [Specific setup]
    Expected: [Predicted outcome]
    Verifies: [What this proves about engine]
    """
    # RED: This test doesn't exist yet
    scenario = (
        ScenarioBuilder("TestFeature_Scenario")
        .with_specific_setup()
        .build()
    )

    policy = load_json_policy("test_feature_name")

    expectations = OutcomeExpectation(
        settlement_rate=Exact(1.0),  # Or whatever is expected
    )

    test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
    result = test.run()

    assert result.passed, "Feature should behave as documented"
```

---

## Test Policy Categories

### Tier 1: Baseline Policies (Verify Action Execution)

**Purpose**: Prove that actions execute correctly without any conditions

| Policy File | Behavior | Verifies |
|-------------|----------|----------|
| `test_always_release.json` | No conditions, always Release | Release action works |
| `test_always_hold.json` | No conditions, always Hold | Hold action works |
| `test_always_release_with_credit.json` | No conditions, always ReleaseWithCredit | Credit action works |

**TDD Cycle Example**:
1. RED: Write test expecting 100% settlement for `test_always_release`
2. GREEN: Create policy with single Release action
3. Run test → should pass
4. REFACTOR: Add documentation to policy JSON
5. DOCUMENT: Record that Release action settles transactions

### Tier 2: Single-Feature Policies (Verify Conditions)

**Purpose**: Test one decision condition in isolation

#### 2A. EOD Rush Detection

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_eod_only.json` | `is_eod_rush == 1.0` → Release, else Hold | EOD flag works |

**Test Scenarios**:
- EOD rush active (tick >= 80% of day) → expect Release
- Early day (tick < 80% of day) → expect Hold

#### 2B. Urgency (Ticks to Deadline)

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_urgency_only.json` | `ticks_to_deadline <= 3.0` → Release, else Hold | Urgency calculation |

**Test Scenarios**:
- Transaction with 2 ticks to deadline → expect Release
- Transaction with 10 ticks to deadline → expect Hold

#### 2C. Affordability (Liquidity Check)

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_affordability_only.json` | `effective_liquidity >= remaining_amount` → Release, else Hold | Liquidity calculation |

**Test Scenarios**:
- Balance $15k, transaction $10k → expect Release
- Balance $5k, transaction $10k → expect Hold

#### 2D. Buffer Check

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_buffer_only.json` | `effective_liquidity >= remaining_amount * 2.0` → Release, else Hold | Buffer calculation |

**Test Scenarios**:
- Balance $20k, transaction $10k (2× buffer) → expect Release
- Balance $15k, transaction $10k (1.5× buffer) → expect Hold

#### 2E. Time of Day

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_time_of_day_only.json` | `day_progress_fraction > 0.5` → Release, else Hold | Day progress calculation |

**Test Scenarios**:
- Tick 60 of 100 (60% progress) → expect Release
- Tick 30 of 100 (30% progress) → expect Hold

#### 2F. Cost Comparison

| Policy File | Condition | Verifies |
|-------------|-----------|----------|
| `test_cost_comparison_only.json` | `cost_delay_this_tick < cost_overdraft_this_amount_one_tick` → Hold, else Release | Cost calculations |

**Test Scenarios**:
- Small transaction, high overdraft rate → expect Hold (delay cheaper)
- Large transaction, low overdraft rate → expect Release (credit cheaper)

### Tier 3: Two-Feature Policies (Verify Interactions)

**Purpose**: Test how two conditions interact

| Policy File | Conditions | Verifies |
|-------------|------------|----------|
| `test_eod_and_liquidity.json` | EOD rush AND affordable → Release, else Hold | AND logic |
| `test_urgent_or_affordable.json` | Urgent OR affordable → Release, else Hold | OR logic |
| `test_buffer_then_time.json` | If buffer, release; else check time | Nested conditions |

### Tier 4: Field Validation Policies (Verify Calculations)

**Purpose**: Test that computed fields return expected values

| Policy File | Computation | Verifies |
|-------------|-------------|----------|
| `test_compute_multiply.json` | `remaining_amount * 2.0` | Multiplication |
| `test_compute_divide.json` | `balance / 2.0` | Division |
| `test_compute_min.json` | `min(balance, remaining_amount)` | Min function |
| `test_compute_max.json` | `max(cost_delay, cost_overdraft)` | Max function |

### Tier 5: Edge Case Policies (Verify Boundaries)

**Purpose**: Test boundary conditions and edge cases

| Policy File | Edge Case | Verifies |
|-------------|-----------|----------|
| `test_zero_deadline.json` | `ticks_to_deadline == 0.0` | Zero handling |
| `test_exactly_at_threshold.json` | `effective_liquidity == remaining_amount` | Equality edge |
| `test_negative_balance.json` | Balance < 0 (overdraft) | Negative handling |

---

## Implementation Plan

### Phase 1: Setup (RED) ✅ Complete when test file exists with failing tests

**Tasks**:
1. Create directory: `backend/policies/test_policies/`
2. Create test file: `api/tests/integration/test_policy_engine_unit.py`
3. Add helper function to load test policies
4. Write 3 baseline tests (always_release, always_hold, always_release_with_credit)
5. Run tests → ALL MUST FAIL (policies don't exist)

**Success Criteria**: Test file exists, runs, and fails with "policy not found" errors

### Phase 2: Baseline Policies (GREEN) ✅ Complete when 3/3 baseline tests pass

**Tasks**:
1. Create `test_always_release.json`
2. Run test → should pass
3. Create `test_always_hold.json`
4. Run test → should pass
5. Create `test_always_release_with_credit.json`
6. Run test → should pass

**Success Criteria**: 3/3 baseline tests passing

### Phase 3: Single-Feature Policies (GREEN) ✅ Complete when 6/6 single-feature tests pass

**Tasks**:
1. Write test for `test_eod_only.json` (RED)
2. Create policy (GREEN)
3. Write test for `test_urgency_only.json` (RED)
4. Create policy (GREEN)
5. Write test for `test_affordability_only.json` (RED)
6. Create policy (GREEN)
7. Write test for `test_buffer_only.json` (RED)
8. Create policy (GREEN)
9. Write test for `test_time_of_day_only.json` (RED)
10. Create policy (GREEN)
11. Write test for `test_cost_comparison_only.json` (RED)
12. Create policy (GREEN)

**Success Criteria**: 6/6 single-feature tests passing

### Phase 4: Two-Feature Policies (GREEN) ✅ Complete when 3/3 interaction tests pass

**Tasks**:
1. Write test for `test_eod_and_liquidity.json` (RED)
2. Create policy (GREEN)
3. Write test for `test_urgent_or_affordable.json` (RED)
4. Create policy (GREEN)
5. Write test for `test_buffer_then_time.json` (RED)
6. Create policy (GREEN)

**Success Criteria**: 3/3 interaction tests passing

### Phase 5: Field Validation (GREEN) ✅ Complete when 4/4 computation tests pass

**Tasks**:
1. Write test for `test_compute_multiply.json` (RED)
2. Create policy (GREEN)
3. Write test for `test_compute_divide.json` (RED)
4. Create policy (GREEN)
5. Write test for `test_compute_min.json` (RED)
6. Create policy (GREEN)
7. Write test for `test_compute_max.json` (RED)
8. Create policy (GREEN)

**Success Criteria**: 4/4 computation tests passing

### Phase 6: Edge Cases (GREEN) ✅ Complete when 3/3 edge case tests pass

**Tasks**:
1. Write test for `test_zero_deadline.json` (RED)
2. Create policy (GREEN)
3. Write test for `test_exactly_at_threshold.json` (RED)
4. Create policy (GREEN)
5. Write test for `test_negative_balance.json` (RED)
6. Create policy (GREEN)

**Success Criteria**: 3/3 edge case tests passing

### Phase 7: Documentation & Findings (REFACTOR)

**Tasks**:
1. Document all findings in this plan
2. Update CLAUDE.md with test policy usage
3. Note any engine bugs discovered
4. Create summary of field behavior

---

## Test Count Matrix

| Category | Policies | Test Scenarios | Total Tests |
|----------|----------|----------------|-------------|
| Baseline | 3 | 1 each | 3 |
| Single-Feature | 6 | 2 each | 12 |
| Two-Feature | 3 | 2 each | 6 |
| Field Validation | 4 | 2 each | 8 |
| Edge Cases | 3 | 2 each | 6 |
| **TOTAL** | **19** | **~2 avg** | **35** |

---

## Expected Findings

### Questions These Tests Will Answer

1. **Does `is_eod_rush` accurately reflect day progress?**
2. **Is `ticks_to_deadline` calculated from transaction deadline or arrival?**
3. **What exactly is `effective_liquidity`?** (balance? balance + credit?)
4. **Are cost fields computed per-tick or per-day?**
5. **Do AND/OR conditions short-circuit?**
6. **What happens with zero/negative values?**

### Potential Bugs to Discover

- Field calculations incorrect
- Conditions not evaluating properly
- Actions not executing as expected
- Edge cases causing panics/errors

---

## Integration with Existing Tests

### Relationship to Production Policy Trace Tests

**Test Policies (Unit)**: Verify engine correctness
- File: `test_policy_engine_unit.py`
- Policies: `backend/policies/test_policies/*.json`
- Purpose: Prove policy engine works correctly
- Scope: Individual features in isolation

**Production Policies (Integration)**: Verify real-world behavior
- Files: `test_trace_cautious_policy.py`, `test_trace_balanced_policy.py`
- Policies: `backend/policies/*.json` (production)
- Purpose: Understand how policies behave in practice
- Scope: Complex decision trees with multiple interacting conditions

**Both Are Valuable**:
- Unit tests → confidence in engine
- Integration tests → confidence in policies

---

## Success Criteria

### Phase 1 Complete When:
- [ ] Test file exists with 3 baseline tests
- [ ] All 3 tests fail with "policy not found"
- [ ] Test structure follows TDD pattern

### Phase 2 Complete When:
- [ ] 3 baseline policy JSON files created
- [ ] All 3 baseline tests passing
- [ ] Committed and pushed

### Phase 3 Complete When:
- [ ] 6 single-feature policy JSON files created
- [ ] 12 single-feature tests passing (2 scenarios each)
- [ ] Committed and pushed

### Phase 4 Complete When:
- [ ] 3 two-feature policy JSON files created
- [ ] 6 interaction tests passing (2 scenarios each)
- [ ] Committed and pushed

### Phase 5 Complete When:
- [ ] 4 field validation policy JSON files created
- [ ] 8 computation tests passing (2 scenarios each)
- [ ] Committed and pushed

### Phase 6 Complete When:
- [ ] 3 edge case policy JSON files created
- [ ] 6 edge case tests passing (2 scenarios each)
- [ ] Committed and pushed

### ALL PHASES Complete When:
- [ ] 19 test policies created
- [ ] 35 unit tests passing
- [ ] Findings documented
- [ ] No engine bugs discovered (or all bugs filed/fixed)

---

## Next Steps

1. ✅ Create this plan document
2. ⏭️ Start Phase 1: Write baseline tests (RED)
3. Continue through phases following strict TDD

**Status**: Ready to begin Phase 1
**Next Command**: Create test file with 3 baseline tests
