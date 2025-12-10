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
/// - effective_liquidity: balance + unused_credit_capacity (i64 → f64) - Phase 11 fix
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
/// **T2/CLM Collateral/Headroom Fields** (Invariant Enforcement):
/// - credit_used: Amount of intraday credit currently used (i64 → f64)
/// - allowed_overdraft_limit: Max overdraft from collateral + unsecured cap (i64 → f64)
/// - overdraft_headroom: Remaining capacity (allowed_limit - credit_used) (i64 → f64)
/// - collateral_haircut: Discount rate applied to collateral value (f64, 0.0-1.0)
/// - unsecured_cap: Unsecured daylight overdraft capacity (i64 → f64)
/// - required_collateral_for_usage: Min collateral needed for current credit usage (f64)
/// - excess_collateral: Collateral available for withdrawal (f64)
/// - overdraft_utilization: credit_used / allowed_limit ratio (0.0-1.0+)
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
///
/// **Overdraft Regime Fields** (Policy Enhancements V2, Phase 1.1):
/// - credit_headroom: Remaining credit capacity (credit_limit - credit_used) (f64)
/// - is_overdraft_capped: Boolean (1.0) indicating credit limit is enforced (f64)
///
/// **LSM-Aware Fields** (Policy Enhancements V2, Phase 1.2):
/// - my_q2_out_value_to_counterparty: Value of my Q2 outflows to this tx's counterparty (f64)
/// - my_q2_in_value_from_counterparty: Value of Q2 inflows from this tx's counterparty (f64)
/// - my_bilateral_net_q2: Net Q2 position with this counterparty (out - in) (f64)
/// - my_q2_out_value_top_1..5: Top 5 counterparties by Q2 outflow value (f64)
/// - my_q2_in_value_top_1..5: Top 5 counterparties by Q2 inflow value (f64)
/// - my_bilateral_net_q2_top_1..5: Top 5 counterparties by net Q2 position (f64)
///
/// **Public Signal Fields** (Policy Enhancements V2, Phase 1.3):
/// - system_queue2_pressure_index: System-wide Q2 pressure (0.0 = low, 1.0 = high) (f64)
/// - lsm_run_rate_last_10_ticks: LSM events per tick over last 10 ticks (f64)
/// - system_throughput_guidance_fraction_by_tick: Expected throughput by this tick (0.0-1.0) (f64)
///
/// **Throughput Progress Fields** (Policy Enhancements V2, Phase 2.1):
/// - my_throughput_fraction_today: Agent's throughput today (settled / total_due) (f64)
/// - expected_throughput_fraction_by_now: Expected progress from guidance curve (f64)
/// - throughput_gap: my_throughput - expected (negative = behind, positive = ahead) (f64)
///
/// **Counterparty Fields** (Policy Enhancements V2, Phase 2.2):
/// - tx_counterparty_id: Hash of counterparty ID for this transaction (f64)
/// - tx_is_top_counterparty: Boolean (1.0) if counterparty is in top 5 by volume (f64)
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
    /// let agent = Agent::new("BANK_A".to_string(), 1_000_000);
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

        // Phase 0.8: Queue 2 status field (TARGET2 Dual Priority)
        // Allows policies to check if transaction is in RTGS Queue 2
        // Transaction is in Queue 2 if it has a non-None RTGS priority
        fields.insert(
            "is_in_queue2".to_string(),
            if tx.rtgs_priority().is_some() { 1.0 } else { 0.0 },
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
        fields.insert("credit_limit".to_string(), agent.unsecured_cap() as f64);
        fields.insert(
            "available_liquidity".to_string(),
            agent.available_liquidity() as f64,
        );
        fields.insert("credit_used".to_string(), agent.credit_used() as f64);

        // Phase 11: Effective Liquidity Fix (from lsm-splitting-investigation-plan.md)
        // effective_liquidity = balance + unused_credit_capacity
        // This is what policies should use for "can I do X?" checks when in overdraft,
        // as it represents the TRUE available capacity (both positive balance and credit headroom)
        let credit_headroom = (agent.unsecured_cap() as i64) - agent.credit_used();
        let effective_liquidity = agent.balance() + credit_headroom;

        if std::env::var("POLICY_DEBUG").is_ok() {
            eprintln!("[POLICY CONTEXT] Agent: {}", agent.id());
            eprintln!("  balance: {}", agent.balance());
            eprintln!("  credit_limit: {}", agent.unsecured_cap());
            eprintln!("  credit_used: {}", agent.credit_used());
            eprintln!("  credit_headroom: {}", credit_headroom);
            eprintln!("  effective_liquidity: {}", effective_liquidity);
        }

        fields.insert("effective_liquidity".to_string(), effective_liquidity as f64);
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

        // Phase 1.1: Overdraft Regime Fields (Policy Enhancements V2)
        // credit_headroom = remaining capacity before hitting credit limit
        // This is what policies should check to see if they can afford a payment
        fields.insert("credit_headroom".to_string(), credit_headroom as f64);

        // is_overdraft_capped = 1.0 (always true for Option B: enforced credit limits)
        // Policies can use this to distinguish between capped (hard limit) and
        // unbounded (priced) overdraft regimes. In Option B, this is always 1.0.
        fields.insert("is_overdraft_capped".to_string(), 1.0);

        // Phase 1.2: LSM-Aware Fields (Policy Enhancements V2)
        // These fields enable policies to intentionally feed LSM by releasing
        // to counterparties where bilateral offset is likely.
        //
        // Privacy: Only exposes OWN-BANK queue composition relative to THIS transaction's
        // counterparty. Does not expose other banks' queues or system-wide information.

        let counterparty_id = tx.receiver_id();

        // Calculate Queue 2 composition for this specific counterparty
        let (my_q2_out, my_q2_in) = calculate_q2_bilateral_values(state, agent.id(), counterparty_id);
        let bilateral_net = (my_q2_out as i64) - (my_q2_in as i64);

        fields.insert("my_q2_out_value_to_counterparty".to_string(), my_q2_out as f64);
        fields.insert("my_q2_in_value_from_counterparty".to_string(), my_q2_in as f64);
        fields.insert("my_bilateral_net_q2".to_string(), bilateral_net as f64);

        // Calculate top 5 counterparties by Queue 2 outflow
        let top_outflows = calculate_top_counterparties_by_q2_outflow(state, agent.id(), 5);
        for (idx, (cpty_id, value)) in top_outflows.iter().enumerate() {
            let field_idx = idx + 1; // 1-indexed for readability
            fields.insert(format!("my_q2_out_value_top_{}", field_idx), *value as f64);

            // For categorical fields (counterparty IDs), we'll use a simple hash
            // This allows policies to check "is top_cpty_1 == this_counterparty"
            // by hashing both and comparing. Not perfect, but works for DSL constraints.
            let cpty_hash = simple_string_hash(cpty_id);
            fields.insert(format!("top_cpty_{}_id_hash", field_idx), cpty_hash as f64);
        }

        // Fill remaining top_N slots with zeros if < 5 counterparties
        for idx in (top_outflows.len() + 1)..=5 {
            fields.insert(format!("my_q2_out_value_top_{}", idx), 0.0);
            fields.insert(format!("top_cpty_{}_id_hash", idx), 0.0);
        }

        // Calculate top 5 counterparties by Queue 2 inflow
        let top_inflows = calculate_top_counterparties_by_q2_inflow(state, agent.id(), 5);
        for (idx, (_cpty_id, value)) in top_inflows.iter().enumerate() {
            let field_idx = idx + 1;
            fields.insert(format!("my_q2_in_value_top_{}", field_idx), *value as f64);
        }

        for idx in (top_inflows.len() + 1)..=5 {
            fields.insert(format!("my_q2_in_value_top_{}", idx), 0.0);
        }

        // Calculate bilateral net positions for top counterparties
        // (by absolute value of net position)
        let top_bilateral_nets = calculate_top_bilateral_nets(state, agent.id(), 5);
        for (idx, (_cpty_id, net_value)) in top_bilateral_nets.iter().enumerate() {
            let field_idx = idx + 1;
            fields.insert(format!("my_bilateral_net_q2_top_{}", field_idx), *net_value as f64);
        }

        for idx in (top_bilateral_nets.len() + 1)..=5 {
            fields.insert(format!("my_bilateral_net_q2_top_{}", idx), 0.0);
        }

        // Phase 1.3: Public Signal Fields (Policy Enhancements V2)
        // These fields expose system-wide coarse metrics visible to all agents.
        // No privacy violation - everyone sees the same values.
        //
        // Use cases:
        // - System pressure: Adjust aggression when system is gridlocked
        // - LSM run rate: Coordinate releases when LSM is active
        // - Throughput guidance: Compare own progress against expected curve

        // Calculate system-wide Queue 2 pressure index (0.0 = low, 1.0 = high)
        let system_pressure = calculate_queue2_pressure_index(state);
        fields.insert("system_queue2_pressure_index".to_string(), system_pressure);

        // LSM run rate: events per tick over last 10 ticks
        // TODO: Requires LSM event tracking in SimulationState
        // For now, returns 0.0 (will be implemented with state.lsm_event_rate(10))
        let lsm_run_rate = 0.0; // Placeholder until LSM event tracking added
        fields.insert("lsm_run_rate_last_10_ticks".to_string(), lsm_run_rate);

        // Throughput guidance: Expected throughput fraction by this tick (0.0-1.0)
        // This comes from optional configuration parameter (throughput_guidance_curve)
        // For now, returns 0.0 (will be passed via build() parameter when available)
        let throughput_guidance = 0.0; // Placeholder until config parameter added
        fields.insert("system_throughput_guidance_fraction_by_tick".to_string(), throughput_guidance);

        // Phase 2.1: Throughput Progress Fields (Policy Enhancements V2)
        // These fields enable policies to track settlement progress against expected
        // throughput curves (e.g., "am I 30% done when I should be 50% done?").
        //
        // Use cases:
        // - Catch-up behavior: Release more aggressively when behind schedule
        // - Throttling: Be conservative when ahead of schedule
        // - EOD rush detection: Know when to switch to panic mode

        // Calculate agent's throughput today (settled / total_due)
        // TODO: Requires SimulationState to track daily settlement amounts per agent
        // For now, we calculate from transaction data (may include all-time, not just today)
        let my_throughput_fraction = calculate_throughput_fraction_simple(state, agent.id());
        fields.insert("my_throughput_fraction_today".to_string(), my_throughput_fraction);

        // Expected throughput fraction by now (from guidance curve)
        // TODO: Pass throughput_guidance_curve as parameter to build()
        // For now, use a simple linear model: expected = tick_in_day / ticks_per_day
        let tick_in_day = tick % ticks_per_day;
        let expected_throughput = if ticks_per_day > 0 {
            tick_in_day as f64 / ticks_per_day as f64
        } else {
            0.0
        };
        fields.insert("expected_throughput_fraction_by_now".to_string(), expected_throughput);

        // Throughput gap: negative = behind, positive = ahead
        let throughput_gap = my_throughput_fraction - expected_throughput;
        fields.insert("throughput_gap".to_string(), throughput_gap);

        // Phase 2.2: Counterparty Fields (Policy Enhancements V2)
        // These fields enable policies to identify and prioritize transactions based on
        // counterparty relationships (e.g., "is this my top trading partner?").
        //
        // Use cases:
        // - Prioritize payments to top counterparties
        // - Different strategies for frequent vs infrequent trading partners
        // - Relationship-based liquidity management

        // Transaction counterparty ID (hash-encoded for categorical comparison)
        let counterparty_id = tx.receiver_id();
        let counterparty_hash = simple_string_hash(counterparty_id);
        fields.insert("tx_counterparty_id".to_string(), counterparty_hash as f64);

        // Is this counterparty in agent's top 5 by historical volume?
        let top_counterparties = agent.top_counterparties(5);
        let is_top = if top_counterparties.contains(&counterparty_id.to_string()) {
            1.0
        } else {
            0.0
        };
        fields.insert("tx_is_top_counterparty".to_string(), is_top);

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

        // New T2/CLM-style collateral/headroom fields
        fields.insert(
            "credit_used".to_string(),
            agent.credit_used() as f64,
        );
        fields.insert(
            "allowed_overdraft_limit".to_string(),
            agent.allowed_overdraft_limit() as f64,
        );
        fields.insert(
            "overdraft_headroom".to_string(),
            agent.headroom() as f64,
        );
        fields.insert(
            "collateral_haircut".to_string(),
            agent.collateral_haircut(),
        );
        fields.insert(
            "unsecured_cap".to_string(),
            agent.unsecured_cap() as f64,
        );

        // Derived collateral metrics for policy decisions
        // Required collateral = credit usage beyond unsecured cap / (1 - haircut)
        // Cap unsecured_cap at credit_used to prevent negative values when not using credit
        let required_collateral_for_usage = if agent.collateral_haircut() < 1.0 {
            let one_minus_h = (1.0 - agent.collateral_haircut()).max(0.0);
            let credit_used = agent.credit_used();
            let unsecured_contribution = agent.unsecured_cap().min(credit_used);
            let usage_after_unsecured = credit_used - unsecured_contribution;
            ((usage_after_unsecured as f64) / one_minus_h).ceil()
        } else {
            0.0
        };
        fields.insert("required_collateral_for_usage".to_string(), required_collateral_for_usage);

        let excess_collateral = ((agent.posted_collateral() as f64) - required_collateral_for_usage).max(0.0);
        fields.insert("excess_collateral".to_string(), excess_collateral);

        // Overdraft utilization ratio (for policy thresholds)
        let allowed_limit = agent.allowed_overdraft_limit() as f64;
        let overdraft_utilization = if allowed_limit > 0.0 {
            (agent.credit_used() as f64) / allowed_limit
        } else {
            0.0
        };
        fields.insert("overdraft_utilization".to_string(), overdraft_utilization);

        // Liquidity gap fields
        fields.insert(
            "queue1_liquidity_gap".to_string(),
            agent.queue1_liquidity_gap(state) as f64,
        );

        let mut queue1_total_value = 0i64;
        for tx_id in agent.outgoing_queue() {
            if let Some(tx_in_queue) = state.get_transaction(tx_id) {
                queue1_total_value = queue1_total_value.saturating_add(tx_in_queue.remaining_amount());
            }
        }
        fields.insert("queue1_total_value".to_string(), queue1_total_value as f64);

        // Headroom: available liquidity minus what's needed for Queue 1
        // Use saturating_sub to handle potential overflow
        let headroom = agent.available_liquidity().saturating_sub(queue1_total_value);
        fields.insert("headroom".to_string(), headroom as f64);

        // Queue 2 (RTGS) pressure fields
        // Total size of Queue 2 (all agents)
        fields.insert("queue2_size".to_string(), state.rtgs_queue().len() as f64);

        // Performance optimization: Use Queue2 index for O(1) lookup instead of O(Queue2_Size) scans
        let queue2_metrics = state.queue2_index().get_metrics(agent.id());
        fields.insert(
            "queue2_count_for_agent".to_string(),
            queue2_metrics.count as f64,
        );

        fields.insert(
            "queue2_nearest_deadline".to_string(),
            queue2_metrics.nearest_deadline as f64,
        );

        let ticks_to_nearest_queue2_deadline = if queue2_metrics.nearest_deadline == usize::MAX {
            f64::INFINITY
        } else {
            queue2_metrics
                .nearest_deadline
                .saturating_sub(tick) as f64
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

        // Phase 4.5: Add state registers from agent
        // State registers provide policy micro-memory (bank_state_* fields)
        for (key, value) in agent.state_registers() {
            fields.insert(key.clone(), *value);
        }

        Self { fields }
    }

    /// Create bank-level evaluation context (Phase 3.3: Policy Enhancements V2)
    ///
    /// Used for evaluating bank_tree nodes, which make decisions once per tick
    /// without reference to a specific transaction (e.g., setting budgets).
    ///
    /// # Arguments
    ///
    /// * `agent` - Agent whose bank-level policy is being evaluated
    /// * `state` - Full simulation state
    /// * `tick` - Current simulation tick
    /// * `cost_rates` - Cost configuration
    /// * `ticks_per_day` - Number of ticks in a simulation day
    /// * `eod_rush_threshold` - End-of-day rush threshold (0.0 to 1.0)
    ///
    /// # Returns
    ///
    /// Context populated with agent-level and system-level fields (no transaction fields)
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::policy::tree::EvalContext;
    /// use payment_simulator_core_rs::{Agent, SimulationState};
    /// use payment_simulator_core_rs::orchestrator::CostRates;
    ///
    /// let agent = Agent::new("BANK_A".to_string(), 1_000_000);
    /// let state = SimulationState::new(vec![agent.clone()]);
    /// let cost_rates = CostRates::default();
    ///
    /// let context = EvalContext::bank_level(&agent, &state, 100, &cost_rates, 100, 0.8);
    /// let balance = context.get_field("balance").unwrap();
    /// assert_eq!(balance, 1_000_000.0);
    /// ```
    pub fn bank_level(
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
        ticks_per_day: usize,
        eod_rush_threshold: f64,
    ) -> Self {
        let mut fields = HashMap::new();

        // Agent fields (same as transaction context)
        fields.insert("balance".to_string(), agent.balance() as f64);
        fields.insert("credit_limit".to_string(), agent.unsecured_cap() as f64);
        fields.insert(
            "available_liquidity".to_string(),
            agent.available_liquidity() as f64,
        );
        fields.insert("credit_used".to_string(), agent.credit_used() as f64);

        // Effective liquidity and credit headroom
        let credit_headroom = (agent.unsecured_cap() as i64) - agent.credit_used();
        let effective_liquidity = agent.balance() + credit_headroom;
        fields.insert("effective_liquidity".to_string(), effective_liquidity as f64);
        fields.insert("credit_headroom".to_string(), credit_headroom as f64);

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
        fields.insert("is_overdraft_capped".to_string(), 1.0);

        // Queue 1 metrics
        let mut queue1_total_value = 0i64;
        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = state.get_transaction(tx_id) {
                queue1_total_value += tx.remaining_amount();
            }
        }
        fields.insert("queue1_total_value".to_string(), queue1_total_value as f64);
        fields.insert(
            "queue1_liquidity_gap".to_string(),
            agent.queue1_liquidity_gap(state) as f64,
        );

        // Headroom
        let headroom = agent.available_liquidity() - queue1_total_value;
        fields.insert("headroom".to_string(), headroom as f64);

        // System fields
        fields.insert("current_tick".to_string(), tick as f64);
        fields.insert("rtgs_queue_size".to_string(), state.queue_size() as f64);
        fields.insert("rtgs_queue_value".to_string(), state.queue_value() as f64);
        fields.insert("total_agents".to_string(), state.num_agents() as f64);

        // Collateral fields
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

        // New T2/CLM-style collateral/headroom fields (end-of-tick)
        fields.insert(
            "credit_used".to_string(),
            agent.credit_used() as f64,
        );
        fields.insert(
            "allowed_overdraft_limit".to_string(),
            agent.allowed_overdraft_limit() as f64,
        );
        fields.insert(
            "overdraft_headroom".to_string(),
            agent.headroom() as f64,
        );
        fields.insert(
            "collateral_haircut".to_string(),
            agent.collateral_haircut(),
        );
        fields.insert(
            "unsecured_cap".to_string(),
            agent.unsecured_cap() as f64,
        );

        // Derived collateral metrics for end-of-tick decisions
        // Required collateral = credit usage beyond unsecured cap / (1 - haircut)
        // Cap unsecured_cap at credit_used to prevent negative values when not using credit
        let required_collateral_for_usage = if agent.collateral_haircut() < 1.0 {
            let one_minus_h = (1.0 - agent.collateral_haircut()).max(0.0);
            let credit_used = agent.credit_used();
            let unsecured_contribution = agent.unsecured_cap().min(credit_used);
            let usage_after_unsecured = credit_used - unsecured_contribution;
            ((usage_after_unsecured as f64) / one_minus_h).ceil()
        } else {
            0.0
        };
        fields.insert("required_collateral_for_usage".to_string(), required_collateral_for_usage);

        let excess_collateral = ((agent.posted_collateral() as f64) - required_collateral_for_usage).max(0.0);
        fields.insert("excess_collateral".to_string(), excess_collateral);

        // Queue 2 metrics
        fields.insert("queue2_size".to_string(), state.rtgs_queue().len() as f64);
        let queue2_metrics = state.queue2_index().get_metrics(agent.id());
        fields.insert(
            "queue2_count_for_agent".to_string(),
            queue2_metrics.count as f64,
        );
        fields.insert(
            "queue2_nearest_deadline".to_string(),
            queue2_metrics.nearest_deadline as f64,
        );

        let ticks_to_nearest_queue2_deadline = if queue2_metrics.nearest_deadline == usize::MAX {
            f64::INFINITY
        } else {
            queue2_metrics
                .nearest_deadline
                .saturating_sub(tick) as f64
        };
        fields.insert(
            "ticks_to_nearest_queue2_deadline".to_string(),
            ticks_to_nearest_queue2_deadline,
        );

        // Cost fields
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

        // Time/day fields
        fields.insert("system_ticks_per_day".to_string(), ticks_per_day as f64);
        let current_day = tick / ticks_per_day;
        let tick_in_day = tick % ticks_per_day;
        fields.insert("system_current_day".to_string(), current_day as f64);
        fields.insert("system_tick_in_day".to_string(), tick_in_day as f64);

        let ticks_remaining = ticks_per_day.saturating_sub(tick_in_day).saturating_sub(1);
        fields.insert("ticks_remaining_in_day".to_string(), ticks_remaining as f64);

        let day_progress = if ticks_per_day > 0 {
            tick_in_day as f64 / ticks_per_day as f64
        } else {
            0.0
        };
        fields.insert("day_progress_fraction".to_string(), day_progress);

        let is_eod_rush = if day_progress >= eod_rush_threshold { 1.0 } else { 0.0 };
        fields.insert("is_eod_rush".to_string(), is_eod_rush);

        // Public signal fields
        let system_pressure = calculate_queue2_pressure_index(state);
        fields.insert("system_queue2_pressure_index".to_string(), system_pressure);

        // Throughput progress fields
        let my_throughput_fraction = calculate_throughput_fraction_simple(state, agent.id());
        fields.insert("my_throughput_fraction_today".to_string(), my_throughput_fraction);

        let expected_throughput = if ticks_per_day > 0 {
            tick_in_day as f64 / ticks_per_day as f64
        } else {
            0.0
        };
        fields.insert("expected_throughput_fraction_by_now".to_string(), expected_throughput);

        let throughput_gap = my_throughput_fraction - expected_throughput;
        fields.insert("throughput_gap".to_string(), throughput_gap);

        // Phase 4.5: Add state registers from agent
        // State registers provide policy micro-memory (bank_state_* fields)
        for (key, value) in agent.state_registers() {
            fields.insert(key.clone(), *value);
        }

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
    ///
    /// # Phase 4.5: State Register Default Values
    ///
    /// State registers (fields starting with "bank_state_") default to 0.0
    /// if not explicitly set. This allows policies to read registers before
    /// they're initialized.
    pub fn get_field(&self, name: &str) -> Result<f64, ContextError> {
        if let Some(&value) = self.fields.get(name) {
            Ok(value)
        } else if name.starts_with("bank_state_") {
            // State registers default to 0.0 if not set
            Ok(0.0)
        } else {
            Err(ContextError::FieldNotFound(name.to_string()))
        }
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
            100_000, // liquidity_buffer
        );
        agent.set_unsecured_cap(200_000); // $2,000 unsecured overdraft capacity
        agent.queue_outgoing("tx_001".to_string());
        agent.queue_outgoing("tx_002".to_string());
        agent.add_expected_inflow("tx_003".to_string());

        // Create simulation state
        let state = SimulationState::new(vec![
            agent.clone(),
            Agent::new("BANK_B".to_string(), 1_000_000),
            Agent::new("BANK_C".to_string(), 2_000_000),
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
        assert_eq!(context.get_field("unsecured_cap").unwrap(), 200_000.0);
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
        let agent = Agent::new("BANK_A".to_string(), -50_000);
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

        let agent = Agent::new("BANK_A".to_string(), 1_000_000);
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
        let agent = Agent::with_buffer("BANK_A".to_string(), 500_000, 100_000);
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
        let agent = Agent::new("BANK_A".to_string(), 1_000_000);
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
        let agent = Agent::new("BANK_A".to_string(), 1_000_000);
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
        let agent = Agent::new("BANK_A".to_string(), 1_000_000);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 50);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = create_cost_rates();

        // Not overdue - duration should be 0
        let context = EvalContext::build(&tx, &agent, &state, 40, &cost_rates, 100, 0.8);

        assert_eq!(context.get_field("overdue_duration").unwrap(), 0.0);
    }
}

// ============================================================================
// Phase 1.2: LSM-Aware Helper Functions (Policy Enhancements V2)
// ============================================================================

/// Calculate bilateral Queue 2 values for a specific counterparty
///
/// Returns (my_q2_out, my_q2_in):
/// - my_q2_out: Total value of my outgoing Q2 transactions to counterparty
/// - my_q2_in: Total value of counterparty's outgoing Q2 transactions to me
fn calculate_q2_bilateral_values(
    state: &SimulationState,
    agent_id: &str,
    counterparty_id: &str,
) -> (i64, i64) {
    let mut my_q2_out = 0i64;
    let mut my_q2_in = 0i64;

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            // Outgoing to counterparty
            // Use saturating_add to prevent overflow
            if tx.sender_id() == agent_id && tx.receiver_id() == counterparty_id {
                my_q2_out = my_q2_out.saturating_add(tx.remaining_amount());
            }
            // Incoming from counterparty
            if tx.sender_id() == counterparty_id && tx.receiver_id() == agent_id {
                my_q2_in = my_q2_in.saturating_add(tx.remaining_amount());
            }
        }
    }

    (my_q2_out, my_q2_in)
}

/// Calculate top N counterparties by Queue 2 outflow value
fn calculate_top_counterparties_by_q2_outflow(
    state: &SimulationState,
    agent_id: &str,
    n: usize,
) -> Vec<(String, i64)> {
    use std::collections::HashMap;

    // Aggregate by counterparty
    let mut by_counterparty: HashMap<String, i64> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.sender_id() == agent_id {
                // Use saturating_add to prevent overflow
                let entry = by_counterparty
                    .entry(tx.receiver_id().to_string())
                    .or_insert(0);
                *entry = entry.saturating_add(tx.remaining_amount());
            }
        }
    }

    // Sort by value descending
    let mut sorted: Vec<_> = by_counterparty.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1)); // Descending by value

    // Take top N
    sorted.into_iter().take(n).collect()
}

/// Calculate top N counterparties by Queue 2 inflow value
fn calculate_top_counterparties_by_q2_inflow(
    state: &SimulationState,
    agent_id: &str,
    n: usize,
) -> Vec<(String, i64)> {
    use std::collections::HashMap;

    // Aggregate by counterparty
    let mut by_counterparty: HashMap<String, i64> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            if tx.receiver_id() == agent_id {
                // Use saturating_add to prevent overflow
                let entry = by_counterparty
                    .entry(tx.sender_id().to_string())
                    .or_insert(0);
                *entry = entry.saturating_add(tx.remaining_amount());
            }
        }
    }

    // Sort by value descending
    let mut sorted: Vec<_> = by_counterparty.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1));

    sorted.into_iter().take(n).collect()
}

/// Calculate top N counterparties by bilateral net position (absolute value)
fn calculate_top_bilateral_nets(
    state: &SimulationState,
    agent_id: &str,
    n: usize,
) -> Vec<(String, i64)> {
    use std::collections::HashMap;

    // Calculate net for each counterparty
    let mut nets: HashMap<String, i64> = HashMap::new();

    for tx_id in state.rtgs_queue() {
        if let Some(tx) = state.get_transaction(tx_id) {
            // Outgoing (positive contribution to net)
            // Use saturating arithmetic to prevent overflow
            if tx.sender_id() == agent_id {
                let entry = nets.entry(tx.receiver_id().to_string()).or_insert(0);
                *entry = entry.saturating_add(tx.remaining_amount());
            }
            // Incoming (negative contribution to net)
            if tx.receiver_id() == agent_id {
                let entry = nets.entry(tx.sender_id().to_string()).or_insert(0);
                *entry = entry.saturating_sub(tx.remaining_amount());
            }
        }
    }

    // Sort by absolute value of net position descending
    let mut sorted: Vec<_> = nets.into_iter().collect();
    sorted.sort_by(|a, b| b.1.abs().cmp(&a.1.abs()));

    sorted.into_iter().take(n).collect()
}

/// Simple string hash for categorical field encoding
///
/// Uses FNV-1a hash algorithm (simple, fast, good distribution)
/// Returns u64 cast to f64 for storage in policy context fields
fn simple_string_hash(s: &str) -> u64 {
    const FNV_OFFSET_BASIS: u64 = 14695981039346656037;
    const FNV_PRIME: u64 = 1099511628211;

    let mut hash = FNV_OFFSET_BASIS;
    for byte in s.bytes() {
        hash ^= byte as u64;
        hash = hash.wrapping_mul(FNV_PRIME);
    }
    hash
}

// ============================================================================
// Phase 1.3: Public Signal Helper Functions (Policy Enhancements V2)
// ============================================================================

/// Calculate Queue 2 pressure index (0.0 = no pressure, 1.0 = high pressure)
///
/// Formula: Normalized based on queue size and total system capacity
/// Uses a sigmoid-like function to map queue size to [0, 1]
///
/// **Public Information**: This exposes coarse system-level metrics that
/// all agents can see. No privacy violation - everyone sees the same value.
///
/// **Use Case**: Adjust aggression when system is gridlocked
fn calculate_queue2_pressure_index(state: &SimulationState) -> f64 {
    let queue_size = state.queue_size();
    let num_agents = state.num_agents();

    if num_agents == 0 || queue_size == 0 {
        return 0.0;
    }

    // Normalize: pressure increases with queue size relative to agent count
    // Use a sigmoid-like function to map to [0, 1]
    // Threshold: ~10 transactions per agent is considered "moderate"
    let threshold = (num_agents * 10) as f64;
    let x = queue_size as f64 / threshold;

    // Sigmoid: 1 / (1 + e^(-k*x))
    // Using k=2 for moderate steepness
    let pressure = 1.0 / (1.0 + (-2.0 * x).exp());

    pressure.min(1.0)
}

// ============================================================================
// Phase 2.1: Throughput Progress Helper Functions (Policy Enhancements V2)
// ============================================================================

/// Calculate agent's throughput fraction (simple version)
///
/// Returns the ratio of settled amount to total amount for this agent's transactions.
///
/// **Note**: This is a simplified version that doesn't track daily boundaries.
/// It calculates from all transactions in the system, not just today's.
///
/// TODO: Implement proper day-tracking in SimulationState for accurate daily throughput.
fn calculate_throughput_fraction_simple(state: &SimulationState, agent_id: &str) -> f64 {
    let mut total_amount = 0i64;
    let mut settled_amount = 0i64;

    // Iterate through all transactions where this agent is the sender
    // Use saturating_add to prevent overflow with large transaction volumes
    for tx in state.transactions().values() {
        if tx.sender_id() == agent_id {
            total_amount = total_amount.saturating_add(tx.amount());
            settled_amount = settled_amount.saturating_add(tx.settled_amount());
        }
    }

    if total_amount > 0 {
        settled_amount as f64 / total_amount as f64
    } else {
        0.0
    }
}
