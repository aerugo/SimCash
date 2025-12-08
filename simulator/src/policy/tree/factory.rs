// Policy Factory - Phase 3
//
// Creates TreePolicy instances from PolicyConfig, handling:
// - JSON file loading from policies/ directory
// - Parameter injection from configuration
// - Error handling and validation

use crate::orchestrator::engine::PolicyConfig;
use crate::policy::tree::{TreePolicy, TreePolicyError};
use std::collections::HashMap;
use std::path::PathBuf;

/// Create a TreePolicy from PolicyConfig
///
/// Loads the appropriate JSON policy file and injects parameters from config.
///
/// # Arguments
///
/// * `config` - PolicyConfig enum variant specifying which policy and parameters
///
/// # Returns
///
/// Ok(TreePolicy) if successful, Err(TreePolicyError) otherwise
///
/// # Example
///
/// ```rust
/// use payment_simulator_core_rs::policy::tree::create_policy;
/// use payment_simulator_core_rs::orchestrator::PolicyConfig;
///
/// # fn main() -> Result<(), Box<dyn std::error::Error>> {
/// let config = PolicyConfig::Deadline { urgency_threshold: 10 };
/// let policy = create_policy(&config)?;
/// # Ok(())
/// # }
/// ```
pub fn create_policy(config: &PolicyConfig) -> Result<TreePolicy, TreePolicyError> {
    match config {
        PolicyConfig::Fifo => {
            // Load FIFO policy (no parameters)
            let path = policies_dir().join("fifo.json");
            TreePolicy::from_file(path)
        }

        PolicyConfig::Deadline { urgency_threshold } => {
            // Load Deadline policy and inject urgency_threshold
            let path = policies_dir().join("deadline.json");
            let mut policy = TreePolicy::from_file(path)?;

            let mut params = HashMap::new();
            params.insert("urgency_threshold".to_string(), *urgency_threshold as f64);
            policy.with_parameters(params);

            Ok(policy)
        }

        PolicyConfig::LiquidityAware {
            target_buffer,
            urgency_threshold,
        } => {
            // Load LiquidityAware policy and inject both parameters
            let path = policies_dir().join("liquidity_aware.json");
            let mut policy = TreePolicy::from_file(path)?;

            let mut params = HashMap::new();
            params.insert("target_buffer".to_string(), *target_buffer as f64);
            params.insert("urgency_threshold".to_string(), *urgency_threshold as f64);
            policy.with_parameters(params);

            Ok(policy)
        }

        PolicyConfig::LiquiditySplitting {
            max_splits,
            min_split_amount,
        } => {
            // Load LiquiditySplitting policy and inject parameters
            let path = policies_dir().join("liquidity_splitting.json");
            let mut policy = TreePolicy::from_file(path)?;

            let mut params = HashMap::new();
            params.insert("max_splits".to_string(), *max_splits as f64);
            params.insert("min_split_amount".to_string(), *min_split_amount as f64);
            policy.with_parameters(params);

            Ok(policy)
        }

        PolicyConfig::MockSplitting { num_splits } => {
            // Load MockSplitting policy and inject num_splits
            let path = policies_dir().join("mock_splitting.json");
            let mut policy = TreePolicy::from_file(path)?;

            let mut params = HashMap::new();
            params.insert("num_splits".to_string(), *num_splits as f64);
            policy.with_parameters(params);

            Ok(policy)
        }

        PolicyConfig::MockStaggerSplit {
            num_splits,
            stagger_first_now,
            stagger_gap_ticks,
            priority_boost_children,
        } => {
            // Create a simple policy that always returns StaggerSplit
            // This is a test-only policy, so we generate it dynamically
            let json = format!(
                r#"{{
                    "name": "MockStaggerSplit",
                    "description": "Test policy that always stagger splits",
                    "parameters": {{
                        "num_splits": {{"default": {}}},
                        "stagger_first_now": {{"default": {}}},
                        "stagger_gap_ticks": {{"default": {}}},
                        "priority_boost_children": {{"default": {}}}
                    }},
                    "payment_tree": {{
                        "type": "action",
                        "node_id": "A_StaggerSplit",
                        "action": "StaggerSplit",
                        "parameters": {{
                            "num_splits": {{"param": "num_splits"}},
                            "stagger_first_now": {{"param": "stagger_first_now"}},
                            "stagger_gap_ticks": {{"param": "stagger_gap_ticks"}},
                            "priority_boost_children": {{"param": "priority_boost_children"}}
                        }}
                    }}
                }}"#,
                *num_splits as f64,
                *stagger_first_now as f64,
                *stagger_gap_ticks as f64,
                *priority_boost_children as f64
            );

            TreePolicy::from_json(&json)
        }

        PolicyConfig::FromJson { json } => {
            // Parse custom JSON policy directly (for testing)
            TreePolicy::from_json(json)
        }
    }
}

/// Get the policies directory path
///
/// Resolves to `simulator/policies/` relative to project root.
/// When running tests from simulator/, this is just `policies/`.
fn policies_dir() -> PathBuf {
    // First try simulator/policies (when running from project root)
    let simulator_policies = PathBuf::from("simulator/policies");
    if simulator_policies.exists() {
        return simulator_policies;
    }

    // Fall back to policies/ (when running tests from simulator/ directory)
    PathBuf::from("policies")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_create_fifo_policy() {
        let config = PolicyConfig::Fifo;
        let policy = create_policy(&config).expect("Failed to create FIFO policy");
        assert_eq!(policy.policy_id(), "fifo_policy");
    }

    #[test]
    fn test_create_deadline_policy_with_default_threshold() {
        let config = PolicyConfig::Deadline {
            urgency_threshold: 5,
        };
        let policy = create_policy(&config).expect("Failed to create Deadline policy");
        assert_eq!(policy.policy_id(), "deadline_policy");

        // Verify parameter was injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("urgency_threshold"), Some(&5.0));
    }

    #[test]
    fn test_create_deadline_policy_with_custom_threshold() {
        let config = PolicyConfig::Deadline {
            urgency_threshold: 10,
        };
        let policy = create_policy(&config).expect("Failed to create Deadline policy");

        // Verify custom parameter was injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("urgency_threshold"), Some(&10.0));
    }

    #[test]
    fn test_create_liquidity_aware_policy() {
        let config = PolicyConfig::LiquidityAware {
            target_buffer: 100_000,
            urgency_threshold: 5,
        };
        let policy = create_policy(&config).expect("Failed to create LiquidityAware policy");
        assert_eq!(policy.policy_id(), "liquidity_aware_policy");

        // Verify both parameters were injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("target_buffer"), Some(&100_000.0));
        assert_eq!(tree.parameters.get("urgency_threshold"), Some(&5.0));
    }

    #[test]
    fn test_create_liquidity_aware_with_custom_params() {
        let config = PolicyConfig::LiquidityAware {
            target_buffer: 250_000,
            urgency_threshold: 10,
        };
        let policy = create_policy(&config).expect("Failed to create LiquidityAware policy");

        // Verify custom parameters were injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("target_buffer"), Some(&250_000.0));
        assert_eq!(tree.parameters.get("urgency_threshold"), Some(&10.0));
    }

    #[test]
    fn test_create_liquidity_splitting_policy() {
        let config = PolicyConfig::LiquiditySplitting {
            max_splits: 5,
            min_split_amount: 10_000,
        };
        let policy = create_policy(&config).expect("Failed to create LiquiditySplitting policy");
        assert_eq!(policy.policy_id(), "liquidity_splitting_policy");

        // Verify parameters were injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("max_splits"), Some(&5.0));
        assert_eq!(tree.parameters.get("min_split_amount"), Some(&10_000.0));
    }

    #[test]
    fn test_create_mock_splitting_policy() {
        let config = PolicyConfig::MockSplitting { num_splits: 3 };
        let policy = create_policy(&config).expect("Failed to create MockSplitting policy");
        assert_eq!(policy.policy_id(), "mock_splitting_policy");

        // Verify parameter was injected
        let tree = policy.tree();
        assert_eq!(tree.parameters.get("num_splits"), Some(&3.0));
    }
}
