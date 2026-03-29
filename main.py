import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from app.db.database import init_db
from app.services.monitor_service import monitor_service
from app.services.speaker_service import speaker_service
from app.services.stt_service import stt_service
from app.services.tts_service import tts_service
from app.routers import conversations, health, models, profiles
from app.routers import websocket as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("═" * 50)
    logger.info("  OllamaBuddy starting up")
    logger.info("═" * 50)

    await init_db()
    logger.info("Database ready")

    await stt_service.initialize()
    await tts_service.initialize()
    await speaker_service.initialize()

    monitor_task = asyncio.create_task(monitor_service.run_loop())

    yield

    logger.info("Shutting down…")
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


# Create directories before FastAPI mounts them (StaticFiles checks at import time)
os.makedirs("data/voices", exist_ok=True)
os.makedirs("data/avatars", exist_ok=True)
os.makedirs("data/whisper_models", exist_ok=True)

app = FastAPI(title="OllamaBuddy", version="0.1.0", lifespan=lifespan)

app.include_router(ws_router.router)
app.include_router(conversations.router, prefix="/api/conversations")
app.include_router(profiles.router, prefix="/api/profiles")
app.include_router(models.router, prefix="/api/models")
app.include_router(health.router, prefix="/api")

app.mount("/data/avatars", StaticFiles(directory="data/avatars"), name="avatars")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="OllamaBuddy server")
    parser.add_argument("--host", default=settings.host, help="Bind host (default: %(default)s)")
    parser.add_argument("--port", type=int, default=settings.port, help="Bind port (default: %(default)s)")
    parser.add_argument("--reload", action="store_true", default=settings.debug, help="Enable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
