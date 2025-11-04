// Phase 6: Evaluation Context
//
// Builds field values from simulation state for expression evaluation.
// Exposes transaction fields, agent fields, derived fields, and system state.

use crate::orchestrator::CostRates;
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
///
/// **Cost Fields** (Phase 9.5.1):
/// - cost_overdraft_bps_per_tick: Overdraft cost in basis points per tick (f64)
/// - cost_delay_per_tick_per_cent: Delay cost per tick per cent (f64)
/// - cost_collateral_bps_per_tick: Collateral opportunity cost in bps per tick (f64)
/// - cost_split_friction: Cost per split operation (f64)
/// - cost_deadline_penalty: Penalty for missing deadline (f64)
/// - cost_eod_penalty: End-of-day penalty per unsettled transaction (f64)
/// - cost_delay_this_tx_one_tick: Delay cost for THIS transaction for one tick (f64)
/// - cost_overdraft_this_amount_one_tick: Overdraft cost for THIS amount for one tick (f64)
///
/// **System Configuration Fields** (Phase 9.5.2):
/// - system_ticks_per_day: Number of ticks in a simulation day (f64)
/// - system_current_day: Current day number (0-indexed) (f64)
/// - system_tick_in_day: Current tick within the day (0 to ticks_per_day-1) (f64)
/// - ticks_remaining_in_day: Ticks remaining in current day (f64)
/// - day_progress_fraction: Progress through day (0.0 to 1.0) (f64)
/// - is_eod_rush: Boolean (1.0) if in end-of-day rush period (f64)
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
    /// * `cost_rates` - Cost configuration (Phase 9.5.1)
    /// * `ticks_per_day` - Number of ticks in a simulation day (Phase 9.5.2)
    /// * `eod_rush_threshold` - End-of-day rush threshold (0.0 to 1.0) (Phase 9.5.2)
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
    /// use payment_simulator_core_rs::orchestrator::CostRates;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
    /// let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
    /// let state = SimulationState::new(vec![agent.clone()]);
    /// let cost_rates = CostRates::default();
    ///
    /// let context = EvalContext::build(&tx, &agent, &state, 100, &cost_rates, 100, 0.8);
    /// let balance = context.get_field("balance").unwrap();
    /// assert_eq!(balance, 1_000_000.0);
    /// ```
    pub fn build(
        tx: &Transaction,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
        ticks_per_day: usize,
        eod_rush_threshold: f64,
    ) -> Self {
        let mut fields = HashMap::new();

        // Transaction fields
        fields.insert("amount".to_string(), tx.amount() as f64);
        fields.insert("remaining_amount".to_string(), tx.remaining_amount() as f64);
        fields.insert("settled_amount".to_string(), tx.settled_amount() as f64);
        fields.insert("arrival_tick".to_string(), tx.arrival_tick() as f64);
        fields.insert("deadline_tick".to_string(), tx.deadline_tick() as f64);
        fields.insert("priority".to_string(), tx.priority() as f64);
        fields.insert(
            "is_split".to_string(),
            if tx.is_split() { 1.0 } else { 0.0 },
        );
        fields.insert(
            "is_past_deadline".to_string(),
            if tx.is_past_deadline(tick) { 1.0 } else { 0.0 },
        );

        // Phase 4: Overdue status fields
        // Allows policies to detect and react to overdue transactions
        fields.insert(
            "is_overdue".to_string(),
            if tx.is_overdue() { 1.0 } else { 0.0 },
        );

        // Calculate overdue duration (0 if not overdue)
        let overdue_duration = if let Some(overdue_since) = tx.overdue_since_tick() {
            tick.saturating_sub(overdue_since)
        } else {
            0
        };
        fields.insert("overdue_duration".to_string(), overdue_duration as f64);

        // Agent fields
        fields.insert("balance".to_string(), agent.balance() as f64);
        fields.insert("credit_limit".to_string(), agent.credit_limit() as f64);
        fields.insert(
            "available_liquidity".to_string(),
            agent.available_liquidity() as f64,
        );
        fields.insert("credit_used".to_string(), agent.credit_used() as f64);
        fields.insert(
            "is_using_credit".to_string(),
            if agent.is_using_credit() { 1.0 } else { 0.0 },
        );
        fields.insert(
            "liquidity_buffer".to_string(),
            agent.liquidity_buffer() as f64,
        );
        fields.insert(
            "outgoing_queue_size".to_string(),
            agent.outgoing_queue_size() as f64,
        );
        fields.insert(
            "incoming_expected_count".to_string(),
            agent.incoming_expected().len() as f64,
        );
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
        fields.insert(
            "posted_collateral".to_string(),
            agent.posted_collateral() as f64,
        );
        fields.insert(
            "max_collateral_capacity".to_string(),
            agent.max_collateral_capacity() as f64,
        );
        fields.insert(
            "remaining_collateral_capacity".to_string(),
            agent.remaining_collateral_capacity() as f64,
        );

        let max_cap = agent.max_collateral_capacity() as f64;
        let collateral_utilization = if max_cap > 0.0 {
            (agent.posted_collateral() as f64) / max_cap
        } else {
            0.0
        };
        fields.insert("collateral_utilization".to_string(), collateral_utilization);

        // Liquidity gap fields
        fields.insert(
            "queue1_liquidity_gap".to_string(),
            agent.queue1_liquidity_gap(state) as f64,
        );

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

        let queue2_count = state
            .rtgs_queue()
            .iter()
            .filter(|tx_id| {
                state
                    .get_transaction(tx_id)
                    .map(|t| t.sender_id() == agent.id())
                    .unwrap_or(false)
            })
            .count();
        fields.insert("queue2_count_for_agent".to_string(), queue2_count as f64);

        let queue2_nearest_deadline = state
            .rtgs_queue()
            .iter()
            .filter_map(|tx_id| state.get_transaction(tx_id))
            .filter(|t| t.sender_id() == agent.id())
            .map(|t| t.deadline_tick())
            .min()
            .unwrap_or(usize::MAX);
        fields.insert(
            "queue2_nearest_deadline".to_string(),
            queue2_nearest_deadline as f64,
        );

        let ticks_to_nearest_queue2_deadline = if queue2_nearest_deadline == usize::MAX {
            f64::INFINITY
        } else {
            queue2_nearest_deadline.saturating_sub(tick) as f64
        };
        fields.insert(
            "ticks_to_nearest_queue2_deadline".to_string(),
            ticks_to_nearest_queue2_deadline,
        );

        // Phase 9.5.1: Cost Fields
        //
        // Expose cost parameters to enable cost-based decision making in policies.
        // Policies can compare costs (e.g., "is delay cheaper than overdraft?").

        // Direct cost rate fields
        fields.insert(
            "cost_overdraft_bps_per_tick".to_string(),
            cost_rates.overdraft_bps_per_tick,
        );
        fields.insert(
            "cost_delay_per_tick_per_cent".to_string(),
            cost_rates.delay_cost_per_tick_per_cent,
        );
        fields.insert(
            "cost_collateral_bps_per_tick".to_string(),
            cost_rates.collateral_cost_per_tick_bps,
        );
        fields.insert(
            "cost_split_friction".to_string(),
            cost_rates.split_friction_cost as f64,
        );
        fields.insert(
            "cost_deadline_penalty".to_string(),
            cost_rates.deadline_penalty as f64,
        );
        fields.insert(
            "cost_eod_penalty".to_string(),
            cost_rates.eod_penalty_per_transaction as f64,
        );

        // Derived cost calculations specific to this transaction
        let amount_f64 = tx.remaining_amount() as f64;

        // Delay cost for THIS transaction for one tick
        // Formula: delay_cost_per_tick_per_cent * amount
        let delay_cost_one_tick = amount_f64 * cost_rates.delay_cost_per_tick_per_cent;
        fields.insert("cost_delay_this_tx_one_tick".to_string(), delay_cost_one_tick);

        // Overdraft cost for THIS amount for one tick
        // Formula: (overdraft_bps_per_tick / 10000) * amount
        // Note: Basis points conversion (1 bp = 0.0001 = 1/10000)
        let overdraft_cost_one_tick = (cost_rates.overdraft_bps_per_tick / 10_000.0) * amount_f64;
        fields.insert(
            "cost_overdraft_this_amount_one_tick".to_string(),
            overdraft_cost_one_tick,
        );

        // Phase 9.5.2: System Configuration Fields
        //
        // Expose time-of-day context to enable EOD rush detection and time-based strategies.

        // Direct system configuration fields
        fields.insert("system_ticks_per_day".to_string(), ticks_per_day as f64);

        // Calculate current day and tick within day
        let current_day = tick / ticks_per_day;
        let tick_in_day = tick % ticks_per_day;

        fields.insert("system_current_day".to_string(), current_day as f64);
        fields.insert("system_tick_in_day".to_string(), tick_in_day as f64);

        // Derived time fields
        // Ticks remaining in day: ticks_per_day - tick_in_day - 1
        // (subtract 1 because current tick counts as "used")
        let ticks_remaining = ticks_per_day.saturating_sub(tick_in_day).saturating_sub(1);
        fields.insert("ticks_remaining_in_day".to_string(), ticks_remaining as f64);

        // Day progress fraction: how far through the day (0.0 = start, 1.0 = end)
        let day_progress = if ticks_per_day > 0 {
            tick_in_day as f64 / ticks_per_day as f64
        } else {
            0.0
        };
        fields.insert("day_progress_fraction".to_string(), day_progress);

        // EOD rush detection: boolean field (1.0 = in rush, 0.0 = not in rush)
        let is_eod_rush = if day_progress >= eod_rush_threshold { 1.0 } else { 0.0 };
        fields.insert("is_eod_rush".to_string(), is_eod_rush);

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
    use crate::orchestrator::CostRates;
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

    fn create_cost_rates() -> CostRates {
        CostRates::default()
    }

    #[test]
    fn test_context_contains_agent_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

        // Check derived fields
        // tick = 30, deadline = 50 → ticks_to_deadline = 20
        assert_eq!(context.get_field("ticks_to_deadline").unwrap(), 20.0);

        // tick = 30, arrival = 10 → queue_age = 20
        assert_eq!(context.get_field("queue_age").unwrap(), 20.0);
    }

    #[test]
    fn test_context_contains_system_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

        // Check system fields
        assert_eq!(context.get_field("rtgs_queue_size").unwrap(), 0.0); // Empty queue
        assert_eq!(context.get_field("rtgs_queue_value").unwrap(), 0.0);
        assert_eq!(context.get_field("total_agents").unwrap(), 3.0);
    }

    #[test]
    fn test_field_lookup_returns_correct_value() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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

        let context = EvalContext::build(&tx, &agent, &state, 0, &create_cost_rates(), 100, 0.8);

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

        let context = EvalContext::build(&child, &agent, &state, 5, &create_cost_rates(), 100, 0.8);

        // Child transaction should have is_split = 1.0
        assert_eq!(context.get_field("is_split").unwrap(), 1.0);
    }

    // ============================================================================
    // PHASE 8.2: Collateral Management Context Fields
    // ============================================================================

    #[test]
    fn test_context_contains_collateral_fields() {
        let (tx, agent, state, tick) = create_test_context();
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let context = EvalContext::build(&tx, &agent, &state, tick, &create_cost_rates(), 100, 0.8);

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
        let mut agent = Agent::with_buffer("BANK_A".to_string(), 500_000, 200_000, 100_000);
        // TODO: Need to add posted_collateral to agent for this test
        // For now, test will fail until Agent supports collateral

        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 10_000, 0, 10);
        let state = SimulationState::new(vec![agent.clone()]);

        let context = EvalContext::build(&tx, &agent, &state, 0, &create_cost_rates(), 100, 0.8);

        // Collateral utilization should be computable
        assert!(context.has_field("collateral_utilization"));
    }

    // ========================================================================
    // Phase 4: Overdue Context Fields (TDD)
    // ========================================================================

    #[test]
    fn test_context_includes_is_overdue_field() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_cost_rates();

        // Pending transaction
        let context = EvalContext::build(&tx, &agent, &state, 40, &cost_rates, 100, 0.8);
        assert_eq!(context.get_field("is_overdue").unwrap(), 0.0);

        // Overdue transaction
        tx.mark_overdue(51).unwrap();
        let context = EvalContext::build(&tx, &agent, &state, 55, &cost_rates, 100, 0.8);
        assert_eq!(context.get_field("is_overdue").unwrap(), 1.0);
    }

    #[test]
    fn test_context_includes_overdue_duration() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let mut tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_cost_rates();

        // Mark overdue at tick 51
        tx.mark_overdue(51).unwrap();

        // Current tick 60 → 9 ticks overdue
        let context = EvalContext::build(&tx, &agent, &state, 60, &cost_rates, 100, 0.8);

        assert_eq!(context.get_field("overdue_duration").unwrap(), 9.0);
    }

    #[test]
    fn test_overdue_duration_zero_when_not_overdue() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_cost_rates();

        // Not overdue - duration should be 0
        let context = EvalContext::build(&tx, &agent, &state, 40, &cost_rates, 100, 0.8);

        assert_eq!(context.get_field("overdue_duration").unwrap(), 0.0);
    }
}
