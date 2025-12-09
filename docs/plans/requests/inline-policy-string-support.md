# Feature Request: Inline Policy String Support for Schema Validation

**Requested by:** Castro Experiments Team
**Priority:** High
**Date:** 2025-12-09

## Summary

Extend the policy configuration schema to support inline JSON policy strings alongside file paths. This enables dynamic policy injection from databases, in-memory dictionaries, and LLM-generated policies without requiring intermediate file I/O.

## Problem Statement

### Current Behavior

The `FromJsonPolicy` schema only accepts a file path:

```python
# schemas.py line 425-428
class FromJsonPolicy(BaseModel):
    type: Literal["FromJson"] = "FromJson"
    json_path: str = Field(..., description="Path to JSON policy file")
```

However, the FFI layer accepts both formats:
- `{"type": "FromJson", "json_path": "path/to/file.json"}` - Load from file
- `{"type": "FromJson", "json": "<inline JSON string>"}` - Use inline JSON

### Impact

This mismatch causes **7 failing tests** in Castro experiments:

```
tests/test_verbose_output.py::test_inline_policy_to_from_json FAILED
tests/test_verbose_output.py::test_inline_policy_integration_with_orchestrator FAILED
tests/test_verbose_output.py::test_inline_policy_type_preserved_through_json FAILED
tests/test_verbose_output.py::test_verbose_capture_filters_agent_specific_events FAILED
tests/test_verbose_output.py::test_verbose_output_available_per_seed FAILED
tests/test_verbose_context_integration.py::test_verbose_context_has_expected_structure FAILED
tests/test_verbose_context_integration.py::test_verbose_context_includes_simulation_events FAILED
```

**Root Cause**: `CastroSimulationRunner._build_config()` creates:
```python
agent["policy"] = {"type": "FromJson", "json": json.dumps(policy)}
```

When `SimulationConfig.from_dict()` validates this, Pydantic rejects it because `FromJsonPolicy` expects `json_path`, not `json`.

### Workaround Available But Suboptimal

The current workaround is to use `InlinePolicy`:
```python
agent["policy"] = {"type": "Inline", "decision_trees": policy}
```

This works but:
1. Requires the policy to be a dict, not a JSON string
2. Doesn't support policies that are already serialized as JSON strings
3. Adds unnecessary serialization/deserialization overhead

## Requirements

### Must Have

1. **Inline JSON string support** - Accept raw JSON policy strings directly in configuration
2. **Backward compatibility** - Existing `json_path` usage must continue to work
3. **Database/API integration** - Enable loading policies from databases or REST APIs
4. **Validation** - JSON string must be validated as proper policy DSL before FFI

### Nice to Have

1. **Policy source abstraction** - Unified interface for file, string, database, and dict sources
2. **Lazy loading** - Don't parse JSON until needed (for large policy stores)

## Proposed Solution

### Option A: Extend FromJsonPolicy (Recommended)

Add `json_string` as an alternative to `json_path`:

```python
class FromJsonPolicy(BaseModel):
    """Policy loaded from JSON file or inline JSON string."""
    type: Literal["FromJson"] = "FromJson"
    json_path: str | None = Field(None, description="Path to JSON policy file")
    json_string: str | None = Field(None, description="Inline JSON policy string")

    @model_validator(mode="after")
    def validate_exactly_one_source(self) -> "FromJsonPolicy":
        """Ensure exactly one of json_path or json_string is provided."""
        if self.json_path is None and self.json_string is None:
            raise ValueError("Either json_path or json_string must be provided")
        if self.json_path is not None and self.json_string is not None:
            raise ValueError("Cannot specify both json_path and json_string")
        return self
```

Update `_policy_to_ffi_dict()`:

```python
case FromJsonPolicy(json_path=path_str, json_string=json_str):
    if json_str is not None:
        # Validate JSON is parseable
        try:
            json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in json_string: {e}") from e
        return {"type": "FromJson", "json": json_str}
    else:
        return self._load_json_policy(path_str)
```

### Option B: New InlineJsonPolicy Type

Create a dedicated type for inline JSON strings:

```python
class InlineJsonPolicy(BaseModel):
    """Policy from inline JSON string (for database/API integration)."""
    type: Literal["InlineJson"] = "InlineJson"
    json_string: str = Field(..., description="JSON policy string")

    @field_validator("json_string")
    @classmethod
    def validate_json(cls, v: str) -> str:
        """Validate JSON is parseable."""
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        return v
```

Update `PolicyConfig` union:

```python
PolicyConfig = (
    FifoPolicy
    | DeadlinePolicy
    | LiquidityAwarePolicy
    | LiquiditySplittingPolicy
    | MockSplittingPolicy
    | FromJsonPolicy
    | InlinePolicy
    | InlineJsonPolicy  # NEW
)
```

### Option C: Policy Source Abstraction (Future Enhancement)

Create a unified policy loading interface:

```python
from abc import ABC, abstractmethod
from typing import Protocol

class PolicySource(Protocol):
    """Protocol for policy sources."""
    def load(self) -> dict[str, Any]:
        """Load and return policy dict."""
        ...

class FilePolicySource:
    """Load policy from file."""
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text())

class StringPolicySource:
    """Load policy from JSON string."""
    def __init__(self, json_string: str) -> None:
        self.json_string = json_string

    def load(self) -> dict[str, Any]:
        return json.loads(self.json_string)

class DatabasePolicySource:
    """Load policy from database."""
    def __init__(self, db_conn: Any, policy_id: str) -> None:
        self.db_conn = db_conn
        self.policy_id = policy_id

    def load(self) -> dict[str, Any]:
        row = self.db_conn.execute(
            "SELECT policy_json FROM policies WHERE id = ?",
            [self.policy_id]
        ).fetchone()
        return json.loads(row[0])
```

## Use Cases

### 1. Castro LLM Policy Optimization

```python
# Current (broken)
agent["policy"] = {"type": "FromJson", "json": json.dumps(llm_policy)}

# With Option A
agent["policy"] = {"type": "FromJson", "json_string": json.dumps(llm_policy)}

# With Option B
agent["policy"] = {"type": "InlineJson", "json_string": json.dumps(llm_policy)}
```

### 2. Database Policy Store

```python
# Load policy from database
policy_json = db.execute(
    "SELECT policy_json FROM agent_policies WHERE agent_id = ?",
    [agent_id]
).fetchone()[0]

# Inject into config
agent["policy"] = {"type": "FromJson", "json_string": policy_json}
```

### 3. REST API Policy Injection

```python
# Receive policy from API request
@app.post("/simulations")
async def create_simulation(request: SimulationRequest):
    config = base_config.copy()
    for agent in config["agents"]:
        agent["policy"] = {
            "type": "FromJson",
            "json_string": request.policy_json
        }
    return run_simulation(config)
```

### 4. Parameter Sweep Experiments

```python
# Generate policies programmatically
for threshold in range(1, 10):
    policy = generate_policy(urgency_threshold=threshold)
    config["agents"][0]["policy"] = {
        "type": "FromJson",
        "json_string": json.dumps(policy)
    }
    results.append(run_simulation(config))
```

## Migration Impact

### Backward Compatibility

- Existing `json_path` usage continues to work unchanged
- No changes to FFI layer (already supports both formats)
- No database migrations required

### Code Changes

| File | Change |
|------|--------|
| `api/payment_simulator/config/schemas.py` | Add `json_string` field to `FromJsonPolicy` |
| `api/payment_simulator/config/schemas.py` | Update `_policy_to_ffi_dict()` |
| `experiments/castro/castro/simulation.py` | Update to use new field name |

## Acceptance Criteria

- [ ] `FromJsonPolicy` accepts either `json_path` or `json_string`
- [ ] Validation ensures exactly one is provided
- [ ] `json_string` content is validated as parseable JSON
- [ ] FFI conversion works correctly for both source types
- [ ] All 7 failing Castro tests pass
- [ ] Existing `json_path` tests continue to pass
- [ ] Unit tests for new `json_string` functionality
- [ ] Documentation updated with examples

## Test Plan

### Unit Tests

```python
def test_from_json_policy_with_json_string():
    """FromJsonPolicy accepts json_string."""
    policy = FromJsonPolicy(
        type="FromJson",
        json_string='{"version": "2.0", "parameters": {}}'
    )
    assert policy.json_string is not None
    assert policy.json_path is None

def test_from_json_policy_with_json_path():
    """FromJsonPolicy still accepts json_path."""
    policy = FromJsonPolicy(
        type="FromJson",
        json_path="policies/seed_policy.json"
    )
    assert policy.json_path is not None
    assert policy.json_string is None

def test_from_json_policy_requires_one_source():
    """FromJsonPolicy requires exactly one source."""
    with pytest.raises(ValidationError):
        FromJsonPolicy(type="FromJson")  # Neither provided

    with pytest.raises(ValidationError):
        FromJsonPolicy(
            type="FromJson",
            json_path="path.json",
            json_string='{"key": "value"}'
        )  # Both provided

def test_from_json_policy_validates_json_string():
    """json_string must be valid JSON."""
    with pytest.raises(ValidationError):
        FromJsonPolicy(
            type="FromJson",
            json_string="not valid json {"
        )
```

### Integration Tests

```python
def test_simulation_config_with_inline_json_string():
    """SimulationConfig accepts inline JSON string policy."""
    config_dict = {
        "simulation": {"ticks_per_day": 10, "num_days": 1, "rng_seed": 42},
        "agents": [{
            "id": "BANK_A",
            "opening_balance": 100000,
            "unsecured_cap": 50000,
            "policy": {
                "type": "FromJson",
                "json_string": json.dumps({
                    "version": "2.0",
                    "parameters": {"urgency_threshold": 3},
                    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"}
                })
            }
        }]
    }

    config = SimulationConfig.from_dict(config_dict)
    ffi_dict = config.to_ffi_dict()

    assert ffi_dict["agent_configs"][0]["policy"]["type"] == "FromJson"
    assert "json" in ffi_dict["agent_configs"][0]["policy"]
```

## Recommendation

**Implement Option A** (extend `FromJsonPolicy`) because:

1. **Minimal change** - Single field addition with validator
2. **Semantic clarity** - `FromJson` already implies "from JSON source"
3. **No new union members** - Avoids complicating `PolicyConfig` type
4. **FFI alignment** - Matches existing FFI format exactly

## Files to Modify

1. `api/payment_simulator/config/schemas.py`
   - Add `json_string` field to `FromJsonPolicy`
   - Add model validator for mutual exclusivity
   - Update `_policy_to_ffi_dict()` to handle `json_string`

2. `experiments/castro/castro/simulation.py`
   - Update `_build_config()` to use `json_string` field

3. `api/tests/unit/test_config_schemas.py`
   - Add tests for new `json_string` functionality

4. `api/payment_simulator/config/__init__.py`
   - No changes needed (exports unchanged)
