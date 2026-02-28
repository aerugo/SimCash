#!/usr/bin/env python3
"""Generate chart-ready JSON from Q1 2026 experiment results.

Reads all experiment JSONs, computes summary stats, outputs paper-data.json.
Excludes GLM from complex scenarios (pre-bugfix compromised data).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional
from collections import defaultdict
from typing import Optional

RESULTS_DIR = Path(__file__).parent / "results"
OUTPUT = Path(__file__).parent / "paper-data.json"
# Also write to docs dir for Docker deployment
DOCS_OUTPUT = Path(__file__).parent.parent.parent / "web" / "backend" / "docs" / "papers" / "q1-campaign" / "chart-data.json"

# GLM complex scenario files are compromised (pre-bugfix)
COMPLEX_SCENARIOS = {"periodic_shocks", "large_network", "lehman_month"}

def parse_filename(name: str) -> Optional[dict]:
    """Extract scenario, model, run from filename."""
    name = name.replace(".json", "")
    m = re.match(r"^(.+?)_-_(.+?)(?:_\(r(\d+)\))?$", name)
    if not m:
        return None
    scenario, model, run = m.group(1), m.group(2), m.group(3)
    return {
        "scenario": scenario,
        "model": model,
        "run": int(run) if run else 1,
    }


def compute_stats(data: dict) -> dict:
    """Compute summary stats from experiment data."""
    days = data.get("days", [])
    if not days:
        return {}

    last_day = days[-1]

    # Detect if stats are cumulative (complex scenarios) or per-day (simple).
    # Complex scenarios have monotonically increasing total_arrivals.
    is_cumulative = len(days) > 1 and all(
        days[i].get("total_arrivals", 0) >= days[i-1].get("total_arrivals", 0)
        for i in range(1, len(days))
    )

    if is_cumulative:
        # Complex: arrivals/settled are running totals → last day has the totals
        # Cost is per-day → sum for total system cost over the period
        total_settled = last_day.get("total_settled", 0)
        total_arrived = last_day.get("total_arrivals", 0)
        final_total_cost = sum(d.get("total_cost", 0) for d in days)
    else:
        # Simple: each day is an independent optimization run
        # Last day = converged policy performance
        total_settled = last_day.get("total_settled", 0)
        total_arrived = last_day.get("total_arrivals", 0)
        final_total_cost = last_day.get("total_cost", 0)

    cumulative_sr = total_settled / total_arrived if total_arrived > 0 else 0
    avg_daily_cost = final_total_cost / len(days) if days else 0

    # Per-day settlement rates for chart
    daily_sr = []
    for d in days:
        if is_cumulative:
            # Complex: total_settled/total_arrivals are running totals
            cum_settled = d.get("total_settled", 0)
            cum_arrived = d.get("total_arrivals", 0)
        else:
            # Simple: per-day values, compute running total manually
            idx = d.get("day", len(daily_sr))
            cum_settled = sum(dd.get("total_settled", 0) for dd in days[:idx+1])
            cum_arrived = sum(dd.get("total_arrivals", 0) for dd in days[:idx+1])
        daily_sr.append({
            "day": d.get("day", len(daily_sr)),
            "cumulative_rate": cum_settled / cum_arrived if cum_arrived > 0 else 1.0,
            "daily_cost": d.get("total_cost", 0),
        })

    # Liquidity fraction evolution
    liq_fractions = []
    for d in days:
        policies = d.get("policies", {})
        fracs = {bank: p.get("parameters", {}).get("initial_liquidity_fraction", 0.5)
                 for bank, p in policies.items()}
        liq_fractions.append({"day": d.get("day", len(liq_fractions)), **fracs})

    return {
        "num_days": len(days),
        "final_total_cost": final_total_cost,
        "avg_daily_cost": round(avg_daily_cost),
        "cumulative_sr": round(cumulative_sr, 4),
        "total_settled": total_settled,
        "total_arrived": total_arrived,
        "daily_sr": daily_sr,
        "liq_fractions": liq_fractions,
    }


def main():
    experiments = []
    baselines = {}

    for f in sorted(RESULTS_DIR.glob("*.json")):
        info = parse_filename(f.name)
        if not info:
            continue

        # Skip GLM complex scenarios
        if info["model"] == "glm" and info["scenario"] in COMPLEX_SCENARIOS:
            continue

        data = json.loads(f.read_text())
        stats = compute_stats(data)
        if not stats:
            continue

        entry = {**info, **stats}

        if info["model"] == "baseline":
            baselines[info["scenario"]] = stats
        experiments.append(entry)

    # Add cost delta vs baseline
    for exp in experiments:
        if exp["model"] == "baseline":
            exp["cost_delta_pct"] = 0
            continue
        bl = baselines.get(exp["scenario"])
        if bl and bl["final_total_cost"] > 0:
            delta = (exp["final_total_cost"] - bl["final_total_cost"]) / bl["final_total_cost"]
            exp["cost_delta_pct"] = round(delta * 100, 1)
        else:
            exp["cost_delta_pct"] = None

    # Summary table for charts
    summary = defaultdict(dict)
    for exp in experiments:
        key = (exp["scenario"], exp["model"])
        if key not in summary or exp["run"] == 1:
            summary[key] = {
                "scenario": exp["scenario"],
                "model": exp["model"],
                "cost": exp["final_total_cost"],
                "sr": exp["cumulative_sr"],
                "cost_delta_pct": exp["cost_delta_pct"],
                "num_days": exp["num_days"],
            }

    output = {
        "generated": "auto",
        "experiments": experiments,
        "summary": list(summary.values()),
        "baselines": {k: {"cost": v["final_total_cost"], "sr": v["cumulative_sr"]}
                      for k, v in baselines.items()},
    }

    out_json = json.dumps(output, indent=2)
    OUTPUT.write_text(out_json)
    if DOCS_OUTPUT.parent.exists():
        DOCS_OUTPUT.write_text(out_json)
        print(f"Wrote {DOCS_OUTPUT}")
    print(f"Wrote {OUTPUT} ({len(experiments)} experiments, {len(baselines)} baselines)")


if __name__ == "__main__":
    main()
