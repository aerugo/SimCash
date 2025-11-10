//! Scenario event types for simulation configuration
//!
//! Scenario events allow modifying simulation state at specific ticks.
//! Examples: direct transfers, collateral adjustments, arrival rate changes.
//!
//! # Design Principles
//!
//! 1. **Determinism**: All events are deterministically scheduled and executed
//! 2. **Money is i64**: All monetary values are integer cents
//! 3. **Self-contained**: Events include all data needed for execution
//! 4. **Logged**: All executions are logged for replay identity

use serde::{Deserialize, Serialize};

/// A scenario event that modifies simulation state
///
/// Events are configured in YAML and executed at specific ticks.
/// All events are logged to enable replay identity.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ScenarioEvent {
    /// Direct transfer of funds between agents
    ///
    /// Moves money from one agent to another, bypassing normal settlement.
    /// Useful for modeling external liquidity injections or withdrawals.
    ///
    /// # Example
    /// Monthly payroll: corporate bank → consumer bank
    DirectTransfer {
        from_agent: String,
        to_agent: String,
        amount: i64, // Integer cents
    },

    /// Adjust agent's credit limit (collateral)
    ///
    /// Positive delta increases credit, negative decreases.
    ///
    /// # Example
    /// Central bank expands emergency liquidity facility
    CollateralAdjustment {
        agent: String,
        delta: i64, // Can be positive or negative
    },

    /// Change arrival rates for all agents
    ///
    /// Multiplies all agents' arrival rates by the given factor.
    ///
    /// # Example
    /// Market rush: 33% increase in transaction volume
    GlobalArrivalRateChange {
        multiplier: f64, // OK to use float for rates (not money)
    },

    /// Change arrival rate for specific agent
    ///
    /// Multiplies one agent's arrival rate.
    ///
    /// # Example
    /// Bank D's corporate clients increase activity
    AgentArrivalRateChange {
        agent: String,
        multiplier: f64,
    },

    /// Adjust counterparty weights for an agent
    ///
    /// Changes the probability of sending to a specific counterparty.
    /// If auto_balance_others is true, other weights are adjusted proportionally.
    ///
    /// # Example
    /// Bank D increases transactions to Bank A from 20% to 50%
    CounterpartyWeightChange {
        agent: String,
        counterparty: String,
        new_weight: f64,
        auto_balance_others: bool,
    },

    /// Change deadline window parameters
    ///
    /// Multiplies min/max deadline ticks by the given factors.
    /// Useful for modeling tighter settlement windows.
    ///
    /// # Example
    /// Regulators tighten deadlines by 20% (multiply by 0.8)
    DeadlineWindowChange {
        min_ticks_multiplier: Option<f64>,
        max_ticks_multiplier: Option<f64>,
    },
}

/// When to execute a scenario event
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum EventSchedule {
    /// Execute once at a specific tick
    OneTime { tick: usize },

    /// Execute at regular intervals starting from start_tick
    Repeating { start_tick: usize, interval: usize },
}

impl EventSchedule {
    /// Check if this schedule triggers at the given tick
    pub fn should_execute(&self, tick: usize) -> bool {
        match self {
            EventSchedule::OneTime { tick: event_tick } => tick == *event_tick,
            EventSchedule::Repeating { start_tick, interval } => {
                tick >= *start_tick && (tick - start_tick) % interval == 0
            }
        }
    }
}

/// A scenario event paired with its schedule
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScheduledEvent {
    pub event: ScenarioEvent,
    pub schedule: EventSchedule,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_one_time_schedule() {
        let schedule = EventSchedule::OneTime { tick: 10 };

        assert!(!schedule.should_execute(9));
        assert!(schedule.should_execute(10));
        assert!(!schedule.should_execute(11));
    }

    #[test]
    fn test_repeating_schedule() {
        let schedule = EventSchedule::Repeating {
            start_tick: 10,
            interval: 5,
        };

        assert!(!schedule.should_execute(9));
        assert!(schedule.should_execute(10));
        assert!(!schedule.should_execute(11));
        assert!(schedule.should_execute(15));
        assert!(schedule.should_execute(20));
        assert!(!schedule.should_execute(22));
    }

    #[test]
    fn test_repeating_schedule_start_at_zero() {
        let schedule = EventSchedule::Repeating {
            start_tick: 0,
            interval: 10,
        };

        assert!(schedule.should_execute(0));
        assert!(schedule.should_execute(10));
        assert!(schedule.should_execute(20));
        assert!(!schedule.should_execute(15));
    }
}
