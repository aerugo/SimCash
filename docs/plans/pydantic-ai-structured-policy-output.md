# Pydantic AI Structured Policy Output

**Status**: Planning
**Priority**: Critical (Flagship Feature)
**Target**: Next major version
**Created**: 2025-12-03

---

## Executive Summary

LLM-based policy generation in the Castro experiments is unreliable due to complex, recursive policy DSL structures. This plan implements **Pydantic AI structured output** to constrain LLM responses to valid policy JSON, dramatically improving generation reliability.

### The Problem

Current optimizer scripts ask LLMs to generate policy JSON in free-form text. Observed failure modes:
- Invalid JSON syntax (missing brackets, trailing commas)
- Schema violations (wrong field names, invalid action types)
- Recursive structure errors (malformed nested decision trees)
- Feature toggle violations (using disabled DSL features)

From `LAB_NOTES.md` experiments: GPT-5.1 produced corrupted policy files, failing validation on retry.

### The Solution

Use **OpenAI Structured Output** (via Pydantic AI) to constrain generation:
1. Define Pydantic models matching the policy DSL
2. Handle recursive structures via **depth-limited flattening**
3. Generate schemas dynamically based on `PolicyFeatureToggles`
4. Validate outputs with existing Rust CLI validator as fallback

---

## Technical Constraints

### OpenAI Structured Output Limitations

OpenAI's structured output has critical limitations that affect our design:

| Limitation | Impact | Workaround |
|------------|--------|------------|
| **No `$ref`** | Cannot use recursive schemas | Depth-limited flattening |
| **No `anyOf`/`oneOf`** | Discriminated unions problematic | Explicit type enumeration |
| **100 properties max** | Large schemas may exceed | Split into sub-schemas |
| **5 nesting levels max** | Deep trees fail | Enforce max depth at schema level |
| **`additionalProperties: false`** | Strict by default | Explicit field definitions |

### Policy DSL Complexity

The policy DSL is deeply recursive:

```
TreeNode
├── Condition
│   ├── condition: Expression (recursive: And/Or/Not)
│   ├── on_true: TreeNode (recursive)
│   └── on_false: TreeNode (recursive)
└── Action
    └── action: ActionType
        └── parameters: Map<String, Value>
            └── Value (recursive for nested computations)
```

**Measured complexity:**
- 4 tree types with different valid actions/fields
- 14 PaymentActions + 4 BankActions + 3 CollateralActions + 2 RtgsActions = 23 action types
- 140+ context fields organized by category
- Expressions can nest arbitrarily deep (And(Or(Not(...))))

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                     PolicySchemaGenerator                    │
│  ┌─────────────────┐  ┌────────────────────────────────┐   │
│  │ FeatureToggles  │→│ Dynamic Schema Builder          │   │
│  │ (from scenario) │  │ - Filter allowed actions        │   │
│  └─────────────────┘  │ - Filter allowed fields         │   │
│                       │ - Set max depth                 │   │
│                       └────────────────────────────────┘   │
│                                    ↓                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Depth-Limited Pydantic Models               │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │  │
│  │  │ TreeNodeL0   │  │ TreeNodeL1   │  │ TreeNodeL2 │ │  │
│  │  │ (leaf only)  │  │ (1 level)    │  │ (2 levels) │ │  │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    LLM Generation Layer                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Pydantic AI Client                  │   │
│  │  response_format = PolicyTreeL5.model_json_schema() │   │
│  └─────────────────────────────────────────────────────┘   │
│                              ↓                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Post-Generation Validation             │   │
│  │  1. Pydantic model validation (structural)          │   │
│  │  2. Rust CLI validator (semantic/cross-field)       │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. Depth-Limited Tree Models

Since OpenAI doesn't support `$ref`, we create explicit types for each depth level:

```python
from pydantic import BaseModel, Field
from typing import Literal, Union
from typing_extensions import Annotated

# Level 0: Leaf nodes only (actions, no conditions)
class TreeNodeL0(BaseModel):
    """Leaf node - can only be an action."""
    type: Literal["action"]
    action: ActionType
    parameters: dict[str, PolicyValue] = Field(default_factory=dict)

# Level 1: Can have conditions with L0 children
class ConditionL1(BaseModel):
    """Condition node with depth-1 children."""
    type: Literal["condition"]
    condition: Expression
    on_true: TreeNodeL0
    on_false: TreeNodeL0

TreeNodeL1 = Annotated[
    Union[TreeNodeL0, ConditionL1],
    Field(discriminator="type")
]

# Level 2: Can have conditions with L1 children
class ConditionL2(BaseModel):
    type: Literal["condition"]
    condition: Expression
    on_true: TreeNodeL1
    on_false: TreeNodeL1

TreeNodeL2 = Annotated[
    Union[TreeNodeL0, ConditionL2],
    Field(discriminator="type")
]

# ... continue to Level 5 (max practical depth)
```

#### 2. Expression Flattening

Expressions (`And`, `Or`, `Not`, comparisons) also have recursive structure. Flatten similarly:

```python
# Base comparison - non-recursive
class Comparison(BaseModel):
    """A single comparison expression."""
    operator: Literal["gt", "lt", "gte", "lte", "eq", "ne"]
    left: ContextFieldOrValue
    right: ContextFieldOrValue

# Level 0: Single comparison only
ExpressionL0 = Comparison

# Level 1: Can combine with And/Or/Not
class AndL1(BaseModel):
    type: Literal["and"]
    operands: list[ExpressionL0]

class OrL1(BaseModel):
    type: Literal["or"]
    operands: list[ExpressionL0]

class NotL1(BaseModel):
    type: Literal["not"]
    operand: ExpressionL0

ExpressionL1 = Union[ExpressionL0, AndL1, OrL1, NotL1]

# Level 2: Can nest L1 expressions
class AndL2(BaseModel):
    type: Literal["and"]
    operands: list[ExpressionL1]

# ... etc
```

#### 3. Dynamic Schema Generator

Generate schemas based on scenario configuration:

```python
class PolicySchemaGenerator:
    """Generates Pydantic models based on feature toggles."""

    def __init__(
        self,
        tree_type: TreeType,
        feature_toggles: PolicyFeatureToggles,
        max_depth: int = 5,
    ):
        self.tree_type = tree_type
        self.toggles = feature_toggles
        self.max_depth = max_depth

    def get_allowed_actions(self) -> list[str]:
        """Return action types valid for this tree and toggles."""
        base_actions = ACTIONS_BY_TREE_TYPE[self.tree_type]
        return [a for a in base_actions if self._action_allowed(a)]

    def get_allowed_fields(self) -> list[str]:
        """Return context fields valid for this tree and toggles."""
        base_fields = FIELDS_BY_TREE_TYPE[self.tree_type]
        return [f for f in base_fields if self._field_allowed(f)]

    def build_schema(self) -> type[BaseModel]:
        """Dynamically construct the Pydantic model."""
        # Create action enum with allowed values only
        allowed_actions = self.get_allowed_actions()
        ActionEnum = Literal[tuple(allowed_actions)]

        # Build depth-limited tree model
        return self._build_tree_model(self.max_depth, ActionEnum)

    def _action_allowed(self, action: str) -> bool:
        """Check if action is allowed by feature toggles."""
        category = ACTION_CATEGORIES.get(action)
        return self.toggles.is_category_allowed(category)
```

#### 4. Pydantic AI Integration

Integrate with OpenAI structured output:

```python
from openai import OpenAI
from pydantic_ai import Agent

class StructuredPolicyGenerator:
    """Generate valid policies using structured output."""

    def __init__(
        self,
        model: str = "gpt-4o-2024-08-06",
        max_depth: int = 5,
    ):
        self.client = OpenAI()
        self.model = model
        self.max_depth = max_depth

    async def generate_policy(
        self,
        tree_type: TreeType,
        feature_toggles: PolicyFeatureToggles,
        context: PolicyContext,
        current_policy: dict | None = None,
    ) -> dict:
        """Generate a valid policy tree."""

        # Build schema for this specific context
        generator = PolicySchemaGenerator(
            tree_type=tree_type,
            feature_toggles=feature_toggles,
            max_depth=self.max_depth,
        )
        PolicyModel = generator.build_schema()

        # Build prompt with context
        prompt = self._build_prompt(
            tree_type=tree_type,
            allowed_actions=generator.get_allowed_actions(),
            allowed_fields=generator.get_allowed_fields(),
            context=context,
            current_policy=current_policy,
        )

        # Call OpenAI with structured output
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            response_format=PolicyModel,
        )

        # Extract and validate
        policy = response.choices[0].message.parsed
        return policy.model_dump()

    def _build_prompt(self, ...) -> str:
        """Build context-aware prompt for policy generation."""
        return f"""
Generate an improved {tree_type} policy tree.

## Available Actions
{self._format_actions(allowed_actions)}

## Available Context Fields
{self._format_fields(allowed_fields)}

## Current Policy Performance
{self._format_performance(context)}

## Current Policy (to improve)
{json.dumps(current_policy, indent=2) if current_policy else "None - create initial policy"}

## Instructions
Generate a {tree_type} that improves upon the current policy based on the performance data.
Focus on reducing costs while maintaining settlement rate.
"""
```

---

## Implementation Plan

### Phase 1: Core Schema Models (TDD)

**Goal**: Create depth-limited Pydantic models that represent the policy DSL

#### Step 1.1: Base Value Types
```python
# tests/unit/test_policy_schema_values.py
def test_context_field_validation():
    """Context fields must be valid identifiers."""
    field = ContextField(name="tx.amount")
    assert field.name == "tx.amount"

def test_literal_value_types():
    """Literals can be int, float, or string."""
    assert LiteralValue(value=100).value == 100
    assert LiteralValue(value="HIGH").value == "HIGH"
```

**Implementation files:**
- `experiments/castro/schemas/values.py` - PolicyValue, ContextField, LiteralValue
- `experiments/castro/schemas/operators.py` - Comparison operators

#### Step 1.2: Expression Models
```python
# tests/unit/test_policy_schema_expressions.py
def test_simple_comparison():
    """Basic comparison expressions."""
    expr = Comparison(
        operator="gt",
        left=ContextField(name="tx.amount"),
        right=LiteralValue(value=10000),
    )
    assert expr.operator == "gt"

def test_and_expression_l1():
    """Level-1 AND combines comparisons."""
    expr = AndL1(
        operands=[
            Comparison(operator="gt", left=..., right=...),
            Comparison(operator="lt", left=..., right=...),
        ]
    )
    assert len(expr.operands) == 2
```

**Implementation files:**
- `experiments/castro/schemas/expressions.py` - Comparison, AndL{N}, OrL{N}, NotL{N}

#### Step 1.3: Action Models
```python
# tests/unit/test_policy_schema_actions.py
def test_release_action():
    """ReleasePayment action with no parameters."""
    action = ActionModel(type="ReleasePayment", parameters={})
    assert action.type == "ReleasePayment"

def test_hold_action_with_params():
    """HoldPayment can have optional reason."""
    action = ActionModel(
        type="HoldPayment",
        parameters={"reason": "low_balance"}
    )
    assert action.parameters["reason"] == "low_balance"
```

**Implementation files:**
- `experiments/castro/schemas/actions.py` - ActionModel, action type enums

#### Step 1.4: Tree Node Models
```python
# tests/unit/test_policy_schema_tree.py
def test_leaf_action_node():
    """Level-0 nodes are actions only."""
    node = TreeNodeL0(
        type="action",
        action="ReleasePayment",
        parameters={},
    )
    assert node.type == "action"

def test_condition_node_l1():
    """Level-1 nodes can have conditions with L0 children."""
    node = ConditionL1(
        type="condition",
        condition=Comparison(...),
        on_true=TreeNodeL0(type="action", action="ReleasePayment", parameters={}),
        on_false=TreeNodeL0(type="action", action="HoldPayment", parameters={}),
    )
    assert node.on_true.action == "ReleasePayment"

def test_nested_tree_l3():
    """Level-3 tree can have 3 levels of nesting."""
    # Build a tree that requires 3 levels
    ...
```

**Implementation files:**
- `experiments/castro/schemas/tree.py` - TreeNodeL{N}, ConditionL{N}

### Phase 2: Dynamic Schema Generation (TDD)

**Goal**: Generate schemas dynamically based on feature toggles

#### Step 2.1: Action Filtering
```python
# tests/unit/test_schema_generator.py
def test_payment_tree_actions():
    """Payment tree has specific allowed actions."""
    gen = PolicySchemaGenerator(tree_type="payment_tree", toggles=default_toggles())
    actions = gen.get_allowed_actions()
    assert "ReleasePayment" in actions
    assert "HoldPayment" in actions
    assert "PostCollateral" not in actions  # Collateral action

def test_disabled_category_filters_actions():
    """Disabled categories exclude their actions."""
    toggles = PolicyFeatureToggles(
        exclude_categories=["splitting"]
    )
    gen = PolicySchemaGenerator(tree_type="payment_tree", toggles=toggles)
    actions = gen.get_allowed_actions()
    assert "SplitPayment" not in actions
```

#### Step 2.2: Field Filtering
```python
def test_payment_tree_fields():
    """Payment tree has transaction fields available."""
    gen = PolicySchemaGenerator(tree_type="payment_tree", toggles=default_toggles())
    fields = gen.get_allowed_fields()
    assert "tx.amount" in fields
    assert "tx.priority" in fields

def test_bank_tree_fields():
    """Bank tree has agent-level fields."""
    gen = PolicySchemaGenerator(tree_type="bank_tree", toggles=default_toggles())
    fields = gen.get_allowed_fields()
    assert "agent.balance" in fields
    assert "tx.amount" not in fields  # No transaction context
```

#### Step 2.3: Schema Building
```python
def test_build_schema_returns_pydantic_model():
    """Generated schema is a valid Pydantic model."""
    gen = PolicySchemaGenerator(
        tree_type="payment_tree",
        toggles=default_toggles(),
        max_depth=3,
    )
    Model = gen.build_schema()
    assert issubclass(Model, BaseModel)

def test_schema_validates_valid_policy():
    """Valid policy passes schema validation."""
    gen = PolicySchemaGenerator(...)
    Model = gen.build_schema()

    valid_policy = {
        "type": "action",
        "action": "ReleasePayment",
        "parameters": {},
    }
    parsed = Model.model_validate(valid_policy)
    assert parsed.action == "ReleasePayment"

def test_schema_rejects_invalid_action():
    """Invalid action type fails validation."""
    gen = PolicySchemaGenerator(tree_type="payment_tree", ...)
    Model = gen.build_schema()

    invalid_policy = {
        "type": "action",
        "action": "InvalidAction",  # Not a real action
        "parameters": {},
    }
    with pytest.raises(ValidationError):
        Model.model_validate(invalid_policy)
```

**Implementation files:**
- `experiments/castro/schemas/generator.py` - PolicySchemaGenerator
- `experiments/castro/schemas/registry.py` - Action/field registries per tree type

### Phase 3: LLM Integration (TDD)

**Goal**: Integrate with OpenAI structured output API

#### Step 3.1: Prompt Builder
```python
# tests/unit/test_prompt_builder.py
def test_prompt_includes_allowed_actions():
    """Prompt lists available actions."""
    builder = PolicyPromptBuilder(
        tree_type="payment_tree",
        allowed_actions=["ReleasePayment", "HoldPayment"],
        allowed_fields=["tx.amount"],
    )
    prompt = builder.build()
    assert "ReleasePayment" in prompt
    assert "HoldPayment" in prompt

def test_prompt_includes_performance_context():
    """Prompt shows current policy performance."""
    builder = PolicyPromptBuilder(...)
    builder.set_performance(
        total_cost=1500,
        settlement_rate=0.95,
        per_bank_costs={"A": 800, "B": 700},
    )
    prompt = builder.build()
    assert "1500" in prompt
    assert "95%" in prompt or "0.95" in prompt
```

**Implementation files:**
- `experiments/castro/prompts/builder.py` - PolicyPromptBuilder
- `experiments/castro/prompts/templates.py` - Prompt templates

#### Step 3.2: Structured Output Client
```python
# tests/integration/test_structured_output.py
@pytest.mark.integration
@pytest.mark.requires_openai
def test_generate_simple_policy():
    """Generate a valid simple policy via structured output."""
    generator = StructuredPolicyGenerator(model="gpt-4o-2024-08-06")

    policy = await generator.generate_policy(
        tree_type="payment_tree",
        feature_toggles=default_toggles(),
        context=PolicyContext(
            current_costs={"A": 1000, "B": 1000},
            settlement_rate=1.0,
        ),
    )

    # Policy should be valid dict
    assert isinstance(policy, dict)
    assert "type" in policy

    # Should pass CLI validation
    result = validate_policy_with_cli(policy, tree_type="payment_tree")
    assert result.is_valid

@pytest.mark.integration
@pytest.mark.requires_openai
def test_generate_with_constraints():
    """Generated policy respects feature toggle constraints."""
    toggles = PolicyFeatureToggles(exclude_categories=["splitting"])

    generator = StructuredPolicyGenerator()
    policy = await generator.generate_policy(
        tree_type="payment_tree",
        feature_toggles=toggles,
        context=...,
    )

    # Should not contain any splitting actions
    policy_str = json.dumps(policy)
    assert "SplitPayment" not in policy_str
```

**Implementation files:**
- `experiments/castro/generator/client.py` - StructuredPolicyGenerator
- `experiments/castro/generator/validation.py` - CLI validation wrapper

#### Step 3.3: Retry and Fallback Logic
```python
# tests/unit/test_generation_retry.py
def test_retry_on_validation_failure():
    """Retries if generated policy fails semantic validation."""
    # Mock generator that fails first attempt
    mock_generator = MockGenerator(fail_count=1)

    generator = RobustPolicyGenerator(
        base_generator=mock_generator,
        max_retries=3,
    )

    policy = await generator.generate_policy(...)
    assert policy is not None
    assert mock_generator.call_count == 2  # 1 fail + 1 success

def test_includes_error_in_retry_prompt():
    """Retry prompt includes validation error details."""
    # First attempt fails with specific error
    error = "Invalid field: tx.unknown_field"

    generator = RobustPolicyGenerator(...)
    # Mock first failure
    ...

    # Check retry prompt includes error
    assert error in mock_generator.last_prompt
```

**Implementation files:**
- `experiments/castro/generator/robust.py` - RobustPolicyGenerator with retries

### Phase 4: Optimizer Integration

**Goal**: Integrate structured output into existing optimizer workflow

#### Step 4.1: Replace Free-Form Generation
```python
# In optimizer_v4.py (new version)
class StructuredOptimizer:
    """Optimizer using structured output for policy generation."""

    def __init__(
        self,
        config: ExperimentConfig,
        model: str = "gpt-4o-2024-08-06",
    ):
        self.config = config
        self.generator = StructuredPolicyGenerator(model=model)
        self.feature_toggles = self._extract_toggles(config)

    async def optimize_iteration(
        self,
        current_policy: dict,
        performance: PerformanceMetrics,
    ) -> dict:
        """Run one optimization iteration."""

        # Generate improved policy with structured output
        new_policy = await self.generator.generate_policy(
            tree_type="payment_tree",  # Or iterate over all trees
            feature_toggles=self.feature_toggles,
            context=PolicyContext.from_performance(performance),
            current_policy=current_policy,
        )

        # Validate with Rust CLI (belt and suspenders)
        validation = validate_policy_cli(new_policy)
        if not validation.is_valid:
            raise PolicyValidationError(validation.errors)

        return new_policy
```

#### Step 4.2: Multi-Tree Policy Generation
```python
async def generate_full_policy(
    self,
    current_policies: dict[str, dict],
    performance: PerformanceMetrics,
) -> dict[str, dict]:
    """Generate all policy trees."""

    new_policies = {}
    for tree_type in ["payment_tree", "bank_tree",
                      "strategic_collateral_tree",
                      "end_of_tick_collateral_tree"]:

        if tree_type in current_policies:
            new_policies[tree_type] = await self.generator.generate_policy(
                tree_type=tree_type,
                feature_toggles=self.feature_toggles,
                context=PolicyContext.from_performance(performance),
                current_policy=current_policies.get(tree_type),
            )

    return new_policies
```

### Phase 5: Testing and Validation

#### Step 5.1: Unit Test Suite
```
experiments/castro/tests/
├── unit/
│   ├── test_schema_values.py      # Value types
│   ├── test_schema_expressions.py # Expression models
│   ├── test_schema_actions.py     # Action models
│   ├── test_schema_tree.py        # Tree node models
│   ├── test_schema_generator.py   # Dynamic generation
│   ├── test_prompt_builder.py     # Prompt construction
│   └── test_retry_logic.py        # Retry behavior
```

#### Step 5.2: Integration Test Suite
```
experiments/castro/tests/
├── integration/
│   ├── test_structured_output.py  # OpenAI API integration
│   ├── test_cli_validation.py     # Rust CLI validation
│   └── test_optimizer_v4.py       # Full optimizer flow
```

#### Step 5.3: Edge Case Tests
```python
# tests/integration/test_edge_cases.py

@pytest.mark.integration
@pytest.mark.requires_openai
def test_max_depth_policy():
    """Generate policy at maximum allowed depth."""
    generator = StructuredPolicyGenerator(max_depth=5)
    # Request a complex policy that uses full depth
    ...

@pytest.mark.integration
@pytest.mark.requires_openai
def test_all_action_types():
    """Ensure all action types can be generated."""
    for action_type in ALL_PAYMENT_ACTIONS:
        # Generate policy that uses this action
        ...

@pytest.mark.integration
@pytest.mark.requires_openai
def test_complex_expressions():
    """Generate policies with nested And/Or/Not expressions."""
    ...

@pytest.mark.integration
@pytest.mark.requires_openai
def test_feature_toggle_edge_cases():
    """Test various feature toggle combinations."""
    test_cases = [
        PolicyFeatureToggles(include_categories=["basic"]),
        PolicyFeatureToggles(exclude_categories=["timing", "splitting"]),
        PolicyFeatureToggles(include_categories=[], exclude_categories=[]),
    ]
    for toggles in test_cases:
        ...
```

---

## File Structure

```
experiments/castro/
├── schemas/
│   ├── __init__.py
│   ├── values.py          # PolicyValue, ContextField, LiteralValue
│   ├── operators.py       # Comparison operators
│   ├── expressions.py     # ExpressionL{N} models
│   ├── actions.py         # ActionModel, action enums
│   ├── tree.py            # TreeNodeL{N}, ConditionL{N}
│   ├── generator.py       # PolicySchemaGenerator
│   └── registry.py        # Action/field registries
│
├── prompts/
│   ├── __init__.py
│   ├── builder.py         # PolicyPromptBuilder
│   └── templates.py       # System/user prompt templates
│
├── generator/
│   ├── __init__.py
│   ├── client.py          # StructuredPolicyGenerator
│   ├── robust.py          # RobustPolicyGenerator (with retries)
│   └── validation.py      # CLI validation wrapper
│
├── scripts/
│   ├── optimizer_v4.py    # New structured optimizer
│   └── ...
│
└── tests/
    ├── unit/
    │   └── ...
    └── integration/
        └── ...
```

---

## Risk Mitigation

### Risk 1: OpenAI API Changes
**Mitigation**:
- Pin to specific model version (`gpt-4o-2024-08-06`)
- Abstract API calls behind interface for easy swap
- Keep fallback to free-form generation + validation

### Risk 2: Schema Too Complex for OpenAI
**Mitigation**:
- Start with max_depth=3, increase if needed
- Split complex schemas into sub-schemas
- Monitor for "schema too large" errors

### Risk 3: Generated Policies Semantically Invalid
**Mitigation**:
- Always validate with Rust CLI as second pass
- Include validation errors in retry prompts
- Log all validation failures for analysis

### Risk 4: Feature Toggle Combinations Untested
**Mitigation**:
- Enumerate all toggle combinations in tests
- Use property-based testing for toggle matrix
- Maintain known-good test fixtures per toggle set

---

## Success Metrics

| Metric | Current (Baseline) | Target |
|--------|-------------------|--------|
| Policy generation success rate | ~60% | >95% |
| Validation retry needed | ~40% | <10% |
| Schema validation failures | ~30% | <5% |
| Semantic validation failures | ~20% | <5% |
| Mean iterations to valid policy | 1.7 | 1.05 |

---

## Timeline Estimate

| Phase | Description | Complexity |
|-------|-------------|------------|
| Phase 1 | Core Schema Models | Medium |
| Phase 2 | Dynamic Generation | High |
| Phase 3 | LLM Integration | High |
| Phase 4 | Optimizer Integration | Medium |
| Phase 5 | Testing & Validation | Medium |

---

## Dependencies

- `pydantic>=2.0` (already installed)
- `openai>=1.0` (already installed)
- `pydantic-ai` (optional - for higher-level abstractions)

---

## Open Questions

1. **Max depth trade-off**: Deeper trees = more expressive but slower/riskier generation. Start with 5?

2. **Expression depth separate from tree depth?**: Expressions could be limited to 2-3 levels while trees go to 5.

3. **Caching schemas**: Should we cache generated Pydantic models for same toggle configurations?

4. **Streaming**: Should we support streaming responses for long generations?

5. **Multi-model fallback**: If GPT-4o fails, try Claude? Different models may have different structured output behavior.

---

## References

- [OpenAI Structured Output Guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Pydantic AI Documentation](https://ai.pydantic.dev/)
- [SimCash Policy DSL Reference](../reference/policy/index.md)
- [Castro Experiment Lab Notes](../../experiments/castro/LAB_NOTES.md)
