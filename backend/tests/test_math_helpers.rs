//! Math Helper Functions Tests - Phase 2.3
//!
//! Tests for new computation operators that enable advanced policy logic.
//!
//! **Purpose**: Add mathematical operations commonly needed in policy decisions
//! (rounding, clamping, safe division, absolute values).
//!
//! **Use Cases**:
//! - Ceil/Floor/Round: Discretization (e.g., "round amount to nearest 1000")
//! - Clamp: Bounds enforcement (e.g., "priority between 1 and 10")
//! - SafeDiv: Avoid runtime errors (e.g., "throughput / total_due with default 0")
//! - Abs: Distance calculations (e.g., "absolute gap from target")

use payment_simulator_core_rs::policy::tree::{EvalContext, Computation, Value};
use payment_simulator_core_rs::{Agent, SimulationState, Transaction};
use payment_simulator_core_rs::orchestrator::CostRates;

/// Helper to create agent
fn create_agent(id: &str, balance: i64, unsecured_cap: i64) -> Agent {
    let mut agent = Agent::new(id.to_string(), balance);
    agent.set_unsecured_cap(unsecured_cap);
    agent
}

/// Helper to create transaction
fn create_tx(sender: &str, receiver: &str, amount: i64) -> Transaction {
    Transaction::new(
        sender.to_string(),
        receiver.to_string(),
        amount,
        0,   // arrival
        100, // deadline
    )
}

/// Helper to create evaluation context
fn create_context() -> (EvalContext, std::collections::HashMap<String, f64>) {
    let state = SimulationState::new(vec![
        create_agent("BANK_A", 1_000_000, 500_000),
        create_agent("BANK_B", 1_000_000, 0),
    ]);

    let tx = create_tx("BANK_A", "BANK_B", 75_500);
    let agent = state.get_agent("BANK_A").unwrap().clone();
    let cost_rates = CostRates::default();
    let context = EvalContext::build(&tx, &agent, &state, 10, &cost_rates, 100, 0.8);

    let mut params = std::collections::HashMap::new();
    params.insert("test_param".to_string(), 42.7);

    (context, params)
}

/// Helper to evaluate a computation
fn eval_compute(
    compute: Computation,
    context: &EvalContext,
    params: &std::collections::HashMap<String, f64>,
) -> Result<f64, Box<dyn std::error::Error>> {
    use payment_simulator_core_rs::policy::tree::interpreter;
    Ok(interpreter::evaluate_computation(&compute, context, params)?)
}

// ============================================================================
// Test Group 1: Ceil (Ceiling) - Round Up
// ============================================================================

#[test]
fn test_ceil_positive_value() {
    let (context, params) = create_context();

    // Ceil of 42.3 should be 43.0
    let compute = Computation::Ceil {
        value: Value::Literal {
            value: serde_json::json!(42.3),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 43.0);
}

#[test]
fn test_ceil_negative_value() {
    let (context, params) = create_context();

    // Ceil of -42.7 should be -42.0 (rounds toward positive infinity)
    let compute = Computation::Ceil {
        value: Value::Literal {
            value: serde_json::json!(-42.7),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, -42.0);
}

#[test]
fn test_ceil_already_integer() {
    let (context, params) = create_context();

    // Ceil of 42.0 should be 42.0 (no change)
    let compute = Computation::Ceil {
        value: Value::Literal {
            value: serde_json::json!(42.0),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

#[test]
fn test_ceil_with_field() {
    let (context, params) = create_context();

    // amount = 75_500, ceil(75500 / 1000) = 76
    let compute = Computation::Ceil {
        value: Value::Compute {
            compute: Box::new(Computation::Divide {
                left: Value::Field { field: "amount".to_string() },
                right: Value::Literal { value: serde_json::json!(1000) },
            }),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 76.0);
}

// ============================================================================
// Test Group 2: Floor - Round Down
// ============================================================================

#[test]
fn test_floor_positive_value() {
    let (context, params) = create_context();

    // Floor of 42.7 should be 42.0
    let compute = Computation::Floor {
        value: Value::Literal {
            value: serde_json::json!(42.7),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

#[test]
fn test_floor_negative_value() {
    let (context, params) = create_context();

    // Floor of -42.3 should be -43.0 (rounds toward negative infinity)
    let compute = Computation::Floor {
        value: Value::Literal {
            value: serde_json::json!(-42.3),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, -43.0);
}

#[test]
fn test_floor_already_integer() {
    let (context, params) = create_context();

    // Floor of 42.0 should be 42.0 (no change)
    let compute = Computation::Floor {
        value: Value::Literal {
            value: serde_json::json!(42.0),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

// ============================================================================
// Test Group 3: Round - Round to Nearest Integer
// ============================================================================

#[test]
fn test_round_up() {
    let (context, params) = create_context();

    // Round of 42.6 should be 43.0 (rounds up)
    let compute = Computation::Round {
        value: Value::Literal {
            value: serde_json::json!(42.6),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 43.0);
}

#[test]
fn test_round_down() {
    let (context, params) = create_context();

    // Round of 42.4 should be 42.0 (rounds down)
    let compute = Computation::Round {
        value: Value::Literal {
            value: serde_json::json!(42.4),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

#[test]
fn test_round_half() {
    let (context, params) = create_context();

    // Round of 42.5 should be 42.0 or 43.0 (depends on rounding mode)
    // Rust uses "round half to even" (banker's rounding)
    let compute = Computation::Round {
        value: Value::Literal {
            value: serde_json::json!(42.5),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Rust's round() uses "round half away from zero", so 42.5 → 43.0
    assert_eq!(result, 43.0);
}

#[test]
fn test_round_negative() {
    let (context, params) = create_context();

    // Round of -42.6 should be -43.0
    let compute = Computation::Round {
        value: Value::Literal {
            value: serde_json::json!(-42.6),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, -43.0);
}

// ============================================================================
// Test Group 4: Abs - Absolute Value
// ============================================================================

#[test]
fn test_abs_positive() {
    let (context, params) = create_context();

    // Abs of 42.0 should be 42.0
    let compute = Computation::Abs {
        value: Value::Literal {
            value: serde_json::json!(42.0),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

#[test]
fn test_abs_negative() {
    let (context, params) = create_context();

    // Abs of -42.0 should be 42.0
    let compute = Computation::Abs {
        value: Value::Literal {
            value: serde_json::json!(-42.0),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 42.0);
}

#[test]
fn test_abs_zero() {
    let (context, params) = create_context();

    // Abs of 0.0 should be 0.0
    let compute = Computation::Abs {
        value: Value::Literal {
            value: serde_json::json!(0.0),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 0.0);
}

#[test]
fn test_abs_with_computation() {
    let (context, params) = create_context();

    // throughput_gap field (can be negative or positive)
    // Abs of throughput_gap
    let compute = Computation::Abs {
        value: Value::Field {
            field: "throughput_gap".to_string(),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Should be non-negative
    assert!(result >= 0.0);
}

// ============================================================================
// Test Group 5: Clamp - Constrain Value to Range
// ============================================================================

#[test]
fn test_clamp_within_range() {
    let (context, params) = create_context();

    // Clamp 50 to range [0, 100] should be 50 (unchanged)
    let compute = Computation::Clamp {
        value: Value::Literal { value: serde_json::json!(50.0) },
        min: Value::Literal { value: serde_json::json!(0.0) },
        max: Value::Literal { value: serde_json::json!(100.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 50.0);
}

#[test]
fn test_clamp_below_minimum() {
    let (context, params) = create_context();

    // Clamp -10 to range [0, 100] should be 0 (clamped to min)
    let compute = Computation::Clamp {
        value: Value::Literal { value: serde_json::json!(-10.0) },
        min: Value::Literal { value: serde_json::json!(0.0) },
        max: Value::Literal { value: serde_json::json!(100.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 0.0);
}

#[test]
fn test_clamp_above_maximum() {
    let (context, params) = create_context();

    // Clamp 150 to range [0, 100] should be 100 (clamped to max)
    let compute = Computation::Clamp {
        value: Value::Literal { value: serde_json::json!(150.0) },
        min: Value::Literal { value: serde_json::json!(0.0) },
        max: Value::Literal { value: serde_json::json!(100.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 100.0);
}

#[test]
fn test_clamp_with_fields() {
    let (context, params) = create_context();

    // Clamp priority (field) to range [1, 10]
    let compute = Computation::Clamp {
        value: Value::Field { field: "priority".to_string() },
        min: Value::Literal { value: serde_json::json!(1.0) },
        max: Value::Literal { value: serde_json::json!(10.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Priority should be clamped to [1, 10]
    assert!(result >= 1.0 && result <= 10.0);
}

// ============================================================================
// Test Group 6: SafeDiv - Division with Default Value
// ============================================================================

#[test]
fn test_safediv_normal_division() {
    let (context, params) = create_context();

    // SafeDiv 100 / 4 with default 0 should be 25.0
    let compute = Computation::SafeDiv {
        numerator: Value::Literal { value: serde_json::json!(100.0) },
        denominator: Value::Literal { value: serde_json::json!(4.0) },
        default: Value::Literal { value: serde_json::json!(0.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 25.0);
}

#[test]
fn test_safediv_divide_by_zero_returns_default() {
    let (context, params) = create_context();

    // SafeDiv 100 / 0 with default 999 should be 999 (default)
    let compute = Computation::SafeDiv {
        numerator: Value::Literal { value: serde_json::json!(100.0) },
        denominator: Value::Literal { value: serde_json::json!(0.0) },
        default: Value::Literal { value: serde_json::json!(999.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 999.0);
}

#[test]
fn test_safediv_divide_by_near_zero_returns_default() {
    let (context, params) = create_context();

    // SafeDiv 100 / 1e-10 with default -1 should use default (denominator too small)
    let compute = Computation::SafeDiv {
        numerator: Value::Literal { value: serde_json::json!(100.0) },
        denominator: Value::Literal { value: serde_json::json!(1e-10) },
        default: Value::Literal { value: serde_json::json!(-1.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Should return default because denominator < epsilon (1e-9)
    assert_eq!(result, -1.0);
}

#[test]
fn test_safediv_with_field_computation() {
    let (context, params) = create_context();

    // SafeDiv settled_amount / amount with default 0.0
    // This is throughput fraction calculation
    let compute = Computation::SafeDiv {
        numerator: Value::Field { field: "settled_amount".to_string() },
        denominator: Value::Field { field: "amount".to_string() },
        default: Value::Literal { value: serde_json::json!(0.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Should be valid (0.0 to 1.0) or default
    assert!(result >= 0.0 && result <= 1.0);
}

// ============================================================================
// Test Group 7: Integration Tests - Combining Multiple Math Helpers
// ============================================================================

#[test]
fn test_combined_ceil_and_clamp() {
    let (context, params) = create_context();

    // Clamp(Ceil(42.3), 40, 45) should be 43.0
    let compute = Computation::Clamp {
        value: Value::Compute {
            compute: Box::new(Computation::Ceil {
                value: Value::Literal { value: serde_json::json!(42.3) },
            }),
        },
        min: Value::Literal { value: serde_json::json!(40.0) },
        max: Value::Literal { value: serde_json::json!(45.0) },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 43.0);
}

#[test]
fn test_combined_abs_and_round() {
    let (context, params) = create_context();

    // Round(Abs(-42.6)) should be 43.0
    let compute = Computation::Round {
        value: Value::Compute {
            compute: Box::new(Computation::Abs {
                value: Value::Literal { value: serde_json::json!(-42.6) },
            }),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    assert_eq!(result, 43.0);
}

#[test]
fn test_safediv_in_complex_expression() {
    let (context, params) = create_context();

    // SafeDiv for throughput calculation with validation
    // Round(SafeDiv(settled, amount, 0) * 100) = percentage
    let compute = Computation::Round {
        value: Value::Compute {
            compute: Box::new(Computation::Multiply {
                left: Value::Compute {
                    compute: Box::new(Computation::SafeDiv {
                        numerator: Value::Field { field: "settled_amount".to_string() },
                        denominator: Value::Field { field: "amount".to_string() },
                        default: Value::Literal { value: serde_json::json!(0.0) },
                    }),
                },
                right: Value::Literal { value: serde_json::json!(100.0) },
            }),
        },
    };

    let result = eval_compute(compute, &context, &params).unwrap();
    // Should be 0 to 100 (percentage)
    assert!(result >= 0.0 && result <= 100.0);
}

// ============================================================================
// Test Group 8: JSON Deserialization Tests
// ============================================================================

#[test]
fn test_ceil_deserializes_from_json() {
    let json = r#"{"op": "ceil", "value": {"field": "amount"}}"#;
    let compute: Computation = serde_json::from_str(json).unwrap();

    match compute {
        Computation::Ceil { .. } => (),
        _ => panic!("Expected Ceil variant"),
    }
}

#[test]
fn test_clamp_deserializes_from_json() {
    let json = r#"{
        "op": "clamp",
        "value": {"field": "priority"},
        "min": {"value": 1},
        "max": {"value": 10}
    }"#;
    let compute: Computation = serde_json::from_str(json).unwrap();

    match compute {
        Computation::Clamp { .. } => (),
        _ => panic!("Expected Clamp variant"),
    }
}

#[test]
fn test_safediv_deserializes_from_json() {
    let json = r#"{
        "op": "div0",
        "numerator": {"field": "balance"},
        "denominator": {"field": "amount"},
        "default": {"value": 0}
    }"#;
    let compute: Computation = serde_json::from_str(json).unwrap();

    match compute {
        Computation::SafeDiv { .. } => (),
        _ => panic!("Expected SafeDiv variant"),
    }
}
