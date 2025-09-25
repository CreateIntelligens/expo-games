# =============================================================================
# action_detection_service.py - 動作偵測服務
# 互動式動作挑戰系統，整合臉部特徵辨識與即時遊戲邏輯
# =============================================================================

import threading
import time
from enum import Enum
from typing import Dict, List, Optional

import cv2

from .status_broadcaster import StatusBroadcaster


class ActionType(Enum):
    """動作類型枚舉"""

    SMILE = "smile"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    SHRUG = "shrug"
    RAISE_EYEBROWS = "raise_eyebrows"
    WINK = "wink"
    NOD = "nod"


class DifficultyLevel(Enum):
    """難度等級"""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ActionChallenge:
    """單個動作挑戰資料結構"""

    def __init__(
        self,
        action_type: ActionType,
        name: str,
        description: str,
        emoji: str,
        threshold: float = 0.7,
    ) -> None:
        self.action_type = action_type
        self.name = name
        self.description = description
        self.emoji = emoji
        self.threshold = threshold
        self.completed = False
        self.progress = 0.0
        self.start_time: Optional[float] = None
        self.completion_time: Optional[float] = None


class FacialFeatureExtractor:
    """臉部特徵提取器，使用 MediaPipe FaceMesh"""

    def __init__(self) -> None:
        self.LEFT_EYE_INDICES = [33, 7, 163, 144, 145, 153]
        self.RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373]
        self.MOUTH_INDICES = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324]
        self.EYEBROW_LEFT_INDICES = [70, 63, 105, 66]
        self.EYEBROW_RIGHT_INDICES = [296, 334, 293, 300]

        # 初始化 MediaPipe
        self.mediapipe_ready = True
        try:
            os.environ.setdefault("MEDIAPIPE_DISABLE_GPU", "1")
            import mediapipe as mp
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception:
            self.mediapipe_ready = False
            self.face_mesh = None

    def extract_features(self, frame) -> Optional[Dict]:
        if not self.mediapipe_ready or frame is None:
            # 回退到模擬數據
            import random
            landmarks = [(random.randint(40, 600), random.randint(40, 440)) for _ in range(468)]
            return self._build_feature_dict(landmarks, 640, 480)

        height, width = frame.shape[:2]
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(frame_rgb)

        if not results or not results.multi_face_landmarks:
            return None

        face_landmarks = results.multi_face_landmarks[0].landmark
        landmarks = [(lm.x * width, lm.y * height) for lm in face_landmarks]

        return self._build_feature_dict(landmarks, width, height)

    def _build_feature_dict(self, landmarks, width, height):
        """構建特徵字典"""
        return {
            "landmarks": landmarks,
            "left_eye": [landmarks[i] for i in self.LEFT_EYE_INDICES],
            "right_eye": [landmarks[i] for i in self.RIGHT_EYE_INDICES],
            "mouth": [landmarks[i] for i in self.MOUTH_INDICES],
            "eyebrow_left": [landmarks[i] for i in self.EYEBROW_LEFT_INDICES],
            "eyebrow_right": [landmarks[i] for i in self.EYEBROW_RIGHT_INDICES],
            "nose_tip": landmarks[1] if len(landmarks) > 1 else (width/2, height/2),
            "chin": landmarks[175] if len(landmarks) > 175 else (width/2, height*0.8),
            "forehead": landmarks[10] if len(landmarks) > 10 else (width/2, height*0.2),
        }


class ActionDetector:
    """動作進度計算器"""

    def __init__(self) -> None:
        self.baseline_features: Optional[Dict] = None

    def set_baseline(self, features: Dict) -> None:
        self.baseline_features = features

    def calculate_progress(self, action_type: ActionType, current_features: Dict) -> float:
        if not self.baseline_features:
            return 0.0

        try:
            if action_type == ActionType.SMILE:
                return self._detect_smile(current_features)
            if action_type == ActionType.TURN_LEFT:
                return self._detect_head_turn_left(current_features)
            if action_type == ActionType.TURN_RIGHT:
                return self._detect_head_turn_right(current_features)
            if action_type == ActionType.SHRUG:
                return self._detect_shrug(current_features)
            if action_type == ActionType.RAISE_EYEBROWS:
                return self._detect_eyebrow_raise(current_features)
            if action_type == ActionType.WINK:
                return self._detect_wink(current_features)
            if action_type == ActionType.NOD:
                return self._detect_nod(current_features)
        except Exception:
            return 0.0

        return 0.0

    def _detect_smile(self, features: Dict) -> float:
        mouth_points = features["mouth"]
        if len(mouth_points) < 10 or not self.baseline_features:
            return 0.0

        left_corner = mouth_points[0]
        right_corner = mouth_points[6]
        top_lip = mouth_points[3]
        bottom_lip = mouth_points[9]

        mouth_width = abs(right_corner[0] - left_corner[0])
        mouth_height = abs(bottom_lip[1] - top_lip[1]) or 1
        width_height_ratio = mouth_width / mouth_height

        baseline = self.baseline_features["mouth"]
        base_left = baseline[0]
        base_right = baseline[6]
        base_top = baseline[3]
        base_bottom = baseline[9]
        base_width = abs(base_right[0] - base_left[0])
        base_height = abs(base_bottom[1] - base_top[1]) or 1

        baseline_ratio = base_width / base_height
        ratio_change = (width_height_ratio - baseline_ratio) / baseline_ratio
        return float(min(1.0, max(0.0, ratio_change * 2)))

    def _detect_head_turn_left(self, features: Dict) -> float:
        if not self.baseline_features:
            return 0.0
        nose_tip = features["nose_tip"]
        chin = features["chin"]
        forehead = features["forehead"]
        face_center_x = (nose_tip[0] + chin[0] + forehead[0]) / 3

        baseline_nose = self.baseline_features["nose_tip"]
        baseline_chin = self.baseline_features["chin"]
        baseline_forehead = self.baseline_features["forehead"]
        baseline_center_x = (baseline_nose[0] + baseline_chin[0] + baseline_forehead[0]) / 3

        shift = face_center_x - baseline_center_x
        return float(min(1.0, max(0.0, -shift / 50))) if shift < 0 else 0.0

    def _detect_head_turn_right(self, features: Dict) -> float:
        if not self.baseline_features:
            return 0.0
        nose_tip = features["nose_tip"]
        chin = features["chin"]
        forehead = features["forehead"]
        face_center_x = (nose_tip[0] + chin[0] + forehead[0]) / 3

        baseline_nose = self.baseline_features["nose_tip"]
        baseline_chin = self.baseline_features["chin"]
        baseline_forehead = self.baseline_features["forehead"]
        baseline_center_x = (baseline_nose[0] + baseline_chin[0] + baseline_forehead[0]) / 3

        shift = face_center_x - baseline_center_x
        return float(min(1.0, max(0.0, shift / 50))) if shift > 0 else 0.0

    def _detect_shrug(self, features: Dict) -> float:
        if not self.baseline_features:
            return 0.0
        baseline_nose = self.baseline_features["nose_tip"]
        baseline_chin = self.baseline_features["chin"]
        baseline_vertical = abs(baseline_chin[1] - baseline_nose[1]) or 1

        nose_tip = features["nose_tip"]
        chin = features["chin"]
        current_vertical = abs(chin[1] - nose_tip[1]) or 1

        change = (baseline_vertical - current_vertical) / baseline_vertical
        return float(min(1.0, max(0.0, change * 3)))

    def _detect_eyebrow_raise(self, features: Dict) -> float:
        if not self.baseline_features:
            return 0.0
        eyebrow = features["eyebrow_left"] + features["eyebrow_right"]
        baseline = self.baseline_features["eyebrow_left"] + self.baseline_features["eyebrow_right"]

        avg_current_y = sum(point[1] for point in eyebrow) / len(eyebrow)
        avg_baseline_y = sum(point[1] for point in baseline) / len(baseline)

        raise_amount = avg_baseline_y - avg_current_y
        return float(min(1.0, max(0.0, raise_amount / 15)))

    def _detect_wink(self, features: Dict) -> float:
        left_eye = features["left_eye"]
        right_eye = features["right_eye"]
        if len(left_eye) < 6 or len(right_eye) < 6:
            return 0.0

        left_height = abs(left_eye[1][1] - left_eye[4][1]) or 1
        right_height = abs(right_eye[1][1] - right_eye[4][1]) or 1
        ratio = left_height / right_height
        return float(min(1.0, max(0.0, (ratio - 1.0))))

    def _detect_nod(self, features: Dict) -> float:
        if not self.baseline_features:
            return 0.0
        nose_tip = features["nose_tip"]
        baseline_nose = self.baseline_features["nose_tip"]
        vertical_shift = nose_tip[1] - baseline_nose[1]
        return float(min(1.0, max(0.0, vertical_shift / 20))) if vertical_shift > 0 else 0.0


class ActionDetectionService:
    """動作偵測遊戲主服務"""

    def __init__(self, status_broadcaster: StatusBroadcaster) -> None:
        self.status_broadcaster = status_broadcaster
        self.feature_extractor = FacialFeatureExtractor()
        self.action_detector = ActionDetector()

        self.is_detecting = False
        self.detection_thread: Optional[threading.Thread] = None
        self.camera = None

        self.current_challenge_set: List[ActionChallenge] = []
        self.current_challenge_index = 0
        self.difficulty_level = DifficultyLevel.EASY
        self.game_start_time: Optional[float] = None
        self.total_score = 0

        self.challenge_sets = {
            DifficultyLevel.EASY: [
                ActionChallenge(ActionType.SMILE, "微笑", "請對著鏡頭微笑", "😊", 0.6),
                ActionChallenge(ActionType.TURN_LEFT, "向左轉頭", "請向左轉頭", "←", 0.5),
                ActionChallenge(ActionType.TURN_RIGHT, "向右轉頭", "請向右轉頭", "→", 0.5),
            ],
            DifficultyLevel.MEDIUM: [
                ActionChallenge(ActionType.SMILE, "微笑", "請對著鏡頭微笑", "😊", 0.7),
                ActionChallenge(ActionType.TURN_LEFT, "向左轉頭", "請向左轉頭", "←", 0.6),
                ActionChallenge(ActionType.TURN_RIGHT, "向右轉頭", "請向右轉頭", "→", 0.6),
                ActionChallenge(ActionType.RAISE_EYEBROWS, "挑眉", "請挑起眉毛", "🤨", 0.7),
                ActionChallenge(ActionType.WINK, "眨眼", "請眨一隻眼", "😉", 0.8),
            ],
            DifficultyLevel.HARD: [
                ActionChallenge(ActionType.SMILE, "微笑", "請對著鏡頭微笑", "😊", 0.8),
                ActionChallenge(ActionType.TURN_LEFT, "向左轉頭", "請向左轉頭", "←", 0.7),
                ActionChallenge(ActionType.TURN_RIGHT, "向右轉頭", "請向右轉頭", "→", 0.7),
                ActionChallenge(ActionType.SHRUG, "聳肩", "請聳聳肩", "🤷", 0.6),
                ActionChallenge(ActionType.RAISE_EYEBROWS, "挑眉", "請挑起眉毛", "🤨", 0.8),
                ActionChallenge(ActionType.WINK, "眨眼", "請眨一隻眼", "😉", 0.9),
                ActionChallenge(ActionType.NOD, "點頭", "請點點頭", "👋", 0.8),
            ],
        }

    def start_action_detection(self, difficulty: str = "easy") -> Dict:
        if self.is_detecting:
            return {"status": "error", "message": "動作檢測已在進行中"}

        self.difficulty_level = {
            "easy": DifficultyLevel.EASY,
            "medium": DifficultyLevel.MEDIUM,
            "hard": DifficultyLevel.HARD,
        }.get(difficulty, DifficultyLevel.EASY)

        self.current_challenge_set = [
            ActionChallenge(
                challenge.action_type,
                challenge.name,
                challenge.description,
                challenge.emoji,
                challenge.threshold,
            )
            for challenge in self.challenge_sets[self.difficulty_level]
        ]

        self.current_challenge_index = 0
        self.game_start_time = time.time()
        self.total_score = 0

        for challenge in self.current_challenge_set:
            challenge.completed = False
            challenge.progress = 0.0
            challenge.start_time = None
            challenge.completion_time = None

        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            return {"status": "error", "message": "無法開啟攝影機"}

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_FPS, 30)

        self.is_detecting = True
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()

        self.status_broadcaster.broadcast_threadsafe(
            {
                "channel": "action",
                "stage": "started",
                "message": f"動作檢測遊戲開始 - {self.difficulty_level.value.upper()} 模式",
                "data": {
                    "difficulty": self.difficulty_level.value,
                    "total_challenges": len(self.current_challenge_set),
                    "current_challenge": 0,
                },
            }
        )

        return {
            "status": "started",
            "message": "動作檢測遊戲已開始",
            "difficulty": self.difficulty_level.value,
            "total_challenges": len(self.current_challenge_set),
        }

    def stop_action_detection(self) -> Dict:
        if not self.is_detecting:
            return {"status": "idle", "message": "動作檢測未在進行中"}

        self.is_detecting = False

        if self.camera:
            self.camera.release()
            self.camera = None

        if self.detection_thread:
            self.detection_thread.join(timeout=2)

        self.status_broadcaster.broadcast_threadsafe(
            {
                "channel": "action",
                "stage": "stopped",
                "message": "動作檢測已停止",
            }
        )

        return {"status": "stopped", "message": "動作檢測已停止"}

    def get_detection_status(self) -> Dict:
        if not self.is_detecting:
            return {
                "status": "idle",
                "message": "動作檢測未在進行中",
                "is_detecting": False,
            }

        current_challenge = None
        if 0 <= self.current_challenge_index < len(self.current_challenge_set):
            challenge = self.current_challenge_set[self.current_challenge_index]
            current_challenge = {
                "name": challenge.name,
                "description": challenge.description,
                "emoji": challenge.emoji,
                "progress": challenge.progress,
                "completed": challenge.completed,
            }

        completed_count = sum(1 for c in self.current_challenge_set if c.completed)

        return {
            "status": "detecting",
            "message": "動作檢測進行中",
            "is_detecting": True,
            "difficulty": self.difficulty_level.value,
            "current_challenge_index": self.current_challenge_index,
            "total_challenges": len(self.current_challenge_set),
            "completed_challenges": completed_count,
            "current_challenge": current_challenge,
            "total_score": self.total_score,
            "game_duration": time.time() - self.game_start_time if self.game_start_time else 0,
        }

    def _detection_loop(self) -> None:
        baseline_set = False
        frame_count = 0

        try:
            while self.is_detecting and self.camera and self.camera.isOpened():
                ret, frame = self.camera.read()
                if not ret:
                    break

                frame_count += 1

                if frame_count % 3 != 0:
                    continue

                features = self.feature_extractor.extract_features(frame)
                if not features:
                    continue

                if not baseline_set:
                    self.action_detector.set_baseline(features)
                    baseline_set = True
                    self.status_broadcaster.broadcast_threadsafe(
                        {
                            "channel": "action",
                            "stage": "baseline_set",
                            "message": "基準建立完成，準備開始挑戰",
                        }
                    )
                    continue

                if self.current_challenge_index >= len(self.current_challenge_set):
                    self._complete_game()
                    break

                challenge = self.current_challenge_set[self.current_challenge_index]
                challenge.progress = self.action_detector.calculate_progress(challenge.action_type, features)

                if challenge.progress >= challenge.threshold:
                    challenge.completed = True
                    challenge.completion_time = time.time()
                    self.total_score += int(challenge.progress * 100)
                    self.status_broadcaster.broadcast_threadsafe(
                        {
                            "channel": "action",
                            "stage": "challenge_completed",
                            "message": f"完成挑戰: {challenge.name}",
                            "data": {
                                "score": self.total_score,
                                "completed": self.current_challenge_index + 1,
                                "total": len(self.current_challenge_set),
                            },
                        }
                    )
                    self.current_challenge_index += 1

                    if self.current_challenge_index < len(self.current_challenge_set):
                        next_challenge = self.current_challenge_set[self.current_challenge_index]
                        self.status_broadcaster.broadcast_threadsafe(
                            {
                                "channel": "action",
                                "stage": "next_challenge",
                                "message": f"下一個挑戰: {next_challenge.name}",
                                "data": {
                                    "name": next_challenge.name,
                                    "description": next_challenge.description,
                                    "emoji": next_challenge.emoji,
                                    "index": self.current_challenge_index,
                                    "total": len(self.current_challenge_set),
                                },
                            }
                        )
                    else:
                        self._complete_game()

                if frame_count % 12 == 0:
                    self.status_broadcaster.broadcast_threadsafe(
                        {
                            "channel": "action",
                            "stage": "progress_update",
                            "message": "動作進度更新",
                            "data": {
                                "progress_percent": min(100, challenge.progress * 100 / challenge.threshold if challenge.threshold else 0),
                                "current_challenge": {
                                    "name": challenge.name,
                                    "description": challenge.description,
                                    "emoji": challenge.emoji,
                                    "progress": round(challenge.progress, 3),
                                },
                                "score": self.total_score,
                                "difficulty": self.difficulty_level.value,
                                "completed": self.current_challenge_index,
                                "total": len(self.current_challenge_set),
                            },
                        }
                    )

                time.sleep(1 / 30)

        finally:
            if self.camera:
                self.camera.release()
                self.camera = None

            if self.is_detecting:
                self.stop_action_detection()

    def _complete_game(self) -> None:
        self.status_broadcaster.broadcast_threadsafe(
            {
                "channel": "action",
                "stage": "game_completed",
                "message": "遊戲完成！",
                "data": {
                    "score": self.total_score,
                    "total_time": time.time() - (self.game_start_time or time.time()),
                    "challenges_completed": len(self.current_challenge_set),
                    "difficulty": self.difficulty_level.value,
                },
            }
        )
        self.is_detecting = False

    def analyze_video(self, video_path: str) -> Dict:
        """
        分析影片檔案中的動作內容。

        Args:
            video_path (str): 影片檔案路径

        Returns:
            Dict: 動作分析結果
        """
        try:
            start_time = time.time()

            # 開啟影片檔案
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"無法開啟影片: {video_path}")

            # 獲取影片資訊
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            # 設定基準特徵 (使用第一幀)
            ret, first_frame = cap.read()
            if not ret:
                raise ValueError("無法讀取影片第一幀")

            baseline_features = self.feature_extractor.extract_features(first_frame)
            if not baseline_features:
                return {
                    "message": "影片中未檢測到臉部特徵",
                    "video_info": {
                        "duration": duration,
                        "fps": fps,
                        "frame_count": frame_count
                    },
                    "analysis_time": time.time() - start_time
                }

            self.action_detector.set_baseline(baseline_features)

            # 分析所有動作類型
            action_results = {}
            sample_interval = max(1, fps // 10)  # 每秒取10幀分析

            for action_type in ActionType:
                # 重置影片到開始
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

                action_detections = []
                frame_idx = 0

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # 按間隔採樣幀
                    if frame_idx % sample_interval == 0:
                        features = self.feature_extractor.extract_features(frame)
                        if features:
                            progress = self.action_detector.calculate_progress(action_type, features)
                            timestamp = frame_idx / fps if fps > 0 else 0

                            action_detections.append({
                                "timestamp": round(timestamp, 2),
                                "progress": round(progress, 3),
                                "detected": progress > 0.5  # 簡單閾值判定
                            })

                    frame_idx += 1

                # 統計該動作的檢測結果
                detected_moments = [d for d in action_detections if d["detected"]]
                max_progress = max([d["progress"] for d in action_detections]) if action_detections else 0

                action_results[action_type.value] = {
                    "detected_count": len(detected_moments),
                    "max_progress": round(max_progress, 3),
                    "detection_rate": len(detected_moments) / len(action_detections) if action_detections else 0,
                    "detected_moments": detected_moments[:10],  # 只保留前10個檢測時刻
                    "overall_detected": max_progress > 0.5
                }

            cap.release()

            # 找出最可能的動作
            detected_actions = {k: v for k, v in action_results.items() if v["overall_detected"]}
            primary_action = max(detected_actions.keys(), key=lambda k: action_results[k]["max_progress"]) if detected_actions else None

            return {
                "primary_action": primary_action,
                "confidence": action_results[primary_action]["max_progress"] if primary_action else 0,
                "all_actions": action_results,
                "detected_actions": list(detected_actions.keys()),
                "message": f"影片分析完成，主要動作: {primary_action or '未檢測到明顯動作'}",
                "video_info": {
                    "duration": duration,
                    "fps": fps,
                    "frame_count": frame_count,
                    "frames_analyzed": len(action_detections) if 'action_detections' in locals() else 0,
                    "sample_interval": sample_interval
                },
                "analysis_time": time.time(),
                "processing_time": round(time.time() - start_time, 3)
            }

        except Exception as exc:
            return {
                "primary_action": None,
                "confidence": 0.0,
                "message": f"影片分析失敗: {str(exc)}",
                "error": str(exc),
                "analysis_time": time.time() if 'start_time' in locals() else 0
            }


__all__ = ["ActionDetectionService", "DifficultyLevel", "ActionType"]
