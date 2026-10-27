from datetime import datetime, timedelta, timezone

import pytest

jwt = pytest.importorskip("jwt")

KEY = "unit-test-secret-at-least-32-bytes-long"

from app.security import (  # noqa: E402
    InvalidToken,
    Principal,
    decode_token,
    hash_password,
    issue_token,
    verify_password,
)


def test_password_round_trip():
    h = hash_password("s3cret", iterations=1000)
    assert h.startswith("pbkdf2_sha256$1000$")
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("s3cret", None)
    assert not verify_password("s3cret", "garbage")
    with pytest.raises(ValueError):
        hash_password("")


def test_hashes_are_salted():
    assert hash_password("x", iterations=1000) != hash_password("x", iterations=1000)


def test_token_round_trip_and_permissions():
    p = Principal(7, 3, "finance")
    back = decode_token(issue_token(p, KEY), KEY)
    assert back == p
    assert back.can("assumptions") and back.can("read") and not back.can("ingest")
    assert Principal(1, 1, "viewer").can("read") and not Principal(1, 1, "viewer").can("snapshots")
    assert not Principal(1, 1, "member").can("read")


def test_token_rejections():
    p = Principal(1, 1, "admin")
    with pytest.raises(InvalidToken):
        decode_token(issue_token(p, KEY), "another-32-byte-secret-for-tests-xxxxx")
    old = datetime.now(timezone.utc) - timedelta(days=2)
    with pytest.raises(InvalidToken):
        decode_token(issue_token(p, KEY, now=old, minutes=1), KEY)
    forged = jwt.encode({"sub": "1", "org": 1, "role": "superuser", "exp": 9999999999}, KEY)
    with pytest.raises(InvalidToken):
        decode_token(forged, KEY)
