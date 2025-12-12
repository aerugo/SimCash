# Phase 2: System Prompt Builder

## Objective
Build the complete system prompt that provides the LLM with:
1. Expert context and role definition
2. Domain explanation (RTGS, queues, LSM, costs)
3. Cost structure and objectives
4. Policy tree architecture explanation
5. Injected policy schema (filtered by constraints)
6. Injected cost schema (with current values)

## TDD Approach
Write tests first, then implement the code to make them pass.

## Files to Create

### 1. Test File
`api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py`

### 2. Implementation File
`api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py`

## System Prompt Structure

Based on the user's scaffold, the system prompt should follow this structure:

```
──────────────
System Prompt
──────────────
You are an expert in payment system optimization.
Your job is to generate valid JSON policies for the SimCash payment simulator.

[Domain explanation - RTGS, queues, costs]

Cost Structure and Objectives
[Cost parameters injected - filtered by scenario]

Policy Tree Architecture
[Architecture explanation]

Optimization Process
[What the LLM will receive and what it needs to do]

POLICY FORMAT SPECIFICATION:
[Policy schema specification - filtered by constraints]

COST PARAMETERS:
[Cost schema specification - filtered by scenario]

CRITICAL: Every node MUST have a unique "node_id" string field!
```

## Test Plan

### Test Group 1: System Prompt Structure

```python
class TestSystemPromptStructure:
    """Tests for system prompt overall structure."""

    def test_prompt_starts_with_expert_role():
        """Prompt begins with expert role definition."""
        prompt = build_system_prompt(constraints)
        assert prompt.startswith("You are an expert")

    def test_prompt_includes_domain_explanation():
        """Prompt includes RTGS/queue/LSM explanation."""
        prompt = build_system_prompt(constraints)
        assert "RTGS" in prompt or "real-time" in prompt.lower()
        assert "queue" in prompt.lower()
        assert "settlement" in prompt.lower()

    def test_prompt_includes_cost_objectives():
        """Prompt explains cost minimization objective."""
        prompt = build_system_prompt(constraints)
        assert "cost" in prompt.lower()
        assert "minimize" in prompt.lower() or "objective" in prompt.lower()

    def test_prompt_includes_policy_tree_explanation():
        """Prompt explains policy tree architecture."""
        prompt = build_system_prompt(constraints)
        assert "policy tree" in prompt.lower() or "decision tree" in prompt.lower()
        assert "condition" in prompt.lower()
        assert "action" in prompt.lower()

    def test_prompt_includes_optimization_process():
        """Prompt explains what the LLM receives."""
        prompt = build_system_prompt(constraints)
        assert "simulation" in prompt.lower()
        assert "iteration" in prompt.lower()
```

### Test Group 2: Schema Injection

```python
class TestSchemaInjection:
    """Tests for schema injection into system prompt."""

    def test_policy_schema_injected():
        """Policy schema section is included."""
        prompt = build_system_prompt(constraints)
        assert "POLICY FORMAT" in prompt.upper() or "policy schema" in prompt.lower()

    def test_cost_schema_injected():
        """Cost schema section is included."""
        prompt = build_system_prompt(constraints)
        assert "COST PARAMETERS" in prompt.upper() or "cost schema" in prompt.lower()

    def test_node_id_requirement_emphasized():
        """node_id requirement is clearly stated."""
        prompt = build_system_prompt(constraints)
        assert "node_id" in prompt
        assert "unique" in prompt.lower() or "CRITICAL" in prompt

    def test_allowed_actions_visible():
        """Allowed actions from constraints are in prompt."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]}
        )
        prompt = build_system_prompt(constraints)
        assert "Release" in prompt
        assert "Hold" in prompt
        assert "Split" not in prompt  # Not in allowed_actions

    def test_allowed_fields_visible():
        """Allowed fields from constraints are in prompt."""
        constraints = ScenarioConstraints(
            allowed_fields=["balance", "ticks_to_deadline"]
        )
        prompt = build_system_prompt(constraints)
        assert "balance" in prompt
        assert "ticks_to_deadline" in prompt
```

### Test Group 3: Cost Rate Injection

```python
class TestCostRateInjection:
    """Tests for cost rate injection."""

    def test_cost_rates_included():
        """Current cost rates are shown."""
        cost_rates = {
            "overdraft_bps_per_tick": 0.001,
            "delay_cost_per_tick_per_cent": 0.0001,
        }
        prompt = build_system_prompt(constraints, cost_rates=cost_rates)
        assert "0.001" in prompt
        assert "0.0001" in prompt

    def test_default_rates_used_when_none():
        """Default documentation used when no rates provided."""
        prompt = build_system_prompt(constraints)
        # Should still include cost documentation
        assert "overdraft" in prompt.lower()
        assert "delay" in prompt.lower()
```

### Test Group 4: Castro Mode

```python
class TestCastroMode:
    """Tests for Castro paper alignment mode."""

    def test_castro_mode_adds_constraints():
        """Castro mode includes paper alignment section."""
        constraints = get_castro_constraints()
        prompt = build_system_prompt(constraints, castro_mode=True)
        # Castro-specific content
        assert "Castro" in prompt or "t=0" in prompt or "initial" in prompt.lower()

    def test_castro_mode_restricts_collateral():
        """Castro mode emphasizes t=0 collateral decision."""
        constraints = get_castro_constraints()
        prompt = build_system_prompt(constraints, castro_mode=True)
        # Should mention initial decision
        assert "tick 0" in prompt.lower() or "t=0" in prompt
```

## API Design

```python
# api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py

@dataclass
class SystemPromptConfig:
    """Configuration for system prompt generation."""
    constraints: ScenarioConstraints
    cost_rates: dict[str, Any] | None = None
    castro_mode: bool = False
    include_examples: bool = True


def build_system_prompt(
    constraints: ScenarioConstraints,
    cost_rates: dict[str, Any] | None = None,
    castro_mode: bool = False,
    include_examples: bool = True,
) -> str:
    """Build the complete system prompt for policy optimization.

    Args:
        constraints: Scenario constraints for filtering schemas.
        cost_rates: Current cost rate values (optional).
        castro_mode: Whether to include Castro paper alignment.
        include_examples: Whether to include JSON examples.

    Returns:
        Complete system prompt string.
    """
    ...


class SystemPromptBuilder:
    """Builder for constructing system prompts.

    Allows step-by-step construction with method chaining.
    """

    def __init__(self, constraints: ScenarioConstraints) -> None:
        ...

    def with_cost_rates(self, rates: dict[str, Any]) -> SystemPromptBuilder:
        ...

    def with_castro_mode(self, enabled: bool = True) -> SystemPromptBuilder:
        ...

    def with_examples(self, enabled: bool = True) -> SystemPromptBuilder:
        ...

    def build(self) -> str:
        ...
```

## Implementation Plan

### Step 1: Create Test File (TDD)
Create comprehensive tests covering all prompt sections.

### Step 2: Create Implementation Skeleton
Create the module with function signatures and docstrings.

### Step 3: Implement Domain Explanation
Write the RTGS/queue/LSM domain explanation text.

### Step 4: Implement Cost Objectives
Write the cost minimization objective explanation.

### Step 5: Implement Policy Tree Architecture
Write the policy tree architecture explanation.

### Step 6: Implement Optimization Process
Explain what the LLM receives and should produce.

### Step 7: Integrate Schema Injection
Use Phase 1 helpers to inject filtered schemas.

### Step 8: Implement Castro Mode
Add optional Castro paper alignment section.

### Step 9: Run All Tests
Verify all tests pass.

## Acceptance Criteria

1. [ ] All tests pass
2. [ ] Prompt includes all required sections
3. [ ] Schema filtering works correctly
4. [ ] Cost rates can be injected
5. [ ] Castro mode works when enabled
6. [ ] Type annotations complete
7. [ ] mypy passes

## Dependencies

- Phase 1: `schema_injection.py` (get_filtered_policy_schema, get_filtered_cost_schema)
- `payment_simulator.ai_cash_mgmt.constraints.ScenarioConstraints`

## Notes

- The system prompt should be comprehensive but not excessively long
- Focus on clarity and reducing LLM confusion
- Examples are valuable for reducing errors
- The Castro mode is optional but important for research experiments
