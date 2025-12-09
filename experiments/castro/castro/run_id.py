"""Run ID generation for Castro experiments.

Provides unique identifiers for experiment runs to enable replay and tracking.
"""

from __future__ import annotations

import re
import secrets
from datetime import datetime
from typing import TypedDict


class ParsedRunId(TypedDict):
    """Parsed components of a run ID."""

    experiment_name: str
    date: str
    time: str
    random_suffix: str


def generate_run_id(experiment_name: str) -> str:
    """Generate a unique run ID.

    Format: {exp_name}-{YYYYMMDD}-{HHMMSS}-{random_hex}
    Example: exp1-20251209-143022-a1b2c3

    Args:
        experiment_name: Experiment name (exp1, exp2, exp3, or custom)

    Returns:
        Unique run ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    random_suffix = secrets.token_hex(3)  # 6 hex chars
    return f"{experiment_name}-{timestamp}-{random_suffix}"


def parse_run_id(run_id: str) -> ParsedRunId | None:
    """Parse a run ID into its components.

    Args:
        run_id: Run ID string to parse

    Returns:
        ParsedRunId with components, or None if invalid format
    """
    if not run_id:
        return None

    # Pattern: {experiment_name}-{YYYYMMDD}-{HHMMSS}-{hex6}
    # experiment_name can contain underscores
    pattern = r"^(.+)-(\d{8})-(\d{6})-([a-f0-9]{6})$"
    match = re.match(pattern, run_id)

    if not match:
        return None

    return ParsedRunId(
        experiment_name=match.group(1),
        date=match.group(2),
        time=match.group(3),
        random_suffix=match.group(4),
    )
