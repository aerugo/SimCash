"""Pydantic schemas for configuration validation."""
import json
from pathlib import Path
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
    mean: float = Field(..., description="Mean parameter for log-normal distribution")
    std_dev: float = Field(..., description="Std dev parameter for log-normal distribution", gt=0)


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
# Scenario Events Configuration
# ============================================================================

class OneTimeSchedule(BaseModel):
    """One-time event schedule (executes once)."""
    type: Literal["OneTime"] = "OneTime"
    tick: int = Field(..., description="Tick number when event executes", ge=0)


class RepeatingSchedule(BaseModel):
    """Repeating event schedule (executes at regular intervals)."""
    type: Literal["Repeating"] = "Repeating"
    start_tick: int = Field(..., description="First tick when event executes", ge=0)
    interval: int = Field(..., description="Ticks between executions", gt=0)


EventSchedule = Union[OneTimeSchedule, RepeatingSchedule]


class DirectTransferEvent(BaseModel):
    """Direct balance transfer between agents."""
    type: Literal["DirectTransfer"] = "DirectTransfer"
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str = Field(..., description="Destination agent ID")
    amount: int = Field(..., description="Amount to transfer (cents)", gt=0)
    schedule: EventSchedule = Field(..., description="When event executes")


class CustomTransactionArrivalEvent(BaseModel):
    """Schedule a custom transaction arrival through normal settlement path."""
    type: Literal["CustomTransactionArrival"] = "CustomTransactionArrival"
    from_agent: str = Field(..., description="Source agent ID")
    to_agent: str = Field(..., description="Destination agent ID")
    amount: int = Field(..., description="Amount to transfer (cents)", gt=0)
    priority: Optional[int] = Field(None, description="Transaction priority (0-10, default 5)", ge=0, le=10)
    deadline: Optional[int] = Field(None, description="Deadline in ticks from arrival (default: auto)", gt=0)
    is_divisible: Optional[bool] = Field(None, description="Whether transaction can be split (default: false)")
    schedule: EventSchedule = Field(..., description="When event executes")


class CollateralAdjustmentEvent(BaseModel):
    """Adjust agent's credit limit (collateral)."""
    type: Literal["CollateralAdjustment"] = "CollateralAdjustment"
    agent: str = Field(..., description="Agent ID")
    delta: int = Field(..., description="Change in credit limit (cents)")
    schedule: EventSchedule = Field(..., description="When event executes")


class GlobalArrivalRateChangeEvent(BaseModel):
    """Multiply all agents' arrival rates by a factor."""
    type: Literal["GlobalArrivalRateChange"] = "GlobalArrivalRateChange"
    multiplier: float = Field(..., description="Multiply all rates by this factor", gt=0)
    schedule: EventSchedule = Field(..., description="When event executes")


class AgentArrivalRateChangeEvent(BaseModel):
    """Multiply specific agent's arrival rate by a factor."""
    type: Literal["AgentArrivalRateChange"] = "AgentArrivalRateChange"
    agent: str = Field(..., description="Agent ID")
    multiplier: float = Field(..., description="Multiply rate by this factor", gt=0)
    schedule: EventSchedule = Field(..., description="When event executes")


class CounterpartyWeightChangeEvent(BaseModel):
    """Change counterparty selection weight for a single counterparty."""
    type: Literal["CounterpartyWeightChange"] = "CounterpartyWeightChange"
    agent: str = Field(..., description="Agent whose weights to change")
    counterparty: str = Field(..., description="Target counterparty")
    new_weight: float = Field(..., description="New weight for this counterparty", ge=0, le=1)
    auto_balance_others: bool = Field(
        False, description="Redistribute remaining weight to other counterparties"
    )
    schedule: EventSchedule = Field(..., description="When event executes")


class DeadlineWindowChangeEvent(BaseModel):
    """Change deadline ranges for ALL agents using multipliers.

    Applies globally to all agents that have arrival configs. Multiplies
    the min/max of existing deadline ranges by the provided multipliers.
    """
    type: Literal["DeadlineWindowChange"] = "DeadlineWindowChange"
    min_ticks_multiplier: Optional[float] = Field(None, description="Multiplier for min deadline", gt=0)
    max_ticks_multiplier: Optional[float] = Field(None, description="Multiplier for max deadline", gt=0)
    schedule: EventSchedule = Field(..., description="When event executes")

    @model_validator(mode="after")
    def validate_at_least_one_multiplier(self):
        """At least one multiplier must be provided."""
        if self.min_ticks_multiplier is None and self.max_ticks_multiplier is None:
            raise ValueError("At least one of min_ticks_multiplier or max_ticks_multiplier must be provided")
        return self


# Union type for all scenario events
ScenarioEvent = Union[
    DirectTransferEvent,
    CustomTransactionArrivalEvent,
    CollateralAdjustmentEvent,
    GlobalArrivalRateChangeEvent,
    AgentArrivalRateChangeEvent,
    CounterpartyWeightChangeEvent,
    DeadlineWindowChangeEvent,
]


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


class FromJsonPolicy(BaseModel):
    """Policy loaded from JSON file."""
    type: Literal["FromJson"] = "FromJson"
    json_path: str = Field(..., description="Path to JSON policy file (relative to project root)")


# Union type for all policies
PolicyConfig = Union[
    FifoPolicy,
    DeadlinePolicy,
    LiquidityAwarePolicy,
    LiquiditySplittingPolicy,
    MockSplittingPolicy,
    FromJsonPolicy,
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
    collateral_cost_per_tick_bps: float = Field(
        0.0002, description="Collateral opportunity cost in basis points per tick", ge=0
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

    enable_bilateral: bool = Field(True, description="Enable bilateral offsetting (A↔B netting)")
    enable_cycles: bool = Field(True, description="Enable cycle detection and settlement")
    max_cycle_length: int = Field(4, description="Maximum cycle length to detect (3-5 typical)", ge=3, le=10)
    max_cycles_per_tick: int = Field(10, description="Maximum cycles to settle per tick (performance limit)", ge=1, le=100)


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
    scenario_events: Optional[List[ScenarioEvent]] = Field(
        None, description="Optional scenario events to execute during simulation"
    )

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
    def validate_references(self):
        """Validate that all agent references are valid."""
        agent_ids = {agent.id for agent in self.agents}

        # Validate counterparty references
        for agent in self.agents:
            if agent.arrival_config:
                for counterparty in agent.arrival_config.counterparty_weights.keys():
                    if counterparty not in agent_ids:
                        raise ValueError(
                            f"Agent {agent.id} references unknown counterparty: {counterparty}"
                        )

        # Validate scenario event references
        if self.scenario_events:
            for i, event in enumerate(self.scenario_events):
                if isinstance(event, (DirectTransferEvent, CustomTransactionArrivalEvent)):
                    if event.from_agent not in agent_ids:
                        raise ValueError(
                            f"Scenario event {i} references unknown from_agent: {event.from_agent}"
                        )
                    if event.to_agent not in agent_ids:
                        raise ValueError(
                            f"Scenario event {i} references unknown to_agent: {event.to_agent}"
                        )
                elif isinstance(event, (
                    CollateralAdjustmentEvent,
                    AgentArrivalRateChangeEvent,
                    CounterpartyWeightChangeEvent,
                )):
                    if event.agent not in agent_ids:
                        raise ValueError(
                            f"Scenario event {i} references unknown agent: {event.agent}"
                        )
                    # Additional validation for CounterpartyWeightChangeEvent
                    if isinstance(event, CounterpartyWeightChangeEvent):
                        if event.counterparty not in agent_ids:
                            raise ValueError(
                                f"Scenario event {i} references unknown counterparty: {event.counterparty}"
                            )
                # DeadlineWindowChangeEvent is global (no agent field) - no validation needed

        return self

    def to_ffi_dict(self) -> dict:
        """Convert to dictionary format expected by FFI layer."""
        result = {
            "ticks_per_day": self.simulation.ticks_per_day,
            "num_days": self.simulation.num_days,
            "rng_seed": self.simulation.rng_seed,
            "agent_configs": [self._agent_to_ffi_dict(agent) for agent in self.agents],
            "cost_rates": {
                "overdraft_bps_per_tick": self.cost_rates.overdraft_bps_per_tick,
                "delay_cost_per_tick_per_cent": self.cost_rates.delay_cost_per_tick_per_cent,
                "collateral_cost_per_tick_bps": self.cost_rates.collateral_cost_per_tick_bps,
                "eod_penalty_per_transaction": self.cost_rates.eod_penalty_per_transaction,
                "deadline_penalty": self.cost_rates.deadline_penalty,
                "split_friction_cost": self.cost_rates.split_friction_cost,
            },
            "lsm_config": {
                "enable_bilateral": self.lsm_config.enable_bilateral,
                "enable_cycles": self.lsm_config.enable_cycles,
                "max_cycle_length": self.lsm_config.max_cycle_length,
                "max_cycles_per_tick": self.lsm_config.max_cycles_per_tick,
            },
        }

        # Add scenario_events if present
        if self.scenario_events:
            result["scenario_events"] = [
                self._scenario_event_to_ffi_dict(event) for event in self.scenario_events
            ]

        return result

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
        elif isinstance(policy, FromJsonPolicy):
            # Load JSON policy from file
            # Try the path as-is first, then try relative to project root
            json_path = Path(policy.json_path)
            if not json_path.exists():
                # Try relative to project root
                # schemas.py is at api/payment_simulator/config/schemas.py, so go up 4 levels
                project_root = Path(__file__).resolve().parent.parent.parent.parent
                json_path = project_root / policy.json_path
                if not json_path.exists():
                    raise ValueError(f"Policy JSON file not found: {policy.json_path} (tried {json_path})")

            with open(json_path, 'r') as f:
                policy_json = f.read()

            # Validate it's valid JSON
            try:
                json.loads(policy_json)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in policy file {policy.json_path}: {e}")

            return {"type": "FromJson", "json": policy_json}
        else:
            raise ValueError(f"Unknown policy type: {type(policy)}")

    def _distribution_to_ffi_dict(self, dist: AmountDistribution) -> dict:
        """Convert distribution config to FFI dict format."""
        if isinstance(dist, NormalDistribution):
            return {"type": "Normal", "mean": dist.mean, "std_dev": dist.std_dev}
        elif isinstance(dist, LogNormalDistribution):
            return {"type": "LogNormal", "mean": dist.mean, "std_dev": dist.std_dev}
        elif isinstance(dist, UniformDistribution):
            return {"type": "Uniform", "min": dist.min, "max": dist.max}
        elif isinstance(dist, ExponentialDistribution):
            return {"type": "Exponential", "lambda": dist.lambda_}
        else:
            raise ValueError(f"Unknown distribution type: {type(dist)}")

    def _scenario_event_to_ffi_dict(self, event: ScenarioEvent) -> dict:
        """Convert scenario event config to FFI dict format."""
        # Extract schedule info
        schedule_dict: dict
        if isinstance(event.schedule, OneTimeSchedule):
            schedule_dict = {"schedule": "OneTime", "tick": event.schedule.tick}
        elif isinstance(event.schedule, RepeatingSchedule):
            schedule_dict = {
                "schedule": "Repeating",
                "start_tick": event.schedule.start_tick,
                "interval": event.schedule.interval,
            }
        else:
            raise ValueError(f"Unknown schedule type: {type(event.schedule)}")

        # Build event dict based on type
        if isinstance(event, DirectTransferEvent):
            return {
                "type": "DirectTransfer",
                "from_agent": event.from_agent,
                "to_agent": event.to_agent,
                "amount": event.amount,
                **schedule_dict,
            }
        elif isinstance(event, CustomTransactionArrivalEvent):
            result = {
                "type": "CustomTransactionArrival",
                "from_agent": event.from_agent,
                "to_agent": event.to_agent,
                "amount": event.amount,
                **schedule_dict,
            }
            # Add optional fields if present
            if event.priority is not None:
                result["priority"] = event.priority
            if event.deadline is not None:
                result["deadline"] = event.deadline
            if event.is_divisible is not None:
                result["is_divisible"] = event.is_divisible
            return result
        elif isinstance(event, CollateralAdjustmentEvent):
            return {
                "type": "CollateralAdjustment",
                "agent": event.agent,
                "delta": event.delta,
                **schedule_dict,
            }
        elif isinstance(event, GlobalArrivalRateChangeEvent):
            return {
                "type": "GlobalArrivalRateChange",
                "multiplier": event.multiplier,
                **schedule_dict,
            }
        elif isinstance(event, AgentArrivalRateChangeEvent):
            return {
                "type": "AgentArrivalRateChange",
                "agent": event.agent,
                "multiplier": event.multiplier,
                **schedule_dict,
            }
        elif isinstance(event, CounterpartyWeightChangeEvent):
            return {
                "type": "CounterpartyWeightChange",
                "agent": event.agent,
                "counterparty": event.counterparty,
                "new_weight": event.new_weight,
                "auto_balance_others": event.auto_balance_others,
                **schedule_dict,
            }
        elif isinstance(event, DeadlineWindowChangeEvent):
            result = {
                "type": "DeadlineWindowChange",
                **schedule_dict,
            }
            if event.min_ticks_multiplier is not None:
                result["min_ticks_multiplier"] = event.min_ticks_multiplier
            if event.max_ticks_multiplier is not None:
                result["max_ticks_multiplier"] = event.max_ticks_multiplier
            return result
        else:
            raise ValueError(f"Unknown scenario event type: {type(event)}")

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SimulationConfig":
        """Create config from dictionary."""
        return cls.model_validate(config_dict)
