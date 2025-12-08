// ! FFI (Foreign Function Interface) module
//!
//! PyO3 bindings for exposing Rust orchestrator to Python.
//!
//! # Design Principles
//!
//! 1. **Minimal boundary**: Only expose what's needed
//! 2. **Simple types**: Use primitives, strings, dicts at boundary
//! 3. **Validate inputs**: Check all values before crossing boundary
//! 4. **Safe errors**: Convert all Rust errors to Python exceptions
//! 5. **No references**: Python gets copies, never references to Rust state

pub mod orchestrator;
pub mod types;
