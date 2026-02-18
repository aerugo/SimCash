"""Game data export (CSV / JSON) for researcher download."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from .auth import get_current_user

router = APIRouter()


def _game_to_csv_rows(game: Any) -> list[dict[str, Any]]:
    """Flatten game state into one row per (day, agent)."""
    rows: list[dict[str, Any]] = []
    for day in game.days:
        for aid in game.agent_ids:
            costs = day.costs.get(aid, {})
            policy = day.policies.get(aid, {})
            fraction = policy.get("parameters", {}).get("initial_liquidity_fraction", 1.0)

            # Count payment outcomes from events
            settled = delayed = failed = 0
            for e in day.events:
                etype = e.get("event_type", "")
                agent_match = (
                    e.get("sender_id") == aid
                    or e.get("agent_id") == aid
                )
                if not agent_match:
                    continue
                if etype in ("RtgsImmediateSettlement", "CycleSettlement", "BilateralOffset"):
                    settled += 1
                elif etype == "QueuedRtgs":
                    delayed += 1
                elif etype == "DeadlineMiss":
                    failed += 1

            total_payments = settled + delayed + failed
            settlement_rate = (settled / total_payments) if total_payments > 0 else 1.0

            rows.append({
                "day": day.day_num + 1,
                "agent": aid,
                "total_cost": costs.get("total", 0),
                "liquidity_cost": costs.get("liquidity_cost", 0),
                "delay_cost": costs.get("delay_cost", 0),
                "deadline_penalties": costs.get("penalty_cost", 0),
                "settlement_rate": round(settlement_rate, 4),
                "initial_liquidity_fraction": round(fraction, 4),
                "payments_settled": settled,
                "payments_delayed": delayed,
                "payments_failed": failed,
            })
    return rows


def _game_to_json_export(game: Any) -> dict[str, Any]:
    """Full game state dump for JSON export."""
    return game.get_state()


CSV_COLUMNS = [
    "day", "agent", "total_cost", "liquidity_cost", "delay_cost",
    "deadline_penalties", "settlement_rate", "initial_liquidity_fraction",
    "payments_settled", "payments_delayed", "payments_failed",
]


@router.get("/api/games/{game_id}/export")
def export_game(
    game_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    uid: str = Depends(get_current_user),
):
    """Export game results as CSV or JSON for researcher analysis."""
    from .main import game_manager

    game = game_manager.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    if len(game.days) == 0:
        raise HTTPException(status_code=400, detail="No days to export")

    if format == "csv":
        rows = _game_to_csv_rows(game)
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=game_{game_id}.csv"},
        )
    else:
        data = _game_to_json_export(game)
        content = json.dumps(data, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=game_{game_id}.json"},
        )
