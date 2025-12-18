# Feature Request: Filter System Prompt Builder by Scenario Constraints

**Date**: 2025-12-18
**Priority**: Medium
**Affects**: `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py`

## Summary

The `SystemPromptBuilder` mentions all policy tree types (payment_tree, bank_tree, strategic_collateral_tree, end_of_tick_collateral_tree) in several sections regardless of which trees are enabled in the scenario constraints. This causes LLMs to generate policies with tree types that aren't valid for the scenario, leading to validation failures.

## Problem Statement

When building the system prompt for LLM policy optimization, the `SystemPromptBuilder` correctly filters the **schema injection** section based on `ScenarioConstraints.allowed_actions`, but other sections mention tree types unconditionally.

### Current Behavior

In `system_prompt_builder.py`, the `_build_policy_architecture()` function always lists all tree types:

```python
def _build_policy_architecture() -> str:
    """Build the policy tree architecture explanation."""
    return """
    ...
    ### Tree Types
    Different trees handle different decision types:
    - **payment_tree**: Decides what to do with each transaction
    - **bank_tree**: Bank-level decisions (once per tick)
    - **strategic_collateral_tree**: Collateral management       # ← ALWAYS shown
    - **end_of_tick_collateral_tree**: End-of-tick collateral   # ← ALWAYS shown
    ...
    """
```

Similarly, `_build_common_errors()` shows examples for `strategic_collateral_tree`:

```python
### ERROR 2: WRONG ACTION FOR TREE
// WRONG in strategic_collateral_tree:    # ← ALWAYS shown
{"action": "Hold"}      // Hold is PAYMENT-only!
```

### Why This Is a Problem

When running experiments with `liquidity_pool` mode (where `strategic_collateral_tree` is not used), the LLM sees:
1. "strategic_collateral_tree: Collateral management" in the policy architecture section
2. Error examples mentioning `strategic_collateral_tree`

Even though the schema injection doesn't document any actions for `strategic_collateral_tree`, the LLM infers it should include one and generates invalid policies like:

```json
{
  "strategic_collateral_tree": {
    "type": "action",
    "node_id": "SC1",
    "action": "PostCollateral",
    "parameters": {"amount": {"value": 5000}}
  }
}
```

This causes runtime errors like: `Tree evaluation failed: Missing required action parameter: amount`

The current workaround is using `prompt_customization` to tell the LLM "DO NOT modify strategic_collateral_tree", but this is a band-aid that shouldn't be necessary.

## Proposed Solution

Make the `SystemPromptBuilder` class constraint-aware by passing `ScenarioConstraints` to the private section builder functions. Only mention tree types that have allowed actions.

### Design Goals

1. **Consistency**: If a tree type has no allowed actions, it should not be mentioned anywhere in the prompt
2. **Minimal changes**: Only modify sections that mention tree types unconditionally
3. **Backward compatible**: Scenarios that use all tree types continue to work unchanged

### Proposed API / Interface

The `SystemPromptBuilder` already receives `constraints` in its constructor. The change is to pass constraints to the private builder functions:

```python
class SystemPromptBuilder:
    def __init__(self, constraints: ScenarioConstraints) -> None:
        self._constraints = constraints
        # ...

    def build(self) -> str:
        sections: list[str] = []
        # ...

        # Pass constraints to functions that need to filter tree types
        sections.append(self._build_policy_architecture())  # Now uses self._constraints
        sections.append(self._build_common_errors())        # Now uses self._constraints
        # ...

    def _build_policy_architecture(self) -> str:
        """Build the policy tree architecture explanation."""
        # Only list tree types with allowed actions
        tree_descriptions = []

        if self._constraints.allowed_actions.get("payment_tree"):
            tree_descriptions.append("- **payment_tree**: Decides what to do with each transaction")
        if self._constraints.allowed_actions.get("bank_tree"):
            tree_descriptions.append("- **bank_tree**: Bank-level decisions (once per tick)")
        if self._constraints.allowed_actions.get("strategic_collateral_tree"):
            tree_descriptions.append("- **strategic_collateral_tree**: Collateral management")
        if self._constraints.allowed_actions.get("end_of_tick_collateral_tree"):
            tree_descriptions.append("- **end_of_tick_collateral_tree**: End-of-tick collateral adjustments")

        # Build string with only enabled trees
        return f"""
        ...
        ### Tree Types
        Different trees handle different decision types:
        {chr(10).join(tree_descriptions)}
        ...
        """

    def _build_common_errors(self) -> str:
        """Build the common errors section."""
        errors = []
        errors.append(ERROR_1_UNDEFINED_PARAMETER)

        # Only show strategic_collateral_tree error if it's enabled
        if self._constraints.allowed_actions.get("strategic_collateral_tree"):
            errors.append(ERROR_2_WRONG_ACTION_FOR_TREE)

        # ... other errors
        return "\n".join(errors)
```

### Usage Example

No usage change required. The filtering happens automatically based on the experiment config:

```yaml
# exp1.yaml - liquidity_pool mode, no strategic_collateral_tree
policy_constraints:
  allowed_actions:
    payment_tree:
      - Release
      - Hold
    bank_tree:
      - NoAction
    # Note: strategic_collateral_tree NOT listed → won't be mentioned in prompt
```

## Implementation Notes

### Invariants to Respect

- **Constraints filtering is already working** in `schema_injection.py` - follow that pattern
- **System prompt must remain valid** for all configurations

### Related Components

| Component | Impact |
|-----------|--------|
| `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` | Main changes - filter tree mentions |
| `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py` | Reference for how filtering works |
| `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py` | Add tests for filtering |

### Migration Path

1. Update `_build_policy_architecture()` to filter tree types based on constraints
2. Update `_build_common_errors()` to conditionally include tree-specific error examples
3. Add unit tests verifying tree types are filtered correctly
4. Remove `prompt_customization` workarounds from experiment configs (optional, can keep for extra clarity)

## Acceptance Criteria

- [ ] `_build_policy_architecture()` only lists tree types with allowed actions
- [ ] `_build_common_errors()` only shows examples for enabled tree types
- [ ] Experiment configs without `strategic_collateral_tree` in allowed_actions produce prompts with no mention of it
- [ ] Existing tests pass (backward compatible)
- [ ] New unit tests verify filtering behavior
- [ ] LLM no longer generates `strategic_collateral_tree` when it's not in allowed_actions

## Testing Requirements

1. **Unit tests**: Verify `SystemPromptBuilder.build()` output doesn't contain "strategic_collateral_tree" when constraints don't include it
2. **Unit tests**: Verify all tree types appear when all are in constraints
3. **Integration tests**: Run experiment with minimal constraints and verify LLM generates valid policy

## Related Documentation

- `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Evaluation modes and when trees are used

## Related Code

- `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` - Main file to modify
- `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py` - Reference for constraint-based filtering
- `api/payment_simulator/ai_cash_mgmt/constraints/scenario_constraints.py` - ScenarioConstraints model

## Notes

The `_build_castro_section()` function also mentions `strategic_collateral_tree`, but this is controlled by `castro_mode=True` which is not currently used. It can be addressed separately if Castro mode experiments are reactivated.

Current workaround in experiment configs uses `prompt_customization` to explicitly tell the LLM not to modify certain trees:
```yaml
prompt_customization:
  all: |
    IMPORTANT CONSTRAINTS:
    ...
    3. DO NOT modify strategic_collateral_tree - it should remain as HoldCollateral
```
This works but is a band-aid - the proper fix is filtering the system prompt.
