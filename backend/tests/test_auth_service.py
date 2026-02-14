"""
Tests: Auth Service — password hashing and JWT token lifecycle.
"""
import pytest
from backend.app.services.auth_service import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
    verify_ws_token,
)


class TestPasswordHashing:
    def test_hash_is_different_from_plain(self):
        """Hashed password should not equal the plain text."""
        plain = "my_secure_password"
        hashed = hash_password(plain)
        assert hashed != plain

    def test_verify_correct_password(self):
        """Correct password verification returns True."""
        plain = "my_secure_password"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_verify_wrong_password(self):
        """Wrong password verification returns False."""
        hashed = hash_password("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """bcrypt generates different salts each time."""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        # But both verify correctly
        assert verify_password("same", h1) is True
        assert verify_password("same", h2) is True


class TestJWT:
    def test_create_and_verify_token(self):
        """Create a token and verify it returns correct payload."""
        token = create_access_token(user_id="user123", email="test@test.com")
        payload = verify_token(token)
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@test.com"
        assert "exp" in payload

    def test_invalid_token_raises(self):
        """Invalid token string raises HTTPException."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            verify_token("this.is.garbage")
        assert exc_info.value.status_code == 401

    def test_ws_token_valid(self):
        """verify_ws_token returns payload for valid token."""
        token = create_access_token(user_id="ws_user", email="ws@test.com")
        payload = verify_ws_token(token)
        assert payload is not None
        assert payload["sub"] == "ws_user"

    def test_ws_token_invalid_returns_none(self):
        """verify_ws_token returns None for invalid token (no exception)."""
        result = verify_ws_token("invalid.token.here")
        assert result is None

    def test_token_contains_expected_fields(self):
        """Token payload has sub, email, and exp fields."""
        token = create_access_token(user_id="u1", email="e@e.com")
        payload = verify_token(token)
        assert set(payload.keys()) >= {"sub", "email", "exp"}
