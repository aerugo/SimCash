//! Cost Rates and Related Types
//!
//! Defines rates for various costs accrued during simulation.
//! All monetary values in cents/minor units.

use serde::{Deserialize, Serialize};

/// Priority band for categorizing transaction urgency
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PriorityBand {
    /// Priority 8-10: Time-critical payments
    Urgent,
    /// Priority 4-7: Standard payments
    Normal,
    /// Priority 0-3: Low priority/batch payments
    Low,
}

/// Get the priority band for a given priority level
///
/// # Arguments
/// * `priority` - Priority level (0-10)
///
/// # Returns
/// The corresponding priority band
pub fn get_priority_band(priority: u8) -> PriorityBand {
    match priority {
        8..=10 => PriorityBand::Urgent,
        4..=7 => PriorityBand::Normal,
        _ => PriorityBand::Low, // 0-3 and any out-of-range values
    }
}

/// Priority-based delay cost multipliers (BIS model support)
///
/// Allows different delay costs for different priority bands.
/// This enables modeling BIS scenarios where urgent payments
/// have higher delay costs than normal payments.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PriorityDelayMultipliers {
    /// Multiplier for urgent priority (8-10). Default: 1.0
    pub urgent_multiplier: f64,
    /// Multiplier for normal priority (4-7). Default: 1.0
    pub normal_multiplier: f64,
    /// Multiplier for low priority (0-3). Default: 1.0
    pub low_multiplier: f64,
}

impl Default for PriorityDelayMultipliers {
    fn default() -> Self {
        Self {
            urgent_multiplier: 1.0,
            normal_multiplier: 1.0,
            low_multiplier: 1.0,
        }
    }
}

impl PriorityDelayMultipliers {
    /// Get the delay cost multiplier for a given priority level
    ///
    /// # Arguments
    /// * `priority` - Priority level (0-10)
    ///
    /// # Returns
    /// The multiplier for the corresponding priority band
    pub fn get_multiplier_for_priority(&self, priority: u8) -> f64 {
        match get_priority_band(priority) {
            PriorityBand::Urgent => self.urgent_multiplier,
            PriorityBand::Normal => self.normal_multiplier,
            PriorityBand::Low => self.low_multiplier,
        }
    }
}

/// Cost Rates Configuration
///
/// Defines rates for various costs accrued during simulation.
/// All monetary values in cents/minor units.
#[derive(Debug, Clone, Serialize, Deserialize)]
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

    /// Priority-based delay cost multipliers (BIS model support)
    ///
    /// When configured, applies different multipliers to delay costs based on
    /// transaction priority bands:
    /// - Urgent (8-10): urgent_multiplier
    /// - Normal (4-7): normal_multiplier
    /// - Low (0-3): low_multiplier
    ///
    /// If None, all priorities use the same base delay cost rate.
    #[serde(default)]
    pub priority_delay_multipliers: Option<PriorityDelayMultipliers>,

    /// Liquidity opportunity cost in basis points per tick (Enhancement 11.2)
    ///
    /// Applied to allocated liquidity (from liquidity_pool × allocation_fraction)
    /// to represent the opportunity cost of holding funds in the settlement system
    /// rather than earning interest elsewhere.
    ///
    /// Example: 15 bps per tick for a 1M allocation = 1,000,000 × (15/10,000) = 1,500 cents/tick
    ///
    /// Note: This only applies to allocated liquidity, not to opening_balance
    /// (which is assumed to already be at the central bank).
    #[serde(default)]
    pub liquidity_cost_per_tick_bps: f64,
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
            priority_delay_multipliers: None,     // No priority differentiation by default
            liquidity_cost_per_tick_bps: 0.0,     // No liquidity opportunity cost by default
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cost_rates_default() {
        let rates = CostRates::default();
        assert_eq!(rates.overdraft_bps_per_tick, 0.001);
        assert_eq!(rates.delay_cost_per_tick_per_cent, 0.0001);
        assert_eq!(rates.collateral_cost_per_tick_bps, 0.0002);
        assert_eq!(rates.eod_penalty_per_transaction, 10_000);
        assert_eq!(rates.deadline_penalty, 50_000);
        assert_eq!(rates.split_friction_cost, 1000);
        assert_eq!(rates.overdue_delay_multiplier, 5.0);
        assert!(rates.priority_delay_multipliers.is_none());
        assert_eq!(rates.liquidity_cost_per_tick_bps, 0.0);
    }

    #[test]
    fn test_priority_delay_multipliers_default() {
        let mults = PriorityDelayMultipliers::default();
        assert_eq!(mults.urgent_multiplier, 1.0);
        assert_eq!(mults.normal_multiplier, 1.0);
        assert_eq!(mults.low_multiplier, 1.0);
    }

    #[test]
    fn test_get_multiplier_for_priority() {
        let mults = PriorityDelayMultipliers {
            urgent_multiplier: 2.0,
            normal_multiplier: 1.0,
            low_multiplier: 0.5,
        };

        // Urgent (8-10)
        assert_eq!(mults.get_multiplier_for_priority(10), 2.0);
        assert_eq!(mults.get_multiplier_for_priority(9), 2.0);
        assert_eq!(mults.get_multiplier_for_priority(8), 2.0);

        // Normal (4-7)
        assert_eq!(mults.get_multiplier_for_priority(7), 1.0);
        assert_eq!(mults.get_multiplier_for_priority(5), 1.0);
        assert_eq!(mults.get_multiplier_for_priority(4), 1.0);

        // Low (0-3)
        assert_eq!(mults.get_multiplier_for_priority(3), 0.5);
        assert_eq!(mults.get_multiplier_for_priority(1), 0.5);
        assert_eq!(mults.get_multiplier_for_priority(0), 0.5);
    }

    #[test]
    fn test_cost_rates_serialize_deserialize() {
        let rates = CostRates::default();
        let json = serde_json::to_string(&rates).unwrap();
        let restored: CostRates = serde_json::from_str(&json).unwrap();

        assert_eq!(rates.overdraft_bps_per_tick, restored.overdraft_bps_per_tick);
        assert_eq!(rates.deadline_penalty, restored.deadline_penalty);
    }
}
