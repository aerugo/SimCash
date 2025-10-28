// Phase 6.18: Policy Equivalence Tests
//
// Validates that JSON decision tree policies produce identical results
// to their Rust trait-based implementations.

#[cfg(test)]
mod tests {
    use crate::orchestrator::CostRates;
    use crate::policy::tree::{ActionType, DecisionTreeDef, Expression, TreeNode, TreePolicy, Value};
    use crate::policy::{CashManagerPolicy, DeadlinePolicy, FifoPolicy, ReleaseDecision};
    use crate::{Agent, SimulationState, Transaction};
    use serde_json::json;
    use std::collections::HashMap;

    fn create_test_cost_rates() -> CostRates {
        CostRates {
            overdraft_bps_per_tick: 0.0001,
            delay_cost_per_tick_per_cent: 0.00001,
            eod_penalty_per_transaction: 10000,
            deadline_penalty: 5000,
            split_friction_cost: 1000,
        }
    }

    // ========================================================================
    // FIFO Policy - JSON Version
    // ========================================================================

    /// Create JSON FIFO policy (always release)
    fn create_fifo_tree() -> DecisionTreeDef {
        DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "fifo_policy".to_string(),
            root: TreeNode::Action {
                node_id: "A1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            },
            parameters: HashMap::new(),
        }
    }

    #[test]
    fn test_fifo_equivalence_empty_queue() {
        let mut trait_policy = FifoPolicy::new();
        let mut tree_policy = TreePolicy::new(create_fifo_tree());

        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_test_cost_rates();

        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 10, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        assert_eq!(trait_decisions, tree_decisions);
        assert_eq!(trait_decisions.len(), 0);
    }

    #[test]
    fn test_fifo_equivalence_single_transaction() {
        let mut trait_policy = FifoPolicy::new();
        let mut tree_policy = TreePolicy::new(create_fifo_tree());

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 10, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        assert_eq!(trait_decisions, tree_decisions);
        assert_eq!(trait_decisions.len(), 1);
        assert!(matches!(
            &trait_decisions[0],
            ReleaseDecision::SubmitFull { tx_id: id } if id == &tx_id
        ));
    }

    #[test]
    fn test_fifo_equivalence_multiple_transactions() {
        let mut trait_policy = FifoPolicy::new();
        let mut tree_policy = TreePolicy::new(create_fifo_tree());

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_C".to_string(), 200_000, 0, 100);
        let tx3 = Transaction::new("BANK_A".to_string(), "BANK_D".to_string(), 300_000, 0, 100);

        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();
        let tx3_id = tx3.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx1);
        state.add_transaction(tx2);
        state.add_transaction(tx3);

        agent.queue_outgoing(tx1_id.clone());
        agent.queue_outgoing(tx2_id.clone());
        agent.queue_outgoing(tx3_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 10, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        assert_eq!(trait_decisions, tree_decisions);
        assert_eq!(trait_decisions.len(), 3);

        for decision in &trait_decisions {
            assert!(matches!(decision, ReleaseDecision::SubmitFull { .. }));
        }
    }

    // ========================================================================
    // Deadline Policy - JSON Version
    // ========================================================================

    /// Create JSON Deadline policy
    ///
    /// Logic:
    /// - If is_past_deadline (deadline_tick <= current_tick) → Drop
    /// - Else if ticks_to_deadline <= urgency_threshold → Release
    /// - Else → Hold
    fn create_deadline_tree(urgency_threshold: f64) -> DecisionTreeDef {
        let mut params = HashMap::new();
        params.insert("urgency_threshold".to_string(), urgency_threshold);

        DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "deadline_policy".to_string(),
            root: TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check if past deadline".to_string(),
                condition: Expression::Equal {
                    left: Value::Field {
                        field: "is_past_deadline".to_string(),
                    },
                    right: Value::Literal { value: json!(1.0) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Drop,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Condition {
                    node_id: "N2".to_string(),
                    description: "Check if urgent".to_string(),
                    condition: Expression::LessOrEqual {
                        left: Value::Field {
                            field: "ticks_to_deadline".to_string(),
                        },
                        right: Value::Param {
                            param: "urgency_threshold".to_string(),
                        },
                    },
                    on_true: Box::new(TreeNode::Action {
                        node_id: "A2".to_string(),
                        action: ActionType::Release,
                        parameters: HashMap::new(),
                    }),
                    on_false: Box::new(TreeNode::Action {
                        node_id: "A3".to_string(),
                        action: ActionType::Hold,
                        parameters: HashMap::new(),
                    }),
                }),
            },
            parameters: params,
        }
    }

    #[test]
    fn test_deadline_equivalence_past_deadline() {
        let urgency_threshold = 5;
        let mut trait_policy = DeadlinePolicy::new(urgency_threshold);
        let mut tree_policy = TreePolicy::new(create_deadline_tree(urgency_threshold as f64));

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate at tick 15 (past deadline)
        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 15, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 15, &cost_rates);

        assert_eq!(trait_decisions, tree_decisions);
        assert_eq!(trait_decisions.len(), 1);
        assert!(matches!(
            &trait_decisions[0],
            ReleaseDecision::Drop { tx_id: id } if id == &tx_id
        ));
    }

    #[test]
    fn test_deadline_equivalence_urgent() {
        let urgency_threshold = 5;
        let mut trait_policy = DeadlinePolicy::new(urgency_threshold);
        let mut tree_policy = TreePolicy::new(create_deadline_tree(urgency_threshold as f64));

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate at tick 8 (ticks_to_deadline = 2, which is <= 5)
        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 8, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 8, &cost_rates);

        assert_eq!(trait_decisions, tree_decisions);
        assert_eq!(trait_decisions.len(), 1);
        assert!(matches!(
            &trait_decisions[0],
            ReleaseDecision::SubmitFull { tx_id: id } if id == &tx_id
        ));
    }

    #[test]
    fn test_deadline_equivalence_not_urgent() {
        let urgency_threshold = 5;
        let mut trait_policy = DeadlinePolicy::new(urgency_threshold);
        let mut tree_policy = TreePolicy::new(create_deadline_tree(urgency_threshold as f64));

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate at tick 10 (ticks_to_deadline = 40, which is > 5)
        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 10, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        // Both should produce Hold decisions (HoldReason may differ)
        assert_eq!(trait_decisions.len(), tree_decisions.len());
        assert_eq!(trait_decisions.len(), 1);

        // Verify both are Hold decisions for same tx_id
        assert!(matches!(
            &trait_decisions[0],
            ReleaseDecision::Hold { tx_id: id, .. } if id == &tx_id
        ));
        assert!(matches!(
            &tree_decisions[0],
            ReleaseDecision::Hold { tx_id: id, .. } if id == &tx_id
        ));
    }

    #[test]
    fn test_deadline_equivalence_mixed_transactions() {
        let urgency_threshold = 5;
        let mut trait_policy = DeadlinePolicy::new(urgency_threshold);
        let mut tree_policy = TreePolicy::new(create_deadline_tree(urgency_threshold as f64));

        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);

        // tx1: Past deadline (should Drop)
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 5);
        let tx1_id = tx1.id().to_string();

        // tx2: Urgent (should Release)
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_C".to_string(), 200_000, 0, 13);
        let tx2_id = tx2.id().to_string();

        // tx3: Not urgent (should Hold)
        let tx3 = Transaction::new("BANK_A".to_string(), "BANK_D".to_string(), 300_000, 0, 50);
        let tx3_id = tx3.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx1);
        state.add_transaction(tx2);
        state.add_transaction(tx3);

        agent.queue_outgoing(tx1_id.clone());
        agent.queue_outgoing(tx2_id.clone());
        agent.queue_outgoing(tx3_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate at tick 10
        // tx1: deadline=5, past deadline → Drop
        // tx2: deadline=13, ticks_to_deadline=3 <= 5 → Release
        // tx3: deadline=50, ticks_to_deadline=40 > 5 → Hold
        let trait_decisions = trait_policy.evaluate_queue(&agent, &state, 10, &cost_rates);
        let tree_decisions = tree_policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        assert_eq!(trait_decisions.len(), tree_decisions.len());
        assert_eq!(trait_decisions.len(), 3);

        // Helper function to find decision by tx_id
        fn find_decision<'a>(
            decisions: &'a [ReleaseDecision],
            tx_id: &str,
        ) -> &'a ReleaseDecision {
            decisions
                .iter()
                .find(|d| match d {
                    ReleaseDecision::SubmitFull { tx_id: id }
                    | ReleaseDecision::Drop { tx_id: id }
                    | ReleaseDecision::Hold { tx_id: id, .. }
                    | ReleaseDecision::SubmitPartial { tx_id: id, .. } => id == tx_id,
                })
                .unwrap()
        }

        // Verify both implementations produce same decision types for same tx_ids
        let trait_tx1_decision = find_decision(&trait_decisions, &tx1_id);
        let trait_tx2_decision = find_decision(&trait_decisions, &tx2_id);
        let trait_tx3_decision = find_decision(&trait_decisions, &tx3_id);

        let tree_tx1_decision = find_decision(&tree_decisions, &tx1_id);
        let tree_tx2_decision = find_decision(&tree_decisions, &tx2_id);
        let tree_tx3_decision = find_decision(&tree_decisions, &tx3_id);

        assert!(matches!(trait_tx1_decision, ReleaseDecision::Drop { .. }));
        assert!(matches!(tree_tx1_decision, ReleaseDecision::Drop { .. }));

        assert!(matches!(trait_tx2_decision, ReleaseDecision::SubmitFull { .. }));
        assert!(matches!(tree_tx2_decision, ReleaseDecision::SubmitFull { .. }));

        assert!(matches!(trait_tx3_decision, ReleaseDecision::Hold { .. }));
        assert!(matches!(tree_tx3_decision, ReleaseDecision::Hold { .. }));
    }
}
