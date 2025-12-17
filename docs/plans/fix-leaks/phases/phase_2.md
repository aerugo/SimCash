# Phase 2: Sanitize LSM Event Details

**Status**: Pending
**Started**:
**Completed**:

---

## Objective

Ensure that LSM bilateral and cycle events only show information relevant to the viewing agent, hiding counterparty-specific transaction amounts and net positions.

---

## Invariants Enforced in This Phase

- **INV-10** (NEW): Agent Isolation - Agent X must not see Agent Y's transaction amounts or net positions

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

Add tests to `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py`:

**Test Cases**:
1. `test_lsm_bilateral_hides_counterparty_amount` - Only own side visible in bilateral
2. `test_lsm_cycle_hides_all_tx_amounts` - Individual tx amounts not visible
3. `test_lsm_cycle_hides_net_positions` - Net positions not visible
4. `test_lsm_shows_own_participation` - Agent can see they participated

```python
class TestLSMEventSanitization:
    """Tests for LSM event information sanitization.

    Enforces INV-10: Agent Isolation - Counterparty details hidden.
    """

    def test_lsm_bilateral_hides_counterparty_amount(self) -> None:
        """Bilateral offset must hide counterparty's amount.

        When BANK_A and BANK_B offset:
        - BANK_A sees their own amount
        - BANK_A does NOT see BANK_B's amount
        """
        # Setup: Bilateral with amount_a=80000, amount_b=60000
        # Build context for BANK_A
        # Assert: 80000 visible, 60000 NOT visible

    def test_lsm_cycle_hides_all_tx_amounts(self) -> None:
        """Cycle settlement must hide individual transaction amounts.

        Only total value saved should be visible, not per-agent amounts.
        """
        # Setup: Cycle with tx_amounts=[100000, 150000, 125000]
        # Build context for one participant
        # Assert: Individual amounts NOT visible, total visible

    def test_lsm_cycle_hides_net_positions(self) -> None:
        """Cycle settlement must hide net positions array.

        Net positions reveal liquidity stress of other participants.
        """
        # Setup: Cycle with net_positions=[50000, -75000, 25000]
        # Build context for participant
        # Assert: Net position values NOT visible

    def test_lsm_shows_own_participation(self) -> None:
        """Agent should know they participated in LSM settlement."""
        # Setup: Cycle including viewing agent
        # Build context
        # Assert: Agent sees they were part of settlement
```

### Step 2.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`:

Add agent-aware LSM formatting in `_format_event_details()`:

```python
def _format_event_details(self, event: BootstrapEvent) -> str:
    """Format event details for readability.

    CRITICAL: LSM events are sanitized to hide counterparty-specific data.
    This enforces INV-10: Agent Isolation.
    """
    # Handle settlement events specially to show balance changes
    if event.event_type == "RtgsImmediateSettlement":
        return self._format_settlement_event(event)

    # NEW: Handle LSM bilateral with sanitization
    if event.event_type == "LsmBilateralOffset":
        return self._format_lsm_bilateral(event)

    # NEW: Handle LSM cycle with sanitization
    if event.event_type == "LsmCycleSettlement":
        return self._format_lsm_cycle(event)

    # ... rest of existing code ...

def _format_lsm_bilateral(self, event: BootstrapEvent) -> str:
    """Format LSM bilateral offset with agent isolation.

    Only shows the viewing agent's side of the offset.
    """
    d = event.details
    agent_a = d.get("agent_a")
    agent_b = d.get("agent_b")
    amount_a = d.get("amount_a", 0)
    amount_b = d.get("amount_b", 0)

    # Determine which side is the viewing agent
    if self._agent_id == agent_a:
        own_amount = amount_a
        counterparty = agent_b
    elif self._agent_id == agent_b:
        own_amount = amount_b
        counterparty = agent_a
    else:
        # Shouldn't happen if filtering works, but safe fallback
        return f"LSM Bilateral: {agent_a} <-> {agent_b}"

    # Only show own amount, not counterparty's
    own_fmt = f"${own_amount / 100:,.2f}"
    return f"LSM Bilateral with {counterparty}: Your payment ${own_fmt} offset"

def _format_lsm_cycle(self, event: BootstrapEvent) -> str:
    """Format LSM cycle settlement with agent isolation.

    Shows participation and total saved, but not individual amounts.
    """
    d = event.details
    agents = d.get("agents", [])
    total_value = d.get("total_value", 0)

    # Show participation and total, but not individual amounts/positions
    total_fmt = f"${total_value / 100:,.2f}"
    num_participants = len(agents)

    return f"LSM Cycle: {num_participants} participants, Total: {total_fmt}"
```

### Step 2.3: Refactor

- Extract common formatting helpers
- Ensure consistent currency formatting
- Add type hints

---

## Implementation Details

### What to Hide

| Event Type | Field | Should Hide | Reason |
|------------|-------|-------------|--------|
| `LsmBilateralOffset` | `amount_a` | If viewer != agent_a | Counterparty's transaction size |
| `LsmBilateralOffset` | `amount_b` | If viewer != agent_b | Counterparty's transaction size |
| `LsmCycleSettlement` | `tx_amounts` | Always | Individual transaction sizes |
| `LsmCycleSettlement` | `net_positions` | Always | Liquidity stress indicators |
| `LsmCycleSettlement` | `max_net_outflow` | Always | Identifies struggling bank |
| `LsmCycleSettlement` | `max_net_outflow_agent` | Always | Names struggling bank |

### What to Show

| Event Type | Field | Should Show | Reason |
|------------|-------|-------------|--------|
| `LsmBilateralOffset` | Own amount | Yes | Agent's own data |
| `LsmBilateralOffset` | Counterparty ID | Yes | Know who you offset with |
| `LsmCycleSettlement` | `total_value` | Yes | Total liquidity saved |
| `LsmCycleSettlement` | Participant count | Yes | Scale of cycle |
| `LsmCycleSettlement` | Own participation | Yes | Confirmation of settlement |

### Edge Cases to Handle

- Agent not in LSM event (should be filtered out, but handle gracefully)
- Empty agents list
- Missing amount fields

---

## Files

| File | Action |
|------|--------|
| `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` | MODIFY - Add LSM sanitization tests |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` | MODIFY - Add LSM formatting methods |

---

## Verification

```bash
# Run LSM-specific tests
cd /home/user/SimCash/api
uv run python -m pytest tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py -v -k "lsm"

# Type check
uv run python -m mypy payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py

# Lint
uv run python -m ruff check payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py
```

---

## Completion Criteria

- [ ] `test_lsm_bilateral_hides_counterparty_amount` passes
- [ ] `test_lsm_cycle_hides_all_tx_amounts` passes
- [ ] `test_lsm_cycle_hides_net_positions` passes
- [ ] `test_lsm_shows_own_participation` passes
- [ ] All existing tests still pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] INV-10 (Agent Isolation) verified for LSM events
