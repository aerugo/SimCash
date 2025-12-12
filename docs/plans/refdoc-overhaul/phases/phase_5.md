# Phase 5: API/CLI Docs Cleanup

**Status**: Complete
**Scope**: `docs/reference/api/`, `docs/reference/cli/`

---

## Objective

Review and clean API/CLI documentation by:
1. Checking for line number references
2. Checking for Source Code Reference tables
3. Verifying code examples are user-facing (not implementation)

---

## Assessment

### API Docs (`docs/reference/api/`)

Files reviewed:
- `endpoints.md` - Clean (endpoint tables, examples)
- `index.md` - Clean (navigation)
- `output-strategies.md` - Clean (usage patterns with Mermaid diagrams)
- `state-provider.md` - Clean (pattern explanation with usage examples)

**Findings**: These docs contain:
- Usage examples showing how to call APIs
- Mermaid diagrams explaining patterns
- Python code showing API consumption (user-facing)
- `**Source:**` references without line numbers (acceptable)

No cleanup needed.

### CLI Docs (`docs/reference/cli/`)

Files reviewed:
- `commands/*.md` - All clean (synopsis, options, examples)
- `exit-codes.md` - Clean
- `filtering.md` - Clean
- `output-modes.md` - Clean
- `index.md` - Navigation

**Findings**: CLI docs follow good patterns:
- Command synopsis and option tables
- Example invocations (bash)
- Example output (JSON)
- Implementation Details sections only name the file (no line numbers)

**One exception**: `policy-schema.md` shows line number references in its **output examples**, but this is correct because the command itself outputs source locations. This documents the command's behavior, not implementation details.

No cleanup needed.

---

## Notes

The API/CLI docs were likely written later and already follow the gold standard pattern:
- User-facing examples
- Option/parameter tables
- Mermaid diagrams for architecture
- No full class/struct implementations

---

## Completion Criteria

- [x] API docs reviewed (4 files)
- [x] CLI docs reviewed (12 files)
- [x] No line number references found (except in command output examples)
- [x] No Source Code Reference tables
- [x] All code examples are user-facing

---

## Next Phase

After completion, proceed to [Phase 6: Remaining Modules](phase_6.md).
