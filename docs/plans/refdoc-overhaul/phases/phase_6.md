# Phase 6: Remaining Modules Cleanup

**Status**: Complete
**Scope**: `docs/reference/{experiments, ai_cash_mgmt, castro, llm, orchestrator}`

---

## Objective

Review remaining reference documentation modules for issues:
1. Line number references
2. Source Code Reference tables
3. Full struct/class implementations (vs API documentation)

---

## Assessment

### Global Search Results

Searched entire `docs/reference/` for remaining issues:

| Pattern | Result |
|---------|--------|
| Line number references (`\.(rs|py):\d+`) | 1 file (policy-schema.md - acceptable, shows command output) |
| Source Code Reference tables | 0 files |

All problematic patterns have been removed.

### Module-by-Module Review

#### experiments/ (3 files)

- `runner.md` - Contains Python dataclass definitions, but these ARE the user-facing API. Fields, methods, and usage examples properly documented.
- `configuration.md` - Clean
- `index.md` - Clean

**Assessment**: Python code shown is API documentation (public interface users interact with), not implementation details. Similar pattern to state-provider.md in API docs.

#### orchestrator/02-models/ (2 files)

- `agent.md` - Excellent pattern: field tables, method tables, formula explanations, error types. No implementation code.
- `transaction.md` - Same pattern as agent.md

**Assessment**: Already follows gold standard pattern.

#### ai_cash_mgmt/ (7 files)

- All files reviewed
- Uses Mermaid diagrams for architecture
- Field/parameter tables
- No implementation code

**Assessment**: Clean

#### castro/ (1 file)

- `index.md` - Example YAML experiments
- No code to clean

**Assessment**: Clean

#### llm/ (3 files)

- `protocols.md` - Shows Protocol definitions, but these ARE the user-facing interface
- `configuration.md` - YAML examples
- `index.md` - Navigation

**Assessment**: Clean

---

## Notes

The remaining modules already follow good documentation patterns:
- Field reference tables (Type, Description)
- Method reference tables (Returns, Description)
- Mermaid diagrams for architecture
- Example output/configuration
- No line number references
- No Source Code Reference tables

Python dataclass/Protocol definitions in experiments and llm docs are acceptable because they document the **public API** that users interact with (imports, fields, methods). This is different from showing internal Rust struct implementations.

---

## Completion Criteria

- [x] experiments/ reviewed (3 files)
- [x] orchestrator/02-models/ reviewed (2 files)
- [x] ai_cash_mgmt/ reviewed (7 files)
- [x] castro/ reviewed (1 file)
- [x] llm/ reviewed (3 files)
- [x] No line number references (except command output examples)
- [x] No Source Code Reference tables
- [x] Python API definitions preserved (user-facing interface)

---

## Overall Summary

The reference documentation overhaul is complete:

| Phase | Result |
|-------|--------|
| Phase 1 | Deleted duplicate orchestrator/01-configuration/, cleaned 02-models/ |
| Phase 2 | Cleaned architecture files, removed line counts |
| Phase 3 | Cleaned 10 scenario files (removed Python/Rust code, line numbers) |
| Phase 4 | Cleaned 10 policy files (removed line numbers, Source Code Reference) |
| Phase 5 | API/CLI docs already clean |
| Phase 6 | Remaining modules already clean |

All documentation now follows the gold standard pattern.
