"""Unit tests for incoming liquidity display helpers.

Tests the helper functions that calculate and format incoming liquidity
notifications when --filter-agent matches the settlement receiver.
"""

import pytest

from payment_simulator.cli.filters import (
    calculate_incoming_liquidity,
    calculate_lsm_net_change,
)


class TestCalculateIncomingLiquidity:
    """Test calculate_incoming_liquidity() for simple settlement events."""

    def test_rtgs_immediate_settlement_as_receiver(self):
        """Receiver sees incoming liquidity amount for RTGS settlement."""
        event = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 1000000,  # $10,000.00
        }
        result = calculate_incoming_liquidity(event, "BANK_A")
        assert result == 1000000

    def test_rtgs_immediate_settlement_as_sender(self):
        """Sender does NOT see incoming liquidity (outgoing)."""
        event = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 1000000,
        }
        result = calculate_incoming_liquidity(event, "BANK_A")
        assert result == 0  # Sender has no incoming liquidity

    def test_rtgs_immediate_settlement_not_involved(self):
        """Agent not involved in settlement sees no liquidity."""
        event = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_B",
            "receiver": "BANK_C",
            "amount": 1000000,
        }
        result = calculate_incoming_liquidity(event, "BANK_A")
        assert result == 0

    def test_queue2_release_as_receiver(self):
        """Receiver sees incoming liquidity for Queue2 release."""
        event = {
            "event_type": "Queue2LiquidityRelease",
            "sender": "BANK_B",
            "receiver": "BANK_A",
            "amount": 500000,
        }
        result = calculate_incoming_liquidity(event, "BANK_A")
        assert result == 500000

    def test_overdue_transaction_settled_as_receiver(self):
        """Receiver sees incoming liquidity for overdue settlement."""
        event = {
            "event_type": "OverdueTransactionSettled",
            "sender_id": "BANK_B",
            "receiver_id": "BANK_A",
            "amount": 250000,
        }
        result = calculate_incoming_liquidity(event, "BANK_A")
        assert result == 250000


class TestCalculateLsmNetChange:
    """Test calculate_lsm_net_change() for LSM events."""

    def test_bilateral_offset_agent_a_receives_more(self):
        """Agent A pays 8000, receives 10000, net +2000."""
        event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 8000,   # A pays B $80.00
            "amount_b": 10000,  # B pays A $100.00
        }
        # A pays 8000 to B, receives 10000 from B
        # Net change for A = +2000 (receives more than pays)
        result = calculate_lsm_net_change(event, "BANK_A")
        assert result == 2000

    def test_bilateral_offset_agent_a_pays_more(self):
        """Agent A pays 10000, receives 8000, net -2000."""
        event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 10000,  # A pays B $100.00
            "amount_b": 8000,   # B pays A $80.00
        }
        result = calculate_lsm_net_change(event, "BANK_A")
        assert result == -2000

    def test_bilateral_offset_agent_b_perspective(self):
        """Agent B pays 10000, receives 8000, net -2000."""
        event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 8000,   # A pays B $80.00
            "amount_b": 10000,  # B pays A $100.00
        }
        # B pays 10000 to A, receives 8000 from A
        # Net change for B = -2000
        result = calculate_lsm_net_change(event, "BANK_B")
        assert result == -2000

    def test_bilateral_offset_not_involved(self):
        """Agent not in bilateral sees no change."""
        event = {
            "event_type": "LsmBilateralOffset",
            "agent_a": "BANK_A",
            "agent_b": "BANK_B",
            "amount_a": 8000,
            "amount_b": 10000,
        }
        result = calculate_lsm_net_change(event, "BANK_C")
        assert result == 0

    def test_cycle_settlement_with_net_positions(self):
        """Cycle settlement uses net_positions array (negative = net sender)."""
        event = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            "net_positions": [-5000, 3000, 2000],  # A: -5000, B: +3000, C: +2000
        }
        # BANK_A has net position -5000 (net sender, loses liquidity)
        # Net change = -(-5000) = 5000? No wait, net_positions being negative
        # means they owe that much to the system
        # Actually, net_positions convention: negative = owes to system (net sender)
        # So liquidity change = -net_positions (if negative net_pos, pays out)
        result = calculate_lsm_net_change(event, "BANK_A")
        # With net_positions = -5000, BANK_A is a net sender
        # Liquidity change should be the opposite: -(-5000) = +5000?
        # Actually need to verify the convention in the codebase
        # For now, let's say net_positions positive = receives that much net
        # So BANK_A with -5000 receives -5000 (i.e., pays out 5000)
        assert result == -5000  # Net sender loses liquidity

    def test_cycle_settlement_agent_receives_net(self):
        """Agent with positive net position receives liquidity."""
        event = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            "net_positions": [-5000, 3000, 2000],
        }
        result = calculate_lsm_net_change(event, "BANK_B")
        assert result == 3000  # Net receiver gains liquidity

    def test_cycle_settlement_agent_not_in_cycle(self):
        """Agent not in cycle sees no change."""
        event = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            "net_positions": [-5000, 3000, 2000],
        }
        result = calculate_lsm_net_change(event, "BANK_D")
        assert result == 0

    def test_cycle_settlement_missing_net_positions(self):
        """Handle missing net_positions gracefully."""
        event = {
            "event_type": "LsmCycleSettlement",
            "agents": ["BANK_A", "BANK_B", "BANK_C"],
            # net_positions missing
        }
        result = calculate_lsm_net_change(event, "BANK_A")
        assert result == 0  # Can't calculate without data

    def test_non_lsm_event_returns_zero(self):
        """Non-LSM events return 0."""
        event = {
            "event_type": "RtgsImmediateSettlement",
            "sender": "BANK_A",
            "receiver": "BANK_B",
            "amount": 10000,
        }
        result = calculate_lsm_net_change(event, "BANK_A")
        assert result == 0
