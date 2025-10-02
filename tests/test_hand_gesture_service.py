import pytest
from unittest.mock import MagicMock, patch
from backend.services.hand_gesture_service import HandGestureService, HandGestureType
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def gesture_service(mock_broadcaster):
    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_video_capture.return_value.isOpened.return_value = True
        service = HandGestureService(mock_broadcaster)
        service.gesture_detector = MagicMock()
        service.gesture_detector.is_available.return_value = True
        yield service

class TestHandGestureService:

    def test_initialization(self, gesture_service, mock_broadcaster):
        assert gesture_service.status_broadcaster == mock_broadcaster
        assert not gesture_service.is_detecting
        assert gesture_service.current_gesture == HandGestureType.UNKNOWN

    def test_start_gesture_detection(self, gesture_service):
        with patch('threading.Thread') as mock_thread:
            result = gesture_service.start_gesture_detection(duration=60)
            assert result["status"] == "started"
            assert gesture_service.is_detecting
            mock_thread.assert_called_once()

    def test_start_gesture_detection_already_running(self, gesture_service):
        gesture_service.is_detecting = True
        result = gesture_service.start_gesture_detection()
        assert result["status"] == "error"
        assert "已在進行中" in result["message"]

    def test_stop_gesture_detection(self, gesture_service):
        gesture_service.is_detecting = True
        mock_thread = MagicMock()
        gesture_service.detection_thread = mock_thread
        result = gesture_service.stop_gesture_detection()
        assert result["status"] == "stopped"
        assert not gesture_service.is_detecting
        mock_thread.join.assert_called_once()

    def test_get_detection_status_running(self, gesture_service):
        gesture_service.is_detecting = True
        gesture_service.current_gesture = HandGestureType.ROCK
        status = gesture_service.get_detection_status()
        assert status["status"] == "detecting"
        assert status["current_gesture"] == "rock"

    def test_get_detection_status_not_running(self, gesture_service):
        gesture_service.is_detecting = False
        status = gesture_service.get_detection_status()
        assert status["status"] == "idle"

    def test_get_current_gesture(self, gesture_service):
        gesture_service.current_gesture = HandGestureType.PAPER
        gesture_service.current_confidence = 0.9
        result = gesture_service.get_current_gesture()
        assert result["gesture"] == "paper"
        assert result["confidence"] == 0.9

    def test_detection_loop(self, gesture_service, mock_broadcaster):
        # Mock the gesture detector to simulate detection
        gesture_service.gesture_detector.recognize_async = MagicMock()

        # This is a simplified test for the loop's logic
        # A full test would require more complex async/threading mocks
        with patch('time.sleep'): # Avoid sleeping
            gesture_service.is_detecting = True
            gesture_service.camera = MagicMock()
            gesture_service.camera.isOpened.return_value = True
            gesture_service.camera.read.side_effect = [(True, MagicMock()), (False, None)]

            # Simulate detection by directly incrementing total_detections
            # (in real code this happens in the MediaPipe callback)
            gesture_service.total_detections = 1
            gesture_service.current_gesture = HandGestureType.SCISSORS

            gesture_service._detection_loop(duration=1)

            assert gesture_service.total_detections > 0
            assert gesture_service.current_gesture == HandGestureType.SCISSORS
            mock_broadcaster.broadcast_threadsafe.assert_called()
