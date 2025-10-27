//! Orchestrator Engine - Phase 4b
//!
//! Main simulation loop integrating all components:
//! - Transaction arrivals (deterministic generation)
//! - Policy evaluation (Queue 1 decisions)
//! - Settlement processing (RTGS + LSM)
//! - Cost accrual (liquidity, delay, penalties)
//! - Event logging (complete simulation history)
//!
//! # Architecture
//!
//! The Orchestrator implements the tick loop specified in `/docs/grand_plan.md`:
//!
//! ```text
//! For each tick t:
//! 1. Generate arrivals (Poisson sampling)
//! 2. Evaluate policies (Queue 1 → settlement decisions)
//! 3. Execute RTGS settlements
//! 4. Process RTGS queue (Queue 2 retry)
//! 5. Run LSM coordinator (find offsets)
//! 6. Accrue costs (liquidity, delay)
//! 7. Drop expired transactions
//! 8. Log events
//! 9. Advance time
//! 10. Handle end-of-day if needed
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use payment_simulator_core_rs::orchestrator::{Orchestrator, OrchestratorConfig, AgentConfig, PolicyConfig};
//!
//! let config = OrchestratorConfig {
//!     ticks_per_day: 100,
//!     num_days: 1,
//!     rng_seed: 12345,
//!     agent_configs: vec![
//!         AgentConfig {
//!             id: "BANK_A".to_string(),
//!             opening_balance: 1_000_000,
//!             credit_limit: 500_000,
//!             policy: PolicyConfig::Fifo,
//!             arrival_config: None,
//!         },
//!         AgentConfig {
//!             id: "BANK_B".to_string(),
//!             opening_balance: 2_000_000,
//!             credit_limit: 0,
//!             policy: PolicyConfig::LiquidityAware {
//!                 target_buffer: 500_000,
//!                 urgency_threshold: 5,
//!             },
//!             arrival_config: None,
//!         },
//!     ],
//!     cost_rates: Default::default(),
//! };
//!
//! let mut orchestrator = Orchestrator::new(config).unwrap();
//!
//! // Run simulation for 10 ticks
//! for _ in 0..10 {
//!     let result = orchestrator.tick().unwrap();
//!     println!("Tick {}: {} arrivals, {} settlements",
//!              result.tick, result.num_arrivals, result.num_settlements);
//! }
//! ```

use crate::core::time::TimeManager;
use crate::models::agent::Agent;
use crate::models::state::SimulationState;
use crate::policy::{CashManagerPolicy, DeadlinePolicy, FifoPolicy, LiquidityAwarePolicy};
use crate::rng::RngManager;
use crate::settlement::lsm::LsmConfig;
use std::collections::HashMap;

// ============================================================================
// Configuration Types
// ============================================================================

/// Complete orchestrator configuration
///
/// This struct contains all parameters needed to initialize a simulation.
///
/// # Fields
///
/// * `ticks_per_day` - Number of discrete time steps per business day
/// * `num_days` - Total simulation duration in days
/// * `rng_seed` - Seed for deterministic random number generation
/// * `agent_configs` - Configuration for each participating agent (bank)
/// * `cost_rates` - Rates for calculating liquidity, delay, and penalty costs
#[derive(Debug, Clone)]
pub struct OrchestratorConfig {
    /// Number of ticks per business day (e.g., 100 ticks = 1 tick per ~5 minutes)
    pub ticks_per_day: usize,

    /// Number of business days to simulate
    pub num_days: usize,

    /// RNG seed for deterministic simulation
    pub rng_seed: u64,

    /// Per-agent configuration
    pub agent_configs: Vec<AgentConfig>,

    /// Cost calculation rates
    pub cost_rates: CostRates,

    /// LSM configuration
    pub lsm_config: LsmConfig,
}

/// Per-agent configuration
///
/// Specifies initial state and behavior for a single agent (bank).
#[derive(Debug, Clone)]
pub struct AgentConfig {
    /// Unique agent identifier
    pub id: String,

    /// Opening balance in settlement account (cents/minor units)
    pub opening_balance: i64,

    /// Daylight overdraft or collateralized credit limit (cents)
    pub credit_limit: i64,

    /// Cash manager policy for Queue 1 decisions
    pub policy: PolicyConfig,

    /// Arrival generation configuration (None = no automatic arrivals)
    pub arrival_config: Option<ArrivalConfig>,
}

/// Policy selection for an agent
///
/// Determines which cash manager policy algorithm to use for Queue 1 decisions.
#[derive(Debug, Clone)]
pub enum PolicyConfig {
    /// FIFO: Submit all transactions immediately (baseline)
    Fifo,

    /// Deadline-based: Prioritize urgent transactions approaching deadline
    Deadline {
        /// Number of ticks before deadline to consider urgent
        urgency_threshold: usize,
    },

    /// Liquidity-aware: Preserve buffer, override for urgency
    LiquidityAware {
        /// Target minimum balance to maintain (cents)
        target_buffer: i64,
        /// Number of ticks before deadline to override buffer rule
        urgency_threshold: usize,
    },
}

/// Arrival generation configuration (placeholder for Phase 4b.2)
///
/// Specifies how transactions arrive for this agent during simulation.
/// Full implementation in `/backend/src/arrivals/mod.rs` (Phase 4b.2).
#[derive(Debug, Clone)]
pub struct ArrivalConfig {
    /// Rate parameter for Poisson distribution (expected arrivals per tick)
    pub rate_per_tick: f64,

    /// Minimum transaction amount (cents)
    pub amount_min: i64,

    /// Maximum transaction amount (cents)
    pub amount_max: i64,

    /// Counterparty selection weights (AgentId → weight)
    pub counterparty_weights: HashMap<String, f64>,

    /// Deadline range (min_ticks_ahead, max_ticks_ahead)
    pub deadline_range: (usize, usize),
}

/// Cost calculation rates
///
/// Defines rates for various costs accrued during simulation.
/// All monetary values in cents/minor units.
#[derive(Debug, Clone)]
pub struct CostRates {
    /// Overdraft cost in basis points per tick
    /// (e.g., 0.001 = 1 bp per tick ≈ 10 bp per day for 100 ticks/day)
    pub overdraft_bps_per_tick: f64,

    /// Delay cost per tick per cent of queued value
    /// (e.g., 0.0001 = 1 bp delay cost per tick)
    pub delay_cost_per_tick_per_cent: f64,

    /// End-of-day penalty for each unsettled transaction (cents)
    pub eod_penalty_per_transaction: i64,

    /// Penalty for missing deadline (cents per transaction)
    pub deadline_penalty: i64,
}

impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,            // 1 bp/tick
            delay_cost_per_tick_per_cent: 0.0001,     // 0.1 bp/tick
            eod_penalty_per_transaction: 10_000,      // $100 per unsettled tx
            deadline_penalty: 50_000,                  // $500 per missed deadline
        }
    }
}

/// Cost breakdown for a single tick or agent
#[derive(Debug, Clone, Default)]
pub struct CostBreakdown {
    /// Overdraft cost accrued this tick (cents)
    pub liquidity_cost: i64,

    /// Queue delay cost accrued this tick (cents)
    pub delay_cost: i64,

    /// Penalties incurred this tick (cents)
    pub penalty_cost: i64,
}

impl CostBreakdown {
    /// Total cost across all categories
    pub fn total(&self) -> i64 {
        self.liquidity_cost + self.delay_cost + self.penalty_cost
    }
}

/// Accumulated costs for an agent over time
#[derive(Debug, Clone, Default)]
pub struct CostAccumulator {
    /// Total liquidity cost (overdraft)
    pub total_liquidity_cost: i64,

    /// Total delay cost
    pub total_delay_cost: i64,

    /// Total penalties
    pub total_penalty_cost: i64,

    /// Peak net debit observed (most negative balance)
    pub peak_net_debit: i64,
}

impl CostAccumulator {
    /// Create new accumulator
    pub fn new() -> Self {
        Self::default()
    }

    /// Add costs from a tick
    pub fn add(&mut self, costs: &CostBreakdown) {
        self.total_liquidity_cost += costs.liquidity_cost;
        self.total_delay_cost += costs.delay_cost;
        self.total_penalty_cost += costs.penalty_cost;
    }

    /// Update peak net debit if current balance is more negative
    pub fn update_peak_debit(&mut self, current_balance: i64) {
        if current_balance < 0 {
            self.peak_net_debit = self.peak_net_debit.min(current_balance);
        }
    }

    /// Total cost across all categories
    pub fn total(&self) -> i64 {
        self.total_liquidity_cost + self.total_delay_cost + self.total_penalty_cost
    }
}

// ============================================================================
// Orchestrator
// ============================================================================

/// Main orchestrator managing simulation state and tick loop
///
/// The Orchestrator owns all simulation state and coordinates:
/// - Transaction arrivals
/// - Policy evaluation
/// - Settlement processing
/// - Cost accrual
/// - Event logging
///
/// # Determinism
///
/// All randomness is via `rng_manager` with seeded xorshift64*.
/// Same seed + same config = identical results (deterministic replay).
pub struct Orchestrator {
    /// Simulation state (agents, transactions, queues)
    state: SimulationState,

    /// Time management
    time_manager: TimeManager,

    /// Deterministic RNG
    rng_manager: RngManager,

    /// Per-agent policy executors
    policies: HashMap<String, Box<dyn CashManagerPolicy>>,

    /// Arrival configurations (None = no automatic arrivals)
    arrival_configs: HashMap<String, ArrivalConfig>,

    /// Cost calculation rates
    cost_rates: CostRates,

    /// LSM configuration
    lsm_config: LsmConfig,

    /// Accumulated costs per agent
    accumulated_costs: HashMap<String, CostAccumulator>,

    /// Event log (all simulation events)
    /// Phase 4b.4 will define Event enum
    event_count: usize, // Placeholder until Event enum implemented

    /// Transaction IDs to attempt settlement this tick
    pending_settlements: Vec<String>,

    /// Counter for generating unique transaction IDs
    next_tx_id: usize,
}

/// Result of a single tick
#[derive(Debug, Clone)]
pub struct TickResult {
    /// Tick number
    pub tick: usize,

    /// Number of new arrivals this tick
    pub num_arrivals: usize,

    /// Number of successful settlements this tick
    pub num_settlements: usize,

    /// Number of LSM releases this tick
    pub num_lsm_releases: usize,

    /// Total cost accrued across all agents this tick
    pub total_cost: i64,
}

/// Simulation error types
#[derive(Debug, Clone, PartialEq)]
pub enum SimulationError {
    /// Configuration validation error
    InvalidConfig(String),

    /// Agent not found
    AgentNotFound(String),

    /// Transaction not found
    TransactionNotFound(String),

    /// Settlement engine error
    SettlementError(String),

    /// RNG error
    RngError(String),
}

impl std::fmt::Display for SimulationError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SimulationError::InvalidConfig(msg) => write!(f, "Invalid config: {}", msg),
            SimulationError::AgentNotFound(id) => write!(f, "Agent not found: {}", id),
            SimulationError::TransactionNotFound(id) => {
                write!(f, "Transaction not found: {}", id)
            }
            SimulationError::SettlementError(msg) => write!(f, "Settlement error: {}", msg),
            SimulationError::RngError(msg) => write!(f, "RNG error: {}", msg),
        }
    }
}

impl std::error::Error for SimulationError {}

/// Outcome of a settlement attempt
#[derive(Debug, Clone, PartialEq)]
enum SettlementOutcome {
    /// Transaction settled successfully
    Settled,
    /// Transaction queued (insufficient liquidity)
    Queued,
}

impl Orchestrator {
    /// Create new orchestrator from configuration
    ///
    /// Initializes all simulation state, policies, and RNG.
    ///
    /// # Arguments
    ///
    /// * `config` - Complete orchestrator configuration
    ///
    /// # Returns
    ///
    /// * `Ok(Orchestrator)` - Successfully initialized orchestrator
    /// * `Err(SimulationError)` - Configuration validation failed
    ///
    /// # Example
    ///
    /// ```rust
    /// use payment_simulator_core_rs::orchestrator::{Orchestrator, OrchestratorConfig, AgentConfig, PolicyConfig};
    /// use payment_simulator_core_rs::settlement::lsm::LsmConfig;
    ///
    /// let config = OrchestratorConfig {
    ///     ticks_per_day: 100,
    ///     num_days: 1,
    ///     rng_seed: 12345,
    ///     agent_configs: vec![
    ///         AgentConfig {
    ///             id: "BANK_A".to_string(),
    ///             opening_balance: 1_000_000,
    ///             credit_limit: 0,
    ///             policy: PolicyConfig::Fifo,
    ///             arrival_config: None,
    ///         },
    ///     ],
    ///     cost_rates: Default::default(),
    ///     lsm_config: LsmConfig::default(),
    /// };
    ///
    /// let orchestrator = Orchestrator::new(config).unwrap();
    /// ```
    pub fn new(config: OrchestratorConfig) -> Result<Self, SimulationError> {
        // Validate configuration
        Self::validate_config(&config)?;

        // Initialize agents
        let agents: Vec<Agent> = config
            .agent_configs
            .iter()
            .map(|ac| Agent::new(ac.id.clone(), ac.opening_balance, ac.credit_limit))
            .collect();

        let state = SimulationState::new(agents);

        // Initialize time manager
        let time_manager = TimeManager::new(config.ticks_per_day);

        // Initialize RNG
        let rng_manager = RngManager::new(config.rng_seed);

        // Initialize policies
        let mut policies: HashMap<String, Box<dyn CashManagerPolicy>> = HashMap::new();
        for agent_config in &config.agent_configs {
            let policy: Box<dyn CashManagerPolicy> = match &agent_config.policy {
                PolicyConfig::Fifo => Box::new(FifoPolicy),
                PolicyConfig::Deadline { urgency_threshold } => {
                    Box::new(DeadlinePolicy::new(*urgency_threshold))
                }
                PolicyConfig::LiquidityAware {
                    target_buffer,
                    urgency_threshold,
                } => Box::new(LiquidityAwarePolicy::with_urgency_threshold(
                    *target_buffer,
                    *urgency_threshold,
                )),
            };
            policies.insert(agent_config.id.clone(), policy);
        }

        // Initialize arrival configs
        let mut arrival_configs = HashMap::new();
        for agent_config in &config.agent_configs {
            if let Some(arrival_cfg) = &agent_config.arrival_config {
                arrival_configs.insert(agent_config.id.clone(), arrival_cfg.clone());
            }
        }

        // Initialize cost accumulators
        let mut accumulated_costs = HashMap::new();
        for agent_config in &config.agent_configs {
            accumulated_costs.insert(agent_config.id.clone(), CostAccumulator::new());
        }

        Ok(Self {
            state,
            time_manager,
            rng_manager,
            policies,
            arrival_configs,
            cost_rates: config.cost_rates,
            lsm_config: config.lsm_config,
            accumulated_costs,
            event_count: 0,
            pending_settlements: Vec::new(),
            next_tx_id: 1,
        })
    }

    /// Validate configuration
    fn validate_config(config: &OrchestratorConfig) -> Result<(), SimulationError> {
        if config.ticks_per_day == 0 {
            return Err(SimulationError::InvalidConfig(
                "ticks_per_day must be > 0".to_string(),
            ));
        }

        if config.num_days == 0 {
            return Err(SimulationError::InvalidConfig(
                "num_days must be > 0".to_string(),
            ));
        }

        if config.agent_configs.is_empty() {
            return Err(SimulationError::InvalidConfig(
                "Must have at least one agent".to_string(),
            ));
        }

        // Check for duplicate agent IDs
        let mut ids = std::collections::HashSet::new();
        for agent_config in &config.agent_configs {
            if !ids.insert(&agent_config.id) {
                return Err(SimulationError::InvalidConfig(format!(
                    "Duplicate agent ID: {}",
                    agent_config.id
                )));
            }
        }

        Ok(())
    }

    // ========================================================================
    // Accessors
    // ========================================================================

    /// Get current tick number
    pub fn current_tick(&self) -> usize {
        self.time_manager.current_tick() as usize
    }

    /// Get current day number
    pub fn current_day(&self) -> usize {
        self.time_manager.current_day() as usize
    }

    /// Get reference to simulation state
    pub fn state(&self) -> &SimulationState {
        &self.state
    }

    /// Get total events logged
    pub fn event_count(&self) -> usize {
        self.event_count
    }

    /// Get accumulated costs for an agent
    pub fn get_costs(&self, agent_id: &str) -> Option<&CostAccumulator> {
        self.accumulated_costs.get(agent_id)
    }

    /// Get all accumulated costs
    pub fn all_costs(&self) -> &HashMap<String, CostAccumulator> {
        &self.accumulated_costs
    }

    // ========================================================================
    // Tick Loop Implementation
    // ========================================================================

    /// Execute one simulation tick
    ///
    /// Implements the complete tick loop integrating all components:
    /// 1. Generate arrivals (Phase 4b.2 - currently none)
    /// 2. Evaluate policies (Queue 1 → release decisions)
    /// 3. Execute settlements (RTGS)
    /// 4. Process RTGS queue (retry queued transactions)
    /// 5. Run LSM coordinator (find offsets)
    /// 6. Accrue costs (Phase 4b.3 - currently minimal)
    /// 7. Drop expired transactions
    /// 8. Advance time
    /// 9. Handle end-of-day if needed
    ///
    /// # Returns
    ///
    /// * `Ok(TickResult)` - Tick executed successfully
    /// * `Err(SimulationError)` - Execution failed
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let mut orchestrator = Orchestrator::new(config)?;
    ///
    /// for _ in 0..100 {
    ///     let result = orchestrator.tick()?;
    ///     println!("Tick {}: {} settlements", result.tick, result.num_settlements);
    /// }
    /// ```
    pub fn tick(&mut self) -> Result<TickResult, SimulationError> {
        use crate::settlement::{lsm, rtgs};

        let current_tick = self.current_tick();
        let mut num_settlements = 0;
        let mut num_lsm_releases = 0;

        // Clear pending settlements from previous tick
        self.pending_settlements.clear();

        // STEP 1: ARRIVALS (Phase 4b.2 - not implemented yet)
        let num_arrivals = 0; // TODO: Implement arrival generation

        // STEP 2: POLICY EVALUATION
        // Get agents with queued transactions (Queue 1)
        let agents_with_queues: Vec<String> = self
            .state
            .agents_with_queued_transactions()
            .into_iter()
            .collect();

        for agent_id in agents_with_queues {
            // Get agent and policy
            let agent = self
                .state
                .get_agent(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            let policy = self
                .policies
                .get_mut(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            // Evaluate policy for all transactions in Queue 1
            let decisions = policy.evaluate_queue(agent, &self.state, current_tick);

            // Process decisions
            for decision in decisions {
                use crate::policy::ReleaseDecision;

                match decision {
                    ReleaseDecision::SubmitFull { tx_id } => {
                        // Move from Queue 1 to pending settlements
                        if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                            agent.remove_from_queue(&tx_id);
                        }
                        self.pending_settlements.push(tx_id.clone());
                        self.event_count += 1; // PolicyDecision event (Phase 4b.4)
                    }
                    ReleaseDecision::SubmitPartial { .. } => {
                        // Phase 5: Transaction splitting
                        // For now, treat as error
                        return Err(SimulationError::SettlementError(
                            "Transaction splitting not implemented (Phase 5)".to_string(),
                        ));
                    }
                    ReleaseDecision::Hold { tx_id, .. } => {
                        // Transaction stays in Queue 1
                        self.event_count += 1; // PolicyHold event (Phase 4b.4)
                        // No action needed - transaction remains queued
                        let _ = tx_id; // Suppress unused warning
                    }
                    ReleaseDecision::Drop { tx_id } => {
                        // Remove from Queue 1, mark as dropped
                        if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                            agent.remove_from_queue(&tx_id);
                        }
                        if let Some(tx) = self.state.get_transaction_mut(&tx_id) {
                            tx.drop_transaction(current_tick);
                        }
                        self.event_count += 1; // Drop event (Phase 4b.4)
                    }
                }
            }
        }

        // STEP 3: RTGS SETTLEMENT
        // Process pending settlements (Queue 1 → RTGS)
        // Clone to avoid borrow checker issues
        let pending = self.pending_settlements.clone();
        for tx_id in pending.iter() {
            // Try to settle the transaction (already in state)
            let settlement_result = self.try_settle_transaction(tx_id, current_tick)?;

            match settlement_result {
                SettlementOutcome::Settled => {
                    num_settlements += 1;
                    self.event_count += 1; // Settlement event
                }
                SettlementOutcome::Queued => {
                    // Insufficient liquidity, added to Queue 2 (RTGS queue)
                    self.event_count += 1; // QueuedRtgs event
                }
            }
        }

        // STEP 4: PROCESS RTGS QUEUE (Queue 2)
        // Retry queued transactions
        let queue_result = rtgs::process_queue(&mut self.state, current_tick);
        num_settlements += queue_result.settled_count;

        // STEP 5: LSM COORDINATOR
        // Find and release offsetting transactions
        let lsm_result = lsm::run_lsm_pass(&mut self.state, &self.lsm_config, current_tick);
        num_lsm_releases = lsm_result.bilateral_offsets + lsm_result.cycles_settled;
        num_settlements += num_lsm_releases;
        self.event_count += num_lsm_releases; // LSM release events

        // STEP 6: COST ACCRUAL (Phase 4b.3 - minimal for now)
        let total_cost = self.accrue_costs(current_tick);

        // STEP 7: DEADLINE ENFORCEMENT (handled by policies in STEP 2)
        // Policies drop expired transactions via ReleaseDecision::Drop

        // STEP 8: ADVANCE TIME
        self.time_manager.advance_tick();

        // STEP 9: END-OF-DAY HANDLING
        if self.time_manager.is_end_of_day() {
            self.handle_end_of_day()?;
        }

        Ok(TickResult {
            tick: current_tick,
            num_arrivals,
            num_settlements,
            num_lsm_releases,
            total_cost,
        })
    }

    /// Accrue costs for this tick (minimal implementation)
    ///
    /// Phase 4b.3 will implement full cost calculation logic.
    /// For now, just track peak net debit.
    fn accrue_costs(&mut self, _tick: usize) -> i64 {
        let total_cost = 0;

        for (agent_id, agent) in self.state.agents() {
            if let Some(accumulator) = self.accumulated_costs.get_mut(agent_id) {
                // Track peak net debit
                accumulator.update_peak_debit(agent.balance());

                // TODO Phase 4b.3: Calculate actual costs
                // - Overdraft cost (if balance < 0)
                // - Delay cost (for queued transactions)
                // - No penalties yet (policies handle deadline drops)
            }
        }

        total_cost
    }

    /// Handle end-of-day processing
    fn handle_end_of_day(&mut self) -> Result<(), SimulationError> {
        // TODO Phase 4b: End-of-day processing
        // - Apply end-of-day penalties for unsettled transactions
        // - Reset daily counters
        // - Roll over to next day

        self.event_count += 1; // EndOfDay event

        Ok(())
    }

    /// Try to settle a transaction that's already in the state
    ///
    /// If settlement fails due to insufficient liquidity, queue the transaction.
    fn try_settle_transaction(
        &mut self,
        tx_id: &str,
        tick: usize,
    ) -> Result<SettlementOutcome, SimulationError> {
        // Get transaction details
        let (sender_id, receiver_id, amount) = {
            let tx = self
                .state
                .get_transaction(tx_id)
                .ok_or_else(|| SimulationError::TransactionNotFound(tx_id.to_string()))?;
            (
                tx.sender_id().to_string(),
                tx.receiver_id().to_string(),
                tx.remaining_amount(),
            )
        };

        // Check if sender can pay
        let can_pay = self
            .state
            .get_agent(&sender_id)
            .ok_or_else(|| SimulationError::AgentNotFound(sender_id.clone()))?
            .can_pay(amount);

        if can_pay {
            // Settle the transaction
            {
                let sender = self.state.get_agent_mut(&sender_id).unwrap();
                sender
                    .debit(amount)
                    .map_err(|e| SimulationError::SettlementError(format!("Debit failed: {}", e)))?;
            }
            {
                let receiver = self.state.get_agent_mut(&receiver_id).unwrap();
                receiver.credit(amount);
            }
            {
                let tx = self.state.get_transaction_mut(tx_id).unwrap();
                tx.settle(amount, tick)
                    .map_err(|e| SimulationError::SettlementError(format!("Settle failed: {}", e)))?;
            }

            Ok(SettlementOutcome::Settled)
        } else {
            // Queue the transaction in RTGS queue (Queue 2)
            self.state.queue_transaction(tx_id.to_string());
            Ok(SettlementOutcome::Queued)
        }
    }
}

// Manual Debug implementation (policies don't implement Debug)
impl std::fmt::Debug for Orchestrator {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Orchestrator")
            .field("current_tick", &self.current_tick())
            .field("current_day", &self.current_day())
            .field("num_agents", &self.state.num_agents())
            .field("num_transactions", &self.state.num_transactions())
            .field("event_count", &self.event_count)
            .finish()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_config() -> OrchestratorConfig {
        OrchestratorConfig {
            ticks_per_day: 100,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![
                AgentConfig {
                    id: "BANK_A".to_string(),
                    opening_balance: 1_000_000,
                    credit_limit: 500_000,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                },
                AgentConfig {
                    id: "BANK_B".to_string(),
                    opening_balance: 2_000_000,
                    credit_limit: 0,
                    policy: PolicyConfig::LiquidityAware {
                        target_buffer: 500_000,
                        urgency_threshold: 5,
                    },
                    arrival_config: None,
                },
            ],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
        }
    }

    #[test]
    fn test_orchestrator_creation() {
        let config = create_test_config();
        let orchestrator = Orchestrator::new(config).unwrap();

        assert_eq!(orchestrator.current_tick(), 0);
        assert_eq!(orchestrator.current_day(), 0);
        assert_eq!(orchestrator.state().num_agents(), 2);
        assert_eq!(orchestrator.event_count(), 0);
    }

    #[test]
    fn test_orchestrator_agents_initialized() {
        let config = create_test_config();
        let orchestrator = Orchestrator::new(config).unwrap();

        let bank_a = orchestrator.state().get_agent("BANK_A").unwrap();
        assert_eq!(bank_a.balance(), 1_000_000);
        assert_eq!(bank_a.credit_limit(), 500_000);

        let bank_b = orchestrator.state().get_agent("BANK_B").unwrap();
        assert_eq!(bank_b.balance(), 2_000_000);
        assert_eq!(bank_b.credit_limit(), 0);
    }

    #[test]
    fn test_orchestrator_policies_initialized() {
        let config = create_test_config();
        let orchestrator = Orchestrator::new(config).unwrap();

        assert!(orchestrator.policies.contains_key("BANK_A"));
        assert!(orchestrator.policies.contains_key("BANK_B"));
        assert_eq!(orchestrator.policies.len(), 2);
    }

    #[test]
    fn test_validate_config_empty_agents() {
        let config = OrchestratorConfig {
            ticks_per_day: 100,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
        };

        let result = Orchestrator::new(config);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            SimulationError::InvalidConfig(_)
        ));
    }

    #[test]
    fn test_validate_config_zero_ticks() {
        let mut config = create_test_config();
        config.ticks_per_day = 0;

        let result = Orchestrator::new(config);
        assert!(result.is_err());
    }

    #[test]
    fn test_validate_config_duplicate_agent_ids() {
        let config = OrchestratorConfig {
            ticks_per_day: 100,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![
                AgentConfig {
                    id: "BANK_A".to_string(),
                    opening_balance: 1_000_000,
                    credit_limit: 0,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                },
                AgentConfig {
                    id: "BANK_A".to_string(), // Duplicate!
                    opening_balance: 2_000_000,
                    credit_limit: 0,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                },
            ],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
        };

        let result = Orchestrator::new(config);
        assert!(result.is_err());
    }

    #[test]
    fn test_cost_accumulator() {
        let mut acc = CostAccumulator::new();

        let cost1 = CostBreakdown {
            liquidity_cost: 100,
            delay_cost: 50,
            penalty_cost: 0,
        };

        acc.add(&cost1);
        assert_eq!(acc.total_liquidity_cost, 100);
        assert_eq!(acc.total_delay_cost, 50);
        assert_eq!(acc.total(), 150);

        let cost2 = CostBreakdown {
            liquidity_cost: 200,
            delay_cost: 100,
            penalty_cost: 500,
        };

        acc.add(&cost2);
        assert_eq!(acc.total_liquidity_cost, 300);
        assert_eq!(acc.total_delay_cost, 150);
        assert_eq!(acc.total_penalty_cost, 500);
        assert_eq!(acc.total(), 950);
    }

    #[test]
    fn test_peak_net_debit_tracking() {
        let mut acc = CostAccumulator::new();

        acc.update_peak_debit(1_000_000); // Positive, no change
        assert_eq!(acc.peak_net_debit, 0);

        acc.update_peak_debit(-100_000); // Negative
        assert_eq!(acc.peak_net_debit, -100_000);

        acc.update_peak_debit(-50_000); // Less negative, no change
        assert_eq!(acc.peak_net_debit, -100_000);

        acc.update_peak_debit(-200_000); // More negative
        assert_eq!(acc.peak_net_debit, -200_000);
    }

    #[test]
    fn test_cost_breakdown_total() {
        let cost = CostBreakdown {
            liquidity_cost: 1000,
            delay_cost: 500,
            penalty_cost: 2000,
        };

        assert_eq!(cost.total(), 3500);
    }
}
