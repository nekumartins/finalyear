"""
Debate Coach Backend — FastAPI Application Entry Point

Run locally:
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

Run via Docker:
    docker compose up --build
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.db.init_db import init_db
from backend.app.routers.api import router as api_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.ws_handler import DebateWebSocketHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info(f"🎙️ Debate Coach Backend starting (mode={settings.default_mode})")
    logger.info(f"📡 WebSocket endpoint: ws://{settings.host}:{settings.port}/ws/debate")

    # Ensure database tables exist (idempotent CREATE IF NOT EXISTS)
    try:
        await init_db()
        logger.info("✅ Database tables verified/created")
    except Exception:
        logger.exception("❌ Failed to initialise database tables")

    yield
    logger.info("Debate Coach Backend shutting down")


app = FastAPI(
    title="Debate Coach API",
    description="Real-Time AI Debate Coach with Predictive Turn-Taking",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend to connect (dev: Vite on localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(api_router)
app.include_router(auth_router)


# WebSocket endpoint
@app.websocket("/ws/debate")
async def websocket_debate(websocket: WebSocket):
    handler = DebateWebSocketHandler(websocket)
    await handler.handle()


class SPAStaticFiles(StaticFiles):
    """
    Static file server with SPA fallback.
    If a client-side route is missing as a file, serve index.html.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            request_path = scope.get("path", "")
            is_client_route = (
                scope.get("method") == "GET"
                and not request_path.startswith("/api")
                and not request_path.startswith("/ws")
                and "." not in request_path.rsplit("/", 1)[-1]
            )
            if is_client_route:
                return await super().get_response("index.html", scope)
        return response


# ── Static Frontend (Docker production build) ─────────────
# In Docker, the Vite build output is copied to /app/static/
# Serve it as a single-page app (catch-all → index.html)
STATIC_DIR = Path("/app/static")
if STATIC_DIR.is_dir():
    logger.info(f"📦 Serving frontend from {STATIC_DIR}")
    app.mount("/", SPAStaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    logger.info("🔧 No static frontend found (running in dev mode)")


@app.exception_handler(404)
async def spa_404_fallback(request: Request, exc):
    """
    Serve SPA entrypoint for client-side routes like /auth, /dashboard, /history/:id.
    Keep API and asset 404s as JSON Not Found.
    """
    if STATIC_DIR.is_dir():
        path = request.url.path
        is_client_route = (
            request.method == "GET"
            and not path.startswith("/api")
            and not path.startswith("/ws")
            and "." not in path.rsplit("/", 1)[-1]
        )
        if is_client_route:
            index_file = STATIC_DIR / "index.html"
            if index_file.is_file():
                return FileResponse(index_file)

    return JSONResponse(status_code=404, content={"detail": "Not Found"})
