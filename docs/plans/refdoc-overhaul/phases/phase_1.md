# Phase 1: Remove Duplicate Configuration Docs

**Status**: Completed
**Scope**: `docs/reference/orchestrator/01-configuration/`

---

## Objective

Delete the `orchestrator/01-configuration/` directory which duplicates content already present in `scenario/`.

---

## Pre-Execution Checklist

- [x] Verified `scenario/` covers all configuration topics
- [x] Confirmed `orchestrator/01-configuration/` is true duplication (not different perspective)
- [ ] Check for internal links pointing to files being deleted
- [ ] Verify no unique content in files to be deleted

---

## Files to Delete

| File | Reason | Replacement |
|------|--------|-------------|
| `orchestrator/01-configuration/agent-config.md` | Duplicates agent configuration | `scenario/agents.md` |
| `orchestrator/01-configuration/arrival-config.md` | Duplicates arrival configuration | `scenario/arrivals.md` |
| `orchestrator/01-configuration/cost-rates.md` | Duplicates cost configuration | `scenario/cost-rates.md` |
| `orchestrator/01-configuration/lsm-config.md` | Duplicates LSM configuration | `scenario/lsm-config.md` |
| `orchestrator/01-configuration/orchestrator-config.md` | Duplicates simulation settings | `scenario/simulation-settings.md` |
| `orchestrator/01-configuration/scenario-events.md` | Duplicates scenario events | `scenario/scenario-events.md` |

---

## Files to Update

### `orchestrator/index.md`

**Action**: Remove references to `01-configuration/` section, keep only `02-models/` references.

### `orchestrator/02-models/agent.md`

**Action**:
- Remove full struct definition
- Remove line number references
- Convert to field reference tables
- Keep behavioral descriptions (methods, lifecycle)

### `orchestrator/02-models/transaction.md`

**Action**:
- Remove full struct definition
- Remove line number references
- Convert to field reference tables
- Keep lifecycle state machine, split transaction logic

---

## Link Verification Required

Search for links pointing to deleted files:

```bash
# Find all markdown links to orchestrator/01-configuration/
grep -r "orchestrator/01-configuration" docs/
grep -r "01-configuration" docs/reference/
```

Any found links must be updated to point to `scenario/` equivalents.

---

## Execution Steps

### Step 1: Verify No Unique Content

Before deleting, confirm each file in `01-configuration/` has no unique content missing from `scenario/`:

1. Compare `agent-config.md` vs `scenario/agents.md`
2. Compare `arrival-config.md` vs `scenario/arrivals.md`
3. Compare `cost-rates.md` vs `scenario/cost-rates.md`
4. Compare `lsm-config.md` vs `scenario/lsm-config.md`
5. Compare `orchestrator-config.md` vs `scenario/simulation-settings.md`
6. Compare `scenario-events.md` vs `scenario/scenario-events.md`

### Step 2: Find and Update Links

Search entire `docs/` directory for references to files being deleted. Update to new locations.

### Step 3: Delete Files

Delete the `orchestrator/01-configuration/` directory.

### Step 4: Update `orchestrator/index.md`

Remove the "Configuration" section, update to only reference "Models".

### Step 5: Clean `orchestrator/02-models/` (Code Removal)

For each file in `02-models/`:
1. Remove full struct definitions (the `pub struct Agent { ... }` blocks)
2. Remove line number references (`agent.rs:144`)
3. Convert field documentation to tables
4. Preserve behavioral content (methods, lifecycle, concepts)

### Step 6: Verify Build/Links

Ensure no broken links remain.

---

## Rollback Plan

If issues discovered:
1. Git revert the deletion commit
2. Document what unique content was found
3. Update plan to preserve/migrate that content

---

## Completion Criteria

- [x] `orchestrator/01-configuration/` directory deleted
- [x] No broken links in `docs/reference/`
- [x] `orchestrator/index.md` updated
- [x] `orchestrator/02-models/agent.md` cleaned (no struct defs, no line numbers)
- [x] `orchestrator/02-models/transaction.md` cleaned (no struct defs, no line numbers)

---

## Next Phase

After completion, proceed to [Phase 2: Architecture Docs](phase_2.md).
