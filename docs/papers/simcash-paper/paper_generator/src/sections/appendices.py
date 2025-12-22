"""Appendices section generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from payment_simulator.ai_cash_mgmt.prompts.system_prompt_builder import (
    get_checklist,
    get_cost_objectives,
    get_domain_explanation,
    get_expert_introduction,
    get_final_instructions,
    get_optimization_process,
)

from src.latex.figures import include_figure
from src.latex.formatting import format_money, format_percent, format_verbatim_text
from src.latex.tables import (
    generate_iteration_table,
    generate_results_summary_table,
)

if TYPE_CHECKING:
    from src.data_provider import DataProvider

# Chart paths relative to output directory
CHARTS_DIR = "charts"


def generate_appendices(provider: DataProvider) -> str:
    """Generate the appendices section.

    Args:
        provider: DataProvider instance for accessing experiment data

    Returns:
        LaTeX string for the appendices
    """
    # Generate detailed tables for all experiments and passes
    appendix_sections = []

    # Appendix A: Results Summary
    results_summary = _generate_results_summary_appendix(provider)
    appendix_sections.append(results_summary)

    # Appendix B: Experiment 1 Detailed Results
    exp1_content = _generate_experiment_appendix(
        provider,
        exp_id="exp1",
        title="Experiment 1: Asymmetric Scenario",
        label_prefix="exp1",
    )
    appendix_sections.append(exp1_content)

    # Appendix C: Experiment 2 Detailed Results
    exp2_content = _generate_experiment_appendix(
        provider,
        exp_id="exp2",
        title="Experiment 2: Stochastic Environment",
        label_prefix="exp2",
    )
    appendix_sections.append(exp2_content)

    # Appendix D: Experiment 3 Detailed Results
    exp3_content = _generate_experiment_appendix(
        provider,
        exp_id="exp3",
        title="Experiment 3: Symmetric Scenario",
        label_prefix="exp3",
    )
    appendix_sections.append(exp3_content)

    # Appendix E: System Prompt Documentation
    system_prompt_doc = _generate_system_prompt_appendix(provider)
    appendix_sections.append(system_prompt_doc)

    all_content = "\n\n".join(appendix_sections)

    return rf"""
\appendix

{all_content}
"""


def _generate_results_summary_appendix(provider: DataProvider) -> str:
    """Generate appendix section with comprehensive results summary.

    Args:
        provider: DataProvider instance

    Returns:
        LaTeX string for results summary appendix
    """
    # Get all pass summaries
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Generate comprehensive table
    summary_table = generate_results_summary_table(
        exp1_summaries,
        exp2_summaries,
        exp3_summaries,
        caption="Complete results summary across all experiments and passes",
        label="tab:results_summary",
    )

    # Calculate total passes for summary text
    total_passes = len(exp1_summaries) + len(exp2_summaries) + len(exp3_summaries)

    return rf"""
\section{{Results Summary}}
\label{{app:results_summary}}

This appendix provides a comprehensive summary of all experimental results
across {total_passes} passes ({len(exp1_summaries)} per experiment). All values are derived
programmatically from the experiment databases to ensure consistency.

{summary_table}
"""


def _generate_experiment_appendix(
    provider: DataProvider,
    exp_id: str,
    title: str,
    label_prefix: str,
) -> str:
    """Generate appendix section for one experiment with all passes.

    Args:
        provider: DataProvider instance
        exp_id: Experiment identifier (exp1, exp2, exp3)
        title: Section title
        label_prefix: Prefix for LaTeX labels

    Returns:
        LaTeX string for this experiment's appendix
    """
    pass_sections = []

    for pass_num in [1, 2, 3]:
        results = provider.get_iteration_results(exp_id, pass_num=pass_num)
        if results:
            # Generate convergence chart figure with [H] to prevent floating
            # [H] from float package forces figure to stay exactly here
            figure = include_figure(
                path=f"{CHARTS_DIR}/{exp_id}_pass{pass_num}_combined.png",
                caption=f"{title} - Pass {pass_num} convergence",
                label=f"fig:{label_prefix}_pass{pass_num}_convergence",
                width=0.85,
                position="H",  # Force figure to stay in place, don't float
            )

            # Generate table (may use longtable for long experiments)
            # Use position="H" to prevent floating in appendices
            table = generate_iteration_table(
                results,
                caption=f"{title} - Pass {pass_num}",
                label=f"tab:{label_prefix}_pass{pass_num}",
                position="H",  # Force table to stay in place
            )

            # Figure before table helps LaTeX place floats correctly
            pass_sections.append(f"\\subsection{{Pass {pass_num}}}\n\n{figure}\n\n{table}")

    content = "\n\n".join(pass_sections)

    return rf"""
\section{{{title} - Detailed Results}}
\label{{app:{label_prefix}}}

This appendix provides iteration-by-iteration results and convergence charts for
all three passes of {title.lower()}.

{content}
"""


def _format_policy_constraints(config: dict) -> str:
    """Format policy constraints section from experiment config.

    Args:
        config: Experiment configuration dict with policy_constraints key

    Returns:
        Formatted text for verbatim display
    """
    constraints = config.get("policy_constraints", {})
    lines = ["### ALLOWED PARAMETERS", "", "Define these in the `parameters` object:", ""]

    for param in constraints.get("allowed_parameters", []):
        param_type = param.get("param_type", "unknown")
        min_val = param.get("min_value", "")
        max_val = param.get("max_value", "")
        desc = param.get("description", "")
        range_str = f"{min_val} to {max_val}" if min_val != "" and max_val != "" else ""
        lines.append(f"  {param['name']} ({param_type}): {range_str}")
        if desc:
            lines.append(f"    {desc}")
        lines.append("")

    lines.append("### ALLOWED FIELDS")
    lines.append("")
    lines.append('Reference with {"field": "name"}:')
    lines.append("")

    for field in constraints.get("allowed_fields", []):
        lines.append(f"  - {field}")

    lines.append("")
    lines.append("### ALLOWED ACTIONS BY TREE TYPE")
    lines.append("")

    for tree_type, actions in constraints.get("allowed_actions", {}).items():
        actions_str = ", ".join(actions)
        lines.append(f"  {tree_type}:  {actions_str}")

    return "\n".join(lines)


def _format_cost_parameters(scenario_config: dict) -> str:
    """Format cost parameters section from scenario config.

    Args:
        scenario_config: Scenario configuration dict with cost_rates key

    Returns:
        Formatted text for verbatim display
    """
    cost_rates = scenario_config.get("cost_rates", {})
    ticks = scenario_config.get("simulation", {}).get("ticks_per_day", 12)

    lines = ["## COST PARAMETERS", "", "Per-Tick Costs:"]

    liq_cost = cost_rates.get("liquidity_cost_per_tick_bps", 0)
    lines.append(f"  - liquidity_cost_per_tick_bps: {liq_cost} (0.1 / {ticks} ticks)")

    delay_cost = cost_rates.get("delay_cost_per_tick_per_cent", 0)
    lines.append(f"  - delay_cost_per_tick_per_cent: {delay_cost}")

    lines.append("")
    lines.append("One-Time Costs:")

    deadline = cost_rates.get("deadline_penalty", 0)
    lines.append(f"  - deadline_penalty: {deadline:,} cents")

    eod = cost_rates.get("eod_penalty_per_transaction", 0)
    lines.append(f"  - eod_penalty_per_transaction: {eod:,} cents")

    lines.append("")
    lines.append("Disabled in this scenario:")

    overdraft = cost_rates.get("overdraft_bps_per_tick", 0)
    lines.append(f"  - overdraft_bps_per_tick: {overdraft} (hard liquidity constraint)")

    collateral = cost_rates.get("collateral_cost_per_tick_bps", 0)
    lines.append(f"  - collateral_cost_per_tick_bps: {collateral} (using liquidity_pool mode)")

    return "\n".join(lines)


def _extract_user_prompt_sections(user_prompt: str) -> dict:
    """Extract key sections from a user prompt for display.

    Args:
        user_prompt: Full user prompt text

    Returns:
        Dict with extracted sections: header, cost_analysis, history, instructions, trace
    """
    sections = {}

    # Extract header and current state summary (first major section)
    header_end = user_prompt.find("## 2.")
    if header_end > 0:
        sections["current_state"] = user_prompt[:header_end].strip()

    # Extract cost analysis section
    cost_start = user_prompt.find("## 2. COST ANALYSIS")
    cost_end = user_prompt.find("## 3.")
    if cost_start > 0 and cost_end > cost_start:
        sections["cost_analysis"] = user_prompt[cost_start:cost_end].strip()

    # Extract simulation trace (inside <simulation_trace> tags)
    trace_start = user_prompt.find("<simulation_trace>")
    trace_end = user_prompt.find("</simulation_trace>")
    if trace_start > 0 and trace_end > trace_start:
        # Extract content between tags, remove the ``` markers
        trace_content = user_prompt[trace_start + len("<simulation_trace>") : trace_end]
        trace_content = trace_content.strip()
        if trace_content.startswith("```"):
            trace_content = trace_content[3:]
        if trace_content.endswith("```"):
            trace_content = trace_content[:-3]
        sections["simulation_trace"] = trace_content.strip()

    # Extract iteration history and parameter trajectories (sections 5-6)
    history_start = user_prompt.find("## 5. FULL ITERATION HISTORY")
    history_end = user_prompt.find("## 7.")
    if history_start > 0 and history_end > history_start:
        sections["history"] = user_prompt[history_start:history_end].strip()

    # Extract final instructions (section 7 to end)
    instructions_start = user_prompt.find("## 7. FINAL INSTRUCTIONS")
    if instructions_start > 0:
        sections["instructions"] = user_prompt[instructions_start:].strip()

    return sections


def _generate_system_prompt_appendix(provider: DataProvider) -> str:
    """Generate appendix section documenting the LLM system prompt.

    This section includes the actual prompt text used to guide LLM agents
    during policy optimization. All content is loaded programmatically:
    - Static sections from the codebase (system_prompt_builder.py)
    - Dynamic sections from experiment configs (exp2.yaml, exp2_12period.yaml)
    - User prompt examples from the experiment database

    Args:
        provider: DataProvider instance for accessing experiment data and configs

    Returns:
        LaTeX string for the system prompt appendix
    """
    # Get static prompt sections from the codebase
    # Note: LSM is disabled in all paper experiments (exp1, exp2, exp3)
    expert_intro = format_verbatim_text(get_expert_introduction())
    domain_explanation = format_verbatim_text(get_domain_explanation(lsm_enabled=False))
    cost_objectives = format_verbatim_text(get_cost_objectives())
    optimization_process = format_verbatim_text(get_optimization_process())
    checklist = format_verbatim_text(get_checklist())
    final_instructions = format_verbatim_text(get_final_instructions())

    # Load dynamic sections from exp2 configuration
    exp2_config = provider.get_experiment_config("exp2")
    exp2_scenario = provider.get_scenario_config("exp2")

    # Get experiment customization text
    prompt_customization = exp2_config.get("prompt_customization", {}).get("all", "")
    customization_text = (
        "################################################################################\n"
        "#                       EXPERIMENT CUSTOMIZATION                               #\n"
        "################################################################################\n\n"
        f"{prompt_customization.strip()}\n\n"
        "################################################################################"
    )

    # Format policy constraints
    policy_constraints_text = _format_policy_constraints(exp2_config)

    # Format cost parameters
    cost_params_text = _format_cost_parameters(exp2_scenario)

    # Get user prompt from database (exp2, pass 2, iteration 5, BANK_A)
    # Note: Database iteration 5 contains the prompt for generating iteration 6 policy
    user_prompt = provider.get_user_prompt("exp2", pass_num=2, iteration=5, agent_id="BANK_A")
    user_prompt_sections = _extract_user_prompt_sections(user_prompt or "")

    # Extract sections for display
    current_state = user_prompt_sections.get("current_state", "")
    cost_analysis = user_prompt_sections.get("cost_analysis", "")
    history = user_prompt_sections.get("history", "")
    instructions = user_prompt_sections.get("instructions", "")

    # Get simulation trace from exp2 simulation_events table
    # The events are stored in the database even though they weren't captured in prompts
    simulation_trace = provider.get_simulation_trace("exp2", pass_num=2, max_events=40)

    return rf"""
\section{{LLM System Prompt Documentation}}
\label{{app:system_prompt}}

This appendix documents the system prompt provided to LLM agents during policy
optimization. The content is extracted programmatically from the SimCash codebase
to ensure this documentation remains synchronized with the actual implementation.

The system prompt establishes the agent's role, provides domain context, and
specifies the format requirements for policy proposals. Additional sections
(policy schema, cost rates, and constraint-specific guidance) are injected
dynamically based on experiment configuration.

\subsection{{Expert Introduction}}

The prompt begins by establishing the agent's role as a payment system optimization expert:

\begin{{verbatim}}
{expert_intro}
\end{{verbatim}}

\subsection{{Domain Context}}

The agent receives detailed context about RTGS settlement mechanics:

\begin{{verbatim}}
{domain_explanation}
\end{{verbatim}}

\subsection{{Cost Structure and Objectives}}

The optimization objective and cost components are explained:

\begin{{verbatim}}
{cost_objectives}
\end{{verbatim}}

\subsection{{Optimization Process}}

The iterative optimization workflow is described:

\begin{{verbatim}}
{optimization_process}
\end{{verbatim}}

\subsection{{Pre-Generation Checklist}}

Before generating policies, agents must verify compliance:

\begin{{verbatim}}
{checklist}
\end{{verbatim}}

\subsection{{Final Instructions}}

The prompt concludes with output requirements:

\begin{{verbatim}}
{final_instructions}
\end{{verbatim}}

\subsection{{Dynamic Sections}}

The following sections are injected dynamically based on experiment configuration.
We show examples from Experiment 2 (12-Period Stochastic) to illustrate the content.

\subsubsection{{Experiment Customization (Exp 2)}}

Each experiment can provide scenario-specific guidance:

\begin{{verbatim}}
{customization_text}
\end{{verbatim}}

\subsubsection{{Policy Constraints (Exp 2)}}

The policy schema is filtered to show only allowed elements:

\begin{{verbatim}}
{policy_constraints_text}
\end{{verbatim}}

\subsubsection{{Cost Parameters (Exp 2)}}

Current cost rates from the experiment configuration:

\begin{{verbatim}}
{cost_params_text}
\end{{verbatim}}

\subsection{{User Prompt Example (Exp 2, Pass 2, Iteration 6)}}

Each iteration, agents receive a comprehensive user prompt containing their
performance history and current context. The full prompt ($\sim$10,000 tokens)
includes the following sections. We show condensed excerpts from BANK\_A's
prompt at iteration 6 of Experiment 2, Pass 2:

\subsubsection{{Current State Summary}}

\begin{{verbatim}}
{current_state}
\end{{verbatim}}

\subsubsection{{Cost Breakdown and Rates}}

\begin{{verbatim}}
{cost_analysis}
\end{{verbatim}}

\subsubsection{{Iteration History and Parameter Trajectories}}

\begin{{verbatim}}
{history}
\end{{verbatim}}

\subsubsection{{Final Instructions}}

\begin{{verbatim}}
{instructions}
\end{{verbatim}}

\subsubsection{{Simulation Trace (Exp 2, Pass 2)}}

The prompt includes a tick-by-tick simulation trace showing transaction arrivals,
settlements, and balance changes. This example is from Experiment 2 (stochastic
scenario) showing the first 40 events from a representative simulation:

\begin{{verbatim}}
{simulation_trace}
\end{{verbatim}}
"""
