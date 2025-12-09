"""Pydantic schemas for configuration validation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

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
    def max_must_be_greater_than_min(cls, v: int, info: ValidationInfo) -> int:
        """Validate max > min."""
        if info.data and "min" in info.data and v <= info.data["min"]:
            raise ValueError("max must be greater than min")
        return v


class ExponentialDistribution(BaseModel):
    """Exponential distribution."""
    type: Literal["Exponential"] = "Exponential"
    lambda_: float = Field(..., alias="lambda", description="Rate parameter", gt=0)


# Union type for all distributions
AmountDistribution = (
    NormalDistribution
    | LogNormalDistribution
    | UniformDistribution
    | ExponentialDistribution
)


# ============================================================================
# Priority Distribution Schemas
# ============================================================================

class FixedPriorityDistribution(BaseModel):
    """Fixed priority (all transactions get same value)."""
    type: Literal["Fixed"] = "Fixed"
    value: int = Field(..., description="Fixed priority value (0-10)", ge=0, le=10)


class CategoricalPriorityDistribution(BaseModel):
    """Categorical priority distribution (discrete values with weights)."""
    type: Literal["Categorical"] = "Categorical"
    values: list[int] = Field(..., description="Priority values to sample from")
    weights: list[float] = Field(..., description="Weights for each value")

    @field_validator("values")
    @classmethod
    def validate_values_range(cls, v: list[int]) -> list[int]:
        """Validate all values are in range 0-10."""
        for val in v:
            if not 0 <= val <= 10:
                raise ValueError(f"Priority value must be between 0 and 10, got {val}")
        return v

    @field_validator("weights")
    @classmethod
    def validate_weights_positive_sum(cls, v: list[float]) -> list[float]:
        """Validate weights sum to positive value."""
        if sum(v) <= 0:
            raise ValueError("Weights must sum to positive value")
        return v

    @model_validator(mode="after")
    def validate_lengths_match(self) -> CategoricalPriorityDistribution:
        """Validate values and weights have same length."""
        if len(self.values) != len(self.weights):
            raise ValueError(
                f"Values and weights must have same length: "
                f"values={len(self.values)}, weights={len(self.weights)}"
            )
        return self


class UniformPriorityDistribution(BaseModel):
    """Uniform priority distribution (random integer in range)."""
    type: Literal["Uniform"] = "Uniform"
    min: int = Field(..., description="Minimum priority (inclusive)", ge=0, le=10)
    max: int = Field(..., description="Maximum priority (inclusive)", ge=0, le=10)

    @model_validator(mode="after")
    def validate_min_max(self) -> UniformPriorityDistribution:
        """Validate min <= max."""
        if self.min > self.max:
            raise ValueError(f"Max must be greater than or equal to min: min={self.min}, max={self.max}")
        return self


# Union type for priority distributions
PriorityDistribution = (
    FixedPriorityDistribution
    | CategoricalPriorityDistribution
    | UniformPriorityDistribution
)


# ============================================================================
# Arrival Configuration
# ============================================================================

class ArrivalConfig(BaseModel):
    """Configuration for automatic transaction arrival generation."""

    rate_per_tick: float = Field(..., description="Expected arrivals per tick (Poisson λ)", ge=0)
    amount_distribution: AmountDistribution = Field(..., description="Transaction amount distribution")
    counterparty_weights: dict[str, float] = Field(
        ..., description="Weights for selecting receiver agents"
    )
    deadline_range: list[int] = Field(
        ..., description="[min_ticks, max_ticks] until deadline", min_length=2, max_length=2
    )
    # Legacy single priority value (backward compatible)
    priority: int = Field(5, description="Transaction priority (0-10)", ge=0, le=10)
    # New priority distribution (takes precedence over single priority)
    priority_distribution: PriorityDistribution | None = Field(
        None, description="Priority distribution for generated transactions"
    )
    divisible: bool = Field(False, description="Whether transactions can be split")

    @field_validator("deadline_range")
    @classmethod
    def validate_deadline_range(cls, v: list[int]) -> list[int]:
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
    def validate_weights(cls, v: dict[str, float]) -> dict[str, float]:
        """Validate counterparty weights sum to positive value."""
        if not v:
            raise ValueError("counterparty_weights cannot be empty")
        total = sum(v.values())
        if total <= 0:
            raise ValueError("counterparty_weights must sum to positive value")
        return v

    def get_effective_priority_config(
        self,
    ) -> dict[str, str | int | float | list[int] | list[float]]:
        """Get the effective priority configuration as FFI-compatible dict.

        If priority_distribution is set, use it.
        Otherwise, convert legacy priority to Fixed distribution.
        """
        if self.priority_distribution is not None:
            return self._priority_distribution_to_dict(self.priority_distribution)
        else:
            # Convert legacy single priority to Fixed distribution
            return {"type": "Fixed", "value": self.priority}

    def _priority_distribution_to_dict(
        self, dist: PriorityDistribution
    ) -> dict[str, str | int | float | list[int] | list[float]]:
        """Convert priority distribution to FFI dict format."""
        match dist:
            case FixedPriorityDistribution(value=val):
                return {"type": "Fixed", "value": val}
            case CategoricalPriorityDistribution(values=vals, weights=wts):
                return {"type": "Categorical", "values": vals, "weights": wts}
            case UniformPriorityDistribution(min=min_val, max=max_val):
                return {"type": "Uniform", "min": min_val, "max": max_val}
            case _:
                raise ValueError(f"Unknown priority distribution type: {type(dist)}")


# ============================================================================
# Per-Band Arrival Configuration (Enhancement 11.3)
# ============================================================================

class ArrivalBandConfig(BaseModel):
    """Configuration for arrivals in a single priority band.

    This allows different arrival characteristics (rate, amounts, deadlines)
    for different priority levels (urgent, normal, low).
    """

    rate_per_tick: float = Field(
        ...,
        description="Expected arrivals per tick for this band (Poisson λ)",
        ge=0
    )
    amount_distribution: AmountDistribution = Field(
        ...,
        description="Transaction amount distribution for this band"
    )
    deadline_offset_min: int = Field(
        ...,
        description="Minimum ticks until deadline from arrival",
        gt=0
    )
    deadline_offset_max: int = Field(
        ...,
        description="Maximum ticks until deadline from arrival",
        gt=0
    )
    counterparty_weights: dict[str, float] = Field(
        default_factory=dict,
        description="Weights for selecting receiver agents (empty = uniform across all)"
    )
    divisible: bool = Field(
        False,
        description="Whether transactions in this band can be split"
    )

    @model_validator(mode="after")
    def validate_deadline_offsets(self) -> ArrivalBandConfig:
        """Validate deadline_offset_max >= deadline_offset_min."""
        if self.deadline_offset_max < self.deadline_offset_min:
            raise ValueError(
                f"deadline_offset_max ({self.deadline_offset_max}) must be >= "
                f"deadline_offset_min ({self.deadline_offset_min})"
            )
        return self


class ArrivalBandsConfig(BaseModel):
    """Configuration for per-band arrival generation (Enhancement 11.3).

    Allows specifying different arrival characteristics for each priority band:
    - Urgent (priority 8-10): Critical payments, tight deadlines
    - Normal (priority 4-7): Standard payments
    - Low (priority 0-3): Low-priority payments, relaxed deadlines

    At least one band must be configured. Bands can be independently configured
    with different rates, amounts, and deadline parameters.
    """

    urgent: ArrivalBandConfig | None = Field(
        None,
        description="Arrival config for urgent priority (8-10)"
    )
    normal: ArrivalBandConfig | None = Field(
        None,
        description="Arrival config for normal priority (4-7)"
    )
    low: ArrivalBandConfig | None = Field(
        None,
        description="Arrival config for low priority (0-3)"
    )

    @model_validator(mode="after")
    def validate_at_least_one_band(self) -> ArrivalBandsConfig:
        """At least one band must be configured."""
        if self.urgent is None and self.normal is None and self.low is None:
            raise ValueError("At least one arrival band must be configured")
        return self


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


EventSchedule = OneTimeSchedule | RepeatingSchedule


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
    priority: int | None = Field(None, description="Transaction priority (0-10, default 5)", ge=0, le=10)
    deadline: int | None = Field(None, description="Deadline in ticks from arrival (default: auto)", gt=0)
    is_divisible: bool | None = Field(None, description="Whether transaction can be split (default: false)")
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
    min_ticks_multiplier: float | None = Field(None, description="Multiplier for min deadline", gt=0)
    max_ticks_multiplier: float | None = Field(None, description="Multiplier for max deadline", gt=0)
    schedule: EventSchedule = Field(..., description="When event executes")

    @model_validator(mode="after")
    def validate_at_least_one_multiplier(self) -> DeadlineWindowChangeEvent:
        """At least one multiplier must be provided."""
        if self.min_ticks_multiplier is None and self.max_ticks_multiplier is None:
            raise ValueError("At least one of min_ticks_multiplier or max_ticks_multiplier must be provided")
        return self


# Union type for all scenario events
ScenarioEvent = (
    DirectTransferEvent
    | CustomTransactionArrivalEvent
    | CollateralAdjustmentEvent
    | GlobalArrivalRateChangeEvent
    | AgentArrivalRateChangeEvent
    | CounterpartyWeightChangeEvent
    | DeadlineWindowChangeEvent
)


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


class InlinePolicy(BaseModel):
    """Inline policy with embedded decision tree DSL.

    This policy type allows embedding decision tree DSL structures directly
    in configuration dictionaries, complementing the existing FromJson policy
    that loads from external files.

    Useful for:
    - Dynamic policy testing without file I/O
    - LLM policy optimization experiments
    - Parameter sweeps where policy varies programmatically
    """

    type: Literal["Inline"] = "Inline"
    decision_trees: dict[str, Any] = Field(
        ...,
        description="Embedded decision tree DSL structure (same format as seed_policy.json)"
    )


class InlineJsonPolicy(BaseModel):
    """Policy from inline JSON string.

    This policy type allows passing a raw JSON policy string directly,
    enabling policy injection from databases, LLM responses, and
    programmatic sources without file I/O.

    Unlike InlinePolicy (which takes a dict), this takes a raw JSON string,
    useful when policies are stored or transmitted as strings.

    Useful for:
    - LLM-generated policies (JSON string output)
    - Database-stored policies
    - API-submitted policies
    - Castro experiment policy injection
    """

    type: Literal["InlineJson"] = "InlineJson"
    json_string: str = Field(..., description="JSON policy string")

    @field_validator("json_string")
    @classmethod
    def validate_json(cls, v: str) -> str:
        """Validate JSON is parseable."""
        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
        return v


# Union type for all policies
PolicyConfig = (
    FifoPolicy
    | DeadlinePolicy
    | LiquidityAwarePolicy
    | LiquiditySplittingPolicy
    | MockSplittingPolicy
    | FromJsonPolicy
    | InlinePolicy
    | InlineJsonPolicy
)


# ============================================================================
# Agent Configuration
# ============================================================================

class AgentConfig(BaseModel):
    """Configuration for a single agent (bank)."""

    id: str = Field(..., description="Unique agent identifier")
    opening_balance: int = Field(..., description="Opening balance in cents")
    unsecured_cap: int = Field(0, description="Unsecured overdraft capacity in cents", ge=0)
    policy: PolicyConfig = Field(..., description="Cash manager policy configuration")
    arrival_config: ArrivalConfig | None = Field(None, description="Arrival generation config (if any)")
    # Enhancement 11.3: Per-Band Arrival Configuration
    arrival_bands: ArrivalBandsConfig | None = Field(
        None,
        description="Per-band arrival generation config (mutually exclusive with arrival_config)"
    )
    posted_collateral: int | None = Field(None, description="Posted collateral in cents")
    collateral_haircut: float | None = Field(None, description="Collateral haircut (discount rate)", ge=0, le=1)
    max_collateral_capacity: int | None = Field(
        None,
        description="Maximum collateral capacity override (cents). If not set, uses heuristic (10 × unsecured_cap).",
        ge=0
    )
    limits: dict[str, int | dict[str, int]] | None = Field(None, description="Payment limits configuration")

    # Enhancement 11.2: Liquidity Pool Configuration
    liquidity_pool: int | None = Field(
        None,
        description="External liquidity pool available for allocation (cents)",
        ge=0
    )
    liquidity_allocation_fraction: float | None = Field(
        None,
        description="Fraction of liquidity_pool to allocate (0.0-1.0, defaults to 1.0)",
        ge=0.0,
        le=1.0
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate agent ID is not empty."""
        if not v or not v.strip():
            raise ValueError("Agent ID cannot be empty")
        return v

    @model_validator(mode="after")
    def validate_arrival_config_exclusivity(self) -> AgentConfig:
        """Validate arrival_config and arrival_bands are mutually exclusive."""
        if self.arrival_config is not None and self.arrival_bands is not None:
            raise ValueError(
                "arrival_config and arrival_bands are mutually exclusive - "
                "specify only one"
            )
        return self


# ============================================================================
# Cost Rates Configuration
# ============================================================================

class PriorityDelayMultipliers(BaseModel):
    """Priority-based delay cost multipliers (Enhancement 11.1).

    Allows differentiated delay costs by transaction priority band:
    - Urgent (priority 8-10): Higher delay costs
    - Normal (priority 4-7): Base delay costs
    - Low (priority 0-3): Lower delay costs
    """

    urgent_multiplier: float = Field(
        1.0, description="Delay cost multiplier for urgent priority (8-10)", ge=0
    )
    normal_multiplier: float = Field(
        1.0, description="Delay cost multiplier for normal priority (4-7)", ge=0
    )
    low_multiplier: float = Field(
        1.0, description="Delay cost multiplier for low priority (0-3)", ge=0
    )


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
    overdue_delay_multiplier: float = Field(
        5.0, description="Multiplier for delay cost when transaction is overdue", ge=0
    )
    priority_delay_multipliers: PriorityDelayMultipliers | None = Field(
        None, description="Priority-based delay cost multipliers (Enhancement 11.1)"
    )
    liquidity_cost_per_tick_bps: float = Field(
        0.0, description="Liquidity opportunity cost in basis points per tick (Enhancement 11.2)", ge=0
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
# Policy Feature Toggles
# ============================================================================

# All valid category names from the policy schema
VALID_POLICY_CATEGORIES: set[str] = {
    # Expression categories
    "ComparisonOperator",
    "LogicalOperator",
    # Computation categories
    "BinaryArithmetic",
    "NaryArithmetic",
    "UnaryMath",
    "TernaryMath",
    # Value categories
    "ValueType",
    # Action categories
    "PaymentAction",
    "BankAction",
    "CollateralAction",
    "RtgsAction",
    # Field categories
    "TransactionField",
    "AgentField",
    "QueueField",
    "CollateralField",
    "CostField",
    "TimeField",
    "LsmField",
    "ThroughputField",
    "StateRegisterField",
    "SystemField",
    "DerivedField",
    # Node and tree categories
    "NodeType",
    "TreeType",
}


class PolicyFeatureToggles(BaseModel):
    """Feature toggles for policy DSL in this scenario.

    Allows restricting which policy features are available.
    Only ONE of include or exclude can be specified.

    Examples:
        # Only allow basic payment actions and transaction fields
        policy_feature_toggles:
          include:
            - PaymentAction
            - TransactionField
            - TimeField

        # Allow all except collateral features
        policy_feature_toggles:
          exclude:
            - CollateralAction
            - CollateralField
    """

    include: list[str] | None = Field(
        None,
        description="Only allow these categories (mutually exclusive with exclude)"
    )
    exclude: list[str] | None = Field(
        None,
        description="Forbid these categories (mutually exclusive with include)"
    )

    @field_validator("include", "exclude", mode="before")
    @classmethod
    def validate_categories(cls, v: list[str] | None) -> list[str] | None:
        """Validate that all category names are valid."""
        if v is None:
            return v
        for cat in v:
            if cat not in VALID_POLICY_CATEGORIES:
                raise ValueError(
                    f"Unknown category: {cat}. "
                    f"Valid categories: {sorted(VALID_POLICY_CATEGORIES)}"
                )
        return v

    @model_validator(mode="after")
    def validate_mutual_exclusion(self) -> "PolicyFeatureToggles":
        """Ensure include and exclude are mutually exclusive."""
        if self.include is not None and self.exclude is not None:
            raise ValueError(
                "Cannot specify both 'include' and 'exclude' - choose one"
            )
        return self

    def is_category_allowed(self, category: str) -> bool:
        """Check if a category is allowed by the toggles.

        Args:
            category: The category name to check.

        Returns:
            True if the category is allowed, False otherwise.
        """
        if self.include is not None:
            return category in self.include
        if self.exclude is not None:
            return category not in self.exclude
        return True  # No toggles means all allowed

    def get_allowed_categories(self) -> set[str]:
        """Get the set of allowed category names.

        Returns:
            Set of category names that are allowed.
        """
        if self.include is not None:
            return set(self.include)
        if self.exclude is not None:
            return VALID_POLICY_CATEGORIES - set(self.exclude)
        return VALID_POLICY_CATEGORIES.copy()

    def get_forbidden_categories(self) -> set[str]:
        """Get the set of forbidden category names.

        Returns:
            Set of category names that are forbidden.
        """
        if self.exclude is not None:
            return set(self.exclude)
        if self.include is not None:
            return VALID_POLICY_CATEGORIES - set(self.include)
        return set()  # No toggles means nothing forbidden


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
    agents: list[AgentConfig] = Field(..., description="Agent configurations", min_length=1)
    cost_rates: CostRates = Field(default_factory=CostRates, description="Cost calculation rates")  # type: ignore[arg-type]
    lsm_config: LsmConfig = Field(default_factory=LsmConfig, description="LSM configuration")  # type: ignore[arg-type]
    scenario_events: list[ScenarioEvent] | None = Field(
        None, description="Optional scenario events to execute during simulation"
    )
    policy_feature_toggles: PolicyFeatureToggles | None = Field(
        None, description="Restrict policy DSL features for this scenario"
    )
    deferred_crediting: bool = Field(
        False,
        description=(
            "When true, credits are batched and applied at end of tick. "
            "When false (default), credits are applied immediately allowing "
            "within-tick recycling."
        ),
    )
    deadline_cap_at_eod: bool = Field(
        False,
        description=(
            "When true, all generated transaction deadlines are capped at the "
            "end of the current day. When false (default), deadlines are only "
            "capped at episode end."
        ),
    )

    @field_validator("agents")
    @classmethod
    def validate_unique_agent_ids(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        """Validate that all agent IDs are unique."""
        ids = [agent.id for agent in v]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            raise ValueError(f"Duplicate agent IDs found: {duplicates}")
        return v

    @model_validator(mode="after")
    def validate_references(self) -> SimulationConfig:
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

    def validate_policies_against_toggles(self) -> list[str]:
        """Validate all FromJson and Inline policies against feature toggles.

        Returns:
            List of error messages. Empty list if all policies are valid.
        """
        if self.policy_feature_toggles is None:
            return []  # No toggles, all policies allowed

        errors: list[str] = []

        from payment_simulator.policy.validation import validate_policy_for_scenario

        for agent in self.agents:
            policy_json: str | None = None

            if isinstance(agent.policy, FromJsonPolicy):
                # Load the policy JSON from file
                json_path = Path(agent.policy.json_path)
                if not json_path.exists():
                    project_root = Path(__file__).resolve().parent.parent.parent.parent
                    json_path = project_root / agent.policy.json_path

                if not json_path.exists():
                    errors.append(
                        f"Agent {agent.id}: Policy file not found: {agent.policy.json_path}"
                    )
                    continue

                try:
                    policy_json = json_path.read_text()
                except Exception as e:
                    errors.append(
                        f"Agent {agent.id}: Failed to read policy file: {e}"
                    )
                    continue

            elif isinstance(agent.policy, InlinePolicy):
                # Serialize the inline decision trees to JSON
                policy_json = json.dumps(agent.policy.decision_trees)

            # Validate against toggles if we have policy JSON
            if policy_json is not None:
                result = validate_policy_for_scenario(
                    policy_json, scenario_config=self
                )
                if not result.valid:
                    for error in result.errors:
                        errors.append(
                            f"Agent {agent.id}: {error.get('message', 'Unknown error')}"
                        )

        return errors

    def to_ffi_dict(self) -> dict[str, Any]:
        """Convert to dictionary format expected by FFI layer.

        Returns dict[str, Any] because FFI boundary types are dynamic.
        """
        result = {
            "ticks_per_day": self.simulation.ticks_per_day,
            "num_days": self.simulation.num_days,
            "rng_seed": self.simulation.rng_seed,
            "agent_configs": [self._agent_to_ffi_dict(agent) for agent in self.agents],
            "cost_rates": self._cost_rates_to_ffi_dict(),
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

        # Add deferred_crediting
        result["deferred_crediting"] = self.deferred_crediting

        # Add deadline_cap_at_eod
        result["deadline_cap_at_eod"] = self.deadline_cap_at_eod

        return result

    def _agent_to_ffi_dict(self, agent: AgentConfig) -> dict[str, Any]:
        """Convert agent config to FFI dict format."""
        result = {
            "id": agent.id,
            "opening_balance": agent.opening_balance,
            "unsecured_cap": agent.unsecured_cap,
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
                "priority_distribution": agent.arrival_config.get_effective_priority_config(),
                "divisible": agent.arrival_config.divisible,
            }

        # Enhancement 11.3: Per-band arrival configuration
        if agent.arrival_bands:
            result["arrival_bands"] = self._arrival_bands_to_ffi_dict(agent.arrival_bands)

        # Enhancement 11.2: Liquidity pool allocation
        if agent.liquidity_pool is not None:
            result["liquidity_pool"] = agent.liquidity_pool
        if agent.liquidity_allocation_fraction is not None:
            result["liquidity_allocation_fraction"] = agent.liquidity_allocation_fraction

        # Collateral capacity
        if agent.max_collateral_capacity is not None:
            result["max_collateral_capacity"] = agent.max_collateral_capacity

        return result

    def _policy_to_ffi_dict(self, policy: PolicyConfig) -> dict[str, str | int]:
        """Convert policy config to FFI dict format."""
        match policy:
            case FifoPolicy():
                return {"type": "Fifo"}
            case DeadlinePolicy(urgency_threshold=threshold):
                return {"type": "Deadline", "urgency_threshold": threshold}
            case LiquidityAwarePolicy(target_buffer=buffer, urgency_threshold=threshold):
                return {
                    "type": "LiquidityAware",
                    "target_buffer": buffer,
                    "urgency_threshold": threshold,
                }
            case LiquiditySplittingPolicy(max_splits=max_s, min_split_amount=min_amt):
                return {
                    "type": "LiquiditySplitting",
                    "max_splits": max_s,
                    "min_split_amount": min_amt,
                }
            case MockSplittingPolicy(num_splits=num):
                return {"type": "MockSplitting", "num_splits": num}
            case FromJsonPolicy(json_path=path_str):
                return self._load_json_policy(path_str)
            case InlinePolicy(decision_trees=trees):
                # Serialize decision_trees to JSON and use same format as FromJson
                return {"type": "FromJson", "json": json.dumps(trees)}
            case InlineJsonPolicy(json_string=json_str):
                # Pass the JSON string directly to FFI
                return {"type": "FromJson", "json": json_str}
            case _:
                raise ValueError(f"Unknown policy type: {type(policy)}")

    def _load_json_policy(self, path_str: str) -> dict[str, str | int]:
        """Load and validate a JSON policy file."""
        json_path = Path(path_str)
        if not json_path.exists():
            # Try relative to project root
            # schemas.py is at api/payment_simulator/config/schemas.py, so go up 4 levels
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            json_path = project_root / path_str
            if not json_path.exists():
                raise ValueError(f"Policy JSON file not found: {path_str} (tried {json_path})")

        with open(json_path) as f:
            policy_json = f.read()

        # Validate it's valid JSON
        try:
            json.loads(policy_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in policy file {path_str}: {e}") from e

        return {"type": "FromJson", "json": policy_json}

    def _distribution_to_ffi_dict(self, dist: AmountDistribution) -> dict[str, str | int | float]:
        """Convert distribution config to FFI dict format."""
        match dist:
            case NormalDistribution(mean=mean, std_dev=std_dev):
                return {"type": "Normal", "mean": mean, "std_dev": std_dev}
            case LogNormalDistribution(mean=mean, std_dev=std_dev):
                return {"type": "LogNormal", "mean": mean, "std_dev": std_dev}
            case UniformDistribution(min=min_val, max=max_val):
                return {"type": "Uniform", "min": min_val, "max": max_val}
            case ExponentialDistribution(lambda_=lambda_val):
                return {"type": "Exponential", "lambda": lambda_val}
            case _:
                raise ValueError(f"Unknown distribution type: {type(dist)}")

    def _scenario_event_to_ffi_dict(self, event: ScenarioEvent) -> dict[str, Any]:
        """Convert scenario event config to FFI dict format."""
        # Extract schedule info
        schedule_dict = self._schedule_to_ffi_dict(event.schedule)

        # Build event dict based on type
        match event:
            case DirectTransferEvent(
                from_agent=from_ag, to_agent=to_ag, amount=amt
            ):
                return {
                    "type": "DirectTransfer",
                    "from_agent": from_ag,
                    "to_agent": to_ag,
                    "amount": amt,
                    **schedule_dict,
                }
            case CustomTransactionArrivalEvent(
                from_agent=from_ag,
                to_agent=to_ag,
                amount=amt,
                priority=prio,
                deadline=dl,
                is_divisible=div,
            ):
                result: dict[str, Any] = {
                    "type": "CustomTransactionArrival",
                    "from_agent": from_ag,
                    "to_agent": to_ag,
                    "amount": amt,
                    **schedule_dict,
                }
                if prio is not None:
                    result["priority"] = prio
                if dl is not None:
                    result["deadline"] = dl
                if div is not None:
                    result["is_divisible"] = div
                return result
            case CollateralAdjustmentEvent(agent=ag, delta=d):
                return {
                    "type": "CollateralAdjustment",
                    "agent": ag,
                    "delta": d,
                    **schedule_dict,
                }
            case GlobalArrivalRateChangeEvent(multiplier=mult):
                return {
                    "type": "GlobalArrivalRateChange",
                    "multiplier": mult,
                    **schedule_dict,
                }
            case AgentArrivalRateChangeEvent(agent=ag, multiplier=mult):
                return {
                    "type": "AgentArrivalRateChange",
                    "agent": ag,
                    "multiplier": mult,
                    **schedule_dict,
                }
            case CounterpartyWeightChangeEvent(
                agent=ag,
                counterparty=cp,
                new_weight=nw,
                auto_balance_others=abo,
            ):
                return {
                    "type": "CounterpartyWeightChange",
                    "agent": ag,
                    "counterparty": cp,
                    "new_weight": nw,
                    "auto_balance_others": abo,
                    **schedule_dict,
                }
            case DeadlineWindowChangeEvent(
                min_ticks_multiplier=min_mult, max_ticks_multiplier=max_mult
            ):
                result = {
                    "type": "DeadlineWindowChange",
                    **schedule_dict,
                }
                if min_mult is not None:
                    result["min_ticks_multiplier"] = min_mult
                if max_mult is not None:
                    result["max_ticks_multiplier"] = max_mult
                return result
            case _:
                raise ValueError(f"Unknown scenario event type: {type(event)}")

    def _schedule_to_ffi_dict(self, schedule: EventSchedule) -> dict[str, str | int]:
        """Convert schedule config to FFI dict format."""
        match schedule:
            case OneTimeSchedule(tick=t):
                return {"schedule": "OneTime", "tick": t}
            case RepeatingSchedule(start_tick=start, interval=intv):
                return {"schedule": "Repeating", "start_tick": start, "interval": intv}
            case _:
                raise ValueError(f"Unknown schedule type: {type(schedule)}")

    def _cost_rates_to_ffi_dict(self) -> dict[str, Any]:
        """Convert cost rates config to FFI dict format."""
        result: dict[str, Any] = {
            "overdraft_bps_per_tick": self.cost_rates.overdraft_bps_per_tick,
            "delay_cost_per_tick_per_cent": self.cost_rates.delay_cost_per_tick_per_cent,
            "collateral_cost_per_tick_bps": self.cost_rates.collateral_cost_per_tick_bps,
            "eod_penalty_per_transaction": self.cost_rates.eod_penalty_per_transaction,
            "deadline_penalty": self.cost_rates.deadline_penalty,
            "split_friction_cost": self.cost_rates.split_friction_cost,
            "overdue_delay_multiplier": self.cost_rates.overdue_delay_multiplier,
            "liquidity_cost_per_tick_bps": self.cost_rates.liquidity_cost_per_tick_bps,
        }

        # Enhancement 11.1: Priority-based delay multipliers
        if self.cost_rates.priority_delay_multipliers:
            result["priority_delay_multipliers"] = {
                "urgent_multiplier": self.cost_rates.priority_delay_multipliers.urgent_multiplier,
                "normal_multiplier": self.cost_rates.priority_delay_multipliers.normal_multiplier,
                "low_multiplier": self.cost_rates.priority_delay_multipliers.low_multiplier,
            }

        return result

    def _arrival_bands_to_ffi_dict(self, bands: ArrivalBandsConfig) -> dict[str, Any]:
        """Convert per-band arrival config to FFI dict format."""
        result = {}

        if bands.urgent:
            result["urgent"] = self._arrival_band_to_ffi_dict(bands.urgent)
        if bands.normal:
            result["normal"] = self._arrival_band_to_ffi_dict(bands.normal)
        if bands.low:
            result["low"] = self._arrival_band_to_ffi_dict(bands.low)

        return result

    def _arrival_band_to_ffi_dict(self, band: ArrivalBandConfig) -> dict[str, Any]:
        """Convert single arrival band config to FFI dict format."""
        return {
            "rate_per_tick": band.rate_per_tick,
            "amount_distribution": self._distribution_to_ffi_dict(band.amount_distribution),
            "deadline_offset_min": band.deadline_offset_min,
            "deadline_offset_max": band.deadline_offset_max,
            "counterparty_weights": band.counterparty_weights,
            "divisible": band.divisible,
        }

    @classmethod
    def from_dict(cls, config_dict: dict) -> SimulationConfig:
        """Create config from dictionary."""
        return cls.model_validate(config_dict)
