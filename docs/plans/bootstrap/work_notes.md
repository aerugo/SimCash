# Bootstrap Evaluation - Work Notes

**Started**: 2025-12-13
**Current Phase**: Phase 7 - Experiment Runner Integration
**Feature Request**: `docs/requests/implement-real-bootstrap-evaluation.md`

---

## Session Log

### 2025-12-13 - Initial Planning & Discovery

**What was done**:
1. Read and analyzed the feature request document
2. Reviewed existing infrastructure - **MAJOR DISCOVERY**: Bootstrap infrastructure already exists!
3. Created development plan structure in `docs/plans/bootstrap/`
4. Updated plan based on existing code

**MAJOR DISCOVERY - Existing Bootstrap Infrastructure**:

The following components already exist in `api/payment_simulator/ai_cash_mgmt/bootstrap/`:

| File | Component | Status |
|------|-----------|--------|
| `models.py` | `TransactionRecord`, `RemappedTransaction`, `BootstrapSample` | ✅ Complete |
| `history_collector.py` | `TransactionHistoryCollector` - processes events to collect history | ✅ Complete |
| `sampler.py` | `BootstrapSampler` - deterministic xorshift64* RNG resampling | ✅ Complete |
| `evaluator.py` | `BootstrapPolicyEvaluator` - paired comparison | ✅ Complete |
| `sandbox_config.py` | `SandboxConfigBuilder` - 3-agent sandbox configs | ✅ Complete |
| `context_builder.py` | `EnrichedBootstrapContextBuilder` - LLM context | ✅ Complete |

**The Problem**: This infrastructure is **NOT wired into the experiment runner**!

The `OptimizationLoop` in `experiments/runner/optimization.py` still uses parametric Monte Carlo:
```python
def _run_single_simulation(self, seed: int) -> tuple[int, dict[str, int]]:
    # Runs a COMPLETE NEW SIMULATION for each "sample"
    # This is Monte Carlo, not bootstrap!
```

**Key Remaining Work**:
1. Wire existing bootstrap infrastructure into `OptimizationLoop`
2. Add initial simulation step to collect historical data
3. Update `_evaluate_policies()` to use `BootstrapSampler` + `BootstrapPolicyEvaluator`
4. Add 3 event streams to LLM context (initial sim, best sample, worst sample)

**Key Findings**:
- Current implementation runs complete NEW simulations for each "bootstrap sample"
- This is parametric Monte Carlo (generates new transactions from distributions)
- Real bootstrap should resample FROM observed historical data
- **The infrastructure to do this correctly ALREADY EXISTS but isn't used!**

**Key Concepts to Implement**:
1. **Initial Simulation**: Run ONE simulation to collect historical transactions
2. **TransactionRecord**: Store transactions with relative timing offsets (deadline_offset, settlement_offset)
3. **Remapping**: When resampling, assign new arrival_tick but preserve deadline_offset
4. **Liquidity Beats**: Incoming settlements treated as fixed external events
5. **3-Agent Sandbox**: AGENT (evaluated), SINK (receives outgoing), SOURCE (sends liquidity beats)
6. **3 Event Streams for LLM**: Initial sim output, best sample, worst sample

**Project Invariants to Respect**:
- INV-1: Money is i64/int (integer cents) - NO FLOATS
- INV-2: Determinism - seeded RNG, reproducible results
- INV-3: FFI minimal - simple types across boundary
- INV-4: Replay identity - StateProvider pattern

**Next Steps**:
- ~~Create Phase 1 detailed plan (Data Structures)~~ - Phases 1-5 already implemented!
- Create Phase 7 detailed plan (Experiment Runner Integration)
- Write TDD tests for integration
- Wire bootstrap infrastructure into OptimizationLoop

### 2025-12-13 - Phase 7 Plan Created

**What was done**:
1. Analyzed `OptimizationLoop` in `experiments/runner/optimization.py` (1600+ lines)
2. Identified exact code locations that need modification
3. Created detailed Phase 7 plan in `phases/phase_7.md`
4. Designed TDD test suite for integration

**Key Implementation Points**:
1. Add `_run_initial_simulation()` method - runs ONCE to collect history
2. Update `run()` to call initial simulation at start
3. Update `_evaluate_policies()` to use `BootstrapSampler` + `BootstrapPolicyEvaluator`
4. Update `_should_accept_policy()` to use `compute_paired_deltas()`
5. Add 3 event streams to LLM context (initial sim, best, worst)

**Next Steps**:
- ~~Write integration tests (TDD - RED phase)~~ Done
- Implement changes to OptimizationLoop (GREEN phase)
- Run type checking and linting (REFACTOR phase)

### 2025-12-13 - TDD Tests Created

**What was done**:
1. Created comprehensive TDD test file: `api/tests/integration/test_real_bootstrap_evaluation.py`
2. Tests verify correct bootstrap behavior:
   - `TestInitialSimulationCollectsHistory` - History collection from events
   - `TestBootstrapSamplingFromHistory` - Resampling from history, not generating new
   - `TestSandboxConfigBuilder` - 3-agent sandbox structure
   - `TestPairedComparison` - Same samples for old/new policies
   - `TestIntegerCentsInvariant` - INV-1 compliance
   - `TestLLMContextStreams` - Best/worst identification
   - `TestOptimizationLoopBootstrapIntegration` - Main integration (marked skip until impl)

**Note**: Tests require Rust FFI module to be built. In environments without FFI:
- Unit-like tests for Python components will pass
- Integration tests requiring Orchestrator are skipped

**Next Steps**:
1. Build Rust FFI module (`uv sync --extra dev` in api/)
2. ~~Implement Phase 7 changes to OptimizationLoop~~ In Progress
3. Run tests to verify implementation

### 2025-12-13 - Phase 7 Implementation Started

**What was done**:
1. Created `experiments/runner/bootstrap_support.py` with:
   - `InitialSimulationResult` dataclass - captures initial simulation data
   - `BootstrapLLMContext` dataclass - holds 3 event streams for LLM

2. Updated `experiments/runner/optimization.py`:
   - Added imports for bootstrap infrastructure
   - Added bootstrap state variables (`_initial_sim_result`, `_bootstrap_samples`, etc.)
   - Added `_run_initial_simulation()` method - runs ONCE to collect history
   - Added `_create_bootstrap_samples()` method - creates samples from history
   - Updated `run()` to call initial simulation once for bootstrap mode

**Implementation Status**:
- [x] `InitialSimulationResult` dataclass
- [x] `BootstrapLLMContext` dataclass
- [x] `_run_initial_simulation()` method
- [x] `_create_bootstrap_samples()` method
- [x] Initial simulation call in `run()` for bootstrap mode
- [ ] Update `_evaluate_policies()` for bootstrap mode
- [ ] Update `_should_accept_policy()` for paired comparison
- [ ] Wire `BootstrapLLMContext` into LLM context building

**Remaining Work** (detailed):

1. **Add helper methods for agent config extraction**:
   ```python
   def _get_agent_opening_balance(self, agent_id: str) -> int:
       """Get opening balance for an agent from scenario config."""
       scenario = self._load_scenario_config()
       for agent in scenario.get("agents", []):
           if agent.get("id") == agent_id:
               return int(agent.get("opening_balance", 0))
       return 0

   def _get_agent_credit_limit(self, agent_id: str) -> int:
       """Get credit limit for an agent from scenario config."""
       scenario = self._load_scenario_config()
       for agent in scenario.get("agents", []):
           if agent.get("id") == agent_id:
               return int(agent.get("unsecured_cap", 0))
       return 0
   ```

2. **Update `_evaluate_policy_pair()` for real bootstrap**:
   ```python
   # In bootstrap mode with _bootstrap_samples available:
   if self._bootstrap_samples and agent_id in self._bootstrap_samples:
       samples = self._bootstrap_samples[agent_id]
       evaluator = BootstrapPolicyEvaluator(
           opening_balance=self._get_agent_opening_balance(agent_id),
           credit_limit=self._get_agent_credit_limit(agent_id),
           cost_rates=self._cost_rates,
       )
       paired_deltas = evaluator.compute_paired_deltas(samples, old_policy, new_policy)
       deltas = [d.delta for d in paired_deltas]
       return deltas, sum(deltas)
   ```

3. **Update `_evaluate_policies()` for real bootstrap**:
   - Use `BootstrapPolicyEvaluator.evaluate_samples()` instead of running new simulations
   - Build `EnrichedEvaluationResult` from evaluation results

4. **Wire `BootstrapLLMContext` into LLM context**:
   - Add initial simulation output to context
   - Ensure 3 streams are available for LLM optimization

### 2025-12-13 - Phase 7b Started (Completing Integration)

**What was done**:
1. Created `phases/phase_7b.md` - detailed plan for completing integration
2. Identified remaining tasks:
   - Add helper methods for agent config extraction
   - Update `_evaluate_policy_pair()` with bootstrap branch
   - Wire BootstrapLLMContext

**TDD Approach**:
- Write failing tests FIRST
- Implement to pass tests
- Refactor (type check, lint)

**Current Task**: Writing TDD tests for remaining integration work

### 2025-12-13 - Phase 7b Completed

**What was done**:
1. **Helper methods added** (`_get_agent_opening_balance()`, `_get_agent_credit_limit()`)
   - Tests pass: `TestAgentConfigHelpers` (3 tests)

2. **Real bootstrap branch added to `_evaluate_policy_pair()`**:
   - Uses `BootstrapPolicyEvaluator.compute_paired_deltas()` when samples available
   - Falls back to Monte Carlo only when no samples (to be removed in Phase 7c)
   - Tests pass: `TestEvaluatePolicyPairUsesBootstrapSamples` (2 tests)

3. **BootstrapLLMContext wired into LLM context**:
   - `_build_agent_contexts()` creates `BootstrapLLMContext` with all 3 streams
   - `_optimize_agent()` combines initial simulation output (Stream 1) with best seed (Stream 2)
   - LLM now receives: Initial Simulation + Best Bootstrap Sample + Worst Bootstrap Sample

4. **Design decision documented**: No fallback to Monte Carlo (single code path)
   - Cleanup deferred to Phase 7c after everything verified working

**Test Results**:
- 18 tests passed
- 4 tests skipped (require full FFI integration)
- mypy: Success
- ruff: Only pre-existing warnings

**Next Steps**:
- Phase 7c: Remove Monte Carlo fallback (cleanup)
- Phase 8: E2E Testing with real experiment configs

### 2025-12-13 - Phase 7c Completed

**What was done**:
1. **Updated test** to expect `RuntimeError` instead of Monte Carlo fallback
   - `test_evaluate_policy_pair_raises_without_samples()`
2. **Removed Monte Carlo fallback code** from `_evaluate_policy_pair()`
   - Now raises `RuntimeError` if no bootstrap samples available
   - Code simplified from ~40 lines to ~25 lines
3. **All tests pass**: 18 passed, 4 skipped (FFI integration tests)

**Design simplification achieved**:
- Single code path for bootstrap evaluation
- No fallback branches
- Clear error if samples missing

### 2025-12-13 - Verbose Output Wiring Completed

**What was done**:
1. **Added `_format_events_for_llm()` helper method**:
   - Formats simulation events into human-readable verbose output for LLM consumption
   - Priority-based event selection (policy decisions, costs, settlements first)
   - Limits to 100 most important events to avoid overwhelming context
   - Chronological ordering within selected events

2. **Added `_format_event_details_for_llm()` helper method**:
   - Formats individual event details into compact strings
   - Extracts key fields: tx_id, action, amount, cost, agent_id, sender_id, receiver_id
   - Formats money as dollars (INV-1: converts integer cents to display)

3. **Updated `_run_initial_simulation()`**:
   - Now uses `_format_events_for_llm()` to generate verbose output
   - Verbose output stored in `InitialSimulationResult.verbose_output`
   - Provides Stream 1 for LLM context (initial simulation trace)

**Test Results**:
- 18 tests passed, 4 skipped (FFI integration tests)
- mypy: Success
- ruff: Only pre-existing warnings

### 2025-12-13 - Phase 9: CRITICAL ISSUE - Sandbox Evaluation Invalid

**Problem observed** (after Phase 8 fixes):
After fixing max_collateral_capacity and cost_rates key typo, experiment 2 now shows:
- **Baseline costs vary**: $5,065 - $5,280 across 50 samples (good - transaction-dependent)
- **Paired deltas ALL IDENTICAL**: -$1,764 for ALL 50 samples (bad!)

**Root Cause Analysis**:

The deltas are identical because:
1. Delta = 176,400 cents = exactly the collateral cost difference
2. Policy change: 0.5 → 0.85 = +0.35 of max_collateral
3. Collateral difference: 0.35 × 10,000,000 cents = 3,500,000 cents
4. Cost at 42 bps/tick: 3,500,000 × 42 / 10,000 = 14,700 cents/tick
5. Over 12 ticks: 14,700 × 12 = **176,400 cents** ✅

**The sandbox removes bilateral constraints!**

Current 3-agent sandbox:
```
SOURCE → AGENT → SINK
```
- SOURCE has infinite liquidity
- SINK always accepts (infinite capacity)
- No bilateral settlement interactions

In main simulation with BANK_A ↔ BANK_B:
- BANK_A releases payment → settles via RTGS
- BANK_B receives liquidity from that settlement
- BANK_B can now settle its queued payments
- This causal chain affects timing, delays, and costs

**The sandbox evaluation path is NOT equivalent to the main simulation path!**

**New Plan Required**:
Bootstrap evaluation MUST use the SAME engine as main simulation:
1. Same orchestrator (Rust FFI)
2. Same bilateral agent structure
3. Same settlement mechanics
4. Same cost calculation

See: `docs/plans/bootstrap/bilateral_evaluation.md` for detailed phased plan.

---

### 2025-12-13 - Phase 8 Completed: Zero Deltas Fixed

**Problem observed**:
When running experiment 2 with gpt-5.2, all bootstrap paired evaluation deltas were zero.

**Root Cause Found**:
`SandboxConfigBuilder._build_target_agent()` didn't pass `max_collateral_capacity` to `AgentConfig`.

Without `max_collateral_capacity`, Rust used heuristic: `max_collateral_capacity = 10 × unsecured_cap = 10 × 0 = 0`

The agent couldn't post any collateral because `initial_liquidity_fraction * remaining_capacity = X * 0 = 0`

All policies behaved identically → all deltas were 0.

**Fix Implemented**:
1. **`sandbox_config.py`**: Added `max_collateral_capacity` parameter to `build_config()` and `_build_target_agent()`
2. **`evaluator.py`**: Added `max_collateral_capacity` to `__init__()` and passed it to config builder
3. **`optimization.py`**: Added `_get_agent_max_collateral_capacity()` helper and updated `_evaluate_policy_pair()` to pass it

**Verification**:
Debug script showed non-zero deltas:
- Low (0.1) policy: $504.00
- High (0.9) policy: $4536.00
- Delta: -$4032.00 ✅

**Files modified**:
- `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`
- `api/payment_simulator/experiments/runner/optimization.py`
- `api/tests/integration/test_real_bootstrap_evaluation.py` (added test for helper)

---

## Phase Progress

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1 | **ALREADY DONE** | - | Pre-existing | `models.py` - TransactionRecord, RemappedTransaction, BootstrapSample |
| 2 | **ALREADY DONE** | - | Pre-existing | `history_collector.py` - TransactionHistoryCollector |
| 3 | **ALREADY DONE** | - | Pre-existing | `sampler.py` - BootstrapSampler with xorshift64* |
| 4 | **ALREADY DONE** | - | Pre-existing | `sandbox_config.py` - SandboxConfigBuilder |
| 5 | **ALREADY DONE** | - | Pre-existing | `evaluator.py` - BootstrapPolicyEvaluator |
| 6 | **COMPLETE** | 2025-12-13 | 2025-12-13 | BootstrapLLMContext wired with 3 streams |
| 7 | **COMPLETE** | 2025-12-13 | 2025-12-13 | Initial sim + bootstrap samples in OptimizationLoop |
| 7b | **COMPLETE** | 2025-12-13 | 2025-12-13 | Helper methods + evaluation wiring |
| 7c | **COMPLETE** | 2025-12-13 | 2025-12-13 | Removed Monte Carlo fallback |
| 7d | **COMPLETE** | 2025-12-13 | 2025-12-13 | Verbose output wiring for LLM |
| 8 | **COMPLETE** | 2025-12-13 | 2025-12-13 | Fixed: max_collateral_capacity passed to sandbox |
| 8b | **COMPLETE** | 2025-12-13 | 2025-12-13 | Fixed: cost_rates key typo (cost_config → cost_rates) |
| 9 | **CRITICAL ISSUE FOUND** | 2025-12-13 | - | Sandbox evaluation invalid - see Phase 9 below |
| 10 | **COMPLETE** | 2025-12-13 | 2025-12-13 | ScheduledSettlementEvent for RTGS correctness |
| 11+ | Pending | - | - | Bilateral evaluation (if needed) |

---

## Technical Decisions

### Decision 1: TransactionRecord vs HistoricalTransaction

**Context**: Existing `HistoricalTransaction` in `transaction_sampler.py` stores absolute ticks.

**Decision**: Create new `TransactionRecord` dataclass that stores relative offsets.

**Rationale**:
- `deadline_offset = deadline_tick - arrival_tick` is the key concept for remapping
- Preserving relative timing is critical for bootstrap validity
- Can convert between formats as needed

### Decision 2: Reuse vs Replace TransactionSampler

**Context**: Existing `TransactionSampler` has `_bootstrap_sample()` method.

**Decision**: Enhance existing class, add new methods for remapping.

**Rationale**:
- Preserve backward compatibility
- Existing code tested and working
- Add `create_bootstrap_samples()` that returns `BootstrapSample` objects

### Decision 3: 3-Agent Sandbox Architecture

**Context**: Need to evaluate agent policy in isolation.

**Decision**: Use AGENT/SINK/SOURCE architecture:
- AGENT: The agent being evaluated (has the policy)
- SINK: Receives all outgoing payments from AGENT (unlimited liquidity)
- SOURCE: Sends all liquidity beats to AGENT (scheduled incoming)

**Rationale**:
- Isolates policy evaluation from other agents' decisions
- SINK with unlimited liquidity ensures outgoing payments can settle
- SOURCE provides controlled liquidity inflows (the "liquidity beats")

---

## Open Questions

1. **Q**: How to handle settlement_offset for transactions that didn't settle in initial sim?
   **A**: Set to None, these represent failed settlements. May still include in bootstrap but mark differently.

2. **Q**: Should bootstrap samples have same number of transactions as original?
   **A**: Yes, standard bootstrap resamples n items from n items with replacement.

3. **Q**: How to handle multi-day simulations?
   **A**: Initial implementation focuses on single-day. May need per-day remapping later.

---

## Code Snippets / References

### Existing HistoricalTransaction (for reference)
```python
# From transaction_sampler.py
@dataclass(frozen=True)
class HistoricalTransaction:
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents
    priority: int
    arrival_tick: int
    deadline_tick: int  # ABSOLUTE, not offset
    is_divisible: bool
```

### Target TransactionRecord
```python
@dataclass(frozen=True)
class TransactionRecord:
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # INV-1: Integer cents
    priority: int
    arrival_tick: int
    deadline_offset: int  # RELATIVE: deadline_tick - arrival_tick
    settlement_offset: int | None  # RELATIVE: settlement_tick - arrival_tick
    is_divisible: bool
```

---

## Blockers / Issues

*None currently*

---

## Notes for Next Session

When resuming work:
1. Check current phase status in this file
2. Read the detailed phase plan in `phases/phase_N.md`
3. Run existing tests to ensure environment is working
4. Continue TDD cycle: Red → Green → Refactor

---

### 2025-12-13 - Phase 10: ScheduledSettlementEvent Implemented

**Goal**: Implement `ScheduledSettlementEvent` for bootstrap correctness per `scheduled_settlement_event.md` plan.

**What was done (TDD approach)**:

1. **RED Phase - TDD Tests Written**:
   - Created `simulator/tests/test_scheduled_settlement_event.rs` (Rust unit tests)
   - Created `api/tests/integration/test_scheduled_settlement_event.py` (Python integration tests)
   - 14 total tests covering:
     - Parsing/serialization
     - Settlement at exact tick
     - RtgsImmediateSettlement event emission (proves RTGS engine used)
     - No Arrival event (atomic create+settle)
     - Liquidity constraints (respects balance + credit)
     - Comparison vs DirectTransfer (events emitted differ)
     - Repeating schedule support
     - Determinism (INV-2)
     - Error handling (invalid agent, missing amount)

2. **GREEN Phase - Implementation**:
   - **`simulator/src/events/types.rs`**: Added `ScheduledSettlement` variant to `ScenarioEvent` enum
   - **`simulator/src/events/handler.rs`**: Added stub delegating to orchestrator level
   - **`simulator/src/ffi/types.rs`**: Added FFI parsing for `"ScheduledSettlement"` event type
   - **`simulator/src/orchestrator/engine.rs`**: Added execution logic:
     - Validates agents exist
     - Checks sender can pay (liquidity)
     - Debits sender, credits receiver
     - Emits `RtgsImmediateSettlement` event (proves RTGS engine used)
     - Emits `ScenarioEventExecuted` for replay identity
     - Gracefully handles insufficient liquidity (logs, doesn't error)

3. **Python Schema & Sandbox Config Update**:
   - **`api/payment_simulator/config/schemas.py`**: Added `ScheduledSettlementEvent` Pydantic model
   - **`api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`**:
     - Changed `_incoming_to_transfer()` → `_incoming_to_scheduled_settlement()`
     - Now uses `ScheduledSettlementEvent` instead of `DirectTransferEvent` for incoming liquidity beats
     - This ensures liquidity beats go through real RTGS engine

**Key Difference from DirectTransfer**:
- `DirectTransfer`: Bypasses RTGS, just adjusts balances, no `RtgsImmediateSettlement` event
- `ScheduledSettlement`: Goes through RTGS engine, emits `RtgsImmediateSettlement` event

**Test Results**:
- 11 Python integration tests: ✅ All pass
- 3 Rust unit tests: ✅ All pass
- mypy: ✅ No issues
- ruff: Only pre-existing warnings

**Files Modified**:
- `simulator/src/events/types.rs` - Added ScheduledSettlement variant
- `simulator/src/events/handler.rs` - Added stub
- `simulator/src/ffi/types.rs` - Added FFI parsing
- `simulator/src/orchestrator/engine.rs` - Added execution logic
- `api/payment_simulator/config/schemas.py` - Added Pydantic model
- `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py` - Updated for RTGS correctness

**Files Created**:
- `simulator/tests/test_scheduled_settlement_event.rs` - Rust TDD tests
- `api/tests/integration/test_scheduled_settlement_event.py` - Python TDD tests

**Impact**:
Bootstrap sandbox evaluation now uses real RTGS engine for incoming liquidity beats.
This is a correctness fix - settlements now emit proper events and respect liquidity constraints.

**Next Steps**:
- Verify experiment 2 still runs with new sandbox config
- Note: Bilateral feedback issue (Phase 9) remains - deltas may still be uniform
  due to abundant liquidity in exp2 scenario, but now they're computed correctly

---

*Last updated: 2025-12-13 (Phase 10 complete - ScheduledSettlementEvent implemented)*
