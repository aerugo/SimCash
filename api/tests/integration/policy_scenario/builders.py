"""
Scenario builders for policy-scenario testing.

Provides fluent API for constructing test scenarios programmatically.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any


@dataclass
class AgentScenarioConfig:
    """Configuration for a single agent in a scenario."""

    agent_id: str
    opening_balance: int  # cents
    credit_limit: int = 0  # cents
    arrival_rate: float = 0.0  # arrivals per tick
    arrival_amount_range: Tuple[int, int] = (100_000, 250_000)  # (min, max) cents
    deadline_range: Tuple[int, int] = (10, 40)  # (min, max) ticks
    counterparty_weights: Optional[Dict[str, float]] = None
    posted_collateral: Optional[int] = None  # cents
    collateral_haircut: Optional[float] = None

    def __post_init__(self):
        if self.counterparty_weights is None:
            self.counterparty_weights = {}


@dataclass
class ScenarioEvent:
    """Represents a scenario event (crisis event, market change, etc.)."""

    tick: int
    event_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioDefinition:
    """Complete specification of a test scenario.

    A scenario defines:
    - Duration (number of ticks)
    - Agents (balances, arrival patterns)
    - Scenario events (crises, market changes)
    - Cost environment

    Scenarios are deterministic (controlled by RNG seed).
    """

    name: str
    description: str = ""
    duration_ticks: int = 100
    ticks_per_day: int = 100

    # Agents
    agents: List[AgentScenarioConfig] = field(default_factory=list)

    # Scenario events (optional)
    events: List[ScenarioEvent] = field(default_factory=list)

    # RNG seed for determinism
    seed: int = 12345

    def to_orchestrator_config(self, policy_configs: Dict[str, Dict]) -> Dict:
        """Convert scenario to Orchestrator config dict.

        Args:
            policy_configs: Map of agent_id -> policy config dict

        Returns:
            Config dict suitable for Orchestrator.new()
        """
        agent_configs = []

        for agent_cfg in self.agents:
            # Build arrival config if agent has arrivals
            arrival_config = None
            if agent_cfg.arrival_rate > 0:
                arrival_config = {
                    "rate_per_tick": agent_cfg.arrival_rate,
                    "amount_distribution": {
                        "type": "Uniform",
                        "min": agent_cfg.arrival_amount_range[0],
                        "max": agent_cfg.arrival_amount_range[1],
                    },
                    "deadline_range": agent_cfg.deadline_range,
                    "counterparty_weights": agent_cfg.counterparty_weights,
                    "priority": 0,
                    "divisible": False,
                }

            # Get policy config for this agent
            policy_config = policy_configs.get(
                agent_cfg.agent_id, {"type": "Fifo"}
            )

            agent_dict = {
                "id": agent_cfg.agent_id,
                "opening_balance": agent_cfg.opening_balance,
                "credit_limit": agent_cfg.credit_limit,
                "policy": policy_config,
            }

            if arrival_config:
                agent_dict["arrival_config"] = arrival_config

            if agent_cfg.posted_collateral is not None:
                agent_dict["posted_collateral"] = agent_cfg.posted_collateral

            if agent_cfg.collateral_haircut is not None:
                agent_dict["collateral_haircut"] = agent_cfg.collateral_haircut

            agent_configs.append(agent_dict)

        # Build scenario events
        scenario_events = []
        for event in self.events:
            event_dict = {
                "schedule": "OneTime",
                "tick": event.tick,
                "event_type": event.event_type,
                **event.parameters,
            }
            scenario_events.append(event_dict)

        # Number of days = ceil(duration_ticks / ticks_per_day)
        num_days = (self.duration_ticks + self.ticks_per_day - 1) // self.ticks_per_day

        return {
            "ticks_per_day": self.ticks_per_day,
            "num_days": num_days,
            "rng_seed": self.seed,
            "agent_configs": agent_configs,
            "scenario_events": scenario_events if scenario_events else None,
        }


class ScenarioBuilder:
    """Fluent API for building test scenarios.

    Example:
        scenario = (
            ScenarioBuilder("HighPressure")
            .with_description("High arrival rate scenario")
            .with_duration(100)
            .add_agent(
                "BANK_A",
                balance=1_000_000,
                arrival_rate=5.0,
                arrival_amount_range=(100_000, 250_000)
            )
            .add_agent("BANK_B", balance=20_000_000)
            .add_crisis_event(
                tick=50,
                event_type="CollateralAdjustment",
                agent_id="BANK_A",
                collateral_change=-200_000
            )
            .build()
        )
    """

    def __init__(self, name: str):
        self._scenario = ScenarioDefinition(name=name)

    def with_description(self, description: str) -> 'ScenarioBuilder':
        """Set scenario description."""
        self._scenario.description = description
        return self

    def with_duration(self, ticks: int) -> 'ScenarioBuilder':
        """Set simulation duration in ticks."""
        self._scenario.duration_ticks = ticks
        return self

    def with_ticks_per_day(self, ticks: int) -> 'ScenarioBuilder':
        """Set ticks per day (default 100)."""
        self._scenario.ticks_per_day = ticks
        return self

    def with_seed(self, seed: int) -> 'ScenarioBuilder':
        """Set RNG seed for determinism."""
        self._scenario.seed = seed
        return self

    def add_agent(
        self,
        agent_id: str,
        balance: int,
        credit_limit: int = 0,
        arrival_rate: float = 0.0,
        arrival_amount_range: Tuple[int, int] = (100_000, 250_000),
        deadline_range: Tuple[int, int] = (10, 40),
        counterparty_weights: Optional[Dict[str, float]] = None,
        posted_collateral: Optional[int] = None,
        collateral_haircut: Optional[float] = None,
    ) -> 'ScenarioBuilder':
        """Add an agent to the scenario.

        Args:
            agent_id: Agent identifier
            balance: Opening balance in cents
            credit_limit: Credit limit in cents (default 0)
            arrival_rate: Expected arrivals per tick (default 0 = receiver only)
            arrival_amount_range: (min, max) transaction amounts in cents
            deadline_range: (min, max) deadline ticks
            counterparty_weights: Preferred receivers (default: uniform)
            posted_collateral: Initial posted collateral in cents
            collateral_haircut: Haircut percentage (0.0-1.0)
        """
        agent_cfg = AgentScenarioConfig(
            agent_id=agent_id,
            opening_balance=balance,
            credit_limit=credit_limit,
            arrival_rate=arrival_rate,
            arrival_amount_range=arrival_amount_range,
            deadline_range=deadline_range,
            counterparty_weights=counterparty_weights,
            posted_collateral=posted_collateral,
            collateral_haircut=collateral_haircut,
        )
        self._scenario.agents.append(agent_cfg)
        return self

    def add_event(
        self,
        tick: int,
        event_type: str,
        **parameters
    ) -> 'ScenarioBuilder':
        """Add a scenario event.

        Args:
            tick: Tick when event occurs
            event_type: Type of event (e.g., "CollateralAdjustment")
            **parameters: Event-specific parameters
        """
        event = ScenarioEvent(
            tick=tick,
            event_type=event_type,
            parameters=parameters
        )
        self._scenario.events.append(event)
        return self

    def add_collateral_adjustment(
        self,
        tick: int,
        agent_id: str,
        haircut_change: Optional[float] = None,
        collateral_change: Optional[int] = None,
    ) -> 'ScenarioBuilder':
        """Add a collateral adjustment event (convenience method).

        Args:
            tick: When event occurs
            agent_id: Affected agent
            haircut_change: Change to haircut percentage
            collateral_change: Change to posted collateral (cents)
        """
        params = {"agent_id": agent_id}
        if haircut_change is not None:
            params["haircut_change"] = haircut_change
        if collateral_change is not None:
            params["collateral_change"] = collateral_change

        return self.add_event(tick, "CollateralAdjustment", **params)

    def add_arrival_rate_change(
        self,
        tick: int,
        agent_id: Optional[str] = None,
        multiplier: float = 1.0,
    ) -> 'ScenarioBuilder':
        """Add arrival rate change event.

        Args:
            tick: When event occurs
            agent_id: If None, applies globally; otherwise specific agent
            multiplier: Rate multiplier (e.g., 2.0 = double rate)
        """
        if agent_id:
            return self.add_event(
                tick,
                "AgentArrivalRateChange",
                agent_id=agent_id,
                multiplier=multiplier
            )
        else:
            return self.add_event(
                tick,
                "GlobalArrivalRateChange",
                multiplier=multiplier
            )

    def add_large_payment(
        self,
        tick: int,
        sender: str,
        receiver: str,
        amount: int,
        deadline_offset: int = 10,
    ) -> 'ScenarioBuilder':
        """Add a custom large payment arrival.

        Args:
            tick: When payment arrives
            sender: Sending agent
            receiver: Receiving agent
            amount: Payment amount in cents
            deadline_offset: Ticks until deadline
        """
        return self.add_event(
            tick,
            "CustomTransactionArrival",
            sender=sender,
            receiver=receiver,
            amount=amount,
            deadline=tick + deadline_offset,
            priority=10,
            divisible=False,
        )

    def build(self) -> ScenarioDefinition:
        """Build and return the scenario definition."""
        if not self._scenario.agents:
            raise ValueError("Scenario must have at least one agent")

        return self._scenario
