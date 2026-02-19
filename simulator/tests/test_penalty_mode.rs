//! Tests for PenaltyMode enum
//!
//! Phase 1 TDD: RED step — these tests define the expected behavior
//! of PenaltyMode::resolve() before implementation.

use payment_simulator_core_rs::costs::PenaltyMode;

// =============================================================================
// Fixed mode tests
// =============================================================================

#[test]
fn test_fixed_returns_exact_amount() {
    let mode = PenaltyMode::Fixed { amount: 50_000 };
    assert_eq!(mode.resolve(1_000_000), 50_000);
}

#[test]
fn test_fixed_ignores_transaction_amount() {
    let mode = PenaltyMode::Fixed { amount: 50_000 };
    assert_eq!(mode.resolve(0), 50_000);
    assert_eq!(mode.resolve(1), 50_000);
    assert_eq!(mode.resolve(999_999_999), 50_000);
    assert_eq!(mode.resolve(-500_000), 50_000);
}

#[test]
fn test_fixed_zero() {
    let mode = PenaltyMode::Fixed { amount: 0 };
    assert_eq!(mode.resolve(1_000_000), 0);
    assert_eq!(mode.resolve(0), 0);
}

// =============================================================================
// Rate mode tests
// =============================================================================

#[test]
fn test_rate_basic() {
    // 100 bps = 1%. On $10,000 (1_000_000 cents) → 10_000 cents ($100)
    let mode = PenaltyMode::Rate { bps_per_event: 100.0 };
    assert_eq!(mode.resolve(1_000_000), 10_000);
}

#[test]
fn test_rate_fractional_bps() {
    // 50 bps = 0.5%. On $10,000 (1_000_000 cents) → 5_000 cents ($50)
    let mode = PenaltyMode::Rate { bps_per_event: 50.0 };
    assert_eq!(mode.resolve(1_000_000), 5_000);
}

#[test]
fn test_rate_small_amount() {
    // 1 bps = 0.01%. On $1 (100 cents) → 0.01 cents → truncates to 0
    let mode = PenaltyMode::Rate { bps_per_event: 1.0 };
    assert_eq!(mode.resolve(100), 0);
}

#[test]
fn test_rate_small_amount_larger_bps() {
    // 100 bps = 1%. On $1 (100 cents) → 1 cent
    let mode = PenaltyMode::Rate { bps_per_event: 100.0 };
    assert_eq!(mode.resolve(100), 1);
}

#[test]
fn test_rate_large_amount_no_overflow() {
    // 50 bps on a very large amount — must not overflow
    let mode = PenaltyMode::Rate { bps_per_event: 50.0 };
    let large_amount = i64::MAX / 2; // ~4.6 × 10^18 cents
    let result = mode.resolve(large_amount);
    // Expected: large_amount * 50 / 10_000 = large_amount / 200
    let expected = large_amount / 200;
    // Allow ±1 for rounding
    assert!((result - expected).abs() <= 1, "result={result}, expected≈{expected}");
}

#[test]
fn test_rate_zero_bps() {
    let mode = PenaltyMode::Rate { bps_per_event: 0.0 };
    assert_eq!(mode.resolve(1_000_000), 0);
}

#[test]
fn test_rate_zero_amount() {
    let mode = PenaltyMode::Rate { bps_per_event: 100.0 };
    assert_eq!(mode.resolve(0), 0);
}

#[test]
fn test_rate_negative_amount_uses_absolute() {
    // Penalties are always positive, even for negative amounts
    let mode = PenaltyMode::Rate { bps_per_event: 100.0 };
    assert_eq!(mode.resolve(-1_000_000), 10_000);
}

// =============================================================================
// Safety tests (NaN, Inf, negative bps)
// =============================================================================

#[test]
fn test_rate_nan_bps_returns_zero() {
    let mode = PenaltyMode::Rate { bps_per_event: f64::NAN };
    assert_eq!(mode.resolve(1_000_000), 0);
}

#[test]
fn test_rate_inf_bps_returns_zero() {
    let mode = PenaltyMode::Rate { bps_per_event: f64::INFINITY };
    assert_eq!(mode.resolve(1_000_000), 0);
}

#[test]
fn test_rate_negative_inf_bps_returns_zero() {
    let mode = PenaltyMode::Rate { bps_per_event: f64::NEG_INFINITY };
    assert_eq!(mode.resolve(1_000_000), 0);
}

#[test]
fn test_rate_negative_bps_returns_zero() {
    // Negative bps would be a rebate — not valid for penalties
    let mode = PenaltyMode::Rate { bps_per_event: -50.0 };
    assert_eq!(mode.resolve(1_000_000), 0);
}

// =============================================================================
// Determinism test (INV-2)
// =============================================================================

#[test]
fn test_resolve_is_deterministic() {
    let mode = PenaltyMode::Rate { bps_per_event: 73.5 };
    let amount = 7_654_321;
    let first = mode.resolve(amount);
    for _ in 0..10 {
        assert_eq!(mode.resolve(amount), first, "resolve() must be deterministic");
    }
}

// =============================================================================
// Serialization tests
// =============================================================================

#[test]
fn test_fixed_serialize_deserialize() {
    let mode = PenaltyMode::Fixed { amount: 50_000 };
    let json = serde_json::to_string(&mode).unwrap();
    let restored: PenaltyMode = serde_json::from_str(&json).unwrap();
    assert_eq!(mode, restored);
}

#[test]
fn test_rate_serialize_deserialize() {
    let mode = PenaltyMode::Rate { bps_per_event: 50.0 };
    let json = serde_json::to_string(&mode).unwrap();
    let restored: PenaltyMode = serde_json::from_str(&json).unwrap();
    assert_eq!(mode, restored);
}
