# Castro Experiment - Complete Technical Documentation

**Last Updated**: 2025-12-03
**Author**: Claude (AI Research Assistant)

---

## 1. Executive Summary

The `experiments/castro/` directory contains a **research environment** for replicating and extending Castro et al. (2025) "Strategic Payment Timing" paper using **LLM-based policy optimization** instead of reinforcement learning. The experiment uses large language models (GPT-4o/GPT-5.1) to iteratively generate and refine payment settlement policies for banks in a simulated high-value payment system.

**Key Results** (from RESEARCH_PAPER.md):
- **92.5% cost reduction** in deterministic 2-period scenarios
- **99.95% cost reduction** in joint learning symmetric scenarios
- **10x sample efficiency** compared to RL (~10 iterations vs ~100 episodes)
- **Stochastic environments remain challenging** (8.5% cost increase in Exp 2)

---

## 2. Research Context and Hypotheses

### 2.1 The Castro Paper (2025)

Castro et al. demonstrated that **reinforcement learning** can discover near-optimal policies for banks in high-value payment systems (HVPS). Banks face a **liquidity-delay tradeoff**:
- Post more collateral → Higher opportunity cost, but payments settle immediately
- Post less collateral → Lower cost, but payments may be delayed or fail at EOD

### 2.2 Research Hypotheses

**Primary Hypothesis**: LLMs can discover near-optimal policies through iterative refinement with:
1. Greater sample efficiency than RL (~10 iterations vs ~100 episodes)
2. Interpretable policies (decision trees vs opaque neural networks)
3. Novel policy mechanisms through explicit reasoning

**Secondary Hypotheses**:
- H1: LLM will discover asymmetric Nash equilibrium in 2-period scenario
- H2: LLM will achieve comparable cost reduction to RL in 12-period scenario
- H3: LLM can jointly optimize liquidity AND payment timing (3-period scenario)

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    EXPERIMENT RUNNER LAYER                              │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐    │
│  │ reproducible_experiment │    │     robust_experiment.py        │    │
│  │         .py             │    │  (constrained schema version)   │    │
│  └───────────┬─────────────┘    └──────────────┬──────────────────┘    │
│              │                                  │                       │
│              └──────────────┬───────────────────┘                       │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    LLM OPTIMIZER LAYER                            │  │
│  │  ┌────────────────┐   ┌───────────────────────────────────────┐  │  │
│  │  │  LLMOptimizer  │──▶│         RobustPolicyAgent             │  │  │
│  │  │   (wrapper)    │   │  (PydanticAI structured output)       │  │  │
│  │  └────────────────┘   └───────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                             │                                           │
│                             ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    SCHEMA LAYER                                   │  │
│  │  ┌─────────────────┐   ┌───────────────────┐   ┌──────────────┐  │  │
│  │  │ScenarioConstraints│ │ Dynamic Schema   │   │ Depth-Limited│  │  │
│  │  │ + ParameterSpec │──▶│   Generation     │──▶│ Tree Models  │  │  │
│  │  └─────────────────┘   └───────────────────┘   │  (L0-L5)     │  │  │
│  │                                                └──────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ FFI (payment-sim CLI)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          SIMCASH BACKEND                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  payment-sim run --config <yaml> --seed <N> --output-format json │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                              │                                          │
│  ┌───────────────┐  ┌───────────────┐  ┌────────────────────────────┐  │
│  │ RTGS Engine   │  │ Cost Model    │  │  Castro Features           │  │
│  │ (settlement)  │  │ (collateral,  │  │ • deferred_crediting: true │  │
│  │               │  │  delay, EOD)  │  │ • deadline_cap_at_eod: true│  │
│  └───────────────┘  └───────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       PERSISTENCE LAYER (DuckDB)                         │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐   │
│  │ experiment_config  │  │ policy_iterations  │  │ llm_interactions │   │
│  └────────────────────┘  └────────────────────┘  └──────────────────┘   │
│  ┌────────────────────┐  ┌────────────────────┐  ┌──────────────────┐   │
│  │  simulation_runs   │  │ iteration_metrics  │  │validation_errors │   │
│  └────────────────────┘  └────────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Core Classes and Data Structures

### 4.1 Schema Layer (`schemas/`)

#### `ParameterSpec` (parameter_config.py:18-67)
Defines a single tunable policy parameter with bounds:

```python
class ParameterSpec(BaseModel):
    name: str           # e.g., "urgency_threshold"
    min_value: float    # e.g., 0.0
    max_value: float    # e.g., 20.0
    default: float      # e.g., 3.0
    description: str    # For LLM prompt
```

#### `ScenarioConstraints` (parameter_config.py:70-155)
Defines all allowed elements for a scenario:

```python
class ScenarioConstraints(BaseModel):
    allowed_parameters: list[ParameterSpec]  # Tunable params
    allowed_fields: list[str]                # Context fields (e.g., "balance")
    allowed_actions: list[str]               # Actions (e.g., "Release", "Hold")
```

#### Pre-defined Constraint Sets (`parameter_sets.py`)

| Set | Parameters | Fields | Actions | Use Case |
|-----|-----------|--------|---------|----------|
| `MINIMAL_CONSTRAINTS` | 1 (urgency_threshold) | 5 | 2 | Simple experiments |
| `STANDARD_CONSTRAINTS` | 4 | 19 | 3 | Typical experiments |
| `FULL_CONSTRAINTS` | 10 | All | All | Maximum flexibility |

#### Depth-Limited Tree Models (`tree.py`)

**Key Innovation**: Solves OpenAI's structured output limitation (no recursive schemas) by creating explicit types for each depth level:

```python
TreeNodeL0 = ActionNode              # Leaf only
TreeNodeL1 = Action | ConditionL1   # Condition with L0 children
TreeNodeL2 = Action | ConditionL2   # Condition with L1 children
...
TreeNodeL5 = Action | ConditionL5   # Max depth (5 levels)
```

This allows policy trees up to 5 levels deep while maintaining valid Pydantic schemas for LLM structured output.

### 4.2 Field and Action Registry (`registry.py`)

Categories of context fields available to policies:

| Category | Count | Examples |
|----------|-------|----------|
| Transaction | 15 | `amount`, `ticks_to_deadline`, `priority` |
| Agent | 10 | `balance`, `effective_liquidity`, `credit_limit` |
| Queue | 5 | `outgoing_queue_size`, `queue1_total_value` |
| Queue2 (RTGS) | 6 | `rtgs_queue_size`, `queue2_nearest_deadline` |
| Collateral | 11 | `posted_collateral`, `max_collateral_capacity` |
| Time | 8 | `current_tick`, `ticks_remaining_in_day` |
| LSM | 15 | `my_bilateral_net_q2`, `tx_counterparty_id` |

Available actions:
- **Payment tree**: `Release`, `Hold`, `Split`
- **Collateral tree**: `PostCollateral`, `HoldCollateral`, `WithdrawCollateral`

### 4.3 Generator Layer (`generator/`)

#### `RobustPolicyAgent` (robust_policy_agent.py:333-511)

Main policy generation class using PydanticAI:

```python
class RobustPolicyAgent:
    def __init__(
        self,
        constraints: ScenarioConstraints,  # Defines allowed elements
        model: str = "gpt-4o",             # LLM model
        retries: int = 3,                   # Retry on validation failure
        reasoning_effort: Literal["low", "medium", "high"] = "high",
    ) -> None

    def generate_policy(
        self,
        instruction: str,              # Natural language instruction
        current_policy: dict | None,   # Policy to improve
        current_cost: float | None,    # Current performance
        settlement_rate: float | None, # Current settlement rate
        iteration: int = 0,            # Optimization iteration
    ) -> dict[str, Any]:               # Returns validated policy
```

**Key features**:
1. Dynamically generates Pydantic models from constraints
2. Uses few-shot learning with examples in system prompt
3. Enforces parameter bounds, allowed fields, and allowed actions
4. Supports GPT-4o, GPT-5.1, and other models via PydanticAI

#### Dynamic Schema Generation (`dynamic.py`)

`create_constrained_policy_model(constraints)` generates a Pydantic model at runtime that:
- Creates `Literal` types for allowed fields and actions
- Creates bounded `float` fields for parameters
- Builds nested tree node models with correct typing

### 4.4 Experiment Runner Layer (`scripts/`)

#### `ReproducibleExperiment` (reproducible_experiment.py:913-1424)

Main experiment orchestrator:

```python
class ReproducibleExperiment:
    def __init__(
        self,
        experiment_key: str,       # "exp1", "exp2", "exp3"
        db_path: str,              # DuckDB output path
        simcash_root: str,         # SimCash installation
        model: str = "gpt-4o",     # LLM model
        reasoning_effort: str,     # "low", "medium", "high"
    )

    def run(self) -> dict:  # Runs full optimization loop
```

**Optimization Loop**:
1. Load seed policies (read-only, never modified)
2. For each iteration:
   a. Create iteration-specific policy files
   b. Run parallel simulations (10 seeds)
   c. Compute metrics (mean, std, settlement rate)
   d. Check convergence
   e. Call LLM to generate improved policies
   f. Validate policies (retry up to 3x if invalid)
   g. Store everything to DuckDB
3. Export summary

#### `ExperimentDatabase` (reproducible_experiment.py:260-627)

DuckDB wrapper for experiment tracking with tables:

| Table | Purpose |
|-------|---------|
| `experiment_config` | Full experiment configuration |
| `policy_iterations` | Every policy version with hash |
| `llm_interactions` | All prompts/responses with token counts |
| `simulation_runs` | Per-seed simulation results |
| `iteration_metrics` | Aggregated metrics per iteration |
| `validation_errors` | Policy validation failures for analysis |

---

## 5. Data Flow

### 5.1 Policy Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. PROMPT CONSTRUCTION                                          │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ generate_system_prompt(constraints)                     │   │
│    │ • Critical rules                                        │   │
│    │ • Allowed vocabulary (params, fields, actions)          │   │
│    │ • Few-shot examples (valid JSON)                        │   │
│    │ • Common errors to avoid                                │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 2. LLM CALL (PydanticAI)                                        │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ agent.run_sync(prompt, deps=context)                    │   │
│    │ • Structured output → DynamicPolicy model               │   │
│    │ • Automatic validation against schema                   │   │
│    │ • Retries on validation failure                         │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 3. POLICY VALIDATION (SimCash CLI)                              │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ payment-sim validate-policy <policy.json> --format json │   │
│    │ • Validates against Rust backend schema                 │   │
│    │ • Returns errors or success                             │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 4. OUTPUT: Validated policy dict ready for simulation            │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Simulation Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. CREATE ITERATION CONFIG                                       │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ create_iteration_config(iteration)                      │   │
│    │ • Write policies to iter_XXX_policy_{a,b}.json          │   │
│    │ • Create modified YAML config pointing to policy files  │   │
│    │ • Store in output/configs/ and output/policies/         │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 2. PARALLEL SIMULATION (ProcessPoolExecutor)                     │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ For each seed in [1, 2, ..., 10]:                       │   │
│    │   payment-sim run --config <iter.yaml> --seed <N>       │   │
│    │   → Returns JSON with costs, settlement_rate, events    │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 3. METRIC AGGREGATION                                            │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ compute_metrics(results)                                │   │
│    │ • Mean cost ± std                                       │   │
│    │ • Settlement rate                                       │   │
│    │ • Best/worst seed                                       │   │
│    │ • Risk-adjusted cost (mean + std)                       │   │
│    └────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│ 4. PERSISTENCE (DuckDB)                                          │
│    ┌────────────────────────────────────────────────────────┐   │
│    │ • Record simulation_runs (per-seed results)             │   │
│    │ • Record iteration_metrics (aggregated)                 │   │
│    │ • Record llm_interactions (prompt, response, tokens)    │   │
│    └────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Configuration System

### 6.1 Experiment Definitions (`scripts/reproducible_experiment.py:185-219`)

```python
EXPERIMENTS = {
    "exp1": {
        "name": "Experiment 1: Two-Period Deterministic",
        "config_path": "configs/castro_2period_aligned.yaml",
        "policy_a_path": "policies/seed_policy.json",
        "policy_b_path": "policies/seed_policy.json",
        "num_seeds": 1,       # Deterministic - only need 1
        "max_iterations": 25,
        "convergence_threshold": 0.05,  # 5% cost change
        "convergence_window": 3,        # 3 stable iterations
    },
    "exp2": { ... },  # 12-period stochastic
    "exp3": { ... },  # Joint learning
}
```

### 6.2 Simulation Configuration (castro_2period_aligned.yaml)

**Castro-Alignment Features**:
```yaml
# CRITICAL for Castro paper replication
deferred_crediting: true      # Credits applied at END of tick
deadline_cap_at_eod: true     # All deadlines capped at day end
```

**Cost Structure**:
```yaml
cost_rates:
  collateral_cost_per_tick_bps: 500    # 5% per tick collateral cost
  delay_cost_per_tick_per_cent: 0.001  # 0.1% delay cost per cent
  overdraft_bps_per_tick: 2000         # 20% overdraft penalty
  eod_penalty_per_transaction: 0       # Disabled for Castro model
```

**Payment Profile (Deterministic)**:
```yaml
scenario_events:
  # Bank A: $150 outgoing in period 2 (tick 1)
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 15000  # cents
    deadline: 2
    schedule:
      type: OneTime
      tick: 1
```

### 6.3 Seed Policy Structure (`policies/seed_policy.json`)

```json
{
  "version": "2.0",
  "policy_id": "castro_aligned_seed_policy",
  "description": "Seed policy for Castro-aligned experiments",

  "parameters": {
    "urgency_threshold": 3.0,
    "initial_liquidity_fraction": 0.25,
    "liquidity_buffer_factor": 1.0
  },

  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_tick_zero",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        }
      }
    },
    "on_false": {"type": "action", "action": "HoldCollateral"}
  },

  "payment_tree": {
    "type": "condition",
    "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, ...},
    "on_true": {"type": "action", "action": "Release"},
    "on_false": { /* nested condition for liquidity check */ }
  }
}
```

---

## 7. State Management

### 7.1 In-Memory State (ReproducibleExperiment)

```python
class ReproducibleExperiment:
    # Configuration (immutable after init)
    self.experiment_def: dict      # Experiment definition
    self.config: dict              # Simulation config (YAML)
    self.seed_policy_a: dict       # Initial policy A (read-only)
    self.seed_policy_b: dict       # Initial policy B (read-only)

    # Current state (mutable)
    self.policy_a: dict            # Current Bank A policy
    self.policy_b: dict            # Current Bank B policy
    self.history: list[dict]       # Cost history for convergence
    self.current_config_path: Path # Current iteration config

    # Settings
    self.num_seeds: int            # Seeds per iteration
    self.max_iterations: int       # Max optimization iterations
    self.convergence_threshold: float
    self.convergence_window: int
```

### 7.2 Persistent State (DuckDB)

**Schema** (reproducible_experiment.py:60-178):

```sql
-- Experiment-level config
CREATE TABLE experiment_config (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    config_yaml TEXT NOT NULL,
    config_hash VARCHAR(64) NOT NULL,
    cost_rates JSON NOT NULL,
    agent_configs JSON NOT NULL,
    model_name VARCHAR NOT NULL,
    reasoning_effort VARCHAR NOT NULL,
    num_seeds INTEGER NOT NULL,
    max_iterations INTEGER NOT NULL,
    ...
);

-- Per-iteration policies
CREATE TABLE policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    parameters JSON NOT NULL,
    created_by VARCHAR NOT NULL,  -- 'init', 'llm', 'manual'
    ...
);

-- Individual simulation runs
CREATE TABLE simulation_runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    total_cost BIGINT NOT NULL,    -- cents (i64)
    bank_a_cost BIGINT NOT NULL,
    bank_b_cost BIGINT NOT NULL,
    settlement_rate DOUBLE NOT NULL,
    ...
);
```

---

## 8. SimCash Integration

### 8.1 How Castro Uses SimCash

The experiment **does not import SimCash as a Python library**. Instead, it:

1. **Calls the CLI** (`payment-sim`) via subprocess
2. **Passes configuration** via YAML files
3. **Receives results** as JSON output

```python
# From run_single_simulation()
cmd = [
    str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
    "run",
    "--config", str(config_path),
    "--seed", str(seed),
]
result = subprocess.run(cmd, capture_output=True, text=True)
output = json.loads(result.stdout)
```

### 8.2 Key SimCash Features Used

**Castro-Alignment Features** (implemented in Rust backend):

| Feature | Config Key | Purpose |
|---------|------------|---------|
| Deferred Crediting | `deferred_crediting: true` | Credits apply at END of tick, not immediately |
| Deadline Cap at EOD | `deadline_cap_at_eod: true` | All deadlines capped at day end |
| Custom Transaction Arrivals | `scenario_events` | Deterministic payment injection |
| Policy Trees | `policy.type: FromJson` | Load policies from JSON files |

**Policy Execution Context** (available fields):

The Rust backend evaluates policy trees with a rich context containing:
- Transaction fields (`amount`, `ticks_to_deadline`, `priority`)
- Agent state (`balance`, `effective_liquidity`, `credit_limit`)
- Queue state (`outgoing_queue_size`, `queue1_total_value`)
- Time (`current_tick`, `ticks_remaining_in_day`)

### 8.3 Policy Validation

```python
# From validate_policy_with_details()
result = subprocess.run([
    "payment-sim",
    "validate-policy",
    temp_path,
    "--format", "json"
], capture_output=True, text=True)
```

The validator checks:
- JSON structure is valid
- All referenced fields exist in registry
- All referenced parameters are defined
- Action names are valid
- Tree structure is correct

---

## 9. Design Decisions and Rationale

### 9.1 Why Depth-Limited Trees Instead of Recursive?

**Problem**: OpenAI's structured output doesn't support recursive JSON schemas (`$ref` cycles).

**Solution**: Explicit types for each depth level (`TreeNodeL0` through `TreeNodeL5`).

**Trade-off**: Max depth is limited to 5 levels, but this is sufficient for practical policies.

### 9.2 Why Dynamic Schema Generation?

**Problem**: Different experiments need different allowed parameters/fields/actions.

**Solution**: `create_constrained_policy_model(constraints)` generates Pydantic models at runtime.

**Benefit**: LLM can only generate policies with valid elements—prevents 94% of validation errors.

### 9.3 Why Subprocess Instead of Direct Import?

**Problem**: Rust FFI boundary is complex, and simulation needs to be isolated.

**Solution**: Call `payment-sim` CLI and parse JSON output.

**Benefits**:
- Clean separation of concerns
- Easy parallelization (separate processes)
- Deterministic: same seed always produces same output
- No FFI complexity in research code

### 9.4 Why DuckDB for Persistence?

**Requirements**:
- Full reproducibility (store all LLM interactions)
- Ad-hoc queries for analysis
- Single-file portability

**DuckDB benefits**:
- Embedded (no server)
- SQL interface for analysis
- JSON column support
- Fast analytical queries

---

## 10. File Inventory

### 10.1 Configuration Files

| Path | Purpose |
|------|---------|
| `configs/castro_2period_aligned.yaml` | Exp 1: 2-period deterministic |
| `configs/castro_12period_aligned.yaml` | Exp 2: 12-period stochastic |
| `configs/castro_joint_aligned.yaml` | Exp 3: Joint learning |
| `policies/seed_policy.json` | Starting policy for all experiments |

### 10.2 Core Modules

| Path | Purpose | Key Classes |
|------|---------|-------------|
| `generator/robust_policy_agent.py` | LLM policy generation | `RobustPolicyAgent` |
| `schemas/parameter_config.py` | Constraint definitions | `ParameterSpec`, `ScenarioConstraints` |
| `schemas/dynamic.py` | Dynamic model generation | `create_constrained_policy_model()` |
| `schemas/tree.py` | Depth-limited trees | `TreeNodeL0`-`TreeNodeL5` |
| `schemas/registry.py` | Field/action registry | `PAYMENT_TREE_FIELDS`, `PAYMENT_ACTIONS` |
| `parameter_sets.py` | Pre-defined constraints | `MINIMAL_CONSTRAINTS`, etc. |

### 10.3 Entry Points

| Path | Purpose | Usage |
|------|---------|-------|
| `scripts/reproducible_experiment.py` | Main experiment runner | `python reproducible_experiment.py --experiment exp1` |
| `scripts/robust_experiment.py` | Constrained schema runner | `python robust_experiment.py --experiment exp2` |

### 10.4 Documentation

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | Research environment style guide |
| `HANDOVER.md` | Current status and protocols |
| `LAB_NOTES.md` | Detailed experiment log |
| `RESEARCH_PAPER.md` | Draft paper with results |
| `papers/castro_et_al.md` | Original Castro paper |

---

## 11. Running the Experiments

### 11.1 Setup

```bash
cd experiments/castro
uv sync --extra dev
export OPENAI_API_KEY="your-key-here"
```

### 11.2 Run Experiments

```bash
# Experiment 1: 2-period deterministic
python scripts/reproducible_experiment.py --experiment exp1 --output results/exp1.db

# Experiment 2: 12-period stochastic
python scripts/reproducible_experiment.py --experiment exp2 --output results/exp2.db

# Experiment 3: Joint learning
python scripts/reproducible_experiment.py --experiment exp3 --output results/exp3.db
```

### 11.3 After Rust Changes

```bash
uv sync --extra dev --reinstall-package payment-simulator
```

---

## 12. Key Findings from LAB_NOTES

### 12.1 Experiment 1 Results

- **Cost progression**: $1,080 → $81 (92.5% reduction)
- **Iterations**: 12
- **Equilibrium discovered**: Symmetric (both banks → 0.025% collateral)
- **Key insight**: LLM discovered alternative equilibrium, not Castro's asymmetric one

### 12.2 Experiment 2 Challenges

- **Cost increased** 8.5% despite optimization
- **High variance**: σ = $95,661 across seeds
- **Failure modes**:
  - Variance-mean tradeoff
  - EOD penalty cliff (binary settle/fail)
  - Limited DSL expressiveness

### 12.3 Experiment 3 Success

- **Cost progression**: $499.50 → $0.24 (99.95% reduction)
- **Discovered optimal strategy**: Near-zero liquidity + payment recycling
- **Novel mechanisms invented**:
  - Time-varying liquidity buffer
  - Partial release capability
  - Late window detection

---

## 13. Schema Files Reference

### 13.1 Complete Schema Module List (`schemas/`)

| File | Purpose |
|------|---------|
| `__init__.py` | Module exports |
| `actions.py` | Action node definitions (`Release`, `Hold`, `Split`, etc.) |
| `dynamic.py` | Runtime Pydantic model generation from constraints |
| `expressions.py` | Comparison and logical expressions (`op`, `left`, `right`) |
| `generator.py` | `PolicySchemaGenerator` class |
| `parameter_config.py` | `ParameterSpec` and `ScenarioConstraints` |
| `registry.py` | Field and action registries by tree type |
| `toggles.py` | Feature toggles for schema generation |
| `tree.py` | Depth-limited tree models (L0-L5) |
| `values.py` | `PolicyValue` types (literal, field ref, param ref, compute) |

### 13.2 Value Types (`values.py`)

```python
# Literal value
{"value": 5}

# Field reference
{"field": "balance"}

# Parameter reference (must be defined in parameters)
{"param": "urgency_threshold"}

# Computed value (arithmetic)
{"compute": {"op": "*", "left": {"field": "X"}, "right": {"value": 2}}}
```

### 13.3 Expression Types (`expressions.py`)

```python
# Comparison
{"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "threshold"}}

# Logical AND
{"op": "and", "conditions": [expr1, expr2, ...]}

# Logical OR
{"op": "or", "conditions": [expr1, expr2, ...]}
```

---

## 14. Troubleshooting

### 14.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Expected 2 JSON blocks, found 0" | LLM returned empty/malformed JSON | Check LLM model availability; use GPT-4o |
| TLS certificate errors | OpenAI API connectivity | Retry with exponential backoff |
| Policy validation failures | Invalid field/parameter reference | Use `STANDARD_CONSTRAINTS` or check registry |
| High variance in costs | Stochastic scenario | Run more seeds; consider variance-aware objective |

### 14.2 Debugging Policy Generation

1. **Check system prompt**: `agent.get_system_prompt()`
2. **Check constraints**: Verify allowed fields/actions in `ScenarioConstraints`
3. **Run validation manually**: `payment-sim validate-policy <path> --format json`
4. **Check LAB_NOTES.md**: Previous experiments may have encountered same issue

---

*This documentation provides a comprehensive reference for understanding, maintaining, and extending the Castro experiment codebase.*
