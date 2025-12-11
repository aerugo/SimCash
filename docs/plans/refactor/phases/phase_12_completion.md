# Phase 12 Completion Plan

**Status:** Partially Complete
**Created:** 2025-12-11
**Updated:** 2025-12-11

---

## Current State Assessment

### Phase 11 Status: COMPLETE ✅

Core infrastructure exists and is functional:

| Component | Location | Status |
|-----------|----------|--------|
| `ExperimentStateProviderProtocol` | `experiments/runner/state_provider.py` | ✅ |
| `LiveStateProvider` | `experiments/runner/state_provider.py` | ✅ |
| `DatabaseStateProvider` | `experiments/runner/state_provider.py` | ✅ |
| `ExperimentRepository` | `experiments/persistence/repository.py` | ✅ |
| `EventRecord` | `experiments/persistence/repository.py` | ✅ |

### Phase 12 Status: PARTIALLY COMPLETE

| Task | Description | Status |
|------|-------------|--------|
| 12.1 | Move event system to core | ✅ DONE |
| 12.2 | Delete Castro infrastructure | ❌ NOT DONE |
| 12.3 | Update Castro to use core | ❌ PARTIAL |

### What Was Done in Phase 12.1

1. **Created `ai_cash_mgmt/events.py`** with:
   - Event type constants
   - Event creation helpers returning `EventRecord`

2. **Created `castro/event_compat.py`** with:
   - `CastroEvent` wrapper providing `.details` alias for `.event_data`
   - Allows gradual migration from Castro events to core events

3. **Updated Castro files** to import events from core

4. **Deleted `castro/events.py`** (moved to core)

### What Was NOT Done

1. **Did NOT delete Castro infrastructure:**
   - `castro/state_provider.py` - kept, modified
   - `castro/persistence/repository.py` - kept, modified
   - `castro/persistence/models.py` - kept

2. **Did NOT migrate Castro to use core infrastructure:**
   - Castro still uses its own `LiveExperimentProvider` (not core `LiveStateProvider`)
   - Castro still uses its own `ExperimentEventRepository` (not core `ExperimentRepository`)

---

## Why We Deviated

The original Phase 12 plan assumed Castro could simply switch to core infrastructure. In practice:

1. **Different APIs**: Castro's `LiveExperimentProvider` has methods like `capture_event()` and `set_final_result()` that core's `LiveStateProvider` uses differently (`record_event()`, `record_iteration()`)

2. **Event format differences**: Castro expects `.details`, core uses `.event_data`

3. **Test coupling**: 335+ Castro tests depend on Castro's infrastructure APIs

The pragmatic choice was to:
- Move event definitions to core ✅
- Add compatibility layer ✅
- Defer infrastructure deletion to avoid breaking tests

---

## Completion Plan

### Option A: Full Migration (Recommended)

Migrate Castro to use core infrastructure completely, then delete Castro's duplicates.

#### Task 12.2A: Migrate Castro to Core LiveStateProvider

**Goal:** Replace `castro/state_provider.py:LiveExperimentProvider` with core's `LiveStateProvider`

**Steps:**
1. Map Castro API to core API:
   ```
   Castro                          Core
   ------                          ----
   capture_event(event)     →     record_event(iteration, type, data)
   set_final_result(...)    →     set_converged(bool, reason)
   get_all_events()         →     get_iteration_events(iteration)
   ```

2. Update `castro/runner.py` to use core `LiveStateProvider`:
   ```python
   # Before
   from castro.state_provider import LiveExperimentProvider
   provider = LiveExperimentProvider(run_id=..., experiment_name=...)

   # After
   from payment_simulator.experiments.runner import LiveStateProvider
   provider = LiveStateProvider(experiment_name=..., experiment_type="castro", config=...)
   ```

3. Update all Castro code that creates events:
   ```python
   # Before
   event = create_llm_interaction_event(...)
   provider.capture_event(event)

   # After
   event = create_llm_interaction_event(...)
   provider.record_event(event.iteration, event.event_type, event.event_data)
   ```

4. Update tests to use new APIs

**Files to modify:**
- `castro/runner.py`
- `castro/display.py`
- `castro/audit_display.py`
- All test files using `LiveExperimentProvider`

#### Task 12.2B: Migrate Castro to Core ExperimentRepository

**Goal:** Replace `castro/persistence/repository.py` with core's `ExperimentRepository`

**Steps:**
1. Map Castro API to core API:
   ```
   Castro                              Core
   ------                              ----
   ExperimentEventRepository     →     ExperimentRepository
   save_run_record(record)       →     save_experiment(ExperimentRecord)
   save_event(event)             →     save_event(EventRecord)
   get_run_record(run_id)        →     load_experiment(run_id)
   get_events_for_run(run_id)    →     get_all_events(run_id)
   ```

2. Update `castro/cli.py` replay command:
   ```python
   # Before
   from castro.persistence.repository import ExperimentEventRepository
   repo = ExperimentEventRepository(conn)

   # After
   from payment_simulator.experiments.persistence import ExperimentRepository
   repo = ExperimentRepository(db_path)
   ```

3. Update Castro to save using core records:
   ```python
   # Before
   from castro.persistence.models import ExperimentRunRecord
   record = ExperimentRunRecord(...)
   repo.save_run_record(record)

   # After
   from payment_simulator.experiments.persistence import ExperimentRecord
   record = ExperimentRecord(...)
   repo.save_experiment(record)
   ```

**Files to modify:**
- `castro/cli.py`
- `castro/runner.py`
- All test files using persistence

#### Task 12.2C: Delete Castro Infrastructure

After migration is complete and all tests pass:

**Files to delete:**
- `castro/state_provider.py`
- `castro/persistence/repository.py`
- `castro/persistence/models.py`
- `castro/event_compat.py`
- `castro/persistence/__init__.py` (if empty)

#### Task 12.2D: Update Castro Re-exports

Update `castro/__init__.py` to re-export from core:

```python
# castro/__init__.py
from payment_simulator.experiments.runner import (
    LiveStateProvider,
    DatabaseStateProvider,
    ExperimentStateProviderProtocol,
)
from payment_simulator.experiments.persistence import (
    ExperimentRepository,
    ExperimentRecord,
    IterationRecord,
    EventRecord,
)
from payment_simulator.ai_cash_mgmt.events import (
    EVENT_LLM_INTERACTION,
    EVENT_POLICY_CHANGE,
    create_llm_interaction_event,
    # ... etc
)
```

---

### Option B: Keep Compatibility Layer (Minimal Change)

Keep the current state with compatibility layer. Castro continues using its own infrastructure but events come from core.

**Pros:**
- No additional work required
- Tests continue to pass
- Lower risk

**Cons:**
- Code duplication remains
- Two parallel infrastructures
- Doesn't achieve Phase 12's goal of "Castro reduced to ~200 lines"

---

## Recommended Approach

**Phase 12.2-12.3: Incremental Migration**

```
Phase 12.2a: Migrate runner.py to core LiveStateProvider (~2-3 hours)
Phase 12.2b: Migrate CLI replay to core DatabaseStateProvider (~1-2 hours)
Phase 12.2c: Migrate persistence to core ExperimentRepository (~2-3 hours)
Phase 12.2d: Delete Castro infrastructure files (~30 min)
Phase 12.2e: Update tests (~2-3 hours)
```

**TDD Tests to Write First:**

1. `test_castro_uses_core_live_provider.py`:
   - Test Castro runner uses `LiveStateProvider`
   - Test events are recorded correctly
   - Test iteration data is recorded

2. `test_castro_uses_core_repository.py`:
   - Test Castro saves via `ExperimentRepository`
   - Test replay loads via `ExperimentRepository`
   - Test event persistence round-trip

3. `test_castro_infrastructure_deleted.py`:
   - Test `castro/state_provider.py` doesn't exist
   - Test `castro/persistence/` doesn't exist
   - Test Castro line count < 500

---

## Verification Checklist

### Before Starting
- [ ] All current tests pass (335 Castro, 84 core)
- [ ] Core infrastructure verified functional

### After Each Task
- [ ] All tests pass
- [ ] Type checking passes
- [ ] CLI commands work

### Final Verification
- [ ] `castro/state_provider.py` deleted
- [ ] `castro/persistence/` deleted
- [ ] `castro/event_compat.py` deleted
- [ ] Castro imports from core work
- [ ] Castro CLI run works
- [ ] Castro CLI replay works
- [ ] Total Castro code < 500 lines

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| API incompatibility | High | Add adapter methods if needed |
| Test failures | Medium | Fix tests incrementally |
| Database schema mismatch | Medium | Core schema is flexible (JSON) |
| pydantic_ai dependency | Low | Unrelated to infrastructure |

---

*Phase 12 Completion Plan v1.0 - 2025-12-11*
