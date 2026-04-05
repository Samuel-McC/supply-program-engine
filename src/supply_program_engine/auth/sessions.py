from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Request
from fastapi.responses import Response

from supply_program_engine.config import settings

from .models import OperatorUser, SessionPrincipal


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _session_secret() -> bytes:
    return settings.SESSION_SECRET.encode("utf-8")


def _sign(payload: str) -> str:
    digest = hmac.new(_session_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def _serialize(data: dict[str, object]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    encoded_payload = _b64encode(payload.encode("utf-8"))
    signature = _sign(encoded_payload)
    return f"{encoded_payload}.{signature}"


def _deserialize(token: str) -> dict[str, object] | None:
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = _sign(encoded_payload)
    if not hmac.compare_digest(expected, signature):
        return None

    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except Exception:
        return None

    expires_at = int(payload.get("exp", 0))
    if expires_at <= int(time.time()):
        return None
    return payload


def create_session_principal(user: OperatorUser) -> SessionPrincipal:
    issued_at = int(time.time())
    expires_at = issued_at + settings.SESSION_TTL_SECONDS
    return SessionPrincipal(
        username=user.username,
        display_name=user.display_name,
        roles=user.roles,
        issued_at=issued_at,
        expires_at=expires_at,
        csrf_key=secrets.token_urlsafe(16),
    )


def encode_session(principal: SessionPrincipal) -> str:
    return _serialize(
        {
            "u": principal.username,
            "d": principal.display_name,
            "r": principal.roles,
            "iat": principal.issued_at,
            "exp": principal.expires_at,
            "csrf": principal.csrf_key,
        }
    )


def decode_session(token: str | None) -> SessionPrincipal | None:
    if not token:
        return None

    payload = _deserialize(token)
    if payload is None:
        return None

    return SessionPrincipal(
        username=str(payload["u"]),
        display_name=str(payload["d"]),
        roles=list(payload["r"]),
        issued_at=int(payload["iat"]),
        expires_at=int(payload["exp"]),
        csrf_key=str(payload["csrf"]),
    )


def load_session_from_request(request: Request) -> SessionPrincipal | None:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    return decode_session(token)


def set_session_cookie(response: Response, principal: SessionPrincipal) -> None:
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=encode_session(principal),
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
