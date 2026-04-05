from __future__ import annotations

import base64
import hashlib
import hmac
import json

from .models import SessionPrincipal
from .sessions import _session_secret


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _sign(payload: str) -> str:
    digest = hmac.new(_session_secret(), f"csrf:{payload}".encode("utf-8"), hashlib.sha256).digest()
    return _b64encode(digest)


def issue_csrf_token(principal: SessionPrincipal) -> str:
    payload = json.dumps(
        {
            "u": principal.username,
            "csrf": principal.csrf_key,
            "exp": principal.expires_at,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    encoded_payload = _b64encode(payload.encode("utf-8"))
    signature = _sign(encoded_payload)
    return f"{encoded_payload}.{signature}"


def verify_csrf_token(token: str | None, principal: SessionPrincipal | None) -> bool:
    if not token or principal is None:
        return False

    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError:
        return False

    expected = _sign(encoded_payload)
    if not hmac.compare_digest(expected, signature):
        return False

    try:
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except Exception:
        return False

    return (
        payload.get("u") == principal.username
        and payload.get("csrf") == principal.csrf_key
        and int(payload.get("exp", 0)) == principal.expires_at
    )
