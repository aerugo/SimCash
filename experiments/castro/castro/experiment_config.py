"""Protocol and implementations for experiment configuration.

This module defines the interface that ExperimentRunner requires
and provides implementations for both legacy CastroExperiment
and new YAML-based configs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from dataclasses import dataclass, field

from payment_simulator.ai_cash_mgmt import (
    BootstrapConfig,
    ConvergenceCriteria,
    OutputConfig,
    SampleMethod,
)
from payment_simulator.llm import LLMConfig

# Default model for experiments
DEFAULT_MODEL = "anthropic:claude-sonnet-4-5"


@runtime_checkable
class ExperimentConfigProtocol(Protocol):
    """Protocol defining the interface for experiment configurations.

    ExperimentRunner accepts any object implementing this protocol.
    Both CastroExperiment (legacy) and YamlExperimentConfig implement it.

    Required properties:
        name: Experiment name
        description: Experiment description
        master_seed: Master seed for determinism
        scenario_path: Path to scenario configuration file
        optimized_agents: List of agent IDs to optimize

    Required methods:
        get_convergence_criteria(): Get convergence criteria configuration
        get_bootstrap_config(): Get bootstrap sampling configuration
        get_model_config(): Get LLM model configuration
        get_output_config(): Get output configuration
    """

    @property
    def name(self) -> str:
        """Experiment name."""
        ...

    @property
    def description(self) -> str:
        """Experiment description."""
        ...

    @property
    def master_seed(self) -> int:
        """Master seed for determinism."""
        ...

    @property
    def scenario_path(self) -> Path:
        """Path to scenario configuration file."""
        ...

    @property
    def optimized_agents(self) -> list[str]:
        """List of agent IDs to optimize."""
        ...

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        """Get convergence criteria configuration."""
        ...

    def get_bootstrap_config(self) -> BootstrapConfig:
        """Get bootstrap sampling configuration."""
        ...

    def get_model_config(self) -> LLMConfig:
        """Get LLM model configuration."""
        ...

    def get_output_config(self) -> OutputConfig:
        """Get output configuration."""
        ...


class YamlExperimentConfig:
    """Experiment configuration loaded from YAML.

    Wraps a dict from load_experiment() and implements
    ExperimentConfigProtocol for use with ExperimentRunner.

    Example:
        >>> from castro.experiment_loader import load_experiment
        >>> from castro.experiment_config import YamlExperimentConfig
        >>> config_dict = load_experiment("exp1")
        >>> yaml_config = YamlExperimentConfig(config_dict)
        >>> runner = ExperimentRunner(yaml_config)
    """

    def __init__(
        self, config: dict[str, Any], output_dir: Path | None = None
    ) -> None:
        """Initialize from config dict.

        Args:
            config: Dictionary from load_experiment()
            output_dir: Override for output directory
        """
        self._config = config
        self._output_dir = output_dir or Path("results")

    @property
    def name(self) -> str:
        """Experiment name."""
        return self._config["name"]

    @property
    def description(self) -> str:
        """Experiment description."""
        return self._config["description"]

    @property
    def master_seed(self) -> int:
        """Master seed for determinism."""
        return self._config.get("master_seed", 42)

    @property
    def scenario_path(self) -> Path:
        """Path to scenario configuration file."""
        # The 'scenario' key in YAML points to the relative path
        scenario = self._config.get("scenario", self._config.get("scenario_path", ""))
        return Path(scenario)

    @property
    def optimized_agents(self) -> list[str]:
        """List of agent IDs to optimize."""
        return self._config.get("optimized_agents", ["BANK_A", "BANK_B"])

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        """Get convergence criteria configuration."""
        conv = self._config.get("convergence", {})
        return ConvergenceCriteria(
            max_iterations=conv.get("max_iterations", 25),
            stability_threshold=conv.get("stability_threshold", 0.05),
            stability_window=conv.get("stability_window", 5),
        )

    def get_bootstrap_config(self) -> BootstrapConfig:
        """Get bootstrap sampling configuration."""
        eval_cfg = self._config.get("evaluation", {})
        mode = eval_cfg.get("mode", "bootstrap")
        is_deterministic = mode == "deterministic"

        # For non-deterministic mode, ensure num_samples >= 5
        num_samples = eval_cfg.get("num_samples", 10)
        if not is_deterministic and num_samples < 5:
            num_samples = 10  # Default to valid value

        return BootstrapConfig(
            deterministic=is_deterministic,
            num_samples=num_samples if not is_deterministic else 1,
            sample_method=SampleMethod.BOOTSTRAP,
            evaluation_ticks=eval_cfg.get("ticks", 100),
        )

    def get_model_config(self) -> LLMConfig:
        """Get LLM model configuration."""
        llm = self._config.get("llm", {})
        return LLMConfig(
            model=llm.get("model", "anthropic:claude-sonnet-4-5"),
            temperature=llm.get("temperature", 0.0),
            thinking_budget=llm.get("thinking_budget"),
            reasoning_effort=llm.get("reasoning_effort"),
        )

    def get_output_config(self) -> OutputConfig:
        """Get output configuration."""
        output = self._config.get("output", {})
        database = output.get("database", f"{self.name}.db")
        return OutputConfig(
            database_path=str(self._output_dir / database),
            verbose=output.get("verbose", True),
        )


@dataclass
class CastroExperiment:
    """Legacy experiment configuration (dataclass-based).

    Retained for backward compatibility with existing tests.
    For new code, use YamlExperimentConfig with YAML files.

    Implements ExperimentConfigProtocol.

    Example:
        >>> exp = CastroExperiment(
        ...     name="test",
        ...     description="Test experiment",
        ...     scenario_path=Path("configs/exp1_2period.yaml"),
        ...     deterministic=True,
        ... )
    """

    # Identity
    name: str
    description: str

    # Scenario
    scenario_path: Path

    # Deterministic mode - skip bootstrap sampling
    deterministic: bool = False
    """When True, run single deterministic evaluation instead of bootstrap sampling."""

    # Bootstrap settings (ignored if deterministic=True)
    num_samples: int = 1
    evaluation_ticks: int = 100

    # Optimization settings
    max_iterations: int = 25
    stability_threshold: float = 0.05
    stability_window: int = 5

    # LLM settings - unified model string format
    model: str = DEFAULT_MODEL
    """Model string in provider:model format (e.g., 'anthropic:claude-sonnet-4-5')."""

    temperature: float = 0.0
    """Sampling temperature (0.0 = deterministic)."""

    thinking_budget: int | None = None
    """Token budget for Anthropic extended thinking (Claude only)."""

    reasoning_effort: str | None = None
    """OpenAI reasoning effort: 'low', 'medium', or 'high' (GPT models only)."""

    # Agent settings
    optimized_agents: list[str] = field(default_factory=lambda: ["BANK_A", "BANK_B"])

    # Output settings
    output_dir: Path = field(default_factory=lambda: Path("results"))
    master_seed: int = 42

    def get_bootstrap_config(self) -> BootstrapConfig:
        """Get bootstrap configuration for this experiment."""
        return BootstrapConfig(
            deterministic=self.deterministic,
            num_samples=self.num_samples,
            sample_method=SampleMethod.BOOTSTRAP,
            evaluation_ticks=self.evaluation_ticks,
        )

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        """Get convergence criteria for this experiment."""
        return ConvergenceCriteria(
            stability_threshold=self.stability_threshold,
            stability_window=self.stability_window,
            max_iterations=self.max_iterations,
        )

    def get_model_config(self) -> LLMConfig:
        """Get unified model configuration for this experiment."""
        return LLMConfig(
            model=self.model,
            temperature=self.temperature,
            thinking_budget=self.thinking_budget,
            reasoning_effort=self.reasoning_effort,
        )

    def get_output_config(self) -> OutputConfig:
        """Get output configuration for this experiment."""
        return OutputConfig(
            database_path=str(self.output_dir / f"{self.name}.db"),
            verbose=True,
        )
