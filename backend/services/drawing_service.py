# =============================================================================
# drawing_service.py - AI 畫布識別服務
# 基於 MediaPipe 和手勢追蹤的虛擬繪畫和 AI 圖像識別系統
# =============================================================================

import logging
import os
import threading
import time
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
import base64
import io

import cv2
import numpy as np
from PIL import Image, ImageDraw

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
                    min_detection_confidence=0.7,
                    min_tracking_confidence=0.5
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
        """檢測哪些手指是伸直的"""
        fingers = []

        # 拇指 (特殊處理)
        if hand_landmarks.landmark[4].x > hand_landmarks.landmark[3].x:
            fingers.append(True)
        else:
            fingers.append(False)

        # 其他四指
        for finger_tip, finger_pip in [(8, 6), (12, 10), (16, 14), (20, 18)]:
            if hand_landmarks.landmark[finger_tip].y < hand_landmarks.landmark[finger_pip].y:
                fingers.append(True)
            else:
                fingers.append(False)

        return fingers


class VirtualCanvas:
    """虛擬畫布"""

    def __init__(self, width: int = 640, height: int = 480):
        self.width = width
        self.height = height
        self.canvas = np.zeros((height, width, 3), dtype=np.uint8)
        self.drawing_points = deque(maxlen=1000)  # 最近1000個繪畫點
        self.current_color = DrawingColor.BLACK.value
        self.brush_size = 5
        self.is_drawing = False
        self.last_position = None

    def clear_canvas(self):
        """清空畫布"""
        self.canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
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
                cv2.line(self.canvas, self.last_position, (x, y), self.current_color, self.brush_size)
            else:
                # 畫點
                cv2.circle(self.canvas, (x, y), self.brush_size // 2, self.current_color, -1)

            self.drawing_points.append({
                'position': (x, y),
                'color': self.current_color,
                'size': self.brush_size,
                'timestamp': time.time()
            })

        elif action == DrawingAction.ERASE:
            # 橡皮擦效果
            cv2.circle(self.canvas, (x, y), self.brush_size * 2, (0, 0, 0), -1)

        self.last_position = (x, y)

    def stop_drawing(self):
        """停止繪畫（抬筆）"""
        self.last_position = None

    def get_canvas_image(self) -> np.ndarray:
        """獲取當前畫布圖像"""
        return self.canvas.copy()

    def get_canvas_base64(self) -> str:
        """獲取畫布的 base64 編碼"""
        # 轉換為 PIL Image
        pil_image = Image.fromarray(cv2.cvtColor(self.canvas, cv2.COLOR_BGR2RGB))

        # 轉換為 base64
        buffered = io.BytesIO()
        pil_image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"


class SimpleAIRecognizer:
    """簡單的 AI 識別器（基於形狀分析）"""

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
        # 轉為灰度圖
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
        self.ai_recognizer = SimpleAIRecognizer()

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

    def start_drawing_session(self,
                            mode: str = "index_finger",
                            color: str = "black",
                            auto_recognize: bool = True) -> Dict:
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

            # 開啟攝影機
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                return {"status": "error", "message": "無法開啟攝影機"}

            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)

            # 重置狀態
            self.virtual_canvas.clear_canvas()
            self.virtual_canvas.set_color(self.current_color)
            self.drawing_start_time = time.time()
            self.total_strokes = 0
            self.recognition_history = []

            # 開始繪畫線程
            self.is_drawing = True
            self.drawing_thread = threading.Thread(
                target=self._drawing_loop,
                daemon=True
            )
            self.drawing_thread.start()

            # 廣播開始狀態
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "drawing",
                "stage": "started",
                "message": "AI 畫布會話已開始",
                "data": {
                    "mode": mode,
                    "color": color,
                    "auto_recognize": auto_recognize,
                    "start_time": self.drawing_start_time
                }
            })

            return {
                "status": "started",
                "message": "繪畫會話已開始",
                "mode": mode,
                "color": color
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