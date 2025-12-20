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
    BootstrapConfig,
    ConvergenceCriteria,
    GameConfig,
    LLMConfig,
    LLMProviderType,
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

# Events - LLM optimization event types and helpers (Phase 12)
from payment_simulator.ai_cash_mgmt.events import (
    ALL_EVENT_TYPES,
    EVENT_BOOTSTRAP_EVALUATION,
    EVENT_EXPERIMENT_END,
    EVENT_EXPERIMENT_START,
    EVENT_ITERATION_START,
    EVENT_LLM_CALL,
    EVENT_LLM_INTERACTION,
    EVENT_POLICY_CHANGE,
    EVENT_POLICY_REJECTED,
    create_bootstrap_evaluation_event,
    create_experiment_end_event,
    create_experiment_start_event,
    create_iteration_start_event,
    create_llm_call_event,
    create_llm_interaction_event,
    create_policy_change_event,
    create_policy_rejected_event,
)

# Optimization
from payment_simulator.ai_cash_mgmt.optimization import (
    BootstrapConvergenceDetector,
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
    "BootstrapConfig",
    "ConvergenceCriteria",
    "GameConfig",
    "LLMConfig",
    "LLMProviderType",
    "OptimizationSchedule",
    "OptimizationScheduleType",
    "OutputConfig",
    "PolicyConstraints",
    "ReasoningEffortType",
    "SampleMethod",
    # Constraints
    "ParameterSpec",
    "ScenarioConstraints",
    # Core
    "GameMode",
    "GameOrchestrator",
    "GameSession",
    # Events
    "ALL_EVENT_TYPES",
    "EVENT_BOOTSTRAP_EVALUATION",
    "EVENT_EXPERIMENT_END",
    "EVENT_EXPERIMENT_START",
    "EVENT_ITERATION_START",
    "EVENT_LLM_CALL",
    "EVENT_LLM_INTERACTION",
    "EVENT_POLICY_CHANGE",
    "EVENT_POLICY_REJECTED",
    "create_bootstrap_evaluation_event",
    "create_experiment_end_event",
    "create_experiment_start_event",
    "create_iteration_start_event",
    "create_llm_call_event",
    "create_llm_interaction_event",
    "create_policy_change_event",
    "create_policy_rejected_event",
    # Optimization
    "BootstrapConvergenceDetector",
    "ConstraintValidator",
    "ConvergenceDetector",
    "PolicyEvaluator",
    "PolicyOptimizer",
    # Persistence
    "GameRepository",
    "GameSessionRecord",
    "GameStatus",
    "PolicyIterationRecord",
    # Sampling
    "HistoricalTransaction",
    "SeedManager",
    "TransactionSampler",
    # Version
    "__version__",
]
