"""Results section for web version — the key file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.markdown.figures import include_figure
from src.markdown.formatting import format_money, format_percent
from src.markdown.tables import (
    generate_bootstrap_table,
    generate_convergence_table,
    generate_iteration_table,
    generate_pass_summary_table,
)

if TYPE_CHECKING:
    from src.data_provider import DataProvider

CHARTS_DIR = "charts"


def generate_results(provider: DataProvider) -> str:
    """Generate the results section in blog style with inline stats and collapsible tables."""
    # Aggregate stats
    agg = provider.get_aggregate_stats()

    # Convergence stats
    exp1_conv = provider.get_convergence_statistics("exp1")
    exp2_conv = provider.get_convergence_statistics("exp2")
    exp3_conv = provider.get_convergence_statistics("exp3")

    # Pass summaries
    exp1_summaries = provider.get_all_pass_summaries("exp1")
    exp2_summaries = provider.get_all_pass_summaries("exp2")
    exp3_summaries = provider.get_all_pass_summaries("exp3")

    # Exp1 Pass 1 detail
    exp1_results = provider.get_iteration_results("exp1", pass_num=1)
    exp1_convergence = provider.get_convergence_iteration("exp1", pass_num=1)
    exp1_final = [r for r in exp1_results if r["iteration"] == exp1_convergence]
    exp1_a = next((r for r in exp1_final if r["agent_id"] == "BANK_A"), None)
    exp1_b = next((r for r in exp1_final if r["agent_id"] == "BANK_B"), None)

    # Exp2 Pass 2 detail
    exp2_results = provider.get_iteration_results("exp2", pass_num=2)
    exp2_bootstrap = provider.get_final_bootstrap_stats("exp2", pass_num=2)

    # Exp3 Pass 1 detail
    exp3_results = provider.get_iteration_results("exp3", pass_num=1)
    exp3_convergence = provider.get_convergence_iteration("exp3", pass_num=1)
    exp3_final = [r for r in exp3_results if r["iteration"] == exp3_convergence]
    exp3_a = next((r for r in exp3_final if r["agent_id"] == "BANK_A"), None)
    exp3_b = next((r for r in exp3_final if r["agent_id"] == "BANK_B"), None)

    # Formatted values
    exp1_a_cost = format_money(exp1_a["cost"]) if exp1_a else "N/A"
    exp1_a_liq = format_percent(exp1_a["liquidity_fraction"]) if exp1_a else "N/A"
    exp1_b_cost = format_money(exp1_b["cost"]) if exp1_b else "N/A"
    exp1_b_liq = format_percent(exp1_b["liquidity_fraction"]) if exp1_b else "N/A"

    exp3_a_cost = format_money(exp3_a["cost"]) if exp3_a else "N/A"
    exp3_a_liq = format_percent(exp3_a["liquidity_fraction"]) if exp3_a else "N/A"
    exp3_b_cost = format_money(exp3_b["cost"]) if exp3_b else "N/A"
    exp3_b_liq = format_percent(exp3_b["liquidity_fraction"]) if exp3_b else "N/A"

    exp2_a_mean = format_money(exp2_bootstrap["BANK_A"]["mean_cost"]) if "BANK_A" in exp2_bootstrap else "N/A"
    exp2_a_std = format_money(exp2_bootstrap["BANK_A"]["std_dev"]) if "BANK_A" in exp2_bootstrap else "N/A"
    exp2_b_mean = format_money(exp2_bootstrap["BANK_B"]["mean_cost"]) if "BANK_B" in exp2_bootstrap else "N/A"
    exp2_b_std = format_money(exp2_bootstrap["BANK_B"]["std_dev"]) if "BANK_B" in exp2_bootstrap else "N/A"
    exp2_samples = exp2_bootstrap["BANK_A"]["num_samples"] if "BANK_A" in exp2_bootstrap else 0

    # Exp2 liquidity range
    exp2_all_liqs = [s["bank_a_liquidity"] for s in exp2_summaries] + [s["bank_b_liquidity"] for s in exp2_summaries]
    exp2_liq_min = format_percent(min(exp2_all_liqs))
    exp2_liq_max = format_percent(max(exp2_all_liqs))

    # Convergence table
    conv_table = generate_convergence_table([exp1_conv, exp2_conv, exp3_conv])

    # Figures
    exp1_fig = include_figure(f"{CHARTS_DIR}/exp1_pass1_combined.png", "Experiment 1: Both agents converge to an asymmetric stable outcome")
    exp2_fig = include_figure(f"{CHARTS_DIR}/exp2_pass2_combined.png", "Experiment 2: Convergence under stochastic arrivals (Pass 2)")
    exp2_var_fig = include_figure(f"{CHARTS_DIR}/exp2_pass2_variance.png", "Experiment 2: Cost variance with 95% confidence intervals")
    exp3_fig = include_figure(f"{CHARTS_DIR}/exp3_pass1_combined.png", "Experiment 3: Coordination failure in symmetric game")

    # Tables
    exp1_iter_table = generate_iteration_table(exp1_results)
    exp1_summary_table = generate_pass_summary_table(exp1_summaries)
    exp2_iter_table = generate_iteration_table(exp2_results)
    exp2_boot_table = generate_bootstrap_table(exp2_bootstrap)
    exp2_summary_table = generate_pass_summary_table(exp2_summaries)
    exp3_iter_table = generate_iteration_table(exp3_results)
    exp3_summary_table = generate_pass_summary_table(exp3_summaries)

    return rf"""# Results

## Convergence Summary

{conv_table}

Experiments 1 and 3 achieved formal convergence via temporal policy stability (mean
{exp1_conv['mean_iterations']:.1f} and {exp3_conv['mean_iterations']:.1f} iterations
respectively). Experiment 2's stochastic passes terminated at the 50-iteration budget —
the strict bootstrap convergence criteria proved overly conservative for environments
with inherent cost variance.

---

## Experiment 1: The Free-Rider Emerges

In this 2-period deterministic scenario, Bank A faces lower delay costs than Bank B,
creating incentives for free-rider behavior.

{exp1_fig}

The agents converged after {exp1_convergence} iterations in Pass 1 to a clear asymmetric outcome:

- **Bank A**: {exp1_a_cost} cost with {exp1_a_liq} liquidity — classic free-rider
- **Bank B**: {exp1_b_cost} cost with {exp1_b_liq} liquidity — the liquidity provider

This matches the game-theoretic prediction: Bank A free-rides on Bank B's liquidity,
minimizing its own reserves while relying on incoming payments from Bank B to fund
outgoing obligations.

But **Pass 3 told a different story**: the free-rider identity flipped. Bank B adopted
zero liquidity while Bank A maintained just 1.8%. Both agents ended up with high costs
(\$31.78 and \$70.00) — nearly 4× the efficient outcome. Same game, same agents, completely
different result driven by early exploration dynamics.

<details>
<summary>📊 View iteration-by-iteration results (Pass 1)</summary>

{exp1_iter_table}

</details>

<details>
<summary>📊 View summary across all passes</summary>

{exp1_summary_table}

</details>

---

## Experiment 2: Stochastic Environment

Experiment 2 introduces a 12-period scenario with random transaction arrivals and amounts,
requiring bootstrap evaluation to assess policy quality under variance.

{exp2_fig}

All three passes terminated at the 50-iteration budget without formal convergence.
The strict criteria — CV < 3%, no significant trend, and regret < 10% sustained over
5 iterations — were simply too demanding for this stochastic environment. But the
policies achieved practical stability: liquidity allocations settled into consistent
ranges and costs stayed within narrow bands.

### Bootstrap Evaluation

Each iteration uses 50 bootstrap samples for paired comparison. The table below shows
bootstrap statistics for the final accepted policies:

{exp2_boot_table}

Bank A achieved mean cost {exp2_a_mean} (± {exp2_a_std}). Bank B maintained more
consistent costs at {exp2_b_mean} (± {exp2_b_std}).

### Risk vs. Return

{exp2_var_fig}

The convergence chart reveals cases where dramatically better policies were *rejected*.
For example, at iteration 22, Bank A's proposed policy achieved mean cost \$324 vs the
current \$915 — but was rejected because its CV was 0.83 (above the 0.5 threshold).
Better average performance, but unacceptably volatile.

This risk-adjusted acceptance biases optimization toward policies that improve cost
while maintaining stability — explaining the apparent paradox where rejected proposals
(✕ markers) appear below the current policy line.

<details>
<summary>📊 View iteration-by-iteration results (Pass 2)</summary>

{exp2_iter_table}

</details>

<details>
<summary>📊 View summary across all passes</summary>

{exp2_summary_table}

</details>

---

## Experiment 3: When Cooperation Fails

This is the most revealing experiment. Both banks face **identical cost structures** and
start with identical 50% liquidity (baseline cost ~\$50 each). Theory predicts they should
converge to a symmetric ~20% allocation.

**Every single pass produced coordination failure.** Both agents ended up worse off than
where they started.

{exp3_fig}

Final stable profile (Pass 1):
- **Bank A**: {exp3_a_cost} cost, {exp3_a_liq} liquidity
- **Bank B**: {exp3_b_cost} cost, {exp3_b_liq} liquidity

### How Coordination Fails

Here's the mechanism: In Pass 1, iteration 1 saw both agents reduce liquidity moderately
(Bank A to 30%, Bank B to 40%). Costs improved for both — great! Encouraged by this,
Bank A aggressively dropped to 1% in iteration 2. This initially looked beneficial
(force the other side to provide liquidity), but trapped both agents:

- Bank A can't increase liquidity without reducing Bank B's incentive to maintain reserves
- Bank B can't reduce liquidity without causing settlement failures
- The profile is *stable* but *Pareto-dominated* — both are worse off than baseline

This isn't a bug in the LLM agents' reasoning. It's exactly what happens when rational
agents optimize greedily without coordination mechanisms. The LLM agents exhibit the same
coordination failures that game theory predicts for non-communicating optimizers.

<details>
<summary>📊 View iteration-by-iteration results (Pass 1)</summary>

{exp3_iter_table}

</details>

<details>
<summary>📊 View summary across all passes</summary>

{exp3_summary_table}

</details>

---

## Cross-Experiment Patterns

Four key observations emerge:

1. **Stability ≠ optimality** — All deterministic passes achieved policy stability, but
   Experiment 3 shows stable profiles can be worse than baseline.

2. **Coordination failure is systematic** — In symmetric games, agents *always* fell
   into traps where both are worse off. Not a fluke — 3 out of 3 passes.

3. **Asymmetric free-riding is path-dependent** — Who becomes the free-rider depends
   on who makes the first aggressive move, not on the cost structure.

4. **Stochastic environments prevent coordination collapse** — Experiment 2 produced
   near-symmetric allocations ({exp2_liq_min}–{exp2_liq_max} range) without the severe
   coordination failures of deterministic scenarios. Uncertainty prevents the confident
   aggressive moves that trigger traps.
"""
