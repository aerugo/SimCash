//! Checkpoint - Save/Load Simulation State
//!
//! Enables serialization and deserialization of complete orchestrator state
//! for pause/resume functionality.
//!
//! # Critical Invariants
//!
//! - **Determinism**: Same seed + config produces identical results
//! - **Balance Conservation**: Total agent balance preserved
//! - **Queue Integrity**: No orphaned or duplicate transactions
//! - **Config Matching**: State can only be loaded with matching config

use crate::models::agent::Agent;
use crate::models::transaction::{Transaction, TransactionStatus};
use crate::orchestrator::SimulationError;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashMap;

// ============================================================================
// Snapshot Structures
// ============================================================================

/// Complete orchestrator state snapshot
///
/// This structure captures all state necessary to resume a simulation
/// from an arbitrary point in time.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateSnapshot {
    /// Current tick position
    pub current_tick: usize,

    /// Current day position
    pub current_day: usize,

    /// RNG seed at time of snapshot (CRITICAL for determinism)
    pub rng_seed: u64,

    /// All agent states
    pub agents: Vec<AgentSnapshot>,

    /// All transaction states
    pub transactions: Vec<TransactionSnapshot>,

    /// Queue 2 (RTGS queue) transaction IDs
    pub rtgs_queue: Vec<String>,

    /// SHA256 hash of original config (for validation)
    pub config_hash: String,
}

/// Agent state snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentSnapshot {
    pub id: String,
    pub balance: i64,
    pub credit_limit: i64,
    pub outgoing_queue: Vec<String>, // Queue 1 (internal)
    pub incoming_expected: Vec<String>,
    pub last_decision_tick: Option<usize>,
    pub liquidity_buffer: i64,
    pub posted_collateral: i64,
    pub collateral_haircut: f64,
    pub collateral_posted_at_tick: Option<usize>,
}

impl From<&Agent> for AgentSnapshot {
    fn from(agent: &Agent) -> Self {
        AgentSnapshot {
            id: agent.id().to_string(),
            balance: agent.balance(),
            credit_limit: agent.credit_limit(),
            outgoing_queue: agent.outgoing_queue().to_vec(),
            incoming_expected: agent.incoming_expected().to_vec(),
            last_decision_tick: agent.last_decision_tick(),
            liquidity_buffer: agent.liquidity_buffer(),
            posted_collateral: agent.posted_collateral(),
            collateral_haircut: agent.collateral_haircut(),
            collateral_posted_at_tick: agent.collateral_posted_at_tick(),
        }
    }
}

impl From<AgentSnapshot> for Agent {
    fn from(snapshot: AgentSnapshot) -> Self {
        Agent::from_snapshot(
            snapshot.id,
            snapshot.balance,
            snapshot.credit_limit,
            snapshot.outgoing_queue,
            snapshot.incoming_expected,
            snapshot.last_decision_tick,
            snapshot.liquidity_buffer,
            snapshot.posted_collateral,
            snapshot.collateral_haircut,
            snapshot.collateral_posted_at_tick,
        )
    }
}

/// Transaction state snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransactionSnapshot {
    pub id: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub amount: i64,
    pub remaining_amount: i64,
    pub arrival_tick: usize,
    pub deadline_tick: usize,
    pub priority: u8,
    pub status: TransactionStatus,
    pub parent_id: Option<String>,
}

impl From<&Transaction> for TransactionSnapshot {
    fn from(tx: &Transaction) -> Self {
        TransactionSnapshot {
            id: tx.id().to_string(),
            sender_id: tx.sender_id().to_string(),
            receiver_id: tx.receiver_id().to_string(),
            amount: tx.amount(),
            remaining_amount: tx.remaining_amount(),
            arrival_tick: tx.arrival_tick(),
            deadline_tick: tx.deadline_tick(),
            priority: tx.priority(),
            status: tx.status().clone(),
            parent_id: tx.parent_id().map(|s| s.to_string()),
        }
    }
}

impl From<TransactionSnapshot> for Transaction {
    fn from(snapshot: TransactionSnapshot) -> Self {
        Transaction::from_snapshot(
            snapshot.id,
            snapshot.sender_id,
            snapshot.receiver_id,
            snapshot.amount,
            snapshot.remaining_amount,
            snapshot.arrival_tick,
            snapshot.deadline_tick,
            snapshot.priority,
            snapshot.status,
            snapshot.parent_id,
        )
    }
}

// ============================================================================
// Config Hashing
// ============================================================================

/// Compute deterministic SHA256 hash of config
///
/// This hash is used to verify that a checkpoint's config matches
/// the config used to restore it.
///
/// Uses canonical JSON serialization with sorted keys to ensure
/// deterministic hashing regardless of HashMap iteration order.
pub fn compute_config_hash<T: Serialize>(config: &T) -> Result<String, SimulationError> {
    use serde_json::Value;
    use std::collections::BTreeMap;

    // First serialize to serde_json::Value
    let value = serde_json::to_value(config).map_err(|e| {
        SimulationError::SerializationError(format!("Config serialization failed: {}", e))
    })?;

    // Recursively sort all object keys for canonical representation
    fn canonicalize(value: Value) -> Value {
        match value {
            Value::Object(map) => {
                // Convert HashMap to BTreeMap (sorted keys)
                let sorted: BTreeMap<String, Value> =
                    map.into_iter().map(|(k, v)| (k, canonicalize(v))).collect();
                Value::Object(sorted.into_iter().collect())
            }
            Value::Array(arr) => Value::Array(arr.into_iter().map(canonicalize).collect()),
            other => other,
        }
    }

    let canonical_value = canonicalize(value);

    // Serialize to JSON string (now with sorted keys)
    let json = serde_json::to_string(&canonical_value).map_err(|e| {
        SimulationError::SerializationError(format!("Config serialization failed: {}", e))
    })?;

    // Compute SHA256 hash
    let mut hasher = Sha256::new();
    hasher.update(json.as_bytes());
    let result = hasher.finalize();

    Ok(format!("{:x}", result))
}

// ============================================================================
// Validation Functions
// ============================================================================

/// Validate state snapshot integrity
///
/// Checks critical invariants:
/// - Balance conservation
/// - Transaction referential integrity
/// - Queue uniqueness (no duplicates)
pub fn validate_snapshot(
    snapshot: &StateSnapshot,
    expected_total_balance: i64,
) -> Result<(), SimulationError> {
    // 1. Balance conservation
    let total_balance: i64 = snapshot.agents.iter().map(|a| a.balance).sum();
    if total_balance != expected_total_balance {
        return Err(SimulationError::StateValidationError(format!(
            "Balance conservation violated: expected {}, got {}",
            expected_total_balance, total_balance
        )));
    }

    // 2. Transaction referential integrity
    let tx_ids: HashMap<_, _> = snapshot
        .transactions
        .iter()
        .map(|t| (t.id.clone(), ()))
        .collect();

    // Check Queue 1 (agent queues)
    for agent in &snapshot.agents {
        for tx_id in &agent.outgoing_queue {
            if !tx_ids.contains_key(tx_id) {
                return Err(SimulationError::StateValidationError(format!(
                    "Orphaned transaction in agent {} queue: {}",
                    agent.id, tx_id
                )));
            }
        }
    }

    // Check Queue 2 (RTGS queue)
    for tx_id in &snapshot.rtgs_queue {
        if !tx_ids.contains_key(tx_id) {
            return Err(SimulationError::StateValidationError(format!(
                "Orphaned transaction in RTGS queue: {}",
                tx_id
            )));
        }
    }

    // 3. Queue uniqueness (no transaction in multiple queues)
    let mut seen = HashMap::new();
    for agent in &snapshot.agents {
        for tx_id in &agent.outgoing_queue {
            if let Some(prev_location) = seen.insert(tx_id.clone(), format!("agent {}", agent.id)) {
                return Err(SimulationError::StateValidationError(format!(
                    "Duplicate transaction {} in multiple queues: {} and agent {}",
                    tx_id, prev_location, agent.id
                )));
            }
        }
    }

    for tx_id in &snapshot.rtgs_queue {
        if let Some(prev_location) = seen.insert(tx_id.clone(), "RTGS queue".to_string()) {
            return Err(SimulationError::StateValidationError(format!(
                "Duplicate transaction {} in multiple queues: {} and RTGS queue",
                tx_id, prev_location
            )));
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compute_config_hash_deterministic() {
        #[derive(Serialize)]
        struct TestConfig {
            value: i32,
            name: String,
        }

        let config1 = TestConfig {
            value: 42,
            name: "test".to_string(),
        };

        let config2 = TestConfig {
            value: 42,
            name: "test".to_string(),
        };

        let hash1 = compute_config_hash(&config1).unwrap();
        let hash2 = compute_config_hash(&config2).unwrap();

        assert_eq!(hash1, hash2, "Same config should produce same hash");
    }

    #[test]
    fn test_compute_config_hash_different_for_different_configs() {
        #[derive(Serialize)]
        struct TestConfig {
            value: i32,
        }

        let config1 = TestConfig { value: 42 };
        let config2 = TestConfig { value: 43 };

        let hash1 = compute_config_hash(&config1).unwrap();
        let hash2 = compute_config_hash(&config2).unwrap();

        assert_ne!(
            hash1, hash2,
            "Different configs should produce different hashes"
        );
    }
}
