//! PyO3 wrapper for Orchestrator
//!
//! This module provides the Python interface to the Rust orchestrator.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use crate::orchestrator::Orchestrator as RustOrchestrator;
use super::types::{parse_orchestrator_config, tick_result_to_py, transaction_to_py};

/// Python wrapper for Rust Orchestrator
///
/// This class provides the main entry point for Python code to create
/// and control simulations.
///
/// # Example (from Python)
///
/// ```python
/// from payment_simulator._core import Orchestrator
///
/// config = {
///     "ticks_per_day": 100,
///     "num_days": 1,
///     "rng_seed": 12345,
///     "agent_configs": [
///         {
///             "id": "BANK_A",
///             "opening_balance": 1_000_000,
///             "credit_limit": 500_000,
///             "policy": {"type": "Fifo"},
///         },
///     ],
/// }
///
/// orch = Orchestrator.new(config)
/// result = orch.tick()
/// print(f"Tick {result['tick']}: {result['num_settlements']} settlements")
/// ```
#[pyclass(name = "Orchestrator")]
pub struct PyOrchestrator {
    inner: RustOrchestrator,
}

#[pymethods]
impl PyOrchestrator {
    /// Create a new orchestrator from configuration
    ///
    /// # Arguments
    ///
    /// * `config` - Dictionary containing simulation configuration
    ///
    /// # Returns
    ///
    /// New Orchestrator instance
    ///
    /// # Errors
    ///
    /// Raises ValueError if:
    /// - Required configuration fields missing
    /// - Values out of valid range
    /// - Type conversions fail
    #[staticmethod]
    fn new(config: &Bound<'_, PyDict>) -> PyResult<Self> {
        let rust_config = parse_orchestrator_config(config)?;

        let inner = RustOrchestrator::new(rust_config)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to create orchestrator: {}", e)
            ))?;

        Ok(PyOrchestrator { inner })
    }

    /// Execute one simulation tick
    ///
    /// Runs the complete 9-step tick loop:
    /// 1. Generate arrivals
    /// 2. Evaluate policies
    /// 3. Execute RTGS settlements
    /// 4. Process RTGS queue
    /// 5. Run LSM coordinator
    /// 6. Accrue costs
    /// 7. Drop expired transactions
    /// 8. Log events
    /// 9. Advance time
    ///
    /// # Returns
    ///
    /// Dictionary containing tick results:
    /// - `tick`: Current tick number
    /// - `num_arrivals`: Number of new transactions
    /// - `num_settlements`: Number of settled transactions
    /// - `num_drops`: Number of dropped transactions
    /// - `lsm_bilateral_releases`: LSM bilateral offset count
    /// - `lsm_cycle_releases`: LSM cycle settlement count
    /// - `queue1_size`: Total Queue 1 size across agents
    /// - `queue2_size`: Queue 2 (RTGS queue) size
    /// - `total_liquidity_cost`: Liquidity cost this tick
    /// - `total_delay_cost`: Delay cost this tick
    fn tick(&mut self, py: Python) -> PyResult<Py<PyDict>> {
        let result = self.inner.tick()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Tick execution failed: {}", e)
            ))?;

        tick_result_to_py(py, &result)
    }

    /// Get current simulation tick
    fn current_tick(&self) -> usize {
        self.inner.current_tick()
    }

    /// Get current simulation day
    fn current_day(&self) -> usize {
        self.inner.current_day()
    }

    // ========================================================================
    // State Query Methods (Phase 7)
    // ========================================================================

    /// Get agent's current balance
    ///
    /// Returns the settlement account balance for the specified agent.
    /// Negative values indicate overdraft usage.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    ///
    /// Balance in cents (integer), or None if agent not found
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// balance = orch.get_agent_balance("BANK_A")
    /// if balance is not None:
    ///     print(f"BANK_A balance: ${balance / 100:.2f}")
    /// else:
    ///     print("Agent not found")
    /// ```
    fn get_agent_balance(&self, agent_id: &str) -> Option<i64> {
        self.inner.get_agent_balance(agent_id)
    }

    /// Get size of agent's internal queue (Queue 1)
    ///
    /// Returns the number of transactions waiting in the agent's
    /// internal queue for policy decisions.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    ///
    /// Queue size (integer), or None if agent not found
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// queue_size = orch.get_queue1_size("BANK_A")
    /// if queue_size is not None:
    ///     print(f"BANK_A has {queue_size} transactions in Queue 1")
    /// ```
    fn get_queue1_size(&self, agent_id: &str) -> Option<usize> {
        self.inner.get_queue1_size(agent_id)
    }

    /// Get size of RTGS central queue (Queue 2)
    ///
    /// Returns the number of transactions waiting in the RTGS
    /// central queue for liquidity to become available.
    ///
    /// # Returns
    ///
    /// Queue size (integer)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// queue2_size = orch.get_queue2_size()
    /// print(f"RTGS queue has {queue2_size} transactions waiting")
    /// ```
    fn get_queue2_size(&self) -> usize {
        self.inner.get_queue2_size()
    }

    /// Get list of all agent identifiers
    ///
    /// Returns all agent IDs configured in the simulation.
    /// Useful for iterating over agents to query their state.
    ///
    /// # Returns
    ///
    /// List of agent IDs (strings)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// for agent_id in orch.get_agent_ids():
    ///     balance = orch.get_agent_balance(agent_id)
    ///     print(f"{agent_id}: ${balance / 100:.2f}")
    /// ```
    fn get_agent_ids(&self) -> Vec<String> {
        self.inner.get_agent_ids()
    }

    // ========================================================================
    // Transaction Submission (Phase 7)
    // ========================================================================

    /// Submit a transaction for processing
    ///
    /// Creates a new transaction and queues it in the sender's internal queue.
    /// The transaction will be processed by the sender's policy during subsequent ticks.
    ///
    /// # Arguments
    ///
    /// * `sender` - ID of the sending agent (e.g., "BANK_A")
    /// * `receiver` - ID of the receiving agent (e.g., "BANK_B")
    /// * `amount` - Transaction amount in cents (must be positive)
    /// * `deadline_tick` - Tick by which transaction must settle
    /// * `priority` - Priority level (0-10, higher = more urgent)
    /// * `divisible` - Whether transaction can be split (currently unused, reserved for future use)
    ///
    /// # Returns
    ///
    /// Transaction ID (string) that can be used to track the transaction
    ///
    /// # Errors
    ///
    /// Raises RuntimeError if:
    /// - Sender or receiver doesn't exist
    /// - Amount is zero or negative
    /// - Deadline is in the past (before current tick)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// # Submit a $1,000 payment
    /// tx_id = orch.submit_transaction(
    ///     sender="BANK_A",
    ///     receiver="BANK_B",
    ///     amount=100_000,       # $1,000.00 in cents
    ///     deadline_tick=50,     # Must settle by tick 50
    ///     priority=5,           # Medium priority
    ///     divisible=False,      # Cannot be split
    /// )
    /// print(f"Created transaction: {tx_id}")
    ///
    /// # Wait for settlement
    /// orch.tick()
    /// balance = orch.get_agent_balance("BANK_A")
    /// ```
    fn submit_transaction(
        &mut self,
        sender: &str,
        receiver: &str,
        amount: i64,
        deadline_tick: usize,
        priority: u8,
        divisible: bool,
    ) -> PyResult<String> {
        self.inner
            .submit_transaction(sender, receiver, amount, deadline_tick, priority, divisible)
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to submit transaction: {}",
                    e
                ))
            })
    }

    // ========================================================================
    // Persistence Methods (Phase 10)
    // ========================================================================

    /// Get all transactions that arrived during a specific day
    ///
    /// Returns a list of dictionaries, each representing a transaction that
    /// arrived during the specified day. The dictionaries match the schema
    /// of the TransactionRecord Pydantic model for direct insertion into DuckDB.
    ///
    /// # Arguments
    ///
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    ///
    /// List of transaction dictionaries with all fields required by TransactionRecord
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// # Run simulation for one day
    /// for _ in range(100):  # 100 ticks per day
    ///     orch.tick()
    ///
    /// # Get all transactions from day 0
    /// daily_txs = orch.get_transactions_for_day(0)
    ///
    /// # Convert to Polars DataFrame
    /// import polars as pl
    /// df = pl.DataFrame(daily_txs)
    ///
    /// # Write to DuckDB
    /// conn.execute("INSERT INTO transactions SELECT * FROM df")
    /// ```
    fn get_transactions_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
        // Get transactions from Rust orchestrator
        let transactions = self.inner.get_transactions_for_day(day);

        // Get simulation metadata for conversion
        let simulation_id = self.inner.simulation_id();
        let ticks_per_day = self.inner.ticks_per_day();

        // Convert each transaction to Python dict
        let py_list = PyList::empty(py);
        for tx in transactions {
            let tx_dict = transaction_to_py(py, tx, &simulation_id, ticks_per_day)?;
            py_list.append(tx_dict)?;
        }

        Ok(py_list.into())
    }
}
