"""
Integration Tests: Sessions API — protected endpoints, user scoping.

Tests that session endpoints require auth and only return the
authenticated user's sessions.
"""
import pytest
from backend.app.db.models import Session, User
from backend.app.services.auth_service import hash_password


class TestSessionsEndpoint:
    @pytest.mark.asyncio
    async def test_list_sessions_requires_auth(self, client):
        """GET /api/sessions without token returns 401."""
        resp = await client.get("/api/sessions")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client, auth_headers):
        """Authenticated user with no sessions gets empty list."""
        resp = await client.get("/api/sessions", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_sessions_returns_own_sessions(self, client, auth_headers, db_session):
        """User only sees their own sessions."""
        # Get user ID from /me
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]

        # Insert sessions directly into DB
        s1 = Session(id="sess-1", user_id=user_id, mode="cloud", topic="Topic A", user_position="for")
        s2 = Session(id="sess-2", user_id=user_id, mode="cloud", topic="Topic B", user_position="against")
        db_session.add(s1)
        db_session.add(s2)
        await db_session.commit()

        resp = await client.get("/api/sessions", headers=auth_headers)
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 2
        topics = {s["topic"] for s in sessions}
        assert topics == {"Topic A", "Topic B"}

    @pytest.mark.asyncio
    async def test_sessions_scoped_to_user(self, client, db_session):
        """User A cannot see User B's sessions."""
        # Register two users
        resp_a = await client.post("/api/auth/register", json={
            "email": "alice@test.com", "password": "pass", "name": "Alice",
        })
        resp_b = await client.post("/api/auth/register", json={
            "email": "bob@test.com", "password": "pass", "name": "Bob",
        })
        token_a = resp_a.json()["access_token"]
        token_b = resp_b.json()["access_token"]
        user_a_id = resp_a.json()["user"]["id"]
        user_b_id = resp_b.json()["user"]["id"]

        # Insert a session for each user
        sa = Session(id="alice-sess", user_id=user_a_id, mode="cloud", topic="Alice Topic", user_position="for")
        sb = Session(id="bob-sess", user_id=user_b_id, mode="cloud", topic="Bob Topic", user_position="against")
        db_session.add(sa)
        db_session.add(sb)
        await db_session.commit()

        # Alice should only see her session
        resp = await client.get("/api/sessions", headers={"Authorization": f"Bearer {token_a}"})
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["topic"] == "Alice Topic"

        # Bob should only see his session
        resp = await client.get("/api/sessions", headers={"Authorization": f"Bearer {token_b}"})
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["topic"] == "Bob Topic"


class TestSessionDetail:
    @pytest.mark.asyncio
    async def test_get_session_detail(self, client, auth_headers, db_session):
        """GET /api/sessions/{id} returns session details."""
        me_resp = await client.get("/api/auth/me", headers=auth_headers)
        user_id = me_resp.json()["id"]

        s = Session(
            id="detail-sess", user_id=user_id, mode="cloud",
            topic="Detail Topic", user_position="for",
            duration_seconds=120.5, user_wpm=85.3,
        )
        db_session.add(s)
        await db_session.commit()

        resp = await client.get("/api/sessions/detail-sess", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "Detail Topic"
        assert data["duration_seconds"] == 120.5
        assert data["user_wpm"] == 85.3

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client, auth_headers):
        """GET /api/sessions/{nonexistent} returns 404."""
        resp = await client.get("/api/sessions/does-not-exist", headers=auth_headers)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_other_users_session_returns_404(self, client, db_session):
        """Cannot access another user's session by ID."""
        # Register two users
        resp_a = await client.post("/api/auth/register", json={
            "email": "viewer@test.com", "password": "pass", "name": "Viewer",
        })
        resp_b = await client.post("/api/auth/register", json={
            "email": "owner@test.com", "password": "pass", "name": "Owner",
        })
        token_a = resp_a.json()["access_token"]
        user_b_id = resp_b.json()["user"]["id"]

        # Create session owned by user B
        s = Session(id="private-sess", user_id=user_b_id, mode="cloud", topic="Private", user_position="for")
        db_session.add(s)
        await db_session.commit()

        # User A tries to access it — should get 404
        resp = await client.get("/api/sessions/private-sess", headers={
            "Authorization": f"Bearer {token_a}"
        })
        assert resp.status_code == 404
