"""
Integration-style Tests: WebSocket handler lifecycle and message flow.

Runs DebateWebSocketHandler against an async mock websocket object to validate
the real message protocol without relying on network sockets/TestClient.
"""
from __future__ import annotations

import json
from collections import deque

import pytest
from fastapi import WebSocketDisconnect

from backend.app.routers.ws_handler import DebateWebSocketHandler
from backend.app.services.auth_service import create_access_token


class MockWebSocket:
    """Minimal async websocket stub for handler-level integration tests."""

    def __init__(self, messages: list[dict] | None = None, token: str | None = None):
        self._messages = deque(json.dumps(m) for m in (messages or []))
        self.query_params = {"token": token} if token else {}
        self.accepted = False
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.sent_texts: list[str] = []

    async def accept(self) -> None:
        self.accepted = True

    async def receive_text(self) -> str:
        if self._messages:
            return self._messages.popleft()
        raise WebSocketDisconnect()

    async def send_text(self, text: str) -> None:
        self.sent_texts.append(text)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


async def run_handler(ws: MockWebSocket) -> list[dict]:
    handler = DebateWebSocketHandler(ws)  # type: ignore[arg-type]
    await handler.handle()
    return [json.loads(m) for m in ws.sent_texts]


class TestWebSocketAuth:
    @pytest.mark.asyncio
    async def test_ws_connect_without_token_guest_mode(self):
        """WebSocket connects without token in guest mode."""
        ws = MockWebSocket(messages=[{"type": "ping"}])
        messages = await run_handler(ws)

        assert ws.accepted is True
        assert any(m.get("type") == "pong" for m in messages)

    @pytest.mark.asyncio
    async def test_ws_rejects_invalid_token(self):
        """WebSocket with invalid token should close with 4001."""
        ws = MockWebSocket(token="bad.token.here")
        messages = await run_handler(ws)

        assert ws.accepted is True
        assert ws.closed is True
        assert ws.close_code == 4001
        assert ws.close_reason == "Invalid or expired token"
        assert messages == []

    @pytest.mark.asyncio
    async def test_ws_accepts_valid_token(self):
        """WebSocket with valid token connects successfully."""
        token = create_access_token(user_id="test-user-123", email="ws@test.com")
        ws = MockWebSocket(messages=[{"type": "ping"}], token=token)
        messages = await run_handler(ws)

        assert ws.accepted is True
        assert ws.closed is False
        assert any(m.get("type") == "pong" for m in messages)


class TestWebSocketMessages:
    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        """Unknown message type returns error."""
        ws = MockWebSocket(messages=[{"type": "nonexistent"}])
        messages = await run_handler(ws)

        assert messages
        response = messages[0]
        assert response["type"] == "error"
        assert "unknown" in response.get("message", "").lower() or "unknown" in response.get("code", "").lower()

    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Ping message receives pong response."""
        ws = MockWebSocket(messages=[{"type": "ping"}])
        messages = await run_handler(ws)

        assert messages
        assert messages[0]["type"] == "pong"
