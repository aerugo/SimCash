"""Experiment persistence policy configuration.

Phase 3 Database Consolidation: Controls what gets persisted
during experiment execution.

Default policy based on design decisions:
- Full tick-level state snapshots for all evaluation simulations
- Do NOT persist bootstrap sample transactions
- Always persist final evaluation
- Always persist every policy iteration (accepted AND rejected)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SimulationPersistenceLevel(str, Enum):
    """Level of simulation detail to persist.

    Ordered from least to most detail for comparison:
    - NONE: No persistence at all
    - SUMMARY: Final metrics only
    - EVENTS: Events + summary
    - FULL: Full tick-level state
    """

    NONE = "none"
    SUMMARY = "summary"
    EVENTS = "events"
    FULL = "full"


@dataclass
class ExperimentPersistencePolicy:
    """Policy controlling what gets persisted during experiments.

    Attributes:
        simulation_persistence: Level of detail for simulation persistence.
            Default FULL for complete replay capability.

        persist_bootstrap_transactions: Whether to persist bootstrap sample
            transactions. Default False to save storage.

        persist_final_evaluation: Whether to always persist the final
            evaluation simulation. Default True for auditability.

        persist_all_policy_iterations: Whether to persist all policy
            iterations, including rejected ones. Default True for
            complete audit trail.
    """

    simulation_persistence: SimulationPersistenceLevel = SimulationPersistenceLevel.FULL
    persist_bootstrap_transactions: bool = False
    persist_final_evaluation: bool = True
    persist_all_policy_iterations: bool = True
