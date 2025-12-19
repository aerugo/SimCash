"""Experiment configuration from YAML.

This module provides dataclasses for loading and validating
experiment configurations from YAML files.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
from payment_simulator.llm.config import LLMConfig


@dataclass(frozen=True)
class EvaluationConfig:
    """Evaluation mode configuration.

    Controls how policies are evaluated (bootstrap vs deterministic).

    Attributes:
        ticks: Number of simulation ticks per evaluation.
        mode: Evaluation mode. Valid values:
            - 'bootstrap': N samples with different seeds, paired comparison
            - 'deterministic': Alias for 'deterministic-pairwise' (backward compat)
            - 'deterministic-pairwise': Same iteration, compare old vs new on same seed
            - 'deterministic-temporal': Compare cost across iterations
        num_samples: Number of bootstrap samples (for bootstrap mode).
    """

    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    # Valid evaluation modes
    VALID_MODES: frozenset[str] = frozenset({
        "bootstrap",
        "deterministic",
        "deterministic-pairwise",
        "deterministic-temporal",
    })

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.mode not in self.VALID_MODES:
            msg = f"Invalid evaluation mode: {self.mode}. Valid modes: {sorted(self.VALID_MODES)}"
            raise ValueError(msg)

    @property
    def is_bootstrap(self) -> bool:
        """Check if using bootstrap evaluation mode."""
        return self.mode == "bootstrap"

    @property
    def is_deterministic(self) -> bool:
        """Check if using any deterministic evaluation mode."""
        return self.mode in ("deterministic", "deterministic-pairwise", "deterministic-temporal")

    @property
    def is_deterministic_pairwise(self) -> bool:
        """Check if using deterministic-pairwise mode.

        Note: Plain 'deterministic' is treated as 'deterministic-pairwise'
        for backward compatibility.
        """
        return self.mode in ("deterministic", "deterministic-pairwise")

    @property
    def is_deterministic_temporal(self) -> bool:
        """Check if using deterministic-temporal mode."""
        return self.mode == "deterministic-temporal"


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
class PromptCustomization:
    """Prompt customization configuration for LLM optimization.

    Allows experiment YAML files to inject custom text into the
    dynamically built optimization prompt. Supports:
    - `all`: Customization for all agents
    - Agent-specific customizations via agent_customizations dict

    The customization text is injected into the system prompt after
    the expert introduction section.

    Attributes:
        all: Customization text to apply to all agents.
        agent_customizations: Dict mapping agent_id to agent-specific text.

    Example YAML:
        prompt_customization:
          all: "This is a 2-period deterministic game."
          BANK_A: "Bank A optimal collateral is 0."
          BANK_B: "Bank B optimal collateral is 20000."
    """

    all: str | None = None
    agent_customizations: dict[str, str] = field(default_factory=dict)

    def get_for_agent(self, agent_id: str) -> str | None:
        """Get combined customization for a specific agent.

        Returns combined 'all' and agent-specific customization.
        If both are present, 'all' comes first.
        Blank strings and whitespace-only strings are ignored.

        Args:
            agent_id: The agent ID to get customization for.

        Returns:
            Combined customization string, or None if no customization.
        """
        parts: list[str] = []

        # Add 'all' customization if present and non-blank
        if self.all and self.all.strip():
            parts.append(self.all.strip())

        # Add agent-specific customization if present and non-blank
        agent_custom = self.agent_customizations.get(agent_id)
        if agent_custom and agent_custom.strip():
            parts.append(agent_custom.strip())

        if not parts:
            return None

        return "\n\n".join(parts)


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
        prompt_customization:
          all: "General instructions for all agents."
          BANK_A: "Bank A specific instructions."
        optimized_agents:
          - BANK_A
        policy_constraints:
          allowed_parameters:
            - name: threshold
              param_type: int
              min_value: 0
              max_value: 100
          allowed_fields:
            - balance
          allowed_actions:
            payment_tree:
              - Release
              - Hold
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
        constraints_module: Python module path for constraints (legacy).
        policy_constraints: Inline constraints from YAML (preferred).
        output: Output settings.
        master_seed: Master RNG seed for reproducibility.
        prompt_customization: Optional prompt customizations for LLM.
    """

    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceConfig
    llm: LLMConfig
    optimized_agents: tuple[str, ...]
    constraints_module: str
    output: OutputConfig | None
    master_seed: int = 42
    policy_constraints: ScenarioConstraints | None = None
    prompt_customization: PromptCustomization | None = None

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

        # Pass the YAML directory for resolving relative paths
        return cls._from_dict(data, yaml_dir=path.parent)

    @classmethod
    def _from_dict(
        cls, data: dict[str, Any], yaml_dir: Path | None = None
    ) -> ExperimentConfig:
        """Create config from dictionary.

        Args:
            data: Dictionary loaded from YAML.
            yaml_dir: Directory of the YAML file (for resolving relative paths).

        Returns:
            ExperimentConfig instance.

        Raises:
            ValueError: If required fields are missing.
            FileNotFoundError: If system_prompt_file doesn't exist.
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

        # Parse LLM config with system_prompt handling
        llm_data = data["llm"]
        system_prompt = cls._resolve_system_prompt(llm_data, yaml_dir)

        llm = LLMConfig(
            model=llm_data["model"],
            temperature=llm_data.get("temperature", 0.0),
            max_retries=llm_data.get("max_retries", 3),
            timeout_seconds=llm_data.get("timeout_seconds", 120),
            thinking_budget=llm_data.get("thinking_budget"),
            reasoning_effort=llm_data.get("reasoning_effort"),
            system_prompt=system_prompt,
        )

        # Parse output config (only if explicitly specified)
        output: OutputConfig | None = None
        if "output" in data:
            out_data = data["output"]
            output = OutputConfig(
                directory=Path(out_data.get("directory", "results")),
                database=out_data.get("database", "experiments.db"),
                verbose=out_data.get("verbose", True),
            )

        # Parse inline policy_constraints if present
        policy_constraints: ScenarioConstraints | None = None
        if "policy_constraints" in data:
            policy_constraints = ScenarioConstraints.model_validate(
                data["policy_constraints"]
            )

        # Parse prompt_customization with backward compatibility
        prompt_customization = cls._parse_prompt_customization(data, system_prompt)

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
            policy_constraints=policy_constraints,
            prompt_customization=prompt_customization,
        )

    @classmethod
    def _resolve_system_prompt(
        cls, llm_data: dict[str, Any], yaml_dir: Path | None
    ) -> str | None:
        """Resolve system_prompt from inline or file.

        Priority:
        1. Inline system_prompt (takes precedence)
        2. system_prompt_file (loaded from path)
        3. None if neither specified

        Args:
            llm_data: The llm section of the config.
            yaml_dir: Directory of YAML file for resolving relative paths.

        Returns:
            System prompt string or None.

        Raises:
            FileNotFoundError: If system_prompt_file doesn't exist.
        """
        # Inline system_prompt takes precedence
        if "system_prompt" in llm_data:
            prompt: str = llm_data["system_prompt"]
            return prompt

        # Load from file if specified
        if "system_prompt_file" in llm_data:
            prompt_path = Path(llm_data["system_prompt_file"])

            # Resolve relative path from YAML directory
            if not prompt_path.is_absolute() and yaml_dir is not None:
                prompt_path = yaml_dir / prompt_path

            if not prompt_path.exists():
                msg = f"System prompt file not found: {prompt_path}"
                raise FileNotFoundError(msg)

            return prompt_path.read_text()

        return None

    @classmethod
    def _parse_prompt_customization(
        cls, data: dict[str, Any], legacy_system_prompt: str | None
    ) -> PromptCustomization | None:
        """Parse prompt_customization from YAML data.

        Supports two formats:
        1. New format: `prompt_customization` block with `all` and agent keys
        2. Legacy format: `system_prompt` in `llm` section (converted to `all`)

        New format takes precedence if both are present.

        Args:
            data: Full YAML data dict.
            legacy_system_prompt: Resolved system_prompt from llm section (legacy).

        Returns:
            PromptCustomization if configured, None otherwise.
        """
        # Check for new format first (takes precedence)
        if "prompt_customization" in data:
            pc_data = data["prompt_customization"]

            # Handle empty dict or None
            if not pc_data:
                return None

            # Extract 'all' and agent-specific customizations
            all_customization = pc_data.get("all")
            agent_customizations: dict[str, str] = {}

            for key, value in pc_data.items():
                if key != "all" and isinstance(value, str):
                    agent_customizations[key] = value

            # If everything is empty, return None
            if not all_customization and not agent_customizations:
                return None

            return PromptCustomization(
                all=all_customization,
                agent_customizations=agent_customizations,
            )

        # Fall back to legacy system_prompt (convert to 'all')
        if legacy_system_prompt:
            return PromptCustomization(all=legacy_system_prompt)

        return None

    def load_constraints(self) -> ScenarioConstraints | None:
        """Dynamically load constraints from module path.

        DEPRECATED: Use get_constraints() instead, which supports inline constraints.

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
        constraints: ScenarioConstraints = getattr(module, variable_name)
        return constraints

    def get_constraints(self) -> ScenarioConstraints | None:
        """Get policy constraints (inline or from module).

        Returns inline policy_constraints if present, otherwise falls back
        to loading from constraints_module (legacy support).

        Returns:
            ScenarioConstraints if configured, None otherwise.

        Raises:
            ValueError: If constraints_module format is invalid.
            ImportError: If constraints module cannot be imported.
        """
        # Prefer inline policy_constraints
        if self.policy_constraints is not None:
            return self.policy_constraints

        # Fall back to legacy module loading
        return self.load_constraints()

    def with_seed(self, seed: int) -> ExperimentConfig:
        """Return a new config with the specified master seed.

        Since ExperimentConfig is frozen (immutable), this method creates
        a new instance with the updated seed while preserving all other fields.

        Args:
            seed: The new master seed value.

        Returns:
            A new ExperimentConfig with the updated master_seed.

        Example:
            >>> config = ExperimentConfig.from_yaml(path)
            >>> config.master_seed
            42
            >>> new_config = config.with_seed(12345)
            >>> new_config.master_seed
            12345
            >>> config.master_seed  # Original unchanged
            42
        """
        return replace(self, master_seed=seed)

    @classmethod
    def from_stored_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        """Reconstruct ExperimentConfig from stored config dict.

        This is used for experiment continuation - reconstructing the config
        from the JSON stored in the database.

        Args:
            data: Dictionary stored in database (from _save_experiment_start).

        Returns:
            ExperimentConfig instance.

        Raises:
            KeyError: If required fields are missing.
        """
        # Parse evaluation config
        eval_data = data.get("evaluation", {})
        evaluation = EvaluationConfig(
            mode=eval_data.get("mode", "bootstrap"),
            num_samples=eval_data.get("num_samples", 10),
            ticks=eval_data.get("ticks", 100),
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
        llm_data = data.get("llm", {})
        llm = LLMConfig(
            model=llm_data.get("model", "anthropic:claude-sonnet-4-5"),
            temperature=llm_data.get("temperature", 0.0),
            max_retries=llm_data.get("max_retries", 3),
            timeout_seconds=llm_data.get("timeout_seconds", 120),
            thinking_budget=llm_data.get("thinking_budget"),
            reasoning_effort=llm_data.get("reasoning_effort"),
            system_prompt=llm_data.get("system_prompt"),
        )

        # Parse output config (none for continuation - handled by repository)
        output: OutputConfig | None = None

        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            scenario_path=Path(data.get("scenario_path", "")),
            evaluation=evaluation,
            convergence=convergence,
            llm=llm,
            optimized_agents=tuple(data.get("optimized_agents", [])),
            constraints_module=data.get("constraints_module", ""),
            output=output,
            master_seed=data.get("master_seed", 42),
            policy_constraints=None,  # Not stored, will reload from module if needed
            prompt_customization=None,  # Not stored
        )

    def with_llm_overrides(
        self,
        model: str | None = None,
        reasoning_effort: str | None = None,
        thinking_budget: int | None = None,
    ) -> ExperimentConfig:
        """Return a new config with LLM settings overridden.

        Since ExperimentConfig is frozen (immutable), this method creates
        a new instance with updated LLM settings while preserving all other fields.

        Args:
            model: Model specification in provider:model format (e.g., "openai:gpt-4o").
            reasoning_effort: OpenAI reasoning effort level (low/medium/high).
            thinking_budget: Anthropic extended thinking budget tokens.

        Returns:
            A new ExperimentConfig with the updated LLM settings.

        Example:
            >>> config = ExperimentConfig.from_yaml(path)
            >>> config.llm.model
            'anthropic:claude-sonnet-4-5'
            >>> new_config = config.with_llm_overrides(model="openai:gpt-4o")
            >>> new_config.llm.model
            'openai:gpt-4o'
            >>> config.llm.model  # Original unchanged
            'anthropic:claude-sonnet-4-5'
        """
        # Build new LLMConfig with overrides
        new_llm = LLMConfig(
            model=model if model is not None else self.llm.model,
            temperature=self.llm.temperature,
            max_retries=self.llm.max_retries,
            timeout_seconds=self.llm.timeout_seconds,
            max_tokens=self.llm.max_tokens,
            thinking_budget=thinking_budget if thinking_budget is not None else self.llm.thinking_budget,
            reasoning_effort=reasoning_effort if reasoning_effort is not None else self.llm.reasoning_effort,
            thinking_config=self.llm.thinking_config,
            system_prompt=self.llm.system_prompt,
        )
        return replace(self, llm=new_llm)
