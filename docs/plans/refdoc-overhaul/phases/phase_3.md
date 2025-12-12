# Phase 3: Scenario Docs Cleanup

**Status**: Complete
**Scope**: `docs/reference/scenario/`

---

## Objective

Clean up scenario configuration documentation by:
1. Removing Python/Rust code snippets from field definitions
2. Removing line number references
3. Keeping YAML configuration examples (user-facing)
4. Converting "Implementation Details" sections to behavioral descriptions
5. Evaluating `feature-toggles.md` for merge into `advanced-settings.md`

---

## Files to Process

| File | Priority | Issues Found |
|------|----------|--------------|
| `agents.md` | High | Python/Rust code, line numbers in "Implementation Details" |
| `advanced-settings.md` | High | Rust code snippets, line number references, implementation table |
| `arrivals.md` | Medium | Check for code |
| `cost-rates.md` | Medium | Check for code |
| `policies.md` | Medium | Check for code |
| `distributions.md` | Medium | Check for code |
| `lsm-config.md` | Medium | Check for code |
| `scenario-events.md` | Medium | Check for code |
| `priority-system.md` | Medium | Check for code |
| `simulation-settings.md` | Medium | Check for code |
| `feature-toggles.md` | Low | Clean, may merge into advanced-settings |
| `examples.md` | Low | Pure YAML examples, keep as-is |
| `index.md` | Low | Navigation, keep as-is |

---

## Execution Steps

### Step 1: Clean `agents.md`

**Problems identified:**
- "Implementation Details" subsections under each field with Python/Rust code
- Line number references like `schemas.py:448-449`, `engine.rs:251`

**Actions:**
- Remove all "Implementation Details" subsections
- Remove Python code blocks (`@model_validator`, etc.)
- Remove Rust code blocks with field definitions
- Keep YAML examples (user-facing configuration)
- Keep field reference tables
- Keep behavioral descriptions

### Step 2: Clean `advanced-settings.md`

**Problems identified:**
- "Implementation" subsections with Rust code
- Line number references like `engine.rs:176-177`
- "Implementation Location" table at bottom with line numbers

**Actions:**
- Remove "Implementation" subsections
- Remove Rust code blocks
- Remove "Implementation Location" table
- Keep YAML examples
- Keep behavior tables
- Keep interaction matrices

### Step 3: Evaluate Merge `feature-toggles.md`

Review whether to merge into `advanced-settings.md`:
- If content overlaps significantly → merge
- If distinct topic → keep separate

Current assessment: Keep separate (feature toggles is a distinct concept).

### Step 4: Spot-check remaining files

For each remaining file, quick check for:
- Line number references
- Full code implementations
- Remove if found

---

## Transformation Pattern

### Before (agents.md excerpt)

```markdown
### `id`

**Type**: `str`
**Required**: Yes

Unique identifier for the agent.

#### Implementation Details

**Python Schema** (`schemas.py:448-449`):
\`\`\`python
id: str = Field(..., min_length=1)
\`\`\`

**Validation** (`schemas.py:462-477`):
\`\`\`python
@model_validator(mode='after')
def validate_agent_ids_unique(self) -> 'SimulationConfig':
    ...
\`\`\`
```

### After

```markdown
### `id`

**Type**: `str`
**Required**: Yes
**Constraint**: Non-empty string, must be unique across all agents

Unique identifier for the agent. Used in transaction routing, counterparty weights, and scenario event targeting.

**Best Practices:**

\`\`\`yaml
# Clear, descriptive names
agents:
  - id: BIG_BANK_A
  - id: REGIONAL_TRUST
\`\`\`
```

---

## Completion Criteria

- [x] `agents.md` has no Python/Rust code, no line numbers
- [x] `advanced-settings.md` has no Rust code, no line numbers
- [x] `simulation-settings.md` cleaned
- [x] `lsm-config.md` cleaned
- [x] `arrivals.md` cleaned
- [x] `cost-rates.md` cleaned
- [x] `priority-system.md` cleaned
- [x] `policies.md` cleaned
- [x] `scenario-events.md` cleaned
- [x] `distributions.md` cleaned
- [x] YAML examples preserved throughout
- [x] Field reference tables preserved

---

## Next Phase

After completion, proceed to [Phase 4: Policy Docs](phase_4.md).
