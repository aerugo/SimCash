# AI Agent Implementation Planning Guide

This directory is where AI-agents can put plans for features or documentation.
Plans for relatively small features or documentation can be stored here as markdown files.
Larger features or documentation efforts should have their own directories in the `docs/plans/` directory.

## Directory Structure for Larger Plans

Each plan with its own directory should have the following structure:

```
docs/plans/<feature-name>/
├── initial_findings.md      # Research and discovery notes (if applicable)
├── development-plan.md      # Phased development plan (required)
├── work_notes.md            # Progress tracking and session notes (required)
├── doc-draft.md             # Documentation drafts for docs/reference/
└── phases/
    ├── phase_1.md           # Detailed plan for phase 1
    ├── phase_2.md           # Detailed plan for phase 2
    └── ...
```

---

## Starting a New Implementation

### 1. Understand the Project Context

Before writing any code:

- **Read all relevant `CLAUDE.md` files** and `.claude/agents/` guides for language and project conventions
- **Read `docs/reference/patterns-and-conventions.md`** to understand ALL project invariants (INV-1 through INV-N) and established patterns
- **Review `docs/reference/` documentation** for related systems
- **Study existing implementations** that solve similar problems (e.g., if implementing a Protocol, find existing Protocols in the codebase)
- **Analyze the current state** of files you'll modify—understand what exists before changing it

### 2. Create the Development Plan

Save to `docs/plans/<feature-name>/development-plan.md`:

```markdown
# <Feature Name> - Development Plan

**Status**: In Progress
**Created**: <date>
**Branch**: <branch-name>

## Summary

<1-2 sentence description of what this implementation accomplishes>

## Critical Invariants to Respect

<Reference invariants from docs/reference/patterns-and-conventions.md by their canonical IDs>

- **INV-X**: <Name> - <How it applies to this implementation>
- **INV-Y**: <Name> - <How it applies to this implementation>

If this implementation introduces a NEW invariant, note it here and plan to add it to
`docs/reference/patterns-and-conventions.md` in the documentation phase:

- **NEW INV**: <Proposed Name> - <Description and rationale>

## Current State Analysis

<Describe what exists now and what problem you're solving>

### Files to Modify
| File | Current State | Planned Changes |
|------|---------------|-----------------|
| ... | ... | ... |

## Solution Design

<Describe the solution approach, with diagrams if helpful>

```
<ASCII diagram showing architecture/flow>
```

### Key Design Decisions

1. **<Decision>**: <Rationale>
2. **<Decision>**: <Rationale>

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | <description> | <what tests verify> | X tests |
| 2 | <description> | <what tests verify> | X tests |
| ... | ... | ... | ... |

## Phase 1: <Name>

**Goal**: <Clear objective>

### Deliverables
1. <File or component>
2. <File or component>

### TDD Approach
1. Write failing tests for <behavior>
2. Implement <component> to pass tests
3. Refactor for clarity

### Success Criteria
- [ ] <Specific, testable criterion>
- [ ] <Specific, testable criterion>

## Phase 2: <Name>
...

## Testing Strategy

### Unit Tests
- <test category>: <what it verifies>

### Integration Tests
- <test category>: <what it verifies>

### Identity/Invariant Tests
- <test category>: <what invariant it enforces>

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add new invariants (if any) and new patterns (if any)
- [ ] <other docs/reference/ files as needed>

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| ... | ... | ... |
```

### 3. Create Work Notes

Save to `docs/plans/<feature-name>/work_notes.md`:

```markdown
# <Feature Name> - Work Notes

**Project**: <brief description>
**Started**: <date>
**Branch**: <branch-name>

---

## Session Log

### <date> - <Session Focus>

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-X, INV-Y
- Read <file> - understood <what>
- Read <file> - understood <what>

**Applicable Invariants**:
- INV-X: <how it constrains this work>
- INV-Y: <how it constrains this work>

**Key Insights**:
- <insight that affects implementation>

**Completed**:
- [x] <task>
- [x] <task>

**Next Steps**:
1. <next task>
2. <next task>

---

## Phase Progress

### Phase 1: <Name>
**Status**: <Pending|In Progress|Complete>
**Started**: <date>
**Completed**: <date or blank>

#### Results
- <what was accomplished>
- <files created/modified>

#### Notes
- <decisions made>
- <issues encountered>

---

## Key Decisions

### Decision 1: <Title>
**Rationale**: <why this approach>

---

## Issues Encountered

### Issue 1: <Description>
**Resolution**: <how it was solved>

---

## Files Modified

### Created
- `<path>` - <purpose>

### Modified
- `<path>` - <what changed>

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] Add INV-N: <New Invariant Name> (if introducing new invariant)
- [ ] Add Pattern N: <New Pattern Name> (if introducing new pattern)
- [ ] Update Key Source Files table (if adding key files)

### Other Documentation
- [ ] <other doc file> - <what to add>
```

### 4. Create Phase Plans

For each phase, create `docs/plans/<feature-name>/phases/phase_X.md`:

```markdown
# Phase X: <Name>

**Status**: <Pending|In Progress|Complete>
**Started**: <date>

---

## Objective

<What this phase accomplishes>

---

## Invariants Enforced in This Phase

<List which invariants from patterns-and-conventions.md are specifically tested/enforced here>

- INV-X: <How tests in this phase verify this invariant>

---

## TDD Steps

### Step X.1: Write Failing Tests (RED)

Create `<test file path>`:

**Test Cases**:
1. `test_<name>` - <what it verifies>
2. `test_<name>` - <what it verifies>
...

```python
# Example test structure
class Test<Component>:
    def test_<behavior>(self) -> None:
        """<Description of what this test verifies>."""
        ...
```

### Step X.2: Implement to Pass Tests (GREEN)

Create/modify `<implementation file path>`:

```python
# Example implementation structure
def <function>(...) -> <ReturnType>:
    """<Docstring>."""
    ...
```

### Step X.3: Refactor

- Ensure type safety (no bare `Any` where avoidable)
- Add docstrings with examples
- Optimize for readability

---

## Implementation Details

<Specific technical details for this phase>

### Edge Cases to Handle

- <edge case>
- <edge case>

---

## Files

| File | Action |
|------|--------|
| `<path>` | CREATE |
| `<path>` | MODIFY |

---

## Verification

```bash
# Run tests
cd <directory>
<test command>

# Type check
<mypy command>

# Lint
<lint command>
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added
- [ ] Handles all edge cases
- [ ] Invariants INV-X, INV-Y verified by tests
```

---

## Execution Workflow

### Starting Each Session

1. **Read `work_notes.md`** to understand current state
2. **Review the current phase plan** in `phases/phase_X.md`
3. **Re-read `docs/reference/patterns-and-conventions.md`** if working on invariant-sensitive code
4. **Check which tests are passing/failing**
5. **Continue from the documented next step**

### Working Through Each Phase

1. **Create the detailed phase plan** in `phases/phase_X.md` before starting
2. **Follow strict TDD**:
   - Write failing tests first (RED)
   - Implement minimal code to pass (GREEN)
   - Refactor while keeping tests green (REFACTOR)
3. **Update `work_notes.md` continuously**:
   - What was completed
   - Decisions made and rationale
   - Issues encountered and resolutions
   - Next steps when resuming
4. **Run test suites at major milestones**
5. **Update `doc-draft.md`** as you implement

### Completing a Phase

1. **Verify all phase tests pass**
2. **Run type checking and linting**
3. **Update phase status** in `development-plan.md`
4. **Add completion notes** to `work_notes.md`
5. **Create next phase plan** in `phases/phase_X+1.md`

### Completing the Implementation

1. **Run full relevant test suite**
2. **Verify all invariants are preserved**
3. **Update `docs/reference/patterns-and-conventions.md`**:
   - Add any new invariants with next available INV-N number
   - Add any new patterns with next available Pattern N number
   - Update Key Source Files table if new key files were added
   - Update version number and date
4. **Update other documentation** in `docs/reference/` from `doc-draft.md`
5. **Final review checklist**:
   - [ ] All tests pass
   - [ ] Type checking passes
   - [ ] Linting passes
   - [ ] `patterns-and-conventions.md` updated (if new invariants/patterns)
   - [ ] Other documentation updated
   - [ ] Work notes complete

---

## Invariant Management

### Referencing Existing Invariants

Always reference invariants by their canonical ID from `docs/reference/patterns-and-conventions.md`:

```markdown
## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs in this feature use integer cents
- **INV-5**: Replay Identity - Events persisted contain all fields needed for replay
```

### Introducing New Invariants

If your implementation introduces a constraint that must be maintained project-wide:

1. **Document it in your development plan** as a proposed new invariant
2. **Create tests that enforce the invariant**
3. **Add to `docs/reference/patterns-and-conventions.md`** in the documentation phase:
   - Use next available INV-N number
   - Follow existing format
   - Include: Rule, Requirements, Where it applies
4. **Update the version number** in patterns-and-conventions.md

Example from PolicyConfigBuilder implementation:
```markdown
### INV-9: Policy Evaluation Identity

**Rule**: For any policy P and scenario S, policy parameter extraction MUST produce
identical results regardless of which code path processes them.

**Requirements**:
- ALL code paths that apply policies to agents MUST use `StandardPolicyConfigBuilder`
- Parameter extraction logic MUST be in one place
- Default values MUST be consistent across all paths

**Where it applies**:
- `optimization.py._build_simulation_config()` - deterministic evaluation
- `sandbox_config.py._build_target_agent()` - bootstrap evaluation
```

### Introducing New Patterns

If your implementation introduces a reusable pattern:

1. **Document it in your development plan**
2. **Add to `docs/reference/patterns-and-conventions.md`** in the documentation phase:
   - Use next available Pattern N number
   - Include: Purpose, Protocol/interface definition, Usage example, Key features, Anti-patterns

---

## TDD Principles to Follow

### Red-Green-Refactor Cycle

1. **RED**: Write a test that fails (defines expected behavior)
2. **GREEN**: Write minimal code to make the test pass
3. **REFACTOR**: Clean up while keeping tests green

### Test Categories

1. **Unit Tests**: Test individual functions/methods in isolation
2. **Integration Tests**: Test components working together
3. **Identity/Invariant Tests**: Enforce critical project invariants (reference INV-N)
4. **Property-Based Tests**: Use Hypothesis for comprehensive coverage (when appropriate)

### Test File Naming

- Unit tests: `tests/unit/test_<module>.py`
- Integration tests: `tests/integration/test_<feature>_integration.py`
- Follow existing project conventions

---

## Common Patterns

### Protocol-Based Abstractions

When creating a shared interface (see existing patterns in `patterns-and-conventions.md`):
1. Define a `Protocol` with method signatures
2. Create a single `Standard<Name>` implementation
3. Use dependency injection to provide the implementation
4. Test both the protocol contract and implementation
5. Document as a new pattern if reusable

### Service Layer Pattern

When orchestrating complex operations:
1. Create a `<Name>Service` class
2. Inject dependencies (repositories, other services)
3. Keep business logic in service methods
4. Return domain models, not raw dicts

### CLI Commands

When adding CLI commands:
1. Use `Annotated` pattern for Typer parameters
2. Wire to service layer (don't put business logic in CLI)
3. Output JSON for tool interoperability
4. Handle errors with appropriate exit codes

---

## Checklist Templates

### Pre-Implementation Checklist

- [ ] Read relevant `CLAUDE.md` files
- [ ] Read `docs/reference/patterns-and-conventions.md` for all invariants
- [ ] Identify all applicable invariants (list by INV-N)
- [ ] Analyze current state of files to modify
- [ ] Study similar existing implementations
- [ ] Create development plan (with invariants section)
- [ ] Create work notes file
- [ ] Create first phase plan

### Phase Completion Checklist

- [ ] All phase tests pass
- [ ] Type checking passes (`mypy`)
- [ ] Linting passes (`ruff` or project linter)
- [ ] Work notes updated
- [ ] Doc draft updated (if applicable)
- [ ] Phase status updated in development plan

### Implementation Completion Checklist

- [ ] All tests pass (unit + integration)
- [ ] All invariants verified with tests
- [ ] Type checking passes
- [ ] Linting passes
- [ ] `docs/reference/patterns-and-conventions.md` updated:
  - [ ] New invariants added (if any)
  - [ ] New patterns added (if any)
  - [ ] Key Source Files table updated (if any)
  - [ ] Version number incremented
- [ ] Other `docs/reference/` documentation updated
- [ ] Work notes reflect final state
- [ ] Code follows project conventions
