# TDD Implementation Plan: Unified Replay Output

## TDD Principles

**Red → Green → Refactor Cycle**
1. 🔴 **Red**: Write a failing test that defines desired behavior
2. 🟢 **Green**: Write minimal code to make the test pass
3. 🔵 **Refactor**: Improve code while keeping tests green

**Rules**:
- ✅ Write tests BEFORE implementation
- ✅ Run full test suite after every phase
- ✅ Never proceed to next phase with failing tests
- ✅ Commit after each passing phase

---

## Phase 1: StateProvider Protocol

### 🔴 Red: Write Failing Tests

**File**: `api/tests/unit/test_state_provider.py` (NEW)

```python
"""Test StateProvider protocol and implementations."""
import pytest
from payment_simulator.cli.execution.state_provider import (
    StateProvider,
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator._core import Orchestrator


class TestStateProviderProtocol:
    """Test that StateProvider protocol is properly defined."""

    def test_protocol_has_all_required_methods(self):
        """StateProvider protocol must define all required methods."""
        required_methods = [
            "get_transaction_details",
            "get_agent_balance",
            "get_agent_credit_limit",
            "get_agent_queue1_contents",
            "get_rtgs_queue_contents",
            "get_agent_collateral_posted",
            "get_agent_accumulated_costs",
            "get_queue1_size",
        ]

        for method_name in required_methods:
            assert hasattr(StateProvider, method_name), \
                f"StateProvider protocol missing method: {method_name}"


class TestOrchestratorStateProvider:
    """Test OrchestratorStateProvider wrapper."""

    @pytest.fixture
    def orchestrator(self):
        """Create test orchestrator."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agents": [
                {"id": "BANK_A", "initial_balance": 1000000, "credit_limit": 500000},
                {"id": "BANK_B", "initial_balance": 2000000, "credit_limit": 1000000},
            ],
        }
        return Orchestrator.new(config)

    @pytest.fixture
    def provider(self, orchestrator):
        """Create OrchestratorStateProvider."""
        return OrchestratorStateProvider(orchestrator)

    def test_get_transaction_details(self, provider, orchestrator):
        """Should delegate to orchestrator.get_transaction_details()."""
        # This will fail until we add a transaction
        result = provider.get_transaction_details("nonexistent")
        assert result is None

    def test_get_agent_balance(self, provider):
        """Should return agent balance from orchestrator."""
        balance = provider.get_agent_balance("BANK_A")
        assert balance == 1000000

    def test_get_agent_credit_limit(self, provider):
        """Should return agent credit limit from orchestrator."""
        limit = provider.get_agent_credit_limit("BANK_A")
        assert limit == 500000

    def test_get_agent_queue1_contents(self, provider):
        """Should return queue1 contents from orchestrator."""
        contents = provider.get_agent_queue1_contents("BANK_A")
        assert isinstance(contents, list)
        assert len(contents) == 0  # Empty initially

    def test_get_rtgs_queue_contents(self, provider):
        """Should return RTGS queue contents from orchestrator."""
        contents = provider.get_rtgs_queue_contents()
        assert isinstance(contents, list)
        assert len(contents) == 0  # Empty initially

    def test_get_agent_collateral_posted(self, provider):
        """Should return collateral posted from orchestrator."""
        collateral = provider.get_agent_collateral_posted("BANK_A")
        assert collateral == 0  # None posted initially

    def test_get_agent_accumulated_costs(self, provider):
        """Should return accumulated costs from orchestrator."""
        costs = provider.get_agent_accumulated_costs("BANK_A")
        assert isinstance(costs, dict)
        assert "liquidity_cost" in costs
        assert "delay_cost" in costs
        assert costs["liquidity_cost"] == 0  # No costs initially

    def test_get_queue1_size(self, provider):
        """Should return queue1 size from orchestrator."""
        size = provider.get_queue1_size("BANK_A")
        assert size == 0  # Empty initially


class TestDatabaseStateProvider:
    """Test DatabaseStateProvider for replay."""

    @pytest.fixture
    def mock_db_data(self):
        """Create mock database data for testing."""
        return {
            "tx_cache": {
                "tx_001": {
                    "tx_id": "tx_001",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "amount_settled": 0,
                    "priority": 5,
                    "deadline_tick": 50,
                    "status": "pending",
                    "is_divisible": False,
                }
            },
            "agent_states": {
                "BANK_A": {
                    "agent_id": "BANK_A",
                    "balance": 900000,  # After sending tx_001
                    "credit_limit": 500000,
                    "collateral_posted": 100000,
                    "liquidity_cost": 1000,
                    "delay_cost": 500,
                    "collateral_cost": 200,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
                "BANK_B": {
                    "agent_id": "BANK_B",
                    "balance": 2000000,
                    "credit_limit": 1000000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {
                    "queue1": ["tx_001"],
                    "rtgs": [],
                },
                "BANK_B": {
                    "queue1": [],
                    "rtgs": [],
                },
            },
        }

    @pytest.fixture
    def provider(self, mock_db_data):
        """Create DatabaseStateProvider with mock data."""
        return DatabaseStateProvider(
            conn=None,  # Not needed for these tests
            simulation_id="sim_test",
            tick=42,
            tx_cache=mock_db_data["tx_cache"],
            agent_states=mock_db_data["agent_states"],
            queue_snapshots=mock_db_data["queue_snapshots"],
        )

    def test_get_transaction_details(self, provider):
        """Should return transaction from cache."""
        tx = provider.get_transaction_details("tx_001")
        assert tx is not None
        assert tx["tx_id"] == "tx_001"
        assert tx["sender_id"] == "BANK_A"
        assert tx["amount"] == 100000

    def test_get_transaction_details_nonexistent(self, provider):
        """Should return None for nonexistent transaction."""
        tx = provider.get_transaction_details("nonexistent")
        assert tx is None

    def test_get_agent_balance(self, provider):
        """Should return balance from agent_states."""
        balance = provider.get_agent_balance("BANK_A")
        assert balance == 900000

    def test_get_agent_credit_limit(self, provider):
        """Should return credit limit from agent_states."""
        limit = provider.get_agent_credit_limit("BANK_A")
        assert limit == 500000

    def test_get_agent_queue1_contents(self, provider):
        """Should return queue1 from queue_snapshots."""
        contents = provider.get_agent_queue1_contents("BANK_A")
        assert contents == ["tx_001"]

    def test_get_rtgs_queue_contents(self, provider):
        """Should aggregate RTGS queue from all agents."""
        contents = provider.get_rtgs_queue_contents()
        assert isinstance(contents, list)
        # In this test data, no transactions in RTGS

    def test_get_agent_collateral_posted(self, provider):
        """Should return collateral from agent_states."""
        collateral = provider.get_agent_collateral_posted("BANK_A")
        assert collateral == 100000

    def test_get_agent_accumulated_costs(self, provider):
        """Should return costs dict from agent_states."""
        costs = provider.get_agent_accumulated_costs("BANK_A")
        assert costs["liquidity_cost"] == 1000
        assert costs["delay_cost"] == 500
        assert costs["collateral_cost"] == 200
        assert costs["penalty_cost"] == 0  # Note: using "penalty_cost", not "deadline_penalty"

    def test_get_queue1_size(self, provider):
        """Should return queue1 size."""
        size = provider.get_queue1_size("BANK_A")
        assert size == 1


class TestStateProviderEquivalence:
    """Test that both providers return equivalent data for same state."""

    def test_orchestrator_and_database_providers_match(self):
        """Both providers should return same data for equivalent states."""
        # This is an integration test we'll implement after both providers work
        # For now, just a placeholder
        pass
```

**Expected**: All tests FAIL (files don't exist yet)

### 🟢 Green: Implement Minimal Code

**File**: `api/payment_simulator/cli/execution/state_provider.py` (NEW)

```python
"""State provider protocol for unified output functions.

Defines a common interface for accessing simulation state, implemented by
both live Orchestrator (via FFI) and database replay (via queries).
"""

from typing import Protocol, runtime_checkable
from payment_simulator._core import Orchestrator


@runtime_checkable
class StateProvider(Protocol):
    """Protocol for accessing simulation state.

    This interface is implemented by both:
    - OrchestratorStateProvider (live execution via FFI)
    - DatabaseStateProvider (replay from database)

    Enables unified output functions that work identically in both modes.
    """

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Get transaction details by ID.

        Returns:
            Transaction dict with keys: tx_id, sender_id, receiver_id, amount,
            remaining_amount, priority, deadline_tick, status, is_divisible
            Returns None if transaction not found.
        """
        ...

    def get_agent_balance(self, agent_id: str) -> int:
        """Get agent's current balance in cents."""
        ...

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Get agent's credit limit in cents."""
        ...

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get list of transaction IDs in agent's internal queue."""
        ...

    def get_rtgs_queue_contents(self) -> list[str]:
        """Get list of transaction IDs in RTGS central queue."""
        ...

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral posted by agent in cents."""
        ...

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Get accumulated costs for agent.

        Returns:
            Dict with keys: liquidity_cost, delay_cost, collateral_cost,
            penalty_cost, split_friction_cost (all in cents)
        """
        ...

    def get_queue1_size(self, agent_id: str) -> int:
        """Get size of agent's internal queue."""
        ...


class OrchestratorStateProvider:
    """StateProvider implementation wrapping live Orchestrator (FFI).

    Thin wrapper that delegates all calls to the Rust Orchestrator via PyO3.
    """

    def __init__(self, orch: Orchestrator):
        """Initialize with orchestrator.

        Args:
            orch: Orchestrator instance from Rust FFI
        """
        self.orch = orch

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Delegate to orchestrator."""
        return self.orch.get_transaction_details(tx_id)

    def get_agent_balance(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_balance(agent_id)

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_credit_limit(agent_id)

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_agent_queue1_contents(agent_id)

    def get_rtgs_queue_contents(self) -> list[str]:
        """Delegate to orchestrator."""
        return self.orch.get_rtgs_queue_contents()

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_agent_collateral_posted(agent_id)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Delegate to orchestrator."""
        return self.orch.get_agent_accumulated_costs(agent_id)

    def get_queue1_size(self, agent_id: str) -> int:
        """Delegate to orchestrator."""
        return self.orch.get_queue1_size(agent_id)


class DatabaseStateProvider:
    """StateProvider implementation using database state (replay).

    Reads from pre-loaded database state (agent_states, queue_snapshots, tx_cache)
    to provide same interface as Orchestrator without re-execution.
    """

    def __init__(
        self,
        conn,
        simulation_id: str,
        tick: int,
        tx_cache: dict[str, dict],
        agent_states: dict[str, dict],
        queue_snapshots: dict[str, dict],
    ):
        """Initialize with database state.

        Args:
            conn: Database connection (for future queries if needed)
            simulation_id: Simulation identifier
            tick: Current tick number
            tx_cache: Dict mapping tx_id -> transaction details
            agent_states: Dict mapping agent_id -> agent state dict
            queue_snapshots: Dict mapping agent_id -> queue snapshot dict
        """
        self.conn = conn
        self.simulation_id = simulation_id
        self.tick = tick
        self._tx_cache = tx_cache
        self._agent_states = agent_states
        self._queue_snapshots = queue_snapshots

    def get_transaction_details(self, tx_id: str) -> dict | None:
        """Get transaction from cache."""
        tx = self._tx_cache.get(tx_id)
        if not tx:
            return None

        # Convert database format to orchestrator format
        return {
            "tx_id": tx["tx_id"],
            "sender_id": tx["sender_id"],
            "receiver_id": tx["receiver_id"],
            "amount": tx["amount"],
            "remaining_amount": tx.get("amount", 0) - tx.get("amount_settled", 0),
            "priority": tx["priority"],
            "deadline_tick": tx["deadline_tick"],
            "status": tx["status"],
            "is_divisible": tx.get("is_divisible", False),
        }

    def get_agent_balance(self, agent_id: str) -> int:
        """Get balance from agent_states."""
        return self._agent_states[agent_id]["balance"]

    def get_agent_credit_limit(self, agent_id: str) -> int:
        """Get credit limit from agent_states."""
        return self._agent_states[agent_id]["credit_limit"]

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        """Get queue1 from queue_snapshots."""
        return self._queue_snapshots.get(agent_id, {}).get("queue1", [])

    def get_rtgs_queue_contents(self) -> list[str]:
        """Aggregate RTGS queue from all agent snapshots."""
        rtgs_txs = []
        for agent_id, queues in self._queue_snapshots.items():
            rtgs_txs.extend(queues.get("rtgs", []))
        return rtgs_txs

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        """Get collateral from agent_states."""
        return self._agent_states[agent_id].get("collateral_posted", 0)

    def get_agent_accumulated_costs(self, agent_id: str) -> dict:
        """Get costs from agent_states."""
        state = self._agent_states[agent_id]
        return {
            "liquidity_cost": state.get("liquidity_cost", 0),
            "delay_cost": state.get("delay_cost", 0),
            "collateral_cost": state.get("collateral_cost", 0),
            "penalty_cost": state.get("penalty_cost", 0),
            "split_friction_cost": state.get("split_friction_cost", 0),
        }

    def get_queue1_size(self, agent_id: str) -> int:
        """Get queue1 size."""
        return len(self.get_agent_queue1_contents(agent_id))
```

**Expected**: Tests PASS

### 🔵 Refactor
- Add type hints
- Add docstrings
- Ensure error handling

### ✅ Verify
```bash
cd api
.venv/bin/python -m pytest tests/unit/test_state_provider.py -v
cd ../backend
cargo test --no-default-features
```

---

## Phase 2: Unified log_agent_state()

### 🔴 Red: Write Failing Tests

**File**: `api/tests/unit/test_output_unified.py` (NEW)

```python
"""Test unified output functions work with both StateProvider implementations."""
import pytest
from io import StringIO
import sys
from payment_simulator.cli.execution.state_provider import (
    OrchestratorStateProvider,
    DatabaseStateProvider,
)
from payment_simulator.cli.output import log_agent_state
from payment_simulator._core import Orchestrator


class TestUnifiedLogAgentState:
    """Test that log_agent_state() works with both providers."""

    @pytest.fixture
    def orchestrator_provider(self):
        """Create provider from live orchestrator."""
        config = {
            "seed": 12345,
            "ticks_per_day": 100,
            "agents": [
                {"id": "BANK_A", "initial_balance": 1000000, "credit_limit": 500000},
                {"id": "BANK_B", "initial_balance": 2000000, "credit_limit": 1000000},
            ],
        }
        orch = Orchestrator.new(config)
        return OrchestratorStateProvider(orch)

    @pytest.fixture
    def database_provider(self):
        """Create provider from database state."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": 1000000,
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        return DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

    def capture_output(self, provider, agent_id, balance_change=0):
        """Capture stderr output from log_agent_state."""
        # Redirect stderr to capture output
        old_stderr = sys.stderr
        sys.stderr = StringIO()

        try:
            log_agent_state(provider, agent_id, balance_change, quiet=False)
            output = sys.stderr.getvalue()
        finally:
            sys.stderr = old_stderr

        return output

    def test_log_agent_state_with_orchestrator_provider(self, orchestrator_provider):
        """Should display agent state using orchestrator provider."""
        output = self.capture_output(orchestrator_provider, "BANK_A", balance_change=0)

        # Check output contains expected elements
        assert "BANK_A" in output
        assert "$10,000.00" in output  # 1000000 cents = $10,000.00

    def test_log_agent_state_with_database_provider(self, database_provider):
        """Should display agent state using database provider."""
        output = self.capture_output(database_provider, "BANK_A", balance_change=0)

        # Check output contains expected elements
        assert "BANK_A" in output
        assert "$10,000.00" in output

    def test_both_providers_produce_identical_output(
        self, orchestrator_provider, database_provider
    ):
        """CRITICAL: Both providers must produce identical output."""
        output_orch = self.capture_output(orchestrator_provider, "BANK_A", 0)
        output_db = self.capture_output(database_provider, "BANK_A", 0)

        # Strip timestamps if any, normalize whitespace
        output_orch_normalized = " ".join(output_orch.split())
        output_db_normalized = " ".join(output_db.split())

        assert output_orch_normalized == output_db_normalized, \
            f"Outputs differ:\nOrch: {output_orch}\nDB:   {output_db}"

    def test_log_agent_state_with_balance_change(self, orchestrator_provider):
        """Should show balance change indicator."""
        output = self.capture_output(orchestrator_provider, "BANK_A", balance_change=50000)

        assert "+$500.00" in output

    def test_log_agent_state_with_negative_balance(self):
        """Should show overdraft indicator for negative balance."""
        mock_data = {
            "tx_cache": {},
            "agent_states": {
                "BANK_A": {
                    "balance": -100000,  # Negative balance
                    "credit_limit": 500000,
                    "collateral_posted": 0,
                    "liquidity_cost": 0,
                    "delay_cost": 0,
                    "collateral_cost": 0,
                    "penalty_cost": 0,
                    "split_friction_cost": 0,
                },
            },
            "queue_snapshots": {
                "BANK_A": {"queue1": [], "rtgs": []},
            },
        }
        provider = DatabaseStateProvider(
            conn=None,
            simulation_id="test",
            tick=0,
            tx_cache=mock_data["tx_cache"],
            agent_states=mock_data["agent_states"],
            queue_snapshots=mock_data["queue_snapshots"],
        )

        output = self.capture_output(provider, "BANK_A", 0)
        assert "overdraft" in output.lower()
```

**Expected**: All tests FAIL (log_agent_state doesn't exist yet with new signature)

### 🟢 Green: Implement Unified Function

**File**: `api/payment_simulator/cli/output.py` (MODIFY)

Add new unified function, mark old ones as deprecated:

```python
def log_agent_state(
    provider: "StateProvider",  # Type hint with string to avoid circular import
    agent_id: str,
    balance_change: int = 0,
    quiet: bool = False,
):
    """Log agent state with detailed queue contents (UNIFIED for live & replay).

    Replaces both log_agent_queues_detailed() and log_agent_state_from_db().
    Works with any StateProvider implementation.

    Shows:
    - Agent balance with color coding (overdraft = red, negative change = yellow)
    - Queue 1 (internal) contents with transaction details
    - Queue 2 (RTGS) contents for this agent's transactions
    - Total queued value
    - Credit utilization percentage
    - Collateral posted (if any)

    Args:
        provider: StateProvider instance (Orchestrator or Database)
        agent_id: Agent identifier
        balance_change: Balance change since last tick (cents)
        quiet: Suppress output if True
    """
    if quiet:
        return

    # Get agent state from provider
    balance = provider.get_agent_balance(agent_id)
    credit_limit = provider.get_agent_credit_limit(agent_id)
    collateral = provider.get_agent_collateral_posted(agent_id)
    queue1_contents = provider.get_agent_queue1_contents(agent_id)
    rtgs_queue = provider.get_rtgs_queue_contents()

    # Format balance with color coding
    balance_str = f"${balance / 100:,.2f}"
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    # Balance change indicator
    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    # Credit utilization
    credit_str = ""
    if credit_limit and credit_limit > 0:
        used = max(0, credit_limit - balance)
        utilization_pct = (used / credit_limit) * 100

        if utilization_pct > 80:
            util_str = f"[red]{utilization_pct:.0f}% used[/red]"
        elif utilization_pct > 50:
            util_str = f"[yellow]{utilization_pct:.0f}% used[/yellow]"
        else:
            util_str = f"[green]{utilization_pct:.0f}% used[/green]"

        credit_str = f" | Credit: {util_str}"

    console.print(f"  {agent_id}: {balance_str}{change_str}{credit_str}")

    # Queue 1 (internal)
    if queue1_contents:
        total_value = 0
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 1 ({len(queue1_contents)} transactions, ${total_value / 100:,.2f} total):")
        for tx_id in queue1_contents:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                priority_str = f"P:{tx['priority']}"
                console.print(
                    f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                    f"${tx['remaining_amount'] / 100:,.2f} | {priority_str} | "
                    f"⏰ Tick {tx['deadline_tick']}"
                )
        console.print()

    # Queue 2 (RTGS) - filter for this agent's transactions
    agent_rtgs_txs = []
    for tx_id in rtgs_queue:
        tx = provider.get_transaction_details(tx_id)
        if tx and tx.get("sender_id") == agent_id:
            agent_rtgs_txs.append(tx_id)

    if agent_rtgs_txs:
        total_value = 0
        for tx_id in agent_rtgs_txs:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                total_value += tx.get("remaining_amount", 0)

        console.print(f"     Queue 2 - RTGS ({len(agent_rtgs_txs)} transactions, ${total_value / 100:,.2f}):")
        for tx_id in agent_rtgs_txs:
            tx = provider.get_transaction_details(tx_id)
            if tx:
                console.print(
                    f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                    f"${tx['remaining_amount'] / 100:,.2f} | P:{tx['priority']} | "
                    f"⏰ Tick {tx['deadline_tick']}"
                )
        console.print()

    # Collateral
    if collateral and collateral > 0:
        console.print(f"     Collateral Posted: ${collateral / 100:,.2f}")
        console.print()


# Mark old functions as deprecated
def log_agent_queues_detailed(orch, agent_id, balance, balance_change, quiet=False):
    """DEPRECATED: Use log_agent_state() instead."""
    import warnings
    warnings.warn(
        "log_agent_queues_detailed() is deprecated, use log_agent_state() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    # Delegate to new function
    from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider
    provider = OrchestratorStateProvider(orch)
    log_agent_state(provider, agent_id, balance_change, quiet)


def log_agent_state_from_db(mock_orch, agent_id, state_data, queue_data, quiet=False):
    """DEPRECATED: Use log_agent_state() instead."""
    import warnings
    warnings.warn(
        "log_agent_state_from_db() is deprecated, use log_agent_state() instead",
        DeprecationWarning,
        stacklevel=2,
    )
    # This will need DatabaseStateProvider, but for now just warn
    pass
```

**Expected**: Tests PASS

### ✅ Verify
```bash
cd api
.venv/bin/python -m pytest tests/unit/test_output_unified.py -v
.venv/bin/python -m pytest  # Full suite
cd ../backend
cargo test --no-default-features
```

---

## Phase 3: Unified log_cost_breakdown()

### 🔴 Red: Write Failing Tests

Similar pattern to Phase 2, but for cost breakdown function.

**File**: `api/tests/unit/test_output_unified.py` (ADD TO EXISTING)

```python
class TestUnifiedLogCostBreakdown:
    """Test unified log_cost_breakdown() function."""

    # ... similar tests to log_agent_state
    # Key test: both providers produce identical output
```

### 🟢 Green: Implement

**File**: `api/payment_simulator/cli/output.py` (MODIFY)

Replace both `log_cost_breakdown()` and `log_cost_breakdown_from_db()` with unified version.

### ✅ Verify
```bash
cd api
.venv/bin/python -m pytest tests/unit/test_output_unified.py::TestUnifiedLogCostBreakdown -v
.venv/bin/python -m pytest
cd ../backend
cargo test --no-default-features
```

---

## Phase 4: Database Schema Expansion

### 🔴 Red: Write Failing Tests

**File**: `api/tests/integration/test_database_schema.py` (NEW)

```python
"""Test database schema has all required fields for replay."""
import pytest
from payment_simulator.persistence.database import DatabaseManager


class TestTickAgentStatesSchema:
    """Test tick_agent_states table has all required columns."""

    def test_table_has_credit_limit_column(self):
        """tick_agent_states must have credit_limit column."""
        db = DatabaseManager("test_schema.db")
        # Query schema, verify column exists
        # This will FAIL until we add the migration

    def test_table_has_collateral_posted_column(self):
        """tick_agent_states must have collateral_posted column."""
        # This will FAIL


class TestTickQueueSnapshotsSchema:
    """Test tick_queue_snapshots table has RTGS queue."""

    def test_table_has_rtgs_queue_column(self):
        """tick_queue_snapshots must have rtgs_queue column."""
        # This will FAIL
```

### 🟢 Green: Implement Migration

**File**: `api/payment_simulator/persistence/migrations/` (NEW)

Add Alembic migration or manual SQL migration to add columns.

### ✅ Verify
```bash
cd api
.venv/bin/python -m pytest tests/integration/test_database_schema.py -v
.venv/bin/python -m pytest
cd ../backend
cargo test --no-default-features
```

---

## Phase 5: Complete Persistence

### 🔴 Red: Write Failing Tests

**File**: `api/tests/integration/test_complete_persistence.py` (NEW)

```python
"""Test that all required data is persisted for replay."""

class TestAgentStatePersistence:
    """Test agent state persistence includes all fields."""

    def test_persists_credit_limit(self):
        """Verify credit_limit is saved to database."""
        # Run simulation with persistence
        # Query database
        # Verify credit_limit is present
        # This will FAIL until we update persistence manager
```

### 🟢 Green: Update Persistence Manager

**File**: `api/payment_simulator/cli/execution/persistence.py` (MODIFY)

Update to persist all new fields.

### ✅ Verify
```bash
cd api
.venv/bin/python -m pytest tests/integration/test_complete_persistence.py -v
.venv/bin/python -m pytest
cd ../backend
cargo test --no-default-features
```

---

## Phase 6: Byte-for-Byte Determinism Test

### 🔴 Red: Write THE Test

**File**: `api/tests/integration/test_replay_determinism.py` (NEW)

```python
"""THE ULTIMATE TEST: Replay must produce identical output to live execution."""
import pytest
import subprocess
import tempfile
from pathlib import Path


class TestReplayOutputDeterminism:
    """Verify replay produces byte-for-byte identical output."""

    @pytest.mark.slow
    def test_replay_output_matches_live_execution_exactly(self):
        """CRITICAL TEST: Replay must match live execution line-by-line.

        This test:
        1. Runs simulation with --verbose, captures stderr
        2. Replays from database with --verbose, captures stderr
        3. Compares line-by-line (excluding timestamps)
        4. FAILS if any line differs
        """
        # Create test config
        config_path = Path("test_scenario.yaml")

        # Run live execution, capture stderr
        result_live = subprocess.run(
            ["payment-sim", "run", "--config", str(config_path),
             "--verbose", "--persist", "--db-path", "test_replay.db"],
            capture_output=True,
            text=True,
        )
        live_stderr = result_live.stderr

        # Extract simulation ID from stdout (JSON output)
        import json
        live_output = json.loads(result_live.stdout)
        sim_id = live_output["simulation_id"]

        # Replay from database
        result_replay = subprocess.run(
            ["payment-sim", "replay", "--simulation-id", sim_id,
             "--db-path", "test_replay.db", "--verbose"],
            capture_output=True,
            text=True,
        )
        replay_stderr = result_replay.stderr

        # Normalize output (remove timestamps, normalize whitespace)
        live_lines = normalize_output(live_stderr)
        replay_lines = normalize_output(replay_stderr)

        # Compare line by line
        assert len(live_lines) == len(replay_lines), \
            f"Line count differs: live={len(live_lines)}, replay={len(replay_lines)}"

        for i, (live_line, replay_line) in enumerate(zip(live_lines, replay_lines)):
            assert live_line == replay_line, \
                f"Line {i} differs:\n  Live:   {live_line}\n  Replay: {replay_line}"

        # If we get here, SUCCESS!
        print("✅ REPLAY OUTPUT IS IDENTICAL TO LIVE EXECUTION")


def normalize_output(text: str) -> list[str]:
    """Normalize output for comparison.

    - Remove timestamps
    - Normalize whitespace
    - Remove progress bars/spinners
    """
    lines = []
    for line in text.splitlines():
        # Skip progress indicators
        if "⠋" in line or "⠙" in line or "⠹" in line:
            continue

        # Remove ANSI color codes
        import re
        line = re.sub(r'\x1b\[[0-9;]*m', '', line)

        # Normalize whitespace
        line = " ".join(line.split())

        if line:  # Skip empty lines
            lines.append(line)

    return lines
```

**Expected**: This test will FAIL until we complete all previous phases

### 🟢 Green: Fix All Discrepancies

Iteratively fix issues until test passes:
1. Run test
2. See which line differs
3. Fix the root cause
4. Re-run test
5. Repeat until PASS

### ✅ Final Verification
```bash
cd api
.venv/bin/python -m pytest tests/integration/test_replay_determinism.py -v
.venv/bin/python -m pytest  # Full suite must pass
cd ../backend
cargo test --no-default-features  # Rust tests must pass
```

---

## Commit Strategy

After each phase passes:
```bash
git add .
git commit -m "Phase N: <description>"
```

Final commit after all tests pass:
```bash
git commit -m "feat: achieve byte-for-byte identical replay output

- Implement StateProvider protocol for unified data access
- Replace duplicate output functions with unified versions
- Expand database schema to capture all state
- Add comprehensive determinism tests
- All tests passing (Rust + Python)

Closes #<issue-number>"
```

---

## Success Criteria

✅ All Rust tests pass: `cargo test --no-default-features`
✅ All Python tests pass: `pytest`
✅ Replay determinism test passes
✅ No deprecated warnings
✅ Full test coverage on new code
✅ Documentation updated

## Time Estimate

- Phase 1: 2 hours (protocol + tests)
- Phase 2: 2 hours (agent state unification)
- Phase 3: 1.5 hours (cost breakdown unification)
- Phase 4: 2 hours (schema migration + tests)
- Phase 5: 2 hours (persistence updates)
- Phase 6: 3 hours (determinism test + fixes)

**Total: ~12.5 hours**
