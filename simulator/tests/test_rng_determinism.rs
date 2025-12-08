//! Tests for deterministic RNG
//!
//! CRITICAL: Determinism is sacred. Same seed MUST produce same sequence.

use payment_simulator_core_rs::RngManager;

#[test]
fn test_rng_new_with_seed() {
    let rng = RngManager::new(12345);
    assert_eq!(rng.get_state(), 12345);
}

#[test]
fn test_rng_next_deterministic() {
    let mut rng1 = RngManager::new(12345);
    let mut rng2 = RngManager::new(12345);

    // Same seed should produce same sequence
    for _ in 0..100 {
        let val1 = rng1.next();
        let val2 = rng2.next();
        assert_eq!(val1, val2, "RNG not deterministic!");
    }
}

#[test]
fn test_rng_different_seeds_different_sequences() {
    let mut rng1 = RngManager::new(12345);
    let mut rng2 = RngManager::new(54321);

    let val1 = rng1.next();
    let val2 = rng2.next();

    assert_ne!(
        val1, val2,
        "Different seeds should produce different values"
    );
}

#[test]
fn test_rng_range() {
    let mut rng = RngManager::new(12345);

    // Generate 100 values in range [0, 100)
    for _ in 0..100 {
        let val = rng.range(0, 100);
        assert!(val >= 0 && val < 100, "Value {} out of range [0, 100)", val);
    }
}

#[test]
fn test_rng_range_single_value() {
    let mut rng = RngManager::new(12345);

    // Range [5, 6) should always return 5
    let val = rng.range(5, 6);
    assert_eq!(val, 5);
}

#[test]
fn test_rng_range_deterministic() {
    let mut rng1 = RngManager::new(99999);
    let mut rng2 = RngManager::new(99999);

    for _ in 0..50 {
        let val1 = rng1.range(10, 1000);
        let val2 = rng2.range(10, 1000);
        assert_eq!(val1, val2, "range() not deterministic!");
    }
}

#[test]
fn test_rng_state_advances() {
    let mut rng = RngManager::new(12345);
    let initial_state = rng.get_state();

    rng.next();
    let new_state = rng.get_state();

    assert_ne!(initial_state, new_state, "RNG state should advance");
}

#[test]
fn test_rng_replay_from_state() {
    let mut rng1 = RngManager::new(12345);

    // Generate some values
    for _ in 0..10 {
        rng1.next();
    }

    let checkpoint_state = rng1.get_state();

    // Generate more values from rng1
    let val1_a = rng1.next();
    let val1_b = rng1.next();

    // Create new RNG from checkpoint
    let mut rng2 = RngManager::new(checkpoint_state);

    let val2_a = rng2.next();
    let val2_b = rng2.next();

    // Should produce same values from checkpoint
    assert_eq!(val1_a, val2_a);
    assert_eq!(val1_b, val2_b);
}

#[test]
fn test_rng_long_sequence_determinism() {
    let mut rng1 = RngManager::new(42);
    let mut rng2 = RngManager::new(42);

    // Test determinism over a long sequence
    for i in 0..1000 {
        let val1 = rng1.next();
        let val2 = rng2.next();
        assert_eq!(
            val1, val2,
            "Determinism broken at iteration {}: {} != {}",
            i, val1, val2
        );
    }
}

#[test]
fn test_rng_produces_diverse_values() {
    let mut rng = RngManager::new(12345);
    let mut values = Vec::new();

    for _ in 0..100 {
        values.push(rng.next());
    }

    // Check that we got diverse values (not all the same)
    let unique_count = values
        .iter()
        .collect::<std::collections::HashSet<_>>()
        .len();
    assert!(
        unique_count > 90,
        "RNG not diverse enough: only {} unique values out of 100",
        unique_count
    );
}
