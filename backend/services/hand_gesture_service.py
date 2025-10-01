# =============================================================================
# hand_gesture_service.py - 手勢識別服務
# 基於 MediaPipe Tasks GestureRecognizer 實作石頭剪刀布手勢檢測
# =============================================================================

import logging
import threading
import time
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..utils.gpu_runtime import configure_gpu_runtime

_GPU_STATUS = configure_gpu_runtime()

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        GestureRecognizer,
        GestureRecognizerOptions,
        GestureRecognizerResult,
        RunningMode,
    )
    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR: Optional[str] = None
except Exception as exc:
    mp = SimpleNamespace(
        solutions=SimpleNamespace(hands=None),
        Image=object  # 添加 Image 屬性避免錯誤
    )
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)
    # Mock missing classes for type hinting
    GestureRecognizerResult = object

from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts


logger = logging.getLogger(__name__)

if _GPU_STATUS.warnings:
    for warning in _GPU_STATUS.warnings:
        logger.warning("GPU setup warning: %s", warning)
else:
    logger.info(
        "HandGestureService GPU ready | TensorFlow devices: %s | MediaPipe GPU enabled: %s",
        _GPU_STATUS.tensorflow_devices,
        _GPU_STATUS.mediapipe_gpu_enabled,
    )


class HandGestureType(Enum):
    """手勢類型枚舉"""
    ROCK = "rock"      # 石頭 ✊
    PAPER = "paper"    # 布 ✋
    SCISSORS = "scissors"  # 剪刀 ✌️
    UNKNOWN = "unknown"

# MediaPipe 手勢名稱對應到 RPS 手勢
GESTURE_MAPPING = {
    "Closed_Fist": HandGestureType.ROCK,
    "Open_Palm": HandGestureType.PAPER,
    "Victory": HandGestureType.SCISSORS,
    "Thumb_Up": HandGestureType.ROCK,
    "ILoveYou": HandGestureType.PAPER,
}


class HandGestureDetector:
    """手勢檢測器，基於 MediaPipe Tasks GestureRecognizer"""

    def __init__(self, service: "HandGestureService"):
        self.service = service
        self.mediapipe_ready = _MEDIAPIPE_AVAILABLE
        self.init_error: Optional[str] = _MEDIAPIPE_ERROR
        self.recognizer: Optional[GestureRecognizer] = None

        if self.mediapipe_ready:
            try:
                model_path = Path(__file__).resolve().parent.parent / "models" / "gesture_recognizer.task"
                if not model_path.exists():
                    raise FileNotFoundError(f"模型檔案不存在: {model_path}")

                options = GestureRecognizerOptions(
                    base_options=BaseOptions(
                        model_asset_path=str(model_path)
                        # 舊版 MediaPipe 0.10.11 不支援 delegate 參數
                    ),
                    running_mode=RunningMode.LIVE_STREAM,
                    num_hands=1,
                    min_hand_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                    result_callback=self._result_callback,
                )
                self.recognizer = GestureRecognizer.create_from_options(options)
                logger.info("MediaPipe GestureRecognizer 初始化完成（CPU 模式）")
            except Exception as exc:
                self.mediapipe_ready = False
                self.init_error = str(exc)
                logger.exception("初始化 MediaPipe GestureRecognizer 失敗: %s", exc)
        else:
            logger.warning("MediaPipe GestureRecognizer 無法使用: %s", self.init_error)

    def _result_callback(self, result: GestureRecognizerResult, output_image: 'mp.Image', timestamp_ms: int):
        """MediaPipe 結果回呼"""
        if not self.service.is_detecting:
            return

        gesture = HandGestureType.UNKNOWN
        confidence = 0.0

        if result.gestures:
            top_gesture = result.gestures[0][0]
            gesture = GESTURE_MAPPING.get(top_gesture.category_name, HandGestureType.UNKNOWN)
            confidence = top_gesture.score

        if gesture != HandGestureType.UNKNOWN and confidence > 0.5:
            self.service.total_detections += 1
            self.service.current_gesture = gesture
            self.service.current_confidence = confidence

            # 手勢穩定性檢測
            if gesture == self.service.last_stable_gesture:
                self.service.gesture_stable_count += 1
            else:
                self.service.gesture_stable_count = 1
                self.service.last_stable_gesture = gesture

            # 記錄歷史
            self.service.gesture_history.append({
                "gesture": gesture.value,
                "confidence": round(confidence, 3),
                "timestamp": time.time(),
                "stable_count": self.service.gesture_stable_count
            })

    def recognize_async(self, frame: np.ndarray, timestamp_ms: int):
        """異步辨識手勢"""
        if not self.is_available():
            return

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.recognizer.recognize_async(mp_image, timestamp_ms)

    def is_available(self) -> bool:
        """回傳 MediaPipe 是否可用"""
        return self.mediapipe_ready and self.recognizer is not None

    def close(self):
        if self.recognizer:
            self.recognizer.close()


class HandGestureService:
    """手勢識別服務主類"""

    def __init__(self, status_broadcaster: StatusBroadcaster):
        self.status_broadcaster = status_broadcaster
        self.gesture_detector = HandGestureDetector(self)

        if not self.gesture_detector.is_available():
            logger.error(
                "MediaPipe GestureRecognizer 未啟用，手勢識別功能將不可用: %s",
                self.gesture_detector.init_error,
            )

        # 服務狀態
        self.is_detecting = False
        self.detection_thread = None
        self.camera = None

        # 檢測統計
        self.detection_start_time: Optional[float] = None
        self.total_detections = 0
        self.gesture_history: List[Dict] = []
        self.current_gesture = HandGestureType.UNKNOWN
        self.current_confidence = 0.0
        self.gesture_stable_count = 0
        self.last_stable_gesture = HandGestureType.UNKNOWN
        self.last_broadcast_time = 0

    def start_gesture_detection(self, duration: Optional[int] = None) -> Dict:
        """開始手勢檢測"""
        if not self.gesture_detector.is_available():
            error_msg = self.gesture_detector.init_error or "MediaPipe GestureRecognizer 初始化失敗"
            return {
                "status": "error",
                "message": f"無法啟動手勢檢測: {error_msg}",
            }

        if self.is_detecting:
            return {"status": "error", "message": "手勢檢測已在進行中"}

        try:
            # 開啟攝影機
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                return {"status": "error", "message": "無法開啟攝影機"}

            # 設定攝影機參數
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)

            # 重置統計
            self.detection_start_time = time.time()
            self.total_detections = 0
            self.gesture_history = []
            self.current_gesture = HandGestureType.UNKNOWN
            self.current_confidence = 0.0
            self.gesture_stable_count = 0
            self.last_stable_gesture = HandGestureType.UNKNOWN
            self.last_broadcast_time = 0

            # 開始檢測線程
            self.is_detecting = True
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                args=(duration,),
                daemon=True
            )
            self.detection_thread.start()

            # 廣播開始狀態
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "gesture",
                "stage": "started",
                "message": "手勢檢測已開始",
                "data": {
                    "duration": duration,
                    "start_time": self.detection_start_time
                }
            })

            return {
                "status": "started",
                "message": "手勢檢測已開始",
                "duration": duration
            }

        except Exception as exc:
            self.is_detecting = False
            return {"status": "error", "message": f"啟動失敗: {str(exc)}"}

    def stop_gesture_detection(self) -> Dict:
        """停止手勢檢測"""
        if not self.is_detecting:
            return {"status": "idle", "message": "手勢檢測未在進行中"}

        self.is_detecting = False

        if self.camera:
            self.camera.release()
            self.camera = None

        if self.detection_thread:
            self.detection_thread.join(timeout=2)
        
        self.gesture_detector.close()

        # 生成最終報告
        total_time = time.time() - self.detection_start_time if self.detection_start_time else 0

        # 廣播停止狀態
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "gesture",
            "stage": "stopped",
            "message": "手勢檢測已停止",
            "data": {
                "total_time": total_time,
                "total_detections": self.total_detections,
                "gesture_history": self.gesture_history[-10:]  # 最後10次檢測
            }
        })

        return {
            "status": "stopped",
            "message": "手勢檢測已停止",
            "summary": {
                "total_time": total_time,
                "total_detections": self.total_detections
            }
        }

    def get_detection_status(self) -> Dict:
        """獲取檢測狀態"""
        if not self.is_detecting:
            return {
                "status": "idle",
                "message": "手勢檢測未在進行中",
                "is_detecting": False
            }

        current_time = time.time()
        detection_duration = current_time - self.detection_start_time if self.detection_start_time else 0

        return {
            "status": "detecting",
            "message": "手勢檢測進行中",
            "is_detecting": True,
            "detection_duration": detection_duration,
            "total_detections": self.total_detections,
            "current_gesture": self.current_gesture.value,
            "current_confidence": self.current_confidence,
            "recent_history": self.gesture_history[-5:]  # 最近5次檢測
        }

    def get_current_gesture(self) -> Dict:
        """獲取當前手勢（供其他服務調用）"""
        return {
            "gesture": self.current_gesture.value,
            "confidence": self.current_confidence,
            "timestamp": _now_ts()
        }

    def _detection_loop(self, duration: Optional[int] = None):
        """檢測循環 (在背景線程中運行)"""
        if self.detection_start_time is None:
            self.detection_start_time = time.time()

        try:
            while self.is_detecting and self.camera and self.camera.isOpened():
                # 檢查時間限制
                if duration and (time.time() - self.detection_start_time) >= duration:
                    break

                ret, frame = self.camera.read()
                if not ret:
                    break
                
                timestamp_ms = int(time.time() * 1000)
                self.gesture_detector.recognize_async(frame, timestamp_ms)

                # 定期廣播結果 (每秒)
                current_time = time.time()
                if current_time - self.last_broadcast_time >= 1.0:
                    if self.current_gesture != HandGestureType.UNKNOWN:
                        self.status_broadcaster.broadcast_threadsafe({
                            "channel": "gesture",
                            "stage": "detecting",
                            "message": f"檢測到手勢: {self.current_gesture.value}",
                            "data": {
                                "current_gesture": self.current_gesture.value,
                                "confidence": round(self.current_confidence, 3),
                                "detection_count": self.total_detections,
                                "detection_duration": current_time - self.detection_start_time,
                                "stable_count": self.gesture_stable_count,
                                "is_stable": self.gesture_stable_count >= 3
                            }
                        })
                    self.last_broadcast_time = current_time

                # 控制幀率
                time.sleep(1/60)

        except Exception as exc:
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "gesture",
                "stage": "error",
                "message": f"檢測錯誤: {str(exc)}"
            })
        finally:
            if self.camera:
                self.camera.release()
                self.camera = None

            # 自動停止
            if self.is_detecting:
                self.stop_gesture_detection()


__all__ = ["HandGestureService", "HandGestureType"]
