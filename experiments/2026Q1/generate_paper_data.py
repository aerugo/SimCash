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

    total_settled = sum(d.get("total_settled", 0) for d in days)
    total_arrived = sum(d.get("total_arrivals", 0) for d in days)
    cumulative_sr = total_settled / total_arrived if total_arrived > 0 else 0

    last_day = days[-1]
    # Cumulative total cost is on the last day (running sum)
    final_total_cost = last_day.get("total_cost", 0)
    # Average daily cost
    avg_daily_cost = final_total_cost / len(days) if days else 0

    # Per-day settlement rates for chart
    daily_sr = []
    for d in days:
        day_arrived = d.get("total_arrivals", 0)
        day_settled = d.get("total_settled", 0)
        # Cumulative up to this day
        cum_settled = sum(dd.get("total_settled", 0) for dd in days[:d["day"] + 1]) if "day" in d else day_settled
        cum_arrived = sum(dd.get("total_arrivals", 0) for dd in days[:d["day"] + 1]) if "day" in d else day_arrived
        daily_sr.append({
            "day": d.get("day", len(daily_sr)),
            "daily_rate": day_settled / day_arrived if day_arrived > 0 else 1.0,
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

    OUTPUT.write_text(json.dumps(output, indent=2))
    print(f"Wrote {OUTPUT} ({len(experiments)} experiments, {len(baselines)} baselines)")


if __name__ == "__main__":
    main()
