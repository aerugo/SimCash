"""
Event Persistence Writer

Provides batch writing of simulation events to database with high performance.

Per docs/plans/event-timeline-enhancement.md Phase 2:
- Batch writes for efficiency (target < 5% overhead)
- Converts Rust events to database records
- Handles all event types (Arrival, PolicySubmit, Settlement, LSM, Collateral, etc.)
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List

import duckdb


def write_events_batch(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    events: List[Dict[str, Any]],
    ticks_per_day: int,
) -> int:
    """Write batch of events to simulation_events table.

    For StateRegisterSet events, also writes to agent_state_registers table
    for efficient querying during replay (dual-write pattern).

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID to associate events with
        events: List of event dicts from Rust (via FFI)
        ticks_per_day: Number of ticks per day (for day calculation)

    Returns:
        Number of events written

    Event dict format (from Rust FFI - flat structure):
        {
            "event_type": "PolicySubmit",  # Event variant name
            "tick": 42,
            "tx_id": "...",  # Event-specific fields at top level
            "agent_id": "...",
            # etc.
        }

    Examples:
        >>> conn = duckdb.connect(":memory:")
        >>> # ... setup schema ...
        >>> events = [
        ...     {
        ...         "event_type": "PolicySubmit",
        ...         "tick": 10,
        ...         "tx_id": "tx1",
        ...         "agent_id": "BANK_A"
        ...     },
        ...     {
        ...         "event_type": "Settlement",
        ...         "tick": 10,
        ...         "tx_id": "tx1",
        ...         "amount": 100000
        ...     }
        ... ]
        >>> count = write_events_batch(conn, "sim1", events, ticks_per_day=100)
        >>> count
        2
    """
    if not events:
        return 0

    # Prepare batch insert data for simulation_events
    records = []
    # Prepare batch insert data for agent_state_registers (dual-write)
    state_register_records = []

    for event in events:
        tick = event["tick"]
        day = tick // ticks_per_day
        event_type = event["event_type"]

        # Extract common fields (from flat structure)
        agent_id = event.get("agent_id")
        tx_id = event.get("tx_id")

        # Build details dict from all fields except common ones
        # Common fields: event_type, tick, agent_id, tx_id
        details = {
            k: v
            for k, v in event.items()
            if k not in ("event_type", "tick", "agent_id", "tx_id")
        }

        # Create record tuple for simulation_events
        record = (
            str(uuid.uuid4()),  # event_id
            simulation_id,  # simulation_id
            tick,  # tick
            day,  # day
            datetime.now(),  # event_timestamp
            event_type,  # event_type
            json.dumps(details),  # details (JSON)
            agent_id,  # agent_id (nullable)
            tx_id,  # tx_id (nullable)
            datetime.now(),  # created_at
        )
        records.append(record)

        # Phase 4.5: Dual-write StateRegisterSet events to agent_state_registers
        if event_type == "StateRegisterSet":
            state_register_record = (
                simulation_id,  # simulation_id
                tick,  # tick
                agent_id,  # agent_id
                event.get("register_key"),  # register_key
                event.get("new_value"),  # register_value (store new_value)
            )
            state_register_records.append(state_register_record)

    # Batch insert into simulation_events
    conn.executemany(
        """
        INSERT INTO simulation_events (
            event_id,
            simulation_id,
            tick,
            day,
            event_timestamp,
            event_type,
            details,
            agent_id,
            tx_id,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )

    # Batch insert into agent_state_registers (if any StateRegisterSet events)
    if state_register_records:
        conn.executemany(
            """
            INSERT INTO agent_state_registers (
                simulation_id,
                tick,
                agent_id,
                register_key,
                register_value
            ) VALUES (?, ?, ?, ?, ?)
            """,
            state_register_records,
        )

    return len(records)


def clear_simulation_events(conn: duckdb.DuckDBPyConnection, simulation_id: str) -> int:
    """Clear all events for a simulation.

    Useful for cleanup or when restarting a simulation.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID to clear events for

    Returns:
        Number of events deleted

    Examples:
        >>> conn = duckdb.connect(":memory:")
        >>> # ... setup schema and insert events ...
        >>> deleted = clear_simulation_events(conn, "sim1")
        >>> deleted
        42
    """
    result = conn.execute(
        "DELETE FROM simulation_events WHERE simulation_id = ?", [simulation_id]
    ).fetchone()

    # DuckDB returns number of rows affected
    return result[0] if result else 0


def get_event_count(conn: duckdb.DuckDBPyConnection, simulation_id: str) -> int:
    """Get total number of events for a simulation.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID

    Returns:
        Number of events

    Examples:
        >>> conn = duckdb.connect(":memory:")
        >>> # ... setup schema and insert events ...
        >>> count = get_event_count(conn, "sim1")
        >>> count
        150
    """
    result = conn.execute(
        "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?",
        [simulation_id],
    ).fetchone()

    return result[0] if result else 0


def get_events(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: int | None = None,
    agent_id: str | None = None,
    tx_id: str | None = None,
    event_type: str | None = None,
    day: int | None = None,
    limit: int = 1000,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query events with optional filters.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID (required)
        tick: Filter by specific tick (optional)
        agent_id: Filter by agent ID (optional)
        tx_id: Filter by transaction ID (optional)
        event_type: Filter by event type (optional)
        day: Filter by day (optional)
        limit: Maximum events to return (default 1000)
        offset: Pagination offset (default 0)

    Returns:
        Dict with:
            - events: List of event dicts
            - total_count: Total matching events (before limit/offset)
            - limit: Limit used
            - offset: Offset used

    Examples:
        >>> conn = duckdb.connect(":memory:")
        >>> # ... setup schema and insert events ...
        >>> result = get_events(conn, "sim1", tick=10)
        >>> result["total_count"]
        5
        >>> len(result["events"])
        5
        >>> result["events"][0]["event_type"]
        'PolicySubmit'
    """
    # Build WHERE clause dynamically
    where_clauses = ["simulation_id = ?"]
    params = [simulation_id]

    if tick is not None:
        where_clauses.append("tick = ?")
        params.append(tick)

    if agent_id is not None:
        where_clauses.append("agent_id = ?")
        params.append(agent_id)

    if tx_id is not None:
        where_clauses.append("tx_id = ?")
        params.append(tx_id)

    if event_type is not None:
        where_clauses.append("event_type = ?")
        params.append(event_type)

    if day is not None:
        where_clauses.append("day = ?")
        params.append(day)

    where_clause = " AND ".join(where_clauses)

    # Get total count
    count_query = f"SELECT COUNT(*) FROM simulation_events WHERE {where_clause}"
    total_count = conn.execute(count_query, params).fetchone()[0]

    # Get events with limit/offset
    events_query = f"""
        SELECT
            event_id,
            simulation_id,
            tick,
            day,
            event_timestamp,
            event_type,
            details,
            agent_id,
            tx_id,
            created_at
        FROM simulation_events
        WHERE {where_clause}
        ORDER BY tick, event_timestamp
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    rows = conn.execute(events_query, params).fetchall()

    # Convert to list of dicts
    events = []
    for row in rows:
        event = {
            "event_id": row[0],
            "simulation_id": row[1],
            "tick": row[2],
            "day": row[3],
            "event_timestamp": row[4].isoformat() if row[4] else None,
            "event_type": row[5],
            "details": json.loads(row[6]) if row[6] else {},
            "agent_id": row[7],
            "tx_id": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
        }
        events.append(event)

    return {
        "events": events,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }
