# Lab Notes: Castro Experiment

**Researcher**: Claude (Opus 4)
**Date Started**: 2025-12-03
**Project**: LLM-based Policy Optimization for Payment Systems

---

## Overview

This notebook tracks experiments replicating and extending Castro et al. (2025) "Strategic Payment Timing" using LLM-based policy optimization.

See `ARCHITECTURE.md` for technical documentation of the codebase.

---

## Experiment Log

### Entry 1: Initial Setup and Environment Verification
**Date**: 2025-12-03 20:20 UTC
**Objective**: Verify experiment environment and run baseline tests

**Environment Setup**:
- OpenAI API key verified: ✓
- SimCash payment-simulator built: ✓
- Castro experiment dependencies installed: ✓
- Unit tests passing: 89/89 ✓

**Baseline Simulation Test**:
```bash
payment-sim run --config castro_2period_aligned.yaml --seed 42 --quiet
```
Result: 3 transactions, 100% settlement, $290 total cost, 3655 ticks/sec

**Observations**:
- Simulation engine is operational
- Castro-aligned config features (deferred_crediting, deadline_cap_at_eod) are enabled
- Seed policy produces valid baseline results

---

### Entry 2: Experiment 1 - GPT-5.1 Policy Optimization Attempt
**Date**: 2025-12-03 20:24 UTC
**Objective**: Run 2-period deterministic Castro scenario with GPT-5.1

**Configuration**:
- Model: GPT-5.1
- Reasoning effort: high
- Experiment: exp1 (Two-Period Deterministic, Castro-Aligned)
- Max iterations: 25

**Command**:
```bash
python reproducible_experiment.py --experiment exp1 --output results/exp1_gpt51_run1.db --model gpt-5.1 --reasoning high
```

**Results**:
- Iteration 1: $29,000 mean cost, 100% settlement ✓
- Iteration 2-25: ALL FAILED - "All simulations failed, reverting to previous policies"

**Root Cause Analysis**:

The failure stems from a **tree-type/action-type mismatch** in the generated policies:

1. **What the LLM generated** (iter_002_policy_a.json):
   ```json
   "strategic_collateral_tree": {
     "type": "action",
     "action": "Hold",  // ← WRONG ACTION TYPE
     "node_id": "C1_noop_strategic_collateral"
   }
   ```

2. **What was expected**:
   ```json
   "strategic_collateral_tree": {
     "type": "action",
     "action": "HoldCollateral",  // ← CORRECT ACTION TYPE
     "node_id": "C1_noop_strategic_collateral"
   }
   ```

3. **Runtime error**:
   ```
   Invalid action type: Payment/bank action Hold cannot be used in
   collateral decision tree. These actions require separate tree evaluation.
   ```

**Technical Analysis**:

The `STANDARD_CONSTRAINTS` in `parameter_sets.py` only defines:
```python
allowed_actions=["Release", "Hold", "Split"]  # Payment actions only!
```

But SimCash policies have **four tree types** with **different valid action sets**:

| Tree Type | Valid Actions |
|-----------|---------------|
| `payment_tree` | Release, Hold, Split, Drop, etc. |
| `bank_tree` | SetReleaseBudget, SetState, NoAction |
| `strategic_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral |
| `end_of_tick_collateral_tree` | PostCollateral, WithdrawCollateral, HoldCollateral |

The system prompt tells the LLM to generate full multi-tree policies, but only provides the payment action vocabulary. The LLM reasonably uses `Hold` (which it was told is allowed) in collateral trees, not knowing that collateral trees require different actions.

**Validation Gap**:
- Schema validation passes (syntactically valid JSON)
- Tree-type validation is not enforced at constraint level
- Runtime catches the semantic error too late (after LLM call)

**Conclusion**: This is an **architectural bug** in the experiment framework, not an LLM capability issue. The constraint system needs tree-type-aware action validation.

---

### Entry 3: Systematic Root Cause Analysis
**Date**: 2025-12-03 21:00 UTC
**Objective**: Properly investigate the failure instead of applying workarounds

**Principle**: When LLM generates invalid policies, NEVER post-process or retrofit. Instead:
1. Investigate the prompt for confusing instructions
2. Check Pydantic validation classes
3. Verify retry-on-validation-failure mechanism

---

### Entry 4: Investigation Results
**Date**: 2025-12-03 21:15 UTC

#### 1. Prompt Analysis (`generator/robust_policy_agent.py`)

**Finding**: The system prompt is incomplete and misleading.

```python
# Line 149 - Only one action list for all trees:
ACTIONS (use in action nodes):
{action_list}  # Contains: Release, Hold, Split
```

**Problem**:
- Prompt shows only `payment_tree` examples (lines 166-197)
- No examples for `bank_tree`, `strategic_collateral_tree`, `end_of_tick_collateral_tree`
- LLM has no information about tree-specific action vocabularies

**Fix Required**: Add per-tree-type action vocabularies and examples to the prompt.

---

#### 2. Pydantic Schema Analysis (`schemas/dynamic.py`)

**Finding**: Schema uses same `ActionLiteral` for ALL tree types.

```python
# Line 144 - Same actions for all trees:
ActionLiteral = Literal[tuple(constraints.allowed_actions)]

# Line 178-183 - Used in all action nodes:
class DynamicActionNode(BaseModel):
    type: Literal["action"]
    action: ActionLiteral  # ← Same for payment, bank, collateral trees!
```

**Problem**: No tree-type-specific action validation in the Pydantic schema.

**Fix Required**: Create separate action literals for each tree type:
- `PaymentActionLiteral` for payment_tree
- `BankActionLiteral` for bank_tree
- `CollateralActionLiteral` for collateral trees

---

#### 3. Validation Mechanism Analysis

**Finding**: CLI validation has the capability but isn't being used properly.

**Test with `--functional-tests` flag**:
```bash
payment-sim validate-policy iter_002_policy_a.json --functional-tests --format json
```

**Result**:
```json
{
  "valid": true,  // Schema validation passes!
  "functional_tests": {
    "passed": false,
    "results": [{
      "name": "execute_policy",
      "passed": false,
      "message": "Invalid action type: Payment/bank action Hold cannot be used in collateral decision tree."
    }]
  }
}
```

**Key Insight**: Basic validation passes (`valid: true`) but functional tests catch the error!

**Experiment's Current Validation** (`reproducible_experiment.py` line 1210-1220):
```python
result = subprocess.run([
    "payment-sim", "validate-policy", temp_path,
    "--format", "json"
    # ← Missing: --functional-tests flag!
])
```

**Fix Required**: Add `--functional-tests` flag to validation calls in the experiment.

---

#### 4. Retry Mechanism Analysis

**Finding**: Retry mechanism exists (`validate_and_fix_policy()`) but never triggers because basic validation passes.

**Flow**:
1. LLM generates policy with `Hold` in collateral tree
2. Basic validation passes (JSON structure is valid)
3. Policy is saved and simulation runs
4. Simulation fails at runtime
5. Retry mechanism is never invoked because validation "passed"

**Fix Required**: If `--functional-tests` is added, the retry mechanism will properly:
1. Detect the runtime error at validation time
2. Pass the error message to the LLM: "Invalid action type: Payment/bank action Hold..."
3. Allow LLM to regenerate with correct action (`HoldCollateral`)

---

### Entry 5: Required Fixes Summary
**Date**: 2025-12-03 21:30 UTC

Three fixes are needed (in priority order):

| Priority | Component | Fix |
|----------|-----------|-----|
| **P0** | `reproducible_experiment.py` | Add `--functional-tests` to validation calls |
| **P1** | `robust_policy_agent.py` | Add tree-specific action vocabularies to prompt |
| **P2** | `schemas/dynamic.py` | Create per-tree-type action literals |

**Immediate Mitigation**: Fix P0 first - enabling functional tests will allow the existing retry mechanism to work, letting the LLM see and fix its own errors.

---

### Entry 6: P0 Fix Implementation
**Date**: 2025-12-03 21:45 UTC

**Changes Made** to `reproducible_experiment.py`:

1. Added `--functional-tests` flag to validation command (line 1220)
2. Updated response parsing to check `functional_tests.passed` (lines 1235-1242)
3. Extract functional test error messages for LLM retry

**Code Diff**:
```python
# Before:
result = subprocess.run([
    "payment-sim", "validate-policy", temp_path, "--format", "json"
])

# After:
result = subprocess.run([
    "payment-sim", "validate-policy", temp_path, "--format", "json",
    "--functional-tests",  # Catches runtime errors like wrong action types
])

# Added functional test error extraction:
functional_tests = output.get("functional_tests", {})
if functional_tests and not functional_tests.get("passed", True):
    is_valid = False
    for test_result in functional_tests.get("results", []):
        if not test_result.get("passed", True):
            errors.append(f"[FunctionalTest] {test_result.get('message', 'Test failed')}")
```

**Expected Behavior**: Now when LLM generates `Hold` in a collateral tree:
1. Functional test will fail with "Invalid action type: Payment/bank action Hold..."
2. Error is captured and passed to `request_policy_fix_from_llm()`
3. LLM sees the actual error and can generate correct action (`HoldCollateral`)

---

### Entry 7: Experiment 1 Re-run with P0 Fix
**Date**: 2025-12-03 21:48 UTC

**Command**:
```bash
python reproducible_experiment.py --experiment exp1 --output results/exp1_gpt51_run2_with_fix.db --model gpt-5.1 --reasoning high --max-iter 10
```

**Results**:

| Iteration | Mean Cost | Settlement | Notes |
|-----------|-----------|------------|-------|
| 1 | $29,000 | 100% | Baseline with seed policy |
| 2 | $16,500 | 100% | **43% cost reduction!** Bank A fixed after 3 attempts |
| 3-5 | $16,500 | 100% | Converged |

**Key Observations**:

1. **P0 fix is working**: The retry mechanism now triggers because functional tests catch the errors
2. **Bank A was successfully fixed** on iteration 2 after 3 LLM retry attempts
3. **Bank B remained unfixable** - LLM couldn't correct its errors after max retries
4. **Convergence achieved** at 43% cost reduction

**Analysis**:

The experiment now makes progress because:
- Functional tests catch runtime errors (wrong action types)
- Error messages are passed to the LLM for fixing
- Some policies get successfully repaired

However, the LLM still struggles because:
- The prompt doesn't explain tree-specific action vocabularies
- It keeps generating `Hold` instead of `HoldCollateral` for collateral trees
- Fix success rate is ~50% (Bank A fixed, Bank B not)

**Next Steps**: Implement P1 fix (update prompt with tree-specific actions) to improve fix success rate.

---

### Entry 8: P1 Fix Implementation
**Date**: 2025-12-03 22:00 UTC

**Changes Made** to `robust_policy_agent.py` (system prompt):

1. **Added tree-specific action vocabularies** (lines 150-171):
   - `PAYMENT_TREE actions`: Release, Hold, Split
   - `BANK_TREE actions`: SetReleaseBudget, SetState, AddState
   - `COLLATERAL_TREE actions`: PostCollateral, WithdrawCollateral, HoldCollateral

2. **Added explicit common error warning** (lines 169-171):
   ```
   ⚠️ COMMON ERROR: Using "Hold" in collateral trees - this WILL cause validation failure!
      ✗ WRONG:   {"action": "Hold"} in strategic_collateral_tree
      ✓ CORRECT: {"action": "HoldCollateral"} in strategic_collateral_tree
   ```

3. **Added ERROR 4 example** (lines 310-321):
   - Explicit example of wrong/correct actions for collateral trees
   - Explicit example of wrong/correct actions for bank trees

**Expected Improvement**: LLM should now:
1. Know which actions are valid for each tree type BEFORE generating
2. Avoid the Hold/HoldCollateral confusion upfront
3. Require fewer retry attempts

---

