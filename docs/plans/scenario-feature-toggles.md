# Scenario Feature Toggles Implementation Plan

> Enabling/disabling policy features per scenario configuration

## Overview

This feature allows scenario authors to control which policy DSL features are available in a given scenario. By specifying an `include` or `exclude` list of schema categories in the scenario config, policies can be restricted to a subset of the full policy DSL.

### Use Cases

1. **Simplified Scenarios**: Research scenarios that only allow basic payment actions
2. **Feature-Gated Experiments**: Testing policies with/without collateral actions
3. **Compliance Testing**: Ensuring policies don't use advanced features
4. **Educational**: Gradually introducing policy features to learners

## Requirements

### R1: Scenario Configuration

Add a new `policy_feature_toggles` section to the scenario configuration schema that allows either:
- An `include` list of categories (only these are allowed)
- An `exclude` list of categories (all except these are allowed)

**Constraint**: A valid scenario can only have an `include` OR an `exclude` list, not both.

### R2: Policy Validation Function

Create a core validation function:
```python
def validate_policy_for_scenario(
    policy_json: str,
    scenario_path: Path | None = None,
    scenario_config: SimulationConfig | None = None,
) -> PolicyValidationResult
```

The function:
1. Validates the policy JSON compiles (uses existing Rust validator)
2. If scenario provided, checks policy doesn't use forbidden categories
3. Returns structured result with success/failure and error details

### R3: CLI Command `validate-policy --scenario`

Update the existing `validate-policy` command to accept an optional `--scenario` flag:
```bash
payment-sim validate-policy policy.json --scenario scenario.yaml
```

When provided:
- Validates policy against scenario's feature toggles
- Reports which categories/elements are forbidden if validation fails

### R4: CLI Command `policy-schema --scenario`

Add a `--scenario` flag to the existing `policy-schema` command:
```bash
payment-sim policy-schema --scenario scenario.yaml
```

When provided:
- Outputs the schema filtered by the scenario's include/exclude toggles
- Works with all existing format options (json, markdown)

## Implementation Plan (TDD)

### Phase 1: Schema Definition

#### 1.1 Write Tests for PolicyFeatureToggles Schema

**File**: `api/tests/unit/config/test_policy_feature_toggles.py`

```python
def test_include_list_valid():
    """Include list with valid categories parses correctly."""

def test_exclude_list_valid():
    """Exclude list with valid categories parses correctly."""

def test_include_and_exclude_mutual_exclusion():
    """Cannot have both include and exclude lists."""

def test_empty_toggles_is_valid():
    """No toggles means all features allowed."""

def test_invalid_category_rejected():
    """Unknown category names are rejected."""
```

#### 1.2 Implement PolicyFeatureToggles Schema

**File**: `api/payment_simulator/config/schemas.py`

Add new Pydantic models:

```python
class PolicyFeatureToggles(BaseModel):
    """Feature toggles for policy DSL in this scenario.

    Allows restricting which policy features are available.
    Only ONE of include or exclude can be specified.
    """
    include: list[str] | None = Field(
        None,
        description="Only allow these categories (mutually exclusive with exclude)"
    )
    exclude: list[str] | None = Field(
        None,
        description="Forbid these categories (mutually exclusive with include)"
    )

    @model_validator(mode="after")
    def validate_mutual_exclusion(self) -> PolicyFeatureToggles:
        """Ensure include and exclude are mutually exclusive."""
        if self.include is not None and self.exclude is not None:
            raise ValueError("Cannot specify both 'include' and 'exclude' - choose one")
        return self

    @field_validator("include", "exclude", mode="before")
    @classmethod
    def validate_categories(cls, v: list[str] | None) -> list[str] | None:
        """Validate that all category names are valid."""
        if v is None:
            return v
        valid_categories = get_valid_category_names()  # From policy schema
        for cat in v:
            if cat not in valid_categories:
                raise ValueError(f"Unknown category: {cat}. Valid: {valid_categories}")
        return v
```

Add to `SimulationConfig`:

```python
class SimulationConfig(BaseModel):
    # ... existing fields ...
    policy_feature_toggles: PolicyFeatureToggles | None = Field(
        None,
        description="Restrict policy DSL features for this scenario"
    )
```

### Phase 2: Core Validation Function

#### 2.1 Write Tests for Policy-Scenario Validation

**File**: `api/tests/unit/cli/test_policy_scenario_validation.py`

```python
def test_policy_valid_without_toggles():
    """Policy validates when no toggles specified."""

def test_policy_valid_with_allowed_categories():
    """Policy using only allowed categories passes."""

def test_policy_invalid_with_forbidden_category():
    """Policy using forbidden category fails with clear error."""

def test_policy_invalid_include_list():
    """Policy using category NOT in include list fails."""

def test_policy_invalid_exclude_list():
    """Policy using category IN exclude list fails."""

def test_validation_result_includes_forbidden_elements():
    """Error message identifies specific forbidden elements."""

def test_rust_validation_errors_returned():
    """Rust-level validation errors are returned properly."""
```

#### 2.2 Implement Policy Category Extraction

**File**: `api/payment_simulator/policy/analysis.py` (new file)

```python
"""Policy analysis utilities for extracting categories used by a policy."""

def extract_categories_from_policy(policy_json: str) -> set[str]:
    """Extract all schema categories used by a policy.

    Parses the policy JSON and identifies which categories
    (PaymentAction, CollateralAction, etc.) are used.

    Returns:
        Set of category names used in the policy.
    """
```

Implementation approach:
1. Parse policy JSON
2. Walk the tree structure
3. For each action, expression, computation, field reference:
   - Look up its category from the policy schema
4. Return set of all categories found

#### 2.3 Implement Validation Function

**File**: `api/payment_simulator/policy/validation.py` (new file)

```python
"""Policy validation with scenario feature toggle support."""

from dataclasses import dataclass

@dataclass
class PolicyValidationResult:
    """Result of policy validation."""
    valid: bool
    policy_id: str | None = None
    version: str | None = None
    description: str | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    forbidden_categories: list[str] = field(default_factory=list)
    forbidden_elements: list[str] = field(default_factory=list)

def validate_policy_for_scenario(
    policy_json: str,
    scenario_path: Path | None = None,
    scenario_config: SimulationConfig | None = None,
) -> PolicyValidationResult:
    """Validate a policy against scenario feature toggles.

    Args:
        policy_json: The policy JSON content
        scenario_path: Path to scenario YAML (will be loaded)
        scenario_config: Pre-loaded scenario config (takes precedence)

    Returns:
        PolicyValidationResult with validation outcome.

    Note:
        If neither scenario_path nor scenario_config provided,
        only performs base policy validation (no toggle checks).
    """
```

### Phase 3: CLI Integration

#### 3.1 Write Tests for validate-policy --scenario

**File**: `api/tests/integration/cli/test_validate_policy_scenario.py`

```python
def test_validate_policy_with_valid_scenario():
    """Policy valid when scenario allows all used categories."""

def test_validate_policy_with_forbidden_category():
    """Clear error when policy uses forbidden category."""

def test_validate_policy_json_output_with_scenario():
    """JSON output includes scenario validation details."""

def test_validate_policy_text_output_with_scenario():
    """Text output shows forbidden categories nicely."""

def test_validate_policy_exit_code_on_forbidden():
    """Exit code 1 when policy uses forbidden category."""
```

#### 3.2 Update validate-policy Command

**File**: `api/payment_simulator/cli/commands/validate_policy.py`

Add scenario-aware validation:

```python
def validate_policy(
    policy_file: Annotated[Path, ...],
    format: Annotated[OutputFormat, ...] = OutputFormat.text,
    verbose: Annotated[bool, ...] = False,
    functional_tests: Annotated[bool, ...] = False,
    scenario: Annotated[
        Path | None,
        typer.Option(
            "--scenario", "-s",
            help="Validate policy against scenario's feature toggles"
        ),
    ] = None,
) -> None:
    """Validate a policy tree JSON file.

    When --scenario is provided, also validates that the policy
    only uses features allowed by the scenario's policy_feature_toggles.
    """
```

### Phase 4: policy-schema --scenario

#### 4.1 Write Tests for policy-schema --scenario

**File**: `api/tests/integration/cli/test_policy_schema_scenario.py`

```python
def test_policy_schema_with_scenario_include():
    """Schema filtered to scenario's include list."""

def test_policy_schema_with_scenario_exclude():
    """Schema excludes scenario's exclude list."""

def test_policy_schema_scenario_with_json_format():
    """JSON output respects scenario toggles."""

def test_policy_schema_scenario_with_markdown_format():
    """Markdown output respects scenario toggles."""

def test_policy_schema_scenario_combined_with_category():
    """Scenario toggles combine with --category filter."""
```

#### 4.2 Update policy-schema Command

**File**: `api/payment_simulator/cli/commands/policy_schema.py`

Add scenario support:

```python
def policy_schema(
    format: Annotated[OutputFormat, ...] = OutputFormat.markdown,
    category: Annotated[list[SchemaCategory] | None, ...] = None,
    exclude_category: Annotated[list[SchemaCategory] | None, ...] = None,
    tree: Annotated[list[TreeType] | None, ...] = None,
    section: Annotated[list[SchemaSection] | None, ...] = None,
    scenario: Annotated[
        Path | None,
        typer.Option(
            "--scenario",
            help="Filter schema based on scenario's feature toggles"
        ),
    ] = None,
    output: Annotated[Path | None, ...] = None,
    no_examples: Annotated[bool, ...] = False,
    compact: Annotated[bool, ...] = False,
) -> None:
    """Generate policy schema documentation.

    When --scenario is provided, filters the schema based on
    the scenario's policy_feature_toggles (include/exclude lists).
    """
```

### Phase 5: Integration Testing

#### 5.1 End-to-End Tests

**File**: `api/tests/e2e/test_scenario_feature_toggles.py`

```python
def test_run_simulation_with_forbidden_policy_rejected():
    """payment-sim run fails if policy uses forbidden features."""

def test_run_simulation_with_allowed_policy_succeeds():
    """payment-sim run succeeds with compliant policy."""

def test_fromjson_policy_validated_against_scenario():
    """FromJson policies are validated against scenario toggles."""
```

#### 5.2 Update run Command Validation

**File**: `api/payment_simulator/cli/commands/run.py`

Add validation during simulation setup:

```python
# In run_simulation(), after loading config:
if config.policy_feature_toggles:
    for agent in config.agents:
        if isinstance(agent.policy, FromJsonPolicy):
            result = validate_policy_for_scenario(
                policy_json=load_policy_json(agent.policy.json_path),
                scenario_config=config,
            )
            if not result.valid:
                console.print(f"[red]Policy validation failed for {agent.id}:[/red]")
                for error in result.errors:
                    console.print(f"  {error}")
                raise typer.Exit(code=1)
```

### Phase 6: Documentation

#### 6.1 Update docs/reference/scenario/index.md

Add `policy_feature_toggles` to the Configuration Hierarchy section.

#### 6.2 Create docs/reference/scenario/feature-toggles.md (new file)

```markdown
# Policy Feature Toggles

> Restrict which policy DSL features are available in a scenario

## Overview

Scenario authors can control which policy features are available...

## Configuration

### Include List

Only allow specific categories:

```yaml
policy_feature_toggles:
  include:
    - PaymentAction
    - TransactionField
    - AgentField
```

### Exclude List

Allow all except specific categories:

```yaml
policy_feature_toggles:
  exclude:
    - CollateralAction
    - CollateralField
```

## Available Categories

| Category | Description |
|----------|-------------|
| PaymentAction | submit, hold, drop, split, reprioritize |
| CollateralAction | post_collateral, withdraw_collateral |
| ... | ... |

## CLI Integration

### Validating Policies

```bash
# Validate policy against scenario's feature toggles
payment-sim validate-policy policy.json --scenario scenario.yaml
```

### Viewing Allowed Schema

```bash
# Show schema filtered by scenario's toggles
payment-sim policy-schema --scenario scenario.yaml
```

## Examples

### Research Scenario (Simple Policies Only)

```yaml
simulation:
  ticks_per_day: 100
  num_days: 10
  rng_seed: 42

policy_feature_toggles:
  include:
    - PaymentAction
    - TransactionField
    - TimeField

agents:
  - id: BANK_A
    # ...
```

### Production Scenario (No Experimental Features)

```yaml
policy_feature_toggles:
  exclude:
    - StateRegisterField
    - DerivedField
```
```

#### 6.3 Update docs/reference/cli/commands/validate-policy.md

Add documentation for `--scenario` flag.

#### 6.4 Update docs/reference/cli/commands/policy-schema.md

Add documentation for `--scenario` flag.

## File Changes Summary

### New Files

| File | Description |
|------|-------------|
| `api/payment_simulator/policy/__init__.py` | Package init |
| `api/payment_simulator/policy/analysis.py` | Policy category extraction |
| `api/payment_simulator/policy/validation.py` | Scenario-aware validation |
| `api/tests/unit/config/test_policy_feature_toggles.py` | Schema unit tests |
| `api/tests/unit/cli/test_policy_scenario_validation.py` | Validation unit tests |
| `api/tests/integration/cli/test_validate_policy_scenario.py` | CLI integration tests |
| `api/tests/integration/cli/test_policy_schema_scenario.py` | Schema CLI tests |
| `api/tests/e2e/test_scenario_feature_toggles.py` | E2E tests |
| `docs/reference/scenario/feature-toggles.md` | Feature documentation |

### Modified Files

| File | Changes |
|------|---------|
| `api/payment_simulator/config/schemas.py` | Add PolicyFeatureToggles model |
| `api/payment_simulator/cli/commands/validate_policy.py` | Add --scenario flag |
| `api/payment_simulator/cli/commands/policy_schema.py` | Add --scenario flag |
| `api/payment_simulator/cli/commands/run.py` | Add toggle validation |
| `docs/reference/scenario/index.md` | Add feature toggles section |
| `docs/reference/cli/commands/validate-policy.md` | Document --scenario |
| `docs/reference/cli/commands/policy-schema.md` | Document --scenario |

## Implementation Order (TDD)

1. **Schema Tests** → Schema Implementation
2. **Category Extraction Tests** → Category Extraction
3. **Validation Function Tests** → Validation Function
4. **validate-policy CLI Tests** → validate-policy Changes
5. **policy-schema CLI Tests** → policy-schema Changes
6. **E2E Tests** → run Command Validation
7. **Documentation**

## Success Criteria

- [ ] All tests pass
- [ ] `payment-sim validate-policy --scenario` works as documented
- [ ] `payment-sim policy-schema --scenario` works as documented
- [ ] `payment-sim run` rejects policies with forbidden features
- [ ] Documentation complete and accurate
- [ ] No regressions in existing functionality

## Open Questions

1. **Should we validate built-in policies too?** Built-in policies (Fifo, Deadline, etc.) don't use the policy DSL, so toggles don't apply to them. Document this clearly.

2. **What about nested policies?** If a policy references another policy file, should we validate transitively? Initial answer: No, each policy file is validated independently.

3. **Category granularity**: The current categories may be too coarse. Should we support element-level toggles (e.g., `actions.submit` vs `actions.drop`)? Initial answer: No, start with categories, add granularity later if needed.

---

*Created: 2025-11-30*
*Status: Ready for Implementation*
