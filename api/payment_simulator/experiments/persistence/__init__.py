"""Experiment persistence module.

Handles storing and retrieving experiment results.

Components:
    - ExperimentRepository: Unified repository for persistence
    - ExperimentRecord: Immutable experiment metadata record
    - IterationRecord: Immutable iteration data record
    - EventRecord: Immutable event data record

Example:
    >>> from payment_simulator.experiments.persistence import (
    ...     ExperimentRepository,
    ...     ExperimentRecord,
    ... )
    >>> with ExperimentRepository(Path("experiments.db")) as repo:
    ...     repo.save_experiment(record)
    ...     loaded = repo.load_experiment("run-123")
"""

from payment_simulator.experiments.persistence.repository import (
    EventRecord,
    ExperimentRecord,
    ExperimentRepository,
    IterationRecord,
)

__all__ = [
    "ExperimentRepository",
    "ExperimentRecord",
    "IterationRecord",
    "EventRecord",
]
