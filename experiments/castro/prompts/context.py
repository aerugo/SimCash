"""Extended context builder for LLM policy optimization.

This module provides rich historical context for the LLM, including:
- Full tick-by-tick output from best and worst seeds
- Complete iteration history with metrics
- Policy changes between iterations (diffs)

The resulting prompts can be large (50k+ tokens) but are designed for
models with 200k+ token context windows.

Best practices for agentic applications:
1. Structure data hierarchically with clear section headers
2. Use consistent formatting (markdown tables, JSON blocks)
3. Put most important information first (recency bias)
4. Include explicit reasoning guidance
5. Provide concrete examples from actual runs
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ============================================================================
# Data Structures for Context
# ============================================================================


@dataclass
class IterationRecord:
    """Record of a single iteration's results and policy changes.

    Tracks both successful improvements and rejected policies to provide
    the LLM with complete history of what worked and what didn't.
    """

    iteration: int
    metrics: dict[str, Any]
    policy_a: dict[str, Any]
    policy_b: dict[str, Any]
    policy_a_changes: list[str] = field(default_factory=list)
    policy_b_changes: list[str] = field(default_factory=list)
    # New fields for tracking policy acceptance
    was_accepted: bool = True  # False if policy was rejected (worse than best)
    is_best_so_far: bool = False  # True if this is the best policy discovered
    comparison_to_best: str = ""  # Human-readable comparison to best policy


@dataclass
class SimulationContext:
    """Complete context for policy optimization."""

    # Current state
    current_iteration: int
    current_policy_a: dict[str, Any]
    current_policy_b: dict[str, Any]
    current_metrics: dict[str, Any]

    # Historical data
    iteration_history: list[IterationRecord] = field(default_factory=list)

    # Verbose output from last run (best and worst seeds)
    best_seed_output: str | None = None
    worst_seed_output: str | None = None
    best_seed: int = 0
    worst_seed: int = 0
    best_seed_cost: int = 0
    worst_seed_cost: int = 0

    # Cost breakdown for analysis
    cost_breakdown: dict[str, int] = field(default_factory=dict)

    # Configuration context
    cost_rates: dict[str, Any] = field(default_factory=dict)
    ticks_per_day: int = 100


# ============================================================================
# Policy Diff Computation
# ============================================================================


def compute_policy_diff(old_policy: dict[str, Any], new_policy: dict[str, Any]) -> list[str]:
    """Compute human-readable differences between two policies.

    Returns a list of change descriptions.
    """
    changes: list[str] = []

    # Compare parameters
    old_params = old_policy.get("parameters", {})
    new_params = new_policy.get("parameters", {})

    # Added parameters
    for key in set(new_params.keys()) - set(old_params.keys()):
        changes.append(f"Added parameter '{key}' = {new_params[key]}")

    # Removed parameters
    for key in set(old_params.keys()) - set(new_params.keys()):
        changes.append(f"Removed parameter '{key}' (was {old_params[key]})")

    # Changed parameters
    for key in set(old_params.keys()) & set(new_params.keys()):
        if old_params[key] != new_params[key]:
            delta = new_params[key] - old_params[key]
            direction = "↑" if delta > 0 else "↓"
            changes.append(
                f"Changed '{key}': {old_params[key]} → {new_params[key]} ({direction}{abs(delta):.2f})"
            )

    # Compare tree structure (simplified - check if trees are different)
    old_tree = json.dumps(old_policy.get("payment_tree", {}), sort_keys=True)
    new_tree = json.dumps(new_policy.get("payment_tree", {}), sort_keys=True)
    if old_tree != new_tree:
        changes.append("Modified payment_tree structure")

    # Compare collateral tree if present
    old_coll = json.dumps(old_policy.get("strategic_collateral_tree", {}), sort_keys=True)
    new_coll = json.dumps(new_policy.get("strategic_collateral_tree", {}), sort_keys=True)
    if old_coll != new_coll:
        changes.append("Modified strategic_collateral_tree structure")

    if not changes:
        changes.append("No changes from previous iteration")

    return changes


def compute_parameter_trajectory(history: list[IterationRecord], param_name: str) -> list[tuple[int, float]]:
    """Extract the trajectory of a parameter value across iterations."""
    trajectory = []
    for record in history:
        # Check both policies
        for policy in [record.policy_a, record.policy_b]:
            params = policy.get("parameters", {})
            if param_name in params:
                trajectory.append((record.iteration, params[param_name]))
                break  # One value per iteration
    return trajectory


# ============================================================================
# Context Prompt Builder
# ============================================================================


class ExtendedContextBuilder:
    """Builds massive context prompts for policy optimization.

    This builder creates structured prompts that include:
    1. Current state summary (most important, shown first)
    2. Verbose simulation output (tick-by-tick for debugging)
    3. Full iteration history with metrics and changes
    4. Analytical insights and optimization guidance

    The prompt is designed for models with 200k+ token context windows.
    """

    def __init__(self, context: SimulationContext) -> None:
        """Initialize the builder with simulation context."""
        self.context = context

    def build(self) -> str:
        """Build the complete extended context prompt.

        Returns:
            A structured markdown prompt with all context.
        """
        sections = [
            self._build_header(),
            self._build_current_state_summary(),
            self._build_cost_analysis(),
            self._build_optimization_guidance(),
            self._build_simulation_output_section(),
            self._build_iteration_history_section(),
            self._build_parameter_trajectory_section(),
            self._build_final_instructions(),
        ]

        return "\n\n".join(section for section in sections if section)

    def _build_header(self) -> str:
        """Build the header section."""
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POLICY OPTIMIZATION CONTEXT - ITERATION {self.context.current_iteration}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This document provides complete context for optimizing payment policies.
Analyze the simulation outputs and historical data to identify improvements.

TABLE OF CONTENTS:
1. Current State Summary
2. Cost Analysis
3. Optimization Guidance
4. Simulation Output (Best/Worst Seeds)
5. Full Iteration History
6. Parameter Trajectories
7. Final Instructions
""".strip()

    def _build_current_state_summary(self) -> str:
        """Build the current state summary section."""
        m = self.context.current_metrics
        cost_delta = ""
        if self.context.iteration_history:
            prev_cost = self.context.iteration_history[-1].metrics.get("total_cost_mean", 0)
            if prev_cost > 0:
                delta = m.get("total_cost_mean", 0) - prev_cost
                pct = (delta / prev_cost) * 100
                direction = "↑" if delta > 0 else "↓"
                cost_delta = f" ({direction}{abs(pct):.1f}% from previous)"

        return f"""
## 1. CURRENT STATE SUMMARY

### Performance Metrics (Iteration {self.context.current_iteration})

| Metric | Value |
|--------|-------|
| **Mean Total Cost** | ${m.get('total_cost_mean', 0):,.0f}{cost_delta} |
| **Cost Std Dev** | ±${m.get('total_cost_std', 0):,.0f} |
| **Risk-Adjusted Cost** | ${m.get('risk_adjusted_cost', 0):,.0f} |
| **Settlement Rate** | {m.get('settlement_rate_mean', 0) * 100:.1f}% |
| **Failure Rate** | {m.get('failure_rate', 0) * 100:.0f}% |
| **Best Seed** | #{self.context.best_seed} (${self.context.best_seed_cost:,}) |
| **Worst Seed** | #{self.context.worst_seed} (${self.context.worst_seed_cost:,}) |

### Current Policy Parameters

**Bank A:**
```json
{json.dumps(self.context.current_policy_a.get('parameters', {}), indent=2)}
```

**Bank B:**
```json
{json.dumps(self.context.current_policy_b.get('parameters', {}), indent=2)}
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
        for i, (cost_type, amount) in enumerate(sorted_costs):
            pct = (amount / total) * 100
            priority = "🔴 HIGH" if pct > 40 else ("🟡 MEDIUM" if pct > 20 else "🟢 LOW")
            lines.append(f"| {cost_type} | ${amount:,} | {pct:.1f}% | {priority} |")

        # Add cost rates context
        if self.context.cost_rates:
            lines.extend([
                "",
                "### Cost Rate Configuration",
                "```json",
                json.dumps(self.context.cost_rates, indent=2),
                "```",
            ])

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
            if all(recent_costs[i] <= recent_costs[i - 1] for i in range(1, len(recent_costs))):
                guidance.append(
                    "✅ **IMPROVING TREND** - Costs decreasing consistently. "
                    "Continue current optimization direction."
                )
            elif all(recent_costs[i] >= recent_costs[i - 1] for i in range(1, len(recent_costs))):
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

        if not guidance[2:]:  # Only header
            guidance.append("No specific issues detected. Focus on incremental improvements.")

        return "\n\n".join(guidance)

    def _build_simulation_output_section(self) -> str:
        """Build the simulation output section with tick-by-tick logs."""
        sections = ["## 4. SIMULATION OUTPUT (TICK-BY-TICK)", ""]

        # Best seed output
        if self.context.best_seed_output:
            sections.extend([
                f"### Best Performing Seed (#{self.context.best_seed}, Cost: ${self.context.best_seed_cost:,})",
                "",
                "This is the OPTIMAL outcome from the current policy. Analyze what went right.",
                "",
                "<best_seed_output>",
                "```",
                self.context.best_seed_output,
                "```",
                "</best_seed_output>",
                "",
            ])

        # Worst seed output
        if self.context.worst_seed_output:
            sections.extend([
                f"### Worst Performing Seed (#{self.context.worst_seed}, Cost: ${self.context.worst_seed_cost:,})",
                "",
                "This is the PROBLEMATIC outcome. Identify failure patterns and edge cases.",
                "",
                "<worst_seed_output>",
                "```",
                self.context.worst_seed_output,
                "```",
                "</worst_seed_output>",
                "",
            ])

        if not self.context.best_seed_output and not self.context.worst_seed_output:
            sections.append("*No verbose output available for this iteration.*")

        return "\n".join(sections)

    def _build_iteration_history_section(self) -> str:
        """Build the complete iteration history section.

        Includes acceptance status for each policy attempt, highlighting
        which policies improved performance and which were rejected.
        """
        sections = ["## 5. FULL ITERATION HISTORY", ""]

        if not self.context.iteration_history:
            sections.append("*No previous iterations.*")
            return "\n".join(sections)

        # Summary table with acceptance status
        sections.append("### Metrics Summary Table")
        sections.append("")
        sections.append("| Iter | Status | Mean Cost | Std Dev | Settlement | Best Seed | Worst Seed |")
        sections.append("|------|--------|-----------|---------|------------|-----------|------------|")

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
            sections.extend([
                "",
                "### Current Best Policy",
                f"The best policy so far was discovered in **iteration {best.iteration}** "
                f"with mean cost **${best.metrics.get('total_cost_mean', 0):,.0f}**.",
                "",
            ])

        # Detailed changes per iteration
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

            sections.append(f"#### {status_emoji} Iteration {record.iteration} ({status_text})")
            sections.append("")

            m = record.metrics
            sections.append(f"**Performance:** Mean cost ${m.get('total_cost_mean', 0):,.0f}, "
                          f"Settlement {m.get('settlement_rate_mean', 0) * 100:.1f}%")

            # Show comparison to best if not accepted
            if record.comparison_to_best:
                sections.append(f"**Comparison:** {record.comparison_to_best}")
            sections.append("")

            if record.policy_a_changes:
                sections.append("**Bank A Changes:**")
                for change in record.policy_a_changes:
                    sections.append(f"  - {change}")
                sections.append("")

            if record.policy_b_changes:
                sections.append("**Bank B Changes:**")
                for change in record.policy_b_changes:
                    sections.append(f"  - {change}")
                sections.append("")

            # Show policy parameters at this iteration
            sections.append("**Parameters at this iteration:**")
            sections.append("```json")
            sections.append(json.dumps({
                "bank_a": record.policy_a.get("parameters", {}),
                "bank_b": record.policy_b.get("parameters", {}),
            }, indent=2))
            sections.append("```")
            sections.append("")

        return "\n".join(sections)

    def _build_parameter_trajectory_section(self) -> str:
        """Build parameter trajectory analysis."""
        if not self.context.iteration_history:
            return ""

        sections = ["## 6. PARAMETER TRAJECTORIES", ""]

        # Get all parameter names
        all_params = set()
        for record in self.context.iteration_history:
            all_params.update(record.policy_a.get("parameters", {}).keys())
            all_params.update(record.policy_b.get("parameters", {}).keys())

        if not all_params:
            sections.append("*No parameters tracked across iterations.*")
            return "\n".join(sections)

        sections.append("Track how each parameter evolved across iterations:")
        sections.append("")

        for param in sorted(all_params):
            trajectory = compute_parameter_trajectory(self.context.iteration_history, param)
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
                        sections.append(f"*Overall: {direction} {abs(change_pct):.1f}% from {first_val:.3f} to {last_val:.3f}*")
                        sections.append("")

        return "\n".join(sections)

    def _build_final_instructions(self) -> str:
        """Build final instructions for the LLM."""
        # Count rejected policies
        rejected = [r for r in self.context.iteration_history if not r.was_accepted]
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

Based on the above analysis, generate an improved policy that:

1. **Beats the current best policy** - your policy must have LOWER cost than the best
2. **Maintains 100% settlement rate** - this is non-negotiable
3. **Makes incremental adjustments** - avoid drastic changes unless clearly needed
4. **Learns from REJECTED policies** - don't repeat changes that made things worse
{rejected_warning}{best_context}
### What to Consider:

- **Best seed analysis**: What made seed #{self.context.best_seed} perform well?
- **Worst seed analysis**: What went wrong in seed #{self.context.worst_seed}?
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


# ============================================================================
# Convenience Function
# ============================================================================


def build_extended_context(
    current_iteration: int,
    current_policy_a: dict[str, Any],
    current_policy_b: dict[str, Any],
    current_metrics: dict[str, Any],
    iteration_history: list[IterationRecord] | None = None,
    best_seed_output: str | None = None,
    worst_seed_output: str | None = None,
    best_seed: int = 0,
    worst_seed: int = 0,
    best_seed_cost: int = 0,
    worst_seed_cost: int = 0,
    cost_breakdown: dict[str, int] | None = None,
    cost_rates: dict[str, Any] | None = None,
) -> str:
    """Build an extended context prompt for policy optimization.

    Args:
        current_iteration: Current iteration number
        current_policy_a: Current policy for Bank A
        current_policy_b: Current policy for Bank B
        current_metrics: Aggregated metrics from current iteration
        iteration_history: List of all previous iteration records
        best_seed_output: Verbose tick-by-tick output from best seed
        worst_seed_output: Verbose tick-by-tick output from worst seed
        best_seed: Best performing seed number
        worst_seed: Worst performing seed number
        best_seed_cost: Cost from best seed
        worst_seed_cost: Cost from worst seed
        cost_breakdown: Breakdown of costs by type
        cost_rates: Cost rate configuration

    Returns:
        Complete extended context prompt string
    """
    context = SimulationContext(
        current_iteration=current_iteration,
        current_policy_a=current_policy_a,
        current_policy_b=current_policy_b,
        current_metrics=current_metrics,
        iteration_history=iteration_history or [],
        best_seed_output=best_seed_output,
        worst_seed_output=worst_seed_output,
        best_seed=best_seed,
        worst_seed=worst_seed,
        best_seed_cost=best_seed_cost,
        worst_seed_cost=worst_seed_cost,
        cost_breakdown=cost_breakdown or {},
        cost_rates=cost_rates or {},
    )

    builder = ExtendedContextBuilder(context)
    return builder.build()


# ============================================================================
# Single-Agent Isolated Context (CRITICAL FOR LLM ISOLATION)
# ============================================================================


@dataclass
class SingleAgentIterationRecord:
    """Record of a single iteration for ONE agent only.

    CRITICAL: This dataclass contains NO information about other agents.
    Each agent sees only its own policy history and changes.
    """

    iteration: int
    metrics: dict[str, Any]
    policy: dict[str, Any]  # Only this agent's policy
    policy_changes: list[str] = field(default_factory=list)  # Only this agent's changes
    was_accepted: bool = True
    is_best_so_far: bool = False
    comparison_to_best: str = ""


@dataclass
class SingleAgentContext:
    """Complete context for policy optimization of a SINGLE agent.

    CRITICAL ISOLATION: This context contains ONLY the specified agent's data.
    No other agent's policy, history, or metrics are included.
    """

    # Agent identification
    agent_id: str | None = None

    # Current state (single agent only)
    current_iteration: int = 0
    current_policy: dict[str, Any] = field(default_factory=dict)
    current_metrics: dict[str, Any] = field(default_factory=dict)

    # Historical data (single agent only)
    iteration_history: list[SingleAgentIterationRecord] = field(default_factory=list)

    # Verbose output from last run (filtered for this agent only)
    best_seed_output: str | None = None
    worst_seed_output: str | None = None
    best_seed: int = 0
    worst_seed: int = 0
    best_seed_cost: int = 0
    worst_seed_cost: int = 0

    # Cost breakdown for analysis
    cost_breakdown: dict[str, int] = field(default_factory=dict)

    # Configuration context
    cost_rates: dict[str, Any] = field(default_factory=dict)
    ticks_per_day: int = 100


class SingleAgentContextBuilder:
    """Builds context prompts for SINGLE AGENT policy optimization.

    CRITICAL ISOLATION: This builder creates prompts that contain ONLY
    the specified agent's data. No cross-agent information leakage.

    The prompt is designed for models with 200k+ token context windows.
    """

    def __init__(self, context: SingleAgentContext) -> None:
        """Initialize the builder with single-agent context."""
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
            self._build_simulation_output_section(),
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
4. Simulation Output (Best/Worst Seeds)
5. Full Iteration History
6. Parameter Trajectories
7. Final Instructions
""".strip()

    def _build_current_state_summary(self) -> str:
        """Build the current state summary section (single agent only)."""
        m = self.context.current_metrics
        cost_delta = ""
        if self.context.iteration_history:
            prev_cost = self.context.iteration_history[-1].metrics.get("total_cost_mean", 0)
            if prev_cost > 0:
                delta = m.get("total_cost_mean", 0) - prev_cost
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
| **Cost Std Dev** | ±${m.get('total_cost_std', 0):,.0f} |
| **Risk-Adjusted Cost** | ${m.get('risk_adjusted_cost', 0):,.0f} |
| **Settlement Rate** | {m.get('settlement_rate_mean', 0) * 100:.1f}% |
| **Failure Rate** | {m.get('failure_rate', 0) * 100:.0f}% |
| **Best Seed** | #{self.context.best_seed} (${self.context.best_seed_cost:,}) |
| **Worst Seed** | #{self.context.worst_seed} (${self.context.worst_seed_cost:,}) |

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
        for i, (cost_type, amount) in enumerate(sorted_costs):
            pct = (amount / total) * 100
            priority = "🔴 HIGH" if pct > 40 else ("🟡 MEDIUM" if pct > 20 else "🟢 LOW")
            lines.append(f"| {cost_type} | ${amount:,} | {pct:.1f}% | {priority} |")

        # Add cost rates context
        if self.context.cost_rates:
            lines.extend([
                "",
                "### Cost Rate Configuration",
                "```json",
                json.dumps(self.context.cost_rates, indent=2),
                "```",
            ])

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
            if all(recent_costs[i] <= recent_costs[i - 1] for i in range(1, len(recent_costs))):
                guidance.append(
                    "✅ **IMPROVING TREND** - Costs decreasing consistently. "
                    "Continue current optimization direction."
                )
            elif all(recent_costs[i] >= recent_costs[i - 1] for i in range(1, len(recent_costs))):
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

        if not guidance[2:]:  # Only header
            guidance.append("No specific issues detected. Focus on incremental improvements.")

        return "\n\n".join(guidance)

    def _build_simulation_output_section(self) -> str:
        """Build the simulation output section with tick-by-tick logs."""
        sections = ["## 4. SIMULATION OUTPUT (TICK-BY-TICK)", ""]

        # Best seed output
        if self.context.best_seed_output:
            sections.extend([
                f"### Best Performing Seed (#{self.context.best_seed}, Cost: ${self.context.best_seed_cost:,})",
                "",
                "This is the OPTIMAL outcome from the current policy. Analyze what went right.",
                "",
                "<best_seed_output>",
                "```",
                self.context.best_seed_output,
                "```",
                "</best_seed_output>",
                "",
            ])

        # Worst seed output
        if self.context.worst_seed_output:
            sections.extend([
                f"### Worst Performing Seed (#{self.context.worst_seed}, Cost: ${self.context.worst_seed_cost:,})",
                "",
                "This is the PROBLEMATIC outcome. Identify failure patterns and edge cases.",
                "",
                "<worst_seed_output>",
                "```",
                self.context.worst_seed_output,
                "```",
                "</worst_seed_output>",
                "",
            ])

        if not self.context.best_seed_output and not self.context.worst_seed_output:
            sections.append("*No verbose output available for this iteration.*")

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
        sections.append("| Iter | Status | Mean Cost | Std Dev | Settlement | Best Seed | Worst Seed |")
        sections.append("|------|--------|-----------|---------|------------|-----------|------------|")

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
            sections.extend([
                "",
                "### Current Best Policy",
                f"The best policy so far was discovered in **iteration {best.iteration}** "
                f"with mean cost **${best.metrics.get('total_cost_mean', 0):,.0f}**.",
                "",
            ])

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

            sections.append(f"#### {status_emoji} Iteration {record.iteration} ({status_text})")
            sections.append("")

            m = record.metrics
            sections.append(f"**Performance:** Mean cost ${m.get('total_cost_mean', 0):,.0f}, "
                          f"Settlement {m.get('settlement_rate_mean', 0) * 100:.1f}%")

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

        sections.append(f"Track how each {agent_label} parameter evolved across iterations:")
        sections.append("")

        for param in sorted(all_params):
            trajectory = []
            for record in self.context.iteration_history:
                params = record.policy.get("parameters", {})
                if param in params:
                    trajectory.append((record.iteration, params[param]))

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
                        sections.append(f"*Overall: {direction} {abs(change_pct):.1f}% from {first_val:.3f} to {last_val:.3f}*")
                        sections.append("")

        return "\n".join(sections)

    def _build_final_instructions(self) -> str:
        """Build final instructions for the LLM (single agent focus)."""
        agent_label = self.context.agent_id or "Agent"

        # Count rejected policies
        rejected = [r for r in self.context.iteration_history if not r.was_accepted]
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

- **Best seed analysis**: What made seed #{self.context.best_seed} perform well?
- **Worst seed analysis**: What went wrong in seed #{self.context.worst_seed}?
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
    best_seed_output: str | None = None,
    worst_seed_output: str | None = None,
    best_seed: int = 0,
    worst_seed: int = 0,
    best_seed_cost: int = 0,
    worst_seed_cost: int = 0,
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
        current_iteration: Current iteration number
        current_policy: Current policy for THIS agent only
        current_metrics: Aggregated metrics from current iteration
        iteration_history: List of previous iteration records for THIS agent only
        best_seed_output: Verbose tick-by-tick output from best seed (filtered for this agent)
        worst_seed_output: Verbose tick-by-tick output from worst seed (filtered for this agent)
        best_seed: Best performing seed number
        worst_seed: Worst performing seed number
        best_seed_cost: Cost from best seed
        worst_seed_cost: Cost from worst seed
        cost_breakdown: Breakdown of costs by type
        cost_rates: Cost rate configuration
        agent_id: Identifier for this agent (e.g., "BANK_A")

    Returns:
        Complete extended context prompt string for single agent
    """
    context = SingleAgentContext(
        agent_id=agent_id,
        current_iteration=current_iteration,
        current_policy=current_policy,
        current_metrics=current_metrics,
        iteration_history=iteration_history or [],
        best_seed_output=best_seed_output,
        worst_seed_output=worst_seed_output,
        best_seed=best_seed,
        worst_seed=worst_seed,
        best_seed_cost=best_seed_cost,
        worst_seed_cost=worst_seed_cost,
        cost_breakdown=cost_breakdown or {},
        cost_rates=cost_rates or {},
    )

    builder = SingleAgentContextBuilder(context)
    return builder.build()
