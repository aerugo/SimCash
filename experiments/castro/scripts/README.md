# Castro et al. Replication - Reproducible Experiment Scripts

This directory contains scripts for running reproducible experiments that replicate the Castro et al. (2025) payment system optimization results.

## Castro Alignment (2025-12-02)

All experiments now use **Castro-aligned** configurations with two critical features enabled:

1. **`deferred_crediting: true`** - Credits applied at end of tick (matches Castro's timing model)
2. **`deadline_cap_at_eod: true`** - All deadlines capped at day end (same-day settlement)

These features ensure the simulation environment matches Castro et al. (2025) Section 3.

> **Note**: Previous experiments (pre-alignment) have been archived to `archive/pre-castro-alignment/`.
> See `LAB_NOTES.md` for details on alignment issues discovered.

## Quick Start

```bash
# List available experiments
python reproducible_experiment.py --list

# Run Experiment 1 (Two-Period Deterministic)
python reproducible_experiment.py --experiment exp1 --output exp1_results.db

# Run Experiment 2 (Twelve-Period Stochastic)
python reproducible_experiment.py --experiment exp2 --output exp2_results.db

# Run Experiment 3 (Joint Learning)
python reproducible_experiment.py --experiment exp3 --output exp3_results.db

# Run with custom settings (GPT-5.1 is default with high reasoning)
python reproducible_experiment.py --experiment exp2 \
    --output exp2_custom.db \
    --model gpt-5.1 \
    --max-iter 50 \
    --reasoning high
```

## Available Experiments

| Key | Name | Seeds | Description |
|-----|------|-------|-------------|
| `exp1` | Two-Period Deterministic (Castro-Aligned) | 1 | Nash equilibrium validation with deferred crediting |
| `exp2` | Twelve-Period Stochastic (Castro-Aligned) | 10 | 12-period LVTS-style with deferred crediting + EOD deadline cap |
| `exp3` | Joint Learning (Castro-Aligned) | 10 | 3-period joint policy learning with deferred crediting |

## Database Schema

The experiment database stores:

1. **experiment_config** - Full experiment configuration
   - Config YAML text and hash
   - Cost rates, agent configs
   - Model settings (name, reasoning effort)
   - Convergence parameters

2. **policy_iterations** - Every policy version
   - Full policy JSON and hash
   - Extracted parameters for easy querying
   - Creation source (`init`, `llm`, `manual`)

3. **llm_interactions** - All LLM calls
   - Complete prompt and response text with hashes
   - Token counts and latency
   - Error messages (if any)

4. **simulation_runs** - Every simulation result
   - Per-seed costs and settlement rates
   - Cost breakdown (when available)
   - Raw JSON output

5. **iteration_metrics** - Aggregated stats
   - Mean, std, risk-adjusted costs
   - Best/worst seeds
   - Convergence status

## Reproducing Results

To reproduce an experiment:

1. **Get the database file** from the original researcher
2. **Extract the experiment configuration**:
   ```python
   import duckdb
   conn = duckdb.connect('experiment.db', read_only=True)

   # Get config
   config = conn.execute("SELECT config_yaml FROM experiment_config").fetchone()[0]
   print(config)

   # Get initial policies
   policies = conn.execute("""
       SELECT agent_id, policy_json FROM policy_iterations
       WHERE iteration_number = 0
   """).fetchall()
   ```

3. **Run with the same seed and config**:
   ```bash
   # The database contains all settings needed
   python reproducible_experiment.py --experiment exp2_fixed \
       --output my_reproduction.db
   ```

4. **Compare results**:
   ```python
   # Query both databases and compare iteration_metrics
   original = duckdb.connect('original.db', read_only=True)
   mine = duckdb.connect('my_reproduction.db', read_only=True)

   # Compare costs at each iteration
   orig_costs = original.execute("""
       SELECT iteration_number, total_cost_mean
       FROM iteration_metrics ORDER BY iteration_number
   """).fetchall()

   my_costs = mine.execute("""
       SELECT iteration_number, total_cost_mean
       FROM iteration_metrics ORDER BY iteration_number
   """).fetchall()
   ```

## Analyzing Results

### Query Examples

```python
import duckdb
conn = duckdb.connect('experiment.db', read_only=True)

# Cost reduction over iterations
conn.execute("""
    SELECT iteration_number,
           total_cost_mean,
           100 * (1 - total_cost_mean / FIRST_VALUE(total_cost_mean)
                  OVER (ORDER BY iteration_number)) as reduction_pct
    FROM iteration_metrics
    ORDER BY iteration_number
""").fetchall()

# Best policies (lowest cost)
conn.execute("""
    SELECT p.iteration_number, p.agent_id, p.parameters, m.total_cost_mean
    FROM policy_iterations p
    JOIN iteration_metrics m ON p.experiment_id = m.experiment_id
                             AND p.iteration_number = m.iteration_number
    ORDER BY m.total_cost_mean
    LIMIT 10
""").fetchall()

# LLM token usage
conn.execute("""
    SELECT SUM(tokens_used) as total_tokens,
           AVG(latency_seconds) as avg_latency,
           COUNT(*) as num_calls
    FROM llm_interactions
""").fetchone()
```

### Export for Publication

```python
# Export summary JSON
import json
summary = conn.execute("""
    SELECT json_object(
        'experiment_name', ec.experiment_name,
        'model', ec.model_name,
        'iterations', (SELECT COUNT(*) FROM iteration_metrics),
        'final_cost', (SELECT total_cost_mean FROM iteration_metrics ORDER BY iteration_number DESC LIMIT 1),
        'initial_cost', (SELECT total_cost_mean FROM iteration_metrics ORDER BY iteration_number ASC LIMIT 1),
        'cost_reduction_pct', 100 * (1 -
            (SELECT total_cost_mean FROM iteration_metrics ORDER BY iteration_number DESC LIMIT 1) /
            (SELECT total_cost_mean FROM iteration_metrics ORDER BY iteration_number ASC LIMIT 1)
        )
    )
    FROM experiment_config ec
""").fetchone()[0]

print(json.dumps(json.loads(summary), indent=2))
```

## Known Issues

### max_collateral_capacity Bug
The `max_collateral_capacity` config field is currently ignored - it's computed as `10 * unsecured_cap` in Rust. Use corrected `initial_liquidity_fraction` values to work around this. See archived experiment notes for details.

### Castro Alignment Requirements
For accurate Castro et al. replication, both alignment features MUST be enabled:
- `deferred_crediting: true` - Without this, within-tick recycling changes equilibrium structure
- `deadline_cap_at_eod: true` - Without this, multi-day deadlines reduce settlement urgency

Pre-alignment experiments (before 2025-12-02) are archived and should not be used for comparison.

## Requirements

- Python 3.11+
- DuckDB
- OpenAI API key (for LLM optimization)
- SimCash payment simulator built and installed

## Environment Variables

- `OPENAI_API_KEY` - Required for LLM policy optimization
