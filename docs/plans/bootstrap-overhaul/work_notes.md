# Bootstrap Overhaul - Work Notes

## Session Log

### Session 1: 2025-12-12

**Goal**: Analyze current implementation, create comprehensive plan

**Completed**:
1. ✅ Analyzed current `OptimizationLoop` implementation in `optimization.py`
2. ✅ Identified key issues:
   - Bootstrap baseline runs BEFORE iterations (incorrect)
   - Seeds derived on-the-fly, not pre-generated
   - All agents share same sample seeds
   - Progress tracked by absolute costs, not deltas
3. ✅ Created overview plan in `overview.md`
4. ✅ Created this work_notes.md

**Next Steps**:
1. Create Phase 1 detailed plan (`phases/phase_1.md`)
2. Implement `SeedMatrix` class with TDD
3. Unit tests for seed derivation and reproducibility

**Key Files Analyzed**:
- `api/payment_simulator/experiments/runner/optimization.py` - Main loop (1512 lines)
- `api/payment_simulator/experiments/config/experiment_config.py` - Config parsing
- `experiments/castro/experiments/exp2.yaml` - Example experiment config

**Key Findings**:

1. **Current Seed Derivation** (optimization.py:937-953):
```python
def _derive_sample_seed(self, sample_idx: int) -> int:
    key = f"{self._config.master_seed}:sample:{sample_idx}"
    hash_bytes = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)
```
- Uses SHA256 hash of `{master_seed}:sample:{sample_idx}`
- Same seeds for all agents, all iterations
- No per-agent or per-iteration isolation

2. **Current Evaluation Flow** (optimization.py:810-935):
```python
async def _evaluate_policies(self):
    # Called at START of each iteration (before optimization)
    for sample_idx in range(num_samples):
        seed = self._derive_sample_seed(sample_idx)
        enriched = self._run_simulation_with_events(seed, sample_idx)
        # ...
```
- Evaluates current policies BEFORE generating new ones
- Used for LLM context (best/worst seed)
- Does NOT compare old vs new policies

3. **Current Acceptance Logic** (optimization.py:1375-1426):
```python
async def _should_accept_policy(...):
    # Evaluate both policies on same samples
    old_costs = self._evaluate_policy_on_samples(old_policy, ...)
    new_costs = self._evaluate_policy_on_samples(new_policy, ...)

    # Compute deltas
    deltas = [old - new for old, new in zip(old_costs, new_costs)]
    mean_delta = sum(deltas) / len(deltas)

    return mean_delta > 0  # Accept if positive
```
- Already uses paired comparison! Good.
- But runs AFTER both initial eval and policy generation
- Uses same seeds as initial evaluation (no isolation)

**Insight**: The paired comparison logic is actually correct! The issue is:
1. The "Bootstrap Baseline" before iteration 1 is confusing/unnecessary
2. Seeds are shared across agents (should be isolated)
3. Progress tracking uses absolute costs, not delta sums

---

## Current Status

**Phase**: ALL PHASES COMPLETE ✅

### Final Summary (2025-12-12)

**Commits:**
1. `00ae359` - Overhaul bootstrap evaluation for correct paired comparison (Phase 1 & 2)
2. `a11c075` - Add verbose output for bootstrap delta evaluation (Phase 3)
3. `afceeb4` - Add integration tests for OptimizationLoop SeedMatrix integration (Phase 4)

**Test Results:**
- 14 SeedMatrix unit tests ✅
- 15 bootstrap overhaul integration tests ✅
- 206+ existing tests pass (3 pre-existing failures unrelated to this work)

**All Success Criteria Met:**
1. ✅ Bootstrap evaluation runs AFTER policy generation
2. ✅ Each agent has independent seed stream per iteration
3. ✅ Delta sums are tracked and displayed correctly
4. ✅ Determinism preserved (same seed = same results)
5. ✅ All existing tests pass (except pre-existing failures)
6. ✅ New tests cover the correct algorithm

---

## Previous Phase

**Phase**: Phase 3 COMPLETE, verbose output updated

### Phase 3 Completion Summary (2025-12-12)

**Files Modified:**
- `api/payment_simulator/experiments/runner/verbose.py`:
  - Added `BootstrapDeltaResult` dataclass for delta display
  - Added `log_bootstrap_deltas()` method to `VerboseLogger`
  - Shows per-sample deltas with improvement/regression labels
  - Shows delta_sum and decision (ACCEPTED/REJECTED)

- `api/payment_simulator/experiments/runner/optimization.py`:
  - Added `BootstrapDeltaResult` import
  - Added call to `log_bootstrap_deltas()` in `_optimize_agent()`

- `api/payment_simulator/experiments/runner/__init__.py`:
  - Exported `BootstrapDeltaResult`

**Verbose Output Example:**
```
Bootstrap Paired Evaluation (10 samples) - BANK_A:
┃ Sample ┃ Delta (¢) ┃ Note        ┃
│     #1 │     +150  │ improvement │
│     #2 │      -30  │ regression  │
│     #3 │     +200  │ improvement │
...
  Delta sum: +1,250¢ (+$12.50 total improvement)
  Mean delta: 125.0¢ per sample
  Decision: ACCEPTED (delta_sum > 0)
```

---

### Divergence Analysis

**Followed the plan for:**
1. ✅ Phase 1: SeedMatrix implementation with TDD
2. ✅ Phase 2: Evaluation flow refactored
3. ✅ Phase 3: Delta-based acceptance + verbose output

**Intentional divergences:**
1. **SeedMatrix location**: Plan said `ai_cash_mgmt/bootstrap/sampler.py`, but used `experiments/runner/seed_matrix.py` - **better** since it's experiment-specific.

2. **`_evaluate_policies()` still exists**: The plan said "remove pre-iteration baseline evaluation" but this method is REQUIRED for LLM context.

   **Verification (2025-12-12)**: Confirmed in `single_agent_context.py:263-308` that best/worst seed output IS part of Section 4 of the LLM prompt:
   ```
   ## 4. SIMULATION OUTPUT (TICK-BY-TICK)

   ### Best Performing Seed (#42, Cost: $1,234)
   This is the OPTIMAL outcome from the current policy. Analyze what went right.
   <best_seed_output>...</best_seed_output>

   ### Worst Performing Seed (#99, Cost: $9,876)
   This is the PROBLEMATIC outcome. Identify failure patterns and edge cases.
   <worst_seed_output>...</worst_seed_output>
   ```

   This tick-by-tick output helps the LLM understand WHY certain policies perform well/poorly. Removing this would degrade prompt quality.

   The key fix was that `_should_accept_policy()` now uses SeedMatrix for per-agent seeds (the actual bootstrap comparison).

3. **"Bootstrap Baseline" label remains**: The verbose output from `_evaluate_policies()` still shows this label in iteration 1. Could be renamed to "Context Evaluation" but low priority.

---

## Previous Phase

**Phase**: Phase 2 COMPLETE, core implementation done

### Phase 2 Completion Summary (2025-12-12)

**Files Modified:**
- `api/payment_simulator/experiments/runner/optimization.py`:
  - Added SeedMatrix import and initialization
  - Added `_evaluate_policy_pair()` method for paired bootstrap evaluation
  - Updated `_should_accept_policy()` to use SeedMatrix and return deltas
  - Updated `_optimize_agent()` to track delta history
  - Added `_delta_history` tracking for progress monitoring

- `api/tests/integration/test_bootstrap_overhaul.py`:
  - Created 12 integration tests for bootstrap overhaul
  - Tests cover: seed isolation, delta acceptance, paired comparison, progress tracking

**Results:**
- 14 SeedMatrix unit tests pass
- 12 bootstrap overhaul integration tests pass
- Import verification successful

**Key Changes:**
1. **SeedMatrix Integration**: Pre-generates N×A iteration seeds for reproducibility
2. **Per-Agent Seed Isolation**: Each agent gets unique seed stream per iteration
3. **Delta-Based Acceptance**: Accept if `sum(old_cost - new_cost) > 0`
4. **Paired Bootstrap Evaluation**: Old and new policies evaluated with SAME seeds
5. **Delta History Tracking**: Track improvement deltas for progress monitoring

**Remaining Work:**
- Verbose output updates (lower priority, existing output still works)
- End-to-end testing with real experiments

---

## Previous Status

**Phase**: Phase 1 COMPLETE, starting Phase 2

### Phase 1 Completion Summary (2025-12-12)

**Files Created:**
- `api/payment_simulator/experiments/runner/seed_matrix.py` - SeedMatrix class
- `api/tests/unit/test_seed_matrix.py` - 14 unit tests

**Results:**
- All 14 tests pass
- mypy: no issues
- ruff: no issues

**Key Features:**
- Hierarchical seed derivation: master_seed → iteration → agent → bootstrap
- Pre-computed seeds for fast access
- Proper isolation between agents and iterations
- SHA-256 based deterministic derivation
- i32 range for Rust FFI compatibility

**Blockers**: None

**Questions to Resolve**:
1. Should iteration seeds be completely independent per agent, or derived from a common iteration seed?
   - Decision: Per-agent seeds derived from common iteration seed for traceability
2. Should we remove the "Bootstrap Baseline" display entirely, or repurpose it?
   - Decision: Remove it - bootstrap happens after policy generation

---

## Architecture Decision Records

### ADR-1: Seed Generation Strategy

**Context**: Need deterministic seeds that are:
- Reproducible (same master_seed → same seeds)
- Independent per agent per iteration
- Traceable (can reconstruct from master_seed)

**Decision**: Use hierarchical derivation:
```
master_seed
  └── iteration_i
        └── agent_a
              └── bootstrap_sample_s
```

**Derivation Formula**:
```python
iteration_seed = derive(master_seed, f"iteration:{i}")
agent_seed = derive(iteration_seed, f"agent:{agent_id}")
bootstrap_seed = derive(agent_seed, f"sample:{s}")
```

**Rationale**:
- SHA256 is collision-resistant
- Hierarchical structure enables debugging
- Per-agent isolation prevents cross-contamination

### ADR-2: Two Purposes of Evaluation (Clarified)

**Context**: The bootstrap overhaul revealed that "evaluation" serves two different purposes:

1. **Context Evaluation** (`_evaluate_policies()`):
   - Runs BEFORE policy generation
   - Purpose: Provide tick-by-tick logs to LLM for pattern analysis
   - Identifies best/worst performing seeds
   - Included in LLM prompt as Section 4 "SIMULATION OUTPUT"
   - Uses shared seeds (not per-agent isolated)

2. **Acceptance Evaluation** (`_should_accept_policy()`):
   - Runs AFTER policy generation
   - Purpose: Paired comparison of old vs new policy
   - Uses SeedMatrix for per-agent seed isolation
   - Accepts if delta_sum > 0 (new policy cheaper overall)
   - This is the actual "bootstrap" for statistical comparison

**Decision**: Keep both evaluation types, but clarify their purposes:
- Context evaluation: Unchanged (needed for LLM prompt quality)
- Acceptance evaluation: Refactored to use SeedMatrix with per-agent seeds

**Rationale**:
- LLM needs tick-by-tick output to understand policy behavior
- Acceptance needs paired comparison with isolated seeds
- These are orthogonal concerns that happen at different times

### ADR-3: Progress Metric

**Context**: How to track optimization progress?

**Decision**: Track delta sums per iteration:
```python
@dataclass
class IterationProgress:
    iteration: int
    agent_deltas: dict[str, int]  # agent_id -> sum of (old_cost - new_cost)
    accepted: dict[str, bool]     # agent_id -> was policy accepted
```

**Rationale**:
- Delta sums directly measure improvement
- Positive delta = new policy is cheaper
- Can aggregate across agents for total progress

---

## File Change Tracker

| File | Status | Changes |
|------|--------|---------|
| `optimization.py` | Pending | Major refactor of evaluation flow |
| `seed_matrix.py` | Pending | New file for seed management |
| `verbose.py` | Pending | Update output format |
| `test_seed_matrix.py` | Pending | New unit tests |
| `test_bootstrap_evaluation.py` | Pending | New integration tests |
