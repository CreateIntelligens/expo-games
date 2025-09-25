# =============================================================================
# hand_gesture_service.py - 手勢識別服務
# 基於 MediaPipe Hands 實作石頭剪刀布手勢檢測
# =============================================================================

import logging
import os
import threading
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# MediaPipe 依賴初始化
os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")
try:
    import mediapipe as mp
    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR: Optional[str] = None
except Exception as exc:
    mp = None
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)

from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts


logger = logging.getLogger(__name__)


class HandGestureType(Enum):
    """手勢類型枚舉"""
    ROCK = "rock"      # 石頭 ✊
    PAPER = "paper"    # 布 ✋
    SCISSORS = "scissors"  # 剪刀 ✌️
    UNKNOWN = "unknown"


class HandGestureDetector:
    """手勢檢測器，基於 MediaPipe Hands"""

    def __init__(self):
        self.mediapipe_ready = _MEDIAPIPE_AVAILABLE
        self.init_error: Optional[str] = _MEDIAPIPE_ERROR
        self.hands = None

        if self.mediapipe_ready:
            try:
                self.mp_hands = mp.solutions.hands
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.5
                )
                logger.info("MediaPipe Hands 初始化完成，啟用手勢檢測")
            except Exception as exc:
                self.mediapipe_ready = False
                self.init_error = str(exc)
                logger.exception("初始化 MediaPipe Hands 失敗: %s", exc)
        else:
            logger.warning("MediaPipe Hands 無法使用: %s", self.init_error)

    def is_available(self) -> bool:
        """回傳 MediaPipe 是否可用"""
        return self.mediapipe_ready and self.hands is not None

    def detect_gesture(self, frame) -> Tuple[HandGestureType, float]:
        """檢測手勢並返回手勢類型和信心度"""
        if frame is None or not self.is_available():
            return HandGestureType.UNKNOWN, 0.0

        # 轉換為 RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return HandGestureType.UNKNOWN, 0.0

        # 獲取第一隻手的關鍵點
        hand_landmarks = results.multi_hand_landmarks[0]
        landmarks = [(lm.x, lm.y) for lm in hand_landmarks.landmark]

        # 分析手勢
        gesture, confidence = self._classify_gesture(landmarks)
        return gesture, confidence

    def _classify_gesture(self, landmarks: List[Tuple[float, float]]) -> Tuple[HandGestureType, float]:
        """根據關鍵點分類手勢"""
        if len(landmarks) != 21:
            return HandGestureType.UNKNOWN, 0.0

        # MediaPipe 手部關鍵點索引
        # 拇指: 4, 食指: 8, 中指: 12, 無名指: 16, 小指: 20
        # 指根: 拇指3, 食指6, 中指10, 無名指14, 小指18

        thumb_tip = landmarks[4]
        thumb_ip = landmarks[3]
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        # 計算手指是否伸直
        fingers_up = []

        # 拇指 (比較特殊，需要看 x 座標)
        if thumb_tip[0] > thumb_ip[0]:  # 右手
            fingers_up.append(thumb_tip[0] > thumb_ip[0])
        else:  # 左手
            fingers_up.append(thumb_tip[0] < thumb_ip[0])

        # 其他四指 (比較 y 座標，tip 在 pip 上方表示伸直)
        fingers_up.append(index_tip[1] < index_pip[1])
        fingers_up.append(middle_tip[1] < middle_pip[1])
        fingers_up.append(ring_tip[1] < ring_pip[1])
        fingers_up.append(pinky_tip[1] < pinky_pip[1])

        # 計算伸直的手指數量
        fingers_count = sum(fingers_up)

        # 手勢分類邏輯
        confidence = 0.8  # 基礎信心度

        if fingers_count == 0:
            # 所有手指收起 = 石頭
            return HandGestureType.ROCK, confidence

        elif fingers_count == 5:
            # 所有手指伸直 = 布
            return HandGestureType.PAPER, confidence

        elif fingers_count == 2 and fingers_up[1] and fingers_up[2]:
            # 食指和中指伸直 = 剪刀
            return HandGestureType.SCISSORS, confidence

        else:
            # 其他情況，降低信心度
            if fingers_count <= 1:
                return HandGestureType.ROCK, confidence * 0.6
            elif fingers_count >= 4:
                return HandGestureType.PAPER, confidence * 0.6
            elif fingers_count == 2:
                return HandGestureType.SCISSORS, confidence * 0.5
            else:
                return HandGestureType.UNKNOWN, confidence * 0.3


class HandGestureService:
    """手勢識別服務主類"""

    def __init__(self, status_broadcaster: StatusBroadcaster):
        self.status_broadcaster = status_broadcaster
        self.gesture_detector = HandGestureDetector()

        if not self.gesture_detector.is_available():
            logger.error(
                "MediaPipe Hands 未啟用，手勢識別功能將不可用: %s",
                self.gesture_detector.init_error,
            )

        # 服務狀態
        self.is_detecting = False
        self.detection_thread = None
        self.camera = None

        # 檢測統計
        self.detection_start_time = None
        self.total_detections = 0
        self.gesture_history = []
        self.current_gesture = HandGestureType.UNKNOWN
        self.current_confidence = 0.0

    def start_gesture_detection(self, duration: Optional[int] = None) -> Dict:
        """開始手勢檢測"""
        if not self.gesture_detector.is_available():
            error_msg = self.gesture_detector.init_error or "MediaPipe Hands 初始化失敗"
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
        frame_count = 0
        last_broadcast_time = 0
        gesture_stable_count = 0
        last_stable_gesture = HandGestureType.UNKNOWN

        try:
            while self.is_detecting and self.camera and self.camera.isOpened():
                # 檢查時間限制
                if duration and (time.time() - self.detection_start_time) >= duration:
                    break

                ret, frame = self.camera.read()
                if not ret:
                    break

                frame_count += 1

                # 每2幀檢測一次
                if frame_count % 2 == 0:
                    # 檢測手勢
                    gesture, confidence = self.gesture_detector.detect_gesture(frame)

                    if gesture != HandGestureType.UNKNOWN and confidence > 0.5:
                        self.total_detections += 1

                        # 更新當前手勢
                        self.current_gesture = gesture
                        self.current_confidence = confidence

                        # 手勢穩定性檢測
                        if gesture == last_stable_gesture:
                            gesture_stable_count += 1
                        else:
                            gesture_stable_count = 1
                            last_stable_gesture = gesture

                        # 記錄歷史
                        self.gesture_history.append({
                            "gesture": gesture.value,
                            "confidence": round(confidence, 3),
                            "timestamp": time.time(),
                            "stable_count": gesture_stable_count
                        })

                        # 定期廣播結果 (每秒)
                        current_time = time.time()
                        if current_time - last_broadcast_time >= 1.0:
                            self.status_broadcaster.broadcast_threadsafe({
                                "channel": "gesture",
                                "stage": "detecting",
                                "message": f"檢測到手勢: {gesture.value}",
                                "data": {
                                    "current_gesture": gesture.value,
                                    "confidence": round(confidence, 3),
                                    "detection_count": self.total_detections,
                                    "detection_duration": current_time - self.detection_start_time,
                                    "stable_count": gesture_stable_count,
                                    "is_stable": gesture_stable_count >= 3
                                }
                            })

                            last_broadcast_time = current_time

                # 控制幀率
                time.sleep(1/30)  # 30 FPS

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