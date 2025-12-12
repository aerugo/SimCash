//! Cost Types and Schema Documentation
//!
//! This module provides:
//! - Cost rate configuration (`CostRates`)
//! - Self-documenting schema for cost types (`schema_docs`)
//!
//! # Single Source of Truth
//!
//! Cost documentation lives in `schema_docs.rs` and is exported via FFI
//! for the CLI command `payment-sim cost-schema`.

pub mod rates;
pub mod schema_docs;

// Re-exports
pub use rates::{get_priority_band, CostRates, PriorityBand, PriorityDelayMultipliers};
pub use schema_docs::{
    get_cost_schema, CostCategory, CostElement, CostExample, CostSchemaDoc, CostSchemaDocumented,
};
