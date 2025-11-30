# validate-policy

Validate a policy tree JSON file.

## Synopsis

```bash
payment-sim validate-policy POLICY_FILE [OPTIONS]
```

## Description

The `validate-policy` command performs comprehensive validation of policy tree JSON files. It validates policies through multiple stages:

1. **JSON Syntax Validation** - Catches malformed JSON
2. **Schema Validation** - Verifies required fields are present
3. **Semantic Validation** - Deep validation via the Rust backend:
   - Node ID uniqueness across all trees
   - Tree depth limits (max 100)
   - Field reference validity
   - Parameter reference validity
   - Division-by-zero safety analysis
   - Action reachability

This command is useful for:

- Validating custom policies before using them in simulations
- CI/CD pipelines to catch policy errors early
- Debugging policy syntax and semantic issues
- Running functional tests to verify policy behavior

## Arguments

| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `POLICY_FILE` | Path | Yes | Path to the policy JSON file to validate |

## Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--format` | `-f` | Enum | `text` | Output format: `text` or `json` |
| `--verbose` | `-v` | Boolean | `false` | Show detailed validation output |
| `--functional-tests` | - | Boolean | `false` | Run functional tests against the policy |
| `--scenario` | `-s` | Path | None | Validate against scenario's feature toggles and use for functional tests |

## Validation Stages

### Stage 1: JSON Syntax

Parses the JSON file and catches syntax errors:

```bash
# Invalid JSON
$ payment-sim validate-policy invalid.json
┌──────────────────────────────────────────────────────────────────────────────┐
│ Type       │ Message                                                         │
├────────────┼─────────────────────────────────────────────────────────────────┤
│ ParseError │ JSON parsing failed: expected `:` at line 5 column 1            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Stage 2: Schema Validation

Verifies required fields are present:

```bash
# Missing policy_id
$ payment-sim validate-policy missing_id.json
┌──────────────────────────────────────────────────────────────────────────────┐
│ Type       │ Message                                                         │
├────────────┼─────────────────────────────────────────────────────────────────┤
│ ParseError │ JSON parsing failed: missing field `policy_id` at line 1        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Stage 3: Semantic Validation

Deep validation of policy structure and references:

| Validation | Description | Error Type |
|------------|-------------|------------|
| Node ID Uniqueness | All node_ids must be unique across trees | `DuplicateNodeId` |
| Tree Depth | Maximum depth of 100 levels | `ExcessiveDepth` |
| Field References | All field references must be valid | `InvalidFieldReference` |
| Parameter References | All parameters must be defined | `InvalidParameterReference` |
| Division Safety | Static check for division by zero | `DivisionByZeroRisk` |
| Action Reachability | All actions must be reachable | `UnreachableAction` |

### Stage 4: Scenario Feature Toggle Validation

When `--scenario` is provided, the command also validates that the policy doesn't use categories forbidden by the scenario's `policy_feature_toggles`:

```yaml
# scenario.yaml
policy_feature_toggles:
  exclude:
    - CollateralAction      # Policies cannot use collateral actions
    - StateRegisterField    # No custom state registers allowed
```

The validation extracts all categories used by the policy (actions, fields, operators) and checks them against the scenario's allowed categories. If a forbidden category is used, the validation fails with details about which elements are forbidden.

See [Feature Toggles](../../scenario/feature-toggles.md) for complete documentation.

## Functional Tests

When `--functional-tests` is specified, the command runs additional runtime tests:

| Test | Description |
|------|-------------|
| `load_policy` | Policy can be loaded by the orchestrator |
| `execute_policy` | Policy executes for 5 ticks without errors |
| `valid_state` | Policy produces valid simulation state |

Functional tests create a minimal simulation with:
- 2 agents (BANK_A, BANK_B)
- 10 ticks per day
- 1 sample transaction

## Examples

### Basic Validation

```bash
# Validate a policy file
payment-sim validate-policy policies/fifo.json

# Output on success:
╭───────────────────────────── Validation Result ──────────────────────────────╮
│ Policy validation passed                                                     │
│                                                                              │
│ File: policies/fifo.json                                                     │
│ Policy ID: fifo_policy                                                       │
│ Version: 1.0                                                                 │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### Verbose Output

```bash
# Show detailed policy information
payment-sim validate-policy policies/sophisticated.json --verbose

# Output:
╭───────────────────────────── Validation Result ──────────────────────────────╮
│ Policy validation passed                                                     │
│                                                                              │
│ File: policies/sophisticated.json                                            │
│ Policy ID: sophisticated_policy                                              │
│ Version: 1.0                                                                 │
╰──────────────────────────────────────────────────────────────────────────────╯
              Policy Trees
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Tree Type                   ┃ Present ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
│ payment_tree                │ Yes     │
│ bank_tree                   │ Yes     │
│ strategic_collateral_tree   │ Yes     │
│ end_of_tick_collateral_tree │ No      │
└─────────────────────────────┴─────────┘

Parameters (3): threshold, urgency_factor, max_splits

Description: A sophisticated policy with multiple decision trees...
```

### JSON Output

```bash
# Machine-readable output for CI/CD
payment-sim validate-policy policies/custom.json --format json

# Success output:
{
  "valid": true,
  "policy_id": "custom_policy",
  "version": "1.0",
  "description": "Custom policy",
  "trees": {
    "has_payment_tree": true,
    "has_bank_tree": false,
    "has_strategic_collateral_tree": false,
    "has_end_of_tick_collateral_tree": false,
    "parameter_count": 2,
    "parameters": ["threshold", "buffer"]
  }
}

# Error output:
{
  "valid": false,
  "errors": [
    {
      "type": "DuplicateNodeId",
      "message": "Duplicate node ID: A1"
    }
  ]
}
```

### Functional Tests

```bash
# Run functional tests
payment-sim validate-policy policies/fifo.json --functional-tests

# Output:
╭───────────────────────────── Validation Result ──────────────────────────────╮
│ Policy validation passed                                                     │
╰──────────────────────────────────────────────────────────────────────────────╯
                            Functional Tests
┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Test           ┃ Status ┃ Message                                    ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ load_policy    │ PASS   │ Policy loaded successfully by orchestrator │
│ execute_policy │ PASS   │ Policy executed for 5 ticks without errors │
│ valid_state    │ PASS   │ Policy produces valid simulation state     │
└────────────────┴────────┴────────────────────────────────────────────┘

All functional tests passed (3/3)
```

### Scenario Feature Toggle Validation

```bash
# Validate policy against scenario feature toggles
payment-sim validate-policy policies/custom.json --scenario scenario.yaml

# Output when policy uses forbidden categories:
                              Validation Errors
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Type                       ┃ Message                                                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ForbiddenCategory          │ Policy uses forbidden category 'CollateralAction'        │
└────────────────────────────┴──────────────────────────────────────────────────────────┘

Forbidden categories used: CollateralAction

Policy validation failed with 1 error(s)
```

```bash
# JSON output shows detailed forbidden elements
payment-sim validate-policy policies/collateral.json --scenario restricted.yaml --format json

# Output:
{
  "valid": false,
  "policy_id": "collateral_policy",
  "version": "1.0",
  "errors": [
    {
      "type": "ForbiddenCategory",
      "message": "Policy uses forbidden category 'CollateralAction'"
    }
  ],
  "forbidden_categories": ["CollateralAction"],
  "forbidden_elements": [
    {"element": "PostCollateral", "category": "CollateralAction"}
  ]
}
```

### Validation Errors

```bash
# Duplicate node ID
payment-sim validate-policy bad_policy.json

# Output:
                               Validation Errors
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Type              ┃ Message                                                  ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ DuplicateNodeId   │ Duplicate node ID: A1                                    │
└───────────────────┴──────────────────────────────────────────────────────────┘

Policy validation failed with 1 error(s)
```

### CI/CD Integration

```bash
#!/bin/bash
# Validate all policies in a directory

for policy in policies/*.json; do
    echo "Validating $policy..."
    if ! payment-sim validate-policy "$policy" --format json > /dev/null 2>&1; then
        echo "FAILED: $policy"
        payment-sim validate-policy "$policy"
        exit 1
    fi
done

echo "All policies valid!"
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Validation passed |
| 1 | Validation failed (syntax, schema, or semantic errors) |
| 1 | Functional tests failed (if `--functional-tests` specified) |
| 1 | File not found or read error |

## Error Types

| Error Type | Description | How to Fix |
|------------|-------------|------------|
| `ParseError` | JSON syntax or schema error | Check JSON syntax, ensure required fields present |
| `DuplicateNodeId` | Two nodes have same ID | Use unique node_id values |
| `ExcessiveDepth` | Tree exceeds 100 levels | Simplify tree structure |
| `InvalidFieldReference` | Unknown field name | Check available fields in policy schema |
| `InvalidParameterReference` | Parameter not defined | Add parameter to `parameters` section |
| `DivisionByZeroRisk` | Division by literal zero | Use SafeDiv or check divisor |
| `UnreachableAction` | Action node never reached | Fix condition logic |
| `ForbiddenCategory` | Policy uses category forbidden by scenario | Remove elements from forbidden category or update scenario toggles |

## Related Commands

- [`policy-schema`](policy-schema.md) - Generate policy schema documentation
- [`run`](run.md) - Run simulations with policies

## Related Documentation

- [Policy Reference](../../policy/index.md) - Complete policy DSL documentation
- [Feature Toggles](../../scenario/feature-toggles.md) - Scenario feature toggle configuration
- [Policy Validation](../../policy/validation.md) - Validation rules in detail

## Implementation Details

**File**: `api/payment_simulator/cli/commands/validate_policy.py`

The validation is performed by the Rust backend via the `validate_policy()` FFI function, which uses the same validation logic as the orchestrator when loading policies.
