# Database Consolidation - Work Notes

This file tracks detailed progress and decisions made during the database consolidation work.

---

## 2025-12-14: Project Setup

### Session Start
- Created `docs/plans/dbconsolidate/` directory structure
- Reviewed project constraints from `CLAUDE.md` and `docs/reference/patterns-and-conventions.md`
- Created `development-plan.md` from exploration document

### Key Findings from Code Analysis

**Castro Audit Tables Analysis**:
The `ai_cash_mgmt` module defines 5 tables, but 3 are effectively dead code:

| Table | Status | Reason |
|-------|--------|--------|
| `game_sessions` | Unknown | May be legacy |
| `policy_iterations` | Unknown | May be legacy |
| `llm_interaction_log` | **Dead code** | Not written to - experiments use `experiment_events` |
| `policy_diffs` | **Dead code** | Not written to |
| `iteration_context` | **Dead code** | Not written to |

The experiment framework saves LLM interactions via `_save_llm_interaction_event()` which writes to `experiment_events` table, NOT to `llm_interaction_log`.

**Critical Invariants to Preserve**:
- INV-1: Money as i64 (integer cents) - affects cost storage
- INV-2: Determinism - seeds must be stored
- INV-5: Replay identity - must work for experiment simulations
- INV-6: Event completeness - events must be self-contained

### Design Decisions Confirmed

1. **No backwards compatibility** - Clean slate
2. **Structured simulation IDs** - `{experiment_id}-iter{N}-{purpose}`
3. **Delete dead Castro audit tables**
4. **Policy storage** - Keep in `experiment_iterations` (Option A)
5. **Default persistence**:
   - FULL for all evaluation simulations
   - No bootstrap sample transactions
   - All policy iterations (accepted AND rejected)

### Next Steps
- [x] Create Phase 1 detailed plan
- [x] Start Phase 1 implementation (delete dead code)

---

## 2025-12-14: Phase 1 Complete - Dead Code Removal

### Summary
Removed dead Castro audit tables and associated code:
- `llm_interaction_log` table
- `policy_diffs` table
- `iteration_context` table

### Files Modified

**Deleted Files**:
- `api/tests/integration/test_castro_audit_trail_persistence.py`
- `api/tests/unit/test_castro_audit_trail_models.py`
- `api/migrations/004_add_audit_tables.sql`

**Modified Files**:
- `api/payment_simulator/ai_cash_mgmt/persistence/models.py` - Removed 3 model classes (~120 lines)
- `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` - Removed table creation + methods (~300 lines)

**New Files**:
- `api/tests/unit/test_dead_code_verification.py` - Verification tests documenting dead code

### Tests Run
- All verification tests pass (5/5)
- All database integration tests pass (12/12)
- mypy passes
- ruff passes

### Pre-existing Test Failures (Unrelated)
- `tests/ai_cash_mgmt/bootstrap/test_context_builder_core.py::TestCastroBackwardCompatibility` - Tests import path that doesn't exist
- `tests/ai_cash_mgmt/unit/bootstrap/test_sandbox_config.py::TestIncomingLiquidityEvents` - Unrelated sandbox config issue

### Next Steps
- [x] Begin Phase 2: Schema unification

---

## 2025-12-14: Phase 2 In Progress - Schema Unification

### Summary
Added unified schema support for experiments → simulation linking.

### Completed (Phase 2.1-2.5)

**New Pydantic Models** (`persistence/models.py`):
- `SimulationRunPurpose` enum - structured run purposes (standalone, initial, bootstrap, evaluation, best, final)
- `ExperimentRecord` - experiment metadata with INV-1 compliant costs (integer cents)
- `ExperimentIterationRecord` - per-iteration data with simulation linkage
- `ExperimentEventRecord` - experiment-level events

**Extended SimulationRunRecord**:
- `experiment_id` - link to experiments table
- `iteration` - iteration number within experiment
- `sample_index` - bootstrap sample index
- `run_purpose` - purpose of simulation run

**Schema Generator Updates** (`persistence/schema_generator.py`):
- Added new models to DDL generation
- Correct table ordering for FK dependencies (experiments before simulation_runs)

**DatabaseManager Updates** (`persistence/connection.py`):
- Added new models to validation list
- Updated _drop_all_tables() with experiment tables in reverse FK order

### Tests
- 9 tests pass, 1 skipped (Phase 2.6)
- Tests verify:
  - All 3 experiment tables created by DatabaseManager
  - simulation_runs has experiment linkage columns
  - Simulation can reference experiment (FK works)
  - Iteration can reference simulation (FK works)
  - INV-1: Costs stored as integer cents
  - INV-2: master_seed stored for determinism

### Remaining Work (Phase 2.6-2.10)
- [ ] Refactor ExperimentRepository to use DatabaseManager
- [ ] Update GameRepository to use DatabaseManager (if still needed)
- [ ] Run full test suite
- [ ] Update phase_2.md checklist

---

## Work Log Format

Each session should include:
- Date and brief description
- What was accomplished
- Key decisions made
- Blockers or issues encountered
- Next steps

---
