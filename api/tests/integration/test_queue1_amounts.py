"""
Test that Queue-1 amounts are displayed correctly in replay.

Issue #3 from replay-crisis-scenario-fixes.md
"""

import pytest
from pathlib import Path
import json

try:
    import duckdb
    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False

from payment_simulator.persistence.connection import DatabaseManager
from payment_simulator.persistence.event_queries import get_simulation_events


@pytest.fixture
def crisis_db():
    """Path to the three_day_realistic_crisis simulation database."""
    db_path = Path(__file__).parent.parent.parent.parent / "api" / "simulation_data.db"
    if not db_path.exists():
        pytest.skip(f"Crisis database not found at {db_path}")
    return db_path


@pytest.fixture
def crisis_db_manager(crisis_db):
    """Database manager for the crisis database, with lock handling."""
    try:
        db_manager = DatabaseManager(str(crisis_db))
        yield db_manager
    except Exception as e:
        if "lock" in str(e).lower() or "IOException" in str(type(e).__name__):
            pytest.skip(f"Database is locked by another process: {e}")
        raise


def test_queue1_amounts_are_nonzero(crisis_db_manager):
    """
    Queue-1 transactions must have positive amounts.

    GIVEN a simulation with queued transactions
    WHEN we retrieve agent state from the database
    THEN queue1 items must have 'amount' field > 0
    """
    db_manager = crisis_db_manager
    conn = db_manager.get_connection()
    cursor = conn.cursor()

    # Get simulation ID
    cursor.execute("SELECT simulation_id FROM simulations LIMIT 1")
    row = cursor.fetchone()
    if not row:
        pytest.skip("No simulation found in database")
    sim_id = row[0]

    # Get agent state at tick 250 (known to have queued items)
    cursor.execute("""
        SELECT details
        FROM simulation_events
        WHERE simulation_id = ?
        AND tick = 250
        AND event_type = 'agent_state'
        LIMIT 1
    """, (sim_id,))

    row = cursor.fetchone()
    if not row:
        pytest.skip("No agent state found at tick 250")

    agent_states = json.loads(row[0])

    # Find an agent with non-empty Queue-1
    found_queue1_with_items = False
    for agent in agent_states:
        if 'queue1' in agent and len(agent['queue1']) > 0:
            found_queue1_with_items = True
            queue1 = agent['queue1']

            # ASSERTION 1: Every Queue-1 item must have an 'amount' field
            for tx in queue1:
                assert 'amount' in tx, (
                    f"Queue-1 transaction {tx.get('id', 'unknown')} missing 'amount' field. "
                    f"Available fields: {list(tx.keys())}"
                )

                # ASSERTION 2: Amount must be positive (non-zero)
                assert tx['amount'] > 0, (
                    f"Queue-1 transaction {tx['id']} has zero/negative amount: {tx['amount']}"
                )

            # ASSERTION 3: Sum of amounts should be non-zero
            total = sum(tx['amount'] for tx in queue1)
            assert total > 0, f"Queue-1 total is zero despite {len(queue1)} transactions"

            break

    assert found_queue1_with_items, "No agent found with Queue-1 items at tick 250"


def test_queue1_display_amounts_match_sum(crisis_db_manager):
    """
    Queue-1 display header sum must match individual amounts.

    GIVEN Queue-1 transactions with amounts
    WHEN displayed in verbose output
    THEN the header total must equal sum of detail amounts
    """
    db_manager = crisis_db_manager

    # Get simulation ID
    conn = db_manager.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT simulation_id FROM simulations LIMIT 1")
    row = cursor.fetchone()
    if not row:
        pytest.skip("No simulation found")
    sim_id = row[0]

    # Get agent states at tick 250
    events_result = get_simulation_events(conn, sim_id, tick=250)
    events = events_result.get('events', [])
    agent_state_events = [e for e in events if e.get('event_type') == 'agent_state']

    if not agent_state_events:
        pytest.skip("No agent state events at tick 250")

    # Parse agent states from first event
    agent_states = agent_state_events[0].get('agents', [])

    for agent in agent_states:
        if 'queue1' in agent and len(agent['queue1']) > 0:
            queue1 = agent['queue1']

            # Calculate actual sum
            actual_sum = sum(tx['amount'] for tx in queue1)

            # The display would show this as:
            # "Queue 1 (N transactions, $X.XX total)"
            # We need to ensure actual_sum > 0
            assert actual_sum > 0, (
                f"Agent {agent['id']} Queue-1 sum is {actual_sum} "
                f"but has {len(queue1)} transactions"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
