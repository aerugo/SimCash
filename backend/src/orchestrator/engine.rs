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

use crate::arrivals::{ArrivalConfig, ArrivalGenerator, AmountDistribution};
use crate::core::time::TimeManager;
use crate::models::agent::Agent;
use crate::models::event::{Event, EventLog};
use crate::models::state::SimulationState;
use crate::policy::{CashManagerPolicy, DeadlinePolicy, FifoPolicy, LiquidityAwarePolicy, LiquiditySplittingPolicy, MockSplittingPolicy};
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

    /// Liquidity-aware splitting policy (Phase 5)
    ///
    /// Intelligently splits large payments when liquidity is constrained.
    /// Balances split friction cost against liquidity and deadline urgency.
    LiquiditySplitting {
        /// Maximum number of splits allowed per transaction
        max_splits: usize,
        /// Minimum amount per split (don't create tiny splits)
        min_split_amount: i64,
    },

    /// Mock splitting policy for testing (Phase 5)
    ///
    /// Always splits transactions into fixed number of parts.
    /// Used in tests to verify splitting mechanics.
    ///
    /// NOTE: Available in all builds to support integration testing,
    /// but should only be used in test code.
    MockSplitting {
        /// Number of splits to create for every transaction
        num_splits: usize,
    },
}

// ArrivalConfig is now imported from crate::arrivals module

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

    /// Split friction cost per split (cents)
    ///
    /// When a transaction is split into N parts, the cost is:
    /// split_friction_cost × (N-1)
    ///
    /// This represents the operational overhead of creating and processing
    /// multiple payment instructions instead of a single instruction.
    pub split_friction_cost: i64,
}

impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,            // 1 bp/tick
            delay_cost_per_tick_per_cent: 0.0001,     // 0.1 bp/tick
            eod_penalty_per_transaction: 10_000,      // $100 per unsettled tx
            deadline_penalty: 50_000,                  // $500 per missed deadline
            split_friction_cost: 1000,                 // $10 per split
        }
    }
}

/// Cost breakdown for a single tick or agent
#[derive(Debug, Clone, Default, PartialEq)]
pub struct CostBreakdown {
    /// Overdraft cost accrued this tick (cents)
    pub liquidity_cost: i64,

    /// Queue delay cost accrued this tick (cents)
    pub delay_cost: i64,

    /// Penalties incurred this tick (cents)
    pub penalty_cost: i64,

    /// Transaction splitting friction cost (cents)
    ///
    /// When a policy decides to split a transaction into N parts,
    /// a friction cost is charged using the formula: f_s × (N-1)
    /// where f_s is the per-split friction rate (split_friction_cost).
    ///
    /// This represents the operational overhead of creating and
    /// processing multiple smaller payments instead of one large payment.
    pub split_friction_cost: i64,
}

impl CostBreakdown {
    /// Total cost across all categories
    pub fn total(&self) -> i64 {
        self.liquidity_cost + self.delay_cost + self.penalty_cost + self.split_friction_cost
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

    /// Total split friction cost
    pub total_split_friction_cost: i64,

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
        self.total_split_friction_cost += costs.split_friction_cost;
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

    /// Arrival generator for automatic transaction creation
    arrival_generator: Option<ArrivalGenerator>,

    /// Cost calculation rates
    cost_rates: CostRates,

    /// LSM configuration
    lsm_config: LsmConfig,

    /// Accumulated costs per agent
    accumulated_costs: HashMap<String, CostAccumulator>,

    /// Event log (all simulation events)
    event_log: EventLog,

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
                PolicyConfig::LiquiditySplitting {
                    max_splits,
                    min_split_amount,
                } => Box::new(LiquiditySplittingPolicy::new(
                    *max_splits,
                    *min_split_amount,
                )),
                PolicyConfig::MockSplitting { num_splits } => {
                    Box::new(MockSplittingPolicy::new(*num_splits))
                }
            };
            policies.insert(agent_config.id.clone(), policy);
        }

        // Initialize arrival generator (if any agents have arrival configs)
        let mut arrival_configs_map = HashMap::new();
        for agent_config in &config.agent_configs {
            if let Some(arrival_cfg) = &agent_config.arrival_config {
                arrival_configs_map.insert(agent_config.id.clone(), arrival_cfg.clone());
            }
        }

        let arrival_generator = if !arrival_configs_map.is_empty() {
            let all_agent_ids: Vec<String> = config
                .agent_configs
                .iter()
                .map(|ac| ac.id.clone())
                .collect();
            Some(ArrivalGenerator::new(arrival_configs_map, all_agent_ids))
        } else {
            None
        };

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
            arrival_generator,
            cost_rates: config.cost_rates,
            lsm_config: config.lsm_config,
            accumulated_costs,
            event_log: EventLog::new(),
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

    /// Get mutable reference to simulation state
    ///
    /// # Safety
    ///
    /// This is primarily for testing. Direct state mutation bypasses
    /// orchestrator invariants. Use with caution.
    pub fn state_mut(&mut self) -> &mut SimulationState {
        &mut self.state
    }

    /// Get total events logged
    pub fn event_count(&self) -> usize {
        self.event_log.len()
    }

    /// Get reference to event log
    pub fn event_log(&self) -> &EventLog {
        &self.event_log
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
    // Event Logging
    // ========================================================================

    /// Log an event to the event log
    fn log_event(&mut self, event: Event) {
        self.event_log.log(event);
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

        // Clear pending settlements from previous tick
        self.pending_settlements.clear();

        // STEP 1: ARRIVALS
        // Generate new transactions according to arrival configurations
        let mut num_arrivals = 0;
        let mut arrival_events = Vec::new();

        if let Some(generator) = &mut self.arrival_generator {
            // Get all agent IDs that have arrival configs
            let agent_ids: Vec<String> = self.state.get_all_agent_ids();

            for agent_id in agent_ids {
                // Generate arrivals for this agent
                let new_transactions = generator.generate_for_agent(&agent_id, current_tick, &mut self.rng_manager);
                num_arrivals += new_transactions.len();

                // Add transactions to state and queue them
                for tx in new_transactions {
                    let tx_id = tx.id().to_string();

                    // Collect arrival event for logging (after generator is done)
                    arrival_events.push(Event::Arrival {
                        tick: current_tick,
                        tx_id: tx_id.clone(),
                        sender_id: tx.sender_id().to_string(),
                        receiver_id: tx.receiver_id().to_string(),
                        amount: tx.amount(),
                        deadline: tx.deadline_tick(),
                    });

                    self.state.add_transaction(tx);

                    // Queue in the sender's outgoing queue (Queue 1)
                    if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                        agent.queue_outgoing(tx_id);
                    }
                }
            }
        }

        // Log arrival events (after generator is done to avoid borrow checker issues)
        for event in arrival_events {
            self.log_event(event);
        }

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
            // Pass cost_rates for policy decision-making (read-only, external)
            let decisions = policy.evaluate_queue(agent, &self.state, current_tick, &self.cost_rates);

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

                        // Log policy submit event
                        self.log_event(Event::PolicySubmit {
                            tick: current_tick,
                            agent_id: agent_id.clone(),
                            tx_id,
                        });
                    }
                    ReleaseDecision::SubmitPartial { tx_id, num_splits } => {
                        // Phase 5: Transaction splitting implementation

                        // Validate num_splits
                        if num_splits < 2 {
                            return Err(SimulationError::SettlementError(
                                format!("num_splits must be >= 2, got {}", num_splits)
                            ));
                        }

                        // Get parent transaction
                        let parent_tx = self.state.get_transaction(&tx_id)
                            .ok_or_else(|| SimulationError::SettlementError(
                                format!("Transaction {} not found for splitting", tx_id)
                            ))?
                            .clone();

                        // Remove parent from Queue 1 (will be replaced by children)
                        if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                            agent.remove_from_queue(&tx_id);
                        }

                        // Calculate child amounts (equal splits with remainder in last)
                        let total_amount = parent_tx.amount();
                        let base_amount = total_amount / num_splits as i64;
                        let remainder = total_amount % num_splits as i64;

                        // Create child transactions
                        let mut child_ids = Vec::new();
                        for i in 0..num_splits {
                            let child_amount = if i == num_splits - 1 {
                                base_amount + remainder // Last child gets remainder
                            } else {
                                base_amount
                            };

                            // Create child transaction
                            let mut child = crate::models::Transaction::new_split(
                                parent_tx.sender_id().to_string(),
                                parent_tx.receiver_id().to_string(),
                                child_amount,
                                parent_tx.arrival_tick(),
                                parent_tx.deadline_tick(),
                                tx_id.clone(),
                            );

                            // Preserve parent's priority
                            child = child.with_priority(parent_tx.priority());

                            let child_id = child.id().to_string();
                            child_ids.push(child_id.clone());

                            // Add child to state and pending settlements
                            self.state.add_transaction(child);
                            self.pending_settlements.push(child_id);
                        }

                        // Calculate and charge split friction cost
                        let friction_cost = self.cost_rates.split_friction_cost * (num_splits as i64 - 1);

                        if friction_cost > 0 {
                            if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
                                accumulator.total_split_friction_cost += friction_cost;
                            }

                            // Log friction cost event
                            self.log_event(Event::CostAccrual {
                                tick: current_tick,
                                agent_id: agent_id.clone(),
                                costs: CostBreakdown {
                                    liquidity_cost: 0,
                                    delay_cost: 0,
                                    penalty_cost: 0,
                                    split_friction_cost: friction_cost,
                                },
                            });
                        }

                        // Log policy split event
                        self.log_event(Event::PolicySplit {
                            tick: current_tick,
                            agent_id: agent_id.clone(),
                            tx_id,
                            num_splits,
                            child_ids,
                        });
                    }
                    ReleaseDecision::Hold { tx_id, reason } => {
                        // Transaction stays in Queue 1
                        // Log policy hold event
                        self.log_event(Event::PolicyHold {
                            tick: current_tick,
                            agent_id: agent_id.clone(),
                            tx_id,
                            reason: format!("{:?}", reason),
                        });
                    }
                    ReleaseDecision::Drop { tx_id } => {
                        // Remove from Queue 1, mark as dropped
                        if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                            agent.remove_from_queue(&tx_id);
                        }
                        if let Some(tx) = self.state.get_transaction_mut(&tx_id) {
                            tx.drop_transaction(current_tick);
                        }

                        // Log policy drop event
                        self.log_event(Event::PolicyDrop {
                            tick: current_tick,
                            agent_id: agent_id.clone(),
                            tx_id,
                            reason: "Expired deadline".to_string(),
                        });
                    }
                }
            }
        }

        // STEP 3: RTGS SETTLEMENT
        // Process pending settlements (Queue 1 → RTGS)
        // Clone to avoid borrow checker issues
        let pending = self.pending_settlements.clone();
        for tx_id in pending.iter() {
            // Get transaction details for event logging
            let (sender_id, receiver_id, amount) = {
                let tx = self.state.get_transaction(tx_id)
                    .ok_or_else(|| SimulationError::TransactionNotFound(tx_id.clone()))?;
                (tx.sender_id().to_string(), tx.receiver_id().to_string(), tx.remaining_amount())
            };

            // Try to settle the transaction (already in state)
            let settlement_result = self.try_settle_transaction(tx_id, current_tick)?;

            match settlement_result {
                SettlementOutcome::Settled => {
                    num_settlements += 1;

                    // Log settlement event
                    self.log_event(Event::Settlement {
                        tick: current_tick,
                        tx_id: tx_id.clone(),
                        sender_id,
                        receiver_id,
                        amount,
                    });
                }
                SettlementOutcome::Queued => {
                    // Insufficient liquidity, added to Queue 2 (RTGS queue)
                    // Log queued event
                    self.log_event(Event::QueuedRtgs {
                        tick: current_tick,
                        tx_id: tx_id.clone(),
                        sender_id,
                    });
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
        let num_lsm_releases = lsm_result.bilateral_offsets + lsm_result.cycles_settled;
        num_settlements += num_lsm_releases;

        // TODO: Log detailed LSM events
        // Currently the LSM module doesn't return enough details for proper event logging
        // Would need to track which specific transactions were settled via LSM

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

    /// Accrue costs for this tick
    ///
    /// Calculates and accumulates:
    /// - Overdraft costs (basis points per tick on negative balance)
    /// - Delay costs (cost per tick per cent of queued value)
    ///
    /// Penalties for dropped transactions are handled in policy evaluation.
    /// End-of-day penalties are handled in handle_end_of_day().
    fn accrue_costs(&mut self, tick: usize) -> i64 {
        let mut total_cost = 0;

        // Collect agent IDs first to avoid borrow checker issues
        let agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

        for agent_id in agent_ids {
            let agent = self.state.get_agent(&agent_id).unwrap();

            // Calculate overdraft cost (liquidity cost)
            let liquidity_cost = self.calculate_overdraft_cost(agent.balance());

            // Calculate delay cost for queued transactions
            let delay_cost = self.calculate_delay_cost(&agent_id);

            // No penalty or split friction cost in this step
            // (penalties handled by policies and EOD, splits handled at decision time)
            let penalty_cost = 0;
            let split_friction_cost = 0;

            let costs = CostBreakdown {
                liquidity_cost,
                delay_cost,
                penalty_cost,
                split_friction_cost,
            };

            // Accumulate costs
            if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
                accumulator.add(&costs);
                accumulator.update_peak_debit(agent.balance());
            }

            total_cost += costs.total();

            // Log cost accrual event if there are any costs
            if costs.total() > 0 {
                self.log_event(Event::CostAccrual {
                    tick,
                    agent_id: agent_id.clone(),
                    costs,
                });
            }
        }

        total_cost
    }

    /// Calculate overdraft cost for a given balance
    ///
    /// Overdraft cost = max(0, -balance) * overdraft_bps_per_tick
    ///
    /// Example: -$500,000 balance at 0.001 bps/tick = 500 basis points = $5
    fn calculate_overdraft_cost(&self, balance: i64) -> i64 {
        if balance >= 0 {
            return 0;
        }

        let overdraft_amount = (-balance) as f64;
        let cost = overdraft_amount * self.cost_rates.overdraft_bps_per_tick;
        cost as i64
    }

    /// Calculate delay cost for queued transactions
    ///
    /// Delay cost = sum of (queued transaction values) * delay_cost_per_tick_per_cent
    ///
    /// Only counts transactions in Queue 1 (agent's internal queue).
    /// RTGS queue delays are not penalized (waiting for liquidity is expected).
    fn calculate_delay_cost(&self, agent_id: &str) -> i64 {
        let agent = match self.state.get_agent(agent_id) {
            Some(a) => a,
            None => return 0,
        };

        let mut total_queued_value = 0;

        // Sum up value of all transactions in Queue 1
        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = self.state.get_transaction(tx_id) {
                total_queued_value += tx.remaining_amount();
            }
        }

        let cost = (total_queued_value as f64) * self.cost_rates.delay_cost_per_tick_per_cent;
        cost as i64
    }

    /// Handle end-of-day processing
    ///
    /// Applies penalties for unsettled transactions at end of day.
    /// Each agent pays eod_penalty_per_transaction for each unsettled transaction
    /// in their Queue 1 (internal queue).
    fn handle_end_of_day(&mut self) -> Result<(), SimulationError> {
        let current_tick = self.current_tick();
        let current_day = self.current_day();

        let mut total_penalties = 0;

        // Collect agent IDs to avoid borrow checker issues
        let agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

        for agent_id in agent_ids {
            let agent = self.state.get_agent(&agent_id).unwrap();

            // Count unsettled transactions in Queue 1
            let unsettled_count = agent.outgoing_queue().len();

            if unsettled_count > 0 {
                // Calculate penalty
                let penalty = (unsettled_count as i64) * self.cost_rates.eod_penalty_per_transaction;
                total_penalties += penalty;

                // Accumulate penalty cost
                if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
                    accumulator.total_penalty_cost += penalty;
                }

                // Log cost accrual event for EOD penalty
                self.log_event(Event::CostAccrual {
                    tick: current_tick,
                    agent_id: agent_id.clone(),
                    costs: CostBreakdown {
                        liquidity_cost: 0,
                        delay_cost: 0,
                        penalty_cost: penalty,
                        split_friction_cost: 0,
                    },
                });
            }
        }

        // Count total unsettled transactions across all queues
        let unsettled_count = self.state.queue_size() + self.state.total_internal_queue_size();

        // Log end-of-day event
        self.log_event(Event::EndOfDay {
            tick: current_tick,
            day: current_day,
            unsettled_count,
            total_penalties,
        });

        // TODO: Reset daily counters if needed for multi-day simulations

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
            .field("event_count", &self.event_count())
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
            split_friction_cost: 0,
        };

        acc.add(&cost1);
        assert_eq!(acc.total_liquidity_cost, 100);
        assert_eq!(acc.total_delay_cost, 50);
        assert_eq!(acc.total(), 150);

        let cost2 = CostBreakdown {
            liquidity_cost: 200,
            delay_cost: 100,
            penalty_cost: 500,
            split_friction_cost: 0,
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
            split_friction_cost: 250,
        };

        assert_eq!(cost.total(), 3750); // 1000 + 500 + 2000 + 250
    }
}
