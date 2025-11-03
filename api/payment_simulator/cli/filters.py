"""Event filtering for CLI output.

Provides EventFilter class for filtering events by:
- Event type(s)
- Agent ID (matches both agent_id and sender_id fields)
- Transaction ID
- Tick range (min/max)

All filters use AND logic (all must match).
"""


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
    ):
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

        # Agent filter (check both agent_id and sender_id fields)
        if self.agent_id is not None:
            # Try agent_id first (policy events), then sender_id (transaction events)
            event_agent = event.get("agent_id") or event.get("sender_id")
            if event_agent != self.agent_id:
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
