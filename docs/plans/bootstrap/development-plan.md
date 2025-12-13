# Bootstrap Evaluation Implementation Plan

**Status**: In Progress
**Created**: 2025-12-13
**Feature Request**: `docs/requests/implement-real-bootstrap-evaluation.md`

## Executive Summary

This plan implements **real bootstrap evaluation** to replace the current parametric Monte Carlo approach. The key change is:

- **Current (Wrong)**: Each "bootstrap sample" runs a complete new simulation generating new transactions from parametric distributions
- **Correct Bootstrap**: One initial simulation produces historical data; samples resample FROM that data with replacement

## Critical Project Invariants

These MUST be respected throughout implementation:

1. **INV-1: Money is i64 (Integer Cents)** - All amounts, costs, balances are `int` in Python, `i64` in Rust
2. **INV-2: Determinism is Sacred** - Same seed + same inputs = same outputs. Use seeded RNG everywhere
3. **INV-3: FFI Boundary is Minimal** - Pass only primitives/simple dicts across FFI, validate at boundary
4. **INV-4: Replay Identity** - Run and replay must produce identical output via StateProvider pattern

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    BOOTSTRAP EVALUATION FLOW                     │
└─────────────────────────────────────────────────────────────────┘

Step 1: Initial Simulation (SOURCE)
┌────────────────────────────────────────────────────────────────┐
│  Run ONE complete simulation with stochastic arrivals           │
│  → Collect ALL transactions that occurred                       │
│  → Capture verbose output for LLM context                       │
│  → Store as "historical data" (the empirical distribution)      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 2: Bootstrap Sampling
┌────────────────────────────────────────────────────────────────┐
│  For each of N samples:                                         │
│  → Resample transactions WITH REPLACEMENT from historical data  │
│  → Remap arrival ticks (preserve deadline_offset)               │
│  → Create deterministic scenario_events (no stochastic arrival) │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 3: Policy Evaluation
┌────────────────────────────────────────────────────────────────┐
│  For each bootstrap sample:                                     │
│  → Run simulation with FIXED transaction schedule               │
│  → Measure agent cost under current policy                      │
│  → No random arrivals - deterministic replay of sample          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Step 4: LLM Context (3 Event Streams)
┌────────────────────────────────────────────────────────────────┐
│  1. Initial simulation output (full verbose trace)              │
│  2. Best bootstrap sample events (lowest cost)                  │
│  3. Worst bootstrap sample events (highest cost)                │
└────────────────────────────────────────────────────────────────┘
```

## Phase Overview

**UPDATED 2025-12-13**: Discovery that Phases 1-5 already exist in `api/payment_simulator/ai_cash_mgmt/bootstrap/`!

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 1 | Data Structures | ✅ **EXISTS** | `models.py` - TransactionRecord, RemappedTransaction, BootstrapSample |
| 2 | History Collector | ✅ **EXISTS** | `history_collector.py` - TransactionHistoryCollector |
| 3 | Bootstrap Sampler | ✅ **EXISTS** | `sampler.py` - BootstrapSampler with deterministic xorshift64* |
| 4 | Sandbox Config Builder | ✅ **EXISTS** | `sandbox_config.py` - SandboxConfigBuilder for 3-agent sandbox |
| 5 | Policy Evaluator | ✅ **EXISTS** | `evaluator.py` - BootstrapPolicyEvaluator with paired comparison |
| 6 | LLM Context Update | ⚠️ **PARTIAL** | `context_builder.py` exists, needs initial simulation stream |
| 7 | Experiment Runner Integration | 🔴 **MAIN WORK** | Wire into OptimizationLoop |
| 8 | E2E Testing | ⏳ Pending | Validation, determinism tests |

**The key remaining work is Phase 7**: The infrastructure exists but is NOT wired into the experiment runner!

---

## Phases 1-5: ALREADY IMPLEMENTED

The bootstrap infrastructure already exists in `api/payment_simulator/ai_cash_mgmt/bootstrap/`:

### Phase 1: Data Structures ✅

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py`

Already implemented:
- `TransactionRecord` - Historical transaction with relative timing offsets
- `RemappedTransaction` - Transaction with new arrival tick but preserved offsets
- `BootstrapSample` - Complete bootstrap sample for evaluation

### Phase 2: History Collector ✅

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/history_collector.py`

Already implemented:
- `TransactionHistoryCollector` - Processes events to build transaction history
- Handles arrival events, settlement events (RTGS, Queue2, LSM)
- Computes `deadline_offset` and `settlement_offset` automatically

### Phase 3: Bootstrap Sampler ✅

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/sampler.py`

Already implemented:
- `BootstrapSampler` - Deterministic xorshift64* RNG resampling
- Resamples with replacement
- Remaps arrival ticks uniformly
- Preserves relative timing offsets

### Phase 4: Sandbox Config Builder ✅

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`

Already implemented:
- `SandboxConfigBuilder` - Creates 3-agent sandbox configs
- SOURCE agent with infinite liquidity
- Target agent with test policy
- SINK agent with infinite capacity

### Phase 5: Policy Evaluator ✅

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`

Already implemented:
- `BootstrapPolicyEvaluator` - Evaluates policies on bootstrap samples
- `compute_paired_deltas()` - Paired comparison between policies
- `EvaluationResult` and `PairedDelta` dataclasses

---

## Phase 6: LLM Context Update (PARTIAL)

**Status**: ⚠️ Partially implemented

**Location**: `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`

**What exists**:
- `EnrichedBootstrapContextBuilder` - Builds context from bootstrap results
- `AgentSimulationContext` - Has best/worst seed output

**What's missing**:
- Initial simulation output (Stream 1)
- Currently only has best/worst bootstrap samples (Streams 2-3)

**Required Changes**:

```python
@dataclass
class BootstrapLLMContext:
    """Complete LLM context with 3 event streams."""

    # Stream 1: Initial simulation (full verbose output) - MISSING
    initial_simulation_output: str
    initial_simulation_events: list[dict[str, Any]]
    initial_simulation_cost: int

    # Stream 2: Best bootstrap sample - EXISTS
    best_sample_output: str
    best_sample_events: list[dict[str, Any]]
    best_sample_cost: int
    best_sample_seed: int

    # Stream 3: Worst bootstrap sample - EXISTS
    worst_sample_output: str
    worst_sample_events: list[dict[str, Any]]
    worst_sample_cost: int
    worst_sample_seed: int
```

---

## Phase 7: Experiment Runner Integration (MAIN WORK)

**Goal**: Wire bootstrap into OptimizationLoop

**Location**: Update `api/payment_simulator/experiments/runner/optimization.py`

**Key Changes**:
1. Add `run_initial_simulation()` method
2. Update `_evaluate_policies()` to use bootstrap samples
3. Update `_should_accept_policy()` to use paired comparison
4. Update LLM context building to use 3 streams

**Flow**:
```python
async def run(self) -> OptimizationResult:
    # NEW: Run initial simulation and collect history
    initial_sim_output, history = await self._run_initial_simulation()

    # Create bootstrap samples from history
    samples = self._create_bootstrap_samples(history)

    # Optimization loop
    while not converged:
        # Evaluate using bootstrap samples (NOT parametric Monte Carlo)
        costs = self._evaluate_on_bootstrap_samples(samples)

        # Generate new policy with 3-stream context
        new_policy = await self._optimize_with_bootstrap_context(
            initial_sim_output, best_sample, worst_sample
        )

        # Accept/reject using paired comparison
        accepted = self._paired_accept_reject(samples, old, new)
```

**Tests** (TDD):
- `test_initial_simulation_runs_once()`
- `test_bootstrap_samples_from_initial_sim()`
- `test_evaluation_uses_samples_not_monte_carlo()`
- `test_llm_receives_three_streams()`
- `test_deterministic_across_iterations()`

**Status**: Pending

---

## Phase 8: E2E Testing and Validation

**Goal**: Comprehensive validation of bootstrap implementation

**Tests**:
1. **Determinism**: Same seed produces identical results
2. **Bootstrap vs Monte Carlo**: Verify different behavior
3. **Timing Preservation**: Deadline offsets maintained
4. **Cost Calculation**: Integer cents throughout
5. **LLM Context**: All 3 streams present and correct
6. **Experiment 1 Compatibility**: Deterministic scenarios unchanged
7. **Performance**: Bootstrap evaluation completes in reasonable time

**Validation Metrics**:
- Compare cost distributions: Bootstrap vs Monte Carlo
- Verify variance reduction from paired comparison
- Check LLM response quality with richer context

**Status**: Pending

---

## Implementation Order

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8
   │         │         │         │         │         │         │         │
   │         │         │         │         │         │         │         └── E2E Tests
   │         │         │         │         │         │         └── Integration
   │         │         │         │         │         └── LLM Context
   │         │         │         │         └── Evaluator
   │         │         │         └── Sandbox Builder
   │         │         └── Sampler Enhancement
   │         └── History Collector
   └── Data Structures
```

## Files to Create/Modify

### New Files:
- `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py` (Phase 1)
- `api/payment_simulator/ai_cash_mgmt/bootstrap/history_collector.py` (Phase 2)
- `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_builder.py` (Phase 4)
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` (Phase 5)
- `api/tests/unit/ai_cash_mgmt/bootstrap/test_models.py`
- `api/tests/unit/ai_cash_mgmt/bootstrap/test_history_collector.py`
- `api/tests/unit/ai_cash_mgmt/bootstrap/test_sandbox_builder.py`
- `api/tests/unit/ai_cash_mgmt/bootstrap/test_evaluator.py`
- `api/tests/integration/test_bootstrap_evaluation.py`

### Modified Files:
- `api/payment_simulator/ai_cash_mgmt/sampling/transaction_sampler.py` (Phase 3)
- `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` (Phase 6)
- `api/payment_simulator/experiments/runner/optimization.py` (Phase 7)

## Success Criteria

1. [ ] Bootstrap samples resample FROM historical data, not regenerate
2. [ ] Deadline offsets preserved in remapping
3. [ ] 3 event streams available to LLM
4. [ ] Paired comparison for accept/reject
5. [ ] All money values are integers (INV-1)
6. [ ] Deterministic with same seed (INV-2)
7. [ ] Tests pass: unit, integration, E2E
8. [ ] mypy/ruff pass with no errors
9. [ ] Experiment 1 (deterministic) unchanged
10. [ ] Documentation updated

## Risk Mitigation

1. **Existing TransactionSampler**: Enhance, don't replace - preserve backward compatibility
2. **FFI Complexity**: Use SandboxConfigBuilder to encapsulate FFI config building
3. **Performance**: Bootstrap samples can be computed once and reused across iterations
4. **Determinism**: Use SeedMatrix pattern for consistent seed derivation

---

*Plan created: 2025-12-13*
*Last updated: 2025-12-13*
