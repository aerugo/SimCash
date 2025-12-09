"""Metrics computation for simulation results.

This package provides utilities for aggregating metrics from
multiple simulation runs for policy evaluation.
"""

from __future__ import annotations

from payment_simulator.ai_cash_mgmt.metrics.aggregation import (
    AggregatedMetrics,
    compute_metrics,
)

__all__ = [
    "AggregatedMetrics",
    "compute_metrics",
]
