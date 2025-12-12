"""User prompt builder for optimization iterations.

This module builds the user prompt that provides the LLM with:
1. Current policy for the target agent
2. Filtered tick-by-tick simulation output (ONLY target agent's events)
3. Past iteration history (policy changes and cost deltas)
4. Final instructions for what to optimize

CRITICAL INVARIANT: Agent X may ONLY see:
- Outgoing transactions FROM Agent X
- Incoming liquidity events TO Agent X balance
- Agent X's own policy and state changes
"""

from __future__ import annotations

import json
from typing import Any

from .event_filter import filter_events_for_agent, format_filtered_output


class UserPromptBuilder:
    """Builder for user prompts in optimization.

    Supports method chaining for flexible prompt construction.
    """

    def __init__(self, agent_id: str, current_policy: dict[str, Any]) -> None:
        """Initialize the user prompt builder.

        Args:
            agent_id: ID of the target agent being optimized.
            current_policy: Current policy JSON for the agent.
        """
        self._agent_id = agent_id
        self._current_policy = current_policy
        self._events: list[dict[str, Any]] = []
        self._history: list[dict[str, Any]] = []
        self._cost_breakdown: dict[str, Any] | None = None

    def with_events(self, events: list[dict[str, Any]]) -> UserPromptBuilder:
        """Add simulation events (will be filtered for agent).

        Args:
            events: Raw simulation events (will be filtered).

        Returns:
            Self for method chaining.
        """
        self._events = events
        return self

    def with_history(self, history: list[dict[str, Any]]) -> UserPromptBuilder:
        """Add iteration history.

        Args:
            history: List of iteration records with costs and policy summaries.

        Returns:
            Self for method chaining.
        """
        self._history = history
        return self

    def with_cost_breakdown(
        self,
        best_seed: dict[str, Any],
        worst_seed: dict[str, Any],
        average: dict[str, Any],
    ) -> UserPromptBuilder:
        """Add cost breakdown from bootstrap evaluation.

        Args:
            best_seed: Cost breakdown for best-performing seed.
            worst_seed: Cost breakdown for worst-performing seed.
            average: Average cost breakdown across all seeds.

        Returns:
            Self for method chaining.
        """
        self._cost_breakdown = {
            "best_seed": best_seed,
            "worst_seed": worst_seed,
            "average": average,
        }
        return self

    def build(self) -> str:
        """Build the complete user prompt.

        Returns:
            Complete user prompt string.
        """
        sections: list[str] = []

        # Section 1: Current Policy
        sections.append(self._build_policy_section())

        # Section 2: Simulation Output (filtered)
        sections.append(self._build_simulation_section())

        # Section 3: Cost Breakdown (if provided)
        if self._cost_breakdown is not None:
            sections.append(self._build_cost_breakdown_section())

        # Section 4: Iteration History (if provided)
        if self._history:
            sections.append(self._build_history_section())

        # Section 5: Final Instructions
        sections.append(self._build_instructions_section())

        return "\n\n".join(sections)

    def _build_policy_section(self) -> str:
        """Build the current policy section."""
        lines: list[str] = [
            "=" * 60,
            f"CURRENT POLICY FOR {self._agent_id}",
            "=" * 60,
            "",
        ]

        if self._current_policy:
            policy_json = json.dumps(self._current_policy, indent=2)
            lines.append("```json")
            lines.append(policy_json)
            lines.append("```")
        else:
            lines.append("(No policy currently defined)")

        return "\n".join(lines)

    def _build_simulation_section(self) -> str:
        """Build the simulation output section with filtered events."""
        lines: list[str] = [
            "=" * 60,
            f"SIMULATION OUTPUT FOR {self._agent_id}",
            "=" * 60,
            "",
        ]

        # Filter events for this agent
        filtered_events = filter_events_for_agent(self._agent_id, self._events)

        if not filtered_events:
            lines.append(f"No events recorded for {self._agent_id}.")
            lines.append("")
            lines.append(
                "Note: This may mean no transactions were processed, "
                "or all events were related to other agents."
            )
        else:
            # Format the filtered output
            formatted = format_filtered_output(
                self._agent_id,
                filtered_events,
                include_tick_headers=True,
            )
            lines.append(formatted)

        return "\n".join(lines)

    def _build_cost_breakdown_section(self) -> str:
        """Build the cost breakdown section."""
        if self._cost_breakdown is None:
            return ""

        lines: list[str] = [
            "=" * 60,
            "COST BREAKDOWN (Bootstrap Evaluation)",
            "=" * 60,
            "",
        ]

        best = self._cost_breakdown["best_seed"]
        worst = self._cost_breakdown["worst_seed"]
        average = self._cost_breakdown["average"]

        # Best seed
        lines.append("Best Seed Performance:")
        lines.append(f"  Total Cost: {_format_cost(best.get('total_cost', 0))}")
        lines.extend(_format_cost_components(best, "  "))
        lines.append("")

        # Worst seed
        lines.append("Worst Seed Performance:")
        lines.append(f"  Total Cost: {_format_cost(worst.get('total_cost', 0))}")
        lines.extend(_format_cost_components(worst, "  "))
        lines.append("")

        # Average
        lines.append("Average Performance:")
        lines.append(f"  Total Cost: {_format_cost(average.get('total_cost', 0))}")
        lines.extend(_format_cost_components(average, "  "))

        return "\n".join(lines)

    def _build_history_section(self) -> str:
        """Build the iteration history section."""
        if not self._history:
            return ""

        lines: list[str] = [
            "=" * 60,
            "ITERATION HISTORY",
            "=" * 60,
            "",
        ]

        for record in self._history:
            iteration = record.get("iteration", "?")
            total_cost = record.get("total_cost", 0)
            policy_summary = record.get("policy_summary", "")

            lines.append(f"Iteration {iteration}:")
            lines.append(f"  Total Cost: {_format_cost(total_cost)}")
            if policy_summary:
                lines.append(f"  Policy: {policy_summary}")
            lines.append("")

        return "\n".join(lines)

    def _build_instructions_section(self) -> str:
        """Build the final instructions section."""
        lines: list[str] = [
            "=" * 60,
            "INSTRUCTIONS",
            "=" * 60,
            "",
            "Analyze the simulation output above and generate an IMPROVED policy.",
            "",
            "Your objectives:",
            "1. Minimize total cost (overdraft + delay + deadline penalties)",
            "2. Maintain high settlement rate",
            "3. Avoid end-of-day penalties",
            "",
            "Key considerations:",
            "- Balance liquidity: Holding too much delays settlements",
            "- Release strategically: Consider deadlines and available liquidity",
            "- Monitor incoming payments: Coordinate with expected inflows",
            "",
            "OUTPUT REQUIREMENTS:",
            "- Provide your improved policy as a valid JSON object",
            "- Use ONLY the fields and actions specified in the system prompt",
            "- Every node MUST have a unique 'node_id' field",
            "- Explain your reasoning briefly before the JSON",
        ]

        return "\n".join(lines)


def build_user_prompt(
    agent_id: str,
    current_policy: dict[str, Any],
    events: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    """Convenience function to build user prompt.

    Args:
        agent_id: ID of the target agent.
        current_policy: Current policy JSON.
        events: Simulation events (will be filtered).
        history: Optional iteration history.

    Returns:
        Complete user prompt string.
    """
    builder = UserPromptBuilder(agent_id, current_policy)
    builder.with_events(events)
    if history:
        builder.with_history(history)
    return builder.build()


def _format_cost(cents: int | float) -> str:
    """Format a cost value in cents as dollars.

    Args:
        cents: Cost in integer cents.

    Returns:
        Formatted dollar string.
    """
    if not isinstance(cents, (int, float)):
        return str(cents)
    dollars = abs(cents) / 100
    formatted = f"${dollars:,.2f}"
    if cents < 0:
        formatted = f"-{formatted}"
    return formatted


def _format_cost_components(breakdown: dict[str, Any], indent: str = "") -> list[str]:
    """Format cost breakdown components.

    Args:
        breakdown: Cost breakdown dict with component costs.
        indent: Indentation prefix.

    Returns:
        List of formatted lines.
    """
    lines: list[str] = []

    component_names = [
        ("overdraft_cost", "Overdraft"),
        ("delay_cost", "Delay"),
        ("deadline_penalty", "Deadline Penalty"),
        ("eod_penalty", "EOD Penalty"),
        ("split_cost", "Split Cost"),
    ]

    for key, label in component_names:
        if key in breakdown and breakdown[key]:
            value = breakdown[key]
            lines.append(f"{indent}{label}: {_format_cost(value)}")

    return lines
