# Plan: Full SimCash Expressiveness for Robust Policy Agent

> **Status**: Ready for implementation
> **Author**: Claude
> **Date**: 2025-12-03

## Problem Statement

The current `RobustPolicyAgent` artificially limits policy expressiveness to only 3 hardcoded parameters, when SimCash supports **any user-defined parameters** as long as they're used consistently within the policy.

**Current limitation:**
```python
ALLOWED_PARAMETERS = ["urgency_threshold", "initial_liquidity_fraction", "liquidity_buffer_factor"]
```

**SimCash reality:** Any parameter name is valid if defined in `parameters` and referenced correctly in trees.

## Goal

Make `RobustPolicyAgent` support the **full expressiveness** of SimCash's policy language by:
1. Allowing scenario-configurable parameter sets
2. Dynamically generating Pydantic schemas from configuration
3. Ensuring generated policies pass SimCash validation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  ScenarioConstraints                        │
│  - allowed_parameters: list[ParameterSpec]                  │
│  - allowed_fields: list[str] (from registry)                │
│  - allowed_actions: list[str] (from registry)               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              create_constrained_policy_model()              │
│  Dynamically generates Pydantic models at runtime           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   RobustPolicyAgent                         │
│  Uses dynamic model for PydanticAI structured output        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              SimCash validate_policy()                      │
│  Final validation via Rust backend                          │
└─────────────────────────────────────────────────────────────┘
```

---

## TDD Implementation Plan

### Phase 1: Parameter Configuration Schema

#### Test 1.1: ParameterSpec validation
```python
# tests/test_parameter_config.py

def test_parameter_spec_valid():
    """ParameterSpec accepts valid configuration."""
    spec = ParameterSpec(
        name="urgency_threshold",
        min_value=0.0,
        max_value=20.0,
        default=3.0,
        description="Ticks before deadline when payment is urgent",
    )
    assert spec.name == "urgency_threshold"
    assert spec.default == 3.0

def test_parameter_spec_default_within_bounds():
    """ParameterSpec rejects default outside min/max."""
    with pytest.raises(ValidationError):
        ParameterSpec(
            name="bad_param",
            min_value=0.0,
            max_value=10.0,
            default=15.0,  # Outside bounds!
            description="Invalid",
        )

def test_parameter_spec_min_less_than_max():
    """ParameterSpec rejects min >= max."""
    with pytest.raises(ValidationError):
        ParameterSpec(
            name="bad_param",
            min_value=10.0,
            max_value=5.0,  # min > max!
            default=7.0,
            description="Invalid",
        )
```

#### Test 1.2: ScenarioConstraints validation
```python
def test_scenario_constraints_valid():
    """ScenarioConstraints accepts valid configuration."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "A threshold"),
        ],
        allowed_fields=["balance", "effective_liquidity"],
        allowed_actions=["Release", "Hold"],
    )
    assert len(constraints.allowed_parameters) == 1
    assert "balance" in constraints.allowed_fields

def test_scenario_constraints_rejects_unknown_field():
    """ScenarioConstraints rejects fields not in SimCash registry."""
    with pytest.raises(ValidationError, match="unknown field"):
        ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["invented_field_xyz"],  # Not in registry!
            allowed_actions=["Release"],
        )

def test_scenario_constraints_rejects_unknown_action():
    """ScenarioConstraints rejects actions not in SimCash registry."""
    with pytest.raises(ValidationError, match="unknown action"):
        ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions=["InventedAction"],  # Not in registry!
        )
```

#### Implementation 1: `schemas/parameter_config.py`
```python
class ParameterSpec(BaseModel):
    name: str
    min_value: float
    max_value: float
    default: float
    description: str

    @model_validator(mode="after")
    def validate_bounds(self) -> "ParameterSpec":
        if self.min_value >= self.max_value:
            raise ValueError("min_value must be < max_value")
        if not (self.min_value <= self.default <= self.max_value):
            raise ValueError("default must be within [min_value, max_value]")
        return self

class ScenarioConstraints(BaseModel):
    allowed_parameters: list[ParameterSpec]
    allowed_fields: list[str]
    allowed_actions: list[str]

    @field_validator("allowed_fields")
    @classmethod
    def validate_fields(cls, v: list[str]) -> list[str]:
        from .registry import PAYMENT_TREE_FIELDS
        invalid = set(v) - set(PAYMENT_TREE_FIELDS)
        if invalid:
            raise ValueError(f"unknown field(s): {invalid}")
        return v

    @field_validator("allowed_actions")
    @classmethod
    def validate_actions(cls, v: list[str]) -> list[str]:
        from .registry import ALL_ACTIONS
        invalid = set(v) - set(ALL_ACTIONS)
        if invalid:
            raise ValueError(f"unknown action(s): {invalid}")
        return v
```

---

### Phase 2: Dynamic Model Generation

#### Test 2.1: Generate parameter model
```python
# tests/test_dynamic_schema.py

def test_create_parameter_model_with_single_param():
    """Creates a Pydantic model with one parameter."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "A threshold"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    ParamModel = create_parameter_model(constraints)

    # Should accept valid value
    params = ParamModel(threshold=10.0)
    assert params.threshold == 10.0

    # Should use default
    params_default = ParamModel()
    assert params_default.threshold == 5.0

def test_create_parameter_model_rejects_out_of_bounds():
    """Generated model enforces min/max bounds."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "A threshold"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    ParamModel = create_parameter_model(constraints)

    with pytest.raises(ValidationError):
        ParamModel(threshold=25.0)  # Above max

def test_create_parameter_model_rejects_extra_params():
    """Generated model forbids undefined parameters."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "A threshold"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    ParamModel = create_parameter_model(constraints)

    with pytest.raises(ValidationError):
        ParamModel(threshold=5.0, invented_param=10.0)  # Extra param!

def test_create_parameter_model_multiple_params():
    """Creates model with multiple parameters."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency threshold"),
            ParameterSpec("buffer", 0.5, 3.0, 1.0, "Buffer factor"),
            ParameterSpec("split_size", 0.1, 0.9, 0.5, "Split fraction"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    ParamModel = create_parameter_model(constraints)

    params = ParamModel(urgency=5.0, buffer=2.0, split_size=0.3)
    assert params.urgency == 5.0
    assert params.buffer == 2.0
    assert params.split_size == 0.3
```

#### Test 2.2: Generate field reference model
```python
def test_create_field_literal_restricts_to_allowed():
    """Generated Literal type only allows specified fields."""
    constraints = ScenarioConstraints(
        allowed_parameters=[],
        allowed_fields=["balance", "effective_liquidity", "ticks_to_deadline"],
        allowed_actions=["Release"],
    )

    FieldModel = create_context_field_model(constraints)

    # Should accept allowed field
    field_ref = FieldModel(field="balance")
    assert field_ref.field == "balance"

    # Should reject disallowed field (even if valid in SimCash)
    with pytest.raises(ValidationError):
        FieldModel(field="queue1_total_value")  # Not in allowed list
```

#### Test 2.3: Generate parameter reference model
```python
def test_create_param_ref_model_restricts_to_defined():
    """Generated param ref only allows defined parameter names."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "Threshold"),
            ParameterSpec("buffer", 0.5, 3.0, 1.0, "Buffer"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    ParamRefModel = create_param_ref_model(constraints)

    # Should accept defined param
    ref = ParamRefModel(param="threshold")
    assert ref.param == "threshold"

    # Should reject undefined param
    with pytest.raises(ValidationError):
        ParamRefModel(param="undefined_param")
```

#### Test 2.4: Generate full policy model
```python
def test_create_policy_model_integrates_all_constraints():
    """Full policy model uses all constraint types."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency"),
        ],
        allowed_fields=["balance", "ticks_to_deadline"],
        allowed_actions=["Release", "Hold"],
    )

    PolicyModel = create_constrained_policy_model(constraints)

    # Should accept valid policy
    policy = PolicyModel(
        parameters={"urgency": 5.0},
        payment_tree={
            "type": "condition",
            "condition": {
                "op": "<=",
                "left": {"field": "ticks_to_deadline"},
                "right": {"param": "urgency"},
            },
            "on_true": {"type": "action", "action": "Release"},
            "on_false": {"type": "action", "action": "Hold"},
        },
    )
    assert policy.parameters["urgency"] == 5.0
```

#### Implementation 2: `schemas/dynamic.py`
```python
from pydantic import create_model, Field, ConfigDict
from typing import Literal

def create_parameter_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a Pydantic model for policy parameters."""
    fields = {}
    for spec in constraints.allowed_parameters:
        fields[spec.name] = (
            float,
            Field(
                default=spec.default,
                ge=spec.min_value,
                le=spec.max_value,
                description=spec.description,
            ),
        )

    return create_model(
        "DynamicParameters",
        __config__=ConfigDict(extra="forbid"),
        **fields,
    )

def create_context_field_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a model that only accepts allowed field names."""
    if not constraints.allowed_fields:
        raise ValueError("Must allow at least one field")

    FieldLiteral = Literal[tuple(constraints.allowed_fields)]

    return create_model(
        "DynamicContextField",
        field=(FieldLiteral, ...),
    )

def create_param_ref_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a model that only accepts defined parameter names."""
    param_names = [p.name for p in constraints.allowed_parameters]
    if not param_names:
        # No parameters defined - param refs not allowed
        return None

    ParamLiteral = Literal[tuple(param_names)]

    return create_model(
        "DynamicParamRef",
        param=(ParamLiteral, ...),
    )

def create_constrained_policy_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate a complete policy model from constraints."""
    # ... full implementation
```

---

### Phase 3: SimCash Validation Integration

#### Test 3.1: Generated policies pass SimCash validation
```python
# tests/test_simcash_integration.py

def test_generated_policy_passes_simcash_validation():
    """Policies from dynamic model pass SimCash validation."""
    from payment_simulator.backends import validate_policy

    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency_threshold", 0, 20, 3, "Urgency"),
        ],
        allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity"],
        allowed_actions=["Release", "Hold"],
    )

    PolicyModel = create_constrained_policy_model(constraints)

    policy = PolicyModel(
        policy_id="test_policy",
        version="2.0",
        parameters={"urgency_threshold": 5.0},
        payment_tree={
            "type": "action",
            "action": "Release",
        },
    )

    # Convert to JSON and validate with SimCash
    policy_json = policy.model_dump_json()
    result = json.loads(validate_policy(policy_json))

    assert result["valid"] is True, f"SimCash validation failed: {result['errors']}"

def test_invalid_field_rejected_by_simcash():
    """Policies with invalid fields fail SimCash validation."""
    # This tests that our registry stays in sync with SimCash
    from payment_simulator.backends import validate_policy

    bad_policy = {
        "policy_id": "bad",
        "version": "2.0",
        "parameters": {},
        "payment_tree": {
            "type": "condition",
            "condition": {
                "op": ">=",
                "left": {"field": "invented_field_xyz"},  # Invalid!
                "right": {"value": 0},
            },
            "on_true": {"type": "action", "action": "Release"},
            "on_false": {"type": "action", "action": "Hold"},
        },
    }

    result = json.loads(validate_policy(json.dumps(bad_policy)))
    assert result["valid"] is False
    assert any("InvalidFieldReference" in str(e) for e in result["errors"])
```

#### Test 3.2: Parameter consistency validation
```python
def test_policy_model_ensures_param_consistency():
    """Referenced params must exist in parameters object."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("threshold", 0, 20, 5, "Threshold"),
        ],
        allowed_fields=["ticks_to_deadline"],
        allowed_actions=["Release", "Hold"],
    )

    PolicyModel = create_constrained_policy_model(constraints)

    # Should reject reference to undefined param
    with pytest.raises(ValidationError):
        PolicyModel(
            parameters={"threshold": 5.0},
            payment_tree={
                "type": "condition",
                "condition": {
                    "op": "<=",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"param": "undefined_param"},  # Not in allowed!
                },
                "on_true": {"type": "action", "action": "Release"},
                "on_false": {"type": "action", "action": "Hold"},
            },
        )
```

---

### Phase 4: Robust Policy Agent Integration

#### Test 4.1: Agent accepts constraints
```python
# tests/test_robust_policy_agent.py

def test_agent_accepts_scenario_constraints():
    """RobustPolicyAgent initializes with constraints."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency threshold"),
        ],
        allowed_fields=["balance", "ticks_to_deadline"],
        allowed_actions=["Release", "Hold"],
    )

    agent = RobustPolicyAgent(constraints=constraints)

    assert agent.constraints == constraints
    assert agent.policy_model is not None

def test_agent_uses_dynamic_model():
    """Agent's policy model reflects constraints."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("custom_param", 0, 100, 50, "Custom"),
        ],
        allowed_fields=["balance"],
        allowed_actions=["Release"],
    )

    agent = RobustPolicyAgent(constraints=constraints)

    # Model should accept custom_param
    schema = agent.policy_model.model_json_schema()
    assert "custom_param" in str(schema)
```

#### Test 4.2: Generated policies are valid (mocked LLM)
```python
@pytest.fixture
def mock_llm_response():
    """Mock LLM that returns valid policy structure."""
    # ... mock setup

def test_agent_generates_valid_policy(mock_llm_response):
    """Agent generates policies that pass validation."""
    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency"),
        ],
        allowed_fields=["ticks_to_deadline", "effective_liquidity"],
        allowed_actions=["Release", "Hold"],
    )

    agent = RobustPolicyAgent(constraints=constraints)
    policy = agent.generate_policy("Optimize for low delay")

    # Validate with SimCash
    from payment_simulator.backends import validate_policy
    result = json.loads(validate_policy(json.dumps(policy)))

    assert result["valid"] is True
```

#### Implementation 4: Update `generator/robust_policy_agent.py`
```python
class RobustPolicyAgent:
    def __init__(
        self,
        constraints: ScenarioConstraints,  # Required, no default
        model: str | None = None,
        retries: int = 3,
        reasoning_effort: Literal["low", "medium", "high"] = "high",
    ) -> None:
        self.constraints = constraints
        self.policy_model = create_constrained_policy_model(constraints)
        self.model = model or DEFAULT_MODEL
        # ... rest of init
```

---

### Phase 5: Pre-defined Parameter Sets

#### Test 5.1: Standard parameter sets exist
```python
# tests/test_parameter_sets.py

def test_minimal_params_is_valid():
    """MINIMAL_CONSTRAINTS is a valid ScenarioConstraints."""
    from experiments.castro.parameter_sets import MINIMAL_CONSTRAINTS

    assert isinstance(MINIMAL_CONSTRAINTS, ScenarioConstraints)
    assert len(MINIMAL_CONSTRAINTS.allowed_parameters) >= 1

def test_standard_params_is_valid():
    """STANDARD_CONSTRAINTS is a valid ScenarioConstraints."""
    from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS

    assert isinstance(STANDARD_CONSTRAINTS, ScenarioConstraints)
    assert len(STANDARD_CONSTRAINTS.allowed_parameters) >= 3

def test_full_params_is_valid():
    """FULL_CONSTRAINTS is a valid ScenarioConstraints."""
    from experiments.castro.parameter_sets import FULL_CONSTRAINTS

    assert isinstance(FULL_CONSTRAINTS, ScenarioConstraints)
    # Full should have more params than standard
    assert len(FULL_CONSTRAINTS.allowed_parameters) > len(STANDARD_CONSTRAINTS.allowed_parameters)

def test_all_param_sets_produce_valid_simcash_policies():
    """All pre-defined constraints produce SimCash-valid policies."""
    from experiments.castro.parameter_sets import (
        MINIMAL_CONSTRAINTS,
        STANDARD_CONSTRAINTS,
        FULL_CONSTRAINTS,
    )
    from payment_simulator.backends import validate_policy

    for name, constraints in [
        ("minimal", MINIMAL_CONSTRAINTS),
        ("standard", STANDARD_CONSTRAINTS),
        ("full", FULL_CONSTRAINTS),
    ]:
        PolicyModel = create_constrained_policy_model(constraints)

        # Create minimal valid policy
        policy = PolicyModel(
            policy_id=f"{name}_test",
            version="2.0",
            payment_tree={"type": "action", "action": "Release"},
        )

        result = json.loads(validate_policy(policy.model_dump_json()))
        assert result["valid"], f"{name} constraints produced invalid policy: {result['errors']}"
```

#### Implementation 5: `parameter_sets.py`
```python
from .parameter_config import ParameterSpec, ScenarioConstraints
from .registry import PAYMENT_TREE_FIELDS, PAYMENT_ACTIONS

# Minimal: Just urgency
MINIMAL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec("urgency_threshold", 0, 20, 3.0,
                     "Ticks before deadline when payment is urgent"),
    ],
    allowed_fields=["ticks_to_deadline", "effective_liquidity", "balance"],
    allowed_actions=["Release", "Hold"],
)

# Standard: Common policy parameters
STANDARD_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec("urgency_threshold", 0, 20, 3.0, "Urgency threshold"),
        ParameterSpec("liquidity_buffer", 0.5, 3.0, 1.0, "Buffer multiplier"),
        ParameterSpec("initial_collateral_fraction", 0, 1.0, 0.25, "Initial collateral"),
    ],
    allowed_fields=PAYMENT_TREE_FIELDS[:30],  # Common fields
    allowed_actions=["Release", "Hold", "Split"],
)

# Full: All SimCash capabilities
FULL_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        # ... comprehensive list
    ],
    allowed_fields=PAYMENT_TREE_FIELDS,  # All fields
    allowed_actions=PAYMENT_ACTIONS,  # All actions
)
```

---

## File Structure

```
experiments/castro/
├── schemas/
│   ├── parameter_config.py    # NEW: ParameterSpec, ScenarioConstraints
│   ├── dynamic.py             # NEW: Dynamic model generation
│   ├── registry.py            # KEEP: Field/action registry
│   ├── actions.py             # KEEP: Action definitions
│   ├── constrained.py         # DELETE: Replace with dynamic
│   └── ...
├── generator/
│   ├── robust_policy_agent.py # MODIFY: Use ScenarioConstraints
│   └── policy_agent.py        # DELETE: Old free-form agent
├── parameter_sets.py          # NEW: Pre-defined constraint sets
└── tests/
    ├── test_parameter_config.py    # NEW
    ├── test_dynamic_schema.py      # NEW
    ├── test_simcash_integration.py # NEW
    ├── test_robust_policy_agent.py # MODIFY
    └── test_parameter_sets.py      # NEW
```

---

## Implementation Order (TDD)

1. **Phase 1**: Parameter config (tests first, then implementation)
2. **Phase 2**: Dynamic model generation (tests first, then implementation)
3. **Phase 3**: SimCash validation integration tests
4. **Phase 4**: Update RobustPolicyAgent
5. **Phase 5**: Pre-defined parameter sets
6. **Cleanup**: Delete old constrained.py and policy_agent.py

---

## Success Criteria

- [ ] All new tests pass
- [ ] Generated policies pass `payment-sim validate-policy`
- [ ] RobustPolicyAgent works with arbitrary parameter sets
- [ ] No hardcoded parameter limitations remain
- [ ] Old implementations deleted
