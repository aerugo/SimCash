"""YAML-based experiment loading for Castro experiments.

Provides functions to list and load experiment definitions from YAML files.
This replaces the previous experiments.py module with a cleaner, data-driven approach.

Example:
    >>> from castro.experiment_loader import list_experiments, load_experiment
    >>> experiments = list_experiments()
    ['exp1', 'exp2', 'exp3']
    >>> config = load_experiment("exp1", model_override="openai:gpt-4o")
    >>> config["llm"]["model"]
    'openai:gpt-4o'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from payment_simulator.llm import LLMConfig


def get_experiments_dir() -> Path:
    """Get the directory containing experiment YAML files.

    Returns:
        Path to the experiments directory.
    """
    # The experiments directory is located at castro/experiments/
    module_dir = Path(__file__).parent.parent
    return module_dir / "experiments"


def list_experiments() -> list[str]:
    """List available experiment names.

    Returns:
        List of experiment names (without .yaml extension).
    """
    experiments_dir = get_experiments_dir()
    yaml_files = experiments_dir.glob("*.yaml")
    return sorted(p.stem for p in yaml_files)


def load_experiment(
    name: str,
    *,
    model_override: str | None = None,
    thinking_budget: int | None = None,
    reasoning_effort: str | None = None,
    max_iter_override: int | None = None,
    seed_override: int | None = None,
) -> dict[str, Any]:
    """Load an experiment configuration from YAML.

    Args:
        name: Experiment name (e.g., 'exp1', 'exp2', 'exp3').
        model_override: Override the LLM model (e.g., 'openai:gpt-4o').
        thinking_budget: Override Anthropic extended thinking budget.
        reasoning_effort: Override OpenAI reasoning effort ('low'/'medium'/'high').
        max_iter_override: Override max_iterations.
        seed_override: Override master_seed.

    Returns:
        Dictionary containing the experiment configuration.

    Raises:
        FileNotFoundError: If the experiment YAML file doesn't exist.
    """
    experiments_dir = get_experiments_dir()
    yaml_path = experiments_dir / f"{name}.yaml"

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Experiment '{name}' not found. "
            f"Expected file at: {yaml_path}"
        )

    with open(yaml_path) as f:
        config: dict[str, Any] = yaml.safe_load(f)

    # Apply overrides
    if model_override is not None:
        config.setdefault("llm", {})
        config["llm"]["model"] = model_override

    if thinking_budget is not None:
        config.setdefault("llm", {})
        config["llm"]["thinking_budget"] = thinking_budget

    if reasoning_effort is not None:
        config.setdefault("llm", {})
        config["llm"]["reasoning_effort"] = reasoning_effort

    if max_iter_override is not None:
        config.setdefault("convergence", {})
        config["convergence"]["max_iterations"] = max_iter_override

    if seed_override is not None:
        config["master_seed"] = seed_override

    return config


def get_llm_config(exp_config: dict[str, Any]) -> LLMConfig:
    """Extract LLMConfig from an experiment configuration.

    Args:
        exp_config: Experiment configuration dictionary.

    Returns:
        LLMConfig instance with the LLM settings.
    """
    llm_section = exp_config.get("llm", {})

    return LLMConfig(
        model=llm_section.get("model", "anthropic:claude-sonnet-4-5"),
        temperature=llm_section.get("temperature", 0.0),
        thinking_budget=llm_section.get("thinking_budget"),
        reasoning_effort=llm_section.get("reasoning_effort"),
    )
