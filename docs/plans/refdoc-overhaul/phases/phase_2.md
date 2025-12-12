# Phase 2: Architecture Docs Cleanup

**Status**: Completed (High Priority)
**Scope**: `docs/reference/architecture/`

---

## Objective

Clean up architecture documentation by:
1. Preserving excellent Mermaid diagrams
2. Removing line counts and statistics that will go stale
3. Removing struct/class definitions
4. Removing meta-documentation files
5. Updating import examples to be minimal

---

## Files to Process

| File | Priority | Action |
|------|----------|--------|
| `appendix-a-module-reference.md` | High | Remove line counts from tables |
| `02-rust-core-engine.md` | High | Remove struct defs, keep diagrams |
| `05-domain-models.md` | High | Check for code duplication |
| `03-python-api-layer.md` | Medium | Check for class implementations |
| `04-ffi-boundary.md` | Medium | Keep safety rules, check for code |
| `06-settlement-engines.md` | Medium | Keep algorithm flowcharts |
| `07-policy-system.md` | Medium | Keep decision flow |
| `08-event-system.md` | Medium | Keep event catalog tables |
| `09-persistence-layer.md` | Medium | Keep schema overview |
| `10-cli-architecture.md` | Low | Keep component diagram |
| `11-tick-loop-anatomy.md` | Low | Keep flowchart |
| `12-cost-model.md` | Low | Keep cost formulas |
| `ARCHITECTURE_DOCUMENTATION_PLAN.md` | High | **Delete** (meta-doc) |
| `appendix-b-event-catalog.md` | Medium | Review for relevance |
| `appendix-c-configuration-reference.md` | Medium | May duplicate scenario/ |

---

## Execution Steps

### Step 1: Delete Meta-Documentation

Delete `ARCHITECTURE_DOCUMENTATION_PLAN.md` - internal planning doc, not reference.

### Step 2: Clean appendix-a-module-reference.md

**Problems:**
- Line counts per file will go stale
- Total line statistics will go stale
- Code blocks showing imports

**Actions:**
- Remove `Lines` column from Rust module table
- Remove `Lines` column from Python module table
- Remove "Total Lines: ~19,445" statistic
- Keep module/file/purpose information
- Convert code blocks to import tables

### Step 3: Clean 02-rust-core-engine.md

**Problems:**
- "19,445 lines of code" statistic
- May contain struct definitions

**Actions:**
- Remove line count from overview
- Keep all Mermaid diagrams
- Convert any struct definitions to field tables
- Keep module responsibility descriptions

### Step 4: Review Remaining Files

For each remaining file, check for:
- [ ] Line number references
- [ ] Full struct/class definitions
- [ ] Stale statistics
- [ ] Duplicate content with other docs

Files with good content to preserve:
- Mermaid diagrams (architecture flow)
- Component responsibility tables
- Algorithm descriptions

---

## Completion Criteria

- [x] `ARCHITECTURE_DOCUMENTATION_PLAN.md` deleted
- [x] `appendix-a-module-reference.md` has no line counts
- [x] `02-rust-core-engine.md` has no line counts
- [x] All Mermaid diagrams preserved
- [ ] Medium/low priority files reviewed (deferred - good quality already)
- [ ] Links verified working

---

## Next Phase

After completion, proceed to [Phase 3: Scenario Docs](phase_3.md).
