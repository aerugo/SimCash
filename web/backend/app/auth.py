"""Firebase Auth integration for FastAPI."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, WebSocket, status
from starlette.responses import Response

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


def _verify_token(id_token: str) -> dict:
    """Verify a Firebase ID token, return decoded token dict."""
    from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]

    _get_firebase_app()
    decoded = fb_auth.verify_id_token(id_token)
    return decoded


def _get_email_for_uid(uid: str) -> str:
    """Look up the email address for a Firebase uid."""
    from firebase_admin import auth as fb_auth  # type: ignore[import-untyped]

    _get_firebase_app()
    user_record = fb_auth.get_user(uid)
    return user_record.email or ""


def _check_access(uid: str, email: str, sign_in_provider: str) -> None:
    """Check user is allowed and record login. Raises 403 if not."""
    if config.is_auth_disabled():
        return

    from .admin import user_manager

    if not user_manager.is_allowed(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Contact an admin for access.",
        )

    # Map provider to friendly method name
    method = "google" if "google" in sign_in_provider else "email_link"
    user_manager.record_login(email, method)


def _check_dev_token(request: Request) -> bool:
    """Check if request carries a valid dev token (query param or bearer)."""
    dev_token = config.DEV_TOKEN
    if not dev_token:
        return False
    # Check query param
    if request.query_params.get("dev_token") == dev_token:
        return True
    # Check bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header == f"Bearer {dev_token}":
        return True
    return False


async def get_current_user(request: Request) -> str:
    """FastAPI dependency: extract uid from Firebase ID token.

    If SIMCASH_AUTH_DISABLED=true, returns a fixed dev uid.
    If SIMCASH_DEV_TOKEN is set and matches, returns a dev uid.
    """
    if config.is_auth_disabled():
        return "dev-user"

    if _check_dev_token(request):
        return "dev-user"

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[len("Bearer "):]
    try:
        decoded = _verify_token(token)
        uid = decoded["uid"]
        email = decoded.get("email") or _get_email_for_uid(uid)
        sign_in_provider = decoded.get("firebase", {}).get("sign_in_provider", "")
        _check_access(uid, email, sign_in_provider)
        logger.info("Authenticated user: %s (%s)", uid, email)
        return uid
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Token verification failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user_email(request: Request) -> str:
    """FastAPI dependency: returns the authenticated user's email."""
    if config.is_auth_disabled():
        return "dev@localhost"

    if _check_dev_token(request):
        return "dev@localhost"

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[len("Bearer "):]
    try:
        decoded = _verify_token(token)
        uid = decoded["uid"]
        email = decoded.get("email") or _get_email_for_uid(uid)
        return email
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_admin_user(request: Request) -> str:
    """FastAPI dependency: ensures the user is an admin. Returns email."""
    email = await get_current_user_email(request)

    if config.is_auth_disabled() or _check_dev_token(request):
        return email

    from .admin import user_manager

    if not user_manager.is_admin(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return email


async def get_ws_user(websocket: WebSocket) -> str:
    """Extract uid from WebSocket query param ?token=<idToken>.

    Call BEFORE websocket.accept(). On failure, accepts then closes with error.
    """
    if config.is_auth_disabled():
        return "dev-user"

    # Check dev token on WS
    dev_token = config.DEV_TOKEN
    if dev_token and websocket.query_params.get("dev_token") == dev_token:
        return "dev-user"

    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.close(code=4001, reason="Missing auth token")
        raise HTTPException(status_code=401, detail="Missing auth token")

    try:
        decoded = _verify_token(token)
        uid = decoded["uid"]
        logger.info("WS authenticated user: %s", uid)
        return uid
    except Exception as e:
        logger.warning("WS token verification failed: %s", e)
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_optional_user(request: Request) -> str:
    """Returns uid if authenticated, else 'guest-{session_id}' from cookie."""
    try:
        return await get_current_user(request)
    except HTTPException:
        # Cookie already stores "guest-xxxx" from GuestCookieMiddleware
        guest_id = request.cookies.get("simcash_guest")
        if guest_id:
            return guest_id
        return f"guest-{uuid4().hex[:12]}"


async def get_optional_ws_user(websocket: WebSocket) -> str:
    """WS variant: returns uid if authenticated, else guest id from cookie/query."""
    try:
        return await get_ws_user(websocket)
    except (HTTPException, Exception):
        guest_id = websocket.cookies.get("simcash_guest")
        if guest_id:
            return guest_id
        return f"guest-{uuid4().hex[:12]}"


class GuestCookieMiddleware:
    """Sets a stable guest cookie if not present.

    Implemented as a pure ASGI middleware (not BaseHTTPMiddleware) to avoid
    breaking WebSocket connections — BaseHTTPMiddleware is known to close
    WebSockets prematurely in Starlette.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            # Pass WebSocket (and lifespan) through untouched
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        needs_cookie = not request.cookies.get("simcash_guest")
        guest_id = f"guest-{uuid4().hex[:12]}" if needs_cookie else None

        if not needs_cookie:
            await self.app(scope, receive, send)
            return

        # Intercept the response start to inject the Set-Cookie header
        async def send_with_cookie(message):
            if message["type"] == "http.response.start" and guest_id:
                from http.cookies import SimpleCookie
                cookie: SimpleCookie = SimpleCookie()
                cookie["simcash_guest"] = guest_id
                cookie["simcash_guest"]["max-age"] = str(86400)
                cookie["simcash_guest"]["httponly"] = True
                cookie["simcash_guest"]["samesite"] = "Lax"
                cookie["simcash_guest"]["path"] = "/"
                header_value = cookie["simcash_guest"].OutputString()
                headers = list(message.get("headers", []))
                headers.append((b"set-cookie", header_value.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_cookie)
