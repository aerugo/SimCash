"""YAML configuration loader."""
from pathlib import Path

import yaml

from .schemas import SimulationConfig


def load_config(config_path: str | Path) -> SimulationConfig:
    """
    Load and validate simulation configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file

    Returns:
        Validated SimulationConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
        yaml.YAMLError: If YAML parsing fails
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path) as f:
        config_dict = yaml.safe_load(f)

    if config_dict is None:
        raise ValueError(f"Empty configuration file: {config_path}")

    # Validate and create config
    try:
        config = SimulationConfig.from_dict(config_dict)
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}") from e

    return config
