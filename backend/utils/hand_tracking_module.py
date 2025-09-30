# =============================================================================
# hand_tracking_module.py - MediaPipe手勢追蹤模組
# =============================================================================
# 基於MediaPipe實現的手勢追蹤和識別模組，用於手勢控制繪畫功能
# =============================================================================

import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from types import SimpleNamespace

from .gpu_runtime import configure_gpu_runtime

configure_gpu_runtime()

try:
    import mediapipe as mp
    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - depends on runtime installation
    mp = SimpleNamespace(solutions=SimpleNamespace(hands=None))
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)


class GestureType(Enum):
    """手勢類型枚舉"""
    NONE = "none"
    DRAWING = "drawing"
    SELECTION = "selection"
    CLEAR = "clear"
    UNKNOWN = "unknown"


@dataclass
class HandLandmark:
    """手部關鍵點數據結構"""
    x: float
    y: float
    z: float
    visibility: float = 1.0


@dataclass
class GestureResult:
    """手勢識別結果數據結構"""
    gesture_type: GestureType
    confidence: float
    drawing_position: Optional[Tuple[int, int]] = None
    selection_position: Optional[Tuple[int, int]] = None
    landmarks: Optional[List[HandLandmark]] = None
    hand_detected: bool = False


class HandTrackingModule:
    """基於MediaPipe的手勢追蹤模組"""

    # 手指關鍵點索引
    FINGER_TIPS = [4, 8, 12, 16, 20]  # 拇指, 食指, 中指, 無名指, 小指尖端
    FINGER_PIPS = [3, 6, 10, 14, 18]  # 對應的關節點

    # 預設配置
    DEFAULT_CONFIG = {
        'max_num_hands': 1,
        'min_detection_confidence': 0.4,  # 降低檢測閾值，減少誤判
        'min_tracking_confidence': 0.3,   # 降低追蹤閾值，提高穩定性
        'model_complexity': 0             # 使用較簡單的模型，提高速度
    }

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化手勢追蹤模組

        Args:
            config: 配置字典
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}

        self.mediapipe_ready = _MEDIAPIPE_AVAILABLE and mp is not None
        self.init_error = _MEDIAPIPE_ERROR
        self.hands = None
        self.mp_hands = None
        self.mp_draw = None
        self.mp_draw_styles = None

        if self.mediapipe_ready:
            try:
                self.mp_hands = mp.solutions.hands
                self.mp_draw = mp.solutions.drawing_utils
                self.mp_draw_styles = mp.solutions.drawing_styles
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.config['max_num_hands'],
                    min_detection_confidence=self.config['min_detection_confidence'],
                    min_tracking_confidence=self.config['min_tracking_confidence'],
                    model_complexity=self.config['model_complexity']
                )
            except Exception as exc:  # pragma: no cover - depends on GPU drivers
                self.mediapipe_ready = False
                self.init_error = str(exc)
                self.hands = None

        # 狀態追蹤
        self.previous_gesture = GestureType.NONE
        self.current_stable_gesture = GestureType.NONE  # 當前穩定的手勢
        self.gesture_stability_count = 0
        self.stability_threshold = 5  # 需要連續檢測到相同手勢5次才確認，減少閃爍

        # 繪畫相關
        self.previous_drawing_pos = None
        self.drawing_smoothing_factor = 0.7  # 位置平滑係數

    def process_frame(self, frame: np.ndarray) -> GestureResult:
        """
        處理單一影像幀，檢測手勢

        Args:
            frame: 輸入影像幀 (BGR格式)

        Returns:
            GestureResult: 手勢識別結果
        """
        try:
            if frame is None or not self.mediapipe_ready or self.hands is None:
                return GestureResult(
                    gesture_type=GestureType.UNKNOWN,
                    confidence=0.0,
                    hand_detected=False
                )

            # 轉換顏色空間 (BGR -> RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                # 取第一隻手的關鍵點
                hand_landmarks = results.multi_hand_landmarks[0]
                landmarks = self._extract_landmarks(hand_landmarks, frame.shape)

                # 識別手勢類型
                gesture_type = self._classify_gesture(landmarks)

                # 應用穩定性檢查
                stable_gesture = self._apply_gesture_stability(gesture_type)

                # 獲取相關位置
                drawing_pos = None
                selection_pos = None

                if stable_gesture == GestureType.DRAWING:
                    drawing_pos = self._get_drawing_position(landmarks, frame.shape)
                elif stable_gesture == GestureType.SELECTION:
                    selection_pos = self._get_selection_position(landmarks, frame.shape)

                return GestureResult(
                    gesture_type=stable_gesture,
                    confidence=self._calculate_confidence(landmarks, stable_gesture),
                    drawing_position=drawing_pos,
                    selection_position=selection_pos,
                    landmarks=landmarks,
                    hand_detected=True
                )
            else:
                # 沒有檢測到手
                self._reset_gesture_stability()
                return GestureResult(
                    gesture_type=GestureType.NONE,
                    confidence=0.0,
                    hand_detected=False
                )

        except Exception as e:
            print(f"手勢處理錯誤: {e}")
            return GestureResult(
                gesture_type=GestureType.UNKNOWN,
                confidence=0.0,
                hand_detected=False
            )

    def _extract_landmarks(self, hand_landmarks, frame_shape: Tuple[int, int, int]) -> List[HandLandmark]:
        """提取手部關鍵點"""
        height, width = frame_shape[:2]
        landmarks = []

        for landmark in hand_landmarks.landmark:
            landmarks.append(HandLandmark(
                x=landmark.x * width,
                y=landmark.y * height,
                z=landmark.z,
                visibility=getattr(landmark, 'visibility', 1.0)
            ))

        return landmarks

    def _classify_gesture(self, landmarks: List[HandLandmark]) -> GestureType:
        """
        根據手部關鍵點分類手勢類型

        Args:
            landmarks: 手部關鍵點列表

        Returns:
            GestureType: 識別的手勢類型
        """
        if not landmarks or len(landmarks) < 21:
            return GestureType.NONE

        # 檢測哪些手指伸直
        fingers_up = self._get_fingers_up(landmarks)
        fingers_count = sum(fingers_up)

        # 根據伸直的手指數量和組合判斷手勢
        if fingers_count == 1 and fingers_up[1] == 1:  # 只有食指
            return GestureType.DRAWING
        elif fingers_count == 2 and fingers_up[1] == 1 and fingers_up[2] == 1:  # 食指 + 中指
            return GestureType.SELECTION
        elif fingers_count == 5:  # 五指全開
            return GestureType.CLEAR
        else:
            return GestureType.NONE

    def _get_fingers_up(self, landmarks: List[HandLandmark]) -> List[int]:
        """
        檢測哪些手指伸直

        Args:
            landmarks: 手部關鍵點

        Returns:
            List[int]: 每個手指的狀態 (0=彎曲, 1=伸直)
        """
        fingers = []

        # 拇指 (比較x座標，因為拇指是橫向的)
        if landmarks[self.FINGER_TIPS[0]].x > landmarks[self.FINGER_PIPS[0]].x:
            fingers.append(1)
        else:
            fingers.append(0)

        # 其他四指 (比較y座標)
        for i in range(1, 5):
            if landmarks[self.FINGER_TIPS[i]].y < landmarks[self.FINGER_PIPS[i]].y:
                fingers.append(1)
            else:
                fingers.append(0)

        return fingers

    def _apply_gesture_stability(self, current_gesture: GestureType) -> GestureType:
        """
        應用手勢穩定性檢查，避免抖動

        Args:
            current_gesture: 當前檢測到的手勢

        Returns:
            GestureType: 穩定的手勢類型
        """
        if current_gesture == self.previous_gesture:
            self.gesture_stability_count += 1
        else:
            self.gesture_stability_count = 1
            self.previous_gesture = current_gesture

        # 只有連續檢測到相同手勢達到閾值才確認變更
        if self.gesture_stability_count >= self.stability_threshold:
            self.current_stable_gesture = current_gesture

        # 返回當前穩定的手勢，而不是NONE
        return self.current_stable_gesture

    def _reset_gesture_stability(self):
        """重置手勢穩定性計數"""
        self.previous_gesture = GestureType.NONE
        self.current_stable_gesture = GestureType.NONE
        self.gesture_stability_count = 0

    def _get_drawing_position(self, landmarks: List[HandLandmark], frame_shape: Tuple[int, int, int]) -> Tuple[int, int]:
        """
        獲取繪畫位置 (食指尖端)

        Args:
            landmarks: 手部關鍵點
            frame_shape: 影像尺寸

        Returns:
            Tuple[int, int]: 繪畫位置座標
        """
        if not landmarks:
            return None

        # 使用食指尖端作為繪畫點
        index_tip = landmarks[8]  # 食指尖端

        # 座標範圍檢查
        height, width = frame_shape[:2]
        x = max(0, min(width - 1, int(index_tip.x)))
        y = max(0, min(height - 1, int(index_tip.y)))

        # 應用位置平滑
        if self.previous_drawing_pos:
            prev_x, prev_y = self.previous_drawing_pos
            x = int(prev_x * self.drawing_smoothing_factor + x * (1 - self.drawing_smoothing_factor))
            y = int(prev_y * self.drawing_smoothing_factor + y * (1 - self.drawing_smoothing_factor))

        current_pos = (x, y)
        self.previous_drawing_pos = current_pos

        return current_pos

    def _get_selection_position(self, landmarks: List[HandLandmark], frame_shape: Tuple[int, int, int]) -> Tuple[int, int]:
        """
        獲取選擇位置 (食指和中指中點)

        Args:
            landmarks: 手部關鍵點
            frame_shape: 影像尺寸

        Returns:
            Tuple[int, int]: 選擇位置座標
        """
        if not landmarks:
            return None

        # 計算食指和中指尖端的中點
        index_tip = landmarks[8]  # 食指尖端
        middle_tip = landmarks[12]  # 中指尖端

        x = int((index_tip.x + middle_tip.x) / 2)
        y = int((index_tip.y + middle_tip.y) / 2)

        # 座標範圍檢查
        height, width = frame_shape[:2]
        x = max(0, min(width - 1, x))
        y = max(0, min(height - 1, y))

        return (x, y)

    def _calculate_confidence(self, landmarks: List[HandLandmark], gesture_type: GestureType) -> float:
        """
        計算手勢識別的信心度

        Args:
            landmarks: 手部關鍵點
            gesture_type: 手勢類型

        Returns:
            float: 信心度 (0.0-1.0)
        """
        if not landmarks or gesture_type == GestureType.NONE:
            return 0.0

        # 基礎信心度基於關鍵點可見性
        base_confidence = sum(landmark.visibility for landmark in landmarks) / len(landmarks)

        # 根據手勢穩定性調整信心度
        stability_factor = min(1.0, self.gesture_stability_count / self.stability_threshold)

        # 根據手勢類型的特徵清晰度調整
        gesture_clarity = self._assess_gesture_clarity(landmarks, gesture_type)

        final_confidence = base_confidence * stability_factor * gesture_clarity
        return max(0.0, min(1.0, final_confidence))

    def _assess_gesture_clarity(self, landmarks: List[HandLandmark], gesture_type: GestureType) -> float:
        """
        評估手勢特徵的清晰度

        Args:
            landmarks: 手部關鍵點
            gesture_type: 手勢類型

        Returns:
            float: 清晰度分數 (0.0-1.0)
        """
        if gesture_type == GestureType.DRAWING:
            # 檢查食指是否明顯伸直
            index_tip = landmarks[8]
            index_pip = landmarks[6]
            index_mcp = landmarks[5]

            # 計算食指的直線度
            tip_to_pip = math.sqrt((index_tip.x - index_pip.x)**2 + (index_tip.y - index_pip.y)**2)
            pip_to_mcp = math.sqrt((index_pip.x - index_mcp.x)**2 + (index_pip.y - index_mcp.y)**2)
            tip_to_mcp = math.sqrt((index_tip.x - index_mcp.x)**2 + (index_tip.y - index_mcp.y)**2)

            # 直線度評分 (越接近直線得分越高)
            if tip_to_mcp > 0:
                straightness = (tip_to_pip + pip_to_mcp) / tip_to_mcp
                clarity = max(0.0, min(1.0, (straightness - 1.0) * 2))
            else:
                clarity = 0.0

        elif gesture_type == GestureType.SELECTION:
            # 檢查食指和中指的平行度
            index_tip = landmarks[8]
            middle_tip = landmarks[12]
            index_pip = landmarks[6]
            middle_pip = landmarks[10]

            # 計算兩指的方向向量
            index_vector = (index_tip.x - index_pip.x, index_tip.y - index_pip.y)
            middle_vector = (middle_tip.x - middle_pip.x, middle_tip.y - middle_pip.y)

            # 計算向量夾角 (越平行得分越高)
            dot_product = index_vector[0] * middle_vector[0] + index_vector[1] * middle_vector[1]
            index_mag = math.sqrt(index_vector[0]**2 + index_vector[1]**2)
            middle_mag = math.sqrt(middle_vector[0]**2 + middle_vector[1]**2)

            if index_mag > 0 and middle_mag > 0:
                cos_angle = abs(dot_product / (index_mag * middle_mag))
                clarity = cos_angle  # cosine接近1表示平行
            else:
                clarity = 0.0

        elif gesture_type == GestureType.CLEAR:
            # 檢查五指是否都充分展開
            fingers_up = self._get_fingers_up(landmarks)
            clarity = sum(fingers_up) / 5.0  # 展開的手指比例

        else:
            clarity = 1.0

        return clarity

    def draw_landmarks_on_frame(self, frame: np.ndarray, landmarks: List[HandLandmark],
                               gesture_type: GestureType = None) -> np.ndarray:
        """
        在影像上繪製手部關鍵點和手勢狀態

        Args:
            frame: 輸入影像
            landmarks: 手部關鍵點
            gesture_type: 當前手勢類型

        Returns:
            np.ndarray: 帶有標註的影像
        """
        if not landmarks:
            return frame

        # 轉換關鍵點格式
        height, width = frame.shape[:2]
        landmark_points = []
        for landmark in landmarks:
            landmark_points.append([landmark.x / width, landmark.y / height])

        # 創建MediaPipe格式的關鍵點
        mp_landmarks = mp.solutions.hands.HandLandmarks()
        for i, point in enumerate(landmark_points):
            mp_landmarks.landmark.add(x=point[0], y=point[1], z=landmarks[i].z)

        # 繪製關鍵點
        self.mp_draw.draw_landmarks(
            frame,
            mp_landmarks,
            self.mp_hands.HAND_CONNECTIONS,
            self.mp_draw_styles.get_default_hand_landmarks_style(),
            self.mp_draw_styles.get_default_hand_connections_style()
        )

        # 根據手勢類型添加特殊標記
        if gesture_type == GestureType.DRAWING:
            # 在食指尖端繪製繪畫點
            index_tip = landmarks[8]
            cv2.circle(frame, (int(index_tip.x), int(index_tip.y)), 10, (0, 255, 0), -1)
            cv2.putText(frame, "DRAWING", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        elif gesture_type == GestureType.SELECTION:
            # 在選擇點繪製選擇標記
            index_tip = landmarks[8]
            middle_tip = landmarks[12]
            center_x = int((index_tip.x + middle_tip.x) / 2)
            center_y = int((index_tip.y + middle_tip.y) / 2)
            cv2.circle(frame, (center_x, center_y), 15, (255, 0, 0), 3)
            cv2.putText(frame, "SELECTION", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        elif gesture_type == GestureType.CLEAR:
            cv2.putText(frame, "CLEAR", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        return frame

    def get_distance_between_landmarks(self, landmarks: List[HandLandmark],
                                     index1: int, index2: int) -> float:
        """
        計算兩個關鍵點之間的距離

        Args:
            landmarks: 手部關鍵點
            index1: 第一個關鍵點索引
            index2: 第二個關鍵點索引

        Returns:
            float: 距離
        """
        if not landmarks or index1 >= len(landmarks) or index2 >= len(landmarks):
            return 0.0

        point1 = landmarks[index1]
        point2 = landmarks[index2]

        distance = math.sqrt(
            (point1.x - point2.x)**2 +
            (point1.y - point2.y)**2 +
            (point1.z - point2.z)**2
        )

        return distance

    def cleanup(self):
        """清理資源"""
        if hasattr(self, 'hands'):
            self.hands.close()
