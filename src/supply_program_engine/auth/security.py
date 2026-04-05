from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets

from supply_program_engine.config import settings

from .models import OperatorUser


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt$16384$8$1${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, n_value, r_value, p_value, salt_value, digest_value = stored_hash.split("$", 5)
    except ValueError:
        return False

    if scheme != "scrypt":
        return False

    try:
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=_b64decode(salt_value),
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(_b64decode(digest_value)),
        )
    except Exception:
        return False

    return hmac.compare_digest(_b64encode(derived), digest_value)


def _default_dev_users() -> list[OperatorUser]:
    return [
        OperatorUser(
            username="demo-admin",
            display_name="Demo Admin",
            password_hash=hash_password("dev-password"),
            roles=["reviewer", "approver", "sender", "admin"],
        )
    ]


def load_operator_users() -> dict[str, OperatorUser]:
    raw = settings.OPERATOR_USERS_JSON.strip()
    if not raw:
        if settings.ENV == "dev":
            users = _default_dev_users()
            return {user.username: user for user in users}
        return {}

    parsed = json.loads(raw)
    users = [OperatorUser(**item) for item in parsed]
    return {user.username: user for user in users}


def authenticate_operator(username: str, password: str) -> OperatorUser | None:
    user = load_operator_users().get(username.strip())
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
