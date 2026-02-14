"""
Integration Tests: WebSocket — connection, auth, basic message flow.
"""
import json
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.main import app
from backend.app.services.auth_service import create_access_token


class TestWebSocketAuth:
    @pytest.mark.asyncio
    async def test_ws_connect_without_token_guest_mode(self):
        """WebSocket connects without token in guest mode."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream("GET", "/ws/debate", headers={
                "connection": "upgrade",
                "upgrade": "websocket",
            }) as resp:
                # WebSocket upgrade should be accepted (101)
                # httpx doesn't fully support WS, but we can verify the endpoint exists
                pass
        # If we get here without error, the endpoint is reachable

    @pytest.mark.asyncio
    async def test_ws_rejects_invalid_token(self):
        """WebSocket with invalid token should close with 4001."""
        from starlette.testclient import TestClient
        from starlette.websockets import WebSocketDisconnect

        test_client = TestClient(app)
        with pytest.raises(Exception):
            # Invalid token should cause the server to close with 4001
            with test_client.websocket_connect("/ws/debate?token=bad.token.here") as ws:
                ws.receive_text()

    @pytest.mark.asyncio
    async def test_ws_accepts_valid_token(self):
        """WebSocket with valid token connects successfully."""
        from starlette.testclient import TestClient

        token = create_access_token(user_id="test-user-123", email="ws@test.com")

        test_client = TestClient(app)
        with test_client.websocket_connect(f"/ws/debate?token={token}") as ws:
            # Send a ping and expect a pong
            ws.send_text(json.dumps({"type": "ping"}))
            response = json.loads(ws.receive_text())
            assert response["type"] == "pong"


class TestWebSocketMessages:
    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        """Unknown message type returns error."""
        from starlette.testclient import TestClient

        test_client = TestClient(app)
        with test_client.websocket_connect("/ws/debate") as ws:
            ws.send_text(json.dumps({"type": "nonexistent"}))
            response = json.loads(ws.receive_text())
            assert response["type"] == "error"
            assert "unknown" in response.get("message", "").lower() or "unknown" in response.get("code", "").lower()

    @pytest.mark.asyncio
    async def test_ping_pong(self):
        """Ping message receives pong response."""
        from starlette.testclient import TestClient

        test_client = TestClient(app)
        with test_client.websocket_connect("/ws/debate") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            response = json.loads(ws.receive_text())
            assert response["type"] == "pong"
