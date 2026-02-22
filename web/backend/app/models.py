"""Pydantic models for the web API."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PresetScenario(str, Enum):
    EXP1 = "exp1"
    EXP2 = "exp2"
    EXP3 = "exp3"


class AgentType(str, Enum):
    AI = "ai"
    HUMAN = "human"
    FIFO = "fifo"


class AgentSetup(BaseModel):
    id: str
    agent_type: AgentType = AgentType.AI
    liquidity_pool: int = 100_000
    opening_balance: int = 0
    unsecured_cap: int = 0


class ScenarioConfig(BaseModel):
    """Configuration for creating a simulation."""
    preset: PresetScenario | None = None
    # Custom config overrides (used when preset is None)
    ticks_per_day: int = 3
    num_days: int = 1
    rng_seed: int = 42
    agents: list[AgentSetup] | None = None
    # Cost parameters
    liquidity_cost_per_tick_bps: float = 333
    delay_cost_per_tick_per_cent: float = 0.2
    eod_penalty_per_transaction: int = 100_000
    deadline_penalty: int = 50_000
    deferred_crediting: bool = True
    deadline_cap_at_eod: bool = True
    # Payment schedule (for custom scenarios)
    payment_schedule: list[PaymentEntry] | None = None
    # Stochastic arrival config
    stochastic_arrivals: StochasticArrivalConfig | None = None
    # LSM toggles
    enable_bilateral_lsm: bool = False
    enable_cycle_lsm: bool = False
    # LLM reasoning
    use_llm: bool = True
    simulated_ai: bool = False


class PaymentEntry(BaseModel):
    sender: str
    receiver: str
    amount: int  # in cents
    tick: int
    deadline: int


class StochasticArrivalConfig(BaseModel):
    enabled: bool = False
    rate_per_tick: float = 0.5
    amount_mean: int = 50_000  # cents
    amount_std: int = 10_000
    deadline_min: int = 2
    deadline_max: int = 6


class SimulationState(BaseModel):
    """Current state of a simulation."""
    sim_id: str
    current_tick: int
    current_day: int
    total_ticks: int
    is_complete: bool
    agents: dict[str, AgentState]
    events: list[dict[str, Any]] = []


class AgentState(BaseModel):
    balance: int = 0
    available_liquidity: int = 0
    queue1_size: int = 0
    posted_collateral: int = 0
    costs: CostBreakdown = Field(default_factory=lambda: CostBreakdown())


class CostBreakdown(BaseModel):
    liquidity_cost: float = 0.0
    delay_cost: float = 0.0
    penalty_cost: float = 0.0
    total: float = 0.0


class TickResult(BaseModel):
    tick: int
    num_arrivals: int = 0
    num_settlements: int = 0
    agents: dict[str, AgentState]
    events: list[dict[str, Any]] = []
    llm_decisions: dict[str, Any] = {}


class PaymentDecision(str, Enum):
    RELEASE = "Release"
    HOLD = "Hold"


class HumanDecision(BaseModel):
    """Human player's decisions for a tick."""
    payment_decisions: dict[str, PaymentDecision] = {}  # tx_id -> decision
    initial_liquidity_fraction: float | None = None


class CreateSimResponse(BaseModel):
    sim_id: str
    config: dict[str, Any]


# --- Scenario Library models ---

class SavedScenario(BaseModel):
    """A saved custom scenario."""
    id: str = ""
    name: str = "Custom Scenario"
    description: str = ""
    config: ScenarioConfig


class PolicyRule(BaseModel):
    """A manual policy rule."""
    condition: str  # e.g. "balance > 50000", "tick >= 2"
    action: PaymentDecision = PaymentDecision.RELEASE


class ManualPolicy(BaseModel):
    """A set of manual policy rules."""
    id: str = ""
    name: str = "Custom Policy"
    rules: list[PolicyRule] = []


class CreateGameRequest(BaseModel):
    """Configuration for creating a multi-day policy optimization game."""
    scenario_id: str = "2bank_12tick"
    inline_config: dict[str, Any] | None = None
    use_llm: bool = True
    simulated_ai: bool = False
    max_days: int = Field(default=10, ge=1, le=100)
    num_eval_samples: int = Field(default=1, ge=1, le=50)
    optimization_interval: int = Field(default=1, ge=1, le=50)
    constraint_preset: str = Field(default="simple", pattern="^(simple|standard|full)$")
    include_groups: list[str] | None = None  # Extra field groups to force-include
    exclude_groups: list[str] | None = None  # Field groups to force-exclude
    starting_policies: dict[str, str] | None = None  # agent_id → policy JSON string
    optimization_schedule: str = Field(default="every_scenario_day", pattern="^(every_round|every_scenario_day)$")
    prompt_profile_id: str | None = None  # load saved profile by ID
    prompt_profile: dict[str, dict] | None = None  # inline block overrides {block_id: {enabled, options}}


class CompareRequest(BaseModel):
    """Request to compare multiple scenario+policy combos."""
    runs: list[CompareRun]


class CompareRun(BaseModel):
    scenario: ScenarioConfig
    policy_id: str | None = None  # None = default AI
