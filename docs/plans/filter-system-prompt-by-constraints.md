# Filter System Prompt by Scenario Constraints - Development Plan

**Status**: Complete
**Created**: 2025-12-18
**Branch**: `claude/plan-filter-system-prompt-AWDVe`
**Request**: `docs/requests/filter-system-prompt-by-constraints.md`

## Summary

Make `SystemPromptBuilder` constraint-aware so that tree types (payment_tree, bank_tree, strategic_collateral_tree, end_of_tick_collateral_tree) are only mentioned in the system prompt when they have allowed actions in the `ScenarioConstraints`.

## Critical Invariants to Respect

- **INV-2**: Determinism - System prompt generation must be deterministic (same constraints produce same prompt)
- **INV-9**: Policy Evaluation Identity - Not directly applicable but related to consistent constraint interpretation

## Current State Analysis

### Problem

The `SystemPromptBuilder` correctly filters the **schema injection** section based on `ScenarioConstraints.allowed_actions` (see `schema_injection.py:_format_allowed_actions()`), but other sections mention tree types unconditionally:

1. **`_build_policy_architecture()`** (lines 321-356): Always lists all 4 tree types
2. **`_build_common_errors()`** (lines 407-454): Always shows ERROR 2 with `strategic_collateral_tree` example

When running experiments with `liquidity_pool` mode (where `strategic_collateral_tree` is not used), the LLM sees mentions of `strategic_collateral_tree` in multiple places, causing it to generate invalid policies.

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` | `_build_policy_architecture()` and `_build_common_errors()` are standalone functions | Convert to methods on `SystemPromptBuilder` that use `self._constraints` to filter tree mentions |
| `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py` | Tests exist but don't verify tree filtering | Add tests for tree type filtering |

### Reference Implementation

`schema_injection.py:_format_allowed_actions()` already implements constraints-based filtering:

```python
def _format_allowed_actions(
    constraints: ScenarioConstraints,
    raw_schema: dict[str, Any],
    include_examples: bool,
) -> str:
    # Only shows tree types that have allowed actions
    strategic_actions = constraints.allowed_actions.get("strategic_collateral_tree", [])
    if strategic_actions:
        lines.append("\n#### strategic_collateral_tree\n")
        # ...
```

## Solution Design

Convert standalone functions `_build_policy_architecture()` and `_build_common_errors()` to methods on `SystemPromptBuilder` that use `self._constraints` to conditionally include tree-type-specific content.

```
Before:
┌─────────────────────────────────────────────────────┐
│  _build_policy_architecture()                       │
│  - Always lists all 4 tree types                    │
└─────────────────────────────────────────────────────┘

After:
┌─────────────────────────────────────────────────────┐
│  SystemPromptBuilder._build_policy_architecture()   │
│  - Checks self._constraints.allowed_actions         │
│  - Only lists tree types with allowed actions       │
└─────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Convert to instance methods**: The functions need access to `self._constraints`, so they must become methods on `SystemPromptBuilder` (not remain standalone functions)
2. **Match schema_injection pattern**: Follow the same conditional pattern used in `_format_allowed_actions()` for consistency
3. **Graceful degradation**: If no trees have actions, show a minimal architecture section (shouldn't happen in practice)

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Refactor `_build_policy_architecture()` to filter tree types | Test that tree types without actions are not mentioned | 3 tests |
| 2 | Refactor `_build_common_errors()` to filter tree-specific examples | Test that error examples only show enabled trees | 2 tests |
| 3 | Verify backward compatibility and clean up | Run full test suite | 0 new tests |

## Phase 1: Filter Tree Types in Policy Architecture

**Goal**: `_build_policy_architecture()` only lists tree types that have allowed actions in constraints.

### Deliverables

1. Convert `_build_policy_architecture()` to instance method
2. Use `self._constraints.allowed_actions` to conditionally include tree descriptions

### TDD Approach

1. Write failing tests that verify tree types are filtered
2. Convert function to method and add filtering logic
3. Verify tests pass

### Implementation Details

**Current code** (lines 321-356):
```python
def _build_policy_architecture() -> str:
    """Build the policy tree architecture explanation."""
    return """
    ...
    ### Tree Types
    Different trees handle different decision types:
    - **payment_tree**: Decides what to do with each transaction
    - **bank_tree**: Bank-level decisions (once per tick)
    - **strategic_collateral_tree**: Collateral management
    - **end_of_tick_collateral_tree**: End-of-tick collateral adjustments
    ...
    """
```

**New code**:
```python
def _build_policy_architecture(self) -> str:
    """Build the policy tree architecture explanation."""
    tree_descriptions: list[str] = []

    if self._constraints.allowed_actions.get("payment_tree"):
        tree_descriptions.append("- **payment_tree**: Decides what to do with each transaction")
    if self._constraints.allowed_actions.get("bank_tree"):
        tree_descriptions.append("- **bank_tree**: Bank-level decisions (once per tick)")
    if self._constraints.allowed_actions.get("strategic_collateral_tree"):
        tree_descriptions.append("- **strategic_collateral_tree**: Collateral management")
    if self._constraints.allowed_actions.get("end_of_tick_collateral_tree"):
        tree_descriptions.append("- **end_of_tick_collateral_tree**: End-of-tick collateral adjustments")

    tree_section = "\n".join(tree_descriptions) if tree_descriptions else "No tree types enabled."

    return f"""
## Policy Tree Architecture

Agent behavior is governed by a **policy tree**: a decision structure where:
- **Condition nodes**: Evaluate state conditions (comparisons, logical ops)
- **Action nodes**: Specify what to do (Release, Hold, PostCollateral, etc.)

### Tree Structure
```json
{{
  "type": "condition",
  "node_id": "unique_id",
  ...
}}
```

### Tree Types
Different trees handle different decision types:
{tree_section}

### Evaluation Flow
1. Bank tree evaluates first (sets context like release budgets)
2. Collateral trees manage liquidity positions
3. Payment tree evaluates for each pending transaction
"""
```

### Success Criteria

- [ ] `_build_policy_architecture` is an instance method on `SystemPromptBuilder`
- [ ] Tree types without allowed actions are not mentioned
- [ ] All existing tests pass

## Phase 2: Filter Error Examples

**Goal**: `_build_common_errors()` only shows tree-specific error examples for enabled trees.

### Deliverables

1. Convert `_build_common_errors()` to instance method
2. Conditionally include ERROR 2 (wrong action for tree) based on enabled trees

### Implementation Details

**Current code** (lines 423-431):
```python
### ERROR 2: WRONG ACTION FOR TREE
```json
// WRONG in strategic_collateral_tree:
{"action": "Hold"}      // Hold is PAYMENT-only!
{"action": "NoAction"}  // NoAction is BANK-only!
```

**New approach**: Only show this error example if multiple tree types are enabled (since the error is about mixing actions between trees).

```python
def _build_common_errors(self) -> str:
    """Build the common errors section."""
    errors: list[str] = []

    errors.append(ERROR_1_UNDEFINED_PARAMETER)

    # Only show tree action confusion error if multiple tree types enabled
    enabled_trees = [
        tree for tree in ["payment_tree", "bank_tree", "strategic_collateral_tree", "end_of_tick_collateral_tree"]
        if self._constraints.allowed_actions.get(tree)
    ]
    if len(enabled_trees) > 1:
        # Show error with example from an actually enabled tree
        errors.append(self._build_error_2_wrong_action())

    errors.append(ERROR_3_RAW_ARITHMETIC)
    errors.append(ERROR_4_MISSING_NODE_ID)
    errors.append(ERROR_5_INVALID_FIELD)

    return "\n".join(errors)
```

### Success Criteria

- [ ] `_build_common_errors` is an instance method on `SystemPromptBuilder`
- [ ] ERROR 2 only shown when multiple tree types enabled
- [ ] ERROR 2 examples use actually enabled tree types

## Phase 3: Verification and Cleanup

**Goal**: Ensure backward compatibility and all tests pass.

### Tasks

1. Run full test suite
2. Verify type checking passes
3. Test with actual experiment configs that use `liquidity_pool` mode

### Verification Commands

```bash
cd api

# Run tests
.venv/bin/python -m pytest tests/ai_cash_mgmt/unit/test_system_prompt_builder.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py

# Lint
.venv/bin/python -m ruff check payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py
```

### Success Criteria

- [ ] All existing tests pass
- [ ] New filtering tests pass
- [ ] Type checking passes
- [ ] Lint passes

## Testing Strategy

### Unit Tests (New)

Add to `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py`:

```python
class TestTreeTypeFiltering:
    """Tests for tree type filtering based on constraints."""

    def test_policy_architecture_excludes_unused_trees(self) -> None:
        """Policy architecture section doesn't mention trees without allowed actions."""
        # Only payment_tree enabled
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        prompt = build_system_prompt(constraints)

        assert "payment_tree" in prompt
        assert "strategic_collateral_tree" not in prompt
        assert "end_of_tick_collateral_tree" not in prompt

    def test_policy_architecture_includes_all_enabled_trees(self) -> None:
        """Policy architecture section includes all enabled tree types."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release"],
                "bank_tree": ["NoAction"],
                "strategic_collateral_tree": ["PostCollateral"],
            },
        )
        prompt = build_system_prompt(constraints)

        assert "payment_tree" in prompt
        assert "bank_tree" in prompt
        assert "strategic_collateral_tree" in prompt
        assert "end_of_tick_collateral_tree" not in prompt

    def test_error_examples_contextual_to_enabled_trees(self) -> None:
        """Error examples only reference enabled tree types."""
        # Only payment_tree enabled
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        prompt = build_system_prompt(constraints)

        # Should not show strategic_collateral_tree in error examples
        error_section_match = "strategic_collateral_tree" in prompt.lower()
        # It should only appear in schema if enabled
        assert not error_section_match or "strategic_collateral" not in prompt.split("Common Errors")[1] if "Common Errors" in prompt else True
```

### Existing Tests (Must Pass)

- `TestSystemPromptStructure` - Structure tests should still pass
- `TestSchemaInjection` - Schema tests unchanged
- `TestBuilderPattern` - Builder API unchanged
- `TestPromptQuality` - Quality tests unchanged
- `TestPromptCustomization` - Customization tests unchanged

## Documentation Updates

No documentation updates required for `docs/reference/` since this is an internal implementation detail. The public API (`build_system_prompt()` and `SystemPromptBuilder`) remains unchanged.

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Complete | Filter `_build_policy_architecture()` |
| Phase 2 | Complete | Filter `_build_common_errors()` |
| Phase 3 | Complete | Verification, cleanup, and workaround removal |

## Acceptance Criteria (from Feature Request)

- [x] `_build_policy_architecture()` only lists tree types with allowed actions
- [x] `_build_common_errors()` only shows examples for enabled tree types
- [x] Experiment configs without `strategic_collateral_tree` produce prompts with no mention of it
- [x] Existing tests pass (backward compatible)
- [x] New unit tests verify filtering behavior
- [x] LLM no longer generates `strategic_collateral_tree` when it's not in allowed_actions
- [x] Workarounds removed from paper generator experiment configs

## Related Files

- `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` - Main implementation
- `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py` - Reference for filtering pattern
- `api/payment_simulator/ai_cash_mgmt/constraints/scenario_constraints.py` - Constraints model
- `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py` - Test file
