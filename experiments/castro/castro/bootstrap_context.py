"""Bootstrap-native context builder for LLM prompts.

Re-exports from core payment_simulator.ai_cash_mgmt.bootstrap module.
Maintained for backward compatibility.

Example:
    >>> from castro.bootstrap_context import EnrichedBootstrapContextBuilder
    >>> builder = EnrichedBootstrapContextBuilder(enriched_results, "BANK_A")
    >>> context = builder.build_agent_context()
    >>> best_trace = builder.format_event_trace_for_llm(builder.get_best_result())
"""

from __future__ import annotations

# Re-export from core module
from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
    AgentSimulationContext,
    EnrichedBootstrapContextBuilder,
)

__all__ = [
    "AgentSimulationContext",
    "EnrichedBootstrapContextBuilder",
]
