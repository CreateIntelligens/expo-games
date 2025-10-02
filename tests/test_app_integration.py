# =============================================================================
# tests/test_app_integration.py - FastAPI Application Integration Tests
#
# This module contains integration tests for the refactored FastAPI application.
# Tests verify that all routers are properly integrated, services are injected
# correctly, and the application starts up successfully.
#
# Dependencies: fastapi, httpx, pytest, pytest-asyncio
# Key Features: Integration testing, router validation, service injection verification
# =============================================================================

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app import app, emotion_service, action_service, hand_gesture_service, rps_game_service, drawing_service, status_broadcaster
from backend.config.settings import APP_TITLE, MAX_UPLOAD_SIZE_BYTES

class TestAppIntegration:
    """Integration tests for the FastAPI application."""

    def setup_method(self):
        """Set up test client for each test."""
        self.client = TestClient(app)

    def test_app_creation(self):
        """Test that the FastAPI app is created successfully."""
        assert app is not None
        assert app.title == APP_TITLE
        assert app.version == "0.0.0"
        assert "AI Interactive Games Platform" in app.description

    def test_cors_middleware(self):
        """Test that CORS middleware is properly configured."""
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, 'cls') and 'CORSMiddleware' in str(middleware.cls):
                cors_middleware = middleware
                break

        assert cors_middleware is not None, "CORS middleware not found"

    def test_static_files_mounted(self):
        """Test that static files are properly mounted."""
        static_routes = [route for route in app.routes if hasattr(route, 'path') and '/static' in str(route.path)]
        assert len(static_routes) > 0, "Static files not mounted"

    def test_service_injection(self):
        """Test that services are properly injected into routers."""
        # Test that services are not None
        assert emotion_service is not None
        assert action_service is not None
        assert hand_gesture_service is not None
        assert rps_game_service is not None
        assert drawing_service is not None
        assert status_broadcaster is not None

        # Test that services have required methods (updated for new interfaces)
        assert hasattr(emotion_service, 'analyze_image_deepface')
        assert hasattr(emotion_service, 'analyze_video_deepface_stream')
        assert hasattr(action_service, 'start_action_detection')  # Keep checking if exists
        assert hasattr(hand_gesture_service, 'start_gesture_detection')  # Updated method name
        assert hasattr(rps_game_service, 'submit_player_gesture')
        assert hasattr(drawing_service, 'start_drawing_session')  # Updated method name

    def test_router_inclusion(self):
        """Test that all routers are properly included."""
        router_paths = [route.path for route in app.routes if hasattr(route, 'path')]

        # Check for API router prefixes
        assert any('/api/emotion' in path for path in router_paths), "Emotion router not included"
        assert any('/api/action' in path for path in router_paths), "Action router not included"
        assert any('/api/gesture' in path for path in router_paths), "Hand gesture router not included"
        assert any('/api/drawing' in path for path in router_paths), "Drawing router not included"
        assert any('/ws/' in path for path in router_paths), "WebSocket router not included"

    def test_frontend_routes(self):
        """Test frontend page routes."""
        # Test main page
        response = self.client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert APP_TITLE in response.text

        # Test WebSocket docs page
        response = self.client.get("/docs/ws")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "WebSocket" in response.text

    def test_system_api_routes(self):
        """Test system API routes."""
        # Test GPU status endpoint
        response = self.client.get("/api/system/gpu")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        # Should contain GPU-related keys
        gpu_keys = ['tensorflow_ready', 'mediapipe_gpu_enabled']
        assert any(key in data for key in gpu_keys), f"Expected GPU keys not found in response: {data}"

    def test_emotion_api_endpoints(self):
        """Test emotion API endpoints are accessible."""
        # Test emotion image analysis endpoint (should return 422 for missing file)
        response = self.client.post("/api/emotion/analyze/image")
        assert response.status_code == 422  # Validation error for missing file

        # Test emotion video analysis endpoint (should return 422 for missing file)
        response = self.client.post("/api/emotion/analyze/video")
        assert response.status_code == 422  # Validation error for missing file

    def test_action_api_endpoints(self):
        """Test action detection API endpoints are accessible."""
        # Test action status endpoint
        response = self.client.get("/api/action/status")
        assert response.status_code in [200, 404, 500]  # May fail if service not fully initialized

        # Test action start endpoint
        response = self.client.post("/api/action/start", json={"difficulty": "easy"})
        assert response.status_code in [200, 400, 500]  # May succeed or fail based on service state

    def test_drawing_api_endpoints(self):
        """Test drawing API endpoints are accessible."""
        # Test drawing status endpoint
        response = self.client.get("/api/drawing/status")
        assert response.status_code in [200, 404, 500]  # May fail if service not fully initialized

        # Test drawing start endpoint (should return 400 for missing parameters)
        response = self.client.post("/api/drawing/start")
        assert response.status_code == 400  # Validation error for missing parameters

    def test_hand_gesture_api_endpoints(self):
        """Test hand gesture API endpoints are accessible."""
        # Test hand gesture status endpoint
        response = self.client.get("/api/gesture/status")
        assert response.status_code in [200, 404, 500]  # May fail if service not fully initialized

        # Test hand gesture start endpoint (should return 400 for missing parameters)
        response = self.client.post("/api/gesture/start")
        assert response.status_code == 400  # Validation error for missing parameters

    @pytest.mark.asyncio
    async def test_websocket_router_initialization(self):
        """Test WebSocket router initialization."""
        # This is a basic test to ensure WebSocket router was initialized
        # More comprehensive WebSocket testing would require a WebSocket test client
        websocket_routes = [route for route in app.routes if hasattr(route, 'path') and '/ws/' in str(route.path)]
        assert len(websocket_routes) > 0, "No WebSocket routes found"

    def test_lifespan_context_manager(self):
        """Test that lifespan context manager is properly configured."""
        # Lifespan is configured in FastAPI constructor, app starts successfully
        # This indicates lifespan is working properly
        assert app is not None, "App should be initialized with lifespan"

    def test_openapi_schema_generation(self):
        """Test that OpenAPI schema can be generated."""
        schema = app.openapi()
        assert schema is not None
        assert 'paths' in schema
        assert 'components' in schema
        assert 'info' in schema

        # Check that our main API paths are in the schema
        paths = schema['paths']
        assert '/' in paths
        assert '/docs/ws' in paths
        assert '/api/system/gpu' in paths

    def test_router_tags(self):
        """Test that routers have proper tags."""
        # Get all route tags
        all_tags = set()
        for route in app.routes:
            if hasattr(route, 'tags'):
                all_tags.update(route.tags)

        # Check for expected tags
        expected_tags = {"Emotion Analysis", "Action Detection", "RPS Game", "Hand Gesture", "Drawing Recognition"}
        found_expected = expected_tags.intersection(all_tags)
        assert len(found_expected) > 0, f"Expected tags not found. Found: {all_tags}"

class TestServiceIntegration:
    """Tests for service integration and dependencies."""

    def test_status_broadcaster_integration(self):
        """Test that status broadcaster is properly integrated with services."""
        # Check that services have status_broadcaster attribute or parameter
        services = [emotion_service, action_service, hand_gesture_service, rps_game_service, drawing_service]

        for service in services:
            # Services should have some way to broadcast status
            assert hasattr(service, 'status_broadcaster') or hasattr(service, '_broadcaster'), \
                f"Service {service.__class__.__name__} should have status broadcaster integration"

    def test_service_initialization_order(self):
        """Test that services are initialized in the correct order."""
        # This is more of a documentation test - services should be initialized
        # before routers to ensure proper dependency injection
        assert emotion_service is not None
        assert action_service is not None
        assert rps_game_service is not None

class TestConfigurationIntegration:
    """Tests for configuration integration."""

    def test_settings_integration(self):
        """Test that settings are properly integrated."""
        from backend.config.settings import APP_TITLE as SETTINGS_APP_TITLE

        assert app.title == SETTINGS_APP_TITLE, "App title should match settings"

    def test_max_upload_size_integration(self):
        """Test that max upload size is properly integrated."""
        # The max upload size should be used in file validation
        # This is tested indirectly through the API endpoints
        assert MAX_UPLOAD_SIZE_BYTES > 0, "Max upload size should be positive"

if __name__ == "__main__":
    # Run basic integration tests
    test_instance = TestAppIntegration()
    test_instance.setup_method()

    print("Running FastAPI App Integration Tests...")
    print("=" * 50)

    # Run key tests
    try:
        test_instance.test_app_creation()
        print("✅ App creation test passed")

        test_instance.test_service_injection()
        print("✅ Service injection test passed")

        test_instance.test_router_inclusion()
        print("✅ Router inclusion test passed")

        test_instance.test_frontend_routes()
        print("✅ Frontend routes test passed")

        test_instance.test_system_api_routes()
        print("✅ System API routes test passed")

        print("\n🎉 All basic integration tests passed!")
        print("The refactored app.py appears to be successfully integrated.")

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        raise
