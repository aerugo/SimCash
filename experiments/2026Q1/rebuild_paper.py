#!/usr/bin/env python3
"""Rebuild paper markdown tables from paper-data.json with correct values.

Regenerates results.md and appendix.md tables using the corrected data,
then runs add_links.py to add experiment links.
"""
import json
from pathlib import Path

PAPER_DIR = Path(__file__).parent.parent.parent / "web" / "backend" / "docs" / "papers" / "q1-campaign"
DATA = Path(__file__).parent / "paper-data.json"
RESULTS_DIR = Path(__file__).parent / "results"

BASE_URL = "https://simcash-487714.web.app/experiment"

def load_data():
    return json.loads(DATA.read_text())

def load_experiment(filename):
    """Load raw experiment data."""
    f = RESULTS_DIR / filename
    if f.exists():
        return json.loads(f.read_text())
    return None

def fmt_cost(v):
    """Format cost for display."""
    if v >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    return f"{v:,}"

def fmt_sr(v):
    return f"{v*100:.1f}%"

def fmt_delta(v):
    if v is None:
        return "—"
    if v > 0:
        return f"**+{v:.1f}%**"
    return f"**{v:.1f}%**"

def get_exp(experiments, scenario, model, run=1):
    """Find experiment entry."""
    for e in experiments:
        if e["scenario"] == scenario and e["model"] == model and e.get("run") == run:
            return e
    return None

def rebuild_results(data):
    """Rebuild results.md with correct values."""
    exps = data["experiments"]
    
    # Simple scenarios table
    simple_scenarios = ["2b_3t", "3b_6t", "4b_8t", "castro_exp2", "lynx_day"]
    simple_rows = []
    for sc in simple_scenarios:
        bl = get_exp(exps, sc, "baseline")
        fl = get_exp(exps, sc, "flash")
        pr = get_exp(exps, sc, "pro")
        if not bl:
            continue
        row = {
            "scenario": sc,
            "bl_cost": fmt_cost(bl["final_total_cost"]),
            "fl_cost": fmt_cost(fl["final_total_cost"]) if fl else "—",
            "pr_cost": fmt_cost(pr["final_total_cost"]) if pr else "—",
            "fl_delta": fmt_delta(fl["cost_delta_pct"]) if fl else "—",
            "pr_delta": fmt_delta(pr["cost_delta_pct"]) if pr else "—",
            "fl_sr": fmt_sr(fl["cumulative_sr"]) if fl else "—",
            "pr_sr": fmt_sr(pr["cumulative_sr"]) if pr else "—",
        }
        simple_rows.append(row)

    # Complex scenarios table
    complex_scenarios = ["periodic_shocks", "large_network", "lehman_month"]
    complex_cost_rows = []
    complex_sr_rows = []
    for sc in complex_scenarios:
        bl = get_exp(exps, sc, "baseline")
        fl = get_exp(exps, sc, "flash")
        pr = get_exp(exps, sc, "pro")
        if not bl:
            continue
        complex_cost_rows.append({
            "scenario": sc,
            "bl_cost": fmt_cost(bl["final_total_cost"]),
            "fl_cost": fmt_cost(fl["final_total_cost"]) if fl else "—",
            "pr_cost": fmt_cost(pr["final_total_cost"]) if pr else "—",
            "fl_delta": fmt_delta(fl["cost_delta_pct"]) if fl else "—",
            "pr_delta": fmt_delta(pr["cost_delta_pct"]) if pr else "—",
        })
        complex_sr_rows.append({
            "scenario": sc,
            "bl_sr": fmt_sr(bl["cumulative_sr"]),
            "fl_sr": fmt_sr(fl["cumulative_sr"]) if fl else "—",
            "pr_sr": fmt_sr(pr["cumulative_sr"]) if pr else "—",
        })

    # Free-rider table
    freerider_scenarios = ["2b_3t", "3b_6t", "4b_8t", "castro_exp2", "large_network", "lehman_month"]
    freerider_rows = []
    for sc in freerider_scenarios:
        fl = get_exp(exps, sc, "flash")
        pr = get_exp(exps, sc, "pro")
        if not fl or not pr:
            continue
        fl_wins = fl["final_total_cost"] < pr["final_total_cost"]
        freerider_rows.append({
            "scenario": sc,
            "fl_cost": fmt_cost(fl["final_total_cost"]),
            "pr_cost": fmt_cost(pr["final_total_cost"]),
            "wins": "✅" if fl_wins else "❌",
        })

    # Stress table
    stress_bl = get_exp(exps, "2b_stress", "baseline")
    stress_fl = get_exp(exps, "2b_stress", "flash")
    stress_pr = get_exp(exps, "2b_stress", "pro")
    stress_glm = get_exp(exps, "2b_stress", "glm")

    # Build results.md
    md = f"""# Results

## Headline Finding: The Complexity Threshold

LLM-optimized policies dramatically reduce costs in simple scenarios (2-4 banks) but **actively hurt performance** in complex scenarios (5+ banks). We call this the **complexity threshold** — the point at which LLM agents begin to make the system worse rather than better.

<!-- CHART: cost-comparison -->

## Simple Scenarios: Strong Cost Reduction

In scenarios with 2-4 banks, LLM agents achieve significant cost reductions while maintaining high settlement rates. Values show **last-day (converged) policy cost** — the cost achieved after iterative optimization.

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ | Flash SR | Pro SR |
|----------|--------------|------------|----------|---------|-------|----------|--------|
"""
    for r in simple_rows:
        md += f"| `{r['scenario']}` | {r['bl_cost']} | {r['fl_cost']} | {r['pr_cost']} | {r['fl_delta']} | {r['pr_delta']} | {r['fl_sr']} | {r['pr_sr']} |\n"

    md += """
**Key observations:**
- Flash achieves 55-86% cost reduction in simple scenarios
- Flash consistently outperforms Pro (the "smart free-rider" effect — see Discussion)
- Pro sometimes *increases* costs (castro_exp2: +9.3%)
- Settlement rates remain high (>95%) in simple scenarios

## Complex Scenarios: LLM Makes Things Worse

In scenarios with 5+ banks and 25-day runs, **all models increase costs**. Values show **total system cost summed across all 25 days**.

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ |
|----------|--------------|------------|----------|---------|-------|
"""
    for r in complex_cost_rows:
        md += f"| `{r['scenario']}` | {r['bl_cost']} | {r['fl_cost']} | {r['pr_cost']} | {r['fl_delta']} | {r['pr_delta']} |\n"

    md += """
<!-- CHART: complex-cost-delta -->

<!-- CHART: settlement-degradation -->

Settlement rates also degrade. Values show **cumulative settlement rate** (total settled / total arrived across all 25 days):

| Scenario | Baseline SR | Flash SR | Pro SR |
|----------|-------------|----------|--------|
"""
    for r in complex_sr_rows:
        md += f"| `{r['scenario']}` | {r['bl_sr']} | {r['fl_sr']} | {r['pr_sr']} |\n"

    md += """
> **Note:** GLM results for complex scenarios (periodic_shocks, large_network, lehman_month) are excluded due to a pre-bugfix data integrity issue.

## The "Smart Free-Rider" Effect

Across nearly all scenarios, **Flash outperforms Pro**. This is counterintuitive — a more capable model should do better. We hypothesize this is a **smart free-rider effect**: Pro is sophisticated enough to recognize opportunities for strategic delay (free-riding on other banks' liquidity) but this individually rational behavior creates collectively worse outcomes.

| Scenario | Flash Cost | Pro Cost | Flash wins? |
|----------|-----------|----------|-------------|
"""
    for r in freerider_rows:
        md += f"| `{r['scenario']}` | {r['fl_cost']} | {r['pr_cost']} | {r['wins']} |\n"

    md += f"""
Flash wins in {sum(1 for r in freerider_rows if r['wins'] == '✅')} out of {len(freerider_rows)} comparable scenarios (excluding lynx_day which is trivial).

## Stress Scenarios

The `2b_stress` scenario presents an interesting exception — Pro outperforms Flash:

| Model | Cost | SR |
|-------|------|----|
| Baseline | {fmt_cost(stress_bl['final_total_cost'])} | {fmt_sr(stress_bl['cumulative_sr'])} |
| Flash | {fmt_cost(stress_fl['final_total_cost'])} | {fmt_sr(stress_fl['cumulative_sr'])} |
| Pro | {fmt_cost(stress_pr['final_total_cost'])} | {fmt_sr(stress_pr['cumulative_sr'])} |
| GLM | {fmt_cost(stress_glm['final_total_cost'])} | {fmt_sr(stress_glm['cumulative_sr'])} |

Here Flash and GLM actually *increase* costs while Pro achieves a {abs(stress_pr['cost_delta_pct']):.1f}% reduction. This suggests stress conditions may reward the more careful reasoning of Pro.

## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario was additionally tested with v0.2 prompt engineering variants to test whether improved context can break through performance barriers. These variants add:
- **c1-info**: Enhanced information context
- **c2-floor**: Floor price awareness
- **c3-guidance**: Explicit optimization guidance  
- **c4-composition**: Compositional strategy building

*Detailed v0.2 results are available in the Appendix.*

## Run Variance

Each model was run 3 times per scenario (r1, r2, r3) to measure behavioral variance. Full per-run data is in the Appendix.
"""
    return md


def rebuild_appendix(data):
    """Rebuild appendix.md with all runs and correct values."""
    exps = data["experiments"]
    
    COMPLEX = {"periodic_shocks", "large_network", "lehman_month"}
    
    scenarios = [
        ("2b_3t", "2 banks, 3 types"),
        ("2b_stress", "2 banks, stress conditions"),
        ("3b_6t", "3 banks, 6 types"),
        ("4b_8t", "4 banks, 8 types"),
        ("castro_exp2", "Castro replication"),
        ("lynx_day", "Lynx-calibrated day"),
        ("liquidity_squeeze", "Liquidity squeeze"),
        ("periodic_shocks", "Periodic shocks, 25 days"),
        ("large_network", "Large network, 25 days"),
        ("lehman_month", "Lehman-crisis month, 25 days"),
    ]
    
    md = """# Appendix: Detailed Per-Scenario Data

## Per-Run Results

All experiments were run 3 times (r1, r2, r3) to measure variance. Cost for simple scenarios shows **last-day (converged) policy cost**. Cost for complex scenarios (25-day) shows **total system cost summed across all days**. Settlement rate is **cumulative** (total settled / total arrived).

"""
    
    for sc_key, sc_desc in scenarios:
        is_complex = sc_key in COMPLEX
        cost_note = "total across 25 days" if is_complex else "last-day converged"
        md += f"### {sc_key} ({sc_desc})\n\n"
        md += f"| Run | Model | Final Cost ({cost_note}) | Cumulative SR | Days |\n"
        md += "|-----|-------|-----------|---------------|------|\n"
        
        # Collect all runs for this scenario
        runs = [e for e in exps if e["scenario"] == sc_key]
        runs.sort(key=lambda e: (
            {"baseline": 0, "flash": 1, "pro": 2, "glm": 3}.get(e["model"].split("_")[0] if "_" not in e["model"] else e["model"], 4),
            e.get("run", 1)
        ))
        
        for e in runs:
            model = e["model"]
            run = e.get("run", 1)
            
            # Skip GLM for complex scenarios
            if model == "glm" and sc_key in COMPLEX:
                continue
            
            run_label = "—" if model == "baseline" else f"r{run}"
            model_display = model.capitalize() if model in ("baseline", "flash", "pro", "glm") else model
            
            md += f"| {run_label} | {model_display} | {fmt_cost(e['final_total_cost'])} | {fmt_sr(e['cumulative_sr'])} | {e['num_days']} |\n"
        
        if is_complex:
            md += "\n> GLM excluded for complex scenarios (pre-bugfix data).\n"
        md += "\n"

    # v0.2 variants section
    md += """## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario tested 4 prompt engineering variants across all 3 models:

| Variant | Description |
|---------|-------------|
| c1-info | Enhanced information context about the payment system |
| c2-floor | Floor price awareness — minimum cost thresholds |
| c3-guidance | Explicit optimization guidance in the system prompt |
| c4-composition | Compositional strategy building — layered heuristics |

### Per-Variant Results

| Variant | Run | Model | Final Cost | Cumulative SR | Days |
|---------|-----|-------|-----------|---------------|------|
"""
    
    variants = ["c1-info", "c2-floor", "c3-guidance", "c4-composition", "c4-comp"]
    variant_exps = [e for e in exps if e["scenario"] == "castro_exp2" and any(v in e["model"] for v in variants)]
    variant_exps.sort(key=lambda e: (e["model"], e.get("run", 1)))
    
    for e in variant_exps:
        model = e["model"]
        run = e.get("run", 1)
        # Parse variant and base model from model string like "flash_(c1-info_r2)" or "flash_(c1-info)"
        # The model field includes everything after scenario_-_
        parts = model.split("_(")
        base_model = parts[0] if parts else model
        variant = parts[1].rstrip(")").split("_r")[0] if len(parts) > 1 else ""
        
        md += f"| {variant} | r{run} | {base_model.capitalize()} | {fmt_cost(e['final_total_cost'])} | {fmt_sr(e['cumulative_sr'])} | {e['num_days']} |\n"

    md += """
## Data Processing

Results were extracted using `experiments/2026Q1/generate_paper_data.py`. Raw experiment JSON files are in `experiments/2026Q1/results/`.

### Methodology Notes

- **Simple scenario cost** = last-day total_cost (converged policy performance after optimization)
- **Complex scenario cost** = sum of per-day total_cost across all 25 days (total system cost)
- **Cumulative SR** = total_settled / total_arrivals (cumulative for complex, last-day for simple)
- **Cost delta** = (model_cost - baseline_cost) / baseline_cost × 100%
- **Baselines** run for 1 day (simple) or 25 days (complex) with default FIFO policies
- **GLM exclusion**: GLM results for periodic_shocks, large_network, and lehman_month are excluded due to a simulator bug present when those experiments ran
"""
    return md


def main():
    data = load_data()
    
    results_md = rebuild_results(data)
    appendix_md = rebuild_appendix(data)
    
    (PAPER_DIR / "results.md").write_text(results_md)
    (PAPER_DIR / "appendix.md").write_text(appendix_md)
    
    print(f"Wrote results.md ({len(results_md)} chars)")
    print(f"Wrote appendix.md ({len(appendix_md)} chars)")
    print("Now run add_links.py to add experiment links.")


if __name__ == "__main__":
    main()
