# =============================================================================
# test_emotion_api.py - 情緒分析API端點測試
# =============================================================================
# 測試情緒分析相關的API端點，包括檔案上傳、預覽功能、進度更新等
# =============================================================================

import pytest
import asyncio
import json
import base64
import tempfile
import os
from io import BytesIO
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import UploadFile
import websockets

from backend.app import app
from backend.services.emotion_service import EmotionService


class TestEmotionAPI:
    """情緒分析API測試類"""

    @pytest.fixture
    def client(self):
        """建立FastAPI測試客戶端"""
        return TestClient(app)

    @pytest.fixture
    def sample_image_file(self):
        """建立測試用的圖片檔案"""
        # 建立一個小的測試圖片
        image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        return ("test_image.png", BytesIO(image_data), "image/png")

    @pytest.fixture
    def sample_video_file(self):
        """建立測試用的影片檔案"""
        # 建立一個小的測試影片檔案（模擬）
        video_data = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom'
        return ("test_video.mp4", BytesIO(video_data), "video/mp4")

    @pytest.fixture
    def large_file(self):
        """建立超過大小限制的檔案"""
        # 建立一個100MB的大檔案
        large_data = b'0' * (100 * 1024 * 1024)
        return ("large_file.png", BytesIO(large_data), "image/png")

    def test_image_emotion_analysis_success(self, client, sample_image_file):
        """測試圖片情緒分析成功案例"""
        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.return_value = {
                "emotion_zh": "開心",
                "emotion_en": "happy",
                "emoji": "😊",
                "confidence": 0.95,
                "face_detected": True,
                "engine": "deepface",
                "raw_scores": {
                    "happy": 0.95,
                    "sad": 0.02,
                    "neutral": 0.03
                }
            }

            filename, file_content, content_type = sample_image_file
            response = client.post(
                "/api/emotion/analyze/image",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["emotion_zh"] == "開心"
            assert data["emotion_en"] == "happy"
            assert data["emoji"] == "😊"
            assert data["confidence"] == 0.95
            assert data["face_detected"] is True

    def test_image_emotion_analysis_no_file(self, client):
        """測試未提供檔案的情況"""
        response = client.post("/api/emotion/analyze/image")
        assert response.status_code == 422  # FastAPI validation error

    def test_image_emotion_analysis_invalid_format(self, client):
        """測試不支援的檔案格式"""
        invalid_file = ("test.txt", BytesIO(b"not an image"), "text/plain")
        filename, file_content, content_type = invalid_file

        response = client.post(
            "/api/emotion/analyze/image",
            files={"file": (filename, file_content, content_type)}
        )

        assert response.status_code == 400
        assert "僅支援圖片格式" in response.json()["detail"]

    def test_image_emotion_analysis_file_too_large(self, client, large_file):
        """測試檔案過大的情況"""
        filename, file_content, content_type = large_file

        response = client.post(
            "/api/emotion/analyze/image",
            files={"file": (filename, file_content, content_type)}
        )

        assert response.status_code == 413
        assert "檔案過大" in response.json()["detail"]

    def test_image_emotion_analysis_service_error(self, client, sample_image_file):
        """測試服務錯誤的情況"""
        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.side_effect = Exception("DeepFace analysis failed")

            filename, file_content, content_type = sample_image_file
            response = client.post(
                "/api/emotion/analyze/image",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == 200  # 返回預設值
            data = response.json()
            assert data["emotion_zh"] == "中性"
            assert data["confidence"] == 0.0
            assert "error" in data

    def test_video_emotion_analysis_success(self, client, sample_video_file):
        """測試影片情緒分析成功案例"""
        def mock_stream_generator(video_path, frame_interval):
            """模擬串流分析結果"""
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
                "emotion_zh": "悲傷",
                "emotion_en": "sad",
                "emoji": "😢",
                "confidence": 0.76,
                "frame_time": 1.0,
                "progress": 50,
                "completed": False
            }
            yield {
                "message": "影片分析完成",
                "total_frames": 2,
                "progress": 100,
                "completed": True
            }

        with patch('backend.services.emotion_service.EmotionService.analyze_video_deepface_stream') as mock_stream:
            mock_stream.return_value = mock_stream_generator("", 0.5)

            filename, file_content, content_type = sample_video_file
            response = client.post(
                "/api/emotion/analyze/video",
                files={"file": (filename, file_content, content_type)},
                data={"frame_interval": "0.5"}
            )

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

            # 解析SSE數據
            content = response.content.decode()
            lines = content.strip().split('\n')

            # 驗證至少有SSE格式的數據
            assert any(line.startswith("data: ") for line in lines)

    def test_video_emotion_analysis_invalid_format(self, client):
        """測試影片檔案格式錯誤"""
        invalid_file = ("test.txt", BytesIO(b"not a video"), "text/plain")
        filename, file_content, content_type = invalid_file

        response = client.post(
            "/api/emotion/analyze/video",
            files={"file": (filename, file_content, content_type)},
            data={"frame_interval": "0.5"}
        )

        assert response.status_code == 400
        assert "僅支援影片格式" in response.json()["detail"]

    def test_video_emotion_analysis_invalid_interval(self, client, sample_video_file):
        """測試無效的截幀間隔"""
        filename, file_content, content_type = sample_video_file

        # 測試間隔過小
        response = client.post(
            "/api/emotion/analyze/video",
            files={"file": (filename, file_content, content_type)},
            data={"frame_interval": "0.05"}
        )
        assert response.status_code == 400

        # 測試間隔過大
        response = client.post(
            "/api/emotion/analyze/video",
            files={"file": (filename, file_content, content_type)},
            data={"frame_interval": "6.0"}
        )
        assert response.status_code == 400

    def test_video_emotion_analysis_service_error(self, client, sample_video_file):
        """測試影片分析服務錯誤"""
        def mock_error_generator(video_path, frame_interval):
            """產生器函數，在調用時拋出異常"""
            if False:  # 讓生成器函數有yield，但不執行
                yield {}
            raise Exception("Video processing failed")

        with patch('backend.services.emotion_service.EmotionService.analyze_video_deepface_stream') as mock_stream:
            mock_stream.return_value = mock_error_generator("", 0.5)

            filename, file_content, content_type = sample_video_file
            response = client.post(
                "/api/emotion/analyze/video",
                files={"file": (filename, file_content, content_type)},
                data={"frame_interval": "0.5"}
            )

            assert response.status_code == 200
            content = response.content.decode()
            assert "串流分析錯誤" in content


class TestEmotionWebSocket:
    """情緒分析WebSocket測試類"""

    @pytest.fixture
    def sample_base64_image(self):
        """建立base64編碼的測試圖片"""
        image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\nIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        return base64.b64encode(image_data).decode()

    @pytest.mark.asyncio
    async def test_websocket_emotion_stream_success(self, sample_base64_image):
        """測試WebSocket情緒串流成功案例"""
        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.return_value = {
                "emotion_zh": "開心",
                "emotion_en": "happy",
                "emoji": "😊",
                "confidence": 0.92,
                "face_detected": True,
                "engine": "deepface"
            }

            with TestClient(app) as client:
                with client.websocket_connect("/ws/emotion") as websocket:
                    # 發送測試幀
                    test_message = {
                        "type": "frame",
                        "image": f"data:image/png;base64,{sample_base64_image}",
                        "timestamp": 12345.67
                    }
                    websocket.send_json(test_message)

                    # 接收分析結果
                    response = websocket.receive_json()

                    assert response["type"] == "result"
                    assert response["emotion_zh"] == "開心"
                    assert response["emotion_en"] == "happy"
                    assert response["emoji"] == "😊"
                    assert response["confidence"] == 0.92
                    assert response["timestamp"] == 12345.67

    @pytest.mark.asyncio
    async def test_websocket_emotion_stream_ping_pong(self):
        """測試WebSocket心跳功能"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/emotion") as websocket:
                # 發送ping消息
                websocket.send_json({"type": "ping"})

                # 接收pong回應
                response = websocket.receive_text()
                assert response == "pong"

    @pytest.mark.asyncio
    async def test_websocket_emotion_stream_invalid_message_type(self):
        """測試WebSocket無效消息類型"""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/emotion") as websocket:
                # 發送無效消息類型
                websocket.send_json({"type": "invalid_type"})

                # 接收錯誤回應
                response = websocket.receive_json()
                assert response["type"] == "error"
                assert "不支持的消息類型" in response["message"]

    @pytest.mark.asyncio
    async def test_websocket_emotion_stream_analysis_error(self, sample_base64_image):
        """測試WebSocket分析錯誤"""
        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.side_effect = Exception("Analysis failed")

            with TestClient(app) as client:
                with client.websocket_connect("/ws/emotion") as websocket:
                    # 發送測試幀
                    test_message = {
                        "type": "frame",
                        "image": f"data:image/png;base64,{sample_base64_image}",
                        "timestamp": 12345.67
                    }
                    websocket.send_json(test_message)

                    # 接收錯誤回應
                    response = websocket.receive_json()

                    assert response["type"] == "error"
                    assert "影像分析錯誤" in response["message"]
                    assert response["timestamp"] == 12345.67


class TestFileUploadAndPreview:
    """檔案上傳和預覽功能測試類"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_supported_image_formats(self, client):
        """測試支援的圖片格式"""
        supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.gif']

        for ext in supported_formats:
            with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
                mock_analyze.return_value = {
                    "emotion_zh": "中性",
                    "face_detected": True,
                    "confidence": 0.5
                }

                filename = f"test{ext}"
                file_content = BytesIO(b"fake image data")

                response = client.post(
                    "/api/emotion/analyze/image",
                    files={"file": (filename, file_content, "image/jpeg")}
                )

                assert response.status_code == 200

    def test_supported_video_formats(self, client):
        """測試支援的影片格式"""
        supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm']

        for ext in supported_formats:
            with patch('backend.services.emotion_service.EmotionService.analyze_video_deepface_stream') as mock_stream:
                mock_stream.return_value = iter([{"completed": True}])

                filename = f"test{ext}"
                file_content = BytesIO(b"fake video data")

                response = client.post(
                    "/api/emotion/analyze/video",
                    files={"file": (filename, file_content, "video/mp4")},
                    data={"frame_interval": "0.5"}
                )

                assert response.status_code == 200

    def test_file_size_validation(self, client):
        """測試檔案大小驗證"""
        # 測試正常大小檔案
        normal_file = ("test.png", BytesIO(b"small image"), "image/png")
        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.return_value = {"emotion_zh": "中性", "face_detected": True}

            filename, file_content, content_type = normal_file
            response = client.post(
                "/api/emotion/analyze/image",
                files={"file": (filename, file_content, content_type)}
            )
            assert response.status_code == 200


class TestProgressAndStatusUpdates:
    """進度條和狀態更新測試類"""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_upload_progress_simulation(self, client):
        """測試上傳進度模擬"""
        # 這個測試驗證API能正確處理檔案上傳
        image_file = ("progress_test.png", BytesIO(b"test data for progress"), "image/png")

        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            mock_analyze.return_value = {
                "emotion_zh": "開心",
                "confidence": 0.85,
                "face_detected": True
            }

            filename, file_content, content_type = image_file
            response = client.post(
                "/api/emotion/analyze/image",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == 200
            # 驗證能夠成功完成整個分析流程
            data = response.json()
            assert "emotion_zh" in data
            assert "confidence" in data

    def test_video_stream_progress_tracking(self, client):
        """測試影片串流進度追蹤"""
        def mock_progress_stream(video_path, frame_interval):
            # 模擬有進度資訊的串流
            for i, progress in enumerate([25, 50, 75, 100]):
                yield {
                    "emotion_zh": "開心",
                    "frame_time": i * 0.5,
                    "progress": progress,
                    "completed": progress == 100
                }

        with patch('backend.services.emotion_service.EmotionService.analyze_video_deepface_stream') as mock_stream:
            mock_stream.return_value = mock_progress_stream("", 0.5)

            video_file = ("progress_video.mp4", BytesIO(b"fake video"), "video/mp4")
            filename, file_content, content_type = video_file

            response = client.post(
                "/api/emotion/analyze/video",
                files={"file": (filename, file_content, content_type)},
                data={"frame_interval": "0.5"}
            )

            assert response.status_code == 200
            # 驗證SSE回應包含進度資訊
            content = response.content.decode()
            assert "progress" in content
            assert "completed" in content

    def test_status_message_sequence(self, client):
        """測試狀態消息序列"""
        # 驗證API返回的狀態消息包含必要資訊
        image_file = ("status_test.png", BytesIO(b"status test data"), "image/png")

        with patch('backend.services.emotion_service.EmotionService.analyze_image_deepface') as mock_analyze:
            # 模擬分析過程
            mock_analyze.return_value = {
                "emotion_zh": "驚訝",
                "emotion_en": "surprise",
                "emoji": "😲",
                "confidence": 0.78,
                "face_detected": True,
                "engine": "deepface"
            }

            filename, file_content, content_type = image_file
            response = client.post(
                "/api/emotion/analyze/image",
                files={"file": (filename, file_content, content_type)}
            )

            assert response.status_code == 200
            data = response.json()

            # 驗證回應包含完整的狀態資訊
            required_fields = ["emotion_zh", "emotion_en", "emoji", "confidence", "face_detected"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
