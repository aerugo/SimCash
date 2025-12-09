# Feature Request: Inline Policy String Support

**Requested by:** Castro Experiments Team
**Priority:** High
**Date:** 2025-12-09

## Summary

Add a new `InlineJsonPolicy` schema type that accepts a raw JSON policy string. This enables dynamic policy injection from databases, LLM responses, and in-memory sources without file I/O.

## Problem

The current schema has no way to pass a JSON policy string directly:

```python
# Current: Only file path supported
class FromJsonPolicy(BaseModel):
    type: Literal["FromJson"] = "FromJson"
    json_path: str  # Must be a file path
```

This forces workarounds when policies come from non-file sources (databases, LLM output, API requests).

**Failing Tests:** 7 Castro experiment tests fail because `CastroSimulationRunner` cannot inject policies as JSON strings.

## Solution

Add a new `InlineJsonPolicy` type:

```python
class InlineJsonPolicy(BaseModel):
    """Policy from inline JSON string."""
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

Add FFI conversion:

```python
case InlineJsonPolicy(json_string=json_str):
    return {"type": "FromJson", "json": json_str}
```

## Usage

```python
# LLM-generated policy
agent["policy"] = {
    "type": "InlineJson",
    "json_string": llm_response.policy_json
}

# From database
policy_json = db.query("SELECT policy FROM policies WHERE id = ?", [id])
agent["policy"] = {"type": "InlineJson", "json_string": policy_json}

# Programmatic generation
agent["policy"] = {
    "type": "InlineJson",
    "json_string": json.dumps(generate_policy(threshold=5))
}
```

## Files to Modify

1. `api/payment_simulator/config/schemas.py`
   - Add `InlineJsonPolicy` class
   - Add to `PolicyConfig` union
   - Add case to `_policy_to_ffi_dict()`

2. `experiments/castro/castro/simulation.py`
   - Update `_build_config()` to use `InlineJson` type

## Acceptance Criteria

- [ ] `InlineJsonPolicy` schema type exists
- [ ] JSON string validation on input
- [ ] FFI conversion outputs `{"type": "FromJson", "json": ...}`
- [ ] All 7 failing Castro tests pass
- [ ] Unit tests for `InlineJsonPolicy`

---

# Separate Issue: Skipped Tests (29 tests)

## Root Cause

The 29 skipped tests fail due to a **working directory issue** in the Rust FFI, not a Python schema issue.

Built-in policies (`Fifo`, `Deadline`, etc.) load JSON files from `simulator/policies/`. The path resolution in `simulator/src/policy/tree/factory.rs` doesn't handle the `experiments/castro/` working directory:

```rust
fn policies_dir() -> PathBuf {
    let candidates = [
        PathBuf::from("simulator/policies"),    // From project root ✓
        PathBuf::from("policies"),              // From simulator/ ✓
        PathBuf::from("../simulator/policies"), // From api/ ✓
        // MISSING: "../../simulator/policies" for experiments/castro/
    ];
```

## Fix Required (Rust-side)

Add the missing path candidate in `simulator/src/policy/tree/factory.rs`:

```rust
fn policies_dir() -> PathBuf {
    let candidates = [
        PathBuf::from("simulator/policies"),
        PathBuf::from("policies"),
        PathBuf::from("../simulator/policies"),
        PathBuf::from("../../simulator/policies"),  // ADD: From experiments/castro/
    ];
```

## Alternative: Run Tests from Project Root

Configure Castro pytest to run from project root instead of `experiments/castro/`:

```toml
# experiments/castro/pyproject.toml
[tool.pytest.ini_options]
# ... existing config ...
rootdir = "../.."  # Run from project root
```

## Skipped Test Categories

| Test Class | Count | Issue |
|------------|-------|-------|
| `TestEventCaptureFromOrchestrator` | 3 | policies_dir() path |
| `TestEventFiltering` | 6 | policies_dir() path |
| `TestBestWorstSeedSelection` | 3 | policies_dir() path |
| `TestFilteredEventsForContext` | 3 | policies_dir() path |
| `TestVerboseOutputCapture` | 7 | policies_dir() path |
| `TestVerboseContextIntegration` | 5 | policies_dir() path |
| `TestLLMPromptContent` | 2 | policies_dir() path |

All 29 skipped tests would pass if run from project root or if `policies_dir()` is fixed.
