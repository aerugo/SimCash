# Self-Documenting Cost Types Plan

**Status:** Implemented
**Created:** 2025-12-12
**Last Updated:** 2025-12-12
**Implemented:** 2025-12-12

## Implementation Summary

This plan has been fully implemented. The following components are now available:

### Rust Infrastructure
- `simulator/src/costs/mod.rs` - Module entry point with re-exports
- `simulator/src/costs/rates.rs` - CostRates, PriorityDelayMultipliers, PriorityBand
- `simulator/src/costs/schema_docs.rs` - CostSchemaDocumented trait and implementation
- FFI export `get_cost_schema()` in `lib.rs`

### Python CLI
- `api/payment_simulator/cli/commands/cost_schema.py` - CLI command implementation
- Command registered as `payment-sim cost-schema`

### Tests
- Rust: `simulator/src/costs/schema_docs.rs` (21 tests)
- Rust: `simulator/src/costs/rates.rs` (3 tests)
- Python FFI: `api/tests/unit/test_cost_schema_ffi.py` (13 tests)
- Python CLI: `api/tests/unit/test_cost_schema_cli.py` (14 tests)

### Usage

```bash
# Full markdown documentation
payment-sim cost-schema

# Compact table format
payment-sim cost-schema --compact

# Filter by category
payment-sim cost-schema --category PerTick

# JSON output
payment-sim cost-schema --format json

# Save to file
payment-sim cost-schema --output costs.md
```

---

## Overview

The policy system has a self-documenting architecture where schema metadata lives directly in Rust code and is exported via FFI to a CLI command (`payment-sim policy-schema`). This plan proposes the same pattern for cost types, ensuring documentation is always accurate and making it obvious where to update descriptions when adding or modifying cost types.

## Current State

Cost type documentation is scattered:
- **Rust defaults**: `simulator/src/orchestrator/engine.rs:612-625` (impl Default for CostRates)
- **Python schema**: `api/payment_simulator/config/schemas.py:580-609` (Pydantic model)
- **CLAUDE.md**: Manual documentation in "Costs" section
- **This analysis**: Ad-hoc exploration to find all cost types

**Problem**: When adding a new cost type, developers must update 3+ locations. Documentation drifts from implementation.

## Proposed Architecture

Follow the policy schema pattern exactly:

```
┌─────────────────────────────────────────────────────┐
│  Rust (Single Source of Truth)                      │
│  simulator/src/costs/schema_docs.rs                 │
│  - CostSchemaDocumented trait                       │
│  - CostElement metadata struct                      │
│  - CostRates::schema_docs() implementation          │
└────────────────────┬────────────────────────────────┘
                     │ FFI (PyO3)
                     ▼
┌─────────────────────────────────────────────────────┐
│  Python CLI Command                                 │
│  payment-sim cost-schema                            │
│  - Fetch schema from Rust                           │
│  - Format as Markdown or JSON                       │
│  - Filter by category                               │
└─────────────────────────────────────────────────────┘
```

## Schema Data Structure

### CostElement (Rust)

```rust
// simulator/src/costs/schema_docs.rs

/// Category for grouping cost types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub enum CostCategory {
    /// Costs that accrue every tick
    PerTick,
    /// One-time penalties triggered by events
    OneTime,
    /// Costs charged once per day
    Daily,
    /// Multipliers that modify other costs
    Modifier,
}

/// Documentation for a single cost type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostElement {
    /// Cost type name (e.g., "overdraft_bps_per_tick")
    pub name: String,

    /// Human-readable display name (e.g., "Overdraft Cost")
    pub display_name: String,

    /// Category for filtering
    pub category: CostCategory,

    /// What this cost represents
    pub description: String,

    /// When/how the cost is incurred
    pub incurred_at: String,

    /// Mathematical formula (LaTeX or plain text)
    pub formula: String,

    /// Default value
    pub default_value: String,

    /// Unit of measurement
    pub unit: String,

    /// Data type (f64, i64, etc.)
    pub data_type: String,

    /// Rust source file location
    pub source_location: String,

    /// Related cost types
    pub see_also: Vec<String>,

    /// Example calculation
    pub example: Option<CostExample>,

    /// Version when added
    pub added_in: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostExample {
    pub scenario: String,
    pub inputs: Vec<(String, String)>,  // (name, value)
    pub calculation: String,
    pub result: String,
}
```

### Complete Cost Schema

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostSchemaDoc {
    pub version: String,
    pub generated_at: String,
    pub cost_types: Vec<CostElement>,
}
```

## Implementation Location

All cost documentation will live in **one place**:

```
simulator/src/costs/
├── mod.rs           # Re-exports
├── rates.rs         # CostRates struct (existing, move from engine.rs)
├── schema_docs.rs   # NEW: CostSchemaDocumented trait + implementations
└── calculator.rs    # Cost calculation logic (existing, refactor from engine.rs)
```

### Single Source of Truth Pattern

```rust
// simulator/src/costs/schema_docs.rs

pub trait CostSchemaDocumented {
    fn schema_docs() -> Vec<CostElement>;
}

impl CostSchemaDocumented for CostRates {
    fn schema_docs() -> Vec<CostElement> {
        vec![
            CostElement {
                name: "overdraft_bps_per_tick".to_string(),
                display_name: "Overdraft Cost".to_string(),
                category: CostCategory::PerTick,
                description: "Cost for using intraday credit when balance goes negative. \
                    Represents the fee charged by the central bank for daylight overdrafts.".to_string(),
                incurred_at: "Every tick, when agent balance < 0".to_string(),
                formula: "max(0, -balance) × overdraft_bps_per_tick / 10,000".to_string(),
                default_value: "0.001".to_string(),
                unit: "basis points per tick".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs:15".to_string(),
                see_also: vec!["collateral_cost_per_tick_bps".to_string()],
                example: Some(CostExample {
                    scenario: "Bank A has negative balance".to_string(),
                    inputs: vec![
                        ("balance".to_string(), "-$500,000 (-50,000,000 cents)".to_string()),
                        ("overdraft_bps_per_tick".to_string(), "0.001".to_string()),
                    ],
                    calculation: "50,000,000 × 0.001 / 10,000 = 5,000 cents".to_string(),
                    result: "$50.00 per tick".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            // ... all other cost types
        ]
    }
}
```

## FFI Export

```rust
// simulator/src/lib.rs

/// Generate complete cost schema as JSON string
#[cfg(feature = "pyo3")]
#[pyfunction]
#[pyo3(name = "get_cost_schema")]
fn py_get_cost_schema() -> PyResult<String> {
    Ok(costs::schema_docs::get_cost_schema())
}
```

## CLI Command

### Command: `payment-sim cost-schema`

```python
# api/payment_simulator/cli/commands/cost_schema.py

def cost_schema(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.markdown,
    category: Annotated[
        list[CostCategory] | None,
        typer.Option("--category", "-c", help="Filter by category"),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file (default: stdout)"),
    ] = None,
    no_examples: Annotated[
        bool,
        typer.Option("--no-examples", help="Exclude examples from output"),
    ] = False,
    compact: Annotated[
        bool,
        typer.Option("--compact", help="Table format only"),
    ] = False,
) -> None:
    """Generate cost schema documentation.

    Examples:

        # Full markdown documentation
        payment-sim cost-schema

        # Per-tick costs only
        payment-sim cost-schema --category per_tick

        # JSON format for tools
        payment-sim cost-schema --format json

        # Compact table
        payment-sim cost-schema --compact
    """
```

### Example Output (Markdown)

```markdown
# Cost Types Reference

> Generated: 2025-12-12T10:00:00Z
> Version: 1.0

## Per-Tick Costs

### Overdraft Cost (`overdraft_bps_per_tick`)

Cost for using intraday credit when balance goes negative.

**When Incurred:** Every tick, when agent balance < 0

**Formula:**
```
max(0, -balance) × overdraft_bps_per_tick / 10,000
```

**Default:** `0.001` (basis points per tick)

**Example:**
- **Scenario:** Bank A has negative balance
- **Inputs:**
  - balance: -$500,000 (-50,000,000 cents)
  - overdraft_bps_per_tick: 0.001
- **Calculation:** 50,000,000 × 0.001 / 10,000 = 5,000 cents
- **Result:** $50.00 per tick

*Source: simulator/src/costs/rates.rs:15*

**See also:** collateral_cost_per_tick_bps

---

### Delay Cost (`delay_cost_per_tick_per_cent`)
...
```

### Example Output (Compact Table)

```markdown
| Cost Type | Category | Default | Unit | Description |
|-----------|----------|---------|------|-------------|
| overdraft_bps_per_tick | per_tick | 0.001 | bps/tick | Overdraft cost |
| delay_cost_per_tick_per_cent | per_tick | 0.0001 | per cent/tick | Queue delay cost |
| deadline_penalty | one_time | 50,000 | cents | Missed deadline penalty |
| ... | ... | ... | ... | ... |
```

## Update Workflow

### Adding a New Cost Type

1. **Add field to CostRates struct** (`simulator/src/costs/rates.rs`)
   ```rust
   pub new_cost_field: i64,
   ```

2. **Add default value** (same file, `impl Default`)
   ```rust
   new_cost_field: 1000,
   ```

3. **Add documentation** (`simulator/src/costs/schema_docs.rs`)
   ```rust
   CostElement {
       name: "new_cost_field".to_string(),
       display_name: "New Cost".to_string(),
       // ... all metadata
   },
   ```

4. **Add Python schema field** (`api/payment_simulator/config/schemas.py`)
   ```python
   new_cost_field: int = Field(
       1000, description="...", ge=0
   )
   ```

5. **Verify** - Run `payment-sim cost-schema` to see the new cost documented

### Where to Update (Checklist)

When adding/modifying a cost type:

- [ ] `simulator/src/costs/rates.rs` - Rust struct field
- [ ] `simulator/src/costs/rates.rs` - Default value
- [ ] `simulator/src/costs/schema_docs.rs` - Documentation metadata (**this is the main docs**)
- [ ] `api/payment_simulator/config/schemas.py` - Python Pydantic field
- [ ] Run `payment-sim cost-schema` to verify

## Implementation Tasks

### Phase 1: Create Cost Schema Infrastructure (Rust)

**Estimated Effort:** 2-3 hours

- [ ] Create `simulator/src/costs/` module directory
- [ ] Move `CostRates` from `engine.rs` to `costs/rates.rs`
- [ ] Create `costs/schema_docs.rs` with:
  - [ ] `CostCategory` enum
  - [ ] `CostElement` struct
  - [ ] `CostExample` struct
  - [ ] `CostSchemaDoc` struct
  - [ ] `CostSchemaDocumented` trait
- [ ] Implement `CostSchemaDocumented` for `CostRates` with all 9 cost types
- [ ] Create `get_cost_schema()` function returning JSON
- [ ] Add FFI export `py_get_cost_schema()` to `lib.rs`

### Phase 2: Create CLI Command (Python)

**Estimated Effort:** 1-2 hours

- [ ] Create `api/payment_simulator/cli/commands/cost_schema.py`
- [ ] Add `CostCategory` enum (Python)
- [ ] Implement markdown formatter
- [ ] Implement JSON formatter
- [ ] Implement compact table formatter
- [ ] Add filtering by category
- [ ] Register command in CLI app
- [ ] Add to Python `backends.py` exports

### Phase 3: Testing

**Estimated Effort:** 1-2 hours

- [ ] Rust unit test: All cost types have schema docs
- [ ] Rust unit test: Schema serializes to valid JSON
- [ ] Python integration test: FFI returns valid schema
- [ ] Python integration test: CLI outputs valid markdown
- [ ] Verify all 9 cost types are documented

### Phase 4: Documentation & Cleanup

**Estimated Effort:** 1 hour

- [ ] Update CLAUDE.md to reference `payment-sim cost-schema`
- [ ] Remove manual cost documentation from CLAUDE.md (replace with CLI reference)
- [ ] Add CLI command docs to `docs/reference/cli/commands/cost-schema.md`
- [ ] Update `api/CLAUDE.md` with cost schema pattern

## Success Criteria

1. **Single Source of Truth**: Cost documentation lives only in `schema_docs.rs`
2. **Always Accurate**: Generated from code, cannot drift
3. **Discoverable**: `payment-sim cost-schema` shows all cost types
4. **Maintainable**: Clear checklist for adding new cost types
5. **Machine-Readable**: JSON output for tools/LLMs

## Benefits

1. **For Developers**: Know exactly where to update when adding costs
2. **For Users**: `payment-sim cost-schema` always shows current defaults
3. **For Documentation**: Auto-generated, never stale
4. **For Testing**: Can programmatically verify all costs are documented
5. **For LLMs/Tools**: JSON schema for cost type introspection

## Alternative Considered: Python-Only Schema

We could define the schema entirely in Python (Pydantic) and skip Rust.

**Rejected because:**
- Rust is the source of truth for default values and calculation logic
- Duplicating in Python risks drift
- Policy schema already establishes the Rust-first pattern
- FFI export is minimal overhead

## Related Work

- **Policy Schema**: `simulator/src/policy/tree/schema_docs.rs` (model to follow)
- **Policy CLI**: `api/payment_simulator/cli/commands/policy_schema.py` (code to reuse)
- **Cost Analysis**: This document started from ad-hoc analysis that should not be repeated

---

## Appendix: All Cost Types to Document

| Name | Category | Default | Unit |
|------|----------|---------|------|
| `overdraft_bps_per_tick` | PerTick | 0.001 | bps/tick |
| `delay_cost_per_tick_per_cent` | PerTick | 0.0001 | per cent/tick |
| `collateral_cost_per_tick_bps` | PerTick | 0.0002 | bps/tick |
| `liquidity_cost_per_tick_bps` | PerTick | 0.0 | bps/tick |
| `deadline_penalty` | OneTime | 50,000 | cents |
| `split_friction_cost` | OneTime | 1,000 | cents |
| `eod_penalty_per_transaction` | Daily | 10,000 | cents |
| `overdue_delay_multiplier` | Modifier | 5.0 | multiplier |
| `priority_delay_multipliers` | Modifier | None | multiplier struct |
