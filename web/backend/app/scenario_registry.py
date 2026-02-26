"""Global scenario registry — maps scenario_id → {uid, name, description}.

Mirrors the experiment registry pattern in storage.py.
Stored as `scenarios/registry.json` in GCS (or local disk fallback).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from . import config

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

_gcs_bucket = None
_gcs_checked = False


def _get_gcs_bucket():
    global _gcs_bucket, _gcs_checked
    if _gcs_checked:
        return _gcs_bucket
    _gcs_checked = True
    bucket_name = getattr(config, "GCS_BUCKET", None)
    if not bucket_name:
        return None
    try:
        from google.cloud import storage as gcs_storage
        client = gcs_storage.Client()
        _gcs_bucket = client.bucket(bucket_name)
        return _gcs_bucket
    except Exception:
        logger.debug("GCS unavailable for scenario registry")
        return None


def _registry_path() -> Path:
    d = DATA_DIR / "scenarios"
    d.mkdir(parents=True, exist_ok=True)
    return d / "registry.json"


GCS_KEY = "scenarios/registry.json"


def read_registry() -> dict[str, dict]:
    """Read global scenario registry. Returns {scenario_id: metadata}."""
    p = _registry_path()
    bucket = _get_gcs_bucket()
    if bucket and not p.exists():
        blob = bucket.blob(GCS_KEY)
        if blob.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(blob.download_as_text())
    if p.exists():
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _write_registry(registry: dict[str, dict]):
    p = _registry_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(registry, indent=2))
    bucket = _get_gcs_bucket()
    if bucket:
        try:
            blob = bucket.blob(GCS_KEY)
            blob.upload_from_string(json.dumps(registry, indent=2), content_type="application/json")
        except Exception:
            logger.warning("Failed to write scenario registry to GCS")


def register_scenario(scenario_id: str, uid: str, metadata: dict[str, Any]):
    """Register a custom scenario in the global index."""
    registry = read_registry()
    registry[scenario_id] = {"uid": uid, **metadata}
    _write_registry(registry)


def unregister_scenario(scenario_id: str):
    """Remove a scenario from the global registry."""
    registry = read_registry()
    if scenario_id in registry:
        del registry[scenario_id]
        _write_registry(registry)


def lookup_scenario(scenario_id: str) -> dict[str, Any] | None:
    """Look up a scenario by ID from the global registry. Returns metadata or None."""
    registry = read_registry()
    return registry.get(scenario_id)


def lookup_scenario_owner(scenario_id: str) -> str | None:
    """Look up the owner UID for a scenario_id."""
    entry = lookup_scenario(scenario_id)
    return entry.get("uid") if entry else None


def backfill_from_firestore() -> int:
    """Scan all Firestore custom_scenarios and register any missing ones.

    Returns the number of newly registered scenarios.
    """
    try:
        from .user_content import _get_fs_db
    except ImportError:
        return 0

    db = _get_fs_db()
    if db is None:
        return 0

    registry = read_registry()
    added = 0

    try:
        # Iterate all user documents
        for user_doc in db.collection("users").stream():
            uid = user_doc.id
            scenarios_col = db.collection("users").document(uid).collection("custom_scenarios")
            for sc_doc in scenarios_col.stream():
                sc_id = sc_doc.id
                if sc_id not in registry:
                    data = sc_doc.to_dict()
                    registry[sc_id] = {
                        "uid": uid,
                        "name": data.get("name", ""),
                        "description": data.get("description", ""),
                    }
                    added += 1
    except Exception:
        logger.warning("Failed to backfill scenario registry from Firestore")

    if added > 0:
        _write_registry(registry)
        logger.info("Backfilled %d scenarios into global registry", added)

    return added
