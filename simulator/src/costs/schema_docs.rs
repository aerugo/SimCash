//! Cost Schema Documentation
//!
//! Self-documenting schema system for cost type elements.
//! Generates documentation from code metadata for CLI tool consumption.

use serde::{Deserialize, Serialize};

// ============================================================================
// DATA STRUCTURES
// ============================================================================

/// Category for grouping cost types
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum CostCategory {
    /// Costs that accrue every tick
    PerTick,
    /// One-time penalties triggered by events
    OneTime,
    /// Costs charged once per day
    Daily,
    /// Multipliers that modify other costs
    Modifier,
}

/// Example calculation for a cost type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CostExample {
    /// Scenario description
    pub scenario: String,
    /// Input values as (name, value) pairs
    pub inputs: Vec<(String, String)>,
    /// Calculation steps
    pub calculation: String,
    /// Final result
    pub result: String,
}

/// Documentation for a single cost type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct CostElement {
    /// Cost type name (e.g., "overdraft_bps_per_tick")
    pub name: String,

    /// Human-readable display name (e.g., "Overdraft Cost")
    pub display_name: String,

    /// Category for filtering
    pub category: CostCategory,

    /// What this cost represents
    pub description: String,

    /// When/how the cost is incurred
    pub incurred_at: String,

    /// Mathematical formula (plain text)
    pub formula: String,

    /// Default value
    pub default_value: String,

    /// Unit of measurement
    pub unit: String,

    /// Data type (f64, i64, etc.)
    pub data_type: String,

    /// Rust source file location
    pub source_location: String,

    /// Related cost types
    pub see_also: Vec<String>,

    /// Example calculation
    pub example: Option<CostExample>,

    /// Version when added
    pub added_in: Option<String>,
}

/// Complete cost schema documentation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CostSchemaDoc {
    pub version: String,
    pub generated_at: String,
    pub cost_types: Vec<CostElement>,
}

/// Trait for types that can provide cost schema documentation
pub trait CostSchemaDocumented {
    fn schema_docs() -> Vec<CostElement>;
}

// ============================================================================
// IMPLEMENTATIONS
// ============================================================================

use super::rates::CostRates;

impl CostSchemaDocumented for CostRates {
    fn schema_docs() -> Vec<CostElement> {
        vec![
            // Per-tick costs
            CostElement {
                name: "overdraft_bps_per_tick".to_string(),
                display_name: "Overdraft Cost".to_string(),
                category: CostCategory::PerTick,
                description: "Cost for using intraday credit when balance goes negative. \
                    Represents the fee charged by the central bank for daylight overdrafts.".to_string(),
                incurred_at: "Every tick, when agent balance < 0".to_string(),
                formula: "max(0, -balance) * overdraft_bps_per_tick / 10,000".to_string(),
                default_value: "0.001".to_string(),
                unit: "basis points per tick".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["collateral_cost_per_tick_bps".to_string()],
                example: Some(CostExample {
                    scenario: "Bank A has negative balance".to_string(),
                    inputs: vec![
                        ("balance".to_string(), "-$500,000 (-50,000,000 cents)".to_string()),
                        ("overdraft_bps_per_tick".to_string(), "0.001".to_string()),
                    ],
                    calculation: "50,000,000 * 0.001 / 10,000 = 5 cents".to_string(),
                    result: "$0.05 per tick".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            CostElement {
                name: "delay_cost_per_tick_per_cent".to_string(),
                display_name: "Delay Cost".to_string(),
                category: CostCategory::PerTick,
                description: "Cost per tick for each cent of queued (pending) transaction value. \
                    Incentivizes timely settlement by penalizing delays.".to_string(),
                incurred_at: "Every tick, for each transaction in Queue 1 or Queue 2".to_string(),
                formula: "queued_amount * delay_cost_per_tick_per_cent".to_string(),
                default_value: "0.0001".to_string(),
                unit: "cost per cent per tick".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["overdue_delay_multiplier".to_string(), "priority_delay_multipliers".to_string()],
                example: Some(CostExample {
                    scenario: "$1M transaction waiting in queue".to_string(),
                    inputs: vec![
                        ("queued_amount".to_string(), "$1,000,000 (100,000,000 cents)".to_string()),
                        ("delay_cost_per_tick_per_cent".to_string(), "0.0001".to_string()),
                    ],
                    calculation: "100,000,000 * 0.0001 = 10,000 cents".to_string(),
                    result: "$100 per tick".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            CostElement {
                name: "collateral_cost_per_tick_bps".to_string(),
                display_name: "Collateral Opportunity Cost".to_string(),
                category: CostCategory::PerTick,
                description: "Opportunity cost for posting collateral to the central bank. \
                    Represents foregone interest earnings on pledged assets.".to_string(),
                incurred_at: "Every tick, based on posted collateral amount".to_string(),
                formula: "posted_collateral * collateral_cost_per_tick_bps / 10,000".to_string(),
                default_value: "0.0002".to_string(),
                unit: "basis points per tick".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["overdraft_bps_per_tick".to_string(), "liquidity_cost_per_tick_bps".to_string()],
                example: Some(CostExample {
                    scenario: "$10M collateral posted".to_string(),
                    inputs: vec![
                        ("posted_collateral".to_string(), "$10,000,000 (1,000,000,000 cents)".to_string()),
                        ("collateral_cost_per_tick_bps".to_string(), "0.0002".to_string()),
                    ],
                    calculation: "1,000,000,000 * 0.0002 / 10,000 = 20 cents".to_string(),
                    result: "$0.20 per tick".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            CostElement {
                name: "liquidity_cost_per_tick_bps".to_string(),
                display_name: "Liquidity Opportunity Cost".to_string(),
                category: CostCategory::PerTick,
                description: "Opportunity cost for holding allocated liquidity in the settlement system. \
                    Applied to liquidity_pool * allocation_fraction.".to_string(),
                incurred_at: "Every tick, based on allocated liquidity (not opening_balance)".to_string(),
                formula: "allocated_liquidity * liquidity_cost_per_tick_bps / 10,000".to_string(),
                default_value: "0.0".to_string(),
                unit: "basis points per tick".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["collateral_cost_per_tick_bps".to_string()],
                example: Some(CostExample {
                    scenario: "$5M allocated from liquidity pool".to_string(),
                    inputs: vec![
                        ("allocated_liquidity".to_string(), "$5,000,000 (500,000,000 cents)".to_string()),
                        ("liquidity_cost_per_tick_bps".to_string(), "0.0015".to_string()),
                    ],
                    calculation: "500,000,000 * 0.0015 / 10,000 = 75 cents".to_string(),
                    result: "$0.75 per tick".to_string(),
                }),
                added_in: Some("1.1".to_string()),
            },
            // One-time penalties
            CostElement {
                name: "deadline_penalty".to_string(),
                display_name: "Deadline Penalty".to_string(),
                category: CostCategory::OneTime,
                description: "One-time penalty charged when a transaction misses its deadline \
                    and becomes overdue. Represents reputational and operational costs.".to_string(),
                incurred_at: "Once, when transaction transitions from pending to overdue".to_string(),
                formula: "deadline_penalty (fixed amount)".to_string(),
                default_value: "50,000".to_string(),
                unit: "cents".to_string(),
                data_type: "i64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["overdue_delay_multiplier".to_string(), "eod_penalty_per_transaction".to_string()],
                example: Some(CostExample {
                    scenario: "Transaction misses deadline at tick 50".to_string(),
                    inputs: vec![
                        ("deadline_penalty".to_string(), "50,000 cents".to_string()),
                    ],
                    calculation: "Fixed penalty applied once".to_string(),
                    result: "$500 one-time charge".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            CostElement {
                name: "split_friction_cost".to_string(),
                display_name: "Split Friction Cost".to_string(),
                category: CostCategory::OneTime,
                description: "Cost incurred when splitting a transaction into multiple parts. \
                    Represents operational overhead of processing multiple instructions.".to_string(),
                incurred_at: "Once per split, when Split/StaggerSplit/PaceAndRelease action executes".to_string(),
                formula: "split_friction_cost * (num_splits - 1)".to_string(),
                default_value: "1,000".to_string(),
                unit: "cents per split".to_string(),
                data_type: "i64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec![],
                example: Some(CostExample {
                    scenario: "Transaction split into 4 parts".to_string(),
                    inputs: vec![
                        ("split_friction_cost".to_string(), "1,000 cents".to_string()),
                        ("num_splits".to_string(), "4".to_string()),
                    ],
                    calculation: "1,000 * (4 - 1) = 3,000 cents".to_string(),
                    result: "$30 total split cost".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            // Daily penalties
            CostElement {
                name: "eod_penalty_per_transaction".to_string(),
                display_name: "End-of-Day Penalty".to_string(),
                category: CostCategory::Daily,
                description: "Large penalty for transactions that remain unsettled at end of day. \
                    Represents systemic risk and regulatory non-compliance costs.".to_string(),
                incurred_at: "End of each day, for each unsettled transaction".to_string(),
                formula: "count(unsettled_transactions) * eod_penalty_per_transaction".to_string(),
                default_value: "10,000".to_string(),
                unit: "cents per transaction".to_string(),
                data_type: "i64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["deadline_penalty".to_string()],
                example: Some(CostExample {
                    scenario: "3 transactions unsettled at EOD".to_string(),
                    inputs: vec![
                        ("unsettled_count".to_string(), "3".to_string()),
                        ("eod_penalty_per_transaction".to_string(), "10,000 cents".to_string()),
                    ],
                    calculation: "3 * 10,000 = 30,000 cents".to_string(),
                    result: "$300 EOD penalty".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            // Modifiers
            CostElement {
                name: "overdue_delay_multiplier".to_string(),
                display_name: "Overdue Delay Multiplier".to_string(),
                category: CostCategory::Modifier,
                description: "Multiplier applied to delay costs when a transaction is past its deadline. \
                    Creates escalating urgency for overdue payments.".to_string(),
                incurred_at: "Applied to delay_cost calculation when is_overdue = true".to_string(),
                formula: "delay_cost * overdue_delay_multiplier (when overdue)".to_string(),
                default_value: "5.0".to_string(),
                unit: "multiplier".to_string(),
                data_type: "f64".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["delay_cost_per_tick_per_cent".to_string(), "deadline_penalty".to_string()],
                example: Some(CostExample {
                    scenario: "Overdue $1M transaction".to_string(),
                    inputs: vec![
                        ("base_delay_cost".to_string(), "$100/tick".to_string()),
                        ("overdue_delay_multiplier".to_string(), "5.0".to_string()),
                    ],
                    calculation: "$100 * 5.0 = $500".to_string(),
                    result: "$500 delay cost per tick (vs $100 if on-time)".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
            CostElement {
                name: "priority_delay_multipliers".to_string(),
                display_name: "Priority Delay Multipliers".to_string(),
                category: CostCategory::Modifier,
                description: "Optional priority-based multipliers for delay costs (BIS model). \
                    Applies different rates based on transaction priority bands.".to_string(),
                incurred_at: "Applied to delay_cost based on transaction priority (0-10)".to_string(),
                formula: "delay_cost * multiplier_for_priority_band".to_string(),
                default_value: "None (all priorities use same rate)".to_string(),
                unit: "multiplier struct".to_string(),
                data_type: "Option<PriorityDelayMultipliers>".to_string(),
                source_location: "simulator/src/costs/rates.rs".to_string(),
                see_also: vec!["delay_cost_per_tick_per_cent".to_string(), "overdue_delay_multiplier".to_string()],
                example: Some(CostExample {
                    scenario: "Priority-based delay costs".to_string(),
                    inputs: vec![
                        ("urgent_multiplier".to_string(), "2.0 (priority 8-10)".to_string()),
                        ("normal_multiplier".to_string(), "1.0 (priority 4-7)".to_string()),
                        ("low_multiplier".to_string(), "0.5 (priority 0-3)".to_string()),
                    ],
                    calculation: "Priority 9 tx: delay_cost * 2.0".to_string(),
                    result: "Urgent txs cost 2x, low-priority txs cost 0.5x".to_string(),
                }),
                added_in: Some("1.0".to_string()),
            },
        ]
    }
}

/// Generate complete cost schema documentation as JSON string
pub fn get_cost_schema() -> String {
    let schema = CostSchemaDoc {
        version: "1.0".to_string(),
        generated_at: "2025-01-01T00:00:00Z".to_string(), // Static for determinism
        cost_types: CostRates::schema_docs(),
    };

    serde_json::to_string_pretty(&schema).expect("Schema serialization should not fail")
}

// ============================================================================
// TESTS - Written FIRST (TDD)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    // -------------------------------------------------------------------------
    // Step 1.1: Data structure tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_cost_category_serializes_to_json() {
        let cat = CostCategory::PerTick;
        let json = serde_json::to_string(&cat).unwrap();
        assert_eq!(json, "\"PerTick\"");
    }

    #[test]
    fn test_cost_category_deserializes_from_json() {
        let cat: CostCategory = serde_json::from_str("\"OneTime\"").unwrap();
        assert_eq!(cat, CostCategory::OneTime);
    }

    #[test]
    fn test_cost_example_serializes_roundtrip() {
        let example = CostExample {
            scenario: "Test scenario".to_string(),
            inputs: vec![("amount".to_string(), "1000".to_string())],
            calculation: "1000 * 0.01".to_string(),
            result: "10".to_string(),
        };

        let json = serde_json::to_string(&example).unwrap();
        let restored: CostExample = serde_json::from_str(&json).unwrap();
        assert_eq!(example, restored);
    }

    #[test]
    fn test_cost_element_serializes_roundtrip() {
        let elem = CostElement {
            name: "test_cost".to_string(),
            display_name: "Test Cost".to_string(),
            category: CostCategory::PerTick,
            description: "A test cost".to_string(),
            incurred_at: "Every tick".to_string(),
            formula: "amount * rate".to_string(),
            default_value: "0.001".to_string(),
            unit: "bps".to_string(),
            data_type: "f64".to_string(),
            source_location: "test.rs:1".to_string(),
            see_also: vec!["other_cost".to_string()],
            example: None,
            added_in: Some("1.0".to_string()),
        };

        let json = serde_json::to_string(&elem).unwrap();
        let restored: CostElement = serde_json::from_str(&json).unwrap();
        assert_eq!(elem, restored);
    }

    #[test]
    fn test_cost_schema_doc_serializes_to_json() {
        let schema = CostSchemaDoc {
            version: "1.0".to_string(),
            generated_at: "2025-01-01T00:00:00Z".to_string(),
            cost_types: vec![],
        };

        let json = serde_json::to_string_pretty(&schema).unwrap();
        assert!(json.contains("\"version\": \"1.0\""));
        assert!(json.contains("\"cost_types\": []"));
    }

    // -------------------------------------------------------------------------
    // Step 1.2: CostRates schema documentation tests (TDD)
    // -------------------------------------------------------------------------

    #[test]
    fn test_cost_rates_schema_docs_returns_all_cost_types() {
        let docs = CostRates::schema_docs();

        // Must have all 9 cost types as specified in the plan
        assert_eq!(docs.len(), 9, "Expected 9 cost types, got {}", docs.len());

        let names: Vec<&str> = docs.iter().map(|d| d.name.as_str()).collect();

        // Per-tick costs
        assert!(names.contains(&"overdraft_bps_per_tick"), "Missing overdraft_bps_per_tick");
        assert!(names.contains(&"delay_cost_per_tick_per_cent"), "Missing delay_cost_per_tick_per_cent");
        assert!(names.contains(&"collateral_cost_per_tick_bps"), "Missing collateral_cost_per_tick_bps");
        assert!(names.contains(&"liquidity_cost_per_tick_bps"), "Missing liquidity_cost_per_tick_bps");

        // One-time penalties
        assert!(names.contains(&"deadline_penalty"), "Missing deadline_penalty");
        assert!(names.contains(&"split_friction_cost"), "Missing split_friction_cost");

        // Daily penalties
        assert!(names.contains(&"eod_penalty_per_transaction"), "Missing eod_penalty_per_transaction");

        // Modifiers
        assert!(names.contains(&"overdue_delay_multiplier"), "Missing overdue_delay_multiplier");
        assert!(names.contains(&"priority_delay_multipliers"), "Missing priority_delay_multipliers");
    }

    #[test]
    fn test_cost_rates_schema_docs_has_correct_categories() {
        let docs = CostRates::schema_docs();

        // Per-tick costs
        let overdraft = docs.iter().find(|d| d.name == "overdraft_bps_per_tick").unwrap();
        assert_eq!(overdraft.category, CostCategory::PerTick);

        let delay = docs.iter().find(|d| d.name == "delay_cost_per_tick_per_cent").unwrap();
        assert_eq!(delay.category, CostCategory::PerTick);

        // One-time penalties
        let deadline = docs.iter().find(|d| d.name == "deadline_penalty").unwrap();
        assert_eq!(deadline.category, CostCategory::OneTime);

        // Daily penalties
        let eod = docs.iter().find(|d| d.name == "eod_penalty_per_transaction").unwrap();
        assert_eq!(eod.category, CostCategory::Daily);

        // Modifiers
        let overdue_mult = docs.iter().find(|d| d.name == "overdue_delay_multiplier").unwrap();
        assert_eq!(overdue_mult.category, CostCategory::Modifier);
    }

    #[test]
    fn test_cost_rates_schema_docs_has_descriptions() {
        let docs = CostRates::schema_docs();

        for doc in &docs {
            assert!(!doc.description.is_empty(), "{} has empty description", doc.name);
            assert!(!doc.formula.is_empty(), "{} has empty formula", doc.name);
            assert!(!doc.incurred_at.is_empty(), "{} has empty incurred_at", doc.name);
        }
    }

    #[test]
    fn test_cost_rates_schema_docs_has_display_names() {
        let docs = CostRates::schema_docs();

        for doc in &docs {
            assert!(!doc.display_name.is_empty(), "{} has empty display_name", doc.name);
            // Display names should be human-readable (not snake_case)
            assert!(!doc.display_name.contains('_'), "{} display_name contains underscore", doc.name);
        }
    }

    #[test]
    fn test_cost_rates_schema_docs_has_default_values() {
        let docs = CostRates::schema_docs();

        for doc in &docs {
            assert!(!doc.default_value.is_empty(), "{} has empty default_value", doc.name);
        }

        // Verify specific defaults match CostRates::default()
        let overdraft = docs.iter().find(|d| d.name == "overdraft_bps_per_tick").unwrap();
        assert_eq!(overdraft.default_value, "0.001");

        let deadline = docs.iter().find(|d| d.name == "deadline_penalty").unwrap();
        assert_eq!(deadline.default_value, "50,000");

        let eod = docs.iter().find(|d| d.name == "eod_penalty_per_transaction").unwrap();
        assert_eq!(eod.default_value, "10,000");
    }

    #[test]
    fn test_cost_rates_schema_docs_has_examples() {
        let docs = CostRates::schema_docs();

        // All cost types should have examples
        for doc in &docs {
            assert!(doc.example.is_some(), "{} has no example", doc.name);

            let example = doc.example.as_ref().unwrap();
            assert!(!example.scenario.is_empty(), "{} example has empty scenario", doc.name);
            assert!(!example.inputs.is_empty(), "{} example has no inputs", doc.name);
            assert!(!example.calculation.is_empty(), "{} example has empty calculation", doc.name);
            assert!(!example.result.is_empty(), "{} example has empty result", doc.name);
        }
    }

    #[test]
    fn test_per_tick_costs_count() {
        let docs = CostRates::schema_docs();
        let per_tick_count = docs.iter().filter(|d| d.category == CostCategory::PerTick).count();
        assert_eq!(per_tick_count, 4, "Expected 4 per-tick costs");
    }

    #[test]
    fn test_one_time_costs_count() {
        let docs = CostRates::schema_docs();
        let one_time_count = docs.iter().filter(|d| d.category == CostCategory::OneTime).count();
        assert_eq!(one_time_count, 2, "Expected 2 one-time costs");
    }

    #[test]
    fn test_modifier_costs_count() {
        let docs = CostRates::schema_docs();
        let modifier_count = docs.iter().filter(|d| d.category == CostCategory::Modifier).count();
        assert_eq!(modifier_count, 2, "Expected 2 modifier costs");
    }

    // -------------------------------------------------------------------------
    // Step 1.3: get_cost_schema() tests
    // -------------------------------------------------------------------------

    #[test]
    fn test_get_cost_schema_returns_valid_json() {
        let schema = get_cost_schema();
        let parsed: serde_json::Value = serde_json::from_str(&schema).unwrap();

        assert!(parsed.get("version").is_some());
        assert!(parsed.get("generated_at").is_some());
        assert!(parsed.get("cost_types").is_some());
    }

    #[test]
    fn test_get_cost_schema_has_correct_cost_count() {
        let schema = get_cost_schema();
        let parsed: CostSchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.cost_types.len(), 9, "Expected 9 cost types in schema");
    }

    #[test]
    fn test_get_cost_schema_version() {
        let schema = get_cost_schema();
        let parsed: CostSchemaDoc = serde_json::from_str(&schema).unwrap();

        assert_eq!(parsed.version, "1.0");
    }

    #[test]
    fn test_get_cost_schema_is_deterministic() {
        let schema1 = get_cost_schema();
        let schema2 = get_cost_schema();

        // Should be identical (deterministic)
        assert_eq!(schema1, schema2);
    }

    #[test]
    fn test_all_cost_types_have_source_location() {
        let docs = CostRates::schema_docs();

        for doc in &docs {
            assert!(!doc.source_location.is_empty(), "{} has empty source_location", doc.name);
            assert!(
                doc.source_location.contains("rates.rs"),
                "{} source_location should reference rates.rs, got: {}",
                doc.name,
                doc.source_location
            );
        }
    }

    #[test]
    fn test_data_types_are_valid() {
        let docs = CostRates::schema_docs();
        let valid_types = ["f64", "i64", "Option<PriorityDelayMultipliers>"];

        for doc in &docs {
            assert!(
                valid_types.contains(&doc.data_type.as_str()),
                "{} has invalid data_type: {}",
                doc.name,
                doc.data_type
            );
        }
    }
}
