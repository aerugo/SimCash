"""Robust Policy Agent using dynamic constrained schemas.

This module provides a RobustPolicyAgent that uses PydanticAI structured output
with dynamically generated Pydantic models based on ScenarioConstraints.

The agent supports ANY parameters, fields, and actions that SimCash allows,
configured per-scenario via ScenarioConstraints.

Usage:
    from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
    from experiments.castro.schemas.parameter_config import (
        ParameterSpec,
        ScenarioConstraints,
    )

    constraints = ScenarioConstraints(
        allowed_parameters=[
            ParameterSpec("urgency", 0, 20, 3, "Urgency threshold"),
            ParameterSpec("buffer", 0.5, 3.0, 1.0, "Liquidity buffer"),
        ],
        allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity"],
        allowed_actions=["Release", "Hold", "Split"],
    )

    agent = RobustPolicyAgent(constraints=constraints)
    policy = agent.generate_policy(
        instruction="Optimize for low delay costs",
        current_cost=50000,
        settlement_rate=0.85,
    )
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from experiments.castro.schemas.dynamic import create_constrained_policy_model
from experiments.castro.schemas.parameter_config import ScenarioConstraints

if TYPE_CHECKING:
    from experiments.castro.prompts.context import IterationRecord


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_MODEL = "gpt-4o"
DEFAULT_REASONING_EFFORT: Literal["low", "medium", "high"] = "high"
DEFAULT_REASONING_SUMMARY: Literal["concise", "detailed"] = "detailed"

# Extended thinking configuration
MIN_THINKING_BUDGET = 1024  # Anthropic minimum
MAX_THINKING_BUDGET = 128000  # Reasonable upper limit

# Retry configuration for transient API errors (TLS, 503, etc.)
MAX_RETRIES = 5
INITIAL_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 60.0
BACKOFF_MULTIPLIER = 2.0


# ============================================================================
# Dependencies
# ============================================================================


@dataclass
class RobustPolicyDeps:
    """Dependencies for robust policy generation.

    Extended to support rich historical context for improved optimization.
    """

    # Current state
    current_policy: dict[str, Any] | None = None
    current_cost: float | None = None
    settlement_rate: float | None = None
    per_bank_costs: dict[str, float] | None = None
    iteration: int = 0

    # Extended context for improved optimization
    iteration_history: list[IterationRecord] = field(default_factory=list)
    best_seed_output: str | None = None
    worst_seed_output: str | None = None
    best_seed: int = 0
    worst_seed: int = 0
    best_seed_cost: int = 0
    worst_seed_cost: int = 0
    cost_breakdown: dict[str, int] = field(default_factory=dict)
    cost_rates: dict[str, Any] = field(default_factory=dict)

    # Agent identifier for isolated optimization
    # CRITICAL: Each agent only sees its own data - no cross-agent information leakage
    agent_id: str | None = None


# ============================================================================
# System Prompt Generation
# ============================================================================


def generate_system_prompt(constraints: ScenarioConstraints) -> str:
    """Generate an improved system prompt with few-shot examples.

    The prompt includes:
    - Critical rules for valid policy generation
    - Complete validated example with all tree types
    - Explicit action-to-tree mapping table
    - Pre-generation checklist
    - Structured vocabulary of allowed elements
    """
    # Build parameter vocabulary with defaults
    param_vocab = []
    param_defaults = {}
    if constraints.allowed_parameters:
        for spec in constraints.allowed_parameters:
            param_vocab.append(
                f"    {spec.name}: {spec.description} "
                f"[range: {spec.min_value}-{spec.max_value}, default: {spec.default}]"
            )
            param_defaults[spec.name] = spec.default

    param_list = (
        "\n".join(param_vocab) if param_vocab else "    (No parameters defined)"
    )

    # Build field vocabulary organized by category
    field_list = "\n".join([f"    {f}" for f in constraints.allowed_fields])

    # Build action vocabulary by tree type
    payment_action_list = "\n".join([f"      {a}" for a in constraints.allowed_actions])

    # Build bank and collateral action lists
    bank_actions = constraints.allowed_bank_actions or []
    collateral_actions = constraints.allowed_collateral_actions or []

    bank_action_list = (
        "\n".join([f"      {a}" for a in bank_actions])
        if bank_actions
        else "      (Not enabled)"
    )
    collateral_action_list = (
        "\n".join([f"      {a}" for a in collateral_actions])
        if collateral_actions
        else "      (Not enabled)"
    )

    # Generate parameter defaults JSON for the example
    if param_defaults:
        defaults_json = ",\n    ".join(
            [f'"{k}": {v}' for k, v in param_defaults.items()]
        )
        param_defaults_example = f"{{\n    {defaults_json}\n  }}"
    else:
        param_defaults_example = "{}"

    # Determine which trees are enabled
    has_bank_tree = bool(bank_actions)
    has_collateral_trees = bool(collateral_actions)

    # Build tree enablement info
    tree_info = []
    tree_info.append("    payment_tree: ALWAYS REQUIRED")
    if has_bank_tree:
        tree_info.append("    bank_tree: OPTIONAL (enabled in this scenario)")
    if has_collateral_trees:
        tree_info.append(
            "    strategic_collateral_tree: OPTIONAL (enabled in this scenario)"
        )
        tree_info.append(
            "    end_of_tick_collateral_tree: OPTIONAL (enabled in this scenario)"
        )
    tree_enablement = "\n".join(tree_info)

    return f"""You are an expert policy generator for SimCash, a payment settlement simulation.

################################################################################
#                     MANDATORY PRE-GENERATION CHECKLIST                       #
################################################################################
BEFORE generating ANY policy, verify you will satisfy ALL of these:

  [ ] Every {{"param": "X"}} has a matching "X" key in the "parameters" object
  [ ] Every action matches its tree type (see ACTION VALIDITY TABLE below)
  [ ] Every node has a unique "node_id" string
  [ ] Arithmetic expressions are wrapped in {{"compute": {{...}}}}
  [ ] Only use fields and parameters from the ALLOWED VOCABULARY section

################################################################################
#                        ACTION VALIDITY TABLE                                 #
#                   (VIOLATIONS = IMMEDIATE FAILURE)                           #
################################################################################

  +----------------------------------+----------------------------------------+
  | Tree Type                        | ONLY VALID Actions                     |
  +----------------------------------+----------------------------------------+
  | payment_tree                     | Release, Hold, Split, Drop,            |
  |                                  | Reprioritize, ReleaseWithCredit,       |
  |                                  | PaceAndRelease, StaggerSplit,          |
  |                                  | WithdrawFromRtgs, ResubmitToRtgs       |
  +----------------------------------+----------------------------------------+
  | bank_tree                        | SetReleaseBudget, SetState,            |
  |                                  | AddState, NoAction                     |
  +----------------------------------+----------------------------------------+
  | strategic_collateral_tree        | PostCollateral, WithdrawCollateral,    |
  | end_of_tick_collateral_tree      | HoldCollateral                         |
  +----------------------------------+----------------------------------------+

  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
  !! CRITICAL: "Hold" != "HoldCollateral" - they are DIFFERENT actions!       !!
  !! CRITICAL: "NoAction" is ONLY valid in bank_tree, NOT collateral trees!   !!
  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

################################################################################
#                         ALLOWED VOCABULARY                                   #
################################################################################

ENABLED TREE TYPES (for this scenario):
{tree_enablement}

ALLOWED PARAMETERS (define in "parameters", reference with {{"param": "name"}}):
{param_list}

ALLOWED FIELDS (reference with {{"field": "name"}}):
{field_list}

ALLOWED ACTIONS BY TREE:
  payment_tree:
{payment_action_list}

  bank_tree:
{bank_action_list}

  collateral trees (strategic_collateral_tree, end_of_tick_collateral_tree):
{collateral_action_list}

################################################################################
#                    VALIDATED COMPLETE EXAMPLE                                #
#           (This policy passes SimCash validation - use as template)          #
################################################################################

```json
{{
  "version": "2.0",
  "policy_id": "complete_validated_example",
  "description": "A complete policy showing all tree types with correct actions",
  "parameters": {{
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.0,
    "initial_collateral_fraction": 0.25,
    "budget_fraction": 0.5
  }},
  "bank_tree": {{
    "type": "condition",
    "node_id": "BT1_check_day_progress",
    "description": "Set release budget based on time of day",
    "condition": {{
      "op": ">=",
      "left": {{"field": "day_progress_fraction"}},
      "right": {{"value": 0.8}}
    }},
    "on_true": {{
      "type": "action",
      "node_id": "BT2_eod_budget",
      "description": "End of day - larger budget to clear queues",
      "action": "SetReleaseBudget",
      "parameters": {{
        "max_value_to_release": {{
          "compute": {{
            "op": "*",
            "left": {{"field": "effective_liquidity"}},
            "right": {{"value": 0.7}}
          }}
        }}
      }}
    }},
    "on_false": {{
      "type": "action",
      "node_id": "BT3_normal_budget",
      "description": "Normal budget during the day",
      "action": "SetReleaseBudget",
      "parameters": {{
        "max_value_to_release": {{
          "compute": {{
            "op": "*",
            "left": {{"field": "effective_liquidity"}},
            "right": {{"param": "budget_fraction"}}
          }}
        }}
      }}
    }}
  }},
  "strategic_collateral_tree": {{
    "type": "condition",
    "node_id": "SC1_tick_zero",
    "description": "Post initial collateral at start of day",
    "condition": {{
      "op": "==",
      "left": {{"field": "system_tick_in_day"}},
      "right": {{"value": 0.0}}
    }},
    "on_true": {{
      "type": "action",
      "node_id": "SC2_post_initial",
      "action": "PostCollateral",
      "parameters": {{
        "amount": {{
          "compute": {{
            "op": "*",
            "left": {{"field": "max_collateral_capacity"}},
            "right": {{"param": "initial_collateral_fraction"}}
          }}
        }},
        "reason": {{"value": "InitialAllocation"}}
      }}
    }},
    "on_false": {{
      "type": "action",
      "node_id": "SC3_hold",
      "action": "HoldCollateral"
    }}
  }},
  "payment_tree": {{
    "type": "condition",
    "node_id": "P1_check_urgent",
    "description": "Release if close to deadline",
    "condition": {{
      "op": "<=",
      "left": {{"field": "ticks_to_deadline"}},
      "right": {{"param": "urgency_threshold"}}
    }},
    "on_true": {{
      "type": "action",
      "node_id": "P2_release_urgent",
      "action": "Release"
    }},
    "on_false": {{
      "type": "condition",
      "node_id": "P3_check_liquidity",
      "description": "Release if sufficient liquidity",
      "condition": {{
        "op": ">=",
        "left": {{"field": "effective_liquidity"}},
        "right": {{
          "compute": {{
            "op": "*",
            "left": {{"field": "remaining_amount"}},
            "right": {{"param": "liquidity_buffer"}}
          }}
        }}
      }},
      "on_true": {{
        "type": "action",
        "node_id": "P4_release_liquid",
        "action": "Release"
      }},
      "on_false": {{
        "type": "action",
        "node_id": "P5_hold",
        "action": "Hold"
      }}
    }}
  }}
}}
```

KEY OBSERVATIONS FROM THE VALIDATED EXAMPLE:
  1. ALL parameters are DEFINED in "parameters" BEFORE any {{"param": "X"}} reference
  2. bank_tree uses SetReleaseBudget with REQUIRED "max_value_to_release" parameter!
  3. strategic_collateral_tree uses HoldCollateral (NOT Hold or NoAction!)
  4. payment_tree uses Hold (NOT HoldCollateral!)
  5. Each node has a UNIQUE node_id (BT1, BT2, BT3, SC1, SC2, SC3, P1, P2, P3, P4, P5)
  6. Arithmetic uses {{"compute": {{...}}}} wrapper

CRITICAL FOR bank_tree:
  - SetReleaseBudget action REQUIRES the "max_value_to_release" parameter
  - The "max_value_to_release" controls how much total value the bank can release this tick
  - This is NOT optional - missing it causes validation failure!

################################################################################
#                         VALUE TYPES REFERENCE                                #
################################################################################

Four ways to specify values:

1. LITERAL (constant number):
   {{"value": 5.0}}
   {{"value": 0}}
   {{"value": true}}   // Becomes 1.0
   {{"value": false}}  // Becomes 0.0

2. FIELD REFERENCE (simulation state):
   {{"field": "balance"}}
   {{"field": "ticks_to_deadline"}}
   {{"field": "effective_liquidity"}}

3. PARAMETER REFERENCE (policy constant):
   {{"param": "urgency_threshold"}}
   // REQUIRES: "urgency_threshold" defined in "parameters" object!

4. COMPUTATION (arithmetic):
   {{"compute": {{"op": "+", "left": {{"field": "balance"}}, "right": {{"value": 1000}}}}}}
   {{"compute": {{"op": "*", "left": {{"param": "factor"}}, "right": {{"field": "amount"}}}}}}
   {{"compute": {{"op": "max", "values": [{{"field": "X"}}, {{"value": 0}}]}}}}

   AVAILABLE OPERATORS: +, -, *, /, max, min, ceil, floor, abs, round, clamp, div0

################################################################################
#                      COMMON ERRORS TO AVOID                                  #
################################################################################

ERROR 1: UNDEFINED PARAMETER (causes TYPE_ERROR)
  ✗ WRONG:
    "parameters": {{}},
    "condition": {{"right": {{"param": "threshold"}}}}

  ✓ FIX: Add "threshold" to parameters:
    "parameters": {{"threshold": 5.0}},
    "condition": {{"right": {{"param": "threshold"}}}}

ERROR 2: WRONG ACTION FOR TREE (causes INVALID_ACTION)
  ✗ WRONG in strategic_collateral_tree:
    {{"action": "Hold"}}      // Hold is PAYMENT-only!
    {{"action": "NoAction"}}  // NoAction is BANK-only!

  ✓ FIX in strategic_collateral_tree:
    {{"action": "HoldCollateral"}}  // Correct collateral action

ERROR 3: RAW ARITHMETIC (causes parse error)
  ✗ WRONG:
    "right": {{"op": "*", "left": {{"value": 2}}, "right": {{"field": "X"}}}}

  ✓ FIX: Wrap in "compute":
    "right": {{"compute": {{"op": "*", "left": {{"value": 2}}, "right": {{"field": "X"}}}}}}

ERROR 4: MISSING NODE_ID (causes MISSING_FIELD)
  ✗ WRONG:
    {{"type": "action", "action": "Release"}}

  ✓ FIX: Add unique node_id:
    {{"type": "action", "node_id": "A1_release", "action": "Release"}}

################################################################################
#                         OPTIMIZATION STRATEGY                                #
################################################################################

COST COMPONENTS (minimize total):
  - Delay Cost: Each tick payment waits in queue accrues cost
  - Overdraft Cost: Negative balance charges interest
  - Deadline Penalty: Large one-time penalty when deadline missed
  - End-of-Day Penalty: Very large penalty for unsettled transactions at EOD

EFFECTIVE STRATEGIES:
  1. Release urgent payments (low ticks_to_deadline) to avoid deadline penalties
  2. Check effective_liquidity >= remaining_amount before releasing
  3. Hold low-priority payments when liquidity is tight
  4. Post collateral proactively if queue1_liquidity_gap > 0

RECOMMENDED STARTING PARAMETERS:
{param_defaults_example}

Keep trees simple (2-4 levels) for robustness.
"""


# ============================================================================
# Robust Policy Agent
# ============================================================================


class RobustPolicyAgent:
    """Policy generator using dynamic constrained schemas.

    This agent uses PydanticAI structured output with dynamically generated
    Pydantic models based on ScenarioConstraints. This ensures:

    - Only allowed parameters can be used (with enforced bounds)
    - Only allowed context fields can be referenced
    - Only allowed actions can be used
    - Correct policy structure is enforced

    Example:
        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec("urgency", 0, 20, 3, "Urgency"),
            ],
            allowed_fields=["balance", "ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        agent = RobustPolicyAgent(constraints=constraints)
        policy = agent.generate_policy("Minimize delay costs")

        # Using Google Gemini (set GOOGLE_AI_STUDIO_API_KEY env var):
        agent = RobustPolicyAgent(
            constraints=constraints,
            model="google-gla:gemini-2.0-flash",
        )
    """

    def __init__(
        self,
        constraints: ScenarioConstraints,
        model: str | None = None,
        retries: int = 3,
        reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
        reasoning_summary: Literal["concise", "detailed"] = DEFAULT_REASONING_SUMMARY,
        api_key: str | None = None,
        thinking_budget: int | None = None,
        verbose: bool = False,
    ) -> None:
        """Initialize robust policy agent.

        Args:
            constraints: Scenario constraints defining allowed elements
            model: PydanticAI model string. Defaults to GPT-4o.
                   Supported formats:
                   - "gpt-4o" or "openai:gpt-4o" for OpenAI
                   - "anthropic:claude-3-5-sonnet-20241022" for Anthropic
                   - "google-gla:gemini-2.0-flash" for Google Gemini
            retries: Number of retries on validation failure
            reasoning_effort: Reasoning effort for GPT models
            reasoning_summary: Reasoning summary verbosity
            api_key: Optional API key (used for Google Gemini models).
                     If not provided for Google models, reads from
                     GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY env vars.
            thinking_budget: Token budget for Anthropic extended thinking mode.
                           When set, enables Claude's extended thinking with this
                           many tokens for internal reasoning. Minimum 1024.
                           Only applies to anthropic: models.
            verbose: Enable verbose error logging for debugging API issues.
        """
        self.constraints = constraints
        self.model = model or DEFAULT_MODEL
        self.retries = retries
        self.reasoning_effort = reasoning_effort
        self.reasoning_summary = reasoning_summary
        self._api_key = api_key
        self.verbose = verbose

        # Validate and store thinking budget
        self.thinking_budget: int | None = None
        if thinking_budget is not None:
            if thinking_budget < MIN_THINKING_BUDGET:
                raise ValueError(
                    f"thinking_budget must be at least {MIN_THINKING_BUDGET}, "
                    f"got {thinking_budget}"
                )
            if thinking_budget > MAX_THINKING_BUDGET:
                raise ValueError(
                    f"thinking_budget must be at most {MAX_THINKING_BUDGET}, "
                    f"got {thinking_budget}"
                )
            self.thinking_budget = thinking_budget

        # For Google models, resolve API key from environment if not provided
        if self.model.startswith("google-gla:") and not self._api_key:
            import os

            self._api_key = os.environ.get(
                "GOOGLE_AI_STUDIO_API_KEY"
            ) or os.environ.get("GEMINI_API_KEY")

        # Generate dynamic policy model from constraints
        self.policy_model = create_constrained_policy_model(constraints)

        # Generate system prompt from constraints
        self._system_prompt = generate_system_prompt(constraints)

        # Lazy-initialized PydanticAI agent
        self._agent: Any | None = None

    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        return self._system_prompt

    def _is_anthropic_thinking_mode(self) -> bool:
        """Check if we're using Anthropic model with thinking enabled."""
        return self.model.startswith("anthropic:") and self.thinking_budget is not None

    def _get_model(self) -> Any:
        """Create the appropriate model instance for PydanticAI.

        For Google models, creates a GoogleModel with explicit API key configuration.
        For other models, returns the model string for automatic provider detection.
        """
        model_name = self.model

        # Handle Google models with explicit API key
        if model_name.startswith("google-gla:") and self._api_key:
            try:
                from pydantic_ai.models.google import GoogleModel
                from pydantic_ai.providers.google import GoogleProvider
            except ImportError:
                raise ImportError(
                    "pydantic-ai[google] required. Install with: "
                    "pip install 'pydantic-ai[google]'"
                )

            # Extract the model name after 'google-gla:'
            gemini_model = model_name.split(":", 1)[1]
            provider = GoogleProvider(api_key=self._api_key)
            return GoogleModel(gemini_model, provider=provider)

        # Ensure model has openai: prefix for proper routing (legacy behavior)
        if not model_name.startswith("openai:") and ":" not in model_name:
            model_name = f"openai:{model_name}"

        return model_name

    def _get_anthropic_thinking_model_settings(self) -> Any:
        """Create AnthropicModelSettings with extended thinking enabled."""
        try:
            from pydantic_ai.models.anthropic import AnthropicModelSettings
        except ImportError:
            raise ImportError(
                "pydantic-ai[anthropic] required for thinking mode. "
                "Install with: pip install 'pydantic-ai[anthropic]'"
            )

        # max_tokens must be greater than budget_tokens for extended thinking
        # Default to 50000 to allow ample room for both thinking and response
        return AnthropicModelSettings(
            anthropic_thinking={
                "type": "enabled",
                "budget_tokens": self.thinking_budget,
            },
            max_tokens=50000,
        )

    def _get_agent(self) -> Any:
        """Get or create the PydanticAI agent.

        Uses PydanticAI's automatic model detection - it handles GPT-5.x/o1/o3
        models correctly when using the 'openai:model-name' format.
        For Google models, uses explicit GoogleProvider with API key.
        For Anthropic models with thinking_budget, creates an agent without
        structured output (since thinking + structured output conflict).
        """
        if self._agent is None:
            try:
                from pydantic_ai import Agent

                model = self._get_model()

                # Anthropic with thinking mode: disable structured output
                # because PydanticAI thinking doesn't work with output_type
                if self._is_anthropic_thinking_mode():
                    model_settings = self._get_anthropic_thinking_model_settings()
                    self._agent = Agent(
                        model,
                        output_type=str,  # Raw string output, parse JSON manually
                        system_prompt=self._system_prompt,
                        deps_type=RobustPolicyDeps,
                        retries=self.retries,
                        model_settings=model_settings,
                    )
                else:
                    # Standard mode: use structured output
                    self._agent = Agent(
                        model,
                        output_type=self.policy_model,
                        system_prompt=self._system_prompt,
                        deps_type=RobustPolicyDeps,
                        retries=self.retries,
                    )
            except ImportError as e:
                raise ImportError(
                    "PydanticAI is required for RobustPolicyAgent. "
                    "Install with: pip install pydantic-ai"
                ) from e

        return self._agent

    async def _run_with_streaming(
        self,
        agent: Any,
        prompt: str,
        deps: RobustPolicyDeps,
    ) -> str:
        """Run agent with streaming for Anthropic extended thinking.

        Anthropic requires streaming when max_tokens > 21,333.
        Since we use max_tokens=50000 for extended thinking, streaming is mandatory.

        This method uses PydanticAI's run_stream() to handle the streaming request,
        and collects the full response text.

        Args:
            agent: The PydanticAI Agent instance
            prompt: The user prompt
            deps: Dependencies for the agent

        Returns:
            The complete response text
        """
        response_text = ""
        async with agent.run_stream(prompt, deps=deps) as stream:
            async for chunk in stream.stream_text(delta=True):
                response_text += chunk
        return response_text

    def _parse_json_from_thinking_response(self, text: str) -> dict[str, Any]:
        """Parse JSON policy from raw text response (for thinking mode).

        When using extended thinking, the model returns raw text instead of
        structured output. This method extracts and parses the JSON policy
        from the response, handling various formats:
        - JSON wrapped in ```json ... ``` code blocks
        - Raw JSON objects
        - JSON with surrounding explanation text

        Args:
            text: Raw text response from the model

        Returns:
            Parsed policy dictionary

        Raises:
            ValueError: If no valid JSON can be extracted
        """
        import json
        import re

        # Try to find JSON in code blocks first
        code_block_patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]

        for pattern in code_block_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    parsed = json.loads(match.strip())
                    if isinstance(parsed, dict) and "version" in parsed:
                        return parsed
                except json.JSONDecodeError:
                    continue

        # Try to find a JSON object directly (look for { ... } pattern)
        # Find the outermost braces
        brace_start = text.find("{")
        if brace_start != -1:
            # Find matching closing brace
            depth = 0
            for i, char in enumerate(text[brace_start:], start=brace_start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        potential_json = text[brace_start : i + 1]
                        try:
                            parsed = json.loads(potential_json)
                            if isinstance(parsed, dict):
                                return parsed
                        except json.JSONDecodeError:
                            pass
                        break

        # Last resort: try parsing the entire text as JSON
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        raise ValueError(
            f"Could not extract valid JSON policy from response. "
            f"Response preview: {text[:500]}..."
        )

    def _validate_parsed_policy(self, policy: dict[str, Any]) -> dict[str, Any]:
        """Validate a parsed policy against the constrained model.

        Args:
            policy: Parsed policy dictionary

        Returns:
            Validated and normalized policy dictionary

        Raises:
            ValueError: If policy fails validation
        """
        try:
            # Validate against the dynamic Pydantic model
            validated = self.policy_model.model_validate(policy)
            return validated.model_dump(exclude_none=True)
        except Exception as e:
            raise ValueError(f"Policy validation failed: {e}") from e

    def generate_policy(
        self,
        instruction: str = "Generate an optimal policy",
        current_policy: dict[str, Any] | None = None,
        current_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
        iteration: int = 0,
        # Extended context parameters
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Generate a constrained policy with rich historical context.

        CRITICAL ISOLATION: This method generates policy for a SINGLE agent.
        The iteration_history must be pre-filtered to only contain this agent's
        data. No cross-agent information should be passed to the LLM.

        Args:
            instruction: Natural language instruction for policy
            current_policy: Current policy to improve (optional)
            current_cost: Current total cost for context (optional)
            settlement_rate: Current settlement rate for context (optional)
            per_bank_costs: Per-bank costs for context (optional)
            iteration: Current optimization iteration (optional)
            iteration_history: List of IterationRecord from previous iterations
                              MUST be filtered for this agent only
            best_seed_output: Full tick-by-tick verbose output from best seed
                             MUST be filtered for this agent only
            worst_seed_output: Full tick-by-tick verbose output from worst seed
                              MUST be filtered for this agent only
            best_seed: Best performing seed number
            worst_seed: Worst performing seed number
            best_seed_cost: Cost from best seed
            worst_seed_cost: Cost from worst seed
            cost_breakdown: Breakdown of costs by type (delay, collateral, etc.)
            cost_rates: Cost rate configuration from simulation
            agent_id: Identifier of the agent being optimized (e.g., "BANK_A")

        Returns:
            Generated policy as dict (fully validated)
        """
        # Determine if we should use extended context
        has_extended_context = (
            iteration_history is not None
            or best_seed_output is not None
            or worst_seed_output is not None
        )

        if has_extended_context:
            # Build massive extended context prompt for SINGLE AGENT
            # CRITICAL: Only this agent's data is passed - no cross-agent leakage
            prompt = self._build_extended_prompt(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
                iteration_history=iteration_history,
                best_seed_output=best_seed_output,
                worst_seed_output=worst_seed_output,
                best_seed=best_seed,
                worst_seed=worst_seed,
                best_seed_cost=best_seed_cost,
                worst_seed_cost=worst_seed_cost,
                cost_breakdown=cost_breakdown,
                cost_rates=cost_rates,
                agent_id=agent_id,
            )
        else:
            # Legacy: Build simple context-aware prompt
            prompt = self._build_simple_prompt(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                per_bank_costs=per_bank_costs,
                iteration=iteration,
            )

        # Use PydanticAI agent for all models
        agent = self._get_agent()

        deps = RobustPolicyDeps(
            current_policy=current_policy,
            current_cost=current_cost,
            settlement_rate=settlement_rate,
            per_bank_costs=per_bank_costs,
            iteration=iteration,
            iteration_history=iteration_history or [],
            best_seed_output=best_seed_output,
            worst_seed_output=worst_seed_output,
            best_seed=best_seed,
            worst_seed=worst_seed,
            best_seed_cost=best_seed_cost,
            worst_seed_cost=worst_seed_cost,
            cost_breakdown=cost_breakdown or {},
            cost_rates=cost_rates or {},
            agent_id=agent_id,
        )

        # Retry with exponential backoff for transient API errors
        last_exception: Exception | None = None
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                # For Anthropic extended thinking, we MUST use streaming
                # because max_tokens > 21,333 requires streaming per Anthropic API
                if self._is_anthropic_thinking_mode():
                    result = asyncio.run(self._run_with_streaming(agent, prompt, deps))
                    raw_text = str(result)
                    parsed_policy = self._parse_json_from_thinking_response(raw_text)
                    return self._validate_parsed_policy(parsed_policy)

                # Standard mode: use synchronous call
                result = agent.run_sync(prompt, deps=deps)

                # Standard mode: convert Pydantic model to dict
                if hasattr(result.output, "model_dump"):
                    return result.output.model_dump(exclude_none=True)
                return dict(result.output)

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Log full error details in verbose mode
                if self.verbose:
                    print(f"\n  [VERBOSE] API Error Details:")
                    print(f"    Model: {self.model}")
                    print(f"    Prompt length: {len(prompt):,} chars")
                    print(
                        f"    System prompt length: {len(self._system_prompt):,} chars"
                    )
                    print(f"    Thinking budget: {self.thinking_budget}")
                    print(f"    Full error:\n{e}")
                    # Try to extract more details from the exception
                    if hasattr(e, "__cause__") and e.__cause__:
                        print(f"    Cause: {e.__cause__}")
                    if hasattr(e, "response"):
                        print(f"    Response: {getattr(e, 'response', 'N/A')}")
                    if hasattr(e, "body"):
                        print(f"    Body: {getattr(e, 'body', 'N/A')}")
                    print()

                # Check if this is a transient error worth retrying
                # Note: 400 errors are NOT transient - they indicate bad request
                is_transient = any(
                    indicator in error_str
                    for indicator in [
                        "503",
                        "502",
                        "500",
                        "tls",
                        "ssl",
                        "certificate",
                        "connection",
                        "timeout",
                        "reset",
                        "upstream",
                        "temporarily unavailable",
                        "service unavailable",
                        "bad gateway",
                        "internal server error",
                    ]
                )

                # Explicitly check for 400 errors - these are NOT transient
                if "status_code: 400" in error_str or "400 bad request" in error_str:
                    is_transient = False
                    if self.verbose:
                        print(
                            f"  [VERBOSE] 400 error detected - NOT retrying (bad request)"
                        )

                if not is_transient:
                    # Non-transient error, don't retry
                    raise

                # Transient error - retry with backoff
                if attempt < MAX_RETRIES - 1:
                    print(
                        f"  [Retry {attempt + 1}/{MAX_RETRIES}] "
                        f"Transient API error, waiting {backoff:.1f}s: {str(e)[:100]}"
                    )
                    time.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

        # All retries exhausted
        raise RuntimeError(
            f"API call failed after {MAX_RETRIES} retries: {last_exception}"
        ) from last_exception

    def _build_simple_prompt(
        self,
        instruction: str,
        current_policy: dict[str, Any] | None,
        current_cost: float | None,
        settlement_rate: float | None,
        per_bank_costs: dict[str, float] | None,
        iteration: int,
    ) -> str:
        """Build a simple context-aware prompt (legacy mode)."""
        prompt_parts = [instruction]

        if current_policy:
            params = current_policy.get("parameters", {})
            prompt_parts.append("\n## Current Policy Parameters")
            for name, value in params.items():
                prompt_parts.append(f"- {name}: {value}")

        if current_cost is not None:
            prompt_parts.append("\n## Current Performance")
            prompt_parts.append(f"Total cost: ${current_cost:,.0f}")

        if settlement_rate is not None:
            prompt_parts.append(f"Settlement rate: {settlement_rate * 100:.1f}%")

        if per_bank_costs:
            prompt_parts.append("\nPer-bank costs:")
            for bank, cost in per_bank_costs.items():
                prompt_parts.append(f"  - {bank}: ${cost:,.0f}")

        if iteration > 0:
            prompt_parts.append(f"\n## Iteration: {iteration}")
            prompt_parts.append(
                "Based on the current performance, suggest improvements."
            )

        return "\n".join(prompt_parts)

    def _build_extended_prompt(
        self,
        instruction: str,
        current_policy: dict[str, Any] | None,
        current_cost: float | None,
        settlement_rate: float | None,
        iteration: int,
        iteration_history: list[Any] | None,
        best_seed_output: str | None,
        worst_seed_output: str | None,
        best_seed: int,
        worst_seed: int,
        best_seed_cost: int,
        worst_seed_cost: int,
        cost_breakdown: dict[str, int] | None,
        cost_rates: dict[str, Any] | None,
        agent_id: str | None,
    ) -> str:
        """Build a massive extended context prompt with full history for SINGLE AGENT.

        CRITICAL ISOLATION: This prompt contains ONLY the specified agent's data.
        No other agent's policy, history, or metrics are included.

        This prompt includes:
        - Full tick-by-tick output from best and worst seeds (filtered for this agent)
        - Complete iteration history with metrics (filtered for this agent)
        - Policy changes between iterations (for this agent only)
        - Cost analysis and optimization guidance
        """
        from experiments.castro.prompts.context import build_single_agent_context

        # Build current metrics dict
        current_metrics = {
            "total_cost_mean": current_cost or 0,
            "total_cost_std": 0,
            "risk_adjusted_cost": current_cost or 0,
            "settlement_rate_mean": settlement_rate or 1.0,
            "failure_rate": (
                0 if (settlement_rate or 1.0) >= 1.0 else 1.0 - (settlement_rate or 1.0)
            ),
            "best_seed": best_seed,
            "worst_seed": worst_seed,
            "best_seed_cost": best_seed_cost,
            "worst_seed_cost": worst_seed_cost,
        }

        # Build extended context for SINGLE AGENT only
        # CRITICAL: No cross-agent information is passed
        extended_context = build_single_agent_context(
            current_iteration=iteration,
            current_policy=current_policy or {},
            current_metrics=current_metrics,
            iteration_history=iteration_history,
            best_seed_output=best_seed_output,
            worst_seed_output=worst_seed_output,
            best_seed=best_seed,
            worst_seed=worst_seed,
            best_seed_cost=best_seed_cost,
            worst_seed_cost=worst_seed_cost,
            cost_breakdown=cost_breakdown,
            cost_rates=cost_rates,
            agent_id=agent_id,
        )

        # Combine instruction with extended context
        return f"""# OPTIMIZATION TASK

{instruction}

{extended_context}
"""

    async def generate_policy_async(
        self,
        instruction: str = "Generate an optimal policy",
        current_policy: dict[str, Any] | None = None,
        current_cost: float | None = None,
        settlement_rate: float | None = None,
        per_bank_costs: dict[str, float] | None = None,
        iteration: int = 0,
        # Extended context parameters
        iteration_history: list[Any] | None = None,
        best_seed_output: str | None = None,
        worst_seed_output: str | None = None,
        best_seed: int = 0,
        worst_seed: int = 0,
        best_seed_cost: int = 0,
        worst_seed_cost: int = 0,
        cost_breakdown: dict[str, int] | None = None,
        cost_rates: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Async version of generate_policy with exponential backoff retry.

        This mirrors the sync generate_policy() method but is fully async,
        avoiding nested asyncio.run() calls that cause event loop issues.

        CRITICAL ISOLATION: This method generates policy for a SINGLE agent.
        The iteration_history must be pre-filtered to only contain this agent's
        data. No cross-agent information should be passed to the LLM.
        """
        # Determine if we should use extended context
        has_extended_context = (
            iteration_history is not None
            or best_seed_output is not None
            or worst_seed_output is not None
        )

        if has_extended_context:
            # Build massive extended context prompt for SINGLE AGENT
            # CRITICAL: Only this agent's data is passed - no cross-agent leakage
            prompt = self._build_extended_prompt(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                iteration=iteration,
                iteration_history=iteration_history,
                best_seed_output=best_seed_output,
                worst_seed_output=worst_seed_output,
                best_seed=best_seed,
                worst_seed=worst_seed,
                best_seed_cost=best_seed_cost,
                worst_seed_cost=worst_seed_cost,
                cost_breakdown=cost_breakdown,
                cost_rates=cost_rates,
                agent_id=agent_id,
            )
        else:
            # Legacy: Build simple context-aware prompt
            prompt = self._build_simple_prompt(
                instruction=instruction,
                current_policy=current_policy,
                current_cost=current_cost,
                settlement_rate=settlement_rate,
                per_bank_costs=per_bank_costs,
                iteration=iteration,
            )

        agent = self._get_agent()

        deps = RobustPolicyDeps(
            current_policy=current_policy,
            current_cost=current_cost,
            settlement_rate=settlement_rate,
            per_bank_costs=per_bank_costs,
            iteration=iteration,
            iteration_history=iteration_history or [],
            best_seed_output=best_seed_output,
            worst_seed_output=worst_seed_output,
            best_seed=best_seed,
            worst_seed=worst_seed,
            best_seed_cost=best_seed_cost,
            worst_seed_cost=worst_seed_cost,
            cost_breakdown=cost_breakdown or {},
            cost_rates=cost_rates or {},
            agent_id=agent_id,
        )

        # Retry with exponential backoff for transient API errors
        last_exception: Exception | None = None
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                # For Anthropic extended thinking, we MUST use streaming
                # because max_tokens > 21,333 requires streaming per Anthropic API
                if self._is_anthropic_thinking_mode():
                    raw_text = await self._run_with_streaming(agent, prompt, deps)
                    parsed_policy = self._parse_json_from_thinking_response(raw_text)
                    return self._validate_parsed_policy(parsed_policy)

                # Standard mode: use regular async call
                result = await agent.run(prompt, deps=deps)

                # Standard mode: convert Pydantic model to dict
                if hasattr(result.output, "model_dump"):
                    return result.output.model_dump(exclude_none=True)
                return dict(result.output)

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Log full error details in verbose mode
                if self.verbose:
                    print(f"\n  [VERBOSE] API Error Details (async):")
                    print(f"    Model: {self.model}")
                    print(f"    Prompt length: {len(prompt):,} chars")
                    print(
                        f"    System prompt length: {len(self._system_prompt):,} chars"
                    )
                    print(f"    Thinking budget: {self.thinking_budget}")
                    print(f"    Full error:\n{e}")
                    if hasattr(e, "__cause__") and e.__cause__:
                        print(f"    Cause: {e.__cause__}")
                    if hasattr(e, "response"):
                        print(f"    Response: {getattr(e, 'response', 'N/A')}")
                    if hasattr(e, "body"):
                        print(f"    Body: {getattr(e, 'body', 'N/A')}")
                    print()

                # Check if this is a transient error worth retrying
                # Note: 400 errors are NOT transient - they indicate bad request
                is_transient = any(
                    indicator in error_str
                    for indicator in [
                        "503",
                        "502",
                        "500",
                        "tls",
                        "ssl",
                        "certificate",
                        "connection",
                        "timeout",
                        "reset",
                        "upstream",
                        "temporarily unavailable",
                        "service unavailable",
                        "bad gateway",
                        "internal server error",
                    ]
                )

                # Explicitly check for 400 errors - these are NOT transient
                if "status_code: 400" in error_str or "400 bad request" in error_str:
                    is_transient = False
                    if self.verbose:
                        print(
                            f"  [VERBOSE] 400 error detected - NOT retrying (bad request)"
                        )

                if not is_transient:
                    # Non-transient error, don't retry
                    raise

                # Transient error - retry with backoff
                if attempt < MAX_RETRIES - 1:
                    print(
                        f"  [Retry {attempt + 1}/{MAX_RETRIES}] "
                        f"Transient API error, waiting {backoff:.1f}s: {str(e)[:100]}"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_SECONDS)

        # All retries exhausted
        raise RuntimeError(
            f"API call failed after {MAX_RETRIES} retries: {last_exception}"
        ) from last_exception


# ============================================================================
# Convenience Functions
# ============================================================================


def generate_robust_policy(
    constraints: ScenarioConstraints,
    instruction: str = "Generate an optimal policy",
    model: str | None = None,
    reasoning_effort: Literal["low", "medium", "high"] = DEFAULT_REASONING_EFFORT,
    api_key: str | None = None,
    thinking_budget: int | None = None,
    verbose: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate a policy with a single function call.

    Args:
        constraints: Scenario constraints defining allowed elements
        instruction: Natural language instruction
        model: PydanticAI model string (defaults to GPT-4o).
               Use "google-gla:gemini-2.0-flash" for Google Gemini.
               Use "anthropic:claude-sonnet-4-5-20250929" for Claude.
        reasoning_effort: Reasoning effort for GPT models
        api_key: Optional API key (used for Google Gemini models).
                 If not provided for Google models, reads from
                 GOOGLE_AI_STUDIO_API_KEY or GEMINI_API_KEY env vars.
        thinking_budget: Token budget for Anthropic extended thinking mode.
                        When set, enables Claude's extended thinking. Min 1024.
        verbose: Enable verbose error logging for debugging API issues.
        **kwargs: Additional context (current_policy, current_cost, etc.)

    Returns:
        Generated policy as dict (fully validated)

    Example:
        from experiments.castro.schemas.parameter_config import (
            ParameterSpec, ScenarioConstraints
        )

        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec("urgency", 0, 20, 3, "Urgency"),
            ],
            allowed_fields=["balance", "ticks_to_deadline"],
            allowed_actions=["Release", "Hold"],
        )

        # Using OpenAI (default):
        policy = generate_robust_policy(
            constraints,
            "Minimize delay costs while maintaining 95% settlement",
            current_cost=50000,
            settlement_rate=0.85,
        )

        # Using Google Gemini:
        policy = generate_robust_policy(
            constraints,
            "Minimize delay costs",
            model="google-gla:gemini-2.0-flash",
        )

        # Using Claude with extended thinking:
        policy = generate_robust_policy(
            constraints,
            "Minimize delay costs",
            model="anthropic:claude-sonnet-4-5-20250929",
            thinking_budget=32000,
        )
    """
    agent = RobustPolicyAgent(
        constraints=constraints,
        model=model,
        reasoning_effort=reasoning_effort,
        api_key=api_key,
        thinking_budget=thinking_budget,
        verbose=verbose,
    )
    return agent.generate_policy(instruction, **kwargs)
