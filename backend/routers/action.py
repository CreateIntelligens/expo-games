# =============================================================================
# backend/routers/action.py - Action Detection API Router
#
# This module provides FastAPI router endpoints for action detection functionality.
# Handles real-time action detection, video analysis, and detection status management.
#
# Dependencies: fastapi, action_detection_service
# Key Features: Real-time detection, video analysis, status monitoring
# =============================================================================

"""
Action Detection API Router
動作偵測相關的 API 端點
"""

import os
import tempfile
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..services.action_detection_service import ActionDetectionService

from ..config.settings import MAX_UPLOAD_SIZE_BYTES

# 創建 router
router = APIRouter(prefix="/api/action", tags=["Action Detection"])

# 全域變數（會在 app.py 中設定）
action_service: 'ActionDetectionService' = None


def init_router(service: 'ActionDetectionService'):
    """初始化 router，注入 service"""
    global action_service
    action_service = service


@router.post("/start")
async def start_detection(difficulty: str = Form("easy")) -> JSONResponse:
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
        >>> response = await start_detection("medium")
        >>> response.json()
        {'status': 'success', 'message': 'Action detection started'}
    """
    result = action_service.start_action_detection(difficulty)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動動作檢測失敗"))
    return JSONResponse(result)


@router.post("/stop")
async def stop_detection() -> JSONResponse:
    """
    Stop action detection process.

    Terminates the currently running action detection process and releases
    associated resources.

    Returns:
        JSONResponse: Status response indicating successful stop or error details.

    Example:
        >>> response = await stop_detection()
        >>> response.json()
        {'status': 'success', 'message': 'Action detection stopped'}
    """
    result = action_service.stop_action_detection()
    return JSONResponse(result)


@router.get("/status")
async def get_status() -> JSONResponse:
    """
    Get current action detection status.

    Retrieves the current state of the action detection service, including
    whether it's running, difficulty level, and detection statistics.

    Returns:
        JSONResponse: Current status information of action detection service.

    Example:
        >>> response = await get_status()
        >>> response.json()
        {'status': 'running', 'difficulty': 'easy', 'detections': 8}
    """
    return JSONResponse(action_service.get_detection_status())


@router.post("/analyze")
async def analyze_video(file: UploadFile = File(...)) -> JSONResponse:
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
        >>> response = await analyze_video(video_file)
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
