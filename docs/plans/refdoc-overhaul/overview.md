# Reference Documentation Overhaul - Overview

**Status**: In Progress
**Created**: 2025-12-12
**Location**: `docs/plans/refdoc-overhaul/`

---

## Quick Summary (For AI Agents)

**Problem**: `docs/reference/` contains excessive code duplication - Rust structs, Python classes, and line number references copied verbatim from source files. This creates maintenance burden and obscures conceptual understanding.

**Solution**: Transform documentation to explain behavior, show diagrams, provide configuration examples, and use field reference tables instead of duplicating code.

**Gold Standard**: `docs/reference/policy/context-fields.md` - field tables with Type, Unit, Description columns.

---

## Phase Overview

| Phase | Focus | Status | Details |
|-------|-------|--------|---------|
| 1 | Remove Duplicates | **Complete** | [phase_1.md](phases/phase_1.md) |
| 2 | Architecture Docs | **Complete** | [phase_2.md](phases/phase_2.md) |
| 3 | Scenario Docs | Pending | [phase_3.md](phases/phase_3.md) |
| 4 | Policy Docs | Pending | [phase_4.md](phases/phase_4.md) |
| 5 | API/CLI Docs | Pending | [phase_5.md](phases/phase_5.md) |
| 6 | Remaining Modules | Pending | [phase_6.md](phases/phase_6.md) |

---

## Key Decisions

### What to Remove
- Full struct/class definitions
- Line number references (e.g., `file.rs:123`)
- Python validator implementations
- Duplicate content across files

### What to Keep
- Mermaid diagrams
- Field reference tables
- YAML/JSON configuration examples
- CLI command examples
- Behavioral descriptions

### Acceptable vs Unacceptable Code

**ACCEPTABLE** (user-facing):
- YAML/JSON configuration examples
- CLI commands (`payment-sim run --config ...`)
- Import statements showing usage
- Short usage snippets (3-5 lines)
- Mathematical formulas

**UNACCEPTABLE** (implementation details):
- Full struct/class definitions
- Validator/method implementations
- Full Protocol definitions
- Line number references

---

## Documentation Redundancy Map

### TRUE Duplicates (Delete)

`orchestrator/01-configuration/` duplicates `scenario/`:

| To Delete | Already Covered In |
|-----------|-------------------|
| `orchestrator/01-configuration/agent-config.md` | `scenario/agents.md` |
| `orchestrator/01-configuration/arrival-config.md` | `scenario/arrivals.md` |
| `orchestrator/01-configuration/cost-rates.md` | `scenario/cost-rates.md` |
| `orchestrator/01-configuration/lsm-config.md` | `scenario/lsm-config.md` |
| `orchestrator/01-configuration/orchestrator-config.md` | `scenario/simulation-settings.md` |
| `orchestrator/01-configuration/scenario-events.md` | `scenario/scenario-events.md` |

### Different Purposes (Keep Both, Clean Up)

| File | Purpose |
|------|---------|
| `scenario/agents.md` | **Configuration**: How to write agent YAML |
| `orchestrator/02-models/agent.md` | **Runtime**: Agent methods (`debit()`, `credit()`), state lifecycle |
| `architecture/05-domain-models.md` | **Overview**: High-level model diagrams |

---

## Templates

### Configuration Reference Template

```markdown
# Feature Name

Brief description.

---

## Quick Start

\`\`\`yaml
feature:
  required_field: value
\`\`\`

---

## Field Reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `field_name` | `int` | Yes | - | What it does |

---

## Examples

### Basic Usage
\`\`\`yaml
...
\`\`\`

---

## Related

- [Related Topic](link.md)
```

### Architecture Reference Template

```markdown
# Component Name

Brief description of purpose.

---

## Overview

\`\`\`mermaid
flowchart TB
    ...
\`\`\`

---

## Responsibilities

- What this component does

---

## Key Concepts

### Concept 1
Description without code.

---

## Interactions

\`\`\`mermaid
sequenceDiagram
    ...
\`\`\`

---

## Related

- [Related Component](link.md)
```

---

## Success Criteria

1. No source code (Rust structs, Python classes) in docs
2. No line number references
3. No duplicated content between files
4. All Mermaid diagrams preserved/enhanced
5. Examples are user-facing (YAML, CLI, not implementation)
6. All internal links verified working
7. Consistent structure following templates

---

## File Audit by Priority

### High Priority (Heavy code duplication)

| File | Issue |
|------|-------|
| `orchestrator/01-configuration/*` | Delete (duplicates scenario/) |
| `architecture/02-rust-core-engine.md` | Full struct definitions (~1000 lines) |
| `api/state-provider.md` | Full class implementations (~465 lines) |
| `patterns-and-conventions.md` | Code blocks throughout (~645 lines) |
| `policy/nodes.md` | Full JSON schemas + line numbers |
| `scenario/agents.md` | Python/Rust code + line numbers |

### Medium Priority

| File | Issue |
|------|-------|
| `experiments/runner.md` | Full dataclass definitions |
| `policy/context-fields.md` | Good tables, but has line numbers at end |
| `architecture/appendix-a-module-reference.md` | Line counts will go stale |
| `orchestrator/02-models/*.md` | Full struct definitions |

### Good Examples (Preserve patterns)

| File | What works well |
|------|----------------|
| `cli/commands/run.md` | CLI synopsis, option tables |
| `ai_cash_mgmt/index.md` | Mermaid diagrams, minimal code |
| `policy/context-fields.md` | Field reference tables |
| `scenario/examples.md` | Pure configuration examples |

---

## Progress Log

| Date | Phase | Action | Notes |
|------|-------|--------|-------|
| 2025-12-12 | Setup | Created plan structure | Moved from single file to phased approach |
| 2025-12-12 | Phase 1 | Completed | Deleted `orchestrator/01-configuration/`, cleaned `02-models/` files |
| 2025-12-12 | Phase 2 | Completed | Deleted meta-doc, removed line counts from architecture files |

---

*This overview is updated after each phase completion.*
