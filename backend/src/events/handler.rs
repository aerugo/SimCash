//! Scenario event execution and scheduling
//!
//! This module handles:
//! - Scheduling events by tick
//! - Executing events to modify state
//! - Logging events for replay

use crate::events::types::{EventSchedule, ScenarioEvent, ScheduledEvent};
use crate::models::{state::SimulationState, Event};
use serde_json::json;

/// Handles scenario event scheduling and execution
pub struct ScenarioEventHandler {
    events: Vec<ScheduledEvent>,
}

impl ScenarioEventHandler {
    /// Create a new event handler with the given events
    pub fn new(events: Vec<ScheduledEvent>) -> Self {
        Self { events }
    }

    /// Get all events scheduled for a specific tick
    pub fn get_events_for_tick(&self, tick: usize) -> Vec<&ScenarioEvent> {
        self.events
            .iter()
            .filter(|scheduled| scheduled.schedule.should_execute(tick))
            .map(|scheduled| &scheduled.event)
            .collect()
    }

    /// Execute all events scheduled for the given tick
    ///
    /// Returns Ok with number of events executed, or Err if any event fails
    pub fn execute_tick_events(
        &self,
        state: &mut SimulationState,
        tick: usize,
    ) -> Result<usize, String> {
        let events = self.get_events_for_tick(tick);
        let count = events.len();

        for event in events {
            event.execute(state, tick)?;
        }

        Ok(count)
    }
}

impl ScenarioEvent {
    /// Execute this event, modifying the given state
    ///
    /// # Arguments
    /// * `state` - Simulation state to modify
    /// * `tick` - Current tick number
    ///
    /// # Returns
    /// Ok(()) if successful, Err with description if failed
    pub fn execute(&self, state: &mut SimulationState, tick: usize) -> Result<(), String> {
        match self {
            ScenarioEvent::DirectTransfer {
                from_agent,
                to_agent,
                amount,
            } => execute_direct_transfer(state, tick, from_agent, to_agent, *amount),

            ScenarioEvent::CollateralAdjustment { agent, delta } => {
                execute_collateral_adjustment(state, tick, agent, *delta)
            }

            // CustomTransactionArrival is handled at Orchestrator level
            ScenarioEvent::CustomTransactionArrival { .. } => {
                Err("CustomTransactionArrival must be handled at Orchestrator level".to_string())
            }

            // TODO: Implement these at Orchestrator level
            ScenarioEvent::GlobalArrivalRateChange { .. } => {
                Err("GlobalArrivalRateChange not yet implemented".to_string())
            }

            ScenarioEvent::AgentArrivalRateChange { .. } => {
                Err("AgentArrivalRateChange not yet implemented".to_string())
            }

            ScenarioEvent::CounterpartyWeightChange { .. } => {
                Err("CounterpartyWeightChange not yet implemented".to_string())
            }

            ScenarioEvent::DeadlineWindowChange { .. } => {
                Err("DeadlineWindowChange not yet implemented".to_string())
            }
        }
    }
}

// ============================================================================
// Event Execution Functions
// ============================================================================

fn execute_direct_transfer(
    state: &mut SimulationState,
    tick: usize,
    from_agent: &str,
    to_agent: &str,
    amount: i64,
) -> Result<(), String> {
    // Validate agents exist
    if state.get_agent(from_agent).is_none() {
        return Err(format!("Agent not found: {}", from_agent));
    }
    if state.get_agent(to_agent).is_none() {
        return Err(format!("Agent not found: {}", to_agent));
    }

    // Execute transfer (bypasses liquidity checks - can go negative)
    state
        .get_agent_mut(from_agent)
        .unwrap()
        .adjust_balance(-amount);
    state.get_agent_mut(to_agent).unwrap().adjust_balance(amount);

    // Log event
    log_scenario_event(state, tick, "direct_transfer", &json!({
        "from_agent": from_agent,
        "to_agent": to_agent,
        "amount": amount,
    }));

    Ok(())
}

fn execute_collateral_adjustment(
    state: &mut SimulationState,
    tick: usize,
    agent: &str,
    delta: i64,
) -> Result<(), String> {
    // Validate agent exists
    let agent_obj = state
        .get_agent(agent)
        .ok_or_else(|| format!("Agent not found: {}", agent))?;

    let old_limit = agent_obj.credit_limit();
    let new_limit = (old_limit as i64) + delta;

    // Cannot go negative
    if new_limit < 0 {
        return Err(format!(
            "Credit limit cannot go negative (current: {}, delta: {})",
            old_limit, delta
        ));
    }

    // Apply adjustment
    state.set_credit_limit(agent, new_limit as i64);

    // Log event
    log_scenario_event(state, tick, "collateral_adjustment", &json!({
        "agent": agent,
        "delta": delta,
        "old_limit": old_limit,
        "new_limit": new_limit,
    }));

    Ok(())
}

// ============================================================================
// Helper Functions
// ============================================================================

fn log_scenario_event(state: &mut SimulationState, tick: usize, event_type: &str, details: &serde_json::Value) {
    state.log_event(Event::ScenarioEventExecuted {
        tick,
        event_type: event_type.to_string(),
        details: details.clone(),
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Agent;

    #[test]
    fn test_event_handler_get_events_for_tick() {
        let events = vec![
            ScheduledEvent {
                event: ScenarioEvent::DirectTransfer {
                    from_agent: "A".to_string(),
                    to_agent: "B".to_string(),
                    amount: 100,
                },
                schedule: EventSchedule::OneTime { tick: 10 },
            },
        ];

        let handler = ScenarioEventHandler::new(events);

        // Tick 10 should have the event
        assert_eq!(handler.get_events_for_tick(10).len(), 1);

        // Tick 11 should have no events
        assert_eq!(handler.get_events_for_tick(11).len(), 0);
    }
}
