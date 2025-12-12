# Reference Documentation Overhaul Plan

**Created**: 2025-12-12
**Status**: Draft

---

## Problem Statement

The `docs/reference/` directory contains extensive code duplication that:
1. **Duplicates source code**: Struct definitions, enum variants, and function signatures are copied verbatim from source files
2. **Creates maintenance burden**: Code in docs goes stale when source changes
3. **Obscures conceptual understanding**: Readers must parse implementation details to understand concepts
4. **Contains brittle line number references**: References like `engine.rs:244-321` break with every code change

## Guiding Principles

Reference documentation should:
- **Explain behavior**, not repeat implementation
- **Show examples**, not struct definitions
- **Describe contracts**, not internal code
- **Use diagrams** for architecture and flow
- **Provide configuration examples** in YAML/JSON (the user-facing formats)
- **Cross-reference** related topics rather than duplicating content

## Audit Summary

### Files by Severity

#### High Priority (Heavy code duplication)
| File | Issue |
|------|-------|
| `orchestrator/01-configuration/agent-config.md` | Full Rust structs + Python code (~650 lines) |
| `architecture/02-rust-core-engine.md` | Extensive struct definitions (~1000 lines) |
| `api/state-provider.md` | Full class implementations (~465 lines) |
| `patterns-and-conventions.md` | Code blocks throughout (~645 lines) |
| `policy/nodes.md` | Full JSON schemas + line numbers (~327 lines) |
| `scenario/agents.md` | Python/Rust code + line numbers (~605 lines) |

#### Medium Priority (Moderate code)
| File | Issue |
|------|-------|
| `cli/commands/run.md` | Good, but some implementation references |
| `experiments/runner.md` | Full dataclass definitions (`ExperimentResult`, `VerboseConfig`, etc.) |
| `llm/configuration.md` | Needs review |
| `policy/context-fields.md` | Good tables, but has "Source Code Reference" with line numbers |
| `architecture/appendix-a-module-reference.md` | Line counts will go stale |

#### Good Examples (Keep patterns)
| File | What works well |
|------|----------------|
| `cli/commands/run.md` | CLI synopsis, option tables, usage examples |
| `architecture/02-rust-core-engine.md` | Mermaid diagrams (keep these!) |
| `scenario/examples.md` | Configuration examples |
| `ai_cash_mgmt/index.md` | Architecture diagrams, conceptual flow, minimal code |
| `policy/context-fields.md` | Field reference tables (excellent format!) |
| `experiments/runner.md` | CLI usage examples, output examples |

### Redundant Documentation

**Configuration docs (TRUE duplication - consolidate to `scenario/`):**
1. `orchestrator/01-configuration/agent-config.md` ↔ `scenario/agents.md`
2. `orchestrator/01-configuration/arrival-config.md` ↔ `scenario/arrivals.md`
3. `orchestrator/01-configuration/cost-rates.md` ↔ `scenario/cost-rates.md`
4. `orchestrator/01-configuration/lsm-config.md` ↔ `scenario/lsm-config.md`
5. `orchestrator/01-configuration/orchestrator-config.md` ↔ `scenario/simulation-settings.md`
6. `orchestrator/01-configuration/scenario-events.md` ↔ `scenario/scenario-events.md`

**Model docs (DIFFERENT purposes - keep both, but clean up code):**
- `orchestrator/02-models/agent.md` = Deep-dive into Agent **runtime model** (methods, state, lifecycle)
- `orchestrator/02-models/transaction.md` = Deep-dive into Transaction **runtime model**
- `architecture/05-domain-models.md` = High-level overview with diagrams

These are NOT duplicates - `scenario/agents.md` covers **configuration** (how to write YAML), while `orchestrator/02-models/agent.md` covers the **runtime struct** (methods like `debit()`, `credit()`, state registers, etc.).

**Decision**:
- Delete `orchestrator/01-configuration/` (duplicates `scenario/`)
- Keep `orchestrator/02-models/` but remove code duplication (keep conceptual content)
- Keep `architecture/05-domain-models.md` as the high-level overview

---

## Detailed File Observations

Based on comprehensive review of the documentation files:

### Excellent Patterns to Preserve

#### `policy/context-fields.md` - Model Reference Doc
This is the **gold standard** for reference documentation:
- Field-by-field reference with Type, Unit, Description
- Clear availability matrix (which tree types support which fields)
- No struct definitions - just describes what each field represents
- **ONE ISSUE**: "Source Code Reference" section at bottom has line numbers - remove this

#### `ai_cash_mgmt/index.md` - Architecture Overview
Well-structured module overview:
- Mermaid architecture diagrams
- Data flow diagrams
- Quick start examples (minimal, purposeful code)
- Key concepts table
- Source code locations table (file paths only, no line numbers)

#### `experiments/runner.md` - Mixed Quality
**Good parts**:
- VerboseConfig table with flags
- ExperimentResult field reference table
- CLI usage examples at bottom
- Example output showing what verbose logging looks like

**Problems to fix**:
- Full `@dataclass` definitions copied from source
- Protocol definitions (OK for interface docs, but verbose)

### Specific Issues Found

#### Line Number References (Remove All)
Files with brittle line references:
- `orchestrator/02-models/agent.md`: `agent.rs:144`, `agent.rs:152`, etc.
- `orchestrator/02-models/transaction.md`: `transaction.rs:162-239`, etc.
- `policy/nodes.md`: Various line references
- `policy/context-fields.md`: `context.rs:114-117`, `validation.rs:327-353`

**Replacement strategy**: Reference by function/struct name (e.g., "see `Agent::debit()`") or just remove if not essential.

#### Full Struct/Class Definitions (Remove)
Files copying source code:
- `orchestrator/02-models/agent.md`: Full `Agent` struct (~40 fields)
- `orchestrator/02-models/transaction.md`: Full `Transaction` struct
- `experiments/runner.md`: Full `ExperimentResult`, `VerboseConfig`, `IterationRecord` dataclasses
- `api/state-provider.md`: Full Protocol definitions

**Replacement strategy**: Use field reference tables (like `policy/context-fields.md`).

#### Stale Statistics (Remove or Mark)
- `architecture/appendix-a-module-reference.md`: "Total Lines: ~19,445" will become stale
- Module listing with line counts per file

**Replacement strategy**: Remove line counts, keep file listings.

### Files That Are Already Good

These need minimal changes:
- `cli/commands/run.md` - Clean CLI reference
- `cli/exit-codes.md` - Simple table
- `scenario/examples.md` - Just YAML examples

---

## Transformation Strategy

### What to Remove

1. **Full struct/class definitions**
   ```rust
   // REMOVE: This duplicates source code
   pub struct AgentConfig {
       pub id: String,
       pub opening_balance: i64,
       ...
   }
   ```

2. **Line number references**
   ```
   // REMOVE: These go stale immediately
   **Location:** `engine.rs:244-321`
   ```

3. **Python validation code**
   ```python
   # REMOVE: Implementation detail
   @field_validator("id")
   def validate_id(cls, v):
       ...
   ```

4. **Duplicate content across files**
   - Keep single source of truth per topic

### What to Keep

1. **Mermaid diagrams** - Excellent for understanding architecture
2. **Tables** - Field references, option summaries
3. **YAML/JSON examples** - User-facing configuration
4. **CLI command examples** - Usage patterns
5. **Behavioral descriptions** - What things do, not how

### What to Add

1. **Conceptual introductions** - Why does this exist?
2. **Relationship diagrams** - How do components connect?
3. **Decision guides** - When to use what?
4. **Error troubleshooting** - Common problems and solutions

### Acceptable vs Unacceptable Code

Not all code is bad in documentation. Here's the distinction:

#### ✅ ACCEPTABLE Code

**YAML/JSON Configuration** (user-facing):
```yaml
agents:
  - id: BANK_A
    opening_balance: 1000000
```

**CLI Examples** (user-facing):
```bash
payment-sim run --config scenario.yaml --verbose
```

**Import Statements** (showing how to use):
```python
from payment_simulator.experiments.runner import GenericExperimentRunner
```

**Short Usage Examples** (3-5 lines showing API):
```python
runner = GenericExperimentRunner(config)
result = await runner.run()
print(f"Cost: ${result.final_cost / 100:.2f}")
```

**Formulas** (mathematical, not implementation):
```
available_liquidity = balance + credit_headroom
```

#### ❌ UNACCEPTABLE Code

**Full Struct/Class Definitions**:
```rust
pub struct Agent {
    id: String,
    balance: i64,
    // 30 more fields...
}
```

**Validator/Method Implementations**:
```python
@field_validator("id")
def validate_id(cls, v):
    if not v:
        raise ValueError("...")
    return v
```

**Full Protocol Definitions**:
```python
class StateProviderProtocol(Protocol):
    def get_tick(self) -> int: ...
    def get_agents(self) -> list[dict]: ...
    # 20 more methods...
```

**Line Number References**:
```
**Location:** `agent.rs:144-278`
```

---

## Per-Directory Plan

### 1. `architecture/` (8 files)

**Goal**: Keep diagrams, remove struct definitions, add conceptual explanations

| File | Action |
|------|--------|
| `01-system-overview.md` | Keep diagrams, enhance conceptual content |
| `02-rust-core-engine.md` | Keep Mermaid diagrams, remove struct defs |
| `03-python-api-layer.md` | Remove class code, keep architecture diagrams |
| `04-ffi-boundary.md` | Keep safety rules, remove implementation |
| `05-domain-models.md` | Replace code with field tables |
| `06-settlement-engines.md` | Keep algorithm flowcharts |
| `07-policy-system.md` | Keep decision flow, remove code |
| `08-event-system.md` | Keep event catalog tables |
| `09-persistence-layer.md` | Keep schema overview, remove queries |
| `10-cli-architecture.md` | Keep component diagram |
| `11-tick-loop-anatomy.md` | Keep flowchart (excellent) |
| `12-cost-model.md` | Keep cost formulas, remove code |
| `appendix-a-module-reference.md` | Remove line counts per file, keep module listings |
| `appendix-b-*.md` | Review for consolidation |
| `ARCHITECTURE_DOCUMENTATION_PLAN.md` | Remove (meta-doc) |

### 2. `scenario/` (12 files)

**Goal**: Canonical home for configuration reference

| File | Action |
|------|--------|
| `index.md` | Keep as navigation hub |
| `simulation-settings.md` | Field tables + examples only |
| `agents.md` | Remove code, keep field tables + examples |
| `policies.md` | Policy type reference without code |
| `arrivals.md` | Distribution examples, no code |
| `distributions.md` | Statistical formulas, parameter tables |
| `cost-rates.md` | Cost parameter reference |
| `lsm-config.md` | LSM parameter reference |
| `scenario-events.md` | Event type reference with examples |
| `priority-system.md` | Priority levels and behavior |
| `advanced-settings.md` | Feature flags reference |
| `feature-toggles.md` | Merge into advanced-settings.md |
| `examples.md` | Complete configuration examples |

### 3. `orchestrator/` (Partial deletion + cleanup)

**Recommendation**: Delete `01-configuration/` (duplicates `scenario/`), keep `02-models/` but clean up code.

#### Delete: `orchestrator/01-configuration/` (6 files)

These duplicate `scenario/` docs and should be removed:

| File to Delete | Already Exists In |
|----------------|-------------------|
| `agent-config.md` | `scenario/agents.md` |
| `arrival-config.md` | `scenario/arrivals.md` |
| `cost-rates.md` | `scenario/cost-rates.md` |
| `lsm-config.md` | `scenario/lsm-config.md` |
| `orchestrator-config.md` | `scenario/simulation-settings.md` |
| `scenario-events.md` | `scenario/scenario-events.md` |

#### Keep & Clean: `orchestrator/02-models/` (2 files)

These cover **runtime models** (different from configuration docs):

| File | Action |
|------|--------|
| `agent.md` | Remove struct definitions, keep method explanations, behavioral descriptions |
| `transaction.md` | Remove struct definitions, keep lifecycle state machine, split transaction logic |

**Why keep these?** They document the runtime behavior that isn't covered elsewhere:
- Agent: `debit()`/`credit()` semantics, release budgets, state registers, daily resets
- Transaction: Status lifecycle, split transactions, dual priority system, settlement flow

#### Update: `orchestrator/index.md`

Update to only reference `02-models/` after cleanup.

### 4. `policy/` (10 files)

**Goal**: DSL reference without Rust implementation

| File | Action |
|------|--------|
| `index.md` | Keep as navigation + overview |
| `trees.md` | Conceptual tree structure |
| `nodes.md` | Node types, remove line numbers |
| `expressions.md` | Expression syntax reference |
| `computations.md` | Computation reference |
| `values.md` | Value types reference |
| `actions.md` | Action catalog with parameters |
| `context-fields.md` | ✅ Excellent format - just remove "Source Code Reference" section at end |
| `validation.md` | Validation rules, error messages |
| `configuration.md` | YAML examples for policies |
| `integration.md` | How to integrate custom policies |
| `cross-reference.md` | Review for relevance |

**Note**: `context-fields.md` is the **gold standard** for reference docs - use its field table format for other files.

### 5. `cli/` (9 files)

**Goal**: Command reference (already good, minor cleanup)

| File | Action |
|------|--------|
| `index.md` | Keep |
| `commands/run.md` | Remove implementation references |
| `commands/replay.md` | Review for code |
| `commands/db.md` | Review for code |
| `commands/checkpoint.md` | Review for code |
| `commands/validate-policy.md` | Review for code |
| `commands/policy-schema.md` | Review for code |
| `commands/experiment.md` | Review for code |
| `commands/ai-game.md` | Review for code |
| `output-modes.md` | Keep examples, remove implementation |
| `exit-codes.md` | Keep (already good) |
| `filtering.md` | Keep examples |

### 6. `api/` (4 files)

**Goal**: API documentation without implementation code

| File | Action |
|------|--------|
| `index.md` | Keep |
| `endpoints.md` | OpenAPI-style reference, no code |
| `state-provider.md` | Conceptual explanation, remove impl |
| `output-strategies.md` | Strategy descriptions, no code |

### 7. `experiments/` (3 files)

**Goal**: Experiment framework reference

| File | Action |
|------|--------|
| `index.md` | Keep as overview |
| `runner.md` | Remove dataclass definitions, keep field tables and CLI examples |
| `configuration.md` | YAML examples focus |

**Specific changes for `runner.md`:**
- ✅ Keep: `VerboseConfig` flag table, `ExperimentResult` field reference table, CLI usage examples, example output
- ❌ Remove: Full `@dataclass` definitions, full Protocol definitions
- Convert class definitions to field reference tables (model after `policy/context-fields.md`)

### 8. `ai_cash_mgmt/` (7 files)

**Goal**: AI cash management reference

| File | Action |
|------|--------|
| `index.md` | ✅ Already good - keep Mermaid diagrams, minimal changes needed |
| `configuration.md` | Review for code removal |
| `components.md` | Review for code removal |
| `optimization.md` | Review for code removal |
| `sampling.md` | Review for code removal |
| `constraints.md` | Review for code removal |
| `persistence.md` | Review for code removal |

**Note**: `index.md` is a good example of architecture documentation done right - has diagrams, data flow, key concepts, and only minimal purposeful code examples.

### 9. `llm/` (3 files)

**Goal**: LLM integration reference

| File | Action |
|------|--------|
| `index.md` | Keep |
| `configuration.md` | YAML examples |
| `protocols.md` | Review for code removal |

### 10. `castro/` (1 file)

| File | Action |
|------|--------|
| `index.md` | Review for relevance |

### 11. `patterns-and-conventions.md` (root file)

**Goal**: Keep as authoritative pattern reference, but reduce code examples

- Keep invariant descriptions
- Keep checklists
- Reduce code examples to minimum needed for illustration
- Keep architectural pattern descriptions

---

## Implementation Phases

### Phase 1: Remove Duplicates (Week 1)
1. Delete `orchestrator/01-configuration/` directory (duplicates `scenario/`)
2. Clean up `orchestrator/02-models/` (keep, but remove code blocks)
3. Update `orchestrator/index.md` to only reference models
4. Update any internal links pointing to deleted files

### Phase 2: Architecture Docs (Week 2)
1. Transform `architecture/02-rust-core-engine.md`
2. Transform `architecture/05-domain-models.md`
3. Transform other architecture files
4. Remove `ARCHITECTURE_DOCUMENTATION_PLAN.md`

### Phase 3: Scenario Docs (Week 3)
1. Transform `scenario/agents.md`
2. Transform other scenario files
3. Merge `feature-toggles.md` into `advanced-settings.md`

### Phase 4: Policy Docs (Week 4)
1. Transform all policy files
2. Remove line number references
3. Focus on DSL syntax and examples

### Phase 5: API/CLI Docs (Week 5)
1. Transform `api/state-provider.md`
2. Clean up CLI command docs
3. Ensure examples are current

### Phase 6: Remaining (Week 6)
1. Transform experiments, ai_cash_mgmt, llm docs
2. Clean up `patterns-and-conventions.md`
3. Final review and link verification

---

## Template for Transformed Docs

### Configuration Reference Template

```markdown
# Feature Name

Brief description of what this configures and why.

---

## Quick Start

\`\`\`yaml
feature:
  required_field: value
  optional_field: value  # default: X
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

### Advanced Usage

\`\`\`yaml
...
\`\`\`

---

## Behavior

Describe what happens when configured different ways.

---

## Related

- [Related Topic](link.md)
```

### Architecture Reference Template

```markdown
# Component Name

Brief description of purpose and role in system.

---

## Overview

\`\`\`mermaid
flowchart TB
    ...
\`\`\`

---

## Responsibilities

- Bullet points of what this component does

---

## Key Concepts

### Concept 1
Description without code.

### Concept 2
Description without code.

---

## Interactions

How does this component interact with others?

\`\`\`mermaid
sequenceDiagram
    ...
\`\`\`

---

## Configuration

See [Configuration Reference](../scenario/relevant.md).

---

## Related

- [Related Component](link.md)
```

---

## Concrete Transformation Example

### Before: `orchestrator/02-models/agent.md` (excerpt)

```markdown
## Struct Definition

**Location:** `agent.rs:141-278`

\`\`\`rust
pub struct Agent {
    // Identity
    id: String,

    // Settlement Account
    balance: i64,

    // Queue 1 (Internal)
    outgoing_queue: Vec<String>,
    incoming_expected: Vec<String>,
    last_decision_tick: Option<usize>,
    liquidity_buffer: i64,
    // ... 30 more fields
}
\`\`\`

---

## Fields

### Identity

#### `id`

**Type:** `String`
**Location:** `agent.rs:144`

Unique agent identifier (e.g., "BANK_A").
```

### After: Same section transformed

```markdown
## Agent State

An Agent maintains the following categories of state during simulation:

### Identity

| Field | Type | Description |
|-------|------|-------------|
| `id` | `String` | Unique agent identifier (e.g., "BANK_A") |

### Settlement Account

| Field | Type | Description |
|-------|------|-------------|
| `balance` | `i64` (cents) | Current balance at central bank. Positive = reserves, negative = using credit |

### Queue Management

| Field | Type | Description |
|-------|------|-------------|
| `outgoing_queue` | `Vec<String>` | Transaction IDs awaiting cash manager release decision |
| `incoming_expected` | `Vec<String>` | Expected incoming transaction IDs for liquidity forecasting |
| `liquidity_buffer` | `i64` (cents) | Target minimum balance to maintain |

[Continue with other field categories...]
```

### Key Changes

1. **Removed**: Full struct definition, line number references
2. **Kept**: Field descriptions, type information, behavioral explanations
3. **Added**: Grouped fields by category with tables
4. **Format**: Tables instead of individual field sections

---

## Success Criteria

1. **No source code in docs**: No Rust structs, Python classes, or implementation code
2. **No line number references**: No `file.rs:123` style references
3. **No duplicated content**: Each topic documented once
4. **All diagrams preserved**: Mermaid diagrams retained and enhanced
5. **Examples are user-facing**: YAML/JSON configs, CLI commands, not code
6. **Links verified**: All internal links work
7. **Consistent structure**: All docs follow templates

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Loss of detail | Ensure conceptual explanations cover all behavior |
| Broken links | Run link checker before merging |
| Missing content | Review against source code during transform |
| Stale docs | Update CLAUDE.md to require doc updates with code changes |

---

## Open Questions

1. Should `orchestrator/02-models/` be renamed to something clearer (e.g., `models/` or `runtime-models/`)?
2. Should line numbers be replaced with function/struct names (e.g., "see `AgentConfig` struct")?
3. Should we add auto-generated API docs from code comments?
4. Should we consolidate all configuration docs into a single large file?
5. Should `orchestrator/02-models/` content be merged into `architecture/05-domain-models.md` instead of kept separate?
