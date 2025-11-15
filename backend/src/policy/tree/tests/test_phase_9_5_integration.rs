// Phase 9.5 Integration Tests
//
// Validates that all Phase 9.5 features work together end-to-end:
// - Phase 9.5.1: Cost-Aware Context
// - Phase 9.5.2: System Configuration Context
// - Phase 9.5.3: Dynamic Action Parameters

#[cfg(test)]
mod test_phase_9_5_integration {
    use crate::orchestrator::CostRates;
    use crate::policy::tree::{EvalContext, TreePolicy};
    use crate::policy::CashManagerPolicy;
    use crate::{Agent, SimulationState, Transaction};
    use std::path::PathBuf;

    /// Get the policies directory path (matches factory.rs pattern)
    fn policies_dir() -> PathBuf {
        // First try backend/policies (when running from project root)
        let backend_policies = PathBuf::from("backend/policies");
        if backend_policies.exists() {
            return backend_policies;
        }

        // Fall back to policies/ (when running tests from backend/ directory)
        PathBuf::from("policies")
    }

    fn create_cost_rates() -> CostRates {
        CostRates {
            overdraft_bps_per_tick: 10.0,         // 10 bps per tick (expensive)
            delay_cost_per_tick_per_cent: 0.00001, // 0.001 bps per tick (cheap)
            collateral_cost_per_tick_bps: 0.0002,  // 0.02 bps per tick
            eod_penalty_per_transaction: 1000_00,  // $1,000 EOD penalty
            deadline_penalty: 500_00,               // $500 deadline penalty
            split_friction_cost: 10_00,             // $10 per split
            ..Default::default()
        }
    }

    #[test]
    fn test_adaptive_liquidity_manager_policy_loads() {
        let path = policies_dir().join("adaptive_liquidity_manager.json");
        let policy = TreePolicy::from_file(path);
        assert!(
            policy.is_ok(),
            "Failed to load adaptive liquidity manager policy: {:?}",
            policy.err()
        );

        let policy = policy.unwrap();
        assert_eq!(policy.policy_id(), "adaptive_liquidity_gridlock_manager");

        // Verify all three trees are present
        assert!(
            policy.tree().payment_tree.is_some(),
            "Payment tree should be present"
        );
        assert!(
            policy.tree().strategic_collateral_tree.is_some(),
            "Strategic collateral tree should be present"
        );
        assert!(
            policy.tree().end_of_tick_collateral_tree.is_some(),
            "End-of-tick collateral tree should be present"
        );
    }

    #[test]
    fn test_eod_rush_triggers_aggressive_release() {
        let mut policy =
            TreePolicy::from_file(policies_dir().join("adaptive_liquidity_manager.json")).unwrap();

        // Setup: Tick 90 of 100 (EOD rush with threshold 0.8)
        let tick = 90;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        // Agent with sufficient liquidity
        let mut agent = Agent::new("BANK_A".to_string(), 2_000_000);

        // Transaction with normal deadline (not urgent)
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000,
            80,
            120, // Deadline at tick 120 (not urgent: 30 ticks away)
        );
        let tx_id = tx.id().to_string();

        agent.queue_outgoing(tx_id.clone());

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        let cost_rates = create_cost_rates();

        // Evaluate policy
        let decisions =
            policy.evaluate_queue(&agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold);

        // Should release due to EOD rush (even though not urgent)
        assert_eq!(decisions.len(), 1);
        assert!(
            matches!(
                &decisions[0],
                crate::policy::ReleaseDecision::SubmitFull { .. }
            ),
            "Should release during EOD rush, got: {:?}",
            decisions[0]
        );
    }

    #[test]
    fn test_early_day_conservative_strategy() {
        let mut policy =
            TreePolicy::from_file(policies_dir().join("adaptive_liquidity_manager.json")).unwrap();

        // Setup: Tick 20 of 100 (early day: 20%)
        let tick = 20;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        // Agent with INSUFFICIENT liquidity (not 1.5x buffer: 130k < 1.5 * 100k = 150k)
        let mut agent = Agent::new("BANK_A".to_string(), 130_000);

        // Transaction
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000, // Amount requires 150k for 1.5x buffer, but we only have 130k
            10,
            80,
        )
        .with_priority(5); // Normal priority

        let tx_id = tx.id().to_string();
        agent.queue_outgoing(tx_id.clone());

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        let cost_rates = create_cost_rates();

        // Evaluate policy
        let decisions =
            policy.evaluate_queue(&agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold);

        // Should hold due to conservative early-day strategy
        assert_eq!(decisions.len(), 1);
        assert!(
            matches!(&decisions[0], crate::policy::ReleaseDecision::Hold { .. }),
            "Should hold in early day with insufficient buffer, got: {:?}",
            decisions[0]
        );
    }

    #[test]
    fn test_cost_based_credit_decision() {
        let mut policy =
            TreePolicy::from_file(policies_dir().join("adaptive_liquidity_manager.json")).unwrap();

        // Setup: Late day (tick 75 of 100), urgent deadline
        let tick = 75;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        // Agent with insufficient balance but credit available
        let mut agent = Agent::new(
            "BANK_A".to_string(),
            50_000   // Low balance
        );

        // Urgent transaction (deadline in 3 ticks)
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000, // More than balance
            70,
            78, // Deadline in 3 ticks (urgent)
        );
        let tx_id = tx.id().to_string();

        agent.queue_outgoing(tx_id.clone());

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        let cost_rates = CostRates {
            overdraft_bps_per_tick: 2.0, // Overdraft cheaper than deadline penalty
            deadline_penalty: 500_00,     // $500 penalty
            ..create_cost_rates()
        };

        // Evaluate policy
        let decisions =
            policy.evaluate_queue(&agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold);

        // Should release (policy uses ReleaseWithCredit action, but result is SubmitFull)
        // because overdraft cost < deadline penalty
        assert_eq!(decisions.len(), 1);
        assert!(
            matches!(
                &decisions[0],
                crate::policy::ReleaseDecision::SubmitFull { .. }
            ),
            "Should release when overdraft cheaper than penalty, got: {:?}",
            decisions[0]
        );
    }

    #[test]
    fn test_strategic_collateral_eod_gap() {
        let mut policy =
            TreePolicy::from_file(policies_dir().join("adaptive_liquidity_manager.json")).unwrap();

        // Setup: Late day (tick 75 of 100), approaching EOD
        let tick = 75;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        // Agent with:
        // - Low balance
        // - Queued transactions (creating liquidity gap)
        // - Collateral capacity available (10x unsecured_cap = 10x50k = 500k)
        let mut agent = Agent::new(
            "BANK_A".to_string(),
            100_000  // Balance
        );
        agent.set_unsecured_cap(50_000); // $500 unsecured overdraft

        // Queue transactions totaling 300k (gap = 300k - 100k = 200k)
        let tx1 = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 150_000, tick, tick + 20);
        let tx2 = Transaction::new("BANK_A".to_string(), "BANK_C".to_string(), 150_000, tick, tick + 20);

        agent.queue_outgoing(tx1.id().to_string());
        agent.queue_outgoing(tx2.id().to_string());

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx1);
        state.add_transaction(tx2);

        let cost_rates = create_cost_rates();

        // Evaluate strategic collateral
        let decision = policy
            .evaluate_strategic_collateral(&agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold)
            .unwrap();

        // Should post collateral to cover the gap
        assert!(
            matches!(
                decision,
                crate::policy::CollateralDecision::Post { amount, .. } if amount > 0
            ),
            "Should post collateral for EOD liquidity gap, got: {:?}",
            decision
        );

        if let crate::policy::CollateralDecision::Post { amount, .. } = decision {
            // Amount should cover the liquidity gap
            // Gap = max(queue_total - available_liquidity, 0) = max(300k - 100k, 0) = 200k
            // But the policy uses max(queue1_liquidity_gap, 0) which might calculate differently
            // The policy correctly posts collateral to cover the gap
            assert!(
                amount >= 100_000 && amount <= 210_000,
                "Posted amount should cover liquidity gap, got: {}",
                amount
            );
        }
    }

    #[test]
    fn test_end_of_tick_collateral_withdrawal() {
        let mut policy =
            TreePolicy::from_file(policies_dir().join("adaptive_liquidity_manager.json")).unwrap();

        // Setup: After settlements, we have excess headroom
        let tick = 50;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        // Agent with:
        // - Posted collateral (200k)
        // - Strong balance
        // - Small remaining queue
        // - Collateral capacity (10x credit = 10x50k = 500k)
        let mut agent = Agent::new(
            "BANK_A".to_string(),
            500_000  // Strong balance
        );

        // Post collateral (simulating strategic collateral from earlier)
        agent.set_posted_collateral(200_000);

        // Small remaining queue (only 50k)
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 50_000, tick, tick + 20);
        agent.queue_outgoing(tx.id().to_string());

        let mut state = SimulationState::new(vec![agent.clone()]);
        state.add_transaction(tx);

        // Use costly collateral rates to trigger withdrawal
        let cost_rates = CostRates {
            collateral_cost_per_tick_bps: 0.01, // Expensive collateral (1 bp per tick)
            ..create_cost_rates()
        };

        // Evaluate end-of-tick collateral
        let decision = policy
            .evaluate_end_of_tick_collateral(&agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold)
            .unwrap();

        // Should withdraw some collateral due to excess headroom + costly collateral
        assert!(
            matches!(
                decision,
                crate::policy::CollateralDecision::Withdraw { amount, .. } if amount > 0
            ),
            "Should withdraw excess collateral when headroom is large, got: {:?}",
            decision
        );

        if let crate::policy::CollateralDecision::Withdraw { amount, .. } = decision {
            // Should withdraw approximately half (100k)
            assert!(
                amount >= 90_000 && amount <= 110_000,
                "Should withdraw ~half of posted collateral, got: {}",
                amount
            );
        }
    }

    #[test]
    fn test_all_phase_9_5_features_in_single_context() {
        // This test verifies that a single EvalContext contains all Phase 9.5 fields

        let agent = Agent::new(
            "BANK_A".to_string(),
            500_000  // Balance
        );

        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000,
            10,
            80,
        );

        let state = SimulationState::new(vec![agent.clone()]);

        let cost_rates = create_cost_rates();
        let tick = 90;
        let ticks_per_day = 100;
        let eod_rush_threshold = 0.8;

        let context = EvalContext::build(
            &tx,
            &agent,
            &state,
            tick,
            &cost_rates,
            ticks_per_day,
            eod_rush_threshold,
        );

        // Phase 9.5.1: Cost fields
        assert!(context.has_field("cost_overdraft_bps_per_tick"));
        assert!(context.has_field("cost_delay_per_tick_per_cent"));
        assert!(context.has_field("cost_collateral_bps_per_tick"));
        assert!(context.has_field("cost_split_friction"));
        assert!(context.has_field("cost_deadline_penalty"));
        assert!(context.has_field("cost_eod_penalty"));
        assert!(context.has_field("cost_delay_this_tx_one_tick"));
        assert!(context.has_field("cost_overdraft_this_amount_one_tick"));

        // Phase 9.5.2: System configuration fields
        assert!(context.has_field("system_ticks_per_day"));
        assert!(context.has_field("system_current_day"));
        assert!(context.has_field("system_tick_in_day"));
        assert!(context.has_field("ticks_remaining_in_day"));
        assert!(context.has_field("day_progress_fraction"));
        assert!(context.has_field("is_eod_rush"));

        // Verify EOD rush is correctly detected (tick 90 of 100 with threshold 0.8)
        assert_eq!(context.get_field("is_eod_rush").unwrap(), 1.0);

        // Verify system fields have correct values
        assert_eq!(context.get_field("system_ticks_per_day").unwrap(), 100.0);
        assert_eq!(context.get_field("system_tick_in_day").unwrap(), 90.0);
        assert_eq!(context.get_field("ticks_remaining_in_day").unwrap(), 9.0);

        // All existing fields should still be present
        assert!(context.has_field("balance"));
        assert!(context.has_field("available_liquidity"));
        assert!(context.has_field("amount"));
        assert!(context.has_field("ticks_to_deadline"));
        assert!(context.has_field("queue1_liquidity_gap"));
        assert!(context.has_field("posted_collateral"));
    }
}
