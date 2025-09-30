# =============================================================================
# drawing_service.py - AI 畫布識別服務
# 基於 MediaPipe 和手勢追蹤的虛擬繪畫和 AI 圖像識別系統
# =============================================================================

import logging
import threading
import time
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import base64
import io
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image, ImageDraw

from ..utils.gpu_runtime import configure_gpu_runtime

_GPU_STATUS = configure_gpu_runtime()

try:
    import mediapipe as mp
    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR: Optional[str] = None
except Exception as exc:
    mp = SimpleNamespace(solutions=SimpleNamespace(hands=None))
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)

from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts
from ..utils.hand_tracking_module import HandTrackingModule, GestureResult, GestureType
from ..utils.drawing_engine import DrawingEngine, BrushType

# WebSocket 支援
import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)

if _GPU_STATUS.warnings:
    for warning in _GPU_STATUS.warnings:
        logger.warning("GPU setup warning: %s", warning)
else:
    logger.info(
        "DrawingService GPU ready | TensorFlow devices: %s | MediaPipe GPU enabled: %s",
        _GPU_STATUS.tensorflow_devices,
        _GPU_STATUS.mediapipe_gpu_enabled,
    )


class DrawingMode(Enum):
    """繪畫模式"""
    INDEX_FINGER = "index_finger"  # 食指繪畫
    BOTH_FINGERS = "both_fingers"  # 雙指控制
    GESTURE_CONTROL = "gesture_control"  # 手勢控制


class DrawingColor(Enum):
    """繪畫顏色"""
    BLACK = (0, 0, 0)
    RED = (0, 0, 255)
    GREEN = (0, 255, 0)
    BLUE = (255, 0, 0)
    YELLOW = (0, 255, 255)
    PURPLE = (255, 0, 255)
    CYAN = (255, 255, 0)
    WHITE = (255, 255, 255)


class DrawingAction(Enum):
    """繪畫動作"""
    DRAW = "draw"
    ERASE = "erase"
    CLEAR = "clear"
    SAVE = "save"


class FingerTracker:
    """手指追蹤器，基於 MediaPipe Hands"""

    def __init__(self):
        self.mediapipe_ready = _MEDIAPIPE_AVAILABLE
        self.init_error: Optional[str] = _MEDIAPIPE_ERROR
        self.hands = None

        if self.mediapipe_ready:
            try:
                self.mp_hands = mp.solutions.hands
                self.mp_drawing = mp.solutions.drawing_utils
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.6,  # 平衡準確度和敏感度
                    min_tracking_confidence=0.5,   # 穩定的追蹤
                    model_complexity=1             # 使用中等模型，平衡速度和準確度
                )
                logger.info("MediaPipe Hands 初始化完成，啟用手指追蹤")
            except Exception as exc:
                self.mediapipe_ready = False
                self.init_error = str(exc)
                logger.exception("初始化 MediaPipe Hands 失敗: %s", exc)
        else:
            logger.warning("MediaPipe Hands 無法使用: %s", self.init_error)

    def is_available(self) -> bool:
        """回傳 MediaPipe 是否可用"""
        return self.mediapipe_ready and self.hands is not None

    def get_finger_positions(self, frame) -> Dict:
        """獲取手指位置"""
        if frame is None or not self.is_available():
            return {}

        height, width, _ = frame.shape
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(frame_rgb)

        if not results.multi_hand_landmarks:
            return {}

        # 獲取第一隻手的關鍵點
        hand_landmarks = results.multi_hand_landmarks[0]

        # 重要手指關鍵點索引
        finger_tips = {
            'thumb': 4,      # 拇指
            'index': 8,      # 食指
            'middle': 12,    # 中指
            'ring': 16,      # 無名指
            'pinky': 20      # 小指
        }

        finger_positions = {}
        for finger, tip_idx in finger_tips.items():
            landmark = hand_landmarks.landmark[tip_idx]
            x = int(landmark.x * width)
            y = int(landmark.y * height)
            finger_positions[finger] = (x, y)

        # 計算手指是否伸直 (用於手勢控制)
        fingers_up = self._get_fingers_up(hand_landmarks)
        finger_positions['fingers_up'] = fingers_up

        return finger_positions

    def _get_fingers_up(self, hand_landmarks) -> List[bool]:
        """檢測哪些手指是伸直的

        策略：
        - 拇指永遠回傳 False（忽略拇指判定，避免誤判）
        - 食指判定適中（方便繪畫）
        - 其他手指判定嚴格（確保只有食指伸直時才繪畫）
        - 使用三點判斷避免背景干擾
        """
        fingers = []

        # 拇指 - 直接忽略，永遠回傳 False
        fingers.append(False)

        # 食指 (使用三點判斷)
        index_tip = hand_landmarks.landmark[8]
        index_pip = hand_landmarks.landmark[6]
        index_mcp = hand_landmarks.landmark[5]

        # 食指判定：tip 高於 PIP，且 PIP 高於或接近 MCP
        index_extended = (index_tip.y < index_pip.y - 0.01) and (index_pip.y < index_mcp.y + 0.02)
        fingers.append(index_extended)

        # 中指、無名指、小指 (使用適中的三點判斷)
        other_fingers = [
            (12, 10, 9),   # 中指: tip, pip, mcp
            (16, 14, 13),  # 無名指
            (20, 18, 17)   # 小指
        ]

        for tip_idx, pip_idx, mcp_idx in other_fingers:
            tip = hand_landmarks.landmark[tip_idx]
            pip = hand_landmarks.landmark[pip_idx]
            mcp = hand_landmarks.landmark[mcp_idx]

            # 適中判定：比食指嚴格一點，但不要太嚴格
            is_extended = (tip.y < pip.y - 0.02) and (pip.y < mcp.y + 0.01)
            fingers.append(is_extended)

        return fingers


class VirtualCanvas:
    """虛擬畫布"""

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        # 初始化為透明背景的RGBA畫布
        self.canvas = np.zeros((height, width, 4), dtype=np.uint8)
        self.drawing_points = deque(maxlen=1000)  # 最近1000個繪畫點
        self.current_color = DrawingColor.BLACK.value
        self.brush_size = 5
        self.is_drawing = False
        self.last_position = None

    @property
    def _color_with_alpha(self) -> Tuple[int, int, int, int]:
        """將當前顏色轉換為含 alpha 的 BGRA 顏色。"""

        if len(self.current_color) == 4:
            return self.current_color
        return (*self.current_color, 255)

    def clear_canvas(self):
        """清空畫布"""
        # 清空為透明背景（RGBA）
        self.canvas = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        self.drawing_points.clear()
        self.last_position = None

    def set_color(self, color: DrawingColor):
        """設置繪畫顏色"""
        self.current_color = color.value

    def set_brush_size(self, size: int):
        """設置筆刷大小"""
        self.brush_size = max(1, min(20, size))

    def draw_point(self, position: Tuple[int, int], action: DrawingAction = DrawingAction.DRAW):
        """在指定位置繪畫"""
        x, y = position

        # 邊界檢查
        if not (0 <= x < self.width and 0 <= y < self.height):
            return

        if action == DrawingAction.DRAW:
            if self.last_position is not None:
                # 畫線連接兩點
                cv2.line(self.canvas, self.last_position, (x, y), self._color_with_alpha, self.brush_size)
            else:
                # 畫點
                cv2.circle(self.canvas, (x, y), self.brush_size // 2, self._color_with_alpha, -1)

            self.drawing_points.append({
                'position': (x, y),
                'color': self.current_color,
                'size': self.brush_size,
                'timestamp': time.time()
            })

        elif action == DrawingAction.ERASE:
            # 橡皮擦效果
            cv2.circle(self.canvas, (x, y), self.brush_size * 2, (0, 0, 0, 0), -1)

        self.last_position = (x, y)

    def stop_drawing(self):
        """停止繪畫（抬筆）"""
        self.last_position = None

    def get_canvas_image(self) -> np.ndarray:
        """獲取當前畫布圖像"""
        return self.canvas.copy()

    def get_canvas_base64(self) -> str:
        """獲取畫布的 base64 編碼（左右反轉以符合使用者視角）"""
        # 對於RGBA canvas，直接創建PIL Image
        if self.canvas.shape[2] == 4:  # RGBA
            # 將BGRA轉換為RGBA（OpenCV使用BGRA，PIL使用RGBA）
            rgba_canvas = cv2.cvtColor(self.canvas, cv2.COLOR_BGRA2RGBA)
            pil_image = Image.fromarray(rgba_canvas, mode='RGBA')
        else:  # RGB
            pil_image = Image.fromarray(cv2.cvtColor(self.canvas, cv2.COLOR_BGR2RGB), mode='RGB')

        # 左右反轉畫布，使其符合鏡像攝影機的視角
        pil_image = pil_image.transpose(Image.FLIP_LEFT_RIGHT)

        # 轉換為 base64
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"


class ShapeRecognizer:
    """形狀識別器（基於輪廓分析）"""

    def __init__(self):
        self.shape_templates = {
            'circle': self._create_circle_template(),
            'square': self._create_square_template(),
            'triangle': self._create_triangle_template(),
            'line': self._create_line_template(),
            'heart': self._create_heart_template()
        }

    def recognize_drawing(self, canvas: np.ndarray) -> Dict:
        """識別畫布上的圖形"""
        # 轉為灰度圖，支援 BGRA/BGR
        if canvas.ndim == 3 and canvas.shape[2] == 4:
            gray = cv2.cvtColor(canvas, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)

        # 二值化
        _, binary = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)

        # 找輪廓
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return {
                'recognized': 'empty',
                'confidence': 1.0,
                'message': '畫布是空的',
                'suggestions': ['畫一個圓形', '畫一個正方形', '畫一條線']
            }

        # 找到最大輪廓
        largest_contour = max(contours, key=cv2.contourArea)

        # 分析形狀特徵
        features = self._analyze_shape_features(largest_contour)

        # 匹配形狀
        recognized_shape, confidence = self._match_shape(features)

        return {
            'recognized': recognized_shape,
            'confidence': confidence,
            'message': self._get_recognition_message(recognized_shape, confidence),
            'features': features,
            'suggestions': self._get_suggestions(recognized_shape)
        }

    def _analyze_shape_features(self, contour) -> Dict:
        """分析形狀特徵"""
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        if perimeter == 0:
            return {'area': area, 'perimeter': perimeter, 'circularity': 0}

        # 圓形度
        circularity = 4 * np.pi * area / (perimeter * perimeter)

        # 近似多邊形
        epsilon = 0.02 * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)
        vertex_count = len(approx)

        # 邊界框
        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0

        # 凸包
        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0

        return {
            'area': area,
            'perimeter': perimeter,
            'circularity': circularity,
            'vertex_count': vertex_count,
            'aspect_ratio': aspect_ratio,
            'solidity': solidity
        }

    def _match_shape(self, features: Dict) -> Tuple[str, float]:
        """根據特徵匹配形狀"""
        circularity = features['circularity']
        vertex_count = features['vertex_count']
        aspect_ratio = features['aspect_ratio']
        solidity = features['solidity']

        # 圓形檢測
        if circularity > 0.7 and vertex_count > 8:
            return 'circle', min(0.95, circularity)

        # 正方形檢測
        if (vertex_count == 4 and
            0.8 < aspect_ratio < 1.2 and
            solidity > 0.8):
            return 'square', 0.85

        # 三角形檢測
        if vertex_count == 3 and solidity > 0.7:
            return 'triangle', 0.80

        # 直線檢測
        if (vertex_count == 2 or
            (aspect_ratio > 4 or aspect_ratio < 0.25)):
            return 'line', 0.75

        # 心形檢測（基於複雜度）
        if (circularity < 0.5 and
            vertex_count > 10 and
            solidity < 0.8):
            return 'heart', 0.60

        # 未知形狀
        return 'unknown', 0.3

    def _get_recognition_message(self, shape: str, confidence: float) -> str:
        """獲取識別結果訊息"""
        messages = {
            'circle': '我看到一個圓形！',
            'square': '這是一個正方形！',
            'triangle': '我識別出一個三角形！',
            'line': '這是一條直線！',
            'heart': '看起來像一個心形！',
            'unknown': '我不確定這是什麼形狀...'
        }

        base_message = messages.get(shape, '未知形狀')

        if confidence > 0.8:
            return f"{base_message} (非常確定)"
        elif confidence > 0.6:
            return f"{base_message} (還算確定)"
        else:
            return f"{base_message} (不太確定)"

    def _get_suggestions(self, shape: str) -> List[str]:
        """獲取建議"""
        suggestions_map = {
            'circle': ['試試畫一個正方形', '畫一條直線', '畫個心形'],
            'square': ['試試畫一個圓形', '畫一個三角形', '畫條對角線'],
            'triangle': ['畫一個圓形', '畫一個正方形', '畫個星星'],
            'line': ['畫一個圓形', '畫幾條線組成圖形', '試試曲線'],
            'heart': ['畫一個圓形', '畫一個笑臉', '畫朵花'],
            'unknown': ['試試畫簡單的幾何圖形', '畫一個圓形', '畫一條直線'],
            'empty': ['開始畫畫吧！', '試試畫一個圓形', '畫你喜歡的任何東西']
        }

        return suggestions_map.get(shape, ['繼續創作！'])

    def _create_circle_template(self) -> np.ndarray:
        """創建圓形模板"""
        template = np.zeros((100, 100), dtype=np.uint8)
        cv2.circle(template, (50, 50), 40, 255, 2)
        return template

    def _create_square_template(self) -> np.ndarray:
        """創建正方形模板"""
        template = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(template, (20, 20), (80, 80), 255, 2)
        return template

    def _create_triangle_template(self) -> np.ndarray:
        """創建三角形模板"""
        template = np.zeros((100, 100), dtype=np.uint8)
        points = np.array([[50, 20], [20, 80], [80, 80]], np.int32)
        cv2.polylines(template, [points], True, 255, 2)
        return template

    def _create_line_template(self) -> np.ndarray:
        """創建直線模板"""
        template = np.zeros((100, 100), dtype=np.uint8)
        cv2.line(template, (20, 50), (80, 50), 255, 2)
        return template

    def _create_heart_template(self) -> np.ndarray:
        """創建心形模板"""
        template = np.zeros((100, 100), dtype=np.uint8)
        # 簡化的心形（兩個圓加一個三角形）
        cv2.circle(template, (35, 35), 15, 255, 2)
        cv2.circle(template, (65, 35), 15, 255, 2)
        points = np.array([[25, 45], [75, 45], [50, 75]], np.int32)
        cv2.polylines(template, [points], True, 255, 2)
        return template


class DrawingService:
    """AI 畫布識別服務主類"""

    def __init__(self, status_broadcaster: StatusBroadcaster):
        self.status_broadcaster = status_broadcaster
        self.finger_tracker = FingerTracker()
        self.virtual_canvas = VirtualCanvas()
        self.ai_recognizer = ShapeRecognizer()

        if not self.finger_tracker.is_available():
            logger.error(
                "MediaPipe Hands 未啟用，手指追蹤功能將不可用: %s",
                self.finger_tracker.init_error,
            )

        # 服務狀態
        self.is_drawing = False
        self.drawing_thread = None
        self.camera = None

        # 繪畫設定
        self.drawing_mode = DrawingMode.INDEX_FINGER
        self.current_color = DrawingColor.BLACK
        self.auto_recognize = True
        self.recognition_interval = 3  # 每3秒自動識別一次

        # 統計
        self.drawing_start_time = None
        self.total_strokes = 0
        self.recognition_history = []

        # 視覺穩定性控制
        self.last_canvas_update_time = 0
        self.canvas_update_interval = 0.1  # 最少間隔100ms更新一次畫布
        self.last_stable_gesture = "none"

        # 畫布尺寸（預設值，會在開始會話時更新）
        self.canvas_width = 640
        self.canvas_height = 480

        # 顏色選擇區域配置（4種顏色均分畫面寬度）
        self.color_zones = ['black', 'red', 'blue', 'green']

    def start_drawing_session(self,
                            mode: str = "index_finger",
                            color: str = "black",
                            auto_recognize: bool = True,
                            websocket_mode: bool = False) -> Dict:
        """開始繪畫會話"""
        if not self.finger_tracker.is_available():
            error_msg = self.finger_tracker.init_error or "MediaPipe Hands 初始化失敗"
            return {
                "status": "error",
                "message": f"無法啟動繪畫功能: {error_msg}",
            }

        if self.is_drawing:
            return {"status": "error", "message": "繪畫會話已在進行中"}

        try:
            # 設定參數
            self.drawing_mode = DrawingMode(mode)
            self.current_color = DrawingColor[color.upper()]
            self.auto_recognize = auto_recognize

            # WebSocket 模式不需要開啟攝影機
            if not websocket_mode:
                # 開啟攝影機
                self.camera = cv2.VideoCapture(0)
                if not self.camera.isOpened():
                    return {"status": "error", "message": "無法開啟攝影機"}

                self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self.camera.set(cv2.CAP_PROP_FPS, 30)

                # 開始繪畫線程
                self.drawing_thread = threading.Thread(
                    target=self._drawing_loop,
                    daemon=True
                )
                self.drawing_thread.start()

            # 重置狀態
            self.virtual_canvas.clear_canvas()
            self.virtual_canvas.set_color(self.current_color)
            self.drawing_start_time = time.time()
            self.total_strokes = 0
            self.recognition_history = []

            # 設置繪畫狀態
            self.is_drawing = True

            # 廣播開始狀態
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "drawing",
                "stage": "started",
                "message": "AI 畫布會話已開始",
                "data": {
                    "mode": mode,
                    "color": color,
                    "auto_recognize": auto_recognize,
                    "websocket_mode": websocket_mode,
                    "start_time": self.drawing_start_time
                }
            })

            return {
                "status": "started",
                "message": "繪畫會話已開始",
                "mode": mode,
                "color": color,
                "websocket_mode": websocket_mode
            }

        except Exception as exc:
            self.is_drawing = False
            return {"status": "error", "message": f"啟動失敗: {str(exc)}"}

    def stop_drawing_session(self) -> Dict:
        """停止繪畫會話"""
        if not self.is_drawing:
            return {"status": "idle", "message": "繪畫會話未在進行中"}

        self.is_drawing = False

        if self.camera:
            self.camera.release()
            self.camera = None

        if self.drawing_thread:
            self.drawing_thread.join(timeout=2)

        # 最終識別
        final_recognition = self.ai_recognizer.recognize_drawing(self.virtual_canvas.get_canvas_image())
        total_time = time.time() - self.drawing_start_time if self.drawing_start_time else 0

        # 廣播停止狀態
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "drawing",
            "stage": "stopped",
            "message": "繪畫會話已停止",
            "data": {
                "total_time": total_time,
                "total_strokes": self.total_strokes,
                "final_recognition": final_recognition,
                "canvas_image": self.virtual_canvas.get_canvas_base64()
            }
        })

        return {
            "status": "stopped",
            "message": "繪畫會話已停止",
            "final_recognition": final_recognition
        }

    def get_drawing_status(self) -> Dict:
        """獲取繪畫狀態"""
        if not self.is_drawing:
            return {
                "status": "idle",
                "message": "繪畫會話未在進行中",
                "is_drawing": False
            }

        current_time = time.time()
        drawing_duration = current_time - self.drawing_start_time if self.drawing_start_time else 0

        return {
            "status": "drawing",
            "message": "繪畫會話進行中",
            "is_drawing": True,
            "drawing_duration": drawing_duration,
            "total_strokes": self.total_strokes,
            "current_mode": self.drawing_mode.value,
            "current_color": self.current_color.name.lower(),
            "canvas_image": self.virtual_canvas.get_canvas_base64(),
            "recent_recognitions": self.recognition_history[-3:]  # 最近3次識別
        }

    def recognize_current_drawing(self) -> Dict:
        """手動識別當前繪畫"""
        recognition_result = self.ai_recognizer.recognize_drawing(self.virtual_canvas.get_canvas_image())

        # 記錄識別歷史
        self.recognition_history.append({
            "timestamp": _now_ts(),
            "result": recognition_result
        })

        return recognition_result

    def clear_canvas(self) -> Dict:
        """清空畫布"""
        self.virtual_canvas.clear_canvas()
        self.total_strokes = 0

        self.status_broadcaster.broadcast_threadsafe({
            "channel": "drawing",
            "stage": "canvas_cleared",
            "message": "畫布已清空",
            "data": {"canvas_image": self.virtual_canvas.get_canvas_base64()}
        })

        return {"status": "success", "message": "畫布已清空"}

    def change_drawing_color(self, color: str) -> Dict:
        """變更繪畫顏色"""
        try:
            # 驗證顏色
            valid_colors = ["black", "red", "green", "blue", "yellow", "purple", "cyan", "white"]
            if color not in valid_colors:
                return {
                    "status": "error",
                    "message": f"無效的顏色: {color}，支援的顏色: {', '.join(valid_colors)}"
                }

            # 設置新顏色
            self.current_color = DrawingColor[color.upper()]
            self.virtual_canvas.set_color(self.current_color)

            self.status_broadcaster.broadcast_threadsafe({
                "channel": "drawing",
                "stage": "color_changed",
                "message": f"繪畫顏色已更改為 {color}",
                "data": {"new_color": color}
            })

            return {
                "status": "success",
                "message": f"繪畫顏色已更改為 {color}",
                "color": color
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"顏色變更失敗: {str(e)}"
            }

    def process_frame_for_gesture_drawing(self, frame_data: bytes, mode: str = "gesture_control") -> Dict:
        """處理單一幀用於手勢繪畫（WebSocket模式）

        接收前端發送的影像幀，進行手勢識別和繪畫處理，返回處理結果。

        Args:
            frame_data (bytes): JPEG 編碼的影像幀數據
            mode (str): 繪畫模式 ("gesture_control", "index_finger")

        Returns:
            Dict: 處理結果，包含手勢狀態、畫布更新和識別結果
        """
        try:
            # 將 bytes 轉換為 numpy array
            nparr = np.frombuffer(frame_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return {
                    "type": "error",
                    "message": "無法解碼影像幀",
                    "timestamp": time.time()
                }

            # 翻轉鏡像效果（與攝影機預覽一致）
            frame = cv2.flip(frame, 1)

            # 更新畫布尺寸
            self.canvas_height, self.canvas_width = frame.shape[:2]

            # 獲取手指位置
            finger_positions = self.finger_tracker.get_finger_positions(frame)

            # 處理繪畫輸入
            gesture_info = self._process_gesture_drawing_frame(finger_positions, mode)

            # 檢查是否需要進行 AI 識別
            recognition_result = None
            if self.auto_recognize and self.total_strokes > 0 and self.total_strokes % 50 == 0:  # 每50筆劃檢查一次
                recognition_result = self.recognize_current_drawing()

            # 準備回應數據
            current_time = time.time()
            gesture_name = gesture_info["gesture"]

            response = {
                "type": "gesture_status",
                "current_gesture": gesture_name,
                "fingers_up": finger_positions.get('fingers_up', [False] * 5) if finger_positions else [False] * 5,
                "drawing_position": gesture_info.get("position"),
                "timestamp": current_time
            }

            # 如果有繪畫發生，立即更新畫布（移除節流以確保即時性）
            if gesture_info["drawing_occurred"]:
                response.update({
                    "canvas_base64": self.virtual_canvas.get_canvas_base64(),
                    "stroke_count": self.total_strokes,
                    "current_color": self.current_color.name.lower()
                })

            # 如果是顏色選擇手勢，額外發送顏色變更通知
            if gesture_name == "color_selecting" and "selected_color" in gesture_info:
                response.update({
                    "color_changed": True,
                    "new_color": gesture_info["selected_color"],
                    "current_color": self.current_color.name.lower()
                })
                logger.info(f"✅ 發送顏色變更通知: {gesture_info['selected_color']}")

            # 如果是清空手勢，額外發送清空通知
            if gesture_name == "clearing":
                response.update({
                    "canvas_cleared": True,
                    "canvas_base64": self.virtual_canvas.get_canvas_base64()
                })
                logger.info("✅ 發送畫布清空通知")

            # 如果有識別結果，包含識別信息
            if recognition_result:
                response.update({
                    "type": "recognition_result",
                    "recognized_shape": recognition_result["recognized"],
                    "confidence": recognition_result["confidence"],
                    "message": recognition_result["message"]
                })

            return response

        except Exception as exc:
            logger.exception("處理手勢繪畫幀時發生錯誤: %s", exc)
            return {
                "type": "error",
                "message": f"幀處理錯誤: {str(exc)}",
                "timestamp": time.time()
            }

    def change_drawing_color(self, color_name: str) -> Dict:
        """變更繪畫顏色"""
        try:
            # 驗證顏色名稱
            color_name = color_name.upper()
            if not hasattr(DrawingColor, color_name):
                return {
                    "type": "error",
                    "message": f"不支持的顏色: {color_name}",
                    "timestamp": time.time()
                }

            # 設置新顏色
            self.current_color = DrawingColor[color_name]
            self.virtual_canvas.set_color(self.current_color)

            logger.info("繪畫顏色已變更為: %s", color_name)

            return {
                "type": "color_changed",
                "color": color_name.lower(),
                "message": f"顏色已變更為 {color_name.lower()}",
                "timestamp": time.time()
            }

        except Exception as exc:
            logger.exception("變更顏色時發生錯誤: %s", exc)
            return {
                "type": "error",
                "message": f"顏色變更失敗: {str(exc)}",
                "timestamp": time.time()
            }

    def change_brush_size(self, size: int) -> Dict:
        """變更筆刷大小"""
        try:
            # 驗證筆刷大小
            size = max(1, min(50, size))  # 限制在1-50之間

            # 設置新筆刷大小
            self.virtual_canvas.set_brush_size(size)

            logger.info("筆刷大小已變更為: %d", size)

            return {
                "type": "brush_size_changed",
                "size": size,
                "message": f"筆刷大小已變更為 {size}",
                "timestamp": time.time()
            }

        except Exception as exc:
            logger.exception("變更筆刷大小時發生錯誤: %s", exc)
            return {
                "type": "error",
                "message": f"筆刷大小變更失敗: {str(exc)}",
                "timestamp": time.time()
            }

    def _detect_color_from_position(self, x_pos: int) -> str:
        """根據 x 座標判斷選擇的顏色

        Args:
            x_pos: 手指的 x 座標

        Returns:
            str: 顏色名稱
        """
        zone_width = self.canvas_width / len(self.color_zones)
        color_index = int(x_pos / zone_width)
        color_index = max(0, min(color_index, len(self.color_zones) - 1))
        return self.color_zones[color_index]

    def _process_gesture_drawing_frame(self, finger_positions: Dict, mode: str) -> Dict:
        """處理單一幀的手勢繪畫邏輯"""
        gesture_info = {
            "gesture": "no_hand",
            "drawing_occurred": False,
            "position": None
        }

        if not finger_positions:
            # 沒有檢測到手，停止繪畫
            self.virtual_canvas.stop_drawing()
            return gesture_info

        fingers_up = finger_positions.get('fingers_up', [False] * 5)
        fingers_count = sum(fingers_up)
        index_pos = finger_positions.get('index')

        if mode == "gesture_control":
            # Debug: 印出手勢判定資訊
            logger.info(f"👆 手勢判定 - fingers_up: {fingers_up}, count: {fingers_count}, index_pos: {index_pos}")

            if fingers_count == 1 and fingers_up[1] and index_pos:  # 只有食指 - 繪畫
                self.virtual_canvas.draw_point(index_pos, DrawingAction.DRAW)
                self.total_strokes += 1
                gesture_info.update({
                    "gesture": "drawing",
                    "drawing_occurred": True,
                    "position": index_pos
                })
                logger.info(f"✏️ 繪畫動作確認 - 位置: {index_pos}")

            elif fingers_count == 2 and fingers_up[1] and fingers_up[2] and index_pos:  # 食指+中指 - 選擇模式
                middle_pos = finger_positions.get('middle')
                logger.info(f"🖐️ 雙指偵測 - index_pos: {index_pos}, middle_pos: {middle_pos}")

                if middle_pos:
                    # 計算食指和中指的中點位置
                    selection_pos = ((index_pos[0] + middle_pos[0]) // 2,
                                    (index_pos[1] + middle_pos[1]) // 2)

                    # 檢查是否在顏色選擇區域（畫面頂部 15%）
                    color_zone_height = int(self.canvas_height * 0.15)
                    logger.info(f"🎨 選擇位置: {selection_pos}, 顏色區高度: {color_zone_height}, canvas高度: {self.canvas_height}")

                    if selection_pos[1] < color_zone_height:
                        # 在顏色選擇區域 - 根據 x 座標判斷選擇哪個顏色
                        selected_color = self._detect_color_from_position(selection_pos[0])
                        if selected_color != self.current_color.name.lower():
                            self.current_color = DrawingColor[selected_color.upper()]
                            self.virtual_canvas.set_color(self.current_color)
                            gesture_info.update({
                                "gesture": "color_selecting",
                                "selected_color": selected_color,
                                "position": selection_pos
                            })
                            logger.info(f"🎨 顏色已切換: {selected_color}")
                        else:
                            gesture_info.update({
                                "gesture": "selecting",
                                "position": selection_pos
                            })
                    else:
                        # 在畫布區域 - 橡皮擦功能
                        self.virtual_canvas.draw_point(index_pos, DrawingAction.ERASE)
                        gesture_info.update({
                            "gesture": "erasing",
                            "drawing_occurred": True,
                            "position": index_pos
                        })
                else:
                    # 沒有中指位置，預設為橡皮擦
                    self.virtual_canvas.draw_point(index_pos, DrawingAction.ERASE)
                    gesture_info.update({
                        "gesture": "erasing",
                        "drawing_occurred": True,
                        "position": index_pos
                    })

            elif fingers_count == 4:  # 四指全開（忽略拇指）- 清空
                self.virtual_canvas.clear_canvas()
                self.total_strokes = 0
                gesture_info.update({
                    "gesture": "clearing",
                    "drawing_occurred": True
                })

            else:
                # 其他手勢或無效手勢，停止繪畫
                self.virtual_canvas.stop_drawing()
                gesture_info["gesture"] = "idle"

        elif mode == "index_finger":
            if fingers_up[1] and not fingers_up[2] and index_pos:  # 食指繪畫，中指不伸直
                self.virtual_canvas.draw_point(index_pos, DrawingAction.DRAW)
                self.total_strokes += 1
                gesture_info.update({
                    "gesture": "drawing",
                    "drawing_occurred": True,
                    "position": index_pos
                })
            else:
                self.virtual_canvas.stop_drawing()
                gesture_info["gesture"] = "idle"

        return gesture_info

    def _drawing_loop(self):
        """繪畫主循環"""
        last_recognition_time = 0
        frame_count = 0

        try:
            while self.is_drawing and self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if not ret:
                    break

                frame_count += 1

                # 翻轉鏡像效果
                frame = cv2.flip(frame, 1)

                # 獲取手指位置
                finger_positions = self.finger_tracker.get_finger_positions(frame)

                if finger_positions and 'index' in finger_positions:
                    # 根據模式處理繪畫
                    self._process_drawing_input(finger_positions)
                else:
                    # 沒有檢測到手，停止繪畫
                    self.virtual_canvas.stop_drawing()

                # 定期自動識別
                current_time = time.time()
                if (self.auto_recognize and
                    current_time - last_recognition_time >= self.recognition_interval):

                    recognition_result = self.recognize_current_drawing()

                    # 廣播識別結果
                    self.status_broadcaster.broadcast_threadsafe({
                        "channel": "drawing",
                        "stage": "recognition_update",
                        "message": recognition_result['message'],
                        "data": {
                            "recognition": recognition_result,
                            "canvas_image": self.virtual_canvas.get_canvas_base64(),
                            "drawing_duration": current_time - self.drawing_start_time
                        }
                    })

                    last_recognition_time = current_time

                # 控制幀率
                time.sleep(1/30)

        except Exception as exc:
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "drawing",
                "stage": "error",
                "message": f"繪畫錯誤: {str(exc)}"
            })
        finally:
            if self.camera:
                self.camera.release()
                self.camera = None

            if self.is_drawing:
                self.stop_drawing_session()

    def _process_drawing_input(self, finger_positions: Dict):
        """處理繪畫輸入"""
        if self.drawing_mode == DrawingMode.INDEX_FINGER:
            self._process_index_finger_drawing(finger_positions)
        elif self.drawing_mode == DrawingMode.GESTURE_CONTROL:
            self._process_gesture_control_drawing(finger_positions)

    def _process_index_finger_drawing(self, finger_positions: Dict):
        """食指繪畫模式"""
        index_pos = finger_positions['index']
        fingers_up = finger_positions.get('fingers_up', [False] * 5)

        # 只有食指伸直時才繪畫
        if fingers_up[1] and not fingers_up[2]:  # 食指伸直，中指不伸直
            self.virtual_canvas.draw_point(index_pos, DrawingAction.DRAW)
            self.total_strokes += 1
        else:
            self.virtual_canvas.stop_drawing()

    def _process_gesture_control_drawing(self, finger_positions: Dict):
        """手勢控制繪畫模式"""
        index_pos = finger_positions['index']
        fingers_up = finger_positions.get('fingers_up', [False] * 5)
        fingers_count = sum(fingers_up)

        if fingers_count == 1 and fingers_up[1]:  # 只有食指
            self.virtual_canvas.draw_point(index_pos, DrawingAction.DRAW)
            self.total_strokes += 1
        elif fingers_count == 2 and fingers_up[1] and fingers_up[2]:  # 食指和中指
            self.virtual_canvas.draw_point(index_pos, DrawingAction.ERASE)
        elif fingers_count == 5:  # 所有手指伸直
            self.virtual_canvas.clear_canvas()
            self.total_strokes = 0
        else:
            self.virtual_canvas.stop_drawing()


__all__ = ["DrawingService", "DrawingMode", "DrawingColor"]
