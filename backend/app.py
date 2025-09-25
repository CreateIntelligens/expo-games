# =============================================================================
# backend/app.py - FastAPI Application for AI Interactive Games
# =============================================================================
# This module implements a comprehensive FastAPI web application that provides
# multiple AI-powered interactive experiences including emotion analysis, action
# detection, hand gesture recognition, rock-paper-scissors games, and AI drawing
# recognition. It includes REST API endpoints for controlling various services
# and WebSocket endpoints for real-time updates across all interactive modules.
# The application uses computer vision and machine learning services to create
# engaging interactive experiences for exhibitions and entertainment venues.
# =============================================================================

import asyncio
import base64
import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect

from .config.settings import APP_TITLE, CORS_ALLOW_ORIGINS, MAX_UPLOAD_SIZE_BYTES
from .services.emotion_service import EmotionService
from .services.action_detection_service import ActionDetectionService
from .services.hand_gesture_service import HandGestureService
from .services.rps_game_service import RPSGameService
from .services.drawing_service import DrawingService
from .services.status_broadcaster import StatusBroadcaster


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
rps_game_service = RPSGameService(status_broadcaster, hand_gesture_service)
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


app = FastAPI(title=APP_TITLE, description="Standalone emotion analysis service",
              version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


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
        "emotion_action.html",
        {
            "request": request,
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
        "websocket-docs.html",
        {
            "request": request,
            "title": f"{APP_TITLE} - WebSocket API 文檔",
        },
    )











@app.post("/api/emotion/analyze/image")
async def api_analyze_emotion_image(file: UploadFile = File(...)) -> JSONResponse:
    """
    圖片情緒分析 - 使用 DeepFace 進行圖片情緒檢測

    分析上傳的圖片檔案，檢測人臉情緒並返回分析結果。

    Args:
        file (UploadFile): 上傳的圖片檔案

    Returns:
        JSONResponse: DeepFace 情緒分析結果，包含中文/英文名稱和信心度

    Example:
        >>> response = await api_analyze_emotion_image(image_file)
        >>> response.json()
        {
            'emotion_zh': '開心',
            'emotion_en': 'happy',
            'emoji': '😊',
            'confidence': 0.92
        }
    """
    # Validate file presence
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供檔案")

    # Extract and validate file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".gif"}

    if file_ext not in image_exts:
        raise HTTPException(
            status_code=400, detail=f"DeepFace 僅支援圖片格式，收到: {file_ext}")

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        limit_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"檔案過大，最大允許 {limit_mb}MB")

    # Create temporary file for processing
    suffix = file_ext or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_content)
        temp_path = tmp.name

    try:
        # Use local DeepFace analysis
        result = emotion_service.analyze_image_deepface(temp_path)
        return JSONResponse(result)

    except Exception as e:
        return JSONResponse({
            'emotion_zh': '中性',
            'emotion_en': 'neutral',
            'emoji': '😐',
            'confidence': 0.0,
            'error': f"DeepFace 分析錯誤: {str(e)}"
        })
    finally:
        # Cleanup temporary file
        if os.path.exists(temp_path):
            os.unlink(temp_path)





@app.post("/api/emotion/analyze/video")
async def api_analyze_emotion_video(
    file: UploadFile = File(...),
    frame_interval: float = Form(0.5)
) -> StreamingResponse:
    """
    影片情緒分析 - 使用 DeepFace 進行影片情緒檢測

    逐幀截取影片並使用DeepFace進行情緒分析，以Server-Sent Events串流返回結果。

    Args:
        file (UploadFile): 上傳的影片檔案
        frame_interval (float): 截幀間隔(秒)，默認0.5秒

    Returns:
        StreamingResponse: SSE格式的串流分析結果
    """
    # 驗證檔案
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供檔案")

    # 檢查檔案格式
    file_ext = os.path.splitext(file.filename.lower())[1]
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}

    if file_ext not in video_exts:
        raise HTTPException(status_code=400, detail=f"僅支援影片格式，收到: {file_ext}")

    # 檢查檔案大小
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        limit_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"檔案過大，最大允許 {limit_mb}MB")

    # 驗證截幀間隔
    if frame_interval < 0.1 or frame_interval > 5.0:
        raise HTTPException(status_code=400, detail="截幀間隔必須在0.1-5.0秒之間")

    # 創建臨時檔案
    suffix = file_ext or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_content)
        temp_path = tmp.name

    def generate_stream():
        """產生SSE格式的串流數據"""
        try:
            for result in emotion_service.analyze_video_deepface_stream(temp_path, frame_interval):
                # 格式化為SSE格式
                data = json.dumps(result, ensure_ascii=False)
                yield f"data: {data}\n\n"

                # 如果完成則結束
                if result.get("completed", False):
                    break

        except Exception as e:
            # 發送錯誤信息
            error_data = {
                "error": f"串流分析錯誤: {str(e)}",
                "frame_time": 0,
                "completed": True
            }
            yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"
        finally:
            # 清理臨時檔案
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.post("/api/action/start")
async def api_start_action_detection(difficulty: str = Form("easy")) -> JSONResponse:
    """
    Start action detection process.

    Initiates real-time human action detection with configurable difficulty levels.
    Supports different detection sensitivities for various use cases.

    Args:
        difficulty (str): Detection difficulty level ("easy", "medium", "hard").

    Returns:
        JSONResponse: Status response with success/error information.

    Raises:
        HTTPException: If action detection service fails to start.

    Example:
        >>> response = await api_start_action_detection("medium")
        >>> response.json()
        {'status': 'success', 'message': 'Action detection started'}
    """
    result = action_service.start_action_detection(difficulty)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動動作檢測失敗"))
    return JSONResponse(result)


@app.post("/api/action/stop")
async def api_stop_action_detection() -> JSONResponse:
    """
    Stop action detection process.

    Terminates the currently running action detection process and releases
    associated resources.

    Returns:
        JSONResponse: Status response indicating successful stop or error details.

    Example:
        >>> response = await api_stop_action_detection()
        >>> response.json()
        {'status': 'success', 'message': 'Action detection stopped'}
    """
    result = action_service.stop_action_detection()
    return JSONResponse(result)


@app.get("/api/action/status")
async def api_action_status() -> JSONResponse:
    """
    Get current action detection status.

    Retrieves the current state of the action detection service, including
    whether it's running, difficulty level, and detection statistics.

    Returns:
        JSONResponse: Current status information of action detection service.

    Example:
        >>> response = await api_action_status()
        >>> response.json()
        {'status': 'running', 'difficulty': 'easy', 'detections': 8}
    """
    return JSONResponse(action_service.get_detection_status())


@app.post("/api/action/analyze")
async def api_analyze_action_video(file: UploadFile = File(...)) -> JSONResponse:
    """
    Analyze action from uploaded video file.

    Processes uploaded video files to detect and analyze actions using computer vision.
    Supports various video formats with automatic type detection and validation.

    Args:
        file (UploadFile): The uploaded video file.

    Returns:
        JSONResponse: Analysis results with action detection data and file information.

    Raises:
        HTTPException: For invalid files, unsupported formats, or size limits exceeded.

    Example:
        >>> response = await api_analyze_action_video(video_file)
        >>> response.json()
        {
            'status': 'success',
            'results': {'primary_action': 'smile', 'confidence': 0.85},
            'file_info': {'name': 'video.mp4', 'type': 'video', 'size': 5242880}
        }
    """
    # Validate file presence
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供檔案")

    # Extract and validate file extension
    file_ext = os.path.splitext(file.filename.lower())[1]
    video_exts = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".webm"}

    if file_ext not in video_exts:
        raise HTTPException(
            status_code=400, detail=f"不支援的影片格式: {file_ext}，請使用 MP4, AVI, MOV, MKV, WMV, WEBM")

    # Read and validate file size
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        limit_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"檔案過大，最大允許 {limit_mb}MB")

    # Create temporary file for processing
    suffix = file_ext or ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_content)
        temp_path = tmp.name

    try:
        # Analyze video
        result = action_service.analyze_video(temp_path)

        # Return comprehensive analysis results
        return JSONResponse({
            "status": "success",
            "message": "動作分析完成",
            "results": result,
            "file_info": {
                "name": file.filename,
                "type": "video",
                "size": len(file_content),
            },
        })
    finally:
        # Ensure temporary file cleanup
        os.unlink(temp_path)


# =============================================================================
# 石頭剪刀布遊戲 API 路由
# =============================================================================

@app.post("/api/rps/start")
async def api_start_rps_game(
    mode: str = Form("vs_ai"),
    difficulty: str = Form("medium"),
    target_score: int = Form(3)
) -> JSONResponse:
    """
    Start rock-paper-scissors game session.

    Initiates an interactive rock-paper-scissors game with configurable game modes,
    difficulty levels, and scoring targets. Supports both AI opponent and potentially
    multiplayer modes.

    Args:
        mode (str): Game mode - "vs_ai" for AI opponent, "vs_player" for multiplayer.
        difficulty (str): AI difficulty level - "easy", "medium", "hard".
        target_score (int): Target score to win the game (default: 3).

    Returns:
        JSONResponse: Game initialization status with session details.

    Raises:
        HTTPException: If game service fails to start or invalid parameters provided.

    Example:
        >>> response = await api_start_rps_game("vs_ai", "medium", 5)
        >>> response.json()
        {'status': 'success', 'session_id': 'abc123', 'target_score': 5}
    """
    result = rps_game_service.start_game(mode, difficulty, target_score)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動遊戲失敗"))
    return JSONResponse(result)


@app.post("/api/rps/stop")
async def api_stop_rps_game() -> JSONResponse:
    """
    Stop rock-paper-scissors game session.

    Terminates the current game session and cleans up associated resources.
    Saves final scores and game statistics before shutdown.

    Returns:
        JSONResponse: Game termination status with final results.

    Example:
        >>> response = await api_stop_rps_game()
        >>> response.json()
        {'status': 'success', 'final_score': {'player': 3, 'ai': 2}}
    """
    result = rps_game_service.stop_game()
    return JSONResponse(result)


@app.get("/api/rps/status")
async def api_rps_game_status() -> JSONResponse:
    """
    Get current rock-paper-scissors game status.

    Retrieves real-time game state including current scores, round number,
    game mode, and session statistics.

    Returns:
        JSONResponse: Current game status and statistics.

    Example:
        >>> response = await api_rps_game_status()
        >>> response.json()
        {
            'status': 'active',
            'current_round': 2,
            'scores': {'player': 1, 'ai': 1},
            'target_score': 3
        }
    """
    return JSONResponse(rps_game_service.get_game_status())


# =============================================================================
# 手勢識別 API 路由
# =============================================================================

@app.post("/api/gesture/start")
async def api_start_gesture_detection(duration: Optional[int] = Form(None)) -> JSONResponse:
    """
    Start hand gesture detection process.

    Initiates real-time hand gesture recognition using computer vision.
    Detects various hand gestures and signs for interactive applications.

    Args:
        duration (Optional[int]): Detection duration in seconds. If None, runs continuously.

    Returns:
        JSONResponse: Status response with success/error information.

    Raises:
        HTTPException: If gesture detection service fails to start.

    Example:
        >>> response = await api_start_gesture_detection(60)
        >>> response.json()
        {'status': 'success', 'message': 'Gesture detection started'}
    """
    result = hand_gesture_service.start_gesture_detection(duration)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動手勢檢測失敗"))
    return JSONResponse(result)


@app.post("/api/gesture/stop")
async def api_stop_gesture_detection() -> JSONResponse:
    """
    Stop hand gesture detection process.

    Terminates the currently running gesture detection process and releases
    associated resources.

    Returns:
        JSONResponse: Status response indicating successful stop or error details.

    Example:
        >>> response = await api_stop_gesture_detection()
        >>> response.json()
        {'status': 'success', 'message': 'Gesture detection stopped'}
    """
    result = hand_gesture_service.stop_gesture_detection()
    return JSONResponse(result)


@app.get("/api/gesture/status")
async def api_gesture_status() -> JSONResponse:
    """
    Get current hand gesture detection status.

    Retrieves the current state of the gesture detection service, including
    whether it's running, detection statistics, and current gesture information.

    Returns:
        JSONResponse: Current status information of gesture detection service.

    Example:
        >>> response = await api_gesture_status()
        >>> response.json()
        {'status': 'running', 'uptime': 30, 'current_gesture': 'thumbs_up'}
    """
    return JSONResponse(hand_gesture_service.get_detection_status())


@app.get("/api/gesture/current")
async def api_current_gesture() -> JSONResponse:
    """
    Get current detected hand gesture.

    Retrieves the most recently detected hand gesture from the camera feed.
    Useful for real-time gesture-based interactions.

    Returns:
        JSONResponse: Current gesture information with confidence score.

    Example:
        >>> response = await api_current_gesture()
        >>> response.json()
        {'gesture': 'peace_sign', 'confidence': 0.92, 'timestamp': 1640995200}
    """
    return JSONResponse(hand_gesture_service.get_current_gesture())


# =============================================================================
# AI 畫布 API 路由
# =============================================================================

@app.post("/api/drawing/start")
async def api_start_drawing_session(
    mode: str = Form("index_finger"),
    color: str = Form("black"),
    auto_recognize: bool = Form(True)
) -> JSONResponse:
    """
    Start AI drawing recognition session.

    Initiates an interactive drawing session where users can draw on a virtual
    canvas using hand gestures. The system can automatically recognize drawings
    or allow manual recognition triggers.

    Args:
        mode (str): Drawing input mode - "index_finger" or "full_hand".
        color (str): Drawing color - "black", "red", "blue", etc.
        auto_recognize (bool): Whether to automatically recognize drawings.

    Returns:
        JSONResponse: Session initialization status with session details.

    Raises:
        HTTPException: If drawing service fails to start or invalid parameters.

    Example:
        >>> response = await api_start_drawing_session("index_finger", "blue", True)
        >>> response.json()
        {'status': 'success', 'session_id': 'draw123', 'canvas_size': [800, 600]}
    """
    result = drawing_service.start_drawing_session(mode, color, auto_recognize)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動繪畫會話失敗"))
    return JSONResponse(result)


@app.post("/api/drawing/stop")
async def api_stop_drawing_session() -> JSONResponse:
    """
    Stop AI drawing recognition session.

    Terminates the current drawing session and saves any final drawings.
    Cleans up canvas resources and gesture tracking.

    Returns:
        JSONResponse: Session termination status with final results.

    Example:
        >>> response = await api_stop_drawing_session()
        >>> response.json()
        {'status': 'success', 'drawings_saved': 3, 'session_duration': 120}
    """
    result = drawing_service.stop_drawing_session()
    return JSONResponse(result)


@app.get("/api/drawing/status")
async def api_drawing_status() -> JSONResponse:
    """
    Get current AI drawing session status.

    Retrieves real-time drawing session information including current canvas
    state, drawing statistics, and recognition results.

    Returns:
        JSONResponse: Current drawing session status and statistics.

    Example:
        >>> response = await api_drawing_status()
        >>> response.json()
        {
            'status': 'active',
            'current_stroke_count': 45,
            'recognized_shapes': ['circle', 'square'],
            'canvas_size': [800, 600]
        }
    """
    return JSONResponse(drawing_service.get_drawing_status())


@app.post("/api/drawing/recognize")
async def api_recognize_drawing() -> JSONResponse:
    """
    Manually trigger AI recognition of current drawing.

    Forces immediate analysis of the current canvas content using AI vision
    models to identify shapes, objects, or patterns in the drawing.

    Returns:
        JSONResponse: Recognition results with identified elements and confidence.

    Example:
        >>> response = await api_recognize_drawing()
        >>> response.json()
        {
            'status': 'success',
            'recognized': 'house',
            'confidence': 0.87,
            'bounding_box': [100, 150, 300, 250]
        }
    """
    result = drawing_service.recognize_current_drawing()
    return JSONResponse(result)


@app.post("/api/drawing/clear")
async def api_clear_canvas() -> JSONResponse:
    """
    Clear the drawing canvas.

    Resets the virtual canvas to a blank state, removing all drawn content
    while preserving session settings and recognition history.

    Returns:
        JSONResponse: Canvas clear operation status.

    Example:
        >>> response = await api_clear_canvas()
        >>> response.json()
        {'status': 'success', 'message': 'Canvas cleared', 'previous_drawings': 2}
    """
    result = drawing_service.clear_canvas()
    return JSONResponse(result)





@app.websocket("/ws/rps")
async def websocket_rps(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time RPS game updates.

    Establishes a persistent WebSocket connection to stream rock-paper-scissors
    game results in real-time. Clients receive live updates as the game progresses.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only RPS-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "rps":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@app.websocket("/ws/gesture")
async def websocket_gesture(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time hand gesture updates.

    Establishes a persistent WebSocket connection to stream hand gesture
    detection results in real-time. Clients receive live updates as gestures
    are detected from camera feeds.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only gesture-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "gesture":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@app.websocket("/ws/drawing")
async def websocket_drawing(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time drawing and AI recognition updates.

    Establishes a persistent WebSocket connection to stream drawing session
    and AI recognition results in real-time. Clients receive live updates as
    drawings are created and recognized.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only drawing-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "drawing":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@app.websocket("/ws/action")
async def websocket_action(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for real-time action detection updates.

    Establishes a persistent WebSocket connection to stream action detection
    results in real-time. Clients receive live updates as human actions are
    detected from camera feeds.

    Args:
        websocket (WebSocket): The WebSocket connection instance.

    Note:
        Connection automatically handles cleanup on client disconnect.
        Only action-related messages are forwarded to this endpoint.
    """
    await websocket.accept()
    queue = await status_broadcaster.register()
    try:
        while True:
            message = await queue.get()
            if message.get("channel") == "action":
                await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        await status_broadcaster.unregister(queue)


@app.websocket("/ws/emotion/stream")
async def websocket_emotion_stream(websocket: WebSocket) -> None:
    """
    WebSocket 影像串流情緒分析端點

    接收客戶端發送的影像幀，使用DeepFace進行即時情緒分析，
    並將分析結果即時返回給客戶端。

    支持的訊息格式:
    - 客戶端發送: {"type": "frame", "image": "base64_data", "timestamp": 123.45}
    - 服務器返回: {"type": "result", "emotion_zh": "開心", "confidence": 0.96, ...}

    Args:
        websocket (WebSocket): WebSocket連接實例
    """
    await websocket.accept()

    try:
        while True:
            # 接收客戶端消息
            data = await websocket.receive_json()

            # 處理心跳訊息
            if data.get("type") == "ping":
                await websocket.send_text("pong")
                continue

            if data.get("type") != "frame":
                await websocket.send_json({
                    "type": "error",
                    "message": "不支持的消息類型"
                })
                continue

            # 解析base64影像數據
            image_data = data.get("image", "")
            timestamp = data.get("timestamp", 0)

            try:
                # 處理base64影像數據
                if image_data.startswith("data:image/"):
                    # 移除data URL前綴
                    image_data = image_data.split(",")[1]

                # 解碼base64
                image_bytes = base64.b64decode(image_data)

                # 創建臨時檔案
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                    tmp_file.write(image_bytes)
                    temp_path = tmp_file.name

                try:
                    # 使用DeepFace分析情緒
                    result = emotion_service.analyze_image_deepface(temp_path)

                    # 添加時間戳和類型
                    result.update({
                        "type": "result",
                        "timestamp": timestamp,
                        "frame_time": timestamp
                    })

                    # 發送分析結果
                    await websocket.send_json(result)

                finally:
                    # 清理臨時檔案
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)

            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"影像分析錯誤: {str(e)}",
                    "timestamp": timestamp
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"WebSocket錯誤: {str(e)}"
            })
        except:
            pass
