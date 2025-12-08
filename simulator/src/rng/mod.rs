//! Deterministic random number generation
//!
//! Uses xorshift64* algorithm for fast, deterministic random number generation.
//! CRITICAL: All randomness in the simulator MUST go through this module.

mod xorshift;

pub use xorshift::RngManager;
