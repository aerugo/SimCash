# Replay System Hardening Plan

**Status**: In Progress
**Created**: 2025-01-09
**Owner**: Claude Code Session
**Priority**: High

---

## Executive Summary

This document outlines a comprehensive plan to harden the replay system architecture, ensuring that `payment-sim replay` output remains perfectly consistent with `payment-sim run` output across all future development. The plan addresses the root architectural risks identified during the LSM replay discrepancy investigation.

---

## Background: Current Architecture

### The Good: Shared Display Layer

The codebase has successfully implemented a **Strategy Pattern** for simulation output:

```
┌─────────────────────────────────────────────────────────┐
│          display_tick_verbose_output()                  │
│          (Single Source of Truth)                       │
└────────────────┬───────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
         ▼                ▼
┌────────────────┐  ┌──────────────────┐
│ Orchestrator   │  │ Database         │
│ StateProvider  │  │ StateProvider    │
│ (Live FFI)     │  │ (Replay)         │
└────────────────┘  └──────────────────┘
```

**Key Strength**: If display logic changes, it applies to both run and replay automatically.

### The Risk: Data Reconstruction and Persistence

The risk has shifted from **display divergence** to **data divergence**. The replay system depends on:

1. **Complete Persistence**: All data needed for display must be saved during `run --persist --full-replay`
2. **Correct Reconstruction**: Saved data must be correctly reconstructed during `replay`
3. **Matching Formats**: Rust event formats must match Python reconstruction expectations

**Bugs Found**: All recent replay bugs were in the data handling layer, not the display layer:
- LSM events not reconstructed from `simulation_events` (missing fallback logic)
- Bilateral offset detection using wrong array length (2 vs 3)
- Deadline ticks using wrong field name (`deadline_tick` vs `deadline`)
- Priority/divisible fields missing from Event::Arrival
- Credit utilization hardcoded to 0 instead of calculated

---

## Phase 1: Automated Testing & Validation

### 1.1 StateProvider Contract Tests

**Goal**: Ensure both `OrchestratorStateProvider` and `DatabaseStateProvider` return identical results for the same simulation state.

**Approach**: Property-based testing using hypothesis or similar

```python
# File: api/tests/integration/test_state_provider_contract.py

def test_state_provider_contract(simulation_fixture):
    """Both StateProviders must return identical results."""
    # Run simulation with orchestrator
    orch = Orchestrator.new(config)
    for _ in range(10):
        orch.tick()

    # Get state via OrchestratorStateProvider
    live_provider = OrchestratorStateProvider(orch)
    live_balance = live_provider.get_agent_balance("BANK_A")
    live_tx = live_provider.get_transaction_details("tx_001")

    # Persist and reload via DatabaseStateProvider
    db_provider = load_from_database(simulation_id, tick=9)
    db_balance = db_provider.get_agent_balance("BANK_A")
    db_tx = db_provider.get_transaction_details("tx_001")

    # MUST be identical
    assert live_balance == db_balance
    assert live_tx == db_tx
```

**Coverage**: All methods in `StateProvider` protocol

### 1.2 End-to-End Replay Identity Test

**Goal**: Complete the skipped `test_full_tick_output_identity` test

```python
# File: api/tests/integration/test_run_replay_identity.py

def test_full_tick_output_identity(self):
    """GOLD STANDARD: Run and replay outputs must be byte-for-byte identical."""
    # 1. Run simulation with --persist --full-replay, capture stderr
    run_output = run_simulation(config, verbose=True, persist=True)

    # 2. Replay from database, capture stderr
    replay_output = replay_simulation(simulation_id, verbose=True)

    # 3. Normalize outputs (remove timing, sort non-deterministic sections)
    run_normalized = normalize_output(run_output)
    replay_normalized = normalize_output(replay_output)

    # 4. Line-by-line comparison with detailed diff on failure
    assert run_normalized == replay_normalized, diff(run_normalized, replay_normalized)
```

**Success Criteria**: Test passes on `comprehensive_feature_showcase_ultra_stressed.yaml`

### 1.3 Database Schema Validation Tests

**Goal**: Ensure database schema changes don't break replay

```python
# File: api/tests/integration/test_persistence_schema.py

def test_simulation_events_has_all_event_types():
    """Verify simulation_events table can store all Rust Event types."""
    # Get all Event variants from Rust
    event_types = get_rust_event_types()  # via introspection or parsing

    # Verify each can be serialized and deserialized
    for event_type in event_types:
        event = create_sample_event(event_type)
        serialized = orchestrator.serialize_event(event)
        db.insert_simulation_event(serialized)
        retrieved = db.get_simulation_event(event_id)
        assert retrieved == serialized

def test_agent_state_has_all_required_fields():
    """Verify agent_states table has all fields needed for display."""
    required_fields = [
        "balance", "credit_limit", "collateral_posted",
        "liquidity_cost", "delay_cost", "collateral_cost",
        "penalty_cost", "split_friction_cost"
    ]

    state = get_agent_state_from_db("BANK_A", tick=50)
    for field in required_fields:
        assert field in state, f"Missing required field: {field}"
```

---

## Phase 2: Architectural Guardrails

### 2.1 Pre-Commit Hook: FFI/Persistence Sync

**Goal**: Prevent FFI changes without matching persistence updates

```bash
# File: .git/hooks/pre-commit

#!/bin/bash
# Check if backend/src/ffi/orchestrator.rs changed
if git diff --cached --name-only | grep -q "backend/src/ffi/orchestrator.rs"; then
    echo "⚠️  FFI changes detected!"

    # Check if persistence layer also changed
    if ! git diff --cached --name-only | grep -q "api/payment_simulator/cli/execution/persistence.py"; then
        echo "❌ ERROR: FFI changed but persistence.py didn't!"
        echo ""
        echo "When adding FFI methods, you MUST update:"
        echo "  1. api/payment_simulator/cli/execution/persistence.py (save data)"
        echo "  2. api/payment_simulator/cli/execution/state_provider.py (load data)"
        echo "  3. api/payment_simulator/cli/commands/replay.py (reconstruct events if needed)"
        echo ""
        exit 1
    fi
fi
```

### 2.2 CI Pipeline: Replay Identity Check

**Goal**: Run replay identity test on every commit

```yaml
# File: .github/workflows/test.yml

- name: Test Replay Identity
  run: |
    cd api
    uv run payment-sim run --config ../examples/configs/simple_example.yaml \
        --persist --full-replay --verbose 2> run.log

    uv run payment-sim replay --simulation-id $(cat last_sim_id.txt) \
        --verbose 2> replay.log

    # Compare outputs (ignoring timing lines)
    if ! diff <(grep -v "ticks/s" run.log) <(grep -v "ticks/s" replay.log); then
        echo "❌ Replay output diverged from run output!"
        exit 1
    fi
```

### 2.3 Type-Safe Event Reconstruction

**Goal**: Make reconstruction errors fail fast

```python
# File: api/payment_simulator/cli/commands/replay.py

from typing import TypedDict, Literal

class LsmBilateralOffsetEvent(TypedDict):
    """Type-safe LSM bilateral offset event structure."""
    event_type: Literal["LsmBilateralOffset"]
    agent_a: str
    agent_b: str
    tx_id_a: str
    tx_id_b: str
    amount_a: int
    amount_b: int
    amount: int

def _reconstruct_lsm_events(lsm_cycles: list[dict]) -> list[LsmBilateralOffsetEvent | dict]:
    """Type hints catch missing fields at mypy time."""
    events: list[LsmBilateralOffsetEvent | dict] = []

    for cycle in lsm_cycles:
        if cycle["cycle_type"] == "bilateral":
            # This will fail mypy if any required field is missing
            event: LsmBilateralOffsetEvent = {
                "event_type": "LsmBilateralOffset",
                "agent_a": cycle["agent_ids"][0],
                "agent_b": cycle["agent_ids"][1],
                "tx_id_a": cycle["tx_ids"][0],
                "tx_id_b": cycle["tx_ids"][1],
                "amount_a": cycle["tx_amounts"][0],
                "amount_b": cycle["tx_amounts"][1],
                "amount": cycle["settled_value"],
            }
            events.append(event)

    return events
```

**Enforcement**: Add `mypy --strict` to CI pipeline

---

## Phase 3: Developer Experience & Documentation

### 3.1 Update CLAUDE.md

**Additions**:

```markdown
## Critical Invariant: Replay Identity

**Rule**: `payment-sim replay` output MUST be byte-for-byte identical to `payment-sim run` output (modulo timing).

This is achieved through the **StateProvider Pattern**:

1. **Shared Display**: Both run and replay use `display_tick_verbose_output()`
2. **Data Abstraction**: Display logic calls `StateProvider` methods, never Rust directly
3. **Two Implementations**:
   - `OrchestratorStateProvider`: Wraps live Rust FFI
   - `DatabaseStateProvider`: Wraps DuckDB queries

### When Adding a New Display Feature

Follow this **mandatory workflow**:

1. **Add Rust State**: Implement new metric/field in Rust backend
2. **Expose via FFI**: Add getter to `backend/src/ffi/orchestrator.rs`
3. **Update StateProvider**:
   - Add method to `StateProvider` protocol (state_provider.py)
   - Implement in `OrchestratorStateProvider` (call FFI)
   - Implement in `DatabaseStateProvider` (query DB)
4. **Update Persistence**:
   - Modify `PersistenceManager` to save new data (persistence.py)
   - Update database schema if needed (models.py)
5. **Add Reconstruction**:
   - If displaying events, add reconstruction logic (replay.py)
6. **Update Display**: Use StateProvider method in `display_tick_verbose_output()`
7. **Test Both Paths**: Run integration test verifying run == replay

### Anti-Pattern: Skipping Persistence

❌ **NEVER**:
```python
# BAD: Bypassing StateProvider
def display_new_metric(orch):
    value = orch.get_new_metric_direct()  # Only works in run!
```

✅ **ALWAYS**:
```python
# GOOD: Using StateProvider
def display_new_metric(provider: StateProvider):
    value = provider.get_new_metric()  # Works in run AND replay
```

### Known Pitfalls

1. **Event Field Names**: Rust uses `deadline`, not `deadline_tick`. Check FFI serialization.
2. **Bilateral Cycles**: LSM bilateral offsets have `agent_ids = [A, B, A]` (length 3), not `[A, B]`
3. **Fallback Paths**: Always provide both primary (simulation_events) and fallback (dedicated table) reconstruction
4. **Credit Calculation**: Some metrics (credit utilization) must be calculated, not just retrieved
```

### 3.2 Create docs/architecture/replay-system.md

**Content**:
- Detailed architecture diagrams (with Mermaid)
- Sequence diagrams for run vs replay
- Data flow from Rust → DuckDB → Python
- Event lifecycle documentation
- StateProvider contract specification
- Persistence schema reference

### 3.3 Update api/CLAUDE.md

**Additions**:

```markdown
## Event Reconstruction Patterns

When adding new event types, follow these patterns:

### Pattern 1: Primary + Fallback

```python
# Primary: Reconstruct from simulation_events (rich detail)
lsm_from_events = _reconstruct_lsm_events_from_simulation_events(lsm_events_raw)

# Fallback: Reconstruct from dedicated table (if simulation_events missing)
lsm_from_table = _reconstruct_lsm_events(lsm_data)

# Prefer primary, use fallback
lsm_events = lsm_from_events if lsm_from_events else lsm_from_table
```

**Why**: Older databases may not have full simulation_events data. Graceful degradation.

### Pattern 2: Detail Extraction

```python
def _reconstruct_event_from_simulation_events(events: list[dict]) -> list[dict]:
    result = []
    for event in events:
        details = event.get("details", {})  # Details stored as JSON

        result.append({
            "event_type": event["event_type"],
            # Extract from details, not top-level
            "field_a": details.get("field_a", default_value),
            "field_b": details.get("field_b") or details.get("alternate_name", 0),
        })
    return result
```

**Watch out**: Field names may differ between Rust and Python. Check FFI serialization.

### Pattern 3: State Calculation

Some display values must be **calculated** from state, not retrieved:

```python
# ❌ WRONG: Expecting pre-calculated value
credit_util = agent_state.get("credit_utilization", 0)

# ✅ CORRECT: Calculate from balance and limit
balance = agent_state["balance"]
credit_limit = agent_state["credit_limit"]
if credit_limit > 0:
    used = max(0, credit_limit - balance)
    credit_util = (used / credit_limit) * 100
```

**Rule**: If run output shows calculated metric, replay must use same calculation.
```

---

## Phase 4: Continuous Improvement

### 4.1 Monthly Replay Audit

**Schedule**: First week of each month

**Process**:
1. Run comprehensive simulation suite with `--persist --full-replay`
2. Replay all simulations
3. Compare outputs programmatically
4. File bug reports for any divergence
5. Add regression test

### 4.2 Event Schema Evolution Policy

**Rule**: New Rust Event variants require:
- [ ] FFI serialization test
- [ ] Persistence test (can save/load)
- [ ] Reconstruction test (can display in replay)
- [ ] Documentation update

**Template**: `.claude/templates/new-event-checklist.md`

---

## Success Metrics

1. **Zero Divergence**: `test_full_tick_output_identity` passes on all configs
2. **Fast Feedback**: Pre-commit hook catches 90%+ of violations before commit
3. **Clear Documentation**: New contributors understand StateProvider pattern
4. **Maintainable Tests**: Integration test suite runs in <30 seconds

---

## Implementation Timeline

| Phase | Tasks | Est. Effort | Priority |
|-------|-------|-------------|----------|
| 1 | Automated Testing | 2 days | P0 |
| 2 | Architectural Guardrails | 1 day | P0 |
| 3 | Documentation | 1 day | P1 |
| 4 | Continuous Improvement | Ongoing | P2 |

**Next Steps**: Implement Phase 1.2 (end-to-end test) as highest-value task

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Database schema changes break old replays | Medium | High | Version schema, add migration tests |
| New developer bypasses StateProvider | Medium | High | Pre-commit hook, code review checklist |
| Performance degradation from extra checks | Low | Medium | Profile tests, optimize hot paths |
| Test brittleness from output formatting changes | High | Low | Use semantic diff, not string comparison |

---

## Appendix: Lessons Learned

### Bug #1: LSM Events Missing (Primary Path)
- **Cause**: Collected events but didn't use them
- **Fix**: Created `_reconstruct_lsm_events_from_simulation_events()`
- **Lesson**: Always use collected data or don't collect it

### Bug #2: Bilateral Offset Detection (Fallback Path)
- **Cause**: Wrong array length check (2 vs 3)
- **Fix**: Changed to `len(agent_ids) == 3`
- **Lesson**: Document data model assumptions in comments

### Bug #3: Deadline Ticks Show Tick 0
- **Cause**: Wrong field name (`deadline_tick` vs `deadline`)
- **Fix**: Check both field names
- **Lesson**: Field name consistency across FFI boundary is critical

### Bug #4: Credit Utilization Shows 0%
- **Cause**: Hardcoded 0 instead of calculating
- **Fix**: Implemented calculation in replay
- **Lesson**: Calculated metrics must use same formula in both paths

---

**Last Updated**: 2025-01-09
**Next Review**: 2025-02-09
