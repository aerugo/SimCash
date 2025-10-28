//! Type conversion utilities for FFI boundary
//!
//! Converts between Rust types and PyO3-compatible types (PyDict, PyList, etc.)

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

use crate::arrivals::{AmountDistribution, ArrivalConfig};
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
            "ticks_per_day must be positive"
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

    Ok(OrchestratorConfig {
        ticks_per_day,
        num_days,
        rng_seed,
        agent_configs,
        cost_rates,
        lsm_config,
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
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'opening_balance'"))?
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
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Deadline policy requires 'urgency_threshold'"
                ))?
                .extract()?;

            Ok(PolicyConfig::Deadline { urgency_threshold })
        }
        "LiquidityAware" => {
            let target_buffer: i64 = py_policy
                .get_item("target_buffer")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "LiquidityAware policy requires 'target_buffer'"
                ))?
                .extract()?;

            let urgency_threshold: usize = py_policy
                .get_item("urgency_threshold")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "LiquidityAware policy requires 'urgency_threshold'"
                ))?
                .extract()?;

            Ok(PolicyConfig::LiquidityAware {
                target_buffer,
                urgency_threshold,
            })
        }
        "LiquiditySplitting" => {
            let max_splits: usize = py_policy
                .get_item("max_splits")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "LiquiditySplitting policy requires 'max_splits'"
                ))?
                .extract()?;

            let min_split_amount: i64 = py_policy
                .get_item("min_split_amount")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "LiquiditySplitting policy requires 'min_split_amount'"
                ))?
                .extract()?;

            Ok(PolicyConfig::LiquiditySplitting {
                max_splits,
                min_split_amount,
            })
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unknown policy type: {}", policy_type)
        )),
    }
}

/// Convert Python dict to ArrivalConfig
fn parse_arrival_config(py_arrivals: &Bound<'_, PyDict>) -> PyResult<ArrivalConfig> {
    let rate_per_tick: f64 = py_arrivals
        .get_item("rate_per_tick")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'rate_per_tick'"))?
        .extract()?;

    let py_dist: Bound<'_, PyDict> = py_arrivals
        .get_item("amount_distribution")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'amount_distribution'"))?
        .downcast_into()?;

    let amount_distribution = parse_amount_distribution(&py_dist)?;

    // Parse counterparty weights
    let py_weights: Bound<'_, PyDict> = py_arrivals
        .get_item("counterparty_weights")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'counterparty_weights'"))?
        .downcast_into()?;

    let mut counterparty_weights = HashMap::new();
    for (key, value) in py_weights.iter() {
        let agent_id: String = key.extract()?;
        let weight: f64 = value.extract()?;
        counterparty_weights.insert(agent_id, weight);
    }

    // Parse deadline_range (tuple or list of 2 elements)
    let deadline_range: (usize, usize) = if let Some(range_item) = py_arrivals.get_item("deadline_range")? {
        let range_list: Vec<usize> = range_item.extract()?;
        if range_list.len() != 2 {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "deadline_range must have exactly 2 elements [min, max]"
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
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing distribution 'type'"))?
        .extract()?;

    match dist_type.as_str() {
        "Normal" => {
            let mean: i64 = py_dist.get_item("mean")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("Normal requires 'mean'")
            )?.extract()?;

            let std_dev: i64 = py_dist.get_item("std_dev")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("Normal requires 'std_dev'")
            )?.extract()?;

            Ok(AmountDistribution::Normal { mean, std_dev })
        }
        "LogNormal" => {
            let mean: f64 = py_dist.get_item("mean")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("LogNormal requires 'mean'")
            )?.extract()?;

            let std_dev: f64 = py_dist.get_item("std_dev")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("LogNormal requires 'std_dev'")
            )?.extract()?;

            Ok(AmountDistribution::LogNormal { mean, std_dev })
        }
        "Uniform" => {
            let min: i64 = py_dist.get_item("min")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform requires 'min'")
            )?.extract()?;

            let max: i64 = py_dist.get_item("max")?.ok_or_else(||
                PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform requires 'max'")
            )?.extract()?;

            Ok(AmountDistribution::Uniform { min, max })
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            format!("Unknown distribution type: {}", dist_type)
        )),
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
