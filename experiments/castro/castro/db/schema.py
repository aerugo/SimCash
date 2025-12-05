"""Database schema for castro experiments.

Defines the DuckDB schema for experiment tracking. All tables are created
with IF NOT EXISTS to support idempotent initialization.

Tables:
- experiment_config: Full experiment configuration
- policy_iterations: Every policy version with hash
- llm_interactions: All prompts and responses
- simulation_runs: Results for every seed at every iteration
- iteration_metrics: Aggregated metrics per iteration
- validation_errors: Policy validation failures for learning
"""

SCHEMA_SQL = """
-- Experiment configuration
CREATE TABLE IF NOT EXISTS experiment_config (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    config_yaml TEXT NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    cost_rates JSON NOT NULL,
    agent_configs JSON NOT NULL,
    model_name VARCHAR NOT NULL,
    reasoning_effort VARCHAR NOT NULL,
    num_seeds INTEGER NOT NULL,
    max_iterations INTEGER NOT NULL,
    convergence_threshold DOUBLE NOT NULL,
    convergence_window INTEGER NOT NULL,
    master_seed INTEGER NOT NULL,
    seed_matrix JSON NOT NULL,
    notes TEXT
);

-- Policy iterations (every version of every policy)
CREATE TABLE IF NOT EXISTS policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    parameters JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    created_by VARCHAR NOT NULL,  -- 'init', 'llm', 'manual'
    was_accepted BOOLEAN DEFAULT TRUE,  -- Was this policy kept (improved) or rejected?
    is_best BOOLEAN DEFAULT FALSE,  -- Is this the best policy discovered so far?
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- LLM interactions (prompts and responses)
CREATE TABLE IF NOT EXISTS llm_interactions (
    interaction_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_hash VARCHAR(64) NOT NULL,
    response_text TEXT NOT NULL,
    response_hash VARCHAR(64) NOT NULL,
    model_name VARCHAR NOT NULL,
    reasoning_effort VARCHAR NOT NULL,
    tokens_used INTEGER NOT NULL,
    latency_seconds DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    error_message TEXT,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Individual simulation runs
CREATE TABLE IF NOT EXISTS simulation_runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    total_cost BIGINT NOT NULL,
    bank_a_cost BIGINT NOT NULL,
    bank_b_cost BIGINT NOT NULL,
    settlement_rate DOUBLE NOT NULL,
    collateral_cost BIGINT,
    delay_cost BIGINT,
    overdraft_cost BIGINT,
    eod_penalty BIGINT,
    bank_a_final_balance BIGINT,
    bank_b_final_balance BIGINT,
    total_arrivals INTEGER,
    total_settlements INTEGER,
    raw_output JSON NOT NULL,
    verbose_log TEXT,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Aggregated iteration metrics
CREATE TABLE IF NOT EXISTS iteration_metrics (
    metric_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    total_cost_mean DOUBLE NOT NULL,
    total_cost_std DOUBLE NOT NULL,
    risk_adjusted_cost DOUBLE NOT NULL,
    settlement_rate_mean DOUBLE NOT NULL,
    failure_rate DOUBLE NOT NULL,
    best_seed INTEGER NOT NULL,
    worst_seed INTEGER NOT NULL,
    best_seed_cost BIGINT NOT NULL,
    worst_seed_cost BIGINT NOT NULL,
    converged BOOLEAN NOT NULL DEFAULT FALSE,
    policy_was_accepted BOOLEAN DEFAULT TRUE,  -- Was this iteration's policy accepted?
    is_best_iteration BOOLEAN DEFAULT FALSE,  -- Is this the best iteration so far?
    comparison_to_best VARCHAR,  -- Human-readable comparison
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Policy validation errors (track all failures for learning)
CREATE TABLE IF NOT EXISTS validation_errors (
    error_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    attempt_number INTEGER NOT NULL,  -- 0 = initial, 1-3 = fix attempts
    policy_json TEXT NOT NULL,
    error_messages JSON NOT NULL,
    error_category VARCHAR,           -- Categorized error type
    was_fixed BOOLEAN NOT NULL,
    fix_attempt_count INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiment_config(experiment_id)
);

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_policy_exp_iter ON policy_iterations(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_policy_hash ON policy_iterations(policy_hash);
CREATE INDEX IF NOT EXISTS idx_llm_exp_iter ON llm_interactions(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_sim_exp_iter ON simulation_runs(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_metrics_exp ON iteration_metrics(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_validation_errors_exp ON validation_errors(experiment_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_validation_errors_category ON validation_errors(error_category);
"""
