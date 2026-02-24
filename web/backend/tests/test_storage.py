"""Tests for storage layer and DuckDB persistence."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from app.storage import GameStorage, DATA_DIR
from app.game import Game, GameDay


@pytest.fixture(autouse=True)
def clean_test_data():
    """Clean up test data after each test."""
    yield
    test_dir = DATA_DIR / "test-uid"
    if test_dir.exists():
        shutil.rmtree(test_dir)


@pytest.fixture
def storage():
    return GameStorage(storage_mode="local")


class TestGameStorage:
    def test_create_game_db(self, storage):
        p = storage.create_game_db("test-uid", "g1")
        assert p.exists()
        con = duckdb.connect(str(p))
        tables = con.execute("SHOW TABLES").fetchall()
        assert any("days" in t[0] for t in tables)
        con.close()

    def test_load_game_local(self, storage):
        storage.create_game_db("test-uid", "g1")
        p = storage.load_game("test-uid", "g1")
        assert p is not None and p.exists()

    def test_load_game_missing(self, storage):
        assert storage.load_game("test-uid", "nonexistent") is None

    def test_delete_game(self, storage):
        storage.create_game_db("test-uid", "g1")
        storage.delete_game("test-uid", "g1")
        assert not storage._local_db_path("test-uid", "g1").exists()

    def test_save_game_local_noop(self, storage):
        storage.create_game_db("test-uid", "g1")
        storage.save_game("test-uid", "g1")  # should not raise


class TestIndex:
    def test_update_and_list(self, storage):
        storage.update_index("test-uid", {"game_id": "g1", "status": "created"})
        games = storage.list_games("test-uid")
        assert len(games) == 1
        assert games[0]["game_id"] == "g1"

    def test_update_existing(self, storage):
        storage.update_index("test-uid", {"game_id": "g1", "status": "created"})
        storage.update_index("test-uid", {"game_id": "g1", "status": "in_progress"})
        games = storage.list_games("test-uid")
        assert len(games) == 1
        assert games[0]["status"] == "in_progress"

    def test_remove_from_index(self, storage):
        storage.update_index("test-uid", {"game_id": "g1", "status": "created"})
        storage.update_index("test-uid", {"game_id": "g2", "status": "created"})
        storage.remove_from_index("test-uid", "g1")
        games = storage.list_games("test-uid")
        assert len(games) == 1
        assert games[0]["game_id"] == "g2"

    def test_list_empty(self, storage):
        assert storage.list_games("test-uid") == []


class TestDuckDBPersistence:
    def test_save_day(self, storage, simple_scenario):
        game = Game(game_id="g1", raw_yaml=simple_scenario, total_days=5)
        db_path = storage.create_game_db("test-uid", "g1")
        day = game.run_day()
        game.save_day_to_duckdb(db_path, day)

        con = duckdb.connect(str(db_path))
        rows = con.execute("SELECT * FROM days").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 0  # day_num
        con.close()

    def test_save_multiple_days(self, storage, simple_scenario):
        game = Game(game_id="g1", raw_yaml=simple_scenario, total_days=5)
        db_path = storage.create_game_db("test-uid", "g1")

        for _ in range(3):
            day = game.run_day()
            game.save_day_to_duckdb(db_path, day)

        con = duckdb.connect(str(db_path))
        count = con.execute("SELECT count(*) FROM days").fetchone()[0]
        assert count == 3
        con.close()


class TestGameLifecycle:
    def test_create_step_delete(self, storage, simple_scenario):
        uid = "test-uid"
        game_id = "lifecycle-1"

        # Create
        game = Game(game_id=game_id, raw_yaml=simple_scenario, total_days=3)
        db_path = storage.create_game_db(uid, game_id)
        storage.update_index(uid, {"game_id": game_id, "status": "created", "days_completed": 0})

        # Step
        day = game.run_day()
        game.save_day_to_duckdb(db_path, day)
        storage.update_index(uid, {"game_id": game_id, "status": "in_progress", "days_completed": 1})

        # Verify persisted
        games = storage.list_games(uid)
        assert len(games) == 1
        assert games[0]["days_completed"] == 1

        # Delete
        storage.delete_game(uid, game_id)
        storage.remove_from_index(uid, game_id)
        assert storage.list_games(uid) == []
        assert storage.load_game(uid, game_id) is None
