# =============================================================================
# tests/test_mediapipe_rps.py - MediaPipe RPS Detector Test Script
#
# Test script for MediaPipe-based Rock-Paper-Scissors gesture recognition.
# Tests detector initialization, model loading, and gesture recognition accuracy.
#
# Dependencies: mediapipe, opencv-python, numpy
# Key Features: Unit testing, gesture recognition validation, performance testing
# =============================================================================

#!/usr/bin/env python3
"""
測試 MediaPipe RPS 辨識器
"""

import sys
from pathlib import Path

# 加入專案路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.mediapipe_rps_detector import MediaPipeRPSDetector, RPSGesture


def test_detector():
    """測試辨識器"""
    print("=" * 60)
    print("MediaPipe RPS 辨識器測試")
    print("=" * 60)

    # 建立辨識器
    detector = MediaPipeRPSDetector()

    print(f"\n辨識器可用: {detector.is_available()}")
    if not detector.is_available():
        print(f"錯誤: {detector.init_error}")
        return

    print(f"模型路徑: {detector.model_path}")

    # 測試圖片
    test_images = [
        "test_assets/石頭.jpg",
        "test_assets/布.jpg",
        "test_assets/剪刀.jpg",
        "test_assets/imagetest1.png",
        "test_assets/imagetest2.png",
    ]

    print("\n" + "=" * 60)
    print("開始辨識測試")
    print("=" * 60)

    for img_path in test_images:
        full_path = project_root / img_path
        if not full_path.exists():
            print(f"\n❌ 圖片不存在: {img_path}")
            continue

        print(f"\n📷 測試圖片: {img_path}")
        gesture, confidence = detector.detect(str(full_path))

        if gesture != RPSGesture.UNKNOWN:
            print(f"✅ 辨識結果: {gesture.value}")
            print(f"   信心度: {confidence:.3f} ({confidence*100:.1f}%)")
        else:
            print(f"❌ 無法辨識 (信心度: {confidence:.3f})")

    print("\n" + "=" * 60)
    print("測試完成")
    print("=" * 60)


if __name__ == "__main__":
    test_detector()
