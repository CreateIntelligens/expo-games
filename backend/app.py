# =============================================================================
# backend/app.py - FastAPI Application for AI Interactive Games
# =============================================================================
# This module implements a comprehensive FastAPI web application that provides
# multiple AI-powered interactive experiences including emotion analysis, action
# detection, hand gesture recognition, rock-paper-scissors games, and AI drawing
# recognition. Refactored using FastAPI Router architecture for better modularity.
# =============================================================================

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware

from .config.settings import APP_TITLE, CORS_ALLOW_ORIGINS, MAX_UPLOAD_SIZE_BYTES
from .services.emotion_service import EmotionService
from .services.action_detection_service import ActionDetectionService
from .services.hand_gesture_service import HandGestureService
from .services.rps_game_service import RPSGameService
from .services.drawing_service import DrawingService
from .services.status_broadcaster import StatusBroadcaster
from .utils.gpu_runtime import get_gpu_status_dict

# Import all routers
from .routers import emotion, action, hand_gesture, drawing, websockets


# Project directory structure setup
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"

# Initialize core services with shared status broadcaster
status_broadcaster = StatusBroadcaster()
emotion_service = EmotionService(status_broadcaster)
action_service = ActionDetectionService(status_broadcaster)
hand_gesture_service = HandGestureService(status_broadcaster)
rps_game_service = RPSGameService(status_broadcaster)  # MediaPipe 手勢辨識版本
drawing_service = DrawingService(status_broadcaster)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager for FastAPI.

    Handles application startup and shutdown events. During startup, it sets
    the asyncio event loop for the status broadcaster service to ensure proper
    async operations throughout the application lifecycle.

    Args:
        app (FastAPI): The FastAPI application instance.

    Yields:
        None: Control is yielded back to FastAPI after startup setup.

    Note:
        This replaces the deprecated @app.on_event("startup") decorator
        with the modern lifespan event handler.
    """
    loop = asyncio.get_running_loop()
    status_broadcaster.set_loop(loop)
    yield


app = FastAPI(
    title=APP_TITLE,
    description="AI Interactive Games Platform with Emotion Analysis, Action Detection, Hand Gestures, RPS Game, and AI Drawing",
    version="0.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# =============================================================================
# Initialize routers with service injection
# =============================================================================

emotion.init_router(emotion_service)
action.init_router(action_service)
hand_gesture.init_router(hand_gesture_service)
drawing.init_router(drawing_service)
websockets.init_router(
    rps_service=rps_game_service,
    broadcaster=status_broadcaster,
    emotion_svc=emotion_service,
    drawing_svc=drawing_service
)


# =============================================================================
# Include all routers
# =============================================================================

app.include_router(emotion.router)
app.include_router(action.router)
app.include_router(hand_gesture.router)
app.include_router(drawing.router)
app.include_router(websockets.router)


# =============================================================================
# Frontend page routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def render_emotion_page(request: Request) -> HTMLResponse:
    """
    Render the main emotion and action detection page.

    Serves the HTML template for the web interface that allows users to interact
    with emotion analysis and action detection features through both manual controls
    and real-time WebSocket updates.

    Args:
        request (Request): The incoming HTTP request object.

    Returns:
        HTMLResponse: Rendered HTML page with application title and file size limits.

    Example:
        >>> response = await render_emotion_page(request)
        >>> response.status_code
        200
    """
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": APP_TITLE,
            "max_file_size_mb": MAX_UPLOAD_SIZE_BYTES // (1024 * 1024),
        },
    )


@app.get("/docs/ws", response_class=HTMLResponse)
async def render_websocket_docs(request: Request) -> HTMLResponse:
    """
    Render the WebSocket API documentation page.

    Provides an interactive documentation interface for all WebSocket endpoints
    with real-time testing capabilities and detailed message format specifications.

    Args:
        request (Request): The incoming HTTP request object.

    Returns:
        HTMLResponse: Interactive WebSocket API documentation page.

    Example:
        >>> response = await render_websocket_docs(request)
        >>> response.status_code
        200
    """
    return templates.TemplateResponse(
        request,
        "websocket-docs.html",
        {
            "title": f"{APP_TITLE} - WebSocket API 文檔",
        },
    )


# =============================================================================
# System API routes
# =============================================================================

@app.get("/api/system/gpu")
async def gpu_status() -> dict:
    """
    Return TensorFlow / MediaPipe GPU availability details.

    Provides system-level information about GPU acceleration capabilities
    for TensorFlow and MediaPipe libraries.

    Returns:
        dict: GPU status information including availability and device details.

    Example:
        >>> response = await gpu_status()
        >>> response
        {
            'tensorflow_gpu_available': True,
            'gpu_devices': ['/physical_device:GPU:0'],
            'mediapipe_gpu_available': False
        }
    """
    return get_gpu_status_dict()
