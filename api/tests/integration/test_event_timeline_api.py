"""
Phase 2: Event Timeline API - Integration Tests

Tests for the enhanced events endpoint.

This test suite verifies:
1. Basic event retrieval
2. Tick filtering (exact, min, max, range)
3. Agent filtering
4. Event type filtering
5. Transaction ID filtering
6. Day filtering
7. Pagination (limit, offset)
8. Sorting (tick_asc, tick_desc)
9. Error handling (404, 400)

Status: GREEN - Implementation complete
- Endpoint: GET /simulations/{sim_id}/events
- Query functions implemented in event_queries.py
- Event persistence via event_writer.py

Following plan: docs/plans/event-timeline-enhancement.md Phase 2 (lines 817-967)
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from payment_simulator.api.main import app
from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_writer import write_events_batch
from payment_simulator._core import Orchestrator


@pytest.fixture
def test_db(tmp_path):
    """Create temporary database with schema."""
    db_path = tmp_path / "test_api.db"
    manager = DatabaseManager(db_path)
    manager.setup()
    yield manager
    manager.close()


@pytest.fixture
def sample_simulation_with_events(test_db):
    """Create a simulation and populate with events."""
    simulation_id = "test_sim_api_001"

    # Create orchestrator and run simulation
    config = {
        "rng_seed": 42,
        "ticks_per_day": 10,
        "num_days": 1,
        "agent_configs": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_B",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
            {
                "id": "BANK_C",
                "opening_balance": 1_000_000,
                "credit_limit": 0,
                "policy": {"type": "Fifo"},
            },
        ],
    }

    orch = Orchestrator.new(config)

    # Submit transactions to different agents at different ticks
    orch.submit_transaction(
        sender="BANK_A", receiver="BANK_B", amount=100_000,
        deadline_tick=50, priority=5, divisible=False
    )
    orch.submit_transaction(
        sender="BANK_B", receiver="BANK_C", amount=200_000,
        deadline_tick=50, priority=7, divisible=False
    )

    # Run 5 ticks to generate events
    for _ in range(5):
        orch.tick()

    # Submit more transactions
    orch.submit_transaction(
        sender="BANK_C", receiver="BANK_A", amount=150_000,
        deadline_tick=50, priority=3, divisible=False
    )

    # Run 5 more ticks
    for _ in range(5):
        orch.tick()

    # Extract and persist events
    events = orch.get_all_events()
    count = write_events_batch(
        conn=test_db.conn,
        simulation_id=simulation_id,
        events=events,
        ticks_per_day=config["ticks_per_day"]
    )

    return {
        "simulation_id": simulation_id,
        "total_events": count,
        "total_ticks": 10,
        "agents": ["BANK_A", "BANK_B", "BANK_C"],
    }


@pytest.fixture
def client(test_db):
    """Create FastAPI test client with configured database."""
    # Configure the app's manager to use our test database
    from payment_simulator.api.main import manager

    # Set the test database manager
    manager.db_manager = test_db

    client = TestClient(app)

    yield client

    # Cleanup: reset db_manager
    manager.db_manager = None


class TestBasicEventRetrieval:
    """Test basic event endpoint functionality.

    Endpoint implemented.
    """

    def test_get_events_basic(self, client, sample_simulation_with_events):
        """Verify basic event retrieval without filters.

        Endpoint implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "events" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

        # Verify events returned
        assert isinstance(data["events"], list)
        assert data["total"] > 0
        assert len(data["events"]) <= data["limit"]

    def test_get_events_returns_event_structure(self, client, sample_simulation_with_events):
        """Verify each event has required fields.

        Endpoint implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events")

        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) > 0

        # Check first event structure
        event = events[0]
        assert "event_id" in event
        assert "simulation_id" in event
        assert "tick" in event
        assert "day" in event
        assert "event_type" in event
        assert "event_timestamp" in event
        assert "details" in event


class TestTickFiltering:
    """Test filtering by tick (exact, min, max, range).

    RED: Filtering logic not implemented.
    """

    def test_filter_by_exact_tick(self, client, sample_simulation_with_events):
        """Filter events for a specific tick.

        RED: tick parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?tick=2")

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should be from tick 2
        for event in events:
            assert event["tick"] == 2

    def test_filter_by_tick_range(self, client, sample_simulation_with_events):
        """Filter events by tick range (min and max).

        RED: tick_min and tick_max parameters not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events?tick_min=2&tick_max=5"
        )

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should be in range [2, 5]
        for event in events:
            assert 2 <= event["tick"] <= 5

    def test_filter_by_tick_min_only(self, client, sample_simulation_with_events):
        """Filter events with minimum tick.

        RED: tick_min parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?tick_min=5")

        assert response.status_code == 200
        events = response.json()["events"]

        for event in events:
            assert event["tick"] >= 5

    def test_filter_by_tick_max_only(self, client, sample_simulation_with_events):
        """Filter events with maximum tick.

        RED: tick_max parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?tick_max=3")

        assert response.status_code == 200
        events = response.json()["events"]

        for event in events:
            assert event["tick"] <= 3


class TestAgentFiltering:
    """Test filtering by agent_id.

    RED: Agent filtering not implemented.
    """

    def test_filter_by_agent_id(self, client, sample_simulation_with_events):
        """Filter events involving specific agent.

        RED: agent_id parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?agent_id=BANK_A")

        assert response.status_code == 200
        events = response.json()["events"]

        # At least some events should involve BANK_A
        assert len(events) > 0

        # Check that BANK_A appears in events
        # (either as top-level agent_id or in details)
        for event in events:
            agent_id = event.get("agent_id")
            details = event.get("details", {})

            # BANK_A should appear somewhere in the event
            assert (
                agent_id == "BANK_A"
                or details.get("sender_id") == "BANK_A"
                or details.get("receiver_id") == "BANK_A"
            )


class TestEventTypeFiltering:
    """Test filtering by event_type.

    RED: Event type filtering not implemented.
    """

    def test_filter_by_single_event_type(self, client, sample_simulation_with_events):
        """Filter by single event type.

        RED: event_type parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events?event_type=Settlement"
        )

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should be Settlement type
        for event in events:
            assert event["event_type"] == "Settlement"

    def test_filter_by_multiple_event_types(self, client, sample_simulation_with_events):
        """Filter by multiple event types (comma-separated).

        RED: Multiple event type filtering not implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events?event_type=Arrival,Settlement"
        )

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should be either Arrival or Settlement
        for event in events:
            assert event["event_type"] in ["Arrival", "Settlement"]


class TestTransactionFiltering:
    """Test filtering by transaction ID.

    RED: Transaction filtering not implemented.
    """

    def test_filter_by_tx_id(self, client, sample_simulation_with_events):
        """Filter events for specific transaction.

        RED: tx_id parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]

        # First, get an event with a tx_id
        response = client.get(f"/simulations/{sim_id}/events?event_type=Arrival")
        assert response.status_code == 200
        events = response.json()["events"]
        assert len(events) > 0

        # Get tx_id from first arrival event
        tx_id = events[0]["tx_id"]

        # Now filter by that tx_id
        response = client.get(f"/simulations/{sim_id}/events?tx_id={tx_id}")
        assert response.status_code == 200
        filtered_events = response.json()["events"]

        # All events should relate to this transaction
        for event in filtered_events:
            event_tx_id = event.get("tx_id") or event.get("details", {}).get("tx_id")
            assert event_tx_id == tx_id


class TestDayFiltering:
    """Test filtering by day.

    RED: Day filtering not implemented.
    """

    def test_filter_by_day(self, client, sample_simulation_with_events):
        """Filter events for specific day.

        RED: day parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?day=0")

        assert response.status_code == 200
        events = response.json()["events"]

        # All events should be from day 0
        for event in events:
            assert event["day"] == 0


class TestPagination:
    """Test pagination with limit and offset.

    RED: Pagination not implemented.
    """

    def test_pagination_with_limit(self, client, sample_simulation_with_events):
        """Test limit parameter.

        RED: limit parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?limit=5")

        assert response.status_code == 200
        data = response.json()

        assert len(data["events"]) <= 5
        assert data["limit"] == 5

    def test_pagination_with_offset(self, client, sample_simulation_with_events):
        """Test offset parameter.

        RED: offset parameter not handled.
        """
        sim_id = sample_simulation_with_events["simulation_id"]

        # Get first page
        response1 = client.get(f"/simulations/{sim_id}/events?limit=3&offset=0")
        assert response1.status_code == 200
        page1 = response1.json()["events"]

        # Get second page
        response2 = client.get(f"/simulations/{sim_id}/events?limit=3&offset=3")
        assert response2.status_code == 200
        page2 = response2.json()["events"]

        # Pages should not overlap
        page1_ids = [e["event_id"] for e in page1]
        page2_ids = [e["event_id"] for e in page2]
        assert len(set(page1_ids) & set(page2_ids)) == 0

    def test_pagination_respects_max_limit(self, client, sample_simulation_with_events):
        """Test that limit cannot exceed maximum.

        GREEN: Limit validation implemented (clamps to 1000).
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?limit=5000")

        # Should either clamp to 1000, return 400, or 422 (validation error)
        assert response.status_code in [200, 400, 422]
        if response.status_code == 200:
            assert response.json()["limit"] <= 1000


class TestSorting:
    """Test sorting by tick (ascending/descending).

    RED: Sorting not implemented.
    """

    def test_sort_tick_ascending(self, client, sample_simulation_with_events):
        """Test ascending sort (default).

        RED: Sorting logic not implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?sort=tick_asc")

        assert response.status_code == 200
        events = response.json()["events"]

        # Verify ascending order
        ticks = [e["tick"] for e in events]
        assert ticks == sorted(ticks)

    def test_sort_tick_descending(self, client, sample_simulation_with_events):
        """Test descending sort.

        RED: Descending sort not implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(f"/simulations/{sim_id}/events?sort=tick_desc")

        assert response.status_code == 200
        events = response.json()["events"]

        # Verify descending order
        ticks = [e["tick"] for e in events]
        assert ticks == sorted(ticks, reverse=True)


class TestErrorHandling:
    """Test error cases.

    RED: Error handling not implemented.
    """

    def test_simulation_not_found(self, client):
        """Test 404 when simulation doesn't exist.

        GREEN: 404 handling implemented.
        """
        response = client.get("/simulations/nonexistent_sim/events")
        assert response.status_code == 404
        assert "detail" in response.json()  # FastAPI returns "detail" for errors

    def test_invalid_tick_range(self, client, sample_simulation_with_events):
        """Test 400 when tick_min > tick_max.

        GREEN: Parameter validation implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events?tick_min=10&tick_max=5"
        )

        assert response.status_code == 400
        assert "detail" in response.json()  # FastAPI returns "detail" for errors

    def test_invalid_sort_parameter(self, client, sample_simulation_with_events):
        """Test 400 for invalid sort parameter.

        RED: Sort validation not implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events?sort=invalid"
        )

        assert response.status_code in [400, 422]  # FastAPI uses 422 for validation


class TestCombinedFilters:
    """Test combining multiple filters.

    RED: Multi-filter support not implemented.
    """

    def test_tick_range_and_agent(self, client, sample_simulation_with_events):
        """Test combining tick range and agent filters.

        RED: Combined filtering not implemented.
        """
        sim_id = sample_simulation_with_events["simulation_id"]
        response = client.get(
            f"/simulations/{sim_id}/events"
            f"?tick_min=2&tick_max=5&agent_id=BANK_A"
        )

        assert response.status_code == 200
        events = response.json()["events"]

        # Verify both filters applied
        for event in events:
            assert 2 <= event["tick"] <= 5
            # BANK_A should be involved
            agent_id = event.get("agent_id")
            details = event.get("details", {})
            assert (
                agent_id == "BANK_A"
                or details.get("sender_id") == "BANK_A"
                or details.get("receiver_id") == "BANK_A"
            )


# Implementation complete - tests should now pass
# Note: Endpoints use /simulations/... not /simulations/...
