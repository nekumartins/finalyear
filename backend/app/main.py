"""
Debate Coach Backend — FastAPI Application Entry Point

Run locally:
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

Run via Docker:
    docker compose up --build
"""
import logging
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.routers.api import router as api_router
from backend.app.routers.auth import router as auth_router
from backend.app.routers.ws_handler import DebateWebSocketHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Debate Coach API",
    description="Real-Time AI Debate Coach with Predictive Turn-Taking",
    version="0.1.0",
)

# CORS — allow frontend to connect (dev: Vite on localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
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


# ── Static Frontend (Docker production build) ─────────────
# In Docker, the Vite build output is copied to /app/static/
# Serve it as a single-page app (catch-all → index.html)
STATIC_DIR = Path("/app/static")
if STATIC_DIR.is_dir():
    logger.info(f"📦 Serving frontend from {STATIC_DIR}")
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
else:
    logger.info("🔧 No static frontend found (running in dev mode)")


@app.on_event("startup")
async def startup():
    logger.info(f"🎙️ Debate Coach Backend starting (mode={settings.default_mode})")
    logger.info(f"📡 WebSocket endpoint: ws://{settings.host}:{settings.port}/ws/debate")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Debate Coach Backend shutting down")
