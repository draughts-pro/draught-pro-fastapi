from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from contextlib import asynccontextmanager
import asyncio

from app.core.config import settings
from app.websockets.game_handler import sio
from app.services.room_manager import room_manager

async def cleanup_task():
    """Periodically clean up inactive rooms"""
    while True:
        await asyncio.sleep(settings.ROOM_CLEANUP_INTERVAL_SECONDS)
        room_manager.cleanup_inactive_rooms()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    cleanup_task_handle = asyncio.create_task(cleanup_task())
    yield
    cleanup_task_handle.cancel()


app = FastAPI(
    title="Checkers Multiplayer API",
    description="Real-time multiplayer checkers game backend",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "active_rooms": len(room_manager.rooms),
        "environment": settings.ENV,
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Checkers Multiplayer API",
        "version": "1.0.0",
        "websocket_path": "/socket.io/",
    }


socket_app = socketio.ASGIApp(
    sio,
    other_asgi_app=app,
    socketio_path="socket.io",
)

app_with_socketio = socket_app
