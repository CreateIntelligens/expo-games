"""
Emotion Analysis API Router
情緒分析相關的 API 端點
"""

import json
import os
import tempfile
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse

if TYPE_CHECKING:
    from ..services.emotion_service import EmotionService

from ..config.settings import MAX_UPLOAD_SIZE_BYTES

# 創建 router
router = APIRouter(prefix="/api/emotion", tags=["Emotion Analysis"])

# 全域變數（會在 app.py 中設定）
emotion_service: 'EmotionService' = None


def init_router(service: 'EmotionService'):
    """初始化 router，注入 service"""
    global emotion_service
    emotion_service = service


@router.post("/analyze/image")
async def analyze_image(file: UploadFile = File(...)) -> JSONResponse:
    """
    圖片情緒分析 - 使用 DeepFace 進行圖片情緒檢測

    分析上傳的圖片檔案，檢測人臉情緒並返回分析結果。

    Args:
        file (UploadFile): 上傳的圖片檔案

    Returns:
        JSONResponse: DeepFace 情緒分析結果，包含中文/英文名稱和信心度

    Example:
        >>> response = await analyze_image(image_file)
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


@router.post("/analyze/video")
async def analyze_video(
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
