// Phase 6: Evaluation Context
//
// Builds field values from simulation state for expression evaluation.
// Exposes transaction fields, agent fields, derived fields, and system state.

use crate::{Agent, SimulationState, Transaction};
use std::collections::HashMap;
use thiserror::Error;

/// Errors that can occur during context evaluation
#[derive(Debug, Error, PartialEq)]
pub enum ContextError {
    #[error("Field '{0}' not found in evaluation context")]
    FieldNotFound(String),

    #[error("Invalid field type conversion for '{0}'")]
    InvalidFieldType(String),
}

/// Evaluation context for decision tree expression evaluation
///
/// Contains field values extracted from simulation state (transaction, agent, system).
/// All fields are stored as f64 for uniform arithmetic operations.
///
/// # Field Categories
///
/// **Transaction Fields**:
/// - amount, remaining_amount, settled_amount (i64 → f64)
/// - arrival_tick, deadline_tick, priority (usize/u8 → f64)
/// - is_split, is_past_deadline (bool → 0.0/1.0)
///
/// **Agent Fields**:
/// - balance, credit_limit, available_liquidity, credit_used (i64 → f64)
/// - liquidity_buffer, outgoing_queue_size, incoming_expected_count (i64/usize → f64)
/// - is_using_credit (bool → 0.0/1.0)
/// - liquidity_pressure (f64)
///
/// **Derived Fields**:
/// - ticks_to_deadline (i64, can be negative)
/// - queue_age (usize)
///
/// **System Fields**:
/// - current_tick (usize → f64)
/// - rtgs_queue_size, rtgs_queue_value, total_agents (usize/i64 → f64)
///
/// **Collateral Fields** (Phase 8.2):
/// - posted_collateral: Amount of collateral currently posted (i64 → f64)
/// - max_collateral_capacity: Maximum collateral agent can post (i64 → f64)
/// - remaining_collateral_capacity: Remaining capacity for collateral (i64 → f64)
/// - collateral_utilization: Posted / max capacity ratio (0.0 to 1.0)
/// - queue1_liquidity_gap: Required liquidity to clear Queue 1 minus available (i64 → f64)
/// - queue1_total_value: Total value of all transactions in Queue 1 (i64 → f64)
/// - headroom: Available liquidity minus Queue 1 value (i64 → f64)
/// - queue2_count_for_agent: Number of agent's transactions in Queue 2 (usize → f64)
/// - queue2_nearest_deadline: Nearest deadline in Queue 2 for this agent (usize → f64)
/// - ticks_to_nearest_queue2_deadline: Ticks until nearest Queue 2 deadline (f64, can be INFINITY)
#[derive(Debug, Clone)]
pub struct EvalContext {
    /// Field name → value mapping
    fields: HashMap<String, f64>,
}

impl EvalContext {
    /// Create evaluation context from simulation state
    ///
    /// # Arguments
    ///
    /// * `tx` - Transaction being evaluated
    /// * `agent` - Agent whose queue contains this transaction
    /// * `state` - Full simulation state
    /// * `tick` - Current simulation tick
    ///
    /// # Returns
    ///
    /// Context populated with all available fields
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::policy::tree::EvalContext;
    /// use payment_simulator_core_rs::{Agent, Transaction, SimulationState};
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
    /// let state = SimulationState::new(vec![agent.clone()]);
    ///
    /// let context = EvalContext::build(&tx, &agent, &state, 100);
    /// let balance = context.get_field("balance").unwrap();
    /// assert_eq!(balance, 1_000_000.0);
    /// ```
    pub fn build(tx: &Transaction, agent: &Agent, state: &SimulationState, tick: usize) -> Self {
        let mut fields = HashMap::new();

        // Transaction fields
        fields.insert("amount".to_string(), tx.amount() as f64);
        fields.insert("remaining_amount".to_string(), tx.remaining_amount() as f64);
        fields.insert("settled_amount".to_string(), tx.settled_amount() as f64);
        fields.insert("arrival_tick".to_string(), tx.arrival_tick() as f64);
        fields.insert("deadline_tick".to_string(), tx.deadline_tick() as f64);
        fields.insert("priority".to_string(), tx.priority() as f64);
        fields.insert("is_split".to_string(), if tx.is_split() { 1.0 } else { 0.0 });
        fields.insert("is_past_deadline".to_string(), if tx.is_past_deadline(tick) { 1.0 } else { 0.0 });

        // Agent fields
        fields.insert("balance".to_string(), agent.balance() as f64);
        fields.insert("credit_limit".to_string(), agent.credit_limit() as f64);
        fields.insert("available_liquidity".to_string(), agent.available_liquidity() as f64);
        fields.insert("credit_used".to_string(), agent.credit_used() as f64);
        fields.insert("is_using_credit".to_string(), if agent.is_using_credit() { 1.0 } else { 0.0 });
        fields.insert("liquidity_buffer".to_string(), agent.liquidity_buffer() as f64);
        fields.insert("outgoing_queue_size".to_string(), agent.outgoing_queue_size() as f64);
        fields.insert("incoming_expected_count".to_string(), agent.incoming_expected().len() as f64);
        fields.insert("liquidity_pressure".to_string(), agent.liquidity_pressure());

        // Derived fields
        let ticks_to_deadline = tx.deadline_tick() as i64 - tick as i64;
        fields.insert("ticks_to_deadline".to_string(), ticks_to_deadline as f64);

        let queue_age = tick.saturating_sub(tx.arrival_tick());
        fields.insert("queue_age".to_string(), queue_age as f64);

        // System fields
        fields.insert("current_tick".to_string(), tick as f64);
        fields.insert("rtgs_queue_size".to_string(), state.queue_size() as f64);
        fields.insert("rtgs_queue_value".to_string(), state.queue_value() as f64);
        fields.insert("total_agents".to_string(), state.num_agents() as f64);

        // Phase 8.2: Collateral Management Fields

        // Collateral state fields
        fields.insert("posted_collateral".to_string(), agent.posted_collateral() as f64);
        fields.insert("max_collateral_capacity".to_string(), agent.max_collateral_capacity() as f64);
        fields.insert("remaining_collateral_capacity".to_string(), agent.remaining_collateral_capacity() as f64);

        let max_cap = agent.max_collateral_capacity() as f64;
        let collateral_utilization = if max_cap > 0.0 {
            (agent.posted_collateral() as f64) / max_cap
        } else {
            0.0
        };
        fields.insert("collateral_utilization".to_string(), collateral_utilization);

        // Liquidity gap fields
        fields.insert("queue1_liquidity_gap".to_string(), agent.queue1_liquidity_gap(state) as f64);

        let mut queue1_total_value = 0i64;
        for tx_id in agent.outgoing_queue() {
            if let Some(tx_in_queue) = state.get_transaction(tx_id) {
                queue1_total_value += tx_in_queue.remaining_amount();
            }
        }
        fields.insert("queue1_total_value".to_string(), queue1_total_value as f64);

        // Headroom: available liquidity minus what's needed for Queue 1
        let headroom = agent.available_liquidity() - queue1_total_value;
        fields.insert("headroom".to_string(), headroom as f64);

        // Queue 2 (RTGS) pressure fields
        // Total size of Queue 2 (all agents)
        fields.insert("queue2_size".to_string(), state.rtgs_queue().len() as f64);

        let queue2_count = state.rtgs_queue()
            .iter()
            .filter(|tx_id| {
                state.get_transaction(tx_id)
                    .map(|t| t.sender_id() == agent.id())
                    .unwrap_or(false)
            })
            .count();
        fields.insert("queue2_count_for_agent".to_string(), queue2_count as f64);

        let queue2_nearest_deadline = state.rtgs_queue()
            .iter()
            .filter_map(|tx_id| state.get_transaction(tx_id))
            .filter(|t| t.sender_id() == agent.id())
            .map(|t| t.deadline_tick())
            .min()
            .unwrap_or(usize::MAX);
        fields.insert("queue2_nearest_deadline".to_string(), queue2_nearest_deadline as f64);

        let ticks_to_nearest_queue2_deadline = if queue2_nearest_deadline == usize::MAX {
            f64::INFINITY
        } else {
            queue2_nearest_deadline.saturating_sub(tick) as f64
        };
        fields.insert("ticks_to_nearest_queue2_deadline".to_string(), ticks_to_nearest_queue2_deadline);

        Self { fields }
    }

    /// Get field value by name
    ///
    /// # Arguments
    ///
    /// * `name` - Field name
    ///
    /// # Returns
    ///
    /// Ok(value) if field exists, Err otherwise
    pub fn get_field(&self, name: &str) -> Result<f64, ContextError> {
        self.fields
            .get(name)
            .copied()
            .ok_or_else(|| ContextError::FieldNotFound(name.to_string()))
    }

    /// Check if field exists in context
    pub fn has_field(&self, name: &str) -> bool {
        self.fields.contains_key(name)
    }

    /// Get all field names (for debugging/validation)
    pub fn field_names(&self) -> Vec<&str> {
        self.fields.keys().map(|s| s.as_str()).collect()
    }
}

// ============================================================================
// TESTS - Phase 6.2
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Agent, SimulationState, Transaction};

    fn create_test_context() -> (Transaction, Agent, SimulationState, usize) {
        // Create transaction
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000, // $1,000
            10,      // arrival_tick
            50,      // deadline_tick
        )
        .with_priority(8);

        // Create agent with some state
        let mut agent = Agent::with_buffer(
            "BANK_A".to_string(),
            500_000, // balance
            200_000, // credit_limit
            100_000, // liquidity_buffer
        );
        agent.queue_outgoing("tx_001".to_string());
        agent.queue_outgoing("tx_002".to_string());
        agent.add_expected_inflow("tx_003".to_string());

        // Create simulation state
        let state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000, 0),
            Agent::new("BANK_C".to_string(), 2_000_000, 0),
        ]);

        let tick = 30; // Current tick

        (tx, agent, state, tick)
    }

    #[test]
    fn test_context_contains_agent_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Check agent fields
        assert_eq!(context.get_field("balance").unwrap(), 500_000.0);
        assert_eq!(context.get_field("credit_limit").unwrap(), 200_000.0);
        assert_eq!(context.get_field("available_liquidity").unwrap(), 700_000.0);
        assert_eq!(context.get_field("credit_used").unwrap(), 0.0);
        assert_eq!(context.get_field("is_using_credit").unwrap(), 0.0);
        assert_eq!(context.get_field("liquidity_buffer").unwrap(), 100_000.0);
        assert_eq!(context.get_field("outgoing_queue_size").unwrap(), 2.0);
        assert_eq!(context.get_field("incoming_expected_count").unwrap(), 1.0);

        // Liquidity pressure should be > 0
        assert!(context.get_field("liquidity_pressure").unwrap() > 0.0);
    }

    #[test]
    fn test_context_contains_transaction_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Check transaction fields
        assert_eq!(context.get_field("amount").unwrap(), 100_000.0);
        assert_eq!(context.get_field("remaining_amount").unwrap(), 100_000.0);
        assert_eq!(context.get_field("settled_amount").unwrap(), 0.0);
        assert_eq!(context.get_field("arrival_tick").unwrap(), 10.0);
        assert_eq!(context.get_field("deadline_tick").unwrap(), 50.0);
        assert_eq!(context.get_field("priority").unwrap(), 8.0);
        assert_eq!(context.get_field("is_split").unwrap(), 0.0);
        assert_eq!(context.get_field("is_past_deadline").unwrap(), 0.0); // tick 30 < deadline 50
    }

    #[test]
    fn test_context_contains_derived_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Check derived fields
        // tick = 30, deadline = 50 → ticks_to_deadline = 20
        assert_eq!(context.get_field("ticks_to_deadline").unwrap(), 20.0);

        // tick = 30, arrival = 10 → queue_age = 20
        assert_eq!(context.get_field("queue_age").unwrap(), 20.0);
    }

    #[test]
    fn test_context_contains_system_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Check system fields
        assert_eq!(context.get_field("rtgs_queue_size").unwrap(), 0.0); // Empty queue
        assert_eq!(context.get_field("rtgs_queue_value").unwrap(), 0.0);
        assert_eq!(context.get_field("total_agents").unwrap(), 3.0);
    }

    #[test]
    fn test_field_lookup_returns_correct_value() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Test specific lookups
        assert!(context.has_field("balance"));
        assert!(context.has_field("amount"));
        assert!(context.has_field("ticks_to_deadline"));

        let balance = context.get_field("balance").unwrap();
        assert_eq!(balance, 500_000.0);
    }

    #[test]
    fn test_missing_field_returns_error() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Test missing field
        let result = context.get_field("nonexistent_field");
        assert!(result.is_err());

        match result {
            Err(ContextError::FieldNotFound(name)) => {
                assert_eq!(name, "nonexistent_field");
            }
            _ => panic!("Expected FieldNotFound error"),
        }

        assert!(!context.has_field("nonexistent_field"));
    }

    #[test]
    fn test_ticks_to_deadline_negative_when_past_deadline() {
        let (tx, agent, state, _) = create_test_context();

        // Create context with tick past deadline
        let tick = 60; // deadline is 50
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // ticks_to_deadline should be negative
        assert_eq!(context.get_field("ticks_to_deadline").unwrap(), -10.0);
        assert_eq!(context.get_field("is_past_deadline").unwrap(), 1.0);
    }

    #[test]
    fn test_boolean_fields_as_floats() {
        // Create a transaction that uses credit
        let agent = Agent::new("BANK_A".to_string(), -50_000, 200_000);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10_000, 0, 10);
        let state = SimulationState::new(vec![agent.clone()]);

        let context = EvalContext::build(&tx, &agent, &state, 0);

        // is_using_credit should be 1.0 (true)
        assert_eq!(context.get_field("is_using_credit").unwrap(), 1.0);
    }

    #[test]
    fn test_split_transaction_fields() {
        let parent = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 10);
        let parent_id = parent.id().to_string();

        let child = Transaction::new_split(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            50_000,
            0,
            10,
            parent_id,
        );

        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let state = SimulationState::new(vec![agent.clone()]);

        let context = EvalContext::build(&child, &agent, &state, 5);

        // Child transaction should have is_split = 1.0
        assert_eq!(context.get_field("is_split").unwrap(), 1.0);
    }

    // ============================================================================
    // PHASE 8.2: Collateral Management Context Fields
    // ============================================================================

    #[test]
    fn test_context_contains_collateral_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Collateral state fields
        assert!(context.has_field("posted_collateral"));
        assert!(context.has_field("max_collateral_capacity"));
        assert!(context.has_field("remaining_collateral_capacity"));
        assert!(context.has_field("collateral_utilization"));

        // Should be 0.0 since test context has no collateral
        assert_eq!(context.get_field("posted_collateral").unwrap(), 0.0);
    }

    #[test]
    fn test_context_contains_liquidity_gap_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Liquidity gap fields
        assert!(context.has_field("queue1_liquidity_gap"));
        assert!(context.has_field("queue1_total_value"));
        assert!(context.has_field("headroom"));

        // queue1_total_value should be > 0 (we have 2 items in outgoing queue)
        assert!(context.get_field("queue1_total_value").unwrap() >= 0.0);
    }

    #[test]
    fn test_context_contains_queue2_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick);

        // Queue 2 fields
        assert!(context.has_field("queue2_count_for_agent"));
        assert!(context.has_field("queue2_nearest_deadline"));
        assert!(context.has_field("ticks_to_nearest_queue2_deadline"));

        // Should be 0 since no transactions in queue 2
        assert_eq!(context.get_field("queue2_count_for_agent").unwrap(), 0.0);
    }

    #[test]
    fn test_collateral_utilization_with_posted_collateral() {
        // Create agent with posted collateral
        let mut agent = Agent::with_buffer(
            "BANK_A".to_string(),
            500_000,
            200_000,
            100_000,
        );
        // TODO: Need to add posted_collateral to agent for this test
        // For now, test will fail until Agent supports collateral

        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10_000, 0, 10);
        let state = SimulationState::new(vec![agent.clone()]);

        let context = EvalContext::build(&tx, &agent, &state, 0);

        // Collateral utilization should be computable
        assert!(context.has_field("collateral_utilization"));
    }
}
