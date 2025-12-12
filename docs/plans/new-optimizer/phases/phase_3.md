# Phase 3: User Prompt Builder with Agent Filtering

## Objective
Build the user prompt that provides:
1. Current policy for the target agent
2. Filtered tick-by-tick simulation output (ONLY target agent's events)
3. Past iteration history (policy changes and cost deltas)
4. Final instructions

**CRITICAL INVARIANT**: An LLM optimizing for Agent X may ONLY see:
- Outgoing transactions FROM Agent X
- Incoming liquidity events TO Agent X balance
- Agent X's own policy and state changes

## TDD Approach
Write tests first for the filtering logic, then the prompt builder.

## Files to Create

### 1. Event Filter Module
`api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py`

### 2. User Prompt Builder
`api/payment_simulator/ai_cash_mgmt/prompts/user_prompt_builder.py`

### 3. Test Files
- `api/tests/ai_cash_mgmt/unit/test_event_filter.py`
- `api/tests/ai_cash_mgmt/unit/test_user_prompt_builder.py`

## Event Filtering Rules

### Events Agent X Should See (Outgoing)

| Event Type | Filter Condition |
|------------|------------------|
| `Arrival` | `sender_id == agent_id` |
| `PolicySubmit` | `agent_id == target` |
| `PolicyHold` | `agent_id == target` |
| `PolicyDrop` | `agent_id == target` |
| `PolicySplit` | `agent_id == target` |
| `RtgsImmediateSettlement` | `sender == agent_id` |
| `RtgsSubmission` | `sender == agent_id` |
| `RtgsWithdrawal` | `sender == agent_id` |
| `RtgsResubmission` | `sender == agent_id` |
| `TransactionWentOverdue` | `sender_id == agent_id` |
| `OverdueTransactionSettled` | `sender_id == agent_id` |

### Events Agent X Should See (Incoming Liquidity)

| Event Type | Filter Condition |
|------------|------------------|
| `Arrival` | `receiver_id == agent_id` (notification of incoming) |
| `RtgsImmediateSettlement` | `receiver == agent_id` |
| `Queue2LiquidityRelease` | `receiver == agent_id` |
| `LsmBilateralOffset` | `agent_id in {agent_a, agent_b}` |
| `LsmCycleSettlement` | `agent_id in agents` |

### Events Agent X Should See (Own State)

| Event Type | Filter Condition |
|------------|------------------|
| `CollateralPost` | `agent_id == target` |
| `CollateralWithdraw` | `agent_id == target` |
| `CollateralTimerWithdrawn` | `agent_id == target` |
| `CollateralTimerBlocked` | `agent_id == target` |
| `StateRegisterSet` | `agent_id == target` |
| `BankBudgetSet` | `agent_id == target` |
| `CostAccrual` | `agent_id == target` |

### Events to NEVER Show

| Event Type | Reason |
|------------|--------|
| Other agents' `PolicySubmit/Hold/Drop` | Agent isolation |
| Other agents' `Arrival` (as sender) | Agent isolation |
| Other agents' `CollateralPost/Withdraw` | Agent isolation |
| Other agents' `CostAccrual` | Agent isolation |
| Other agents' `BankBudgetSet` | Agent isolation |

## Test Plan

### Test Group 1: Event Filtering - Outgoing

```python
class TestEventFilterOutgoing:
    """Tests for filtering outgoing transaction events."""

    def test_filters_arrival_by_sender():
        """Only arrivals where agent is sender are included."""
        events = [
            {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A"},
            {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 3  # BANK_A sends 2 + receives 1 (as incoming notification)

    def test_filters_policy_decisions():
        """Policy decisions only for target agent."""
        events = [
            {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx1"},
            {"event_type": "PolicyHold", "agent_id": "BANK_B", "tx_id": "tx2"},
            {"event_type": "PolicyHold", "agent_id": "BANK_A", "tx_id": "tx3"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # Should see BANK_A's decisions only
        assert len(filtered) == 2
        assert all(e["agent_id"] == "BANK_A" for e in filtered if "agent_id" in e)

    def test_filters_rtgs_settlement_by_sender():
        """RTGS settlements where agent is sender."""
        events = [
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_A", "receiver": "BANK_B"},
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # Both: BANK_A as sender (outgoing) and BANK_A as receiver (incoming)
        assert len(filtered) == 2
```

### Test Group 2: Event Filtering - Incoming Liquidity

```python
class TestEventFilterIncoming:
    """Tests for filtering incoming liquidity events."""

    def test_includes_incoming_settlements():
        """Settlements to agent included as incoming liquidity."""
        events = [
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A", "amount": 1000},
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_C", "receiver": "BANK_A", "amount": 2000},
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_C", "amount": 3000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A receives 2 settlements
        receivers = [e for e in filtered if e.get("receiver") == "BANK_A"]
        assert len(receivers) == 2

    def test_includes_lsm_bilateral_if_involved():
        """LSM bilateral offsets included if agent is involved."""
        events = [
            {"event_type": "LsmBilateralOffset", "agent_a": "BANK_A", "agent_b": "BANK_B"},
            {"event_type": "LsmBilateralOffset", "agent_a": "BANK_C", "agent_b": "BANK_D"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["agent_a"] == "BANK_A"

    def test_includes_lsm_cycle_if_involved():
        """LSM cycle settlements included if agent is in cycle."""
        events = [
            {"event_type": "LsmCycleSettlement", "agents": ["BANK_A", "BANK_B", "BANK_C"]},
            {"event_type": "LsmCycleSettlement", "agents": ["BANK_D", "BANK_E"]},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert "BANK_A" in filtered[0]["agents"]

    def test_includes_queue2_release_as_receiver():
        """Queue2 releases where agent receives liquidity."""
        events = [
            {"event_type": "Queue2LiquidityRelease", "sender": "BANK_B", "receiver": "BANK_A"},
            {"event_type": "Queue2LiquidityRelease", "sender": "BANK_A", "receiver": "BANK_C"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        # BANK_A as sender (outgoing) and as receiver (incoming)
        assert len(filtered) == 2
```

### Test Group 3: Event Filtering - Agent State

```python
class TestEventFilterAgentState:
    """Tests for filtering agent state events."""

    def test_includes_own_collateral():
        """Collateral events for target agent only."""
        events = [
            {"event_type": "CollateralPost", "agent_id": "BANK_A", "amount": 10000},
            {"event_type": "CollateralPost", "agent_id": "BANK_B", "amount": 20000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
        assert filtered[0]["agent_id"] == "BANK_A"

    def test_includes_own_cost_accrual():
        """Cost accrual events for target agent only."""
        events = [
            {"event_type": "CostAccrual", "agent_id": "BANK_A", "costs": {"delay": 100}},
            {"event_type": "CostAccrual", "agent_id": "BANK_B", "costs": {"delay": 200}},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1

    def test_includes_own_bank_budget():
        """Bank budget events for target agent only."""
        events = [
            {"event_type": "BankBudgetSet", "agent_id": "BANK_A", "max_value": 50000},
            {"event_type": "BankBudgetSet", "agent_id": "BANK_B", "max_value": 100000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 1
```

### Test Group 4: Event Filtering - Strict Isolation

```python
class TestEventFilterIsolation:
    """Tests for strict agent isolation."""

    def test_never_shows_other_agent_policy():
        """Other agents' policy decisions are never visible."""
        events = [
            {"event_type": "PolicySubmit", "agent_id": "BANK_B", "tx_id": "tx1"},
            {"event_type": "PolicyHold", "agent_id": "BANK_C", "tx_id": "tx2"},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_never_shows_other_agent_collateral():
        """Other agents' collateral events are never visible."""
        events = [
            {"event_type": "CollateralPost", "agent_id": "BANK_B", "amount": 50000},
            {"event_type": "CollateralWithdraw", "agent_id": "BANK_C", "amount": 30000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_never_shows_other_agent_costs():
        """Other agents' cost accruals are never visible."""
        events = [
            {"event_type": "CostAccrual", "agent_id": "BANK_B", "costs": {"delay": 9999}},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 0

    def test_isolation_comprehensive():
        """Comprehensive test of agent isolation."""
        events = [
            # BANK_A should see (4 events)
            {"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"event_type": "RtgsImmediateSettlement", "sender": "BANK_B", "receiver": "BANK_A"},
            {"event_type": "CostAccrual", "agent_id": "BANK_A"},
            {"event_type": "PolicySubmit", "agent_id": "BANK_A", "tx_id": "tx1"},
            # BANK_A should NOT see (4 events)
            {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_C"},
            {"event_type": "CostAccrual", "agent_id": "BANK_B"},
            {"event_type": "PolicyHold", "agent_id": "BANK_B", "tx_id": "tx2"},
            {"event_type": "CollateralPost", "agent_id": "BANK_C", "amount": 10000},
        ]
        filtered = filter_events_for_agent("BANK_A", events)
        assert len(filtered) == 4
```

### Test Group 5: Output Formatting

```python
class TestOutputFormatting:
    """Tests for formatting filtered output as text."""

    def test_format_tick_header():
        """Tick header formatted correctly."""
        events = [{"tick": 5, "event_type": "Arrival", "sender_id": "A", "receiver_id": "B"}]
        output = format_filtered_output("A", events)
        assert "Tick 5" in output or "═══" in output

    def test_format_arrival_event():
        """Arrival event formatted readably."""
        events = [{
            "tick": 1,
            "event_type": "Arrival",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "priority": 5,
            "deadline": 10,
        }]
        output = format_filtered_output("BANK_A", events)
        assert "BANK_A" in output
        assert "BANK_B" in output
        assert "$1,000" in output or "100000" in output

    def test_format_settlement_event():
        """Settlement event formatted with balance info."""
        events = [{
            "tick": 3,
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 50000,
            "sender_balance_before": 100000,
            "sender_balance_after": 50000,
        }]
        output = format_filtered_output("BANK_A", events)
        assert "settled" in output.lower() or "settlement" in output.lower()
```

### Test Group 6: User Prompt Builder

```python
class TestUserPromptBuilder:
    """Tests for building the complete user prompt."""

    def test_includes_current_policy():
        """User prompt includes current policy JSON."""
        policy = {"payment_tree": {"type": "action", "action": "Release"}}
        builder = UserPromptBuilder("BANK_A", policy)
        prompt = builder.build()
        assert "BANK_A" in prompt
        assert "Release" in prompt

    def test_includes_filtered_output():
        """User prompt includes filtered simulation output."""
        events = [{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}]
        builder = UserPromptBuilder("BANK_A", {}).with_events(events)
        prompt = builder.build()
        assert "Tick" in prompt or "tick" in prompt

    def test_includes_iteration_history():
        """User prompt includes past iteration history."""
        history = [{"iteration": 1, "cost_delta": -1000}]
        builder = UserPromptBuilder("BANK_A", {}).with_history(history)
        prompt = builder.build()
        assert "iteration" in prompt.lower() or "history" in prompt.lower()

    def test_includes_final_instructions():
        """User prompt includes final instructions."""
        builder = UserPromptBuilder("BANK_A", {})
        prompt = builder.build()
        assert "instruction" in prompt.lower() or "analyze" in prompt.lower()

    def test_has_table_of_contents():
        """User prompt has clear structure with TOC."""
        builder = UserPromptBuilder("BANK_A", {})
        prompt = builder.build()
        assert "1." in prompt or "TABLE OF CONTENTS" in prompt.upper()
```

## API Design

```python
# event_filter.py

def filter_events_for_agent(
    agent_id: str,
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter simulation events to only those relevant to agent.

    Implements agent isolation: Agent X only sees their outgoing
    transactions and incoming liquidity events.

    Args:
        agent_id: ID of the target agent.
        events: List of simulation events.

    Returns:
        Filtered list of events.
    """
    ...


def format_filtered_output(
    agent_id: str,
    events: list[dict[str, Any]],
    include_tick_headers: bool = True,
) -> str:
    """Format filtered events as readable simulation output.

    Args:
        agent_id: ID of the target agent.
        events: Pre-filtered list of events.
        include_tick_headers: Whether to include tick separators.

    Returns:
        Formatted text output.
    """
    ...


# user_prompt_builder.py

class UserPromptBuilder:
    """Builder for user prompts in optimization."""

    def __init__(self, agent_id: str, current_policy: dict[str, Any]) -> None:
        ...

    def with_events(self, events: list[dict[str, Any]]) -> UserPromptBuilder:
        """Add simulation events (will be filtered)."""
        ...

    def with_history(self, history: list[dict[str, Any]]) -> UserPromptBuilder:
        """Add iteration history."""
        ...

    def with_cost_breakdown(
        self, best_seed: dict[str, Any], worst_seed: dict[str, Any], average: dict[str, Any]
    ) -> UserPromptBuilder:
        """Add cost breakdown from bootstrap evaluation."""
        ...

    def build(self) -> str:
        """Build the complete user prompt."""
        ...


def build_user_prompt(
    agent_id: str,
    current_policy: dict[str, Any],
    events: list[dict[str, Any]],
    history: list[dict[str, Any]] | None = None,
) -> str:
    """Convenience function to build user prompt."""
    ...
```

## Implementation Plan

### Step 1: Create Test Files (TDD)
Create comprehensive tests for event filtering and prompt building.

### Step 2: Implement `filter_events_for_agent()`
Core filtering logic implementing agent isolation.

### Step 3: Implement `format_filtered_output()`
Format events as readable simulation output.

### Step 4: Implement `UserPromptBuilder`
Build the complete user prompt with all sections.

### Step 5: Run All Tests
Verify all tests pass.

### Step 6: Type Check with mypy

## Acceptance Criteria

1. [ ] All tests pass
2. [ ] Agent isolation is strictly enforced
3. [ ] Output is readable and LLM-friendly
4. [ ] Type annotations complete
5. [ ] mypy passes
6. [ ] Integration with existing event types works

## Notes

- Event filtering is the most critical part for correctness
- The output format should match the scaffold in the task description
- Keep formatting consistent with existing verbose output style
- Test edge cases like empty events, single agent scenarios
