//! Type conversion utilities for FFI boundary
//!
//! Converts between Rust types and PyO3-compatible types (PyDict, PyList, etc.)

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

use crate::arrivals::{AmountDistribution, ArrivalBandConfig, ArrivalBandsConfig, ArrivalConfig, PriorityDistribution};
use crate::events::{EventSchedule, ScenarioEvent, ScheduledEvent};
use crate::orchestrator::{AgentConfig, AgentLimitsConfig, CostRates, OrchestratorConfig, PolicyConfig, PriorityDelayMultipliers, PriorityEscalationConfig, Queue1Ordering, TickResult};
use crate::settlement::lsm::LsmConfig;

// ========================================================================
// PyDict Extraction Helpers (DRY Pattern)
// ========================================================================

/// Extract a required field from a Python dict with clear error messages.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `key` - Field name to extract
///
/// # Returns
/// Extracted value of type T
///
/// # Errors
/// Returns PyValueError if:
/// - Field is missing
/// - Type conversion fails
///
/// # Example
/// ```ignore
/// let value: i64 = extract_required(&py_dict, "balance")?;
/// ```
fn extract_required<T>(dict: &Bound<'_, PyDict>, key: &str) -> PyResult<T>
where
    for<'py> T: pyo3::FromPyObject<'py, 'py, Error = PyErr>,
{
    dict.get_item(key)?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Missing required field '{}'", key))
        })?
        .extract()
}

/// Extract an optional field from a Python dict.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `key` - Field name to extract
///
/// # Returns
/// `Some(value)` if field exists, `None` if missing
///
/// # Errors
/// Returns error only if type conversion fails (not if field is missing)
///
/// # Example
/// ```ignore
/// let optional_value: Option<i64> = extract_optional(&py_dict, "collateral")?;
/// ```
fn extract_optional<T>(dict: &Bound<'_, PyDict>, key: &str) -> PyResult<Option<T>>
where
    for<'py> T: pyo3::FromPyObject<'py, 'py, Error = PyErr>,
{
    match dict.get_item(key)? {
        Some(value) => Ok(Some(value.extract()?)),
        None => Ok(None),
    }
}

/// Extract a field with a default value if missing.
///
/// # Arguments
/// * `dict` - Python dictionary to extract from
/// * `key` - Field name to extract
/// * `default` - Default value to use if field is missing
///
/// # Returns
/// Field value if present, otherwise the default
///
/// # Errors
/// Returns error only if type conversion fails (not if field is missing)
///
/// # Example
/// ```ignore
/// let threshold: f64 = extract_with_default(&py_dict, "threshold", 0.8)?;
/// ```
fn extract_with_default<T>(dict: &Bound<'_, PyDict>, key: &str, default: T) -> PyResult<T>
where
    for<'py> T: pyo3::FromPyObject<'py, 'py, Error = PyErr>,
{
    match dict.get_item(key)? {
        Some(value) => value.extract(),
        None => Ok(default),
    }
}

// ========================================================================
// Configuration Parsers
// ========================================================================

/// Convert Python dict to OrchestratorConfig
///
/// # Errors
///
/// Returns PyErr if:
/// - Required fields missing
/// - Type conversions fail
/// - Values out of valid range
pub fn parse_orchestrator_config(py_config: &Bound<'_, PyDict>) -> PyResult<OrchestratorConfig> {
    // Extract required fields using helper
    let ticks_per_day: usize = extract_required(py_config, "ticks_per_day")?;

    if ticks_per_day == 0 {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "ticks_per_day must be positive",
        ));
    }

    let num_days: usize = extract_required(py_config, "num_days")?;
    let rng_seed: u64 = extract_required(py_config, "rng_seed")?;

    // Parse agent configs
    let py_agents: Bound<'_, PyList> = py_config
        .get_item("agent_configs")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing required field 'agent_configs'"))?
        .downcast_into()?;

    let mut agent_configs = Vec::new();
    for py_agent in py_agents.iter() {
        let agent_dict: Bound<'_, PyDict> = py_agent.downcast_into()?;
        agent_configs.push(parse_agent_config(&agent_dict)?);
    }

    // Parse optional fields with defaults using helper
    let cost_rates = if let Some(py_costs) = py_config.get_item("cost_rates")? {
        let costs_dict: Bound<'_, PyDict> = py_costs.downcast_into()?;
        parse_cost_rates(&costs_dict)?
    } else {
        CostRates::default()
    };

    let lsm_config = if let Some(py_lsm) = py_config.get_item("lsm_config")? {
        let lsm_dict: Bound<'_, PyDict> = py_lsm.downcast_into()?;
        parse_lsm_config(&lsm_dict)?
    } else {
        LsmConfig::default()
    };

    // Simple optional fields use extract_with_default
    let eod_rush_threshold: f64 = extract_with_default(py_config, "eod_rush_threshold", 0.8)?;

    // Optional complex fields use extract_optional
    let scenario_events = if let Some(py_events) = py_config.get_item("scenario_events")? {
        let events_list: Bound<'_, PyList> = py_events.downcast_into()?;
        Some(parse_scenario_events(&events_list)?)
    } else {
        None
    };

    // Parse queue1_ordering (default: Fifo for backward compatibility)
    let queue1_ordering: Queue1Ordering =
        if let Some(ordering_str) = py_config.get_item("queue1_ordering")? {
            let ordering: String = ordering_str.extract()?;
            match ordering.as_str() {
                "fifo" | "Fifo" | "FIFO" => Queue1Ordering::Fifo,
                "priority_deadline" | "PriorityDeadline" | "priority-deadline" => {
                    Queue1Ordering::PriorityDeadline
                }
                _ => {
                    return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                        "Invalid queue1_ordering: '{}'. Must be 'fifo' or 'priority_deadline'",
                        ordering
                    )));
                }
            }
        } else {
            Queue1Ordering::Fifo
        };

    // Parse priority_mode (default: false for backward compatibility)
    let priority_mode: bool = py_config
        .get_item("priority_mode")?
        .map(|item| item.extract())
        .transpose()?
        .unwrap_or(false);

    // Parse algorithm_sequencing (default: false for backward compatibility)
    let algorithm_sequencing: bool = py_config
        .get_item("algorithm_sequencing")?
        .map(|item| item.extract())
        .transpose()?
        .unwrap_or(false);

    // Parse entry_disposition_offsetting (default: false for backward compatibility)
    let entry_disposition_offsetting: bool = py_config
        .get_item("entry_disposition_offsetting")?
        .map(|item| item.extract())
        .transpose()?
        .unwrap_or(false);

    // Parse deferred_crediting (default: false for backward compatibility)
    // When true, credits are batched and applied at end of tick (Castro-compatible mode)
    let deferred_crediting: bool = py_config
        .get_item("deferred_crediting")?
        .map(|item| item.extract())
        .transpose()?
        .unwrap_or(false);

    // Parse priority_escalation (default: disabled for backward compatibility)
    let priority_escalation = if let Some(py_escalation) = py_config.get_item("priority_escalation")? {
        let escalation_dict: Bound<'_, PyDict> = py_escalation.downcast_into()?;

        let enabled: bool = escalation_dict
            .get_item("enabled")?
            .map(|item| item.extract())
            .transpose()?
            .unwrap_or(false);

        let curve: String = escalation_dict
            .get_item("curve")?
            .map(|item| item.extract())
            .transpose()?
            .unwrap_or_else(|| "linear".to_string());

        let start_escalating_at_ticks: usize = escalation_dict
            .get_item("start_escalating_at_ticks")?
            .map(|item| item.extract())
            .transpose()?
            .unwrap_or(20);

        let max_boost: u8 = escalation_dict
            .get_item("max_boost")?
            .map(|item| item.extract())
            .transpose()?
            .unwrap_or(3);

        PriorityEscalationConfig {
            enabled,
            curve,
            start_escalating_at_ticks,
            max_boost,
        }
    } else {
        PriorityEscalationConfig::default()
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
        queue1_ordering,
        priority_mode,
        priority_escalation,
        algorithm_sequencing,
        entry_disposition_offsetting,
        deferred_crediting,
    })
}

/// Convert Python dict to AgentConfig
fn parse_agent_config(py_agent: &Bound<'_, PyDict>) -> PyResult<AgentConfig> {
    // Extract required fields using helper
    let id: String = extract_required(py_agent, "id")?;
    let opening_balance: i64 = extract_required(py_agent, "opening_balance")?;

    // Parse policy config
    let py_policy: Bound<'_, PyDict> = py_agent
        .get_item("policy")?
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing required field 'policy'"))?
        .downcast_into()?;
    let policy = parse_policy_config(&py_policy)?;

    // Parse optional arrival config
    let arrival_config = if let Some(py_arrivals) = py_agent.get_item("arrival_config")? {
        let arrivals_dict: Bound<'_, PyDict> = py_arrivals.downcast_into()?;
        Some(parse_arrival_config(&arrivals_dict)?)
    } else {
        None
    };

    // Parse optional arrival bands config (Enhancement 11.3)
    let arrival_bands = if let Some(py_bands) = py_agent.get_item("arrival_bands")? {
        let bands_dict: Bound<'_, PyDict> = py_bands.downcast_into()?;
        Some(parse_arrival_bands_config(&bands_dict)?)
    } else {
        None
    };

    // Parse required unsecured_cap using helper
    let unsecured_cap: i64 = extract_required(py_agent, "unsecured_cap")?;

    // Parse optional collateral_haircut using helper
    let collateral_haircut: Option<f64> = extract_optional(py_agent, "collateral_haircut")?;

    // Parse optional posted_collateral using helper
    let posted_collateral: Option<i64> = extract_optional(py_agent, "posted_collateral")?;

    // Parse optional max_collateral_capacity using helper
    let max_collateral_capacity: Option<i64> = extract_optional(py_agent, "max_collateral_capacity")?;

    // Parse optional limits (bilateral/multilateral) using helper
    let limits: Option<AgentLimitsConfig> = if let Ok(Some(py_limits)) = py_agent.get_item("limits") {
        let limits_dict: Bound<'_, PyDict> = py_limits.downcast_into()?;
        Some(parse_agent_limits_config(&limits_dict)?)
    } else {
        None
    };

    // Parse optional liquidity pool fields (Enhancement 11.2)
    let liquidity_pool: Option<i64> = extract_optional(py_agent, "liquidity_pool")?;
    let liquidity_allocation_fraction: Option<f64> = extract_optional(py_agent, "liquidity_allocation_fraction")?;

    Ok(AgentConfig {
        id,
        opening_balance,
        unsecured_cap,
        policy,
        arrival_config,
        arrival_bands,
        posted_collateral,
        collateral_haircut,
        max_collateral_capacity,
        limits,
        liquidity_pool,
        liquidity_allocation_fraction,
    })
}

/// Convert Python dict to AgentLimitsConfig (bilateral/multilateral limits)
fn parse_agent_limits_config(py_limits: &Bound<'_, PyDict>) -> PyResult<AgentLimitsConfig> {
    // Parse optional bilateral_limits (dict of counterparty -> max_amount)
    let bilateral_limits: HashMap<String, i64> = if let Ok(Some(py_bilateral)) = py_limits.get_item("bilateral_limits") {
        let bilateral_dict: Bound<'_, PyDict> = py_bilateral.downcast_into()?;
        let mut limits = HashMap::new();
        for (key, value) in bilateral_dict.iter() {
            let counterparty: String = key.extract()?;
            let max_amount: i64 = value.extract()?;
            limits.insert(counterparty, max_amount);
        }
        limits
    } else {
        HashMap::new()
    };

    // Parse optional multilateral_limit
    let multilateral_limit: Option<i64> = extract_optional(py_limits, "multilateral_limit")?;

    Ok(AgentLimitsConfig {
        bilateral_limits,
        multilateral_limit,
    })
}

/// Convert Python dict to PolicyConfig
fn parse_policy_config(py_policy: &Bound<'_, PyDict>) -> PyResult<PolicyConfig> {
    // Extract policy type using helper
    let policy_type: String = extract_required(py_policy, "type")?;

    match policy_type.as_str() {
        "Fifo" => Ok(PolicyConfig::Fifo),
        "Deadline" => {
            let urgency_threshold: usize = extract_required(py_policy, "urgency_threshold")?;
            Ok(PolicyConfig::Deadline { urgency_threshold })
        }
        "LiquidityAware" => {
            let target_buffer: i64 = extract_required(py_policy, "target_buffer")?;
            let urgency_threshold: usize = extract_required(py_policy, "urgency_threshold")?;

            Ok(PolicyConfig::LiquidityAware {
                target_buffer,
                urgency_threshold,
            })
        }
        "LiquiditySplitting" => {
            let max_splits: usize = extract_required(py_policy, "max_splits")?;
            let min_split_amount: i64 = extract_required(py_policy, "min_split_amount")?;

            Ok(PolicyConfig::LiquiditySplitting {
                max_splits,
                min_split_amount,
            })
        }
        "MockSplitting" => {
            let num_splits: usize = extract_required(py_policy, "num_splits")?;
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
        PolicyConfig::MockStaggerSplit {
            num_splits,
            stagger_first_now,
            stagger_gap_ticks,
            priority_boost_children,
        } => {
            dict.set_item("type", "MockStaggerSplit")?;
            dict.set_item("num_splits", num_splits)?;
            dict.set_item("stagger_first_now", stagger_first_now)?;
            dict.set_item("stagger_gap_ticks", stagger_gap_ticks)?;
            dict.set_item("priority_boost_children", priority_boost_children)?;
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

    // Parse priority_distribution (new format) or fall back to legacy priority
    let priority_distribution: PriorityDistribution =
        if let Some(py_priority_dist) = py_arrivals.get_item("priority_distribution")? {
            let dist_dict: Bound<'_, PyDict> = py_priority_dist.downcast_into()?;
            parse_priority_distribution(&dist_dict)?
        } else if let Some(priority_val) = py_arrivals.get_item("priority")? {
            // Legacy: single priority value
            let priority: u8 = priority_val.extract()?;
            PriorityDistribution::Fixed { value: priority }
        } else {
            // Default: fixed priority of 5
            PriorityDistribution::Fixed { value: 5 }
        };

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
        priority_distribution,
        divisible,
    })
}

/// Convert Python dict to ArrivalBandsConfig (Enhancement 11.3)
///
/// Expected format:
/// ```python
/// {
///     "urgent": { "rate_per_tick": 0.5, "amount_distribution": {...}, ... },
///     "normal": { "rate_per_tick": 2.0, ... },
///     "low": { "rate_per_tick": 1.0, ... }
/// }
/// ```
fn parse_arrival_bands_config(py_bands: &Bound<'_, PyDict>) -> PyResult<ArrivalBandsConfig> {
    // Parse optional urgent band
    let urgent = if let Some(py_urgent) = py_bands.get_item("urgent")? {
        let urgent_dict: Bound<'_, PyDict> = py_urgent.downcast_into()?;
        Some(parse_arrival_band_config(&urgent_dict)?)
    } else {
        None
    };

    // Parse optional normal band
    let normal = if let Some(py_normal) = py_bands.get_item("normal")? {
        let normal_dict: Bound<'_, PyDict> = py_normal.downcast_into()?;
        Some(parse_arrival_band_config(&normal_dict)?)
    } else {
        None
    };

    // Parse optional low band
    let low = if let Some(py_low) = py_bands.get_item("low")? {
        let low_dict: Bound<'_, PyDict> = py_low.downcast_into()?;
        Some(parse_arrival_band_config(&low_dict)?)
    } else {
        None
    };

    Ok(ArrivalBandsConfig { urgent, normal, low })
}

/// Convert Python dict to ArrivalBandConfig (Enhancement 11.3)
///
/// Expected format:
/// ```python
/// {
///     "rate_per_tick": 1.5,
///     "amount_distribution": { "type": "Uniform", "min": 1000, "max": 5000 },
///     "deadline_offset_min": 5,
///     "deadline_offset_max": 20,
///     "counterparty_weights": { "BANK_B": 0.5, "BANK_C": 0.5 },  # optional
///     "divisible": false  # optional
/// }
/// ```
fn parse_arrival_band_config(py_band: &Bound<'_, PyDict>) -> PyResult<ArrivalBandConfig> {
    // Required: rate_per_tick
    let rate_per_tick: f64 = extract_required(py_band, "rate_per_tick")?;

    // Required: amount_distribution
    let py_dist: Bound<'_, PyDict> = py_band
        .get_item("amount_distribution")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing 'amount_distribution' in arrival band")
        })?
        .downcast_into()?;
    let amount_distribution = parse_amount_distribution(&py_dist)?;

    // Required: deadline_offset_min
    let deadline_offset_min: usize = extract_required(py_band, "deadline_offset_min")?;

    // Required: deadline_offset_max
    let deadline_offset_max: usize = extract_required(py_band, "deadline_offset_max")?;

    // Optional: counterparty_weights (default to empty)
    let counterparty_weights = if let Some(py_weights) = py_band.get_item("counterparty_weights")? {
        let weights_dict: Bound<'_, PyDict> = py_weights.downcast_into()?;
        let mut weights = HashMap::new();
        for (key, value) in weights_dict.iter() {
            let agent_id: String = key.extract()?;
            let weight: f64 = value.extract()?;
            weights.insert(agent_id, weight);
        }
        weights
    } else {
        HashMap::new()
    };

    // Optional: divisible (default false)
    let divisible: bool = extract_with_default(py_band, "divisible", false)?;

    Ok(ArrivalBandConfig {
        rate_per_tick,
        amount_distribution,
        deadline_offset_min,
        deadline_offset_max,
        counterparty_weights,
        divisible,
    })
}

/// Convert Python dict to PriorityDistribution
fn parse_priority_distribution(py_dist: &Bound<'_, PyDict>) -> PyResult<PriorityDistribution> {
    let dist_type: String = py_dist
        .get_item("type")?
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing priority distribution 'type'")
        })?
        .extract()?;

    match dist_type.as_str() {
        "Fixed" => {
            let value: u8 = py_dist
                .get_item("value")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Fixed priority requires 'value'")
                })?
                .extract()?;

            Ok(PriorityDistribution::Fixed { value: value.min(10) })
        }
        "Categorical" => {
            let values: Vec<u8> = py_dist
                .get_item("values")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Categorical requires 'values'")
                })?
                .extract()?;

            let weights: Vec<f64> = py_dist
                .get_item("weights")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Categorical requires 'weights'")
                })?
                .extract()?;

            // Validate and cap values at 10
            let values: Vec<u8> = values.into_iter().map(|v| v.min(10)).collect();

            Ok(PriorityDistribution::Categorical { values, weights })
        }
        "Uniform" => {
            let min: u8 = py_dist
                .get_item("min")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform priority requires 'min'")
                })?
                .extract()?;

            let max: u8 = py_dist
                .get_item("max")?
                .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>("Uniform priority requires 'max'")
                })?
                .extract()?;

            Ok(PriorityDistribution::Uniform {
                min: min.min(10),
                max: max.min(10),
            })
        }
        _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Unknown priority distribution type: {}",
            dist_type
        ))),
    }
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

        // Enhancement 11.1: Priority-based delay cost multipliers
        priority_delay_multipliers: if let Some(py_priority) =
            py_costs.get_item("priority_delay_multipliers")?
        {
            let priority_dict: Bound<'_, PyDict> = py_priority.downcast_into()?;
            Some(parse_priority_delay_multipliers(&priority_dict)?)
        } else {
            None // Default: no priority differentiation
        },

        // Enhancement 11.2: Liquidity opportunity cost
        liquidity_cost_per_tick_bps: py_costs
            .get_item("liquidity_cost_per_tick_bps")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(0.0), // Default: no liquidity opportunity cost
    })
}

/// Convert Python dict to PriorityDelayMultipliers (Enhancement 11.1)
fn parse_priority_delay_multipliers(
    py_priority: &Bound<'_, PyDict>,
) -> PyResult<PriorityDelayMultipliers> {
    Ok(PriorityDelayMultipliers {
        urgent_multiplier: py_priority
            .get_item("urgent_multiplier")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(1.0), // Default: no adjustment

        normal_multiplier: py_priority
            .get_item("normal_multiplier")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(1.0), // Default: no adjustment

        low_multiplier: py_priority
            .get_item("low_multiplier")?
            .map(|v| v.extract())
            .transpose()?
            .unwrap_or(1.0), // Default: no adjustment
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

    // Add timing data
    let timing_dict = PyDict::new(py);
    timing_dict.set_item("arrivals_micros", result.timing.arrivals_micros)?;
    timing_dict.set_item("policy_eval_micros", result.timing.policy_eval_micros)?;
    timing_dict.set_item("rtgs_settlement_micros", result.timing.rtgs_settlement_micros)?;
    timing_dict.set_item("rtgs_queue_micros", result.timing.rtgs_queue_micros)?;
    timing_dict.set_item("lsm_micros", result.timing.lsm_micros)?;
    timing_dict.set_item("cost_accrual_micros", result.timing.cost_accrual_micros)?;
    timing_dict.set_item("total_micros", result.timing.total_micros)?;
    dict.set_item("timing", timing_dict)?;

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

    // RTGS Priority (Phase 0: Dual Priority System)
    // rtgs_priority is None until transaction is submitted to RTGS Queue 2
    if let Some(rtgs_priority) = tx.rtgs_priority() {
        dict.set_item("rtgs_priority", rtgs_priority.to_string())?;
    } else {
        dict.set_item("rtgs_priority", py.None())?;
    }

    // RTGS Submission Tick (Phase 0: Dual Priority System)
    // Used for FIFO ordering within the same RTGS priority band
    if let Some(submission_tick) = tx.rtgs_submission_tick() {
        dict.set_item("rtgs_submission_tick", submission_tick)?;
    } else {
        dict.set_item("rtgs_submission_tick", py.None())?;
    }

    // Declared RTGS Priority (Phase 0: Dual Priority System)
    // Bank's preferred RTGS priority when submitting the transaction
    if let Some(declared_priority) = tx.declared_rtgs_priority() {
        dict.set_item("declared_rtgs_priority", declared_priority.to_string())?;
    } else {
        dict.set_item("declared_rtgs_priority", py.None())?;
    }

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
    dict.set_item("unsecured_cap", metrics.unsecured_cap)?;
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
            "CustomTransactionArrival" => {
                let from_agent: String = event_dict
                    .get_item("from_agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CustomTransactionArrival requires 'from_agent'"
                    ))?
                    .extract()?;
                let to_agent: String = event_dict
                    .get_item("to_agent")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CustomTransactionArrival requires 'to_agent'"
                    ))?
                    .extract()?;
                let amount: i64 = event_dict
                    .get_item("amount")?
                    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "CustomTransactionArrival requires 'amount'"
                    ))?
                    .extract()?;

                // Optional fields with defaults
                let priority: Option<u8> = event_dict
                    .get_item("priority")?
                    .map(|v| v.extract())
                    .transpose()?;
                let deadline: Option<usize> = event_dict
                    .get_item("deadline")?
                    .map(|v| v.extract())
                    .transpose()?;
                let is_divisible: Option<bool> = event_dict
                    .get_item("is_divisible")?
                    .map(|v| v.extract())
                    .transpose()?;

                ScenarioEvent::CustomTransactionArrival {
                    from_agent,
                    to_agent,
                    amount,
                    priority,
                    deadline,
                    is_divisible,
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
