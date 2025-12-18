"""Single-agent context builder for LLM policy optimization.

This module provides context builders for creating rich prompts
that help LLMs generate better policy improvements.

CRITICAL ISOLATION: The SingleAgentContextBuilder creates prompts
that contain ONLY the specified agent's data. No other agent's
policy, history, or metrics are included.

Classes:
    SingleAgentContextBuilder: Builds context prompts for single agent

Functions:
    build_single_agent_context: Convenience function to build context
"""

from __future__ import annotations

import json
from typing import Any

from payment_simulator.ai_cash_mgmt.prompts.context_types import (
    SingleAgentContext,
    SingleAgentIterationRecord,
)
from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
    compute_parameter_trajectory,
)


class SingleAgentContextBuilder:
    """Builds context prompts for SINGLE AGENT policy optimization.

    CRITICAL ISOLATION: This builder creates prompts that contain ONLY
    the specified agent's data. No cross-agent information leakage.

    The prompt is designed for models with 200k+ token context windows.

    Sections included:
        1. Header with agent ID and iteration
        2. Current state summary with metrics
        3. Cost analysis with breakdown
        4. Optimization guidance based on costs
        5. Simulation output (tick-by-tick logs)
        6. Full iteration history
        7. Parameter trajectories
        8. Final instructions

    Example:
        >>> context = SingleAgentContext(
        ...     agent_id="BANK_A",
        ...     current_iteration=5,
        ...     current_metrics={"total_cost_mean": 12500},
        ... )
        >>> builder = SingleAgentContextBuilder(context)
        >>> prompt = builder.build()
    """

    def __init__(self, context: SingleAgentContext) -> None:
        """Initialize the builder with single-agent context.

        Args:
            context: SingleAgentContext with all relevant data.
        """
        self.context = context

    def build(self) -> str:
        """Build the complete single-agent context prompt.

        Returns:
            A structured markdown prompt with ONLY this agent's data.
        """
        sections = [
            self._build_header(),
            self._build_current_state_summary(),
            self._build_cost_analysis(),
            self._build_optimization_guidance(),
            self._build_bootstrap_samples_section(),  # Now builds simulation output section
            self._build_iteration_history_section(),
            self._build_parameter_trajectory_section(),
            self._build_final_instructions(),
        ]

        return "\n\n".join(section for section in sections if section)

    def _build_header(self) -> str:
        """Build the header section."""
        agent_label = self.context.agent_id or "Agent"
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY OPTIMIZATION CONTEXT - {agent_label} - ITERATION {self.context.current_iteration}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This document provides complete context for optimizing YOUR payment policy.
Analyze the simulation outputs and historical data to identify improvements.

NOTE: You are optimizing policy for {agent_label} ONLY. Focus on YOUR decisions.

TABLE OF CONTENTS:
1. Current State Summary
2. Cost Analysis
3. Optimization Guidance
4. Simulation Output
5. Full Iteration History
6. Parameter Trajectories
7. Final Instructions
""".strip()

    def _build_current_state_summary(self) -> str:
        """Build the current state summary section (single agent only)."""
        m = self.context.current_metrics
        cost_delta = ""
        if self.context.iteration_history:
            prev_cost = self.context.iteration_history[-1].metrics.get(
                "total_cost_mean", 0
            )
            if prev_cost > 0:
                current_cost = m.get("total_cost_mean", 0)
                delta = current_cost - prev_cost
                pct = (delta / prev_cost) * 100
                direction = "↑" if delta > 0 else "↓"
                cost_delta = f" ({direction}{abs(pct):.1f}% from previous)"

        agent_label = self.context.agent_id or "Agent"
        return f"""
## 1. CURRENT STATE SUMMARY

### Performance Metrics (Iteration {self.context.current_iteration})

| Metric | Value |
|--------|-------|
| **Mean Total Cost** | ${m.get('total_cost_mean', 0):,.0f}{cost_delta} |
| **Cost Std Dev** | ±${self.context.cost_std:,.0f} |
| **Sample Cost** | ${self.context.sample_cost:,} (Seed #{self.context.sample_seed}) |
| **Settlement Rate** | {m.get('settlement_rate_mean', 0) * 100:.1f}% |
| **Failure Rate** | {m.get('failure_rate', 0) * 100:.0f}% |

### Current Policy Parameters ({agent_label})

```json
{json.dumps(self.context.current_policy.get('parameters', {}), indent=2)}
```
""".strip()

    def _build_cost_analysis(self) -> str:
        """Build the cost breakdown analysis section."""
        cb = self.context.cost_breakdown
        if not cb:
            return ""

        total = sum(cb.values()) or 1  # Avoid division by zero

        lines = ["## 2. COST ANALYSIS", "", "### Cost Breakdown (Last Iteration)", ""]
        lines.append("| Cost Type | Amount | % of Total | Priority |")
        lines.append("|-----------|--------|------------|----------|")

        # Sort by amount descending
        sorted_costs = sorted(cb.items(), key=lambda x: x[1], reverse=True)
        for cost_type, amount in sorted_costs:
            pct = (amount / total) * 100
            priority = (
                "🔴 HIGH" if pct > 40 else ("🟡 MEDIUM" if pct > 20 else "🟢 LOW")
            )
            lines.append(f"| {cost_type} | ${amount:,} | {pct:.1f}% | {priority} |")

        # Add cost rates context
        if self.context.cost_rates:
            lines.extend(
                [
                    "",
                    "### Cost Rate Configuration",
                    "```json",
                    json.dumps(self.context.cost_rates, indent=2),
                    "```",
                ]
            )

        return "\n".join(lines)

    def _build_optimization_guidance(self) -> str:
        """Build optimization guidance based on current state."""
        cb = self.context.cost_breakdown
        m = self.context.current_metrics

        guidance = ["## 3. OPTIMIZATION GUIDANCE", ""]

        # Analyze what's driving costs
        if cb:
            total = sum(cb.values()) or 1
            delay_pct = (cb.get("delay", 0) / total) * 100
            collateral_pct = (cb.get("collateral", 0) / total) * 100
            overdraft_pct = (cb.get("overdraft", 0) / total) * 100
            eod_pct = (cb.get("eod_penalty", 0) / total) * 100

            if delay_pct > 40:
                guidance.append(
                    "⚠️ **HIGH DELAY COSTS** - Payments are waiting too long in queue.\n"
                    "   Consider: Lower urgency_threshold, reduce liquidity_buffer, "
                    "release payments earlier."
                )
            if collateral_pct > 40:
                guidance.append(
                    "⚠️ **HIGH COLLATERAL COSTS** - Posting too much collateral.\n"
                    "   Consider: Lower initial_collateral_fraction, withdraw collateral "
                    "when queue is empty."
                )
            if overdraft_pct > 20:
                guidance.append(
                    "⚠️ **OVERDRAFT COSTS** - Balance going negative.\n"
                    "   Consider: Increase liquidity_buffer, hold non-urgent payments."
                )
            if eod_pct > 20:
                guidance.append(
                    "⚠️ **END-OF-DAY PENALTIES** - Payments not settled by day end.\n"
                    "   Consider: Release all payments aggressively near EOD, "
                    "post emergency collateral."
                )

        # Analyze trajectory
        if len(self.context.iteration_history) >= 3:
            recent_costs = [
                r.metrics.get("total_cost_mean", float("inf"))
                for r in self.context.iteration_history[-3:]
            ]
            if all(
                recent_costs[i] <= recent_costs[i - 1]
                for i in range(1, len(recent_costs))
            ):
                guidance.append(
                    "✅ **IMPROVING TREND** - Costs decreasing consistently. "
                    "Continue current optimization direction."
                )
            elif all(
                recent_costs[i] >= recent_costs[i - 1]
                for i in range(1, len(recent_costs))
            ):
                guidance.append(
                    "🔄 **WORSENING TREND** - Costs increasing. "
                    "Consider reverting recent changes or trying a different approach."
                )
            else:
                guidance.append(
                    "📊 **OSCILLATING** - Costs not converging. "
                    "Try smaller parameter adjustments."
                )

        # Settlement rate warning
        if m.get("settlement_rate_mean", 1.0) < 1.0:
            guidance.append(
                f"🚨 **INCOMPLETE SETTLEMENT** - Only {m.get('settlement_rate_mean', 0) * 100:.1f}% "
                "of payments settled. This should be 100%. Priority fix needed."
            )

        if len(guidance) <= 2:  # Only header
            guidance.append(
                "No specific issues detected. Focus on incremental improvements."
            )

        return "\n\n".join(guidance)

    def _build_initial_simulation_section(self) -> str:
        """Build the initial simulation section (baseline before optimization)."""
        if not self.context.initial_simulation_output:
            return ""

        sections = [
            "## 4. INITIAL SIMULATION (BASELINE)",
            "",
            "This shows what happened in the initial simulation before any "
            "optimization was applied. Use this as a baseline reference.",
            "",
            "<initial_simulation>",
            "```",
            self.context.initial_simulation_output,
            "```",
            "</initial_simulation>",
        ]

        return "\n".join(sections)

    def _build_bootstrap_samples_section(self) -> str:
        """Build the simulation output section with the representative trace."""
        sections = ["## 4. SIMULATION OUTPUT", ""]
        sections.append(
            "This is the tick-by-tick event trace from the representative simulation sample. "
            "Analyze what decisions led to the observed costs."
        )
        sections.append("")

        # Simulation trace (the single representative sample)
        if self.context.simulation_trace:
            cost_str = f", Cost: ${self.context.sample_cost:,}" if self.context.sample_cost else ""
            sections.extend(
                [
                    f"### Simulation Trace (Seed #{self.context.sample_seed}{cost_str})",
                    "",
                    "Analyze this trace to understand what happened during the simulation:",
                    "- Which payments were released vs held?",
                    "- Where did costs accrue (delays, overdrafts, collateral)?",
                    "- What conditions triggered different decisions?",
                    "",
                    "<simulation_trace>",
                    "```",
                    self.context.simulation_trace,
                    "```",
                    "</simulation_trace>",
                    "",
                ]
            )
        else:
            sections.append("*No simulation trace available for this iteration.*")

        return "\n".join(sections)

    def _build_iteration_history_section(self) -> str:
        """Build the complete iteration history section (single agent only).

        CRITICAL: Only shows THIS agent's policy history and changes.
        """
        agent_label = self.context.agent_id or "Agent"
        sections = ["## 5. FULL ITERATION HISTORY", ""]

        if not self.context.iteration_history:
            sections.append("*No previous iterations.*")
            return "\n".join(sections)

        # Summary table with acceptance status
        sections.append("### Metrics Summary Table")
        sections.append("")
        sections.append(
            "| Iter | Status | Mean Cost | Std Dev | Settlement | Best Seed | Worst Seed |"
        )
        sections.append(
            "|------|--------|-----------|---------|------------|-----------|------------|"
        )

        for record in self.context.iteration_history:
            m = record.metrics
            # Status indicator
            if record.is_best_so_far:
                status = "⭐ BEST"
            elif record.was_accepted:
                status = "✅ KEPT"
            else:
                status = "❌ REJECTED"

            sections.append(
                f"| {record.iteration} | {status} | "
                f"${m.get('total_cost_mean', 0):,.0f} | "
                f"±${m.get('total_cost_std', 0):,.0f} | "
                f"{m.get('settlement_rate_mean', 0) * 100:.1f}% | "
                f"${m.get('best_seed_cost', 0):,} | "
                f"${m.get('worst_seed_cost', 0):,} |"
            )

        # Show best policy summary
        best_records = [r for r in self.context.iteration_history if r.is_best_so_far]
        if best_records:
            best = best_records[-1]  # Most recent best
            sections.extend(
                [
                    "",
                    "### Current Best Policy",
                    f"The best policy so far was discovered in **iteration {best.iteration}** "
                    f"with mean cost **${best.metrics.get('total_cost_mean', 0):,.0f}**.",
                    "",
                ]
            )

        # Detailed changes per iteration (single agent only)
        sections.extend(["", "### Detailed Changes Per Iteration", ""])

        for record in self.context.iteration_history:
            # Header with status
            if record.is_best_so_far:
                status_emoji = "⭐"
                status_text = "BEST POLICY"
            elif record.was_accepted:
                status_emoji = "✅"
                status_text = "ACCEPTED"
            else:
                status_emoji = "❌"
                status_text = "REJECTED"

            sections.append(
                f"#### {status_emoji} Iteration {record.iteration} ({status_text})"
            )
            sections.append("")

            m = record.metrics
            sections.append(
                f"**Performance:** Mean cost ${m.get('total_cost_mean', 0):,.0f}, "
                f"Settlement {m.get('settlement_rate_mean', 0) * 100:.1f}%"
            )

            # Show comparison to best if not accepted
            if record.comparison_to_best:
                sections.append(f"**Comparison:** {record.comparison_to_best}")
            sections.append("")

            # Only show THIS agent's changes
            if record.policy_changes:
                sections.append(f"**{agent_label} Changes:**")
                for change in record.policy_changes:
                    sections.append(f"  - {change}")
                sections.append("")

            # Show policy parameters at this iteration (single agent only)
            sections.append(f"**{agent_label} Parameters at this iteration:**")
            sections.append("```json")
            sections.append(json.dumps(record.policy.get("parameters", {}), indent=2))
            sections.append("```")
            sections.append("")

        return "\n".join(sections)

    def _build_parameter_trajectory_section(self) -> str:
        """Build parameter trajectory analysis (single agent only)."""
        if not self.context.iteration_history:
            return ""

        agent_label = self.context.agent_id or "Agent"
        sections = ["## 6. PARAMETER TRAJECTORIES", ""]

        # Get all parameter names from this agent's history
        all_params: set[str] = set()
        for record in self.context.iteration_history:
            all_params.update(record.policy.get("parameters", {}).keys())

        if not all_params:
            sections.append("*No parameters tracked across iterations.*")
            return "\n".join(sections)

        sections.append(
            f"Track how each {agent_label} parameter evolved across iterations:"
        )
        sections.append("")

        for param in sorted(all_params):
            trajectory = compute_parameter_trajectory(
                self.context.iteration_history, param
            )

            if trajectory:
                sections.append(f"### {param}")
                sections.append("")
                sections.append("| Iteration | Value |")
                sections.append("|-----------|-------|")
                for iteration, value in trajectory:
                    sections.append(f"| {iteration} | {value:.3f} |")
                sections.append("")

                # Trend analysis
                if len(trajectory) >= 2:
                    first_val = trajectory[0][1]
                    last_val = trajectory[-1][1]
                    if first_val != 0:
                        change_pct = ((last_val - first_val) / first_val) * 100
                        direction = "increased" if change_pct > 0 else "decreased"
                        sections.append(
                            f"*Overall: {direction} {abs(change_pct):.1f}% "
                            f"from {first_val:.3f} to {last_val:.3f}*"
                        )
                        sections.append("")

        return "\n".join(sections)

    def _build_final_instructions(self) -> str:
        """Build final instructions for the LLM (single agent focus)."""
        agent_label = self.context.agent_id or "Agent"

        # Count rejected policies
        rejected = [
            r for r in self.context.iteration_history if not r.was_accepted
        ]
        best_records = [r for r in self.context.iteration_history if r.is_best_so_far]

        rejected_warning = ""
        if rejected:
            rejected_warning = f"""
⚠️ **IMPORTANT**: {len(rejected)} previous policy attempts were REJECTED because they
performed worse than the current best. Review the rejected policies in the history
above and avoid making similar changes.
"""

        best_context = ""
        if best_records:
            best = best_records[-1]
            best_context = f"""
📌 **Current Best**: Iteration {best.iteration} with mean cost ${best.metrics.get('total_cost_mean', 0):,.0f}.
Your goal is to beat this. If your policy is worse, it will be rejected and we will
continue optimizing from the current best policy.
"""

        return f"""
## 7. FINAL INSTRUCTIONS

Based on the above analysis, generate an improved policy for **{agent_label}** that:

1. **Beats the current best policy** - your policy must have LOWER cost than the best
2. **Maintains 100% settlement rate** - this is non-negotiable
3. **Makes incremental adjustments** - avoid drastic changes unless clearly needed
4. **Learns from REJECTED policies** - don't repeat changes that made things worse
{rejected_warning}{best_context}
### What to Consider:

- **Simulation trace analysis**: What decisions in seed #{self.context.sample_seed} drove costs?
- **Cost breakdown**: Which cost types (delay, collateral, overdraft) dominate?
- **REJECTED policies**: Why did they fail? What changes should you avoid?
- **Parameter trends**: Which parameters correlate with cost improvements?
- **Trade-offs**: Balance delay costs vs collateral costs vs overdraft costs

### Output Requirements:

Generate a complete, valid policy JSON that:
- Defines all parameters before using them
- Uses only allowed fields and actions
- Includes unique node_id for every node
- Wraps arithmetic in {{"compute": {{...}}}}

Focus your changes on the areas with highest impact potential. Remember: if your
policy is worse than the current best, it will be REJECTED and you'll need to try
a different approach.
""".strip()


def build_single_agent_context(
    current_iteration: int,
    current_policy: dict[str, Any],
    current_metrics: dict[str, Any],
    iteration_history: list[SingleAgentIterationRecord] | None = None,
    # New unified naming
    simulation_trace: str | None = None,
    sample_seed: int = 0,
    sample_cost: int = 0,
    mean_cost: int = 0,
    cost_std: int = 0,
    # Deprecated parameters (backward compatibility)
    initial_simulation_output: str | None = None,  # noqa: ARG001 - deprecated
    best_seed_output: str | None = None,
    worst_seed_output: str | None = None,  # noqa: ARG001 - deprecated
    best_seed: int = 0,
    worst_seed: int = 0,  # noqa: ARG001 - deprecated
    best_seed_cost: int = 0,
    worst_seed_cost: int = 0,  # noqa: ARG001 - deprecated
    cost_breakdown: dict[str, int] | None = None,
    cost_rates: dict[str, Any] | None = None,
    agent_id: str | None = None,
) -> str:
    """Build an extended context prompt for SINGLE AGENT policy optimization.

    CRITICAL ISOLATION: This function creates a context that contains ONLY
    the specified agent's data. No other agent's policy, history, or metrics
    are included. This ensures the LLM optimizing one agent never sees
    information about other agents.

    Args:
        current_iteration: Current iteration number.
        current_policy: Current policy for THIS agent only.
        current_metrics: Aggregated metrics from current iteration.
        iteration_history: List of previous iteration records for THIS agent only.
        simulation_trace: Tick-by-tick event log from representative sample.
        sample_seed: Seed used for the representative sample.
        sample_cost: Cost from the representative sample.
        mean_cost: Mean cost across all samples.
        cost_std: Standard deviation of costs.
        cost_breakdown: Breakdown of costs by type.
        cost_rates: Cost rate configuration.
        agent_id: Identifier for this agent (e.g., "BANK_A").
        best_seed_output: Deprecated, use simulation_trace.
        best_seed: Deprecated, use sample_seed.
        best_seed_cost: Deprecated, use sample_cost.

    Returns:
        Complete extended context prompt string for single agent.

    Example:
        >>> prompt = build_single_agent_context(
        ...     current_iteration=5,
        ...     current_policy={"parameters": {"threshold": 4.5}},
        ...     current_metrics={"total_cost_mean": 12500},
        ...     agent_id="BANK_A",
        ... )
    """
    # Handle deprecated parameter names (backward compatibility)
    effective_trace = simulation_trace or best_seed_output
    effective_seed = sample_seed if sample_seed != 0 else best_seed
    effective_cost = sample_cost if sample_cost != 0 else best_seed_cost

    context = SingleAgentContext(
        agent_id=agent_id,
        current_iteration=current_iteration,
        current_policy=current_policy,
        current_metrics=current_metrics,
        iteration_history=iteration_history or [],
        simulation_trace=effective_trace,
        sample_seed=effective_seed,
        sample_cost=effective_cost,
        mean_cost=mean_cost,
        cost_std=cost_std,
        cost_breakdown=cost_breakdown or {},
        cost_rates=cost_rates or {},
    )

    builder = SingleAgentContextBuilder(context)
    return builder.build()
