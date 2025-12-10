"""Bootstrap-based Monte Carlo policy evaluation module.

This module provides components for bootstrap resampling of historical
transactions to evaluate cash management policies via Monte Carlo simulation.

Key components:
- TransactionRecord: Historical transaction with relative timing offsets
- RemappedTransaction: Transaction with absolute ticks after remapping
- BootstrapSample: Collection of remapped transactions for evaluation
- TransactionHistoryCollector: Collects transaction history from events
- AgentTransactionHistory: Per-agent transaction history
- BootstrapSampler: Generates bootstrap samples with deterministic seeding
- SandboxConfigBuilder: Builds 3-agent sandbox configs for policy evaluation
- BootstrapPolicyEvaluator: Evaluates policies using Monte Carlo simulation
- EvaluationResult: Result of a single sample evaluation
- PairedDelta: Paired comparison between two policies
"""

from __future__ import annotations

from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
    BootstrapPolicyEvaluator,
    EvaluationResult,
    PairedDelta,
)
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import (
    AgentTransactionHistory,
    TransactionHistoryCollector,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
    TransactionRecord,
)
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler
from payment_simulator.ai_cash_mgmt.bootstrap.sandbox_config import SandboxConfigBuilder

__all__ = [
    "AgentTransactionHistory",
    "BootstrapPolicyEvaluator",
    "BootstrapSample",
    "BootstrapSampler",
    "EvaluationResult",
    "PairedDelta",
    "RemappedTransaction",
    "SandboxConfigBuilder",
    "TransactionHistoryCollector",
    "TransactionRecord",
]
