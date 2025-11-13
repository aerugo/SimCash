"""
Transaction Journey Testing

Track individual transactions through their lifecycle to understand
policy-specific decision-making and event sequences.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from payment_simulator._core import Orchestrator


@dataclass
class JourneyEvent:
    """Single event in a transaction's journey."""

    tick: int
    event_type: str
    details: Dict[str, Any]

    def __repr__(self) -> str:
        return f"[T{self.tick}] {self.event_type}"


@dataclass
class TransactionJourney:
    """Complete journey of a single transaction through the system."""

    tx_id: str
    sender: str
    receiver: str
    amount: int  # cents
    deadline: int
    events: List[JourneyEvent] = field(default_factory=list)

    def add_event(self, tick: int, event_type: str, details: Dict):
        """Add an event to this journey."""
        self.events.append(JourneyEvent(tick, event_type, details))

    @property
    def arrival_tick(self) -> Optional[int]:
        """Tick when transaction arrived."""
        for event in self.events:
            if event.event_type == "Arrival":
                return event.tick
        return None

    @property
    def settlement_tick(self) -> Optional[int]:
        """Tick when transaction settled (fully or partially)."""
        for event in self.events:
            if event.event_type in ["RtgsImmediateSettlement", "LsmBilateralOffset", "LsmCycleSettlement"]:
                return event.tick
        return None

    @property
    def time_to_settle(self) -> Optional[int]:
        """Ticks between arrival and settlement."""
        if self.arrival_tick is not None and self.settlement_tick is not None:
            return self.settlement_tick - self.arrival_tick
        return None

    @property
    def was_queued(self) -> bool:
        """Was transaction held in queue at any point."""
        return any(e.event_type == "QueueHold" for e in self.events)

    @property
    def used_collateral(self) -> bool:
        """Did transaction trigger collateral posting."""
        return any(e.event_type == "CollateralPosted" for e in self.events)

    @property
    def used_credit(self) -> bool:
        """Did transaction use credit."""
        return any(e.event_type == "CreditUsed" for e in self.events)

    @property
    def was_split(self) -> bool:
        """Was transaction split into parts."""
        return any(e.event_type == "TransactionSplit" for e in self.events)

    @property
    def violated_deadline(self) -> bool:
        """Did transaction violate its deadline."""
        return any(e.event_type == "DeadlineViolation" for e in self.events)

    def summary(self) -> str:
        """Human-readable journey summary."""
        lines = [
            f"Transaction {self.tx_id} ({self.sender} → {self.receiver}, ${self.amount/100:.2f})",
            f"  Deadline: T{self.deadline}",
        ]

        if self.arrival_tick is not None:
            lines.append(f"  Arrived: T{self.arrival_tick}")

        if self.settlement_tick is not None:
            lines.append(f"  Settled: T{self.settlement_tick} (delay: {self.time_to_settle} ticks)")
        else:
            lines.append(f"  Status: UNSETTLED")

        # Key events
        flags = []
        if self.was_queued:
            flags.append("queued")
        if self.used_collateral:
            flags.append("collateral")
        if self.used_credit:
            flags.append("credit")
        if self.was_split:
            flags.append("split")
        if self.violated_deadline:
            flags.append("DEADLINE VIOLATED")

        if flags:
            lines.append(f"  Flags: {', '.join(flags)}")

        # Event sequence
        lines.append(f"  Events ({len(self.events)}):")
        for event in self.events:
            lines.append(f"    {event}")

        return "\n".join(lines)


class JourneyTracker:
    """Tracks journeys for multiple transactions during simulation."""

    def __init__(self):
        self.journeys: Dict[str, TransactionJourney] = {}

    def track_transaction(self, tx_id: str, sender: str, receiver: str, amount: int, deadline: int):
        """Start tracking a transaction."""
        self.journeys[tx_id] = TransactionJourney(tx_id, sender, receiver, amount, deadline)

    def record_event(self, tx_id: str, tick: int, event_type: str, details: Dict):
        """Record an event for a tracked transaction."""
        if tx_id in self.journeys:
            self.journeys[tx_id].add_event(tick, event_type, details)

    def get_journey(self, tx_id: str) -> Optional[TransactionJourney]:
        """Get journey for a specific transaction."""
        return self.journeys.get(tx_id)

    def get_all_journeys(self) -> List[TransactionJourney]:
        """Get all tracked journeys."""
        return list(self.journeys.values())


class TransactionJourneyTest:
    """Test that tracks specific transactions through their lifecycle.

    Unlike PolicyScenarioTest which tracks aggregate metrics, this tracks
    individual transactions to understand policy-specific decision-making.

    Example:
        tracker = JourneyTracker()

        test = TransactionJourneyTest(policy, scenario, tracker)
        test.run()

        # Analyze specific transaction
        journey = tracker.get_journey("tx-001")
        assert journey.settlement_tick is not None
        assert journey.time_to_settle < 20
    """

    def __init__(self, policy: Dict, scenario, tracker: JourneyTracker, agent_id: str = "BANK_A"):
        self.policy = policy
        self.scenario = scenario
        self.tracker = tracker
        self.agent_id = agent_id

    def run(self):
        """Run simulation and track transaction journeys."""
        # Build orchestrator config
        policy_configs = {
            agent.agent_id: self.policy
            for agent in self.scenario.agents
        }

        orch_config = self.scenario.to_orchestrator_config(policy_configs)
        orch = Orchestrator.new(orch_config)

        # Run simulation
        for tick in range(self.scenario.duration_ticks):
            orch.tick()

            # Extract events for all tracked transactions
            events = orch.get_tick_events(tick)
            for event in events:
                event_type = event.get("event_type") or event.get("type")
                if not event_type:
                    continue

                tx_id = event.get("tx_id")

                # Track arrivals (start tracking)
                if event_type == "Arrival":
                    sender_id = event.get("sender_id")
                    receiver_id = event.get("receiver_id")
                    amount = event.get("amount")
                    deadline = event.get("deadline")

                    if sender_id == self.agent_id:
                        self.tracker.track_transaction(tx_id, sender_id, receiver_id, amount, deadline)
                        self.tracker.record_event(tx_id, tick, event_type, event)

                # Track all events for tracked transactions
                elif tx_id and tx_id in self.tracker.journeys:
                    self.tracker.record_event(tx_id, tick, event_type, event)

                # Also track parent transaction for splits
                parent_tx_id = event.get("parent_tx_id")
                if parent_tx_id and parent_tx_id in self.tracker.journeys:
                    self.tracker.record_event(parent_tx_id, tick, event_type, event)


# Convenience functions for common journey assertions

def assert_settled_within(journey: TransactionJourney, max_ticks: int):
    """Assert transaction settled within N ticks."""
    assert journey.settlement_tick is not None, f"{journey.tx_id} never settled"
    assert journey.time_to_settle <= max_ticks, \
        f"{journey.tx_id} took {journey.time_to_settle} ticks (max {max_ticks})"


def assert_no_deadline_violation(journey: TransactionJourney):
    """Assert transaction did not violate deadline."""
    assert not journey.violated_deadline, f"{journey.tx_id} violated deadline"


def assert_used_mechanism(journey: TransactionJourney, mechanism: str):
    """Assert transaction used specific mechanism (collateral, credit, split)."""
    mechanisms = {
        "collateral": journey.used_collateral,
        "credit": journey.used_credit,
        "split": journey.was_split,
    }
    assert mechanisms.get(mechanism, False), \
        f"{journey.tx_id} did not use {mechanism}"


def compare_journeys(journeys: Dict[str, TransactionJourney], metric: str) -> Dict[str, Any]:
    """Compare metric across multiple journeys.

    Args:
        journeys: Dict of policy_name -> TransactionJourney
        metric: Metric to compare (e.g., "time_to_settle", "was_queued")

    Returns:
        Dict with comparison results
    """
    results = {}
    for policy_name, journey in journeys.items():
        value = getattr(journey, metric, None)
        results[policy_name] = value
    return results
