# =============================================================================
# mediapipe_rps_detector.py - MediaPipe 剪刀石頭布手勢辨識器
# 使用 MediaPipe Tasks 的預訓練手勢辨識模型
# =============================================================================

import logging
import os
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class RPSGesture(Enum):
    """手勢類型枚舉"""
    ROCK = "rock"          # 石頭 ✊ - Closed_Fist
    PAPER = "paper"        # 布 ✋ - Open_Palm
    SCISSORS = "scissors"  # 剪刀 ✌️ - Victory
    UNKNOWN = "unknown"    # 未知


# 嘗試載入 MediaPipe
try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR = None
except ImportError as exc:
    mp = None
    python = None
    vision = None
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)


class MediaPipeRPSDetector:
    """
    MediaPipe 剪刀石頭布手勢辨識器

    特點：
    - 使用 Google MediaPipe 預訓練模型
    - 準確率高，辨識速度快
    - 完全獨立，不依賴其他服務
    - 支援圖片檔案或 numpy array 輸入
    """

    # MediaPipe 手勢名稱對應到 RPS 手勢
    GESTURE_MAPPING = {
        "Closed_Fist": RPSGesture.ROCK,       # 握拳 = 石頭
        "Open_Palm": RPSGesture.PAPER,        # 張開手掌 = 布
        "Victory": RPSGesture.SCISSORS,       # 勝利手勢 = 剪刀
        # 備用映射
        "Thumb_Up": RPSGesture.ROCK,          # 豎拇指也算石頭
        "ILoveYou": RPSGesture.PAPER,         # 我愛你手勢（三指展開）也算布
    }

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化 MediaPipe 辨識器

        Args:
            model_path: 模型路徑，預設會自動下載
        """
        self.model_available = _MEDIAPIPE_AVAILABLE
        self.init_error = _MEDIAPIPE_ERROR
        self.recognizer = None

        # 預設模型路徑
        if model_path is None:
            base_dir = Path(__file__).resolve().parent.parent
            model_path = base_dir / "models" / "gesture_recognizer.task"

        self.model_path = Path(model_path)

        if self.model_available:
            self._download_model()
            self._load_model()
        else:
            logger.warning("MediaPipe 未安裝，辨識器無法使用: %s", self.init_error)

    def _download_model(self):
        """下載 MediaPipe 模型（如果不存在）"""
        if self.model_path.exists():
            logger.info("MediaPipe 模型已存在: %s", self.model_path)
            return

        # 確保目錄存在
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            model_url = "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/1/gesture_recognizer.task"
            logger.info("下載 MediaPipe 模型: %s -> %s", model_url, self.model_path)
            urllib.request.urlretrieve(model_url, str(self.model_path))
            logger.info("✅ MediaPipe 模型下載成功")
        except Exception as exc:
            self.model_available = False
            self.init_error = f"下載模型失敗: {exc}"
            logger.error(self.init_error)

    def _load_model(self):
        """載入 MediaPipe 模型"""
        if not self.model_path.exists():
            self.model_available = False
            self.init_error = f"模型檔案不存在: {self.model_path}"
            logger.error(self.init_error)
            return

        try:
            # 建立 GestureRecognizer（舊版 MediaPipe 0.10.11 不支援 Delegate）
            base_options = python.BaseOptions(model_asset_path=str(self.model_path))
            options = vision.GestureRecognizerOptions(
                base_options=base_options,
                num_hands=1,  # 只辨識一隻手
                min_hand_detection_confidence=0.3,  # 降低閾值以提高偵測率
                min_hand_presence_confidence=0.3,
                min_tracking_confidence=0.3
            )
            self.recognizer = vision.GestureRecognizer.create_from_options(options)

            logger.info("✅ MediaPipe 手勢辨識器載入成功: %s", self.model_path.name)

        except Exception as exc:
            self.model_available = False
            self.init_error = str(exc)
            logger.exception("載入 MediaPipe 模型失敗: %s", exc)

    def is_available(self) -> bool:
        """檢查辨識器是否可用"""
        return self.model_available and self.recognizer is not None

    def detect(self, image: Union[str, Path, np.ndarray]) -> Tuple[RPSGesture, float]:
        """
        辨識手勢

        Args:
            image: 圖片路徑或 numpy array (BGR 格式)

        Returns:
            (gesture, confidence): 手勢類型和信心度 (0-1)
        """
        if not self.is_available():
            return RPSGesture.UNKNOWN, 0.0

        try:
            # 載入圖片
            if isinstance(image, (str, Path)):
                # MediaPipe 需要 RGB 格式
                img_bgr = cv2.imread(str(image))
                if img_bgr is None:
                    logger.error("無法載入圖片: %s", image)
                    return RPSGesture.UNKNOWN, 0.0
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            else:
                # 輸入是 numpy array (BGR)
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # 建立 MediaPipe Image 物件
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

            # 辨識手勢
            result = self.recognizer.recognize(mp_image)

            # 處理結果
            if not result.gestures:
                # 檢查是否偵測到手部但沒有手勢
                if result.hand_landmarks:
                    logger.info("偵測到手部但無法辨識手勢")
                else:
                    logger.info("未偵測到手部")
                return RPSGesture.UNKNOWN, 0.0

            # 取得最高信心度的手勢
            top_gesture = result.gestures[0][0]
            gesture_name = top_gesture.category_name
            confidence = top_gesture.score

            # 顯示所有偵測到的手勢（前3名）
            if len(result.gestures[0]) > 1:
                logger.info("所有偵測到的手勢:")
                for i, g in enumerate(result.gestures[0][:3]):
                    logger.info("  %d. %s (%.3f)", i+1, g.category_name, g.score)

            logger.info(
                "MediaPipe 辨識: %s (信心度: %.3f)",
                gesture_name,
                confidence
            )

            # 映射到 RPS 手勢
            rps_gesture = self.GESTURE_MAPPING.get(gesture_name, RPSGesture.UNKNOWN)

            if rps_gesture == RPSGesture.UNKNOWN:
                logger.warning(
                    "無法映射手勢 '%s' 到 RPS，可能是其他手勢（如 Pointing_Up, Thumb_Down 等）",
                    gesture_name
                )

            return rps_gesture, confidence

        except Exception as exc:
            logger.exception("MediaPipe 辨識錯誤: %s", exc)
            return RPSGesture.UNKNOWN, 0.0

    def detect_batch(self, images: list) -> list:
        """
        批次辨識多張圖片

        Args:
            images: 圖片路徑或 numpy array 列表

        Returns:
            [(gesture, confidence), ...] 列表
        """
        results = []
        for image in images:
            result = self.detect(image)
            results.append(result)
        return results


# 全域單例（可選）
_detector_instance: Optional[MediaPipeRPSDetector] = None


def get_detector() -> MediaPipeRPSDetector:
    """取得全域 MediaPipe 辨識器實例（單例模式）"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = MediaPipeRPSDetector()
    return _detector_instance


__all__ = ["MediaPipeRPSDetector", "RPSGesture", "get_detector"]
