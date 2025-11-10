//! Type conversion utilities for FFI boundary
//!
//! Converts between Rust types and PyO3-compatible types (PyDict, PyList, etc.)

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

use crate::arrivals::{AmountDistribution, ArrivalConfig};
use crate::events::{EventSchedule, ScenarioEvent, ScheduledEvent};
use crate::orchestrator::{AgentConfig, CostRates, OrchestratorConfig, PolicyConfig, TickResult};
use crate::settlement::lsm::LsmConfig;

/// Convert Python dict to OrchestratorConfig
///
/// # Errors
///
/// Returns PyErr if:
/// - Required fields missing
/// - Type conversions fail
/// - Values out of valid range
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    // Extract required fields with validation
    let ticks_per_day: usize = py_config
        .get_item("ticks_per_day")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'ticks_per_day'"))?
        .extract()?;

    if ticks_per_day == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "ticks_per_day must be positive",
        ));
    }

    let num_days: usize = py_config
        .get_item("num_days")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'num_days'"))?
        .extract()?;

    let rng_seed: u64 = py_config
        .get_item("rng_seed")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'rng_seed'"))?
        .extract()?;

    // Parse agent configs
    let py_agents: Bound<'_, PyList> = py_config
        .get_item("agent_configs")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'agent_configs'"))?
        .downcast_into()?;

    let mut agent_configs = Vec::new();
    for py_agent in py_agents.iter() {
        let agent_dict: Bound<'_, PyDict> = py_agent.downcast_into()?;
        agent_configs.push(parse_agent_config(&agent_dict)?);
    }

    // Parse optional cost rates (use defaults if not provided)
    let cost_rates = if let Some(py_costs) = py_config.get_item("cost_rates")? {
        let costs_dict: Bound<'_, PyDict> = py_costs.downcast_into()?;
        parse_cost_rates(&costs_dict)?
    } else {
        CostRates::default()
    };

    // Parse optional LSM config (use defaults if not provided)
    let lsm_config = if let Some(py_lsm) = py_config.get_item("lsm_config")? {
        let lsm_dict: Bound<'_, PyDict> = py_lsm.downcast_into()?;
        parse_lsm_config(&lsm_dict)?
    } else {
        LsmConfig::default()
    };

    // Parse optional EOD rush threshold (default to 0.8 if not provided)
    let eod_rush_threshold = if let Some(py_threshold) = py_config.get_item("eod_rush_threshold")? {
        py_threshold.extract()?
    } else {
        0.8
    };

    // Parse optional scenario_events (default to None if not provided)
    let scenario_events = if let Some(py_events) = py_config.get_item("scenario_events")? {
        let events_list: Bound<'_, PyList> = py_events.downcast_into()?;
        Some(parse_scenario_events(&events_list)?)
    } else {
        None
    };

    Ok(OrchestratorConfig {
        ticks_per_day,
        eod_rush_threshold,
        num_days,
        rng_seed,
        agent_configs,
        cost_rates,
        lsm_config,
        scenario_events,
    })
}

/// Convert Python dict to AgentConfig
fn parse_agent_config(py_agent: &Bound<'_, PyDict>) -> PyResult<AgentConfig> {
    let id: String = py_agent
        .get_item("id")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'id'"))?
        .extract()?;

    let opening_balance: i64 = py_agent
        .get_item("opening_balance")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'opening_balance'")
        })?
        .extract()?;

    let credit_limit: i64 = py_agent
        .get_item("credit_limit")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'credit_limit'"))?
        .extract()?;

    // Parse policy config
    let py_policy: Bound<'_, PyDict> = py_agent
        .get_item("policy")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'policy'"))?
        .downcast_into()?;

    let policy = parse_policy_config(&py_policy)?;

    // Parse optional arrival config
    let arrival_config = if let Some(py_arrivals) = py_agent.get_item("arrival_config")? {
        let arrivals_dict: Bound<'_, PyDict> = py_arrivals.downcast_into()?;
        Some(parse_arrival_config(&arrivals_dict)?)
    } else {
        None
    };

    Ok(AgentConfig {
        id,
        opening_balance,
        credit_limit,
        policy,
        arrival_config,
        posted_collateral: None, // TODO: Parse from Python config if provided
    })
}

/// Convert Python dict to PolicyConfig
fn parse_policy_config(py_policy: &Bound<'_, PyDict>) -> PyResult<PolicyConfig> {
    let policy_type: String = py_policy
        .get_item("type")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing policy 'type'"))?
        .extract()?;

    match policy_type.as_str() {
        "Fifo" => Ok(PolicyConfig::Fifo),
        "Deadline" => {
            let urgency_threshold: usize = py_policy
                .get_item("urgency_threshold")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "Deadline policy requires 'urgency_threshold'",
                    )
                })?
                .extract()?;

            Ok(PolicyConfig::Deadline { urgency_threshold })
        }
        "LiquidityAware" => {
            let target_buffer: i64 = py_policy
                .get_item("target_buffer")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "LiquidityAware policy requires 'target_buffer'",
                    )
                })?
                .extract()?;

            let urgency_threshold: usize = py_policy
                .get_item("urgency_threshold")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "LiquidityAware policy requires 'urgency_threshold'",
                    )
                })?
                .extract()?;

            Ok(PolicyConfig::LiquidityAware {
                target_buffer,
                urgency_threshold,
            })
        }
        "LiquiditySplitting" => {
            let max_splits: usize = py_policy
                .get_item("max_splits")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "LiquiditySplitting policy requires 'max_splits'",
                    )
                })?
                .extract()?;

            let min_split_amount: i64 = py_policy
                .get_item("min_split_amount")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "LiquiditySplitting policy requires 'min_split_amount'",
                    )
                })?
                .extract()?;

            Ok(PolicyConfig::LiquiditySplitting {
                max_splits,
                min_split_amount,
            })
        }
        "MockSplitting" => {
            let num_splits: usize = py_policy
                .get_item("num_splits")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "MockSplitting policy requires 'num_splits'",
                    )
                })?
                .extract()?;

            Ok(PolicyConfig::MockSplitting { num_splits })
        }
        "FromJson" => {
            let json: String = py_policy
                .get_item("json")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "FromJson policy requires 'json' field with policy JSON string",
                    )
                })?
                .extract()?;

            Ok(PolicyConfig::FromJson { json })
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Unknown policy type: {}",
            policy_type
        ))),
    }
}

/// Convert PolicyConfig to Python dict
///
/// Reverse of parse_policy_config - converts Rust PolicyConfig enum
/// to Python dictionary format.
///
/// # Example
///
/// PolicyConfig::Fifo → {"type": "Fifo"}
/// PolicyConfig::LiquidityAware { target_buffer: 500000, urgency_threshold: 5 }
///   → {"type": "LiquidityAware", "target_buffer": 500000, "urgency_threshold": 5}
pub fn policy_config_to_py(py: Python, policy: &PolicyConfig) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    match policy {
        PolicyConfig::Fifo => {
            dict.set_item("type", "Fifo")?;
        }
        PolicyConfig::Deadline { urgency_threshold } => {
            dict.set_item("type", "Deadline")?;
            dict.set_item("urgency_threshold", urgency_threshold)?;
        }
        PolicyConfig::LiquidityAware {
            target_buffer,
            urgency_threshold,
        } => {
            dict.set_item("type", "LiquidityAware")?;
            dict.set_item("target_buffer", target_buffer)?;
            dict.set_item("urgency_threshold", urgency_threshold)?;
        }
        PolicyConfig::LiquiditySplitting {
            max_splits,
            min_split_amount,
        } => {
            dict.set_item("type", "LiquiditySplitting")?;
            dict.set_item("max_splits", max_splits)?;
            dict.set_item("min_split_amount", min_split_amount)?;
        }
        PolicyConfig::MockSplitting { num_splits } => {
            dict.set_item("type", "MockSplitting")?;
            dict.set_item("num_splits", num_splits)?;
        }
        PolicyConfig::FromJson { json } => {
            dict.set_item("type", "FromJson")?;
            dict.set_item("json", json)?;
        }
    }

    Ok(dict.into())
}

/// Convert Python dict to ArrivalConfig
fn parse_arrival_config(py_arrivals: &Bound<'_, PyDict>) -> PyResult<ArrivalConfig> {
    let rate_per_tick: f64 = py_arrivals
        .get_item("rate_per_tick")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'rate_per_tick'"))?
        .extract()?;

    let py_dist: Bound<'_, PyDict> = py_arrivals
        .get_item("amount_distribution")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'amount_distribution'")
        })?
        .downcast_into()?;

    let amount_distribution = parse_amount_distribution(&py_dist)?;

    // Parse counterparty weights
    let py_weights: Bound<'_, PyDict> = py_arrivals
        .get_item("counterparty_weights")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'counterparty_weights'")
        })?
        .downcast_into()?;

    let mut counterparty_weights = HashMap::new();
    for (key, value) in py_weights.iter() {
        let agent_id: String = key.extract()?;
        let weight: f64 = value.extract()?;
        counterparty_weights.insert(agent_id, weight);
    }

    // Parse deadline_range (tuple or list of 2 elements)
    let deadline_range: (usize, usize) =
        if let Some(range_item) = py_arrivals.get_item("deadline_range")? {
            let range_list: Vec<usize> = range_item.extract()?;
            if range_list.len() != 2 {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "deadline_range must have exactly 2 elements [min, max]",
                ));
            }
            (range_list[0], range_list[1])
        } else {
            (10, 50) // Default range
        };

    // Parse priority (default 5 if not provided)
    let priority: u8 = py_arrivals
        .get_item("priority")?
        .map(|v| v.extract())
        .transpose()?
        .unwrap_or(5);

    // Parse divisible (default false if not provided)
    let divisible: bool = py_arrivals
        .get_item("divisible")?
        .map(|v| v.extract())
        .transpose()?
        .unwrap_or(false);

    Ok(ArrivalConfig {
        rate_per_tick,
        amount_distribution,
        counterparty_weights,
        deadline_range,
        priority,
        divisible,
    })
}

/// Convert Python dict to AmountDistribution
fn parse_amount_distribution(py_dist: &Bound<'_, PyDict>) -> PyResult<AmountDistribution> {
    let dist_type: String = py_dist
        .get_item("type")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing distribution 'type'")
        })?
        .extract()?;

    match dist_type.as_str() {
        "Normal" => {
            let mean: i64 = py_dist
                .get_item("mean")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Normal requires 'mean'")
                })?
                .extract()?;

            let std_dev: i64 = py_dist
                .get_item("std_dev")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Normal requires 'std_dev'")
                })?
                .extract()?;

            Ok(AmountDistribution::Normal { mean, std_dev })
        }
        "LogNormal" => {
            let mean: f64 = py_dist
                .get_item("mean")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("LogNormal requires 'mean'")
                })?
                .extract()?;

            let std_dev: f64 = py_dist
                .get_item("std_dev")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("LogNormal requires 'std_dev'")
                })?
                .extract()?;

            Ok(AmountDistribution::LogNormal { mean, std_dev })
        }
        "Uniform" => {
            let min: i64 = py_dist
                .get_item("min")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform requires 'min'")
                })?
                .extract()?;

            let max: i64 = py_dist
                .get_item("max")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform requires 'max'")
                })?
                .extract()?;

            Ok(AmountDistribution::Uniform { min, max })
        }
        "Exponential" => {
            let rate: f64 = py_dist
                .get_item("lambda")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Exponential requires 'lambda'")
                })?
                .extract()?;

            Ok(AmountDistribution::Exponential { rate })
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Unknown distribution type: {}",
            dist_type
        ))),
    }
}

/// Convert Python dict to CostRates
fn parse_cost_rates(py_costs: &Bound<'_, PyDict>) -> PyResult<CostRates> {
    Ok(CostRates {
        overdraft_bps_per_tick: py_costs
            .get_item("overdraft_bps_per_tick")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(0.001),

        delay_cost_per_tick_per_cent: py_costs
            .get_item("delay_cost_per_tick_per_cent")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(0.0001),

        collateral_cost_per_tick_bps: py_costs
            .get_item("collateral_cost_per_tick_bps")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(0.0002),

        eod_penalty_per_transaction: py_costs
            .get_item("eod_penalty_per_transaction")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(10_000),

        deadline_penalty: py_costs
            .get_item("deadline_penalty")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(50_000),

        split_friction_cost: py_costs
            .get_item("split_friction_cost")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(1000),

        // Phase 3: Overdue delay cost multiplier
        overdue_delay_multiplier: py_costs
            .get_item("overdue_delay_multiplier")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(5.0), // Default: 5x penalty for overdue transactions
    })
}

/// Convert Python dict to LsmConfig
fn parse_lsm_config(py_lsm: &Bound<'_, PyDict>) -> PyResult<LsmConfig> {
    Ok(LsmConfig {
        enable_bilateral: py_lsm
            .get_item("enable_bilateral")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(true),

        enable_cycles: py_lsm
            .get_item("enable_cycles")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(true),

        max_cycle_length: py_lsm
            .get_item("max_cycle_length")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(4),

        max_cycles_per_tick: py_lsm
            .get_item("max_cycles_per_tick")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(10),
    })
}

/// Convert TickResult to Python dict
pub fn tick_result_to_py(py: Python, result: &TickResult) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    dict.set_item("tick", result.tick)?;
    dict.set_item("num_arrivals", result.num_arrivals)?;
    dict.set_item("num_settlements", result.num_settlements)?;
    dict.set_item("num_lsm_releases", result.num_lsm_releases)?;
    dict.set_item("total_cost", result.total_cost)?;

    Ok(dict.into())
}

/// Convert Transaction to Python dict
///
/// Converts a Rust Transaction to a Python dict matching the TransactionRecord Pydantic model.
/// This is used for persistence to DuckDB.
///
/// # Arguments
///
/// * `py` - Python context
/// * `tx` - Transaction to convert
/// * `simulation_id` - Simulation ID for this transaction
/// * `ticks_per_day` - Ticks per day for day calculation
///
/// # Returns
///
/// Python dict with all fields required by TransactionRecord Pydantic model
pub fn transaction_to_py(
    py: Python,
    tx: &crate::models::Transaction,
    simulation_id: &str,
    ticks_per_day: usize,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    // Identity
    dict.set_item("simulation_id", simulation_id)?;
    dict.set_item("tx_id", tx.id())?;

    // Participants
    dict.set_item("sender_id", tx.sender_id())?;
    dict.set_item("receiver_id", tx.receiver_id())?;

    // Transaction details
    dict.set_item("amount", tx.amount())?;
    dict.set_item("priority", tx.priority())?;
    dict.set_item("is_divisible", false)?; // TODO: Store divisibility in Transaction

    // Lifecycle timing
    let arrival_tick = tx.arrival_tick();
    dict.set_item("arrival_tick", arrival_tick)?;
    dict.set_item("arrival_day", arrival_tick / ticks_per_day)?;
    dict.set_item("deadline_tick", tx.deadline_tick())?;

    // Settlement timing (if settled)
    match tx.status() {
        crate::models::TransactionStatus::Settled { tick } => {
            dict.set_item("settlement_tick", tick)?;
            dict.set_item("settlement_day", tick / ticks_per_day)?;
        }
        _ => {
            dict.set_item("settlement_tick", py.None())?;
            dict.set_item("settlement_day", py.None())?;
        }
    }

    // Status (Phase 5: Updated for Overdue status)
    let status_str = match tx.status() {
        crate::models::TransactionStatus::Pending => "pending",
        crate::models::TransactionStatus::PartiallySettled { .. } => "settled", // Map partially settled to settled
        crate::models::TransactionStatus::Settled { .. } => "settled",
        crate::models::TransactionStatus::Overdue { .. } => "overdue", // Phase 5: New overdue status
    };
    dict.set_item("status", status_str)?;

    // Overdue timing (Phase 5: Track when transaction became overdue)
    match tx.status() {
        crate::models::TransactionStatus::Overdue { missed_deadline_tick } => {
            dict.set_item("overdue_since_tick", missed_deadline_tick)?;
        }
        _ => {
            dict.set_item("overdue_since_tick", py.None())?;
        }
    }

    // Drop reason (deprecated - kept for backward compatibility)
    dict.set_item("drop_reason", py.None())?;

    // Settlement tracking
    dict.set_item("amount_settled", tx.settled_amount())?;

    // Metrics (TODO: Track these in Transaction struct)
    dict.set_item("queue1_ticks", 0)?;
    dict.set_item("queue2_ticks", 0)?;
    dict.set_item("total_delay_ticks", 0)?;

    // Costs (TODO: Track these in Transaction struct)
    dict.set_item("delay_cost", 0)?;

    // Splitting
    if let Some(parent_id) = tx.parent_id() {
        dict.set_item("parent_tx_id", parent_id)?;
    } else {
        dict.set_item("parent_tx_id", py.None())?;
    }
    dict.set_item("split_index", py.None())?; // TODO: Track split index in Transaction

    Ok(dict.into())
}

/// Convert DailyMetrics to Python dict (Phase 3: Agent Metrics Collection)
///
/// Maps all fields from DailyMetrics to Python dict matching
/// the DailyAgentMetricsRecord Pydantic schema.
///
/// # Arguments
///
/// * `py` - Python interpreter handle
/// * `metrics` - Daily metrics to convert
/// * `simulation_id` - Simulation identifier
///
/// # Returns
///
/// PyDict with all fields from DailyAgentMetricsRecord
pub fn agent_metrics_to_py(
    py: Python,
    metrics: &crate::orchestrator::DailyMetrics,
    simulation_id: &str,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    // Identity
    dict.set_item("simulation_id", simulation_id)?;
    dict.set_item("agent_id", &metrics.agent_id)?;
    dict.set_item("day", metrics.day)?;

    // Balance metrics
    dict.set_item("opening_balance", metrics.opening_balance)?;
    dict.set_item("closing_balance", metrics.closing_balance)?;
    dict.set_item("min_balance", metrics.min_balance)?;
    dict.set_item("max_balance", metrics.max_balance)?;

    // Credit usage
    dict.set_item("credit_limit", metrics.credit_limit)?;
    dict.set_item("peak_overdraft", metrics.peak_overdraft)?;

    // Collateral management (Phase 8)
    dict.set_item(
        "opening_posted_collateral",
        metrics.opening_posted_collateral,
    )?;
    dict.set_item(
        "closing_posted_collateral",
        metrics.closing_posted_collateral,
    )?;
    dict.set_item("peak_posted_collateral", metrics.peak_posted_collateral)?;
    dict.set_item("collateral_capacity", metrics.collateral_capacity)?;
    dict.set_item("num_collateral_posts", metrics.num_collateral_posts)?;
    dict.set_item(
        "num_collateral_withdrawals",
        metrics.num_collateral_withdrawals,
    )?;

    // Transaction counts
    dict.set_item("num_arrivals", metrics.num_arrivals)?;
    dict.set_item("num_sent", metrics.num_sent)?;
    dict.set_item("num_received", metrics.num_received)?;
    dict.set_item("num_settled", metrics.num_settled)?;
    dict.set_item("num_dropped", metrics.num_dropped)?;

    // Queue metrics
    dict.set_item("queue1_peak_size", metrics.queue1_peak_size)?;
    dict.set_item("queue1_eod_size", metrics.queue1_eod_size)?;

    // Costs
    dict.set_item("liquidity_cost", metrics.liquidity_cost)?;
    dict.set_item("delay_cost", metrics.delay_cost)?;
    dict.set_item("collateral_cost", metrics.collateral_cost)?;
    dict.set_item("split_friction_cost", metrics.split_friction_cost)?;
    dict.set_item("deadline_penalty_cost", metrics.deadline_penalty_cost)?;
    dict.set_item("total_cost", metrics.total_cost)?;

    Ok(dict.into())
}

/// Convert CollateralEvent to Python dict
///
/// Maps Rust CollateralEvent struct to Python dict with snake_case keys
/// matching the Pydantic CollateralEventRecord schema.
///
/// # Arguments
///
/// * `py` - Python GIL token
/// * `event` - CollateralEvent to convert
/// * `simulation_id` - Simulation identifier
///
/// # Returns
///
/// PyDict with collateral event data
pub fn collateral_event_to_py(
    py: Python,
    event: &crate::models::CollateralEvent,
    simulation_id: &str,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    dict.set_item("simulation_id", simulation_id)?;
    dict.set_item("agent_id", &event.agent_id)?;
    dict.set_item("tick", event.tick)?;
    dict.set_item("day", event.day)?;

    // Convert enum to string
    let action_str = match event.action {
        crate::models::CollateralAction::Post => "post",
        crate::models::CollateralAction::Withdraw => "withdraw",
        crate::models::CollateralAction::Hold => "hold",
    };
    dict.set_item("action", action_str)?;

    dict.set_item("amount", event.amount)?;
    dict.set_item("reason", &event.reason)?;

    // Convert enum to string
    let layer_str = match event.layer {
        crate::models::CollateralLayer::Strategic => "strategic",
        crate::models::CollateralLayer::EndOfTick => "end_of_tick",
    };
    dict.set_item("layer", layer_str)?;

    dict.set_item("balance_before", event.balance_before)?;
    dict.set_item("posted_collateral_before", event.posted_collateral_before)?;
    dict.set_item("posted_collateral_after", event.posted_collateral_after)?;
    dict.set_item("available_capacity_after", event.available_capacity_after)?;

    Ok(dict.into())
}

/// Parse scenario events from Python list
///
/// Converts a Python list of event dicts to a vector of ScheduledEvent.
///
/// # Errors
///
/// Returns PyErr if:
/// - Event type is invalid
/// - Required fields are missing
/// - Schedule type is invalid
fn parse_scenario_events(py_events: &Bound<'_, PyList>) -> PyResult<Vec<ScheduledEvent>> {
    let mut events = Vec::new();

    for py_event in py_events.iter() {
        let event_dict: Bound<'_, PyDict> = py_event.downcast_into()?;

        // Parse event type
        let event_type: String = event_dict
            .get_item("type")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing event 'type'"))?
            .extract()?;

        // Parse schedule
        let schedule_type: String = event_dict
            .get_item("schedule")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'schedule'"))?
            .extract()?;

        let schedule = match schedule_type.as_str() {
            "OneTime" => {
                let tick: usize = event_dict
                    .get_item("tick")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "OneTime schedule requires 'tick'"
                    ))?
                    .extract()?;
                EventSchedule::OneTime { tick }
            }
            "Repeating" => {
                let start_tick: usize = event_dict
                    .get_item("start_tick")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "Repeating schedule requires 'start_tick'"
                    ))?
                    .extract()?;
                let interval: usize = event_dict
                    .get_item("interval")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "Repeating schedule requires 'interval'"
                    ))?
                    .extract()?;
                EventSchedule::Repeating { start_tick, interval }
            }
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid schedule type: {}. Must be 'OneTime' or 'Repeating'",
                    schedule_type
                )));
            }
        };

        // Parse event based on type
        let event = match event_type.as_str() {
            "DirectTransfer" => {
                let from_agent: String = event_dict
                    .get_item("from_agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "DirectTransfer requires 'from_agent'"
                    ))?
                    .extract()?;
                let to_agent: String = event_dict
                    .get_item("to_agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "DirectTransfer requires 'to_agent'"
                    ))?
                    .extract()?;
                let amount: i64 = event_dict
                    .get_item("amount")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "DirectTransfer requires 'amount'"
                    ))?
                    .extract()?;

                ScenarioEvent::DirectTransfer {
                    from_agent,
                    to_agent,
                    amount,
                }
            }
            "CollateralAdjustment" => {
                let agent: String = event_dict
                    .get_item("agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CollateralAdjustment requires 'agent'"
                    ))?
                    .extract()?;
                let delta: i64 = event_dict
                    .get_item("delta")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CollateralAdjustment requires 'delta'"
                    ))?
                    .extract()?;

                ScenarioEvent::CollateralAdjustment { agent, delta }
            }
            "GlobalArrivalRateChange" => {
                let multiplier: f64 = event_dict
                    .get_item("multiplier")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "GlobalArrivalRateChange requires 'multiplier'"
                    ))?
                    .extract()?;

                ScenarioEvent::GlobalArrivalRateChange { multiplier }
            }
            "AgentArrivalRateChange" => {
                let agent: String = event_dict
                    .get_item("agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "AgentArrivalRateChange requires 'agent'"
                    ))?
                    .extract()?;
                let multiplier: f64 = event_dict
                    .get_item("multiplier")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "AgentArrivalRateChange requires 'multiplier'"
                    ))?
                    .extract()?;

                ScenarioEvent::AgentArrivalRateChange { agent, multiplier }
            }
            "CounterpartyWeightChange" => {
                let agent: String = event_dict
                    .get_item("agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CounterpartyWeightChange requires 'agent'"
                    ))?
                    .extract()?;
                let counterparty: String = event_dict
                    .get_item("counterparty")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CounterpartyWeightChange requires 'counterparty'"
                    ))?
                    .extract()?;
                let new_weight: f64 = event_dict
                    .get_item("new_weight")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CounterpartyWeightChange requires 'new_weight'"
                    ))?
                    .extract()?;
                let auto_balance_others: bool = if let Some(abo) = event_dict.get_item("auto_balance_others")? {
                    abo.extract()?
                } else {
                    false
                };

                ScenarioEvent::CounterpartyWeightChange {
                    agent,
                    counterparty,
                    new_weight,
                    auto_balance_others,
                }
            }
            "DeadlineWindowChange" => {
                let min_ticks_multiplier: Option<f64> = event_dict
                    .get_item("min_ticks_multiplier")?
                    .map(|v| v.extract())
                    .transpose()?;
                let max_ticks_multiplier: Option<f64> = event_dict
                    .get_item("max_ticks_multiplier")?
                    .map(|v| v.extract())
                    .transpose()?;

                ScenarioEvent::DeadlineWindowChange {
                    min_ticks_multiplier,
                    max_ticks_multiplier,
                }
            }
            _ => {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Invalid event type: {}",
                    event_type
                )));
            }
        };

        events.push(ScheduledEvent { event, schedule });
    }

    Ok(events)
}
