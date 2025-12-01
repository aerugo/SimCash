// Test for EOD penalty bug fix
//
// EOD penalties should ONLY apply to transactions that are overdue at end of day,
// not all unsettled transactions.

use crate::orchestrator::engine::{AgentConfig, CostRates, Orchestrator, OrchestratorConfig, PolicyConfig, Queue1Ordering};
use crate::settlement::lsm::LsmConfig;

#[test]
fn test_eod_penalty_only_applies_to_overdue_transactions() {
    // Setup: 2-agent system with transactions that will be in queue at EOD
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 2,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "SENDER".to_string(),
                opening_balance: 0, // No liquidity - transactions must queue
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "RECEIVER".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates {
            eod_penalty_per_transaction: 5_000_00, // $5,000
            deadline_penalty: 2_500_00,            // $2,500
            ..Default::default()
        },
        lsm_config: LsmConfig::default(),
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    };

    let mut engine = Orchestrator::new(config).unwrap();

    // Get cost accumulator before submitting transactions
    let sender_costs_before = engine.get_costs("SENDER").unwrap();
    let penalty_cost_before = sender_costs_before.total_penalty_cost;

    // Tick 0: Submit 3 transactions with different deadlines
    // Transaction 1: Deadline tick 50 (will be overdue at EOD tick 99)
    engine.submit_transaction(
        "SENDER",
        "RECEIVER",
        100_000, // $1,000
        50,      // deadline tick 50 (overdue at tick 99)
        5,       // priority
        false,   // not divisible
    ).unwrap();

    // Transaction 2: Deadline tick 120 (NOT overdue at EOD tick 99)
    engine.submit_transaction(
        "SENDER",
        "RECEIVER",
        100_000,
        120, // deadline tick 120 (still valid at tick 99)
        5,   // priority
        false,
    ).unwrap();

    // Transaction 3: Deadline tick 150 (NOT overdue at EOD tick 99)
    engine.submit_transaction(
        "SENDER",
        "RECEIVER",
        100_000,
        150, // deadline tick 150 (still valid at tick 99)
        5,   // priority
        false,
    ).unwrap();

    // Advance through day 0 to trigger EOD at tick 99
    // Need to call tick() 100 times to process ticks 0-99
    for _ in 0..100 {
        let _ = engine.tick();
    }

    // At tick 99 (EOD):
    // - tx1 is overdue (deadline 50 < 99) -> should incur EOD penalty
    // - tx2 is NOT overdue (deadline 120 > 99) -> should NOT incur EOD penalty
    // - tx3 is NOT overdue (deadline 150 > 99) -> should NOT incur EOD penalty

    // Check accumulated penalty costs
    let sender_costs_after = engine.get_costs("SENDER").unwrap();
    let total_penalty_incurred = sender_costs_after.total_penalty_cost - penalty_cost_before;

    // Expected: Only 1 transaction (tx1) should incur penalties:
    // 1. Deadline penalty when tx1 went overdue at tick 50: $2,500
    // 2. EOD penalty at tick 99 for tx1 being overdue: $5,000
    // tx2 and tx3 should NOT incur EOD penalty (they're not overdue at tick 99)
    let expected_deadline_penalty = 1 * 2_500_00; // tx1 went overdue at tick 50
    let expected_eod_penalty = 1 * 5_000_00; // Only tx1 is overdue at EOD
    let expected_total_penalty = expected_deadline_penalty + expected_eod_penalty;

    assert_eq!(
        total_penalty_incurred, expected_total_penalty,
        "Expected deadline penalty ($2,500 when tx1 went overdue at tick 50) + EOD penalty ($5,000 for 1 overdue tx at tick 99). \
         At tick 99: tx1 (deadline 50) is overdue, tx2 (deadline 120) and tx3 (deadline 150) are not."
    );
}

#[test]
fn test_eod_penalty_applies_to_all_overdue_transactions() {
    // Test that ALL overdue transactions get the EOD penalty
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "SENDER".to_string(),
                opening_balance: 0, // No liquidity - transactions must queue
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "RECEIVER".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates {
            eod_penalty_per_transaction: 5_000_00,
            deadline_penalty: 2_500_00,
            ..Default::default()
        },
        lsm_config: LsmConfig::default(),
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    };

    let mut engine = Orchestrator::new(config).unwrap();

    // Submit 5 transactions, all with deadline before EOD
    for i in 0..5 {
        engine.submit_transaction(
            "SENDER",
            "RECEIVER",
            100_000,
            30 + (i as usize) * 5, // deadlines: 30, 35, 40, 45, 50 (all before tick 99)
            5,     // priority
            false, // not divisible
        ).unwrap();
    }

    // Advance through day 0 to trigger EOD at tick 99
    // Need to call tick() 100 times to process ticks 0-99
    for _ in 0..100 {
        let _ = engine.tick();
    }

    // All 5 transactions are overdue, so all should incur penalties:
    // - 5 deadline penalties (when each went overdue at ticks 30, 35, 40, 45, 50): 5 * $2,500
    // - 5 EOD penalties (all overdue at tick 99): 5 * $5,000
    let sender_costs = engine.get_costs("SENDER").unwrap();
    let expected_deadline_penalties = 5 * 2_500_00; // All went overdue before EOD
    let expected_eod_penalties = 5 * 5_000_00;      // All overdue at EOD
    let expected_total = expected_deadline_penalties + expected_eod_penalties;

    assert_eq!(
        sender_costs.total_penalty_cost, expected_total,
        "All 5 overdue transactions should incur both deadline penalties and EOD penalties"
    );
}

#[test]
fn test_no_eod_penalty_when_all_transactions_settle_before_deadline() {
    // Verify no EOD penalty when all transactions settle on time
    let config = OrchestratorConfig {
        ticks_per_day: 100,
        eod_rush_threshold: 0.8,
        num_days: 1,
        rng_seed: 42,
        agent_configs: vec![
            AgentConfig {
                id: "SENDER".to_string(),
                opening_balance: 10_000_000, // Enough to settle immediately
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
            AgentConfig {
                id: "RECEIVER".to_string(),
                opening_balance: 0,
                unsecured_cap: 0,
                policy: PolicyConfig::Fifo,
                arrival_config: None,
                arrival_bands: None,
                posted_collateral: None,
                collateral_haircut: None,
                max_collateral_capacity: None,
                limits: None,
                liquidity_pool: None,
                liquidity_allocation_fraction: None,
            },
        ],
        cost_rates: CostRates {
            eod_penalty_per_transaction: 5_000_00,
            deadline_penalty: 2_500_00,
            ..Default::default()
        },
        lsm_config: LsmConfig::default(),
        scenario_events: None,
        queue1_ordering: Queue1Ordering::default(),
        priority_mode: false,
        priority_escalation: Default::default(),
            algorithm_sequencing: false,
            entry_disposition_offsetting: false,
    };

    let mut engine = Orchestrator::new(config).unwrap();

    // Submit transaction that will settle immediately
    engine.submit_transaction(
        "SENDER",
        "RECEIVER",
        100_000,
        50,    // deadline
        5,     // priority
        false, // not divisible
    ).unwrap();

    // Advance through day 0 to trigger EOD at tick 99
    // Need to call tick() 100 times to process ticks 0-99
    for _ in 0..100 {
        let _ = engine.tick();
    }

    // No transactions in queue at EOD, so no EOD penalty
    let sender_costs = engine.get_costs("SENDER").unwrap();
    assert_eq!(
        sender_costs.total_penalty_cost, 0,
        "No EOD penalty when transaction settles before EOD"
    );
}
