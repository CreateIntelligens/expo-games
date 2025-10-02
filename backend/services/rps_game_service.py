# =============================================================================
# rps_game_service.py - 猜拳遊戲服務（使用 MediaPipe 辨識）
# 獨立的遊戲邏輯，支援 WebSocket 即時更新
# =============================================================================

import logging
import random
import threading
import time
from enum import Enum
from typing import Dict, List, Optional

from .mediapipe_rps_detector import MediaPipeRPSDetector, RPSGesture
from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts

logger = logging.getLogger(__name__)


class GameState(Enum):
    """遊戲狀態"""
    IDLE = "idle"              # 閒置
    COUNTDOWN = "countdown"    # 倒數中 (3...2...1)
    WAITING_PLAYER = "waiting_player"  # 等待玩家出拳
    JUDGING = "judging"        # 判定中
    RESULT = "result"          # 顯示結果
    FINISHED = "finished"      # 遊戲結束


class RoundResult(Enum):
    """回合結果"""
    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"


class RPSGameService:
    """
    猜拳遊戲服務（使用 MediaPipe）

    特點：
    - 使用 MediaPipe 高精度手勢辨識
    - 支援 WebSocket 即時狀態更新
    - 完全獨立，不依賴攝影機服務
    - 支援圖片上傳辨識
    """

    def __init__(self, status_broadcaster: StatusBroadcaster):
        self.status_broadcaster = status_broadcaster
        self.detector = MediaPipeRPSDetector()

        if not self.detector.is_available():
            logger.warning(
                "MediaPipe 辨識器不可用，遊戲功能受限: %s",
                self.detector.init_error
            )

        # 遊戲狀態
        self.game_state = GameState.IDLE
        self.game_thread: Optional[threading.Thread] = None
        self.stop_flag = threading.Event()

        # 遊戲設定
        self.countdown_time = 3  # 倒數秒數
        self.result_display_time = 3  # 結果顯示時間
        self.target_score = 1  # 目標分數

        # 玩家資料
        self.player_score = 0
        self.computer_score = 0
        self.current_round = 0
        self.round_history: List[Dict] = []

        # 當前回合資料
        self.player_gesture: Optional[RPSGesture] = None
        self.computer_gesture: Optional[RPSGesture] = None
        self.current_result: Optional[RoundResult] = None

        # 遊戲統計
        self.game_start_time: Optional[float] = None

    def start_game(self, target_score: int = 1) -> Dict:
        """
        開始遊戲（單回合模式）

        Args:
            target_score: 保留為 API 相容性，實際上遊戲固定為單回合模式
        """
        if self.game_state != GameState.IDLE:
            return {"status": "error", "message": "遊戲已在進行中"}

        if not self.detector.is_available():
            return {
                "status": "error",
                "message": f"MediaPipe 辨識器不可用: {self.detector.init_error}"
            }

        # 重置遊戲狀態（固定為單回合模式，target_score 不實際使用）
        self.target_score = 1  # 固定為 1，不使用傳入的 target_score
        self.player_score = 0
        self.computer_score = 0
        self.current_round = 0
        self.round_history = []
        self.game_start_time = time.time()
        self.stop_flag.clear()

        # 變更狀態
        self.game_state = GameState.COUNTDOWN

        # 開始遊戲循環
        self.game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_thread.start()

        # 廣播遊戲開始
        self._broadcast({
            "stage": "game_started",
            "message": "猜拳遊戲開始！",
            "data": {
                "target_score": target_score,
                "player_score": 0,
                "computer_score": 0
            }
        })

        return {
            "status": "started",
            "message": "遊戲已開始",
            "target_score": target_score
        }

    def stop_game(self) -> Dict:
        """停止遊戲"""
        if self.game_state == GameState.IDLE:
            return {"status": "idle", "message": "遊戲未在進行中"}

        # 設定停止旗標
        self.stop_flag.set()
        self.game_state = GameState.IDLE

        # 等待遊戲線程結束
        if self.game_thread and self.game_thread.is_alive():
            self.game_thread.join(timeout=2)

        # 計算統計資料
        total_time = time.time() - self.game_start_time if self.game_start_time else 0

        # 廣播遊戲停止
        self._broadcast({
            "stage": "game_stopped",
            "message": "遊戲已停止",
            "data": {
                "total_time": total_time,
                "rounds_played": self.current_round,
                "final_scores": {
                    "player": self.player_score,
                    "computer": self.computer_score
                }
            }
        })

        return {
            "status": "stopped",
            "message": "遊戲已停止",
            "summary": {
                "total_time": total_time,
                "rounds_played": self.current_round,
                "player_score": self.player_score,
                "computer_score": self.computer_score
            }
        }

    def submit_player_gesture(self, image_path: str) -> Dict:
        """
        提交玩家手勢圖片

        Args:
            image_path: 圖片檔案路徑

        Returns:
            辨識結果
        """
        if self.game_state != GameState.WAITING_PLAYER:
            return {
                "status": "error",
                "message": f"當前不接受出拳（狀態: {self.game_state.value}）"
            }

        # 使用 MediaPipe 辨識手勢
        gesture, confidence = self.detector.detect(image_path)

        if gesture == RPSGesture.UNKNOWN or confidence < 0.5:
            return {
                "status": "error",
                "message": "無法辨識手勢，請重新拍攝",
                "confidence": confidence
            }

        # 儲存玩家手勢
        self.player_gesture = gesture

        logger.info(
            "玩家出拳: %s (信心度: %.3f)",
            gesture.value,
            confidence
        )

        return {
            "status": "success",
            "message": "手勢辨識成功",
            "gesture": gesture.value,
            "confidence": confidence
        }

    def get_game_status(self) -> Dict:
        """取得遊戲狀態"""
        return {
            "status": self.game_state.value,
            "is_playing": self.game_state != GameState.IDLE,
            "current_round": self.current_round,
            "target_score": self.target_score,
            "scores": {
                "player": self.player_score,
                "computer": self.computer_score
            },
            "current_gestures": {
                "player": self.player_gesture.value if self.player_gesture else None,
                "computer": self.computer_gesture.value if self.computer_gesture else None
            },
            "current_result": self.current_result.value if self.current_result else None,
            "game_duration": time.time() - self.game_start_time if self.game_start_time else 0
        }

    def _game_loop(self):
        """遊戲主循環（在背景執行）"""
        try:
            while not self.stop_flag.is_set():
                # 開始新回合
                self._start_round()

                # 倒數 3...2...1
                if not self._countdown():
                    break

                # 等待玩家出拳
                if not self._wait_for_player():
                    break

                # 電腦出拳
                self._computer_play()

                # 判定結果
                self._judge_result()

                # 顯示結果
                self._show_result()

                # 🎯 永遠只玩一回合，不管結果直接結束
                logger.info("單次對決結束")
                self._finish_game()
                break

        except Exception as exc:
            logger.exception("遊戲循環錯誤: %s", exc)
            self._broadcast({
                "stage": "error",
                "message": f"遊戲錯誤: {str(exc)}"
            })
        finally:
            self.game_state = GameState.IDLE

    def _start_round(self):
        """開始新回合"""
        self.current_round += 1
        self.player_gesture = None
        self.computer_gesture = None
        self.current_result = None

        logger.info("開始第 %d 回合", self.current_round)

        self._broadcast({
            "stage": "round_started",
            "message": f"第 {self.current_round} 回合",
            "data": {
                "round": self.current_round,
                "scores": {
                    "player": self.player_score,
                    "computer": self.computer_score
                }
            }
        })

    def _countdown(self) -> bool:
        """倒數 3...2...1"""
        self.game_state = GameState.COUNTDOWN

        for i in range(self.countdown_time, 0, -1):
            if self.stop_flag.is_set():
                return False

            self._broadcast({
                "stage": "countdown",
                "message": str(i),
                "data": {"count": i}
            })

            time.sleep(1)

        return True

    def _wait_for_player(self) -> bool:
        """等待玩家出拳"""
        self.game_state = GameState.WAITING_PLAYER

        self._broadcast({
            "stage": "waiting_player",
            "message": "請上傳你的手勢！",
            "data": {}
        })

        # 等待玩家透過 WebSocket 自動設定手勢（最多等待 10 秒）
        wait_time = 0
        max_wait = 10

        while self.player_gesture is None and wait_time < max_wait:
            if self.stop_flag.is_set():
                return False

            time.sleep(0.5)
            wait_time += 0.5

        # 🎯 如果超時且沒有偵測到手勢，不要隨機給手勢
        # 前端會發送 no_gesture_detected 訊息，設定為 UNKNOWN
        if self.player_gesture is None:
            logger.warning("⏰ 等待超時，未偵測到玩家手勢")
            # 不做任何事，等待前端發送 no_gesture_detected

        return True

    def _computer_play(self):
        """電腦出拳（隨機）"""
        self.computer_gesture = random.choice([
            RPSGesture.ROCK,
            RPSGesture.PAPER,
            RPSGesture.SCISSORS
        ])

        logger.info("電腦出拳: %s", self.computer_gesture.value)

    def _judge_result(self):
        """判定結果（簡化版：不計分）"""
        self.game_state = GameState.JUDGING

        result = self._determine_winner(self.player_gesture, self.computer_gesture)
        self.current_result = result

        # 🎯 單次對決模式：不更新分數，只記錄結果
        logger.info(
            "對決結果: %s | 玩家: %s vs 電腦: %s",
            result.value,
            self.player_gesture.value,
            self.computer_gesture.value
        )

    def _show_result(self):
        """顯示結果"""
        self.game_state = GameState.RESULT

        # 🎯 特殊處理：如果玩家是 UNKNOWN，顯示特殊訊息
        if self.player_gesture == RPSGesture.UNKNOWN:
            result_message = "不能亂比！😡"
        else:
            result_messages = {
                RoundResult.WIN: "你贏了！🎉",
                RoundResult.LOSE: "你輸了！😢",
                RoundResult.DRAW: "平手！🤝"
            }
            result_message = result_messages[self.current_result]

        self._broadcast({
            "stage": "result",
            "message": result_message,
            "data": {
                "result": self.current_result.value,
                "gestures": {
                    "player": self.player_gesture.value,
                    "computer": self.computer_gesture.value
                },
                # 🎯 保留分數欄位以相容前端，但永遠是 0-0 或對決結果
                "scores": {
                    "player": 1 if self.current_result == RoundResult.WIN else 0,
                    "computer": 1 if self.current_result == RoundResult.LOSE else 0
                }
            }
        })

        # 🎯 不要 sleep，讓遊戲循環立即執行 break
        # 前端會處理 3 秒顯示延遲

    def _determine_winner(self, player: RPSGesture, computer: RPSGesture) -> RoundResult:
        """判定勝負（UNKNOWN 手勢判輸 - 不能亂比）"""
        # 🎯 處理 UNKNOWN 手勢：玩家亂比或未偵測到手勢，判定輸
        if player == RPSGesture.UNKNOWN:
            return RoundResult.LOSE

        if player == computer:
            return RoundResult.DRAW

        winning_combinations = {
            (RPSGesture.ROCK, RPSGesture.SCISSORS),
            (RPSGesture.PAPER, RPSGesture.ROCK),
            (RPSGesture.SCISSORS, RPSGesture.PAPER)
        }

        if (player, computer) in winning_combinations:
            return RoundResult.WIN
        else:
            return RoundResult.LOSE

    def _check_winner(self) -> bool:
        """檢查是否有玩家達到目標分數"""
        return self.player_score >= self.target_score or self.computer_score >= self.target_score

    def _finish_game(self):
        """結束遊戲（單次對決模式）"""
        self.game_state = GameState.FINISHED

        # 🎯 單次對決：根據本回合結果決定訊息
        if self.player_gesture == RPSGesture.UNKNOWN:
            message = "不能亂比！😡"
        else:
            result_messages = {
                RoundResult.WIN: "你贏了！🎉",
                RoundResult.LOSE: "你輸了！😢",
                RoundResult.DRAW: "平手！🤝"
            }
            message = result_messages.get(self.current_result, "對決結束")

        self._broadcast({
            "stage": "game_finished",
            "message": f"遊戲結束！{message}",
            "data": {
                "result": self.current_result.value if self.current_result else "unknown",
                "gestures": {
                    "player": self.player_gesture.value if self.player_gesture else "unknown",
                    "computer": self.computer_gesture.value if self.computer_gesture else "unknown"
                }
            }
        })

        # 不要 sleep，直接設為 IDLE
        self.game_state = GameState.IDLE

    def _broadcast(self, data: Dict):
        """廣播訊息到 WebSocket"""
        message = {
            "channel": "rps_game",
            "timestamp": _now_ts(),
            **data
        }
        logger.info("📡 廣播遊戲狀態: stage=%s", data.get("stage"))
        self.status_broadcaster.broadcast_threadsafe(message)


__all__ = ["RPSGameService", "GameState", "RoundResult"]
