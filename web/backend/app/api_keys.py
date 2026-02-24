"""API Key storage for programmatic access."""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from . import config

logger = logging.getLogger(__name__)

_fs_db = None


def _get_fs_db():
    global _fs_db
    if _fs_db is not None:
        return _fs_db
    try:
        from .auth import _get_firebase_app
        _get_firebase_app()
        from firebase_admin import firestore  # type: ignore[import-untyped]
        db_id = config.FIRESTORE_DATABASE
        _fs_db = firestore.client(database_id=db_id)
        return _fs_db
    except Exception:
        return None


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


class ApiKeyStore:
    """Manage API keys in Firestore with in-memory fallback."""

    def __init__(self):
        # In-memory fallback: hash → {uid, name, ...}
        self._memory_keys: dict[str, dict[str, Any]] = {}
        # uid → [key docs]
        self._memory_user_keys: dict[str, dict[str, dict[str, Any]]] = {}

    def _user_col(self, uid: str):
        db = _get_fs_db()
        if db is None:
            return None
        return db.collection("users").document(uid).collection("api_keys")

    def _lookup_col(self):
        db = _get_fs_db()
        if db is None:
            return None
        return db.collection("api_key_lookup")

    def create_key(self, uid: str, name: str) -> dict[str, Any]:
        """Create a new API key. Returns dict with raw key (shown only once)."""
        raw_key = "sk_live_" + secrets.token_hex(16)
        key_hash = _hash_key(raw_key)
        now = datetime.now(timezone.utc).isoformat()
        prefix = raw_key[:12] + "..." + raw_key[-4:]

        doc_data = {
            "name": name,
            "key_hash": key_hash,
            "prefix": prefix,
            "uid": uid,
            "created_at": now,
            "last_used_at": None,
        }

        user_col = self._user_col(uid)
        lookup_col = self._lookup_col()

        if user_col is not None and lookup_col is not None:
            try:
                _, doc_ref = user_col.add(doc_data)
                key_id = doc_ref.id
                lookup_col.document(key_hash).set({"uid": uid, "key_id": key_id})
                return {"key": raw_key, "id": key_id, "name": name, "prefix": prefix}
            except Exception as e:
                logger.warning("Firestore create_key failed, using memory: %s", e)

        # Memory fallback
        import uuid
        key_id = uuid.uuid4().hex[:12]
        doc_data["id"] = key_id
        self._memory_keys[key_hash] = {"uid": uid, "key_id": key_id}
        self._memory_user_keys.setdefault(uid, {})[key_id] = doc_data
        return {"key": raw_key, "id": key_id, "name": name, "prefix": prefix}

    def list_keys(self, uid: str) -> list[dict[str, Any]]:
        user_col = self._user_col(uid)
        if user_col is not None:
            try:
                docs = user_col.stream()
                return [
                    {
                        "id": doc.id,
                        "name": d.get("name", ""),
                        "prefix": d.get("prefix", ""),
                        "created_at": d.get("created_at"),
                        "last_used_at": d.get("last_used_at"),
                    }
                    for doc in docs
                    for d in [doc.to_dict()]
                ]
            except Exception:
                pass
        return [
            {
                "id": kid,
                "name": d.get("name", ""),
                "prefix": d.get("prefix", ""),
                "created_at": d.get("created_at"),
                "last_used_at": d.get("last_used_at"),
            }
            for kid, d in self._memory_user_keys.get(uid, {}).items()
        ]

    def revoke_key(self, uid: str, key_id: str) -> bool:
        user_col = self._user_col(uid)
        lookup_col = self._lookup_col()
        if user_col is not None and lookup_col is not None:
            try:
                doc = user_col.document(key_id).get()
                if doc.exists:
                    key_hash = doc.to_dict().get("key_hash", "")
                    user_col.document(key_id).delete()
                    if key_hash:
                        lookup_col.document(key_hash).delete()
                    return True
                return False
            except Exception:
                pass
        # Memory fallback
        user_keys = self._memory_user_keys.get(uid, {})
        if key_id in user_keys:
            doc = user_keys.pop(key_id)
            key_hash = doc.get("key_hash", "")
            self._memory_keys.pop(key_hash, None)
            return True
        return False

    def authenticate(self, raw_key: str) -> str | None:
        """Authenticate a raw API key. Returns uid or None."""
        key_hash = _hash_key(raw_key)

        lookup_col = self._lookup_col()
        if lookup_col is not None:
            try:
                doc = lookup_col.document(key_hash).get()
                if doc.exists:
                    data = doc.to_dict()
                    uid = data.get("uid")
                    # Update last_used_at
                    self._touch_last_used(uid, data.get("key_id", ""))
                    return uid
                return None
            except Exception:
                pass

        # Memory fallback
        entry = self._memory_keys.get(key_hash)
        if entry:
            return entry["uid"]
        return None

    def _touch_last_used(self, uid: str, key_id: str):
        if not uid or not key_id:
            return
        user_col = self._user_col(uid)
        if user_col is not None:
            try:
                user_col.document(key_id).update(
                    {"last_used_at": datetime.now(timezone.utc).isoformat()}
                )
            except Exception:
                pass


api_key_store = ApiKeyStore()
