import pytest
from unittest.mock import MagicMock, patch
from backend.services.drawing_service import DrawingService, DrawingMode, DrawingColor
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def drawing_service(mock_broadcaster):
    with patch('cv2.VideoCapture') as mock_video_capture:
        mock_video_capture.return_value.isOpened.return_value = True
        service = DrawingService(mock_broadcaster)
        service.finger_tracker = MagicMock()
        service.finger_tracker.is_available.return_value = True
        service.virtual_canvas = MagicMock()
        service.ai_recognizer = MagicMock()
        yield service

class TestDrawingService:

    def test_initialization(self, drawing_service, mock_broadcaster):
        assert drawing_service.status_broadcaster == mock_broadcaster
        assert not drawing_service.is_drawing
        assert drawing_service.drawing_thread is None
        assert drawing_service.drawing_mode == DrawingMode.INDEX_FINGER

    def test_start_drawing_session(self, drawing_service):
        with patch('threading.Thread') as mock_thread:
            result = drawing_service.start_drawing_session(mode="gesture_control", color="red", auto_recognize=False)
            assert result["status"] == "started"
            assert drawing_service.is_drawing
            assert drawing_service.drawing_mode == DrawingMode.GESTURE_CONTROL
            assert drawing_service.current_color == DrawingColor.RED
            assert not drawing_service.auto_recognize
            mock_thread.assert_called_once()

    def test_start_drawing_session_already_running(self, drawing_service):
        drawing_service.is_drawing = True
        result = drawing_service.start_drawing_session()
        assert result["status"] == "error"
        assert "已在進行中" in result["message"]

    def test_stop_drawing_session(self, drawing_service):
        drawing_service.is_drawing = True
        mock_thread = MagicMock()
        drawing_service.drawing_thread = mock_thread
        drawing_service.ai_recognizer.recognize_drawing.return_value = {"recognized": "circle"}
        drawing_service.virtual_canvas.get_canvas_base64.return_value = "base64_string"

        result = drawing_service.stop_drawing_session()
        assert result["status"] == "stopped"
        assert not drawing_service.is_drawing
        mock_thread.join.assert_called_once()
        assert result["final_recognition"]["recognized"] == "circle"

    def test_get_drawing_status_running(self, drawing_service):
        drawing_service.is_drawing = True
        drawing_service.drawing_mode = DrawingMode.GESTURE_CONTROL
        drawing_service.current_color = DrawingColor.BLUE
        drawing_service.virtual_canvas.get_canvas_base64.return_value = "base64_string"

        status = drawing_service.get_drawing_status()
        assert status["status"] == "drawing"
        assert status["is_drawing"]
        assert status["current_mode"] == "gesture_control"
        assert status["current_color"] == "blue"
        assert status["canvas_image"] == "base64_string"

    def test_get_drawing_status_not_running(self, drawing_service):
        drawing_service.is_drawing = False
        status = drawing_service.get_drawing_status()
        assert status["status"] == "idle"
        assert not status["is_drawing"]

    def test_recognize_current_drawing(self, drawing_service):
        drawing_service.virtual_canvas.get_canvas_image.return_value = "mock_canvas"
        drawing_service.ai_recognizer.recognize_drawing.return_value = {"recognized": "square"}

        result = drawing_service.recognize_current_drawing()
        assert result["recognized"] == "square"
        drawing_service.ai_recognizer.recognize_drawing.assert_called_with("mock_canvas")
        assert len(drawing_service.recognition_history) == 1

    def test_clear_canvas(self, drawing_service, mock_broadcaster):
        result = drawing_service.clear_canvas()
        assert result["status"] == "success"
        drawing_service.virtual_canvas.clear_canvas.assert_called_once()
        mock_broadcaster.broadcast_threadsafe.assert_called_once()