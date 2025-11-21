"""Unit tests for priority distribution configuration.

TDD tests for Phase 1 of priority system redesign.
Tests the Python schema validation for priority distributions.
"""

import pytest
from pydantic import ValidationError

from payment_simulator.config.schemas import (
    ArrivalConfig,
    AgentConfig,
    SimulationConfig,
    FifoPolicy,
)


class TestPriorityDistributionSchema:
    """Test priority distribution schema validation."""

    def test_legacy_single_priority_still_works(self):
        """Backward compatibility: single integer priority should still work."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority=5,  # Legacy single value
            divisible=False,
        )
        assert config.priority == 5

    def test_categorical_priority_distribution(self):
        """Categorical distribution should be accepted."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority_distribution={
                "type": "Categorical",
                "values": [3, 5, 7, 9],
                "weights": [0.25, 0.50, 0.15, 0.10],
            },
            divisible=False,
        )
        assert config.priority_distribution is not None
        assert config.priority_distribution.type == "Categorical"
        assert config.priority_distribution.values == [3, 5, 7, 9]
        assert config.priority_distribution.weights == [0.25, 0.50, 0.15, 0.10]

    def test_uniform_priority_distribution(self):
        """Uniform priority distribution should be accepted."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority_distribution={
                "type": "Uniform",
                "min": 3,
                "max": 8,
            },
            divisible=False,
        )
        assert config.priority_distribution is not None
        assert config.priority_distribution.type == "Uniform"
        assert config.priority_distribution.min == 3
        assert config.priority_distribution.max == 8

    def test_priority_distribution_overrides_single_priority(self):
        """When both priority and priority_distribution are set, distribution wins."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority=5,  # This should be ignored
            priority_distribution={
                "type": "Categorical",
                "values": [3, 7, 9],
                "weights": [0.5, 0.3, 0.2],
            },
            divisible=False,
        )
        # Distribution takes precedence
        assert config.priority_distribution is not None
        assert config.get_effective_priority_config()["type"] == "Categorical"

    def test_categorical_values_must_be_0_to_10(self):
        """Categorical values must be in valid priority range 0-10."""
        with pytest.raises(ValidationError) as exc_info:
            ArrivalConfig(
                rate_per_tick=1.0,
                amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
                counterparty_weights={"BANK_B": 1.0},
                deadline_range=[10, 50],
                priority_distribution={
                    "type": "Categorical",
                    "values": [3, 5, 15],  # 15 is invalid
                    "weights": [0.3, 0.4, 0.3],
                },
                divisible=False,
            )
        assert "priority value must be between 0 and 10" in str(exc_info.value).lower()

    def test_categorical_weights_must_sum_to_positive(self):
        """Categorical weights must sum to a positive value."""
        with pytest.raises(ValidationError) as exc_info:
            ArrivalConfig(
                rate_per_tick=1.0,
                amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
                counterparty_weights={"BANK_B": 1.0},
                deadline_range=[10, 50],
                priority_distribution={
                    "type": "Categorical",
                    "values": [3, 5, 7],
                    "weights": [0.0, 0.0, 0.0],  # All zero
                },
                divisible=False,
            )
        assert "weights must sum to positive" in str(exc_info.value).lower()

    def test_categorical_values_weights_length_mismatch(self):
        """Categorical values and weights must have same length."""
        with pytest.raises(ValidationError) as exc_info:
            ArrivalConfig(
                rate_per_tick=1.0,
                amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
                counterparty_weights={"BANK_B": 1.0},
                deadline_range=[10, 50],
                priority_distribution={
                    "type": "Categorical",
                    "values": [3, 5, 7, 9],  # 4 values
                    "weights": [0.5, 0.5],  # 2 weights
                },
                divisible=False,
            )
        assert "same length" in str(exc_info.value).lower()

    def test_uniform_min_max_validation(self):
        """Uniform distribution min must be <= max."""
        with pytest.raises(ValidationError) as exc_info:
            ArrivalConfig(
                rate_per_tick=1.0,
                amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
                counterparty_weights={"BANK_B": 1.0},
                deadline_range=[10, 50],
                priority_distribution={
                    "type": "Uniform",
                    "min": 8,
                    "max": 3,  # min > max
                },
                divisible=False,
            )
        assert "max must be greater" in str(exc_info.value).lower() or "min" in str(exc_info.value).lower()

    def test_uniform_range_must_be_0_to_10(self):
        """Uniform range must be within 0-10."""
        with pytest.raises(ValidationError) as exc_info:
            ArrivalConfig(
                rate_per_tick=1.0,
                amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
                counterparty_weights={"BANK_B": 1.0},
                deadline_range=[10, 50],
                priority_distribution={
                    "type": "Uniform",
                    "min": 5,
                    "max": 15,  # 15 is out of range
                },
                divisible=False,
            )
        assert "10" in str(exc_info.value) or "range" in str(exc_info.value).lower()


class TestPriorityDistributionFFIConversion:
    """Test conversion of priority distribution to FFI dict format."""

    def test_legacy_priority_converts_to_fixed_distribution(self):
        """Legacy single priority converts to Fixed distribution in FFI."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority=7,
            divisible=False,
        )

        # Create a minimal SimulationConfig to test FFI conversion
        sim_config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                AgentConfig(
                    id="BANK_A",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                    arrival_config=config,
                ),
                AgentConfig(
                    id="BANK_B",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                ),
            ],
        )

        ffi_dict = sim_config.to_ffi_dict()
        arrival_config = ffi_dict["agent_configs"][0]["arrival_config"]

        # Should have priority_distribution with type Fixed
        assert "priority_distribution" in arrival_config
        assert arrival_config["priority_distribution"]["type"] == "Fixed"
        assert arrival_config["priority_distribution"]["value"] == 7

    def test_categorical_distribution_converts_correctly(self):
        """Categorical distribution converts to FFI dict correctly."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority_distribution={
                "type": "Categorical",
                "values": [3, 5, 7, 9],
                "weights": [0.25, 0.50, 0.15, 0.10],
            },
            divisible=False,
        )

        sim_config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                AgentConfig(
                    id="BANK_A",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                    arrival_config=config,
                ),
                AgentConfig(
                    id="BANK_B",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                ),
            ],
        )

        ffi_dict = sim_config.to_ffi_dict()
        arrival_config = ffi_dict["agent_configs"][0]["arrival_config"]

        assert "priority_distribution" in arrival_config
        assert arrival_config["priority_distribution"]["type"] == "Categorical"
        assert arrival_config["priority_distribution"]["values"] == [3, 5, 7, 9]
        assert arrival_config["priority_distribution"]["weights"] == [0.25, 0.50, 0.15, 0.10]

    def test_uniform_distribution_converts_correctly(self):
        """Uniform distribution converts to FFI dict correctly."""
        config = ArrivalConfig(
            rate_per_tick=1.0,
            amount_distribution={"type": "Uniform", "min": 1000, "max": 10000},
            counterparty_weights={"BANK_B": 1.0},
            deadline_range=[10, 50],
            priority_distribution={
                "type": "Uniform",
                "min": 3,
                "max": 8,
            },
            divisible=False,
        )

        sim_config = SimulationConfig(
            simulation={"ticks_per_day": 100, "num_days": 1, "rng_seed": 42},
            agents=[
                AgentConfig(
                    id="BANK_A",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                    arrival_config=config,
                ),
                AgentConfig(
                    id="BANK_B",
                    opening_balance=1000000,
                    policy=FifoPolicy(),
                ),
            ],
        )

        ffi_dict = sim_config.to_ffi_dict()
        arrival_config = ffi_dict["agent_configs"][0]["arrival_config"]

        assert "priority_distribution" in arrival_config
        assert arrival_config["priority_distribution"]["type"] == "Uniform"
        assert arrival_config["priority_distribution"]["min"] == 3
        assert arrival_config["priority_distribution"]["max"] == 8
