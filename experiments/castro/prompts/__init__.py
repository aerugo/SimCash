# Prompt templates and context builders for LLM policy generation

from experiments.castro.prompts.templates import (
    SYSTEM_PROMPT,
    PAYMENT_TREE_CONTEXT,
    BANK_TREE_CONTEXT,
    COLLATERAL_TREE_CONTEXT,
    get_tree_context,
)

from experiments.castro.prompts.context import (
    IterationRecord,
    SimulationContext,
    ExtendedContextBuilder,
    compute_policy_diff,
    compute_parameter_trajectory,
    build_extended_context,
)

from experiments.castro.prompts.builder import PolicyPromptBuilder

__all__ = [
    # Templates
    "SYSTEM_PROMPT",
    "PAYMENT_TREE_CONTEXT",
    "BANK_TREE_CONTEXT",
    "COLLATERAL_TREE_CONTEXT",
    "get_tree_context",
    # Context
    "IterationRecord",
    "SimulationContext",
    "ExtendedContextBuilder",
    "compute_policy_diff",
    "compute_parameter_trajectory",
    "build_extended_context",
    # Builder
    "PolicyPromptBuilder",
]
