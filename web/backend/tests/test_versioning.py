"""Tests for version tracking and prompt manifest in checkpoints."""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ["SIMCASH_AUTH_DISABLED"] = "true"
os.environ["SIMCASH_STORAGE_MODE"] = "local"


class TestVersionInfo:
    def test_version_file_exists(self):
        from app.version import VERSION, GIT_HASH, VERSION_FULL
        assert VERSION == "0.2.0"
        assert len(GIT_HASH) == 8 or GIT_HASH == "unknown"
        assert VERSION in VERSION_FULL

    def test_version_info_dict(self):
        from app.version import version_info
        info = version_info()
        assert "version" in info
        assert "git_hash" in info
        assert "version_full" in info
        assert "git_dirty" in info


class TestCheckpointVersioning:
    def test_checkpoint_includes_version(self):
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="ver-test", raw_yaml=scenario, total_days=2)
        day = game.simulate_day()
        game.commit_day(day)

        cp = game.to_checkpoint()
        assert cp["version"] == 2
        assert "simcash_version" in cp
        assert cp["simcash_version"]["version"] == "0.2.0"
        assert "git_hash" in cp["simcash_version"]

    def test_checkpoint_includes_prompt_manifest(self):
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="pm-test", raw_yaml=scenario, total_days=2,
                     constraint_preset="simple")
        day = game.simulate_day()
        game.commit_day(day)

        cp = game.to_checkpoint()
        pm = cp["prompt_manifest"]
        assert pm["constraint_preset"] == "simple"
        assert "optimization_schedule" in pm
        assert "prompt_profile" in pm

    def test_prompt_manifest_captures_blocks_after_optimization(self):
        """When optimization has run, the manifest includes block details."""
        from app.game import Game, GameDay
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="blocks-test", raw_yaml=scenario, total_days=2)
        day = game.simulate_day()
        game.commit_day(day)

        # Simulate optimization having stored prompt data
        game.days[0].optimization_prompts["BANK_A"] = {
            "blocks": [
                {"id": "sys_role", "name": "Role", "category": "system",
                 "source": "static", "enabled": True, "options": {},
                 "token_estimate": 100},
                {"id": "usr_history", "name": "History", "category": "user",
                 "source": "dynamic", "enabled": False, "options": {"last_n": 5},
                 "token_estimate": 500},
            ],
            "profile_hash": "abc123",
            "total_tokens": 600,
        }

        cp = game.to_checkpoint()
        pm = cp["prompt_manifest"]
        assert "blocks" in pm
        assert len(pm["blocks"]) == 2
        assert pm["blocks"][0]["id"] == "sys_role"
        assert pm["blocks"][0]["enabled"] is True
        assert pm["blocks"][1]["id"] == "usr_history"
        assert pm["blocks"][1]["enabled"] is False
        assert pm["blocks"][1]["options"] == {"last_n": 5}
        assert pm["profile_hash"] == "abc123"

    def test_old_checkpoint_without_version_loads(self):
        """Backward compat: old checkpoints without simcash_version load fine."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="old", raw_yaml=scenario, total_days=2)
        day = game.simulate_day()
        game.commit_day(day)

        cp = game.to_checkpoint()
        # Simulate old checkpoint format
        del cp["simcash_version"]
        del cp["prompt_manifest"]
        cp["version"] = 1

        restored = Game.from_checkpoint(cp)
        assert len(restored.days) == 1


class TestGameStateAPI:
    def test_get_state_includes_version(self):
        from app.game import Game
        from app.serialization import get_game_state
        from app.scenario_pack import get_scenario_by_id

        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="api-test", raw_yaml=scenario, total_days=2)

        state = get_game_state(game)
        assert "simcash_version" in state
        assert state["simcash_version"]["version"] == "0.2.0"
        assert "prompt_manifest" in state
