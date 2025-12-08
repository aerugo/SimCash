//! Collateral Event Model
//!
//! Tracks individual collateral management decisions for Phase 10 persistence.

use serde::{Deserialize, Serialize};

/// Collateral management action
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CollateralAction {
    /// Posted collateral to increase liquidity
    Post,
    /// Withdrew collateral (no longer needed)
    Withdraw,
    /// Considered posting but decided not to (policy decision)
    Hold,
}

/// Layer where collateral decision occurred
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum CollateralLayer {
    /// Strategic policy-driven decision (from policy tree)
    Strategic,
    /// Automatic end-of-tick posting/withdrawal
    EndOfTick,
}

/// Individual collateral management event
///
/// Captures every collateral decision with full context:
/// - What: action (post/withdraw/hold) and amount
/// - When: tick and day
/// - Who: agent_id
/// - Why: reason string
/// - How: layer (strategic vs automatic)
/// - State: before/after balances and collateral
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollateralEvent {
    /// Agent that made the collateral decision
    pub agent_id: String,

    /// Tick when event occurred (0-indexed within simulation)
    pub tick: usize,

    /// Day when event occurred (0-indexed)
    pub day: usize,

    /// Action taken (post, withdraw, hold)
    pub action: CollateralAction,

    /// Amount of collateral posted/withdrawn (i64 cents)
    /// For Hold actions, this is the amount that was considered
    pub amount: i64,

    /// Reason for the action (e.g., "insufficient_liquidity", "strategic_decision")
    pub reason: String,

    /// Layer where decision occurred (strategic vs end-of-tick)
    pub layer: CollateralLayer,

    /// Agent balance before action (i64 cents)
    pub balance_before: i64,

    /// Posted collateral before action (i64 cents)
    pub posted_collateral_before: i64,

    /// Posted collateral after action (i64 cents)
    pub posted_collateral_after: i64,

    /// Available collateral capacity after action (i64 cents)
    /// = max_capacity - posted_collateral_after
    pub available_capacity_after: i64,
}

impl CollateralEvent {
    /// Create a new collateral event
    ///
    /// # Arguments
    /// * `agent_id` - Agent making the decision
    /// * `tick` - Current tick
    /// * `day` - Current day
    /// * `action` - Action taken
    /// * `amount` - Amount posted/withdrawn
    /// * `reason` - Reason for action
    /// * `layer` - Decision layer
    /// * `balance_before` - Balance before action
    /// * `posted_collateral_before` - Collateral before action
    /// * `posted_collateral_after` - Collateral after action
    /// * `available_capacity_after` - Remaining capacity after action
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        agent_id: String,
        tick: usize,
        day: usize,
        action: CollateralAction,
        amount: i64,
        reason: String,
        layer: CollateralLayer,
        balance_before: i64,
        posted_collateral_before: i64,
        posted_collateral_after: i64,
        available_capacity_after: i64,
    ) -> Self {
        Self {
            agent_id,
            tick,
            day,
            action,
            amount,
            reason,
            layer,
            balance_before,
            posted_collateral_before,
            posted_collateral_after,
            available_capacity_after,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_collateral_event_creation() {
        let event = CollateralEvent::new(
            "BANK_A".to_string(),
            42,
            0,
            CollateralAction::Post,
            100_000,
            "insufficient_liquidity".to_string(),
            CollateralLayer::Strategic,
            500_000,
            0,
            100_000,
            4_900_000,
        );

        assert_eq!(event.agent_id, "BANK_A");
        assert_eq!(event.tick, 42);
        assert_eq!(event.day, 0);
        assert_eq!(event.action, CollateralAction::Post);
        assert_eq!(event.amount, 100_000);
        assert_eq!(event.layer, CollateralLayer::Strategic);
    }

    #[test]
    fn test_collateral_action_variants() {
        // Verify all action variants compile
        let _ = CollateralAction::Post;
        let _ = CollateralAction::Withdraw;
        let _ = CollateralAction::Hold;
    }

    #[test]
    fn test_collateral_layer_variants() {
        // Verify all layer variants compile
        let _ = CollateralLayer::Strategic;
        let _ = CollateralLayer::EndOfTick;
    }
}
