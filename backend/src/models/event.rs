//! Event logging for simulation replay and auditing.
//!
//! This module defines the Event enum which captures all significant state changes
//! during simulation. Events enable:
//! - Deterministic replay (re-run simulation from event log)
//! - Debugging (understand what happened and when)
//! - Auditing (verify correctness of settlements)
//! - Analysis (extract metrics and patterns)
//!
//! # Event Types
//!
//! Events are categorized by simulation phase:
//! - **Arrival**: New transaction enters system
//! - **Policy**: Agent decision (submit, hold, drop)
//! - **Settlement**: Transaction state changes (settled, queued)
//! - **LSM**: Liquidity-saving mechanism actions
//! - **Cost**: Cost accrual events
//! - **EOD**: End-of-day processing
//!
//! # Example
//!
//! ```rust
//! use payment_simulator_core_rs::models::Event;
//!
//! let event = Event::Arrival {
//!     tick: 10,
//!     tx_id: "tx_00000042".to_string(),
//!     sender_id: "BANK_A".to_string(),
//!     receiver_id: "BANK_B".to_string(),
//!     amount: 100_000,
//!     deadline: 20,
//!     priority: 5,
//!     is_divisible: false,
//! };
//!
//! println!("Event at tick {}: {:?}", event.tick(), event);
//! ```

use crate::orchestrator::CostBreakdown;

/// Simulation event capturing a state change.
///
/// All events include a tick number for temporal ordering.
/// Events are logged in the order they occur within a tick.
#[derive(Debug, Clone, PartialEq)]
pub enum Event {
    /// New transaction arrived (generated or injected)
    Arrival {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
        deadline: usize,
        priority: u8,
        is_divisible: bool,
    },

    /// Policy decided to submit transaction from Queue 1 to settlement
    PolicySubmit {
        tick: usize,
        agent_id: String,
        tx_id: String,
    },

    /// Policy decided to hold transaction in Queue 1
    PolicyHold {
        tick: usize,
        agent_id: String,
        tx_id: String,
        reason: String,
    },

    /// Policy decided to drop transaction
    PolicyDrop {
        tick: usize,
        agent_id: String,
        tx_id: String,
        reason: String,
    },

    /// Policy decided to split transaction into multiple child transactions
    PolicySplit {
        tick: usize,
        agent_id: String,
        tx_id: String,
        num_splits: usize,
        child_ids: Vec<String>,
    },

    /// Policy reprioritized a transaction (Phase 4: Overdue Handling)
    ///
    /// Transaction priority changed while remaining in Queue 1.
    /// Typically used to bump overdue transactions to higher priority.
    TransactionReprioritized {
        tick: usize,
        agent_id: String,
        tx_id: String,
        old_priority: u8,
        new_priority: u8,
    },

    /// Priority escalated due to approaching deadline (Phase 5: Priority Escalation)
    ///
    /// Emitted when a transaction's effective priority is boosted because
    /// its deadline is approaching. This helps prevent low-priority transactions
    /// from being starved when they become urgent.
    PriorityEscalated {
        tick: usize,
        tx_id: String,
        sender_id: String,
        original_priority: u8,
        escalated_priority: u8,
        ticks_until_deadline: usize,
        boost_applied: u8,
    },

    /// Agent posted collateral to increase available liquidity
    CollateralPost {
        tick: usize,
        agent_id: String,
        amount: i64,
        reason: String,
        new_total: i64,
    },

    /// Agent withdrew collateral to reduce opportunity cost
    CollateralWithdraw {
        tick: usize,
        agent_id: String,
        amount: i64,
        reason: String,
        new_total: i64,
    },

    /// Collateral automatically withdrawn via timer (Phase 3.4: Policy Enhancements V2)
    ///
    /// Emitted when auto_withdraw_after_ticks timer expires and collateral is withdrawn.
    /// Provides full audit trail including when collateral was originally posted.
    /// Updated to include new_total for observability and replay identity.
    CollateralTimerWithdrawn {
        tick: usize,
        agent_id: String,
        amount: i64,
        original_reason: String, // Reason from when collateral was posted
        posted_at_tick: usize,   // When collateral was originally posted
        new_total: i64,          // Posted collateral after withdrawal (for observability)
    },

    /// Collateral timer withdrawal blocked by guard (Invariant I2 enforcement)
    ///
    /// Emitted when automatic withdrawal timer triggers but guard prevents withdrawal.
    /// Reasons: NoHeadroom, MinHoldingPeriodNotMet, etc.
    /// This ensures Invariant I2 (withdrawal headroom protection) is never violated.
    CollateralTimerBlocked {
        tick: usize,
        agent_id: String,
        requested_amount: i64,
        reason: String,          // "NoHeadroom", "MinHoldingPeriodNotMet", etc.
        original_reason: String, // Reason from when collateral was posted
        posted_at_tick: usize,   // When collateral was originally posted
    },

    /// State register value changed (Phase 4.5: Policy Enhancements V2)
    ///
    /// Emitted when policy uses SetState or AddState actions.
    /// Also emitted for EOD resets (all registers reset to 0.0).
    /// CRITICAL: Required for replay identity - state changes must be auditable.
    /// Phase 4.6: Added decision_path for transparency into policy decisions.
    StateRegisterSet {
        tick: usize,
        agent_id: String,
        register_key: String,
        old_value: f64,
        new_value: f64,
        reason: String,                   // e.g., "policy_action", "eod_reset"
        decision_path: Option<String>,    // Phase 4.6: Decision tree path taken
    },

    /// Bank-level budget set for this tick (Phase 3.3: Policy Enhancements V2)
    ///
    /// Emitted when bank_tree evaluation results in SetReleaseBudget action.
    /// Controls total value, focus counterparties, and per-counterparty limits.
    BankBudgetSet {
        tick: usize,
        agent_id: String,
        max_value: i64,                             // Total budget (cents)
        focus_counterparties: Option<Vec<String>>,  // Allowed counterparties
        max_per_counterparty: Option<i64>,          // Max per counterparty (cents)
    },

    /// Transaction settled via RTGS (immediate on submission - payer had liquidity)
    ///
    /// Emitted when a transaction settles immediately upon submission because the
    /// sender had sufficient balance + headroom. This is the "fast path" that bypasses
    /// all queues.
    RtgsImmediateSettlement {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        sender_balance_before: i64,  // For audit trail
        sender_balance_after: i64,   // For audit trail
    },

    /// Transaction queued to RTGS queue (insufficient liquidity)
    QueuedRtgs {
        tick: usize,
        tx_id: String,
        sender_id: String,
    },

    /// Transaction submitted to RTGS Queue 2 (Phase 0: Dual Priority System)
    ///
    /// Emitted when a transaction is released from Queue 1 (internal bank queue)
    /// to Queue 2 (RTGS central queue). Records both internal priority and
    /// declared RTGS priority for replay identity.
    RtgsSubmission {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        internal_priority: u8,      // Bank's internal priority (0-10)
        rtgs_priority: String,       // Declared RTGS priority: "HighlyUrgent", "Urgent", "Normal"
    },

    /// Transaction withdrawn from RTGS Queue 2 (Phase 0: Dual Priority System)
    ///
    /// Emitted when a bank withdraws a transaction from Queue 2 to change its
    /// priority. The transaction can then be resubmitted with a different priority.
    RtgsWithdrawal {
        tick: usize,
        tx_id: String,
        sender: String,
        original_rtgs_priority: String,  // Priority it had before withdrawal
    },

    /// Transaction resubmitted to RTGS Queue 2 with new priority (Phase 0: Dual Priority System)
    ///
    /// Emitted when a previously withdrawn transaction is resubmitted to Queue 2.
    /// The transaction gets a new submission tick (loses FIFO position).
    RtgsResubmission {
        tick: usize,
        tx_id: String,
        sender: String,
        old_rtgs_priority: String,  // Previous priority
        new_rtgs_priority: String,  // New priority after resubmission
    },

    /// Transaction settled via LSM bilateral offset
    LsmBilateralOffset {
        tick: usize,
        agent_a: String,
        agent_b: String,
        amount_a: i64,
        amount_b: i64,
        tx_ids: Vec<String>,  // Changed from tx_id_a, tx_id_b to match test expectations
    },

    /// Transaction settled via LSM cycle detection
    LsmCycleSettlement {
        tick: usize,
        agents: Vec<String>,           // NEW: Full list of agents in cycle
        tx_amounts: Vec<i64>,          // NEW: Transaction amounts
        total_value: i64,              // NEW: Total value settled (renamed from cycle_value)
        net_positions: Vec<i64>,       // NEW: Net positions before settlement
        max_net_outflow: i64,          // NEW: Maximum net outflow in cycle
        max_net_outflow_agent: String, // NEW: Agent with max net outflow
        tx_ids: Vec<String>,
    },

    /// Costs accrued for an agent this tick
    CostAccrual {
        tick: usize,
        agent_id: String,
        costs: CostBreakdown,
    },

    /// End-of-day processing occurred
    EndOfDay {
        tick: usize,
        day: usize,
        unsettled_count: usize,
        total_penalties: i64,
    },

    /// Transaction crossed its deadline and became overdue
    ///
    /// Emitted when a transaction first becomes overdue. The one-time deadline penalty
    /// is charged at this moment. Subsequent delay costs use the overdue multiplier
    /// (typically 5x) for escalating penalties.
    TransactionWentOverdue {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,                    // Total transaction amount
        remaining_amount: i64,          // Unsettled amount
        deadline_tick: usize,           // Original deadline
        ticks_overdue: usize,           // How many ticks late
        deadline_penalty_cost: i64,     // One-time penalty charged
    },

    /// Overdue transaction was finally settled
    ///
    /// Emitted when a transaction that is overdue gets settled (fully or partially).
    /// Includes cost breakdown showing the total financial impact of being overdue.
    OverdueTransactionSettled {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,                    // Total transaction amount
        settled_amount: i64,            // Amount settled this tick
        deadline_tick: usize,           // Original deadline
        overdue_since_tick: usize,      // When it became overdue
        total_ticks_overdue: usize,     // Duration overdue
        deadline_penalty_cost: i64,     // One-time penalty (already paid)
        estimated_delay_cost: i64,      // Accumulated delay costs while overdue
    },

    /// Scenario event executed
    ///
    /// Emitted when a configured scenario event executes (direct transfer,
    /// collateral adjustment, arrival rate change, etc.). Contains full details
    /// for replay identity.
    ScenarioEventExecuted {
        tick: usize,
        event_type: String,           // Type of event (e.g., "direct_transfer")
        details: serde_json::Value,   // Full event data as JSON
    },

    /// Transaction released from Queue-2 due to new liquidity
    ///
    /// Emitted when a queued transaction settles after liquidity becomes available
    /// (not via LSM). This distinguishes queued-then-settled from immediate settlement.
    Queue2LiquidityRelease {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        queue_wait_ticks: i64,       // How long it waited in queue
        release_reason: String,       // "NewLiquidity", "IncomingPayment", "CollateralPosted", etc.
    },

    /// Bilateral limit exceeded - payment blocked due to counterparty-specific limit
    ///
    /// Emitted when a payment cannot settle because it would exceed the sender's
    /// bilateral limit for the specific receiver. Part of TARGET2 LSM Phase 1.
    BilateralLimitExceeded {
        tick: usize,
        sender: String,
        receiver: String,
        tx_id: String,
        amount: i64,
        current_bilateral_outflow: i64,  // Current outflow to this counterparty today
        bilateral_limit: i64,             // Configured limit for this counterparty
    },

    /// Multilateral limit exceeded - payment blocked due to total outflow limit
    ///
    /// Emitted when a payment cannot settle because it would exceed the sender's
    /// multilateral (total) outflow limit. Part of TARGET2 LSM Phase 1.
    MultilateralLimitExceeded {
        tick: usize,
        sender: String,
        tx_id: String,
        amount: i64,
        current_total_outflow: i64,  // Current total outflow today
        multilateral_limit: i64,      // Configured total limit
    },

    /// Algorithm execution event - records which settlement algorithm ran
    ///
    /// Emitted when a settlement algorithm (1-FIFO, 2-Bilateral, 3-Multilateral)
    /// completes execution. Part of TARGET2 LSM Phase 2 (Algorithm Sequencing).
    AlgorithmExecution {
        tick: usize,
        algorithm: u8,           // 1=FIFO, 2=Bilateral, 3=Multilateral
        result: String,          // "Success", "NoProgress", "Failure"
        settlements: usize,      // Number of transactions settled
        settled_value: i64,      // Total value settled in cents
    },

    /// Entry disposition bilateral offset (TARGET2 Phase 3)
    ///
    /// Emitted when an incoming payment triggers immediate bilateral offset
    /// with a queued payment in the opposite direction. This happens at
    /// transaction entry time, before regular LSM processing.
    EntryDispositionOffset {
        tick: usize,
        incoming_tx_id: String,    // The new transaction that triggered offset
        queued_tx_id: String,      // The transaction that was in queue
        agent_a: String,           // First agent in the pair
        agent_b: String,           // Second agent in the pair
        offset_amount: i64,        // Amount that was offset (settled)
        incoming_amount: i64,      // Original incoming transaction amount
        queued_amount: i64,        // Original queued transaction amount
    },

    /// DEPRECATED: Old name for Queue2LiquidityRelease
    ///
    /// Kept for backward compatibility. Use Queue2LiquidityRelease instead.
    #[deprecated(note = "Use Queue2LiquidityRelease instead")]
    RtgsQueue2Settle {
        tick: usize,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        reason: String,
    },
}

impl Event {
    /// Get the tick number when this event occurred
    pub fn tick(&self) -> usize {
        match self {
            Event::Arrival { tick, .. } => *tick,
            Event::PolicySubmit { tick, .. } => *tick,
            Event::PolicyHold { tick, .. } => *tick,
            Event::PolicyDrop { tick, .. } => *tick,
            Event::PolicySplit { tick, .. } => *tick,
            Event::TransactionReprioritized { tick, .. } => *tick,
            Event::PriorityEscalated { tick, .. } => *tick,
            Event::CollateralPost { tick, .. } => *tick,
            Event::CollateralWithdraw { tick, .. } => *tick,
            Event::CollateralTimerWithdrawn { tick, .. } => *tick,
            Event::CollateralTimerBlocked { tick, .. } => *tick,
            Event::StateRegisterSet { tick, .. } => *tick,
            Event::BankBudgetSet { tick, .. } => *tick,
            Event::RtgsImmediateSettlement { tick, .. } => *tick,
            Event::QueuedRtgs { tick, .. } => *tick,
            Event::RtgsSubmission { tick, .. } => *tick,
            Event::RtgsWithdrawal { tick, .. } => *tick,
            Event::RtgsResubmission { tick, .. } => *tick,
            Event::LsmBilateralOffset { tick, .. } => *tick,
            Event::LsmCycleSettlement { tick, .. } => *tick,
            Event::CostAccrual { tick, .. } => *tick,
            Event::EndOfDay { tick, .. } => *tick,
            Event::TransactionWentOverdue { tick, .. } => *tick,
            Event::OverdueTransactionSettled { tick, .. } => *tick,
            Event::ScenarioEventExecuted { tick, .. } => *tick,
            Event::Queue2LiquidityRelease { tick, .. } => *tick,
            Event::BilateralLimitExceeded { tick, .. } => *tick,
            Event::MultilateralLimitExceeded { tick, .. } => *tick,
            Event::AlgorithmExecution { tick, .. } => *tick,
            Event::EntryDispositionOffset { tick, .. } => *tick,
            #[allow(deprecated)]
            Event::RtgsQueue2Settle { tick, .. } => *tick,
        }
    }

    /// Get a short description of the event type
    pub fn event_type(&self) -> &'static str {
        match self {
            Event::Arrival { .. } => "Arrival",
            Event::PolicySubmit { .. } => "PolicySubmit",
            Event::PolicyHold { .. } => "PolicyHold",
            Event::PolicyDrop { .. } => "PolicyDrop",
            Event::PolicySplit { .. } => "PolicySplit",
            Event::TransactionReprioritized { .. } => "TransactionReprioritized",
            Event::PriorityEscalated { .. } => "PriorityEscalated",
            Event::CollateralPost { .. } => "CollateralPost",
            Event::CollateralWithdraw { .. } => "CollateralWithdraw",
            Event::CollateralTimerWithdrawn { .. } => "CollateralTimerWithdrawn",
            Event::CollateralTimerBlocked { .. } => "CollateralTimerBlocked",
            Event::StateRegisterSet { .. } => "StateRegisterSet",
            Event::BankBudgetSet { .. } => "BankBudgetSet",
            Event::RtgsImmediateSettlement { .. } => "RtgsImmediateSettlement",
            Event::QueuedRtgs { .. } => "QueuedRtgs",
            Event::RtgsSubmission { .. } => "RtgsSubmission",
            Event::RtgsWithdrawal { .. } => "RtgsWithdrawal",
            Event::RtgsResubmission { .. } => "RtgsResubmission",
            Event::LsmBilateralOffset { .. } => "LsmBilateralOffset",
            Event::LsmCycleSettlement { .. } => "LsmCycleSettlement",
            Event::CostAccrual { .. } => "CostAccrual",
            Event::EndOfDay { .. } => "EndOfDay",
            Event::TransactionWentOverdue { .. } => "TransactionWentOverdue",
            Event::OverdueTransactionSettled { .. } => "OverdueTransactionSettled",
            Event::ScenarioEventExecuted { .. } => "ScenarioEventExecuted",
            Event::Queue2LiquidityRelease { .. } => "Queue2LiquidityRelease",
            Event::BilateralLimitExceeded { .. } => "BilateralLimitExceeded",
            Event::MultilateralLimitExceeded { .. } => "MultilateralLimitExceeded",
            Event::AlgorithmExecution { .. } => "AlgorithmExecution",
            Event::EntryDispositionOffset { .. } => "EntryDispositionOffset",
            #[allow(deprecated)]
            Event::RtgsQueue2Settle { .. } => "RtgsQueue2Settle",
        }
    }

    /// Get transaction ID if event relates to a specific transaction
    pub fn tx_id(&self) -> Option<&str> {
        match self {
            Event::Arrival { tx_id, .. } => Some(tx_id),
            Event::PolicySubmit { tx_id, .. } => Some(tx_id),
            Event::PolicyHold { tx_id, .. } => Some(tx_id),
            Event::PolicyDrop { tx_id, .. } => Some(tx_id),
            Event::PolicySplit { tx_id, .. } => Some(tx_id),
            Event::TransactionReprioritized { tx_id, .. } => Some(tx_id),
            Event::PriorityEscalated { tx_id, .. } => Some(tx_id),
            Event::RtgsImmediateSettlement { tx_id, .. } => Some(tx_id),
            Event::QueuedRtgs { tx_id, .. } => Some(tx_id),
            Event::TransactionWentOverdue { tx_id, .. } => Some(tx_id),
            Event::OverdueTransactionSettled { tx_id, .. } => Some(tx_id),
            Event::Queue2LiquidityRelease { tx_id, .. } => Some(tx_id),
            Event::BilateralLimitExceeded { tx_id, .. } => Some(tx_id),
            Event::MultilateralLimitExceeded { tx_id, .. } => Some(tx_id),
            #[allow(deprecated)]
            Event::RtgsQueue2Settle { tx_id, .. } => Some(tx_id),
            _ => None,
        }
    }

    /// Get agent ID if event relates to a specific agent
    pub fn agent_id(&self) -> Option<&str> {
        match self {
            Event::Arrival { sender_id, .. } => Some(sender_id),
            Event::PolicySubmit { agent_id, .. } => Some(agent_id),
            Event::PolicyHold { agent_id, .. } => Some(agent_id),
            Event::PolicyDrop { agent_id, .. } => Some(agent_id),
            Event::PolicySplit { agent_id, .. } => Some(agent_id),
            Event::TransactionReprioritized { agent_id, .. } => Some(agent_id),
            Event::PriorityEscalated { sender_id, .. } => Some(sender_id),
            Event::CollateralPost { agent_id, .. } => Some(agent_id),
            Event::CollateralWithdraw { agent_id, .. } => Some(agent_id),
            Event::RtgsImmediateSettlement { sender, .. } => Some(sender),
            Event::QueuedRtgs { sender_id, .. } => Some(sender_id),
            Event::CostAccrual { agent_id, .. } => Some(agent_id),
            Event::TransactionWentOverdue { sender_id, .. } => Some(sender_id),
            Event::OverdueTransactionSettled { sender_id, .. } => Some(sender_id),
            Event::Queue2LiquidityRelease { sender, .. } => Some(sender),
            Event::BilateralLimitExceeded { sender, .. } => Some(sender),
            Event::MultilateralLimitExceeded { sender, .. } => Some(sender),
            #[allow(deprecated)]
            Event::RtgsQueue2Settle { sender, .. } => Some(sender),
            _ => None,
        }
    }
}

/// Event log for storing and querying simulation events.
///
/// This is a simple wrapper around Vec<Event> with convenience methods.
#[derive(Debug, Clone, Default)]
pub struct EventLog {
    events: Vec<Event>,
}

impl EventLog {
    /// Create a new empty event log
    pub fn new() -> Self {
        Self { events: Vec::new() }
    }

    /// Add an event to the log
    pub fn log(&mut self, event: Event) {
        self.events.push(event);
    }

    /// Get the number of events logged
    pub fn len(&self) -> usize {
        self.events.len()
    }

    /// Check if the log is empty
    pub fn is_empty(&self) -> bool {
        self.events.is_empty()
    }

    /// Get all events
    pub fn events(&self) -> &[Event] {
        &self.events
    }

    /// Get events for a specific tick
    pub fn events_at_tick(&self, tick: usize) -> Vec<&Event> {
        self.events.iter().filter(|e| e.tick() == tick).collect()
    }

    /// Get events of a specific type
    pub fn events_of_type(&self, event_type: &str) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|e| e.event_type() == event_type)
            .collect()
    }

    /// Get events for a specific transaction
    pub fn events_for_tx(&self, tx_id: &str) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|e| e.tx_id() == Some(tx_id))
            .collect()
    }

    /// Get events for a specific agent
    pub fn events_for_agent(&self, agent_id: &str) -> Vec<&Event> {
        self.events
            .iter()
            .filter(|e| e.agent_id() == Some(agent_id))
            .collect()
    }

    /// Clear all events
    pub fn clear(&mut self) {
        self.events.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_tick() {
        let event = Event::Arrival {
            tick: 42,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 50,
            priority: 5,
            is_divisible: false,
        };

        assert_eq!(event.tick(), 42);
    }

    #[test]
    fn test_event_type() {
        let event = Event::RtgsImmediateSettlement {
            tick: 10,
            tx_id: "tx_001".to_string(),
            sender: "BANK_A".to_string(),
            receiver: "BANK_B".to_string(),
            amount: 100_000,
            sender_balance_before: 500_000,
            sender_balance_after: 400_000,
        };

        assert_eq!(event.event_type(), "RtgsImmediateSettlement");
    }

    #[test]
    fn test_event_tx_id() {
        let event = Event::PolicySubmit {
            tick: 5,
            agent_id: "BANK_A".to_string(),
            tx_id: "tx_123".to_string(),
        };

        assert_eq!(event.tx_id(), Some("tx_123"));
    }

    #[test]
    fn test_event_agent_id() {
        let event = Event::PolicyHold {
            tick: 5,
            agent_id: "BANK_A".to_string(),
            tx_id: "tx_123".to_string(),
            reason: "Insufficient liquidity".to_string(),
        };

        assert_eq!(event.agent_id(), Some("BANK_A"));
    }

    #[test]
    fn test_event_log_basic() {
        let mut log = EventLog::new();

        assert_eq!(log.len(), 0);
        assert!(log.is_empty());

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        assert_eq!(log.len(), 1);
        assert!(!log.is_empty());
    }

    #[test]
    fn test_event_log_query_by_tick() {
        let mut log = EventLog::new();

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        log.log(Event::RtgsImmediateSettlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender: "BANK_A".to_string(),
            receiver: "BANK_B".to_string(),
            amount: 100_000,
            sender_balance_before: 500_000,
            sender_balance_after: 400_000,
        });

        log.log(Event::Arrival {
            tick: 2,
            tx_id: "tx_002".to_string(),
            sender_id: "BANK_B".to_string(),
            receiver_id: "BANK_A".to_string(),
            amount: 200_000,
            deadline: 20,
            priority: 5,
            is_divisible: false,
        });

        let tick1_events = log.events_at_tick(1);
        assert_eq!(tick1_events.len(), 2);

        let tick2_events = log.events_at_tick(2);
        assert_eq!(tick2_events.len(), 1);
    }

    #[test]
    fn test_event_log_query_by_type() {
        let mut log = EventLog::new();

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        log.log(Event::RtgsImmediateSettlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender: "BANK_A".to_string(),
            receiver: "BANK_B".to_string(),
            amount: 100_000,
            sender_balance_before: 500_000,
            sender_balance_after: 400_000,
        });

        let arrivals = log.events_of_type("Arrival");
        assert_eq!(arrivals.len(), 1);

        let settlements = log.events_of_type("RtgsImmediateSettlement");
        assert_eq!(settlements.len(), 1);
    }

    #[test]
    fn test_event_log_query_by_tx_id() {
        let mut log = EventLog::new();

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        log.log(Event::PolicySubmit {
            tick: 1,
            agent_id: "BANK_A".to_string(),
            tx_id: "tx_001".to_string(),
        });

        log.log(Event::RtgsImmediateSettlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender: "BANK_A".to_string(),
            receiver: "BANK_B".to_string(),
            amount: 100_000,
            sender_balance_before: 500_000,
            sender_balance_after: 400_000,
        });

        let tx_events = log.events_for_tx("tx_001");
        assert_eq!(tx_events.len(), 3);
    }

    #[test]
    fn test_event_log_query_by_agent() {
        let mut log = EventLog::new();

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        log.log(Event::PolicySubmit {
            tick: 1,
            agent_id: "BANK_A".to_string(),
            tx_id: "tx_001".to_string(),
        });

        log.log(Event::Arrival {
            tick: 2,
            tx_id: "tx_002".to_string(),
            sender_id: "BANK_B".to_string(),
            receiver_id: "BANK_A".to_string(),
            amount: 200_000,
            deadline: 20,
            priority: 5,
            is_divisible: false,
        });

        let bank_a_events = log.events_for_agent("BANK_A");
        assert_eq!(bank_a_events.len(), 2);

        let bank_b_events = log.events_for_agent("BANK_B");
        assert_eq!(bank_b_events.len(), 1);
    }

    #[test]
    fn test_event_log_clear() {
        let mut log = EventLog::new();

        log.log(Event::Arrival {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            deadline: 10,
            priority: 5,
            is_divisible: false,
        });

        assert_eq!(log.len(), 1);

        log.clear();
        assert_eq!(log.len(), 0);
        assert!(log.is_empty());
    }

    #[test]
    fn test_transaction_went_overdue_event() {
        let event = Event::TransactionWentOverdue {
            tick: 11,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            remaining_amount: 100_000,
            deadline_tick: 10,
            ticks_overdue: 1,
            deadline_penalty_cost: 50_000, // $500
        };

        assert_eq!(event.tick(), 11);
        assert_eq!(event.event_type(), "TransactionWentOverdue");
        assert_eq!(event.tx_id(), Some("tx_001"));
        assert_eq!(event.agent_id(), Some("BANK_A"));
    }

    #[test]
    fn test_overdue_transaction_settled_event() {
        let event = Event::OverdueTransactionSettled {
            tick: 15,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            settled_amount: 100_000,
            deadline_tick: 10,
            overdue_since_tick: 11,
            total_ticks_overdue: 4, // ticks 11-14
            deadline_penalty_cost: 50_000,
            estimated_delay_cost: 20_000,
        };

        assert_eq!(event.tick(), 15);
        assert_eq!(event.event_type(), "OverdueTransactionSettled");
        assert_eq!(event.tx_id(), Some("tx_001"));
        assert_eq!(event.agent_id(), Some("BANK_A"));
    }

    #[test]
    fn test_overdue_events_in_event_log() {
        let mut log = EventLog::new();

        log.log(Event::TransactionWentOverdue {
            tick: 11,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            remaining_amount: 100_000,
            deadline_tick: 10,
            ticks_overdue: 1,
            deadline_penalty_cost: 50_000,
        });

        log.log(Event::OverdueTransactionSettled {
            tick: 15,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
            settled_amount: 100_000,
            deadline_tick: 10,
            overdue_since_tick: 11,
            total_ticks_overdue: 4,
            deadline_penalty_cost: 50_000,
            estimated_delay_cost: 20_000,
        });

        assert_eq!(log.len(), 2);

        // Query by type
        let went_overdue = log.events_of_type("TransactionWentOverdue");
        assert_eq!(went_overdue.len(), 1);

        let settled = log.events_of_type("OverdueTransactionSettled");
        assert_eq!(settled.len(), 1);

        // Query by transaction
        let tx_events = log.events_for_tx("tx_001");
        assert_eq!(tx_events.len(), 2);

        // Query by agent
        let agent_events = log.events_for_agent("BANK_A");
        assert_eq!(agent_events.len(), 2);

        // Query by tick
        let tick11_events = log.events_at_tick(11);
        assert_eq!(tick11_events.len(), 1);

        let tick15_events = log.events_at_tick(15);
        assert_eq!(tick15_events.len(), 1);
    }
}
