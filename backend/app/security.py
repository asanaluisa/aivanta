"""Password hashing and token handling (standard library + PyJWT only).

Kept free of FastAPI imports so it can be unit-tested in isolation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ITERATIONS = 310_000
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # read: dashboards & reports; ingest: upload usage; assumptions: edit ROI assumptions;
    # snapshots: freeze ROI results; admin: everything incl. audit log.
    "admin": frozenset({"read", "ingest", "assumptions", "snapshots", "audit"}),
    "finance": frozenset({"read", "assumptions", "snapshots"}),
    "analyst": frozenset({"read", "ingest"}),
    "viewer": frozenset({"read"}),
    "member": frozenset(),
}


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations, base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded or not password:
        return False
    try:
        algo, iterations, salt_b64, digest_b64 = encoded.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt_b64), int(iterations))
    return hmac.compare_digest(digest, base64.b64decode(digest_b64))


@dataclass(frozen=True)
class Principal:
    user_id: int
    organization_id: int
    role: str

    def can(self, permission: str) -> bool:
        return permission in ROLE_PERMISSIONS.get(self.role, frozenset())


def issue_token(p: Principal, secret: str, *, algorithm: str = "HS256", minutes: int = 480,
                now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    claims = {"sub": str(p.user_id), "org": p.organization_id, "role": p.role,
              "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=minutes)).timestamp())}
    return jwt.encode(claims, secret, algorithm=algorithm)


class InvalidToken(Exception):
    pass


def decode_token(token: str, secret: str, *, algorithm: str = "HS256") -> Principal:
    try:
        claims = jwt.decode(token, secret, algorithms=[algorithm], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    role = claims.get("role")
    if role not in ROLE_PERMISSIONS:
        raise InvalidToken("unknown role")
    return Principal(int(claims["sub"]), int(claims["org"]), role)
