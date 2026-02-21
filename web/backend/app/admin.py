"""Admin / user management via Firestore."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

# Firestore client — lazily initialised
_db = None


def _get_db():
    global _db
    if _db is not None:
        return _db
    from .auth import _get_firebase_app
    _get_firebase_app()  # Ensure Firebase Admin SDK is initialized
    from firebase_admin import firestore  # type: ignore[import-untyped]
    db_id = config.FIRESTORE_DATABASE if hasattr(config, "FIRESTORE_DATABASE") else "(default)"
    _db = firestore.client(database_id=db_id)
    return _db


class UserManager:
    """Thin wrapper around Firestore collections for access control."""

    # ----- read helpers -----

    def is_allowed(self, email: str) -> bool:
        if config.is_auth_disabled():
            return True
        if email.endswith("@sensestack.xyz"):
            return True
        db = _get_db()
        doc = db.collection("allowed_users").document(email).get()
        return doc.exists

    def is_admin(self, email: str) -> bool:
        if config.is_auth_disabled():
            return True
        db = _get_db()
        doc = db.collection("admins").document(email).get()
        return doc.exists

    # ----- write helpers -----

    def invite_user(self, email: str, invited_by: str) -> None:
        db = _get_db()
        db.collection("allowed_users").document(email).set({
            "email": email,
            "status": "invited",
            "invited_by": invited_by,
            "invited_at": datetime.now(timezone.utc).isoformat(),
        })

    def list_users(self) -> list[dict]:
        db = _get_db()
        docs = db.collection("allowed_users").stream()
        return [d.to_dict() for d in docs]

    def revoke_user(self, email: str) -> None:
        db = _get_db()
        db.collection("allowed_users").document(email).delete()

    def record_login(self, email: str, method: str) -> None:
        db = _get_db()
        db.collection("allowed_users").document(email).set(
            {
                "email": email,
                "status": "active",
                "last_login": datetime.now(timezone.utc).isoformat(),
                "sign_in_method": method,
            },
            merge=True,
        )

    # ----- seeding -----

    def seed_admin(self, email: str) -> None:
        db = _get_db()
        doc = db.collection("admins").document(email).get()
        if not doc.exists:
            db.collection("admins").document(email).set({
                "email": email,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info("Seeded admin: %s", email)


user_manager = UserManager()
