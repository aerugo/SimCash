"""Visualization layer for castro experiments.

Provides chart generation for experiment analysis.

Main components:
- generate_cost_ribbon_chart: Cost over iterations ribbon plot
- generate_settlement_rate_chart: Settlement rate over iterations
- generate_per_agent_cost_chart: Per-agent cost breakdown
- generate_acceptance_chart: Accepted vs rejected iterations
- generate_all_charts: Generate all charts from database
"""

from experiments.castro.castro.visualization.charts import (
    generate_acceptance_chart,
    generate_all_charts,
    generate_cost_ribbon_chart,
    generate_per_agent_cost_chart,
    generate_settlement_rate_chart,
)

__all__ = [
    "generate_cost_ribbon_chart",
    "generate_settlement_rate_chart",
    "generate_per_agent_cost_chart",
    "generate_acceptance_chart",
    "generate_all_charts",
]
