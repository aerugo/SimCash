"""Pydantic schemas for configuration validation."""
from typing import Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# Distribution Schemas
# ============================================================================

class NormalDistribution(BaseModel):
    """Normal (Gaussian) distribution."""
    type: Literal["Normal"] = "Normal"
    mean: int = Field(..., description="Mean value in cents")
    std_dev: int = Field(..., description="Standard deviation in cents", gt=0)


class LogNormalDistribution(BaseModel):
    """Log-normal distribution (right-skewed)."""
    type: Literal["LogNormal"] = "LogNormal"
    mean_log: float = Field(..., description="Mean of log values")
    std_dev_log: float = Field(..., description="Std dev of log values", gt=0)


class UniformDistribution(BaseModel):
    """Uniform distribution."""
    type: Literal["Uniform"] = "Uniform"
    min: int = Field(..., description="Minimum value in cents", ge=0)
    max: int = Field(..., description="Maximum value in cents")

    @field_validator("max")
    @classmethod
    def max_must_be_greater_than_min(cls, v, info):
        """Validate max > min."""
        if "min" in info.data and v <= info.data["min"]:
            raise ValueError("max must be greater than min")
        return v


class ExponentialDistribution(BaseModel):
    """Exponential distribution."""
    type: Literal["Exponential"] = "Exponential"
    lambda_: float = Field(..., alias="lambda", description="Rate parameter", gt=0)


# Union type for all distributions
AmountDistribution = Union[
    NormalDistribution,
    LogNormalDistribution,
    UniformDistribution,
    ExponentialDistribution,
]


# ============================================================================
# Arrival Configuration
# ============================================================================

class ArrivalConfig(BaseModel):
    """Configuration for automatic transaction arrival generation."""

    rate_per_tick: float = Field(..., description="Expected arrivals per tick (Poisson λ)", ge=0)
    amount_distribution: AmountDistribution = Field(..., description="Transaction amount distribution")
    counterparty_weights: Dict[str, float] = Field(
        ..., description="Weights for selecting receiver agents"
    )
    deadline_range: List[int] = Field(
        ..., description="[min_ticks, max_ticks] until deadline", min_length=2, max_length=2
    )
    priority: int = Field(5, description="Transaction priority (0-10)", ge=0, le=10)
    divisible: bool = Field(False, description="Whether transactions can be split")

    @field_validator("deadline_range")
    @classmethod
    def validate_deadline_range(cls, v):
        """Validate deadline range [min, max]."""
        if len(v) != 2:
            raise ValueError("deadline_range must have exactly 2 elements [min, max]")
        min_val, max_val = v
        if min_val <= 0:
            raise ValueError("deadline range min must be > 0")
        if max_val < min_val:
            raise ValueError("deadline range max must be >= min")
        return v

    @field_validator("counterparty_weights")
    @classmethod
    def validate_weights(cls, v):
        """Validate counterparty weights sum to positive value."""
        if not v:
            raise ValueError("counterparty_weights cannot be empty")
        total = sum(v.values())
        if total <= 0:
            raise ValueError("counterparty_weights must sum to positive value")
        return v


# ============================================================================
# Policy Configuration
# ============================================================================

class FifoPolicy(BaseModel):
    """FIFO policy (submit all immediately)."""
    type: Literal["Fifo"] = "Fifo"


class DeadlinePolicy(BaseModel):
    """Deadline-based policy (prioritize urgent)."""
    type: Literal["Deadline"] = "Deadline"
    urgency_threshold: int = Field(..., description="Ticks before deadline to consider urgent", gt=0)


class LiquidityAwarePolicy(BaseModel):
    """Liquidity-aware policy (preserve buffer)."""
    type: Literal["LiquidityAware"] = "LiquidityAware"
    target_buffer: int = Field(..., description="Target minimum balance to maintain (cents)", ge=0)
    urgency_threshold: int = Field(..., description="Ticks before deadline to override buffer", gt=0)


class LiquiditySplittingPolicy(BaseModel):
    """Liquidity splitting policy (split large payments)."""
    type: Literal["LiquiditySplitting"] = "LiquiditySplitting"
    max_splits: int = Field(..., description="Maximum number of splits allowed", ge=2, le=10)
    min_split_amount: int = Field(..., description="Minimum amount per split (cents)", gt=0)


class MockSplittingPolicy(BaseModel):
    """Mock splitting policy for testing."""
    type: Literal["MockSplitting"] = "MockSplitting"
    num_splits: int = Field(..., description="Number of splits to create", ge=2, le=10)


# Union type for all policies
PolicyConfig = Union[
    FifoPolicy,
    DeadlinePolicy,
    LiquidityAwarePolicy,
    LiquiditySplittingPolicy,
    MockSplittingPolicy,
]


# ============================================================================
# Agent Configuration
# ============================================================================

class AgentConfig(BaseModel):
    """Configuration for a single agent (bank)."""

    id: str = Field(..., description="Unique agent identifier")
    opening_balance: int = Field(..., description="Opening balance in cents")
    credit_limit: int = Field(0, description="Intraday credit limit in cents", ge=0)
    policy: PolicyConfig = Field(..., description="Cash manager policy configuration")
    arrival_config: Optional[ArrivalConfig] = Field(None, description="Arrival generation config (if any)")

    @field_validator("id")
    @classmethod
    def validate_id(cls, v):
        """Validate agent ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Agent ID cannot be empty")
        return v


# ============================================================================
# Cost Rates Configuration
# ============================================================================

class CostRates(BaseModel):
    """Cost calculation rates."""

    overdraft_bps_per_tick: float = Field(
        0.001, description="Overdraft cost in basis points per tick", ge=0
    )
    delay_cost_per_tick_per_cent: float = Field(
        0.0001, description="Delay cost per tick per cent of queued value", ge=0
    )
    eod_penalty_per_transaction: int = Field(
        10_000, description="End-of-day penalty per unsettled transaction (cents)", ge=0
    )
    deadline_penalty: int = Field(
        50_000, description="Penalty for missing deadline (cents)", ge=0
    )
    split_friction_cost: int = Field(
        1000, description="Friction cost per split (cents)", ge=0
    )


# ============================================================================
# LSM Configuration
# ============================================================================

class LsmConfig(BaseModel):
    """Liquidity-Saving Mechanism configuration."""

    enabled: bool = Field(True, description="Enable LSM optimization")
    bilateral_enabled: bool = Field(True, description="Enable bilateral offsetting")
    cycle_detection_enabled: bool = Field(True, description="Enable cycle detection")
    max_iterations: int = Field(3, description="Maximum LSM optimization iterations", ge=1, le=10)


# ============================================================================
# Simulation Configuration
# ============================================================================

class SimulationSettings(BaseModel):
    """Core simulation parameters."""

    ticks_per_day: int = Field(..., description="Number of ticks per business day", gt=0)
    num_days: int = Field(..., description="Number of business days to simulate", gt=0)
    rng_seed: int = Field(..., description="RNG seed for deterministic simulation")


class SimulationConfig(BaseModel):
    """Complete simulation configuration."""

    simulation: SimulationSettings = Field(..., description="Core simulation settings")
    agents: List[AgentConfig] = Field(..., description="Agent configurations", min_length=1)
    cost_rates: CostRates = Field(default_factory=CostRates, description="Cost calculation rates")
    lsm_config: LsmConfig = Field(default_factory=LsmConfig, description="LSM configuration")

    @field_validator("agents")
    @classmethod
    def validate_unique_agent_ids(cls, v):
        """Validate that all agent IDs are unique."""
        ids = [agent.id for agent in v]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            raise ValueError(f"Duplicate agent IDs found: {duplicates}")
        return v

    @model_validator(mode="after")
    def validate_counterparty_references(self):
        """Validate that counterparty weights reference existing agents."""
        agent_ids = {agent.id for agent in self.agents}

        for agent in self.agents:
            if agent.arrival_config:
                for counterparty in agent.arrival_config.counterparty_weights.keys():
                    if counterparty not in agent_ids:
                        raise ValueError(
                            f"Agent {agent.id} references unknown counterparty: {counterparty}"
                        )

        return self

    def to_ffi_dict(self) -> dict:
        """Convert to dictionary format expected by FFI layer."""
        return {
            "ticks_per_day": self.simulation.ticks_per_day,
            "num_days": self.simulation.num_days,
            "rng_seed": self.simulation.rng_seed,
            "agent_configs": [self._agent_to_ffi_dict(agent) for agent in self.agents],
            "cost_rates": {
                "overdraft_bps_per_tick": self.cost_rates.overdraft_bps_per_tick,
                "delay_cost_per_tick_per_cent": self.cost_rates.delay_cost_per_tick_per_cent,
                "eod_penalty_per_transaction": self.cost_rates.eod_penalty_per_transaction,
                "deadline_penalty": self.cost_rates.deadline_penalty,
                "split_friction_cost": self.cost_rates.split_friction_cost,
            },
            "lsm_config": {
                "enabled": self.lsm_config.enabled,
                "bilateral_enabled": self.lsm_config.bilateral_enabled,
                "cycle_detection_enabled": self.lsm_config.cycle_detection_enabled,
                "max_iterations": self.lsm_config.max_iterations,
            },
        }

    def _agent_to_ffi_dict(self, agent: AgentConfig) -> dict:
        """Convert agent config to FFI dict format."""
        result = {
            "id": agent.id,
            "opening_balance": agent.opening_balance,
            "credit_limit": agent.credit_limit,
            "policy": self._policy_to_ffi_dict(agent.policy),
        }

        if agent.arrival_config:
            result["arrival_config"] = {
                "rate_per_tick": agent.arrival_config.rate_per_tick,
                "amount_distribution": self._distribution_to_ffi_dict(
                    agent.arrival_config.amount_distribution
                ),
                "counterparty_weights": agent.arrival_config.counterparty_weights,
                "deadline_range": agent.arrival_config.deadline_range,
                "priority": agent.arrival_config.priority,
                "divisible": agent.arrival_config.divisible,
            }

        return result

    def _policy_to_ffi_dict(self, policy: PolicyConfig) -> dict:
        """Convert policy config to FFI dict format."""
        if isinstance(policy, FifoPolicy):
            return {"type": "Fifo"}
        elif isinstance(policy, DeadlinePolicy):
            return {"type": "Deadline", "urgency_threshold": policy.urgency_threshold}
        elif isinstance(policy, LiquidityAwarePolicy):
            return {
                "type": "LiquidityAware",
                "target_buffer": policy.target_buffer,
                "urgency_threshold": policy.urgency_threshold,
            }
        elif isinstance(policy, LiquiditySplittingPolicy):
            return {
                "type": "LiquiditySplitting",
                "max_splits": policy.max_splits,
                "min_split_amount": policy.min_split_amount,
            }
        elif isinstance(policy, MockSplittingPolicy):
            return {"type": "MockSplitting", "num_splits": policy.num_splits}
        else:
            raise ValueError(f"Unknown policy type: {type(policy)}")

    def _distribution_to_ffi_dict(self, dist: AmountDistribution) -> dict:
        """Convert distribution config to FFI dict format."""
        if isinstance(dist, NormalDistribution):
            return {"type": "Normal", "mean": dist.mean, "std_dev": dist.std_dev}
        elif isinstance(dist, LogNormalDistribution):
            return {"type": "LogNormal", "mean_log": dist.mean_log, "std_dev_log": dist.std_dev_log}
        elif isinstance(dist, UniformDistribution):
            return {"type": "Uniform", "min": dist.min, "max": dist.max}
        elif isinstance(dist, ExponentialDistribution):
            return {"type": "Exponential", "lambda": dist.lambda_}
        else:
            raise ValueError(f"Unknown distribution type: {type(dist)}")

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SimulationConfig":
        """Create config from dictionary."""
        return cls.model_validate(config_dict)
