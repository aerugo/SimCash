"""System prompt builder for LLM policy optimization.

This module provides functionality to build the complete system prompt
that provides the LLM with context for policy optimization. The prompt
includes domain explanation, cost structure, and filtered schemas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
from payment_simulator.ai_cash_mgmt.prompts.schema_injection import (
    get_filtered_cost_schema,
    get_filtered_policy_schema,
)


@dataclass
class SystemPromptConfig:
    """Configuration for system prompt generation."""

    constraints: ScenarioConstraints
    cost_rates: dict[str, Any] | None = None
    castro_mode: bool = False
    include_examples: bool = True


def build_system_prompt(
    constraints: ScenarioConstraints,
    cost_rates: dict[str, Any] | None = None,
    castro_mode: bool = False,
    include_examples: bool = True,
    customization: str | None = None,
) -> str:
    """Build the complete system prompt for policy optimization.

    Args:
        constraints: Scenario constraints for filtering schemas.
        cost_rates: Current cost rate values (optional).
        castro_mode: Whether to include Castro paper alignment.
        include_examples: Whether to include JSON examples.
        customization: Optional experiment-specific customization text.

    Returns:
        Complete system prompt string.
    """
    builder = SystemPromptBuilder(constraints)
    if cost_rates:
        builder.with_cost_rates(cost_rates)
    builder.with_examples(include_examples)
    if customization:
        builder.with_customization(customization)
    return builder.build()


class SystemPromptBuilder:
    """Builder for constructing system prompts.

    Allows step-by-step construction with method chaining.

    Example:
        >>> prompt = (
        ...     SystemPromptBuilder(constraints)
        ...     .with_cost_rates(rates)
        ...     .build()
        ... )
    """

    def __init__(self, constraints: ScenarioConstraints) -> None:
        """Initialize the builder with constraints.

        Args:
            constraints: Scenario constraints defining what's allowed.
        """
        self._constraints = constraints
        self._cost_rates: dict[str, Any] | None = None
        self._include_examples = True
        self._customization: str | None = None

    def with_cost_rates(self, rates: dict[str, Any]) -> SystemPromptBuilder:
        """Set cost rates to include in the prompt.

        Args:
            rates: Cost rate values.

        Returns:
            Self for method chaining.
        """
        self._cost_rates = rates
        return self

    def with_examples(self, enabled: bool = True) -> SystemPromptBuilder:
        """Enable or disable JSON examples in schemas.

        Args:
            enabled: Whether to include examples.

        Returns:
            Self for method chaining.
        """
        self._include_examples = enabled
        return self

    def with_customization(self, customization: str | None) -> SystemPromptBuilder:
        """Set experiment-specific customization text.

        The customization text is injected after the expert introduction
        and before the detailed domain explanation. This allows experiments
        to provide context-specific instructions to the LLM.

        Args:
            customization: Customization text to inject. None or blank
                          strings will not add any customization section.

        Returns:
            Self for method chaining.
        """
        self._customization = customization
        return self

    def build(self) -> str:
        """Build the complete system prompt.

        Returns:
            Complete system prompt string.
        """
        sections: list[str] = []

        # Section 1: Expert role introduction
        sections.append(_build_expert_introduction())

        # Section 2: Experiment customization (if provided)
        if self._customization and self._customization.strip():
            sections.append(_build_customization_section(self._customization))

        # Section 4: Domain explanation
        sections.append(_build_domain_explanation())

        # Section 5: Cost structure and objectives
        sections.append(_build_cost_objectives())

        # Section 6: Policy tree architecture
        sections.append(_build_policy_architecture())

        # Section 7: Optimization process explanation
        sections.append(_build_optimization_process())

        # Section 8: Pre-generation checklist
        sections.append(_build_checklist())

        # Section 9: Injected policy schema (filtered)
        sections.append(
            get_filtered_policy_schema(
                self._constraints,
                include_examples=self._include_examples,
            )
        )

        # Section 10: Injected cost schema
        sections.append(get_filtered_cost_schema(cost_rates=self._cost_rates))

        # Section 11: Common errors to avoid
        sections.append(_build_common_errors())

        # Section 12: Final instructions
        sections.append(_build_final_instructions())

        return "\n".join(sections)


# =============================================================================
# Private Section Builders
# =============================================================================


def _build_expert_introduction() -> str:
    """Build the expert role introduction."""
    return """You are an expert in payment system optimization.
Your job is to generate valid JSON policies for the SimCash payment simulator.

You are an optimization agent in a simulation of an interbank payment settlement
in a real-time gross settlement (RTGS) environment. Each agent represents a bank
with a settlement account at the central bank.
"""


def _build_customization_section(customization: str) -> str:
    """Build the experiment customization section.

    Args:
        customization: The customization text from experiment config.

    Returns:
        Formatted customization section.
    """
    return f"""
################################################################################
#                       EXPERIMENT CUSTOMIZATION                               #
################################################################################

{customization.strip()}

################################################################################
"""


def _build_castro_section() -> str:
    """Build the Castro paper alignment section."""
    return """
################################################################################
#                    CASTRO PAPER ALIGNMENT MODE                               #
#           (Replicating Castro et al. 2025 Payment System Game)               #
################################################################################

This experiment follows the rules from:
"Estimating Policy Functions in Payment Systems Using Reinforcement Learning"

CASTRO MODEL CONSTRAINTS:

1. INITIAL LIQUIDITY DECISION (t=0 ONLY):
   - Choose fraction x₀ ∈ [0,1] of collateral B at day start: ℓ₀ = x₀ · B
   - This is the ONLY collateral decision allowed
   - strategic_collateral_tree MUST guard PostCollateral with tick == 0

2. INTRADAY PAYMENT DECISIONS (t=1,...,T-1):
   - Each period, choose whether to release or hold payments
   - Release = send in full (x_t = 1)
   - Hold = delay to next period (x_t = 0)

3. COST STRUCTURE (r_c < r_d < r_b):
   - r_c: Collateral opportunity cost (initial liquidity)
   - r_d: Delay cost per tick (waiting payments)
   - r_b: End-of-day borrowing cost (shortfall)

4. LIQUIDITY EVOLUTION:
   - ℓ_t = ℓ_{t-1} - (outflows) + (inflows)
   - With deferred crediting: inflows available NEXT period only

REQUIRED strategic_collateral_tree STRUCTURE:
```json
{
  "type": "condition",
  "node_id": "SC1",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
  "on_true": {
    "type": "action",
    "node_id": "SC2",
    "action": "PostCollateral",
    "parameters": {"amount": {...}}
  },
  "on_false": {"type": "action", "node_id": "SC3", "action": "HoldCollateral"}
}
```

################################################################################
"""


def _build_domain_explanation() -> str:
    """Build the domain explanation section."""
    return """
## Domain Context: Interbank Payment Settlement

### Real-Time Gross Settlement (RTGS)
Payments arrive throughout the simulated trading day with specified amounts,
counterparties, deadlines, and priority levels. Settlement occurs immediately
when the sending bank has sufficient balance or available credit.

### Queuing Mechanism
When liquidity is insufficient, payments enter a queue:
- **Queue 1**: Immediate settlement attempts (holds payments briefly)
- **Queue 2**: Longer-term holding when liquidity is constrained

Queued payments accumulate delay costs until settled.

### Liquidity-Saving Mechanisms (LSM)
The system provides netting opportunities:
- **Bilateral Offsets**: Two banks with opposing payments can net them
- **Multilateral Cycles**: Multiple banks form a cycle where debts cancel out

LSM reduces liquidity requirements but depends on counterparty behavior.

### Key Concepts
- **Balance**: Current reserves in settlement account (integer cents)
- **Effective Liquidity**: Balance + credit limit - pending obligations
- **Credit Limit**: Available daylight overdraft or collateralized credit
- **Collateral**: Assets posted to central bank to secure credit
"""


def _build_cost_objectives() -> str:
    """Build the cost objectives section."""
    return """
## Cost Structure and Objectives

**Your objective is to minimize total cost.**

Costs include:
1. **Overdraft Charges**: Basis points on negative balance positions
2. **Delay Penalties**: Per-tick costs for each transaction waiting in queue
3. **Deadline Penalties**: One-time charge when a payment becomes overdue
4. **Overdue Multiplier**: Increased delay costs after deadline passes
5. **End-of-Day Penalties**: Severe charges for unsettled payments at close

### Why This is Non-Trivial
Actions have delayed consequences:
- Releasing liquidity early may reduce delay cost but increase overdraft exposure
- Holding payments preserves liquidity but risks deadline penalties
- Optimal behavior requires balancing immediate costs against future states

### Strategic Considerations
- High-priority payments have higher delay costs
- Payments close to deadline should often be released
- Incoming payments may provide liquidity to release queued payments
- End-of-day penalties are typically very high - avoid unsettled transactions
"""


def _build_policy_architecture() -> str:
    """Build the policy tree architecture explanation."""
    return """
## Policy Tree Architecture

Agent behavior is governed by a **policy tree**: a decision structure where:
- **Condition nodes**: Evaluate state conditions (comparisons, logical ops)
- **Action nodes**: Specify what to do (Release, Hold, PostCollateral, etc.)

### Tree Structure
```json
{
  "type": "condition",
  "node_id": "unique_id",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"param": "urgency_threshold"}
  },
  "on_true": {...},   // Subtree if condition is true
  "on_false": {...}   // Subtree if condition is false
}
```

### Tree Types
Different trees handle different decision types:
- **payment_tree**: Decides what to do with each transaction
- **bank_tree**: Bank-level decisions (once per tick)
- **strategic_collateral_tree**: Collateral management
- **end_of_tick_collateral_tree**: End-of-tick collateral adjustments

### Evaluation Flow
1. Bank tree evaluates first (sets context like release budgets)
2. Collateral trees manage liquidity positions
3. Payment tree evaluates for each pending transaction
"""


def _build_optimization_process() -> str:
    """Build the optimization process explanation."""
    return """
## Optimization Process

You will be provided with:
1. **Current policy tree**: The policy to improve
2. **Simulation output**: Tick-by-tick logs from recent runs
3. **Iteration history**: How the policy has evolved and cost changes

### Your Task
Analyze the provided data, identify inefficiencies or suboptimal decisions,
and propose modifications to the policy tree that reduce total costs.

Focus on:
- Decisions that led to deadline penalties or high delay costs
- Opportunities to release payments earlier with available liquidity
- Conditions that are too aggressive (causing overdrafts) or too conservative

### Output Requirements
Return a complete, valid JSON policy with:
- All tree types that are enabled in this scenario
- All parameters defined before they are referenced
- Unique node_id for every node
"""


def _build_checklist() -> str:
    """Build the pre-generation checklist."""
    return """
################################################################################
#                     MANDATORY PRE-GENERATION CHECKLIST                       #
################################################################################

BEFORE generating ANY policy, verify you will satisfy ALL of these:

  [ ] Every {"param": "X"} has a matching "X" key in the "parameters" object
  [ ] Every action matches its tree type (see allowed actions below)
  [ ] Every node has a unique "node_id" string
  [ ] Arithmetic expressions are wrapped in {"compute": {...}}
  [ ] Only use fields and parameters from the ALLOWED sections
  [ ] No undefined field references
  [ ] No mixing of action types between trees

################################################################################
"""


def _build_common_errors() -> str:
    """Build the common errors section."""
    return """
## Common Errors to Avoid

### ERROR 1: UNDEFINED PARAMETER
```json
// WRONG:
"parameters": {},
"condition": {"right": {"param": "threshold"}}

// FIX - Add "threshold" to parameters:
"parameters": {"threshold": 5.0},
"condition": {"right": {"param": "threshold"}}
```

### ERROR 2: WRONG ACTION FOR TREE
```json
// WRONG in strategic_collateral_tree:
{"action": "Hold"}      // Hold is PAYMENT-only!
{"action": "NoAction"}  // NoAction is BANK-only!

// FIX in strategic_collateral_tree:
{"action": "HoldCollateral"}  // Correct collateral action
```

### ERROR 3: RAW ARITHMETIC (Missing compute wrapper)
```json
// WRONG:
"right": {"op": "*", "left": {"value": 2}, "right": {"field": "X"}}

// FIX - Wrap in "compute":
"right": {"compute": {"op": "*", "left": {"value": 2}, "right": {"field": "X"}}}
```

### ERROR 4: MISSING NODE_ID
```json
// WRONG:
{"type": "action", "action": "Release"}

// FIX - Add unique node_id:
{"type": "action", "node_id": "A1_release", "action": "Release"}
```

### ERROR 5: INVALID FIELD REFERENCE
Only use fields listed in the ALLOWED FIELDS section.
Do not invent field names that don't exist in the simulation.
"""


def _build_final_instructions() -> str:
    """Build the final instructions section."""
    return """
################################################################################
#                         FINAL INSTRUCTIONS                                   #
################################################################################

1. Generate a COMPLETE policy JSON with all required trees
2. Ensure EVERY node has a unique node_id
3. Define ALL parameters before referencing them
4. Use ONLY allowed actions for each tree type
5. Wrap ALL arithmetic in {"compute": {...}}
6. Keep trees reasonably simple (3-5 levels max) for robustness
7. Focus improvements on areas identified in the simulation output

The policy MUST be syntactically valid JSON that passes validation.
"""
