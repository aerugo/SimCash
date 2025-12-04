#!/usr/bin/env python
"""Generate convergence graphs for Castro experiments."""

import duckdb
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path


def load_experiment_data(db_path: str) -> tuple[list[int], list[float]]:
    """Load iteration costs from experiment database."""
    con = duckdb.connect(db_path)
    data = con.execute("""
        SELECT iteration_number, total_cost_mean
        FROM iteration_metrics
        ORDER BY iteration_number
    """).fetchall()

    # Deduplicate (take last entry for each iteration)
    seen = {}
    for row in data:
        seen[row[0]] = row[1]

    iterations = sorted(seen.keys())
    costs = [seen[i] for i in iterations]
    return iterations, costs


def generate_all_graphs(results_dir: Path, output_dir: Path) -> None:
    """Generate convergence graphs for all experiments."""
    output_dir.mkdir(exist_ok=True)

    # Data for all experiments
    experiments = {
        "exp1": {
            "db": results_dir / "exp1_gpt51_20iter_v2.db",
            "title": "Experiment 1: Two-Period Deterministic",
            "color": "blue"
        },
        "exp2": {
            "db": results_dir / "exp2_gpt51_20iter_v2.db",
            "title": "Experiment 2: Twelve-Period Stochastic",
            "color": "red"
        },
        "exp3": {
            "db": results_dir / "exp3_gpt51_20iter_v2.db",
            "title": "Experiment 3: Three-Period Joint Learning",
            "color": "green"
        }
    }

    baseline = 24978  # Baseline cost

    # Figure 1: Individual experiment graphs
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    for idx, (name, exp) in enumerate(experiments.items()):
        ax = axes[idx]
        iterations, costs = load_experiment_data(str(exp["db"]))

        # Cap very large values for visualization
        capped_costs = [min(c, 50000) if c < 1e8 else np.nan for c in costs]

        ax.plot(iterations, capped_costs, 'o-', color=exp["color"], linewidth=2, markersize=6)
        ax.axhline(y=baseline, color='gray', linestyle='--', label=f'Baseline (${baseline:,})')
        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Total Cost ($)', fontsize=12)
        ax.set_title(exp["title"], fontsize=12)
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.set_xlim(0, 21)
        ax.set_ylim(0, 35000)

        # Add best cost annotation
        valid_costs = [c for c in costs if c < 1e6]
        if valid_costs:
            best_cost = min(valid_costs)
            best_iter = costs.index(best_cost) + 1
            ax.annotate(f'Best: ${best_cost:,.0f}',
                       xy=(best_iter, best_cost),
                       xytext=(best_iter + 2, best_cost + 3000),
                       arrowprops=dict(arrowstyle='->', color=exp["color"]),
                       fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / "convergence_individual.png", dpi=150, bbox_inches='tight')
    plt.close()

    # Figure 2: Combined comparison (exp1 and exp3 only, since exp2 failed)
    fig, ax = plt.subplots(figsize=(10, 6))

    for name in ["exp1", "exp3"]:
        exp = experiments[name]
        iterations, costs = load_experiment_data(str(exp["db"]))
        ax.plot(iterations, costs, 'o-', color=exp["color"], linewidth=2,
                markersize=6, label=exp["title"])

    ax.axhline(y=baseline, color='gray', linestyle='--', linewidth=2, label=f'Baseline (${baseline:,})')
    ax.set_xlabel('Iteration', fontsize=14)
    ax.set_ylabel('Total Cost ($)', fontsize=14)
    ax.set_title('LLM Policy Optimization Convergence (GPT-5.1)', fontsize=14)
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 21)
    ax.set_ylim(0, 30000)

    plt.tight_layout()
    plt.savefig(output_dir / "convergence_comparison.png", dpi=150, bbox_inches='tight')
    plt.close()

    # Figure 3: exp2 with log scale (to show the billions)
    fig, ax = plt.subplots(figsize=(10, 6))

    iterations, costs = load_experiment_data(str(experiments["exp2"]["db"]))
    ax.semilogy(iterations, costs, 'o-', color='red', linewidth=2, markersize=6)
    ax.axhline(y=baseline, color='gray', linestyle='--', linewidth=2, label=f'Baseline (${baseline:,})')
    ax.set_xlabel('Iteration', fontsize=14)
    ax.set_ylabel('Total Cost ($) - Log Scale', fontsize=14)
    ax.set_title('Experiment 2: 12-Period Stochastic (Unstable Optimization)', fontsize=14)
    ax.legend(loc='lower right', fontsize=11)
    ax.grid(True, alpha=0.3, which='both')
    ax.set_xlim(0, 21)

    plt.tight_layout()
    plt.savefig(output_dir / "exp2_log_scale.png", dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Graphs saved to {output_dir}/")
    print("  - convergence_individual.png")
    print("  - convergence_comparison.png")
    print("  - exp2_log_scale.png")


if __name__ == "__main__":
    results_dir = Path(__file__).parent.parent / "results"
    output_dir = Path(__file__).parent.parent / "results" / "graphs"
    generate_all_graphs(results_dir, output_dir)
