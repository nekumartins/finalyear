"""
Integration Tests: Auth API — register, login, /me, and error cases.

These tests hit the actual FastAPI endpoints with a real SQLite database.
"""
import pytest
import httpx

from backend.app.routers import auth as auth_router


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """New user registration returns token and user info."""
        resp = await client.post("/api/auth/register", json={
            "email": "new@user.com",
            "password": "securepass",
            "name": "New User",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "new@user.com"
        assert data["user"]["name"] == "New User"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        """Registering the same email twice returns 400."""
        payload = {"email": "dupe@user.com", "password": "pass1", "name": "First"}
        resp1 = await client.post("/api/auth/register", json=payload)
        assert resp1.status_code == 200

        resp2 = await client.post("/api/auth/register", json=payload)
        assert resp2.status_code == 400
        assert "already registered" in resp2.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client):
        """Missing required fields returns 422."""
        resp = await client.post("/api/auth/register", json={"email": "no@name.com"})
        assert resp.status_code == 422


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Login with correct credentials returns token."""
        # Register first
        await client.post("/api/auth/register", json={
            "email": "login@test.com",
            "password": "mypassword",
            "name": "Login Test",
        })

        # Login
        resp = await client.post("/api/auth/login", json={
            "email": "login@test.com",
            "password": "mypassword",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login@test.com"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """Wrong password returns 401."""
        await client.post("/api/auth/register", json={
            "email": "wrong@pass.com",
            "password": "correct",
            "name": "Test",
        })

        resp = await client.post("/api/auth/login", json={
            "email": "wrong@pass.com",
            "password": "incorrect",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Login with non-existent email returns 401."""
        resp = await client.post("/api/auth/login", json={
            "email": "nobody@here.com",
            "password": "whatever",
        })
        assert resp.status_code == 401


class TestMe:
    @pytest.mark.asyncio
    async def test_me_authenticated(self, client, auth_headers):
        """GET /api/auth/me with valid token returns user info."""
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@debate.com"
        assert data["name"] == "Test User"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_me_no_token(self, client):
        """GET /api/auth/me without token returns 401."""
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client):
        """GET /api/auth/me with garbled token returns 401."""
        resp = await client.get("/api/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401


class TestTokenReuse:
    @pytest.mark.asyncio
    async def test_register_token_works_for_me(self, client):
        """Token from registration can be used immediately."""
        reg_resp = await client.post("/api/auth/register", json={
            "email": "fresh@user.com",
            "password": "pass123",
            "name": "Fresh",
        })
        token = reg_resp.json()["access_token"]

        me_resp = await client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "fresh@user.com"

    @pytest.mark.asyncio
    async def test_login_token_works_for_me(self, client):
        """Token from login can be used to access protected endpoints."""
        await client.post("/api/auth/register", json={
            "email": "reuse@token.com",
            "password": "pass",
            "name": "Reuse",
        })
        login_resp = await client.post("/api/auth/login", json={
            "email": "reuse@token.com",
            "password": "pass",
        })
        token = login_resp.json()["access_token"]

        me_resp = await client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert me_resp.status_code == 200


class TestGoogleAuth:
    @pytest.mark.asyncio
    async def test_google_auth_success(self, client, monkeypatch):
        """Valid Google token returns app JWT and user profile."""

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {
                    "sub": "google-sub-123",
                    "email": "google@user.com",
                    "name": "Google User",
                    "aud": "test-google-client-id",
                }

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                return FakeResponse()

        monkeypatch.setenv("VITE_GOOGLE_CLIENT_ID", "test-google-client-id")
        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient())

        resp = await client.post("/api/auth/google", json={"id_token": "valid-token"})
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["user"]["email"] == "google@user.com"
        assert body["user"]["name"] == "Google User"

    @pytest.mark.asyncio
    async def test_google_auth_invalid_token(self, client, monkeypatch):
        """Google rejected token should return 401."""

        class FakeResponse:
            status_code = 401

            @staticmethod
            def json():
                return {"error_description": "Invalid Value"}

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                return FakeResponse()

        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient())

        resp = await client.post("/api/auth/google", json={"id_token": "bad-token"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_google_auth_upstream_failure_returns_503(self, client, monkeypatch):
        """Network issues to Google endpoint should return 503, not 500."""

        class FakeAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                raise httpx.ConnectError("connection failed")

        monkeypatch.setattr(auth_router.httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient())

        resp = await client.post("/api/auth/google", json={"id_token": "any-token"})
        assert resp.status_code == 503
