import logging
import os
import threading
import time
import tempfile
from collections import deque
from enum import Enum
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import cv2
import numpy as np

from ..utils.gpu_runtime import configure_gpu_runtime

_GPU_STATUS = configure_gpu_runtime()

# MediaPipe 依賴初始化（GPU 加速設定在 backend.utils.gpu_runtime 中處理）
try:  # pragma: no cover - 匯入狀態依賴執行環境
    import mediapipe as mp

    _MEDIAPIPE_AVAILABLE = True
    _MEDIAPIPE_ERROR: Optional[str] = None
except Exception as exc:  # pragma: no cover - 匯入失敗時提供退回方案
    mp = SimpleNamespace(solutions=SimpleNamespace(face_mesh=None, hands=None))
    _MEDIAPIPE_AVAILABLE = False
    _MEDIAPIPE_ERROR = str(exc)

# TensorFlow 記憶體配置 - 優先使用 CPU 避免 GPU OOM
try:
    import tensorflow as tf
    import os

    # 環境變數配置
    os.environ['TF_DISABLE_TENSORBOARD'] = '1'
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # 減少日誌輸出

    # 檢查是否強制使用 CPU
    force_cpu = os.environ.get('EMOTION_FORCE_CPU', 'true').lower() == 'true'

    if force_cpu:
        print("🔄 強制使用 CPU 模式以避免 GPU 記憶體問題")
        os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # 隱藏所有 GPU
        os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'false'
    else:
        print("🎮 嘗試使用 GPU 模式")
        os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'
        os.environ['CUDA_VISIBLE_DEVICES'] = '0'
        # GPU 記憶體控制
        os.environ['TF_GPU_ALLOCATOR'] = 'cuda_malloc_async'
        os.environ['TF_GPU_THREAD_MODE'] = 'gpu_private'

    gpus = tf.config.list_physical_devices('GPU')
    if gpus and not force_cpu:
        try:
            # 嘗試設定 GPU 記憶體限制
            for gpu in gpus:
                tf.config.set_logical_device_configuration(
                    gpu,
                    [tf.config.LogicalDeviceConfiguration(memory_limit=2048)]  # 降到 2GB
                )

            for gpu in gpus:
                tf.config.experimental.set_memory_growth(gpu, True)

            print(f"✅ GPU 記憶體限制已設定 (2GB): {len(gpus)} 個 GPU 可用")

            # 確認 GPU 真正可用於運算
            with tf.device('/GPU:0'):
                test_tensor = tf.constant([1.0, 2.0])
                result = tf.square(test_tensor)
                print(f"✅ GPU 運算測試通過: {result.numpy()}")

            # 列出 TensorFlow 正在使用的設備
            print(f"📊 可用的物理設備: {[dev.name for dev in tf.config.list_physical_devices()]}")
            print(f"🎯 邏輯GPU設備: {[dev.name for dev in tf.config.list_logical_devices('GPU')]}")

        except RuntimeError as e:
            print(f"⚠️ GPU 記憶體配置失敗: {e}")
    else:
        print("ℹ️ 未檢測到 GPU，使用 CPU")

except ImportError:
    print("⚠️ TensorFlow 未安裝")

# DeepFace 依賴初始化 (人臉情緒分析)
_EMOTION_MODEL = None
try:
    from deepface import DeepFace
    # 注意：新版DeepFace (0.0.85+) 可能移除了build_model方法
    # 先檢查DeepFace是否可用，模型將在第一次調用時自動加載
    _DEEPFACE_AVAILABLE = True
    _DEEPFACE_ERROR: Optional[str] = None
    logging.info("DeepFace 已就緒，模型將在首次使用時加載")
except Exception as exc:
    DeepFace = None
    _EMOTION_MODEL = None
    _DEEPFACE_AVAILABLE = False
    _DEEPFACE_ERROR = str(exc)
    logging.warning(f"DeepFace 不可用: {exc}")

from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts


logger = logging.getLogger(__name__)

if _GPU_STATUS.warnings:
    for warning in _GPU_STATUS.warnings:
        logger.warning("GPU setup warning: %s", warning)
else:
    logger.info(
        "GPU runtime ready | TensorFlow devices: %s | MediaPipe GPU enabled: %s",
        _GPU_STATUS.tensorflow_devices,
        _GPU_STATUS.mediapipe_gpu_enabled,
    )


class EmotionType(Enum):
    """情緒類型枚舉"""
    HAPPY = "開心"
    SAD = "悲傷"
    ANGRY = "生氣"
    SURPRISED = "驚訝"
    FEARFUL = "恐懼"
    DISGUSTED = "厭惡"
    NEUTRAL = "中性"


# 情緒中英文對照表
EMOTION_TRANSLATIONS = {
    "開心": {"en": "happy", "zh": "開心", "emoji": "😊"},
    "悲傷": {"en": "sad", "zh": "悲傷", "emoji": "😢"},
    "生氣": {"en": "angry", "zh": "生氣", "emoji": "😠"},
    "驚訝": {"en": "surprise", "zh": "驚訝", "emoji": "😲"},
    "恐懼": {"en": "fear", "zh": "恐懼", "emoji": "😨"},
    "厭惡": {"en": "disgust", "zh": "厭惡", "emoji": "🤢"},
    "中性": {"en": "neutral", "zh": "面無表情", "emoji": "😐"}
}


class FacialFeatureExtractor:
    """臉部特徵提取器，基於 MediaPipe FaceMesh."""

    def __init__(self):
        self.mediapipe_ready = _MEDIAPIPE_AVAILABLE
        self.init_error: Optional[str] = _MEDIAPIPE_ERROR
        self.face_mesh_stream = None
        self.face_mesh_static = None
        self.face_mesh_lock = threading.Lock()

        # MediaPipe 468點人臉網格關鍵索引
        self.LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
        self.RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]
        self.MOUTH_INDICES = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 16]
        self.EYEBROW_LEFT_INDICES = [70, 63, 105, 66, 107, 55, 65]
        self.EYEBROW_RIGHT_INDICES = [296, 334, 293, 300, 276, 283, 282]
        self.NOSE_TIP = 1
        self.CHIN = 175

        if self.mediapipe_ready:
            try:
                self.mp_face_mesh = mp.solutions.face_mesh
                # 動態串流情境（攝影機/影片）
                self.face_mesh_stream = self.mp_face_mesh.FaceMesh(
                    static_image_mode=False,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                # 靜態圖片情境
                self.face_mesh_static = self.mp_face_mesh.FaceMesh(
                    static_image_mode=True,
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
                logger.info("MediaPipe FaceMesh 初始化完成，啟用真實情緒檢測")
            except Exception as exc:  # pragma: no cover - 初始化失敗時記錄
                self.mediapipe_ready = False
                self.init_error = str(exc)
                logger.exception("初始化 MediaPipe FaceMesh 失敗: %s", exc)
        else:
            logger.warning("MediaPipe FaceMesh 無法使用: %s", self.init_error)

    def is_available(self) -> bool:
        """回傳 MediaPipe 是否可用。"""
        return self.mediapipe_ready and self.face_mesh_stream is not None and self.face_mesh_static is not None

    def extract_features(self, frame, static_image: bool = False) -> Optional[Dict]:
        """從影像幀中提取臉部特徵。"""
        if frame is None or not self.is_available():
            return None

        height, width = frame.shape[:2]
        mesh = self.face_mesh_static if static_image else self.face_mesh_stream
        if mesh is None:
            return None

        # MediaPipe 需要 RGB 影像
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        with self.face_mesh_lock:
            results = mesh.process(frame_rgb)

        if not results or not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark
        if len(landmarks) < 468:
            return None

        # 將標記轉換為像素座標，並保留深度資訊用於對稱性分析
        points = [(lm.x * width, lm.y * height, lm.z * width) for lm in landmarks]

        face_width = abs(points[454][0] - points[234][0]) if len(points) > 454 else float(width)
        face_height = abs(points[152][1] - points[10][1]) if len(points) > 152 else float(height)

        if face_width <= 0:
            face_width = float(width)
        if face_height <= 0:
            face_height = float(height)

        features = {
            "eye_aspect_ratio_left": self._calculate_eye_aspect_ratio(points, self.LEFT_EYE_INDICES),
            "eye_aspect_ratio_right": self._calculate_eye_aspect_ratio(points, self.RIGHT_EYE_INDICES),
            "mouth_aspect_ratio": self._calculate_mouth_aspect_ratio(points),
            "mouth_curvature": self._calculate_mouth_curvature(points, face_height),
            "eyebrow_height_left": self._calculate_eyebrow_relative_height(points, self.EYEBROW_LEFT_INDICES, self.LEFT_EYE_INDICES, face_height),
            "eyebrow_height_right": self._calculate_eyebrow_relative_height(points, self.EYEBROW_RIGHT_INDICES, self.RIGHT_EYE_INDICES, face_height),
            "nose_wrinkle": self._calculate_nose_wrinkle(points, face_width),
            "eye_openness": self._calculate_eye_openness(points),
            "mouth_width": self._calculate_mouth_width(points, face_width),
            "facial_symmetry": self._calculate_facial_symmetry(points),
        }

        return features

    def _calculate_eye_aspect_ratio(self, landmarks: List[Tuple], eye_indices: List[int]) -> float:
        """計算眼部長寬比 (EAR)"""
        try:
            if len(eye_indices) < 6:
                return 0.3

            eye_points = [landmarks[i] for i in eye_indices[:6]]

            # 垂直距離
            A = np.linalg.norm(np.array(eye_points[1]) - np.array(eye_points[5]))
            B = np.linalg.norm(np.array(eye_points[2]) - np.array(eye_points[4]))

            # 水平距離
            C = np.linalg.norm(np.array(eye_points[0]) - np.array(eye_points[3]))

            if C == 0:
                return 0.3

            ear = (A + B) / (2.0 * C)
            return ear
        except:
            return 0.3

    def _calculate_mouth_aspect_ratio(self, landmarks: List[Tuple]) -> float:
        """計算嘴部長寬比 (MAR)"""
        try:
            mouth_points = [landmarks[i] for i in self.MOUTH_INDICES[:6]]

            # 垂直距離
            A = np.linalg.norm(np.array(mouth_points[1]) - np.array(mouth_points[5]))
            B = np.linalg.norm(np.array(mouth_points[2]) - np.array(mouth_points[4]))

            # 水平距離
            C = np.linalg.norm(np.array(mouth_points[0]) - np.array(mouth_points[3]))

            if C == 0:
                return 0.1

            mar = (A + B) / (2.0 * C)
            return mar
        except:
            return 0.1

    def _calculate_mouth_curvature(self, landmarks: List[Tuple], face_height: float) -> float:
        """計算嘴角彎曲度（以臉部高度正規化）。"""
        try:
            left_corner = landmarks[78]
            right_corner = landmarks[308]
            top_lip = landmarks[13]
            bottom_lip = landmarks[14]

            mouth_center_y = (top_lip[1] + bottom_lip[1]) / 2
            left_height = mouth_center_y - left_corner[1]
            right_height = mouth_center_y - right_corner[1]

            curvature = (left_height + right_height) / 2
            normalized = curvature / max(face_height, 1e-6)
            return float(normalized * 100)
        except Exception:
            return 0.0

    def _calculate_eyebrow_relative_height(
        self,
        landmarks: List[Tuple],
        eyebrow_indices: List[int],
        eye_indices: List[int],
        face_height: float,
    ) -> float:
        """計算眉毛相對於眼睛的高度差。"""
        try:
            eyebrow_points = [landmarks[i] for i in eyebrow_indices]
            eyebrow_center_y = sum(p[1] for p in eyebrow_points) / len(eyebrow_points)

            eye_points = [landmarks[i] for i in eye_indices[:6]]
            eye_center_y = sum(p[1] for p in eye_points) / len(eye_points)

            relative_height = (eye_center_y - eyebrow_center_y) / max(face_height, 1e-6)
            return float(relative_height * 100)
        except Exception:
            return 0.0

    def _calculate_nose_wrinkle(self, landmarks: List[Tuple], face_width: float) -> float:
        """計算鼻子皺紋 (鼻翼變化)"""
        try:
            left_nostril = landmarks[31]
            right_nostril = landmarks[35]

            # 計算鼻翼寬度
            nostril_width = abs(right_nostril[0] - left_nostril[0])

            # 正常化
            if face_width == 0:
                return 0.0

            normalized_width = nostril_width / face_width
            return float(normalized_width)
        except Exception:
            return 0.0

    def _calculate_eye_openness(self, landmarks: List[Tuple]) -> float:
        """計算眼睛開合度"""
        left_ear = self._calculate_eye_aspect_ratio(landmarks, self.LEFT_EYE_INDICES)
        right_ear = self._calculate_eye_aspect_ratio(landmarks, self.RIGHT_EYE_INDICES)
        return (left_ear + right_ear) / 2

    def _calculate_mouth_width(self, landmarks: List[Tuple], face_width: float) -> float:
        """計算嘴巴寬度"""
        try:
            left_corner = landmarks[78]
            right_corner = landmarks[308]
            mouth_width = abs(right_corner[0] - left_corner[0])

            # 正常化
            if face_width == 0:
                return 0.0

            normalized_width = mouth_width / face_width
            return float(normalized_width)
        except Exception:
            return 0.0

    def _calculate_facial_symmetry(self, landmarks: List[Tuple]) -> float:
        """計算臉部對稱性"""
        try:
            # 計算臉部中線
            nose_tip = landmarks[self.NOSE_TIP]
            chin = landmarks[self.CHIN]
            forehead = landmarks[10]

            face_center_x = (nose_tip[0] + chin[0] + forehead[0]) / 3

            # 計算左右對稱點的距離差異
            symmetry_points = [
                (landmarks[33], landmarks[362]),    # 眼角
                (landmarks[78], landmarks[308]),    # 嘴角
                (landmarks[234], landmarks[454])    # 臉頰
            ]

            asymmetry_sum = 0
            for left_point, right_point in symmetry_points:
                left_dist = abs(left_point[0] - face_center_x)
                right_dist = abs(right_point[0] - face_center_x)
                asymmetry_sum += abs(left_dist - right_dist)

            # 正常化對稱性分數 (較低的值表示更對稱)
            face_width = abs(landmarks[454][0] - landmarks[234][0])
            if face_width == 0:
                return 0.5

            symmetry_score = 1.0 - (asymmetry_sum / (face_width * len(symmetry_points)))
            return max(0.0, min(1.0, symmetry_score))
        except:
            return 0.5


class EmotionDetector:
    """情緒檢測器"""

    def __init__(self):
        self.emotion_history = deque(maxlen=10)  # 保存最近10次檢測結果
        self.latest_scores: Dict[str, float] = {}

        # 情緒檢測閾值 (可根據實際測試調整)
        self.thresholds = {
            'smile_curvature': 5.0,
            'surprise_eyebrow': -10.0,
            'eye_openness_high': 0.4,
            'eye_openness_low': 0.15,
            'mouth_open_surprise': 0.15,
            'mouth_open_sad': 0.05
        }

    def detect_emotion(self, features: Dict) -> Tuple[EmotionType, float]:
        """檢測情緒並返回情緒類型和信心度"""
        if not features:
            return EmotionType.NEUTRAL, 0.5

        # 提取關鍵特徵
        mouth_curvature = features.get('mouth_curvature', 0)
        eye_openness = features.get('eye_openness', 0.3)
        mouth_aspect_ratio = features.get('mouth_aspect_ratio', 0.1)
        mouth_width = features.get('mouth_width', 0.0)
        eyebrow_left = features.get('eyebrow_height_left', 0)
        eyebrow_right = features.get('eyebrow_height_right', 0)
        nose_wrinkle = features.get('nose_wrinkle', 0)

        # 情緒分數
        emotion_scores = {
            EmotionType.HAPPY: 0.0,
            EmotionType.SAD: 0.0,
            EmotionType.ANGRY: 0.0,
            EmotionType.SURPRISED: 0.0,
            EmotionType.FEARFUL: 0.0,
            EmotionType.DISGUSTED: 0.0,
            EmotionType.NEUTRAL: 0.5
        }

        # 開心檢測 (微笑)
        if mouth_curvature > self.thresholds['smile_curvature']:
            emotion_scores[EmotionType.HAPPY] += 0.6
        if mouth_width > 0.15:  # 嘴巴變寬
            emotion_scores[EmotionType.HAPPY] += 0.3
        if eye_openness > 0.25 and eye_openness < 0.4:  # 眼睛微瞇
            emotion_scores[EmotionType.HAPPY] += 0.1

        # 驚訝檢測
        if eye_openness > self.thresholds['eye_openness_high']:
            emotion_scores[EmotionType.SURPRISED] += 0.4
        if mouth_aspect_ratio > self.thresholds['mouth_open_surprise']:
            emotion_scores[EmotionType.SURPRISED] += 0.3
        average_eyebrow = (eyebrow_left + eyebrow_right) / 2
        if average_eyebrow < self.thresholds['surprise_eyebrow']:  # 眉毛上揚
            emotion_scores[EmotionType.SURPRISED] += 0.3

        # 悲傷檢測
        if mouth_curvature < -3.0:  # 嘴角下垂
            emotion_scores[EmotionType.SAD] += 0.4
        if eye_openness < self.thresholds['eye_openness_low']:  # 眼睛半閉
            emotion_scores[EmotionType.SAD] += 0.3
        if mouth_aspect_ratio < self.thresholds['mouth_open_sad']:  # 嘴巴緊閉
            emotion_scores[EmotionType.SAD] += 0.2
        if average_eyebrow > 10.0:  # 眉毛下垂
            emotion_scores[EmotionType.SAD] += 0.1

        # 生氣檢測
        if nose_wrinkle > 0.12:  # 鼻翼張開
            emotion_scores[EmotionType.ANGRY] += 0.3
        if average_eyebrow > 15.0:  # 眉毛壓低
            emotion_scores[EmotionType.ANGRY] += 0.3
        if mouth_aspect_ratio < 0.03 and mouth_curvature < 0:  # 嘴巴緊閉且下垂
            emotion_scores[EmotionType.ANGRY] += 0.2
        if eye_openness < 0.2:  # 眼睛瞇起
            emotion_scores[EmotionType.ANGRY] += 0.2

        # 恐懼檢測
        if eye_openness > 0.35 and mouth_aspect_ratio > 0.08:
            emotion_scores[EmotionType.FEARFUL] += 0.4
        if average_eyebrow < -5.0:  # 眉毛上揚
            emotion_scores[EmotionType.FEARFUL] += 0.3
        if mouth_width < 0.08:  # 嘴巴收縮
            emotion_scores[EmotionType.FEARFUL] += 0.2

        # 厭惡檢測
        if nose_wrinkle > 0.1 and mouth_curvature < -2.0:
            emotion_scores[EmotionType.DISGUSTED] += 0.4
        if eye_openness < 0.25:  # 眼睛瞇起
            emotion_scores[EmotionType.DISGUSTED] += 0.3
        if mouth_aspect_ratio < 0.05:  # 嘴巴緊閉
            emotion_scores[EmotionType.DISGUSTED] += 0.2

        # 找到最高分的情緒
        detected_emotion = max(emotion_scores, key=emotion_scores.get)
        confidence = emotion_scores[detected_emotion]

        # 如果所有情緒分數都很低，返回中性
        if confidence < 0.3:
            detected_emotion = EmotionType.NEUTRAL
            confidence = 0.5

        # 限制信心度範圍
        confidence = max(0.0, min(1.0, confidence))

        # 儲存分數快照供外部檢視
        self.latest_scores = {emotion.value: round(score, 4) for emotion, score in emotion_scores.items()}

        # 添加到歷史記錄
        self.emotion_history.append((detected_emotion, confidence))

        return detected_emotion, confidence

    def get_latest_scores(self) -> Dict[str, float]:
        """取得最近一次情緒分數分布。"""
        return dict(self.latest_scores)

    def get_emotion_trend(self) -> Dict:
        """獲取情緒趨勢分析"""
        if not self.emotion_history:
            return {"trend": "stable", "dominant_emotion": EmotionType.NEUTRAL.value}

        # 統計最近情緒分布
        emotion_counts = {}
        total_confidence = 0

        for emotion, confidence in self.emotion_history:
            if emotion not in emotion_counts:
                emotion_counts[emotion] = 0
            emotion_counts[emotion] += confidence
            total_confidence += confidence

        # 找到主導情緒
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)

        # 計算趨勢穩定性
        recent_emotions = [e[0] for e in list(self.emotion_history)[-5:]]
        unique_recent = len(set(recent_emotions))

        if unique_recent <= 2:
            trend = "stable"
        elif unique_recent <= 3:
            trend = "changing"
        else:
            trend = "volatile"

        return {
            "trend": trend,
            "dominant_emotion": dominant_emotion.value,
            "confidence_average": total_confidence / len(self.emotion_history) if self.emotion_history else 0.5,
            "emotion_distribution": {e.value: count for e, count in emotion_counts.items()}
        }


class EmotionService:
    """情緒辨識服務主類"""

    def __init__(self, status_broadcaster: StatusBroadcaster):
        self.status_broadcaster = status_broadcaster
        self.feature_extractor = FacialFeatureExtractor()
        self.emotion_detector = EmotionDetector()

        if not self.feature_extractor.is_available():
            logger.error(
                "MediaPipe FaceMesh 未啟用，情緒分析功能將不可用: %s",
                self.feature_extractor.init_error,
            )

        # 簡化的服務設計：只處理圖片分析，不管理攝影機或檢測狀態

    # 移除了攝影機相關功能，保持服務簡潔專注於圖片分析

    def analyze_image(self, image_path: str) -> Dict:
        """
        分析單張圖片的情緒內容。

        Args:
            image_path (str): 圖片檔案路径

        Returns:
            Dict: 情緒分析結果
        """
        try:
            if not self.feature_extractor.is_available():
                raise ValueError(self.feature_extractor.init_error or "MediaPipe FaceMesh 未就緒")

            start_time = time.time()
            # 讀取圖片
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"無法讀取圖片: {image_path}")

            # 提取特徵
            features = self.feature_extractor.extract_features(image, static_image=True)
            if not features:
                return {
                    "emotion": EmotionType.NEUTRAL.value,
                    "confidence": 0.3,
                    "message": "未檢測到臉部特徵",
                    "analysis_time": _now_ts(),
                    "processing_time": round(time.time() - start_time, 3),
                }

            # 檢測情緒
            emotion, confidence = self.emotion_detector.detect_emotion(features)

            return {
                "emotion": emotion.value,
                "confidence": round(confidence, 3),
                "features": {k: round(float(v), 4) for k, v in features.items()},
                "score_breakdown": self.emotion_detector.get_latest_scores(),
                "message": f"檢測到情緒: {emotion.value}",
                "analysis_time": _now_ts(),
                "processing_time": round(time.time() - start_time, 3),
            }

        except Exception as exc:
            return {
                "emotion": EmotionType.NEUTRAL.value,
                "confidence": 0.0,
                "message": f"分析失敗: {str(exc)}",
                "error": str(exc),
                "analysis_time": _now_ts()
            }

    def analyze_video(self, video_path: str) -> Dict:
        """
        分析影片檔案的情緒內容。

        Args:
            video_path (str): 影片檔案路径

        Returns:
            Dict: 情緒分析結果
        """
        try:
            if not self.feature_extractor.is_available():
                raise ValueError(self.feature_extractor.init_error or "MediaPipe FaceMesh 未就緒")

            start_time = time.time()
            # 開啟影片檔案
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"無法開啟影片: {video_path}")

            # 獲取影片資訊
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            # 重置檢測器歷史
            self.emotion_detector.emotion_history.clear()

            emotions_detected = []
            frames_processed = 0
            feature_sums: Dict[str, float] = {}
            sample_interval = max(1, fps // 2)  # 每秒取2幀分析

            frame_idx = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # 按間隔採樣幀
                if frame_idx % sample_interval == 0:
                    # 提取特徵
                    features = self.feature_extractor.extract_features(frame)

                    if features:
                        # 檢測情緒
                        emotion, confidence = self.emotion_detector.detect_emotion(features)

                        for key, value in features.items():
                            feature_sums[key] = feature_sums.get(key, 0.0) + float(value)

                        emotions_detected.append({
                            "timestamp": frame_idx / fps if fps > 0 else 0,
                            "emotion": emotion.value,
                            "confidence": round(confidence, 3),
                            "scores": self.emotion_detector.get_latest_scores(),
                        })
                        frames_processed += 1

                frame_idx += 1

            cap.release()

            if not emotions_detected:
                return {
                    "dominant_emotion": EmotionType.NEUTRAL.value,
                    "confidence_average": 0.3,
                    "emotions_timeline": [],
                    "message": "影片中未檢測到臉部特徵",
                    "video_info": {
                        "duration": duration,
                        "fps": fps,
                        "frame_count": frame_count,
                        "frames_processed": frames_processed
                    },
                    "feature_averages": {},
                    "analysis_time": _now_ts(),
                    "processing_time": round(time.time() - start_time, 3),
                }

            # 計算統計資料
            emotion_counts = {}
            total_confidence = 0

            for detection in emotions_detected:
                emotion_name = detection["emotion"]
                confidence = detection["confidence"]

                if emotion_name not in emotion_counts:
                    emotion_counts[emotion_name] = {"count": 0, "total_confidence": 0}

                emotion_counts[emotion_name]["count"] += 1
                emotion_counts[emotion_name]["total_confidence"] += confidence
                total_confidence += confidence

            # 找到主導情緒
            dominant_emotion = max(emotion_counts.keys(),
                                 key=lambda x: emotion_counts[x]["total_confidence"])

            # 計算情緒分布百分比
            emotion_distribution = {}
            for emotion_name, data in emotion_counts.items():
                percentage = (data["count"] / len(emotions_detected)) * 100
                avg_confidence = data["total_confidence"] / data["count"]
                emotion_distribution[emotion_name] = {
                    "percentage": round(percentage, 2),
                    "average_confidence": round(avg_confidence, 3)
                }

            feature_averages = {
                feature: round(value / frames_processed, 4)
                for feature, value in feature_sums.items()
                if frames_processed
            }

            return {
                "dominant_emotion": dominant_emotion,
                "confidence_average": round(total_confidence / len(emotions_detected), 3),
                "emotion_distribution": emotion_distribution,
                "emotions_timeline": self._get_key_moments(emotions_detected),
                "trend_analysis": self.emotion_detector.get_emotion_trend(),
                "message": f"影片分析完成，主要情緒: {dominant_emotion}",
                "video_info": {
                    "duration": duration,
                    "fps": fps,
                    "frame_count": frame_count,
                    "frames_processed": frames_processed,
                    "sample_interval": sample_interval
                },
                "feature_averages": feature_averages,
                "analysis_time": _now_ts(),
                "processing_time": round(time.time() - start_time, 3),
            }

        except Exception as exc:
            return {
                "dominant_emotion": EmotionType.NEUTRAL.value,
                "confidence_average": 0.0,
                "message": f"影片分析失敗: {str(exc)}",
                "error": str(exc),
                "analysis_time": _now_ts()
            }

    def _get_key_moments(self, emotions_detected: List[Dict]) -> List[Dict]:
        """
        從完整的情緒檢測結果中篩選出關鍵時刻，避免冗長的時間軸。

        Args:
            emotions_detected: 完整的情緒檢測結果列表

        Returns:
            精簡的關鍵時刻列表
        """
        if not emotions_detected:
            return []

        key_moments = []
        last_emotion = None
        last_added_time = -10  # 確保第一個能被加入

        for detection in emotions_detected:
            current_emotion = detection["emotion"]
            current_time = detection["timestamp"]

            # 條件1: 情緒變化
            emotion_changed = current_emotion != last_emotion

            # 條件2: 時間間隔足夠 (至少5秒)
            time_gap_enough = current_time - last_added_time >= 5.0

            # 條件3: 高信心度檢測 (>80%)
            high_confidence = detection["confidence"] > 0.8

            # 添加關鍵時刻的條件
            should_add = (
                emotion_changed or  # 情緒變化總是重要
                (time_gap_enough and high_confidence)  # 或者間隔夠長且信心度高
            )

            if should_add:
                key_moments.append(detection)
                last_added_time = current_time
                last_emotion = current_emotion

        # 確保至少有開始和結束時刻
        if len(key_moments) == 0 and emotions_detected:
            # 如果沒有關鍵時刻，至少包含第一個和最後一個
            key_moments = [emotions_detected[0]]
            if len(emotions_detected) > 1:
                key_moments.append(emotions_detected[-1])
        elif len(key_moments) == 1 and len(emotions_detected) > 1:
            # 如果只有一個關鍵時刻，加上最後一個
            if key_moments[0] != emotions_detected[-1]:
                key_moments.append(emotions_detected[-1])

        # 限制最多顯示10個關鍵時刻
        return key_moments[:10]


    def _create_simple_result(self, emotion: str, confidence: float) -> Dict:
        """
        創建簡化的情緒分析結果，只包含核心信息

        Args:
            emotion: 情緒名稱 (中文)
            confidence: 信心度

        Returns:
            簡化的結果字典
        """
        emotion_info = EMOTION_TRANSLATIONS.get(emotion, {
            "en": "unknown",
            "zh": emotion,
            "emoji": "❓"
        })

        return {
            "emotion_zh": emotion_info["zh"],
            "emotion_en": emotion_info["en"],
            "emoji": emotion_info["emoji"],
            "confidence": round(confidence, 3)
        }

    def analyze_image_simple(self, image_path: str) -> Dict:
        """
        簡化版圖片情緒分析，只返回核心結果

        Args:
            image_path: 圖片檔案路徑

        Returns:
            簡化的分析結果
        """
        try:
            if not self.feature_extractor.is_available():
                raise ValueError(self.feature_extractor.init_error or "MediaPipe FaceMesh 未就緒")

            # 讀取圖片
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"無法讀取圖片: {image_path}")

            # 提取特徵
            features = self.feature_extractor.extract_features(image, static_image=True)
            if not features:
                return self._create_simple_result("中性", 0.3)

            # 檢測情緒
            emotion, confidence = self.emotion_detector.detect_emotion(features)

            return self._create_simple_result(emotion.value, confidence)

        except Exception as exc:
            return {
                "emotion_zh": "中性",
                "emotion_en": "neutral",
                "emoji": "😐",
                "confidence": 0.0,
                "error": str(exc)
            }

    def analyze_video_simple(self, video_path: str) -> Dict:
        """
        簡化版影片情緒分析，只返回主要情緒結果

        Args:
            video_path: 影片檔案路徑

        Returns:
            簡化的分析結果
        """
        try:
            # 先用完整分析獲取結果
            full_result = self.analyze_video(video_path)

            if "error" in full_result:
                return {
                    "emotion_zh": "中性",
                    "emotion_en": "neutral",
                    "emoji": "😐",
                    "confidence": 0.0,
                    "error": full_result.get("error", "Unknown error")
                }

            # 提取主要情緒
            dominant_emotion = full_result.get("dominant_emotion", "中性")
            confidence = full_result.get("confidence_average", 0.0)

            return self._create_simple_result(dominant_emotion, confidence)

        except Exception as exc:
            return {
                "emotion_zh": "中性",
                "emotion_en": "neutral",
                "emoji": "😐",
                "confidence": 0.0,
                "error": str(exc)
            }

    def analyze_video_deepface_stream(self, video_path: str, frame_interval: float = 0.5):
        """
        使用 DeepFace 進行影片串流情緒分析 (逐幀截取分析)

        Args:
            video_path: 影片檔案路徑
            frame_interval: 截幀間隔(秒), 默認0.5秒

        Yields:
            Dict: 每一幀的情緒分析結果
        """
        if not _DEEPFACE_AVAILABLE:
            yield {
                "error": f"DeepFace 不可用: {_DEEPFACE_ERROR}",
                "frame_time": 0,
                "completed": True
            }
            return

        try:
            import tempfile
            import os

            # 開啟影片檔案
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                yield {
                    "error": f"無法開啟影片: {video_path}",
                    "frame_time": 0,
                    "completed": True
                }
                return

            # 獲取影片資訊
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0
            frame_skip = max(1, int(fps * frame_interval))  # 要跳過的幀數

            logger.info(f"開始DeepFace影片分析: FPS={fps}, 總幀數={total_frames}, 間隔={frame_interval}秒")

            frame_count = 0
            analyzed_count = 0

            # 創建臨時目錄來存放截圖
            with tempfile.TemporaryDirectory() as temp_dir:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # 按間隔處理幀
                    if frame_count % frame_skip == 0:
                        current_time = frame_count / fps if fps > 0 else 0

                        # 保存當前幀為臨時圖片
                        temp_image_path = os.path.join(temp_dir, f"frame_{analyzed_count:06d}.jpg")
                        cv2.imwrite(temp_image_path, frame)

                        # 使用DeepFace分析這一幀
                        analysis_result = self.analyze_image_deepface(temp_image_path)

                        # 添加時間戳和進度信息
                        analysis_result.update({
                            "frame_time": round(current_time, 2),
                            "frame_number": frame_count,
                            "analyzed_frame": analyzed_count,
                            "progress": round((frame_count / total_frames) * 100, 1) if total_frames > 0 else 0,
                            "total_duration": round(duration, 2),
                            "completed": False
                        })

                        # 清理臨時檔案
                        try:
                            os.unlink(temp_image_path)
                        except:
                            pass

                        yield analysis_result
                        analyzed_count += 1

                    frame_count += 1

                    # 防止記憶體過載，限制分析幀數
                    if analyzed_count >= 1200:  # 最多10分鐘 (0.5秒間隔)
                        logger.warning("達到分析幀數限制，停止分析")
                        break

            cap.release()

            # 發送完成信號
            yield {
                "message": f"影片分析完成，共分析了 {analyzed_count} 幀",
                "total_frames": total_frames,
                "analyzed_frames": analyzed_count,
                "total_duration": round(duration, 2),
                "frame_time": round(duration, 2),
                "completed": True
            }

        except Exception as exc:
            logger.error(f"DeepFace 影片分析失敗: {exc}")
            yield {
                "error": f"影片分析錯誤: {str(exc)}",
                "frame_time": 0,
                "completed": True
            }

    def analyze_image_deepface(self, image_path: str) -> Dict:
        """
        使用 DeepFace 進行人臉特徵分析和情緒推測

        Args:
            image_path: 圖片檔案路徑

        Returns:
            DeepFace 分析結果
        """

        if not _DEEPFACE_AVAILABLE and DeepFace is None:
            return {
                "emotion_zh": "中性",
                "emotion_en": "neutral",
                "emoji": "😐",
                "confidence": 0.0,
                "error": f"DeepFace 不可用: {_DEEPFACE_ERROR}"
            }

        try:
            # 導入 TensorFlow 用於記憶體管理
            import tensorflow as tf

            analyze_kwargs = dict(
                img_path=image_path,
                actions=['emotion'],
                enforce_detection=False,  # 更寬鬆的人臉檢測
                detector_backend='opencv',  # 使用 GPU 友好的 detector
            )

            if _GPU_STATUS.tensorflow_ready:
                with tf.device('/GPU:0'):
                    analysis = DeepFace.analyze(**analyze_kwargs)
            else:
                analysis = DeepFace.analyze(**analyze_kwargs)

            # DeepFace 返回一個列表，每個元素是一張臉的分析結果
            if not analysis or not isinstance(analysis, list) or len(analysis) == 0:
                return {
                    "emotion_zh": "未檢測到",
                    "emotion_en": "not_detected",
                    "emoji": "❓",
                    "confidence": 0.0,
                    "error": "未檢測到人臉",
                    "engine": "deepface",
                    "face_detected": False
                }

            # 我們只取第一張臉的結果
            result = analysis[0]

            # 檢查是否有有效的臉部檢測結果
            if 'dominant_emotion' not in result or 'emotion' not in result:
                return {
                    "emotion_zh": "未檢測到",
                    "emotion_en": "not_detected",
                    "emoji": "❓",
                    "confidence": 0.0,
                    "error": "臉部檢測失敗",
                    "engine": "deepface",
                    "face_detected": False
                }

            dominant_emotion_en = result['dominant_emotion']
            confidence = result['emotion'][dominant_emotion_en] / 100.0

            # 如果所有情緒的信心度都很低（都接近0），表示實際上沒有檢測到臉
            all_emotions_low = all(score <= 1.0 for score in result['emotion'].values())  # 1%以下算作未檢測
            if confidence <= 0.01 or all_emotions_low:  # 信心度小於1%或所有情緒都很低
                return {
                    "emotion_zh": "未檢測到",
                    "emotion_en": "not_detected",
                    "emoji": "❓",
                    "confidence": 0.0,
                    "error": "未檢測到有效的人臉特徵",
                    "engine": "deepface",
                    "face_detected": False
                }

            # 英文轉中文
            emotion_zh = "面無表情" # 預設值
            for zh, details in EMOTION_TRANSLATIONS.items():
                if details['en'] == dominant_emotion_en:
                    emotion_zh = zh
                    break

            emoji = EMOTION_TRANSLATIONS.get(emotion_zh, {}).get("emoji", "😐")

            # 取得其他特徵分析結果
            age = result.get('age', 0)

            # 性別分析
            gender_analysis = result.get('gender', {})
            if isinstance(gender_analysis, dict) and gender_analysis:
                gender_scores = {k.lower(): v for k, v in gender_analysis.items()}
                dominant_gender_key = max(gender_scores, key=gender_scores.get)
                gender_zh = '男性' if dominant_gender_key == 'man' else '女性' if dominant_gender_key == 'woman' else '未知'
                gender_confidence = gender_scores.get(dominant_gender_key, 0) / 100.0
            else:
                gender_zh = '未知'
                dominant_gender_key = 'unknown'
                gender_confidence = 0.0
                gender_scores = {}

            # 種族分析
            race_analysis = result.get('race', {})
            if isinstance(race_analysis, dict) and race_analysis:
                race_scores = {k.lower().replace(' ', '_'): v for k, v in race_analysis.items()}
                dominant_race_key = max(race_scores, key=race_scores.get)

                # 種族中文映射
                race_mapping = {
                    'asian': '亞洲人',
                    'white': '白人',
                    'black': '黑人',
                    'indian': '印度人',
                    'latino_hispanic': '拉丁裔',
                    'middle_eastern': '中東人'
                }
                race_zh = race_mapping.get(dominant_race_key, '未知')
                race_confidence = race_scores.get(dominant_race_key, 0) / 100.0
            else:
                race_zh = '未知'
                dominant_race_key = 'unknown'
                race_confidence = 0.0
                race_scores = {}

            # 分析完成後清理 TensorFlow session（防止記憶體累積）
            try:
                tf.keras.backend.clear_session()
            except:
                pass  # 如果清理失敗也不影響結果

            return {
                "emotion_zh": emotion_zh,
                "emotion_en": dominant_emotion_en,
                "emoji": emoji,
                "confidence": round(confidence, 3),
                "engine": "deepface",
                "face_detected": True,
                "raw_scores": {k: round(v / 100.0, 4) for k, v in result['emotion'].items()}
            }

        except Exception as exc:
            logger.error(f"DeepFace 分析失敗: {exc}")

            # 錯誤時也清理 session（防止記憶體洩漏）
            try:
                import tensorflow as tf
                tf.keras.backend.clear_session()
            except:
                pass

            return {
                "emotion_zh": "面無表情",
                "emotion_en": "neutral",
                "emoji": "😐",
                "confidence": 0.0,
                "error": f"DeepFace 分析錯誤: {str(exc)}",
                "engine": "deepface"
            }
