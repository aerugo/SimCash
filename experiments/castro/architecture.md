# Castro Experiments: Architecture Documentation

This document provides a comprehensive explanation of the experimental setup in `experiments/castro/`, which implements LLM-based policy optimization for high-value payment system liquidity management. The experiments replicate and extend the work of Castro et al. (2025).

---

## Table of Contents

1. [Research Background](#1-research-background)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Core Components](#3-core-components)
4. [Data Flow & Optimization Loop](#4-data-flow--optimization-loop)
5. [The Three Experiments](#5-the-three-experiments)
6. [Policy Structure](#6-policy-structure)
7. [Constraint System](#7-constraint-system)
8. [Persistence & Analysis](#8-persistence--analysis)
9. [Running Experiments](#9-running-experiments)

---

## 1. Research Background

### 1.1 The Problem: High-Value Payment System Liquidity Management

High-value payment systems (HVPSs) are real-time gross settlement systems where banks process inter-bank payments using central bank liquidity. Banks face a complex strategic optimization problem:

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE LIQUIDITY-DELAY TRADEOFF                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Post MORE Collateral (Liquidity)      Post LESS Collateral    │
│  ────────────────────────────────      ────────────────────    │
│  ✓ Can settle payments immediately     ✗ May need to delay     │
│  ✗ Higher opportunity cost             ✓ Lower opportunity     │
│  ✓ No delay penalties                     cost                 │
│  ✓ No end-of-day borrowing             ✗ Delay penalties      │
│                                         ✗ May need borrowing   │
│                                                                 │
│  Banks must BALANCE these competing incentives!                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Castro et al. (2025) Paper Overview

**Title:** "Estimating Policy Functions in Payment Systems Using Reinforcement Learning"

**Authors:** Pablo Castro (Google Brain), Ajit Desai, Han Du, Rodney Garratt, Francisco Rivadeneyra (Bank of Canada)

**Key Contributions:**
1. Demonstrated that RL agents can learn Nash equilibrium strategies in simple payment games
2. Showed agents learn effective liquidity-delay tradeoffs in realistic LVTS-style scenarios
3. Proved joint optimization of initial liquidity AND payment timing is achievable

**Cost Structure from the Paper:**

| Cost Component | Formula | Rate Ordering |
|----------------|---------|---------------|
| Initial Liquidity (Collateral) | `r_c × ℓ₀` | r_c (cheapest) |
| Per-Period Delay | `r_d × P_t(1 - x_t)` | r_d (middle) |
| End-of-Day Borrowing | `r_b × c_b` | r_b (most expensive) |

**Critical Assumption:** `r_c < r_d < r_b` — Collateral is cheaper than delays, which are cheaper than emergency borrowing.

### 1.3 Our Approach: LLM-Based Policy Optimization

Instead of traditional RL (REINFORCE algorithm with neural networks), we use **Large Language Models** to generate and iteratively improve policy decision trees:

```
Traditional RL (Castro paper)        LLM-Based (This Implementation)
─────────────────────────────        ─────────────────────────────────
Neural network policy                JSON decision tree policy
Gradient-based updates               LLM generates improved versions
Continuous action space              Discrete tree with conditions
Black-box decisions                  Interpretable decision logic
Many training episodes               Fewer iterations needed
```

**Advantages of LLM Approach:**
- Interpretable policies (readable decision trees)
- Fewer iterations to convergence
- Can incorporate domain knowledge via prompts
- Natural handling of constraints

---

## 2. System Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CASTRO EXPERIMENTS                                │
│                                                                             │
│  ┌───────────────────┐     ┌───────────────────────────────────────────┐   │
│  │   CLI Interface   │     │            Experiment Runner               │   │
│  │    (cli.py)       │────▶│  - Orchestrates optimization loop          │   │
│  │                   │     │  - Coordinates components                  │   │
│  └───────────────────┘     │  - Manages convergence                     │   │
│                            └───────────────┬───────────────────────────┘   │
│                                            │                                │
│                     ┌──────────────────────┼──────────────────────┐        │
│                     │                      │                      │        │
│                     ▼                      ▼                      ▼        │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌─────────────────┐   │
│  │   LLM Client         │  │ Simulation Runner    │  │   Persistence   │   │
│  │   (llm_client.py)    │  │ (simulation.py)      │  │   (DuckDB)      │   │
│  │                      │  │                      │  │                 │   │
│  │ - Anthropic Claude   │  │ - Wraps Rust         │  │ - Sessions      │   │
│  │ - OpenAI GPT         │  │   Orchestrator       │  │ - Iterations    │   │
│  │ - Policy generation  │  │ - Monte Carlo eval   │  │ - Policies      │   │
│  └──────────────────────┘  └──────────────────────┘  └─────────────────┘   │
│                                            │                                │
│                                            ▼                                │
│                        ┌───────────────────────────────────────┐           │
│                        │         ai_cash_mgmt Module           │           │
│                        │  (from payment_simulator package)     │           │
│                        │                                       │           │
│                        │  - SeedManager (determinism)          │           │
│                        │  - ConvergenceDetector                │           │
│                        │  - ConstraintValidator                │           │
│                        │  - PolicyOptimizer                    │           │
│                        │  - GameRepository                     │           │
│                        └───────────────────────────────────────┘           │
│                                            │                                │
│                                            ▼                                │
│                        ┌───────────────────────────────────────┐           │
│                        │       Rust Simulation Engine          │           │
│                        │     (via PyO3 FFI boundary)           │           │
│                        │                                       │           │
│                        │  - Real-time payment processing       │           │
│                        │  - Settlement & queuing               │           │
│                        │  - Cost calculation                   │           │
│                        │  - Policy execution                   │           │
│                        └───────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
experiments/castro/
├── castro/                          # Core package
│   ├── __init__.py                  # Public API with lazy imports
│   ├── constraints.py               # CASTRO_CONSTRAINTS definition
│   ├── experiments.py               # CastroExperiment + factory functions
│   ├── model_config.py             # ModelConfig for PydanticAI settings
│   ├── pydantic_llm_client.py      # PydanticAI LLM client (multi-provider)
│   ├── runner.py                   # ExperimentRunner orchestration
│   ├── simulation.py               # CastroSimulationRunner wrapper
│   └── verbose_logging.py          # Structured verbose output
│
├── configs/                         # YAML scenario configurations
│   ├── exp1_2period.yaml           # 2-tick deterministic scenario
│   ├── exp2_12period.yaml          # 12-tick stochastic scenario
│   └── exp3_joint.yaml             # 3-tick joint optimization
│
├── tests/                           # Pytest test suite
│   ├── test_experiments.py         # Experiment unit tests
│   ├── test_model_config.py        # Model configuration tests
│   ├── test_pydantic_llm_client.py # PydanticAI client tests
│   └── test_verbose_logging.py     # Verbose logging tests
│
├── papers/                          # Research documentation
│   └── castro_et_al.md             # Full paper summary
│
├── results/                         # Experiment outputs
│   ├── ANALYSIS_REPORT.md          # Analysis of previous runs
│   ├── exp1.db, exp2.db, exp3.db   # DuckDB databases
│   └── charts/                      # PNG visualizations
│
├── cli.py                           # Typer CLI entry point
├── pyproject.toml                   # Package configuration
├── README.md                        # Quick start guide
└── architecture.md                  # This document
```

---

## 3. Core Components

### 3.1 CastroExperiment (experiments.py)

The `CastroExperiment` dataclass encapsulates all experiment configuration:

```python
@dataclass
class CastroExperiment:
    # Identity
    name: str                              # "exp1", "exp2", "exp3"
    description: str                       # Human-readable description

    # Scenario
    scenario_path: Path                    # Path to YAML config

    # Monte Carlo Settings
    num_samples: int = 1                   # Number of evaluation samples
    evaluation_ticks: int = 100            # Ticks per evaluation

    # Optimization Settings
    max_iterations: int = 25               # Maximum optimization iterations
    stability_threshold: float = 0.05      # Cost variance threshold
    stability_window: int = 5              # Consecutive stable iterations

    # LLM Settings (PydanticAI unified format)
    model: str = "anthropic:claude-sonnet-4-5"  # provider:model format
    temperature: float = 0.0               # Deterministic generation
    thinking_budget: int | None = None     # Anthropic extended thinking
    reasoning_effort: str | None = None    # OpenAI: "low", "medium", "high"

    # Agent Settings
    optimized_agents: list[str] = ["BANK_A", "BANK_B"]

    # Output Settings
    output_dir: Path = Path("results")
    master_seed: int = 42                  # RNG seed for reproducibility

    def get_model_config(self) -> ModelConfig:
        """Get PydanticAI model configuration."""
        return ModelConfig(
            model=self.model,
            temperature=self.temperature,
            thinking_budget=self.thinking_budget,
            reasoning_effort=self.reasoning_effort,
        )
```

**Factory Functions:**
- `create_exp1()`: 2-period deterministic Nash equilibrium test
- `create_exp2()`: 12-period stochastic LVTS-style scenario
- `create_exp3()`: 3-period joint liquidity & timing optimization

### 3.2 ExperimentRunner (runner.py)

The central orchestrator that coordinates the optimization loop:

```
ExperimentRunner
├── Core Components (from ai_cash_mgmt)
│   ├── SeedManager           → Deterministic RNG seed derivation
│   ├── ConvergenceDetector   → Tracks cost history for stability
│   ├── ConstraintValidator   → Validates policies against rules
│   └── PolicyOptimizer       → LLM-based policy improvement
│
├── Castro-Specific Components
│   ├── PydanticAILLMClient   → PydanticAI LLM client (multi-provider)
│   ├── ModelConfig           → Model configuration settings
│   └── CastroSimulationRunner → Simulation executor
│
└── State Management
    ├── _policies             → Current policies per agent
    ├── _iteration_history    → Performance history per agent
    ├── _best_cost            → Best total cost seen
    └── _best_policies        → Best policies seen
```

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `run()` | Main async entry point; runs full optimization loop |
| `_load_seed_policies()` | Creates initial "release urgent, hold otherwise" policies |
| `_evaluate_policies()` | Monte Carlo evaluation across N samples |
| `_create_session_record()` | Creates database session record |
| `_save_iteration()` | Persists iteration results to database |

### 3.3 CastroSimulationRunner (simulation.py)

Bridges the SimCash Rust Orchestrator with the experiment framework:

```python
class CastroSimulationRunner:
    def run_simulation(
        self,
        policy: dict[str, Any],    # Policy to evaluate
        seed: int,                  # RNG seed for this run
        ticks: int | None = None,   # Ticks to simulate
    ) -> SimulationResult:
        """
        1. Build config with injected policy and seed
        2. Create Rust Orchestrator
        3. Run tick loop
        4. Extract and return metrics
        """
```

**SimulationResult:**
```python
@dataclass
class SimulationResult:
    total_cost: int                      # Total system cost (cents)
    per_agent_costs: dict[str, int]      # Cost per agent (cents)
    settlement_rate: float               # Fraction of transactions settled
    transactions_settled: int
    transactions_failed: int
```

### 3.4 PydanticAILLMClient (pydantic_llm_client.py)

Unified LLM client using PydanticAI for multi-provider support:

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PydanticAILLMClient                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐                                               │
│  │  ModelConfig     │                                               │
│  │  - model         │◀──── "anthropic:claude-sonnet-4-5"           │
│  │  - temperature   │      "openai:gpt-5.1"                         │
│  │  - thinking_budget (Anthropic)                                   │
│  │  - reasoning_effort (OpenAI)                                     │
│  └────────┬─────────┘                                               │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                 PydanticAI Agent                              │   │
│  │                                                               │   │
│  │  Agent(                                                       │   │
│  │      config.full_model_string,  # e.g. "anthropic:claude..."  │   │
│  │      system_prompt=SYSTEM_PROMPT,                             │   │
│  │  )                                                            │   │
│  └────────┬─────────────────────────────────────────────────────┘   │
│           │                                                          │
│           ▼                                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    generate_policy()                          │   │
│  │                                                               │   │
│  │  1. Build user prompt with:                                   │   │
│  │     - Optimization prompt                                     │   │
│  │     - Current policy JSON                                     │   │
│  │     - Performance history (last 5 iterations)                │   │
│  │                                                               │   │
│  │  2. Call agent.run() with provider-specific model_settings:  │   │
│  │     - anthropic_thinking: {"budget_tokens": N}               │   │
│  │     - openai_reasoning_effort: "high"                        │   │
│  │     - google_thinking_config: {...}                          │   │
│  │                                                               │   │
│  │  3. Parse response:                                           │   │
│  │     - Strip markdown code blocks                              │   │
│  │     - Parse JSON                                              │   │
│  │     - Ensure required fields (version, policy_id)            │   │
│  │     - Ensure all nodes have node_ids                         │   │
│  │                                                               │   │
│  │  4. Return validated policy dict                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Supported Providers:**
| Provider | Model Format | Special Settings |
|----------|--------------|------------------|
| Anthropic | `anthropic:claude-sonnet-4-5` | `anthropic_thinking` |
| OpenAI | `openai:gpt-5.1` | `openai_reasoning_effort` |
| Google | `google:gemini-2.5-flash` | `google_thinking_config` |

**System Prompt (condensed):**
```
You are an expert in payment system optimization.
Generate valid JSON policies for the SimCash payment simulator.

CRITICAL: Every node MUST have a unique "node_id" string field!

Decision tree node types:
1. Action node: {"type": "action", "node_id": "...", "action": "Release"|"Hold"}
2. Condition node: {"type": "condition", ..., "on_true": ..., "on_false": ...}
3. Collateral action: {"type": "action", "action": "PostCollateral"|"HoldCollateral", ...}

Output ONLY valid JSON, no markdown or explanation.
```

### 3.5 ai_cash_mgmt Module Components

The experiment framework uses these components from `payment_simulator.ai_cash_mgmt`:

| Component | File | Purpose |
|-----------|------|---------|
| **SeedManager** | `sampling/seed_manager.py` | SHA-256 based deterministic seed derivation |
| **ConvergenceDetector** | `core/convergence.py` | Tracks cost history, detects stability |
| **ConstraintValidator** | `optimization/validator.py` | Validates policies against scenario rules |
| **PolicyOptimizer** | `optimization/optimizer.py` | LLM-based policy generation with retry logic |
| **GameRepository** | `persistence/repository.py` | DuckDB persistence for sessions & iterations |
| **ScenarioConstraints** | `constraints/constraints.py` | Defines allowed parameters, fields, actions |

---

## 4. Data Flow & Optimization Loop

### 4.1 Complete Execution Flow

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                         EXPERIMENT EXECUTION FLOW                              │
└───────────────────────────────────────────────────────────────────────────────┘

User: python cli.py run exp1 --model claude-sonnet-4-5-20250929 --max-iter 25
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 1. INITIALIZATION                                                              │
│                                                                                │
│    ┌──────────────────┐     ┌───────────────────────────────────────────┐     │
│    │ Create           │────▶│ CastroExperiment                          │     │
│    │ Experiment       │     │ - name: "exp1"                            │     │
│    └──────────────────┘     │ - scenario_path: configs/exp1_2period.yaml│     │
│                             │ - num_samples: 5                          │     │
│                             │ - max_iterations: 25                      │     │
│                             └───────────────────────────────────────────┘     │
│                                              │                                 │
│                                              ▼                                 │
│    ┌──────────────────────────────────────────────────────────────────────┐   │
│    │ ExperimentRunner.__init__()                                           │   │
│    │                                                                       │   │
│    │ Initialize:                                                           │   │
│    │  • SeedManager(master_seed=42)                                       │   │
│    │  • ConvergenceDetector(threshold=0.05, window=5)                     │   │
│    │  • ConstraintValidator(CASTRO_CONSTRAINTS)                           │   │
│    │  • PolicyOptimizer(constraints, max_retries=3)                       │   │
│    │  • PydanticAILLMClient(ModelConfig("anthropic:claude-sonnet-4-5"))   │   │
│    └──────────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 2. SETUP PHASE                                                                 │
│                                                                                │
│    ┌────────────────────────────────────────────────────────────────────┐     │
│    │ runner.run() begins                                                 │     │
│    │                                                                     │     │
│    │ a) Load scenario from YAML                                          │     │
│    │    CastroSimulationRunner.from_yaml(configs/exp1_2period.yaml)      │     │
│    │                                                                     │     │
│    │ b) Initialize DuckDB database                                       │     │
│    │    CREATE TABLE game_sessions (...)                                 │     │
│    │    CREATE TABLE policy_iterations (...)                             │     │
│    │                                                                     │     │
│    │ c) Load seed policies for each agent                                │     │
│    │    BANK_A: { payment_tree: release if urgent, hold otherwise }      │     │
│    │    BANK_B: { payment_tree: release if urgent, hold otherwise }      │     │
│    │                                                                     │     │
│    │ d) Save initial session record                                      │     │
│    │    INSERT INTO game_sessions (game_id='exp1', status='running', ...)│     │
│    └────────────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 3. OPTIMIZATION LOOP (until convergence or max_iterations)                     │
│                                                                                │
│    ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐    │
│     ITERATION 1, 2, 3, ... max_iterations                                      │
│    │                                                                      │    │
│        ┌──────────────────────────────────────────────────────────────┐        │
│    │   │ 3a. EVALUATE CURRENT POLICIES (Monte Carlo)                   │  │    │
│        │                                                               │        │
│    │   │  FOR sample_idx in 0..num_samples:                            │  │    │
│        │      seed = SeedManager.simulation_seed(iteration * 1000 +    │        │
│    │   │              sample_idx)                                      │  │    │
│        │      result = SimulationRunner.run_simulation(policy, seed)   │        │
│    │   │      costs.append(result.total_cost)                          │  │    │
│        │                                                               │        │
│    │   │  mean_total = sum(costs) / len(costs)                         │  │    │
│        │  mean_per_agent = { agent: mean(agent_costs) }                │        │
│    │   └──────────────────────────────────────────────────────────────┘  │    │
│                                   │                                            │
│    │                              ▼                                       │    │
│        ┌──────────────────────────────────────────────────────────────┐        │
│    │   │ 3b. TRACK BEST & CHECK CONVERGENCE                            │  │    │
│        │                                                               │        │
│    │   │  IF mean_total < best_cost:                                   │  │    │
│        │      best_cost = mean_total                                   │        │
│    │   │      best_policies = current_policies.copy()                  │  │    │
│        │                                                               │        │
│    │   │  convergence.record_metric(mean_total)                        │  │    │
│        │  IF convergence.is_converged:                                 │        │
│    │   │      BREAK  ─────────────────────────────────────────────▶ FINALIZE   │
│        └──────────────────────────────────────────────────────────────┘        │
│    │                              │                                       │    │
│                                   ▼                                            │
│    │   ┌──────────────────────────────────────────────────────────────┐  │    │
│        │ 3c. FOR EACH AGENT: OPTIMIZE POLICY                           │       │
│    │   │                                                               │  │    │
│        │  ┌─────────────────────────────────────────────────────────┐  │       │
│    │   │  │ PolicyOptimizer.optimize()                               │  │  │    │
│        │  │                                                          │  │       │
│    │   │  │  1. Build optimization prompt with history               │  │  │    │
│        │  │  2. Call LLMClient.generate_policy()                     │  │       │
│    │   │  │  3. Validate against CASTRO_CONSTRAINTS                  │  │  │    │
│        │  │  4. Return OptimizationResult                            │  │       │
│    │   │  └─────────────────────────────────────────────────────────┘  │  │    │
│        │                              │                                │       │
│    │   │                              ▼                                │  │    │
│        │  ┌─────────────────────────────────────────────────────────┐  │       │
│    │   │  │ EVALUATE NEW POLICY                                      │  │  │    │
│        │  │                                                          │  │       │
│    │   │  │  - Temporarily apply new policy                          │  │  │    │
│        │  │  - Run Monte Carlo evaluation                            │  │       │
│    │   │  │  - Calculate new cost                                    │  │  │    │
│        │  └─────────────────────────────────────────────────────────┘  │       │
│    │   │                              │                                │  │    │
│        │                              ▼                                │       │
│    │   │  ┌─────────────────────────────────────────────────────────┐  │  │    │
│        │  │ ACCEPT OR REJECT                                         │  │       │
│    │   │  │                                                          │  │  │    │
│        │  │  IF new_cost < old_cost:                                 │  │       │
│    │   │  │      ACCEPT: Keep new policy                             │  │  │    │
│        │  │  ELSE:                                                   │  │       │
│    │   │  │      REJECT: Revert to old policy                        │  │  │    │
│        │  │                                                          │  │       │
│    │   │  │  Save PolicyIterationRecord to database                  │  │  │    │
│        │  └─────────────────────────────────────────────────────────┘  │       │
│    │   │                                                               │  │    │
│        └──────────────────────────────────────────────────────────────┘        │
│    │                                                                      │    │
│    └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘    │
└───────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ 4. FINALIZATION                                                                │
│                                                                                │
│    ┌────────────────────────────────────────────────────────────────────┐     │
│    │ • Update session status to CONVERGED or COMPLETED                   │     │
│    │ • Return ExperimentResult:                                          │     │
│    │     - final_cost: best total cost achieved                          │     │
│    │     - num_iterations: iterations run                                │     │
│    │     - converged: True/False                                         │     │
│    │     - per_agent_costs: {BANK_A: x, BANK_B: y}                      │     │
│    │     - best_policies: optimal policies found                         │     │
│    │     - duration_seconds: wall-clock time                             │     │
│    └────────────────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Monte Carlo Evaluation Detail

Each policy evaluation runs multiple simulations with different seeds:

```
Monte Carlo Evaluation (num_samples = 5)
────────────────────────────────────────

Iteration 3:

  Sample 0:  seed = simulation_seed(3000) = 0x7a3b...
             Orchestrator.new(config_with_policy)
             Run 10 ticks
             → Result: total_cost = 15200, per_agent = {A: 7000, B: 8200}

  Sample 1:  seed = simulation_seed(3001) = 0x2f1c...
             Orchestrator.new(config_with_policy)
             Run 10 ticks
             → Result: total_cost = 14800, per_agent = {A: 6900, B: 7900}

  Sample 2:  seed = simulation_seed(3002) = 0x8e4d...
             ...

  Sample 3:  seed = simulation_seed(3003) = 0x1a9f...
             ...

  Sample 4:  seed = simulation_seed(3004) = 0x5c2e...
             ...

  ─────────────────────────────────────────────────────────────────
  MEAN:      total_cost = 15000, per_agent = {A: 6950, B: 8050}
```

### 4.3 Policy Update Cycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           POLICY UPDATE CYCLE                                │
└─────────────────────────────────────────────────────────────────────────────┘

Current Policy (JSON):
{
  "parameters": {"initial_liquidity_fraction": 0.25, "urgency_threshold": 3.0},
  "payment_tree": { release if ticks_to_deadline <= 3, else hold }
}
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ PydanticAI LLM CLIENT                                                        │
│                                                                              │
│ User Prompt:                                                                 │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Optimize this policy to reduce payment processing costs.                 ││
│ │                                                                          ││
│ │ Current policy:                                                          ││
│ │ {"parameters": {"initial_liquidity_fraction": 0.25, ...}, ...}           ││
│ │                                                                          ││
│ │ Performance history:                                                     ││
│ │   Iteration 1: cost=$150.00                                              ││
│ │   Iteration 2: cost=$142.50                                              ││
│ │   Iteration 3: cost=$138.00                                              ││
│ │                                                                          ││
│ │ Generate an improved policy that reduces total cost.                     ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                         │                                    │
│                     ┌───────────────────┴───────────────────┐                │
│                     │      PydanticAI Agent                 │                │
│                     │ (unified multi-provider interface)    │                │
│                     └───────────────────┬───────────────────┘                │
│                                         │                                    │
│         ┌───────────────────────────────┼───────────────────────────────┐    │
│         ▼                               ▼                               ▼    │
│   ┌──────────────┐              ┌──────────────┐              ┌──────────────┐
│   │ Anthropic    │              │ OpenAI       │              │ Google       │
│   │ Claude       │              │ GPT/o1/o3    │              │ Gemini       │
│   └──────────────┘              └──────────────┘              └──────────────┘
│                                         │                                    │
│                                         ▼                                    │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Raw LLM Response:                                                        ││
│ │ ```json                                                                  ││
│ │ {"parameters": {"initial_liquidity_fraction": 0.20, ...}, ...}           ││
│ │ ```                                                                      ││
│ └──────────────────────────────────────────────────────────────────────────┘│
│                                  │                                           │
│                                  ▼                                           │
│ ┌──────────────────────────────────────────────────────────────────────────┐│
│ │ Parse & Validate:                                                        ││
│ │  1. Strip markdown code blocks                                           ││
│ │  2. Parse JSON                                                           ││
│ │  3. Add missing version/policy_id                                        ││
│ │  4. Add missing node_ids to all tree nodes                               ││
│ └──────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
New Policy (Validated JSON):
{
  "version": "2.0",
  "policy_id": "llm_policy_a3f2c1d4",
  "parameters": {"initial_liquidity_fraction": 0.20, "urgency_threshold": 2.0},
  "payment_tree": { release if ticks_to_deadline <= 2, else hold }
}
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ CONSTRAINT VALIDATION (ConstraintValidator)                                  │
│                                                                              │
│ CASTRO_CONSTRAINTS checks:                                                   │
│  ✓ initial_liquidity_fraction in [0.0, 1.0]                                 │
│  ✓ urgency_threshold in [0, 20]                                             │
│  ✓ All field references are allowed (ticks_to_deadline, balance, ...)       │
│  ✓ All actions are allowed (Release, Hold for payment_tree)                 │
│  ✓ Tree structure is valid                                                  │
│                                                                              │
│ Result: VALID ✓  (or INVALID with error list)                               │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ EVALUATION & ACCEPTANCE                                                      │
│                                                                              │
│ 1. Apply new policy temporarily                                              │
│ 2. Run Monte Carlo evaluation                                                │
│    → new_cost = 13500 cents                                                  │
│                                                                              │
│ 3. Compare: old_cost (15000) vs new_cost (13500)                            │
│                                                                              │
│    new_cost < old_cost ?                                                     │
│         │                                                                    │
│    ┌────┴────┐                                                               │
│    │         │                                                               │
│   YES       NO                                                               │
│    │         │                                                               │
│    ▼         ▼                                                               │
│ ACCEPT    REJECT                                                             │
│ (keep)   (revert)                                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. The Three Experiments

### 5.1 Experiment 1: 2-Period Deterministic (Nash Equilibrium)

**Purpose:** Validate that LLM-based optimization converges to the analytically-derived Nash equilibrium.

**Configuration (`configs/exp1_2period.yaml`):**

```yaml
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 42

deferred_crediting: true    # Credits available next tick, not immediately

cost_rates:
  collateral_cost_per_tick_bps: 500      # r_c = 500 basis points/day
  delay_cost_per_tick_per_cent: 0.001    # r_d = 0.1% per tick
  overdraft_bps_per_tick: 2000           # r_b = 2000 bps (high penalty)

agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 50000
    max_collateral_capacity: 10000000

  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 50000
    max_collateral_capacity: 10000000

# Deterministic payment schedule
scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 15000
    deadline: 1
    schedule: { type: OneTime, tick: 0 }

  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 15000
    deadline: 2
    schedule: { type: OneTime, tick: 1 }

  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 5000
    deadline: 2
    schedule: { type: OneTime, tick: 1 }
```

**Expected Outcome (Nash Equilibrium):**

```
Timeline:
─────────────────────────────────────────────────────────────────
Tick 0:  Bank B must pay 15000 → Bank A (deadline: tick 1)
         Bank B has no incoming payments yet
         Bank B must post collateral to fund this payment

Tick 1:  Bank A receives 15000 from Bank B
         Bank A must pay 15000 → Bank B (deadline: tick 2)
         Bank B must pay 5000 → Bank A (deadline: tick 2)

         Bank A can use received 15000 to fund outgoing 15000!
         Bank A needs: 0 collateral (net neutral)

Tick 2:  End of day - all settled
─────────────────────────────────────────────────────────────────

Nash Equilibrium:
  Bank A: initial_liquidity_fraction = 0.0  (posts 0 collateral)
  Bank B: initial_liquidity_fraction = 0.2  (posts 20000 collateral)

  Bank A cost: $0.00 (free-rides on Bank B's liquidity)
  Bank B cost: $20.00 (20000 × 0.001 = $20 collateral cost)
```

### 5.2 Experiment 2: 12-Period Stochastic (LVTS-Style)

**Purpose:** Test liquidity-delay tradeoff learning with realistic stochastic payment arrivals.

**Configuration (`configs/exp2_12period.yaml`):**

```yaml
simulation:
  ticks_per_day: 12
  num_days: 1

cost_rates:
  collateral_cost_per_tick_bps: 42       # ~500/12 scaled to 12 ticks
  delay_cost_per_tick_per_cent: 0.001
  overdraft_bps_per_tick: 167            # ~2000/12

agents:
  - id: BANK_A
    opening_balance: 0
    max_collateral_capacity: 10000000
    arrival_config:
      rate_per_tick: 2.0                 # Poisson λ = 2
      amount_distribution:
        type: LogNormal
        mean: 10000
        std: 5000
      deadline_range: [3, 8]             # Uniform 3-8 ticks
      counterparty_weights:
        BANK_B: 1.0                      # 100% to Bank B

  - id: BANK_B
    # ... similar stochastic config
```

**Expected Behavior:**
- Agents learn to balance initial liquidity vs. delay costs
- Total costs decrease monotonically over iterations
- Higher-demand agent posts more collateral
- Policies stabilize within convergence window

### 5.3 Experiment 3: Joint Optimization (Liquidity + Timing)

**Purpose:** Test simultaneous optimization of initial liquidity AND payment timing decisions.

**Configuration (`configs/exp3_joint.yaml`):**

```yaml
simulation:
  ticks_per_day: 3
  num_days: 1

cost_rates:
  collateral_cost_per_tick_bps: 167      # ~500/3 scaled
  delay_cost_per_tick_per_cent: 0.005    # 5x higher than exp2
  overdraft_bps_per_tick: 667            # ~2000/3

# ... agent configs with stochastic arrivals
```

**Expected Behavior:**
- Agents learn inter-temporal tradeoffs
- When delay is expensive: post more collateral, release payments earlier
- When collateral is expensive: tolerate more delays
- Joint optimization outperforms individual optimization

---

## 6. Policy Structure

### 6.1 Complete Policy Schema

```json
{
  "version": "2.0",
  "policy_id": "unique_identifier",

  "parameters": {
    "initial_liquidity_fraction": 0.25,
    "urgency_threshold": 3.0,
    "liquidity_buffer_factor": 1.0
  },

  "payment_tree": {
    "type": "condition",
    "node_id": "urgency_check",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "action",
      "node_id": "hold_not_urgent",
      "action": "Hold"
    }
  },

  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "tick_zero_check",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "post_initial",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_collateral_capacity"},
            "right": {"param": "initial_liquidity_fraction"}
          }
        },
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "hold_collateral",
      "action": "HoldCollateral"
    }
  }
}
```

### 6.2 Decision Tree Node Types

**Action Node:**
```json
{
  "type": "action",
  "node_id": "release_payment",      // REQUIRED: unique identifier
  "action": "Release"                // or "Hold"
}
```

**Condition Node:**
```json
{
  "type": "condition",
  "node_id": "check_urgency",        // REQUIRED: unique identifier
  "condition": {
    "op": "<=",                      // Operator: <, <=, >, >=, ==, !=
    "left": {"field": "ticks_to_deadline"},  // Left operand
    "right": {"param": "urgency_threshold"}  // Right operand
  },
  "on_true": { /* node */ },         // Branch if condition true
  "on_false": { /* node */ }         // Branch if condition false
}
```

**Collateral Action Node:**
```json
{
  "type": "action",
  "node_id": "post_collateral",
  "action": "PostCollateral",        // or "HoldCollateral"
  "parameters": {
    "amount": {
      "compute": {
        "op": "*",
        "left": {"field": "remaining_collateral_capacity"},
        "right": {"param": "initial_liquidity_fraction"}
      }
    },
    "reason": {"value": "InitialAllocation"}
  }
}
```

### 6.3 Operand Types

| Type | Syntax | Description |
|------|--------|-------------|
| **Field** | `{"field": "ticks_to_deadline"}` | Reference to context field |
| **Parameter** | `{"param": "urgency_threshold"}` | Reference to policy parameter |
| **Value** | `{"value": 3.0}` | Literal numeric value |
| **Compute** | `{"compute": {"op": "*", "left": ..., "right": ...}}` | Arithmetic expression |

---

## 7. Constraint System

### 7.1 CASTRO_CONSTRAINTS Definition

The constraints enforce rules from the Castro paper:

```python
CASTRO_CONSTRAINTS = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec(
            name="initial_liquidity_fraction",
            param_type="float",
            min_value=0.0,
            max_value=1.0,
            description="Fraction of collateral to post at t=0",
        ),
        ParameterSpec(
            name="urgency_threshold",
            param_type="int",
            min_value=0,
            max_value=20,
            description="Ticks before deadline to release payment",
        ),
        ParameterSpec(
            name="liquidity_buffer",
            param_type="float",
            min_value=0.5,
            max_value=3.0,
            description="Multiplier for required liquidity",
        ),
    ],

    allowed_fields=[
        # Time context
        "system_tick_in_day",
        "ticks_remaining_in_day",
        "current_tick",
        # Agent liquidity state
        "balance",
        "effective_liquidity",
        # Transaction context
        "ticks_to_deadline",
        "remaining_amount",
        "amount",
        "priority",
        # Queue state
        "queue1_total_value",
        "outgoing_queue_size",
        # Collateral
        "max_collateral_capacity",
        "posted_collateral",
    ],

    allowed_actions={
        "payment_tree": ["Release", "Hold"],     # No "Split" in Castro
        "bank_tree": ["NoAction"],
        "collateral_tree": ["PostCollateral", "HoldCollateral"],
    },
)
```

### 7.2 What Castro Constraints Prohibit

| Feature | Allowed | Reason |
|---------|---------|--------|
| Payment Splitting | No | Castro paper uses divisible payments conceptually but not explicit splitting |
| Mid-day Collateral | No | Initial liquidity decision at t=0 only |
| LSM (Liquidity Saving) | No | Not part of Castro model |
| Credit Lines | No | Only collateralized liquidity |
| Bank-level Budgeting | No | Simplified agent model |

---

## 8. Persistence & Analysis

### 8.1 Database Schema

**Table: `game_sessions`**
```sql
CREATE TABLE game_sessions (
    game_id VARCHAR PRIMARY KEY,
    scenario_config VARCHAR,
    master_seed BIGINT,
    game_mode VARCHAR,
    config_json VARCHAR,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR,           -- 'running', 'completed', 'converged', 'failed'
    optimized_agents VARCHAR, -- JSON array
    total_iterations INTEGER,
    converged BOOLEAN,
    final_cost DOUBLE
);
```

**Table: `policy_iterations`**
```sql
CREATE TABLE policy_iterations (
    game_id VARCHAR,
    agent_id VARCHAR,
    iteration_number INTEGER,
    trigger_tick INTEGER,
    old_policy_json VARCHAR,
    new_policy_json VARCHAR,
    old_cost DOUBLE,
    new_cost DOUBLE,
    cost_improvement DOUBLE,
    was_accepted BOOLEAN,
    validation_errors VARCHAR,  -- JSON array
    llm_model VARCHAR,
    llm_latency_seconds DOUBLE,
    tokens_used INTEGER,
    created_at TIMESTAMP,

    PRIMARY KEY (game_id, agent_id, iteration_number)
);
```

### 8.2 Analysis Queries

**Cost Evolution:**
```sql
SELECT
    iteration_number,
    agent_id,
    new_cost / 100.0 as cost_dollars,
    was_accepted
FROM policy_iterations
WHERE game_id = 'exp1'
ORDER BY iteration_number, agent_id;
```

**Best Policies:**
```sql
SELECT
    agent_id,
    new_policy_json,
    new_cost / 100.0 as cost_dollars
FROM policy_iterations
WHERE game_id = 'exp1'
  AND was_accepted = true
ORDER BY new_cost ASC
LIMIT 2;
```

**Convergence Detection:**
```sql
WITH cost_deltas AS (
    SELECT
        iteration_number,
        SUM(new_cost) as total_cost,
        LAG(SUM(new_cost)) OVER (ORDER BY iteration_number) as prev_cost
    FROM policy_iterations
    WHERE game_id = 'exp2'
    GROUP BY iteration_number
)
SELECT MIN(iteration_number) as convergence_iteration
FROM cost_deltas
WHERE ABS(total_cost - prev_cost) < 100  -- $1 threshold
  AND iteration_number > 5;
```

### 8.3 Results Charts

The `results/charts/` directory contains visualizations:

| Chart | Description |
|-------|-------------|
| `cost_convergence.png` | Total and per-agent costs over iterations |
| `convergence_speed.png` | How quickly each experiment converges |
| `policy_parameters.png` | Evolution of policy parameters (liquidity fraction, threshold) |
| `exp2_oscillation.png` | Cost oscillation patterns in stochastic experiment |
| `summary_comparison.png` | Cross-experiment comparison |

---

## 9. Running Experiments

### 9.1 CLI Commands

```bash
# List available experiments
uv run castro list

# Show experiment details
uv run castro info exp1

# Validate configuration
uv run castro validate exp2

# Run experiment with defaults
uv run castro run exp1

# Run with custom model (provider:model format)
uv run castro run exp2 \
    --model anthropic:claude-sonnet-4-5 \
    --max-iter 50 \
    --seed 12345 \
    --output ./my_results

# Run with Anthropic extended thinking
uv run castro run exp1 \
    --model anthropic:claude-sonnet-4-5 \
    --thinking-budget 8000

# Run with OpenAI high reasoning effort
uv run castro run exp1 \
    --model openai:gpt-5.1 \
    --reasoning-effort high

# Run with Google Gemini
uv run castro run exp1 --model google:gemini-2.5-flash

# Run with verbose output
uv run castro run exp1 --verbose

# Run with specific verbose flags
uv run castro run exp2 --verbose-policy --verbose-monte-carlo
```

### 9.2 Verbose Logging

The verbose logging system provides granular visibility into experiment execution via CLI flags:

| Flag | Shows |
|------|-------|
| `--verbose` / `-v` | Enable all verbose output |
| `--quiet` / `-q` | Suppress all verbose output |
| `--verbose-policy` | Policy parameter changes (before/after with deltas) |
| `--verbose-monte-carlo` | Per-seed Monte Carlo results with best/worst identification |
| `--verbose-llm` | LLM call metadata (model, tokens, latency) |
| `--verbose-rejections` | Policy rejection analysis (validation errors, retry counts) |

**Components (`verbose_logging.py`):**

```
┌───────────────────────────────────────────────────────────────────┐
│                       VerboseLogger                                │
├───────────────────────────────────────────────────────────────────┤
│  Configuration:                                                    │
│    VerboseConfig(policy, monte_carlo, llm, rejections)           │
│                                                                    │
│  Log Methods:                                                      │
│    log_iteration_start(iteration, total_cost)                     │
│    log_policy_change(agent, old, new, old_cost, new_cost, accept) │
│    log_monte_carlo_evaluation(seed_results, mean, std)            │
│    log_llm_call(LLMCallMetadata)                                  │
│    log_rejection(RejectionDetail)                                  │
│                                                                    │
│  Data Types:                                                       │
│    MonteCarloSeedResult(seed, cost, settled, total, rate)        │
│    LLMCallMetadata(agent_id, model, tokens, latency, context)    │
│    RejectionDetail(agent_id, policy, errors, reason, costs)      │
└───────────────────────────────────────────────────────────────────┘
```

**Example Output (`--verbose-policy`):**

```
Iteration 3
  Total cost: $150.00

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Policy Change: BANK_A      ┃ Old   ┃ New   ┃ Delta ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ initial_liquidity_fraction │ 0.25  │ 0.20  │ -20%  │
│ urgency_threshold          │ 3.0   │ 2.0   │ -33%  │
└────────────────────────────┴───────┴───────┴───────┘
  Evaluation: $150.00 → $135.00 (-10.0%)
  Decision: ACCEPTED
```

**Example Output (`--verbose-monte-carlo`):**

```
Monte Carlo Evaluation (5 samples):
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━┳━━━━━━━┓
┃ Seed         ┃ Cost      ┃ Settled  ┃ Rate  ┃ Note  ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━╇━━━━━━━┩
│ 0x7a3b2c1d   │ $152.00   │ 95/100   │ 95.0% │       │
│ 0x2f1c3e4d   │ $148.00   │ 97/100   │ 97.0% │ Best  │
│ 0x8e4d5f6a   │ $155.00   │ 93/100   │ 93.0% │ Worst │
│ 0x1a9f0b2c   │ $150.00   │ 96/100   │ 96.0% │       │
│ 0x5c2e3d4f   │ $149.00   │ 96/100   │ 96.0% │       │
└──────────────┴───────────┴──────────┴───────┴───────┘
  Mean: $150.80 (std: $2.50)
  Best seed: 0x2f1c3e4d (for debugging)
```

### 9.3 Programmatic Usage

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
print(f"Final cost: ${result.final_cost / 100:.2f}")
print(f"Converged: {result.converged} ({result.convergence_reason})")
print(f"Iterations: {result.num_iterations}")

for agent_id, cost in result.per_agent_costs.items():
    print(f"  {agent_id}: ${cost / 100:.2f}")

for agent_id, policy in result.best_policies.items():
    liquidity = policy['parameters']['initial_liquidity_fraction']
    print(f"  {agent_id} liquidity fraction: {liquidity:.2%}")
```

### 9.4 Environment Setup

```bash
# Install dependencies (ALWAYS use UV, never pip!)
cd experiments/castro
uv sync --extra dev

# Set API keys
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...

# Run tests
uv run pytest tests/ -v
```

---

## Summary

The Castro experiments framework provides a robust, reproducible system for LLM-based policy optimization in payment systems. Key features:

1. **Determinism**: SHA-256 seeded RNG ensures reproducible results
2. **Interpretability**: JSON decision trees are human-readable
3. **Constraint-Driven**: All policies validated against Castro paper rules
4. **Monte Carlo Evaluation**: Robust cost estimation across multiple samples
5. **Full Persistence**: DuckDB storage for analysis and debugging
6. **Multi-Provider via PydanticAI**: Unified interface supporting:
   - **Anthropic Claude** with extended thinking (`--thinking-budget`)
   - **OpenAI GPT/o1/o3** with reasoning effort (`--reasoning-effort`)
   - **Google Gemini** with thinking config

The framework successfully demonstrates that LLMs can learn optimal payment system strategies, converging to Nash equilibria in simple cases and finding effective policies in complex stochastic environments.

---

*Last updated: 2025-12-09*
