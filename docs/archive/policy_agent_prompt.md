# Policy Agent LLM Prompt (Archived)

> **Source:** `experiments/castro/generator/robust_policy_agent.py`
> **Deleted in:** commit `c7c3513` (chore: Remove old castro code, rename new-castro to castro)
> **Recovered:** 2025-12-12

This document preserves the LLM system prompt used by the `RobustPolicyAgent` to generate valid policy trees for the SimCash payment simulator. The prompt was carefully crafted through iteration to minimize LLM errors when generating structured JSON policies.

---

## Table of Contents

1. [Overview](#overview)
2. [Dynamically Injected Sections](#dynamically-injected-sections)
3. [Complete System Prompt Template](#complete-system-prompt-template)
4. [Usage Context](#usage-context)

---

## Overview

The policy agent prompt was designed to:

1. **Prevent common LLM errors** - The prompt includes explicit error examples and a pre-generation checklist
2. **Enforce action-tree mapping** - Different tree types accept different actions (a major source of errors)
3. **Provide validated examples** - A complete working policy serves as a template
4. **Support scenario constraints** - The prompt is dynamically generated based on what parameters/fields/actions are allowed

### Key Design Decisions

- **ASCII tables** for action validity - LLMs parse these more reliably than prose
- **Explicit "WRONG vs FIX" examples** - Showing both incorrect and correct patterns
- **Node ID emphasis** - Missing `node_id` was a frequent validation failure
- **Compute wrapper reminder** - Raw arithmetic expressions were a common mistake

---

## Dynamically Injected Sections

The prompt template contains several placeholders that are filled at runtime based on `ScenarioConstraints`:

### `{castro_section}`

**Injected when:** `castro_mode=True`

Contains Castro paper alignment rules that restrict the policy to match the theoretical model from Castro et al. (2025). This section explains:
- The Castro model constraints (initial liquidity at t=0 only, Release/Hold decisions)
- Cost structure (r_c < r_d < r_b)
- Liquidity evolution with deferred crediting
- Prohibited actions in Castro mode
- Required structure for the `strategic_collateral_tree`

The full content is shown inline in the [Complete System Prompt Template](#complete-system-prompt-template) section below.

### `{tree_enablement}`

**Source:** Computed from `constraints.allowed_bank_actions` and `constraints.allowed_collateral_actions`

**Example output:**
```
    payment_tree: ALWAYS REQUIRED
    bank_tree: OPTIONAL (enabled in this scenario)
    strategic_collateral_tree: OPTIONAL (enabled in this scenario)
    end_of_tick_collateral_tree: OPTIONAL (enabled in this scenario)
```

**Purpose:** Tells the LLM which tree types are available in this scenario. Some scenarios disable bank_tree or collateral trees.

### `{param_list}`

**Source:** `constraints.allowed_parameters` (list of `ParameterSpec` objects)

**Example output:**
```
    urgency_threshold: Ticks before deadline to release payment [range: 0-20, default: 3.0]
    liquidity_buffer: Multiplier for required liquidity [range: 0.5-3.0, default: 1.0]
    initial_liquidity_fraction: Fraction of collateral to post at t=0 [range: 0.0-1.0, default: 0.25]
```

**Purpose:** Documents which parameters the LLM can define and reference with `{"param": "name"}`. Includes valid ranges to prevent out-of-bounds values.

### `{field_list}`

**Source:** `constraints.allowed_fields` (list of strings)

**Example output:**
```
    balance
    effective_liquidity
    ticks_to_deadline
    remaining_amount
    system_tick_in_day
    queue1_total_value
    ...
```

**Purpose:** Documents which simulation state fields can be referenced with `{"field": "name"}`. Prevents LLM from inventing non-existent fields.

### `{payment_action_list}`

**Source:** `constraints.allowed_actions` (list of strings)

**Example output:**
```
      Release
      Hold
      Split
```

**Purpose:** Lists valid actions for `payment_tree`. In Castro mode, this is typically just `Release` and `Hold`.

### `{bank_action_list}`

**Source:** `constraints.allowed_bank_actions` (list of strings, optional)

**Example output:**
```
      SetReleaseBudget
      SetState
      AddState
      NoAction
```

**Or if disabled:**
```
      (Not enabled)
```

**Purpose:** Lists valid actions for `bank_tree`. When empty, the LLM knows not to generate a bank_tree.

### `{collateral_action_list}`

**Source:** `constraints.allowed_collateral_actions` (list of strings, optional)

**Example output:**
```
      PostCollateral
      WithdrawCollateral
      HoldCollateral
```

**Purpose:** Lists valid actions for `strategic_collateral_tree` and `end_of_tick_collateral_tree`.

### `{param_defaults_example}`

**Source:** Computed from `constraints.allowed_parameters` defaults

**Example output:**
```json
{
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.0,
    "initial_liquidity_fraction": 0.25
}
```

**Purpose:** Provides recommended starting parameter values at the end of the prompt.

---

## Complete System Prompt Template

Below is the full prompt template with placeholders shown as `{placeholder_name}`.

**Note:** The `{castro_section}` placeholder is shown expanded below to demonstrate what the LLM sees when `castro_mode=True`. When `castro_mode=False`, this entire section is omitted (empty string).

```
You are an expert policy generator for SimCash, a payment settlement simulation.

################################################################################
#                    CASTRO PAPER ALIGNMENT MODE                               #
#           (Replicating Castro et al. 2025 Payment System Game)               #
################################################################################
# >>> DYNAMICALLY INJECTED when castro_mode=True <<<
# >>> This entire block is OMITTED when castro_mode=False <<<

This experiment follows the rules from:
"Estimating Policy Functions in Payment Systems Using Reinforcement Learning"

CASTRO MODEL CONSTRAINTS:

1. INITIAL LIQUIDITY DECISION (t=0 ONLY):
   - Choose fraction x₀ ∈ [0,1] of collateral B at day start: ℓ₀ = x₀ · B
   - This is the ONLY collateral decision allowed
   - strategic_collateral_tree MUST guard PostCollateral with tick == 0

2. INTRADAY PAYMENT DECISIONS (t=1,...,T-1):
   - Each period, choose x_t ∈ [0,1] of payments to send
   - Release = send in full (x_t = 1)
   - Hold = delay to next period (x_t = 0)
   - Constraint: Can only send what liquidity covers: P_t · x_t ≤ ℓ_{t-1}

3. COST STRUCTURE (r_c < r_d < r_b):
   - r_c: Collateral opportunity cost (initial liquidity)
   - r_d: Delay cost per tick (waiting payments)
   - r_b: End-of-day borrowing cost (shortfall)

4. LIQUIDITY EVOLUTION:
   - ℓ_t = ℓ_{t-1} - (outflows) + (inflows)
   - With deferred crediting: inflows available NEXT period only

PROHIBITED IN CASTRO MODE:
  ✗ Split, PaceAndRelease, StaggerSplit (continuous payments assumed)
  ✗ ReleaseWithCredit (no interbank credit)
  ✗ WithdrawCollateral (no mid-day collateral reduction)
  ✗ PostCollateral after tick 0 (initial decision only)
  ✗ SetReleaseBudget, SetState, AddState (no complex bank logic)

REQUIRED STRATEGIC_COLLATERAL_TREE STRUCTURE:
```json
{
  "type": "condition",
  "node_id": "SC1",
  "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0}},
  "on_true": {
    "type": "action",
    "node_id": "SC2",
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
  "on_false": {"type": "action", "node_id": "SC3", "action": "HoldCollateral"}
}
```

# >>> END OF CASTRO SECTION <<<

################################################################################
#                     MANDATORY PRE-GENERATION CHECKLIST                       #
################################################################################
BEFORE generating ANY policy, verify you will satisfy ALL of these:

  [ ] Every {"param": "X"} has a matching "X" key in the "parameters" object
  [ ] Every action matches its tree type (see ACTION VALIDITY TABLE below)
  [ ] Every node has a unique "node_id" string
  [ ] Arithmetic expressions are wrapped in {"compute": {...}}
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

ALLOWED PARAMETERS (define in "parameters", reference with {"param": "name"}):
{param_list}

ALLOWED FIELDS (reference with {"field": "name"}):
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
{
  "version": "2.0",
  "policy_id": "complete_validated_example",
  "description": "A complete policy showing all tree types with correct actions",
  "parameters": {
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.0,
    "initial_collateral_fraction": 0.25,
    "budget_fraction": 0.5
  },
  "bank_tree": {
    "type": "condition",
    "node_id": "BT1_check_day_progress",
    "description": "Set release budget based on time of day",
    "condition": {
      "op": ">=",
      "left": {"field": "day_progress_fraction"},
      "right": {"value": 0.8}
    },
    "on_true": {
      "type": "action",
      "node_id": "BT2_eod_budget",
      "description": "End of day - larger budget to clear queues",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release": {
          "compute": {
            "op": "*",
            "left": {"field": "effective_liquidity"},
            "right": {"value": 0.7}
          }
        }
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "BT3_normal_budget",
      "description": "Normal budget during the day",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release": {
          "compute": {
            "op": "*",
            "left": {"field": "effective_liquidity"},
            "right": {"param": "budget_fraction"}
          }
        }
      }
    }
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_tick_zero",
    "description": "Post initial collateral at start of day",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_post_initial",
      "action": "PostCollateral",
      "parameters": {
        "amount": {
          "compute": {
            "op": "*",
            "left": {"field": "max_collateral_capacity"},
            "right": {"param": "initial_collateral_fraction"}
          }
        },
        "reason": {"value": "InitialAllocation"}
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "SC3_hold",
      "action": "HoldCollateral"
    }
  },
  "payment_tree": {
    "type": "condition",
    "node_id": "P1_check_urgent",
    "description": "Release if close to deadline",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "P2_release_urgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3_check_liquidity",
      "description": "Release if sufficient liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {
          "compute": {
            "op": "*",
            "left": {"field": "remaining_amount"},
            "right": {"param": "liquidity_buffer"}
          }
        }
      },
      "on_true": {
        "type": "action",
        "node_id": "P4_release_liquid",
        "action": "Release"
      },
      "on_false": {
        "type": "action",
        "node_id": "P5_hold",
        "action": "Hold"
      }
    }
  }
}
```

KEY OBSERVATIONS FROM THE VALIDATED EXAMPLE:
  1. ALL parameters are DEFINED in "parameters" BEFORE any {"param": "X"} reference
  2. bank_tree uses SetReleaseBudget with REQUIRED "max_value_to_release" parameter!
  3. strategic_collateral_tree uses HoldCollateral (NOT Hold or NoAction!)
  4. payment_tree uses Hold (NOT HoldCollateral!)
  5. Each node has a UNIQUE node_id (BT1, BT2, BT3, SC1, SC2, SC3, P1, P2, P3, P4, P5)
  6. Arithmetic uses {"compute": {...}} wrapper

CRITICAL FOR bank_tree:
  - SetReleaseBudget action REQUIRES the "max_value_to_release" parameter
  - The "max_value_to_release" controls how much total value the bank can release this tick
  - This is NOT optional - missing it causes validation failure!

################################################################################
#                         VALUE TYPES REFERENCE                                #
################################################################################

Four ways to specify values:

1. LITERAL (constant number):
   {"value": 5.0}
   {"value": 0}
   {"value": true}   // Becomes 1.0
   {"value": false}  // Becomes 0.0

2. FIELD REFERENCE (simulation state):
   {"field": "balance"}
   {"field": "ticks_to_deadline"}
   {"field": "effective_liquidity"}

3. PARAMETER REFERENCE (policy constant):
   {"param": "urgency_threshold"}
   // REQUIRES: "urgency_threshold" defined in "parameters" object!

4. COMPUTATION (arithmetic):
   {"compute": {"op": "+", "left": {"field": "balance"}, "right": {"value": 1000}}}
   {"compute": {"op": "*", "left": {"param": "factor"}, "right": {"field": "amount"}}}
   {"compute": {"op": "max", "values": [{"field": "X"}, {"value": 0}]}}

   AVAILABLE OPERATORS: +, -, *, /, max, min, ceil, floor, abs, round, clamp, div0

################################################################################
#                      COMMON ERRORS TO AVOID                                  #
################################################################################

ERROR 1: UNDEFINED PARAMETER (causes TYPE_ERROR)
  ✗ WRONG:
    "parameters": {},
    "condition": {"right": {"param": "threshold"}}

  ✓ FIX: Add "threshold" to parameters:
    "parameters": {"threshold": 5.0},
    "condition": {"right": {"param": "threshold"}}

ERROR 2: WRONG ACTION FOR TREE (causes INVALID_ACTION)
  ✗ WRONG in strategic_collateral_tree:
    {"action": "Hold"}      // Hold is PAYMENT-only!
    {"action": "NoAction"}  // NoAction is BANK-only!

  ✓ FIX in strategic_collateral_tree:
    {"action": "HoldCollateral"}  // Correct collateral action

ERROR 3: RAW ARITHMETIC (causes parse error)
  ✗ WRONG:
    "right": {"op": "*", "left": {"value": 2}, "right": {"field": "X"}}

  ✓ FIX: Wrap in "compute":
    "right": {"compute": {"op": "*", "left": {"value": 2}, "right": {"field": "X"}}}

ERROR 4: MISSING NODE_ID (causes MISSING_FIELD)
  ✗ WRONG:
    {"type": "action", "action": "Release"}

  ✓ FIX: Add unique node_id:
    {"type": "action", "node_id": "A1_release", "action": "Release"}

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
```

---

## Usage Context

### How the Prompt Was Used

The `RobustPolicyAgent` class used this prompt as follows:

```python
from experiments.castro.generator.robust_policy_agent import RobustPolicyAgent
from experiments.castro.schemas.parameter_config import (
    ParameterSpec,
    ScenarioConstraints,
)

# Define what's allowed in this scenario
constraints = ScenarioConstraints(
    allowed_parameters=[
        ParameterSpec("urgency_threshold", 0, 20, 3, "Ticks before deadline to release"),
        ParameterSpec("liquidity_buffer", 0.5, 3.0, 1.0, "Multiplier for required liquidity"),
    ],
    allowed_fields=["balance", "ticks_to_deadline", "effective_liquidity", "remaining_amount"],
    allowed_actions=["Release", "Hold"],
    allowed_bank_actions=["SetReleaseBudget", "NoAction"],
    allowed_collateral_actions=["PostCollateral", "HoldCollateral"],
)

# Create agent - prompt is generated from constraints
agent = RobustPolicyAgent(
    constraints=constraints,
    model="gpt-4o",
    castro_mode=True,  # Include Castro paper alignment section
)

# Generate an improved policy
policy = agent.generate_policy(
    instruction="Reduce delay costs while maintaining settlement rate",
    current_cost=50000,
    settlement_rate=0.85,
)
```

### Why Dynamic Generation?

The prompt is generated dynamically rather than being a static string because:

1. **Different scenarios have different allowed elements** - A Castro experiment might only allow `Release`/`Hold`, while a full SimCash scenario allows `Split`, `PaceAndRelease`, etc.

2. **Parameter bounds vary** - Each scenario defines its own parameter ranges

3. **Tree types can be enabled/disabled** - Some scenarios don't use `bank_tree` or collateral trees

4. **Reduces hallucination** - By explicitly listing only valid options, the LLM is less likely to invent non-existent fields or actions

---

## Related Files (Also Deleted)

These files worked together with the prompt:

- `experiments/castro/prompts/templates.py` - Additional context templates for different tree types
- `experiments/castro/prompts/builder.py` - `PolicyPromptBuilder` class for constructing user prompts
- `experiments/castro/schemas/parameter_config.py` - `ScenarioConstraints` and `ParameterSpec` dataclasses
- `experiments/castro/schemas/dynamic.py` - Dynamic Pydantic model generation from constraints

---

*Recovered from git history, commit `c7c3513^`*
