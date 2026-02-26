#!/usr/bin/env python3
"""
SimCash Experiment Results Analyzer
====================================
Produces reproducible tables and statistics from api-results/*.json files.

Usage:
    python3 analyze_results.py                  # Full report
    python3 analyze_results.py --section costs  # Just cost summary
    python3 analyze_results.py --section trees  # Just policy tree analysis
    python3 analyze_results.py --section baseline  # Baseline comparison
    python3 analyze_results.py --section castro  # Castro Exp2 detail
    python3 analyze_results.py --section repro  # Reproducibility (r1 vs r2 vs r3)
    python3 analyze_results.py --section perbank # Per-bank breakdown
"""

import json
import glob
import hashlib
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

RESULTS_DIR = Path(__file__).parent / "api-results"


# ─── Helpers ────────────────────────────────────────────────────────────────

def load_experiment(filepath):
    """Load a single experiment JSON, return parsed data with metadata."""
    with open(filepath) as f:
        data = json.load(f)
    name = os.path.basename(filepath).replace(".json", "")
    days = data.get("days", [])
    return {
        "name": name,
        "path": filepath,
        "data": data,
        "days": days,
        "num_days": len(days),
    }


def load_all_experiments():
    """Load all experiment JSONs, skip pipeline logs."""
    exps = []
    for f in sorted(glob.glob(str(RESULTS_DIR / "*.json"))):
        if "pipeline" in f:
            continue
        exps.append(load_experiment(f))
    return exps


def experiment_costs(exp, final_round_only=False):
    """Compute costs and settlement for an experiment.
    
    SimCash costs are PER-DAY (not cumulative). We sum across all days/rounds.
    
    For multi-round experiments (e.g., 10 rounds of 2B 3T), set 
    final_round_only=True to get just the last round's performance
    (after optimization has converged).
    """
    days = exp["days"]
    if not days:
        return {
            "total_cost": 0, "final_round_cost": 0,
            "total_settled": 0, "total_arrivals": 0,
            "settlement_rate": 0, "per_agent_costs": {}, "num_days": 0,
        }

    if final_round_only:
        days = [days[-1]]

    total_cost = sum(day.get("total_cost", 0) for day in days)
    total_settled = sum(day.get("total_settled", 0) for day in days)
    total_arrivals = sum(day.get("total_arrivals", 0) for day in days)
    per_agent = defaultdict(int)
    for day in days:
        for agent, cost in day.get("per_agent_costs", {}).items():
            per_agent[agent] += cost

    # Also get final round cost for multi-round comparison
    last = exp["days"][-1]
    
    return {
        "total_cost": total_cost,
        "final_round_cost": last.get("total_cost", 0),
        "total_settled": total_settled,
        "total_arrivals": total_arrivals,
        "settlement_rate": total_settled / total_arrivals if total_arrivals else 0,
        "per_agent_costs": dict(per_agent),
        "num_days": len(exp["days"]),
    }


def count_tree_nodes(tree):
    """Count nodes in a policy decision tree."""
    if not isinstance(tree, dict):
        return 0
    count = 1
    for key in ["on_true", "on_false"]:
        if key in tree and isinstance(tree[key], dict):
            count += count_tree_nodes(tree[key])
    return count


def tree_depth(tree, d=0):
    """Compute depth of a policy decision tree."""
    if not isinstance(tree, dict):
        return d
    depths = [d]
    for key in ["on_true", "on_false"]:
        if key in tree and isinstance(tree[key], dict):
            depths.append(tree_depth(tree[key], d + 1))
    return max(depths)


def tree_hash(tree):
    """Hash a tree for deduplication."""
    return hashlib.md5(json.dumps(tree, sort_keys=True).encode()).hexdigest()


def walk_tree(tree, on_action=None, on_condition=None):
    """Walk a tree, calling callbacks on action/condition nodes."""
    if not isinstance(tree, dict):
        return
    if tree.get("type") == "action" and on_action:
        on_action(tree)
    if tree.get("type") == "condition" and on_condition:
        on_condition(tree)
    for key in ["on_true", "on_false"]:
        if key in tree:
            walk_tree(tree[key], on_action, on_condition)


def get_fraction(policy):
    """Extract liquidity fraction from a policy's parameters."""
    params = policy.get("parameters", {})
    return params.get("initial_liquidity_fraction",
                       params.get("starting_fraction"))


def parse_experiment_name(name):
    """Parse experiment filename into scenario, model, run."""
    # Remove known suffixes
    n = name
    run = "1"
    for suffix in ["_(r2)", "_(r3)", "_(b1)", "_(b2)", "_(b3)"]:
        if suffix in n:
            run = suffix.replace("_(", "").replace(")", "")
            n = n.replace(suffix, "")
            break

    if "_-_baseline" in n:
        return n.replace("_-_baseline", ""), "baseline", "baseline"

    parts = n.rsplit("_-_", 1)
    if len(parts) == 2:
        scenario, model = parts
        return scenario, model, run
    return n, "unknown", run


# ─── Sections ───────────────────────────────────────────────────────────────

def section_costs(experiments):
    """Print cost and settlement summary for all experiments."""
    print("=" * 100)
    print("COST & SETTLEMENT SUMMARY")
    print("=" * 100)
    print(f"{'Experiment':<45s} {'Total Cost':>14s} {'Settle':>8s} {'Days':>5s}")
    print("-" * 100)

    for exp in experiments:
        if not exp["days"]:
            continue
        c = experiment_costs(exp)
        print(f"{exp['name']:<45s} {c['total_cost']:>14,.0f} {c['settlement_rate']:>7.1%} {c['num_days']:>5d}")

    print()


def section_baseline(experiments):
    """Compare optimized runs against baselines."""
    print("=" * 100)
    print("BASELINE COMPARISON (FIFO 0.5 vs Best LLM)")
    print("=" * 100)

    # Group by scenario
    by_scenario = defaultdict(list)
    for exp in experiments:
        if not exp["days"]:
            continue
        scenario, model, run = parse_experiment_name(exp["name"])
        c = experiment_costs(exp)
        # For multi-round experiments (rounds>1, single day scenarios),
        # use final_round_cost for fair baseline comparison.
        # For multi-day experiments, use total_cost (sum of all days).
        is_multi_round = c["num_days"] > 1 and all(
            exp["days"][i].get("seed") != exp["days"][0].get("seed")
            for i in range(1, min(2, len(exp["days"])))
        ) if len(exp["days"]) > 1 else False
        
        comparable_cost = c["final_round_cost"] if is_multi_round else c["total_cost"]
        
        by_scenario[scenario].append({
            "model": model,
            "run": run,
            "cost": comparable_cost,
            "total_cost": c["total_cost"],
            "settlement": c["settlement_rate"],
            "name": exp["name"],
        })

    print(f"{'Scenario':<25s} {'BL Cost':>14s} {'BL Sett':>8s} {'Best LLM Cost':>14s} {'LLM Sett':>9s} {'Δ Cost':>8s} {'Model':>8s}")
    print("-" * 100)
    print("  Multi-round: final round cost (post-optimization) vs single-round baseline")
    print("  Multi-day: sum of all daily costs for both baseline and optimized")
    print("  Settlement: averaged across all rounds/days")
    print()

    for scenario in sorted(by_scenario.keys()):
        runs = by_scenario[scenario]
        baselines = [r for r in runs if r["model"] == "baseline"]
        optimized = [r for r in runs if r["model"] != "baseline" and r["run"] == "1"]

        if not baselines or not optimized:
            continue

        bl = baselines[0]
        best = min(optimized, key=lambda x: x["cost"])
        delta = (best["cost"] - bl["cost"]) / bl["cost"] * 100 if bl["cost"] else 0

        print(f"{scenario:<25s} {bl['cost']:>14,.0f} {bl['settlement']:>7.1%} {best['cost']:>14,.0f} {best['settlement']:>8.1%} {delta:>+7.1f}% {best['model']:>8s}")

    print()


def section_repro(experiments):
    """Reproducibility analysis: compare runs 1, 2, 3."""
    print("=" * 100)
    print("REPRODUCIBILITY: RUN 1 vs RUN 2 vs RUN 3")
    print("=" * 100)

    by_key = defaultdict(list)
    for exp in experiments:
        if not exp["days"]:
            continue
        scenario, model, run = parse_experiment_name(exp["name"])
        if model == "baseline":
            continue
        c = experiment_costs(exp)
        by_key[(scenario, model)].append({
            "run": run,
            "cost": c["total_cost"],
            "settlement": c["settlement_rate"],
        })

    print(f"{'Scenario':<25s} {'Model':<8s} {'Run 1 Cost':>14s} {'Run 2 Cost':>14s} {'Run 3 Cost':>14s} {'CV%':>6s} {'Settle Range':>14s}")
    print("-" * 110)

    for (scenario, model) in sorted(by_key.keys()):
        runs = sorted(by_key[(scenario, model)], key=lambda x: str(x["run"]))
        costs = [r["cost"] for r in runs]
        settles = [r["settlement"] for r in runs]

        cost_strs = []
        for r in ["1", "r2", "r3"]:
            match = [x for x in runs if str(x["run"]) == r]
            cost_strs.append(f"{match[0]['cost']:>14,.0f}" if match else f"{'—':>14s}")

        # Coefficient of variation
        if len(costs) > 1:
            mean = sum(costs) / len(costs)
            variance = sum((c - mean) ** 2 for c in costs) / len(costs)
            cv = (variance ** 0.5 / mean * 100) if mean else 0
        else:
            cv = 0

        settle_range = f"{min(settles):.0%}-{max(settles):.0%}"
        cost_cols = " ".join(cost_strs)
        print(f"{scenario:<25s} {model:<8s} {cost_cols} {cv:>5.1f}% {settle_range:>14s}")

    print()


def section_castro(experiments):
    """Detailed Castro Exp2 analysis with fraction evolution."""
    print("=" * 100)
    print("CASTRO EXP2 — LIQUIDITY FRACTION EVOLUTION")
    print("=" * 100)
    print("Paper prediction: optimal ~20-40% of capacity (Castro et al. Figure 6)")
    print("Baseline: 50% (FIFO default)")
    print()

    for exp in experiments:
        if "castro_exp2" not in exp["name"] or "baseline" in exp["name"]:
            continue
        if not exp["days"]:
            continue

        print(f"--- {exp['name']} ---")
        print(f"{'Round':>5s} {'A frac':>8s} {'B frac':>8s} {'Cost':>10s} {'Settle':>7s}")

        for i, day in enumerate(exp["days"]):
            pols = day.get("policies", {})
            a_frac = get_fraction(pols.get("BANK_A", {}))
            b_frac = get_fraction(pols.get("BANK_B", {}))
            settled = day.get("total_settled", 0)
            arrivals = day.get("total_arrivals", 0)
            rate = settled / arrivals if arrivals else 0
            a_str = f"{a_frac}" if a_frac is not None else "?"
            b_str = f"{b_frac}" if b_frac is not None else "?"
            print(f"  {i + 1:>3d} {a_str:>8s} {b_str:>8s} {day['total_cost']:>10,d} {rate:>6.0%}")

        print()


def section_perbank(experiments):
    """Per-bank cost breakdown for multi-bank scenarios."""
    print("=" * 100)
    print("PER-BANK COST BREAKDOWN (Baseline vs Optimized)")
    print("=" * 100)

    # Find baselines
    baselines = {}
    for exp in experiments:
        if "baseline" not in exp["name"] or not exp["days"]:
            continue
        scenario, _, _ = parse_experiment_name(exp["name"])
        baselines[scenario] = experiment_costs(exp)

    # Show per-bank for selected scenarios
    for target in ["lehman_month", "large_network", "liquidity_squeeze"]:
        if target not in baselines:
            continue

        bl = baselines[target]
        print(f"\n{'─' * 80}")
        print(f"  {target.upper().replace('_', ' ')}")
        print(f"{'─' * 80}")
        print(f"  {'Agent':<20s} {'Baseline':>14s}", end="")

        # Find r1 optimized runs for this scenario
        opt_runs = []
        for exp in experiments:
            scenario, model, run = parse_experiment_name(exp["name"])
            if scenario == target and model != "baseline" and run == "1" and exp["days"]:
                opt_runs.append((model, experiment_costs(exp)))

        for model, _ in opt_runs:
            print(f" {model:>14s}", end="")
        print()

        agents = sorted(bl["per_agent_costs"].keys())
        for agent in agents:
            bl_cost = bl["per_agent_costs"].get(agent, 0)
            print(f"  {agent:<20s} {bl_cost:>14,.0f}", end="")
            for model, costs in opt_runs:
                opt_cost = costs["per_agent_costs"].get(agent, 0)
                delta_pct = (opt_cost - bl_cost) / bl_cost * 100 if bl_cost else 0
                print(f" {opt_cost:>10,.0f} ({delta_pct:>+.0f}%)", end="")
            print()

        # Totals
        bl_total = sum(bl["per_agent_costs"].get(a, 0) for a in agents)
        print(f"  {'TOTAL':<20s} {bl_total:>14,.0f}", end="")
        for model, costs in opt_runs:
            opt_total = sum(costs["per_agent_costs"].get(a, 0) for a in agents)
            delta_pct = (opt_total - bl_total) / bl_total * 100 if bl_total else 0
            print(f" {opt_total:>10,.0f} ({delta_pct:>+.0f}%)", end="")
        print()

    print()


def section_trees(experiments):
    """Policy tree complexity and structure analysis."""
    print("=" * 100)
    print("POLICY TREE ANALYSIS")
    print("=" * 100)

    unique_trees = {}
    action_counts = Counter()
    condition_fields = Counter()
    total_instances = 0
    changes = 0
    prev_hashes = {}
    size_dist = Counter()
    trees_by_size = defaultdict(list)

    for exp in experiments:
        if "baseline" in exp["name"]:
            continue
        for i, day in enumerate(exp["days"]):
            for agent, pol in day.get("policies", {}).items():
                for tt in ["bank_tree", "payment_tree"]:
                    tree = pol.get(tt)
                    if not tree or not isinstance(tree, dict):
                        continue
                    total_instances += 1

                    h = tree_hash(tree)
                    key = f"{exp['name']}:{agent}:{tt}"

                    if key in prev_hashes and prev_hashes[key] != h:
                        changes += 1
                    prev_hashes[key] = h

                    nodes = count_tree_nodes(tree)
                    size_dist[nodes] += 1

                    if h not in unique_trees:
                        unique_trees[h] = {
                            "tree": tree,
                            "nodes": nodes,
                            "depth": tree_depth(tree),
                            "source": f"{exp['name']}/{agent}/day{i}/{tt}",
                        }

                        def on_action(node):
                            action_counts[node.get("action", "?")] += 1

                        def on_condition(node):
                            cond = node.get("condition", {})
                            left = cond.get("left", {})
                            if "field" in left:
                                condition_fields[left["field"]] += 1

                        walk_tree(tree, on_action, on_condition)

                        if nodes >= 7:
                            trees_by_size[nodes].append(unique_trees[h])

    print(f"\nTotal tree instances:     {total_instances:>6,d}")
    print(f"Unique trees (by hash):  {len(unique_trees):>6,d}")
    print(f"Policy changes:          {changes:>6,d}")
    print(f"Reuse ratio:             {total_instances / len(unique_trees):.1f}x")

    print(f"\nTREE SIZE DISTRIBUTION (instances):")
    for size in sorted(size_dist.keys()):
        bar = "█" * (size_dist[size] // 50)
        print(f"  {size:>2d} nodes: {size_dist[size]:>5d} {bar}")

    print(f"\nACTIONS (unique trees only):")
    for action, count in action_counts.most_common():
        print(f"  {action:<25s} {count:>5d}")

    print(f"\nCONDITION FIELDS (unique trees only):")
    for field, count in condition_fields.most_common():
        print(f"  {field:<30s} {count:>5d}")

    # Show most complex trees
    print(f"\nMOST COMPLEX TREES (≥7 nodes):")
    for size in sorted(trees_by_size.keys(), reverse=True):
        for t in trees_by_size[size]:
            print(f"\n  [{t['nodes']} nodes, depth {t['depth']}] {t['source']}")
            print(f"  {json.dumps(t['tree'], indent=4)[:600]}")

    print()


# ─── Main ───────────────────────────────────────────────────────────────────

SECTIONS = {
    "costs": section_costs,
    "baseline": section_baseline,
    "repro": section_repro,
    "castro": section_castro,
    "perbank": section_perbank,
    "trees": section_trees,
}


def section_check(experiments):
    """Validate every JSON maps to an experiment-config entry; flag orphans (1a)."""
    import yaml
    config_path = Path(__file__).parent / "experiment-config.yaml"
    if not config_path.exists():
        print("ERROR: experiment-config.yaml not found")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Build set of expected safe_names from config
    def _safe(name):
        return name.lower().replace(" ", "_").replace("\u2014", "-").replace("/", "_")

    expected = {_safe(e["name"]) for e in config.get("experiments", [])}

    print("=" * 80)
    print("ORPHAN CHECK: JSON files vs experiment-config.yaml")
    print("=" * 80)

    orphans = []
    matched = []
    for exp in experiments:
        if exp["name"] in expected:
            matched.append(exp["name"])
        else:
            orphans.append(exp["name"])

    print(f"Matched: {len(matched)}")
    if orphans:
        print(f"\n⚠️  ORPHAN FILES ({len(orphans)}):")
        for o in orphans:
            print(f"  - api-results/{o}.json")
    else:
        print("✅ No orphan files found")
    print()


def section_validate(experiments):
    """Validate cost structure and data integrity (3a)."""
    print("=" * 80)
    print("DATA VALIDATION")
    print("=" * 80)

    issues = []

    for exp in experiments:
        name = exp["name"]
        days = exp["days"]
        if not days:
            continue

        # Determine if multi-day (rounds=1, many days) or multi-round
        num_days = len(days)

        # Check: for multi-day scenarios (1 round, many days), costs should be
        # cumulative (monotonically increasing). Multi-round experiments (rounds>1)
        # have per-round costs that may decrease as optimization improves.
        # Heuristic: if scenario has "month" or "shocks" or "network" in name, it's multi-day.
        is_multiday = any(kw in name.lower() for kw in ["month", "shocks", "network", "lynx"])
        if is_multiday and num_days > 1:
            costs = [d.get("total_cost", 0) for d in days]
            for i in range(1, len(costs)):
                if costs[i] < costs[i - 1]:
                    issues.append(f"  {name}: cost decreased day {i} → {i+1}: {costs[i-1]:,} → {costs[i]:,}")

        # Check: multi-round experiments (not multi-day) should have different seeds
        is_multiround = not is_multiday and num_days > 1
        if is_multiround:
            seeds = [d.get("seed") for d in days if d.get("seed") is not None]
            if seeds and len(set(seeds)) < len(seeds):
                issues.append(f"  {name}: duplicate seeds across {len(seeds)} rounds: {len(set(seeds))} unique")

        # Check: optimization_summary.failed == 0
        data = exp["data"]
        opt_summary = data.get("optimization_summary", {})
        failed = opt_summary.get("failed", 0)
        if failed and failed > 0:
            issues.append(f"  {name}: optimization_summary.failed = {failed}")

    if issues:
        print(f"⚠️  Found {len(issues)} issue(s):")
        for issue in issues:
            print(issue)
    else:
        print("✅ All validations passed")
    print()


SECTIONS["check"] = section_check
SECTIONS["validate"] = section_validate


def main():
    section = None
    if "--section" in sys.argv:
        idx = sys.argv.index("--section")
        if idx + 1 < len(sys.argv):
            section = sys.argv[idx + 1]

    # Handle --check and --validate as shortcuts
    if "--check" in sys.argv:
        section = "check"
    if "--validate" in sys.argv:
        section = "validate"

    experiments = load_all_experiments()
    print(f"Loaded {len(experiments)} experiment files from {RESULTS_DIR}\n")

    if section:
        if section in SECTIONS:
            SECTIONS[section](experiments)
        else:
            print(f"Unknown section: {section}")
            print(f"Available: {', '.join(SECTIONS.keys())}")
    else:
        for name, fn in SECTIONS.items():
            if name in ("check", "validate"):
                continue  # Don't run these by default
            fn(experiments)


if __name__ == "__main__":
    main()
