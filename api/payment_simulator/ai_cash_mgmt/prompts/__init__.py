"""Prompt building for LLM-based policy optimization.

This package provides context builders for creating rich prompts
that help LLMs generate better policy improvements.

Modules:
    context_types: Data structures for context building
    policy_diff: Policy diff computation utilities
    single_agent_context: Single-agent context builder
"""

from __future__ import annotations

from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentContext,
    SingleAgentIterationRecord,
)
from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
    compute_parameter_trajectory,
    compute_policy_diff,
)
from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
    SingleAgentContextBuilder,
    build_single_agent_context,
)

__all__ = [
    "SingleAgentContext",
    "SingleAgentContextBuilder",
    "SingleAgentIterationRecord",
    "build_single_agent_context",
    "compute_parameter_trajectory",
    "compute_policy_diff",
]
