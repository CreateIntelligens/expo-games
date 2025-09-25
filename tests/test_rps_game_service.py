import pytest
from unittest.mock import MagicMock, patch
from backend.services.rps_game_service import RPSGameService, RPSGameMode, RPSGameDifficulty, RPSGameState, RPSRoundResult, HandGestureType
from backend.services.hand_gesture_service import HandGestureService
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def mock_gesture_service():
    return MagicMock(spec=HandGestureService)

@pytest.fixture
def rps_service(mock_broadcaster, mock_gesture_service):
    return RPSGameService(mock_broadcaster, mock_gesture_service)

class TestRPSGameService:

    def test_initialization(self, rps_service, mock_broadcaster, mock_gesture_service):
        assert rps_service.status_broadcaster == mock_broadcaster
        assert rps_service.hand_gesture_service == mock_gesture_service
        assert rps_service.game_state == RPSGameState.IDLE

    def test_start_game_vs_ai(self, rps_service):
        with patch('threading.Thread') as mock_thread:
            result = rps_service.start_game(mode="vs_ai", difficulty="medium", target_score=3)
            assert result["status"] == "started"
            assert rps_service.game_mode == RPSGameMode.VS_AI
            assert "ai" in rps_service.players
            assert rps_service.ai_player is not None
            mock_thread.assert_called_once()

    def test_start_game_already_running(self, rps_service):
        rps_service.game_state = RPSGameState.ROUND_COUNTDOWN
        result = rps_service.start_game()
        assert result["status"] == "error"

    def test_stop_game(self, rps_service):
        rps_service.game_state = RPSGameState.ROUND_RESULT
        mock_thread = MagicMock()
        rps_service.game_thread = mock_thread
        result = rps_service.stop_game()
        assert result["status"] == "stopped"
        assert rps_service.game_state == RPSGameState.IDLE
        mock_thread.join.assert_called_once()

    def test_get_game_status_running(self, rps_service):
        rps_service.game_state = RPSGameState.ROUND_RESULT
        rps_service.players["player1"] = MagicMock()
        status = rps_service.get_game_status()
        assert status["status"] == "result"
        assert status["is_playing"]

    def test_get_game_status_idle(self, rps_service):
        rps_service.game_state = RPSGameState.IDLE
        status = rps_service.get_game_status()
        assert status["status"] == "idle"
        assert not status["is_playing"]

    @pytest.mark.parametrize("p1, p2, winner", [
        (HandGestureType.ROCK, HandGestureType.SCISSORS, RPSRoundResult.WIN),
        (HandGestureType.PAPER, HandGestureType.ROCK, RPSRoundResult.WIN),
        (HandGestureType.SCISSORS, HandGestureType.PAPER, RPSRoundResult.WIN),
        (HandGestureType.ROCK, HandGestureType.ROCK, RPSRoundResult.DRAW),
        (HandGestureType.SCISSORS, HandGestureType.ROCK, RPSRoundResult.LOSE),
    ])
    def test_determine_winner(self, rps_service, p1, p2, winner):
        assert rps_service._determine_winner(p1, p2) == winner

    def test_check_game_winner(self, rps_service):
        rps_service.players["player1"] = MagicMock()
        rps_service.players["player1"].score = 3
        rps_service.target_score = 3
        assert rps_service._check_game_winner()

    def test_ai_choice(self, rps_service):
        rps_service.start_game(difficulty="hard")
        ai_player = rps_service.ai_player
        ai_player.player_history = [HandGestureType.ROCK, HandGestureType.PAPER]
        choice = ai_player.get_ai_gesture(round_number=3)
        assert choice in [HandGestureType.ROCK, HandGestureType.PAPER, HandGestureType.SCISSORS]