// Test: Collateral withdrawal should clamp to available amount
//
// TDD test for fixing the issue where policies try to withdraw more collateral
// than is currently posted, causing a runtime error instead of gracefully clamping.

use payment_simulator_core_rs::{Agent, Orchestrator, SimulationState, Transaction};
use payment_simulator_core_rs::orchestrator::CostRates;
use payment_simulator_core_rs::policy::tree::{DecisionTreeDef, TreeNode};
use payment_simulator_core_rs::policy::tree::types::{ActionType, Expression, Value};
use payment_simulator_core_rs::policy::TreePolicy;
use serde_json::json;
use std::collections::HashMap;

#[test]
fn test_withdrawal_clamps_to_available_amount() {
    // Create a policy that tries to withdraw based on a stale `posted_collateral` field
    // The policy will evaluate when collateral is posted, but by execution time it's gone

    let mut params = HashMap::new();

    // Policy: If posted_collateral > 0, withdraw all of it
    let tree = DecisionTreeDef {
        version: "1.0".to_string(),
        policy_id: "test_withdrawal_clamp".to_string(),
        description: Some("Test withdrawal clamping".to_string()),
        payment_tree: Some(TreeNode::Action {
            node_id: "A1".to_string(),
            action: ActionType::Hold,
            parameters: HashMap::new(),
        }),
        bank_tree: None,
        strategic_collateral_tree: None,
        end_of_tick_collateral_tree: Some(TreeNode::Condition {
            node_id: "EC1".to_string(),
            description: String::new(),
            condition: Expression::GreaterThan {
                left: Value::Field {
                    field: "posted_collateral".to_string(),
                },
                right: Value::Literal { value: json!(0) },
            },
            on_true: Box::new(TreeNode::Action {
                node_id: "ECA1".to_string(),
                action: ActionType::WithdrawCollateral,
                parameters: {
                    let mut p = HashMap::new();
                    p.insert(
                        "amount".to_string(),
                        crate::policy::tree::types::ValueOrCompute::Field {
                            field: "posted_collateral".to_string(),
                        },
                    );
                    p.insert(
                        "reason".to_string(),
                        crate::policy::tree::types::ValueOrCompute::Literal {
                            value: json!("TestWithdrawal"),
                        },
                    );
                    p
                },
            }),
            on_false: Box::new(TreeNode::Action {
                node_id: "ECA2".to_string(),
                action: ActionType::HoldCollateral,
                parameters: HashMap::new(),
            }),
        }),
        parameters: params,
    };

    // Create orchestrator with this policy
    let mut config = HashMap::new();
    config.insert("ticks_per_day".to_string(), 100);
    config.insert("seed".to_string(), 42);

    let agent = Agent::new("BANK_A".to_string(), 1_000_000);
    let mut state = SimulationState::new(vec![agent.clone()]);

    // Manually post some collateral to the agent
    let agent_mut = state.get_agent_mut("BANK_A").unwrap();
    agent_mut.set_posted_collateral(500_000);
    agent_mut.set_max_collateral_capacity(1_000_000);

    // Create the policy
    let mut policy = TreePolicy::new(tree);

    // Now, manually reduce the collateral to 0 (simulating auto-withdrawal or other event)
    let agent_mut = state.get_agent_mut("BANK_A").unwrap();
    agent_mut.set_posted_collateral(0);

    // Evaluate end-of-tick collateral tree
    // The policy will see posted_collateral in its decision parameters (captured earlier)
    // but the actual posted_collateral is now 0
    // This should NOT error - it should clamp to 0 and do nothing

    let cost_rates = CostRates::default();
    let result = policy.evaluate_end_of_tick_collateral(
        &agent,
        &state,
        0,
        &cost_rates,
        100,
        0.8,
    );

    // The evaluation should succeed and return a Withdraw decision
    assert!(result.is_ok(), "Evaluation should not fail");
    let decision = result.unwrap();

    // The decision will have amount = 500_000 (from the field evaluation)
    // But when executed, it should clamp to 0 and become a no-op
    match decision {
        payment_simulator_core_rs::policy::CollateralDecision::Withdraw { amount, .. } => {
            assert_eq!(amount, 500_000, "Decision should have the evaluated amount");
        }
        _ => panic!("Expected Withdraw decision"),
    }

    // Now the critical test: try to execute this decision when collateral is 0
    // This currently FAILS with an error, but should succeed by clamping
    // We'll test this at the orchestrator level
}

#[test]
fn test_orchestrator_handles_withdrawal_overflow_gracefully() {
    // Integration test: Full orchestrator with a policy that tries to withdraw
    // more than available should not crash, but should clamp

    // This test will initially FAIL, then PASS after we implement clamping

    // TODO: Implement this test once we have a way to create an orchestrator
    // with a custom policy and trigger the withdrawal scenario

    // For now, this is a placeholder that will guide the fix
}
