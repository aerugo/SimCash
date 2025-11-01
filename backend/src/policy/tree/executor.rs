// Phase 6: Tree Policy Executor
//
// Implements CashManagerPolicy trait for JSON decision tree policies.
// Provides unified interface for both trait-based and tree-based policies.

use crate::orchestrator::CostRates;
use crate::policy::tree::{
    build_decision, traverse_tree, validate_tree, DecisionTreeDef, EvalContext, EvalError,
    ValidationError,
};
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
/// ```rust
/// use payment_simulator_core_rs::policy::tree::TreePolicy;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// // Create from inline JSON
/// let json = r#"{
///   "version": "1.0",
///   "policy_id": "simple_policy",
///   "payment_tree": {
///     "type": "action",
///     "node_id": "A1",
///     "action": "Release"
///   },
///   "strategic_collateral_tree": null,
///   "end_of_tick_collateral_tree": null,
///   "parameters": {}
/// }"#;
///
/// let policy = TreePolicy::from_json(json)?;
/// // Use like any other CashManagerPolicy
/// # Ok(())
/// # }
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
    /// ```rust
    /// use payment_simulator_core_rs::policy::tree::{TreePolicy, DecisionTreeDef};
    ///
    /// # fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// let json = r#"{
    ///   "version": "1.0",
    ///   "policy_id": "test_policy",
    ///   "payment_tree": {
    ///     "type": "action",
    ///     "node_id": "A1",
    ///     "action": "Release"
    ///   },
    ///   "strategic_collateral_tree": null,
    ///   "end_of_tick_collateral_tree": null,
    ///   "parameters": {}
    /// }"#;
    /// let tree: DecisionTreeDef = serde_json::from_str(json)?;
    /// let policy = TreePolicy::new(tree);
    /// # Ok(())
    /// # }
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
    /// ```rust,no_run
    /// use payment_simulator_core_rs::policy::tree::TreePolicy;
    ///
    /// # fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// // Requires actual JSON file to exist
    /// let policy = TreePolicy::from_file("policies/my_policy.json")?;
    /// # Ok(())
    /// # }
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
    /// ```rust
    /// use payment_simulator_core_rs::policy::tree::TreePolicy;
    ///
    /// # fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// let json = r#"{
    ///   "version": "1.0",
    ///   "policy_id": "fifo_policy",
    ///   "payment_tree": {
    ///     "type": "action",
    ///     "node_id": "A1",
    ///     "action": "Release"
    ///   },
    ///   "strategic_collateral_tree": null,
    ///   "end_of_tick_collateral_tree": null,
    ///   "parameters": {}
    /// }"#;
    /// let policy = TreePolicy::from_json(json)?;
    /// # Ok(())
    /// # }
    /// ```
    pub fn from_json(json: &str) -> Result<Self, TreePolicyError> {
        let tree: DecisionTreeDef = serde_json::from_str(json)?;
        Ok(Self::new(tree))
    }

    /// Validate tree against sample context
    ///
    /// This is automatically called on first evaluate_queue call.
    /// Can be called explicitly to fail fast.
    fn validate_if_needed(&mut self, sample_context: &EvalContext) -> Result<(), TreePolicyError> {
        if !self.validated {
            validate_tree(&self.tree, sample_context).map_err(TreePolicyError::ValidationError)?;
            self.validated = true;
        }
        Ok(())
    }

    /// Get reference to underlying decision tree
    pub fn tree(&self) -> &DecisionTreeDef {
        &self.tree
    }

    /// Get policy ID
    pub fn policy_id(&self) -> &str {
        &self.tree.policy_id
    }

    /// Get tree version
    pub fn version(&self) -> &str {
        &self.tree.version
    }

    /// Evaluate strategic collateral tree (STEP 2.5 - before RTGS submission)
    ///
    /// This method evaluates the strategic_collateral_tree to determine
    /// whether to post collateral proactively before settlements begin.
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent being evaluated
    /// * `state` - Full simulation state
    /// * `tick` - Current simulation tick
    ///
    /// # Returns
    ///
    /// CollateralDecision indicating whether to post, withdraw, or hold collateral
    ///
    /// # Notes
    ///
    /// - Returns Hold if strategic_collateral_tree is not defined
    /// - Uses same EvalContext as payment decisions (no transaction context)
    /// - Evaluated once per agent per tick at STEP 2.5
    pub fn evaluate_strategic_collateral(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
    ) -> Result<crate::policy::CollateralDecision, TreePolicyError> {
        use crate::policy::tree::interpreter::{
            build_collateral_decision, traverse_strategic_collateral_tree,
        };

        // If no strategic tree defined, return Hold (default)
        if self.tree.strategic_collateral_tree.is_none() {
            return Ok(crate::policy::CollateralDecision::Hold);
        }

        // Build evaluation context (without transaction - use dummy tx for context building)
        // We create a dummy transaction just to build context, but strategic decisions
        // are based on agent-level state, not individual transactions
        let dummy_tx = crate::Transaction::new(
            agent.id().to_string(),
            "DUMMY".to_string(),
            1, // Must be positive (not used in strategic decisions, but required by constructor)
            tick,
            tick + 1,
        );
        let context = EvalContext::build(&dummy_tx, agent, state, tick, cost_rates);

        // Validate tree on first use
        if !self.validated {
            self.validate_if_needed(&context)?;
        }

        // Traverse strategic collateral tree
        let action_node = traverse_strategic_collateral_tree(&self.tree, &context)?;

        // Build collateral decision from action node
        let decision = build_collateral_decision(action_node, &context, &self.tree.parameters)?;

        Ok(decision)
    }

    /// Evaluate end-of-tick collateral tree (STEP 8 - after LSM completion)
    ///
    /// This method evaluates the end_of_tick_collateral_tree to determine
    /// whether to withdraw excess collateral after settlement attempts complete.
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent being evaluated
    /// * `state` - Full simulation state (after RTGS and LSM)
    /// * `tick` - Current simulation tick
    ///
    /// # Returns
    ///
    /// CollateralDecision indicating whether to post, withdraw, or hold collateral
    ///
    /// # Notes
    ///
    /// - Returns Hold if end_of_tick_collateral_tree is not defined
    /// - Uses same EvalContext as payment decisions
    /// - Evaluated once per agent per tick at STEP 8
    /// - Sees final queue states after all settlement attempts
    pub fn evaluate_end_of_tick_collateral(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
    ) -> Result<crate::policy::CollateralDecision, TreePolicyError> {
        use crate::policy::tree::interpreter::{
            build_collateral_decision, traverse_end_of_tick_collateral_tree,
        };

        // If no end-of-tick tree defined, return Hold (default)
        if self.tree.end_of_tick_collateral_tree.is_none() {
            return Ok(crate::policy::CollateralDecision::Hold);
        }

        // Build evaluation context (without transaction - use dummy tx for context building)
        let dummy_tx = crate::Transaction::new(
            agent.id().to_string(),
            "DUMMY".to_string(),
            1, // Must be positive (not used in end-of-tick decisions, but required by constructor)
            tick,
            tick + 1,
        );
        let context = EvalContext::build(&dummy_tx, agent, state, tick, cost_rates);

        // Validate tree on first use
        if !self.validated {
            self.validate_if_needed(&context)?;
        }

        // Traverse end-of-tick collateral tree
        let action_node = traverse_end_of_tick_collateral_tree(&self.tree, &context)?;

        // Build collateral decision from action node
        let decision = build_collateral_decision(action_node, &context, &self.tree.parameters)?;

        Ok(decision)
    }

    /// Override tree parameters
    ///
    /// Allows runtime parameter injection from configuration.
    /// This is used to customize policies without modifying JSON files.
    ///
    /// # Arguments
    ///
    /// * `params` - HashMap of parameter names to new values
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::policy::tree::TreePolicy;
    /// use std::collections::HashMap;
    ///
    /// # fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// let json = r#"{
    ///   "version": "1.0",
    ///   "policy_id": "parameterized_policy",
    ///   "payment_tree": {
    ///     "type": "action",
    ///     "node_id": "A1",
    ///     "action": "Release"
    ///   },
    ///   "strategic_collateral_tree": null,
    ///   "end_of_tick_collateral_tree": null,
    ///   "parameters": {
    ///     "urgency_threshold": 5.0
    ///   }
    /// }"#;
    /// let mut policy = TreePolicy::from_json(json)?;
    ///
    /// // Override parameters at runtime
    /// let mut params = HashMap::new();
    /// params.insert("urgency_threshold".to_string(), 10.0);
    /// policy.with_parameters(params);
    /// # Ok(())
    /// # }
    /// ```
    pub fn with_parameters(&mut self, params: std::collections::HashMap<String, f64>) {
        for (key, value) in params {
            self.tree.parameters.insert(key, value);
        }
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
        cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        // Phase 9.5.1: Expose cost_rates to policy decision trees
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

            // Build evaluation context (Phase 9.5.1: now includes cost_rates)
            let context = EvalContext::build(tx, agent, state, tick, cost_rates);

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

    fn as_any_mut(&mut self) -> &mut dyn std::any::Any {
        self
    }
}

// ============================================================================
// TESTS - Phase 6.16 & 6.17
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::orchestrator::CostRates;
    use crate::policy::tree::types::{ActionType, Expression, TreeNode, Value, ValueOrCompute};
    use crate::{Agent, Transaction};
    use serde_json::json;
    use std::collections::HashMap;

    fn create_test_cost_rates() -> CostRates {
        CostRates {
            overdraft_bps_per_tick: 0.0001,
            delay_cost_per_tick_per_cent: 0.00001,
            collateral_cost_per_tick_bps: 0.0002,
            eod_penalty_per_transaction: 10000,
            deadline_penalty: 5000,
            split_friction_cost: 1000,
        }
    }

    #[test]
    fn test_tree_policy_creation() {
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_policy".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "A1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let policy = TreePolicy::new(tree);
        assert_eq!(policy.policy_id(), "test_policy");
        assert_eq!(policy.version(), "1.0");
    }

    #[test]
    fn test_tree_policy_from_json() {
        let json = r#"{
            "version": "1.0",
            "policy_id": "simple_policy",
            "payment_tree": {
                "type": "action",
                "node_id": "A1",
                "action": "Release"
            },
            "parameters": {}
        }"#;

        let policy = TreePolicy::from_json(json).unwrap();
        assert_eq!(policy.policy_id(), "simple_policy");
    }

    #[test]
    fn test_tree_policy_evaluates_queue() {
        // Create a simple tree: if balance > amount then Release else Hold
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "liquidity_check".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Condition {
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
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let mut policy = TreePolicy::new(tree);

        // Create simulation state
        let mut agent = Agent::new("BANK_A".to_string(), 500_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
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
            policy_id: "always_release".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "A1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
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
            policy_id: "threshold_policy".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Condition {
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
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
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

    // ========================================================================
    // Phase 8.2 TDD Cycle 5: Collateral Evaluation Methods
    // ========================================================================

    #[test]
    fn test_evaluate_strategic_collateral_with_tree() {
        use crate::policy::CollateralDecision;

        // Create tree with strategic_collateral_tree that posts 100k collateral
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_strategic_collateral".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "P1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: Some(TreeNode::Action {
                node_id: "S1".to_string(),
                action: ActionType::PostCollateral,
                parameters: {
                    let mut params = HashMap::new();
                    params.insert(
                        "amount".to_string(),
                        ValueOrCompute::Direct {
                            value: json!(100000),
                        },
                    );
                    params.insert(
                        "reason".to_string(),
                        ValueOrCompute::Direct {
                            value: json!("UrgentLiquidityNeed"),
                        },
                    );
                    params
                },
            }),
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let cost_rates = CostRates::default();
        let mut policy = TreePolicy::new(tree);

        // Create test state
        let agent = Agent::new("BANK_A".to_string(), 100_000, 0);
        let state = SimulationState::new(vec![agent.clone()]);

        // Evaluate strategic collateral
        let decision = policy
            .evaluate_strategic_collateral(&agent, &state, 10, &cost_rates)
            .unwrap();

        // Should return PostCollateral decision
        assert!(matches!(
            decision,
            CollateralDecision::Post { amount: 100000, .. }
        ));
    }

    #[test]
    fn test_evaluate_strategic_collateral_without_tree() {
        use crate::policy::CollateralDecision;

        // Create tree WITHOUT strategic_collateral_tree
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_no_strategic".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "P1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let cost_rates = CostRates::default();
        let mut policy = TreePolicy::new(tree);

        // Create test state
        let agent = Agent::new("BANK_A".to_string(), 100_000, 0);
        let state = SimulationState::new(vec![agent.clone()]);

        // Evaluate strategic collateral
        let decision = policy
            .evaluate_strategic_collateral(&agent, &state, 10, &cost_rates)
            .unwrap();

        // Should return Hold (default when tree not defined)
        assert_eq!(decision, CollateralDecision::Hold);
    }

    #[test]
    fn test_evaluate_end_of_tick_collateral_with_tree() {
        use crate::policy::CollateralDecision;

        // Create tree with end_of_tick_collateral_tree that withdraws posted collateral
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_eot_collateral".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "P1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: Some(TreeNode::Action {
                node_id: "E1".to_string(),
                action: ActionType::WithdrawCollateral,
                parameters: {
                    let mut params = HashMap::new();
                    params.insert(
                        "amount".to_string(),
                        ValueOrCompute::Field {
                            field: "posted_collateral".to_string(),
                        },
                    );
                    params.insert(
                        "reason".to_string(),
                        ValueOrCompute::Direct {
                            value: json!("EndOfDayCleanup"),
                        },
                    );
                    params
                },
            }),
            parameters: HashMap::new(),
        };

        let cost_rates = CostRates::default();
        let mut policy = TreePolicy::new(tree);

        // Create test state with agent that has posted collateral
        let mut agent = Agent::new("BANK_A".to_string(), 100_000, 0);
        agent.set_posted_collateral(50000);
        let state = SimulationState::new(vec![agent.clone()]);

        // Evaluate end-of-tick collateral
        let decision = policy
            .evaluate_end_of_tick_collateral(&agent, &state, 10, &cost_rates)
            .unwrap();

        // Should return WithdrawCollateral decision for the posted amount
        assert!(matches!(
            decision,
            CollateralDecision::Withdraw { amount: 50000, .. }
        ));
    }

    #[test]
    fn test_evaluate_end_of_tick_collateral_without_tree() {
        use crate::policy::CollateralDecision;

        // Create tree WITHOUT end_of_tick_collateral_tree
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_no_eot".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "P1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: None,
            parameters: HashMap::new(),
        };

        let cost_rates = CostRates::default();
        let mut policy = TreePolicy::new(tree);

        // Create test state
        let agent = Agent::new("BANK_A".to_string(), 100_000, 0);
        let state = SimulationState::new(vec![agent.clone()]);

        // Evaluate end-of-tick collateral
        let decision = policy
            .evaluate_end_of_tick_collateral(&agent, &state, 10, &cost_rates)
            .unwrap();

        // Should return Hold (default when tree not defined)
        assert_eq!(decision, CollateralDecision::Hold);
    }

    #[test]
    fn test_evaluate_end_of_tick_collateral_with_condition() {
        use crate::policy::CollateralDecision;

        // Create tree with conditional end-of-tick logic:
        // If queue2_size == 0: Withdraw all collateral
        // Else: Hold collateral
        let tree = DecisionTreeDef {
            version: "1.0".to_string(),
            policy_id: "test_conditional_eot".to_string(),
            description: None,
            payment_tree: Some(TreeNode::Action {
                node_id: "P1".to_string(),
                action: ActionType::Release,
                parameters: HashMap::new(),
            }),
            strategic_collateral_tree: None,
            end_of_tick_collateral_tree: Some(TreeNode::Condition {
                node_id: "E1".to_string(),
                description: "Check if RTGS queue is empty".to_string(),
                condition: Expression::Equal {
                    left: Value::Field {
                        field: "queue2_size".to_string(),
                    },
                    right: Value::Literal { value: json!(0) },
                },
                on_true: Box::new(TreeNode::Action {
                    node_id: "E2".to_string(),
                    action: ActionType::WithdrawCollateral,
                    parameters: {
                        let mut params = HashMap::new();
                        params.insert(
                            "amount".to_string(),
                            ValueOrCompute::Field {
                                field: "posted_collateral".to_string(),
                            },
                        );
                        params.insert(
                            "reason".to_string(),
                            ValueOrCompute::Direct {
                                value: json!("EndOfDayCleanup"),
                            },
                        );
                        params
                    },
                }),
                on_false: Box::new(TreeNode::Action {
                    node_id: "E3".to_string(),
                    action: ActionType::HoldCollateral,
                    parameters: HashMap::new(),
                }),
            }),
            parameters: HashMap::new(),
        };

        let cost_rates = CostRates::default();
        let mut policy = TreePolicy::new(tree);

        // Create test state with empty RTGS queue and posted collateral
        let mut agent = Agent::new("BANK_A".to_string(), 100_000, 0);
        agent.set_posted_collateral(75000);
        let state = SimulationState::new(vec![agent.clone()]);

        // Evaluate end-of-tick collateral (queue2_size = 0, so should withdraw)
        let decision = policy
            .evaluate_end_of_tick_collateral(&agent, &state, 10, &cost_rates)
            .unwrap();

        // Should return WithdrawCollateral decision
        assert!(matches!(
            decision,
            CollateralDecision::Withdraw { amount: 75000, .. }
        ));
    }
}
