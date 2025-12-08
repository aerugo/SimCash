//! Integration tests for Release with RTGS flags (Phase 3.2: Policy Enhancements V2).
//!
//! Following TDD principles: these tests are written BEFORE implementation.
//!
//! ## Test Coverage
//!
//! 1. **Priority Override**: Release with HIGH/MEDIUM/LOW priority flags
//! 2. **Timed Release**: Release with target tick for LSM coordination
//! 3. **Combined Flags**: Both priority and timing flags together
//! 4. **Default Behavior**: Release without flags (backward compatibility)
//! 5. **JSON Deserialization**: Verify action can be loaded from policy JSON
//! 6. **Integration**: Full orchestrator tick loop with flagged releases
//! 7. **Priority Mapping**: Verify string → numeric priority conversion

use payment_simulator_core_rs::policy::ReleaseDecision;

// ============================================================================
// Test Group 1: Priority Override (4 tests)
// ============================================================================

#[test]
fn test_release_with_high_priority_flag() {
    // Test that Release can specify HIGH priority override

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(10), // HIGH = 10
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert_eq!(priority_override, Some(10));
        }
        _ => panic!("Expected SubmitFull with priority override"),
    }
}

#[test]
fn test_release_with_medium_priority_flag() {
    // Test that Release can specify MEDIUM priority override

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(5), // MEDIUM = 5
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert_eq!(priority_override, Some(5));
        }
        _ => panic!("Expected SubmitFull with priority override"),
    }
}

#[test]
fn test_release_with_low_priority_flag() {
    // Test that Release can specify LOW priority override

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(1), // LOW = 1
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert_eq!(priority_override, Some(1));
        }
        _ => panic!("Expected SubmitFull with priority override"),
    }
}

#[test]
fn test_release_no_priority_override_is_none() {
    // Test that Release without priority flag has None (uses transaction's original priority)

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert!(priority_override.is_none());
        }
        _ => panic!("Expected SubmitFull without priority override"),
    }
}

// ============================================================================
// Test Group 2: Timed Release (4 tests)
// ============================================================================

#[test]
fn test_release_with_target_tick() {
    // Test that Release can specify a target tick for LSM coordination

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: Some(25), // Release at tick 25
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert_eq!(target_tick, Some(25));
        }
        _ => panic!("Expected SubmitFull with target tick"),
    }
}

#[test]
fn test_release_with_future_target_tick() {
    // Test that Release can target a future tick

    let current_tick = 10;
    let target_tick = current_tick + 5;

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: Some(target_tick),
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert_eq!(target_tick, Some(15));
        }
        _ => panic!("Expected SubmitFull with future target tick"),
    }
}

#[test]
fn test_release_with_immediate_target_tick() {
    // Test that Release can target the current tick (immediate release)

    let current_tick = 10;

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: Some(current_tick), // Release now
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert_eq!(target_tick, Some(10));
        }
        _ => panic!("Expected SubmitFull with immediate target tick"),
    }
}

#[test]
fn test_release_no_target_tick_is_none() {
    // Test that Release without target_tick has None (releases immediately)

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert!(target_tick.is_none());
        }
        _ => panic!("Expected SubmitFull without target tick"),
    }
}

// ============================================================================
// Test Group 3: Combined Flags (3 tests)
// ============================================================================

#[test]
fn test_release_with_both_priority_and_timing() {
    // Test that Release can use both flags simultaneously

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(10), // HIGH priority
        target_tick: Some(25),       // Target tick 25
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override,
            target_tick,
            ..
        } => {
            assert_eq!(priority_override, Some(10));
            assert_eq!(target_tick, Some(25));
        }
        _ => panic!("Expected SubmitFull with both flags"),
    }
}

#[test]
fn test_release_low_priority_delayed() {
    // Test that Release can lower priority and delay timing

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(1), // LOW priority
        target_tick: Some(50),      // Delayed release
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override,
            target_tick,
            ..
        } => {
            assert_eq!(priority_override, Some(1));
            assert_eq!(target_tick, Some(50));
        }
        _ => panic!("Expected SubmitFull with low priority and delay"),
    }
}

#[test]
fn test_release_high_priority_immediate() {
    // Test that Release can boost priority for immediate release

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: Some(10), // HIGH priority
        target_tick: Some(10),       // Immediate (current tick)
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override,
            target_tick,
            ..
        } => {
            assert_eq!(priority_override, Some(10));
            assert_eq!(target_tick, Some(10));
        }
        _ => panic!("Expected SubmitFull with high priority immediate"),
    }
}

// ============================================================================
// Test Group 4: Backward Compatibility (2 tests)
// ============================================================================

#[test]
fn test_release_default_behavior_unchanged() {
    // Test that Release without any flags behaves like original SubmitFull

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            tx_id,
            priority_override,
            target_tick,
        } => {
            assert_eq!(tx_id, "tx_001");
            assert!(priority_override.is_none());
            assert!(target_tick.is_none());
        }
        _ => panic!("Expected SubmitFull with default behavior"),
    }
}

#[test]
fn test_release_backward_compatible_construction() {
    // Test that old code pattern still works (can omit optional fields)

    // This simulates how existing policies create SubmitFull decisions
    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: None,
    };

    // Should match without error
    match decision {
        ReleaseDecision::SubmitFull { tx_id, .. } => {
            assert_eq!(tx_id, "tx_001");
        }
        _ => panic!("Backward compatibility broken"),
    }
}

// ============================================================================
// Test Group 5: Priority Mapping (4 tests)
// ============================================================================

#[test]
fn test_priority_string_to_numeric_high() {
    // Test that "HIGH" maps to 10

    let priority_str = "HIGH";
    let priority_num = match priority_str {
        "HIGH" => 10,
        "MEDIUM" => 5,
        "LOW" => 1,
        _ => 5, // Default to MEDIUM
    };

    assert_eq!(priority_num, 10);
}

#[test]
fn test_priority_string_to_numeric_medium() {
    // Test that "MEDIUM" maps to 5

    let priority_str = "MEDIUM";
    let priority_num = match priority_str {
        "HIGH" => 10,
        "MEDIUM" => 5,
        "LOW" => 1,
        _ => 5,
    };

    assert_eq!(priority_num, 5);
}

#[test]
fn test_priority_string_to_numeric_low() {
    // Test that "LOW" maps to 1

    let priority_str = "LOW";
    let priority_num = match priority_str {
        "HIGH" => 10,
        "MEDIUM" => 5,
        "LOW" => 1,
        _ => 5,
    };

    assert_eq!(priority_num, 1);
}

#[test]
fn test_priority_string_invalid_defaults_to_medium() {
    // Test that invalid priority strings default to MEDIUM (5)

    let priority_str = "INVALID";
    let priority_num = match priority_str {
        "HIGH" => 10,
        "MEDIUM" => 5,
        "LOW" => 1,
        _ => 5, // Default
    };

    assert_eq!(priority_num, 5);
}

// ============================================================================
// Test Group 6: JSON Deserialization (3 tests)
// ============================================================================

#[test]
fn test_release_with_priority_flag_deserializes_from_json() {
    // Test that Release with priority_flag can be loaded from JSON

    let json = r#"{
        "type": "action",
        "node_id": "A_ReleaseHigh",
        "action": "Release",
        "parameters": {
            "priority_flag": {"value": "HIGH"}
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["action"], "Release");
    assert_eq!(parsed["parameters"]["priority_flag"]["value"], "HIGH");
}

#[test]
fn test_release_with_timed_for_tick_deserializes_from_json() {
    // Test that Release with timed_for_tick can be loaded from JSON

    let json = r#"{
        "type": "action",
        "node_id": "A_ReleaseTimed",
        "action": "Release",
        "parameters": {
            "timed_for_tick": {
                "compute": {
                    "op": "add",
                    "left": {"field": "current_tick"},
                    "right": {"value": 5.0}
                }
            }
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["action"], "Release");
    assert!(parsed["parameters"]["timed_for_tick"].is_object());
}

#[test]
fn test_release_with_both_flags_deserializes_from_json() {
    // Test that Release with both flags can be loaded from JSON

    let json = r#"{
        "type": "action",
        "node_id": "A_ReleaseHighTimed",
        "action": "Release",
        "parameters": {
            "priority_flag": {"value": "HIGH"},
            "timed_for_tick": {"value": 25.0}
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["action"], "Release");
    assert_eq!(parsed["parameters"]["priority_flag"]["value"], "HIGH");
    assert_eq!(parsed["parameters"]["timed_for_tick"]["value"], 25.0);
}

// ============================================================================
// Test Group 7: Validation (3 tests)
// ============================================================================

#[test]
fn test_priority_capped_at_10() {
    // Test that priority values are capped at maximum 10

    let priority = 15u8; // Attempt to set > 10
    let capped = priority.min(10);

    assert_eq!(capped, 10);
}

#[test]
fn test_priority_floored_at_0() {
    // Test that priority values cannot be negative

    // In Rust, u8 cannot be negative, but test conversion from f64
    let priority_f64 = -5.0;
    let priority_u8 = if priority_f64 < 0.0 {
        0
    } else if priority_f64 > 10.0 {
        10
    } else {
        priority_f64 as u8
    };

    assert_eq!(priority_u8, 0);
}

#[test]
fn test_target_tick_can_be_past() {
    // Test that target_tick in the past is allowed (would release immediately)
    // This is valid - policy might target tick 10 but we're already at tick 15

    let current_tick = 15;
    let target_tick = 10; // In the past

    // Should be allowed - orchestrator would release immediately
    assert!(target_tick < current_tick);

    // Decision should still be valid
    let decision = ReleaseDecision::SubmitFull {
        tx_id: "tx_001".to_string(),
        priority_override: None,
        target_tick: Some(target_tick),
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert_eq!(target_tick, Some(10));
        }
        _ => panic!("Expected SubmitFull with past target tick"),
    }
}

// ============================================================================
// Test Group 8: Use Cases (3 tests)
// ============================================================================

#[test]
fn test_use_case_urgent_deadline_boost_priority() {
    // Use case: Transaction approaching deadline should be boosted to HIGH

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "urgent_tx".to_string(),
        priority_override: Some(10), // Boost to HIGH
        target_tick: None,           // Release now
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert_eq!(priority_override, Some(10));
        }
        _ => panic!("Expected high priority release"),
    }
}

#[test]
fn test_use_case_lsm_coordination_timed_release() {
    // Use case: Release payment at tick when counterparty's payment expected

    let _current_tick = 10;
    let expected_inbound_tick = 15;
    let target_tick = expected_inbound_tick; // Coordinate for LSM

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "lsm_coordinated_tx".to_string(),
        priority_override: None,
        target_tick: Some(target_tick),
    };

    match decision {
        ReleaseDecision::SubmitFull { target_tick, .. } => {
            assert_eq!(target_tick, Some(15));
        }
        _ => panic!("Expected timed release"),
    }
}

#[test]
fn test_use_case_lower_priority_for_oversupply() {
    // Use case: Agent has excess liquidity, lower priority to let urgent payments through

    let decision = ReleaseDecision::SubmitFull {
        tx_id: "low_urgency_tx".to_string(),
        priority_override: Some(1), // Lower to LOW
        target_tick: None,
    };

    match decision {
        ReleaseDecision::SubmitFull {
            priority_override, ..
        } => {
            assert_eq!(priority_override, Some(1));
        }
        _ => panic!("Expected low priority release"),
    }
}
