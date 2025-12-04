"""Event filtering for CLI output.

Provides EventFilter class for filtering events by:
- Event type(s)
- Agent ID (matches agent_id, sender_id, sender, agent_a, agent_b, agents fields)
- Transaction ID
- Tick range (min/max)

All filters use AND logic (all must match).

For agent filtering:
- Sender/actor matching: agent_id, sender_id, sender, agent_a, agent_b, agents
- Receiver matching: Only for settlement events (receiver, receiver_id)
"""

# Event types that represent settlements where the receiver gains liquidity.
# For these events, we also match when the filtered agent is the receiver.
SETTLEMENT_EVENT_TYPES: frozenset[str] = frozenset({
    "RtgsImmediateSettlement",
    "Queue2LiquidityRelease",
    "LsmBilateralOffset",
    "LsmCycleSettlement",
    "OverdueTransactionSettled",
})


def _get_event_agents(event: dict) -> set[str]:
    """Extract all agent IDs involved in an event as sender/actor.

    Handles the various field naming conventions across event types:
    - agent_id: Policy events (PolicySubmit, PolicyHold, etc.)
    - sender_id: Arrival, QueuedRtgs, TransactionWentOverdue, OverdueTransactionSettled
    - sender: RTGS events (RtgsImmediateSettlement, RtgsSubmission, etc.)
    - agent_a, agent_b: LsmBilateralOffset
    - agents: LsmCycleSettlement

    Args:
        event: Event dict from Rust FFI

    Returns:
        Set of agent IDs involved as sender/actor in the event
    """
    agents: set[str] = set()

    # Standard agent field (policy events, collateral, cost accrual, etc.)
    if agent_id := event.get("agent_id"):
        agents.add(agent_id)

    # Sender ID field (arrivals, queued, overdue events)
    if sender_id := event.get("sender_id"):
        agents.add(sender_id)

    # Sender field (RTGS events use 'sender' not 'sender_id')
    if sender := event.get("sender"):
        agents.add(sender)

    # LSM bilateral fields
    if agent_a := event.get("agent_a"):
        agents.add(agent_a)
    if agent_b := event.get("agent_b"):
        agents.add(agent_b)

    # LSM cycle agents array (both 'agents' and 'agent_ids' field names)
    if agents_list := event.get("agents"):
        if isinstance(agents_list, list):
            agents.update(agents_list)
    if agent_ids_list := event.get("agent_ids"):
        if isinstance(agent_ids_list, list):
            agents.update(agent_ids_list)

    return agents


def _get_event_receiver(event: dict) -> str | None:
    """Extract the receiver agent ID from an event.

    Handles both field naming conventions:
    - receiver: RTGS events
    - receiver_id: Arrival, overdue events

    Args:
        event: Event dict from Rust FFI

    Returns:
        Receiver agent ID or None if not present
    """
    return event.get("receiver") or event.get("receiver_id")


def calculate_incoming_liquidity(event: dict, agent_id: str) -> int:
    """Calculate incoming liquidity for an agent from a settlement event.

    For simple settlements (RTGS, Queue2, OverdueTransactionSettled),
    if the agent is the receiver, they gain the full amount.

    Args:
        event: Settlement event dict from Rust FFI
        agent_id: Agent to calculate incoming liquidity for

    Returns:
        Positive amount if agent receives liquidity, 0 otherwise

    Examples:
        >>> event = {"event_type": "RtgsImmediateSettlement",
        ...          "sender": "BANK_B", "receiver": "BANK_A", "amount": 10000}
        >>> calculate_incoming_liquidity(event, "BANK_A")
        10000
        >>> calculate_incoming_liquidity(event, "BANK_B")
        0
    """
    receiver = _get_event_receiver(event)
    if receiver == agent_id:
        amount = event.get("amount", 0)
        return int(amount) if amount else 0
    return 0


def calculate_lsm_net_change(event: dict, agent_id: str) -> int:
    """Calculate net liquidity change for an agent in an LSM settlement.

    For bilateral offsets:
    - agent_a pays amount_a to agent_b
    - agent_b pays amount_b to agent_a
    - Net change for A = amount_b - amount_a (receives amount_b, pays amount_a)
    - Net change for B = amount_a - amount_b

    For cycle settlements:
    - net_positions[i] gives the net position for agents[i]
    - Positive = net receiver (gains liquidity)
    - Negative = net sender (loses liquidity)

    Args:
        event: LSM event dict from Rust FFI
        agent_id: Agent to calculate net change for

    Returns:
        Net liquidity change (positive = gain, negative = loss)

    Examples:
        >>> event = {"event_type": "LsmBilateralOffset",
        ...          "agent_a": "BANK_A", "agent_b": "BANK_B",
        ...          "amount_a": 8000, "amount_b": 10000}
        >>> calculate_lsm_net_change(event, "BANK_A")
        2000
        >>> calculate_lsm_net_change(event, "BANK_B")
        -2000
    """
    event_type = event.get("event_type")

    if event_type == "LsmBilateralOffset":
        agent_a = event.get("agent_a")
        agent_b = event.get("agent_b")
        amount_a: int = int(event.get("amount_a", 0) or 0)  # A pays to B
        amount_b: int = int(event.get("amount_b", 0) or 0)  # B pays to A

        if agent_id == agent_a:
            # A receives amount_b from B, pays amount_a to B
            return amount_b - amount_a
        elif agent_id == agent_b:
            # B receives amount_a from A, pays amount_b to A
            return amount_a - amount_b
        else:
            return 0

    elif event_type == "LsmCycleSettlement":
        # Handle both field names: 'agents' (test data) and 'agent_ids' (Rust FFI)
        agents: list[str] = event.get("agents") or event.get("agent_ids", [])
        net_positions: list[int] = event.get("net_positions", [])

        if agent_id not in agents:
            return 0

        try:
            idx = agents.index(agent_id)
            if idx < len(net_positions):
                # net_positions: positive = net receiver, negative = net sender
                return int(net_positions[idx])
        except (ValueError, IndexError):
            pass

        return 0

    # Not an LSM event
    return 0


class EventFilter:
    """Filter events based on multiple criteria.

    Attributes:
        event_types: List of event type names to match (None = match all)
        agent_id: Agent ID to match via agent_id or sender_id (None = match all)
        tx_id: Transaction ID to match (None = match all)
        tick_min: Minimum tick (inclusive, None = no minimum)
        tick_max: Maximum tick (inclusive, None = no maximum)

    Examples:
        >>> # Filter for Arrival and Settlement events from BANK_A
        >>> filter = EventFilter(
        ...     event_types=["Arrival", "Settlement"],
        ...     agent_id="BANK_A"
        ... )
        >>> event = {"event_type": "Arrival", "sender_id": "BANK_A"}
        >>> filter.matches(event, tick=10)
        True

        >>> # Filter for specific transaction in tick range
        >>> filter = EventFilter(tx_id="tx123", tick_min=10, tick_max=20)
        >>> filter.matches({"tx_id": "tx123"}, tick=15)
        True
        >>> filter.matches({"tx_id": "tx123"}, tick=25)
        False
    """

    def __init__(
        self,
        event_types: list[str] | None = None,
        agent_id: str | None = None,
        tx_id: str | None = None,
        tick_min: int | None = None,
        tick_max: int | None = None,
    ) -> None:
        """Initialize event filter with optional criteria.

        Args:
            event_types: List of event type names (None = match all, [] = match none)
            agent_id: Agent ID to match (None = match all)
            tx_id: Transaction ID to match (None = match all)
            tick_min: Minimum tick inclusive (None = no minimum)
            tick_max: Maximum tick inclusive (None = no maximum)
        """
        self.event_types = event_types
        self.agent_id = agent_id
        self.tx_id = tx_id
        self.tick_min = tick_min
        self.tick_max = tick_max

    def matches(self, event: dict, tick: int) -> bool:
        """Check if event matches all filter criteria (AND logic).

        Args:
            event: Event dict from Rust FFI
            tick: Current simulation tick

        Returns:
            True if event matches all active filters, False otherwise

        Examples:
            >>> filter = EventFilter(event_types=["Arrival"], tick_min=10)
            >>> filter.matches({"event_type": "Arrival"}, tick=15)
            True
            >>> filter.matches({"event_type": "Arrival"}, tick=5)
            False
            >>> filter.matches({"event_type": "Settlement"}, tick=15)
            False
        """
        # Event type filter
        if self.event_types is not None:
            # Empty list means "match no event types"
            if len(self.event_types) == 0:
                return False
            # Check if event type is in the list
            if event.get("event_type") not in self.event_types:
                return False

        # Agent filter (comprehensive agent matching)
        if self.agent_id is not None:
            # Check if agent is sender/actor
            event_agents = _get_event_agents(event)
            if self.agent_id in event_agents:
                pass  # Agent is sender/actor - continue to other filters
            elif event.get("event_type") in SETTLEMENT_EVENT_TYPES:
                # For settlements only: also match if agent is receiver
                receiver = _get_event_receiver(event)
                if receiver != self.agent_id:
                    return False
            else:
                # Agent not involved in this event
                return False

        # Transaction ID filter
        if self.tx_id is not None:
            if event.get("tx_id") != self.tx_id:
                return False

        # Tick range filters
        if self.tick_min is not None and tick < self.tick_min:
            return False
        if self.tick_max is not None and tick > self.tick_max:
            return False

        # All filters passed
        return True

    @classmethod
    def from_cli_args(
        cls,
        filter_event_type: str | None = None,
        filter_agent: str | None = None,
        filter_tx: str | None = None,
        filter_tick_range: str | None = None,
    ) -> "EventFilter":
        """Create EventFilter from CLI argument strings.

        Args:
            filter_event_type: Comma-separated event type names (e.g., "Arrival,Settlement")
            filter_agent: Agent ID string
            filter_tx: Transaction ID string
            filter_tick_range: Tick range in format "min-max", "min-", or "-max"

        Returns:
            EventFilter instance configured from CLI args

        Examples:
            >>> filter = EventFilter.from_cli_args(
            ...     filter_event_type="Arrival,Settlement",
            ...     filter_agent="BANK_A",
            ...     filter_tick_range="10-50"
            ... )
            >>> filter.event_types
            ['Arrival', 'Settlement']
            >>> filter.agent_id
            'BANK_A'
            >>> filter.tick_min
            10
            >>> filter.tick_max
            50
        """
        # Parse event types (comma-separated)
        event_types = None
        if filter_event_type:
            # Split by comma and strip whitespace from each type
            event_types = [t.strip() for t in filter_event_type.split(",")]

        # Parse tick range ("10-50", "10-", "-50")
        tick_min = None
        tick_max = None
        if filter_tick_range:
            parts = filter_tick_range.split("-", 1)  # Split on first hyphen only
            if len(parts) == 2:
                # "10-50" or "10-" (has min)
                if parts[0]:
                    tick_min = int(parts[0])
                # "10-50" or "-50" (has max)
                if parts[1]:
                    tick_max = int(parts[1])

        return cls(
            event_types=event_types,
            agent_id=filter_agent,
            tx_id=filter_tx,
            tick_min=tick_min,
            tick_max=tick_max,
        )
