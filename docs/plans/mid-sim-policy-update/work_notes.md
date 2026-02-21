# Mid-Simulation Policy Update — Work Notes

**Project**: Add `update_agent_policy` to Orchestrator for mid-sim policy swaps
**Started**: 2025-07-11
**Branch**: `feature/mid-sim-policy-update`

---

## Session Log

### 2025-07-11 — Planning

**Context Review**:
- Read Nash's handover: `docs/reports/handover-dennis-mid-sim-policy-update.md`
- Verified code pointers: `engine.rs:755` (policies HashMap), `factory.rs:140` (FromJson path)
- Identified consistency issue: `get_agent_policies()` reads from `self.config`, not `self.policies` — must update both on swap

**Applicable Invariants**:
- INV-2: Determinism — same swaps at same ticks = identical output
- INV-4: Balance conservation — swap must not corrupt state
- INV-5: Replay identity — save_state must capture swapped policy
- INV-9: Policy eval identity — use `create_policy()` standard path

**Key Insight**: `get_agent_policies()` at `engine.rs:2569` reads from `self.config.agent_configs`, not the live `self.policies` HashMap. A naive swap that only updates `self.policies` would leave `get_agent_policies()` and `save_state()` returning stale policy configs. Must update `self.config.agent_configs[].policy` too.

**Completed**:
- [x] Read handover doc
- [x] Verified all code pointers
- [x] Created development plan

**Next Steps**:
1. Write Phase 1 detailed plan
2. Write failing Rust tests (RED)
3. Implement `update_agent_policy` (GREEN)

---

## Key Decisions

### Decision 1: Update both `self.policies` and `self.config`
**Rationale**: `get_agent_policies()` and `save_state()` read from config, not the live HashMap. Without updating config, checkpoint-restore loses the swapped policy.

### Decision 2: No policy swap event
**Rationale**: Nash tracks policy history in the web backend. The engine treats this as an external control action, not a simulation event. Keeps event stream clean and avoids replay complications.

---

## Files Modified

### Created
- `docs/plans/mid-sim-policy-update/development-plan.md`
- `docs/plans/mid-sim-policy-update/work_notes.md`
