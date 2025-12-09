"""Unit tests for GameMode - game mode enumeration and utilities.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

import pytest


class TestGameModeEnum:
    """Test GameMode enumeration."""

    def test_game_mode_has_rl_optimization(self) -> None:
        """GameMode should have RL_OPTIMIZATION mode."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert hasattr(GameMode, "RL_OPTIMIZATION")
        assert GameMode.RL_OPTIMIZATION.value == "rl_optimization"

    def test_game_mode_has_campaign_learning(self) -> None:
        """GameMode should have CAMPAIGN_LEARNING mode."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert hasattr(GameMode, "CAMPAIGN_LEARNING")
        assert GameMode.CAMPAIGN_LEARNING.value == "campaign_learning"

    def test_game_mode_from_string(self) -> None:
        """GameMode should be creatable from string."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert GameMode("rl_optimization") == GameMode.RL_OPTIMIZATION
        assert GameMode("campaign_learning") == GameMode.CAMPAIGN_LEARNING

    def test_game_mode_invalid_string_raises(self) -> None:
        """GameMode should raise ValueError for invalid string."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        with pytest.raises(ValueError):
            GameMode("invalid_mode")


class TestGameModeDescriptions:
    """Test GameMode descriptions and properties."""

    def test_rl_optimization_is_intra_simulation(self) -> None:
        """RL_OPTIMIZATION should be marked as intra-simulation."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert GameMode.RL_OPTIMIZATION.is_intra_simulation is True

    def test_campaign_learning_is_not_intra_simulation(self) -> None:
        """CAMPAIGN_LEARNING should NOT be marked as intra-simulation."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert GameMode.CAMPAIGN_LEARNING.is_intra_simulation is False

    def test_game_modes_have_descriptions(self) -> None:
        """Each GameMode should have a description."""
        from payment_simulator.ai_cash_mgmt.core.game_mode import GameMode

        assert len(GameMode.RL_OPTIMIZATION.description) > 0
        assert len(GameMode.CAMPAIGN_LEARNING.description) > 0
