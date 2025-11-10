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

use crate::arrivals::{ArrivalConfig, ArrivalGenerator};
use crate::core::time::TimeManager;
use crate::models::agent::Agent;
use crate::models::event::{Event, EventLog};
use crate::models::state::SimulationState;
use crate::models::transaction::Transaction;
use crate::policy::CashManagerPolicy;
use crate::rng::RngManager;
use crate::settlement::lsm::LsmConfig;
use std::collections::HashMap;

// ============================================================================
// Configuration Types
// ============================================================================

/// Default EOD rush threshold for serde deserialization (Phase 9.5.2)
fn default_eod_rush_threshold() -> f64 {
    0.8
}

/// Complete orchestrator configuration
///
/// This struct contains all parameters needed to initialize a simulation.
///
/// # Fields
///
/// * `ticks_per_day` - Number of discrete time steps per business day
/// * `eod_rush_threshold` - Fraction of day (0.0-1.0) that defines EOD rush period start
/// * `num_days` - Total simulation duration in days
/// * `rng_seed` - Seed for deterministic random number generation
/// * `agent_configs` - Configuration for each participating agent (bank)
/// * `cost_rates` - Rates for calculating liquidity, delay, and penalty costs
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct OrchestratorConfig {
    /// Number of ticks per business day (e.g., 100 ticks = 1 tick per ~5 minutes)
    pub ticks_per_day: usize,

    /// End-of-day rush threshold (Phase 9.5.2)
    /// Fraction of day (0.0 to 1.0) when EOD rush period begins.
    /// Default: 0.8 (last 20% of day)
    /// Policies can check `is_eod_rush` field to enable time-based strategies.
    #[serde(default = "default_eod_rush_threshold")]
    pub eod_rush_threshold: f64,

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

    /// Scenario events (optional)
    /// Scheduled events that modify simulation state at specific ticks
    #[serde(default)]
    pub scenario_events: Option<Vec<crate::events::ScheduledEvent>>,
}

/// Per-agent configuration
///
/// Specifies initial state and behavior for a single agent (bank).
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
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

    /// Posted collateral amount (cents) - Phase 8
    /// If None, defaults to 0 (no collateral)
    pub posted_collateral: Option<i64>,
}

/// Policy selection for an agent
///
/// Determines which cash manager policy algorithm to use for Queue 1 decisions.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
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

    /// Custom JSON policy for testing
    ///
    /// Allows tests to pass arbitrary JSON policy definitions without
    /// requiring policy files. Useful for integration tests that need
    /// specific policy configurations.
    ///
    /// NOTE: Available in all builds to support integration testing,
    /// but should only be used in test code.
    FromJson {
        /// JSON string containing complete policy definition
        json: String,
    },
}

// ArrivalConfig is now imported from crate::arrivals module

/// Cost calculation rates
///
/// Defines rates for various costs accrued during simulation.
/// All monetary values in cents/minor units.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct CostRates {
    /// Overdraft cost in basis points per tick
    /// (e.g., 0.001 = 1 bp per tick ≈ 10 bp per day for 100 ticks/day)
    pub overdraft_bps_per_tick: f64,

    /// Delay cost per tick per cent of queued value
    /// (e.g., 0.0001 = 1 bp delay cost per tick)
    pub delay_cost_per_tick_per_cent: f64,

    /// Collateral opportunity cost in basis points per tick (Phase 8)
    /// (e.g., 0.0002 = 2 bps annualized / 100 ticks = 0.02 bps per tick)
    pub collateral_cost_per_tick_bps: f64,

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

    /// Multiplier for delay cost when transaction is overdue (default: 5.0)
    ///
    /// Overdue transactions incur escalating costs to represent urgency.
    /// If a transaction is overdue, its delay cost per tick is multiplied by this factor.
    ///
    /// Example: If delay_cost_per_tick_per_cent = 0.0001 and overdue_delay_multiplier = 5.0,
    /// then an overdue $1M transaction costs $5/tick instead of $1/tick.
    pub overdue_delay_multiplier: f64,
}

impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,        // 1 bp/tick
            delay_cost_per_tick_per_cent: 0.0001, // 0.1 bp/tick
            collateral_cost_per_tick_bps: 0.0002, // 2 bps annualized / 100 ticks
            eod_penalty_per_transaction: 10_000,  // $100 per unsettled tx
            deadline_penalty: 50_000,             // $500 per missed deadline
            split_friction_cost: 1000,            // $10 per split
            overdue_delay_multiplier: 5.0,        // 5x multiplier for overdue
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

    /// Collateral opportunity cost accrued this tick (cents) - Phase 8
    pub collateral_cost: i64,

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
        self.liquidity_cost
            + self.delay_cost
            + self.collateral_cost
            + self.penalty_cost
            + self.split_friction_cost
    }
}

/// Accumulated costs for an agent over time
#[derive(Debug, Clone, Default)]
pub struct CostAccumulator {
    /// Total liquidity cost (overdraft)
    pub total_liquidity_cost: i64,

    /// Total delay cost
    pub total_delay_cost: i64,

    /// Total collateral opportunity cost (Phase 8)
    pub total_collateral_cost: i64,

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
        self.total_collateral_cost += costs.collateral_cost;
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
        self.total_liquidity_cost
            + self.total_delay_cost
            + self.total_collateral_cost
            + self.total_penalty_cost
            + self.total_split_friction_cost
    }
}

// ============================================================================
// System-Wide Metrics (Phase 8: Cost Model API)
// ============================================================================

/// System-wide performance metrics
///
/// Provides comprehensive view of simulation health and efficiency.
/// Used for Phase 8 API endpoints and monitoring dashboards.
#[derive(Debug, Clone)]
pub struct SystemMetrics {
    /// Total transactions that have arrived in the system
    pub total_arrivals: usize,

    /// Total transactions that have been settled (fully or partially)
    pub total_settlements: usize,

    /// Settlement rate: settlements / arrivals (0.0 to 1.0)
    pub settlement_rate: f64,

    /// Average delay in ticks for settled transactions
    pub avg_delay_ticks: f64,

    /// Maximum delay in ticks observed
    pub max_delay_ticks: usize,

    /// Total number of transactions in all agent queues (Queue 1)
    pub queue1_total_size: usize,

    /// Total number of transactions in RTGS queue (Queue 2)
    pub queue2_total_size: usize,

    /// Peak overdraft observed across all agents (absolute value)
    pub peak_overdraft: i64,

    /// Number of agents currently in overdraft
    pub agents_in_overdraft: usize,
}

// ============================================================================
// Daily Metrics Tracking (Phase 3: Agent Metrics Collection)
// ============================================================================

/// Daily agent metrics collected during simulation
///
/// Tracks per-agent statistics for a single day, reset at start of each day.
/// These metrics enable fast queries for agent performance analysis without
/// scanning all transactions.
#[derive(Debug, Clone)]
pub struct DailyMetrics {
    /// Agent identifier
    pub agent_id: String,

    /// Day number (0-indexed)
    pub day: usize,

    // Balance metrics
    pub opening_balance: i64,
    pub closing_balance: i64,
    pub min_balance: i64,
    pub max_balance: i64,

    // Credit usage
    pub credit_limit: i64,
    pub peak_overdraft: i64,

    // Collateral management (Phase 8)
    pub opening_posted_collateral: i64,
    pub closing_posted_collateral: i64,
    pub peak_posted_collateral: i64,
    pub collateral_capacity: i64,
    pub num_collateral_posts: usize,
    pub num_collateral_withdrawals: usize,

    // Transaction counts
    pub num_arrivals: usize,
    pub num_sent: usize,
    pub num_received: usize,
    pub num_settled: usize,
    pub num_dropped: usize,

    // Queue metrics
    pub queue1_peak_size: usize,
    pub queue1_eod_size: usize,

    // Costs (captured from CostAccumulator at EOD)
    pub liquidity_cost: i64,
    pub delay_cost: i64,
    pub collateral_cost: i64,
    pub split_friction_cost: i64,
    pub deadline_penalty_cost: i64,
    pub total_cost: i64,
}

impl DailyMetrics {
    /// Create new daily metrics for an agent at start of day
    fn new(agent_id: String, day: usize, agent: &Agent) -> Self {
        let credit_limit = agent.credit_limit();
        let opening_balance = agent.balance();
        let opening_posted_collateral = agent.posted_collateral();

        Self {
            agent_id,
            day,
            opening_balance,
            closing_balance: opening_balance, // Will be updated at EOD
            min_balance: opening_balance,
            max_balance: opening_balance,
            credit_limit,
            peak_overdraft: 0,
            opening_posted_collateral,
            closing_posted_collateral: opening_posted_collateral,
            peak_posted_collateral: opening_posted_collateral,
            collateral_capacity: credit_limit * 10, // 10x leverage
            num_collateral_posts: 0,
            num_collateral_withdrawals: 0,
            num_arrivals: 0,
            num_sent: 0,
            num_received: 0,
            num_settled: 0,
            num_dropped: 0,
            queue1_peak_size: 0,
            queue1_eod_size: 0,
            liquidity_cost: 0,
            delay_cost: 0,
            collateral_cost: 0,
            split_friction_cost: 0,
            deadline_penalty_cost: 0,
            total_cost: 0,
        }
    }

    /// Update balance tracking (called after balance changes)
    fn update_balance(&mut self, new_balance: i64) {
        self.min_balance = self.min_balance.min(new_balance);
        self.max_balance = self.max_balance.max(new_balance);

        // Peak overdraft = most negative balance seen
        if new_balance < 0 {
            self.peak_overdraft = self.peak_overdraft.max(new_balance.abs());
        }
    }

    /// Update collateral tracking (called after collateral changes)
    fn update_collateral(&mut self, new_collateral: i64) {
        self.peak_posted_collateral = self.peak_posted_collateral.max(new_collateral);
    }

    /// Update queue size tracking (called each tick)
    fn update_queue_size(&mut self, current_size: usize) {
        self.queue1_peak_size = self.queue1_peak_size.max(current_size);
    }

    /// Finalize metrics at end of day
    fn finalize(&mut self, agent: &Agent, costs: &CostAccumulator) {
        self.closing_balance = agent.balance();
        self.closing_posted_collateral = agent.posted_collateral();
        self.queue1_eod_size = agent.outgoing_queue_size();

        // Capture costs from accumulator
        self.liquidity_cost = costs.total_liquidity_cost;
        self.delay_cost = costs.total_delay_cost;
        self.collateral_cost = costs.total_collateral_cost;
        self.split_friction_cost = costs.total_split_friction_cost;
        self.deadline_penalty_cost = costs.total_penalty_cost;
        self.total_cost = costs.total();
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
    /// Original configuration (stored for checkpoint hash verification)
    config: OrchestratorConfig,

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

    /// Daily metrics for current day (Phase 3: Agent Metrics Collection)
    /// Key: agent_id
    current_day_metrics: HashMap<String, DailyMetrics>,

    /// Historical daily metrics for completed days (Phase 3: Agent Metrics Collection)
    /// Key: (agent_id, day)
    historical_metrics: HashMap<(String, usize), DailyMetrics>,

    /// Scenario event handler for scheduled events
    scenario_event_handler: Option<crate::events::ScenarioEventHandler>,
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

    /// Serialization error (checkpoint save)
    SerializationError(String),

    /// Deserialization error (checkpoint load)
    DeserializationError(String),

    /// Config mismatch (checkpoint from different config)
    ConfigMismatch { expected: String, actual: String },

    /// State validation error (invariant violated)
    StateValidationError(String),
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
            SimulationError::SerializationError(msg) => write!(f, "Serialization error: {}", msg),
            SimulationError::DeserializationError(msg) => {
                write!(f, "Deserialization error: {}", msg)
            }
            SimulationError::ConfigMismatch { expected, actual } => write!(
                f,
                "Config mismatch: expected hash {}, got {}",
                expected, actual
            ),
            SimulationError::StateValidationError(msg) => {
                write!(f, "State validation error: {}", msg)
            }
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
    /// ```rust,no_run
    /// use payment_simulator_core_rs::orchestrator::{Orchestrator, OrchestratorConfig, AgentConfig, PolicyConfig};
    /// use payment_simulator_core_rs::settlement::lsm::LsmConfig;
    ///
    /// let config = OrchestratorConfig {
    ///     ticks_per_day: 100,
    ///     eod_rush_threshold: 0.8,
    ///     num_days: 1,
    ///     rng_seed: 12345,
    ///     agent_configs: vec![
    ///         AgentConfig {
    ///             id: "BANK_A".to_string(),
    ///             opening_balance: 1_000_000,
    ///             credit_limit: 0,
    ///             policy: PolicyConfig::Fifo,
    ///             arrival_config: None,
    ///             posted_collateral: None,
    ///         },
    ///     ],
    ///     cost_rates: Default::default(),
    ///     lsm_config: LsmConfig::default(),
    ///     scenario_events: None,
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
            .map(|ac| {
                let mut agent = Agent::new(ac.id.clone(), ac.opening_balance, ac.credit_limit);
                // Set posted collateral if specified (Phase 8)
                if let Some(collateral) = ac.posted_collateral {
                    agent.set_posted_collateral(collateral);
                }
                agent
            })
            .collect();

        let state = SimulationState::new(agents);

        // Initialize time manager
        let time_manager = TimeManager::new(config.ticks_per_day);

        // Initialize RNG
        let rng_manager = RngManager::new(config.rng_seed);

        // Initialize policies
        // All policies now use JSON-based TreePolicy loaded via factory
        let mut policies: HashMap<String, Box<dyn CashManagerPolicy>> = HashMap::new();
        for agent_config in &config.agent_configs {
            let tree_policy =
                crate::policy::tree::create_policy(&agent_config.policy).map_err(|e| {
                    SimulationError::InvalidConfig(format!(
                        "Failed to create JSON policy for agent {}: {}",
                        agent_config.id, e
                    ))
                })?;
            policies.insert(agent_config.id.clone(), Box::new(tree_policy));
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

        // Initialize daily metrics for day 0 (Phase 3: Agent Metrics Collection)
        let mut current_day_metrics = HashMap::new();
        for agent_config in &config.agent_configs {
            let agent = state.get_agent(&agent_config.id).unwrap();
            let metrics = DailyMetrics::new(agent_config.id.clone(), 0, agent);
            current_day_metrics.insert(agent_config.id.clone(), metrics);
        }

        // Initialize scenario event handler (if events configured)
        let scenario_event_handler = config
            .scenario_events
            .as_ref()
            .map(|events| crate::events::ScenarioEventHandler::new(events.clone()));

        // Clone values we need before moving config
        let cost_rates = config.cost_rates.clone();
        let lsm_config = config.lsm_config.clone();

        Ok(Self {
            config,
            state,
            time_manager,
            rng_manager,
            policies,
            arrival_generator,
            cost_rates,
            lsm_config,
            accumulated_costs,
            event_log: EventLog::new(),
            pending_settlements: Vec::new(),
            next_tx_id: 1,
            current_day_metrics,
            historical_metrics: HashMap::new(),
            scenario_event_handler,
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

    /// Get reference to cost rates configuration
    pub fn cost_rates(&self) -> &CostRates {
        &self.cost_rates
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
    // Scenario Event Support - Query Methods
    // ========================================================================
    // Note: get_agent_balance and get_agent_credit_limit are defined
    // in the "State Query Methods" section below (Phase 7: FFI Integration)

    /// Get arrival rate for an agent
    pub fn get_arrival_rate(&self, agent_id: &str) -> Option<f64> {
        self.arrival_generator
            .as_ref()
            .and_then(|gen| gen.get_rate(agent_id))
    }

    /// Get counterparty weight for an agent
    pub fn get_counterparty_weight(&self, agent_id: &str, counterparty: &str) -> Option<f64> {
        self.arrival_generator
            .as_ref()
            .and_then(|gen| gen.get_counterparty_weight(agent_id, counterparty))
    }

    /// Get deadline range for an agent
    pub fn get_deadline_range(&self, agent_id: &str) -> Option<(usize, usize)> {
        self.arrival_generator
            .as_ref()
            .and_then(|gen| gen.get_deadline_range(agent_id))
    }

    // ========================================================================
    // Scenario Event Execution
    // ========================================================================

    /// Execute a scenario event
    ///
    /// Handles both simple events (delegated to SimulationState) and complex events
    /// (requiring Orchestrator-level coordination)
    fn execute_scenario_event(
        &mut self,
        event: &crate::events::ScenarioEvent,
        tick: usize,
    ) -> Result<(), SimulationError> {
        use crate::events::ScenarioEvent;
        use serde_json::json;

        match event {
            // Simple events: delegate to SimulationState
            ScenarioEvent::DirectTransfer { from_agent, to_agent, amount } => {
                event.execute(&mut self.state, tick).map_err(|e| {
                    SimulationError::InvalidConfig(format!("Scenario event failed: {}", e))
                })?;

                // Log to Orchestrator's event log
                self.log_event(crate::models::Event::ScenarioEventExecuted {
                    tick,
                    event_type: "direct_transfer".to_string(),
                    details: json!({
                        "from_agent": from_agent,
                        "to_agent": to_agent,
                        "amount": amount,
                    }),
                });
            }

            ScenarioEvent::CollateralAdjustment { agent, delta } => {
                event.execute(&mut self.state, tick).map_err(|e| {
                    SimulationError::InvalidConfig(format!("Scenario event failed: {}", e))
                })?;

                // Log to Orchestrator's event log
                self.log_event(crate::models::Event::ScenarioEventExecuted {
                    tick,
                    event_type: "collateral_adjustment".to_string(),
                    details: json!({
                        "agent": agent,
                        "delta": delta,
                    }),
                });
            }

            // Complex events: handle at Orchestrator level
            ScenarioEvent::GlobalArrivalRateChange { multiplier } => {
                if *multiplier <= 0.0 {
                    return Err(SimulationError::InvalidConfig(
                        "Arrival rate multiplier must be positive".to_string(),
                    ));
                }

                if let Some(generator) = &mut self.arrival_generator {
                    generator.multiply_all_rates(*multiplier);

                    // Log event
                    self.log_event(crate::models::Event::ScenarioEventExecuted {
                        tick,
                        event_type: "global_arrival_rate_change".to_string(),
                        details: json!({
                            "multiplier": multiplier,
                        }),
                    });
                }
            }

            ScenarioEvent::AgentArrivalRateChange { agent, multiplier } => {
                if *multiplier <= 0.0 {
                    return Err(SimulationError::InvalidConfig(
                        "Arrival rate multiplier must be positive".to_string(),
                    ));
                }

                if let Some(generator) = &mut self.arrival_generator {
                    if let Some(old_rate) = generator.get_rate(agent) {
                        let new_rate = old_rate * multiplier;
                        generator.set_rate(agent, new_rate);

                        // Log event
                        self.log_event(crate::models::Event::ScenarioEventExecuted {
                            tick,
                            event_type: "agent_arrival_rate_change".to_string(),
                            details: json!({
                                "agent": agent,
                                "multiplier": multiplier,
                                "old_rate": old_rate,
                                "new_rate": new_rate,
                            }),
                        });
                    }
                }
            }

            ScenarioEvent::CounterpartyWeightChange {
                agent,
                counterparty,
                new_weight,
                auto_balance_others,
            } => {
                if *new_weight < 0.0 {
                    return Err(SimulationError::InvalidConfig(
                        "Counterparty weight cannot be negative".to_string(),
                    ));
                }

                if let Some(generator) = &mut self.arrival_generator {
                    generator.set_counterparty_weight(agent, counterparty, *new_weight);

                    // TODO: Implement auto_balance_others logic
                    // For now, just set the weight directly

                    // Log event
                    self.log_event(crate::models::Event::ScenarioEventExecuted {
                        tick,
                        event_type: "counterparty_weight_change".to_string(),
                        details: json!({
                            "agent": agent,
                            "counterparty": counterparty,
                            "new_weight": new_weight,
                            "auto_balance_others": auto_balance_others,
                        }),
                    });
                }
            }

            ScenarioEvent::DeadlineWindowChange {
                min_ticks_multiplier,
                max_ticks_multiplier,
            } => {
                // Validate multipliers
                if let Some(m) = min_ticks_multiplier {
                    if *m <= 0.0 {
                        return Err(SimulationError::InvalidConfig(
                            "Deadline multiplier must be positive".to_string(),
                        ));
                    }
                }
                if let Some(m) = max_ticks_multiplier {
                    if *m <= 0.0 {
                        return Err(SimulationError::InvalidConfig(
                            "Deadline multiplier must be positive".to_string(),
                        ));
                    }
                }

                if let Some(generator) = &mut self.arrival_generator {
                    // Apply to all agents
                    let agent_ids: Vec<String> = self.state.get_all_agent_ids();
                    for agent_id in agent_ids {
                        if let Some((old_min, old_max)) = generator.get_deadline_range(&agent_id) {
                            let new_min = if let Some(m) = min_ticks_multiplier {
                                ((old_min as f64) * m).round() as usize
                            } else {
                                old_min
                            };

                            let new_max = if let Some(m) = max_ticks_multiplier {
                                ((old_max as f64) * m).round() as usize
                            } else {
                                old_max
                            };

                            generator.set_deadline_range(&agent_id, (new_min, new_max));
                        }
                    }

                    // Log event
                    self.log_event(crate::models::Event::ScenarioEventExecuted {
                        tick,
                        event_type: "deadline_window_change".to_string(),
                        details: json!({
                            "min_ticks_multiplier": min_ticks_multiplier,
                            "max_ticks_multiplier": max_ticks_multiplier,
                        }),
                    });
                }
            }
        }

        Ok(())
    }

    /// Check if a transaction is effectively settled (recursively)
    ///
    /// A transaction is considered effectively settled if:
    /// 1. It is fully settled itself, OR
    /// 2. All of its child transactions are effectively settled (recursive check)
    ///
    /// This enables correct settlement rate calculation for split transactions.
    /// A split transaction family counts as ONE arrival but is only considered
    /// settled when ALL children have settled.
    ///
    /// # Arguments
    /// * `tx_id` - Transaction ID to check
    /// * `transactions` - Map of all transactions
    /// * `children_map` - Map from parent ID to list of child IDs
    ///
    /// # Returns
    /// `true` if transaction is effectively settled, `false` otherwise
    fn is_effectively_settled(
        tx_id: &str,
        transactions: &std::collections::BTreeMap<String, Transaction>,
        children_map: &HashMap<String, Vec<String>>,
    ) -> bool {
        let tx = match transactions.get(tx_id) {
            Some(t) => t,
            None => return false, // Transaction not found
        };

        // CRITICAL FIX: Check for children FIRST before checking parent's settled status
        // A split parent with children should ONLY be considered settled if ALL children are settled,
        // regardless of the parent's own settled_amount.

        // Case 1: Transaction has children - check if ALL children are settled (recursive)
        if let Some(child_ids) = children_map.get(tx_id) {
            return child_ids.iter().all(|child_id| {
                Self::is_effectively_settled(child_id, transactions, children_map)
            });
        }

        // Case 2: No children - check if transaction itself is fully settled
        if tx.settled_amount() > 0 && tx.settled_amount() == tx.amount() {
            return true;
        }

        // Case 3: No children and not fully settled = still pending
        false
    }

    /// Calculate comprehensive system-wide metrics
    ///
    /// Provides a snapshot of current system health including:
    /// - Settlement performance (rate, delays)
    /// - Queue statistics
    /// - Liquidity usage (overdrafts)
    ///
    /// Used by Phase 8 REST API endpoints for monitoring.
    pub fn calculate_system_metrics(&self) -> SystemMetrics {
        // Step 1: Build parent → children mapping
        let mut children_map: HashMap<String, Vec<String>> = HashMap::new();
        for tx in self.state.transactions().values() {
            if let Some(parent_id) = tx.parent_id() {
                children_map
                    .entry(parent_id.to_string())
                    .or_insert_with(Vec::new)
                    .push(tx.id().to_string());
            }
        }

        // Step 2: Count only original arrivals and check effective settlement
        let mut total_arrivals = 0;
        let mut total_settlements = 0;
        let mut delays = Vec::new();

        for tx in self.state.transactions().values() {
            // Only count original transactions (not splits)
            if tx.parent_id().is_none() {
                total_arrivals += 1;

                // Check if effectively settled (recursively for splits)
                if Self::is_effectively_settled(
                    tx.id(),
                    self.state.transactions(),
                    &children_map,
                ) {
                    total_settlements += 1;

                    // Calculate delay for the original transaction
                    let current_tick = self.current_tick();
                    let delay = current_tick.saturating_sub(tx.arrival_tick() as usize);
                    delays.push(delay);
                }
            }
        }

        // Calculate settlement rate
        let settlement_rate = if total_arrivals > 0 {
            total_settlements as f64 / total_arrivals as f64
        } else {
            0.0
        };

        // Calculate average and max delay
        let avg_delay_ticks = if !delays.is_empty() {
            delays.iter().sum::<usize>() as f64 / delays.len() as f64
        } else {
            0.0
        };
        let max_delay_ticks = delays.into_iter().max().unwrap_or(0);

        // Count queue sizes
        let queue1_total_size: usize = self
            .state
            .agents()
            .values()
            .map(|agent| agent.outgoing_queue_size())
            .sum();

        let queue2_total_size = self.state.rtgs_queue().len();

        // Find peak overdraft (most negative balance)
        let peak_overdraft = self
            .state
            .agents()
            .values()
            .map(|agent| agent.balance().min(0).abs())
            .max()
            .unwrap_or(0);

        // Count agents in overdraft
        let agents_in_overdraft = self
            .state
            .agents()
            .values()
            .filter(|agent| agent.balance() < 0)
            .count();

        SystemMetrics {
            total_arrivals,
            total_settlements,
            settlement_rate,
            avg_delay_ticks,
            max_delay_ticks,
            queue1_total_size,
            queue2_total_size,
            peak_overdraft,
            agents_in_overdraft,
        }
    }

    /// Get detailed transaction counts for debugging
    ///
    /// Returns a breakdown of transaction counts to help diagnose
    /// settlement rate calculation issues.
    ///
    /// # Returns
    ///
    /// Tuple of (total_txs, arrivals, children, settled_arrivals, settled_children)
    pub fn get_transaction_counts_debug(&self) -> (usize, usize, usize, usize, usize) {
        let total_txs = self.state.transactions().len();
        let mut arrivals = 0;
        let mut children = 0;
        let mut settled_arrivals = 0;
        let mut settled_children = 0;

        for tx in self.state.transactions().values() {
            if tx.parent_id().is_none() {
                arrivals += 1;
                if tx.is_fully_settled() {
                    settled_arrivals += 1;
                }
            } else {
                children += 1;
                if tx.is_fully_settled() {
                    settled_children += 1;
                }
            }
        }

        (total_txs, arrivals, children, settled_arrivals, settled_children)
    }

    // ========================================================================
    // State Query Methods (Phase 7: FFI Integration)
    // ========================================================================

    /// Get current balance for an agent
    ///
    /// Returns the agent's settlement account balance in cents.
    /// Negative balance indicates overdraft usage.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// * `Some(balance)` - Agent's current balance (cents)
    /// * `None` - Agent not found
    pub fn get_agent_balance(&self, agent_id: &str) -> Option<i64> {
        self.state.get_agent(agent_id).map(|a| a.balance())
    }

    /// Get size of agent's internal queue (Queue 1)
    ///
    /// Returns the number of transactions waiting in the agent's
    /// outgoing queue for policy decisions.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// * `Some(size)` - Number of transactions in Queue 1
    /// * `None` - Agent not found
    pub fn get_queue1_size(&self, agent_id: &str) -> Option<usize> {
        self.state
            .get_agent(agent_id)
            .map(|a| a.outgoing_queue_size())
    }

    /// Get size of RTGS central queue (Queue 2)
    ///
    /// Returns the number of transactions waiting in the RTGS
    /// central queue for liquidity to become available.
    pub fn get_queue2_size(&self) -> usize {
        self.state.queue_size()
    }

    /// Get contents of agent's internal queue (Queue 1)
    ///
    /// Returns a vector of transaction IDs currently in the agent's
    /// internal queue (Queue 1), preserving queue order.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Vector of transaction ID strings in queue order.
    /// Returns empty vector if agent not found or queue is empty.
    ///
    /// # Phase 3: Queue Contents Persistence
    ///
    /// This method enables Phase 3 queue persistence by providing access
    /// to the actual transaction IDs in each agent's queue for end-of-day
    /// snapshots.
    ///
    /// # Example
    ///
    /// ```ignore
    /// let queue_contents = orch.get_agent_queue1_contents("BANK_A");
    /// for (idx, tx_id) in queue_contents.iter().enumerate() {
    ///     println!("Position {}: {}", idx, tx_id);
    /// }
    /// ```
    pub fn get_agent_queue1_contents(&self, agent_id: &str) -> Vec<String> {
        self.state
            .get_agent(agent_id)
            .map(|a| a.outgoing_queue().to_vec())
            .unwrap_or_default()
    }

    /// Get list of all agent identifiers
    ///
    /// Returns all agent IDs configured in the simulation.
    /// Useful for iterating over agents to query their state.
    pub fn get_agent_ids(&self) -> Vec<String> {
        self.state.get_all_agent_ids()
    }

    /// Get LSM cycle events for a specific day (Phase 4)
    ///
    /// Returns all LSM cycle events (bilateral offsets and multilateral cycles)
    /// that were settled during the specified day.
    ///
    /// # Arguments
    ///
    /// * `day` - The day number to query (0-indexed)
    ///
    /// # Returns
    ///
    /// Vector of LsmCycleEvent structs for the specified day
    pub fn get_lsm_cycles_for_day(&self, day: usize) -> Vec<crate::settlement::lsm::LsmCycleEvent> {
        self.state
            .lsm_cycle_events
            .iter()
            .filter(|event| event.day == day)
            .cloned()
            .collect()
    }

    // ========================================================================
    // Verbose CLI Query Methods (Enhanced Monitoring)
    // ========================================================================

    /// Get all events that occurred during a specific tick
    ///
    /// Returns references to all events logged during the specified tick.
    /// Used by verbose CLI mode to show detailed tick-by-tick activity.
    ///
    /// # Arguments
    ///
    /// * `tick` - Tick number to query
    ///
    /// # Returns
    ///
    /// Vector of references to Event objects for the specified tick
    ///
    /// # Example
    ///
    /// ```ignore
    /// let events = orch.get_tick_events(42);
    /// for event in events {
    ///     println!("Event type: {}", event.event_type());
    /// }
    /// ```
    pub fn get_tick_events(&self, tick: usize) -> Vec<&Event> {
        self.event_log.events_at_tick(tick)
    }

    /// Get transaction details by ID
    ///
    /// Returns a reference to a transaction if it exists in the system.
    /// Used to query full transaction details for verbose output.
    ///
    /// # Arguments
    ///
    /// * `tx_id` - Transaction identifier
    ///
    /// # Returns
    ///
    /// * `Some(&Transaction)` - Transaction reference if found
    /// * `None` - Transaction not found
    ///
    /// # Example
    ///
    /// ```ignore
    /// if let Some(tx) = orch.get_transaction("tx_12345") {
    ///     println!("{} -> {}: ${}", tx.sender_id(), tx.receiver_id(), tx.amount() / 100);
    /// }
    /// ```
    pub fn get_transaction(&self, tx_id: &str) -> Option<&Transaction> {
        self.state.get_transaction(tx_id)
    }

    /// Get contents of RTGS queue (Queue 2)
    ///
    /// Returns transaction IDs currently waiting in the central RTGS queue
    /// for liquidity to become available. Used by verbose CLI to show which
    /// transactions are queued in the RTGS system.
    ///
    /// # Returns
    ///
    /// Vector of transaction ID strings in queue order
    ///
    /// # Example
    ///
    /// ```ignore
    /// let rtgs_queue = orch.get_rtgs_queue_contents();
    /// println!("RTGS Queue has {} transactions", rtgs_queue.len());
    /// for tx_id in rtgs_queue {
    ///     println!("  - {}", tx_id);
    /// }
    /// ```
    pub fn get_rtgs_queue_contents(&self) -> Vec<String> {
        self.state.get_rtgs_queue().clone()
    }

    /// Get agent's credit limit
    ///
    /// Returns the maximum credit/overdraft amount available to an agent.
    /// Used by verbose CLI to calculate credit utilization percentage.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// * `Some(limit)` - Credit limit in cents
    /// * `None` - Agent not found
    ///
    /// # Example
    ///
    /// ```ignore
    /// if let Some(limit) = orch.get_agent_credit_limit("BANK_A") {
    ///     let balance = orch.get_agent_balance("BANK_A").unwrap_or(0);
    ///     let used = limit - balance;
    ///     let utilization = (used as f64 / limit as f64) * 100.0;
    ///     println!("Credit utilization: {:.1}%", utilization);
    /// }
    /// ```
    pub fn get_agent_credit_limit(&self, agent_id: &str) -> Option<i64> {
        self.state.get_agent(agent_id).map(|a| a.credit_limit())
    }

    /// Get agent's currently posted collateral
    ///
    /// Returns the amount of collateral currently posted by an agent.
    /// Used by verbose CLI to display collateral status.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// * `Some(amount)` - Posted collateral in cents
    /// * `None` - Agent not found
    ///
    /// # Example
    ///
    /// ```ignore
    /// if let Some(collateral) = orch.get_agent_collateral_posted("BANK_A") {
    ///     println!("Collateral posted: ${:.2}", collateral as f64 / 100.0);
    /// }
    /// ```
    pub fn get_agent_collateral_posted(&self, agent_id: &str) -> Option<i64> {
        self.state.get_agent(agent_id).map(|a| a.posted_collateral())
    }

    // ========================================================================
    // Transaction Submission (Phase 7: External Transaction Injection)
    // ========================================================================

    /// Submit a transaction for processing
    ///
    /// Creates a new transaction and queues it in the sender's internal queue (Queue 1).
    /// The transaction will be processed by the sender's policy during the next tick.
    ///
    /// # Arguments
    ///
    /// * `sender_id` - ID of the sending agent
    /// * `receiver_id` - ID of the receiving agent
    /// * `amount` - Transaction amount in cents (must be > 0)
    /// * `deadline_tick` - Tick by which transaction must settle (or be dropped)
    /// * `priority` - Priority level (0-10, higher = more urgent)
    /// * `divisible` - Whether transaction can be split into parts
    ///
    /// # Returns
    ///
    /// * `Ok(transaction_id)` - Unique ID of the created transaction
    /// * `Err(SimulationError)` - Validation failed
    ///
    /// # Errors
    ///
    /// Returns error if:
    /// - Sender or receiver doesn't exist
    /// - Amount is zero or negative
    /// - Deadline is in the past (before current tick)
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let mut orchestrator = Orchestrator::new(config)?;
    ///
    /// let tx_id = orchestrator.submit_transaction(
    ///     "BANK_A",
    ///     "BANK_B",
    ///     100_000,  // $1,000.00
    ///     50,       // Deadline at tick 50
    ///     5,        // Medium priority
    ///     false,    // Not divisible
    /// )?;
    ///
    /// println!("Created transaction: {}", tx_id);
    /// ```
    pub fn submit_transaction(
        &mut self,
        sender_id: &str,
        receiver_id: &str,
        amount: i64,
        deadline_tick: usize,
        priority: u8,
        divisible: bool,
    ) -> Result<String, SimulationError> {
        // Validate sender exists
        if !self.state.agents().contains_key(sender_id) {
            return Err(SimulationError::AgentNotFound(sender_id.to_string()));
        }

        // Validate receiver exists
        if !self.state.agents().contains_key(receiver_id) {
            return Err(SimulationError::AgentNotFound(receiver_id.to_string()));
        }

        // Validate amount
        if amount <= 0 {
            return Err(SimulationError::InvalidConfig(format!(
                "Transaction amount must be positive, got {}",
                amount
            )));
        }

        // Validate deadline is not in the past
        let current_tick = self.current_tick();
        if deadline_tick <= current_tick {
            return Err(SimulationError::InvalidConfig(format!(
                "Transaction deadline {} is in the past (current tick: {})",
                deadline_tick, current_tick
            )));
        }

        // Create transaction (Transaction::new() generates its own UUID)
        let mut tx = crate::models::Transaction::new(
            sender_id.to_string(),
            receiver_id.to_string(),
            amount,
            current_tick, // Arrival tick = current tick
            deadline_tick,
        );

        // Set priority
        tx = tx.with_priority(priority);

        // TODO(Phase 7): Store divisibility flag on Transaction
        // Currently, the Transaction struct doesn't have a divisible field.
        // Policies check divisibility from ArrivalConfig, but externally-submitted
        // transactions don't have a way to store this flag yet.
        // For now, we accept the parameter but don't use it.
        let _ = divisible; // Suppress unused warning

        // Add transaction to state
        let tx_id_clone = tx.id().to_string();
        self.state.add_transaction(tx);

        // Queue in sender's outgoing queue (Queue 1)
        if let Some(agent) = self.state.get_agent_mut(sender_id) {
            agent.queue_outgoing(tx_id_clone.clone());
        }

        // Log submission event
        self.log_event(Event::Arrival {
            tick: current_tick,
            tx_id: tx_id_clone.clone(),
            sender_id: sender_id.to_string(),
            receiver_id: receiver_id.to_string(),
            amount,
            deadline: deadline_tick,
            priority,
            is_divisible: divisible,
        });

        Ok(tx_id_clone)
    }

    // ========================================================================
    // Transaction Query Methods (Phase 10 - Persistence)
    // ========================================================================

    /// Get all transactions that arrived during a specific day
    ///
    /// Filters transactions by arrival_tick, converting to day using ticks_per_day.
    /// Returns all transactions (pending, settled, dropped) that arrived during
    /// the specified day.
    ///
    /// # Arguments
    ///
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    ///
    /// Vector of references to transactions that arrived during the specified day
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Get all transactions from day 0
    /// let day_0_txs = orch.get_transactions_for_day(0);
    /// for tx in day_0_txs {
    ///     println!("Transaction {}: {} cents", tx.id(), tx.amount());
    /// }
    /// ```
    pub fn get_transactions_for_day(&self, day: usize) -> Vec<&crate::models::Transaction> {
        let ticks_per_day = self.time_manager.ticks_per_day();
        let day_start_tick = day * ticks_per_day;
        let day_end_tick = (day + 1) * ticks_per_day;

        self.state
            .transactions()
            .values()
            .filter(|tx| {
                let arrival_tick = tx.arrival_tick();
                arrival_tick >= day_start_tick && arrival_tick < day_end_tick
            })
            .collect()
    }

    /// Get simulation ID
    ///
    /// Returns a unique identifier for this simulation run.
    /// Used for persistence and tracking.
    ///
    /// # Returns
    ///
    /// Simulation ID string (currently derived from RNG seed)
    pub fn simulation_id(&self) -> String {
        // For now, use RNG seed as simulation ID
        // In future, this could be a UUID or user-provided ID
        format!("sim-{}", self.rng_manager.get_state())
    }

    /// Get ticks per day
    ///
    /// Returns the number of ticks in one simulated day.
    ///
    /// # Returns
    ///
    /// Number of ticks per day
    pub fn ticks_per_day(&self) -> usize {
        self.time_manager.ticks_per_day()
    }

    // ========================================================================
    // Daily Metrics Retrieval (Phase 3: Agent Metrics Collection)
    // ========================================================================

    /// Get daily agent metrics for a specific day
    ///
    /// Returns metrics for all agents for the specified day.
    /// Metrics include balance tracking, transaction counts, queue sizes, and costs.
    ///
    /// # Arguments
    ///
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    ///
    /// Vector of DailyMetrics for all agents on the specified day.
    /// Returns empty vector if day hasn't been completed yet or doesn't exist.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Run simulation for 2 days
    /// for _ in 0..200 {
    ///     orch.tick();
    /// }
    ///
    /// // Get metrics for day 0
    /// let day0_metrics = orch.get_daily_agent_metrics(0);
    /// for metrics in day0_metrics {
    ///     println!("{}: balance {} -> {}",
    ///              metrics.agent_id,
    ///              metrics.opening_balance,
    ///              metrics.closing_balance);
    /// }
    /// ```
    pub fn get_daily_agent_metrics(&self, day: usize) -> Vec<&DailyMetrics> {
        let mut metrics = Vec::new();

        // Collect metrics for all agents for the specified day
        for agent_id in self.state.get_all_agent_ids() {
            if let Some(m) = self.historical_metrics.get(&(agent_id, day)) {
                metrics.push(m);
            }
        }

        metrics
    }

    /// Get agent policy configurations
    ///
    /// Returns the PolicyConfig for each agent as specified in the original
    /// simulation configuration. Useful for policy snapshot tracking and
    /// provenance ("what policy was BANK_A using?").
    ///
    /// # Returns
    ///
    /// Vector of tuples containing (agent_id, PolicyConfig) for all agents.
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// // Create orchestrator with policies
    /// let orch = Orchestrator::new(config)?;
    ///
    /// // Get policy configs for all agents
    /// let policies = orch.get_agent_policies();
    /// for (agent_id, policy_config) in policies {
    ///     println!("{}: {:?}", agent_id, policy_config);
    /// }
    /// ```
    pub fn get_agent_policies(&self) -> Vec<(String, PolicyConfig)> {
        self.config
            .agent_configs
            .iter()
            .map(|ac| (ac.id.clone(), ac.policy.clone()))
            .collect()
    }

    // ========================================================================
    // Checkpoint - Save/Load State
    // ========================================================================

    /// Save complete simulation state to JSON
    ///
    /// Serializes all state necessary to resume the simulation from this point.
    /// Validates invariants before saving to ensure state integrity.
    ///
    /// # Returns
    ///
    /// JSON string containing complete state snapshot
    ///
    /// # Errors
    ///
    /// - `SerializationError`: If state cannot be serialized to JSON
    /// - `StateValidationError`: If state invariants are violated
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let state_json = orchestrator.save_state()?;
    /// // Save to file or database
    /// std::fs::write("checkpoint.json", state_json)?;
    /// ```
    pub fn save_state(&self) -> Result<String, SimulationError> {
        use crate::orchestrator::checkpoint::{
            compute_config_hash, validate_snapshot, AgentSnapshot, StateSnapshot,
            TransactionSnapshot,
        };

        // Compute config hash for validation
        let config_hash = compute_config_hash(&self.get_config())?;

        // Create snapshot with deterministic ordering
        let mut agents: Vec<AgentSnapshot> = self
            .state
            .agents()
            .iter()
            .map(|(_, a)| AgentSnapshot::from(a))
            .collect();
        agents.sort_by(|a, b| a.id.cmp(&b.id)); // Sort by ID for deterministic order

        let mut transactions: Vec<TransactionSnapshot> = self
            .state
            .transactions()
            .iter()
            .map(|(_, t)| TransactionSnapshot::from(t))
            .collect();
        transactions.sort_by(|a, b| a.id.cmp(&b.id)); // Sort by ID for deterministic order

        let snapshot = StateSnapshot {
            current_tick: self.time_manager.current_tick(),
            current_day: self.time_manager.current_day(),
            rng_seed: self.rng_manager.get_state(), // CRITICAL: Current RNG state
            agents,
            transactions,
            rtgs_queue: self.state.get_rtgs_queue().clone(),
            config_hash,
        };

        // Validate invariants before serializing
        let expected_balance = self.get_all_agent_balances().values().sum();
        validate_snapshot(&snapshot, expected_balance)?;

        // Serialize to JSON
        serde_json::to_string(&snapshot).map_err(|e| {
            SimulationError::SerializationError(format!("Failed to serialize state: {}", e))
        })
    }

    /// Load simulation state from JSON and create new orchestrator
    ///
    /// Deserializes state and validates that it matches the provided config.
    /// Ensures all invariants are preserved after reconstruction.
    ///
    /// # Arguments
    ///
    /// * `config` - Orchestrator configuration (must match original)
    /// * `state_json` - JSON string from previous save_state() call
    ///
    /// # Returns
    ///
    /// New orchestrator instance restored to the saved state
    ///
    /// # Errors
    ///
    /// - `DeserializationError`: If JSON is invalid or corrupted
    /// - `ConfigMismatch`: If config doesn't match checkpoint's config
    /// - `StateValidationError`: If restored state violates invariants
    ///
    /// # Example
    ///
    /// ```rust,ignore
    /// let state_json = std::fs::read_to_string("checkpoint.json")?;
    /// let orchestrator = Orchestrator::load_state(config, &state_json)?;
    /// // Continue simulation from checkpoint
    /// orchestrator.tick()?;
    /// ```
    pub fn load_state(
        config: OrchestratorConfig,
        state_json: &str,
    ) -> Result<Self, SimulationError> {
        use crate::orchestrator::checkpoint::{
            compute_config_hash, validate_snapshot, StateSnapshot,
        };

        // Deserialize snapshot
        let snapshot: StateSnapshot = serde_json::from_str(state_json).map_err(|e| {
            SimulationError::DeserializationError(format!("Failed to parse state JSON: {}", e))
        })?;

        // Validate config matches
        let config_hash = compute_config_hash(&config)?;
        if snapshot.config_hash != config_hash {
            return Err(SimulationError::ConfigMismatch {
                expected: snapshot.config_hash,
                actual: config_hash,
            });
        }

        // Validate state integrity
        let expected_balance: i64 = snapshot.agents.iter().map(|a| a.balance).sum();
        validate_snapshot(&snapshot, expected_balance)?;

        // Reconstruct state
        let agents: std::collections::BTreeMap<_, _> = snapshot
            .agents
            .into_iter()
            .map(|a| {
                let agent = crate::models::agent::Agent::from(a);
                (agent.id().to_string(), agent)
            })
            .collect();

        let transactions: std::collections::BTreeMap<_, _> = snapshot
            .transactions
            .into_iter()
            .map(|t| {
                let tx = crate::models::transaction::Transaction::from(t);
                (tx.id().to_string(), tx)
            })
            .collect();

        let state = crate::models::state::SimulationState::from_parts(
            agents,
            transactions,
            snapshot.rtgs_queue,
        )
        .map_err(|e| SimulationError::StateValidationError(e))?;

        // Reconstruct time manager
        let time_manager = crate::core::time::TimeManager::from_state(
            config.ticks_per_day,
            config.num_days,
            snapshot.current_tick,
            snapshot.current_day,
        );

        // Reconstruct RNG manager with saved seed
        let rng_manager = crate::rng::RngManager::new(snapshot.rng_seed);

        // Reconstruct policies
        // All policies now use JSON-based TreePolicy loaded via factory
        let mut policies: HashMap<String, Box<dyn crate::policy::CashManagerPolicy>> =
            HashMap::new();
        for agent_config in &config.agent_configs {
            let tree_policy =
                crate::policy::tree::create_policy(&agent_config.policy).map_err(|e| {
                    SimulationError::InvalidConfig(format!(
                        "Failed to create JSON policy for agent {}: {}",
                        agent_config.id, e
                    ))
                })?;
            policies.insert(agent_config.id.clone(), Box::new(tree_policy));
        }

        // Reconstruct arrival generator if configured
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
            Some(crate::arrivals::ArrivalGenerator::new(
                arrival_configs_map,
                all_agent_ids,
            ))
        } else {
            None
        };

        // Initialize empty accumulators and metrics (will be recalculated)
        let accumulated_costs: HashMap<String, CostAccumulator> = config
            .agent_configs
            .iter()
            .map(|a| (a.id.clone(), CostAccumulator::new()))
            .collect();

        let current_day_metrics: HashMap<String, DailyMetrics> = HashMap::new();
        let historical_metrics: HashMap<(String, usize), DailyMetrics> = HashMap::new();

        // Initialize scenario event handler (if events configured)
        let scenario_event_handler = config
            .scenario_events
            .as_ref()
            .map(|events| crate::events::ScenarioEventHandler::new(events.clone()));

        // Clone values we need before moving config
        let cost_rates = config.cost_rates.clone();
        let lsm_config = config.lsm_config.clone();

        Ok(Self {
            config,
            state,
            time_manager,
            rng_manager,
            policies,
            arrival_generator,
            cost_rates,
            lsm_config,
            accumulated_costs,
            event_log: crate::models::event::EventLog::new(),
            pending_settlements: Vec::new(),
            next_tx_id: 0, // Will be updated on next transaction
            current_day_metrics,
            historical_metrics,
            scenario_event_handler,
        })
    }

    /// Get current orchestrator configuration
    ///
    /// Returns the original configuration used to create this orchestrator.
    /// Used for config hashing during checkpoint save/load.
    fn get_config(&self) -> OrchestratorConfig {
        self.config.clone()
    }

    /// Get all agent balances
    ///
    /// Returns a map of agent ID to current balance.
    ///
    /// # Returns
    ///
    /// HashMap mapping agent IDs to their current balances (cents)
    pub fn get_all_agent_balances(&self) -> HashMap<String, i64> {
        self.state
            .agents()
            .iter()
            .map(|(_, agent)| (agent.id().to_string(), agent.balance()))
            .collect()
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

        // STEP 0: RESET COST ACCUMULATORS AT START OF NEW DAY
        // (This ensures the previous day's costs remain queryable until the new day starts)
        if self.time_manager.tick_within_day() == 0 && current_tick > 0 {
            // First tick of a new day (but not tick 0) - reset accumulators
            let agent_ids: Vec<String> = self.state.get_all_agent_ids();
            for agent_id in agent_ids {
                if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
                    *accumulator = CostAccumulator::new();
                }
            }
        }

        // STEP 0.5: EXECUTE SCENARIO EVENTS
        // Execute scheduled scenario events before arrivals (they may modify rates, etc.)
        if let Some(handler) = &self.scenario_event_handler {
            // Collect events first to avoid borrow checker conflicts
            let events: Vec<_> = handler.get_events_for_tick(current_tick)
                .into_iter()
                .cloned()
                .collect();

            for event in events {
                self.execute_scenario_event(&event, current_tick)?;
            }
        }

        // STEP 1: ARRIVALS
        // Generate new transactions according to arrival configurations
        let mut num_arrivals = 0;
        let mut arrival_events = Vec::new();

        if let Some(generator) = &mut self.arrival_generator {
            // Get all agent IDs that have arrival configs
            let agent_ids: Vec<String> = self.state.get_all_agent_ids();

            for agent_id in agent_ids {
                // Generate arrivals for this agent
                let new_transactions =
                    generator.generate_for_agent(&agent_id, current_tick, &mut self.rng_manager);
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
                        priority: tx.priority(),
                        is_divisible: false, // TODO: Add is_divisible to Transaction struct
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

        // STEP 1.5: STRATEGIC COLLATERAL MANAGEMENT (Layer 1)
        // Evaluate strategic collateral decisions BEFORE policy evaluation
        // This is forward-looking: agents post collateral based on full Queue 1 state
        // MUST run before STEP 2 so it sees transactions before policies remove them
        let all_agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

        for agent_id in all_agent_ids.clone() {
            let agent = self
                .state
                .get_agent(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            let policy = self
                .policies
                .get_mut(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            let tree_policy = policy
                .as_any_mut()
                .downcast_mut::<crate::policy::tree::TreePolicy>()
                .ok_or_else(|| {
                    SimulationError::InvalidConfig(format!(
                        "Agent {} policy is not a TreePolicy",
                        agent_id
                    ))
                })?;

            let decision = tree_policy
                .evaluate_strategic_collateral(agent, &self.state, current_tick, &self.cost_rates, self.config.ticks_per_day, self.config.eod_rush_threshold)
                .map_err(|e| {
                    SimulationError::InvalidConfig(format!(
                        "Failed to evaluate strategic collateral for {}: {}",
                        agent_id, e
                    ))
                })?;

            use crate::policy::CollateralDecision;

            match decision {
                CollateralDecision::Post { amount, reason } => {
                    if amount <= 0 {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Collateral post amount must be positive, got {}",
                            amount
                        )));
                    }

                    let agent = self.state.get_agent(&agent_id).unwrap();
                    let remaining_capacity = agent.remaining_collateral_capacity();

                    if amount > remaining_capacity {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Agent {} tried to post {} collateral but only has {} capacity remaining",
                            agent_id, amount, remaining_capacity
                        )));
                    }

                    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
                    let old_collateral = agent_mut.posted_collateral();
                    let new_collateral = old_collateral + amount;
                    agent_mut.set_posted_collateral(new_collateral);

                    // Record detailed collateral event (Phase 10)
                    self.record_collateral_event(
                        &agent_id,
                        crate::models::CollateralAction::Post,
                        amount,
                        format!("{:?}", reason),
                        crate::models::CollateralLayer::Strategic,
                    );

                    self.log_event(Event::CollateralPost {
                        tick: current_tick,
                        agent_id: agent_id.clone(),
                        amount,
                        reason: format!("{:?}", reason),
                        new_total: new_collateral,
                    });
                }
                CollateralDecision::Withdraw { amount, reason } => {
                    if amount <= 0 {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Collateral withdraw amount must be positive, got {}",
                            amount
                        )));
                    }

                    let agent = self.state.get_agent(&agent_id).unwrap();
                    let posted = agent.posted_collateral();

                    if amount > posted {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Agent {} tried to withdraw {} collateral but only has {} posted",
                            agent_id, amount, posted
                        )));
                    }

                    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
                    let old_collateral = agent_mut.posted_collateral();
                    let new_collateral = old_collateral - amount;
                    agent_mut.set_posted_collateral(new_collateral);

                    // Record detailed collateral event (Phase 10)
                    self.record_collateral_event(
                        &agent_id,
                        crate::models::CollateralAction::Withdraw,
                        amount,
                        format!("{:?}", reason),
                        crate::models::CollateralLayer::Strategic,
                    );

                    self.log_event(Event::CollateralWithdraw {
                        tick: current_tick,
                        agent_id: agent_id.clone(),
                        amount,
                        reason: format!("{:?}", reason),
                        new_total: new_collateral,
                    });
                }
                CollateralDecision::Hold => {}
            }
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
            let decisions =
                policy.evaluate_queue(agent, &self.state, current_tick, &self.cost_rates, self.config.ticks_per_day, self.config.eod_rush_threshold);

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
                            return Err(SimulationError::SettlementError(format!(
                                "num_splits must be >= 2, got {}",
                                num_splits
                            )));
                        }

                        // Get parent transaction
                        let parent_tx = self
                            .state
                            .get_transaction(&tx_id)
                            .ok_or_else(|| {
                                SimulationError::SettlementError(format!(
                                    "Transaction {} not found for splitting",
                                    tx_id
                                ))
                            })?
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
                        let friction_cost =
                            self.cost_rates.split_friction_cost * (num_splits as i64 - 1);

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
                                    collateral_cost: 0,
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
                    ReleaseDecision::Reprioritize { tx_id, new_priority } => {
                        // Phase 4: Update transaction priority
                        // Transaction remains in Queue 1, only priority changes
                        if let Some(tx) = self.state.get_transaction_mut(&tx_id) {
                            let old_priority = tx.priority();
                            tx.set_priority(new_priority);

                            // Log reprioritization event
                            self.log_event(Event::TransactionReprioritized {
                                tick: current_tick,
                                agent_id: agent_id.clone(),
                                tx_id: tx_id.clone(),
                                old_priority,
                                new_priority,
                            });
                        }
                    }
                    ReleaseDecision::Drop { tx_id } => {
                        // Remove from Queue 1, mark as overdue (temporary - policies should handle this differently)
                        if let Some(agent) = self.state.get_agent_mut(&agent_id) {
                            agent.remove_from_queue(&tx_id);
                        }
                        if let Some(tx) = self.state.get_transaction_mut(&tx_id) {
                            tx.mark_overdue(current_tick).ok(); // NOTE: Changed from drop_transaction
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
            // Get transaction details for event logging (including overdue status before settlement)
            let (sender_id, receiver_id, amount, was_overdue, overdue_data) = {
                let tx = self
                    .state
                    .get_transaction(tx_id)
                    .ok_or_else(|| SimulationError::TransactionNotFound(tx_id.clone()))?;

                let sender_id = tx.sender_id().to_string();
                let receiver_id = tx.receiver_id().to_string();
                let amount = tx.remaining_amount();
                let was_overdue = tx.is_overdue();

                // Collect overdue data if transaction is overdue
                let overdue_data = if was_overdue {
                    Some((
                        tx.amount(),                          // total amount
                        tx.deadline_tick(),                   // deadline_tick
                        tx.overdue_since_tick().unwrap(),     // overdue_since_tick
                        current_tick - tx.overdue_since_tick().unwrap(), // total_ticks_overdue
                        self.cost_rates.deadline_penalty,     // deadline_penalty_cost
                        // Estimate accumulated delay cost
                        (tx.remaining_amount() as f64
                            * self.cost_rates.delay_cost_per_tick_per_cent
                            * self.cost_rates.overdue_delay_multiplier
                            * (current_tick - tx.overdue_since_tick().unwrap()) as f64)
                            .round() as i64,
                    ))
                } else {
                    None
                };

                (sender_id, receiver_id, amount, was_overdue, overdue_data)
            };

            // Try to settle the transaction (already in state)
            let settlement_result = self.try_settle_transaction(tx_id, current_tick)?;

            match settlement_result {
                SettlementOutcome::Settled => {
                    num_settlements += 1;

                    // Log appropriate settlement event based on overdue status
                    if was_overdue {
                        if let Some((total_amount, deadline_tick, overdue_since_tick,
                                    total_ticks_overdue, deadline_penalty_cost, estimated_delay_cost)) = overdue_data {
                            self.log_event(Event::OverdueTransactionSettled {
                                tick: current_tick,
                                tx_id: tx_id.clone(),
                                sender_id: sender_id.clone(),
                                receiver_id: receiver_id.clone(),
                                amount: total_amount,
                                settled_amount: amount,
                                deadline_tick,
                                overdue_since_tick,
                                total_ticks_overdue,
                                deadline_penalty_cost,
                                estimated_delay_cost,
                            });
                        }
                    }

                    // Always log standard settlement event for compatibility
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

        // DIAGNOSTIC LOGGING (Test 4 from lsm-splitting-investigation-plan.md)
        // Enable by setting environment variable: LSM_DEBUG=1
        if std::env::var("LSM_DEBUG").is_ok() {
            eprintln!("[LSM DEBUG] Tick {}: Queue 2 (RTGS): {}, Queue 1 (Internal): {}",
                current_tick, self.state.queue_size(), self.state.total_internal_queue_size());
            eprintln!("[LSM DEBUG] Tick {}: LSM config: bilateral={}, cycles={}, max_cycle_length={}",
                current_tick,
                self.lsm_config.enable_bilateral,
                self.lsm_config.enable_cycles,
                self.lsm_config.max_cycle_length
            );
        }

        let lsm_result = lsm::run_lsm_pass(
            &mut self.state,
            &self.lsm_config,
            current_tick,
            self.time_manager.ticks_per_day(),
        );
        let num_lsm_releases = lsm_result.bilateral_offsets + lsm_result.cycles_settled;
        num_settlements += num_lsm_releases;

        // DIAGNOSTIC LOGGING (continued)
        if std::env::var("LSM_DEBUG").is_ok() {
            eprintln!("[LSM DEBUG] Tick {}: LSM result: bilateral_offsets={}, cycles_settled={}, total_value=${:.2}, queue_after={}",
                current_tick,
                lsm_result.bilateral_offsets,
                lsm_result.cycles_settled,
                lsm_result.total_settled_value as f64 / 100.0,
                self.state.queue_size()
            );

            if lsm_result.bilateral_offsets > 0 || lsm_result.cycles_settled > 0 {
                eprintln!("[LSM DEBUG] Tick {}: ✓ LSM ACTIVATED - {} bilateral, {} cycles",
                    current_tick, lsm_result.bilateral_offsets, lsm_result.cycles_settled);
            } else if self.state.queue_size() > 0 {
                eprintln!("[LSM DEBUG] Tick {}: ⚠ LSM did not find any settlements despite {} queued transactions",
                    current_tick, self.state.queue_size());
            }
        }

        // Store LSM cycle events for persistence (Phase 4.2)
        self.state
            .lsm_cycle_events
            .extend(lsm_result.cycle_events.clone());

        // Log enriched LSM replay events (already contain all fields for display)
        // These events are created in lsm.rs with complete data and don't need reconstruction
        let lsm_debug = std::env::var("LSM_DEBUG").is_ok();
        if lsm_debug {
            eprintln!("[LSM DEBUG] Logging {} LSM replay events", lsm_result.replay_events.len());
        }
        for event in &lsm_result.replay_events {
            if lsm_debug {
                eprintln!("[LSM DEBUG] Logging enriched event: {:?}", event.event_type());
            }
            self.log_event(event.clone());
        }

        // STEP 5.5: END-OF-TICK COLLATERAL MANAGEMENT (Layer 2)
        // Evaluate end-of-tick collateral decisions for each agent AFTER settlements complete
        // This is reactive: agents adjust collateral based on final settlement state
        let all_agent_ids: Vec<String> = self.state.agents().keys().cloned().collect();

        for agent_id in all_agent_ids {
            // Get agent
            let agent = self
                .state
                .get_agent(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            // Get policy and downcast to TreePolicy
            let policy = self
                .policies
                .get_mut(&agent_id)
                .ok_or_else(|| SimulationError::AgentNotFound(agent_id.clone()))?;

            // Downcast to TreePolicy to access end-of-tick collateral method
            let tree_policy = policy
                .as_any_mut()
                .downcast_mut::<crate::policy::tree::TreePolicy>()
                .ok_or_else(|| {
                    SimulationError::InvalidConfig(format!(
                        "Agent {} policy is not a TreePolicy",
                        agent_id
                    ))
                })?;

            // Evaluate END-OF-TICK collateral decision (Layer 2)
            let decision = tree_policy
                .evaluate_end_of_tick_collateral(agent, &self.state, current_tick, &self.cost_rates, self.config.ticks_per_day, self.config.eod_rush_threshold)
                .map_err(|e| {
                    SimulationError::InvalidConfig(format!(
                        "Failed to evaluate end-of-tick collateral for {}: {}",
                        agent_id, e
                    ))
                })?;

            // Execute collateral decision (same logic as strategic layer)
            use crate::policy::CollateralDecision;

            match decision {
                CollateralDecision::Post { amount, reason } => {
                    // Validate amount is positive
                    if amount <= 0 {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Collateral post amount must be positive, got {}",
                            amount
                        )));
                    }

                    // Get agent to check capacity
                    let agent = self.state.get_agent(&agent_id).unwrap();
                    let remaining_capacity = agent.remaining_collateral_capacity();

                    if amount > remaining_capacity {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Agent {} tried to post {} collateral but only has {} capacity remaining",
                            agent_id, amount, remaining_capacity
                        )));
                    }

                    // Execute the post
                    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
                    let old_collateral = agent_mut.posted_collateral();
                    let new_collateral = old_collateral + amount;
                    agent_mut.set_posted_collateral(new_collateral);

                    // Record detailed collateral event (Phase 10)
                    self.record_collateral_event(
                        &agent_id,
                        crate::models::CollateralAction::Post,
                        amount,
                        format!("{:?}", reason),
                        crate::models::CollateralLayer::EndOfTick,
                    );

                    // Log collateral post event
                    self.log_event(Event::CollateralPost {
                        tick: current_tick,
                        agent_id: agent_id.clone(),
                        amount,
                        reason: format!("{:?}", reason),
                        new_total: new_collateral,
                    });
                }
                CollateralDecision::Withdraw { amount, reason } => {
                    // Validate amount is positive
                    if amount <= 0 {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Collateral withdraw amount must be positive, got {}",
                            amount
                        )));
                    }

                    // Get agent to check available collateral
                    let agent = self.state.get_agent(&agent_id).unwrap();
                    let posted = agent.posted_collateral();

                    if amount > posted {
                        return Err(SimulationError::InvalidConfig(format!(
                            "Agent {} tried to withdraw {} collateral but only has {} posted",
                            agent_id, amount, posted
                        )));
                    }

                    // Execute the withdrawal
                    let agent_mut = self.state.get_agent_mut(&agent_id).unwrap();
                    let old_collateral = agent_mut.posted_collateral();
                    let new_collateral = old_collateral - amount;
                    agent_mut.set_posted_collateral(new_collateral);

                    // Record detailed collateral event (Phase 10)
                    self.record_collateral_event(
                        &agent_id,
                        crate::models::CollateralAction::Withdraw,
                        amount,
                        format!("{:?}", reason),
                        crate::models::CollateralLayer::EndOfTick,
                    );

                    // Log collateral withdraw event
                    self.log_event(Event::CollateralWithdraw {
                        tick: current_tick,
                        agent_id: agent_id.clone(),
                        amount,
                        reason: format!("{:?}", reason),
                        new_total: new_collateral,
                    });
                }
                CollateralDecision::Hold => {
                    // No action needed
                }
            }
        }

        // STEP 6: COST ACCRUAL (Phase 4b.3 - minimal for now)
        let mut total_cost = self.accrue_costs(current_tick);

        // STEP 7: DEADLINE ENFORCEMENT (handled by policies in STEP 2)
        // Policies drop expired transactions via ReleaseDecision::Drop

        // STEP 8: END-OF-DAY HANDLING (before advancing time)
        // Check if current tick is the last tick of the day
        if self.time_manager.is_end_of_day() {
            let eod_penalties = self.handle_end_of_day()?;
            total_cost += eod_penalties;  // Include EOD penalties in tick's total cost
        }

        // STEP 9: ADVANCE TIME
        self.time_manager.advance_tick();

        // STEP 9.5: UPDATE DAILY METRICS (Phase 3: Agent Metrics Collection)
        // Track balance changes, queue sizes, and collateral for all agents
        self.update_tick_metrics();

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
            // First pass: collect data and identify newly overdue transactions
            // Check both Queue 1 (agent's outgoing queue) and Queue 2 (RTGS queue)
            let (balance, collateral, newly_overdue_txs) = {
                let agent = self.state.get_agent(&agent_id).unwrap();
                let mut overdue = Vec::new();

                // Check Queue 1 (agent's internal queue)
                for tx_id in agent.outgoing_queue() {
                    if let Some(tx) = self.state.get_transaction(tx_id) {
                        if tx.is_past_deadline(tick) && !tx.is_overdue() {
                            overdue.push(tx_id.clone());
                        }
                    }
                }

                // Check Queue 2 (RTGS queue) for this agent's transactions
                // that were marked overdue in this tick (by RTGS process_queue in STEP 4)
                for tx_id in self.state.rtgs_queue() {
                    if let Some(tx) = self.state.get_transaction(tx_id) {
                        if tx.sender_id() == agent_id
                            && tx.is_overdue()
                            && tx.overdue_since_tick() == Some(tick) {
                            overdue.push(tx_id.clone());
                        }
                    }
                }

                (agent.balance(), agent.posted_collateral(), overdue)
            };

            // Mark transactions as overdue and emit events (mutable borrow, agent borrow released)
            for tx_id in &newly_overdue_txs {
                if let Some(tx_mut) = self.state.get_transaction_mut(tx_id) {
                    // Collect transaction data before marking overdue
                    let amount = tx_mut.amount();
                    let remaining_amount = tx_mut.remaining_amount();
                    let sender_id = tx_mut.sender_id().to_string();
                    let receiver_id = tx_mut.receiver_id().to_string();
                    let deadline_tick = tx_mut.deadline_tick();

                    // Mark as overdue
                    tx_mut.mark_overdue(tick).ok();

                    // Emit event
                    self.log_event(Event::TransactionWentOverdue {
                        tick,
                        tx_id: tx_id.clone(),
                        sender_id,
                        receiver_id,
                        amount,
                        remaining_amount,
                        deadline_tick,
                        ticks_overdue: tick - deadline_tick,
                        deadline_penalty_cost: self.cost_rates.deadline_penalty,
                    });
                }
            }

            // Calculate penalty cost
            let penalty_cost = (newly_overdue_txs.len() as i64) * self.cost_rates.deadline_penalty;

            // Calculate overdraft cost (liquidity cost)
            let liquidity_cost = self.calculate_overdraft_cost(balance);

            // Calculate delay cost for queued transactions
            let delay_cost = self.calculate_delay_cost(&agent_id);

            // Calculate collateral opportunity cost (Phase 8)
            let collateral_cost = self.calculate_collateral_cost(collateral);

            // Split friction cost handled at decision time
            let split_friction_cost = 0;

            let costs = CostBreakdown {
                liquidity_cost,
                delay_cost,
                collateral_cost,
                penalty_cost,
                split_friction_cost,
            };

            // Accumulate costs
            if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
                accumulator.add(&costs);
                accumulator.update_peak_debit(balance);
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
        cost.round() as i64 // Use rounding instead of truncation (Phase 8 fix)
    }

    /// Calculate delay cost for queued transactions
    ///
    /// Delay cost = sum of (queued transaction values × multiplier) * delay_cost_per_tick_per_cent
    ///
    /// Overdue transactions have their value multiplied by overdue_delay_multiplier
    /// to represent escalating urgency.
    ///
    /// Counts transactions in both Queue 1 (agent's internal queue) and Queue 2 (RTGS queue).
    /// All unsettled transactions accrue delay cost, as they represent unsettled obligations.
    fn calculate_delay_cost(&self, agent_id: &str) -> i64 {
        let agent = match self.state.get_agent(agent_id) {
            Some(a) => a,
            None => return 0,
        };

        let mut total_weighted_value = 0.0;

        // Sum up weighted value of all transactions in Queue 1
        for tx_id in agent.outgoing_queue() {
            if let Some(tx) = self.state.get_transaction(tx_id) {
                let amount = tx.remaining_amount() as f64;

                // Apply multiplier for overdue transactions
                let multiplier = if tx.is_overdue() {
                    self.cost_rates.overdue_delay_multiplier
                } else {
                    1.0
                };

                total_weighted_value += amount * multiplier;
            }
        }

        // Also sum up transactions in Queue 2 (RTGS queue) for this agent
        for tx_id in self.state.rtgs_queue() {
            if let Some(tx) = self.state.get_transaction(tx_id) {
                if tx.sender_id() == agent_id {
                    let amount = tx.remaining_amount() as f64;

                    // Apply multiplier for overdue transactions
                    let multiplier = if tx.is_overdue() {
                        self.cost_rates.overdue_delay_multiplier
                    } else {
                        1.0
                    };

                    total_weighted_value += amount * multiplier;
                }
            }
        }

        let cost = total_weighted_value * self.cost_rates.delay_cost_per_tick_per_cent;
        cost.round() as i64 // Use rounding instead of truncation (Phase 8 fix)
    }

    /// Calculate collateral opportunity cost (Phase 8)
    ///
    /// Collateral cost = posted_collateral * collateral_cost_per_tick_bps
    ///
    /// Represents the opportunity cost of having assets posted as collateral
    /// rather than deployed in other earning activities.
    ///
    /// Example: $1,000,000 collateral at 0.0002 bps/tick = 200 cents = $2
    fn calculate_collateral_cost(&self, posted_collateral: i64) -> i64 {
        if posted_collateral <= 0 {
            return 0;
        }

        let collateral_amount = posted_collateral as f64;
        let cost = collateral_amount * self.cost_rates.collateral_cost_per_tick_bps;
        cost.round() as i64
    }

    /// Handle end-of-day processing
    ///
    /// Applies penalties for unsettled transactions at end of day.
    /// Each agent pays eod_penalty_per_transaction for each unsettled transaction
    /// in their Queue 1 (internal queue).
    ///
    /// Returns the total EOD penalties accrued across all agents.
    fn handle_end_of_day(&mut self) -> Result<i64, SimulationError> {
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
                let penalty =
                    (unsettled_count as i64) * self.cost_rates.eod_penalty_per_transaction;
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
                        collateral_cost: 0,
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

        // Phase 3: Finalize daily metrics and prepare for next day
        self.finalize_daily_metrics(current_day)?;

        Ok(total_penalties)
    }

    /// Finalize daily metrics at end of day (Phase 3: Agent Metrics Collection)
    ///
    /// 1. Finalize current day metrics (capture closing balance, costs, etc.)
    /// 2. Move current day metrics to historical storage
    /// 3. Initialize metrics for next day
    /// 4. Reset cost accumulators for next day
    fn finalize_daily_metrics(&mut self, current_day: usize) -> Result<(), SimulationError> {
        let agent_ids: Vec<String> = self.state.get_all_agent_ids();

        for agent_id in &agent_ids {
            // Get current day metrics
            if let Some(mut metrics) = self.current_day_metrics.remove(agent_id) {
                // Finalize metrics with agent state and costs
                let agent = self.state.get_agent(agent_id).unwrap();
                let costs = self.accumulated_costs.get(agent_id).unwrap();
                metrics.finalize(agent, costs);

                // Store in historical metrics
                self.historical_metrics
                    .insert((agent_id.clone(), current_day), metrics);
            }

            // Initialize metrics for next day
            let agent = self.state.get_agent(agent_id).unwrap();
            let next_day_metrics = DailyMetrics::new(agent_id.clone(), current_day + 1, agent);
            self.current_day_metrics
                .insert(agent_id.clone(), next_day_metrics);

            // NOTE: Cost accumulators are now reset at START of new day in tick(),
            // not here at EOD. This allows the CLI to query EOD costs after the tick completes.
        }

        Ok(())
    }

    /// Update metrics at end of tick (Phase 3: Agent Metrics Collection)
    ///
    /// Tracks balance changes and queue sizes for all agents.
    fn update_tick_metrics(&mut self) {
        let agent_ids: Vec<String> = self.state.get_all_agent_ids();

        for agent_id in &agent_ids {
            let agent = self.state.get_agent(agent_id).unwrap();

            if let Some(metrics) = self.current_day_metrics.get_mut(agent_id) {
                // Update balance tracking
                metrics.update_balance(agent.balance());

                // Update collateral tracking
                metrics.update_collateral(agent.posted_collateral());

                // Update queue size tracking
                metrics.update_queue_size(agent.outgoing_queue_size());
            }
        }
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
                sender.debit(amount).map_err(|e| {
                    SimulationError::SettlementError(format!("Debit failed: {}", e))
                })?;
            }
            {
                let receiver = self.state.get_agent_mut(&receiver_id).unwrap();
                receiver.credit(amount);
            }

            // Get parent_id before settling (need to read before mut borrow)
            let parent_id = {
                let tx = self.state.get_transaction(tx_id).unwrap();
                tx.parent_id().map(|s| s.to_string())
            };

            {
                let tx = self.state.get_transaction_mut(tx_id).unwrap();
                tx.settle(amount, tick).map_err(|e| {
                    SimulationError::SettlementError(format!("Settle failed: {}", e))
                })?;
            }

            // If this is a child transaction, update parent's remaining_amount
            if let Some(parent_id) = parent_id {
                let parent = self.state.get_transaction_mut(&parent_id).unwrap();
                parent.reduce_remaining_for_child(amount).map_err(|e| {
                    SimulationError::SettlementError(format!("Parent update failed: {}", e))
                })?;

                // If parent now fully settled, mark it as settled
                if parent.remaining_amount() == 0 {
                    parent.mark_fully_settled(tick).map_err(|e| {
                        SimulationError::SettlementError(format!("Parent mark settled failed: {}", e))
                    })?;
                }
            }

            Ok(SettlementOutcome::Settled)
        } else {
            // Queue the transaction in RTGS queue (Queue 2)
            self.state.queue_transaction(tx_id.to_string());
            Ok(SettlementOutcome::Queued)
        }
    }

    // ========================================================================
    // Collateral Event Tracking (Phase 10)
    // ========================================================================

    /// Calculate collateral amount after applying an action
    ///
    /// # Arguments
    /// * `before` - Current posted collateral amount
    /// * `action` - Action to apply (Post/Withdraw/Hold)
    /// * `amount` - Amount to post or withdraw
    ///
    /// # Returns
    /// New posted collateral amount after action
    fn calculate_collateral_after(
        before: i64,
        action: &crate::models::CollateralAction,
        amount: i64,
    ) -> i64 {
        match action {
            crate::models::CollateralAction::Post => before + amount,
            crate::models::CollateralAction::Withdraw => before - amount,
            crate::models::CollateralAction::Hold => before,
        }
    }

    /// Record a collateral event with full state capture
    ///
    /// Called whenever collateral is posted, withdrawn, or a hold decision is made.
    /// Captures the complete state before and after the action for later analysis.
    ///
    /// # Arguments
    /// * `agent_id` - Agent making the decision
    /// * `action` - Action taken (Post/Withdraw/Hold)
    /// * `amount` - Amount involved (i64 cents)
    /// * `reason` - Reason for action (e.g., "insufficient_liquidity")
    /// * `layer` - Decision layer (Strategic/EndOfTick)
    ///
    /// # Implementation Notes
    ///
    /// This method is called from 4 locations in the tick loop:
    /// 1. Strategic layer collateral post (policy-driven)
    /// 2. Strategic layer collateral withdraw (policy-driven)
    /// 3. End-of-tick automatic collateral post
    /// 4. End-of-tick automatic collateral withdraw
    ///
    /// The captured state enables detailed analysis of collateral behavior,
    /// including capacity utilization, decision timing, and layer distinction.
    fn record_collateral_event(
        &mut self,
        agent_id: &str,
        action: crate::models::CollateralAction,
        amount: i64,
        reason: String,
        layer: crate::models::CollateralLayer,
    ) {
        let agent = self.state.get_agent(agent_id).unwrap();
        let current_tick = self.time_manager.current_tick() as usize;
        let current_day = current_tick / self.config.ticks_per_day;

        // Capture before state
        let balance_before = agent.balance();
        let posted_collateral_before = agent.posted_collateral();

        // Calculate after state based on action
        let posted_collateral_after =
            Self::calculate_collateral_after(posted_collateral_before, &action, amount);

        // Calculate remaining capacity
        let max_capacity = agent.max_collateral_capacity();
        let available_capacity_after = max_capacity - posted_collateral_after;

        // Create event with all captured state
        let event = crate::models::CollateralEvent::new(
            agent_id.to_string(),
            current_tick,
            current_day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after,
        );

        // Store event in state for later retrieval
        self.state.collateral_events.push(event);
    }

    /// Get collateral events for a specific day
    ///
    /// Returns all collateral management events that occurred during the specified day.
    ///
    /// # Arguments
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    /// Vector of collateral events filtered by day
    ///
    /// # Example
    /// ```ignore
    /// let events = orch.get_collateral_events_for_day(0);
    /// for event in events {
    ///     println!("{} posted {} at tick {}", event.agent_id, event.amount, event.tick);
    /// }
    /// ```
    pub fn get_collateral_events_for_day(&self, day: usize) -> Vec<crate::models::CollateralEvent> {
        self.state
            .collateral_events
            .iter()
            .filter(|e| e.day == day)
            .cloned()
            .collect()
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
            eod_rush_threshold: 0.8,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![
                AgentConfig {
                    id: "BANK_A".to_string(),
                    opening_balance: 1_000_000,
                    credit_limit: 500_000,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                    posted_collateral: None,
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
                    posted_collateral: None,
                },
            ],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
            scenario_events: None,
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
            eod_rush_threshold: 0.8,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
            scenario_events: None,
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
            eod_rush_threshold: 0.8,
            num_days: 1,
            rng_seed: 12345,
            agent_configs: vec![
                AgentConfig {
                    id: "BANK_A".to_string(),
                    opening_balance: 1_000_000,
                    credit_limit: 0,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                    posted_collateral: None,
                },
                AgentConfig {
                    id: "BANK_A".to_string(), // Duplicate!
                    opening_balance: 2_000_000,
                    credit_limit: 0,
                    policy: PolicyConfig::Fifo,
                    arrival_config: None,
                    posted_collateral: None,
                },
            ],
            cost_rates: CostRates::default(),
            lsm_config: LsmConfig::default(),
            scenario_events: None,
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
            collateral_cost: 0,
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
            collateral_cost: 0,
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
            collateral_cost: 0,
            penalty_cost: 2000,
            split_friction_cost: 250,
        };

        assert_eq!(cost.total(), 3750); // 1000 + 500 + 2000 + 250
    }

    // ========================================================================
    // Phase 3: Overdue Cost Tests (TDD)
    // ========================================================================

    #[test]
    fn test_overdue_delay_cost_multiplier() {
        let cost_rates = CostRates {
            delay_cost_per_tick_per_cent: 0.0001, // 1 bp per tick
            overdue_delay_multiplier: 5.0,         // 5x for overdue
            deadline_penalty: 100_000,             // $1000 one-time
            ..Default::default()
        };

        // Create orchestrator with custom cost rates
        let mut config = create_test_config();
        config.cost_rates = cost_rates;
        // Reduce BANK_A's balance and credit so transaction stays in queue
        config.agent_configs[0].opening_balance = 500_000;
        config.agent_configs[0].credit_limit = 0; // No credit to prevent immediate settlement
        let mut orch = Orchestrator::new(config).unwrap();

        // Submit a transaction that will become overdue
        orch.submit_transaction("BANK_A", "BANK_B", 1_000_000, 50, 5, false).unwrap();

        // Run to tick 1 - transaction pending, normal delay cost
        orch.tick().unwrap();
        let costs_normal = orch.get_costs("BANK_A").unwrap();
        // Expected: 1_000_000 * 0.0001 = 100 cents
        assert_eq!(costs_normal.total_delay_cost, 100);

        // Mark transaction as overdue manually for testing
        {
            let tx_id = orch.state().transactions().keys().next().unwrap().clone();
            let tx = orch.state.get_transaction_mut(&tx_id).unwrap();
            tx.mark_overdue(51).unwrap();
        }

        // Run another tick - overdue, should have 5x multiplier
        orch.tick().unwrap();
        let costs_overdue = orch.get_costs("BANK_A").unwrap();
        // Previous delay_cost was 100, now adding 1_000_000 * 0.0001 * 5.0 = 500
        // Total should be 100 + 500 = 600
        assert_eq!(costs_overdue.total_delay_cost, 600);
    }

    #[test]
    fn test_one_time_deadline_penalty() {
        let cost_rates = CostRates {
            deadline_penalty: 100_000, // $1000
            ..Default::default()
        };

        let mut config = create_test_config();
        config.cost_rates = cost_rates;
        // Reduce BANK_A's balance and credit so transaction stays in queue
        config.agent_configs[0].opening_balance = 500_000;
        config.agent_configs[0].credit_limit = 0; // No credit to prevent immediate settlement
        let mut orch = Orchestrator::new(config).unwrap();

        // Submit transaction with deadline at tick 2
        orch.submit_transaction("BANK_A", "BANK_B", 1_000_000, 2, 5, false).unwrap();

        // Tick 0: Before deadline
        orch.tick().unwrap();
        let costs_before = orch.get_costs("BANK_A").unwrap();
        assert_eq!(costs_before.total_penalty_cost, 0);

        // Tick 1: Still before deadline
        orch.tick().unwrap();
        let costs_tick_1 = orch.get_costs("BANK_A").unwrap();
        assert_eq!(costs_tick_1.total_penalty_cost, 0);

        // Tick 2: At deadline (last valid tick, not overdue yet)
        orch.tick().unwrap();
        let costs_at_deadline = orch.get_costs("BANK_A").unwrap();
        assert_eq!(costs_at_deadline.total_penalty_cost, 0);

        // Tick 3: Past deadline - penalty charged
        orch.tick().unwrap();
        let costs_after = orch.get_costs("BANK_A").unwrap();
        assert_eq!(costs_after.total_penalty_cost, 100_000);
    }

    #[test]
    fn test_deadline_penalty_only_charged_once() {
        let cost_rates = CostRates {
            delay_cost_per_tick_per_cent: 0.0001,
            overdue_delay_multiplier: 5.0,
            deadline_penalty: 100_000,
            ..Default::default()
        };

        let mut config = create_test_config();
        config.cost_rates = cost_rates;
        // Reduce BANK_A's balance and credit so transaction stays in queue
        config.agent_configs[0].opening_balance = 500_000;
        config.agent_configs[0].credit_limit = 0; // No credit to prevent immediate settlement
        let mut orch = Orchestrator::new(config).unwrap();

        // Submit transaction with deadline at tick 2
        orch.submit_transaction("BANK_A", "BANK_B", 1_000_000, 2, 5, false).unwrap();

        // Run to tick 3 (past deadline) - need 4 ticks to process tick 3
        for _ in 0..4 {
            orch.tick().unwrap();
        }

        let costs_tick_3 = orch.get_costs("BANK_A").unwrap();
        let penalty_tick_3 = costs_tick_3.total_penalty_cost;
        let delay_cost_tick_3 = costs_tick_3.total_delay_cost;

        // Penalty should be 100,000 (charged once during tick 3 processing)
        assert_eq!(penalty_tick_3, 100_000);

        // Run more ticks - penalty should NOT increase
        for _ in 0..5 {
            orch.tick().unwrap();
        }

        let costs_tick_8 = orch.get_costs("BANK_A").unwrap();
        // Penalty cost should still be 100,000 (no additional deadline penalties)
        assert_eq!(costs_tick_8.total_penalty_cost, 100_000);

        // Delay cost should increase each tick due to multiplier
        assert!(costs_tick_8.total_delay_cost > delay_cost_tick_3);
    }

    // ========================================================================
    // Settlement Rate Tests (TDD for bug fix)
    // ========================================================================

    #[test]
    fn test_settlement_rate_without_splits() {
        // Test baseline: settlement rate calculation without any splits
        let config = create_test_config();
        let mut orch = Orchestrator::new(config).unwrap();

        // Submit 3 normal transactions
        let _tx1 = orch
            .submit_transaction("BANK_A", "BANK_B", 100_000, 50, 5, false)
            .unwrap();
        let _tx2 = orch
            .submit_transaction("BANK_A", "BANK_B", 200_000, 50, 5, false)
            .unwrap();
        let _tx3 = orch
            .submit_transaction("BANK_B", "BANK_A", 150_000, 50, 5, false)
            .unwrap();

        // Run 10 ticks to settle
        for _ in 0..10 {
            orch.tick().unwrap();
        }

        // Get metrics - should show 3 arrivals, 3 settlements, 100% rate
        let metrics = orch.calculate_system_metrics();
        assert_eq!(
            metrics.total_arrivals, 3,
            "Should count 3 original arrivals"
        );
        assert_eq!(metrics.total_settlements, 3, "Should count 3 settlements");
        assert_eq!(
            metrics.settlement_rate, 1.0,
            "Settlement rate should be 100%"
        );
    }

    #[test]
    fn test_settlement_rate_with_split_fully_settled() {
        // Test: split transaction where ALL children settle
        // Expected: Parent counted as 1 arrival, considered settled when all children settle
        let config = create_test_config();
        let mut orch = Orchestrator::new(config).unwrap();

        // Submit 3 normal transactions that will settle
        let _tx1 = orch
            .submit_transaction("BANK_A", "BANK_B", 100_000, 50, 5, false)
            .unwrap();
        let _tx2 = orch
            .submit_transaction("BANK_A", "BANK_B", 200_000, 50, 5, false)
            .unwrap();
        let _tx3 = orch
            .submit_transaction("BANK_B", "BANK_A", 150_000, 50, 5, false)
            .unwrap();

        // Run 10 ticks to settle the normal transactions
        for _ in 0..10 {
            orch.tick().unwrap();
        }

        // Now manually create a split scenario
        let parent_id = orch
            .submit_transaction("BANK_A", "BANK_B", 1_000_000, 100, 5, false)
            .unwrap();

        // Manually create 2 children (simulating policy split decision)
        let child1 = crate::models::Transaction::new_split(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            500_000,
            orch.current_tick(),
            100,
            parent_id.clone(),
        );
        let child1_id = child1.id().to_string();
        orch.state_mut().add_transaction(child1);

        let child2 = crate::models::Transaction::new_split(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            500_000,
            orch.current_tick(),
            100,
            parent_id.clone(),
        );
        let child2_id = child2.id().to_string();
        orch.state_mut().add_transaction(child2);

        // Get metrics before settling children
        let metrics = orch.calculate_system_metrics();
        assert_eq!(
            metrics.total_arrivals, 4,
            "Should count 4 original arrivals (including parent)"
        );
        assert_eq!(
            metrics.total_settlements, 3,
            "Parent not settled yet (children pending)"
        );
        assert!(
            metrics.settlement_rate < 1.0,
            "Settlement rate should be <100% with unsettled parent"
        );

        // Settle child1 only
        let tick = orch.current_tick();
        orch.state_mut()
            .get_transaction_mut(&child1_id)
            .unwrap()
            .settle(500_000, tick)
            .unwrap();

        let metrics = orch.calculate_system_metrics();
        assert_eq!(
            metrics.total_settlements, 3,
            "Parent still not fully settled (only 1 of 2 children settled)"
        );

        // Settle child2
        let tick = orch.current_tick();
        orch.state_mut()
            .get_transaction_mut(&child2_id)
            .unwrap()
            .settle(500_000, tick)
            .unwrap();

        // Now parent should be considered effectively settled
        let metrics = orch.calculate_system_metrics();
        assert_eq!(
            metrics.total_arrivals, 4,
            "Should still count 4 original arrivals"
        );
        assert_eq!(
            metrics.total_settlements, 4,
            "All 4 arrivals effectively settled (including split parent)"
        );
        assert_eq!(
            metrics.settlement_rate, 1.0,
            "Settlement rate should be 100%"
        );
    }

    #[test]
    fn test_settlement_rate_with_partial_split() {
        // Test: split where only SOME children settle
        // Expected: Parent NOT considered settled (incomplete split family)
        let config = create_test_config();
        let mut orch = Orchestrator::new(config).unwrap();

        // Create parent + split into 3 children
        let parent_id = orch
            .submit_transaction("BANK_A", "BANK_B", 1_500_000, 100, 5, false)
            .unwrap();

        // Create 3 children
        let mut child_ids = Vec::new();
        for _ in 0..3 {
            let child = crate::models::Transaction::new_split(
                "BANK_A".to_string(),
                "BANK_B".to_string(),
                500_000,
                orch.current_tick(),
                100,
                parent_id.clone(),
            );
            let child_id = child.id().to_string();
            child_ids.push(child_id.clone());
            orch.state_mut().add_transaction(child);
        }

        // Settle only 2 of 3 children
        let tick = orch.current_tick();
        orch.state_mut()
            .get_transaction_mut(&child_ids[0])
            .unwrap()
            .settle(500_000, tick)
            .unwrap();
        orch.state_mut()
            .get_transaction_mut(&child_ids[1])
            .unwrap()
            .settle(500_000, tick)
            .unwrap();
        // child_ids[2] remains unsettled

        // Parent should NOT be considered settled
        let metrics = orch.calculate_system_metrics();
        assert_eq!(
            metrics.total_arrivals, 1,
            "Should count 1 original arrival"
        );
        assert_eq!(
            metrics.total_settlements, 0,
            "Parent not settled (only 2/3 children settled)"
        );
        assert_eq!(
            metrics.settlement_rate, 0.0,
            "Settlement rate should be 0%"
        );
    }
}
