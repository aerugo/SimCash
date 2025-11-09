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

    /// Transaction settled via RTGS
    Settlement {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,
    },

    /// Transaction queued to RTGS queue (insufficient liquidity)
    QueuedRtgs {
        tick: usize,
        tx_id: String,
        sender_id: String,
    },

    /// Transaction settled via LSM bilateral offset
    LsmBilateralOffset {
        tick: usize,
        agent_a: String,
        agent_b: String,
        tx_id_a: String,
        tx_id_b: String,
        amount_a: i64,
        amount_b: i64,
    },

    /// Transaction settled via LSM cycle detection
    LsmCycleSettlement {
        tick: usize,
        tx_ids: Vec<String>,
        cycle_value: i64,
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
            Event::CollateralPost { tick, .. } => *tick,
            Event::CollateralWithdraw { tick, .. } => *tick,
            Event::Settlement { tick, .. } => *tick,
            Event::QueuedRtgs { tick, .. } => *tick,
            Event::LsmBilateralOffset { tick, .. } => *tick,
            Event::LsmCycleSettlement { tick, .. } => *tick,
            Event::CostAccrual { tick, .. } => *tick,
            Event::EndOfDay { tick, .. } => *tick,
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
            Event::CollateralPost { .. } => "CollateralPost",
            Event::CollateralWithdraw { .. } => "CollateralWithdraw",
            Event::Settlement { .. } => "Settlement",
            Event::QueuedRtgs { .. } => "QueuedRtgs",
            Event::LsmBilateralOffset { .. } => "LsmBilateralOffset",
            Event::LsmCycleSettlement { .. } => "LsmCycleSettlement",
            Event::CostAccrual { .. } => "CostAccrual",
            Event::EndOfDay { .. } => "EndOfDay",
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
            Event::Settlement { tx_id, .. } => Some(tx_id),
            Event::QueuedRtgs { tx_id, .. } => Some(tx_id),
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
            Event::CollateralPost { agent_id, .. } => Some(agent_id),
            Event::CollateralWithdraw { agent_id, .. } => Some(agent_id),
            Event::Settlement { sender_id, .. } => Some(sender_id),
            Event::QueuedRtgs { sender_id, .. } => Some(sender_id),
            Event::CostAccrual { agent_id, .. } => Some(agent_id),
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
        let event = Event::Settlement {
            tick: 10,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
        };

        assert_eq!(event.event_type(), "Settlement");
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

        log.log(Event::Settlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
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

        log.log(Event::Settlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
        });

        let arrivals = log.events_of_type("Arrival");
        assert_eq!(arrivals.len(), 1);

        let settlements = log.events_of_type("Settlement");
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

        log.log(Event::Settlement {
            tick: 1,
            tx_id: "tx_001".to_string(),
            sender_id: "BANK_A".to_string(),
            receiver_id: "BANK_B".to_string(),
            amount: 100_000,
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
}
