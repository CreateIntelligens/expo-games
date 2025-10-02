# =============================================================================
# test_rps_game_service.py - 猜拳遊戲服務測試
# =============================================================================

import pytest
from unittest.mock import MagicMock, patch
from backend.services.rps_game_service import RPSGameService, GameState, RoundResult
from backend.services.mediapipe_rps_detector import RPSGesture
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    """模擬狀態廣播器"""
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def rps_service(mock_broadcaster):
    """創建 RPS 遊戲服務實例"""
    return RPSGameService(mock_broadcaster)

class TestRPSGameService:
    """RPS 遊戲服務測試類"""

    def test_initialization(self, rps_service, mock_broadcaster):
        """測試服務初始化"""
        assert rps_service.status_broadcaster == mock_broadcaster
        assert rps_service.game_state == GameState.IDLE
        assert rps_service.player_score == 0
        assert rps_service.computer_score == 0
        assert rps_service.target_score == 1

    def test_start_game_success(self, rps_service):
        """測試成功開始遊戲"""
        with patch('threading.Thread') as mock_thread, \
             patch.object(rps_service.detector, 'is_available', return_value=True):
            result = rps_service.start_game(target_score=1)
            assert result["status"] == "started"
            assert rps_service.game_state == GameState.COUNTDOWN
            assert rps_service.target_score == 1
            mock_thread.assert_called_once()

    def test_start_game_already_running(self, rps_service):
        """測試遊戲已在進行中時開始遊戲"""
        rps_service.game_state = GameState.COUNTDOWN
        result = rps_service.start_game()
        assert result["status"] == "error"
        assert "遊戲已在進行中" in result["message"]

    def test_stop_game_idle(self, rps_service):
        """測試停止閒置遊戲"""
        result = rps_service.stop_game()
        assert result["status"] == "idle"
        assert "遊戲未在進行中" in result["message"]

    def test_stop_game_running(self, rps_service):
        """測試停止進行中的遊戲"""
        rps_service.game_state = GameState.WAITING_PLAYER
        mock_thread = MagicMock()
        rps_service.game_thread = mock_thread

        result = rps_service.stop_game()
        assert result["status"] == "stopped"
        assert rps_service.game_state == GameState.IDLE
        mock_thread.join.assert_called_once()

    def test_get_game_status_idle(self, rps_service):
        """測試獲取閒置狀態"""
        status = rps_service.get_game_status()
        assert status["status"] == "idle"
        assert not status["is_playing"]
        assert status["current_round"] == 0

    def test_get_game_status_running(self, rps_service):
        """測試獲取運行中狀態"""
        rps_service.game_state = GameState.WAITING_PLAYER
        rps_service.current_round = 1
        rps_service.player_score = 0
        rps_service.computer_score = 0

        status = rps_service.get_game_status()
        assert status["status"] == "waiting_player"
        assert status["is_playing"]
        assert status["current_round"] == 1

    @pytest.mark.parametrize("player,computer,expected", [
        (RPSGesture.ROCK, RPSGesture.SCISSORS, RoundResult.WIN),
        (RPSGesture.PAPER, RPSGesture.ROCK, RoundResult.WIN),
        (RPSGesture.SCISSORS, RPSGesture.PAPER, RoundResult.WIN),
        (RPSGesture.ROCK, RPSGesture.ROCK, RoundResult.DRAW),
        (RPSGesture.PAPER, RPSGesture.PAPER, RoundResult.DRAW),
        (RPSGesture.SCISSORS, RPSGesture.SCISSORS, RoundResult.DRAW),
        (RPSGesture.ROCK, RPSGesture.PAPER, RoundResult.LOSE),
        (RPSGesture.PAPER, RPSGesture.SCISSORS, RoundResult.LOSE),
        (RPSGesture.SCISSORS, RPSGesture.ROCK, RoundResult.LOSE),
        (RPSGesture.UNKNOWN, RPSGesture.ROCK, RoundResult.LOSE),  # UNKNOWN 手勢判輸
    ])
    def test_determine_winner(self, rps_service, player, computer, expected):
        """測試勝負判定邏輯"""
        result = rps_service._determine_winner(player, computer)
        assert result == expected

    def test_submit_player_gesture_wrong_state(self, rps_service):
        """測試在錯誤狀態下提交手勢"""
        rps_service.game_state = GameState.IDLE
        result = rps_service.submit_player_gesture("/path/to/image.jpg")
        assert result["status"] == "error"
        assert "當前不接受出拳" in result["message"]

    def test_submit_player_gesture_success(self, rps_service):
        """測試成功提交玩家手勢"""
        rps_service.game_state = GameState.WAITING_PLAYER

        # 模擬 MediaPipe 檢測器
        with patch.object(rps_service.detector, 'detect', return_value=(RPSGesture.ROCK, 0.8)):
            result = rps_service.submit_player_gesture("/path/to/image.jpg")

            assert result["status"] == "success"
            assert result["gesture"] == "rock"
            assert result["confidence"] == 0.8
            assert rps_service.player_gesture == RPSGesture.ROCK

    def test_submit_player_gesture_low_confidence(self, rps_service):
        """測試信心度不足的手勢辨識"""
        rps_service.game_state = GameState.WAITING_PLAYER

        # 模擬低信心度的辨識結果
        with patch.object(rps_service.detector, 'detect', return_value=(RPSGesture.UNKNOWN, 0.3)):
            result = rps_service.submit_player_gesture("/path/to/image.jpg")

            assert result["status"] == "error"
            assert "無法辨識手勢" in result["message"]
            assert result["confidence"] == 0.3
