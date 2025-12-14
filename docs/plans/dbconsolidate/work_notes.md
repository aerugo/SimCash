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
- [ ] Create Phase 1 detailed plan
- [ ] Start Phase 1 implementation (delete dead code)

---

## Work Log Format

Each session should include:
- Date and brief description
- What was accomplished
- Key decisions made
- Blockers or issues encountered
- Next steps

---
