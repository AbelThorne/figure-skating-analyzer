import pytest
import time
from app.auth.passwords import hash_password, verify_password


def test_hash_and_verify():
    hashed = hash_password("mysecretpass")
    assert hashed != "mysecretpass"
    assert verify_password("mysecretpass", hashed) is True


def test_verify_wrong_password():
    hashed = hash_password("correct")
    assert verify_password("wrong", hashed) is False


from app.auth.tokens import create_access_token, create_refresh_token, decode_token


def test_access_token_roundtrip():
    token = create_access_token(user_id="u1", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_includes_version():
    token = create_refresh_token(user_id="u1", token_version=3)
    payload = decode_token(token)
    assert payload["sub"] == "u1"
    assert payload["type"] == "refresh"
    assert payload["ver"] == 3


def test_expired_token_raises():
    token = create_access_token(user_id="u1", role="admin", expires_seconds=0)
    time.sleep(0.1)
    with pytest.raises(Exception):
        decode_token(token)
