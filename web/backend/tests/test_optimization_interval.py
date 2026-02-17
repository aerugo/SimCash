"""Tests for configurable optimization interval."""
import copy
import pytest

from app.game import Game, DEFAULT_POLICY


@pytest.fixture
def raw_yaml(simple_scenario):
    return copy.deepcopy(simple_scenario)


class TestShouldOptimize:
    def test_interval_1_every_day(self, raw_yaml):
        game = Game("t1", raw_yaml, optimization_interval=1)
        for d in range(6):
            assert game.should_optimize(d) is True

    def test_interval_3(self, raw_yaml):
        game = Game("t2", raw_yaml, optimization_interval=3)
        # (day+1) % 3 == 0 → days 2, 5, 8
        assert game.should_optimize(0) is False
        assert game.should_optimize(1) is False
        assert game.should_optimize(2) is True
        assert game.should_optimize(3) is False
        assert game.should_optimize(4) is False
        assert game.should_optimize(5) is True

    def test_interval_2(self, raw_yaml):
        game = Game("t3", raw_yaml, optimization_interval=2)
        assert game.should_optimize(0) is False
        assert game.should_optimize(1) is True
        assert game.should_optimize(2) is False
        assert game.should_optimize(3) is True


class TestOptimizationIntervalGameplay:
    def test_interval_1_all_days_run(self, raw_yaml):
        game = Game("t4", raw_yaml, use_llm=True, mock_reasoning=True, max_days=3, optimization_interval=1)
        for _ in range(3):
            day = game.run_day()
        # All days should be runnable
        assert len(game.days) == 3

    def test_interval_stored_in_state(self, raw_yaml):
        game = Game("t5", raw_yaml, optimization_interval=3)
        state = game.get_state()
        assert state["optimization_interval"] == 3

    def test_default_interval_is_1(self, raw_yaml):
        game = Game("t6", raw_yaml)
        assert game.optimization_interval == 1

    def test_policies_unchanged_on_non_optimization_days(self, raw_yaml):
        """Without optimization, policies should stay the same."""
        game = Game("t7", raw_yaml, use_llm=True, mock_reasoning=True, max_days=5, optimization_interval=3)
        
        # Run day 0
        game.run_day()
        policies_after_day0 = copy.deepcopy(game.policies)
        
        # Day 0: should_optimize(0) is False (interval=3, (0+1)%3=1≠0)
        # So no optimization should happen
        assert game.should_optimize(0) is False
        
        # Run day 1 — policies should still be default
        game.run_day()
        assert game.should_optimize(1) is False
        for aid in game.agent_ids:
            assert game.policies[aid]["parameters"]["initial_liquidity_fraction"] == policies_after_day0[aid]["parameters"]["initial_liquidity_fraction"]

    def test_optimized_field_default_false(self, raw_yaml):
        game = Game("t8", raw_yaml, max_days=3)
        day = game.run_day()
        assert day.optimized is False

    def test_optimized_in_to_dict(self, raw_yaml):
        game = Game("t9", raw_yaml, max_days=3)
        day = game.run_day()
        d = day.to_dict()
        assert "optimized" in d
        assert d["optimized"] is False

    def test_min_interval_is_1(self, raw_yaml):
        game = Game("t10", raw_yaml, optimization_interval=0)
        assert game.optimization_interval == 1
