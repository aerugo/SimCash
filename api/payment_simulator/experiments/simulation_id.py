"""Simulation ID generation for experiment runs.

Phase 3 Database Consolidation: Provides structured simulation IDs
that link experiments to their constituent simulation runs.

Format: {experiment_id}-iter{N}-{purpose}[-sample{M}]

Examples:
  exp1-20251214-abc123-iter0-initial
  exp1-20251214-abc123-iter5-evaluation
  exp1-20251214-abc123-iter5-bootstrap-sample3
  exp1-20251214-abc123-iter49-final
"""

from __future__ import annotations

import re
from typing import TypedDict

from payment_simulator.persistence.models import SimulationRunPurpose


class ParsedSimulationId(TypedDict):
    """Parsed components of a structured simulation ID."""

    experiment_id: str
    iteration: int
    purpose: SimulationRunPurpose
    sample_index: int | None


# Pattern to match structured simulation IDs
# Format: {experiment_id}-iter{N}-{purpose}[-sample{M}]
# The experiment_id can contain hyphens, so we match greedily up to "-iter"
_SIMULATION_ID_PATTERN = re.compile(
    r"^(.+)-iter(\d+)-(\w+)(?:-sample(\d+))?$"
)


def generate_experiment_simulation_id(
    experiment_id: str,
    iteration: int,
    purpose: SimulationRunPurpose,
    sample_index: int | None = None,
) -> str:
    """Generate structured simulation ID for experiment runs.

    Args:
        experiment_id: Parent experiment ID
        iteration: Iteration number (0-indexed)
        purpose: Simulation purpose (evaluation, bootstrap, etc.)
        sample_index: Bootstrap sample index (only used for BOOTSTRAP purpose)

    Returns:
        Structured simulation ID in format:
        {experiment_id}-iter{N}-{purpose}[-sample{M}]
    """
    base = f"{experiment_id}-iter{iteration}-{purpose.value}"

    # Only include sample index for bootstrap runs
    if sample_index is not None and purpose == SimulationRunPurpose.BOOTSTRAP:
        base += f"-sample{sample_index}"

    return base


def parse_experiment_simulation_id(sim_id: str) -> ParsedSimulationId:
    """Parse structured simulation ID back to components.

    Args:
        sim_id: Structured simulation ID

    Returns:
        Dict with experiment_id, iteration, purpose, sample_index

    Raises:
        ValueError: If sim_id doesn't match expected format
    """
    match = _SIMULATION_ID_PATTERN.match(sim_id)

    if not match:
        raise ValueError(
            f"Invalid simulation ID format: '{sim_id}'. "
            "Expected format: {{experiment_id}}-iter{{N}}-{{purpose}}[-sample{{M}}]"
        )

    experiment_id = match.group(1)
    iteration = int(match.group(2))
    purpose_str = match.group(3)
    sample_str = match.group(4)

    # Validate purpose is a known value
    try:
        purpose = SimulationRunPurpose(purpose_str)
    except ValueError as e:
        raise ValueError(
            f"Invalid simulation ID format: '{sim_id}'. "
            f"Unknown purpose '{purpose_str}'. "
            f"Expected one of: {[p.value for p in SimulationRunPurpose]}"
        ) from e

    sample_index = int(sample_str) if sample_str else None

    return ParsedSimulationId(
        experiment_id=experiment_id,
        iteration=iteration,
        purpose=purpose,
        sample_index=sample_index,
    )
