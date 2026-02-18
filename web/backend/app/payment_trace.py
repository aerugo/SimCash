"""Payment lifecycle trace — groups events by tx_id to reconstruct payment journeys."""
from __future__ import annotations

from typing import Any


# Event types that represent settlement
SETTLEMENT_TYPES = {"RtgsImmediateSettlement", "BilateralOffset", "CycleSettlement"}

# Event types that represent failure/penalty
FAILURE_TYPES = {"DeadlineMiss", "EodPenalty"}


def build_payment_traces(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group events by tx_id to build per-payment lifecycle traces.

    Returns a list of payment objects sorted by arrival tick, each containing:
      - tx_id, sender, receiver, amount, arrival_tick, deadline_tick
      - status: "settled" | "delayed" | "failed"
      - settled_tick: tick when settled (or None)
      - settlement_type: e.g. "RtgsImmediateSettlement"
      - lifecycle: list of {tick, event_type, details} dicts
    """
    # First pass: group events by tx_id
    payments: dict[str, dict[str, Any]] = {}

    for event in events:
        tx_id = event.get("tx_id")
        if not tx_id:
            continue

        if tx_id not in payments:
            payments[tx_id] = {
                "tx_id": tx_id,
                "sender": None,
                "receiver": None,
                "amount": None,
                "arrival_tick": None,
                "deadline_tick": None,
                "settled_tick": None,
                "settlement_type": None,
                "status": "pending",
                "lifecycle": [],
            }

        p = payments[tx_id]
        event_type = event.get("event_type", "")
        tick = event.get("tick", 0)

        # Extract payment metadata from Arrival events
        if event_type == "Arrival":
            p["sender"] = event.get("sender_id")
            p["receiver"] = event.get("receiver_id")
            p["amount"] = event.get("amount")
            p["arrival_tick"] = tick
            p["deadline_tick"] = event.get("deadline")

        # Track settlement
        if event_type in SETTLEMENT_TYPES:
            p["settled_tick"] = tick
            p["settlement_type"] = event_type
            p["status"] = "settled"
            # Fill sender/receiver from settlement if not set
            if not p["sender"]:
                p["sender"] = event.get("sender")
            if not p["receiver"]:
                p["receiver"] = event.get("receiver")
            if p["amount"] is None:
                p["amount"] = event.get("amount")

        # Build lifecycle entry (omit redundant fields)
        details: dict[str, Any] = {}
        for k, v in event.items():
            if k not in ("event_type", "tick", "tx_id"):
                details[k] = v

        p["lifecycle"].append({
            "tick": tick,
            "event_type": event_type,
            "details": details,
        })

    # Determine final status for non-settled payments
    for p in payments.values():
        if p["status"] != "settled":
            # Check if there was a deadline and if it was missed
            has_failure = any(
                e["event_type"] in FAILURE_TYPES for e in p["lifecycle"]
            )
            if has_failure:
                p["status"] = "failed"
            elif p["arrival_tick"] is not None and p["deadline_tick"] is not None:
                p["status"] = "failed"  # never settled
            else:
                p["status"] = "failed"

        # Check for delayed settlement (settled after deadline)
        if (p["status"] == "settled" and p["deadline_tick"] is not None
                and p["settled_tick"] is not None
                and p["settled_tick"] > p["deadline_tick"]):
            p["status"] = "delayed"

    # Sort lifecycle events by tick, then sort payments by arrival_tick
    for p in payments.values():
        p["lifecycle"].sort(key=lambda e: e["tick"])

    result = sorted(payments.values(), key=lambda p: (p["arrival_tick"] or 0, p["tx_id"]))

    # Add index
    for i, p in enumerate(result):
        p["index"] = i

    return result
