"""Run ID generation for Castro experiments.

Re-exports from core payment_simulator.experiments module.
Maintained for backward compatibility.
"""

from __future__ import annotations

# Re-export from core module
from payment_simulator.experiments.run_id import (
    ParsedRunId,
    generate_run_id,
    parse_run_id,
)

__all__ = [
    "generate_run_id",
    "parse_run_id",
    "ParsedRunId",
]
