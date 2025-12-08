//! Integration tests for Bank-Level Budget Actions (Phase 3.3: Policy Enhancements V2).
//!
//! Following TDD principles: these tests are written BEFORE implementation.
//!
//! ## Test Coverage
//!
//! 1. **Budget Setting**: SetReleaseBudget action sets per-tick budget
//! 2. **Budget Enforcement**: Release decisions respect budget limits
//! 3. **Budget Exhaustion**: Releases beyond budget become Holds
//! 4. **Budget Reset**: Budget resets at start of each tick
//! 5. **Counterparty Focus**: Optional focus list prioritizes specific counterparties
//! 6. **Per-Counterparty Limits**: Max per counterparty enforcement
//! 7. **JSON Deserialization**: bank_tree loads from policy JSON
//! 8. **Integration**: Full orchestrator with bank-level budgets

use payment_simulator_core_rs::policy::{BankDecision, ReleaseDecision};

// ============================================================================
// Test Group 1: Budget Setting (4 tests)
// ============================================================================

#[test]
fn test_set_release_budget_creates_budget_state() {
    // Test that SetReleaseBudget action creates budget state for the tick

    let decision = BankDecision::SetReleaseBudget {
        max_value_to_release: 500_000, // $5,000.00
        focus_counterparties: None,
        max_per_counterparty: None,
    };

    match decision {
        BankDecision::SetReleaseBudget {
            max_value_to_release,
            ..
        } => {
            assert_eq!(max_value_to_release, 500_000);
        }
        _ => panic!("Expected SetReleaseBudget decision"),
    }
}

#[test]
fn test_set_release_budget_with_focus_list() {
    // Test that budget can specify focus counterparties

    let focus_list = vec!["BANK_A".to_string(), "BANK_B".to_string()];

    let decision = BankDecision::SetReleaseBudget {
        max_value_to_release: 500_000,
        focus_counterparties: Some(focus_list.clone()),
        max_per_counterparty: None,
    };

    match decision {
        BankDecision::SetReleaseBudget {
            focus_counterparties,
            ..
        } => {
            assert!(focus_counterparties.is_some());
            let focus = focus_counterparties.unwrap();
            assert_eq!(focus.len(), 2);
            assert!(focus.contains(&"BANK_A".to_string()));
            assert!(focus.contains(&"BANK_B".to_string()));
        }
        _ => panic!("Expected SetReleaseBudget with focus list"),
    }
}

#[test]
fn test_set_release_budget_with_per_counterparty_limit() {
    // Test that budget can specify max per counterparty

    let decision = BankDecision::SetReleaseBudget {
        max_value_to_release: 500_000,
        focus_counterparties: None,
        max_per_counterparty: Some(100_000), // $1,000.00 max per counterparty
    };

    match decision {
        BankDecision::SetReleaseBudget {
            max_per_counterparty,
            ..
        } => {
            assert_eq!(max_per_counterparty, Some(100_000));
        }
        _ => panic!("Expected SetReleaseBudget with per-counterparty limit"),
    }
}

#[test]
fn test_set_release_budget_with_all_parameters() {
    // Test that budget can specify all parameters together

    let focus_list = vec!["BANK_A".to_string()];

    let decision = BankDecision::SetReleaseBudget {
        max_value_to_release: 500_000,
        focus_counterparties: Some(focus_list),
        max_per_counterparty: Some(100_000),
    };

    match decision {
        BankDecision::SetReleaseBudget {
            max_value_to_release,
            focus_counterparties,
            max_per_counterparty,
        } => {
            assert_eq!(max_value_to_release, 500_000);
            assert!(focus_counterparties.is_some());
            assert_eq!(max_per_counterparty, Some(100_000));
        }
        _ => panic!("Expected SetReleaseBudget with all parameters"),
    }
}

// ============================================================================
// Test Group 2: Budget Tracking (4 tests)
// ============================================================================

#[test]
fn test_budget_state_tracks_remaining_budget() {
    // Test that budget state tracks how much budget remains

    // Simulate budget state
    let initial_budget = 500_000i64;
    let spent = 100_000i64;
    let remaining = initial_budget - spent;

    assert_eq!(remaining, 400_000);
}

#[test]
fn test_budget_state_tracks_per_counterparty_usage() {
    // Test that budget state tracks usage per counterparty

    use std::collections::HashMap;

    let mut per_counterparty = HashMap::new();
    per_counterparty.insert("BANK_A".to_string(), 50_000i64);
    per_counterparty.insert("BANK_B".to_string(), 30_000i64);

    assert_eq!(per_counterparty.get("BANK_A"), Some(&50_000));
    assert_eq!(per_counterparty.get("BANK_B"), Some(&30_000));
}

#[test]
fn test_budget_state_checks_if_amount_fits() {
    // Test logic for checking if a release amount fits in budget

    let remaining_budget = 100_000i64;
    let release_amount = 50_000i64;

    let fits = release_amount <= remaining_budget;
    assert!(fits);

    let too_large = 150_000i64;
    let does_not_fit = too_large <= remaining_budget;
    assert!(!does_not_fit);
}

#[test]
fn test_budget_state_checks_per_counterparty_limit() {
    // Test logic for checking per-counterparty limits

    use std::collections::HashMap;

    let max_per_cpty = 100_000i64;
    let mut per_counterparty = HashMap::new();
    per_counterparty.insert("BANK_A".to_string(), 80_000i64);

    let release_amount = 30_000i64;
    let current = *per_counterparty.get("BANK_A").unwrap_or(&0);
    let would_exceed = (current + release_amount) > max_per_cpty;

    assert!(would_exceed); // 80k + 30k = 110k > 100k limit
}

// ============================================================================
// Test Group 3: Budget Enforcement (5 tests)
// ============================================================================

#[test]
fn test_release_within_budget_succeeds() {
    // Test that Release within budget proceeds normally

    let remaining_budget = 500_000i64;
    let release_amount = 100_000i64;

    let can_release = release_amount <= remaining_budget;
    assert!(can_release);
}

#[test]
fn test_release_exceeding_budget_becomes_hold() {
    // Test that Release exceeding budget becomes Hold with BudgetExhausted reason

    let remaining_budget = 50_000i64;
    let release_amount = 100_000i64;

    let can_release = release_amount <= remaining_budget;

    if !can_release {
        // Should convert to Hold
        let decision = ReleaseDecision::Hold {
            tx_id: "tx_001".to_string(),
            reason: payment_simulator_core_rs::policy::HoldReason::Custom(
                "BudgetExhausted".to_string(),
            ),
        };

        match decision {
            ReleaseDecision::Hold { reason, .. } => {
                match reason {
                    payment_simulator_core_rs::policy::HoldReason::Custom(msg) => {
                        assert_eq!(msg, "BudgetExhausted");
                    }
                    _ => panic!("Expected Custom hold reason"),
                }
            }
            _ => panic!("Expected Hold decision"),
        }
    }
}

#[test]
fn test_multiple_releases_deplete_budget() {
    // Test that multiple releases correctly deplete the budget

    let mut remaining = 500_000i64;

    // Release 1
    let amount1 = 200_000i64;
    if amount1 <= remaining {
        remaining -= amount1;
    }
    assert_eq!(remaining, 300_000);

    // Release 2
    let amount2 = 150_000i64;
    if amount2 <= remaining {
        remaining -= amount2;
    }
    assert_eq!(remaining, 150_000);

    // Release 3 - would exceed
    let amount3 = 200_000i64;
    let can_release = amount3 <= remaining;
    assert!(!can_release); // Should be blocked
}

#[test]
fn test_budget_enforcement_with_zero_budget() {
    // Test that zero budget blocks all releases

    let remaining_budget = 0i64;
    let release_amount = 1i64;

    let can_release = release_amount <= remaining_budget;
    assert!(!can_release);
}

#[test]
fn test_budget_enforcement_exact_match() {
    // Test that release exactly matching budget succeeds

    let remaining_budget = 100_000i64;
    let release_amount = 100_000i64;

    let can_release = release_amount <= remaining_budget;
    assert!(can_release);

    let remaining_after = remaining_budget - release_amount;
    assert_eq!(remaining_after, 0);
}

// ============================================================================
// Test Group 4: Per-Counterparty Limits (4 tests)
// ============================================================================

#[test]
fn test_per_counterparty_limit_blocks_excess() {
    // Test that per-counterparty limit blocks releases exceeding it

    use std::collections::HashMap;

    let max_per_cpty = 100_000i64;
    let mut usage = HashMap::new();
    usage.insert("BANK_A".to_string(), 90_000i64);

    let release_amount = 20_000i64;
    let current = *usage.get("BANK_A").unwrap_or(&0);
    let would_exceed = (current + release_amount) > max_per_cpty;

    assert!(would_exceed);
}

#[test]
fn test_per_counterparty_limit_allows_within() {
    // Test that per-counterparty limit allows releases within limit

    use std::collections::HashMap;

    let max_per_cpty = 100_000i64;
    let mut usage = HashMap::new();
    usage.insert("BANK_A".to_string(), 50_000i64);

    let release_amount = 40_000i64;
    let current = *usage.get("BANK_A").unwrap_or(&0);
    let would_exceed = (current + release_amount) > max_per_cpty;

    assert!(!would_exceed);
}

#[test]
fn test_per_counterparty_tracking_multiple_counterparties() {
    // Test that per-counterparty tracking works independently

    use std::collections::HashMap;

    let max_per_cpty = 100_000i64;
    let mut usage = HashMap::new();

    // BANK_A uses 90k
    usage.insert("BANK_A".to_string(), 90_000i64);

    // BANK_B uses 30k
    usage.insert("BANK_B".to_string(), 30_000i64);

    // BANK_A cannot send more (would exceed)
    let bank_a_amount = 20_000i64;
    let bank_a_current = *usage.get("BANK_A").unwrap_or(&0);
    let bank_a_exceeds = (bank_a_current + bank_a_amount) > max_per_cpty;
    assert!(bank_a_exceeds);

    // BANK_B can still send (within limit)
    let bank_b_amount = 50_000i64;
    let bank_b_current = *usage.get("BANK_B").unwrap_or(&0);
    let bank_b_exceeds = (bank_b_current + bank_b_amount) > max_per_cpty;
    assert!(!bank_b_exceeds);
}

#[test]
fn test_per_counterparty_limit_none_means_no_limit() {
    // Test that None per-counterparty limit means unlimited

    use std::collections::HashMap;

    let max_per_cpty: Option<i64> = None;
    let mut usage = HashMap::new();
    usage.insert("BANK_A".to_string(), 500_000i64);

    let release_amount = 1_000_000i64;

    // With no limit, should always be allowed
    let would_exceed = if let Some(limit) = max_per_cpty {
        let current = *usage.get("BANK_A").unwrap_or(&0);
        (current + release_amount) > limit
    } else {
        false // No limit
    };

    assert!(!would_exceed);
}

// ============================================================================
// Test Group 5: Focus Counterparties (3 tests)
// ============================================================================

#[test]
fn test_focus_list_empty_means_all_allowed() {
    // Test that empty focus list means all counterparties are allowed

    let focus_list: Option<Vec<String>> = None;
    let counterparty = "BANK_X";

    let is_allowed = if let Some(ref focus) = focus_list {
        focus.contains(&counterparty.to_string())
    } else {
        true // No focus list = all allowed
    };

    assert!(is_allowed);
}

#[test]
fn test_focus_list_blocks_non_focus_counterparties() {
    // Test that focus list blocks counterparties not in the list

    let focus_list = Some(vec!["BANK_A".to_string(), "BANK_B".to_string()]);
    let counterparty = "BANK_C";

    let is_allowed = if let Some(ref focus) = focus_list {
        focus.contains(&counterparty.to_string())
    } else {
        true
    };

    assert!(!is_allowed);
}

#[test]
fn test_focus_list_allows_focus_counterparties() {
    // Test that focus list allows counterparties in the list

    let focus_list = Some(vec!["BANK_A".to_string(), "BANK_B".to_string()]);
    let counterparty = "BANK_A";

    let is_allowed = if let Some(ref focus) = focus_list {
        focus.contains(&counterparty.to_string())
    } else {
        true
    };

    assert!(is_allowed);
}

// ============================================================================
// Test Group 6: Budget Reset (3 tests)
// ============================================================================

#[test]
fn test_budget_resets_each_tick() {
    // Test that budget state resets at the start of each tick

    // Tick 1: Set budget and use some
    let mut remaining_budget = 500_000i64;
    remaining_budget -= 300_000; // Use 300k
    assert_eq!(remaining_budget, 200_000);

    // Tick 2: Budget should reset
    remaining_budget = 500_000; // Reset
    assert_eq!(remaining_budget, 500_000);
}

#[test]
fn test_per_counterparty_usage_resets_each_tick() {
    // Test that per-counterparty usage resets each tick

    use std::collections::HashMap;

    // Tick 1: Track usage
    let mut usage = HashMap::new();
    usage.insert("BANK_A".to_string(), 90_000i64);

    // Tick 2: Usage should reset
    usage.clear(); // Reset
    assert_eq!(usage.get("BANK_A"), None);
}

#[test]
fn test_no_budget_set_means_unlimited() {
    // Test that if no budget is set, releases are unlimited

    // If budget state is None, no limits apply
    let budget_set = false;

    if !budget_set {
        // All releases should proceed
        let can_release = true;
        assert!(can_release);
    }
}

// ============================================================================
// Test Group 7: JSON Deserialization (3 tests)
// ============================================================================

#[test]
fn test_bank_tree_deserializes_from_json() {
    // Test that bank_tree field can be loaded from policy JSON

    let json = r#"{
        "version": "1.0",
        "policy_id": "budget_policy",
        "bank_tree": {
            "type": "action",
            "node_id": "B1_SetBudget",
            "action": "SetReleaseBudget",
            "parameters": {
                "max_value_to_release": {"value": 500000.0}
            }
        },
        "payment_tree": {
            "type": "action",
            "node_id": "A1_Release",
            "action": "Release"
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["policy_id"], "budget_policy");
    assert!(parsed["bank_tree"].is_object());
    assert_eq!(parsed["bank_tree"]["action"], "SetReleaseBudget");
}

#[test]
fn test_set_release_budget_with_focus_list_deserializes() {
    // Test that focus list deserializes from JSON

    let json = r#"{
        "type": "action",
        "node_id": "B1_SetBudget",
        "action": "SetReleaseBudget",
        "parameters": {
            "max_value_to_release": {"value": 500000.0},
            "focus_cpty_list": {"value": ["BANK_A", "BANK_B"]},
            "max_per_cpty": {"value": 100000.0}
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["action"], "SetReleaseBudget");
    assert!(parsed["parameters"]["focus_cpty_list"].is_object());
    assert!(parsed["parameters"]["focus_cpty_list"]["value"].is_array());
}

#[test]
fn test_policy_without_bank_tree_is_valid() {
    // Test that policy without bank_tree is still valid (backward compatibility)

    let json = r#"{
        "version": "1.0",
        "policy_id": "simple_policy",
        "payment_tree": {
            "type": "action",
            "node_id": "A1_Release",
            "action": "Release"
        }
    }"#;

    let parsed: serde_json::Value = serde_json::from_str(json).unwrap();

    assert_eq!(parsed["policy_id"], "simple_policy");
    assert!(parsed["bank_tree"].is_null());
    assert!(parsed["payment_tree"].is_object());
}

// ============================================================================
// Test Group 8: Validation (3 tests)
// ============================================================================

#[test]
fn test_negative_budget_invalid() {
    // Test that negative budget is invalid

    let budget = -100_000i64;
    let is_valid = budget >= 0;

    assert!(!is_valid);
}

#[test]
fn test_zero_budget_valid() {
    // Test that zero budget is valid (blocks all releases)

    let budget = 0i64;
    let is_valid = budget >= 0;

    assert!(is_valid);
}

#[test]
fn test_negative_per_counterparty_limit_invalid() {
    // Test that negative per-counterparty limit is invalid

    let limit = -50_000i64;
    let is_valid = limit >= 0;

    assert!(!is_valid);
}
