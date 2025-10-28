// Phase 6: Tree Policy Executor
//
// Implements CashManagerPolicy trait for JSON decision tree policies.
// Provides unified interface for both trait-based and tree-based policies.

use crate::policy::tree::{
    build_decision, traverse_tree, validate_tree, DecisionTreeDef, EvalContext, EvalError,
    ValidationError,
};
use crate::orchestrator::CostRates;
use crate::policy::{CashManagerPolicy, ReleaseDecision};
use crate::{Agent, SimulationState};
use std::path::Path;
use thiserror::Error;

/// Errors that can occur when using TreePolicy
#[derive(Debug, Error)]
pub enum TreePolicyError {
    #[error("Failed to load tree from file: {0}")]
    LoadError(#[from] std::io::Error),

    #[error("Failed to parse JSON: {0}")]
    ParseError(#[from] serde_json::Error),

    #[error("Tree validation failed: {0:?}")]
    ValidationError(Vec<ValidationError>),

    #[error("Tree evaluation failed: {0}")]
    EvaluationError(#[from] EvalError),
}

/// JSON decision tree policy
///
/// Implements CashManagerPolicy by loading and executing a JSON decision tree.
///
/// # Example
///
/// ```ignore
/// use payment_simulator_core_rs::policy::tree::TreePolicy;
///
/// // Load from JSON file
/// let mut policy = TreePolicy::from_file("policies/deadline_policy.json")?;
///
/// // Or create from DecisionTreeDef
/// let tree = serde_json::from_str(json_string)?;
/// let mut policy = TreePolicy::new(tree)?;
///
/// // Use like any other policy
/// let decisions = policy.evaluate_queue(&agent, &state, tick);
/// ```
pub struct TreePolicy {
    /// Decision tree definition
    tree: DecisionTreeDef,

    /// Whether tree has been validated
    validated: bool,
}

impl TreePolicy {
    /// Create a new TreePolicy from a DecisionTreeDef
    ///
    /// Tree is validated on first use (lazy validation).
    ///
    /// # Arguments
    ///
    /// * `tree` - Decision tree definition
    ///
    /// # Example
    ///
    /// ```ignore
    /// let tree = serde_json::from_str::<DecisionTreeDef>(json_string)?;
    /// let policy = TreePolicy::new(tree)?;
    /// ```
    pub fn new(tree: DecisionTreeDef) -> Self {
        Self {
            tree,
            validated: false,
        }
    }

    /// Load TreePolicy from JSON file
    ///
    /// # Arguments
    ///
    /// * `path` - Path to JSON file containing DecisionTreeDef
    ///
    /// # Returns
    ///
    /// Ok(TreePolicy) if loading and parsing succeeds, Err otherwise
    ///
    /// # Example
    ///
    /// ```ignore
    /// let policy = TreePolicy::from_file("policies/my_policy.json")?;
    /// ```
    pub fn from_file<P: AsRef<Path>>(path: P) -> Result<Self, TreePolicyError> {
        let contents = std::fs::read_to_string(path)?;
        let tree: DecisionTreeDef = serde_json::from_str(&contents)?;
        Ok(Self::new(tree))
    }

    /// Load TreePolicy from JSON string
    ///
    /// # Arguments
    ///
    /// * `json` - JSON string containing DecisionTreeDef
    ///
    /// # Returns
    ///
    /// Ok(TreePolicy) if parsing succeeds, Err otherwise
    ///
    /// # Example
    ///
    /// ```ignore
    /// let json = r#"{"version": "1.0", ...}"#;
    /// let policy = TreePolicy::from_json(json)?;
    /// ```
    pub fn from_json(json: &str) -> Result<Self, TreePolicyError> {
        let tree: DecisionTreeDef = serde_json::from_str(json)?;
        Ok(Self::new(tree))
    }

    /// Validate tree against sample context
    ///
    /// This is automatically called on first evaluate_queue call.
    /// Can be called explicitly to fail fast.
    fn validate_if_needed(
        &mut self,
        sample_context: &EvalContext,
    ) -> Result<(), TreePolicyError> {
        if !self.validated {
            validate_tree(&self.tree, sample_context)
                .map_err(TreePolicyError::ValidationError)?;
            self.validated = true;
        }
        Ok(())
    }

    /// Get reference to underlying decision tree
    pub fn tree(&self) -> &DecisionTreeDef {
        &self.tree
    }

    /// Get tree ID
    pub fn tree_id(&self) -> &str {
        &self.tree.tree_id
    }

    /// Get tree version
    pub fn version(&self) -> &str {
        &self.tree.version
    }
}

impl CashManagerPolicy for TreePolicy {
    /// Evaluate queue using decision tree
    ///
    /// For each transaction in the agent's queue:
    /// 1. Build evaluation context
    /// 2. Traverse decision tree
    /// 3. Convert action node to ReleaseDecision
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent whose queue is being evaluated
    /// * `state` - Full simulation state
    /// * `tick` - Current simulation tick
    ///
    /// # Returns
    ///
    /// Vector of decisions for transactions in agent's queue
    ///
    /// # Panics
    ///
    /// Panics if tree evaluation fails (indicates bug in tree or interpreter).
    /// Tree should be validated before execution.
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        _cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        // Note: cost_rates not currently used in tree evaluation
        // Future: could expose as variable in EvalContext for tree-based cost calculations
        let mut decisions = Vec::new();

        // Process each transaction in agent's queue
        for tx_id in agent.outgoing_queue() {
            let tx = match state.get_transaction(tx_id) {
                Some(tx) => tx,
                None => {
                    eprintln!("WARNING: Transaction {} not found in state", tx_id);
                    continue;
                }
            };

            // Build evaluation context
            let context = EvalContext::build(tx, agent, state, tick);

            // Validate tree on first use
            if !self.validated {
                if let Err(e) = self.validate_if_needed(&context) {
                    panic!("Tree validation failed: {:?}", e);
                }
            }

            // Traverse tree to find action
            let action_node = match traverse_tree(&self.tree, &context) {
                Ok(node) => node,
                Err(e) => {
                    panic!("Tree traversal failed for tx {}: {:?}", tx_id, e);
                }
            };

            // Build decision from action node
            let decision = match build_decision(
                action_node,
                tx_id.to_string(),
                &context,
                &self.tree.parameters,
            ) {
                Ok(decision) => decision,
                Err(e) => {
                    panic!("Action building failed for tx {}: {:?}", tx_id, e);
                }
            };

            decisions.push(decision);
        }

        decisions
    }
}

// ============================================================================
// TESTS - Phase 6.16 & 6.17
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::orchestrator::CostRates;
    use crate::policy::tree::types::{ActionType, Expression, TreeNode, Value};
    use crate::{Agent, Transaction};
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

    #[test]
    fn test_tree_policy_creation() {
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "test_policy".to_string(),
            root: TreeNode::Action {
                node_id: "A1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            },
            parameters: HashMap::new(),
        };

        let policy = TreePolicy::new(tree);
        assert_eq!(policy.tree_id(), "test_policy");
        assert_eq!(policy.version(), "1.0");
    }

    #[test]
    fn test_tree_policy_from_json() {
        let json = r#"{
            "version": "1.0",
            "tree_id": "simple_policy",
            "root": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            },
            "parameters": {}
        }"#;

        let policy = TreePolicy::from_json(json).unwrap();
        assert_eq!(policy.tree_id(), "simple_policy");
    }

    #[test]
    fn test_tree_policy_evaluates_queue() {
        // Create a simple tree: if balance > amount then Release else Hold
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "liquidity_check".to_string(),
            root: TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check if sufficient liquidity".to_string(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Field {
                        field: "amount".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            },
            parameters: HashMap::new(),
        };

        let mut policy = TreePolicy::new(tree);

        // Create simulation state
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 0);
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000,
            0,
            100,
        );
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        // Add transaction to agent's queue
        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate queue
        let decisions = policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        // Should release (balance 500k > amount 100k)
        assert_eq!(decisions.len(), 1);
        assert!(matches!(
            &decisions[0],
            ReleaseDecision::SubmitFull { tx_id: id } if id == &tx_id
        ));
    }

    #[test]
    fn test_tree_policy_evaluates_multiple_transactions() {
        // Simple tree: always release
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "always_release".to_string(),
            root: TreeNode::Action {
                node_id: "A1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            },
            parameters: HashMap::new(),
        };

        let mut policy = TreePolicy::new(tree);

        // Create simulation state with multiple transactions
        let mut agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_C".to_string(), 200_000, 0, 100);
        let tx1_id = tx1.id().to_string();
        let tx2_id = tx2.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx1);
        state.add_transaction(tx2);

        agent.queue_outgoing(tx1_id.clone());
        agent.queue_outgoing(tx2_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate queue
        let decisions = policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        // Should release both
        assert_eq!(decisions.len(), 2);
        assert!(matches!(&decisions[0], ReleaseDecision::SubmitFull { .. }));
        assert!(matches!(&decisions[1], ReleaseDecision::SubmitFull { .. }));
    }

    #[test]
    fn test_tree_policy_with_parameters() {
        // Tree with parameter: if balance > threshold then Release else Hold
        let mut params = HashMap::new();
        params.insert("min_balance".to_string(), 300_000.0);

        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            tree_id: "threshold_policy".to_string(),
            root: TreeNode::Condition {
                node_id: "N1".to_string(),
                description: "Check balance threshold".to_string(),
                condition: Expression::GreaterThan {
                    left: Value::Field {
                        field: "balance".to_string(),
                    },
                    right: Value::Param {
                        param: "min_balance".to_string(),
                    },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "A1".to_string(),
                    action: ActionType::Release,
                    parameters: HashMap::new(),
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "A2".to_string(),
                    action: ActionType::Hold,
                    parameters: HashMap::new(),
                }),
            },
            parameters: params,
        };

        let mut policy = TreePolicy::new(tree);

        // Create simulation state
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 0); // balance > 300k threshold
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let tx_id = tx.id().to_string();

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        agent.queue_outgoing(tx_id.clone());
        *state.get_agent_mut("BANK_A").unwrap() = agent.clone();
        let cost_rates = create_test_cost_rates();

        // Evaluate queue
        let decisions = policy.evaluate_queue(&agent, &state, 10, &cost_rates);

        // Should release (balance 500k > threshold 300k)
        assert_eq!(decisions.len(), 1);
        assert!(matches!(
            &decisions[0],
            ReleaseDecision::SubmitFull { tx_id: id } if id == &tx_id
        ));
    }
}
