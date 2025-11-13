# Transaction-Trace Testing Plan

**Goal**: Create comprehensive tests that trace individual transactions through policy decision trees, exercising all major decision branches.

**Status**: Planning Phase
**Date**: November 2025

---

## Overview

After completing Phase 1 GREEN with aggregate metrics, we now need fine-grained tests that:
1. Track specific transactions through their lifecycle
2. Exercise all branches of policy decision trees
3. Verify correct policy behavior at decision points
4. Cover edge cases and boundary conditions

---

## Policy Decision Dimensions

### 1. Transaction Characteristics

| Dimension | Values | Impact on Policy |
|-----------|--------|------------------|
| **Priority** | 0-10 | High priority may bypass buffer checks |
| **Deadline** | 1-100 ticks | Urgent = release, far = hold |
| **Amount** | 10k-5M cents | Large = may split, small = release |
| **Divisible** | true/false | Enables splitting strategies |
| **Age** | 0-100 ticks | Overdue triggers special handling |

### 2. Agent State

| Dimension | Values | Impact on Policy |
|-----------|--------|------------------|
| **Balance** | -1M to 10M | Low = conservative, high = aggressive |
| **Effective Liquidity** | With/without credit | Affects release decisions |
| **Queue Depth** | 0-200 | High queue = more selective |
| **Posted Collateral** | 0-5M | Increases effective liquidity |

### 3. Time Context

| Dimension | Values | Impact on Policy |
|-----------|--------|------------------|
| **Day Progress** | 0-100% | Early = conservative, EOD = aggressive |
| **Is EOD Rush** | true/false | Triggers emergency mode |
| **Ticks to EOD** | 0-100 | Affects deadline urgency |

### 4. Cost Factors

| Dimension | Values | Impact on Policy |
|-----------|--------|------------------|
| **Overdraft Cost** | bp/tick | High = avoid credit |
| **Delay Cost** | per tick | High = release faster |
| **Deadline Penalty** | one-time | High = prioritize |
| **Split Friction** | per split | High = avoid splitting |

---

## Policy Decision Trees to Cover

### 1. CautiousLiquidityPreserver

**Major Branches**:
```
Root
├─ EOD Rush?
│  ├─ Past Deadline? → Force Release
│  ├─ Has Liquidity? → Release
│  └─ No Liquidity → Hold
├─ Very Urgent? (<3 ticks)
│  ├─ Can Afford? → Release
│  └─ Penalty vs Credit
│     ├─ Penalty Cheaper → Hold
│     └─ Credit Cheaper → ReleaseWithCredit
├─ Strong Buffer? (2.5× amount)
│  └─ Release
├─ Late Day? (>80%)
│  ├─ Minimal Liquidity → Release
│  └─ No Liquidity → Hold
└─ Early/Mid Day → Hold (Preserving Buffer)
```

**Test Matrix**: 12 decision paths to exercise

### 2. BalancedCostOptimizer

**Major Branches**:
```
Root
├─ EOD Rush?
│  ├─ Past Deadline? → Force Release
│  ├─ Affordable? → Release
│  └─ Penalty vs Credit → Compare costs
├─ Time of Day
│  ├─ Early (<30%)
│  │  ├─ Strong Buffer (1.5×) → Release
│  │  └─ High Priority (≥8) → Check affordability
│  ├─ Mid Day (30-60%)
│  │  ├─ Affordable? → Release
│  │  ├─ Can Split? → Cost comparison
│  │  └─ Credit vs Delay → Compare costs
│  └─ Late Day (>60%)
│     ├─ 1.2× Buffer → Release
│     └─ Urgent (<3 ticks) → Cost comparison
```

**Test Matrix**: 15+ decision paths to exercise

### 3. SmartSplitter

**Major Branches**:
```
Root
├─ Can Split?
│  ├─ Above Threshold? (>250k)
│  │  ├─ Has Min Liquidity? (>80k)
│  │  │  └─ Split Cost vs Delay → Compare
│  │  └─ Insufficient Liquidity → Hold
│  └─ Below Threshold → Standard logic
├─ Affordable?
│  └─ Release
└─ Hold for inflows
```

**Test Matrix**: 8 decision paths to exercise

### 4. GoliathNationalBank

**Major Branches**:
```
Root
├─ Urgent? (≤5 ticks)
│  └─ Release
├─ Is EOD Rush?
│  ├─ Has 0.5× Buffer? → Release
│  └─ No Buffer → Hold
├─ Time of Day
│  ├─ Early (<30%)
│  │  ├─ Has 1.5× Buffer? → Release
│  │  └─ Insufficient → Hold
│  ├─ Mid Day (30-80%)
│  │  ├─ Has 1.0× Buffer? → Release
│  │  └─ Insufficient → Hold
│  └─ Strategic Collateral
│     ├─ Gap Exists? → Post to cover
│     └─ Withdraw Excess
```

**Test Matrix**: 10 decision paths to exercise

---

## Test Design Strategy

### Trace Test Structure

Each test should:
1. **Setup**: Create agent with specific state
2. **Inject**: Add single transaction with known characteristics
3. **Execute**: Run 1-5 ticks to observe decision
4. **Assert**: Verify correct branch taken

Example:
```python
def test_cautious_urgent_with_credit_available():
    """
    Policy: CautiousLiquidityPreserver
    Branch: Very Urgent → Can't Afford → Credit Cheaper → ReleaseWithCredit

    Transaction: Priority 5, Deadline 2 ticks, Amount $1500
    Agent State: Balance $1000, Credit $500

    Expected: Should release with credit since deadline penalty > overdraft cost
    """
```

### Test Naming Convention

```
test_{policy}_{branch_path}_{expected_outcome}
```

Examples:
- `test_cautious_eod_past_deadline_forces_release`
- `test_balanced_midday_split_opportunity_taken`
- `test_splitter_below_threshold_releases`
- `test_goliath_early_insufficient_buffer_holds`

---

## Test Matrix Implementation Plan

### Phase 1: Core Decision Paths (Priority 1)

**CautiousLiquidityPreserver** (8 tests):
- [x] EOD + Past Deadline → Force Release
- [x] EOD + Has Liquidity → Release
- [x] EOD + No Liquidity → Hold
- [ ] Urgent + Can Afford → Release
- [ ] Urgent + Penalty Cheaper → Hold
- [ ] Strong Buffer → Release
- [ ] Late Day + Minimal Liquidity → Release
- [ ] Early Day + No Buffer → Hold

**BalancedCostOptimizer** (10 tests):
- [ ] EOD + Past Deadline → Force Release
- [ ] EOD + Affordable → Release
- [ ] Early + Strong Buffer → Release
- [ ] Early + High Priority + Affordable → Release
- [ ] Mid + Affordable → Release
- [ ] Mid + Split Opportunity + Cost Effective → Split
- [ ] Mid + Credit vs Delay → Choose Credit
- [ ] Late + 1.2× Buffer → Release
- [ ] Late + Urgent + Cost Compare → Optimal choice
- [ ] Late + Minimal Liquidity → Release

**SmartSplitter** (6 tests):
- [ ] Above Threshold + Has Liquidity + Cost Effective → Split
- [ ] Above Threshold + Insufficient Liquidity → Hold
- [ ] Below Threshold + Affordable → Release
- [ ] Below Threshold + Unaffordable → Hold
- [ ] Split Cost > Delay Cost → Hold
- [ ] Multiple Splits → Progressive splitting

**GoliathNationalBank** (8 tests):
- [ ] Urgent (≤5 ticks) → Release
- [ ] EOD + 0.5× Buffer → Release
- [ ] EOD + No Buffer → Hold
- [ ] Early + 1.5× Buffer → Release
- [ ] Early + Insufficient → Hold
- [ ] Mid + 1.0× Buffer → Release
- [ ] Strategic Collateral + Gap → Post
- [ ] Strategic Collateral + Excess → Withdraw

### Phase 2: Edge Cases & Boundaries (Priority 2)

- Boundary conditions (exactly at thresholds)
- Multiple transactions interacting
- State transitions during execution
- Collateral changes mid-decision

### Phase 3: Complex Scenarios (Priority 3)

- Multi-tick traces (transaction lifecycle)
- Policy switching mid-scenario
- Cascading effects (one decision affects next)
- Stress testing (many transactions)

---

## Test File Organization

```
api/tests/integration/
├── test_trace_cautious_policy.py          # CautiousLiquidityPreserver traces
├── test_trace_balanced_policy.py          # BalancedCostOptimizer traces
├── test_trace_splitter_policy.py          # SmartSplitter traces
├── test_trace_goliath_policy.py           # GoliathNationalBank traces
└── test_trace_cross_policy_comparison.py  # Same scenario, different policies
```

---

## Success Criteria

- [ ] All major decision branches covered (80%+ coverage)
- [ ] Each test clearly documents which branch it exercises
- [ ] Tests are deterministic (same seed = same result)
- [ ] Test names clearly describe scenario and expected outcome
- [ ] All tests pass in GREEN phase

---

## Implementation Notes

### Helper Functions Needed

```python
def create_traced_transaction(
    sender: str,
    receiver: str,
    amount: int,
    priority: int = 5,
    deadline: int = 10,
    divisible: bool = False
) -> Dict:
    """Create a transaction with known characteristics for tracing."""

def assert_transaction_status(
    orch: Orchestrator,
    tx_id: str,
    expected_status: str,
    tick: int
):
    """Assert transaction reached expected status."""

def assert_decision_taken(
    orch: Orchestrator,
    agent_id: str,
    tx_id: str,
    expected_decision: str  # "Release", "Hold", "Split", etc.
):
    """Assert policy made expected decision."""
```

---

## Next Steps

1. Create `test_trace_cautious_policy.py` with 8 core tests
2. Implement helper functions for transaction tracing
3. Run tests and verify branch coverage
4. Repeat for other policies
5. Add cross-policy comparison tests

---

**Status**: Ready to implement Phase 1 tests
**Target**: 32 trace tests covering core decision paths across 4 policies
