// Phase 9.5.2: System Configuration Context Tests
//
// These tests verify that system-wide configuration parameters are exposed
// to policy decision trees, enabling time-of-day strategies (e.g., EOD rush behavior).
//
// TDD Approach: These tests WILL FAIL initially until implementation is complete.

#[cfg(test)]
mod test_system_context {
    use crate::models::{Agent, Transaction};
    use crate::orchestrator::CostRates;
    use crate::policy::tree::context::EvalContext;
    use crate::SimulationState;

    /// Helper: Create test context with system config at specific tick
    fn create_test_context_at_tick(tick: usize, ticks_per_day: usize) -> EvalContext {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 500_000);
        let tx = Transaction::new(
            "BANK_A".to_string(),
            "BANK_B".to_string(),
            100_000,
            0,
            ticks_per_day, // deadline at end of day
        );
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = CostRates::default();
        let eod_rush_threshold = 0.8; // Last 20% of day

        EvalContext::build(&tx, &agent, &state, tick, &cost_rates, ticks_per_day, eod_rush_threshold)
    }

    /// Helper: Create context at tick 80 of 100
    fn create_test_context_at_tick_80_of_100() -> EvalContext {
        create_test_context_at_tick(80, 100)
    }

    /// Helper: Create context at tick 20 of 100
    fn create_test_context_at_tick_20_of_100() -> EvalContext {
        create_test_context_at_tick(20, 100)
    }

    /// Helper: Create context at tick 90 of 100 (in EOD rush)
    fn create_test_context_at_tick_90_of_100() -> EvalContext {
        create_test_context_at_tick(90, 100)
    }

    // ========================================================================
    // TEST 1: System ticks_per_day field available
    // ========================================================================
    #[test]
    fn test_system_ticks_per_day_available() {
        let context = create_test_context_at_tick_80_of_100();

        assert!(
            context.has_field("system_ticks_per_day"),
            "Missing system_ticks_per_day field"
        );
        assert_eq!(context.get_field("system_ticks_per_day").unwrap(), 100.0);
    }

    // ========================================================================
    // TEST 2: System current_day field available
    // ========================================================================
    #[test]
    fn test_system_current_day_available() {
        // Day 0: ticks 0-99
        let context_day0 = create_test_context_at_tick(50, 100);
        assert!(context_day0.has_field("system_current_day"));
        assert_eq!(context_day0.get_field("system_current_day").unwrap(), 0.0);

        // Day 1: ticks 100-199
        let context_day1 = create_test_context_at_tick(150, 100);
        assert_eq!(context_day1.get_field("system_current_day").unwrap(), 1.0);

        // Day 2: ticks 200-299
        let context_day2 = create_test_context_at_tick(250, 100);
        assert_eq!(context_day2.get_field("system_current_day").unwrap(), 2.0);
    }

    // ========================================================================
    // TEST 3: System tick_in_day field available
    // ========================================================================
    #[test]
    fn test_system_tick_in_day_available() {
        let context = create_test_context_at_tick(80, 100);

        assert!(
            context.has_field("system_tick_in_day"),
            "Missing system_tick_in_day field"
        );
        // Tick 80 in a 100-tick day → tick_in_day = 80
        assert_eq!(context.get_field("system_tick_in_day").unwrap(), 80.0);

        // Test at day boundary
        let context_new_day = create_test_context_at_tick(100, 100);
        assert_eq!(
            context_new_day.get_field("system_tick_in_day").unwrap(),
            0.0
        );
    }

    // ========================================================================
    // TEST 4: Derived ticks_remaining_in_day
    // ========================================================================
    #[test]
    fn test_derived_ticks_remaining_in_day() {
        let context = create_test_context_at_tick(80, 100);

        assert!(
            context.has_field("ticks_remaining_in_day"),
            "Missing ticks_remaining_in_day field"
        );

        // Tick 80 of 100: remaining = 100 - 80 - 1 = 19
        assert_eq!(
            context.get_field("ticks_remaining_in_day").unwrap(),
            19.0,
            "At tick 80 of 100, should have 19 ticks remaining"
        );

        // Test at start of day
        let context_start = create_test_context_at_tick(0, 100);
        assert_eq!(
            context_start.get_field("ticks_remaining_in_day").unwrap(),
            99.0
        );

        // Test near end of day
        let context_end = create_test_context_at_tick(99, 100);
        assert_eq!(
            context_end.get_field("ticks_remaining_in_day").unwrap(),
            0.0
        );
    }

    // ========================================================================
    // TEST 5: Derived day_progress_fraction
    // ========================================================================
    #[test]
    fn test_derived_day_progress_fraction() {
        let context = create_test_context_at_tick(80, 100);

        assert!(
            context.has_field("day_progress_fraction"),
            "Missing day_progress_fraction field"
        );

        // Tick 80 of 100 → 0.8 (80%)
        let progress = context.get_field("day_progress_fraction").unwrap();
        assert!((progress - 0.8).abs() < 0.0001, "Expected 0.8, got {}", progress);

        // Test at 0%
        let context_start = create_test_context_at_tick(0, 100);
        assert_eq!(
            context_start.get_field("day_progress_fraction").unwrap(),
            0.0
        );

        // Test at 50%
        let context_mid = create_test_context_at_tick(50, 100);
        assert_eq!(
            context_mid.get_field("day_progress_fraction").unwrap(),
            0.5
        );
    }

    // ========================================================================
    // TEST 6: Boolean is_eod_rush field
    // ========================================================================
    #[test]
    fn test_is_eod_rush_boolean_field() {
        let context_early = create_test_context_at_tick_20_of_100();
        let context_late = create_test_context_at_tick_90_of_100();

        assert!(
            context_late.has_field("is_eod_rush"),
            "Missing is_eod_rush field"
        );

        // Tick 90 of 100 = 90% through day, threshold is 80% → in EOD rush
        assert_eq!(
            context_late.get_field("is_eod_rush").unwrap(),
            1.0,
            "Tick 90 should be in EOD rush (>= 80%)"
        );

        // Tick 20 of 100 = 20% through day → not in EOD rush
        assert_eq!(
            context_early.get_field("is_eod_rush").unwrap(),
            0.0,
            "Tick 20 should NOT be in EOD rush (< 80%)"
        );
    }

    // ========================================================================
    // TEST 7: EOD rush threshold is configurable
    // ========================================================================
    #[test]
    fn test_eod_rush_threshold_configurable() {
        let agent = Agent::new("BANK_A".to_string(), 1_000_000, 0);
        let tx = Transaction::new("BANK_A".to_string(), "BANK_B".to_string(), 100_000, 0, 100);
        let state = SimulationState::new(vec![agent.clone()]);
        let cost_rates = CostRates::default();

        // Threshold 0.5 (50%) - tick 60 should be in EOD rush
        let context_50pct = EvalContext::build(&tx, &agent, &state, 60, &cost_rates, 100, 0.5);
        assert_eq!(context_50pct.get_field("is_eod_rush").unwrap(), 1.0);

        // Threshold 0.9 (90%) - tick 60 should NOT be in EOD rush
        let context_90pct = EvalContext::build(&tx, &agent, &state, 60, &cost_rates, 100, 0.9);
        assert_eq!(context_90pct.get_field("is_eod_rush").unwrap(), 0.0);
    }

    // ========================================================================
    // TEST 8: System context integration with tree
    // ========================================================================
    #[test]
    fn test_system_context_integration_with_tree() {
        let context = create_test_context_at_tick_80_of_100();

        // Should be able to use system fields in expressions
        let ticks_per_day = context.get_field("system_ticks_per_day");
        let day_progress = context.get_field("day_progress_fraction");
        let is_eod = context.get_field("is_eod_rush");

        assert!(ticks_per_day.is_ok());
        assert!(day_progress.is_ok());
        assert!(is_eod.is_ok());
    }

    // ========================================================================
    // TEST 9: Time-based policy behavior
    // ========================================================================
    #[test]
    fn test_time_based_policy_behavior() {
        // Morning: Different behavior expected
        let context_morning = create_test_context_at_tick(20, 100);
        assert_eq!(context_morning.get_field("is_eod_rush").unwrap(), 0.0);
        assert!(context_morning.get_field("day_progress_fraction").unwrap() < 0.5);

        // EOD: Aggressive behavior expected
        let context_eod = create_test_context_at_tick(90, 100);
        assert_eq!(context_eod.get_field("is_eod_rush").unwrap(), 1.0);
        assert!(context_eod.get_field("day_progress_fraction").unwrap() > 0.8);
    }

    // ========================================================================
    // TEST 10: System config determinism
    // ========================================================================
    #[test]
    fn test_system_config_determinism() {
        // Same inputs should produce same system fields
        let context1 = create_test_context_at_tick(50, 100);
        let context2 = create_test_context_at_tick(50, 100);

        assert_eq!(
            context1.get_field("system_ticks_per_day").unwrap(),
            context2.get_field("system_ticks_per_day").unwrap()
        );
        assert_eq!(
            context1.get_field("system_current_day").unwrap(),
            context2.get_field("system_current_day").unwrap()
        );
        assert_eq!(
            context1.get_field("day_progress_fraction").unwrap(),
            context2.get_field("day_progress_fraction").unwrap()
        );
    }

    // ========================================================================
    // TEST 11: Multi-day simulation context
    // ========================================================================
    #[test]
    fn test_multi_day_simulation_context() {
        // Day 0
        let context_day0_start = create_test_context_at_tick(0, 100);
        assert_eq!(
            context_day0_start.get_field("system_current_day").unwrap(),
            0.0
        );
        assert_eq!(
            context_day0_start.get_field("system_tick_in_day").unwrap(),
            0.0
        );

        let context_day0_end = create_test_context_at_tick(99, 100);
        assert_eq!(
            context_day0_end.get_field("system_current_day").unwrap(),
            0.0
        );
        assert_eq!(
            context_day0_end.get_field("system_tick_in_day").unwrap(),
            99.0
        );

        // Day 1
        let context_day1_start = create_test_context_at_tick(100, 100);
        assert_eq!(
            context_day1_start.get_field("system_current_day").unwrap(),
            1.0
        );
        assert_eq!(
            context_day1_start.get_field("system_tick_in_day").unwrap(),
            0.0
        );

        // Day 3, mid-day
        let context_day3_mid = create_test_context_at_tick(350, 100);
        assert_eq!(
            context_day3_mid.get_field("system_current_day").unwrap(),
            3.0
        );
        assert_eq!(
            context_day3_mid.get_field("system_tick_in_day").unwrap(),
            50.0
        );
    }

    // ========================================================================
    // TEST 12: System fields validation
    // ========================================================================
    #[test]
    fn test_system_fields_validation() {
        let context = create_test_context_at_tick(80, 100);

        // All system fields should be in the context's field list
        let field_names = context.field_names();
        assert!(field_names.contains(&"system_ticks_per_day"));
        assert!(field_names.contains(&"system_current_day"));
        assert!(field_names.contains(&"system_tick_in_day"));
        assert!(field_names.contains(&"ticks_remaining_in_day"));
        assert!(field_names.contains(&"day_progress_fraction"));
        assert!(field_names.contains(&"is_eod_rush"));
    }
}
