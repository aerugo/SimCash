//! Tests for Phase 4.5: Stateful Micro-Memory (Simple Registers)
//!
//! State registers provide limited memory for policy decisions across ticks.
//! Design constraints:
//! - Max 10 registers per agent
//! - Keys MUST be prefixed with "bank_state_"
//! - Values are f64 only
//! - Reset at EOD (daily scope)

use payment_simulator_core_rs::Agent;

#[test]
fn test_set_state_register_basic() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    let (old, new) = agent.set_state_register("bank_state_cooldown".to_string(), 42.0).unwrap();
    assert_eq!(old, 0.0);
    assert_eq!(new, 42.0);
    assert_eq!(agent.get_state_register("bank_state_cooldown"), 42.0);
}

#[test]
fn test_state_register_default_value_is_zero() {
    let agent = Agent::new("A".to_string(), 100_000);

    // Reading non-existent register should return 0.0
    assert_eq!(agent.get_state_register("bank_state_nonexistent"), 0.0);
}

#[test]
fn test_state_register_can_update_existing() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Set initial value
    agent.set_state_register("bank_state_counter".to_string(), 10.0).unwrap();
    assert_eq!(agent.get_state_register("bank_state_counter"), 10.0);

    // Update value
    let (old, new) = agent.set_state_register("bank_state_counter".to_string(), 20.0).unwrap();
    assert_eq!(old, 10.0);
    assert_eq!(new, 20.0);
    assert_eq!(agent.get_state_register("bank_state_counter"), 20.0);
}

#[test]
fn test_state_register_max_limit() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Add 10 registers (should succeed)
    for i in 0..10 {
        agent.set_state_register(format!("bank_state_reg{}", i), i as f64).unwrap();
    }

    // Verify all 10 are stored
    for i in 0..10 {
        assert_eq!(agent.get_state_register(&format!("bank_state_reg{}", i)), i as f64);
    }

    // 11th should fail
    let result = agent.set_state_register("bank_state_reg11".to_string(), 11.0);
    assert!(result.is_err());
    let err_msg = result.unwrap_err();
    assert!(err_msg.contains("Maximum 10"), "Expected max limit error, got: {}", err_msg);
}

#[test]
fn test_state_register_max_limit_allows_updates() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Add 10 registers
    for i in 0..10 {
        agent.set_state_register(format!("bank_state_reg{}", i), i as f64).unwrap();
    }

    // Updating existing register should work (not creating new one)
    let result = agent.set_state_register("bank_state_reg5".to_string(), 99.0);
    assert!(result.is_ok(), "Should allow updating existing register even at max limit");
    assert_eq!(agent.get_state_register("bank_state_reg5"), 99.0);
}

#[test]
fn test_state_register_requires_prefix() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Without prefix should fail
    let result = agent.set_state_register("bad_key".to_string(), 42.0);
    assert!(result.is_err());
    let err_msg = result.unwrap_err();
    assert!(err_msg.contains("bank_state_"), "Expected prefix error, got: {}", err_msg);

    // With prefix should succeed
    let result = agent.set_state_register("bank_state_good_key".to_string(), 42.0);
    assert!(result.is_ok());
}

#[test]
fn test_state_register_various_invalid_prefixes() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    let invalid_keys = vec![
        "state_register",
        "bankstate_foo",
        "bank_State_foo", // Wrong capitalization
        "BANK_STATE_FOO",
        "_bank_state_foo",
        "",
        "bank",
    ];

    for key in invalid_keys {
        let result = agent.set_state_register(key.to_string(), 1.0);
        assert!(result.is_err(), "Key '{}' should be rejected", key);
    }
}

#[test]
fn test_state_register_eod_reset() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Set multiple registers
    agent.set_state_register("bank_state_cooldown".to_string(), 42.0).unwrap();
    agent.set_state_register("bank_state_counter".to_string(), 99.0).unwrap();
    agent.set_state_register("bank_state_flag".to_string(), 1.0).unwrap();

    assert_eq!(agent.get_state_register("bank_state_cooldown"), 42.0);
    assert_eq!(agent.get_state_register("bank_state_counter"), 99.0);
    assert_eq!(agent.get_state_register("bank_state_flag"), 1.0);

    // Reset all registers
    let old_values = agent.reset_state_registers();

    // Should return all old values
    assert_eq!(old_values.len(), 3);

    // Verify values are in the vec (order not guaranteed)
    let values_map: std::collections::HashMap<String, f64> = old_values.into_iter().collect();
    assert_eq!(values_map.get("bank_state_cooldown"), Some(&42.0));
    assert_eq!(values_map.get("bank_state_counter"), Some(&99.0));
    assert_eq!(values_map.get("bank_state_flag"), Some(&1.0));

    // After reset, all should return 0.0
    assert_eq!(agent.get_state_register("bank_state_cooldown"), 0.0);
    assert_eq!(agent.get_state_register("bank_state_counter"), 0.0);
    assert_eq!(agent.get_state_register("bank_state_flag"), 0.0);
}

#[test]
fn test_state_register_reset_empty() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Reset with no registers should return empty vec
    let old_values = agent.reset_state_registers();
    assert_eq!(old_values.len(), 0);
}

#[test]
fn test_state_register_negative_values_allowed() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Negative values should be allowed (useful for deltas)
    let result = agent.set_state_register("bank_state_delta".to_string(), -123.45);
    assert!(result.is_ok());
    assert_eq!(agent.get_state_register("bank_state_delta"), -123.45);
}

#[test]
fn test_state_register_zero_value_allowed() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    // Set to non-zero first
    agent.set_state_register("bank_state_flag".to_string(), 1.0).unwrap();
    assert_eq!(agent.get_state_register("bank_state_flag"), 1.0);

    // Then set to zero (should work)
    let (old, new) = agent.set_state_register("bank_state_flag".to_string(), 0.0).unwrap();
    assert_eq!(old, 1.0);
    assert_eq!(new, 0.0);
    assert_eq!(agent.get_state_register("bank_state_flag"), 0.0);
}

#[test]
fn test_state_register_floating_point_precision() {
    let mut agent = Agent::new("A".to_string(), 100_000);

    let value = 123.456789;
    agent.set_state_register("bank_state_precise".to_string(), value).unwrap();
    assert_eq!(agent.get_state_register("bank_state_precise"), value);
}
