"""Database models for Castro experiment persistence.

Defines the schema for experiment runs and events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ExperimentRunRecord:
    """Record for an experiment run.

    Stores metadata about each experiment execution.

    Attributes:
        run_id: Unique run identifier (e.g., exp1-20251209-143022-a1b2c3)
        experiment_name: Name of the experiment (exp1, exp2, exp3)
        started_at: When the run started
        status: Current status (running, completed, converged, failed)
        completed_at: When the run completed (optional)
        final_cost: Final cost at end (cents, optional)
        best_cost: Best cost achieved (cents, optional)
        num_iterations: Total iterations (optional)
        converged: Whether experiment converged (optional)
        convergence_reason: Reason for stopping (optional)
        model: LLM model used (optional)
        master_seed: Master seed for determinism (optional)
        config_json: Full configuration as JSON (optional)
    """

    run_id: str
    experiment_name: str
    started_at: datetime
    status: str
    completed_at: datetime | None = None
    final_cost: int | None = None
    best_cost: int | None = None
    num_iterations: int | None = None
    converged: bool | None = None
    convergence_reason: str | None = None
    model: str | None = None
    master_seed: int | None = None
    config_json: str | None = None
