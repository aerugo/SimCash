# Castro Experiments

LLM-based replication of Castro et al. (2025) "Estimating Policy Functions in Payment Systems Using Reinforcement Learning" using the SimCash `ai_cash_mgmt` module.

## Overview

This module implements experiments from the Castro et al. (2025) paper, replacing the original reinforcement learning approach with **LLM-based policy optimization**. The goal is to validate whether large language models can discover optimal liquidity management policies in high-value payment systems (HVPS).

**Key Features:**
- Three experiments matching the paper's scenarios (2-period, 12-period, joint optimization)
- LLM-based policy generation via **PydanticAI** (unified multi-provider support)
- Support for Anthropic Claude, OpenAI GPT, and Google Gemini
- Provider-specific reasoning features (thinking tokens, reasoning effort)
- Bootstrap policy evaluation with paired comparison
- Deterministic execution via seeded RNG
- Full persistence to DuckDB with replay support

---

## Architecture

### Module Structure

```
experiments/castro/
├── castro/                          # Core implementation
│   ├── __init__.py                  # Public API exports
│   ├── audit_display.py             # Audit mode display (--audit flag)
│   ├── bootstrap_context.py         # EnrichedBootstrapContextBuilder for LLM context
│   ├── constraints.py               # CASTRO_CONSTRAINTS (paper-aligned rules)
│   ├── context_builder.py           # BootstrapContextBuilder (simulation context)
│   ├── display.py                   # Unified display (StateProvider pattern)
│   ├── events.py                    # Event model for replay identity
│   ├── experiments.py               # Experiment definitions (YAML-driven)
│   ├── persistence/
│   │   ├── models.py                # Database models (ExperimentRunRecord)
│   │   └── repository.py            # DuckDB persistence operations
│   ├── pydantic_llm_client.py       # PydanticAI LLM client (multi-provider)
│   ├── run_id.py                    # Run ID generation
│   ├── runner.py                    # ExperimentRunner orchestration
│   ├── simulation.py                # CastroSimulationRunner
│   ├── state_provider.py            # StateProvider pattern for replay
│   ├── verbose_capture.py           # Verbose output capture
│   └── verbose_logging.py           # VerboseConfig, VerboseLogger
├── configs/                         # Scenario YAML configurations
│   ├── exp1_2period.yaml            # 2-period deterministic scenario
│   ├── exp2_12period.yaml           # 12-period stochastic scenario
│   └── exp3_joint.yaml              # Joint optimization scenario
├── experiments/                     # Experiment config YAML files
│   ├── exp1.yaml                    # 2-Period Deterministic Nash Equilibrium
│   ├── exp2.yaml                    # 12-Period Stochastic LVTS-Style
│   └── exp3.yaml                    # Joint Liquidity & Timing Optimization
├── papers/
│   └── castro_et_al.md              # Full paper text for reference
├── tests/                           # Comprehensive test suite
│   ├── test_bootstrap_context.py    # Bootstrap context builder tests
│   ├── test_cli_audit.py            # CLI audit flag tests
│   ├── test_cli_commands.py         # CLI command tests
│   ├── test_deterministic_mode.py   # Deterministic mode tests
│   ├── test_display.py              # Display function tests
│   ├── test_events.py               # Event model tests
│   ├── test_experiments.py          # Experiment unit tests
│   ├── test_pydantic_llm_client.py  # PydanticAI client tests
│   ├── test_run_id.py               # Run ID tests
│   ├── test_state_provider.py       # StateProvider tests
│   └── test_verbose_logging.py      # Verbose logging tests
├── cli.py                           # Typer CLI entry point
├── pyproject.toml                   # Package configuration
└── README.md                        # This file
```

### Integration with SimCash Components

Castro experiments leverage the SimCash `ai_cash_mgmt` module for core functionality:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Castro Experiment Layer                          │
├─────────────────────────────────────────────────────────────────────────┤
│  CastroExperiment      │  ExperimentRunner       │  PydanticAILLMClient │
│  (config dataclass)    │  (orchestration loop)   │  (LLM integration)   │
└────────────┬───────────┴───────────┬─────────────┴───────────┬──────────┘
             │                       │                         │
             ▼                       ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     payment_simulator.ai_cash_mgmt                      │
├─────────────────────────────────────────────────────────────────────────┤
│  BootstrapPolicyEvaluator  │  PolicyOptimizer    │  ConvergenceDetector │
│  BootstrapSampler          │  ConstraintValidator│  SeedManager         │
│  TransactionHistoryCollector│  GameRepository    │  SingleAgentPrompts  │
└────────────┬───────────────┴───────────┬────────┴───────────┬───────────┘
             │                           │                    │
             ▼                           ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     payment_simulator (Rust Core)                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Orchestrator              │  Settlement Engine   │  Policy Execution   │
│  (tick loop, state mgmt)   │  (RTGS, queues)      │  (decision trees)   │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Components Used:**

| SimCash Component | Castro Usage |
|------------------|--------------|
| `BootstrapPolicyEvaluator` | Evaluates policies using bootstrap resampling |
| `BootstrapSampler` | Generates bootstrap samples from transaction history |
| `PolicyOptimizer` | LLM-based policy generation with validation |
| `ConstraintValidator` | Enforces Castro paper rules (CASTRO_CONSTRAINTS) |
| `ConvergenceDetector` | Detects policy stability for stopping criteria |
| `SeedManager` | Manages deterministic RNG seeds |
| `GameRepository` | Persists sessions and iterations to DuckDB |
| `LLMConfig` | Unified LLM configuration (from `payment_simulator.llm`) |

---

## The Castro Paper

### Reference

Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). *Estimating Policy Functions in Payment Systems Using Reinforcement Learning*. ACM Transactions on Economics and Computation, 13(1), Article 1.

The full paper is available at: `papers/castro_et_al.md`

### Paper Summary

The paper addresses **liquidity management in high-value payment systems (HVPS)**, where banks must balance:

1. **Initial liquidity cost** (`r_c`): Cost of posting collateral at the start of the day
2. **Delay cost** (`r_d`): Cost of delaying customer payments
3. **End-of-day borrowing cost** (`r_b`): Emergency borrowing from central bank

Banks face a **strategic game**: posting more liquidity is costly, but delaying payments to wait for incoming funds risks customer dissatisfaction. The paper shows that RL agents can learn optimal policies even without complete knowledge of the environment.

### Cost Structure (Paper Section 3)

| Cost Type | Formula | When Incurred |
|-----------|---------|---------------|
| Initial liquidity | `r_c × ℓ₀` | Start of day (t=0) |
| Delay | `r_d × P_t(1 - x_t)` | Each period with delayed payments |
| End-of-day borrowing | `r_b × c_b` | End of day if shortfall |

**Assumption:** `r_c < r_d < r_b` (collateral cheaper than delay, delay cheaper than emergency borrowing)

---

## Experiment Mapping: Paper → SimCash

### Experiment 1: 2-Period Deterministic (Paper Section 4, 6.3)

**Paper Setup:**
- 2 time periods (T=2)
- Known, fixed payment demands
- Agent A: receives payment in period 1, pays in period 2
- Agent B: pays in period 1, receives in period 2
- Analytical Nash equilibrium exists

**SimCash Implementation (`exp1`):**
```yaml
# configs/exp1_2period.yaml
ticks_per_day: 2
days: 1
# Fixed transactions - no stochastic arrivals
transactions:
  - sender: BANK_A, receiver: BANK_B, amount: 15000, arrival_tick: 0
  - sender: BANK_B, receiver: BANK_A, amount: 20000, arrival_tick: 0
```

**Expected Outcomes:**
| Agent | Optimal Liquidity | Optimal Cost | Reasoning |
|-------|-------------------|--------------|-----------|
| Bank A | 0% | $0.00 | Free-rides on B's payment in period 1 |
| Bank B | 20% (20,000 / collateral) | $20.00 | Must cover period-1 demand |

**Validation Protocol:**
1. Run `castro run exp1` until convergence
2. Extract final `initial_liquidity_fraction` for each agent
3. Compute Nash gap: `|learned - theoretical|`
4. **Pass criteria:** Nash gap < 0.02 for both agents

### Experiment 2: 12-Period Stochastic (Paper Section 6.4)

**Paper Setup:**
- 12 time periods (hourly, 6am-6pm)
- Payment demands drawn from LVTS data (Poisson arrivals, LogNormal amounts)
- No analytical solution; brute-force benchmark available
- Agents learn to reduce costs over iterations

**SimCash Implementation (`exp2`):**
```yaml
# configs/exp2_12period.yaml
ticks_per_day: 12
days: 1
# Stochastic arrivals
agent_configs:
  - id: BANK_A
    arrivals:
      rate_per_tick: 2.5  # Poisson λ
      amount_distribution: lognormal
      amount_mean: 10000
      amount_std: 5000
```

**Expected Outcomes:**
- Total costs decrease monotonically over iterations
- Higher-demand agent posts more collateral
- Cost reduction > 30% from initial to final iteration
- Policy stability in final 5 iterations (CV < 0.1)

**Validation Protocol:**
1. Run `castro run exp2 --seed 42`
2. Track cost trajectory per iteration
3. Compute cost reduction rate: `(initial - final) / initial`
4. Verify liquidity ordering matches payment demand ordering
5. **Pass criteria:** Cost reduction > 30%, convergence within max_iterations - 5

### Experiment 3: Joint Liquidity & Timing (Paper Section 7)

**Paper Setup:**
- 3 time periods (T=3)
- Agents choose BOTH initial liquidity AND intraday timing
- Tests interaction between liquidity and delay decisions
- Special case: indivisible payment in period 2

**SimCash Implementation (`exp3`):**
```yaml
# configs/exp3_joint.yaml
ticks_per_day: 3
days: 1
# Indivisible payment constraint for BANK_B in period 2
constraints:
  BANK_B:
    period_2_indivisible: true
```

**Expected Outcomes:**
- When `r_d < r_c`: Agents delay more, post less collateral
- When `r_d > r_c`: Agents post more, delay less
- Agent B (with indivisible payment) delays period-1 payments strategically

**Validation Protocol:**
1. Run under both cost orderings (`r_d < r_c` and `r_d > r_c`)
2. Compare timing decisions between agents
3. Verify asymmetric behavior matches payment structure
4. **Pass criteria:** Timing strategy adapts correctly to cost structure

---

## Castro Constraints

The `CASTRO_CONSTRAINTS` object enforces paper-aligned rules:

```python
from castro.constraints import CASTRO_CONSTRAINTS

# Allowed policy parameters
CASTRO_CONSTRAINTS.allowed_parameters = [
    # Fraction of collateral to post at t=0 (paper: x_0 ∈ [0,1])
    ParameterSpec(name="initial_liquidity_fraction", min=0.0, max=1.0),

    # Ticks before deadline to release payment
    ParameterSpec(name="urgency_threshold", min=0, max=20),

    # Multiplier for required liquidity
    ParameterSpec(name="liquidity_buffer", min=0.5, max=3.0),
]

# Allowed actions (paper: x_t ∈ {0, 1} for indivisible, [0,1] for divisible)
CASTRO_CONSTRAINTS.allowed_actions = {
    "payment_tree": ["Release", "Hold"],      # Send or delay
    "collateral_tree": ["PostCollateral", "HoldCollateral"],
    "bank_tree": ["NoAction"],                # No interbank borrowing
}
```

---

## Quick Start

### Installation

```bash
# Navigate to castro experiments
cd experiments/castro

# Install dependencies (ALWAYS use UV, never pip!)
uv sync --extra dev
```

### Running Experiments

```bash
# List available experiments
uv run castro list

# Run experiment 1 (2-period deterministic)
uv run castro run exp1

# Run with specific model
uv run castro run exp2 --model anthropic:claude-sonnet-4-5

# Run with Anthropic extended thinking
uv run castro run exp1 --model anthropic:claude-sonnet-4-5 --thinking-budget 8000

# Run with OpenAI high reasoning
uv run castro run exp1 --model openai:gpt-5.1 --reasoning-effort high
```

### Viewing Results

```bash
# List experiment runs
uv run castro results

# Replay a specific run
uv run castro replay exp1-20251210-143022-a1b2c3

# Replay with audit trail (shows full LLM prompts/responses)
uv run castro replay exp1-20251210-143022-a1b2c3 --audit --start 1 --end 3
```

---

## CLI Reference

### `run` - Execute an experiment

```bash
uv run castro run <experiment> [OPTIONS]

Arguments:
  experiment    Experiment key: exp1, exp2, or exp3

Options:
  -m, --model TEXT              LLM model in provider:model format
                                [default: anthropic:claude-sonnet-4-5]
  -t, --thinking-budget INT     Token budget for Anthropic extended thinking
  -r, --reasoning-effort TEXT   OpenAI reasoning effort: low, medium, high
  -i, --max-iter INT            Max iterations [default: 25]
  -o, --output PATH             Output directory [default: results]
  -s, --seed INT                Master seed [default: 42]

Verbose Output:
  -v, --verbose              Enable all verbose output
  -q, --quiet                Suppress verbose output
  --verbose-policy           Show policy parameter changes
  --verbose-bootstrap        Show per-sample bootstrap results
  --verbose-llm              Show LLM call metadata
  --verbose-rejections       Show rejection analysis

Debug Output:
  -d, --debug                Show debug output (validation errors, retries)
```

### `replay` - Replay experiment output

```bash
uv run castro replay <run_id> [OPTIONS]

Arguments:
  run_id    Run ID to replay

Options:
  -d, --db PATH                Database path [default: results/castro.db]
  -v, --verbose                Enable all verbose output
  --verbose-bootstrap          Show bootstrap evaluations
  --verbose-llm                Show LLM call details
  --verbose-policy             Show policy changes

Audit Mode:
  --audit                      Show detailed audit trail
  --start N                    Start iteration (inclusive)
  --end M                      End iteration (inclusive)
```

### Other Commands

```bash
# List experiments
uv run castro list

# Show experiment details
uv run castro info exp1

# Validate experiment configuration
uv run castro validate exp2

# List all runs from database
uv run castro results --experiment exp1 --limit 10
```

---

## Evaluation and Analysis Protocol

### For AI Reviewers

Use this structured protocol to evaluate experiment results:

#### Phase 1: Data Extraction

```
FOR EACH EXPERIMENT RUN:
1. Metadata: experiment_name, model, seed, max_iterations
2. Per-Iteration: liquidity_fraction, costs (per agent), acceptance status
3. Final State: best policies, convergence reason, total duration
```

#### Phase 2: Hypothesis Testing

**H1 (Exp1 - Nash Equilibrium):**
```python
# Compute Nash gaps
nash_gap_A = abs(bank_a_liquidity_frac - 0.0)
nash_gap_B = abs(bank_b_liquidity_frac - 0.20)

# Classification
if nash_gap_A < 0.02 and nash_gap_B < 0.02:
    result = "PASS - Nash equilibrium achieved"
elif nash_gap_A < 0.05 and nash_gap_B < 0.05:
    result = "PARTIAL PASS - Near Nash equilibrium"
else:
    result = "FAIL - Significant deviation"
```

**H2 (Exp2 - Learning):**
```python
# Cost reduction check
reduction_rate = (costs[0] - costs[-1]) / costs[0]
# Target: > 0.30 (30% reduction)

# Monotonicity check
negative_deltas = sum(1 for i in range(1, len(costs)) if costs[i] < costs[i-1])
monotonicity_score = negative_deltas / (len(costs) - 1)
# Target: > 0.70 (70% of iterations reduce cost)
```

**H3 (Exp3 - Joint Optimization):**
```python
# Verify cost structure sensitivity
if r_d < r_c:
    assert more_delays_observed
    assert lower_liquidity_allocation
else:
    assert fewer_delays
    assert higher_liquidity_allocation
```

### For Human Reviewers

Generate these charts for visual analysis:

1. **Cost Convergence** (Line Plot): X=iteration, Y=total cost
2. **Liquidity Evolution** (Line Plot): X=iteration, Y=liquidity fraction
3. **Cost Component Breakdown** (Stacked Bar): collateral/delay/borrowing
4. **Nash Gap** (Line Plot, exp1 only): deviation from theoretical optimum

### DuckDB Queries for Analysis

```sql
-- Get iteration costs
SELECT iteration_number, agent_id, new_cost / 100.0 as cost_dollars
FROM policy_iterations
ORDER BY iteration_number, agent_id;

-- Get final policies
SELECT agent_id, policy_json
FROM policy_iterations
WHERE iteration_number = (SELECT MAX(iteration_number) FROM policy_iterations)
AND was_accepted = true;

-- Compute cost reduction
WITH bounds AS (
    SELECT MIN(iteration_number) as first_iter,
           MAX(iteration_number) as last_iter
    FROM policy_iterations
)
SELECT
    (SELECT SUM(new_cost) FROM policy_iterations WHERE iteration_number = first_iter) as initial,
    (SELECT SUM(new_cost) FROM policy_iterations WHERE iteration_number = last_iter) as final
FROM bounds;
```

---

## Programmatic Usage

```python
import asyncio
from castro import create_exp1, ExperimentRunner

# Create experiment with default Anthropic model
exp = create_exp1(model="anthropic:claude-sonnet-4-5")

# Or with OpenAI and reasoning effort
exp = create_exp1(
    model="openai:gpt-5.1",
    reasoning_effort="high",
)

# Or with Anthropic extended thinking
exp = create_exp1(
    model="anthropic:claude-sonnet-4-5",
    thinking_budget=8000,
)

# Run optimization
runner = ExperimentRunner(exp)
result = asyncio.run(runner.run())

# Access results
print(f"Run ID: {result.run_id}")
print(f"Final cost: ${result.final_cost / 100:.2f}")
print(f"Converged: {result.converged}")
print(f"Iterations: {result.num_iterations}")

# Per-agent costs
for agent_id, cost in result.per_agent_costs.items():
    print(f"  {agent_id}: ${cost / 100:.2f}")

# Best policies found
for agent_id, policy in result.best_policies.items():
    print(f"{agent_id}: {policy}")
```

---

## LLM Providers

Supports multiple providers via PydanticAI with unified `provider:model` format:

| Provider | Example Models | Special Features |
|----------|----------------|------------------|
| `anthropic` | `claude-sonnet-4-5`, `claude-opus-4` | `--thinking-budget` for extended thinking |
| `openai` | `gpt-4o`, `gpt-5.1`, `o1`, `o3` | `--reasoning-effort` (low/medium/high) |
| `google` | `gemini-2.5-flash`, `gemini-2.5-pro` | Google AI thinking config |

Set API keys via environment variables or `.env` file:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=...
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

## Testing

```bash
cd experiments/castro
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_experiments.py -v

# Run with coverage
uv run pytest tests/ --cov=castro --cov-report=html
```

---

## Design Principles

1. **Paper Fidelity**: Experiments match Castro et al. (2025) setup
2. **Deterministic Replay**: Same seed produces identical results
3. **Type Safe**: Full type annotations, mypy strict mode
4. **Testable**: Comprehensive unit and integration tests
5. **Observable**: Rich verbose output and audit trails

---

## References

- Castro, M., et al. (2025). "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"
- [ai_cash_mgmt Documentation](../../docs/reference/ai_cash_mgmt/index.md)
- [LLM Module Documentation](../../docs/reference/llm/index.md)
- [Experiments Framework](../../docs/reference/experiments/index.md)
- [SimCash Architecture](../../docs/architecture.md)

---

*Last updated: 2025-12-11*
