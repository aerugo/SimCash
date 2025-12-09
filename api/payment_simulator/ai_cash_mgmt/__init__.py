"""AI Cash Management Module - LLM-based policy optimization for SimCash.

This module provides an "AI Cash Manager" game where multiple agents can have
their payment policies automatically optimized by an LLM to minimize costs
while maintaining settlement throughput.

Key Features:
- Transaction Source: Resample from REAL historical transactions
- Optimization Timing: Intra-simulation (every X tick, EoD, or sim end)
- Per-Agent LLM Config: Different agents can use different LLM models
- Determinism: Same master seed produces identical optimization trajectories

Example:
    >>> from payment_simulator.ai_cash_mgmt import (
    ...     GameConfig,
    ...     GameOrchestrator,
    ...     GameMode,
    ... )
    >>> config = GameConfig.from_yaml("game_config.yaml")
    >>> orchestrator = GameOrchestrator(config)
    >>> session = orchestrator.create_session()
"""

from __future__ import annotations

# Configuration
from payment_simulator.ai_cash_mgmt.config import (
    AgentOptimizationConfig,
    ConvergenceCriteria,
    GameConfig,
    LLMConfig,
    LLMProviderType,
    MonteCarloConfig,
    OptimizationSchedule,
    OptimizationScheduleType,
    OutputConfig,
    PolicyConstraints,
    ReasoningEffortType,
    SampleMethod,
)

# Constraints
from payment_simulator.ai_cash_mgmt.constraints import (
    ParameterSpec,
    ScenarioConstraints,
)

# Core
from payment_simulator.ai_cash_mgmt.core import (
    GameMode,
    GameOrchestrator,
    GameSession,
)

# Optimization
from payment_simulator.ai_cash_mgmt.optimization import (
    ConstraintValidator,
    ConvergenceDetector,
    PolicyEvaluator,
    PolicyOptimizer,
)

# Persistence
from payment_simulator.ai_cash_mgmt.persistence import (
    GameRepository,
    GameSessionRecord,
    GameStatus,
    PolicyIterationRecord,
)

# Sampling
from payment_simulator.ai_cash_mgmt.sampling import (
    HistoricalTransaction,
    SeedManager,
    TransactionSampler,
)

__version__ = "0.1.0"

__all__ = [
    # Configuration
    "AgentOptimizationConfig",
    # Optimization
    "ConstraintValidator",
    "ConvergenceCriteria",
    "ConvergenceDetector",
    "GameConfig",
    # Core
    "GameMode",
    "GameOrchestrator",
    # Persistence
    "GameRepository",
    "GameSession",
    "GameSessionRecord",
    "GameStatus",
    # Sampling
    "HistoricalTransaction",
    "LLMConfig",
    "LLMProviderType",
    "MonteCarloConfig",
    "OptimizationSchedule",
    "OptimizationScheduleType",
    "OutputConfig",
    # Constraints
    "ParameterSpec",
    "PolicyConstraints",
    "PolicyEvaluator",
    "PolicyIterationRecord",
    "PolicyOptimizer",
    "ReasoningEffortType",
    "SampleMethod",
    "ScenarioConstraints",
    "SeedManager",
    "TransactionSampler",
    # Version
    "__version__",
]
