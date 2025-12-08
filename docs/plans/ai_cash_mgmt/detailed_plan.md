# AI Cash Management Module - Detailed Implementation Plan

> **Document Version**: 1.0
> **Date**: 2025-12-08
> **Status**: Planning
> **Authors**: SimCash Engineering Team

---

## Executive Summary

This document outlines the implementation plan for `ai_cash_mgmt`, a new Python module that enables LLM-based policy optimization for the SimCash payment settlement simulator. The module provides an "AI Cash Manager" game where multiple agents can have their payment policies automatically optimized by an LLM to minimize costs while maintaining settlement throughput.

### Key Differentiators from Castro Experiments

| Aspect | Castro Experiments | ai_cash_mgmt Module |
|--------|-------------------|---------------------|
| **Transaction Source** | New random transactions each run | Resample from REAL historical transactions |
| **Optimization Timing** | End of simulation only | Intra-simulation (every X tick, EoD, or sim end) |
| **Database** | Separate experiment database | Shared with main SimCash database |
| **Monte Carlo Data** | Persisted | NOT persisted (ephemeral evaluation) |
| **Scope** | Research experiments | Production feature |
| **Reference** | Castro paper specific | Generalized (no paper reference) |

### Goals

1. **Generalized LLM Policy Optimization** - A production-ready module for AI-driven cash management
2. **Historical Transaction Resampling** - Monte Carlo evaluation using real transaction patterns
3. **Flexible Optimization Schedules** - Support intra-simulation, end-of-day, and inter-simulation optimization
4. **Strict Determinism** - Same master seed produces identical optimization trajectories
5. **Full Observability** - All policy iterations, diffs, and metrics saved to database

---

## Part I: Architecture Overview

### 1.1 Module Position in SimCash

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         User Configuration                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │ scenario.yaml   │  │ seed_policies/  │  │ game_config.yaml        │  │
│  │ (agents, costs, │  │ (initial JSON   │  │ (optimization settings, │  │
│  │  arrivals, etc) │  │  policies)      │  │  LLM config, sampling)  │  │
│  └────────┬────────┘  └────────┬────────┘  └────────────┬────────────┘  │
│           │                    │                        │               │
│           └────────────────────┼────────────────────────┘               │
│                                │                                        │
│                                ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    ai_cash_mgmt Module                            │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │   │
│  │  │ GameOrchest-   │  │ PolicyOptim-   │  │ TransactionSampler  │ │   │
│  │  │ rator          │  │ izer           │  │ (Monte Carlo)       │ │   │
│  │  └───────┬────────┘  └───────┬────────┘  └──────────┬──────────┘ │   │
│  │          │                   │                      │            │   │
│  │          │    ┌──────────────┴──────────────┐       │            │   │
│  │          │    │   ConstraintValidator       │       │            │   │
│  │          │    │   (ScenarioConstraints)     │       │            │   │
│  │          │    └──────────────┬──────────────┘       │            │   │
│  │          │                   │                      │            │   │
│  └──────────┼───────────────────┼──────────────────────┼────────────┘   │
│             │                   │                      │                │
│             ▼                   ▼                      ▼                │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                       api/ Module                                 │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │   │
│  │  │ SimulationRun- │  │ Persistence    │  │ Config Validation   │ │   │
│  │  │ ner            │  │ Layer          │  │ (Pydantic)          │ │   │
│  │  └───────┬────────┘  └───────┬────────┘  └─────────────────────┘ │   │
│  │          │                   │                                   │   │
│  └──────────┼───────────────────┼───────────────────────────────────┘   │
│             │                   │                                       │
│             ▼                   ▼                                       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     simulator/ (Rust FFI)                         │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────┐ │   │
│  │  │ Orchestrator   │  │ Settlement     │  │ Policy Tree         │ │   │
│  │  │ (tick loop)    │  │ Engine         │  │ Executor            │ │   │
│  │  └────────────────┘  └────────────────┘  └─────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     DuckDB (Shared Database)                      │   │
│  │  ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────┐ │   │
│  │  │ simulations  │ │transactions │ │ policy_      │ │ game_     │ │   │
│  │  │              │ │             │ │ iterations   │ │ sessions  │ │   │
│  │  └──────────────┘ └─────────────┘ └──────────────┘ └───────────┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Core Design Principles

1. **Separation of Concerns**
   - `GameOrchestrator`: Manages game lifecycle, scheduling, convergence detection
   - `PolicyOptimizer`: Handles LLM interaction, policy generation, validation
   - `TransactionSampler`: Creates deterministic Monte Carlo samples from historical data
   - `ConstraintValidator`: Ensures generated policies respect scenario limitations

2. **Determinism First**
   - Master seed derives all sub-seeds (sampling, LLM temperature, tie-breaking)
   - Same master seed + same config = identical optimization trajectory
   - Monte Carlo samples are deterministically reproducible

3. **Database Integration**
   - Game sessions share the main SimCash database
   - Monte Carlo evaluation runs are NOT persisted (ephemeral)
   - Policy iterations, metrics, and diffs ARE persisted

4. **Fail-Safe Policy Handling**
   - Invalid policies trigger retry with error feedback
   - Configurable max retries before falling back to best-known policy
   - All validation errors logged for debugging

---

## Part II: Module Structure

### 2.1 Directory Layout

```
ai_cash_mgmt/
├── __init__.py                    # Public API exports
├── config/
│   ├── __init__.py
│   ├── game_config.py             # GameConfig Pydantic model
│   ├── optimization_schedule.py   # Schedule configuration (tick/eod/sim-end)
│   └── convergence.py             # Convergence criteria definitions
├── core/
│   ├── __init__.py
│   ├── game_orchestrator.py       # Main game loop controller
│   ├── game_session.py            # Single game session state
│   └── game_modes.py              # RL-optimization vs campaign-learning
├── optimization/
│   ├── __init__.py
│   ├── policy_optimizer.py        # LLM-based policy generation
│   ├── constraint_validator.py    # Scenario constraint enforcement
│   ├── policy_evaluator.py        # Monte Carlo policy comparison
│   └── convergence_detector.py    # Stability detection logic
├── sampling/
│   ├── __init__.py
│   ├── transaction_sampler.py     # Historical transaction resampling
│   ├── bootstrap_sampler.py       # Bootstrap resampling implementation
│   └── seed_manager.py            # Deterministic seed derivation
├── persistence/
│   ├── __init__.py
│   ├── models.py                  # Database models (GameSession, PolicyIteration, etc.)
│   ├── repository.py              # Database operations
│   └── schema.py                  # DDL for ai_cash_mgmt tables
├── protocols.py                   # Abstract interfaces (Protocol classes)
├── exceptions.py                  # Custom exception types
└── cli.py                         # CLI commands (ai-game run, ai-game replay, etc.)

tests/
├── __init__.py
├── conftest.py                    # Shared fixtures, mocked LLM responses
├── unit/
│   ├── test_game_config.py
│   ├── test_transaction_sampler.py
│   ├── test_constraint_validator.py
│   ├── test_convergence_detector.py
│   ├── test_policy_evaluator.py
│   └── test_seed_manager.py
├── integration/
│   ├── test_game_orchestrator.py
│   ├── test_policy_optimizer.py
│   ├── test_database_integration.py
│   └── test_determinism.py
└── fixtures/
    ├── mock_llm_responses/        # Pre-recorded LLM responses for testing
    ├── sample_scenarios/          # Test scenario configs
    └── sample_policies/           # Test seed policies
```

### 2.2 Public API

```python
# ai_cash_mgmt/__init__.py

from ai_cash_mgmt.config import GameConfig, OptimizationSchedule, ConvergenceCriteria
from ai_cash_mgmt.core import GameOrchestrator, GameSession, GameMode
from ai_cash_mgmt.optimization import PolicyOptimizer, PolicyEvaluator
from ai_cash_mgmt.sampling import TransactionSampler
from ai_cash_mgmt.persistence import GameRepository

__all__ = [
    # Configuration
    "GameConfig",
    "OptimizationSchedule",
    "ConvergenceCriteria",
    # Core
    "GameOrchestrator",
    "GameSession",
    "GameMode",
    # Optimization
    "PolicyOptimizer",
    "PolicyEvaluator",
    # Sampling
    "TransactionSampler",
    # Persistence
    "GameRepository",
]
```

---

## Part III: Configuration Schema

### 3.1 Game Configuration (game_config.yaml)

```yaml
# game_config.yaml - Configuration for AI Cash Management Game

# Metadata
game_id: "experiment_2024_q4_001"
description: "Multi-agent policy optimization with 4 banks"

# Scenario reference
scenario_config: "scenarios/4bank_high_volume.yaml"

# Seed policies for each agent (paths to JSON files)
seed_policies:
  BANK_A: "policies/conservative_seed.json"
  BANK_B: "policies/aggressive_seed.json"
  BANK_C: "policies/balanced_seed.json"
  BANK_D: "policies/balanced_seed.json"

# Master seed for determinism
master_seed: 42

# Agents to optimize (others keep seed policy)
optimized_agents:
  - BANK_A
  - BANK_B
  # BANK_C and BANK_D keep their seed policies

# LLM configuration
llm_config:
  provider: "openai"               # openai, anthropic, google
  model: "gpt-5.1"                 # Model identifier
  reasoning_effort: "high"         # low, medium, high (for reasoning models)
  thinking_budget: null            # Token budget for Claude extended thinking
  temperature: 0.0                 # Deterministic output (derived from master_seed if > 0)
  max_retries: 3                   # Retries on validation failure
  timeout_seconds: 120             # Per-request timeout

# Optimization schedule
optimization_schedule:
  type: "every_x_ticks"            # every_x_ticks, after_eod, on_simulation_end
  # For every_x_ticks:
  interval_ticks: 50               # Optimize every 50 ticks
  # For after_eod:
  # min_remaining_days: 1          # Only if at least 1 day remaining
  # For on_simulation_end:
  # min_remaining_repetitions: 1   # Only if at least 1 more repetition

# Monte Carlo evaluation parameters
monte_carlo:
  num_samples: 20                  # Number of resampled scenarios
  sample_method: "bootstrap"       # bootstrap, permutation, or stratified
  evaluation_ticks: 100            # Ticks to simulate per sample
  parallel_workers: 8              # Parallel simulation workers

# Convergence criteria
convergence:
  metric: "total_cost"             # Metric to track (total_cost, settlement_rate, etc.)
  stability_threshold: 0.05        # 5% relative change threshold
  stability_window: 5              # Require 5 consecutive stable iterations
  max_iterations: 50               # Hard cap on optimization iterations
  improvement_threshold: 0.01      # Minimum improvement to accept new policy

# Policy constraints (derived from scenario, can be overridden)
policy_constraints:
  # If null, derived from scenario config
  allowed_parameters: null
  allowed_fields: null
  allowed_actions: null
  allowed_bank_actions: null
  allowed_collateral_actions: null

# Output configuration
output:
  database_path: "results/game_sessions.db"  # Shared with main SimCash if same path
  save_policy_diffs: true
  save_iteration_metrics: true
  verbose: true
```

### 3.2 Pydantic Configuration Models

```python
# ai_cash_mgmt/config/game_config.py

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class OptimizationScheduleType(str, Enum):
    """When optimization occurs."""
    EVERY_X_TICKS = "every_x_ticks"
    AFTER_EOD = "after_eod"
    ON_SIMULATION_END = "on_simulation_end"


class SampleMethod(str, Enum):
    """Monte Carlo sampling method."""
    BOOTSTRAP = "bootstrap"
    PERMUTATION = "permutation"
    STRATIFIED = "stratified"


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: LLMProvider = Field(
        default=LLMProvider.OPENAI,
        description="LLM provider (openai, anthropic, google)",
    )
    model: str = Field(
        default="gpt-5.1",
        description="Model identifier",
    )
    reasoning_effort: str = Field(
        default="high",
        description="Reasoning effort for compatible models",
    )
    thinking_budget: int | None = Field(
        default=None,
        description="Token budget for extended thinking (Claude only)",
    )
    temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0 for deterministic)",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Max retries on validation failure",
    )
    timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=600,
        description="Request timeout in seconds",
    )


class OptimizationSchedule(BaseModel):
    """Configuration for when optimization occurs."""

    type: OptimizationScheduleType = Field(
        ...,
        description="Schedule type",
    )
    interval_ticks: int | None = Field(
        default=None,
        ge=1,
        description="Interval for every_x_ticks schedule",
    )
    min_remaining_days: int | None = Field(
        default=None,
        ge=1,
        description="Minimum remaining days for after_eod schedule",
    )
    min_remaining_repetitions: int | None = Field(
        default=None,
        ge=1,
        description="Minimum remaining repetitions for on_simulation_end schedule",
    )

    @model_validator(mode="after")
    def validate_schedule_params(self) -> "OptimizationSchedule":
        """Validate schedule-specific parameters are provided."""
        if self.type == OptimizationScheduleType.EVERY_X_TICKS:
            if self.interval_ticks is None:
                raise ValueError("interval_ticks required for every_x_ticks schedule")
        elif self.type == OptimizationScheduleType.AFTER_EOD:
            if self.min_remaining_days is None:
                self.min_remaining_days = 1  # Default
        elif self.type == OptimizationScheduleType.ON_SIMULATION_END:
            if self.min_remaining_repetitions is None:
                self.min_remaining_repetitions = 1  # Default
        return self


class MonteCarloConfig(BaseModel):
    """Monte Carlo evaluation configuration."""

    num_samples: int = Field(
        default=20,
        ge=5,
        le=1000,
        description="Number of resampled scenarios",
    )
    sample_method: SampleMethod = Field(
        default=SampleMethod.BOOTSTRAP,
        description="Sampling method",
    )
    evaluation_ticks: int = Field(
        default=100,
        ge=10,
        description="Ticks to simulate per sample",
    )
    parallel_workers: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Parallel simulation workers",
    )


class ConvergenceCriteria(BaseModel):
    """Convergence detection configuration."""

    metric: str = Field(
        default="total_cost",
        description="Metric to track for convergence",
    )
    stability_threshold: float = Field(
        default=0.05,
        ge=0.001,
        le=0.5,
        description="Relative change threshold for stability",
    )
    stability_window: int = Field(
        default=5,
        ge=2,
        le=20,
        description="Consecutive stable iterations required",
    )
    max_iterations: int = Field(
        default=50,
        ge=5,
        le=500,
        description="Hard cap on optimization iterations",
    )
    improvement_threshold: float = Field(
        default=0.01,
        ge=0.0,
        le=0.5,
        description="Minimum relative improvement to accept new policy",
    )


class PolicyConstraints(BaseModel):
    """Policy generation constraints (from ScenarioConstraints)."""

    allowed_parameters: list[dict[str, Any]] | None = Field(
        default=None,
        description="Allowed parameters (ParameterSpec dicts)",
    )
    allowed_fields: list[str] | None = Field(
        default=None,
        description="Allowed context fields",
    )
    allowed_actions: list[str] | None = Field(
        default=None,
        description="Allowed payment tree actions",
    )
    allowed_bank_actions: list[str] | None = Field(
        default=None,
        description="Allowed bank tree actions",
    )
    allowed_collateral_actions: list[str] | None = Field(
        default=None,
        description="Allowed collateral tree actions",
    )


class OutputConfig(BaseModel):
    """Output and persistence configuration."""

    database_path: str = Field(
        default="results/game_sessions.db",
        description="Path to database file",
    )
    save_policy_diffs: bool = Field(
        default=True,
        description="Save policy diffs between iterations",
    )
    save_iteration_metrics: bool = Field(
        default=True,
        description="Save detailed iteration metrics",
    )
    verbose: bool = Field(
        default=True,
        description="Enable verbose output",
    )


class GameConfig(BaseModel):
    """Complete game configuration."""

    # Metadata
    game_id: str = Field(
        ...,
        min_length=1,
        description="Unique game identifier",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    # Scenario
    scenario_config: str = Field(
        ...,
        description="Path to scenario configuration file",
    )

    # Seed policies
    seed_policies: dict[str, str] = Field(
        ...,
        min_length=1,
        description="Agent ID to seed policy path mapping",
    )

    # Master seed
    master_seed: int = Field(
        ...,
        ge=0,
        description="Master seed for determinism",
    )

    # Optimized agents
    optimized_agents: list[str] = Field(
        ...,
        min_length=1,
        description="Agent IDs to optimize with LLM",
    )

    # Components
    llm_config: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM configuration",
    )
    optimization_schedule: OptimizationSchedule = Field(
        ...,
        description="When to run optimization",
    )
    monte_carlo: MonteCarloConfig = Field(
        default_factory=MonteCarloConfig,
        description="Monte Carlo evaluation settings",
    )
    convergence: ConvergenceCriteria = Field(
        default_factory=ConvergenceCriteria,
        description="Convergence detection settings",
    )
    policy_constraints: PolicyConstraints | None = Field(
        default=None,
        description="Policy generation constraints (derived from scenario if null)",
    )
    output: OutputConfig = Field(
        default_factory=OutputConfig,
        description="Output configuration",
    )

    @field_validator("optimized_agents")
    @classmethod
    def validate_optimized_agents_in_seed_policies(
        cls, v: list[str], info
    ) -> list[str]:
        """Ensure optimized agents have seed policies."""
        seed_policies = info.data.get("seed_policies", {})
        for agent_id in v:
            if agent_id not in seed_policies:
                raise ValueError(
                    f"Optimized agent '{agent_id}' must have a seed policy"
                )
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> "GameConfig":
        """Load configuration from YAML file."""
        import yaml

        with open(path) as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)
```

---

## Part IV: Game Modes

### 4.1 Mode 1: RL-Policy-Optimization

**Purpose**: Iteratively optimize agent policies during a single simulation run or across repeated runs of the same scenario.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────┐
│                    RL-Policy-Optimization Mode                       │
└─────────────────────────────────────────────────────────────────────┘

1. Load scenario + seed policies
2. Initialize simulation
3. Run simulation until optimization trigger:

   ┌──────────────────────────────────────────────────────────────┐
   │ OPTIMIZATION STEP (triggered every X ticks / EoD / sim-end) │
   │                                                              │
   │  a. Collect historical transactions from simulation         │
   │     - Only transactions up to current tick                  │
   │     - Filter by agent if intra-simulation                   │
   │                                                              │
   │  b. For each optimized agent (in parallel):                 │
   │     i.   Sample Monte Carlo scenarios from historical txns  │
   │     ii.  Evaluate CURRENT policy on samples                 │
   │     iii. Generate NEW policy via LLM                        │
   │     iv.  Validate NEW policy against constraints            │
   │     v.   Evaluate NEW policy on SAME samples                │
   │     vi.  Compare: If NEW better → adopt, else → keep        │
   │                                                              │
   │  c. Save iteration metrics to database                      │
   │  d. Check convergence                                       │
   └──────────────────────────────────────────────────────────────┘

4. Continue simulation with (possibly) updated policies
5. Repeat until simulation ends AND convergence reached
```

**Key Characteristics**:
- Optimization can happen mid-simulation
- Policies take effect immediately after optimization
- Historical transactions grow as simulation progresses
- Useful for studying adaptation dynamics

### 4.2 Mode 2: Campaign-Learning

**Purpose**: Run multiple complete simulations (campaigns), optimizing policies between campaigns based on full-run performance.

**Flow**:
```
┌─────────────────────────────────────────────────────────────────────┐
│                      Campaign-Learning Mode                          │
└─────────────────────────────────────────────────────────────────────┘

Iteration 0: Run full simulation with seed policies
             Record all transactions and outcomes

┌──────────────────────────────────────────────────────────────────┐
│ CAMPAIGN ITERATION N (N = 1, 2, 3, ...)                          │
│                                                                  │
│  1. Analyze results from iteration N-1:                         │
│     - Total costs per agent                                     │
│     - Settlement rates                                          │
│     - Cost breakdowns (delay, overdraft, penalty)               │
│                                                                  │
│  2. For each optimized agent (in parallel):                     │
│     a. Create Monte Carlo samples from iteration N-1 txns       │
│     b. Evaluate current policy on samples                       │
│     c. Generate improved policy via LLM with full history       │
│     d. Validate policy against scenario constraints             │
│     e. Evaluate new policy on SAME samples                      │
│     f. Accept if improved, else keep best-known                 │
│                                                                  │
│  3. Run full simulation with updated policies                   │
│     - Fresh simulation state                                    │
│     - Same scenario configuration                               │
│     - Deterministic seed derived from master_seed + N           │
│                                                                  │
│  4. Check convergence across campaign history                   │
└──────────────────────────────────────────────────────────────────┘

Repeat until convergence or max iterations
```

**Key Characteristics**:
- Clean separation between learning and evaluation
- Full simulation history available for optimization
- Policies only change between campaigns
- Better for studying converged equilibria

---

## Part V: Transaction Sampling

### 5.1 Historical Transaction Collection

The `TransactionSampler` collects transactions from the simulation for Monte Carlo evaluation.

```python
# ai_cash_mgmt/sampling/transaction_sampler.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(frozen=True)
class HistoricalTransaction:
    """Immutable record of a historical transaction."""

    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents
    priority: int
    arrival_tick: int
    deadline_tick: int
    is_divisible: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for simulation injection."""
        return {
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "amount": self.amount,
            "priority": self.priority,
            "deadline_ticks": self.deadline_tick - self.arrival_tick,
            "is_divisible": self.is_divisible,
        }


class TransactionSampler:
    """Samples transactions from historical data for Monte Carlo evaluation.

    Key Design Decisions:
    - Deterministic: Same seed produces same samples
    - Agent-filtered: Can sample only transactions relevant to specific agent
    - Tick-bounded: For intra-simulation, only uses transactions up to current tick

    Usage:
        sampler = TransactionSampler(seed=42)

        # Collect from simulation
        sampler.collect_transactions(orchestrator.get_all_transactions())

        # Generate samples for BANK_A
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=20,
            max_tick=50,  # Only txns from ticks 0-50
        )
    """

    def __init__(self, seed: int) -> None:
        """Initialize sampler with deterministic seed."""
        self._seed = seed
        self._rng = self._create_rng(seed)
        self._transactions: list[HistoricalTransaction] = []

    @staticmethod
    def _create_rng(seed: int):
        """Create deterministic RNG from seed."""
        import numpy as np
        return np.random.Generator(np.random.PCG64(seed))

    def collect_transactions(
        self,
        transactions: list[dict[str, Any]],
    ) -> None:
        """Collect transactions from simulation state.

        Args:
            transactions: List of transaction dicts from orchestrator
        """
        for tx in transactions:
            self._transactions.append(
                HistoricalTransaction(
                    tx_id=tx["tx_id"],
                    sender_id=tx["sender_id"],
                    receiver_id=tx["receiver_id"],
                    amount=tx["amount"],
                    priority=tx.get("priority", 5),
                    arrival_tick=tx["arrival_tick"],
                    deadline_tick=tx["deadline_tick"],
                    is_divisible=tx.get("is_divisible", True),
                )
            )

    def create_samples(
        self,
        agent_id: str,
        num_samples: int,
        max_tick: int | None = None,
        method: str = "bootstrap",
    ) -> list[list[HistoricalTransaction]]:
        """Create Monte Carlo transaction samples.

        Args:
            agent_id: Filter to transactions involving this agent
            num_samples: Number of samples to create
            max_tick: Only include transactions arriving before this tick
            method: Sampling method (bootstrap, permutation, stratified)

        Returns:
            List of transaction lists (one per sample)
        """
        # Filter transactions
        filtered = self._filter_transactions(agent_id, max_tick)

        if not filtered:
            return [[] for _ in range(num_samples)]

        if method == "bootstrap":
            return self._bootstrap_sample(filtered, num_samples)
        elif method == "permutation":
            return self._permutation_sample(filtered, num_samples)
        elif method == "stratified":
            return self._stratified_sample(filtered, num_samples)
        else:
            raise ValueError(f"Unknown sampling method: {method}")

    def _filter_transactions(
        self,
        agent_id: str,
        max_tick: int | None,
    ) -> list[HistoricalTransaction]:
        """Filter transactions by agent and tick."""
        result = []
        for tx in self._transactions:
            # Include if agent is sender or receiver
            if tx.sender_id != agent_id and tx.receiver_id != agent_id:
                continue
            # Include if within tick bound
            if max_tick is not None and tx.arrival_tick > max_tick:
                continue
            result.append(tx)
        return result

    def _bootstrap_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Bootstrap resampling (with replacement)."""
        n = len(transactions)
        samples = []
        for _ in range(num_samples):
            indices = self._rng.integers(0, n, size=n)
            samples.append([transactions[i] for i in indices])
        return samples

    def _permutation_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Permutation sampling (shuffle arrival order)."""
        samples = []
        for _ in range(num_samples):
            shuffled = list(transactions)
            self._rng.shuffle(shuffled)
            samples.append(shuffled)
        return samples

    def _stratified_sample(
        self,
        transactions: list[HistoricalTransaction],
        num_samples: int,
    ) -> list[list[HistoricalTransaction]]:
        """Stratified sampling by transaction size buckets."""
        # Group by amount quartiles
        amounts = [tx.amount for tx in transactions]
        quartiles = [
            int(q) for q in
            [0] + list(self._rng.choice(amounts, size=3, replace=False)) + [max(amounts) + 1]
        ]
        quartiles.sort()

        buckets: dict[int, list[HistoricalTransaction]] = {i: [] for i in range(4)}
        for tx in transactions:
            for i in range(4):
                if quartiles[i] <= tx.amount < quartiles[i + 1]:
                    buckets[i].append(tx)
                    break

        samples = []
        for _ in range(num_samples):
            sample = []
            for bucket in buckets.values():
                if bucket:
                    n = len(bucket)
                    indices = self._rng.integers(0, n, size=n)
                    sample.extend([bucket[i] for i in indices])
            samples.append(sample)
        return samples

    def derive_subseed(self, iteration: int, agent_id: str) -> int:
        """Derive deterministic subseed for a specific optimization.

        Ensures same master_seed + iteration + agent produces same samples.
        """
        import hashlib

        key = f"{self._seed}:{iteration}:{agent_id}"
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big")
```

### 5.2 Deterministic Seed Manager

```python
# ai_cash_mgmt/sampling/seed_manager.py

from __future__ import annotations

import hashlib


class SeedManager:
    """Manages deterministic seed derivation for reproducibility.

    All randomness in the ai_cash_mgmt module flows through this manager,
    ensuring that the same master_seed produces identical results.

    Seed derivation hierarchy:
    - master_seed
      ├── simulation_seed (for running the main simulation)
      ├── sampling_seed (for Monte Carlo transaction sampling)
      │   ├── iteration_N_agent_A
      │   ├── iteration_N_agent_B
      │   └── ...
      ├── llm_seed (for LLM temperature if stochastic)
      └── tiebreaker_seed (for equal-cost policy selection)
    """

    def __init__(self, master_seed: int) -> None:
        self.master_seed = master_seed

    def derive_seed(self, *components: str | int) -> int:
        """Derive a sub-seed from master seed and components.

        Args:
            *components: Hierarchical components (e.g., "simulation", 0, "BANK_A")

        Returns:
            Deterministic seed derived from master + components
        """
        key = ":".join(str(c) for c in [self.master_seed] + list(components))
        hash_bytes = hashlib.sha256(key.encode()).digest()
        return int.from_bytes(hash_bytes[:8], byteorder="big") % (2**31)

    def simulation_seed(self, iteration: int) -> int:
        """Seed for running simulation at given iteration."""
        return self.derive_seed("simulation", iteration)

    def sampling_seed(self, iteration: int, agent_id: str) -> int:
        """Seed for Monte Carlo sampling for specific agent/iteration."""
        return self.derive_seed("sampling", iteration, agent_id)

    def llm_seed(self, iteration: int, agent_id: str) -> int:
        """Seed for LLM randomness (if temperature > 0)."""
        return self.derive_seed("llm", iteration, agent_id)

    def tiebreaker_seed(self, iteration: int) -> int:
        """Seed for breaking ties between equal-cost policies."""
        return self.derive_seed("tiebreaker", iteration)
```

---

## Part VI: Policy Optimization

### 6.1 Policy Optimizer

```python
# ai_cash_mgmt/optimization/policy_optimizer.py

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from ai_cash_mgmt.config import GameConfig, LLMConfig
from ai_cash_mgmt.optimization.constraint_validator import ConstraintValidator


@dataclass
class OptimizationResult:
    """Result of a policy optimization attempt."""

    agent_id: str
    iteration: int
    old_policy: dict[str, Any]
    new_policy: dict[str, Any] | None
    old_cost: float
    new_cost: float | None
    was_accepted: bool
    validation_errors: list[str]
    llm_latency_seconds: float
    tokens_used: int


class LLMClient(Protocol):
    """Protocol for LLM clients."""

    async def generate_policy(
        self,
        instruction: str,
        current_policy: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a policy from instruction and context."""
        ...


class PolicyOptimizer:
    """LLM-based policy optimizer with constraint validation.

    Key Responsibilities:
    - Generate improved policies via LLM
    - Validate policies against scenario constraints
    - Handle retries on validation failure
    - Ensure agent isolation (no cross-agent information leakage)

    Usage:
        optimizer = PolicyOptimizer(
            llm_config=config.llm_config,
            constraints=scenario_constraints,
        )

        result = await optimizer.optimize_agent(
            agent_id="BANK_A",
            current_policy=policy_a,
            current_cost=50000,
            iteration_history=history_for_bank_a,  # Pre-filtered!
            monte_carlo_context=mc_context,
        )
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        constraints: "ScenarioConstraints",
        verbose: bool = False,
    ) -> None:
        self.llm_config = llm_config
        self.validator = ConstraintValidator(constraints)
        self.verbose = verbose
        self._client = self._create_client()

    def _create_client(self) -> LLMClient:
        """Create appropriate LLM client based on config."""
        # Implementation uses PydanticAI with provider-specific setup
        from ai_cash_mgmt.optimization._llm_clients import create_llm_client
        return create_llm_client(self.llm_config)

    async def optimize_agent(
        self,
        agent_id: str,
        current_policy: dict[str, Any],
        current_cost: float,
        iteration: int,
        iteration_history: list[dict[str, Any]],
        monte_carlo_context: dict[str, Any],
    ) -> OptimizationResult:
        """Optimize policy for a single agent.

        CRITICAL: iteration_history must be pre-filtered to only contain
        this agent's data. No cross-agent information leakage!

        Args:
            agent_id: Agent being optimized
            current_policy: Agent's current policy
            current_cost: Cost from current policy evaluation
            iteration: Current optimization iteration
            iteration_history: FILTERED history for this agent only
            monte_carlo_context: Context from MC evaluation

        Returns:
            OptimizationResult with new policy (or None if failed)
        """
        import time

        all_errors: list[str] = []

        for attempt in range(self.llm_config.max_retries):
            start_time = time.time()

            try:
                # Build instruction with error feedback for retries
                instruction = self._build_instruction(
                    agent_id=agent_id,
                    current_cost=current_cost,
                    iteration=iteration,
                    iteration_history=iteration_history,
                    monte_carlo_context=monte_carlo_context,
                    previous_errors=all_errors if attempt > 0 else None,
                )

                # Generate policy via LLM
                new_policy = await self._client.generate_policy(
                    instruction=instruction,
                    current_policy=current_policy,
                    context={"agent_id": agent_id, "iteration": iteration},
                )

                latency = time.time() - start_time

                # Validate against constraints
                validation = self.validator.validate(new_policy)

                if not validation.is_valid:
                    all_errors.extend(validation.errors)
                    if self.verbose:
                        print(f"  [{agent_id}] Validation failed (attempt {attempt + 1}): {validation.errors}")
                    continue

                # Success!
                return OptimizationResult(
                    agent_id=agent_id,
                    iteration=iteration,
                    old_policy=current_policy,
                    new_policy=new_policy,
                    old_cost=current_cost,
                    new_cost=None,  # Filled in by evaluator
                    was_accepted=False,  # Determined after evaluation
                    validation_errors=[],
                    llm_latency_seconds=latency,
                    tokens_used=2000,  # Estimate
                )

            except Exception as e:
                all_errors.append(str(e))
                if self.verbose:
                    print(f"  [{agent_id}] LLM error (attempt {attempt + 1}): {e}")

        # All retries exhausted
        return OptimizationResult(
            agent_id=agent_id,
            iteration=iteration,
            old_policy=current_policy,
            new_policy=None,
            old_cost=current_cost,
            new_cost=None,
            was_accepted=False,
            validation_errors=all_errors,
            llm_latency_seconds=0,
            tokens_used=0,
        )

    async def optimize_agents_parallel(
        self,
        agent_contexts: list[dict[str, Any]],
        stagger_interval: float = 0.5,
    ) -> list[OptimizationResult]:
        """Optimize multiple agents in parallel.

        Args:
            agent_contexts: List of dicts with agent optimization context
            stagger_interval: Delay between starting each agent (rate limiting)

        Returns:
            List of OptimizationResults (one per agent)
        """
        tasks = []
        for i, ctx in enumerate(agent_contexts):
            # Stagger starts to avoid rate limits
            if i > 0:
                await asyncio.sleep(stagger_interval)

            task = asyncio.create_task(
                self.optimize_agent(
                    agent_id=ctx["agent_id"],
                    current_policy=ctx["current_policy"],
                    current_cost=ctx["current_cost"],
                    iteration=ctx["iteration"],
                    iteration_history=ctx["iteration_history"],
                    monte_carlo_context=ctx["monte_carlo_context"],
                )
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def _build_instruction(
        self,
        agent_id: str,
        current_cost: float,
        iteration: int,
        iteration_history: list[dict[str, Any]],
        monte_carlo_context: dict[str, Any],
        previous_errors: list[str] | None,
    ) -> str:
        """Build optimization instruction for LLM."""
        parts = [
            f"# Policy Optimization for {agent_id} - Iteration {iteration}",
            "",
            "## Current Performance",
            f"- Total Cost: ${current_cost:,.0f}",
            f"- Settlement Rate: {monte_carlo_context.get('settlement_rate', 1.0) * 100:.1f}%",
            "",
            "## Task",
            "Generate an improved policy that reduces total cost while maintaining high settlement rate.",
        ]

        if previous_errors:
            parts.extend([
                "",
                "## Previous Validation Errors (FIX THESE)",
                *[f"- {e}" for e in previous_errors[:5]],  # Limit to 5
            ])

        if iteration_history:
            parts.extend([
                "",
                "## Recent Iteration History",
            ])
            for hist in iteration_history[-3:]:  # Last 3 iterations
                parts.append(
                    f"- Iter {hist['iteration']}: cost=${hist['cost']:,.0f}, "
                    f"params={hist.get('parameters', {})}"
                )

        return "\n".join(parts)
```

### 6.2 Constraint Validator

```python
# ai_cash_mgmt/optimization/constraint_validator.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from experiments.castro.schemas.parameter_config import ScenarioConstraints


@dataclass
class ValidationResult:
    """Result of policy validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ConstraintValidator:
    """Validates policies against scenario constraints.

    Ensures generated policies only use:
    - Allowed parameters (with valid bounds)
    - Allowed context fields
    - Allowed actions for each tree type

    Usage:
        validator = ConstraintValidator(scenario_constraints)
        result = validator.validate(policy_dict)
        if not result.is_valid:
            print(f"Errors: {result.errors}")
    """

    def __init__(self, constraints: "ScenarioConstraints") -> None:
        self.constraints = constraints
        self._allowed_params = set(constraints.get_parameter_names())
        self._allowed_fields = set(constraints.allowed_fields)
        self._allowed_actions = set(constraints.allowed_actions)
        self._allowed_bank_actions = set(constraints.allowed_bank_actions or [])
        self._allowed_collateral_actions = set(constraints.allowed_collateral_actions or [])

    def validate(self, policy: dict[str, Any]) -> ValidationResult:
        """Validate a complete policy against constraints."""
        errors: list[str] = []
        warnings: list[str] = []

        # Validate parameters
        self._validate_parameters(policy, errors, warnings)

        # Validate each tree
        if "payment_tree" in policy:
            self._validate_tree(
                policy["payment_tree"],
                "payment_tree",
                self._allowed_actions,
                errors,
            )

        if "bank_tree" in policy:
            if not self._allowed_bank_actions:
                errors.append("bank_tree not allowed in this scenario")
            else:
                self._validate_tree(
                    policy["bank_tree"],
                    "bank_tree",
                    self._allowed_bank_actions,
                    errors,
                )

        for tree_name in ["strategic_collateral_tree", "end_of_tick_collateral_tree"]:
            if tree_name in policy:
                if not self._allowed_collateral_actions:
                    errors.append(f"{tree_name} not allowed in this scenario")
                else:
                    self._validate_tree(
                        policy[tree_name],
                        tree_name,
                        self._allowed_collateral_actions,
                        errors,
                    )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_parameters(
        self,
        policy: dict[str, Any],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Validate policy parameters against allowed list and bounds."""
        params = policy.get("parameters", {})

        for name, value in params.items():
            if name not in self._allowed_params:
                errors.append(f"Parameter '{name}' not allowed in this scenario")
                continue

            # Check bounds
            spec = self.constraints.get_parameter_by_name(name)
            if spec:
                if not (spec.min_value <= value <= spec.max_value):
                    errors.append(
                        f"Parameter '{name}' value {value} out of bounds "
                        f"[{spec.min_value}, {spec.max_value}]"
                    )

    def _validate_tree(
        self,
        node: dict[str, Any],
        tree_name: str,
        allowed_actions: set[str],
        errors: list[str],
    ) -> None:
        """Recursively validate a decision tree."""
        if not isinstance(node, dict):
            errors.append(f"{tree_name}: Node must be a dict")
            return

        node_type = node.get("type")

        if node_type == "action":
            action = node.get("action")
            if action not in allowed_actions:
                errors.append(
                    f"{tree_name}: Action '{action}' not allowed. "
                    f"Allowed: {sorted(allowed_actions)}"
                )
            # Validate action parameters reference allowed fields
            self._validate_values_in_node(node, tree_name, errors)

        elif node_type == "condition":
            # Validate condition references allowed fields
            self._validate_condition(node.get("condition", {}), tree_name, errors)

            # Recurse into branches
            if "on_true" in node:
                self._validate_tree(node["on_true"], tree_name, allowed_actions, errors)
            if "on_false" in node:
                self._validate_tree(node["on_false"], tree_name, allowed_actions, errors)

        else:
            errors.append(f"{tree_name}: Unknown node type '{node_type}'")

    def _validate_condition(
        self,
        condition: dict[str, Any],
        tree_name: str,
        errors: list[str],
    ) -> None:
        """Validate a condition expression."""
        for key in ["left", "right"]:
            if key in condition:
                self._validate_value(condition[key], tree_name, errors)

        if "values" in condition:  # For min/max operations
            for val in condition["values"]:
                self._validate_value(val, tree_name, errors)

    def _validate_value(
        self,
        value: Any,
        tree_name: str,
        errors: list[str],
    ) -> None:
        """Validate a value reference."""
        if isinstance(value, dict):
            if "field" in value:
                field_name = value["field"]
                if field_name not in self._allowed_fields:
                    errors.append(
                        f"{tree_name}: Field '{field_name}' not allowed. "
                        f"Allowed: {sorted(list(self._allowed_fields)[:10])}..."
                    )
            elif "param" in value:
                param_name = value["param"]
                if param_name not in self._allowed_params:
                    errors.append(
                        f"{tree_name}: Parameter '{param_name}' not defined"
                    )
            elif "compute" in value:
                self._validate_condition(value["compute"], tree_name, errors)

    def _validate_values_in_node(
        self,
        node: dict[str, Any],
        tree_name: str,
        errors: list[str],
    ) -> None:
        """Validate all value references in a node."""
        params = node.get("parameters", {})
        for param_name, param_value in params.items():
            self._validate_value(param_value, tree_name, errors)
```

### 6.3 Policy Evaluator

```python
# ai_cash_mgmt/optimization/policy_evaluator.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from concurrent.futures import ProcessPoolExecutor, as_completed


@dataclass
class EvaluationResult:
    """Result of Monte Carlo policy evaluation."""

    mean_cost: float
    std_cost: float
    settlement_rate: float
    sample_costs: list[float]
    cost_breakdown: dict[str, float]


class PolicyEvaluator:
    """Evaluates policies using Monte Carlo simulation.

    Key Design:
    - Runs simulations with injected transactions (NOT random arrivals)
    - Uses parallel workers for efficiency
    - Does NOT persist Monte Carlo runs to database

    Usage:
        evaluator = PolicyEvaluator(
            scenario_config=config,
            simcash_root="/path/to/SimCash",
            parallel_workers=8,
        )

        result = evaluator.evaluate(
            policy=new_policy,
            transaction_samples=monte_carlo_samples,
            evaluation_ticks=100,
        )
    """

    def __init__(
        self,
        scenario_config: dict[str, Any],
        simcash_root: str,
        parallel_workers: int = 8,
    ) -> None:
        self.scenario_config = scenario_config
        self.simcash_root = simcash_root
        self.parallel_workers = parallel_workers

    def evaluate(
        self,
        policy: dict[str, Any],
        agent_id: str,
        transaction_samples: list[list[dict[str, Any]]],
        evaluation_ticks: int,
        base_seed: int,
    ) -> EvaluationResult:
        """Evaluate policy on Monte Carlo transaction samples.

        IMPORTANT: These simulation runs are ephemeral and NOT persisted!

        Args:
            policy: Policy to evaluate
            agent_id: Agent whose policy is being evaluated
            transaction_samples: List of transaction lists (one per MC sample)
            evaluation_ticks: Number of ticks to simulate
            base_seed: Base seed for determinism

        Returns:
            EvaluationResult with cost statistics
        """
        sample_costs: list[float] = []
        cost_breakdowns: list[dict[str, float]] = []
        settlement_rates: list[float] = []

        # Prepare args for parallel execution
        eval_args = [
            (
                self.scenario_config,
                policy,
                agent_id,
                samples,
                evaluation_ticks,
                base_seed + i,
                self.simcash_root,
            )
            for i, samples in enumerate(transaction_samples)
        ]

        with ProcessPoolExecutor(max_workers=self.parallel_workers) as executor:
            futures = {
                executor.submit(_run_mc_simulation, args): i
                for i, args in enumerate(eval_args)
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if "error" not in result:
                        sample_costs.append(result["cost"])
                        settlement_rates.append(result["settlement_rate"])
                        cost_breakdowns.append(result["cost_breakdown"])
                except Exception as e:
                    # Log but continue with other samples
                    print(f"  MC sample failed: {e}")

        if not sample_costs:
            raise RuntimeError("All Monte Carlo samples failed")

        import statistics

        # Aggregate cost breakdowns
        avg_breakdown = {}
        if cost_breakdowns:
            keys = cost_breakdowns[0].keys()
            for key in keys:
                avg_breakdown[key] = statistics.mean(
                    bd.get(key, 0) for bd in cost_breakdowns
                )

        return EvaluationResult(
            mean_cost=statistics.mean(sample_costs),
            std_cost=statistics.stdev(sample_costs) if len(sample_costs) > 1 else 0,
            settlement_rate=statistics.mean(settlement_rates),
            sample_costs=sample_costs,
            cost_breakdown=avg_breakdown,
        )


def _run_mc_simulation(args: tuple) -> dict[str, Any]:
    """Run a single Monte Carlo simulation (worker function).

    This function is designed to run in a separate process.
    It does NOT persist results to the database.
    """
    (
        scenario_config,
        policy,
        agent_id,
        transactions,
        evaluation_ticks,
        seed,
        simcash_root,
    ) = args

    try:
        # Import here to avoid multiprocessing issues
        import json
        import tempfile
        import subprocess
        from pathlib import Path

        # Create temporary config with injected transactions
        temp_config = _create_temp_config(
            scenario_config,
            policy,
            agent_id,
            transactions,
            evaluation_ticks,
            seed,
        )

        # Write temp config
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            import yaml
            yaml.dump(temp_config, f)
            config_path = f.name

        # Write temp policy
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(policy, f)
            policy_path = f.name

        try:
            # Run simulation WITHOUT persistence
            cmd = [
                str(Path(simcash_root) / "api" / ".venv" / "bin" / "payment-sim"),
                "run",
                "--config", config_path,
                "--seed", str(seed),
                "--quiet",
                # NO --persist flag - ephemeral run
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=simcash_root,
                timeout=60,
            )

            if result.returncode != 0:
                return {"error": result.stderr}

            # Parse output
            output = json.loads(result.stdout.strip())
            costs = output.get("costs", {})

            return {
                "cost": costs.get("total_cost", 0),
                "settlement_rate": output.get("metrics", {}).get("settlement_rate", 0),
                "cost_breakdown": {
                    "delay": costs.get("total_delay_cost", 0),
                    "overdraft": costs.get("total_overdraft_cost", 0),
                    "collateral": costs.get("total_collateral_cost", 0),
                    "penalty": costs.get("total_eod_penalty", 0),
                },
            }
        finally:
            # Clean up temp files
            import os
            os.unlink(config_path)
            os.unlink(policy_path)

    except Exception as e:
        return {"error": str(e)}


def _create_temp_config(
    base_config: dict[str, Any],
    policy: dict[str, Any],
    agent_id: str,
    transactions: list[dict[str, Any]],
    evaluation_ticks: int,
    seed: int,
) -> dict[str, Any]:
    """Create temporary config with injected transactions."""
    import copy

    config = copy.deepcopy(base_config)

    # Disable random arrivals
    for agent in config.get("agents", []):
        if "arrival_config" in agent:
            agent["arrival_config"]["rate_per_tick"] = 0.0

    # Inject transactions as scenario events
    config["scenario_events"] = []
    for tx in transactions:
        config["scenario_events"].append({
            "type": "CustomTransactionArrival",
            "from_agent": tx["sender_id"],
            "to_agent": tx["receiver_id"],
            "amount": tx["amount"],
            "priority": tx.get("priority", 5),
            "deadline": tx.get("deadline_ticks", 50),
            "schedule": {
                "type": "OneTime",
                "tick": tx.get("arrival_tick", 0),
            },
        })

    # Set evaluation duration
    config["ticks_per_day"] = evaluation_ticks
    config["num_days"] = 1

    return config
```

---

## Part VII: Convergence Detection

### 7.1 Convergence Detector

```python
# ai_cash_mgmt/optimization/convergence_detector.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai_cash_mgmt.config import ConvergenceCriteria


@dataclass
class ConvergenceState:
    """Current convergence state."""

    is_converged: bool
    iterations_stable: int
    best_cost: float
    best_iteration: int
    recent_costs: list[float]
    reason: str | None = None


class ConvergenceDetector:
    """Detects when policy optimization has converged.

    Convergence is defined as:
    - Metric has been stable (within threshold) for N consecutive iterations
    - OR max iterations reached

    Usage:
        detector = ConvergenceDetector(config.convergence)

        for iteration in range(max_iterations):
            cost = evaluate_policy(...)
            detector.record_iteration(iteration, cost)

            if detector.check_convergence().is_converged:
                break
    """

    def __init__(self, criteria: ConvergenceCriteria) -> None:
        self.criteria = criteria
        self._history: list[tuple[int, float]] = []
        self._best_cost: float = float("inf")
        self._best_iteration: int = -1

    def record_iteration(
        self,
        iteration: int,
        metric_value: float,
    ) -> None:
        """Record metric value for an iteration."""
        self._history.append((iteration, metric_value))

        if metric_value < self._best_cost:
            self._best_cost = metric_value
            self._best_iteration = iteration

    def check_convergence(self) -> ConvergenceState:
        """Check if optimization has converged."""
        n = len(self._history)

        # Check max iterations
        if n >= self.criteria.max_iterations:
            return ConvergenceState(
                is_converged=True,
                iterations_stable=0,
                best_cost=self._best_cost,
                best_iteration=self._best_iteration,
                recent_costs=[h[1] for h in self._history[-5:]],
                reason=f"Max iterations ({self.criteria.max_iterations}) reached",
            )

        # Need at least stability_window iterations
        if n < self.criteria.stability_window:
            return ConvergenceState(
                is_converged=False,
                iterations_stable=n,
                best_cost=self._best_cost,
                best_iteration=self._best_iteration,
                recent_costs=[h[1] for h in self._history],
                reason=None,
            )

        # Check stability over window
        window = self._history[-self.criteria.stability_window:]
        window_values = [h[1] for h in window]

        # Calculate relative change within window
        min_val = min(window_values)
        max_val = max(window_values)

        if min_val == 0:
            relative_change = 0 if max_val == 0 else float("inf")
        else:
            relative_change = (max_val - min_val) / abs(min_val)

        is_stable = relative_change <= self.criteria.stability_threshold

        if is_stable:
            return ConvergenceState(
                is_converged=True,
                iterations_stable=self.criteria.stability_window,
                best_cost=self._best_cost,
                best_iteration=self._best_iteration,
                recent_costs=window_values,
                reason=(
                    f"Stable for {self.criteria.stability_window} iterations "
                    f"(relative change {relative_change:.2%} <= "
                    f"{self.criteria.stability_threshold:.2%})"
                ),
            )

        # Count consecutive stable iterations
        stable_count = 0
        for i in range(len(window) - 1, 0, -1):
            prev_val = window[i - 1][1]
            curr_val = window[i][1]
            if prev_val == 0:
                break
            change = abs(curr_val - prev_val) / abs(prev_val)
            if change <= self.criteria.stability_threshold:
                stable_count += 1
            else:
                break

        return ConvergenceState(
            is_converged=False,
            iterations_stable=stable_count,
            best_cost=self._best_cost,
            best_iteration=self._best_iteration,
            recent_costs=window_values,
            reason=None,
        )

    def should_accept_policy(
        self,
        old_cost: float,
        new_cost: float,
    ) -> bool:
        """Determine if new policy should be accepted.

        Accepts if:
        - New cost is lower than old cost
        - AND improvement exceeds threshold
        """
        if new_cost >= old_cost:
            return False

        if old_cost == 0:
            return new_cost < 0

        improvement = (old_cost - new_cost) / abs(old_cost)
        return improvement >= self.criteria.improvement_threshold
```

---

## Part VIII: Database Schema

### 8.1 New Tables for ai_cash_mgmt

```sql
-- ai_cash_mgmt/persistence/schema.py (as SQL for documentation)

-- Game session metadata
CREATE TABLE IF NOT EXISTS game_sessions (
    game_session_id VARCHAR PRIMARY KEY,
    game_id VARCHAR NOT NULL,                   -- From config
    game_mode VARCHAR NOT NULL,                 -- 'rl_optimization' or 'campaign_learning'
    master_seed INTEGER NOT NULL,
    scenario_config_path VARCHAR NOT NULL,
    scenario_config_hash VARCHAR(64) NOT NULL,
    game_config_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR NOT NULL,                    -- 'running', 'completed', 'failed'
    final_convergence_reason VARCHAR,
    total_iterations INTEGER,
    total_llm_calls INTEGER,
    total_llm_tokens INTEGER
);

-- Policy iterations (extends main policy_snapshots with game context)
CREATE TABLE IF NOT EXISTS game_policy_iterations (
    iteration_id VARCHAR PRIMARY KEY,
    game_session_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,
    agent_id VARCHAR NOT NULL,
    policy_json TEXT NOT NULL,
    policy_hash VARCHAR(64) NOT NULL,
    parameters_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,

    -- Evaluation metrics
    mean_cost DOUBLE,
    std_cost DOUBLE,
    settlement_rate DOUBLE,
    cost_breakdown_json TEXT,

    -- Acceptance tracking
    was_accepted BOOLEAN NOT NULL,
    is_best_so_far BOOLEAN NOT NULL,
    acceptance_reason VARCHAR,

    -- LLM metadata
    llm_latency_seconds DOUBLE,
    llm_tokens_used INTEGER,
    validation_errors_json TEXT,

    FOREIGN KEY (game_session_id) REFERENCES game_sessions(game_session_id)
);

-- Policy diffs between iterations
CREATE TABLE IF NOT EXISTS game_policy_diffs (
    diff_id VARCHAR PRIMARY KEY,
    game_session_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    from_iteration INTEGER NOT NULL,
    to_iteration INTEGER NOT NULL,
    diff_json TEXT NOT NULL,                   -- Structured diff
    diff_summary TEXT,                         -- Human-readable summary
    created_at TIMESTAMP NOT NULL,

    FOREIGN KEY (game_session_id) REFERENCES game_sessions(game_session_id)
);

-- Iteration-level metrics (aggregated across agents)
CREATE TABLE IF NOT EXISTS game_iteration_metrics (
    metric_id VARCHAR PRIMARY KEY,
    game_session_id VARCHAR NOT NULL,
    iteration_number INTEGER NOT NULL,

    -- Aggregated costs
    total_cost_mean DOUBLE NOT NULL,
    total_cost_std DOUBLE NOT NULL,
    per_agent_costs_json TEXT NOT NULL,

    -- Settlement
    settlement_rate_mean DOUBLE NOT NULL,

    -- Convergence state
    is_converged BOOLEAN NOT NULL,
    iterations_stable INTEGER NOT NULL,

    -- Timing
    iteration_duration_seconds DOUBLE,
    created_at TIMESTAMP NOT NULL,

    FOREIGN KEY (game_session_id) REFERENCES game_sessions(game_session_id)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_game_policy_iter_session
    ON game_policy_iterations(game_session_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_game_policy_iter_agent
    ON game_policy_iterations(game_session_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_game_metrics_session
    ON game_iteration_metrics(game_session_id, iteration_number);
CREATE INDEX IF NOT EXISTS idx_game_sessions_status
    ON game_sessions(status);
```

---

## Part IX: Implementation Phases

### Phase 1: Foundation (Week 1-2)

**Goal**: Core infrastructure and configuration

**Tasks**:
1. Create module directory structure
2. Implement `GameConfig` Pydantic models
3. Implement `SeedManager` for deterministic seed derivation
4. Implement `ConstraintValidator` (reuse Castro's `ScenarioConstraints`)
5. Set up database schema and migrations
6. Write TDD tests for all foundation components

**Tests** (write FIRST):
```python
# tests/unit/test_game_config.py
def test_game_config_loads_from_yaml(): ...
def test_game_config_validates_optimized_agents_have_seed_policies(): ...
def test_optimization_schedule_validates_required_params(): ...

# tests/unit/test_seed_manager.py
def test_same_master_seed_produces_same_derived_seeds(): ...
def test_different_components_produce_different_seeds(): ...
def test_seed_manager_is_deterministic_across_runs(): ...

# tests/unit/test_constraint_validator.py
def test_validator_rejects_unknown_parameters(): ...
def test_validator_rejects_out_of_bounds_parameters(): ...
def test_validator_rejects_unknown_fields(): ...
def test_validator_rejects_invalid_actions_for_tree_type(): ...
```

**Deliverables**:
- [ ] `ai_cash_mgmt/config/` module complete
- [ ] `ai_cash_mgmt/sampling/seed_manager.py` complete
- [ ] `ai_cash_mgmt/optimization/constraint_validator.py` complete
- [ ] `ai_cash_mgmt/persistence/schema.py` and migrations
- [ ] 100% test coverage for foundation

### Phase 2: Transaction Sampling (Week 2-3)

**Goal**: Historical transaction collection and Monte Carlo sampling

**Tasks**:
1. Implement `TransactionSampler` with bootstrap, permutation, stratified methods
2. Implement transaction filtering by agent and tick
3. Integrate with main SimCash database for transaction queries
4. Ensure deterministic sampling with seed manager

**Tests** (write FIRST):
```python
# tests/unit/test_transaction_sampler.py
def test_bootstrap_sample_with_replacement(): ...
def test_permutation_sample_preserves_all_transactions(): ...
def test_stratified_sample_maintains_distribution(): ...
def test_same_seed_produces_identical_samples(): ...
def test_filter_by_agent_includes_sender_and_receiver(): ...
def test_filter_by_max_tick_excludes_future_transactions(): ...

# tests/integration/test_transaction_sampling_integration.py
def test_sampler_collects_from_orchestrator(): ...
def test_sampler_produces_valid_monte_carlo_inputs(): ...
```

**Deliverables**:
- [ ] `ai_cash_mgmt/sampling/transaction_sampler.py` complete
- [ ] `ai_cash_mgmt/sampling/bootstrap_sampler.py` complete
- [ ] Integration tests with SimCash orchestrator
- [ ] Determinism tests passing

### Phase 3: Policy Optimization (Week 3-4)

**Goal**: LLM-based policy generation with PydanticAI

**Tasks**:
1. Implement `PolicyOptimizer` with LLM client abstraction
2. Create LLM clients for OpenAI, Anthropic, Google (reuse Castro patterns)
3. Implement retry logic with error feedback
4. Implement parallel agent optimization
5. Create comprehensive mock LLM responses for testing

**Tests** (write FIRST, with mocks):
```python
# tests/fixtures/mock_llm_responses/
# - valid_policy_response.json
# - invalid_parameter_response.json
# - invalid_action_response.json

# tests/unit/test_policy_optimizer.py
def test_optimizer_generates_valid_policy(mock_llm): ...
def test_optimizer_retries_on_validation_failure(mock_llm): ...
def test_optimizer_returns_none_after_max_retries(mock_llm): ...
def test_optimizer_includes_error_feedback_in_retry(mock_llm): ...
def test_optimizer_maintains_agent_isolation(mock_llm): ...

# tests/integration/test_policy_optimizer_integration.py
def test_optimizer_with_real_llm_generates_valid_policy(): ...  # Uses actual API
```

**Deliverables**:
- [ ] `ai_cash_mgmt/optimization/policy_optimizer.py` complete
- [ ] `ai_cash_mgmt/optimization/_llm_clients.py` complete
- [ ] Mock LLM response fixtures for all error cases
- [ ] 95%+ test coverage with mocks

### Phase 4: Policy Evaluation (Week 4-5)

**Goal**: Monte Carlo policy evaluation without persistence

**Tasks**:
1. Implement `PolicyEvaluator` with parallel simulation
2. Create ephemeral simulation runner (no database writes)
3. Implement transaction injection via scenario events
4. Aggregate evaluation metrics

**Tests** (write FIRST):
```python
# tests/unit/test_policy_evaluator.py
def test_evaluator_runs_monte_carlo_simulations(): ...
def test_evaluator_does_not_persist_results(): ...
def test_evaluator_aggregates_costs_correctly(): ...
def test_evaluator_handles_simulation_failures_gracefully(): ...

# tests/integration/test_policy_evaluation_integration.py
def test_evaluator_with_real_simcash_runner(): ...
def test_evaluation_is_deterministic_with_same_seed(): ...
```

**Deliverables**:
- [ ] `ai_cash_mgmt/optimization/policy_evaluator.py` complete
- [ ] Ephemeral simulation runner
- [ ] Integration with SimCash CLI
- [ ] Performance benchmarks (target: 20 MC samples in <30s)

### Phase 5: Convergence & Game Orchestrator (Week 5-6)

**Goal**: Complete game loop with convergence detection

**Tasks**:
1. Implement `ConvergenceDetector`
2. Implement `GameOrchestrator` for RL-optimization mode
3. Implement `GameSession` state management
4. Add campaign-learning mode
5. Implement CLI commands

**Tests** (write FIRST):
```python
# tests/unit/test_convergence_detector.py
def test_converges_after_stable_window(): ...
def test_converges_at_max_iterations(): ...
def test_tracks_best_iteration_correctly(): ...
def test_should_accept_policy_with_improvement(): ...

# tests/integration/test_game_orchestrator.py
def test_rl_optimization_mode_runs_to_convergence(mock_llm): ...
def test_campaign_learning_mode_runs_multiple_campaigns(mock_llm): ...
def test_optimization_at_every_x_ticks(mock_llm): ...
def test_optimization_after_eod(mock_llm): ...

# tests/integration/test_determinism.py
def test_same_master_seed_produces_identical_game_trajectory(): ...
```

**Deliverables**:
- [ ] `ai_cash_mgmt/optimization/convergence_detector.py` complete
- [ ] `ai_cash_mgmt/core/game_orchestrator.py` complete
- [ ] `ai_cash_mgmt/core/game_session.py` complete
- [ ] `ai_cash_mgmt/core/game_modes.py` complete
- [ ] CLI commands: `ai-game run`, `ai-game status`, `ai-game export`

### Phase 6: Database Integration & Persistence (Week 6-7)

**Goal**: Full persistence with shared SimCash database

**Tasks**:
1. Implement `GameRepository` for database operations
2. Integrate with main SimCash database (shared connection)
3. Implement policy diff tracking
4. Add query interface for game results
5. Export functionality

**Tests** (write FIRST):
```python
# tests/integration/test_database_integration.py
def test_game_session_persisted_to_database(): ...
def test_policy_iterations_tracked_correctly(): ...
def test_policy_diffs_computed_and_stored(): ...
def test_game_shares_database_with_simcash(): ...
def test_monte_carlo_results_not_persisted(): ...
```

**Deliverables**:
- [ ] `ai_cash_mgmt/persistence/repository.py` complete
- [ ] `ai_cash_mgmt/persistence/models.py` complete
- [ ] Database migrations
- [ ] Query interface for analysis

### Phase 7: Documentation & Polish (Week 7-8)

**Goal**: Complete documentation and production readiness

**Tasks**:
1. Write reference documentation
2. Create user guide with examples
3. Add comprehensive docstrings
4. Performance optimization
5. Error handling improvements
6. Final integration testing

**Documentation**:
- [ ] `docs/reference/ai_cash_mgmt/index.md`
- [ ] `docs/reference/ai_cash_mgmt/configuration.md`
- [ ] `docs/reference/ai_cash_mgmt/game-modes.md`
- [ ] `docs/reference/ai_cash_mgmt/optimization.md`
- [ ] `docs/reference/ai_cash_mgmt/cli.md`
- [ ] Example configs and policies

---

## Part X: Test Strategy

### 10.1 Mock LLM Responses

To minimize LLM API calls during development, we create comprehensive mock responses:

```python
# tests/conftest.py

import pytest
from typing import Any
from unittest.mock import AsyncMock


@pytest.fixture
def mock_llm_client():
    """Mock LLM client that returns pre-defined responses."""
    client = AsyncMock()

    # Default: return valid policy
    client.generate_policy.return_value = VALID_POLICY_RESPONSE

    return client


@pytest.fixture
def mock_llm_client_with_validation_error():
    """Mock that returns invalid policy on first call, valid on second."""
    client = AsyncMock()
    client.generate_policy.side_effect = [
        INVALID_PARAMETER_RESPONSE,  # First call
        VALID_POLICY_RESPONSE,       # Retry
    ]
    return client


# Pre-defined responses
VALID_POLICY_RESPONSE = {
    "version": "2.0",
    "policy_id": "mock_optimized_v1",
    "parameters": {
        "urgency_threshold": 4.0,
        "liquidity_buffer": 1.2,
    },
    "payment_tree": {
        "type": "condition",
        "node_id": "P1",
        "condition": {
            "op": "<=",
            "left": {"field": "ticks_to_deadline"},
            "right": {"param": "urgency_threshold"},
        },
        "on_true": {"type": "action", "node_id": "P2", "action": "Release"},
        "on_false": {"type": "action", "node_id": "P3", "action": "Hold"},
    },
}

INVALID_PARAMETER_RESPONSE = {
    "version": "2.0",
    "policy_id": "mock_invalid_v1",
    "parameters": {
        "unknown_param": 5.0,  # Not in allowed list
    },
    "payment_tree": {
        "type": "action",
        "node_id": "P1",
        "action": "Release",
    },
}
```

### 10.2 Integration Test with Real LLM

For CI/CD, we include a single integration test that calls the real LLM:

```python
# tests/integration/test_real_llm.py

import os
import pytest

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
@pytest.mark.slow
def test_real_llm_generates_valid_policy():
    """Integration test with real GPT-5.1 API.

    This test is skipped in normal CI runs.
    Run with: pytest -m slow
    """
    from ai_cash_mgmt.optimization import PolicyOptimizer
    from ai_cash_mgmt.config import LLMConfig
    from experiments.castro.parameter_sets import STANDARD_CONSTRAINTS

    optimizer = PolicyOptimizer(
        llm_config=LLMConfig(
            provider="openai",
            model="gpt-5.1",
            reasoning_effort="high",
        ),
        constraints=STANDARD_CONSTRAINTS,
    )

    result = asyncio.run(
        optimizer.optimize_agent(
            agent_id="BANK_A",
            current_policy=SEED_POLICY,
            current_cost=50000,
            iteration=0,
            iteration_history=[],
            monte_carlo_context={"settlement_rate": 0.95},
        )
    )

    assert result.new_policy is not None
    assert len(result.validation_errors) == 0
```

### 10.3 Determinism Tests

Critical tests to ensure reproducibility:

```python
# tests/integration/test_determinism.py

def test_same_master_seed_produces_identical_trajectory():
    """The most important test: same seed = same results."""
    from ai_cash_mgmt import GameOrchestrator, GameConfig

    config = GameConfig.from_yaml("tests/fixtures/sample_game_config.yaml")

    # Run 1
    game1 = GameOrchestrator(config)
    result1 = game1.run(max_iterations=5)

    # Run 2 (same config, same seed)
    game2 = GameOrchestrator(config)
    result2 = game2.run(max_iterations=5)

    # Must be identical
    assert result1.final_costs == result2.final_costs
    assert result1.policy_hashes == result2.policy_hashes
    assert result1.convergence_iteration == result2.convergence_iteration


def test_monte_carlo_samples_are_deterministic():
    """Same seed produces identical MC samples."""
    from ai_cash_mgmt.sampling import TransactionSampler

    sampler1 = TransactionSampler(seed=42)
    sampler1.collect_transactions(SAMPLE_TRANSACTIONS)
    samples1 = sampler1.create_samples("BANK_A", num_samples=10)

    sampler2 = TransactionSampler(seed=42)
    sampler2.collect_transactions(SAMPLE_TRANSACTIONS)
    samples2 = sampler2.create_samples("BANK_A", num_samples=10)

    for s1, s2 in zip(samples1, samples2):
        assert [tx.tx_id for tx in s1] == [tx.tx_id for tx in s2]
```

---

## Part XI: Documentation Plan

### 11.1 Reference Documentation Structure

```
docs/reference/ai_cash_mgmt/
├── index.md                    # Overview and quick start
├── configuration.md            # GameConfig schema reference
├── game-modes.md               # RL-optimization vs campaign-learning
├── optimization.md             # Policy optimizer details
├── sampling.md                 # Transaction sampling methods
├── convergence.md              # Convergence detection
├── database.md                 # Database schema and queries
├── cli.md                      # CLI command reference
└── examples/
    ├── basic-2-agent.md        # Simple 2-agent example
    ├── multi-agent-campaign.md # Full campaign example
    └── custom-constraints.md   # Custom constraint definition
```

### 11.2 Documentation Standards

Following the existing SimCash documentation patterns:

1. **Each document has**:
   - Clear purpose statement
   - Code examples with syntax highlighting
   - Configuration snippets in YAML
   - Cross-references to related docs
   - Source code locations

2. **Example-driven**:
   - Every concept illustrated with working examples
   - Examples are tested (extracted and run in CI)

3. **Consistent structure**:
   - Overview → Configuration → Usage → Reference → Source locations

---

## Part XII: Success Criteria

### 12.1 Functional Requirements

- [ ] Two game modes working (RL-optimization, campaign-learning)
- [ ] All three optimization schedules (every_x_ticks, after_eod, on_simulation_end)
- [ ] Monte Carlo sampling from historical transactions
- [ ] Policy validation against scenario constraints
- [ ] Convergence detection with configurable criteria
- [ ] Parallel agent optimization
- [ ] Shared database with SimCash (MC runs NOT persisted)
- [ ] Complete determinism (same seed = same trajectory)

### 12.2 Quality Requirements

- [ ] 90%+ test coverage
- [ ] All TDD tests written before implementation
- [ ] Mock LLM responses for 95% of tests
- [ ] Integration test with real LLM (GPT-5.1)
- [ ] Determinism tests passing
- [ ] Type annotations on all public APIs
- [ ] mypy and ruff passing

### 12.3 Performance Requirements

- [ ] Monte Carlo evaluation: 20 samples in <30 seconds
- [ ] Policy generation: <10 seconds per agent
- [ ] Game orchestrator overhead: <5% of total runtime
- [ ] Database writes: <100ms per iteration

### 12.4 Documentation Requirements

- [ ] Reference docs for all public APIs
- [ ] User guide with examples
- [ ] CLI help text
- [ ] Inline docstrings (Google style)

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Game Session** | A complete optimization run from start to convergence |
| **Iteration** | One optimization cycle (evaluate → generate → validate → compare) |
| **Monte Carlo Sample** | A resampled transaction set for policy evaluation |
| **Policy Constraint** | Restriction on allowed parameters/fields/actions |
| **Convergence** | State where policy cost has stabilized |
| **Campaign** | A full simulation run in campaign-learning mode |
| **Seed Policy** | Initial policy before optimization begins |

---

## Appendix B: Risk Analysis

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM generates invalid policies repeatedly | Medium | Error feedback in retry, fallback to best-known |
| Monte Carlo sampling bias | High | Multiple sampling methods, stratification |
| Non-determinism bugs | Critical | Comprehensive determinism tests, seed manager |
| Database contention | Low | Separate game tables, connection pooling |
| LLM API rate limits | Medium | Staggered requests, exponential backoff |
| Large transaction sets causing memory issues | Medium | Streaming collection, batch processing |

---

## Appendix C: Dependencies

### Python Dependencies

```toml
# pyproject.toml additions
[project.optional-dependencies]
ai_cash_mgmt = [
    "pydantic-ai>=0.0.14",      # LLM structured output
    "openai>=1.0.0",             # OpenAI client
    "anthropic>=0.7.0",          # Anthropic client
    "google-generativeai>=0.3",  # Google Gemini client
    "numpy>=1.24.0",             # Numerical operations
    "pyyaml>=6.0",               # YAML parsing
]
```

### Reused Components from Castro

- `ScenarioConstraints` and `ParameterSpec` from `experiments/castro/schemas/parameter_config.py`
- `RobustPolicyAgent` patterns from `experiments/castro/generator/robust_policy_agent.py`
- Dynamic schema generation from `experiments/castro/schemas/dynamic.py`
- Validation logic from `experiments/castro/generator/validation.py`

---

*Document End - Ready for Team Review*
