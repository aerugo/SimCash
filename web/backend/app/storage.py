"""Game storage layer — local filesystem or GCS."""
from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class GameStorage:
    """Persist game DuckDB files and JSON indexes, locally or on GCS."""

    def __init__(self, bucket_name: str = "", storage_mode: str = "local"):
        self.storage_mode = storage_mode
        self.bucket_name = bucket_name
        self._gcs_client = None
        self._gcs_bucket = None

        if storage_mode == "gcs":
            from google.cloud import storage as gcs_storage
            self._gcs_client = gcs_storage.Client()
            self._gcs_bucket = self._gcs_client.bucket(bucket_name)

    # ---- paths ----

    def _local_dir(self, uid: str) -> Path:
        d = DATA_DIR / uid / "games"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _local_db_path(self, uid: str, game_id: str) -> Path:
        return self._local_dir(uid) / f"{game_id}.duckdb"

    def _index_path(self, uid: str) -> Path:
        return self._local_dir(uid) / "index.json"

    def _gcs_db_key(self, uid: str, game_id: str) -> str:
        return f"users/{uid}/games/{game_id}.duckdb"

    def _gcs_index_key(self, uid: str) -> str:
        return f"users/{uid}/games/index.json"

    # ---- DuckDB lifecycle ----

    def create_game_db(self, uid: str, game_id: str) -> Path:
        """Create a fresh DuckDB file. Returns local path."""
        import duckdb
        p = self._local_db_path(uid, game_id)
        # Create with schema
        con = duckdb.connect(str(p))
        con.execute("""
            CREATE TABLE IF NOT EXISTS days (
                day INTEGER PRIMARY KEY,
                seed INTEGER,
                total_cost BIGINT,
                policies JSON,
                costs JSON,
                per_agent_costs JSON,
                balance_history JSON,
                events JSON,
                created_at TIMESTAMP DEFAULT current_timestamp
            )
        """)
        con.close()
        return p

    def save_game(self, uid: str, game_id: str):
        """Upload local DuckDB to GCS (no-op for local mode)."""
        if self.storage_mode != "gcs":
            return
        local = self._local_db_path(uid, game_id)
        if not local.exists():
            return
        blob = self._gcs_bucket.blob(self._gcs_db_key(uid, game_id))
        blob.upload_from_filename(str(local))
        logger.info("Uploaded %s to GCS", local)

    def load_game(self, uid: str, game_id: str) -> Path | None:
        """Get local path to DuckDB, downloading from GCS if needed."""
        local = self._local_db_path(uid, game_id)
        if local.exists():
            return local
        if self.storage_mode == "gcs":
            blob = self._gcs_bucket.blob(self._gcs_db_key(uid, game_id))
            if blob.exists():
                local.parent.mkdir(parents=True, exist_ok=True)
                blob.download_to_filename(str(local))
                return local
        return None

    def delete_game(self, uid: str, game_id: str):
        """Delete DuckDB from local and GCS."""
        local = self._local_db_path(uid, game_id)
        if local.exists():
            local.unlink()
        # Also remove WAL/tmp files
        for suffix in [".duckdb.wal", ".duckdb.tmp"]:
            p = local.parent / f"{game_id}{suffix}"
            if p.exists():
                p.unlink()
        if self.storage_mode == "gcs":
            blob = self._gcs_bucket.blob(self._gcs_db_key(uid, game_id))
            if blob.exists():
                blob.delete()

    def get_db_path(self, uid: str, game_id: str) -> Path:
        """Return local path for a game's DuckDB (may not exist yet)."""
        return self._local_db_path(uid, game_id)

    # ---- JSON index ----

    def _read_index(self, uid: str) -> list[dict]:
        p = self._index_path(uid)
        if self.storage_mode == "gcs" and not p.exists():
            blob = self._gcs_bucket.blob(self._gcs_index_key(uid))
            if blob.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(blob.download_as_text())
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, ValueError):
                return []
        return []

    def _write_index(self, uid: str, entries: list[dict]):
        p = self._index_path(uid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(entries, indent=2))
        if self.storage_mode == "gcs":
            blob = self._gcs_bucket.blob(self._gcs_index_key(uid))
            blob.upload_from_string(json.dumps(entries, indent=2), content_type="application/json")

    def list_games(self, uid: str) -> list[dict]:
        return self._read_index(uid)

    def update_index(self, uid: str, game_meta: dict):
        entries = self._read_index(uid)
        game_id = game_meta["game_id"]
        for i, e in enumerate(entries):
            if e["game_id"] == game_id:
                entries[i] = game_meta
                self._write_index(uid, entries)
                return
        entries.append(game_meta)
        self._write_index(uid, entries)

    def remove_from_index(self, uid: str, game_id: str):
        entries = self._read_index(uid)
        entries = [e for e in entries if e["game_id"] != game_id]
        self._write_index(uid, entries)
