"""
Event Query Functions

Provides query functions for retrieving simulation events with filters and pagination.

Per docs/plans/event-timeline-enhancement.md Phase 2 (API Implementation):
- Dynamic query building based on filters
- Pagination support
- Sorting (ascending/descending by tick)
- Agent filtering with comprehensive search
"""

from typing import Any, Dict, List, Optional

import duckdb


def get_simulation_events(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
    tick: Optional[int] = None,
    tick_min: Optional[int] = None,
    tick_max: Optional[int] = None,
    day: Optional[int] = None,
    agent_id: Optional[str] = None,
    tx_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "tick_asc",
) -> Dict[str, Any]:
    """Query simulation events with comprehensive filtering and pagination.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID (required)
        tick: Exact tick filter (optional)
        tick_min: Minimum tick (inclusive, optional)
        tick_max: Maximum tick (inclusive, optional)
        day: Filter by specific day (optional)
        agent_id: Filter by agent ID - searches top-level agent_id and JSONB details (optional)
        tx_id: Filter by transaction ID (optional)
        event_type: Filter by event type(s) - comma-separated for multiple (optional)
        limit: Maximum events to return (default 100, max 1000)
        offset: Pagination offset (default 0)
        sort: Sort order - "tick_asc" or "tick_desc" (default "tick_asc")

    Returns:
        Dict with:
            - events: List of event dicts
            - total: Total matching events (before limit/offset)
            - limit: Limit used
            - offset: Offset used
            - filters: Applied filters

    Raises:
        ValueError: If parameters are invalid (e.g., tick_min > tick_max)

    Examples:
        >>> conn = duckdb.connect(":memory:")
        >>> # ... setup schema and data ...
        >>> result = get_simulation_events(conn, "sim1", tick_min=10, tick_max=20)
        >>> print(f"Found {result['total']} events")
        >>> for event in result['events']:
        ...     print(f"Tick {event['tick']}: {event['event_type']}")
    """
    # Validate parameters
    if tick_min is not None and tick_max is not None and tick_min > tick_max:
        raise ValueError("tick_min cannot be greater than tick_max")

    if limit < 1 or limit > 1000:
        limit = min(max(1, limit), 1000)  # Clamp to [1, 1000]

    if offset < 0:
        offset = 0

    if sort not in ("tick_asc", "tick_desc"):
        raise ValueError(f"Invalid sort parameter: {sort}. Must be 'tick_asc' or 'tick_desc'")

    # Build WHERE clause dynamically
    where_clauses = ["simulation_id = ?"]
    params = [simulation_id]

    if tick is not None:
        where_clauses.append("tick = ?")
        params.append(tick)

    if tick_min is not None:
        where_clauses.append("tick >= ?")
        params.append(tick_min)

    if tick_max is not None:
        where_clauses.append("tick <= ?")
        params.append(tick_max)

    if day is not None:
        where_clauses.append("day = ?")
        params.append(day)

    if tx_id is not None:
        where_clauses.append("tx_id = ?")
        params.append(tx_id)

    if event_type is not None:
        # Handle comma-separated event types
        event_types = [et.strip() for et in event_type.split(",")]
        if len(event_types) == 1:
            where_clauses.append("event_type = ?")
            params.append(event_types[0])
        else:
            placeholders = ",".join("?" * len(event_types))
            where_clauses.append(f"event_type IN ({placeholders})")
            params.extend(event_types)

    if agent_id is not None:
        # Comprehensive agent search:
        # - Top-level agent_id field
        # - sender_id in details JSON
        # - receiver_id in details JSON
        # Note: Use json_extract_string to properly extract and compare string values
        where_clauses.append(
            "(agent_id = ? OR "
            "json_extract_string(details, '$.sender_id') = ? OR "
            "json_extract_string(details, '$.receiver_id') = ?)"
        )
        params.extend([agent_id, agent_id, agent_id])

    where_clause = " AND ".join(where_clauses)

    # Get total count (for pagination metadata)
    count_query = f"SELECT COUNT(*) FROM simulation_events WHERE {where_clause}"
    total = conn.execute(count_query, params).fetchone()[0]

    # Build main query with sorting and pagination
    order = "ASC" if sort == "tick_asc" else "DESC"
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
        ORDER BY tick {order}, event_timestamp {order}
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    # Execute query
    rows = conn.execute(events_query, params).fetchall()

    # Convert rows to dicts
    events = []
    for row in rows:
        import json

        details = json.loads(row[6]) if row[6] else {}

        # Build base event structure
        event = {
            "event_id": row[0],
            "simulation_id": row[1],
            "tick": row[2],
            "day": row[3],
            "event_timestamp": row[4].isoformat() if row[4] else None,
            "event_type": row[5],
            "details": details,
            "agent_id": row[7],
            "tx_id": row[8],
            "created_at": row[9].isoformat() if row[9] else None,
        }

        # Flatten commonly-used fields from details to top level for API ergonomics
        # This makes the API easier to use without needing to parse the details JSON
        if "sender_id" in details:
            event["sender_id"] = details["sender_id"]
        if "receiver_id" in details:
            event["receiver_id"] = details["receiver_id"]
        if "amount" in details:
            event["amount"] = details["amount"]
        if "deadline" in details:
            event["deadline"] = details["deadline"]
        if "priority" in details:
            event["priority"] = details["priority"]

        events.append(event)

    # Build response
    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "filters": {
            "tick": tick,
            "tick_min": tick_min,
            "tick_max": tick_max,
            "day": day,
            "agent_id": agent_id,
            "tx_id": tx_id,
            "event_type": event_type,
            "sort": sort,
        },
    }


def get_simulation_event_summary(
    conn: duckdb.DuckDBPyConnection,
    simulation_id: str,
) -> Dict[str, Any]:
    """Get summary statistics for simulation events.

    Provides metadata about the simulation's events without returning
    the full event list. Useful for dashboards and overview pages.

    Args:
        conn: DuckDB connection
        simulation_id: Simulation ID

    Returns:
        Dict with:
            - total_events: Total number of events
            - total_ticks: Maximum tick number
            - total_days: Maximum day number
            - event_type_counts: Dict mapping event type to count
            - agents: List of unique agent IDs involved

    Examples:
        >>> summary = get_simulation_event_summary(conn, "sim1")
        >>> print(f"Total events: {summary['total_events']}")
        >>> print(f"Event types: {summary['event_type_counts']}")
    """
    # Get total event count
    total_events = conn.execute(
        "SELECT COUNT(*) FROM simulation_events WHERE simulation_id = ?",
        [simulation_id]
    ).fetchone()[0]

    # Get tick/day ranges
    ranges = conn.execute(
        "SELECT MAX(tick), MAX(day) FROM simulation_events WHERE simulation_id = ?",
        [simulation_id]
    ).fetchone()
    total_ticks = ranges[0] if ranges[0] is not None else 0
    total_days = ranges[1] if ranges[1] is not None else 0

    # Get event type counts
    type_counts_rows = conn.execute(
        """
        SELECT event_type, COUNT(*) as count
        FROM simulation_events
        WHERE simulation_id = ?
        GROUP BY event_type
        ORDER BY count DESC
        """,
        [simulation_id]
    ).fetchall()
    event_type_counts = {row[0]: row[1] for row in type_counts_rows}

    # Get unique agents
    agents_rows = conn.execute(
        """
        SELECT DISTINCT agent_id
        FROM simulation_events
        WHERE simulation_id = ? AND agent_id IS NOT NULL
        ORDER BY agent_id
        """,
        [simulation_id]
    ).fetchall()
    agents = [row[0] for row in agents_rows]

    return {
        "total_events": total_events,
        "total_ticks": total_ticks,
        "total_days": total_days,
        "event_type_counts": event_type_counts,
        "agents": agents,
    }
