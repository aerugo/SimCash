"""Prompt templates for LLM policy generation.

These templates are used to instruct the LLM on how to generate
valid policy trees.
"""

from __future__ import annotations


# ============================================================================
# Standard System Prompt (Full SimCash Capabilities)
# ============================================================================

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


# ============================================================================
# Castro Paper Alignment - Specialized Prompts
# ============================================================================

CASTRO_SYSTEM_PROMPT = """You are an expert policy optimizer implementing the payment system game from:
"Estimating Policy Functions in Payment Systems Using Reinforcement Learning" (Castro et al., 2025)

## Castro Paper Model

This is a stylized RTGS (Real-Time Gross Settlement) payment system with:
- Two banks (A and B) making payments to each other
- Discrete time: day divided into T intraday periods (t = 0, 1, ..., T-1)
- Each bank must choose policies to minimize total payment processing cost

## Key Decisions

### 1. Initial Liquidity (t=0)
At the start of day, choose fraction x₀ ∈ [0,1] of collateral B to post:
  ℓ₀ = x₀ · B  (initial liquidity)

This is the ONLY collateral decision. No mid-day changes allowed.

### 2. Intraday Payment Release (t=1,...,T-1)
Each period, choose fraction x_t ∈ [0,1] of payment demands P_t to send:
- Release (x_t = 1): Send payment immediately
- Hold (x_t = 0): Delay payment to next period

Constraint: Can only send what liquidity covers: P_t · x_t ≤ ℓ_{t-1}

## Liquidity Evolution
ℓ_t = ℓ_{t-1} - (payments sent) + (payments received)

With deferred crediting: incoming payments available NEXT period only.

## Cost Structure (r_c < r_d < r_b)
- Initial liquidity cost: r_c · ℓ₀
- Delay cost per period: r_d · (value of held payments)
- End-of-day borrowing: r_b · (shortfall if ℓ < remaining payments)

## Policy Structure

### strategic_collateral_tree
MUST follow this pattern:
```json
{
  "type": "condition",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": 0},
  "on_true": {"type": "action", "action": "PostCollateral", "parameters": {"amount": ...}},
  "on_false": {"type": "action", "action": "HoldCollateral"}
}
```

### payment_tree
Use only Release and Hold actions based on:
- Urgency (ticks_to_deadline)
- Available liquidity (effective_liquidity >= remaining_amount)
- Strategic delay (if expecting incoming payments)

## Prohibited Actions
- Split, PaceAndRelease, StaggerSplit (Castro assumes divisible continuous payments)
- ReleaseWithCredit (no interbank credit in Castro model)
- WithdrawCollateral (no mid-day collateral reduction)
- Bank-level budgeting actions (no SetReleaseBudget, SetState)

Generate policies that minimize total cost by balancing:
1. Collateral opportunity cost (post less → save r_c)
2. Delay cost (hold payments → incur r_d)
3. End-of-day borrowing (fail to settle → incur r_b >> r_c, r_d)
"""


CASTRO_PAYMENT_TREE_CONTEXT = """## Payment Tree Context (Castro Mode)

In Castro's model, the payment decision is binary:
- **Release** (x_t = 1): Send the payment in full this period
- **Hold** (x_t = 0): Delay the payment to the next period

Key decision factors:
1. **Urgency**: How many ticks until deadline? (ticks_to_deadline)
2. **Liquidity**: Can we afford to send? (effective_liquidity >= remaining_amount)
3. **Strategic delay**: Can we wait for incoming payments? (counter-party might send)

Cost implications:
- Releasing uses liquidity now (may need more initial collateral tomorrow)
- Holding incurs delay cost r_d per tick
- Failing to settle by EOD incurs borrowing cost r_b >> r_d

Optimal behavior depends on the other bank's policy:
- If other bank sends early → you receive liquidity → can release more
- If other bank delays → less incoming → need more initial liquidity
"""


CASTRO_COLLATERAL_TREE_CONTEXT = """## Collateral Tree Context (Castro Mode)

CRITICAL CONSTRAINT: Collateral is ONLY set at t=0 (start of day).

The strategic_collateral_tree MUST:
1. Check if system_tick_in_day == 0
2. If true: PostCollateral with the initial liquidity amount
3. If false: HoldCollateral (no changes)

Required structure:
```json
{
  "type": "condition",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
  "on_true": {
    "type": "action",
    "action": "PostCollateral",
    "parameters": {
      "amount": {
        "compute": {
          "op": "*",
          "left": {"field": "max_collateral_capacity"},
          "right": {"param": "initial_liquidity_fraction"}
        }
      }
    }
  },
  "on_false": {"type": "action", "action": "HoldCollateral"}
}
```

The key parameter is initial_liquidity_fraction (x₀ ∈ [0,1]):
- Higher x₀ → more initial liquidity → less delay risk → higher collateral cost
- Lower x₀ → rely on incoming payments → risk of delay/borrowing costs

This is the core trade-off in Castro's initial liquidity game.
"""


CASTRO_TREE_CONTEXT_MAP = {
    "payment_tree": CASTRO_PAYMENT_TREE_CONTEXT,
    "bank_tree": "## Bank Tree Context (Castro Mode)\n\nNot used in Castro model. Use NoAction only.",
    "strategic_collateral_tree": CASTRO_COLLATERAL_TREE_CONTEXT,
    "end_of_tick_collateral_tree": (
        "## End-of-Tick Collateral (Castro Mode)\n\n"
        "Not used in Castro model. Use HoldCollateral only."
    ),
}


def get_castro_tree_context(tree_type: str) -> str:
    """Get Castro-specific context description for a tree type."""
    return CASTRO_TREE_CONTEXT_MAP.get(tree_type, "")


def get_system_prompt(castro_mode: bool = False) -> str:
    """Get the appropriate system prompt.

    Args:
        castro_mode: If True, use Castro paper alignment prompt

    Returns:
        The system prompt string
    """
    if castro_mode:
        return CASTRO_SYSTEM_PROMPT
    return SYSTEM_PROMPT
