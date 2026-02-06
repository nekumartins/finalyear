"""
Debate Coach Backend — FastAPI Application Entry Point

Run with:
    conda activate debate-coach
    uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
"""
import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import get_settings
from backend.app.routers.api import router as api_router
from backend.app.routers.ws_handler import DebateWebSocketHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="Debate Coach API",
    description="Real-Time AI Debate Coach with Predictive Turn-Taking",
    version="0.1.0",
)

# CORS — allow mobile app to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REST routes
app.include_router(api_router)


# WebSocket endpoint
@app.websocket("/ws/debate")
async def websocket_debate(websocket: WebSocket):
    handler = DebateWebSocketHandler(websocket)
    await handler.handle()


@app.on_event("startup")
async def startup():
    logger.info(f"🎙️ Debate Coach Backend starting (mode={settings.default_mode})")
    logger.info(f"📡 WebSocket endpoint: ws://{settings.host}:{settings.port}/ws/debate")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Debate Coach Backend shutting down")
