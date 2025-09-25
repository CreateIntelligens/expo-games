import pytest
from unittest.mock import MagicMock, patch
from backend.services.action_detection_service import ActionDetectionService, DifficultyLevel
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    """Create a mock StatusBroadcaster for testing."""
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def action_service(mock_broadcaster):
    """Create an ActionDetectionService instance for testing."""
    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_video_capture.return_value.isOpened.return_value = True
        service = ActionDetectionService(mock_broadcaster)
        # Mock the feature extractor to prevent mediapipe issues in tests
        service.feature_extractor = MagicMock()
        service.feature_extractor.extract_features.return_value = {
            'landmarks': [(i, i) for i in range(468)],
            'left_eye': [], 'right_eye': [], 'mouth': [],
            'eyebrow_left': [], 'eyebrow_right': [],
            'nose_tip': (0, 0), 'chin': (0, 0), 'forehead': (0, 0)
        }
        yield service

class TestActionDetectionService:
    """Test cases for ActionDetectionService functionality."""

    def test_initialization(self, action_service, mock_broadcaster):
        """Test ActionDetectionService initialization."""
        assert action_service.status_broadcaster == mock_broadcaster
        assert not action_service.is_detecting
        assert action_service.detection_thread is None
        assert action_service.difficulty_level == DifficultyLevel.EASY

    def test_start_action_detection_valid_difficulty(self, action_service):
        """Test starting action detection with valid difficulty."""
        with patch('threading.Thread') as mock_thread:
            result = action_service.start_action_detection("medium")
            assert result["status"] == "started"
            assert "動作檢測遊戲已開始" in result["message"]
            assert action_service.difficulty_level == DifficultyLevel.MEDIUM
            assert action_service.is_detecting
            mock_thread.assert_called_once()

    def test_start_action_detection_invalid_difficulty(self, action_service):
        """Test starting action detection with invalid difficulty - should default to easy."""
        with patch('threading.Thread'):
            result = action_service.start_action_detection("invalid")
            assert result["status"] == "started"
            assert action_service.difficulty_level == DifficultyLevel.EASY

    def test_start_action_detection_already_running(self, action_service):
        """Test starting action detection when already running."""
        action_service.is_detecting = True
        result = action_service.start_action_detection("easy")
        assert result["status"] == "error"
        assert "已在進行中" in result["message"]

    def test_stop_action_detection(self, action_service):
        """Test stopping action detection."""
        action_service.is_detecting = True
        mock_thread = MagicMock()
        action_service.detection_thread = mock_thread
        result = action_service.stop_action_detection()
        assert result["status"] == "stopped"
        assert "動作檢測已停止" in result["message"]
        assert not action_service.is_detecting
        mock_thread.join.assert_called_once()

    def test_get_detection_status_running(self, action_service):
        """Test getting detection status when running."""
        action_service.is_detecting = True
        action_service.difficulty_level = DifficultyLevel.HARD
        status = action_service.get_detection_status()
        assert status["status"] == "detecting"
        assert status["difficulty"] == "hard"
        assert "進行中" in status["message"]

    def test_get_detection_status_not_running(self, action_service):
        """Test getting detection status when not running."""
        action_service.is_detecting = False
        status = action_service.get_detection_status()
        assert status["status"] == "idle"
        assert "未在進行中" in status["message"]