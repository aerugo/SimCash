# Phase 4: Policy Docs Cleanup

**Status**: Complete
**Scope**: `docs/reference/policy/`

---

## Objective

Clean up policy DSL documentation by:
1. Removing line number references
2. Removing "Implementation Location" and "Source Code Reference" sections
3. Keeping JSON examples (user-facing DSL syntax)
4. Keeping field reference tables
5. Keeping behavioral descriptions

---

## Files to Process

| File | Priority | Issues Found |
|------|----------|--------------|
| `nodes.md` | High | Line numbers, Implementation Location sections |
| `trees.md` | High | Line numbers, Source Code Reference table |
| `actions.md` | Medium | Line number references |
| `integration.md` | Medium | Line numbers, Rust code blocks |
| `validation.md` | Medium | Line numbers, Rust/Python code |
| `values.md` | Medium | Line numbers, Rust code |
| `configuration.md` | Low | Rust code blocks |
| `computations.md` | Low | Check for issues |
| `context-fields.md` | Low | Gold standard, minimal cleanup |
| `expressions.md` | Low | Check for issues |
| `cross-reference.md` | Low | Check for issues |
| `index.md` | Low | Navigation, keep as-is |

---

## Execution Steps

### Step 1: Clean `nodes.md`

**Problems identified:**
- "Implementation Location" subsections with line numbers
- "Source Code Reference" table at bottom

**Actions:**
- Remove all "Implementation Location" sections
- Remove "Source Code Reference" table
- Keep JSON examples (DSL syntax)
- Keep field reference tables

### Step 2: Clean `trees.md`

**Problems identified:**
- "Implementation Location" subsections with line numbers
- "Source Code Reference" table at bottom

**Actions:**
- Same as nodes.md

### Step 3: Clean remaining files

For each remaining file, remove:
- Line number references
- Implementation/Source Code Reference sections
- Full Rust/Python code blocks
Keep:
- JSON DSL examples
- Behavior descriptions
- Field tables

---

## Notes

The policy docs are special because:
- JSON examples ARE the user-facing interface (not implementation details)
- The DSL syntax IS what users write
- These should be preserved, unlike Python/Rust code

---

## Completion Criteria

- [x] `nodes.md` has no line numbers
- [x] `trees.md` has no line numbers
- [x] `actions.md` cleaned
- [x] `integration.md` cleaned
- [x] `validation.md` cleaned
- [x] `values.md` cleaned
- [x] `configuration.md` cleaned
- [x] `expressions.md` cleaned
- [x] `computations.md` cleaned
- [x] `context-fields.md` cleaned
- [x] JSON DSL examples preserved throughout
- [x] Field reference tables preserved

---

## Next Phase

After completion, proceed to [Phase 5: API/CLI Docs](phase_5.md).
