import pytest
from unittest.mock import MagicMock, patch
from backend.services.emotion_service import EmotionService, EmotionType
from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def mock_broadcaster():
    return MagicMock(spec=StatusBroadcaster)

@pytest.fixture
def emotion_service(mock_broadcaster):
    with patch('cv2.VideoCapture') as mock_video_capture, \
         patch('backend.services.emotion_service.DeepFace') as mock_deepface, \
         patch('backend.services.emotion_service.mp.solutions.face_mesh') as mock_face_mesh:
        mock_video_capture.return_value.isOpened.return_value = True
        service = EmotionService(mock_broadcaster)
        service.feature_extractor = MagicMock()
        service.feature_extractor.is_available.return_value = True
        service.emotion_detector = MagicMock()
        yield service

class TestEmotionService:

    def test_initialization(self, emotion_service, mock_broadcaster):
        assert emotion_service.status_broadcaster == mock_broadcaster
        # 簡化後的服務只處理圖片分析，無攝影機檢測狀態

    @patch('cv2.imread')
    def test_analyze_image_success(self, mock_imread, emotion_service):
        mock_imread.return_value = MagicMock()
        emotion_service.feature_extractor.extract_features.return_value = {"some_feature": 1}
        emotion_service.emotion_detector.detect_emotion.return_value = (EmotionType.HAPPY, 0.9)

        result = emotion_service.analyze_image("fake_path.jpg")
        assert result["emotion"] == "開心"
        assert result["confidence"] == 0.9

    @patch('cv2.VideoCapture')
    def test_analyze_video_success(self, mock_videocapture, emotion_service):
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.side_effect = [(True, MagicMock()), (False, None)] # Simulate one frame
        mock_videocapture.return_value = mock_cap

        emotion_service.feature_extractor.extract_features.return_value = {"some_feature": 1}
        emotion_service.emotion_detector.detect_emotion.return_value = (EmotionType.SAD, 0.8)

        result = emotion_service.analyze_video("fake_video.mp4")
        assert result["dominant_emotion"] == "悲傷"
        assert result["confidence_average"] > 0

    @patch('backend.services.emotion_service.DeepFace')
    def test_analyze_image_deepface_success(self, mock_deepface, emotion_service):
        mock_deepface.analyze.return_value = [{
            'dominant_emotion': 'happy',
            'emotion': {'happy': 99.0, 'sad': 1.0}
        }]

        result = emotion_service.analyze_image_deepface("fake_path.jpg")
        assert result["emotion_en"] == "happy"
        assert result["emotion_zh"] == "開心"
        assert result["confidence"] == 0.99
        assert result["engine"] == "deepface"

    @patch('backend.services.emotion_service.DeepFace')
    def test_analyze_video_deepface_stream_success(self, mock_deepface, emotion_service):
        # Mock the stream generator
        def mock_stream_generator(video_path, frame_interval):
            yield {
                "emotion_zh": "開心",
                "emotion_en": "happy",
                "emoji": "😊",
                "confidence": 0.89,
                "frame_time": 0.5,
                "progress": 25,
                "completed": False
            }
            yield {
                "message": "影片分析完成",
                "total_frames": 2,
                "progress": 100,
                "completed": True
            }

        with patch.object(emotion_service, 'analyze_video_deepface_stream', side_effect=mock_stream_generator):
            results = list(emotion_service.analyze_video_deepface_stream("fake_video.mp4", 0.5))
            assert len(results) == 2
            assert results[0]["emotion_zh"] == "開心"
            assert results[1]["completed"] is True

    @patch('cv2.imread')
    def test_analyze_image_simple_success(self, mock_imread, emotion_service):
        mock_imread.return_value = MagicMock()  # Mock image array
        emotion_service.feature_extractor.extract_features.return_value = {"some_feature": 1}
        emotion_service.emotion_detector.detect_emotion.return_value = (EmotionType.NEUTRAL, 0.5)

        result = emotion_service.analyze_image_simple("fake_path.jpg")
        assert result["emotion_zh"] == "面無表情"
        assert result["emotion_en"] == "neutral"
        assert result["confidence"] == 0.5

    def test_analyze_video_simple_success(self, emotion_service):
        # Mock the full analyze_video method
        with patch.object(emotion_service, 'analyze_video') as mock_analyze_video:
            mock_analyze_video.return_value = {
                "dominant_emotion": "開心",
                "confidence_average": 0.85
            }

            result = emotion_service.analyze_video_simple("fake_video.mp4")
            assert result["emotion_zh"] == "開心"
            assert result["confidence"] == 0.85
