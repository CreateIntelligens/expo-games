"""
RPS (Rock-Paper-Scissors) Game API Router
剪刀石頭布遊戲相關的 API 端點
"""

import os
import tempfile
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse

if TYPE_CHECKING:
    from ..services.rps_game_service import RPSGameService

# 常數
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# 創建 router
router = APIRouter(prefix="/api/rps", tags=["RPS Game"])

# 全域變數（會在 app.py 中設定）
rps_game_service: 'RPSGameService' = None


def init_router(service: 'RPSGameService'):
    """初始化 router，注入 service"""
    global rps_game_service
    rps_game_service = service


@router.post("/start")
async def start_game(request: Request) -> JSONResponse:
    """
    Start rock-paper-scissors game session (MediaPipe version).

    Initiates an interactive rock-paper-scissors game using MediaPipe hand gesture recognition.
    Players upload images of their hand gestures, and the system detects rock/paper/scissors
    with high accuracy.

    Args:
        request (Request): Request containing target_score in JSON body.

    Returns:
        JSONResponse: Game initialization status with session details.

    Raises:
        HTTPException: If game service fails to start or invalid parameters provided.

    Example:
        >>> response = await start_game(request)
        >>> response.json()
        {'status': 'success', 'target_score': 5}
    """
    body = await request.json()
    target_score = body.get("target_score", 3)

    result = rps_game_service.start_game(target_score)
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=result.get("message", "啟動遊戲失敗"))
    return JSONResponse(result)


@router.post("/stop")
async def stop_game() -> JSONResponse:
    """
    Stop rock-paper-scissors game session.

    Terminates the current game session and cleans up associated resources.
    Saves final scores and game statistics before shutdown.

    Returns:
        JSONResponse: Game termination status with final results.

    Example:
        >>> response = await stop_game()
        >>> response.json()
        {'status': 'success', 'final_score': {'player': 3, 'ai': 2}}
    """
    result = rps_game_service.stop_game()
    return JSONResponse(result)


@router.get("/status")
async def get_status() -> JSONResponse:
    """
    Get current rock-paper-scissors game status.

    Retrieves real-time game state including current scores, round number,
    game mode, and session statistics.

    Returns:
        JSONResponse: Current game status and statistics.

    Example:
        >>> response = await get_status()
        >>> response.json()
        {
            'status': 'active',
            'current_round': 2,
            'scores': {'player': 1, 'computer': 1},
            'target_score': 3
        }
    """
    return JSONResponse(rps_game_service.get_game_status())


@router.post("/submit")
async def submit_gesture(file: UploadFile = File(...)) -> JSONResponse:
    """
    [已棄用] 提交玩家手勢圖片進行辨識

    注意：此端點已由整合式 WebSocket 架構取代。
    新的實作中，手勢辨識透過 /ws/rps 端點的即時串流處理，
    無需手動上傳圖片，系統會自動辨識並設定玩家手勢。

    舊版功能說明：
    接受玩家手勢圖片上傳（石頭/布/剪刀），使用 MediaPipe 模型進行高精度辨識。

    Args:
        file (UploadFile): 包含手勢的圖片檔案

    Returns:
        JSONResponse: 辨識結果包含手勢類型和信心度

    Note:
        此端點保留以維持向後相容性，但建議使用新的 WebSocket 串流辨識
    """
    # 驗證檔案
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供檔案")

    # 驗證檔案格式
    file_ext = os.path.splitext(file.filename.lower())[1]
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

    if file_ext not in image_exts:
        raise HTTPException(
            status_code=400,
            detail=f"不支援的圖片格式: {file_ext}，請使用 JPG, PNG, BMP, WEBP"
        )

    # 讀取檔案
    file_content = await file.read()
    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        limit_mb = MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"檔案過大，最大允許 {limit_mb}MB")

    # 建立臨時檔案
    suffix = file_ext or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_content)
        temp_path = tmp.name

    try:
        # 提交手勢給遊戲服務
        result = rps_game_service.submit_player_gesture(temp_path)

        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))

        return JSONResponse(result)

    finally:
        # 清理臨時檔案
        if os.path.exists(temp_path):
            os.unlink(temp_path)
