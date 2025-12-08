# Castro Experiments - Architecture Report

**Version:** 1.1
**Date:** 2025-12-04
**Status:** Comprehensive technical documentation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Purpose and Research Goals](#purpose-and-research-goals)
3. [Dependencies on SimCash](#dependencies-on-simcash)
4. [Directory Structure](#directory-structure)
5. [Architecture Overview](#architecture-overview)
6. [Core Components](#core-components)
7. [Data Structures](#data-structures)
8. [Data Flow](#data-flow)
9. [Design Patterns](#design-patterns)
10. [Key Invariants](#key-invariants)
11. [Database Schema](#database-schema)
12. [Testing Strategy](#testing-strategy)
13. [Historical Context](#historical-context)
14. [Usage Guide](#usage-guide)

---

## Executive Summary

The Castro experiments directory (`experiments/castro/`) is a **research environment** for replicating and extending Castro et al. (2025) "Strategic Payment Timing" using LLM-based policy optimization. It provides a standalone Python package that interfaces with the SimCash payment simulator to conduct reproducible machine learning experiments on payment system optimization.

**Key Innovation:** Uses LLM structured output (via PydanticAI) to generate valid payment policies constrained by dynamically-generated Pydantic schemas, ensuring all generated policies pass SimCash validation automatically.

**Technical Highlights:**
- **Dynamic schema generation** from scenario constraints
- **Depth-limited tree models** that work with OpenAI structured output (no recursion)
- **Full reproducibility** via DuckDB persistence of all experiment artifacts
- **Castro-aligned configurations** with deferred crediting and EOD deadline caps
- **Multi-LLM support** via PydanticAI (GPT-4o, GPT-5.1, o1/o3, Claude, Gemini)

---

## Purpose and Research Goals

### Research Context

The experiments replicate and extend findings from Castro et al. (2025), which provides a game-theoretic analysis of strategic payment timing in Real-Time Gross Settlement (RTGS) systems. The paper identifies Nash equilibria in liquidity allocation and payment release timing.

### Research Questions

1. **Exp1 (2-Period Deterministic):** Can LLM-based optimization discover the asymmetric Nash equilibrium predicted by Castro's theory?
   - Expected: Bank A: l₀=0, Bank B: l₀=20000

2. **Exp2 (12-Period Stochastic):** Can the approach scale to realistic LVTS-style scenarios with stochastic payment arrivals?

3. **Exp3 (Joint Liquidity and Timing):** Can LLMs learn to jointly optimize collateral posting and payment release timing?

### Key Alignment Features

To match Castro's theoretical model, experiments require:

```yaml
deferred_crediting: true      # Credits applied at end of tick
deadline_cap_at_eod: true     # All deadlines capped at day end
```

Without these, within-tick recycling changes the equilibrium structure.

---

## Dependencies on SimCash

### Direct Dependencies

The Castro experiments depend on the SimCash payment simulator:

```
experiments/castro/
    └── depends on ──→ api/payment_simulator/
                           └── depends on ──→ simulator/ (Rust)
```

**Specific dependencies:**

| Component | SimCash Module | Usage |
|-----------|----------------|-------|
| Policy validation | `payment-sim validate-policy` | Validate LLM-generated policies |
| Simulation execution | `payment-sim run` | Run experiments with policies |
| Configuration schemas | `api/payment_simulator/config/` | YAML config structure |
| Policy DSL | Rust `simulator/src/models/policy.rs` | Policy structure/evaluation |

### Installation

```bash
cd experiments/castro
uv sync --extra dev  # Builds Rust backend automatically
```

### Key Invariants (Inherited from SimCash)

1. **Money is i64 cents** - Never use floats for monetary values
2. **Deterministic execution** - Same seed + config = identical results
3. **Valid policy structure** - Must pass SimCash validator before use

---

## Directory Structure

```
experiments/castro/
├── CLAUDE.md                    # Research environment guidelines
├── ARCHITECTURE.md              # This document
├── LAB_NOTES.md                 # Experiment log
├── pyproject.toml               # UV/pip configuration
├── uv.lock                      # Locked dependencies
├── cli.py                       # NEW: Typer CLI entry point
│
├── castro/                      # NEW: Modular library package
│   ├── __init__.py              # Package exports
│   ├── core/                    # Core types and protocols
│   │   ├── __init__.py
│   │   ├── types.py             # TypedDicts, dataclasses
│   │   └── protocols.py         # Repository, SimulationExecutor protocols
│   ├── db/                      # Database layer
│   │   ├── __init__.py
│   │   ├── schema.py            # SQL schema definitions
│   │   └── repository.py        # ExperimentRepository implementation
│   ├── simulation/              # Simulation execution
│   │   ├── __init__.py
│   │   ├── executor.py          # ParallelSimulationExecutor
│   │   └── metrics.py           # compute_metrics()
│   ├── visualization/           # Chart generation
│   │   ├── __init__.py
│   │   └── charts.py            # All chart generators
│   └── experiment/              # Experiment execution
│       ├── __init__.py
│       ├── definitions.py       # EXPERIMENTS registry
│       ├── optimizer.py         # LLMOptimizer class
│       └── runner.py            # ReproducibleExperiment
│
├── configs/                     # Experiment configurations
│   ├── castro_2period_aligned.yaml    # Exp1: 2-period deterministic
│   ├── castro_12period_aligned.yaml   # Exp2: 12-period stochastic
│   └── castro_joint_aligned.yaml      # Exp3: Joint learning
│
├── policies/                    # Policy definitions
│   └── seed_policy.json         # Starting policy (READ-ONLY)
│
├── scripts/                     # Legacy experiment runners (being migrated)
│   ├── README.md                # Script documentation
│   ├── reproducible_experiment.py     # Main runner (legacy)
│   └── analyze_validation_errors.py   # Analysis tool
│
├── generator/                   # LLM policy generation
│   ├── __init__.py
│   ├── robust_policy_agent.py   # Main agent (PydanticAI)
│   ├── client.py                # LLM client wrapper
│   ├── providers.py             # Provider abstraction
│   ├── pydantic_ai_provider.py  # PydanticAI implementation
│   └── validation.py            # Policy validation helpers
│
├── schemas/                     # Pydantic schema definitions
│   ├── __init__.py
│   ├── actions.py               # Action types (Release, Hold, etc.)
│   ├── expressions.py           # Condition expressions
│   ├── values.py                # Value types (field, literal, param)
│   ├── tree.py                  # Depth-limited tree nodes (L0-L5)
│   ├── registry.py              # Field/action registries
│   ├── parameter_config.py      # ParameterSpec, ScenarioConstraints
│   ├── dynamic.py               # Dynamic model generation
│   ├── generator.py             # Schema generator
│   └── toggles.py               # Feature toggles
│
├── prompts/                     # LLM prompt templates
│   ├── __init__.py
│   ├── templates.py             # System prompts
│   └── builder.py               # Prompt construction
│
├── parameter_sets.py            # Pre-defined constraint sets
│
├── results/                     # Output databases and experiment work directories
│   ├── exp1_2025-12-04-143022/  # Experiment work directory (unique per run)
│   │   ├── scenario.yaml        # Copy of simulation scenario config
│   │   ├── parameters.json      # Experiment parameters (model, seeds, etc.)
│   │   ├── seed_policy_a.json   # Initial Bank A policy
│   │   ├── seed_policy_b.json   # Initial Bank B policy
│   │   ├── configs/             # Iteration-specific configs
│   │   │   └── iter_001_config.yaml
│   │   └── policies/            # Iteration-specific policies
│   │       ├── iter_001_policy_a.json
│   │       └── iter_001_policy_b.json
│   └── exp1_2025-12-04-143022.db  # DuckDB database
│
├── tests/                       # Test suite (27 files)
│   ├── conftest.py              # Pytest fixtures
│   ├── unit/                    # Unit tests (14 files)
│   └── integration/             # Integration tests (2 files)
│
├── papers/                      # Reference papers
│   └── castro_et_al.md          # Original paper summary
│
└── archive/                     # Deprecated code
    ├── README.md
    ├── deprecated-scripts-2025-12-03/
    ├── docs-2025-12-03/
    └── pre-castro-alignment/
```

---

## Architecture Overview

### High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Experiment Configuration                          │
│  (exp1, exp2, exp3) → YAML config + seed policies + constraints     │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    ReproducibleExperiment                            │
│  - Manages experiment lifecycle                                      │
│  - Persists ALL data to DuckDB                                      │
│  - Never modifies seed files                                         │
└─────────────────────────────────┬────────────────────────────────────┘
                                  │
           ┌──────────────────────┴──────────────────────┐
           │                                             │
           ▼                                             ▼
┌─────────────────────────┐               ┌─────────────────────────────┐
│   SimCash Simulation    │               │    LLM Policy Optimizer     │
│   (payment-sim CLI)     │               │   (RobustPolicyAgent)       │
│   - Run simulations     │               │   - PydanticAI structured   │
│   - Return metrics      │               │   - Dynamic schemas         │
│   - 8 parallel workers  │               │   - Multi-LLM support       │
└────────────┬────────────┘               └──────────────┬──────────────┘
             │                                           │
             └───────────────────┬───────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         DuckDB Database                              │
│  - experiment_config     - policy_iterations    - llm_interactions  │
│  - simulation_runs       - iteration_metrics    - validation_errors │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Interaction

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│  ScenarioConstraints ─────────────────────────────────────────────────────┐ │
│  (defines allowed params, fields, actions)                                │ │
│                                                                           │ │
│                    ▼                                                      │ │
│                                                                           │ │
│  create_constrained_policy_model() ───────────────────────────────────────┼─┼─┐
│  (generates Pydantic model at runtime)                                    │ │ │
│                                                                           │ │ │
│                    ▼                                                      │ │ │
│                                                                           │ │ │
│  RobustPolicyAgent ◄──────────────────────────────────────────────────────┘ │ │
│  - Holds dynamic policy model                                               │ │
│  - Generates system prompt from constraints                                 │ │
│  - Creates PydanticAI Agent                                                 │ │
│                                                                             │ │
│                    ▼                                                        │ │
│                                                                             │ │
│  PydanticAI Agent ◄─────────────────────────────────────────────────────────┘ │
│  - Structured output using dynamic model                                      │
│  - Automatic validation and retries                                           │
│  - Model detection (GPT-4o, o1/o3, etc.)                                      │
│                                                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. ReproducibleExperiment (scripts/reproducible_experiment.py)

The main experiment runner with full reproducibility guarantees.

**Key Responsibilities:**
- Manage experiment lifecycle (setup → iterations → completion)
- Generate unique experiment ID with timestamp (`exp1_2025-12-04-143022`)
- Create isolated work directory for each experiment run
- Save experiment metadata (scenario, parameters, seed policies) for reproducibility
- Never modify seed policy files (read-only)
- Create iteration-specific policy/config files
- Run simulations in parallel (8 workers)
- Store ALL artifacts in DuckDB

**Key Methods:**

```python
class ReproducibleExperiment:
    def __init__(self, experiment_key: str, db_path: str, ...):
        """Initialize with unique timestamp ID and isolated work directory."""
        # Generates: exp1_2025-12-04-143022
        # Creates: results/exp1_2025-12-04-143022/{configs,policies}/

    def _save_experiment_metadata(self, ...):
        """Save scenario.yaml, parameters.json, seed policies to work dir."""

    def setup(self) -> None:
        """Initialize experiment in database, record seed policies."""

    def create_iteration_config(self, iteration: int) -> Path:
        """Create iteration-specific files without modifying seeds."""

    def run_iteration(self, iteration: int) -> dict:
        """Run simulations for one iteration."""

    def optimize_policies(self, iteration: int, metrics: dict) -> bool:
        """Call LLM to generate improved policies."""

    def validate_and_fix_policy(self, policy: dict, ...) -> tuple[dict, bool]:
        """Validate with retries, log all errors to DB."""

    def run(self) -> dict:
        """Execute full experiment."""
```

**Experiment and Iteration Isolation:**

Each experiment run gets a unique work directory based on timestamp:

```
results/
├── exp1_2025-12-04-143022/           # Experiment 1, run at 14:30:22
│   ├── scenario.yaml                  # Scenario config (for reproducibility)
│   ├── parameters.json                # Experiment parameters
│   ├── seed_policy_a.json             # Initial Bank A policy
│   ├── seed_policy_b.json             # Initial Bank B policy
│   ├── configs/
│   │   ├── iter_001_config.yaml       # Iteration 1 config
│   │   └── iter_002_config.yaml       # Iteration 2 config
│   └── policies/
│       ├── iter_001_policy_a.json     # Iteration 1 policies
│       ├── iter_001_policy_b.json
│       ├── iter_002_policy_a.json     # Iteration 2 policies
│       └── iter_002_policy_b.json
├── exp1_2025-12-04-143022.db          # DuckDB database
└── exp2_2025-12-04-143025/            # Different experiment, different directory
    └── ...

(Original policies/seed_policy.json NEVER modified)
```

This ensures parallel experiment runs never interfere with each other.

### 2. RobustPolicyAgent (generator/robust_policy_agent.py)

LLM-based policy generator using PydanticAI structured output.

**Key Responsibilities:**
- Generate policies that pass SimCash validation
- Support arbitrary parameters, fields, actions per scenario
- Handle multiple LLM providers (OpenAI, Anthropic, etc.)
- Provide rich system prompts with examples

**Constructor:**

```python
def __init__(
    self,
    constraints: ScenarioConstraints,  # What's allowed
    model: str = "gpt-4o",             # LLM model
    retries: int = 3,                   # Validation retries
    reasoning_effort: Literal["low", "medium", "high"] = "high",
) -> None
```

**Key Methods:**

```python
def generate_policy(
    self,
    instruction: str,                    # Natural language goal
    current_policy: dict | None = None,  # Policy to improve
    current_cost: float | None = None,   # Current cost
    settlement_rate: float | None = None,
    iteration: int = 0,
) -> dict[str, Any]:
    """Generate a validated policy."""
```

**System Prompt Generation:**

The agent generates a rich system prompt including:
1. Critical rules (defined params, compute wrapper, node_ids)
2. Allowed vocabulary (parameters, fields, actions)
3. Value type reference
4. Two complete examples (simple and complex)
5. Common errors to avoid
6. Node structure reference
7. Optimization goals

### 3. ScenarioConstraints (schemas/parameter_config.py)

Defines what elements are allowed in a scenario.

```python
@dataclass
class ParameterSpec:
    name: str          # e.g., "urgency_threshold"
    min_value: float   # e.g., 0
    max_value: float   # e.g., 20
    default: float     # e.g., 3.0
    description: str   # For LLM prompt

class ScenarioConstraints:
    allowed_parameters: list[ParameterSpec]  # e.g., [urgency, buffer]
    allowed_fields: list[str]                # e.g., ["balance", "ticks_to_deadline"]
    allowed_actions: list[str]               # e.g., ["Release", "Hold"]
```

**Pre-defined Sets (parameter_sets.py):**

| Set | Parameters | Fields | Actions |
|-----|------------|--------|---------|
| MINIMAL | 1 (urgency) | 5 | 2 (Release, Hold) |
| STANDARD | 4 | 19 | 3 (+ Split) |
| FULL | 10 | 146+ | 10 (all) |

### 4. Dynamic Schema Generation (schemas/dynamic.py)

Generates Pydantic models at runtime from constraints.

```python
def create_constrained_policy_model(constraints: ScenarioConstraints) -> type[BaseModel]:
    """Generate complete policy model from constraints.

    Creates:
    - DynamicContextField with allowed fields as Literal
    - DynamicParamRef with allowed params as Literal
    - DynamicActionNode with allowed actions as Literal
    - Full DynamicPolicy model with parameter bounds
    """
```

**Why Dynamic?**

The original design hardcoded 3 parameters. SimCash supports ANY user-defined parameters. Dynamic generation allows:
- Per-scenario parameter sets
- Enforced bounds (min/max validation)
- Automatic vocabulary restriction
- Consistent parameter-reference validation

### 5. Depth-Limited Tree Models (schemas/tree.py)

**The Problem:** OpenAI structured output doesn't support recursive schemas (`$ref`).

**The Solution:** Explicit types for each depth level:

```python
TreeNodeL0 = ActionNode                              # Leaf only
TreeNodeL1 = Union[ActionNode, ConditionNodeL1]      # L1 has L0 children
TreeNodeL2 = Union[ActionNode, ConditionNodeL2]      # L2 has L1 children
TreeNodeL3 = Union[ActionNode, ConditionNodeL3]
TreeNodeL4 = Union[ActionNode, ConditionNodeL4]
TreeNodeL5 = Union[ActionNode, ConditionNodeL5]      # Max depth
```

Each `ConditionNodeLN` references `TreeNodeL(N-1)` for children, breaking recursion.

**Depth Support:** Up to 5 levels of nesting (sufficient for most policies).

### 6. ExperimentDatabase (scripts/reproducible_experiment.py)

DuckDB wrapper for experiment tracking.

**Key Methods:**

```python
def record_experiment_config(...)     # Full configuration
def record_policy_iteration(...)      # Every policy version
def record_llm_interaction(...)       # All prompts/responses
def record_simulation_run(...)        # Per-seed results
def record_iteration_metrics(...)     # Aggregated stats
def record_validation_error(...)      # All validation failures
def export_summary(...)               # For reproducibility
```

---

## Data Structures

### Policy JSON Structure

```json
{
  "version": "2.0",
  "policy_id": "optimized_policy_v3",
  "description": "LLM-optimized policy for low delay costs",
  "parameters": {
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.2
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_urgent",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
    "on_false": {
      "type": "condition",
      "node_id": "N2_liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"param": "liquidity_buffer"},
            "right": {"field": "remaining_amount"}
          }
        }
      },
      "on_true": {"type": "action", "node_id": "A2", "action": "Release"},
      "on_false": {"type": "action", "node_id": "A3", "action": "Hold"}
    }
  },
  "strategic_collateral_tree": {...}
}
```

### Value Types

| Type | Structure | Example |
|------|-----------|---------|
| Literal | `{"value": X}` | `{"value": 5.0}` |
| Field Reference | `{"field": "name"}` | `{"field": "balance"}` |
| Parameter Reference | `{"param": "name"}` | `{"param": "urgency_threshold"}` |
| Computation | `{"compute": {...}}` | `{"compute": {"op": "*", "left": {...}, "right": {...}}}` |

### Expression Types

| Type | Structure |
|------|-----------|
| Comparison | `{"op": "<=", "left": <value>, "right": <value>}` |
| Logical AND | `{"op": "and", "conditions": [<expr>, ...]}` |
| Logical OR | `{"op": "or", "conditions": [<expr>, ...]}` |
| Logical NOT | `{"op": "not", "condition": <expr>}` |

### Node Types

| Type | Fields |
|------|--------|
| Action | `type`, `node_id`, `action`, `parameters`, `description` |
| Condition | `type`, `node_id`, `condition`, `on_true`, `on_false`, `description` |

### Tree Types

| Tree | Purpose | Available Fields | Available Actions |
|------|---------|------------------|-------------------|
| `payment_tree` | Per-transaction decisions | 146+ (incl. transaction-specific) | Release, Hold, Split, etc. |
| `bank_tree` | Agent-level decisions | 90+ (no transaction fields) | SetReleaseBudget, SetState, etc. |
| `strategic_collateral_tree` | Start-of-tick collateral | 90+ | PostCollateral, WithdrawCollateral, HoldCollateral |
| `end_of_tick_collateral_tree` | End-of-tick collateral | 90+ | Same as above |

---

## Data Flow

### Experiment Execution Flow

```
┌───────────────────────────────────────────────────────────────────────────┐
│  1. SETUP                                                                 │
│  ─────────────────────────────────────────────────────────────────────── │
│  - Load experiment definition (exp1, exp2, exp3)                         │
│  - Generate unique experiment ID: exp1_2025-12-04-143022                 │
│  - Create isolated work directory: results/exp1_2025-12-04-143022/       │
│  - Load config YAML                                                       │
│  - Load seed policies (READ-ONLY, never modified)                        │
│  - Save experiment metadata to work directory:                           │
│      • scenario.yaml (simulation config)                                  │
│      • parameters.json (model, seeds, iterations, etc.)                  │
│      • seed_policy_a.json, seed_policy_b.json                            │
│  - Initialize DuckDB database                                            │
│  - Record experiment_config to DB                                        │
│  - Record initial policies (iteration 0) to DB                           │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  2. ITERATION LOOP (1 to max_iterations)                                  │
│  ─────────────────────────────────────────────────────────────────────── │
│                                                                           │
│  2a. Create Iteration Files:                                              │
│      policies/iter_XXX_policy_{a,b}.json  (current policies)             │
│      configs/iter_XXX_config.yaml         (points to policy files)       │
│                                                                           │
│  2b. Run Simulations:                                                     │
│      - Execute `payment-sim run` for each seed                           │
│      - Parallel execution (8 workers)                                    │
│      - Record each run to simulation_runs                                │
│                                                                           │
│  2c. Compute Metrics:                                                     │
│      - mean cost, std, risk-adjusted cost                                │
│      - settlement rate, failure rate                                     │
│      - best/worst seeds                                                   │
│      - Record to iteration_metrics                                       │
│                                                                           │
│  2d. Check Convergence:                                                   │
│      - If converged (cost stable over window), exit loop                 │
│                                                                           │
│  2e. Optimize Policies (if not converged):                               │
│      - Build instruction prompt from metrics                             │
│      - Call RobustPolicyAgent.generate_policy() for each bank            │
│      - Validate with SimCash                                             │
│      - If invalid: attempt LLM fix (up to 3 retries)                     │
│      - Log all validation errors to validation_errors                    │
│      - Record LLM interactions to llm_interactions                       │
│      - Record new policies to policy_iterations                          │
│      - Update in-memory policy state                                      │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  3. COMPLETION                                                            │
│  ─────────────────────────────────────────────────────────────────────── │
│  - Export summary for reproducibility                                    │
│  - Print final metrics                                                   │
│  - Close database connection                                              │
└───────────────────────────────────────────────────────────────────────────┘
```

### Policy Generation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Create Instruction Prompt                                        │
│     - Current iteration metrics                                      │
│     - Current policy parameters                                      │
│     - Optimization goals                                             │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. RobustPolicyAgent.generate_policy()                             │
│     - Builds context-aware prompt                                    │
│     - Gets PydanticAI Agent (lazy init)                             │
│     - Calls agent.run_sync(prompt, deps)                            │
│     - Returns validated Pydantic model                               │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. PydanticAI Agent                                                 │
│     - Uses dynamic DynamicPolicy model                               │
│     - System prompt with examples and constraints                    │
│     - Structured output enforced by Pydantic                        │
│     - Automatic retries on validation failure                        │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. SimCash Validation                                               │
│     - Write policy to temp file                                      │
│     - Run `payment-sim validate-policy`                              │
│     - Parse JSON output for errors                                   │
│     - If invalid: request LLM fix (up to 3 attempts)                │
└─────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. Return Validated Policy or Fallback                              │
│     - If valid: return new policy                                    │
│     - If unfixable: return previous valid policy                     │
│     - Log all errors to database                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Design Patterns

### 1. Dynamic Schema Generation Pattern

**Problem:** Need to support ANY SimCash-valid parameters without hardcoding.

**Solution:**

```python
# 1. Define constraints for your scenario
constraints = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec("urgency", 0, 20, 3.0, "Urgency threshold"),
        ParameterSpec("buffer", 0.5, 3.0, 1.0, "Liquidity buffer"),
    ],
    allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity"],
    allowed_actions=["Release", "Hold", "Split"],
)

# 2. Generate Pydantic model at runtime
PolicyModel = create_constrained_policy_model(constraints)

# 3. Use with LLM agent
agent = RobustPolicyAgent(constraints)
policy = agent.generate_policy("Minimize delay costs")
```

**Benefits:**
- Scenario-specific validation
- Automatic parameter bounds enforcement
- Vocabulary restriction prevents invalid references

### 2. Depth-Limited Tree Pattern

**Problem:** OpenAI structured output doesn't support recursive schemas.

**Solution:**

```python
# Instead of recursive:
# class TreeNode:
#     children: list[TreeNode]  # NOT SUPPORTED!

# Use explicit depth levels:
TreeNodeL0 = ActionNode
TreeNodeL1 = Union[ActionNode, ConditionNodeL1]  # L1 children are L0
TreeNodeL2 = Union[ActionNode, ConditionNodeL2]  # L2 children are L1
# ... up to L5
```

**Benefits:**
- Works with OpenAI structured output
- Supports up to 5 levels of nesting
- Clear depth limits for LLM guidance

### 3. Experiment Isolation Pattern

**Problem:** Need to track policy evolution without corrupting seed files, AND support parallel experiment runs without race conditions.

**Solution:**

```python
# Generate unique experiment ID with timestamp
timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
self.experiment_id = f"{experiment_key}_{timestamp}"  # e.g., exp1_2025-12-04-143022

# Create isolated work directory for this experiment run
self.experiment_work_dir = self.output_dir / self.experiment_id
self.policies_dir = self.experiment_work_dir / "policies"
self.configs_dir = self.experiment_work_dir / "configs"

# Save experiment metadata for reproducibility
def _save_experiment_metadata(self, ...):
    shutil.copy(self.config_path, self.experiment_work_dir / "scenario.yaml")
    with open(self.experiment_work_dir / "parameters.json", "w") as f:
        json.dump(parameters, f, indent=2)
    shutil.copy(seed_policy_a_src, self.experiment_work_dir / "seed_policy_a.json")
    shutil.copy(seed_policy_b_src, self.experiment_work_dir / "seed_policy_b.json")

# Each iteration creates NEW files within the isolated directory
def create_iteration_config(self, iteration: int) -> Path:
    policy_a_path = self.policies_dir / f"iter_{iteration:03d}_policy_a.json"
    save_json_policy(str(policy_a_path), self.policy_a)
    # ...
```

**Benefits:**
- Seed files are never modified
- Every iteration is independently reproducible
- Full history in database
- **Parallel experiments never interfere** (unique work directories)
- **Complete reproducibility** (all inputs saved in work directory)

### 4. Full Reproducibility Pattern

**Problem:** Research requires complete reproducibility.

**Solution:** Store EVERYTHING in database:

```sql
-- Every experiment configuration
experiment_config (config_yaml, config_hash, ...)

-- Every policy version
policy_iterations (policy_json, policy_hash, created_by, ...)

-- Every LLM call
llm_interactions (prompt_text, prompt_hash, response_text, response_hash, ...)

-- Every simulation result
simulation_runs (seed, total_cost, raw_output, ...)

-- All validation errors
validation_errors (policy_json, error_messages, error_category, was_fixed, ...)
```

**Benefits:**
- Exact reproduction from database alone
- Audit trail for all decisions
- Learning from error patterns

### 5. Validation Error Learning Pattern

**Problem:** LLMs make mistakes; need to understand patterns.

**Solution:**

```python
def record_validation_error(self, ..., errors: list[str], ...):
    # Categorize error for analysis
    error_category = self._categorize_error(errors)
    # Categories: MISSING_FIELD, MISSING_NODE_ID, CUSTOM_PARAM, etc.

    # Store with context
    self.conn.execute("INSERT INTO validation_errors ...", [
        policy_json,      # What was invalid
        error_messages,   # What failed
        error_category,   # Categorized
        was_fixed,        # Resolution status
        fix_attempt_count # Effort required
    ])
```

**Benefits:**
- Track error patterns across experiments
- Identify common LLM failure modes
- Improve prompts based on data

---

## Key Invariants

### 1. Seed Files Are Read-Only

```python
# ✅ CORRECT
self.seed_policy = load_json_policy(seed_path)  # Load once
# ... later ...
self.policy_a = self.seed_policy.copy()  # Work with copy

# ❌ NEVER
save_json_policy(seed_path, modified_policy)  # Never modify!
```

### 2. Money Values Are i64 Cents

```python
# ✅ CORRECT
total_cost: int = 250_000_50  # $2,500.50 in cents

# ❌ NEVER
total_cost: float = 2500.50  # NO FLOATS FOR MONEY
```

### 3. All LLM Interactions Are Logged

```python
# ✅ CORRECT
response = agent.generate_policy(prompt)
db.record_llm_interaction(
    prompt_text=prompt,
    response_text=json.dumps(response),
    ...
)

# ❌ NEVER
response = agent.generate_policy(prompt)  # Unreproducible!
use(response)
```

### 4. Every Parameter Reference Must Be Defined

```json
// ✅ CORRECT
{
  "parameters": {"threshold": 5.0},
  "payment_tree": {
    "condition": {"right": {"param": "threshold"}}
  }
}

// ❌ INVALID (threshold not defined)
{
  "parameters": {},
  "payment_tree": {
    "condition": {"right": {"param": "threshold"}}
  }
}
```

### 5. Every Node Has a Unique node_id

```json
// ✅ CORRECT
{"type": "action", "node_id": "A1_release", "action": "Release"}

// ❌ INVALID (missing node_id)
{"type": "action", "action": "Release"}
```

### 6. Arithmetic Uses compute Wrapper

```json
// ✅ CORRECT
{"compute": {"op": "*", "left": {"value": 2}, "right": {"field": "amount"}}}

// ❌ INVALID (raw arithmetic)
{"op": "*", "left": {"value": 2}, "right": {"field": "amount"}}
```

---

## Database Schema

### Tables

```sql
-- Experiment configuration (1 row per experiment)
experiment_config (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR,
    created_at TIMESTAMP,
    config_yaml TEXT,
    config_hash VARCHAR(64),
    cost_rates JSON,
    agent_configs JSON,
    model_name VARCHAR,
    reasoning_effort VARCHAR,
    num_seeds INTEGER,
    max_iterations INTEGER,
    convergence_threshold DOUBLE,
    convergence_window INTEGER,
    notes TEXT
);

-- Policy iterations (every version of every policy)
policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    iteration_number INTEGER,
    agent_id VARCHAR,          -- 'BANK_A' or 'BANK_B'
    policy_json TEXT,
    policy_hash VARCHAR(64),
    parameters JSON,
    created_at TIMESTAMP,
    created_by VARCHAR         -- 'init', 'llm', 'manual'
);

-- LLM interactions (all prompts and responses)
llm_interactions (
    interaction_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    iteration_number INTEGER,
    prompt_text TEXT,
    prompt_hash VARCHAR(64),
    response_text TEXT,
    response_hash VARCHAR(64),
    model_name VARCHAR,
    reasoning_effort VARCHAR,
    tokens_used INTEGER,
    latency_seconds DOUBLE,
    created_at TIMESTAMP,
    error_message TEXT
);

-- Individual simulation runs (per-seed results)
simulation_runs (
    run_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    iteration_number INTEGER,
    seed INTEGER,
    total_cost BIGINT,          -- cents
    bank_a_cost BIGINT,
    bank_b_cost BIGINT,
    settlement_rate DOUBLE,
    collateral_cost BIGINT,
    delay_cost BIGINT,
    overdraft_cost BIGINT,
    eod_penalty BIGINT,
    bank_a_final_balance BIGINT,
    bank_b_final_balance BIGINT,
    total_arrivals INTEGER,
    total_settlements INTEGER,
    raw_output JSON,
    verbose_log TEXT,
    created_at TIMESTAMP
);

-- Aggregated iteration metrics
iteration_metrics (
    metric_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    iteration_number INTEGER,
    total_cost_mean DOUBLE,
    total_cost_std DOUBLE,
    risk_adjusted_cost DOUBLE,
    settlement_rate_mean DOUBLE,
    failure_rate DOUBLE,
    best_seed INTEGER,
    worst_seed INTEGER,
    best_seed_cost BIGINT,
    worst_seed_cost BIGINT,
    converged BOOLEAN,
    created_at TIMESTAMP
);

-- Policy validation errors (for learning)
validation_errors (
    error_id VARCHAR PRIMARY KEY,
    experiment_id VARCHAR,
    iteration_number INTEGER,
    agent_id VARCHAR,
    attempt_number INTEGER,     -- 0 = initial, 1-3 = fix attempts
    policy_json TEXT,
    error_messages JSON,
    error_category VARCHAR,     -- MISSING_FIELD, PARSE_ERROR, etc.
    was_fixed BOOLEAN,
    fix_attempt_count INTEGER,
    created_at TIMESTAMP
);
```

### Indexes

```sql
CREATE INDEX idx_policy_exp_iter ON policy_iterations(experiment_id, iteration_number);
CREATE INDEX idx_policy_hash ON policy_iterations(policy_hash);
CREATE INDEX idx_llm_exp_iter ON llm_interactions(experiment_id, iteration_number);
CREATE INDEX idx_sim_exp_iter ON simulation_runs(experiment_id, iteration_number);
CREATE INDEX idx_metrics_exp ON iteration_metrics(experiment_id, iteration_number);
CREATE INDEX idx_validation_errors_category ON validation_errors(error_category);
```

---

## Testing Strategy

### Test Structure

```
tests/
├── conftest.py                           # Shared fixtures
├── unit/                                 # 14 unit test files
│   ├── test_dynamic_schema.py            # Dynamic model generation
│   ├── test_parameter_config.py          # ParameterSpec, ScenarioConstraints
│   ├── test_parameter_sets.py            # MINIMAL/STANDARD/FULL
│   ├── test_robust_agent_v2.py           # RobustPolicyAgent
│   ├── test_schema_actions.py            # Action types
│   ├── test_schema_expressions.py        # Expression types
│   ├── test_schema_tree.py               # Depth-limited trees
│   ├── test_schema_values.py             # Value types
│   └── ...
├── integration/                          # 2 integration test files
│   ├── test_simcash_validation.py        # Generated policies pass SimCash
│   └── test_structured_output_pipeline.py # End-to-end LLM → policy
├── test_castro_deferred_crediting.py     # Deferred crediting feature
├── test_castro_scenario_events.py        # Scenario events
├── test_deadline_cap_at_eod.py           # Deadline capping
├── test_determinism.py                   # Reproducibility
├── test_seed_policy.py                   # Seed policy validation
└── ...
```

### Running Tests

```bash
cd experiments/castro

# Run all tests
.venv/bin/python -m pytest tests/ -v

# Run unit tests only
.venv/bin/python -m pytest tests/unit/ -v

# Run integration tests (requires SimCash)
.venv/bin/python -m pytest tests/integration/ -v

# Run with coverage
.venv/bin/python -m pytest tests/ --cov=.
```

### Test Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| Unit | Component validation | Schema parsing, parameter bounds, tree structure |
| Integration | End-to-end validation | Generated policies pass SimCash validator |
| Feature | Castro-specific features | Deferred crediting, deadline caps |
| Determinism | Reproducibility checks | Same seed = same results |

---

## Historical Context

### Evolution of the Codebase

**Phase 1: Original Optimizers (archived)**
- `optimizer.py` → `optimizer_v4.py`: Incremental improvements
- Problem: Corrupted seed files by overwriting them
- Problem: Validation errors not tracked systematically

**Phase 2: Reproducible Framework**
- `reproducible_experiment.py`: Full rewrite with DuckDB
- Never modifies seed files
- Complete artifact tracking
- Parallel simulation

**Phase 3: Dynamic Schema Generation**
- Original: Hardcoded 3 parameters
- Current: Dynamic models from ScenarioConstraints
- Supports any SimCash-valid policy

### Archived Results (docs-2025-12-03/)

| Experiment | Result | Notes |
|------------|--------|-------|
| Exp1 (2-period) | 92.5% cost reduction | Successfully found asymmetric equilibrium |
| Exp3 (joint) | 99.95% cost reduction | Strong learning on joint optimization |
| Exp2 (stochastic) | 8.5% cost increase | Challenging; more work needed |

### Pre-Castro-Alignment (pre-2025-12-02)

Experiments before alignment features:
- Used immediate crediting (not Castro model)
- No EOD deadline caps
- Results not comparable to aligned experiments

---

## Usage Guide

### Quick Start

```bash
cd experiments/castro

# Install dependencies (builds Rust automatically)
uv sync --extra dev

# Set API key
export OPENAI_API_KEY="your-key"

# Run Experiment 1 (2-period deterministic) - NEW CLI
.venv/bin/python cli.py run exp1

# Run Experiment 2 (12-period stochastic) with options
.venv/bin/python cli.py run exp2 --max-iter 30

# Run with Claude and extended thinking
.venv/bin/python cli.py run exp2 \
    --model anthropic:claude-sonnet-4-5-20250929 \
    --thinking-budget 32000

# List available experiments
.venv/bin/python cli.py list

# Generate charts from existing database
.venv/bin/python cli.py charts results/exp1_2025-12-04-143022/experiment.db

# Show experiment summary
.venv/bin/python cli.py summary results/exp1_2025-12-04-143022/experiment.db

# Legacy CLI (still supported)
.venv/bin/python scripts/reproducible_experiment.py --experiment exp1 --output exp1.db
```

### CLI Commands (New Typer CLI)

```bash
# Run an experiment
python cli.py run EXPERIMENT [OPTIONS]
  EXPERIMENT           Experiment key (exp1, exp2, exp3)
  -o, --output         Output database filename (default: experiment.db)
  -m, --model          LLM model (default: gpt-4o)
  --reasoning          Reasoning effort: none|low|medium|high
  --thinking-budget    Token budget for Claude extended thinking
  --max-iter           Override max iterations
  --master-seed        Master seed for reproducibility
  --simcash-root       SimCash root directory
  -v, --verbose        Enable verbose output

# List experiments
python cli.py list

# Generate charts
python cli.py charts DB_PATH [--output DIR]

# Show experiment summary
python cli.py summary DB_PATH
```

### Analyzing Results

```python
import duckdb

conn = duckdb.connect('results/exp1.db', read_only=True)

# Cost progression
conn.execute("""
    SELECT iteration_number, total_cost_mean, settlement_rate_mean
    FROM iteration_metrics
    ORDER BY iteration_number
""").fetchdf()

# Policy evolution
conn.execute("""
    SELECT iteration_number, agent_id, parameters
    FROM policy_iterations
    ORDER BY iteration_number
""").fetchdf()

# Validation error patterns
conn.execute("""
    SELECT error_category, COUNT(*) as count
    FROM validation_errors
    GROUP BY error_category
    ORDER BY count DESC
""").fetchdf()

# LLM token usage
conn.execute("""
    SELECT iteration_number, SUM(tokens_used) as total_tokens
    FROM llm_interactions
    GROUP BY iteration_number
""").fetchdf()
```

### Type Checking

```bash
cd experiments/castro

# Type check
.venv/bin/python -m mypy scripts/ generator/ schemas/

# Lint
.venv/bin/python -m ruff check .

# Format
.venv/bin/python -m ruff format .
```

### After Rust Changes

```bash
# Rebuild SimCash with Rust changes
cd experiments/castro
uv sync --extra dev --reinstall-package payment-simulator
```

---

## Appendix: File Counts

| Category | Count |
|----------|-------|
| Python source files | 25 |
| Test files | 27 |
| Configuration files | 3 |
| Schema files | 9 |
| Generator files | 6 |
| Archived scripts | 5+ |
| Documentation files | 5+ |

---

*Generated: 2025-12-03*
*Updated: 2025-12-04 (v1.1 - experiment isolation, unique IDs, metadata saving)*
*For project-wide patterns, see root `/CLAUDE.md`*
*For API patterns, see `/api/CLAUDE.md`*
