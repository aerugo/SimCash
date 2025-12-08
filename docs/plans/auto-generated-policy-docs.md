# Implementation Plan: Auto-Generated Policy Schema Documentation

## Overview

Create a self-documenting policy schema system that generates up-to-date documentation from source code metadata. Documentation lives in docstrings/attributes, and a CLI tool extracts and formats it.

**This implementation follows strict Test-Driven Development (TDD) principles:**
- ✅ Write failing tests FIRST, then implement to make them pass
- ✅ Run full test suites at every checkpoint to prevent regressions
- ✅ Red → Green → Refactor cycle for each component
- ✅ No implementation without a corresponding test

---

## TDD Ground Rules

### Test Commands (Run Frequently)

```bash
# Rust tests (from simulator/)
cd backend && cargo test --no-default-features

# Python tests (from api/)
cd api && .venv/bin/python -m pytest

# Full rebuild after Rust changes (from api/)
cd api && uv sync --extra dev --reinstall-package payment-simulator

# Quick smoke test
cd api && .venv/bin/python -c "from payment_simulator.backends import Orchestrator; print('FFI OK')"
```

### Checkpoint Protocol

At each checkpoint marked with 🔴 **CHECKPOINT**, you MUST:
1. Run `cargo test --no-default-features` in `simulator/`
2. Run `uv sync --extra dev --reinstall-package payment-simulator` in `api/`
3. Run `pytest` in `api/`
4. Only proceed if ALL tests pass
5. Commit working code before continuing

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Rust Backend                                 │
│                                                                      │
│  ┌────────────────┐    ┌────────────────────┐    ┌──────────────┐  │
│  │ types.rs       │───►│ schema_docs.rs     │───►│ FFI Export   │  │
│  │ (enums with    │    │ (SchemaDocumented  │    │ get_schema() │  │
│  │ variants)      │    │  trait + impls)    │    │ → JSON       │  │
│  └────────────────┘    └────────────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ FFI (JSON)
┌─────────────────────────────────────────────────────────────────────┐
│                         Python CLI                                   │
│                                                                      │
│  ┌────────────────┐    ┌────────────────────┐    ┌──────────────┐  │
│  │ payment-sim    │───►│ schema_formatter.py│───►│ Markdown     │  │
│  │ policy-schema  │    │ (parse + filter +  │    │ Output       │  │
│  │ [options]      │    │  format)           │    │              │  │
│  └────────────────┘    └────────────────────┘    └──────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Rust Schema Documentation Module (TDD)

### Step 1.1: Write Failing Tests for Data Structures

**🔴 RED: Write tests first**

Create test file: `simulator/src/policy/tree/schema_docs.rs`

```rust
// simulator/src/policy/tree/schema_docs.rs

//! Policy Schema Documentation
//!
//! Self-documenting schema system for policy DSL elements.
//! Generates documentation from code metadata for CLI tool consumption.

use serde::{Deserialize, Serialize};

// ============================================================================
// DATA STRUCTURES
// ============================================================================

/// Category for grouping schema elements
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum SchemaCategory {
    // Expression categories
    ComparisonOperator,
    LogicalOperator,

    // Computation categories
    BinaryArithmetic,
    NaryArithmetic,
    UnaryMath,
    TernaryMath,

    // Value categories
    ValueType,

    // Action categories
    PaymentAction,
    BankAction,
    CollateralAction,

    // Field categories
    TransactionField,
    AgentField,
    QueueField,
    CollateralField,
    CostField,
    TimeField,
    LsmField,
    ThroughputField,
    StateRegisterField,

    // Node categories
    NodeType,

    // Tree categories
    TreeType,
}

/// Documentation for an action parameter
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ParameterDoc {
    pub name: String,
    pub param_type: String,
    pub required: bool,
    pub description: String,
    pub example: Option<serde_json::Value>,
    pub valid_values: Option<Vec<String>>,
}

/// Documentation for a single schema element
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct SchemaElement {
    pub name: String,
    pub json_key: String,
    pub category: SchemaCategory,
    pub description: String,
    pub semantics: Option<String>,
    pub parameters: Vec<ParameterDoc>,
    pub valid_in_trees: Vec<String>,
    pub example_json: Option<serde_json::Value>,
    pub source_location: String,
    pub see_also: Vec<String>,
    pub data_type: Option<String>,
    pub unit: Option<String>,
    pub added_in: Option<String>,
}

/// Complete schema documentation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PolicySchemaDoc {
    pub version: String,
    pub generated_at: String,
    pub tree_types: Vec<SchemaElement>,
    pub node_types: Vec<SchemaElement>,
    pub expressions: Vec<SchemaElement>,
    pub values: Vec<SchemaElement>,
    pub computations: Vec<SchemaElement>,
    pub actions: Vec<SchemaElement>,
    pub fields: Vec<SchemaElement>,
}

/// Trait for types that can provide schema documentation
pub trait SchemaDocumented {
    fn schema_docs() -> Vec<SchemaElement>;
}

// ============================================================================
// TESTS - Written FIRST (TDD)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // Step 1.1: Data structure tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_schema_category_serializes_to_json() {
        let cat = SchemaCategory::PaymentAction;
        let json = serde_json::to_string(&cat).unwrap();
        assert_eq!(json, "\"PaymentAction\"");
    }

    #[test]
    fn test_schema_category_deserializes_from_json() {
        let cat: SchemaCategory = serde_json::from_str("\"ComparisonOperator\"").unwrap();
        assert_eq!(cat, SchemaCategory::ComparisonOperator);
    }

    #[test]
    fn test_parameter_doc_serializes_roundtrip() {
        let param = ParameterDoc {
            name: "num_splits".to_string(),
            param_type: "number".to_string(),
            required: true,
            description: "Number of splits".to_string(),
            example: Some(serde_json::json!(4)),
            valid_values: None,
        };

        let json = serde_json::to_string(&param).unwrap();
        let restored: ParameterDoc = serde_json::from_str(&json).unwrap();
        assert_eq!(param, restored);
    }

    #[test]
    fn test_schema_element_serializes_roundtrip() {
        let elem = SchemaElement {
            name: "Release".to_string(),
            json_key: "Release".to_string(),
            category: SchemaCategory::PaymentAction,
            description: "Submit transaction to RTGS".to_string(),
            semantics: Some("Moves from Q1 to Q2".to_string()),
            parameters: vec![],
            valid_in_trees: vec!["payment_tree".to_string()],
            example_json: Some(serde_json::json!({"action": "Release"})),
            source_location: "types.rs:278".to_string(),
            see_also: vec!["Hold".to_string()],
            data_type: None,
            unit: None,
            added_in: Some("1.0".to_string()),
        };

        let json = serde_json::to_string(&elem).unwrap();
        let restored: SchemaElement = serde_json::from_str(&json).unwrap();
        assert_eq!(elem, restored);
    }

    #[test]
    fn test_policy_schema_doc_serializes_to_json() {
        let schema = PolicySchemaDoc {
            version: "1.0".to_string(),
            generated_at: "2025-01-01T00:00:00Z".to_string(),
            tree_types: vec![],
            node_types: vec![],
            expressions: vec![],
            values: vec![],
            computations: vec![],
            actions: vec![],
            fields: vec![],
        };

        let json = serde_json::to_string_pretty(&schema).unwrap();
        assert!(json.contains("\"version\": \"1.0\""));
        assert!(json.contains("\"tree_types\": []"));
    }
}
```

**Run tests - they should PASS (data structures only):**
```bash
cd backend && cargo test --no-default-features schema_docs
```

### 🔴 CHECKPOINT 1: Data Structures

```bash
cd backend && cargo test --no-default-features
# All tests must pass before continuing
```

---

### Step 1.2: Write Failing Tests for Expression Documentation

**🔴 RED: Add tests for Expression::schema_docs()**

Add to `schema_docs.rs` tests:

```rust
    // -------------------------------------------------------------------------
    // Step 1.2: Expression documentation tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_expression_schema_docs_returns_all_operators() {
        let docs = super::Expression::schema_docs();

        // Must have all 6 comparison + 3 logical = 9 operators
        assert_eq!(docs.len(), 9, "Expected 9 expression operators");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Comparison operators
        assert!(names.contains(&"Equal"), "Missing Equal");
        assert!(names.contains(&"NotEqual"), "Missing NotEqual");
        assert!(names.contains(&"LessThan"), "Missing LessThan");
        assert!(names.contains(&"LessOrEqual"), "Missing LessOrEqual");
        assert!(names.contains(&"GreaterThan"), "Missing GreaterThan");
        assert!(names.contains(&"GreaterOrEqual"), "Missing GreaterOrEqual");

        // Logical operators
        assert!(names.contains(&"And"), "Missing And");
        assert!(names.contains(&"Or"), "Missing Or");
        assert!(names.contains(&"Not"), "Missing Not");
    }

    #[test]
    fn test_expression_schema_docs_has_correct_json_keys() {
        let docs = super::Expression::schema_docs();

        let equal = docs.iter().find(|d| d.name == "Equal").unwrap();
        assert_eq!(equal.json_key, "==");

        let and = docs.iter().find(|d| d.name == "And").unwrap();
        assert_eq!(and.json_key, "and");
    }

    #[test]
    fn test_expression_schema_docs_has_correct_categories() {
        let docs = super::Expression::schema_docs();

        let equal = docs.iter().find(|d| d.name == "Equal").unwrap();
        assert_eq!(equal.category, SchemaCategory::ComparisonOperator);

        let and = docs.iter().find(|d| d.name == "And").unwrap();
        assert_eq!(and.category, SchemaCategory::LogicalOperator);
    }

    #[test]
    fn test_expression_schema_docs_has_descriptions() {
        let docs = super::Expression::schema_docs();

        for doc in &docs {
            assert!(!doc.description.is_empty(), "{} has empty description", doc.name);
        }
    }

    #[test]
    fn test_expression_schema_docs_has_valid_trees() {
        let docs = super::Expression::schema_docs();

        for doc in &docs {
            assert!(!doc.valid_in_trees.is_empty(), "{} has no valid_in_trees", doc.name);
            // Expressions are valid in all trees
            assert!(doc.valid_in_trees.contains(&"payment_tree".to_string()));
        }
    }
```

**Run tests - they should FAIL (not implemented yet):**
```bash
cd backend && cargo test --no-default-features expression_schema
# Expected: compilation error - Expression::schema_docs() doesn't exist
```

**🟢 GREEN: Implement Expression::schema_docs()**

Add implementation to `schema_docs.rs`:

```rust
use super::types::Expression;

impl SchemaDocumented for Expression {
    fn schema_docs() -> Vec<SchemaElement> {
        let all_trees = vec![
            "payment_tree".to_string(),
            "bank_tree".to_string(),
            "strategic_collateral_tree".to_string(),
            "end_of_tick_collateral_tree".to_string(),
        ];

        vec![
            // Comparison operators
            SchemaElement {
                name: "Equal".to_string(),
                json_key: "==".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if two values are equal (with epsilon tolerance for floats)".to_string(),
                semantics: Some("Returns true if left == right within floating point tolerance".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "==",
                    "left": {"field": "priority"},
                    "right": {"value": 10}
                })),
                source_location: "simulator/src/policy/tree/types.rs:117".to_string(),
                see_also: vec!["NotEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "NotEqual".to_string(),
                json_key: "!=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if two values are not equal".to_string(),
                semantics: Some("Returns true if left != right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "!=",
                    "left": {"field": "is_split"},
                    "right": {"value": 1}
                })),
                source_location: "simulator/src/policy/tree/types.rs:121".to_string(),
                see_also: vec!["Equal".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "LessThan".to_string(),
                json_key: "<".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is strictly less than right value".to_string(),
                semantics: Some("Returns true if left < right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "<",
                    "left": {"field": "ticks_to_deadline"},
                    "right": {"value": 5}
                })),
                source_location: "simulator/src/policy/tree/types.rs:125".to_string(),
                see_also: vec!["LessOrEqual".to_string(), "GreaterThan".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "LessOrEqual".to_string(),
                json_key: "<=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is less than or equal to right value".to_string(),
                semantics: Some("Returns true if left <= right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "<=",
                    "left": {"field": "queue_age"},
                    "right": {"param": "max_wait_ticks"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:129".to_string(),
                see_also: vec!["LessThan".to_string(), "GreaterOrEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "GreaterThan".to_string(),
                json_key: ">".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is strictly greater than right value".to_string(),
                semantics: Some("Returns true if left > right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": ">",
                    "left": {"field": "effective_liquidity"},
                    "right": {"field": "remaining_amount"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:133".to_string(),
                see_also: vec!["GreaterOrEqual".to_string(), "LessThan".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "GreaterOrEqual".to_string(),
                json_key: ">=".to_string(),
                category: SchemaCategory::ComparisonOperator,
                description: "Tests if left value is greater than or equal to right value".to_string(),
                semantics: Some("Returns true if left >= right".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": ">=",
                    "left": {"field": "balance"},
                    "right": {"field": "amount"}
                })),
                source_location: "simulator/src/policy/tree/types.rs:137".to_string(),
                see_also: vec!["GreaterThan".to_string(), "LessOrEqual".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            // Logical operators
            SchemaElement {
                name: "And".to_string(),
                json_key: "and".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical AND of multiple conditions (short-circuit evaluation)".to_string(),
                semantics: Some("Returns true only if ALL conditions are true. Stops evaluating on first false.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "and",
                    "conditions": [
                        {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
                        {"op": "<", "left": {"field": "amount"}, "right": {"value": 1000000}}
                    ]
                })),
                source_location: "simulator/src/policy/tree/types.rs:142".to_string(),
                see_also: vec!["Or".to_string(), "Not".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Or".to_string(),
                json_key: "or".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical OR of multiple conditions (short-circuit evaluation)".to_string(),
                semantics: Some("Returns true if ANY condition is true. Stops evaluating on first true.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "or",
                    "conditions": [
                        {"op": "==", "left": {"field": "is_overdue"}, "right": {"value": 1}},
                        {"op": "<", "left": {"field": "ticks_to_deadline"}, "right": {"value": 3}}
                    ]
                })),
                source_location: "simulator/src/policy/tree/types.rs:146".to_string(),
                see_also: vec!["And".to_string(), "Not".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
            SchemaElement {
                name: "Not".to_string(),
                json_key: "not".to_string(),
                category: SchemaCategory::LogicalOperator,
                description: "Logical NOT (negation) of a condition".to_string(),
                semantics: Some("Returns true if condition is false, and vice versa.".to_string()),
                parameters: vec![],
                valid_in_trees: all_trees.clone(),
                example_json: Some(serde_json::json!({
                    "op": "not",
                    "condition": {"op": "==", "left": {"field": "is_split"}, "right": {"value": 1}}
                })),
                source_location: "simulator/src/policy/tree/types.rs:150".to_string(),
                see_also: vec!["And".to_string(), "Or".to_string()],
                data_type: None,
                unit: None,
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}
```

**Run tests - they should PASS:**
```bash
cd backend && cargo test --no-default-features expression_schema
```

### 🔴 CHECKPOINT 2: Expression Documentation

```bash
cd backend && cargo test --no-default-features
# All tests must pass before continuing
```

---

### Step 1.3: Write Failing Tests for Computation Documentation

**🔴 RED: Add tests for Computation::schema_docs()**

```rust
    // -------------------------------------------------------------------------
    // Step 1.3: Computation documentation tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_computation_schema_docs_returns_all_operations() {
        let docs = super::Computation::schema_docs();

        // 4 binary + 2 n-ary + 4 unary + 2 ternary = 12 operations
        assert_eq!(docs.len(), 12, "Expected 12 computation operations");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Binary arithmetic
        assert!(names.contains(&"Add"), "Missing Add");
        assert!(names.contains(&"Subtract"), "Missing Subtract");
        assert!(names.contains(&"Multiply"), "Missing Multiply");
        assert!(names.contains(&"Divide"), "Missing Divide");

        // N-ary arithmetic
        assert!(names.contains(&"Max"), "Missing Max");
        assert!(names.contains(&"Min"), "Missing Min");

        // Unary math
        assert!(names.contains(&"Ceil"), "Missing Ceil");
        assert!(names.contains(&"Floor"), "Missing Floor");
        assert!(names.contains(&"Round"), "Missing Round");
        assert!(names.contains(&"Abs"), "Missing Abs");

        // Ternary math
        assert!(names.contains(&"Clamp"), "Missing Clamp");
        assert!(names.contains(&"SafeDiv"), "Missing SafeDiv");
    }

    #[test]
    fn test_computation_schema_docs_has_correct_categories() {
        let docs = super::Computation::schema_docs();

        let add = docs.iter().find(|d| d.name == "Add").unwrap();
        assert_eq!(add.category, SchemaCategory::BinaryArithmetic);

        let max = docs.iter().find(|d| d.name == "Max").unwrap();
        assert_eq!(max.category, SchemaCategory::NaryArithmetic);

        let ceil = docs.iter().find(|d| d.name == "Ceil").unwrap();
        assert_eq!(ceil.category, SchemaCategory::UnaryMath);

        let clamp = docs.iter().find(|d| d.name == "Clamp").unwrap();
        assert_eq!(clamp.category, SchemaCategory::TernaryMath);
    }
```

**🟢 GREEN: Implement Computation::schema_docs()** (similar pattern)

### 🔴 CHECKPOINT 3: Computation Documentation

```bash
cd backend && cargo test --no-default-features
```

---

### Step 1.4: Write Failing Tests for ActionType Documentation

**🔴 RED: Add tests for ActionType::schema_docs()**

```rust
    // -------------------------------------------------------------------------
    // Step 1.4: ActionType documentation tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_action_schema_docs_returns_all_actions() {
        let docs = super::ActionType::schema_docs();

        // 9 payment + 3 bank + 3 collateral + 2 RTGS = 17 actions
        assert_eq!(docs.len(), 17, "Expected 17 action types");

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Payment actions
        assert!(names.contains(&"Release"), "Missing Release");
        assert!(names.contains(&"Hold"), "Missing Hold");
        assert!(names.contains(&"Drop"), "Missing Drop");
        assert!(names.contains(&"Split"), "Missing Split");
        assert!(names.contains(&"StaggerSplit"), "Missing StaggerSplit");

        // Bank actions
        assert!(names.contains(&"SetReleaseBudget"), "Missing SetReleaseBudget");
        assert!(names.contains(&"SetState"), "Missing SetState");

        // Collateral actions
        assert!(names.contains(&"PostCollateral"), "Missing PostCollateral");
        assert!(names.contains(&"WithdrawCollateral"), "Missing WithdrawCollateral");
    }

    #[test]
    fn test_action_schema_docs_payment_actions_valid_only_in_payment_tree() {
        let docs = super::ActionType::schema_docs();

        let release = docs.iter().find(|d| d.name == "Release").unwrap();
        assert_eq!(release.category, SchemaCategory::PaymentAction);
        assert!(release.valid_in_trees.contains(&"payment_tree".to_string()));
        assert!(!release.valid_in_trees.contains(&"bank_tree".to_string()));
    }

    #[test]
    fn test_action_schema_docs_bank_actions_valid_only_in_bank_tree() {
        let docs = super::ActionType::schema_docs();

        let set_budget = docs.iter().find(|d| d.name == "SetReleaseBudget").unwrap();
        assert_eq!(set_budget.category, SchemaCategory::BankAction);
        assert!(set_budget.valid_in_trees.contains(&"bank_tree".to_string()));
        assert!(!set_budget.valid_in_trees.contains(&"payment_tree".to_string()));
    }

    #[test]
    fn test_action_schema_docs_has_required_parameters() {
        let docs = super::ActionType::schema_docs();

        // Split requires num_splits parameter
        let split = docs.iter().find(|d| d.name == "Split").unwrap();
        assert!(!split.parameters.is_empty(), "Split should have parameters");
        let num_splits_param = split.parameters.iter().find(|p| p.name == "num_splits");
        assert!(num_splits_param.is_some(), "Split should have num_splits parameter");
        assert!(num_splits_param.unwrap().required, "num_splits should be required");
    }
```

**🟢 GREEN: Implement ActionType::schema_docs()** (similar pattern)

### 🔴 CHECKPOINT 4: ActionType Documentation

```bash
cd backend && cargo test --no-default-features
```

---

### Step 1.5: Write Failing Tests for Field Documentation

**🔴 RED: Add tests for get_field_docs()**

```rust
    // -------------------------------------------------------------------------
    // Step 1.5: Field documentation tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_field_docs_returns_all_fields() {
        let docs = super::get_field_docs();

        // Should have 60+ fields across all categories
        assert!(docs.len() >= 60, "Expected at least 60 fields, got {}", docs.len());
    }

    #[test]
    fn test_field_docs_has_transaction_fields() {
        let docs = super::get_field_docs();
        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        assert!(names.contains(&"amount"), "Missing amount field");
        assert!(names.contains(&"remaining_amount"), "Missing remaining_amount");
        assert!(names.contains(&"priority"), "Missing priority");
        assert!(names.contains(&"ticks_to_deadline"), "Missing ticks_to_deadline");
    }

    #[test]
    fn test_field_docs_transaction_fields_only_in_payment_tree() {
        let docs = super::get_field_docs();

        let amount = docs.iter().find(|d| d.name == "amount").unwrap();
        assert_eq!(amount.category, SchemaCategory::TransactionField);
        assert!(amount.valid_in_trees.contains(&"payment_tree".to_string()));
        assert_eq!(amount.valid_in_trees.len(), 1, "Transaction fields should only be valid in payment_tree");
    }

    #[test]
    fn test_field_docs_agent_fields_in_all_trees() {
        let docs = super::get_field_docs();

        let balance = docs.iter().find(|d| d.name == "balance").unwrap();
        assert_eq!(balance.category, SchemaCategory::AgentField);
        assert!(balance.valid_in_trees.len() >= 4, "Agent fields should be valid in all trees");
    }

    #[test]
    fn test_field_docs_has_data_types_and_units() {
        let docs = super::get_field_docs();

        let amount = docs.iter().find(|d| d.name == "amount").unwrap();
        assert!(amount.data_type.is_some(), "amount should have data_type");
        assert!(amount.unit.is_some(), "amount should have unit");
        assert_eq!(amount.unit.as_ref().unwrap(), "cents");
    }
```

**🟢 GREEN: Implement get_field_docs()**

### 🔴 CHECKPOINT 5: Field Documentation

```bash
cd backend && cargo test --no-default-features
```

---

### Step 1.6: Write Failing Tests for Complete Schema Generation

**🔴 RED: Add test for get_policy_schema()**

```rust
    // -------------------------------------------------------------------------
    // Step 1.6: Complete schema generation tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_get_policy_schema_returns_valid_json() {
        let schema = super::get_policy_schema();
        let parsed: serde_json::Value = serde_json::from_str(&schema).unwrap();

        assert!(parsed.get("version").is_some());
        assert!(parsed.get("generated_at").is_some());
        assert!(parsed.get("expressions").is_some());
        assert!(parsed.get("computations").is_some());
        assert!(parsed.get("actions").is_some());
        assert!(parsed.get("fields").is_some());
    }

    #[test]
    fn test_get_policy_schema_expressions_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.expressions.len(), 9);
    }

    #[test]
    fn test_get_policy_schema_actions_count() {
        let schema = super::get_policy_schema();
        let parsed: PolicySchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.actions.len(), 17);
    }
```

**🟢 GREEN: Implement get_policy_schema()**

```rust
/// Generate complete policy schema documentation as JSON string
pub fn get_policy_schema() -> String {
    let schema = PolicySchemaDoc {
        version: "1.0".to_string(),
        generated_at: chrono::Utc::now().to_rfc3339(),
        tree_types: get_tree_type_docs(),
        node_types: get_node_type_docs(),
        expressions: Expression::schema_docs(),
        values: Value::schema_docs(),
        computations: Computation::schema_docs(),
        actions: ActionType::schema_docs(),
        fields: get_field_docs(),
    };

    serde_json::to_string_pretty(&schema).expect("Schema serialization should not fail")
}
```

### 🔴 CHECKPOINT 6: Complete Rust Schema Module

```bash
cd backend && cargo test --no-default-features
# ALL Rust tests must pass
```

---

## Phase 2: FFI Export (TDD)

### Step 2.1: Write Failing Python Test for FFI

**🔴 RED: Create Python test first**

Create file: `api/tests/unit/test_policy_schema_ffi.py`

```python
"""TDD tests for policy schema FFI."""

import json
import pytest


class TestPolicySchemaFFI:
    """Tests for get_policy_schema FFI function."""

    def test_get_policy_schema_exists(self):
        """FFI function should be importable."""
        from payment_simulator.backends import get_policy_schema
        assert callable(get_policy_schema)

    def test_get_policy_schema_returns_valid_json(self):
        """FFI function should return valid JSON string."""
        from payment_simulator.backends import get_policy_schema

        schema_json = get_policy_schema()
        assert isinstance(schema_json, str)

        # Should parse as JSON
        schema = json.loads(schema_json)
        assert isinstance(schema, dict)

    def test_get_policy_schema_has_required_keys(self):
        """Schema should have all required top-level keys."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        assert "version" in schema
        assert "generated_at" in schema
        assert "expressions" in schema
        assert "computations" in schema
        assert "actions" in schema
        assert "fields" in schema

    def test_get_policy_schema_expressions_count(self):
        """Should have exactly 9 expression operators."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["expressions"]) == 9

    def test_get_policy_schema_actions_count(self):
        """Should have exactly 17 action types."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["actions"]) == 17

    def test_get_policy_schema_element_structure(self):
        """Each element should have required fields."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        for expr in schema["expressions"]:
            assert "name" in expr
            assert "json_key" in expr
            assert "category" in expr
            assert "description" in expr
            assert "valid_in_trees" in expr
```

**Run tests - they should FAIL (FFI not exported yet):**
```bash
cd api && .venv/bin/python -m pytest tests/unit/test_policy_schema_ffi.py -v
# Expected: ImportError - get_policy_schema not found
```

**🟢 GREEN: Add FFI export**

1. Update `simulator/src/ffi/orchestrator.rs`:

```rust
use crate::policy::tree::schema_docs::get_policy_schema;

#[pyfunction]
#[pyo3(name = "get_policy_schema")]
pub fn py_get_policy_schema() -> PyResult<String> {
    Ok(get_policy_schema())
}
```

2. Update `simulator/src/lib.rs` to export:

```rust
#[pymodule]
fn payment_simulator_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // ... existing exports ...
    m.add_function(wrap_pyfunction!(ffi::orchestrator::py_get_policy_schema, m)?)?;
    Ok(())
}
```

3. Rebuild and test:

```bash
cd api && uv sync --extra dev --reinstall-package payment-simulator
cd api && .venv/bin/python -m pytest tests/unit/test_policy_schema_ffi.py -v
```

### 🔴 CHECKPOINT 7: FFI Export Complete

```bash
# Full Rust test suite
cd backend && cargo test --no-default-features

# Full Python test suite
cd api && uv sync --extra dev --reinstall-package payment-simulator
cd api && .venv/bin/python -m pytest

# Both must pass!
```

---

## Phase 3: Python CLI Tool (TDD)

### Step 3.1: Write Failing Tests for CLI Command

**🔴 RED: Create CLI tests first**

Create file: `api/tests/unit/test_policy_schema_cli.py`

```python
"""TDD tests for policy-schema CLI command."""

import json
import pytest
from click.testing import CliRunner


class TestPolicySchemaCommand:
    """Tests for payment-sim policy-schema command."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def cli(self):
        from payment_simulator.cli.main import cli
        return cli

    def test_policy_schema_command_exists(self, runner, cli):
        """Command should be registered."""
        result = runner.invoke(cli, ["policy-schema", "--help"])
        assert result.exit_code == 0
        assert "Generate policy schema documentation" in result.output

    def test_policy_schema_json_format(self, runner, cli):
        """--format json should output valid JSON."""
        result = runner.invoke(cli, ["policy-schema", "-f", "json"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        assert "version" in schema
        assert "expressions" in schema

    def test_policy_schema_markdown_format(self, runner, cli):
        """--format markdown should output markdown."""
        result = runner.invoke(cli, ["policy-schema", "-f", "markdown"])
        assert result.exit_code == 0
        assert "# Policy Schema Reference" in result.output

    def test_policy_schema_section_filter(self, runner, cli):
        """--section should filter to specific sections."""
        result = runner.invoke(cli, ["policy-schema", "-f", "json", "-s", "actions"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        assert "actions" in schema
        assert "expressions" not in schema
        assert "fields" not in schema

    def test_policy_schema_category_filter(self, runner, cli):
        """--category should filter by category."""
        result = runner.invoke(cli, ["policy-schema", "-f", "json", "-c", "PaymentAction"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # Only payment actions should be present
        if "actions" in schema:
            for action in schema["actions"]:
                assert action["category"] == "PaymentAction"

    def test_policy_schema_exclude_category(self, runner, cli):
        """--exclude-category should exclude categories."""
        result = runner.invoke(cli, ["policy-schema", "-f", "json", "-x", "TransactionField"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        if "fields" in schema:
            for field in schema["fields"]:
                assert field["category"] != "TransactionField"

    def test_policy_schema_tree_filter(self, runner, cli):
        """--tree should filter to elements valid in specific trees."""
        result = runner.invoke(cli, ["policy-schema", "-f", "json", "-t", "bank_tree"])
        assert result.exit_code == 0

        schema = json.loads(result.output)
        # All elements should be valid in bank_tree
        for section in ["actions", "fields"]:
            if section in schema:
                for elem in schema[section]:
                    assert "bank_tree" in elem.get("valid_in_trees", [])

    def test_policy_schema_output_file(self, runner, cli, tmp_path):
        """--output should write to file."""
        output_file = tmp_path / "schema.json"
        result = runner.invoke(cli, ["policy-schema", "-f", "json", "-o", str(output_file)])
        assert result.exit_code == 0

        assert output_file.exists()
        schema = json.loads(output_file.read_text())
        assert "version" in schema

    def test_policy_schema_compact_mode(self, runner, cli):
        """--compact should produce shorter output."""
        full_result = runner.invoke(cli, ["policy-schema", "-f", "markdown"])
        compact_result = runner.invoke(cli, ["policy-schema", "-f", "markdown", "--compact"])

        assert compact_result.exit_code == 0
        # Compact should be shorter
        assert len(compact_result.output) < len(full_result.output)
```

**Run tests - they should FAIL:**
```bash
cd api && .venv/bin/python -m pytest tests/unit/test_policy_schema_cli.py -v
# Expected: Command not found
```

**🟢 GREEN: Implement CLI command**

Create file: `api/payment_simulator/cli/commands/policy_schema.py`

```python
"""CLI command for generating policy schema documentation."""

import json
from typing import Optional, Set
from enum import Enum

import click
from rich.console import Console

from payment_simulator.backends import get_policy_schema


class SchemaCategory(str, Enum):
    """Categories for filtering schema elements."""
    COMPARISON_OPERATOR = "ComparisonOperator"
    LOGICAL_OPERATOR = "LogicalOperator"
    BINARY_ARITHMETIC = "BinaryArithmetic"
    NARY_ARITHMETIC = "NaryArithmetic"
    UNARY_MATH = "UnaryMath"
    TERNARY_MATH = "TernaryMath"
    VALUE_TYPE = "ValueType"
    PAYMENT_ACTION = "PaymentAction"
    BANK_ACTION = "BankAction"
    COLLATERAL_ACTION = "CollateralAction"
    TRANSACTION_FIELD = "TransactionField"
    AGENT_FIELD = "AgentField"
    QUEUE_FIELD = "QueueField"
    COLLATERAL_FIELD = "CollateralField"
    COST_FIELD = "CostField"
    TIME_FIELD = "TimeField"
    LSM_FIELD = "LsmField"
    THROUGHPUT_FIELD = "ThroughputField"
    STATE_REGISTER_FIELD = "StateRegisterField"
    NODE_TYPE = "NodeType"
    TREE_TYPE = "TreeType"


@click.command("policy-schema")
@click.option(
    "--format", "-f",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    help="Output format"
)
@click.option(
    "--category", "-c",
    multiple=True,
    type=click.Choice([c.value for c in SchemaCategory]),
    help="Filter to specific categories (can be repeated)"
)
@click.option(
    "--exclude-category", "-x",
    multiple=True,
    type=click.Choice([c.value for c in SchemaCategory]),
    help="Exclude specific categories (can be repeated)"
)
@click.option(
    "--tree", "-t",
    multiple=True,
    type=click.Choice([
        "payment_tree", "bank_tree",
        "strategic_collateral_tree", "end_of_tick_collateral_tree"
    ]),
    help="Filter to elements valid in specific trees"
)
@click.option(
    "--section", "-s",
    multiple=True,
    type=click.Choice([
        "trees", "nodes", "expressions", "values",
        "computations", "actions", "fields"
    ]),
    help="Include only specific sections"
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Output file (default: stdout)"
)
@click.option(
    "--no-examples",
    is_flag=True,
    help="Exclude JSON examples from output"
)
@click.option(
    "--compact",
    is_flag=True,
    help="Compact output (fewer details)"
)
def policy_schema_command(
    format: str,
    category: tuple,
    exclude_category: tuple,
    tree: tuple,
    section: tuple,
    output: Optional[str],
    no_examples: bool,
    compact: bool,
):
    """Generate policy schema documentation.

    Examples:

        # Full markdown documentation
        payment-sim policy-schema

        # Only actions, in JSON format
        payment-sim policy-schema -s actions -f json

        # Payment tree elements only
        payment-sim policy-schema -t payment_tree

        # Exclude transaction fields
        payment-sim policy-schema -x TransactionField
    """
    # Get schema from Rust
    schema_json = get_policy_schema()
    schema = json.loads(schema_json)

    # Apply filters
    include_categories = set(category) if category else None
    exclude_categories = set(exclude_category)
    include_trees = set(tree) if tree else None
    include_sections = set(section) if section else None

    # Filter schema
    filtered_schema = filter_schema(
        schema,
        include_categories=include_categories,
        exclude_categories=exclude_categories,
        include_trees=include_trees,
        include_sections=include_sections,
    )

    # Format output
    if format == "json":
        result = json.dumps(filtered_schema, indent=2)
    else:  # markdown
        result = format_as_markdown(
            filtered_schema,
            no_examples=no_examples,
            compact=compact
        )

    # Output
    if output:
        with open(output, "w") as f:
            f.write(result)
        click.echo(f"Schema written to {output}")
    else:
        console = Console()
        console.print(result)


def filter_schema(
    schema: dict,
    include_categories: Optional[Set[str]] = None,
    exclude_categories: Optional[Set[str]] = None,
    include_trees: Optional[Set[str]] = None,
    include_sections: Optional[Set[str]] = None,
) -> dict:
    """Filter schema based on options."""
    result = {
        "version": schema["version"],
        "generated_at": schema["generated_at"],
    }

    sections = [
        ("tree_types", "trees"),
        ("node_types", "nodes"),
        ("expressions", "expressions"),
        ("values", "values"),
        ("computations", "computations"),
        ("actions", "actions"),
        ("fields", "fields"),
    ]

    for schema_key, section_name in sections:
        if include_sections and section_name not in include_sections:
            continue

        elements = schema.get(schema_key, [])
        filtered_elements = []

        for elem in elements:
            # Category filter
            if include_categories and elem.get("category") not in include_categories:
                continue
            if exclude_categories and elem.get("category") in exclude_categories:
                continue

            # Tree filter
            if include_trees:
                valid_trees = set(elem.get("valid_in_trees", []))
                if not (valid_trees & include_trees):
                    continue

            filtered_elements.append(elem)

        if filtered_elements:
            result[schema_key] = filtered_elements

    return result


def format_as_markdown(
    schema: dict,
    no_examples: bool = False,
    compact: bool = False,
) -> str:
    """Format schema as markdown documentation."""
    lines = ["# Policy Schema Reference\n"]
    lines.append(f"> Generated: {schema['generated_at']}")
    lines.append(f"> Version: {schema['version']}\n")

    section_titles = {
        "tree_types": "Tree Types",
        "node_types": "Node Types",
        "expressions": "Expressions",
        "values": "Value Types",
        "computations": "Computations",
        "actions": "Actions",
        "fields": "Context Fields",
    }

    for section_key, title in section_titles.items():
        elements = schema.get(section_key, [])
        if not elements:
            continue

        lines.append(f"\n## {title}\n")

        # Group by category
        by_category: dict = {}
        for elem in elements:
            cat = elem.get("category", "Other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(elem)

        for category, cat_elements in sorted(by_category.items()):
            lines.append(f"\n### {_format_category_name(category)}\n")

            for elem in cat_elements:
                lines.append(_format_element_markdown(elem, no_examples, compact))

    return "\n".join(lines)


def _format_element_markdown(elem: dict, no_examples: bool, compact: bool) -> str:
    """Format a single schema element as markdown."""
    lines = []

    name = elem.get("name", "Unknown")
    json_key = elem.get("json_key", name)
    description = elem.get("description", "")

    if json_key != name:
        lines.append(f"#### `{json_key}` ({name})\n")
    else:
        lines.append(f"#### `{name}`\n")

    lines.append(f"{description}\n")

    if not compact:
        if semantics := elem.get("semantics"):
            lines.append(f"\n**Semantics**: {semantics}\n")

        if data_type := elem.get("data_type"):
            unit = elem.get("unit", "")
            unit_str = f" ({unit})" if unit else ""
            lines.append(f"\n**Type**: `{data_type}`{unit_str}\n")

        if valid_trees := elem.get("valid_in_trees"):
            trees_str = ", ".join(f"`{t}`" for t in valid_trees)
            lines.append(f"\n**Valid in**: {trees_str}\n")

        if params := elem.get("parameters"):
            lines.append("\n**Parameters**:\n")
            for p in params:
                req = " (required)" if p.get("required") else ""
                lines.append(f"- `{p['name']}`: {p['param_type']}{req} - {p['description']}")
            lines.append("")

        if not no_examples and (example := elem.get("example_json")):
            lines.append("\n**Example**:\n```json")
            lines.append(json.dumps(example, indent=2))
            lines.append("```\n")

        if source := elem.get("source_location"):
            lines.append(f"\n*Source: {source}*\n")

    return "\n".join(lines)


def _format_category_name(category: str) -> str:
    """Format category enum value as readable name."""
    import re
    return re.sub(r'(?<!^)(?=[A-Z])', ' ', category)
```

Register in `api/payment_simulator/cli/main.py`:

```python
from payment_simulator.cli.commands.policy_schema import policy_schema_command

# Add to CLI group
cli.add_command(policy_schema_command)
```

**Run tests:**
```bash
cd api && .venv/bin/python -m pytest tests/unit/test_policy_schema_cli.py -v
```

### 🔴 CHECKPOINT 8: CLI Complete

```bash
# Full Rust test suite
cd backend && cargo test --no-default-features

# Full Python test suite
cd api && .venv/bin/python -m pytest

# Both must pass!
```

---

## Phase 4: Integration Tests

### Step 4.1: End-to-End Integration Tests

Create file: `api/tests/integration/test_policy_schema_e2e.py`

```python
"""End-to-end integration tests for policy schema generation."""

import json
import subprocess
import pytest


class TestPolicySchemaE2E:
    """End-to-end tests for policy-schema command."""

    def test_cli_generates_valid_json(self):
        """CLI should generate parseable JSON output."""
        result = subprocess.run(
            ["payment-sim", "policy-schema", "-f", "json"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        schema = json.loads(result.stdout)
        assert schema["version"] == "1.0"

    def test_cli_generates_valid_markdown(self):
        """CLI should generate valid markdown output."""
        result = subprocess.run(
            ["payment-sim", "policy-schema", "-f", "markdown"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "# Policy Schema Reference" in result.stdout

    def test_schema_matches_actual_types(self):
        """Schema documentation should match actual Rust types."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        # Verify expression count matches types.rs
        # 6 comparison + 3 logical = 9
        assert len(schema["expressions"]) == 9

        # Verify computation count matches types.rs
        # 4 binary + 2 n-ary + 4 unary + 2 ternary = 12
        assert len(schema["computations"]) == 12

        # Verify action count matches types.rs
        # Check ActionType enum has 17 variants
        assert len(schema["actions"]) == 17

    def test_schema_field_validation_consistency(self):
        """Schema fields should match validation.rs field lists."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        # Transaction-only fields should be marked as payment_tree only
        tx_only_fields = ["amount", "remaining_amount", "settled_amount",
                          "arrival_tick", "deadline_tick", "priority",
                          "is_split", "is_past_deadline", "is_overdue"]

        field_docs = {f["name"]: f for f in schema["fields"]}

        for field_name in tx_only_fields:
            if field_name in field_docs:
                field = field_docs[field_name]
                assert field["category"] == "TransactionField", \
                    f"{field_name} should be TransactionField"
                assert field["valid_in_trees"] == ["payment_tree"], \
                    f"{field_name} should only be valid in payment_tree"
```

### 🔴 CHECKPOINT 9: Integration Tests

```bash
# Full Rust test suite
cd backend && cargo test --no-default-features

# Full Python test suite (includes integration)
cd api && .venv/bin/python -m pytest

# Both must pass!
```

---

## Final Checklist

### Before Marking Complete

1. ✅ All Rust tests pass: `cargo test --no-default-features`
2. ✅ All Python tests pass: `pytest`
3. ✅ CLI works: `payment-sim policy-schema --help`
4. ✅ JSON output is valid: `payment-sim policy-schema -f json | python -m json.tool`
5. ✅ Markdown output is readable: `payment-sim policy-schema -f markdown`
6. ✅ Filtering works: `payment-sim policy-schema -s actions -c PaymentAction`
7. ✅ Documentation updated: CLAUDE.md mentions new command

### Test Commands Summary

```bash
# Run after every code change
cd backend && cargo test --no-default-features

# Run after Rust FFI changes
cd api && uv sync --extra dev --reinstall-package payment-simulator

# Run Python tests
cd api && .venv/bin/python -m pytest

# Smoke test
payment-sim policy-schema -f json | head -20
```

---

## Files to Create/Modify

### New Files
- `simulator/src/policy/tree/schema_docs.rs`
- `api/payment_simulator/cli/commands/policy_schema.py`
- `api/tests/unit/test_policy_schema_ffi.py`
- `api/tests/unit/test_policy_schema_cli.py`
- `api/tests/integration/test_policy_schema_e2e.py`

### Modified Files
- `simulator/src/policy/tree/mod.rs` (add `pub mod schema_docs;`)
- `simulator/src/ffi/orchestrator.rs` (add FFI export)
- `simulator/src/lib.rs` (export schema function)
- `api/payment_simulator/cli/main.py` (register command)
