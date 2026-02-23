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
        con.execute("""
            CREATE TABLE IF NOT EXISTS optimization_prompts (
                day_num INTEGER,
                agent_id TEXT,
                block_id TEXT,
                block_name TEXT,
                category TEXT,
                source TEXT,
                content TEXT,
                token_estimate INTEGER,
                enabled BOOLEAN,
                options TEXT,
                PRIMARY KEY (day_num, agent_id, block_id)
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

    # ---- Checkpoint persistence ----

    def _local_checkpoint_path(self, uid: str, game_id: str) -> Path:
        return self._local_dir(uid) / f"{game_id}.json"

    def _gcs_checkpoint_key(self, uid: str, game_id: str) -> str:
        return f"users/{uid}/games/{game_id}.json"

    def save_checkpoint(self, uid: str, game_id: str, data: dict):
        """Save game checkpoint JSON locally (+ GCS if configured)."""
        p = self._local_checkpoint_path(uid, game_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, default=str))
        if self.storage_mode == "gcs" and self._gcs_bucket:
            try:
                blob = self._gcs_bucket.blob(self._gcs_checkpoint_key(uid, game_id))
                blob.upload_from_string(json.dumps(data, default=str), content_type="application/json")
            except Exception as e:
                logger.warning("GCS checkpoint upload failed for %s: %s", game_id, e)

    def load_checkpoint(self, uid: str, game_id: str) -> dict | None:
        """Load game checkpoint. Tries local first, then GCS."""
        p = self._local_checkpoint_path(uid, game_id)
        if p.exists():
            try:
                return json.loads(p.read_text())
            except (json.JSONDecodeError, ValueError):
                return None
        if self.storage_mode == "gcs" and self._gcs_bucket:
            blob = self._gcs_bucket.blob(self._gcs_checkpoint_key(uid, game_id))
            if blob.exists():
                try:
                    text = blob.download_as_text()
                    data = json.loads(text)
                    # Cache locally
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(text)
                    return data
                except Exception as e:
                    logger.warning("GCS checkpoint load failed for %s: %s", game_id, e)
        return None

    def delete_checkpoint(self, uid: str, game_id: str):
        """Delete checkpoint from local and GCS."""
        p = self._local_checkpoint_path(uid, game_id)
        if p.exists():
            p.unlink()
        if self.storage_mode == "gcs" and self._gcs_bucket:
            blob = self._gcs_bucket.blob(self._gcs_checkpoint_key(uid, game_id))
            try:
                if blob.exists():
                    blob.delete()
            except Exception:
                pass

    def _parse_checkpoint_summary(self, data: dict, fallback_id: str = "") -> dict:
        """Extract summary fields from a checkpoint dict."""
        return {
            "game_id": data.get("game_id", fallback_id),
            "scenario_id": data.get("scenario_id", ""),
            "scenario_name": data.get("scenario_name", ""),
            "optimization_model": data.get("optimization_model", ""),
            "status": data.get("status", "unknown"),
            "current_day": data.get("progress", {}).get("current_day", 0),
            "max_days": data.get("config", {}).get("max_days", 0),
            "use_llm": data.get("config", {}).get("use_llm", False),
            "simulated_ai": data.get("config", {}).get("simulated_ai", True),
            "agent_count": len(data.get("progress", {}).get("agent_ids", [])),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "last_activity_at": data.get("last_activity_at", data.get("updated_at", "")),
        }

    def list_checkpoints(self, uid: str) -> list[dict]:
        """List all checkpoints for a user (summary only: id, status, progress).

        Uses the lightweight index file first (fast). Falls back to scanning
        individual checkpoint files only if the index is empty/missing.
        """
        # Fast path: use the index (small JSON with summaries only)
        index_entries = self._read_index(uid)
        if index_entries:
            # Check if index uses old field names (needs migration)
            sample = index_entries[0]
            if "current_day" not in sample and ("days_completed" in sample or "num_agents" in sample):
                logger.info("Index for user %s uses old field names, forcing rebuild", uid)
            else:
                return index_entries

        # Slow fallback: scan individual checkpoint files (for legacy data)
        logger.info("No index for user %s, falling back to checkpoint scan", uid)
        results = []
        seen_ids: set[str] = set()

        # Local filesystem
        d = self._local_dir(uid)
        if d.exists():
            for p in sorted(d.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.name == "index.json":
                    continue
                try:
                    data = json.loads(p.read_text())
                    summary = self._parse_checkpoint_summary(data, p.stem)
                    results.append(summary)
                    seen_ids.add(summary["game_id"])
                except (json.JSONDecodeError, ValueError):
                    continue

        # GCS fallback — list blobs not already found locally
        if self.storage_mode == "gcs" and self._gcs_bucket:
            prefix = f"users/{uid}/games/"
            try:
                for blob in self._gcs_bucket.list_blobs(prefix=prefix):
                    if not blob.name.endswith(".json") or blob.name.endswith("index.json"):
                        continue
                    game_id = blob.name.rsplit("/", 1)[-1].replace(".json", "")
                    if game_id in seen_ids:
                        continue
                    try:
                        data = json.loads(blob.download_as_text())
                        results.append(self._parse_checkpoint_summary(data, game_id))
                    except Exception:
                        continue
            except Exception as e:
                logger.warning("GCS list_checkpoints failed for %s: %s", uid, e)

        # Rebuild index from scan results so next call is fast
        if results:
            self._write_index(uid, results)

        return results
