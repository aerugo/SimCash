"""Admin / user management via Firestore."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from . import config
from .wordlist import generate_passphrase

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

    def is_admin_uid(self, uid: str) -> bool:
        """Check if a UID belongs to an admin (resolves UID → email via Firebase Auth)."""
        if config.is_auth_disabled():
            return True
        try:
            from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]
            user = fb_auth.get_user(uid)
            if user.email:
                return self.is_admin(user.email)
        except Exception:
            pass
        return False

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

    # ----- password auth -----

    def create_user_with_passphrase(self, email: str, invited_by: str) -> str:
        """Create a Firebase Auth user with a generated passphrase.

        Returns the passphrase (shown once to admin, never stored in plaintext).
        Also adds the user to allowed_users.
        """
        from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]

        passphrase = generate_passphrase(4)

        # Create Firebase Auth user (or update if exists)
        try:
            user_record = fb_auth.create_user(
                email=email,
                password=passphrase,
                email_verified=True,
            )
            logger.info("Created Firebase Auth user: %s (uid=%s)", email, user_record.uid)
        except fb_auth.EmailAlreadyExistsError:
            # User exists — update their password
            user_record = fb_auth.get_user_by_email(email)
            fb_auth.update_user(user_record.uid, password=passphrase)
            logger.info("Reset password for existing user: %s (uid=%s)", email, user_record.uid)

        # Add to allowed_users
        self.invite_user(email, invited_by)

        return passphrase

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
