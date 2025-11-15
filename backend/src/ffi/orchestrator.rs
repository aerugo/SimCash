//! PyO3 wrapper for Orchestrator
//!
//! This module provides the Python interface to the Rust orchestrator.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

use super::types::{
    agent_metrics_to_py, collateral_event_to_py, parse_orchestrator_config, policy_config_to_py,
    tick_result_to_py, transaction_to_py,
};
use crate::orchestrator::Orchestrator as RustOrchestrator;

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

/// Convert a single Event to Python dictionary.
///
/// This is the single source of truth for event serialization to Python.
/// Used by both `get_tick_events()` and `get_all_events()`.
///
/// # Arguments
/// * `py` - Python interpreter context
/// * `event` - Reference to the event to serialize
///
/// # Returns
/// Python dictionary with event fields
///
/// # Example
/// ```ignore
/// let event = Event::Arrival { tick: 1, tx_id: "tx_001".to_string(), ... };
/// let dict = event_to_py_dict(py, &event)?;
/// assert_eq!(dict.get_item("event_type")?, Some("arrival"));
/// ```
fn event_to_py_dict<'py>(
    py: Python<'py>,
    event: &crate::models::event::Event,
) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new(py);

    // Set common fields for all events
    dict.set_item("event_type", event.event_type())?;
    dict.set_item("tick", event.tick())?;

    // Set event-specific fields based on event type
    match event {
        crate::models::event::Event::Arrival { tx_id, sender_id, receiver_id, amount, deadline, priority, is_divisible, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("deadline", deadline)?;
            dict.set_item("priority", priority)?;
            dict.set_item("is_divisible", is_divisible)?;
        }
        crate::models::event::Event::PolicySubmit { agent_id, tx_id, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
        }
        crate::models::event::Event::PolicyHold { agent_id, tx_id, reason, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::PolicyDrop { agent_id, tx_id, reason, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::PolicySplit { agent_id, tx_id, num_splits, child_ids, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("num_splits", num_splits)?;
            dict.set_item("child_ids", child_ids)?;
        }
        crate::models::event::Event::TransactionReprioritized { agent_id, tx_id, old_priority, new_priority, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("old_priority", old_priority)?;
            dict.set_item("new_priority", new_priority)?;
        }
        crate::models::event::Event::CollateralPost { agent_id, amount, reason, new_total, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
            dict.set_item("new_total", new_total)?;
        }
        crate::models::event::Event::CollateralWithdraw { agent_id, amount, reason, new_total, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
            dict.set_item("new_total", new_total)?;
        }
        crate::models::event::Event::CollateralTimerWithdrawn { agent_id, amount, original_reason, posted_at_tick, new_total, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("original_reason", original_reason)?;
            dict.set_item("posted_at_tick", posted_at_tick)?;
            dict.set_item("new_total", new_total)?;
        }
        crate::models::event::Event::CollateralTimerBlocked { agent_id, requested_amount, reason, original_reason, posted_at_tick, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("requested_amount", requested_amount)?;
            dict.set_item("reason", reason)?;
            dict.set_item("original_reason", original_reason)?;
            dict.set_item("posted_at_tick", posted_at_tick)?;
        }
        crate::models::event::Event::BankBudgetSet { agent_id, max_value, focus_counterparties, max_per_counterparty, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("max_value", max_value)?;
            dict.set_item("focus_counterparties", focus_counterparties)?;
            dict.set_item("max_per_counterparty", max_per_counterparty)?;
        }
        crate::models::event::Event::StateRegisterSet { agent_id, register_key, old_value, new_value, reason, decision_path, .. } => {
            dict.set_item("agent_id", agent_id)?;
            dict.set_item("register_key", register_key)?;
            dict.set_item("old_value", old_value)?;
            dict.set_item("new_value", new_value)?;
            dict.set_item("reason", reason)?;
            dict.set_item("decision_path", decision_path)?;
        }
        #[allow(deprecated)]
        crate::models::event::Event::Settlement { tx_id, sender_id, receiver_id, amount, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
        }
        crate::models::event::Event::RtgsImmediateSettlement { tx_id, sender, receiver, amount, sender_balance_before, sender_balance_after, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender", sender)?;
            dict.set_item("receiver", receiver)?;
            dict.set_item("amount", amount)?;
            dict.set_item("sender_balance_before", sender_balance_before)?;
            dict.set_item("sender_balance_after", sender_balance_after)?;
        }
        crate::models::event::Event::Queue2LiquidityRelease { tx_id, sender, receiver, amount, queue_wait_ticks, release_reason, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender", sender)?;
            dict.set_item("receiver", receiver)?;
            dict.set_item("amount", amount)?;
            dict.set_item("queue_wait_ticks", queue_wait_ticks)?;
            dict.set_item("release_reason", release_reason)?;
        }
        crate::models::event::Event::QueuedRtgs { tx_id, sender_id, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
        }
        crate::models::event::Event::LsmBilateralOffset { agent_a, agent_b, tx_ids, amount_a, amount_b, .. } => {
            dict.set_item("agent_a", agent_a)?;
            dict.set_item("agent_b", agent_b)?;
            dict.set_item("tx_ids", tx_ids)?;
            dict.set_item("amount_a", amount_a)?;
            dict.set_item("amount_b", amount_b)?;
            // Also set "amount" for backward compatibility (sum of the two)
            dict.set_item("amount", amount_a + amount_b)?;
        }
        crate::models::event::Event::LsmCycleSettlement { agents, tx_amounts, total_value, net_positions, max_net_outflow, max_net_outflow_agent, tx_ids, .. } => {
            dict.set_item("agents", agents)?;
            dict.set_item("tx_amounts", tx_amounts)?;
            dict.set_item("total_value", total_value)?;
            dict.set_item("net_positions", net_positions)?;
            dict.set_item("max_net_outflow", max_net_outflow)?;
            dict.set_item("max_net_outflow_agent", max_net_outflow_agent)?;
            dict.set_item("tx_ids", tx_ids)?;
            // Backward compatibility: also set "cycle_value"
            dict.set_item("cycle_value", total_value)?;
        }
        crate::models::event::Event::CostAccrual { agent_id, costs, .. } => {
            dict.set_item("agent_id", agent_id)?;
            // Convert CostBreakdown to dict
            let cost_dict = PyDict::new(py);
            cost_dict.set_item("liquidity_cost", costs.liquidity_cost)?;
            cost_dict.set_item("delay_cost", costs.delay_cost)?;
            cost_dict.set_item("collateral_cost", costs.collateral_cost)?;
            cost_dict.set_item("penalty_cost", costs.penalty_cost)?;
            cost_dict.set_item("split_friction_cost", costs.split_friction_cost)?;
            cost_dict.set_item("total", costs.total())?;
            dict.set_item("costs", cost_dict)?;
        }
        crate::models::event::Event::EndOfDay { day, unsettled_count, total_penalties, .. } => {
            dict.set_item("day", day)?;
            dict.set_item("unsettled_count", unsettled_count)?;
            dict.set_item("total_penalties", total_penalties)?;
        }
        crate::models::event::Event::TransactionWentOverdue {
            tx_id, sender_id, receiver_id, amount, remaining_amount,
            deadline_tick, ticks_overdue, deadline_penalty_cost, ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("remaining_amount", remaining_amount)?;
            dict.set_item("deadline_tick", deadline_tick)?;
            dict.set_item("ticks_overdue", ticks_overdue)?;
            dict.set_item("deadline_penalty_cost", deadline_penalty_cost)?;
        }
        crate::models::event::Event::OverdueTransactionSettled {
            tx_id, sender_id, receiver_id, amount, settled_amount,
            deadline_tick, overdue_since_tick, total_ticks_overdue,
            deadline_penalty_cost, estimated_delay_cost, ..
        } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender_id", sender_id)?;
            dict.set_item("receiver_id", receiver_id)?;
            dict.set_item("amount", amount)?;
            dict.set_item("settled_amount", settled_amount)?;
            dict.set_item("deadline_tick", deadline_tick)?;
            dict.set_item("overdue_since_tick", overdue_since_tick)?;
            dict.set_item("total_ticks_overdue", total_ticks_overdue)?;
            dict.set_item("deadline_penalty_cost", deadline_penalty_cost)?;
            dict.set_item("estimated_delay_cost", estimated_delay_cost)?;
        }
        crate::models::event::Event::RtgsQueue2Settle { tx_id, sender, receiver, amount, reason, .. } => {
            dict.set_item("tx_id", tx_id)?;
            dict.set_item("sender", sender)?;
            dict.set_item("receiver", receiver)?;
            dict.set_item("amount", amount)?;
            dict.set_item("reason", reason)?;
        }
        crate::models::event::Event::ScenarioEventExecuted { tick, event_type, details } => {
            dict.set_item("tick", tick)?;
            dict.set_item("event_type", "ScenarioEventExecuted")?;
            dict.set_item("scenario_event_type", event_type)?;
            // Convert JSON value to string, Python can parse it
            let details_json = serde_json::to_string(details).unwrap_or_else(|_| "{}".to_string());
            dict.set_item("details_json", details_json)?;
        }
    }

    Ok(dict)
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

        let inner = RustOrchestrator::new(rust_config).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to create orchestrator: {}",
                e
            ))
        })?;

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
        let result = self.inner.tick().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Tick execution failed: {}",
                e
            ))
        })?;

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

    /// Get agent's credit limit
    ///
    /// Returns the maximum overdraft amount allowed for the agent.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    ///
    /// Credit limit in cents (integer), or None if agent not found
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// unsecured_cap = orch.get_agent_unsecured_cap("BANK_A")
    /// if unsecured_cap is not None:
    ///     print(f"BANK_A unsecured cap: ${unsecured_cap / 100:.2f}")
    /// ```
    fn get_agent_unsecured_cap(&self, agent_id: &str) -> Option<i64> {
        self.inner.get_agent_unsecured_cap(agent_id)
    }

    /// Get agent's arrival rate (transactions per tick)
    ///
    /// Returns the current transaction generation rate for the agent.
    /// This can be dynamically modified by scenario events.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    ///
    /// Rate per tick (float), or None if agent not found or has no arrival config
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// rate = orch.get_arrival_rate("BANK_A")
    /// if rate is not None:
    ///     print(f"BANK_A generates {rate:.2f} transactions per tick")
    /// ```
    fn get_arrival_rate(&self, agent_id: &str) -> Option<f64> {
        self.inner.get_arrival_rate(agent_id)
    }

    /// Get comprehensive agent state including collateral information
    ///
    /// Returns a dictionary with all agent financial state:
    /// - balance: Current settlement account balance (cents)
    /// - credit_used: Amount of credit facility currently in use (cents)
    /// - credit_limit: Maximum overdraft allowed (cents)
    /// - available_liquidity: Usable funds including balance, credit, and collateral headroom (cents)
    /// - posted_collateral: Amount of collateral posted (cents)
    /// - collateral_haircut: Discount factor applied to collateral (0.0-1.0)
    ///
    /// # Arguments
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    /// Dictionary with agent state, or raises exception if agent not found
    ///
    /// # Example (from Python)
    /// ```python
    /// state = orch.get_agent_state("BANK_A")
    /// print(f"Balance: ${state['balance']/100:.2f}")
    /// print(f"Available: ${state['available_liquidity']/100:.2f}")
    /// print(f"Collateral: ${state['posted_collateral']/100:.2f}")
    /// ```
    fn get_agent_state(&self, py: Python, agent_id: &str) -> PyResult<Py<PyDict>> {
        let state = self.inner.state();
        let agent = state.get_agent(agent_id)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Agent '{}' not found", agent_id)
            ))?;

        let dict = PyDict::new(py);
        // Basic fields
        dict.set_item("balance", agent.balance())?;
        dict.set_item("available_liquidity", agent.available_liquidity())?;
        dict.set_item("queue1_size", agent.outgoing_queue().len())?;

        // Collateral fields
        dict.set_item("posted_collateral", agent.posted_collateral())?;
        dict.set_item("collateral_haircut", agent.collateral_haircut())?;
        dict.set_item("unsecured_cap", agent.unsecured_cap())?;

        // New T2/CLM-style collateral/headroom metrics
        dict.set_item("credit_used", agent.credit_used())?;
        dict.set_item("allowed_overdraft_limit", agent.allowed_overdraft_limit())?;
        dict.set_item("overdraft_headroom", agent.headroom())?;
        dict.set_item("max_withdrawable_collateral", agent.max_withdrawable_collateral(0))?;

        Ok(dict.into())
    }

    /// Post collateral to increase available liquidity headroom
    ///
    /// Posts collateral which increases the agent's available liquidity by
    /// (amount * collateral_haircut). The collateral is locked for a minimum
    /// holding period to prevent oscillation.
    ///
    /// # Arguments
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    /// * `amount` - Collateral amount in cents (must be positive)
    ///
    /// # Returns
    /// Dictionary with:
    /// - success: bool
    /// - message: str (description)
    ///
    /// # Example (from Python)
    /// ```python
    /// result = orch.post_collateral("BANK_A", 100000)  # $1,000
    /// if result['success']:
    ///     print(f"Posted collateral: {result['message']}")
    /// ```
    fn post_collateral(&mut self, py: Python, agent_id: &str, amount: i64) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);

        if amount <= 0 {
            dict.set_item("success", false)?;
            dict.set_item("message", "Collateral amount must be positive")?;
            return Ok(dict.into());
        }

        let current_tick = self.inner.current_tick();

        // Update agent state and get new total (scope to drop mutable borrow)
        let new_total = {
            let state = self.inner.state_mut();
            match state.get_agent_mut(agent_id) {
                Some(agent) => {
                    let new_total = agent.posted_collateral() + amount;
                    agent.set_posted_collateral(new_total);
                    agent.set_collateral_posted_at_tick(current_tick);
                    Some(new_total)
                }
                None => None,
            }
        }; // Mutable borrow of state dropped here

        match new_total {
            Some(new_total) => {
                // Log event
                self.inner.log_event(crate::models::Event::CollateralPost {
                    tick: current_tick,
                    agent_id: agent_id.to_string(),
                    amount,
                    reason: "ManualPost".to_string(),
                    new_total,
                });

                dict.set_item("success", true)?;
                dict.set_item("message", format!("Posted {} cents collateral at tick {}", amount, current_tick))?;
                Ok(dict.into())
            }
            None => {
                dict.set_item("success", false)?;
                dict.set_item("message", format!("Agent '{}' not found", agent_id))?;
                Ok(dict.into())
            }
        }
    }

    /// Withdraw collateral (subject to minimum holding period)
    ///
    /// Attempts to withdraw collateral. Will fail if:
    /// - Minimum holding period has not elapsed (default 5 ticks)
    /// - Agent doesn't have enough collateral posted
    ///
    /// # Arguments
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    /// * `amount` - Collateral amount to withdraw in cents (must be positive)
    ///
    /// # Returns
    /// Dictionary with:
    /// - success: bool
    /// - message: str (description or error reason)
    ///
    /// # Example (from Python)
    /// ```python
    /// result = orch.withdraw_collateral("BANK_A", 50000)  # $500
    /// if not result['success']:
    ///     print(f"Withdrawal failed: {result['message']}")
    /// ```
    fn withdraw_collateral(&mut self, py: Python, agent_id: &str, amount: i64) -> PyResult<Py<PyDict>> {
        const MIN_HOLDING_TICKS: usize = 5; // Configurable default
        const SAFETY_BUFFER: i64 = 0; // Could be made configurable

        let dict = PyDict::new(py);

        if amount <= 0 {
            dict.set_item("success", false)?;
            dict.set_item("message", "Withdrawal amount must be positive")?;
            return Ok(dict.into());
        }

        let current_tick = self.inner.current_tick();

        // Validate and update agent state (scope to drop mutable borrow)
        let withdrawal_result: Result<i64, String> = {
            let state = self.inner.state_mut();
            match state.get_agent_mut(agent_id) {
                Some(agent) => {
                    // Check minimum holding period
                    if !agent.can_withdraw_collateral(current_tick, MIN_HOLDING_TICKS) {
                        let posted_at = agent.collateral_posted_at_tick().unwrap_or(0);
                        let ticks_remaining = (posted_at + MIN_HOLDING_TICKS).saturating_sub(current_tick);
                        Err(format!(
                            "Minimum holding period not met. {} tick(s) remaining",
                            ticks_remaining
                        ))
                    } else {
                        // CRITICAL: Check that withdrawal doesn't breach headroom (Invariant I2)
                        let max_withdrawable = agent.max_withdrawable_collateral(SAFETY_BUFFER);
                        if amount > max_withdrawable {
                            let credit_used = agent.credit_used();
                            let allowed_limit = agent.allowed_overdraft_limit();
                            let headroom = agent.headroom();

                            Err(format!(
                                "Withdrawal would breach collateralized headroom. \
                                 Max withdrawable: {}, requested: {}. \
                                 Current state: credit_used={}, allowed_limit={}, headroom={}. \
                                 Ensure balance is restored or post more collateral before withdrawing.",
                                max_withdrawable, amount, credit_used, allowed_limit, headroom
                            ))
                        } else {
                            // Safe to withdraw
                            let current_collateral = agent.posted_collateral();
                            let new_total = current_collateral - amount;
                            agent.set_posted_collateral(new_total);

                            // Clear posted_at_tick if all collateral withdrawn
                            if new_total == 0 {
                                agent.set_collateral_posted_at_tick(0);
                            }

                            Ok(new_total)
                        }
                    }
                }
                None => {
                    Err(format!("Agent '{}' not found", agent_id))
                }
            }
        }; // Mutable borrow of state dropped here

        match withdrawal_result {
            Ok(new_total) => {
                // Log event
                self.inner.log_event(crate::models::Event::CollateralWithdraw {
                    tick: current_tick,
                    agent_id: agent_id.to_string(),
                    amount,
                    reason: "ManualWithdraw".to_string(),
                    new_total,
                });

                dict.set_item("success", true)?;
                dict.set_item("message", format!("Withdrew {} cents collateral", amount))?;
                Ok(dict.into())
            }
            Err(err_msg) => {
                dict.set_item("success", false)?;
                dict.set_item("message", err_msg)?;
                Ok(dict.into())
            }
        }
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

    /// Get contents of agent's internal queue (Queue 1)
    ///
    /// Returns a list of transaction IDs currently in the agent's
    /// internal queue (Queue 1), preserving queue order.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier (e.g., "BANK_A")
    ///
    /// # Returns
    ///
    /// List of transaction IDs (strings) in queue order, or empty list
    /// if agent not found or queue is empty.
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// queue_contents = orch.get_agent_queue1_contents("BANK_A")
    /// print(f"BANK_A Queue 1 has {len(queue_contents)} transactions:")
    /// for tx_id in queue_contents:
    ///     print(f"  - {tx_id}")
    /// ```
    ///
    /// # Phase 3: Queue Contents Persistence
    ///
    /// This method enables Phase 3 queue persistence by providing access
    /// to the actual transaction IDs in each agent's queue.
    fn get_agent_queue1_contents(&self, agent_id: &str) -> Vec<String> {
        self.inner.get_agent_queue1_contents(agent_id)
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

    /// Get LSM cycle events for a specific day (Phase 4)
    ///
    /// Returns all LSM cycle events (bilateral offsets and multilateral cycles)
    /// that were settled during the specified day.
    ///
    /// # Arguments
    ///
    /// * `day` - The day number to query (0-indexed)
    ///
    /// # Returns
    ///
    /// List of dictionaries, each containing:
    /// - tick: int - Tick when cycle was settled
    /// - day: int - Day when cycle was settled
    /// - cycle_type: str - "bilateral" or "multilateral"
    /// - cycle_length: int - Number of agents in cycle
    /// - agents: list[str] - Agent IDs in cycle
    /// - transactions: list[str] - Transaction IDs in cycle
    /// - settled_value: int - Net value settled (cents)
    /// - total_value: int - Gross value before netting (cents)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// lsm_cycles = orch.get_lsm_cycles_for_day(0)
    /// for cycle in lsm_cycles:
    ///     agents_str = " → ".join(cycle["agents"])
    ///     print(f"Cycle: {agents_str}")
    ///     print(f"  Settled: ${cycle['settled_value'] / 100:.2f}")
    /// ```
    fn get_lsm_cycles_for_day(&self, py: Python, day: usize) -> PyResult<Vec<PyObject>> {
        let events = self.inner.get_lsm_cycles_for_day(day);

        let mut result = Vec::new();
        for event in events {
            let dict = PyDict::new(py);
            dict.set_item("tick", event.tick)?;
            dict.set_item("day", event.day)?;
            dict.set_item("cycle_type", event.cycle_type)?;
            dict.set_item("cycle_length", event.cycle_length)?;
            dict.set_item("agents", event.agents)?;
            dict.set_item("transactions", event.transactions)?;
            dict.set_item("settled_value", event.settled_value)?;
            dict.set_item("total_value", event.total_value)?;
            result.push(dict.into());
        }

        Ok(result)
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

    /// Get daily agent metrics for a specific day (Phase 3: Agent Metrics Collection)
    ///
    /// Returns metrics for all agents for the specified day, including balance tracking,
    /// transaction counts, queue sizes, and costs.
    ///
    /// # Arguments
    ///
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    ///
    /// List of dictionaries, each containing metrics for one agent.
    /// Each dictionary matches the schema of DailyAgentMetricsRecord Pydantic model.
    ///
    /// Returns empty list if the day hasn't been completed yet or doesn't exist.
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// from payment_simulator._core import Orchestrator
    /// import polars as pl
    ///
    /// # Run simulation for 1 day
    /// orch = Orchestrator.new(config)
    /// for _ in range(100):  # 100 ticks per day
    ///     orch.tick()
    ///
    /// # Get metrics for day 0
    /// daily_metrics = orch.get_daily_agent_metrics(0)
    ///
    /// # Convert to Polars DataFrame
    /// df = pl.DataFrame(daily_metrics)
    ///
    /// # Write to DuckDB
    /// conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")
    /// ```
    fn get_daily_agent_metrics(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
        // Get metrics from Rust orchestrator
        let metrics = self.inner.get_daily_agent_metrics(day);

        // Get simulation ID for metrics
        let simulation_id = self.inner.simulation_id();

        // Convert each metrics record to Python dict
        let py_list = PyList::empty(py);
        for m in metrics {
            let metrics_dict = agent_metrics_to_py(py, m, &simulation_id)?;
            py_list.append(metrics_dict)?;
        }

        Ok(py_list.into())
    }

    /// Get agent policy configurations
    ///
    /// Returns policy configuration for each agent as specified in the
    /// original simulation configuration. Used for policy snapshot tracking.
    ///
    /// # Returns (Python)
    ///
    /// List of dicts with structure:
    /// ```python
    /// [
    ///     {
    ///         "agent_id": "BANK_A",
    ///         "policy_config": {"type": "Fifo"}
    ///     },
    ///     {
    ///         "agent_id": "BANK_B",
    ///         "policy_config": {
    ///             "type": "LiquidityAware",
    ///             "target_buffer": 500000,
    ///             "urgency_threshold": 5
    ///         }
    ///     }
    /// ]
    /// ```
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// orch = Orchestrator.new(config)
    ///
    /// # Get policy configs
    /// policies = orch.get_agent_policies()
    /// for policy in policies:
    ///     print(f"{policy['agent_id']}: {policy['policy_config']}")
    ///
    /// # Convert to policy snapshots with SHA256 hashing
    /// import hashlib
    /// import json
    /// snapshots = []
    /// for policy in policies:
    ///     policy_json = json.dumps(policy['policy_config'], sort_keys=True)
    ///     policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()
    ///     snapshots.append({
    ///         "agent_id": policy['agent_id'],
    ///         "policy_hash": policy_hash,
    ///         "policy_json": policy_json,
    ///         "created_by": "init"
    ///     })
    /// ```
    fn get_agent_policies(&self, py: Python) -> PyResult<Py<PyList>> {
        // Get policies from Rust orchestrator
        let policies = self.inner.get_agent_policies();

        // Convert each policy to Python dict
        let py_list = PyList::empty(py);
        for (agent_id, policy_config) in policies {
            let policy_dict = PyDict::new(py);
            policy_dict.set_item("agent_id", agent_id)?;

            // Convert PolicyConfig to Python dict
            let policy_config_dict = policy_config_to_py(py, &policy_config)?;
            policy_dict.set_item("policy_config", policy_config_dict)?;

            py_list.append(policy_dict)?;
        }

        Ok(py_list.into())
    }

    // ========================================================================
    // Checkpoint Save/Load (Sprint 2: FFI Boundary)
    // ========================================================================

    /// Save complete orchestrator state to JSON string
    ///
    /// Creates a checkpoint of the entire simulation state including:
    /// - Current tick and day
    /// - RNG seed state (for determinism)
    /// - All agent balances, queues, and settings
    /// - All transactions and their status
    /// - RTGS queue contents
    /// - Configuration hash (for validation)
    ///
    /// # Returns
    ///
    /// JSON string containing complete state snapshot
    ///
    /// # Errors
    ///
    /// Raises RuntimeError if:
    /// - State validation fails (balance conservation violated)
    /// - JSON serialization fails
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// orch = Orchestrator.new(config)
    /// for _ in range(10):
    ///     orch.tick()
    ///
    /// # Save state
    /// state_json = orch.save_state()
    ///
    /// # Write to file or database
    /// with open("checkpoint.json", "w") as f:
    ///     f.write(state_json)
    /// ```
    fn save_state(&self) -> PyResult<String> {
        self.inner.save_state().map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to save state: {}",
                e
            ))
        })
    }

    /// Load orchestrator from saved state JSON
    ///
    /// Restores a complete simulation from a previously saved checkpoint.
    /// The configuration must match the original configuration used to create
    /// the checkpoint (verified via SHA256 hash).
    ///
    /// # Arguments
    ///
    /// * `config` - Configuration dictionary (must match original config)
    /// * `state_json` - JSON string from previous save_state() call
    ///
    /// # Returns
    ///
    /// New Orchestrator instance restored to the saved state
    ///
    /// # Errors
    ///
    /// Raises RuntimeError if:
    /// - Config hash mismatch (config doesn't match checkpoint)
    /// - JSON deserialization fails
    /// - State validation fails (invariants violated)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// # Load from file
    /// with open("checkpoint.json", "r") as f:
    ///     state_json = f.read()
    ///
    /// # Restore orchestrator
    /// orch = Orchestrator.load_state(config, state_json)
    ///
    /// # Continue simulation
    /// result = orch.tick()
    /// ```
    #[staticmethod]
    fn load_state(config: &Bound<'_, PyDict>, state_json: &str) -> PyResult<Self> {
        let rust_config = parse_orchestrator_config(config)?;

        let inner = RustOrchestrator::load_state(rust_config, state_json).map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                "Failed to load state: {}",
                e
            ))
        })?;

        Ok(PyOrchestrator { inner })
    }

    /// Get checkpoint metadata without deserializing entire state
    ///
    /// Quickly extract key information from a checkpoint JSON without
    /// fully loading the orchestrator. Useful for checkpoint management
    /// and diagnostics.
    ///
    /// # Arguments
    ///
    /// * `state_json` - JSON string from save_state()
    ///
    /// # Returns
    ///
    /// Dictionary containing:
    /// - `current_tick`: Tick number when checkpoint was created
    /// - `current_day`: Day number when checkpoint was created
    /// - `rng_seed`: RNG state at checkpoint time
    /// - `config_hash`: SHA256 hash of configuration
    /// - `num_agents`: Number of agents in simulation
    /// - `num_transactions`: Number of active transactions
    ///
    /// # Errors
    ///
    /// Raises RuntimeError if JSON is invalid or missing required fields
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// # List checkpoints in database
    /// for checkpoint_id, state_json in checkpoints:
    ///     info = Orchestrator.get_checkpoint_info(state_json)
    ///     print(f"Checkpoint {checkpoint_id}: tick={info['current_tick']}, agents={info['num_agents']}")
    /// ```
    #[staticmethod]
    fn get_checkpoint_info(py: Python, state_json: &str) -> PyResult<Py<PyDict>> {
        // Parse JSON to extract metadata
        let snapshot: crate::orchestrator::checkpoint::StateSnapshot =
            serde_json::from_str(state_json).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!(
                    "Failed to parse checkpoint JSON: {}",
                    e
                ))
            })?;

        // Create Python dict with metadata
        let info_dict = PyDict::new(py);
        info_dict.set_item("current_tick", snapshot.current_tick)?;
        info_dict.set_item("current_day", snapshot.current_day)?;
        info_dict.set_item("rng_seed", snapshot.rng_seed)?;
        info_dict.set_item("config_hash", snapshot.config_hash)?;
        info_dict.set_item("num_agents", snapshot.agents.len())?;
        info_dict.set_item("num_transactions", snapshot.transactions.len())?;

        Ok(info_dict.into())
    }

    /// Get collateral events for a specific day (Phase 10: Collateral Event Tracking)
    ///
    /// Returns all collateral management events that occurred during the specified day,
    /// including strategic layer decisions and end-of-tick automatic postings.
    ///
    /// # Arguments
    ///
    /// * `day` - Day number (0-indexed)
    ///
    /// # Returns
    ///
    /// List of dictionaries, each containing:
    /// - `simulation_id`: Simulation identifier
    /// - `agent_id`: Agent that made the decision
    /// - `tick`: Tick when event occurred
    /// - `day`: Day when event occurred
    /// - `action`: Action taken ("post", "withdraw", or "hold")
    /// - `amount`: Amount of collateral involved (i64 cents)
    /// - `reason`: Reason for the action
    /// - `layer`: Decision layer ("strategic" or "end_of_tick")
    /// - `balance_before`: Agent balance before action
    /// - `posted_collateral_before`: Posted collateral before action
    /// - `posted_collateral_after`: Posted collateral after action
    /// - `available_capacity_after`: Remaining capacity after action
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// collateral_events = orch.get_collateral_events_for_day(0)
    ///
    /// # Convert to Polars DataFrame
    /// import polars as pl
    /// df = pl.DataFrame(collateral_events)
    ///
    /// # Write to DuckDB
    /// conn.execute("INSERT INTO collateral_events SELECT * FROM df")
    /// ```
    fn get_collateral_events_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
        // Get events from Rust orchestrator
        let events = self.inner.get_collateral_events_for_day(day);

        // Get simulation ID for conversion
        let simulation_id = self.inner.simulation_id();

        // Convert each event to Python dict
        let py_list = PyList::empty(py);
        for event in events {
            let event_dict = collateral_event_to_py(py, &event, &simulation_id)?;
            py_list.append(event_dict)?;
        }

        Ok(py_list.into())
    }

    /// Get accumulated costs for a specific agent
    ///
    /// Returns cost breakdown including:
    /// - Liquidity cost (overdraft)
    /// - Collateral opportunity cost
    /// - Delay cost (Queue 1)
    /// - Split friction cost
    /// - Deadline penalties
    ///
    /// All costs are in cents (i64).
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Dictionary with cost breakdown:
    /// - `liquidity_cost`: Overdraft cost (cents)
    /// - `collateral_cost`: Collateral opportunity cost (cents)
    /// - `delay_cost`: Queue delay cost (cents)
    /// - `split_friction_cost`: Transaction splitting cost (cents)
    /// - `deadline_penalty`: Deadline miss penalties (cents)
    /// - `total_cost`: Sum of all costs (cents)
    ///
    /// # Errors
    ///
    /// Raises KeyError if agent_id not found
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// costs = orch.get_agent_accumulated_costs("BANK_A")
    /// print(f"Total cost: ${costs['total_cost'] / 100:.2f}")
    /// print(f"Liquidity: ${costs['liquidity_cost'] / 100:.2f}")
    /// ```
    fn get_agent_accumulated_costs(&self, py: Python, agent_id: String) -> PyResult<Py<PyDict>> {
        let costs = self.inner.get_costs(&agent_id).ok_or_else(|| {
            pyo3::exceptions::PyKeyError::new_err(format!("Agent not found: {}", agent_id))
        })?;

        let dict = PyDict::new(py);
        dict.set_item("liquidity_cost", costs.total_liquidity_cost)?;
        dict.set_item("collateral_cost", costs.total_collateral_cost)?;
        dict.set_item("delay_cost", costs.total_delay_cost)?;
        dict.set_item("split_friction_cost", costs.total_split_friction_cost)?;
        dict.set_item("deadline_penalty", costs.total_penalty_cost)?;
        dict.set_item("total_cost", costs.total())?;

        Ok(dict.into())
    }

    /// Get comprehensive system-wide metrics
    ///
    /// Returns snapshot of current simulation health including:
    /// - Settlement performance (rate, delays)
    /// - Queue statistics
    /// - Liquidity usage (overdrafts)
    ///
    /// # Returns
    ///
    /// Dictionary with system metrics:
    /// - `total_arrivals`: Total transactions arrived
    /// - `total_settlements`: Total transactions settled
    /// - `settlement_rate`: Settlements / arrivals (0.0-1.0)
    /// - `avg_delay_ticks`: Average settlement delay in ticks
    /// - `max_delay_ticks`: Maximum delay observed
    /// - `queue1_total_size`: Total transactions in agent queues
    /// - `queue2_total_size`: Total transactions in RTGS queue
    /// - `peak_overdraft`: Largest overdraft across all agents (cents)
    /// - `agents_in_overdraft`: Number of agents with negative balance
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// metrics = orch.get_system_metrics()
    /// print(f"Settlement rate: {metrics['settlement_rate']:.1%}")
    /// print(f"Avg delay: {metrics['avg_delay_ticks']:.1f} ticks")
    /// print(f"Agents in overdraft: {metrics['agents_in_overdraft']}")
    /// ```
    fn get_system_metrics(&self, py: Python) -> PyResult<Py<PyDict>> {
        let metrics = self.inner.calculate_system_metrics();

        let dict = PyDict::new(py);
        dict.set_item("total_arrivals", metrics.total_arrivals)?;
        dict.set_item("total_settlements", metrics.total_settlements)?;
        dict.set_item("settlement_rate", metrics.settlement_rate)?;
        dict.set_item("avg_delay_ticks", metrics.avg_delay_ticks)?;
        dict.set_item("max_delay_ticks", metrics.max_delay_ticks)?;
        dict.set_item("queue1_total_size", metrics.queue1_total_size)?;
        dict.set_item("queue2_total_size", metrics.queue2_total_size)?;
        dict.set_item("peak_overdraft", metrics.peak_overdraft)?;
        dict.set_item("agents_in_overdraft", metrics.agents_in_overdraft)?;

        Ok(dict.into())
    }

    /// Get detailed transaction counts for debugging settlement rate issues
    ///
    /// Returns raw transaction counts to help diagnose settlement rate bugs.
    /// This bypasses the complex `is_effectively_settled()` recursion and provides
    /// direct counts of transactions by parent/child status.
    ///
    /// # Returns
    ///
    /// Dictionary with transaction counts:
    /// - `total_transactions`: Total number of transactions in the system
    /// - `arrivals`: Count of transactions with parent_id = None (original arrivals)
    /// - `children`: Count of transactions with parent_id set (split children)
    /// - `settled_arrivals`: Count of fully settled arrival transactions
    /// - `settled_children`: Count of fully settled child transactions
    ///
    /// # Debugging Notes
    ///
    /// This method is specifically designed to help diagnose the settlement rate > 100% bug.
    /// Expected invariants:
    /// - `total_transactions` should equal `arrivals + children`
    /// - Settlement rate should be `settled_arrivals / arrivals` (ideally <= 1.0)
    /// - If settlement rate > 1.0, check if parent_id is being set incorrectly
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// counts = orch.get_transaction_counts_debug()
    /// print(f"Total: {counts['total_transactions']}")
    /// print(f"Arrivals: {counts['arrivals']} (settled: {counts['settled_arrivals']})")
    /// print(f"Children: {counts['children']} (settled: {counts['settled_children']})")
    /// print(f"Manual rate: {counts['settled_arrivals'] / counts['arrivals']:.2%}")
    /// ```
    fn get_transaction_counts_debug(&self, py: Python) -> PyResult<Py<PyDict>> {
        let (total, arrivals, children, settled_arrivals, settled_children) =
            self.inner.get_transaction_counts_debug();

        let dict = PyDict::new(py);
        dict.set_item("total_transactions", total)?;
        dict.set_item("arrivals", arrivals)?;
        dict.set_item("children", children)?;
        dict.set_item("settled_arrivals", settled_arrivals)?;
        dict.set_item("settled_children", settled_children)?;

        Ok(dict.into())
    }

    // ========================================================================
    // Verbose CLI Query Methods (Enhanced Monitoring)
    // ========================================================================

    /// Get all events that occurred during a specific tick
    ///
    /// Returns detailed event log entries for arrivals, settlements,
    /// policy decisions, collateral actions, and LSM cycles.
    ///
    /// # Arguments
    ///
    /// * `tick` - Tick number to query
    ///
    /// # Returns
    ///
    /// List of event dictionaries with structure:
    /// - "event_type": str - Event type (Arrival, Settlement, PolicySubmit, etc.)
    /// - "tick": int - Tick number
    /// - Additional fields specific to event type
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// events = orch.get_tick_events(42)
    /// for event in events:
    ///     if event["event_type"] == "Arrival":
    ///         print(f"TX {event['tx_id']}: {event['sender_id']} → {event['receiver_id']}")
    /// ```
    fn get_tick_events(&self, py: Python, tick: usize) -> PyResult<Py<PyList>> {
        let events = self.inner.get_tick_events(tick);

        let py_list = PyList::empty(py);
        for event in events {
            let event_dict = event_to_py_dict(py, &event)?;
            py_list.append(&event_dict)?;
        }

        Ok(py_list.into())
    }

    /// Get all events from the event log
    ///
    /// Returns complete event history for the simulation.
    /// Used for database persistence and comprehensive analysis.
    ///
    /// # Returns
    ///
    /// List of event dictionaries, each containing:
    /// - `event_type`: Event type name (e.g., "Arrival", "Settlement")
    /// - `tick`: Tick when event occurred
    /// - Additional fields specific to each event type
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// events = orch.get_all_events()
    /// print(f"Total events: {len(events)}")
    /// for event in events[:10]:  # First 10 events
    ///     print(f"Tick {event['tick']}: {event['event_type']}")
    /// ```
    fn get_all_events(&self, py: Python) -> PyResult<Py<PyList>> {
        let events = self.inner.event_log().events();

        let py_list = PyList::empty(py);
        for event in events {
            let event_dict = event_to_py_dict(py, &event)?;
            py_list.append(&event_dict)?;
        }

        Ok(py_list.into())
    }

    /// Get full details for a specific transaction
    ///
    /// # Arguments
    ///
    /// * `tx_id` - Transaction identifier
    ///
    /// # Returns
    ///
    /// Dictionary with:
    /// - id: str
    /// - sender_id: str
    /// - receiver_id: str
    /// - amount: int (cents)
    /// - remaining_amount: int (cents)
    /// - arrival_tick: int
    /// - deadline_tick: int
    /// - priority: int (0-10)
    /// - status: str (Pending, Settled, etc.)
    ///
    /// Returns None if transaction not found.
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// tx = orch.get_transaction_details("tx_12345")
    /// if tx:
    ///     print(f"{tx['sender_id']} → {tx['receiver_id']}: ${tx['amount'] / 100:.2f}")
    /// ```
    fn get_transaction_details(&self, py: Python, tx_id: String) -> PyResult<Option<Py<PyDict>>> {
        if let Some(tx) = self.inner.get_transaction(&tx_id) {
            let dict = PyDict::new(py);
            dict.set_item("id", tx.id())?;
            dict.set_item("sender_id", tx.sender_id())?;
            dict.set_item("receiver_id", tx.receiver_id())?;
            dict.set_item("amount", tx.amount())?;
            dict.set_item("remaining_amount", tx.remaining_amount())?;
            dict.set_item("arrival_tick", tx.arrival_tick())?;
            dict.set_item("deadline_tick", tx.deadline_tick())?;
            dict.set_item("priority", tx.priority())?;

            // Convert status to string
            let status_str = match tx.status() {
                crate::models::transaction::TransactionStatus::Pending => "Pending",
                crate::models::transaction::TransactionStatus::PartiallySettled { .. } => "PartiallySettled",
                crate::models::transaction::TransactionStatus::Settled { .. } => "Settled",
                crate::models::transaction::TransactionStatus::Overdue { .. } => "Overdue",
            };
            dict.set_item("status", status_str)?;

            Ok(Some(dict.into()))
        } else {
            Ok(None)
        }
    }

    /// Get list of transaction IDs in RTGS queue (Queue 2)
    ///
    /// Returns transaction IDs in the central RTGS queue waiting
    /// for liquidity to become available.
    ///
    /// # Returns
    ///
    /// List of transaction IDs (strings) in queue order
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// rtgs_queue = orch.get_rtgs_queue_contents()
    /// print(f"RTGS Queue has {len(rtgs_queue)} transactions")
    /// ```
    fn get_rtgs_queue_contents(&self) -> Vec<String> {
        self.inner.get_rtgs_queue_contents()
    }

    /// Get agent's currently posted collateral
    ///
    /// Returns the amount of collateral currently posted by an agent.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Posted collateral in cents, or None if agent not found
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// collateral = orch.get_agent_collateral_posted("BANK_A")
    /// if collateral:
    ///     print(f"Collateral posted: ${collateral / 100:,.2f}")
    /// ```
    fn get_agent_collateral_posted(&self, agent_id: String) -> Option<i64> {
        self.inner.get_agent_collateral_posted(&agent_id)
    }

    /// Get agent's total allowed overdraft limit
    ///
    /// Returns the maximum negative balance an agent can have, calculated as:
    /// credit_limit + collateral-backed capacity + unsecured cap.
    ///
    /// This is the CORRECT denominator for credit utilization percentage calculations.
    ///
    /// # Arguments
    ///
    /// * `agent_id` - Agent identifier
    ///
    /// # Returns
    ///
    /// Total allowed overdraft in cents, or None if agent not found
    ///
    /// # Example
    ///
    /// ```python
    /// limit = orch.get_agent_allowed_overdraft_limit("BANK_A")
    /// balance = orch.get_agent_balance("BANK_A")
    /// used = max(0, -balance)
    /// utilization_pct = (used / limit) * 100
    /// print(f"Credit utilization: {utilization_pct:.1f}%")
    /// ```
    fn get_agent_allowed_overdraft_limit(&self, agent_id: String) -> Option<i64> {
        self.inner.get_agent_allowed_overdraft_limit(&agent_id)
    }

    /// Get transactions approaching their deadline
    ///
    /// Returns transactions that will go overdue within the specified number of ticks.
    /// Used for early warning displays in verbose output.
    ///
    /// # Arguments
    ///
    /// * `within_ticks` - Number of ticks ahead to check (e.g., 2 for "within 2 ticks")
    ///
    /// # Returns
    ///
    /// List of transaction dictionaries for transactions approaching deadline.
    /// Only includes transactions that are not yet overdue.
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    /// for tx in near_deadline:
    ///     print(f"TX {tx['tx_id']} will be overdue in {tx['deadline_tick'] - orch.current_tick()} ticks")
    /// ```
    fn get_transactions_near_deadline(&self, py: Python, within_ticks: usize) -> PyResult<PyObject> {
        let current_tick = self.inner.current_tick();
        let threshold = current_tick + within_ticks;

        let py_list = PyList::empty(py);

        // Iterate through all transactions
        for tx in self.inner.state().transactions().values() {
            // Skip if already settled or overdue
            if tx.is_fully_settled() || tx.is_overdue() {
                continue;
            }

            // Check if deadline is within threshold
            if tx.deadline_tick() <= threshold && tx.deadline_tick() >= current_tick {
                let tx_dict = PyDict::new(py);
                tx_dict.set_item("tx_id", tx.id())?;
                tx_dict.set_item("sender_id", tx.sender_id())?;
                tx_dict.set_item("receiver_id", tx.receiver_id())?;
                tx_dict.set_item("amount", tx.amount())?;
                tx_dict.set_item("remaining_amount", tx.remaining_amount())?;
                tx_dict.set_item("deadline_tick", tx.deadline_tick())?;
                tx_dict.set_item("ticks_until_deadline", tx.deadline_tick() as i64 - current_tick as i64)?;

                py_list.append(tx_dict)?;
            }
        }

        Ok(py_list.into())
    }

    /// Get all currently overdue transactions with cost data
    ///
    /// Returns all transactions that are currently overdue (past their deadline).
    /// Includes calculated cost information for each transaction.
    ///
    /// # Returns
    ///
    /// List of transaction dictionaries with overdue cost calculations:
    /// - Standard transaction fields (tx_id, sender_id, etc.)
    /// - `ticks_overdue`: How many ticks past deadline
    /// - `estimated_delay_cost`: Accumulated delay costs while overdue
    /// - `deadline_penalty_cost`: One-time penalty when became overdue
    /// - `total_overdue_cost`: Total cost (penalty + delay)
    ///
    /// # Example (from Python)
    ///
    /// ```python
    /// overdue = orch.get_overdue_transactions()
    /// for tx in overdue:
    ///     print(f"TX {tx['tx_id']} overdue for {tx['ticks_overdue']} ticks, cost: ${tx['total_overdue_cost'] / 100:.2f}")
    /// ```
    fn get_overdue_transactions(&self, py: Python) -> PyResult<PyObject> {
        let current_tick = self.inner.current_tick();
        // Access cost_rates via getter method
        let cost_rates = self.inner.cost_rates();

        let py_list = PyList::empty(py);

        // Iterate through all transactions
        for tx in self.inner.state().transactions().values() {
            // Only include overdue transactions that are not yet fully settled
            if !tx.is_overdue() || tx.is_fully_settled() {
                continue;
            }

            let tx_dict = PyDict::new(py);
            tx_dict.set_item("tx_id", tx.id())?;
            tx_dict.set_item("sender_id", tx.sender_id())?;
            tx_dict.set_item("receiver_id", tx.receiver_id())?;
            tx_dict.set_item("amount", tx.amount())?;
            tx_dict.set_item("remaining_amount", tx.remaining_amount())?;
            tx_dict.set_item("deadline_tick", tx.deadline_tick())?;

            // Add overdue-specific fields
            if let Some(overdue_since) = tx.overdue_since_tick() {
                let ticks_overdue = current_tick - overdue_since;
                tx_dict.set_item("overdue_since_tick", overdue_since)?;
                tx_dict.set_item("ticks_overdue", ticks_overdue)?;

                // Estimate accumulated delay cost
                let delay_cost = (tx.remaining_amount() as f64
                    * cost_rates.delay_cost_per_tick_per_cent
                    * cost_rates.overdue_delay_multiplier
                    * ticks_overdue as f64)
                    .round() as i64;

                tx_dict.set_item("estimated_delay_cost", delay_cost)?;
                tx_dict.set_item("deadline_penalty_cost", cost_rates.deadline_penalty)?;

                let total_cost = cost_rates.deadline_penalty + delay_cost;
                tx_dict.set_item("total_overdue_cost", total_cost)?;
            }

            py_list.append(tx_dict)?;
        }

        Ok(py_list.into())
    }
}
