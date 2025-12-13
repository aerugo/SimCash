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

**Remaining Work**:
- `_evaluate_policies()` needs to use `BootstrapPolicyEvaluator` for bootstrap mode
- `_should_accept_policy()` needs to use `compute_paired_deltas()` on same samples
- LLM context needs to include initial simulation output (Stream 1)

---

## Phase Progress

| Phase | Status | Started | Completed | Notes |
|-------|--------|---------|-----------|-------|
| 1 | **ALREADY DONE** | - | Pre-existing | `models.py` - TransactionRecord, RemappedTransaction, BootstrapSample |
| 2 | **ALREADY DONE** | - | Pre-existing | `history_collector.py` - TransactionHistoryCollector |
| 3 | **ALREADY DONE** | - | Pre-existing | `sampler.py` - BootstrapSampler with xorshift64* |
| 4 | **ALREADY DONE** | - | Pre-existing | `sandbox_config.py` - SandboxConfigBuilder |
| 5 | **ALREADY DONE** | - | Pre-existing | `evaluator.py` - BootstrapPolicyEvaluator |
| 6 | **PARTIAL** | - | - | `context_builder.py` exists, needs 3 streams |
| 7 | **IN PROGRESS** | 2025-12-13 | - | ~50% complete: initial sim done, evaluation wiring remaining |
| 8 | Pending | - | - | E2E Testing |

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

*Last updated: 2025-12-13*
