"""
Drawing API Router
畫布相關的 API 端點
"""

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..services.drawing_service import DrawingService

# 創建 router
router = APIRouter(prefix="/api/drawing", tags=["Drawing"])

# 全域變數（會在 app.py 中設定）
drawing_service: 'DrawingService' = None


def init_router(service: 'DrawingService'):
    """初始化 router，注入 service"""
    global drawing_service
    drawing_service = service


@router.post("/start")
async def start_drawing_session(
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
        >>> response = await start_drawing_session("index_finger", "blue", True)
        >>> response.json()
        {'status': 'success', 'session_id': 'draw123', 'canvas_size': [800, 600]}
    """
    result = drawing_service.start_drawing_session(mode, color, auto_recognize)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動繪畫會話失敗"))
    return JSONResponse(result)


@router.post("/stop")
async def stop_drawing_session() -> JSONResponse:
    """
    Stop AI drawing recognition session.

    Terminates the current drawing session and saves any final drawings.
    Cleans up canvas resources and gesture tracking.

    Returns:
        JSONResponse: Session termination status with final results.

    Example:
        >>> response = await stop_drawing_session()
        >>> response.json()
        {'status': 'success', 'drawings_saved': 3, 'session_duration': 120}
    """
    result = drawing_service.stop_drawing_session()
    return JSONResponse(result)


@router.get("/status")
async def get_drawing_status() -> JSONResponse:
    """
    Get current AI drawing session status.

    Retrieves real-time drawing session information including current canvas
    state, drawing statistics, and recognition results.

    Returns:
        JSONResponse: Current drawing session status and statistics.

    Example:
        >>> response = await get_drawing_status()
        >>> response.json()
        {
            'status': 'active',
            'current_stroke_count': 45,
            'recognized_shapes': ['circle', 'square'],
            'canvas_size': [800, 600]
        }
    """
    return JSONResponse(drawing_service.get_drawing_status())


@router.post("/recognize")
async def recognize_drawing() -> JSONResponse:
    """
    Manually trigger AI recognition of current drawing.

    Forces immediate analysis of the current canvas content using AI vision
    models to identify shapes, objects, or patterns in the drawing.

    Returns:
        JSONResponse: Recognition results with identified elements and confidence.

    Example:
        >>> response = await recognize_drawing()
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


@router.post("/clear")
async def clear_canvas() -> JSONResponse:
    """
    Clear the drawing canvas.

    Resets the virtual canvas to a blank state, removing all drawn content
    while preserving session settings and recognition history.

    Returns:
        JSONResponse: Canvas clear operation status.

    Example:
        >>> response = await clear_canvas()
        >>> response.json()
        {'status': 'success', 'message': 'Canvas cleared', 'previous_drawings': 2}
    """
    result = drawing_service.clear_canvas()
    return JSONResponse(result)
