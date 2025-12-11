"""Event compatibility layer for Castro migration to core.

Provides CastroEvent class that wraps core EventRecord and adds
backward-compatible 'details' parameter/property alias for 'event_data'.

Phase 12: Castro Migration to Core Infrastructure
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from payment_simulator.experiments.persistence import EventRecord


class CastroEvent:
    """Event class compatible with both Castro and core.

    Accepts both 'details' and 'event_data' as constructor parameters
    for backward compatibility. Provides 'details' property that
    aliases 'event_data'.

    All costs are integer cents (INV-1 compliance).
    """

    __slots__ = ("event_type", "run_id", "iteration", "timestamp", "event_data")

    def __init__(
        self,
        event_type: str,
        run_id: str,
        iteration: int,
        timestamp: str | datetime,
        event_data: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize CastroEvent.

        Accepts both 'event_data' (core) and 'details' (legacy) parameters.

        Args:
            event_type: Type of event
            run_id: Run identifier
            iteration: Iteration number
            timestamp: Timestamp (str or datetime, will be converted to str)
            event_data: Event data dict (preferred)
            details: Event data dict (legacy alias for event_data)
        """
        self.event_type = event_type
        self.run_id = run_id
        self.iteration = iteration

        # Convert datetime to string if needed
        if isinstance(timestamp, datetime):
            self.timestamp = timestamp.isoformat()
        else:
            self.timestamp = timestamp

        # Accept either event_data or details
        if event_data is not None:
            self.event_data = event_data
        elif details is not None:
            self.event_data = details
        else:
            self.event_data = {}

    @property
    def details(self) -> dict[str, Any]:
        """Backward-compatible alias for event_data."""
        return self.event_data

    def __eq__(self, other: object) -> bool:
        """Check equality."""
        if not isinstance(other, CastroEvent):
            return NotImplemented
        return (
            self.event_type == other.event_type
            and self.run_id == other.run_id
            and self.iteration == other.iteration
            and self.timestamp == other.timestamp
            and self.event_data == other.event_data
        )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"CastroEvent(event_type={self.event_type!r}, "
            f"run_id={self.run_id!r}, iteration={self.iteration}, "
            f"timestamp={self.timestamp!r}, event_data={self.event_data!r})"
        )

    @classmethod
    def from_event_record(cls, record: EventRecord) -> CastroEvent:
        """Create from core EventRecord.

        Args:
            record: Core EventRecord

        Returns:
            CastroEvent wrapping the record
        """
        return cls(
            event_type=record.event_type,
            run_id=record.run_id,
            iteration=record.iteration,
            timestamp=record.timestamp,
            event_data=record.event_data,
        )

    def to_event_record(self) -> EventRecord:
        """Convert to core EventRecord.

        Returns:
            Core EventRecord
        """
        return EventRecord(
            run_id=self.run_id,
            iteration=self.iteration,
            event_type=self.event_type,
            event_data=self.event_data,
            timestamp=self.timestamp,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization.

        Returns:
            Dict representation with 'details' key for compatibility
        """
        return {
            "event_type": self.event_type,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "timestamp": self.timestamp,
            "details": self.event_data,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CastroEvent:
        """Create from dict.

        Args:
            data: Dict with event data

        Returns:
            CastroEvent instance
        """
        # Accept both 'details' and 'event_data' keys
        event_data = data.get("details", data.get("event_data", {}))

        return cls(
            event_type=data["event_type"],
            run_id=data["run_id"],
            iteration=data["iteration"],
            timestamp=data["timestamp"],
            event_data=event_data,
        )
