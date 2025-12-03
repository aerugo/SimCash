#!/usr/bin/env python3
"""
Policy Validator for Castro Experiments

This module provides policy validation with retry logic for LLM-generated policies.
It uses the SimCash CLI validate-policy command with scenario feature toggle support.

Usage:
    from policy_validator import PolicyValidator

    validator = PolicyValidator(scenario_path="configs/castro_2period_aligned.yaml")
    valid, policy, errors = validator.validate_and_fix(policy_json, max_retries=5)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class ValidationResult:
    """Result of policy validation."""

    valid: bool
    policy_json: str | None = None
    policy_dict: dict | None = None
    errors: list[dict[str, str]] = field(default_factory=list)
    error_summary: str | None = None
    attempts: int = 0


@dataclass
class RetryContext:
    """Context passed to LLM for retry attempts."""

    original_policy: str
    validation_errors: list[dict[str, str]]
    error_summary: str
    attempt_number: int
    max_attempts: int
    schema_hints: str  # Relevant schema sections for the errors


class PolicyValidator:
    """Validates policies using the SimCash CLI.

    Supports validation against scenario feature toggles and provides
    detailed error messages suitable for LLM retry prompts.
    """

    def __init__(
        self,
        simcash_root: str = "/home/user/SimCash",
        scenario_path: str | None = None,
    ):
        """Initialize the validator.

        Args:
            simcash_root: Path to SimCash root directory.
            scenario_path: Path to scenario YAML for feature toggle validation.
        """
        self.simcash_root = Path(simcash_root)
        self.cli_path = self.simcash_root / "api" / ".venv" / "bin" / "payment-sim"
        self.scenario_path = scenario_path

        # Verify CLI exists
        if not self.cli_path.exists():
            raise RuntimeError(
                f"CLI not found at {self.cli_path}. "
                f"Run 'cd api && uv sync --extra dev' to build."
            )

        # Cache for dynamic schema
        self._schema_cache: dict | None = None
        self._schema_markdown_cache: str | None = None

    def validate(self, policy_json: str) -> ValidationResult:
        """Validate a policy JSON string.

        Args:
            policy_json: The policy JSON content.

        Returns:
            ValidationResult with validation outcome.
        """
        # Write policy to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            f.write(policy_json)
            temp_path = f.name

        try:
            # Build CLI command
            cmd = [
                str(self.cli_path),
                "validate-policy",
                temp_path,
                "--format", "json",
            ]

            if self.scenario_path:
                scenario_abs = (
                    self.simcash_root / self.scenario_path
                    if not Path(self.scenario_path).is_absolute()
                    else Path(self.scenario_path)
                )
                cmd.extend(["--scenario", str(scenario_abs)])

            # Run validation
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root),
                timeout=30,
            )

            # Parse output
            try:
                output = json.loads(result.stdout)
            except json.JSONDecodeError:
                return ValidationResult(
                    valid=False,
                    policy_json=policy_json,
                    errors=[{
                        "type": "CLIError",
                        "message": f"CLI output not valid JSON: {result.stdout[:500]}"
                    }],
                    error_summary="CLI validation failed with non-JSON output",
                )

            is_valid = output.get("valid", False)
            errors = output.get("errors", [])

            return ValidationResult(
                valid=is_valid,
                policy_json=policy_json if is_valid else None,
                policy_dict=json.loads(policy_json) if is_valid else None,
                errors=errors,
                error_summary=self._summarize_errors(errors) if errors else None,
            )

        except subprocess.TimeoutExpired:
            return ValidationResult(
                valid=False,
                errors=[{"type": "Timeout", "message": "Validation timed out after 30s"}],
                error_summary="Validation timed out",
            )
        except Exception as e:
            return ValidationResult(
                valid=False,
                errors=[{"type": "Exception", "message": str(e)}],
                error_summary=f"Validation exception: {e}",
            )
        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

    def validate_with_retry(
        self,
        initial_policy_json: str,
        retry_callback: Callable[[RetryContext], str | None],
        max_retries: int = 5,
    ) -> ValidationResult:
        """Validate a policy with retry logic.

        If validation fails, calls retry_callback with error context to get
        a corrected policy. Repeats until validation passes or max_retries
        is reached.

        Args:
            initial_policy_json: The initial policy JSON to validate.
            retry_callback: Function that takes RetryContext and returns
                corrected policy JSON, or None to abort.
            max_retries: Maximum number of retry attempts.

        Returns:
            ValidationResult with final outcome.
        """
        current_policy = initial_policy_json
        attempt = 0

        while attempt <= max_retries:
            attempt += 1

            result = self.validate(current_policy)
            result.attempts = attempt

            if result.valid:
                return result

            if attempt > max_retries:
                result.error_summary = (
                    f"Validation failed after {max_retries} retries. "
                    f"Last error: {result.error_summary}"
                )
                return result

            # Prepare retry context
            context = RetryContext(
                original_policy=current_policy,
                validation_errors=result.errors,
                error_summary=result.error_summary or "",
                attempt_number=attempt,
                max_attempts=max_retries,
                schema_hints=self._get_schema_hints(result.errors),
            )

            # Call retry callback
            corrected = retry_callback(context)
            if corrected is None:
                result.error_summary = f"Retry callback returned None at attempt {attempt}"
                return result

            current_policy = corrected

        return result

    def _summarize_errors(self, errors: list[dict[str, str]]) -> str:
        """Create a human-readable error summary."""
        if not errors:
            return ""

        lines = []
        for err in errors[:5]:  # Limit to first 5 errors
            err_type = err.get("type", "Unknown")
            message = err.get("message", "No message")
            lines.append(f"- [{err_type}] {message}")

        if len(errors) > 5:
            lines.append(f"... and {len(errors) - 5} more errors")

        return "\n".join(lines)

    def _get_schema_hints(self, errors: list[dict[str, str]]) -> str:
        """Get relevant schema hints based on error types."""
        hints = []

        for err in errors:
            err_type = err.get("type", "")
            message = err.get("message", "")

            # Provide targeted hints based on error type
            if "field" in message.lower() or "InvalidField" in err_type:
                hints.append(self._get_field_hints())
            elif "action" in message.lower() or "InvalidAction" in err_type:
                hints.append(self._get_action_hints())
            elif "node" in message.lower() or "InvalidNodeId" in err_type:
                hints.append(self._get_node_hints())
            elif "syntax" in message.lower() or "SyntaxError" in err_type:
                hints.append(self._get_syntax_hints())

        return "\n\n".join(set(hints)) if hints else ""

    def _get_field_hints(self) -> str:
        return """VALID FIELDS:
Transaction: amount, remaining_amount, priority, ticks_to_deadline, is_overdue
Agent: balance, effective_liquidity, credit_limit, posted_collateral, max_collateral_capacity
Queue: queue1_size, queue1_value, queue2_size, queue2_value
Time: current_tick, ticks_per_day, system_tick_in_day, ticks_to_eod"""

    def _get_action_hints(self) -> str:
        return """VALID ACTIONS:
payment_tree: Release, Hold, Drop, Split, StaggerSplit, PaceAndRelease, Reprioritize
bank_tree: SetReleaseBudget, SetState, AddState
collateral_trees: PostCollateral, WithdrawCollateral, HoldCollateral"""

    def _get_node_hints(self) -> str:
        return """NODE REQUIREMENTS:
- Every node needs a unique 'node_id' string
- Condition nodes: type, node_id, condition, on_true, on_false
- Action nodes: type, node_id, action, parameters (if required)"""

    def _get_syntax_hints(self) -> str:
        return """JSON SYNTAX:
- Use double quotes for strings
- No trailing commas
- Operators in conditions: ==, !=, <, <=, >, >=, and, or, not
- Value types: {"value": 5}, {"field": "balance"}, {"param": "threshold"}"""

    def get_schema_for_scenario(self) -> str:
        """Get the full policy schema filtered by scenario toggles.

        Returns:
            Markdown-formatted schema documentation.
        """
        if self._schema_markdown_cache is not None:
            return self._schema_markdown_cache

        cmd = [
            str(self.cli_path),
            "policy-schema",
            "--format", "markdown",
            "--compact",
        ]

        if self.scenario_path:
            scenario_abs = (
                self.simcash_root / self.scenario_path
                if not Path(self.scenario_path).is_absolute()
                else Path(self.scenario_path)
            )
            cmd.extend(["--scenario", str(scenario_abs)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root),
                timeout=30,
            )
            self._schema_markdown_cache = result.stdout
            return result.stdout
        except Exception as e:
            return f"Error getting schema: {e}"

    def get_schema_json(self) -> dict:
        """Get the policy schema as a JSON dict, filtered by scenario.

        Returns:
            Schema dict with expressions, values, computations, actions, fields.
        """
        if self._schema_cache is not None:
            return self._schema_cache

        cmd = [
            str(self.cli_path),
            "policy-schema",
            "--format", "json",
        ]

        if self.scenario_path:
            scenario_abs = (
                self.simcash_root / self.scenario_path
                if not Path(self.scenario_path).is_absolute()
                else Path(self.scenario_path)
            )
            cmd.extend(["--scenario", str(scenario_abs)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.simcash_root),
                timeout=30,
            )
            self._schema_cache = json.loads(result.stdout)
            return self._schema_cache
        except Exception as e:
            return {"error": str(e)}

    def generate_dynamic_prompt(self) -> str:
        """Generate a dynamic LLM prompt with only valid schema elements.

        This generates a policy generation guide that includes ONLY the
        actions, fields, and operators that are valid for this scenario.

        Returns:
            Markdown-formatted prompt with scenario-specific schema.
        """
        schema = self.get_schema_json()

        if "error" in schema:
            return f"# Error loading schema: {schema['error']}"

        # Build dynamic prompt sections
        sections = []

        sections.append("""# SimCash Policy Generation Guide

You are generating payment policies for SimCash, a bank payment system simulator.
Policies are JSON decision trees that control when banks release payments and manage collateral.

## Critical Rules

1. **All amounts are in CENTS** - $100 = 10000 cents
2. **Node IDs must be unique** within each tree
3. **Settlement rate is paramount** - Policies must settle all payments
4. **Only use elements listed below** - Other elements will cause validation errors

## Policy JSON Structure

```json
{
  "version": "2.0",
  "policy_id": "your_policy_name",
  "description": "Strategy description",
  "parameters": {
    "param_name": 0.5
  },
  "payment_tree": { ... },
  "strategic_collateral_tree": { ... }
}
```

## Node Types

### Condition Node
```json
{
  "type": "condition",
  "node_id": "C1_unique_id",
  "condition": { "op": ">=", "left": {"field": "balance"}, "right": {"field": "amount"} },
  "on_true": { ... },
  "on_false": { ... }
}
```

### Action Node
```json
{
  "type": "action",
  "node_id": "A1_unique_id",
  "action": "Release"
}
```
""")

        # Actions section
        actions = schema.get("actions", [])
        if actions:
            sections.append("## Available Actions\n")

            # Group by tree type
            by_tree: dict[str, list[dict]] = {}
            for action in actions:
                valid_trees = action.get("valid_in_trees", [])
                for tree in valid_trees:
                    if tree not in by_tree:
                        by_tree[tree] = []
                    by_tree[tree].append(action)

            for tree, tree_actions in sorted(by_tree.items()):
                sections.append(f"### {tree}\n")
                for a in tree_actions:
                    name = a.get("json_key", a.get("name", "Unknown"))
                    desc = a.get("description", "")
                    params = a.get("parameters", [])
                    if params:
                        param_str = ", ".join(
                            f"`{p['name']}`" + (" (required)" if p.get("required") else "")
                            for p in params
                        )
                        sections.append(f"- **{name}**: {desc} - Parameters: {param_str}")
                    else:
                        sections.append(f"- **{name}**: {desc}")
                sections.append("")

        # Expressions section
        expressions = schema.get("expressions", [])
        if expressions:
            sections.append("## Comparison & Logical Operators\n")
            for expr in expressions:
                key = expr.get("json_key", expr.get("name", ""))
                desc = expr.get("description", "")
                sections.append(f"- `{key}`: {desc}")
            sections.append("")

        # Computations section
        computations = schema.get("computations", [])
        if computations:
            sections.append("## Arithmetic Operators\n")
            for comp in computations:
                key = comp.get("json_key", comp.get("name", ""))
                desc = comp.get("description", "")
                sections.append(f"- `{key}`: {desc}")
            sections.append("")

        # Values section
        values = schema.get("values", [])
        if values:
            sections.append("## Value Types\n")
            for val in values:
                key = val.get("json_key", val.get("name", ""))
                desc = val.get("description", "")
                example = val.get("example_json", {})
                sections.append(f"- `{key}`: {desc}")
                if example:
                    sections.append(f"  Example: `{json.dumps(example)}`")
            sections.append("")

        # Fields section - this is critical!
        # Note: The schema may not include fields directly, so we need to
        # provide them from the hardcoded list in analysis.py
        sections.append("""## Available Context Fields

### Transaction Fields (payment_tree only)
| Field | Description |
|-------|-------------|
| `amount` | Transaction amount (cents) |
| `remaining_amount` | Amount still to be paid (cents) |
| `priority` | Payment priority (0-10) |
| `ticks_to_deadline` | Ticks until deadline |
| `is_overdue` | Past deadline (0 or 1) |
| `is_divisible` | Can be split (0 or 1) |

### Agent Fields (all trees)
| Field | Description |
|-------|-------------|
| `balance` | Current account balance (cents) |
| `effective_liquidity` | Balance + credit available (cents) |
| `credit_limit` | Total credit line (cents) |
| `posted_collateral` | Active collateral (cents) |
| `max_collateral_capacity` | Maximum postable collateral (cents) |
| `remaining_collateral_capacity` | Capacity left (cents) |

### Queue Fields (all trees)
| Field | Description |
|-------|-------------|
| `queue1_size` | Pending payment count |
| `queue1_value` | Pending payment total (cents) |
| `queue2_size` | RTGS queue count |
| `queue2_value` | RTGS queue total (cents) |

### Time Fields (all trees)
| Field | Description |
|-------|-------------|
| `current_tick` | Current simulation tick |
| `system_tick_in_day` | Tick within current day (0-indexed) |
| `ticks_per_day` | Total ticks per day |
| `ticks_to_eod` | Ticks until end of day |
""")

        # Example policy
        sections.append("""## Example Valid Policy

```json
{
  "version": "2.0",
  "policy_id": "balanced_timing",
  "description": "Release urgent payments, hold others if low liquidity",
  "parameters": {
    "urgency_threshold": 3.0,
    "liquidity_buffer": 1.1
  },
  "strategic_collateral_tree": {
    "type": "condition",
    "node_id": "SC1_start",
    "condition": {
      "op": "==",
      "left": {"field": "system_tick_in_day"},
      "right": {"value": 0.0}
    },
    "on_true": {
      "type": "action",
      "node_id": "SC2_post",
      "action": "PostCollateral",
      "parameters": {
        "amount": {"compute": {"op": "*", "left": {"field": "max_collateral_capacity"}, "right": {"value": 0.2}}},
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
    "node_id": "P1_urgent",
    "condition": {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}
    },
    "on_true": {
      "type": "action",
      "node_id": "P2_release",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "P3_liquidity",
      "condition": {
        "op": ">=",
        "left": {"field": "effective_liquidity"},
        "right": {"compute": {"op": "*", "left": {"field": "remaining_amount"}, "right": {"param": "liquidity_buffer"}}}
      },
      "on_true": {
        "type": "action",
        "node_id": "P4_release",
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

## Common Mistakes to Avoid

1. **Duplicate node_id** - Each node needs a unique ID
2. **Wrong action for tree** - `Release` only in payment_tree, `PostCollateral` only in collateral trees
3. **Missing parameters** - Actions like `Split` require `num_splits`
4. **Invalid field names** - Only use fields listed above
5. **Forgetting node_id** - Every node needs one
""")

        return "\n".join(sections)


def create_retry_prompt(context: RetryContext, master_prompt_path: str) -> str:
    """Create a prompt for the LLM to fix validation errors.

    Args:
        context: The RetryContext with error information.
        master_prompt_path: Path to the master prompt file.

    Returns:
        Complete prompt for the LLM.
    """
    master_prompt = ""
    try:
        master_prompt = Path(master_prompt_path).read_text()
    except Exception:
        master_prompt = "(Master prompt not available)"

    return f"""{master_prompt}

---

## VALIDATION ERROR - FIX REQUIRED (Attempt {context.attempt_number}/{context.max_attempts})

The following policy failed validation:

```json
{context.original_policy}
```

### Validation Errors

{context.error_summary}

### Schema Hints

{context.schema_hints}

### Instructions

Please provide a CORRECTED version of the policy that fixes ALL the validation errors listed above.

Return ONLY the corrected JSON policy, with no additional explanation.
The policy must be valid JSON that will pass SimCash validation.

```json
"""


# CLI for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate a SimCash policy")
    parser.add_argument("policy_file", help="Path to policy JSON file")
    parser.add_argument("--scenario", "-s", help="Path to scenario YAML")
    parser.add_argument("--simcash-root", default="/home/user/SimCash")

    args = parser.parse_args()

    policy_content = Path(args.policy_file).read_text()
    validator = PolicyValidator(
        simcash_root=args.simcash_root,
        scenario_path=args.scenario,
    )

    result = validator.validate(policy_content)

    if result.valid:
        print("Validation PASSED")
        sys.exit(0)
    else:
        print("Validation FAILED")
        print(result.error_summary)
        sys.exit(1)
