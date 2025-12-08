// Tests for the three new realistic bank policies:
// 1. Goliath National Bank (GNB) - "The Fortress"
// 2. Agile Regional Bank (ARB) - "The Cost-Benefit Analyst"
// 3. Momentum Investment Bank (MIB) - "The Aggressive Trader"

use crate::policy::tree::TreePolicy;
use std::path::PathBuf;

/// Helper function to locate policies directory
fn policies_dir() -> PathBuf {
    let simulator_policies = PathBuf::from("simulator/policies");
    if simulator_policies.exists() {
        return simulator_policies;
    }
    PathBuf::from("policies")
}

#[test]
fn test_load_goliath_national_bank_policy() {
    let path = policies_dir().join("goliath_national_bank.json");
    let policy = TreePolicy::from_file(path).expect("Failed to load GNB policy");

    // Verify basic structure
    assert_eq!(policy.policy_id(), "goliath_national_bank_v2");
    assert!(policy.tree().payment_tree.is_some(), "GNB must have payment tree");
    assert!(
        policy.tree().strategic_collateral_tree.is_some(),
        "GNB must have strategic collateral tree"
    );
    assert!(
        policy.tree().end_of_tick_collateral_tree.is_some(),
        "GNB must have end-of-tick collateral tree"
    );

    // Verify key parameters
    let params = &policy.tree().parameters;
    assert_eq!(
        params.get("urgency_threshold"),
        Some(&5.0),
        "GNB urgency threshold should be 5.0"
    );
    assert_eq!(
        params.get("target_buffer"),
        Some(&50000000.0),
        "GNB target buffer should be 50M"
    );
    assert_eq!(
        params.get("early_day_buffer_multiplier"),
        Some(&1.5),
        "GNB early day buffer multiplier should be 1.5"
    );

    println!("✓ Goliath National Bank policy loaded successfully");
}

#[test]
fn test_load_agile_regional_bank_policy() {
    let path = policies_dir().join("agile_regional_bank.json");
    let policy = TreePolicy::from_file(path).expect("Failed to load ARB policy");

    // Verify basic structure
    assert_eq!(policy.policy_id(), "agile_regional_bank_v2");
    assert!(policy.tree().payment_tree.is_some(), "ARB must have payment tree");
    assert!(
        policy.tree().strategic_collateral_tree.is_some(),
        "ARB must have strategic collateral tree"
    );
    assert!(
        policy.tree().end_of_tick_collateral_tree.is_some(),
        "ARB must have end-of-tick collateral tree"
    );

    // Verify key parameters
    let params = &policy.tree().parameters;
    assert_eq!(
        params.get("urgency_threshold"),
        Some(&3.0),
        "ARB urgency threshold should be 3.0"
    );
    assert_eq!(
        params.get("split_threshold"),
        Some(&100000.0),
        "ARB split threshold should be 100k"
    );
    assert_eq!(
        params.get("max_splits"),
        Some(&8.0),
        "ARB max splits should be 8"
    );
    assert_eq!(
        params.get("safety_margin"),
        Some(&1.1),
        "ARB safety margin should be 1.1"
    );

    println!("✓ Agile Regional Bank policy loaded successfully");
}

#[test]
fn test_load_momentum_investment_bank_policy() {
    let path = policies_dir().join("momentum_investment_bank.json");
    let policy = TreePolicy::from_file(path).expect("Failed to load MIB policy");

    // Verify basic structure
    assert_eq!(policy.policy_id(), "momentum_investment_bank_v2");
    assert!(policy.tree().payment_tree.is_some(), "MIB must have payment tree");
    assert!(
        policy.tree().strategic_collateral_tree.is_some(),
        "MIB must have strategic collateral tree"
    );
    assert!(
        policy.tree().end_of_tick_collateral_tree.is_some(),
        "MIB must have end-of-tick collateral tree"
    );

    // Verify key parameters
    let params = &policy.tree().parameters;
    assert_eq!(
        params.get("trivial_priority_threshold"),
        Some(&3.0),
        "MIB trivial priority threshold should be 3.0"
    );
    assert_eq!(
        params.get("trivial_amount_threshold"),
        Some(&10000.0),
        "MIB trivial amount threshold should be 10k"
    );
    assert_eq!(
        params.get("congestion_threshold"),
        Some(&50.0),
        "MIB congestion threshold should be 50"
    );

    println!("✓ Momentum Investment Bank policy loaded successfully");
}

#[test]
fn test_all_three_policies_have_distinct_strategies() {
    // Load all three
    let gnb = TreePolicy::from_file(policies_dir().join("goliath_national_bank.json"))
        .expect("Failed to load GNB");
    let arb = TreePolicy::from_file(policies_dir().join("agile_regional_bank.json"))
        .expect("Failed to load ARB");
    let mib = TreePolicy::from_file(policies_dir().join("momentum_investment_bank.json"))
        .expect("Failed to load MIB");

    // Verify they have different policy IDs
    assert_ne!(gnb.policy_id(), arb.policy_id());
    assert_ne!(arb.policy_id(), mib.policy_id());
    assert_ne!(gnb.policy_id(), mib.policy_id());

    // Verify different urgency thresholds (shows different risk profiles)
    let gnb_urgency = gnb.tree().parameters.get("urgency_threshold").unwrap();
    let arb_urgency = arb.tree().parameters.get("urgency_threshold").unwrap();
    // MIB doesn't have urgency threshold (it releases everything)

    assert_eq!(*gnb_urgency, 5.0, "GNB is more conservative (higher threshold)");
    assert_eq!(*arb_urgency, 3.0, "ARB is more aggressive (lower threshold)");

    // Verify GNB has the highest buffer (most conservative)
    let gnb_buffer = gnb.tree().parameters.get("target_buffer").unwrap();
    assert_eq!(*gnb_buffer, 50000000.0, "GNB should have 50M buffer");

    // Verify ARB has splitting capability (others don't)
    let arb_splits = arb.tree().parameters.get("max_splits");
    assert!(arb_splits.is_some(), "ARB should support splitting");

    // Verify MIB has congestion awareness (others don't)
    let mib_congestion = mib.tree().parameters.get("congestion_threshold");
    assert!(mib_congestion.is_some(), "MIB should have congestion threshold");

    println!("✓ All three policies have distinct strategies:");
    println!("  - GNB: Conservative with large buffer (50M)");
    println!("  - ARB: Cost-optimizing with splitting (max 8 splits)");
    println!("  - MIB: Aggressive with congestion awareness (threshold 50)");
}
