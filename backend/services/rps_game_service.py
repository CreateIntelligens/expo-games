# =============================================================================
# rps_game_service.py - 石頭剪刀布遊戲服務
# 結合手勢識別的對戰遊戲系統，支援單人 vs AI 和多人對戰模式
# =============================================================================

import logging
import random
import threading
import time
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .hand_gesture_service import HandGestureService, HandGestureType
from .status_broadcaster import StatusBroadcaster
from ..utils.datetime_utils import _now_ts


logger = logging.getLogger(__name__)


class RPSGameMode(Enum):
    """遊戲模式"""
    VS_AI = "vs_ai"          # 單人對戰 AI
    VS_PLAYER = "vs_player"  # 雙人對戰
    TOURNAMENT = "tournament"  # 錦標賽模式


class RPSGameDifficulty(Enum):
    """AI 難度等級"""
    EASY = "easy"      # 完全隨機
    MEDIUM = "medium"  # 有記憶的策略
    HARD = "hard"      # 高級策略 AI


class RPSRoundResult(Enum):
    """回合結果"""
    WIN = "win"
    LOSE = "lose"
    DRAW = "draw"


class RPSGameState(Enum):
    """遊戲狀態"""
    IDLE = "idle"
    WAITING_FOR_PLAYERS = "waiting"
    ROUND_COUNTDOWN = "countdown"
    ROUND_GESTURE_CAPTURE = "capture"
    ROUND_RESULT = "result"
    GAME_FINISHED = "finished"


class RPSPlayer:
    """玩家資料結構"""
    def __init__(self, player_id: str, name: str, is_ai: bool = False):
        self.player_id = player_id
        self.name = name
        self.is_ai = is_ai
        self.score = 0
        self.current_gesture: Optional[HandGestureType] = None
        self.gesture_ready = False
        self.wins = 0
        self.losses = 0
        self.draws = 0

    def reset_round(self):
        """重置回合狀態"""
        self.current_gesture = None
        self.gesture_ready = False

    def add_result(self, result: RPSRoundResult):
        """添加結果統計"""
        if result == RPSRoundResult.WIN:
            self.wins += 1
            self.score += 1
        elif result == RPSRoundResult.LOSE:
            self.losses += 1
        elif result == RPSRoundResult.DRAW:
            self.draws += 1


class RPSAIPlayer:
    """AI 玩家策略"""
    def __init__(self, difficulty: RPSGameDifficulty):
        self.difficulty = difficulty
        self.player_history = []  # 記錄對手出招歷史
        self.my_history = []     # 記錄自己出招歷史

    def get_ai_gesture(self, round_number: int) -> HandGestureType:
        """根據難度和歷史獲取 AI 出招"""
        if self.difficulty == RPSGameDifficulty.EASY:
            return self._random_gesture()
        elif self.difficulty == RPSGameDifficulty.MEDIUM:
            return self._strategy_gesture()
        else:  # HARD
            return self._advanced_strategy_gesture(round_number)

    def add_round_history(self, player_gesture: HandGestureType, ai_gesture: HandGestureType):
        """記錄回合歷史"""
        if player_gesture != HandGestureType.UNKNOWN:
            self.player_history.append(player_gesture)
        self.my_history.append(ai_gesture)

    def _random_gesture(self) -> HandGestureType:
        """完全隨機策略"""
        return random.choice([HandGestureType.ROCK, HandGestureType.PAPER, HandGestureType.SCISSORS])

    def _strategy_gesture(self) -> HandGestureType:
        """中等策略：基於對手最近的出招傾向"""
        if len(self.player_history) < 2:
            return self._random_gesture()

        # 分析對手最近3次出招
        recent_moves = self.player_history[-3:]
        move_counts = {
            HandGestureType.ROCK: recent_moves.count(HandGestureType.ROCK),
            HandGestureType.PAPER: recent_moves.count(HandGestureType.PAPER),
            HandGestureType.SCISSORS: recent_moves.count(HandGestureType.SCISSORS)
        }

        # 預測對手可能出什麼，然後出克制它的
        predicted_opponent = max(move_counts.keys(), key=lambda k: move_counts[k])
        return self._counter_gesture(predicted_opponent)

    def _advanced_strategy_gesture(self, round_number: int) -> HandGestureType:
        """高級策略：混合多種策略"""
        if len(self.player_history) < 5:
            return self._strategy_gesture()

        # 70% 時間使用策略，30% 時間隨機（避免被預測）
        if random.random() < 0.7:
            # 分析對手的週期性模式
            if len(self.player_history) >= 6:
                # 檢查是否有 2-3 個手勢的重複模式
                for pattern_len in [2, 3]:
                    if len(self.player_history) >= pattern_len * 2:
                        recent_pattern = self.player_history[-pattern_len:]
                        prev_pattern = self.player_history[-(pattern_len*2):-pattern_len]

                        if recent_pattern == prev_pattern:
                            # 檢測到模式，預測下一個動作
                            next_in_pattern = self.player_history[-pattern_len + (round_number % pattern_len)]
                            return self._counter_gesture(next_in_pattern)

            # 如果沒有檢測到模式，使用頻率分析
            return self._strategy_gesture()
        else:
            return self._random_gesture()

    def _counter_gesture(self, gesture: HandGestureType) -> HandGestureType:
        """返回克制指定手勢的手勢"""
        counter_map = {
            HandGestureType.ROCK: HandGestureType.PAPER,
            HandGestureType.PAPER: HandGestureType.SCISSORS,
            HandGestureType.SCISSORS: HandGestureType.ROCK
        }
        return counter_map.get(gesture, HandGestureType.ROCK)


class RPSGameService:
    """石頭剪刀布遊戲服務主類"""

    def __init__(self, status_broadcaster: StatusBroadcaster, hand_gesture_service: HandGestureService):
        self.status_broadcaster = status_broadcaster
        self.hand_gesture_service = hand_gesture_service

        # 遊戲狀態
        self.game_state = RPSGameState.IDLE
        self.game_mode = RPSGameMode.VS_AI
        self.players: Dict[str, RPSPlayer] = {}
        self.ai_player: Optional[RPSAIPlayer] = None
        self.game_thread: Optional[threading.Thread] = None

        # 遊戲設定
        self.target_score = 3  # 目標獲勝分數
        self.round_countdown_time = 3  # 回合倒數時間
        self.gesture_capture_time = 2  # 手勢捕捉時間
        self.result_display_time = 2   # 結果顯示時間

        # 遊戲統計
        self.game_start_time: Optional[float] = None
        self.current_round = 0
        self.round_history = []

    def start_game(self, mode: str = "vs_ai", difficulty: str = "medium", target_score: int = 3) -> Dict:
        """開始遊戲"""
        if self.game_state != RPSGameState.IDLE:
            return {"status": "error", "message": "遊戲已在進行中"}

        # 設定遊戲參數
        try:
            self.game_mode = RPSGameMode(mode)
            self.target_score = target_score
        except ValueError:
            return {"status": "error", "message": f"無效的遊戲模式: {mode}"}

        # 初始化玩家
        self.players = {}
        self.players["player1"] = RPSPlayer("player1", "玩家", False)

        if self.game_mode == RPSGameMode.VS_AI:
            try:
                ai_difficulty = RPSGameDifficulty(difficulty)
                self.players["ai"] = RPSPlayer("ai", f"AI ({difficulty.upper()})", True)
                self.ai_player = RPSAIPlayer(ai_difficulty)
            except ValueError:
                return {"status": "error", "message": f"無效的難度等級: {difficulty}"}

        # 重置遊戲狀態
        self.game_state = RPSGameState.WAITING_FOR_PLAYERS
        self.current_round = 0
        self.round_history = []
        self.game_start_time = time.time()

        # 開始遊戲線程
        self.game_thread = threading.Thread(target=self._game_loop, daemon=True)
        self.game_thread.start()

        # 廣播遊戲開始
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "game_started",
            "message": f"石頭剪刀布遊戲開始 - {mode.upper()} 模式",
            "data": {
                "mode": mode,
                "difficulty": difficulty if self.game_mode == RPSGameMode.VS_AI else None,
                "target_score": target_score,
                "players": {pid: {"name": p.name, "is_ai": p.is_ai} for pid, p in self.players.items()}
            }
        })

        return {
            "status": "started",
            "message": "石頭剪刀布遊戲已開始",
            "mode": mode,
            "target_score": target_score
        }

    def stop_game(self) -> Dict:
        """停止遊戲"""
        if self.game_state == RPSGameState.IDLE:
            return {"status": "idle", "message": "遊戲未在進行中"}

        self.game_state = RPSGameState.IDLE

        if self.game_thread:
            self.game_thread.join(timeout=2)

        # 計算遊戲統計
        total_time = time.time() - self.game_start_time if self.game_start_time else 0

        # 廣播遊戲停止
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "game_stopped",
            "message": "遊戲已停止",
            "data": {
                "total_time": total_time,
                "rounds_played": self.current_round,
                "final_scores": {pid: p.score for pid, p in self.players.items()}
            }
        })

        return {
            "status": "stopped",
            "message": "遊戲已停止",
            "summary": {
                "total_time": total_time,
                "rounds_played": self.current_round
            }
        }

    def get_game_status(self) -> Dict:
        """獲取遊戲狀態"""
        if self.game_state == RPSGameState.IDLE:
            return {
                "status": "idle",
                "message": "遊戲未在進行中",
                "is_playing": False
            }

        return {
            "status": self.game_state.value,
            "message": f"遊戲進行中 - {self.game_state.value}",
            "is_playing": True,
            "current_round": self.current_round,
            "target_score": self.target_score,
            "players": {
                pid: {
                    "name": p.name,
                    "score": p.score,
                    "is_ai": p.is_ai,
                    "current_gesture": p.current_gesture.value if p.current_gesture else None,
                    "gesture_ready": p.gesture_ready
                } for pid, p in self.players.items()
            },
            "game_duration": time.time() - self.game_start_time if self.game_start_time else 0
        }

    def _game_loop(self):
        """遊戲主循環"""
        try:
            while self.game_state != RPSGameState.IDLE:
                if self._check_game_winner():
                    self._finish_game()
                    break

                # 開始新回合
                self._start_new_round()

                # 等待手勢捕捉完成
                if not self._wait_for_gestures():
                    break

                # 計算並顯示結果
                self._process_round_result()

                # 檢查是否應該結束遊戲
                if self._check_game_winner():
                    self._finish_game()
                    break

        except Exception as exc:
            logger.exception("遊戲循環錯誤: %s", exc)
            self.status_broadcaster.broadcast_threadsafe({
                "channel": "rps",
                "stage": "error",
                "message": f"遊戲錯誤: {str(exc)}"
            })
            self.game_state = RPSGameState.IDLE

    def _start_new_round(self):
        """開始新回合"""
        self.current_round += 1
        self.game_state = RPSGameState.ROUND_COUNTDOWN

        # 重置玩家狀態
        for player in self.players.values():
            player.reset_round()

        # 廣播回合開始
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "round_start",
            "message": f"第 {self.current_round} 回合開始",
            "data": {
                "round": self.current_round,
                "countdown": self.round_countdown_time
            }
        })

        # 倒數計時
        for i in range(self.round_countdown_time, 0, -1):
            if self.game_state == RPSGameState.IDLE:
                return

            self.status_broadcaster.broadcast_threadsafe({
                "channel": "rps",
                "stage": "countdown",
                "message": f"倒數 {i}",
                "data": {"countdown": i}
            })
            time.sleep(1)

    def _wait_for_gestures(self) -> bool:
        """等待手勢捕捉"""
        self.game_state = RPSGameState.ROUND_GESTURE_CAPTURE

        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "gesture_capture",
            "message": "出招！",
            "data": {"capture_time": self.gesture_capture_time}
        })

        # 捕捉玩家手勢
        start_time = time.time()
        player_gesture_captured = False

        while time.time() - start_time < self.gesture_capture_time:
            if self.game_state == RPSGameState.IDLE:
                return False

            # 獲取當前手勢
            gesture_data = self.hand_gesture_service.get_current_gesture()
            current_gesture = HandGestureType(gesture_data["gesture"]) if gesture_data["gesture"] != "unknown" else HandGestureType.UNKNOWN
            confidence = gesture_data["confidence"]

            # 檢查手勢是否有效且穩定
            if current_gesture != HandGestureType.UNKNOWN and confidence > 0.7:
                if not player_gesture_captured:
                    self.players["player1"].current_gesture = current_gesture
                    self.players["player1"].gesture_ready = True
                    player_gesture_captured = True

            time.sleep(0.1)

        # AI 出招 (如果是 vs AI 模式)
        if "ai" in self.players:
            ai_gesture = self.ai_player.get_ai_gesture(self.current_round)
            self.players["ai"].current_gesture = ai_gesture
            self.players["ai"].gesture_ready = True

        # 如果玩家沒有出招，給予隨機手勢
        if not self.players["player1"].gesture_ready:
            self.players["player1"].current_gesture = random.choice([
                HandGestureType.ROCK, HandGestureType.PAPER, HandGestureType.SCISSORS
            ])
            self.players["player1"].gesture_ready = True

        return True

    def _process_round_result(self):
        """處理回合結果"""
        self.game_state = RPSGameState.ROUND_RESULT

        player1 = self.players["player1"]
        opponent = self.players["ai"] if "ai" in self.players else list(self.players.values())[1]

        # 計算結果
        result = self._determine_winner(player1.current_gesture, opponent.current_gesture)

        # 更新分數
        if result == RPSRoundResult.WIN:
            player1.add_result(RPSRoundResult.WIN)
            opponent.add_result(RPSRoundResult.LOSE)
        elif result == RPSRoundResult.LOSE:
            player1.add_result(RPSRoundResult.LOSE)
            opponent.add_result(RPSRoundResult.WIN)
        else:
            player1.add_result(RPSRoundResult.DRAW)
            opponent.add_result(RPSRoundResult.DRAW)

        # 記錄歷史
        round_data = {
            "round": self.current_round,
            "player1_gesture": player1.current_gesture.value,
            "opponent_gesture": opponent.current_gesture.value,
            "result": result.value,
            "timestamp": _now_ts()
        }
        self.round_history.append(round_data)

        # 更新 AI 歷史 (如果是 AI 模式)
        if self.ai_player:
            self.ai_player.add_round_history(player1.current_gesture, opponent.current_gesture)

        # 廣播結果
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "round_result",
            "message": self._get_result_message(result, player1.current_gesture, opponent.current_gesture),
            "data": {
                "round": self.current_round,
                "result": result.value,
                "gestures": {
                    "player1": player1.current_gesture.value,
                    "opponent": opponent.current_gesture.value
                },
                "scores": {
                    "player1": player1.score,
                    "opponent": opponent.score
                },
                "round_history": self.round_history[-3:]  # 最近3回合
            }
        })

        # 顯示結果
        time.sleep(self.result_display_time)

    def _determine_winner(self, gesture1: HandGestureType, gesture2: HandGestureType) -> RPSRoundResult:
        """判定勝負"""
        if gesture1 == gesture2:
            return RPSRoundResult.DRAW

        winning_combinations = {
            (HandGestureType.ROCK, HandGestureType.SCISSORS),
            (HandGestureType.PAPER, HandGestureType.ROCK),
            (HandGestureType.SCISSORS, HandGestureType.PAPER)
        }

        if (gesture1, gesture2) in winning_combinations:
            return RPSRoundResult.WIN
        else:
            return RPSRoundResult.LOSE

    def _get_result_message(self, result: RPSRoundResult, player_gesture: HandGestureType, opponent_gesture: HandGestureType) -> str:
        """獲取結果訊息"""
        gesture_emoji = {
            HandGestureType.ROCK: "✊",
            HandGestureType.PAPER: "✋",
            HandGestureType.SCISSORS: "✌️"
        }

        player_emoji = gesture_emoji.get(player_gesture, "❓")
        opponent_emoji = gesture_emoji.get(opponent_gesture, "❓")

        if result == RPSRoundResult.WIN:
            return f"你贏了！{player_emoji} 打敗 {opponent_emoji}"
        elif result == RPSRoundResult.LOSE:
            return f"你輸了！{opponent_emoji} 打敗 {player_emoji}"
        else:
            return f"平手！{player_emoji} vs {opponent_emoji}"

    def _check_game_winner(self) -> bool:
        """檢查是否有玩家達到目標分數"""
        for player in self.players.values():
            if player.score >= self.target_score:
                return True
        return False

    def _finish_game(self):
        """結束遊戲"""
        self.game_state = RPSGameState.GAME_FINISHED

        # 找出獲勝者
        winner = max(self.players.values(), key=lambda p: p.score)
        total_time = time.time() - self.game_start_time if self.game_start_time else 0

        # 廣播遊戲結束
        self.status_broadcaster.broadcast_threadsafe({
            "channel": "rps",
            "stage": "game_finished",
            "message": f"遊戲結束！獲勝者：{winner.name}",
            "data": {
                "winner": {
                    "name": winner.name,
                    "score": winner.score,
                    "is_ai": winner.is_ai
                },
                "final_scores": {pid: p.score for pid, p in self.players.items()},
                "total_rounds": self.current_round,
                "total_time": total_time,
                "round_history": self.round_history
            }
        })

        # 等待一段時間後重置
        time.sleep(3)
        self.game_state = RPSGameState.IDLE


__all__ = ["RPSGameService", "RPSGameMode", "RPSGameDifficulty"]