"""Experiment analysis module.

Provides tools for analyzing experiment results, including:
- Policy diff calculation
- Policy evolution tracking
- Evolution service for data extraction
- Chart data extraction and rendering
"""

from payment_simulator.experiments.analysis.charting import (
    ChartData,
    ChartDataPoint,
    ExperimentChartService,
    render_convergence_chart,
)
from payment_simulator.experiments.analysis.evolution_model import (
    AgentEvolution,
    IterationEvolution,
    LLMInteractionData,
    build_evolution_output,
)
from payment_simulator.experiments.analysis.evolution_service import (
    PolicyEvolutionService,
)
from payment_simulator.experiments.analysis.policy_diff import (
    compute_policy_diff,
    extract_parameter_changes,
)

__all__ = [
    "AgentEvolution",
    "ChartData",
    "ChartDataPoint",
    "ExperimentChartService",
    "IterationEvolution",
    "LLMInteractionData",
    "PolicyEvolutionService",
    "build_evolution_output",
    "compute_policy_diff",
    "extract_parameter_changes",
    "render_convergence_chart",
]
