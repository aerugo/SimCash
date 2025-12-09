# Castro Experiments

Clean-slate implementation of Castro et al. (2025) experiments using the `ai_cash_mgmt` module.

## Overview

This module replicates the experiments from "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" (Castro et al., 2025) using LLM-based policy optimization instead of traditional RL methods.

**Key Features**:
- Three experiments matching the paper's scenarios
- LLM-based policy generation (Anthropic Claude, OpenAI GPT)
- Monte Carlo policy evaluation
- Deterministic execution via seeded RNG
- Full persistence to DuckDB

## Quick Start

```bash
# Install dependencies
cd experiments/new-castro
pip install -e .

# List available experiments
python cli.py list

# Run experiment 1 (2-period deterministic)
python cli.py run exp1

# Run with custom settings
python cli.py run exp2 --model gpt-4o --max-iter 50 --output ./results
```

## Experiments

| Experiment | Description | Ticks | Samples |
|------------|-------------|-------|---------|
| `exp1` | 2-Period Deterministic Nash Equilibrium | 2 | 1 |
| `exp2` | 12-Period Stochastic LVTS-Style | 12 | 10 |
| `exp3` | Joint Liquidity & Timing Optimization | 3 | 10 |

### Experiment 1: 2-Period Deterministic

Validates Nash equilibrium with deferred crediting. Two banks exchange payments with known amounts and deadlines.

**Expected Outcome**: Bank A posts 0 collateral, Bank B posts 20,000.

```bash
python cli.py run exp1
```

### Experiment 2: 12-Period Stochastic

LVTS-style realistic scenario with Poisson arrivals and LogNormal payment amounts.

```bash
python cli.py run exp2 --seed 42
```

### Experiment 3: Joint Optimization

Tests interaction between initial liquidity decisions and payment timing strategies.

```bash
python cli.py run exp3
```

## Architecture

```
new-castro/
├── castro/
│   ├── __init__.py          # Public API
│   ├── constraints.py       # CASTRO_CONSTRAINTS
│   ├── experiments.py       # Experiment definitions
│   ├── llm_client.py        # LLM client (Anthropic/OpenAI)
│   ├── runner.py            # ExperimentRunner
│   └── simulation.py        # CastroSimulationRunner
├── configs/
│   ├── exp1_2period.yaml    # 2-period scenario
│   ├── exp2_12period.yaml   # 12-period scenario
│   └── exp3_joint.yaml      # Joint optimization scenario
├── tests/
│   └── test_experiments.py  # Unit tests
├── cli.py                   # Typer CLI
├── pyproject.toml           # Package config
└── README.md                # This file
```

## CLI Commands

### `run` - Run an experiment

```bash
python cli.py run <experiment> [OPTIONS]

Arguments:
  experiment    Experiment key: exp1, exp2, or exp3

Options:
  -m, --model TEXT      LLM model [default: claude-sonnet-4-5-20250929]
  -i, --max-iter INT    Max iterations [default: 25]
  -o, --output PATH     Output directory [default: results]
  -s, --seed INT        Master seed [default: 42]
```

### `list` - List experiments

```bash
python cli.py list
```

### `info` - Show experiment details

```bash
python cli.py info exp1
```

### `validate` - Validate configuration

```bash
python cli.py validate exp2
```

## Configuration

### Castro Constraints

The module enforces Castro paper rules via `CASTRO_CONSTRAINTS`:

```python
from castro.constraints import CASTRO_CONSTRAINTS

# Allowed parameters
# - initial_liquidity_fraction: 0.0 - 1.0
# - urgency_threshold: 0 - 20
# - liquidity_buffer: 0.5 - 3.0

# Allowed actions
# - payment_tree: Release, Hold (no Split)
# - collateral_tree: PostCollateral, HoldCollateral
# - bank_tree: NoAction
```

### LLM Providers

Supports both Anthropic and OpenAI:

```bash
# Anthropic (default)
python cli.py run exp1 --model claude-sonnet-4-5-20250929

# OpenAI
python cli.py run exp1 --model gpt-4o
```

Set API keys via environment variables:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

## Programmatic Usage

```python
import asyncio
from castro import create_exp1, ExperimentRunner

# Create experiment
exp = create_exp1(model="claude-sonnet-4-5-20250929")

# Run optimization
runner = ExperimentRunner(exp)
result = asyncio.run(runner.run())

# Access results
print(f"Final cost: ${result.final_cost / 100:.2f}")
print(f"Converged: {result.converged}")
print(f"Iterations: {result.num_iterations}")

# Per-agent costs
for agent_id, cost in result.per_agent_costs.items():
    print(f"  {agent_id}: ${cost / 100:.2f}")

# Best policies found
for agent_id, policy in result.best_policies.items():
    print(f"{agent_id} policy: {policy}")
```

## Output

Results are persisted to DuckDB:

```
results/
├── exp1.db    # Experiment 1 results
├── exp2.db    # Experiment 2 results
└── exp3.db    # Experiment 3 results
```

Query results:

```python
import duckdb

conn = duckdb.connect("results/exp1.db")

# View game sessions
conn.execute("SELECT * FROM game_sessions").fetchall()

# View policy iterations
conn.execute("""
    SELECT agent_id, iteration_number, old_cost, new_cost, was_accepted
    FROM policy_iterations
    ORDER BY iteration_number
""").fetchall()
```

## Testing

```bash
cd experiments/new-castro
pytest tests/ -v
```

## Dependencies

- `payment-simulator` - SimCash core with ai_cash_mgmt module
- `anthropic` - Anthropic API client
- `openai` - OpenAI API client
- `typer` - CLI framework
- `rich` - Terminal formatting
- `pyyaml` - YAML parsing

## Design Principles

1. **No Legacy Code**: Built from scratch using only `ai_cash_mgmt`
2. **No Backwards Compatibility**: Clean break from legacy Castro experiments
3. **Deterministic**: Same seed produces identical results
4. **Type Safe**: Full type annotations, mypy strict mode
5. **Testable**: Comprehensive unit tests

---

## Research Protocol: Evaluating Experiment Results

This section provides a structured protocol for evaluating experiment results against the hypotheses and expected outcomes from Castro et al. (2025). The protocol is designed for:

1. **AI Reviewer (Primary Analysis)**: Capable of processing long textual outputs, detailed numerical data, and structured logs. Should produce comprehensive text-based analysis.
2. **Human Reviewer (Final Review)**: Requires visual summaries via charts for pattern recognition and presentation.

### Reference Paper

The original paper is available at: `papers/castro_et_al.md`

---

## Core Hypotheses

### H1: Nash Equilibrium Convergence (Exp1)

**Hypothesis**: In a 2-period deterministic setting with known payment profiles, LLM-based policy optimization converges to the analytically-derived Nash equilibrium.

**Theoretical Basis** (Section 4 of paper):
- Given cost ordering `r_c < r_d < r_b` (collateral < delay < borrowing)
- Agent B (first-period demand) must post liquidity = total demand to avoid delay/borrowing costs
- Agent A (no first-period demand) can free-ride on B's liquidity, optimal: zero collateral

**Expected Outcome**:
- Bank A initial liquidity fraction: **0.0** (or very close)
- Bank B initial liquidity fraction: **0.20** (matching total demand of 20,000 / 100,000 collateral)
- Bank A total cost: **$0.00**
- Bank B total cost: **$20.00** (collateral cost only: 20,000 × 0.001)

### H2: Liquidity-Delay Tradeoff Learning (Exp2)

**Hypothesis**: In a multi-period stochastic environment, agents learn to balance initial liquidity allocation against delay costs, reducing total payment processing costs over iterations.

**Theoretical Basis** (Section 6 of paper):
- With realistic payment profiles, no closed-form solution exists
- Agents should reduce liquidity allocation over time as they learn incoming payment patterns
- Higher-demand agents should post more collateral than lower-demand agents

**Expected Outcomes**:
- Total costs decrease monotonically (or near-monotonically) over iterations
- Agents converge to stable liquidity fractions (variance < 10% in final 5 iterations)
- Higher-demand agent posts more collateral

### H3: Joint Policy Optimization (Exp3)

**Hypothesis**: When optimizing both initial liquidity AND intraday payment timing, agents learn to exploit the interdependence between these decisions.

**Theoretical Basis** (Section 7 of paper):
- With `r_d < r_c` (delay cheaper than collateral): agents should delay more, post less collateral
- With `r_d > r_c` (collateral cheaper than delay): agents should post more, delay less
- Indivisible payments create inter-period tradeoffs affecting timing strategy

**Expected Outcomes**:
- Timing policies differ between agents based on payment structure
- Cost reduction in joint optimization exceeds sum of individual optimizations
- Agents learn to buffer liquidity before large indivisible payments

---

## Evaluation Metrics

### Primary Metrics

| Metric | Formula | Target |
|--------|---------|--------|
| **Total System Cost** | `Σ agent_costs` | Minimize |
| **Per-Agent Cost** | `collateral_cost + delay_cost + borrowing_cost` | Track per iteration |
| **Cost Reduction Rate** | `(initial_cost - final_cost) / initial_cost` | > 50% |
| **Convergence Iteration** | First iter where `|cost_t - cost_{t-1}| < ε` for 3 consecutive | < max_iter - 5 |

### Convergence Metrics

| Metric | Formula | Threshold |
|--------|---------|-----------|
| **Policy Stability** | `std(liquidity_frac[-5:])` | < 0.05 |
| **Cost Stability** | `std(cost[-5:]) / mean(cost[-5:])` | < 0.1 |
| **Nash Gap (Exp1 only)** | `|actual - theoretical|` | < 0.02 |

### Component Costs (i64 cents)

For each agent per iteration, track:
- `collateral_cost`: `initial_liquidity × r_c`
- `delay_cost`: `Σ delayed_amounts × r_d`
- `borrowing_cost`: `end_of_day_shortfall × r_b`

---

## AI Reviewer Analysis Protocol

### Phase 1: Data Extraction

Extract and organize the following from experiment output:

```
FOR EACH EXPERIMENT RUN:
1. Metadata
   - Experiment ID, timestamp, seed
   - Model used, max iterations
   - Configuration parameters

2. Per-Iteration Data (tabular)
   - Iteration number
   - Per-agent: liquidity_fraction, urgency_threshold, liquidity_buffer
   - Per-agent: collateral_cost, delay_cost, borrowing_cost, total_cost
   - Policy acceptance status (was_accepted)

3. Final State
   - Best policies found (per agent)
   - Total iterations to convergence (or max)
   - Final cost breakdown
```

### Phase 2: Hypothesis Testing

#### For H1 (Exp1 - Nash Equilibrium):

```
EVALUATION PROCEDURE:

1. Extract final liquidity fractions for Bank A and Bank B

2. Compute Nash Gap:
   nash_gap_A = |bank_a_liquidity_frac - 0.0|
   nash_gap_B = |bank_b_liquidity_frac - 0.20|

3. Classify result:
   IF nash_gap_A < 0.02 AND nash_gap_B < 0.02:
       RESULT: "PASS - Nash equilibrium achieved"
   ELIF nash_gap_A < 0.05 AND nash_gap_B < 0.05:
       RESULT: "PARTIAL PASS - Near Nash equilibrium"
   ELSE:
       RESULT: "FAIL - Significant deviation from Nash"

4. Verify cost structure:
   ASSERT bank_a_cost ≈ 0 (within $1)
   ASSERT bank_b_cost ≈ $20 (within $5)
   ASSERT bank_b_cost > bank_a_cost

5. Report deviations with magnitude and direction
```

#### For H2 (Exp2 - Liquidity-Delay Tradeoff):

```
EVALUATION PROCEDURE:

1. Compute iteration-over-iteration cost changes:
   delta_costs = [cost[i] - cost[i-1] for i in range(1, len(costs))]

2. Monotonicity check:
   negative_deltas = count(d < 0 for d in delta_costs)
   monotonicity_score = negative_deltas / len(delta_costs)
   # Target: > 0.7 (70% of iterations reduce cost)

3. Convergence check:
   final_5_costs = costs[-5:]
   cost_variance = std(final_5_costs)
   cost_cv = cost_variance / mean(final_5_costs)
   # Target: CV < 0.1

4. Liquidity ordering check:
   IF payment_demand[agent_A] > payment_demand[agent_B]:
       ASSERT liquidity_frac[agent_A] > liquidity_frac[agent_B]

5. Cost reduction check:
   reduction_rate = (costs[0] - costs[-1]) / costs[0]
   # Target: > 0.3 (30% reduction)

6. Report:
   - Total cost trajectory (text table of costs per iteration)
   - Convergence iteration (if achieved)
   - Final liquidity allocations with demand context
```

#### For H3 (Exp3 - Joint Optimization):

```
EVALUATION PROCEDURE:

1. Extract both policy dimensions per agent:
   - Liquidity policy: initial_liquidity_fraction
   - Timing policy: urgency_threshold, timing decisions

2. Verify cost structure sensitivity:
   IF r_d < r_c (delay cheaper):
       ASSERT more delays observed
       ASSERT lower liquidity allocation
   IF r_d > r_c (liquidity cheaper):
       ASSERT fewer delays
       ASSERT higher liquidity allocation

3. Inter-agent comparison:
   - Compare timing strategies between agents
   - Document asymmetries with payment structure explanations

4. Report:
   - Joint policy evolution (text table)
   - Timing decision patterns
   - Cost component breakdown
```

### Phase 3: Anomaly Detection

Flag and report:

```
ANOMALIES TO DETECT:

1. Non-convergence
   - Cost increases in final 25% of iterations
   - Policy oscillation (alternating high/low values)

2. Constraint violations
   - Liquidity fraction outside [0, 1]
   - Negative costs (impossible)
   - Borrowing when liquidity sufficient

3. Inconsistent cost components
   - Zero delay cost with unsettled payments
   - Zero collateral cost with posted liquidity

4. Seed reproducibility failures
   - Different results with same seed (compare runs)
```

### Phase 4: Summary Report Format

The AI reviewer should produce a report in this structure:

```markdown
# Experiment Analysis Report

## Executive Summary
- Experiment: [exp1/exp2/exp3]
- Model: [model name]
- Status: [PASS/PARTIAL PASS/FAIL]
- Key Finding: [One sentence]

## Hypothesis Evaluation

### H[N]: [Hypothesis Name]
- **Result**: [PASS/FAIL/PARTIAL]
- **Evidence**:
  - [Quantitative finding 1]
  - [Quantitative finding 2]
- **Deviation Analysis**: [If applicable]

## Detailed Metrics

### Cost Evolution
| Iteration | Agent A Cost | Agent B Cost | Total | Delta |
|-----------|--------------|--------------|-------|-------|
| 0         | ...          | ...          | ...   | -     |
| 1         | ...          | ...          | ...   | ...   |
...

### Policy Evolution
| Iteration | Agent A Liquidity | Agent B Liquidity | A Threshold | B Threshold |
|-----------|-------------------|-------------------|-------------|-------------|
...

### Convergence Analysis
- Convergence iteration: [N or "Not converged"]
- Final cost stability (CV): [value]
- Policy stability (std): [value]

## Anomalies Detected
1. [Anomaly description if any]
2. ...

## Recommendations
1. [If FAIL: suggested adjustments]
2. [If PARTIAL: areas for investigation]

## Raw Data Reference
- Database: [path]
- Queries for verification: [SQL snippets]
```

---

## Human Reviewer Visualization Requirements

After AI analysis, generate these charts for human review:

### Required Charts

#### Chart 1: Cost Convergence (Line Plot)

```
Purpose: Show learning progress over iterations
X-axis: Iteration number (0 to max_iter)
Y-axis: Total cost (dollars)
Series:
  - Total system cost (solid line)
  - Agent A cost (dashed)
  - Agent B cost (dashed)
Annotations:
  - Horizontal line at theoretical optimum (if known)
  - Vertical line at convergence point (if achieved)
```

#### Chart 2: Liquidity Allocation Evolution (Line Plot)

```
Purpose: Show policy convergence
X-axis: Iteration number
Y-axis: Liquidity fraction (0.0 to 1.0)
Series:
  - Agent A liquidity fraction
  - Agent B liquidity fraction
Annotations:
  - Horizontal lines at theoretical optimal values (Exp1)
  - 95% confidence band for final 5 iterations
```

#### Chart 3: Cost Component Breakdown (Stacked Bar)

```
Purpose: Show cost structure at key iterations
X-axis: Iteration milestones (0, 25%, 50%, 75%, 100%)
Y-axis: Cost (dollars)
Stacks:
  - Collateral cost (blue)
  - Delay cost (orange)
  - Borrowing cost (red)
One group per agent, side by side
```

#### Chart 4: Nash Gap Evolution (Exp1 Only) (Line Plot)

```
Purpose: Show convergence to Nash equilibrium
X-axis: Iteration number
Y-axis: Nash gap (|actual - theoretical|)
Series:
  - Agent A Nash gap
  - Agent B Nash gap
Threshold line at 0.02 (acceptance threshold)
```

#### Chart 5: Policy Heatmap (Exp2/Exp3) (Heatmap)

```
Purpose: Show policy parameter evolution
X-axis: Iteration number
Y-axis: Policy parameters (liquidity_frac, urgency_threshold, liquidity_buffer)
Color: Parameter value (normalized 0-1)
Separate heatmap per agent
```

### Chart Generation Code Template

```python
# charts.py - Generate human-readable visualizations

import matplotlib.pyplot as plt
import pandas as pd
import duckdb

def generate_experiment_charts(db_path: str, output_dir: str) -> None:
    """Generate all required charts from experiment database."""
    conn = duckdb.connect(db_path)

    # Load iteration data
    df = conn.execute("""
        SELECT
            iteration_number,
            agent_id,
            old_cost,
            new_cost,
            -- Extract policy parameters from JSON
        FROM policy_iterations
        ORDER BY iteration_number, agent_id
    """).fetchdf()

    # Chart 1: Cost convergence
    fig, ax = plt.subplots(figsize=(10, 6))
    # ... plotting code ...
    plt.savefig(f"{output_dir}/01_cost_convergence.png", dpi=150)

    # Chart 2: Liquidity evolution
    # ... etc ...
```

### Chart Interpretation Guide

Include this legend with generated charts:

```
INTERPRETATION GUIDE FOR HUMAN REVIEWERS

Cost Convergence Chart:
- Downward slope = Learning is occurring
- Flat line at end = Convergence achieved
- Oscillation = Exploration or instability
- Gap to optimal = Room for improvement

Liquidity Allocation Chart:
- Convergence to horizontal = Policy stabilized
- Separation between agents = Asymmetric optima (expected)
- High variance at end = Non-convergence

Cost Breakdown Chart:
- Shift from orange/red to blue = Learning to avoid delays/borrowing
- Persistent orange = Delay strategy (may be optimal if r_d < r_c)
- Any red at end = Suboptimal (should have posted more liquidity)

Nash Gap Chart (Exp1):
- Both lines below threshold = Nash equilibrium found
- One above = Partial convergence
- Both above = Failed to find equilibrium
```

---

## Acceptance Criteria Summary

| Experiment | Primary Criterion | Secondary Criteria |
|------------|-------------------|-------------------|
| **Exp1** | Nash gap < 0.02 for both agents | Cost within 10% of theoretical |
| **Exp2** | Cost reduction > 30% | Convergence before max_iter - 5 |
| **Exp3** | Joint cost < sum of individual optima | Policy asymmetry matches cost structure |

### Pass/Fail Decision Tree

```
FOR EACH EXPERIMENT:

1. Did the experiment complete without errors?
   NO → FAIL (Infrastructure)
   YES → Continue

2. Did costs decrease overall (final < initial)?
   NO → FAIL (No Learning)
   YES → Continue

3. Experiment-specific check:
   Exp1: Is Nash gap < 0.02?
   Exp2: Is cost reduction > 30%?
   Exp3: Is joint optimization better than individual?

   NO → PARTIAL PASS (Learning but not optimal)
   YES → Continue

4. Did policy converge (stability check)?
   NO → PARTIAL PASS (Found optimum but unstable)
   YES → PASS
```

---

## Appendix: Query Reference

### DuckDB Queries for Analysis

```sql
-- Get iteration costs
SELECT
    iteration_number,
    agent_id,
    new_cost / 100.0 as cost_dollars
FROM policy_iterations
ORDER BY iteration_number, agent_id;

-- Get final policies
SELECT
    agent_id,
    policy_json
FROM policy_iterations
WHERE iteration_number = (SELECT MAX(iteration_number) FROM policy_iterations)
AND was_accepted = true;

-- Cost component breakdown (requires event detail)
SELECT
    pi.iteration_number,
    pi.agent_id,
    -- Parse cost components from policy evaluation
FROM policy_iterations pi;

-- Convergence detection
WITH cost_deltas AS (
    SELECT
        iteration_number,
        SUM(new_cost) as total_cost,
        LAG(SUM(new_cost)) OVER (ORDER BY iteration_number) as prev_cost
    FROM policy_iterations
    GROUP BY iteration_number
)
SELECT
    MIN(iteration_number) as convergence_iter
FROM cost_deltas
WHERE ABS(total_cost - prev_cost) < 100  -- $1 threshold
AND iteration_number > 5;
```

## References

- Castro, M., et al. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
- [ai_cash_mgmt Documentation](../../docs/reference/ai_cash_mgmt/index.md)
- [SimCash Architecture](../../docs/architecture.md)
