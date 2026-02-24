"""Game serialization: checkpoints, DuckDB persistence, state export."""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from .game import Game, GameDay

logger = logging.getLogger(__name__)


def save_day_to_duckdb(db_path: Path, day: 'GameDay') -> None:
    """Write a day's results to the DuckDB file."""
    con = duckdb.connect(str(db_path))
    con.execute(
        """INSERT OR REPLACE INTO days (day, seed, total_cost, policies, costs, per_agent_costs, balance_history, events)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            day.day_num,
            day.seed,
            day.total_cost,
            json.dumps({aid: p for aid, p in day.policies.items()}),
            json.dumps(day.costs),
            json.dumps(day.per_agent_costs),
            json.dumps(day.balance_history),
            json.dumps(day.events[:200]),
        ],
    )
    con.close()


def day_to_checkpoint(day: 'GameDay') -> dict[str, Any]:
    """Serialize a GameDay for checkpoint (excludes tick_events for size)."""
    return {
        "day_num": day.day_num,
        "seed": day.seed,
        "policies": copy.deepcopy(day.policies),
        "costs": day.costs,
        "events_summary": {
            "total": len(day.events) or (day._total_arrivals + day._total_settled),
            "types": {},
        },
        "settlement_stats": {
            "event_summary": day._event_summary,
            "total_arrivals": day._total_arrivals,
            "total_settled": day._total_settled,
        },
        "balance_history": day.balance_history,
        "total_cost": day.total_cost,
        "per_agent_costs": day.per_agent_costs,
        "per_agent_cost_std": day.per_agent_cost_std,
        "optimized": day.optimized,
        "optimization_failed": day.optimization_failed,
        "optimization_prompts": day.optimization_prompts,
        "rejected_policies": day.rejected_policies,
    }


def game_to_checkpoint(game: 'Game', scenario_id: str = "", uid: str = "") -> dict[str, Any]:
    """Serialize full game state to a checkpoint dict."""
    if game.stalled:
        status = "stalled"
    elif game.is_complete:
        status = "complete"
    else:
        status = "running" if game.days else "created"
    return {
        "version": 1,
        "game_id": game.game_id,
        "uid": uid,
        "scenario_id": scenario_id,
        "created_at": getattr(game, '_created_at', datetime.now(timezone.utc).isoformat()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_activity_at": getattr(game, 'last_activity_at', datetime.now(timezone.utc).isoformat()),
        "status": status,
        "scenario_name": getattr(game, '_scenario_name', ''),
        "optimization_model": getattr(game, '_optimization_model', ''),
        "config": {
            "raw_yaml": game.raw_yaml,
            "use_llm": game.use_llm,
            "simulated_ai": game.simulated_ai,
            "total_days": game.total_days,
            "rounds": game.max_rounds,
            "num_eval_samples": game.num_eval_samples,
            "optimization_interval": game.optimization_interval,
            "constraint_preset": game.constraint_preset,
            "optimization_schedule": game.optimization_schedule,
            "base_seed": game._base_seed,
            "prompt_profile": game.prompt_profile,
        },
        "quality": game.quality,
        "stalled": game.stalled,
        "stall_reason": game.stall_reason,
        "progress": {
            "current_day": game.current_day,
            "agent_ids": game.agent_ids,
            "policies": copy.deepcopy(game.policies),
            "reasoning_history": copy.deepcopy(game.reasoning_history),
            "days": [day_to_checkpoint(d) for d in game.days],
        },
    }


def game_from_checkpoint(data: dict) -> 'Game':
    """Reconstruct a Game from a checkpoint dict."""
    from .game import Game, GameDay

    config = data["config"]
    progress = data["progress"]

    game = Game(
        game_id=data["game_id"],
        raw_yaml=config["raw_yaml"],
        use_llm=config.get("use_llm", True),
        simulated_ai=config.get("simulated_ai", False),
        total_days=config.get("total_days", config.get("max_days", 1)),
        num_eval_samples=config.get("num_eval_samples", 1),
        optimization_interval=config.get("optimization_interval", 1),
        constraint_preset=config.get("constraint_preset", "simple"),
        include_groups=config.get("include_groups"),
        exclude_groups=config.get("exclude_groups"),
        optimization_schedule=config.get("optimization_schedule", "every_scenario_day"),
        prompt_profile=config.get("prompt_profile"),
    )
    game._base_seed = config.get("base_seed", 42)
    game.sim.base_seed = game._base_seed
    game.bootstrap_gate.base_seed = game._base_seed
    game.stalled = data.get("stalled", False)
    game.stall_reason = data.get("stall_reason", "")
    game._created_at = data.get("created_at", "")
    game.last_activity_at = data.get("last_activity_at", data.get("updated_at", ""))
    game._scenario_id = data.get("scenario_id", "")
    game._scenario_name = data.get("scenario_name", "")
    from .settings import DEFAULT_MODEL
    game._optimization_model = data.get("optimization_model", "") or DEFAULT_MODEL
    game._uid = data.get("uid", "")

    # Restore policies (update shared references)
    game.policies = copy.deepcopy(progress.get("policies", game.policies))
    game.sim.policies = game.policies
    game.bootstrap_gate.policies = game.policies

    # Restore reasoning history
    game.reasoning_history = copy.deepcopy(progress.get("reasoning_history", game.reasoning_history))

    # Restore days
    for day_data in progress.get("days", []):
        day = GameDay(
            day_num=day_data["day_num"],
            seed=day_data["seed"],
            policies=copy.deepcopy(day_data.get("policies", {})),
            costs=day_data.get("costs", {}),
            events=[],
            balance_history=day_data.get("balance_history", {}),
            total_cost=day_data.get("total_cost", 0),
            per_agent_costs=day_data.get("per_agent_costs", {}),
            tick_events=[],
            optimized=day_data.get("optimized", False),
            event_summary=day_data.get("settlement_stats", {}).get("event_summary"),
            total_arrivals=day_data.get("settlement_stats", {}).get("total_arrivals"),
            total_settled=day_data.get("settlement_stats", {}).get("total_settled"),
            per_agent_cost_std=day_data.get("per_agent_cost_std", {}),
        )
        day.optimization_failed = day_data.get("optimization_failed", False)
        day.optimization_prompts = day_data.get("optimization_prompts", {})
        day.rejected_policies = day_data.get("rejected_policies", {})
        game.days.append(day)

    return game


def get_game_state(game: 'Game') -> dict[str, Any]:
    """Build the full game state dict for API responses."""
    return {
        "game_id": game.game_id,
        "current_round": game.current_round,
        "rounds": game.max_rounds,
        "current_day": game.current_day,
        "total_days": game.total_days,
        "is_complete": game.is_complete,
        "use_llm": game.use_llm,
        "num_eval_samples": game.num_eval_samples,
        "optimization_interval": game.optimization_interval,
        "constraint_preset": game.constraint_preset,
        "include_groups": game.include_groups,
        "exclude_groups": game.exclude_groups,
        "optimization_schedule": game.optimization_schedule,
        "scenario_num_days": game._scenario_num_days,
        "agent_ids": game.agent_ids,
        "current_policies": {
            aid: p for aid, p in game.policies.items()
        },
        "days": [d.to_summary_dict() for d in game.days],
        "cost_history": {
            aid: [d.per_agent_costs.get(aid, 0) for d in game.days]
            for aid in game.agent_ids
        },
        "fraction_history": {
            aid: [
                d.policies.get(aid, {}).get("parameters", {}).get("initial_liquidity_fraction", 1.0)
                for d in game.days
            ]
            for aid in game.agent_ids
        },
        "reasoning_history": game.reasoning_history,
        "scenario_name": getattr(game, '_scenario_name', ''),
        "optimization_model": getattr(game, '_optimization_model', ''),
        "optimization_summary": game.optimization_summary,
        "quality": game.quality,
        "stalled": game.stalled,
        "stall_reason": game.stall_reason,
    }
