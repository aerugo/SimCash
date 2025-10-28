// Phase 6: Policy DSL Decision Trees - Integration Tests
//
// This file contains TDD-style tests for the JSON decision tree policy system.
// Tests are organized by implementation phase.

use payment_simulator_core_rs::policy::tree::types::*;
use serde_json;

// ============================================================================
// PHASE 6.1: Type System & Deserialization
// ============================================================================

#[test]
fn test_parse_minimal_tree() {
    // Simplest valid tree: single condition, two actions
    let json = r#"{
        "version": "1.0",
        "tree_id": "minimal_test",
        "root": {
            "node_id": "N1",
            "type": "condition",
            "condition": {
                "op": ">",
                "left": {"field": "balance"},
                "right": {"field": "amount"}
            },
            "on_true": {
                "node_id": "A1",
                "type": "action",
                "action": "Release"
            },
            "on_false": {
                "node_id": "A2",
                "type": "action",
                "action": "Hold"
            }
        },
        "parameters": {}
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(tree.is_ok(), "Failed to parse minimal tree: {:?}", tree.err());

    let tree = tree.unwrap();
    assert_eq!(tree.version, "1.0");
    assert_eq!(tree.tree_id, "minimal_test");
    assert!(matches!(tree.root, TreeNode::Condition { .. }));
}

#[test]
fn test_parse_nested_conditions() {
    // Multi-level tree with nested conditions
    let json = r#"{
        "version": "1.0",
        "tree_id": "nested_test",
        "root": {
            "node_id": "N1",
            "type": "condition",
            "condition": {
                "op": "<=",
                "left": {"field": "ticks_to_deadline"},
                "right": {"value": 5}
            },
            "on_true": {
                "node_id": "A1",
                "type": "action",
                "action": "Release"
            },
            "on_false": {
                "node_id": "N2",
                "type": "condition",
                "condition": {
                    "op": ">=",
                    "left": {"field": "balance"},
                    "right": {"field": "amount"}
                },
                "on_true": {
                    "node_id": "A2",
                    "type": "action",
                    "action": "Release"
                },
                "on_false": {
                    "node_id": "A3",
                    "type": "action",
                    "action": "Hold"
                }
            }
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(tree.is_ok(), "Failed to parse nested tree: {:?}", tree.err());
}

#[test]
fn test_parse_with_computations() {
    // Tree with arithmetic computations in conditions
    let json = r#"{
        "version": "1.0",
        "tree_id": "computation_test",
        "root": {
            "node_id": "N1",
            "type": "condition",
            "condition": {
                "op": ">",
                "left": {
                    "compute": {
                        "op": "+",
                        "left": {"field": "balance"},
                        "right": {"field": "credit"}
                    }
                },
                "right": {"field": "amount"}
            },
            "on_true": {
                "node_id": "A1",
                "type": "action",
                "action": "Release"
            },
            "on_false": {
                "node_id": "A2",
                "type": "action",
                "action": "Hold"
            }
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(tree.is_ok(), "Failed to parse tree with computations: {:?}", tree.err());
}

#[test]
fn test_reject_invalid_json() {
    // Missing required field 'version'
    let json = r#"{
        "tree_id": "invalid",
        "root": {
            "node_id": "N1",
            "type": "action",
            "action": "Hold"
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(tree.is_err(), "Should reject JSON missing required field");
}

#[test]
fn test_parse_all_expression_types() {
    // Test all comparison operators
    let operators = vec![
        ("==", "Equal"),
        ("!=", "NotEqual"),
        ("<", "LessThan"),
        ("<=", "LessOrEqual"),
        (">", "GreaterThan"),
        (">=", "GreaterOrEqual"),
    ];

    for (op, _name) in operators {
        let json = format!(r#"{{
            "version": "1.0",
            "tree_id": "test_{}",
            "root": {{
                "node_id": "N1",
                "type": "condition",
                "condition": {{
                    "op": "{}",
                    "left": {{"field": "balance"}},
                    "right": {{"field": "amount"}}
                }},
                "on_true": {{"node_id": "A1", "type": "action", "action": "Release"}},
                "on_false": {{"node_id": "A2", "type": "action", "action": "Hold"}}
            }}
        }}"#, op, op);

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
        assert!(tree.is_ok(), "Failed to parse {} operator: {:?}", op, tree.err());
    }

    // Test logical operators
    let logical_json = r#"{
        "version": "1.0",
        "tree_id": "logical_test",
        "root": {
            "node_id": "N1",
            "type": "condition",
            "condition": {
                "op": "and",
                "conditions": [
                    {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
                    {"op": "<", "left": {"field": "amount"}, "right": {"value": 1000}}
                ]
            },
            "on_true": {"node_id": "A1", "type": "action", "action": "Release"},
            "on_false": {"node_id": "A2", "type": "action", "action": "Hold"}
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(logical_json);
    assert!(tree.is_ok(), "Failed to parse AND operator: {:?}", tree.err());
}

#[test]
fn test_parse_all_value_types() {
    // Test field reference
    let field_json = r#"{"field": "balance"}"#;
    let val: Result<Value, _> = serde_json::from_str(field_json);
    assert!(val.is_ok(), "Failed to parse field value");
    assert!(matches!(val.unwrap(), Value::Field { .. }));

    // Test parameter reference
    let param_json = r#"{"param": "threshold"}"#;
    let val: Result<Value, _> = serde_json::from_str(param_json);
    assert!(val.is_ok(), "Failed to parse param value");
    assert!(matches!(val.unwrap(), Value::Param { .. }));

    // Test literal
    let literal_json = r#"{"value": 100}"#;
    let val: Result<Value, _> = serde_json::from_str(literal_json);
    assert!(val.is_ok(), "Failed to parse literal value");
    assert!(matches!(val.unwrap(), Value::Literal { .. }));

    // Test computation
    let compute_json = r#"{
        "compute": {
            "op": "+",
            "left": {"field": "balance"},
            "right": {"field": "credit"}
        }
    }"#;
    let val: Result<Value, _> = serde_json::from_str(compute_json);
    assert!(val.is_ok(), "Failed to parse compute value");
    assert!(matches!(val.unwrap(), Value::Compute { .. }));
}

#[test]
fn test_parse_all_action_types() {
    let actions = vec!["Release", "Hold", "Drop", "ReleaseWithCredit", "PaceAndRelease"];

    for action in actions {
        let json = format!(r#"{{
            "version": "1.0",
            "tree_id": "action_test_{}",
            "root": {{
                "node_id": "A1",
                "type": "action",
                "action": "{}"
            }}
        }}"#, action, action);

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
        assert!(tree.is_ok(), "Failed to parse action {}: {:?}", action, tree.err());
    }
}

// ============================================================================
// PHASE 8: Collateral Management Actions
// ============================================================================

#[test]
fn test_parse_collateral_action_types() {
    // Test PostCollateral action
    let post_json = r#"{
        "version": "1.0",
        "tree_id": "collateral_post_test",
        "root": {
            "node_id": "A1",
            "type": "action",
            "action": "PostCollateral",
            "parameters": {
                "amount": {"value": 100000},
                "reason": {"value": "UrgentLiquidityNeed"}
            }
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(post_json);
    assert!(tree.is_ok(), "Failed to parse PostCollateral action: {:?}", tree.err());

    // Test WithdrawCollateral action
    let withdraw_json = r#"{
        "version": "1.0",
        "tree_id": "collateral_withdraw_test",
        "root": {
            "node_id": "A1",
            "type": "action",
            "action": "WithdrawCollateral",
            "parameters": {
                "amount": {"field": "posted_collateral"},
                "reason": {"value": "LiquidityRestored"}
            }
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(withdraw_json);
    assert!(tree.is_ok(), "Failed to parse WithdrawCollateral action: {:?}", tree.err());

    // Test HoldCollateral action (no parameters needed)
    let hold_json = r#"{
        "version": "1.0",
        "tree_id": "collateral_hold_test",
        "root": {
            "node_id": "A1",
            "type": "action",
            "action": "HoldCollateral"
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(hold_json);
    assert!(tree.is_ok(), "Failed to parse HoldCollateral action: {:?}", tree.err());
}

#[test]
fn test_collateral_decision_with_computed_amount() {
    // Test PostCollateral with computed amount (liquidity gap calculation)
    let json = r#"{
        "version": "1.0",
        "tree_id": "collateral_computed_test",
        "root": {
            "node_id": "A1",
            "type": "action",
            "action": "PostCollateral",
            "parameters": {
                "amount": {
                    "compute": {
                        "op": "-",
                        "left": {"field": "queue1_liquidity_gap"},
                        "right": {"value": 0}
                    }
                },
                "reason": {"value": "UrgentLiquidityNeed"}
            }
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(tree.is_ok(), "Failed to parse collateral with computed amount: {:?}", tree.err());
}
