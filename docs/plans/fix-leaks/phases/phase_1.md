# Phase 1: Fix RtgsImmediateSettlement Balance Leakage

**Status**: Pending
**Started**:
**Completed**:

---

## Objective

Ensure that when Agent A receives a payment from Agent B, Agent A cannot see Agent B's balance change (sender_balance_before → sender_balance_after). Only the sender should see their own balance information.

---

## Invariants Enforced in This Phase

- **INV-1**: Money is ALWAYS i64 - Balance values remain integer cents in events
- **INV-10** (NEW): Agent Isolation - Receiver must not see sender's balance

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create tests in `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py`:

**Test Cases**:
1. `test_rtgs_settlement_receiver_cannot_see_sender_balance` - Receiver sees amount but not balance
2. `test_rtgs_settlement_sender_can_see_own_balance` - Sender sees their own balance change
3. `test_rtgs_settlement_balance_fields_hidden_from_receiver` - Specific field check

```python
class TestRtgsBalanceIsolation:
    """Tests for RTGS settlement balance isolation.

    Enforces INV-10: Agent Isolation - Receiver must not see sender's balance.
    """

    def test_rtgs_settlement_receiver_cannot_see_sender_balance(self) -> None:
        """Receiver must NOT see sender's balance_before/balance_after.

        When BANK_B sends to BANK_A, BANK_A should see:
        - The payment amount
        - The sender identity
        But NOT:
        - sender_balance_before
        - sender_balance_after
        """
        # Setup: Create event where BANK_B pays BANK_A
        # Build context for BANK_A (receiver)
        # Assert: Balance values NOT in formatted output

    def test_rtgs_settlement_sender_can_see_own_balance(self) -> None:
        """Sender MUST see their own balance_before/balance_after.

        When BANK_A sends payment, BANK_A should see their balance change.
        """
        # Setup: Create event where BANK_A pays BANK_B
        # Build context for BANK_A (sender)
        # Assert: Balance values ARE in formatted output

    def test_rtgs_settlement_balance_fields_hidden_from_receiver(self) -> None:
        """Verify specific balance field values are not leaked.

        Uses unique marker values to detect leakage.
        """
        # Setup: Use unique balance values (e.g., 123456789)
        # Build context for receiver
        # Assert: Marker values NOT in output
```

### Step 1.2: Implement to Pass Tests (GREEN)

Modify `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`:

The `_format_settlement_event()` method needs to check if the viewing agent is the sender before showing balance:

```python
def _format_settlement_event(self, event: BootstrapEvent) -> str:
    """Format settlement event with balance changes.

    CRITICAL: Only shows balance to sender, not receiver.
    This enforces INV-10: Agent Isolation.
    """
    d = event.details
    parts = []

    # Transaction ID
    if "tx_id" in d:
        parts.append(f"tx_id={d['tx_id']}")

    # Amount
    if "amount" in d and isinstance(d["amount"], int):
        parts.append(f"amount=${d['amount'] / 100:.2f}")

    result = ", ".join(parts)

    # CRITICAL FIX: Only show balance to sender, not receiver
    # This enforces INV-10 (Agent Isolation)
    sender = d.get("sender")
    if sender == self._agent_id:  # Only if viewing agent is sender
        balance_before = d.get("sender_balance_before")
        balance_after = d.get("sender_balance_after")
        if balance_before is not None and balance_after is not None:
            before_fmt = f"${balance_before / 100:,.2f}"
            after_fmt = f"${balance_after / 100:,.2f}"
            result += f"\n  Balance: {before_fmt} → {after_fmt}"

    return result
```

### Step 1.3: Refactor

- Ensure type annotations are complete
- Add docstring explaining the security rationale
- Consider extracting balance formatting to a helper

---

## Implementation Details

### Current Code (context_builder.py:346-352)

```python
# Add balance change if available
balance_before = d.get("sender_balance_before")
balance_after = d.get("sender_balance_after")
if balance_before is not None and balance_after is not None:
    before_fmt = f"${balance_before / 100:,.2f}"
    after_fmt = f"${balance_after / 100:,.2f}"
    result += f"\n  Balance: {before_fmt} → {after_fmt}"
```

### Fixed Code

```python
# CRITICAL: Only show balance to sender (INV-10: Agent Isolation)
sender = d.get("sender")
if sender == self._agent_id:
    balance_before = d.get("sender_balance_before")
    balance_after = d.get("sender_balance_after")
    if balance_before is not None and balance_after is not None:
        before_fmt = f"${balance_before / 100:,.2f}"
        after_fmt = f"${balance_after / 100:,.2f}"
        result += f"\n  Balance: {before_fmt} → {after_fmt}"
```

### Edge Cases to Handle

- Event missing sender field → Don't show balance (safe default)
- Event with sender but no balance fields → No change needed
- Self-payment (sender == receiver) → Sender sees balance (correct)

---

## Files

| File | Action |
|------|--------|
| `api/tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py` | MODIFY - Add balance isolation tests |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` | MODIFY - Fix _format_settlement_event |

---

## Verification

```bash
# Run specific tests
cd /home/user/SimCash/api
uv run python -m pytest tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py -v

# Run all isolation tests
uv run python -m pytest tests/ai_cash_mgmt/unit/test_prompt_agent_isolation.py -v -k "balance"

# Type check
uv run python -m mypy payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py

# Lint
uv run python -m ruff check payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py
```

---

## Completion Criteria

- [ ] `test_rtgs_settlement_receiver_cannot_see_sender_balance` passes
- [ ] `test_rtgs_settlement_sender_can_see_own_balance` passes
- [ ] `test_rtgs_settlement_balance_fields_hidden_from_receiver` passes
- [ ] All existing tests still pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] INV-10 (Agent Isolation) verified for balance information
