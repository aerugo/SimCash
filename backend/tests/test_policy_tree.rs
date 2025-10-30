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
        "policy_id": "minimal_test",
        "payment_tree": {
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
        "strategic_collateral_tree": null,
        "end_of_tick_collateral_tree": null,
        "parameters": {}
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(
        tree.is_ok(),
        "Failed to parse minimal tree: {:?}",
        tree.err()
    );

    let tree = tree.unwrap();
    assert_eq!(tree.version, "1.0");
    assert_eq!(tree.policy_id, "minimal_test");
    assert!(tree.payment_tree.is_some());
    if let Some(ref payment_tree) = tree.payment_tree {
        assert!(matches!(payment_tree, TreeNode::Condition { .. }));
    }
}

#[test]
fn test_parse_nested_conditions() {
    // Multi-level tree with nested conditions
    let json = r#"{
        "version": "1.0",
        "policy_id": "nested_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse nested tree: {:?}",
        tree.err()
    );
}

#[test]
fn test_parse_with_computations() {
    // Tree with arithmetic computations in conditions
    let json = r#"{
        "version": "1.0",
        "policy_id": "computation_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse tree with computations: {:?}",
        tree.err()
    );
}

#[test]
fn test_reject_invalid_json() {
    // Missing required field 'version'
    let json = r#"{
        "policy_id": "invalid",
        "payment_tree": {
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
        let json = format!(
            r#"{{
            "version": "1.0",
            "policy_id": "test_{}",
            "payment_tree": {{
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
        }}"#,
            op, op
        );

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
        assert!(
            tree.is_ok(),
            "Failed to parse {} operator: {:?}",
            op,
            tree.err()
        );
    }

    // Test logical operators
    let logical_json = r#"{
        "version": "1.0",
        "policy_id": "logical_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse AND operator: {:?}",
        tree.err()
    );
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
    let actions = vec![
        "Release",
        "Hold",
        "Drop",
        "ReleaseWithCredit",
        "PaceAndRelease",
    ];

    for action in actions {
        let json = format!(
            r#"{{
            "version": "1.0",
            "policy_id": "action_test_{}",
            "payment_tree": {{
                "node_id": "A1",
                "type": "action",
                "action": "{}"
            }}
        }}"#,
            action, action
        );

        let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
        assert!(
            tree.is_ok(),
            "Failed to parse action {}: {:?}",
            action,
            tree.err()
        );
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
        "policy_id": "collateral_post_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse PostCollateral action: {:?}",
        tree.err()
    );

    // Test WithdrawCollateral action
    let withdraw_json = r#"{
        "version": "1.0",
        "policy_id": "collateral_withdraw_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse WithdrawCollateral action: {:?}",
        tree.err()
    );

    // Test HoldCollateral action (no parameters needed)
    let hold_json = r#"{
        "version": "1.0",
        "policy_id": "collateral_hold_test",
        "payment_tree": {
            "node_id": "A1",
            "type": "action",
            "action": "HoldCollateral"
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(hold_json);
    assert!(
        tree.is_ok(),
        "Failed to parse HoldCollateral action: {:?}",
        tree.err()
    );
}

#[test]
fn test_collateral_decision_with_computed_amount() {
    // Test PostCollateral with computed amount (liquidity gap calculation)
    let json = r#"{
        "version": "1.0",
        "policy_id": "collateral_computed_test",
        "payment_tree": {
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
    assert!(
        tree.is_ok(),
        "Failed to parse collateral with computed amount: {:?}",
        tree.err()
    );
}

// ============================================================================
// PHASE 8.2: Three-Tree Policy Schema (TDD Cycle 1)
// ============================================================================

#[test]
fn test_parse_three_tree_policy() {
    // Test parsing policy with three separate decision trees
    let json = r#"{
        "version": "1.0",
        "policy_id": "test_three_tree_policy",
        "description": "Test policy with all three trees",

        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },

        "strategic_collateral_tree": {
            "node_id": "S1",
            "type": "action",
            "action": "HoldCollateral"
        },

        "end_of_tick_collateral_tree": {
            "node_id": "E1",
            "type": "condition",
            "condition": {
                "op": "==",
                "left": {"field": "queue2_size"},
                "right": {"value": 0}
            },
            "on_true": {
                "node_id": "E2",
                "type": "action",
                "action": "WithdrawCollateral",
                "parameters": {
                    "amount": {"field": "posted_collateral"},
                    "reason": {"value": "EndOfDayCleanup"}
                }
            },
            "on_false": {
                "node_id": "E3",
                "type": "action",
                "action": "HoldCollateral"
            }
        },

        "parameters": {
            "target_buffer": 500000.0
        }
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(
        tree.is_ok(),
        "Failed to parse three-tree policy: {:?}",
        tree.err()
    );

    let tree = tree.unwrap();
    assert_eq!(tree.version, "1.0");
    assert_eq!(tree.policy_id, "test_three_tree_policy");
    assert!(
        tree.payment_tree.is_some(),
        "payment_tree should be present"
    );
    assert!(
        tree.strategic_collateral_tree.is_some(),
        "strategic_collateral_tree should be present"
    );
    assert!(
        tree.end_of_tick_collateral_tree.is_some(),
        "end_of_tick_collateral_tree should be present"
    );
}

#[test]
fn test_parse_policy_with_optional_trees() {
    // Test that collateral trees are optional (can be null)
    let json = r#"{
        "version": "1.0",
        "policy_id": "payment_only_policy",

        "payment_tree": {
            "node_id": "P1",
            "type": "action",
            "action": "Release"
        },

        "strategic_collateral_tree": null,
        "end_of_tick_collateral_tree": null
    }"#;

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(json);
    assert!(
        tree.is_ok(),
        "Failed to parse policy with null trees: {:?}",
        tree.err()
    );

    let tree = tree.unwrap();
    assert!(
        tree.payment_tree.is_some(),
        "payment_tree should be present"
    );
    assert!(
        tree.strategic_collateral_tree.is_none(),
        "strategic_collateral_tree should be None"
    );
    assert!(
        tree.end_of_tick_collateral_tree.is_none(),
        "end_of_tick_collateral_tree should be None"
    );
}

// ============================================================================
// Phase 8.2 TDD Cycle 6: Default End-of-Tick Cleanup Policy
// ============================================================================

#[test]
fn test_load_default_end_of_tick_cleanup_policy() {
    // Test that the default end-of-tick cleanup policy can be loaded and parsed
    let policy_path = "../policies/defaults/end_of_tick_cleanup.json";
    let json = std::fs::read_to_string(policy_path)
        .expect("Failed to read default end-of-tick cleanup policy");

    let tree: Result<DecisionTreeDef, _> = serde_json::from_str(&json);
    assert!(
        tree.is_ok(),
        "Failed to parse default policy: {:?}",
        tree.err()
    );

    let tree = tree.unwrap();
    assert_eq!(tree.policy_id, "default_end_of_tick_cleanup");
    assert_eq!(tree.version, "1.0");

    // Should have end_of_tick_collateral_tree but not payment or strategic trees
    assert!(
        tree.payment_tree.is_none(),
        "payment_tree should be None for collateral-only policy"
    );
    assert!(
        tree.strategic_collateral_tree.is_none(),
        "strategic_collateral_tree should be None"
    );
    assert!(
        tree.end_of_tick_collateral_tree.is_some(),
        "end_of_tick_collateral_tree should be present"
    );
}

#[test]
fn test_default_policy_structure() {
    // Test the structure of the default policy
    let policy_path = "../policies/defaults/end_of_tick_cleanup.json";
    let json = std::fs::read_to_string(policy_path)
        .expect("Failed to read default end-of-tick cleanup policy");

    let tree: DecisionTreeDef = serde_json::from_str(&json).expect("Failed to parse");

    // Verify the root node is a condition checking queue2_size
    match tree.end_of_tick_collateral_tree.as_ref().unwrap() {
        TreeNode::Condition {
            node_id,
            description,
            condition,
            ..
        } => {
            assert_eq!(node_id, "EOT1");
            assert!(
                description.contains("RTGS queue"),
                "Should check RTGS queue status"
            );

            // Should check if queue2_size == 0
            match condition {
                Expression::Equal { left, right } => {
                    assert!(matches!(left, Value::Field { field } if field == "queue2_size"));
                    assert!(matches!(right, Value::Literal { .. }));
                }
                _ => panic!("Expected Equal condition at root"),
            }
        }
        _ => panic!("Expected Condition node at root of end_of_tick_collateral_tree"),
    }
}

#[test]
fn test_default_policy_validates() {
    use payment_simulator_core_rs::policy::tree::{validate_tree, EvalContext};
    use payment_simulator_core_rs::{Agent, SimulationState, Transaction};

    // Load the policy
    let policy_path = "../policies/defaults/end_of_tick_cleanup.json";
    let json = std::fs::read_to_string(policy_path)
        .expect("Failed to read default end-of-tick cleanup policy");
    let tree: DecisionTreeDef = serde_json::from_str(&json).expect("Failed to parse");

    // Create sample context for validation
    let agent = Agent::new("TEST_BANK".to_string(), 500_000, 0);
    let state = SimulationState::new(vec![agent.clone()]);
    let dummy_tx = Transaction::new(
        "TEST_BANK".to_string(),
        "OTHER".to_string(),
        100_000,
        0,
        100,
    );
    let context = EvalContext::build(&dummy_tx, &agent, &state, 10);

    // Validate tree
    let result = validate_tree(&tree, &context);
    assert!(
        result.is_ok(),
        "Policy should validate successfully: {:?}",
        result.err()
    );
}
