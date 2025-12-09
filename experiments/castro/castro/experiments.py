"""Castro experiment definitions.

Defines the three Castro experiments for LLM-based policy optimization:
- Exp1: 2-Period Deterministic (Nash equilibrium validation)
- Exp2: 12-Period Stochastic (LVTS-style realistic scenario)
- Exp3: Joint Liquidity & Timing (combined optimization)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from payment_simulator.ai_cash_mgmt import (
    AgentOptimizationConfig,
    ConvergenceCriteria,
    LLMConfig,
    LLMProviderType,
    MonteCarloConfig,
    OptimizationSchedule,
    OptimizationScheduleType,
    OutputConfig,
    SampleMethod,
)


def _detect_provider(model: str) -> LLMProviderType:
    """Detect the LLM provider from model name.

    Args:
        model: Model name string.

    Returns:
        LLMProviderType based on model name prefix.
    """
    if model.startswith("gpt-") or model.startswith("o1") or model.startswith("o3"):
        return LLMProviderType.OPENAI
    return LLMProviderType.ANTHROPIC


@dataclass
class CastroExperiment:
    """Definition of a Castro experiment.

    Encapsulates all configuration needed to run an experiment:
    scenario path, optimization settings, and output configuration.

    Example:
        >>> exp = CastroExperiment(
        ...     name="exp1",
        ...     description="2-Period Deterministic",
        ...     scenario_path=Path("configs/exp1_2period.yaml"),
        ...     num_samples=1,
        ...     evaluation_ticks=2,
        ... )
    """

    # Identity
    name: str
    description: str

    # Scenario
    scenario_path: Path

    # Monte Carlo settings
    num_samples: int = 1
    evaluation_ticks: int = 100

    # Optimization settings
    max_iterations: int = 25
    stability_threshold: float = 0.05
    stability_window: int = 5

    # LLM settings
    llm_provider: LLMProviderType | None = None  # Auto-detected from model
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_temperature: float = 0.0

    # Agent settings
    optimized_agents: list[str] = field(default_factory=lambda: ["BANK_A", "BANK_B"])

    # Output settings
    output_dir: Path = field(default_factory=lambda: Path("results"))
    master_seed: int = 42

    def get_monte_carlo_config(self) -> MonteCarloConfig:
        """Get Monte Carlo configuration for this experiment.

        Returns:
            MonteCarloConfig instance.
        """
        return MonteCarloConfig(
            num_samples=self.num_samples,
            sample_method=SampleMethod.BOOTSTRAP,
            evaluation_ticks=self.evaluation_ticks,
        )

    def get_convergence_criteria(self) -> ConvergenceCriteria:
        """Get convergence criteria for this experiment.

        Returns:
            ConvergenceCriteria instance.
        """
        return ConvergenceCriteria(
            stability_threshold=self.stability_threshold,
            stability_window=self.stability_window,
            max_iterations=self.max_iterations,
        )

    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration for this experiment.

        Auto-detects provider from model name if not explicitly set.

        Returns:
            LLMConfig instance.
        """
        provider = self.llm_provider or _detect_provider(self.llm_model)
        return LLMConfig(
            provider=provider,
            model=self.llm_model,
            temperature=self.llm_temperature,
            max_retries=3,
        )

    def get_output_config(self) -> OutputConfig:
        """Get output configuration for this experiment.

        Returns:
            OutputConfig instance.
        """
        return OutputConfig(
            database_path=str(self.output_dir / f"{self.name}.db"),
            verbose=True,
        )

    def get_agent_configs(self) -> dict[str, AgentOptimizationConfig]:
        """Get agent optimization configurations.

        Returns:
            Dict mapping agent IDs to AgentOptimizationConfig.
        """
        return {agent_id: AgentOptimizationConfig() for agent_id in self.optimized_agents}

    def get_optimization_schedule(self) -> OptimizationSchedule:
        """Get optimization schedule for this experiment.

        Returns:
            OptimizationSchedule instance.
        """
        return OptimizationSchedule(
            type=OptimizationScheduleType.ON_SIMULATION_END,
            min_remaining_repetitions=1,
        )


def create_exp1(
    output_dir: Path | None = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 1: 2-Period Deterministic.

    Validates Nash equilibrium with deferred crediting.

    Setup:
    - 2 ticks per day, 1 day
    - Deterministic payment arrivals
    - Expected: Bank A posts 0, Bank B posts 20000

    Note: Uses minimum values for Monte Carlo config (5 samples, 10 ticks)
    even though the scenario is deterministic. Extra ticks are idle,
    and all samples will produce identical results.

    Args:
        output_dir: Output directory for results.
        model: LLM model to use.

    Returns:
        CastroExperiment configuration.
    """
    return CastroExperiment(
        name="exp1",
        description="2-Period Deterministic Nash Equilibrium",
        scenario_path=Path("configs/exp1_2period.yaml"),
        num_samples=5,  # Minimum for MonteCarloConfig (deterministic gives same results)
        evaluation_ticks=10,  # Minimum for MonteCarloConfig (ticks 2-9 are idle)
        max_iterations=25,
        stability_threshold=0.05,
        stability_window=5,
        llm_model=model,
        optimized_agents=["BANK_A", "BANK_B"],
        output_dir=output_dir or Path("results"),
        master_seed=42,
    )


def create_exp2(
    output_dir: Path | None = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 2: 12-Period Stochastic.

    LVTS-style realistic scenario with stochastic arrivals.

    Setup:
    - 12 ticks per day
    - Poisson arrivals, LogNormal amounts
    - 10 seeds for Monte Carlo evaluation

    Args:
        output_dir: Output directory for results.
        model: LLM model to use.

    Returns:
        CastroExperiment configuration.
    """
    return CastroExperiment(
        name="exp2",
        description="12-Period Stochastic LVTS-Style",
        scenario_path=Path("configs/exp2_12period.yaml"),
        num_samples=10,  # Monte Carlo with 10 seeds
        evaluation_ticks=12,
        max_iterations=25,
        stability_threshold=0.05,
        stability_window=5,
        llm_model=model,
        optimized_agents=["BANK_A", "BANK_B"],
        output_dir=output_dir or Path("results"),
        master_seed=42,
    )


def create_exp3(
    output_dir: Path | None = None,
    model: str = "claude-sonnet-4-5-20250929",
) -> CastroExperiment:
    """Experiment 3: Joint Liquidity & Timing.

    Optimizes both initial collateral AND payment timing jointly.

    Setup:
    - 3 ticks per day (evaluated over 10 ticks minimum)
    - Tests interaction between liquidity and timing decisions

    Note: Uses minimum evaluation_ticks of 10 for MonteCarloConfig validation.
    The scenario runs 3 ticks per day, remaining ticks are idle.

    Args:
        output_dir: Output directory for results.
        model: LLM model to use.

    Returns:
        CastroExperiment configuration.
    """
    return CastroExperiment(
        name="exp3",
        description="Joint Liquidity & Timing Optimization",
        scenario_path=Path("configs/exp3_joint.yaml"),
        num_samples=10,  # Monte Carlo with 10 seeds
        evaluation_ticks=10,  # Minimum for MonteCarloConfig (ticks 3-9 are idle)
        max_iterations=25,
        stability_threshold=0.05,
        stability_window=5,
        llm_model=model,
        optimized_agents=["BANK_A", "BANK_B"],
        output_dir=output_dir or Path("results"),
        master_seed=42,
    )


# Registry of experiment factory functions
EXPERIMENTS: dict[str, Callable[..., CastroExperiment]] = {
    "exp1": create_exp1,
    "exp2": create_exp2,
    "exp3": create_exp3,
}
