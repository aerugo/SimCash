"""Prompt templates for LLM policy generation.

These templates are used to instruct the LLM on how to generate
valid policy trees.
"""

from __future__ import annotations


SYSTEM_PROMPT = """You are an expert policy optimizer for a payment settlement simulation.

Your task is to generate or improve policy decision trees that control how payments
are processed. The policies use a JSON-based DSL with the following structure:

## Policy Tree Structure

A policy tree is either:
1. An ACTION node: {"type": "action", "action": "<ActionType>", "parameters": {...}}
2. A CONDITION node: {"type": "condition", "condition": <expression>, "on_true": <tree>, "on_false": <tree>}

## Expressions

Conditions use comparison expressions:
- Comparisons: {"op": "<op>", "left": <value>, "right": <value>}
  - Operators: ==, !=, <, <=, >, >=
- Logical: {"op": "and", "conditions": [<expr>, ...]}
          {"op": "or", "conditions": [<expr>, ...]}
          {"op": "not", "condition": <expr>}

## Values

Values can be:
- Context fields: {"field": "<field_name>"} - Runtime values from simulation state
- Literals: {"value": <number_or_string>} - Constant values
- Parameters: {"param": "<param_name>"} - References to policy parameters
- Computed: {"compute": {"op": "<op>", "left": <val>, "right": <val>}}
  - Operations: +, -, *, /, max, min, ceil, floor, abs

## Guidelines

1. Keep policies simple but effective - avoid unnecessary nesting
2. Use meaningful conditions that address the optimization goal
3. Prioritize urgent transactions (low ticks_to_deadline)
4. Balance liquidity usage with settlement throughput
5. Return valid JSON that matches the schema exactly

Generate a policy tree that optimizes for the given performance metrics.
"""


PAYMENT_TREE_CONTEXT = """## Payment Tree Context

The payment_tree evaluates each pending outgoing transaction to decide whether to:
- Release: Submit the payment to RTGS for settlement
- Hold: Keep the payment in queue for later
- Split: Divide the payment into smaller parts
- Other actions as available

Key considerations:
- Balance available liquidity vs. payment amount
- Transaction urgency (ticks to deadline)
- Overall cost optimization (delay costs, overdraft costs)
"""


BANK_TREE_CONTEXT = """## Bank Tree Context

The bank_tree runs once per tick before payment processing to set bank-level parameters:
- SetReleaseBudget: Limit total value of releases this tick
- SetState/AddState: Track counters and state across ticks
- NoAction: Take no bank-level action

Key considerations:
- Current liquidity position
- Queue pressure
- Intraday patterns
"""


COLLATERAL_TREE_CONTEXT = """## Collateral Tree Context

The collateral trees decide how to manage collateral:
- strategic_collateral_tree: Runs at start of tick, proactive collateral management
- end_of_tick_collateral_tree: Runs after settlement, reactive adjustment

Actions:
- PostCollateral: Increase liquidity by posting collateral
- WithdrawCollateral: Reduce collateral exposure
- HoldCollateral: No change

Key considerations:
- Queue liquidity gap
- Collateral opportunity cost vs. settlement benefits
"""


TREE_CONTEXT_MAP = {
    "payment_tree": PAYMENT_TREE_CONTEXT,
    "bank_tree": BANK_TREE_CONTEXT,
    "strategic_collateral_tree": COLLATERAL_TREE_CONTEXT,
    "end_of_tick_collateral_tree": COLLATERAL_TREE_CONTEXT,
}


def get_tree_context(tree_type: str) -> str:
    """Get the context description for a tree type."""
    return TREE_CONTEXT_MAP.get(tree_type, "")
