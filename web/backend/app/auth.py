"""Firebase Auth integration for FastAPI."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, WebSocket, status

from . import config

logger = logging.getLogger(__name__)

_firebase_app: Optional[object] = None


def _get_firebase_app():
    """Lazily initialize Firebase Admin SDK."""
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app
    import firebase_admin  # type: ignore[import-untyped]

    if not firebase_admin._apps:
        _firebase_app = firebase_admin.initialize_app()
    else:
        _firebase_app = firebase_admin.get_app()
    return _firebase_app


def _verify_token(id_token: str) -> str:
    """Verify a Firebase ID token, return uid."""
    from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]

    _get_firebase_app()
    decoded = fb_auth.verify_id_token(id_token)
    return decoded["uid"]


async def get_current_user(request: Request) -> str:
    """FastAPI dependency: extract uid from Firebase ID token.

    If SIMCASH_AUTH_DISABLED=true, returns a fixed dev uid.
    """
    if config.is_auth_disabled():
        return "dev-user"

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[len("Bearer "):]
    try:
        uid = _verify_token(token)
        logger.info("Authenticated user: %s", uid)
        return uid
    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_ws_user(websocket: WebSocket) -> str:
    """Extract uid from WebSocket query param ?token=<idToken>.

    Call BEFORE websocket.accept(). On failure, accepts then closes with error.
    """
    if config.is_auth_disabled():
        return "dev-user"

    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing auth token")
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        uid = _verify_token(token)
        logger.info("WS authenticated user: %s", uid)
        return uid
    except Exception as e:
        logger.warning("WS token verification failed: %s", e)
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")
