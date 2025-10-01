"""
Hand Gesture API Router
手勢偵測相關的 API 端點
"""

from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..services.hand_gesture_service import HandGestureService

# 創建 router
router = APIRouter(prefix="/api/gesture", tags=["Hand Gesture"])

# 全域變數（會在 app.py 中設定）
hand_gesture_service: 'HandGestureService' = None


def init_router(service: 'HandGestureService'):
    """初始化 router，注入 service"""
    global hand_gesture_service
    hand_gesture_service = service


@router.post("/start")
async def start_gesture_detection(duration: Optional[int] = Form(None)) -> JSONResponse:
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
        >>> response = await start_gesture_detection(60)
        >>> response.json()
        {'status': 'success', 'message': 'Gesture detection started'}
    """
    result = hand_gesture_service.start_gesture_detection(duration)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動手勢檢測失敗"))
    return JSONResponse(result)


@router.post("/stop")
async def stop_gesture_detection() -> JSONResponse:
    """
    Stop hand gesture detection process.

    Terminates the currently running gesture detection process and releases
    associated resources.

    Returns:
        JSONResponse: Status response indicating successful stop or error details.

    Example:
        >>> response = await stop_gesture_detection()
        >>> response.json()
        {'status': 'success', 'message': 'Gesture detection stopped'}
    """
    result = hand_gesture_service.stop_gesture_detection()
    return JSONResponse(result)


@router.get("/status")
async def get_gesture_status() -> JSONResponse:
    """
    Get current hand gesture detection status.

    Retrieves the current state of the gesture detection service, including
    whether it's running, detection statistics, and current gesture information.

    Returns:
        JSONResponse: Current status information of gesture detection service.

    Example:
        >>> response = await get_gesture_status()
        >>> response.json()
        {'status': 'running', 'uptime': 30, 'current_gesture': 'thumbs_up'}
    """
    return JSONResponse(hand_gesture_service.get_detection_status())


@router.get("/current")
async def get_current_gesture() -> JSONResponse:
    """
    Get current detected hand gesture.

    Retrieves the most recently detected hand gesture from the camera feed.
    Useful for real-time gesture-based interactions.

    Returns:
        JSONResponse: Current gesture information with confidence score.

    Example:
        >>> response = await get_current_gesture()
        >>> response.json()
        {'gesture': 'peace_sign', 'confidence': 0.92, 'timestamp': 1640995200}
    """
    return JSONResponse(hand_gesture_service.get_current_gesture())
