"""Firestore-backed storage for user custom scenarios and policies."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from . import config

logger = logging.getLogger(__name__)

_fs_db = None


def _get_fs_db():
    """Lazy Firestore client init. Returns None if unavailable."""
    global _fs_db
    if _fs_db is not None:
        return _fs_db
    try:
        from .auth import _get_firebase_app
        _get_firebase_app()  # Ensure Firebase Admin SDK is initialized
        from firebase_admin import firestore  # type: ignore[import-untyped]
        db_id = config.FIRESTORE_DATABASE
        _fs_db = firestore.client(database_id=db_id)
        return _fs_db
    except Exception:
        return None


class UserContentStore:
    """CRUD for user content stored in Firestore subcollections.

    Collection path: users/{uid}/{collection_type}/{item_id}
    Falls back to in-memory dict when Firestore is unavailable.
    """

    def __init__(self, collection_type: str):
        self.collection_type = collection_type
        # In-memory fallback: {uid: {item_id: data}}
        self._memory: dict[str, dict[str, dict[str, Any]]] = {}

    def _col(self, uid: str):
        """Return Firestore collection ref or None."""
        db = _get_fs_db()
        if db is None:
            return None
        return db.collection("users").document(uid).collection(self.collection_type)

    def list(self, uid: str) -> list[dict[str, Any]]:
        col = self._col(uid)
        if col is not None:
            try:
                docs = col.stream()
                return [{"id": doc.id, **doc.to_dict()} for doc in docs]
            except Exception:
                logger.debug("Firestore list failed; falling back to memory")
        return list(self._memory.get(uid, {}).values())

    def get(self, uid: str, item_id: str) -> dict[str, Any] | None:
        col = self._col(uid)
        if col is not None:
            try:
                doc = col.document(item_id).get()
                if doc.exists:
                    return {"id": doc.id, **doc.to_dict()}
                return None
            except Exception:
                logger.debug("Firestore get failed; falling back to memory")
        return self._memory.get(uid, {}).get(item_id)

    def save(self, uid: str, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        col = self._col(uid)
        if col is not None:
            try:
                doc_ref = col.document(item_id)
                existing = doc_ref.get()
                if existing.exists:
                    data["updated_at"] = now
                    data["created_at"] = existing.to_dict().get("created_at", now)
                else:
                    data["created_at"] = now
                    data["updated_at"] = now
                data["id"] = item_id
                doc_ref.set(data)
                return data
            except Exception:
                logger.debug("Firestore save failed; falling back to memory")

        # In-memory fallback
        user_store = self._memory.setdefault(uid, {})
        existing = user_store.get(item_id)
        if existing:
            data["created_at"] = existing.get("created_at", now)
            data["updated_at"] = now
        else:
            data["created_at"] = now
            data["updated_at"] = now
        data["id"] = item_id
        user_store[item_id] = data
        return data

    def get_public(self, item_id: str) -> dict[str, Any] | None:
        """Look up an item by ID across all users (public read).

        Uses Firestore collection group query. Falls back to scanning in-memory store.
        """
        db = _get_fs_db()
        if db is not None:
            try:
                from google.cloud.firestore_v1.base_query import FieldFilter
                query = db.collection_group(self.collection_type).where(
                    filter=FieldFilter("id", "==", item_id)
                ).limit(1)
                docs = list(query.stream())
                if docs:
                    return {"id": docs[0].id, **docs[0].to_dict()}
            except Exception:
                logger.debug("Firestore collection group query failed; falling back to memory")

        # In-memory fallback: scan all users
        for uid_items in self._memory.values():
            if item_id in uid_items:
                return uid_items[item_id]
        return None

    def delete(self, uid: str, item_id: str) -> bool:
        col = self._col(uid)
        if col is not None:
            try:
                doc_ref = col.document(item_id)
                doc = doc_ref.get()
                if not doc.exists:
                    return False
                doc_ref.delete()
                return True
            except Exception:
                logger.debug("Firestore delete failed; falling back to memory")

        user_store = self._memory.get(uid, {})
        if item_id in user_store:
            del user_store[item_id]
            return True
        return False
