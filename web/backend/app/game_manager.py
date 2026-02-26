"""GameManager with idle eviction support."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game import Game

logger = logging.getLogger(__name__)


class GameManager:
    """Dict-like manager for Game objects with idle eviction."""

    def __init__(self):
        self._games: dict[str, Game] = {}

    def add(self, game: 'Game') -> None:
        self._games[game.game_id] = game

    def get(self, game_id: str) -> 'Game | None':
        return self._games.get(game_id)

    def remove(self, game_id: str) -> None:
        self._games.pop(game_id, None)

    def __contains__(self, game_id: str) -> bool:
        return game_id in self._games

    def __iter__(self):
        return iter(self._games)

    def items(self):
        return self._games.items()

    def evict_idle(self, max_idle_seconds: int = 3600) -> list[str]:
        """Evict games that have been idle longer than max_idle_seconds.

        Returns list of evicted game IDs.
        """
        # Import here to avoid circular imports
        try:
            from .main import game_auto_tasks
        except ImportError:
            game_auto_tasks = {}

        now = datetime.now(timezone.utc)
        to_evict = []
        for gid, game in self._games.items():
            # Never evict games with active auto-run tasks
            task = game_auto_tasks.get(gid)
            if task and not task.done():
                continue
            try:
                last = datetime.fromisoformat(game.last_activity_at.replace("Z", "+00:00"))
                idle_secs = (now - last).total_seconds()
                if idle_secs > max_idle_seconds:
                    to_evict.append(gid)
            except (ValueError, AttributeError):
                continue

        for gid in to_evict:
            logger.info("Evicting idle game %s", gid)
            del self._games[gid]

        return to_evict
