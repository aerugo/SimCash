"""Experiment definitions for castro experiments.

Contains the registry of available experiments with their configurations.
Each experiment definition specifies paths, seeds, iteration limits, and
whether to enforce Castro paper constraints.
"""

from __future__ import annotations

from typing import TypedDict


class ExperimentDefinition(TypedDict, total=False):
    """Definition of an experiment from the registry.

    All paths are relative to SimCash root.
    """

    name: str
    description: str
    config_path: str
    policy_a_path: str
    policy_b_path: str
    num_seeds: int
    max_iterations: int
    convergence_threshold: float
    convergence_window: int
    castro_mode: bool


# ============================================================================
# Experiment Registry
# ============================================================================

EXPERIMENTS: dict[str, ExperimentDefinition] = {
    # Castro-aligned experiments (with deferred_crediting and deadline_cap_at_eod)
    # castro_mode=True enforces Castro paper constraints:
    # - Only Release/Hold actions (no Split, ReleaseWithCredit)
    # - Collateral posting only at tick 0 (no mid-day changes)
    # - No reactive end-of-tick collateral tree
    # - No bank-level budgeting (only NoAction)
    "exp1": {
        "name": "Experiment 1: Two-Period Deterministic (Castro-Aligned)",
        "description": "2-period Nash equilibrium validation with deferred crediting",
        "config_path": "experiments/castro/configs/castro_2period_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 1,  # Deterministic - only need 1 seed
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
        "castro_mode": True,  # Enforce Castro paper constraints
    },
    "exp2": {
        "name": "Experiment 2: Twelve-Period Stochastic (Castro-Aligned)",
        "description": "12-period LVTS-style with deferred crediting and EOD deadline cap",
        "config_path": "experiments/castro/configs/castro_12period_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 10,
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
        "castro_mode": True,  # Enforce Castro paper constraints
    },
    "exp3": {
        "name": "Experiment 3: Joint Liquidity and Timing (Castro-Aligned)",
        "description": "3-period joint learning with deferred crediting",
        "config_path": "experiments/castro/configs/castro_joint_aligned.yaml",
        "policy_a_path": "experiments/castro/policies/seed_policy.json",
        "policy_b_path": "experiments/castro/policies/seed_policy.json",
        "num_seeds": 10,
        "max_iterations": 25,
        "convergence_threshold": 0.05,
        "convergence_window": 5,  # Require 5 stable iterations before converging
        "castro_mode": True,  # Enforce Castro paper constraints
    },
}


def get_experiment(key: str) -> ExperimentDefinition:
    """Get an experiment definition by key.

    Args:
        key: Experiment key (e.g., 'exp1', 'exp2')

    Returns:
        ExperimentDefinition for the requested experiment

    Raises:
        KeyError: If experiment key not found
    """
    if key not in EXPERIMENTS:
        available = ", ".join(sorted(EXPERIMENTS.keys()))
        raise KeyError(f"Unknown experiment '{key}'. Available: {available}")
    return EXPERIMENTS[key]


def list_experiments() -> list[str]:
    """List available experiment keys."""
    return sorted(EXPERIMENTS.keys())


def get_experiment_summary() -> str:
    """Get a formatted summary of all experiments."""
    lines = ["Available Experiments:", ""]
    for key, exp in sorted(EXPERIMENTS.items()):
        lines.append(f"  {key}: {exp['name']}")
        lines.append(f"       {exp['description']}")
        lines.append(f"       Seeds: {exp['num_seeds']}, Max Iterations: {exp['max_iterations']}")
        lines.append("")
    return "\n".join(lines)
