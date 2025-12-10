"""Experiment configuration from YAML.

This module provides dataclasses for loading and validating
experiment configurations from YAML files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from payment_simulator.llm.config import LLMConfig


@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation mode configuration.

    Controls how policies are evaluated (bootstrap vs deterministic).

    Attributes:
        ticks: Number of simulation ticks per evaluation.
        mode: Evaluation mode ('bootstrap' or 'deterministic').
        num_samples: Number of bootstrap samples (for bootstrap mode).
    """

    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.mode not in ("bootstrap", "deterministic"):
            msg = f"Invalid evaluation mode: {self.mode}"
            raise ValueError(msg)


@dataclass(frozen=True)
class OutputConfig:
    """Output configuration.

    Controls where experiment results are stored.

    Attributes:
        directory: Output directory for results.
        database: Database filename for persistence.
        verbose: Whether to enable verbose output.
    """

    directory: Path = field(default_factory=lambda: Path("results"))
    database: str = "experiments.db"
    verbose: bool = True


@dataclass(frozen=True)
class ConvergenceConfig:
    """Convergence criteria configuration.

    Controls when the optimization loop terminates.

    Attributes:
        max_iterations: Maximum number of optimization iterations.
        stability_threshold: Cost variance threshold for stability.
        stability_window: Number of iterations to check for stability.
        improvement_threshold: Minimum improvement to continue.
    """

    max_iterations: int = 50
    stability_threshold: float = 0.05
    stability_window: int = 5
    improvement_threshold: float = 0.01


@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment configuration loaded from YAML.

    Defines all settings needed to run an experiment.

    Example YAML:
        name: exp1
        description: "2-Period Deterministic"
        scenario: configs/exp1_2period.yaml
        evaluation:
          mode: bootstrap
          num_samples: 10
          ticks: 12
        convergence:
          max_iterations: 25
        llm:
          model: "anthropic:claude-sonnet-4-5"
        optimized_agents:
          - BANK_A
        constraints: castro.constraints.CASTRO_CONSTRAINTS
        output:
          directory: results

    Attributes:
        name: Experiment name (identifier).
        description: Human-readable description.
        scenario_path: Path to scenario configuration YAML.
        evaluation: Evaluation mode settings.
        convergence: Convergence criteria.
        llm: LLM configuration.
        optimized_agents: Tuple of agent IDs to optimize.
        constraints_module: Python module path for constraints.
        output: Output settings.
        master_seed: Master RNG seed for reproducibility.
    """

    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceConfig
    llm: LLMConfig
    optimized_agents: tuple[str, ...]
    constraints_module: str
    output: OutputConfig
    master_seed: int = 42

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        """Load experiment config from YAML file.

        Args:
            path: Path to experiment YAML file.

        Returns:
            ExperimentConfig loaded from file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            yaml.YAMLError: If YAML is invalid.
            ValueError: If required fields missing.
        """
        if not path.exists():
            msg = f"Experiment config not found: {path}"
            raise FileNotFoundError(msg)

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary loaded from YAML.

        Returns:
            ExperimentConfig instance.

        Raises:
            ValueError: If required fields are missing.
        """
        # Validate required fields
        required = [
            "name",
            "scenario",
            "evaluation",
            "convergence",
            "llm",
            "optimized_agents",
        ]
        missing = [f for f in required if f not in data]
        if missing:
            msg = f"Missing required fields: {missing}"
            raise ValueError(msg)

        # Parse evaluation config
        eval_data = data["evaluation"]
        evaluation = EvaluationConfig(
            mode=eval_data.get("mode", "bootstrap"),
            num_samples=eval_data.get("num_samples", 10),
            ticks=eval_data["ticks"],
        )

        # Parse convergence config
        conv_data = data.get("convergence", {})
        convergence = ConvergenceConfig(
            max_iterations=conv_data.get("max_iterations", 50),
            stability_threshold=conv_data.get("stability_threshold", 0.05),
            stability_window=conv_data.get("stability_window", 5),
            improvement_threshold=conv_data.get("improvement_threshold", 0.01),
        )

        # Parse LLM config
        llm_data = data["llm"]
        llm = LLMConfig(
            model=llm_data["model"],
            temperature=llm_data.get("temperature", 0.0),
            max_retries=llm_data.get("max_retries", 3),
            timeout_seconds=llm_data.get("timeout_seconds", 120),
            thinking_budget=llm_data.get("thinking_budget"),
            reasoning_effort=llm_data.get("reasoning_effort"),
        )

        # Parse output config
        out_data = data.get("output", {})
        output = OutputConfig(
            directory=Path(out_data.get("directory", "results")),
            database=out_data.get("database", "experiments.db"),
            verbose=out_data.get("verbose", True),
        )

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            scenario_path=Path(data["scenario"]),
            evaluation=evaluation,
            convergence=convergence,
            llm=llm,
            optimized_agents=tuple(data["optimized_agents"]),
            constraints_module=data.get("constraints", ""),
            output=output,
            master_seed=data.get("master_seed", 42),
        )

    def load_constraints(self) -> Any:
        """Dynamically load constraints from module path.

        Returns:
            ScenarioConstraints loaded from constraints_module.

        Raises:
            ValueError: If constraints_module format is invalid.
            ImportError: If module cannot be imported.
        """
        import importlib

        if not self.constraints_module:
            return None

        # Parse "module.path.VARIABLE"
        parts = self.constraints_module.rsplit(".", 1)
        if len(parts) != 2:
            msg = f"Invalid constraints module format: {self.constraints_module}"
            raise ValueError(msg)

        module_path, variable_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, variable_name)
