# =============================================================================
# tests/test_mediapipe_detailed.py - MediaPipe RPS Detector Detailed Test Script
#
# Detailed test script for MediaPipe-based Rock-Paper-Scissors gesture recognition.
# Provides comprehensive testing with raw MediaPipe results and detailed logging.
#
# Dependencies: mediapipe, opencv-python, numpy
# Key Features: Detailed testing, raw result inspection, comprehensive validation
# =============================================================================

#!/usr/bin/env python3
"""
測試 MediaPipe RPS 辨識器（詳細版）
顯示所有偵測到的手勢
"""

import sys
from pathlib import Path
import logging

# 設定詳細日誌
logging.basicConfig(level=logging.INFO)

# 加入專案路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.services.mediapipe_rps_detector import MediaPipeRPSDetector, RPSGesture


def test_image_detail(detector, img_path):
    """詳細測試單張圖片"""
    print(f"\n{'='*60}")
    print(f"📷 測試圖片: {img_path}")
    print('='*60)

    full_path = project_root / img_path
    if not full_path.exists():
        print(f"❌ 圖片不存在")
        return

    # 使用 MediaPipe 直接辨識以查看原始結果
    import cv2
    import mediapipe as mp

    img_bgr = cv2.imread(str(full_path))
    if img_bgr is None:
        print(f"❌ 無法讀取圖片")
        return

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)

    # 辨識
    result = detector.recognizer.recognize(mp_image)

    print(f"圖片大小: {img_bgr.shape}")
    print(f"偵測到手部: {len(result.hand_landmarks) if result.hand_landmarks else 0}")
    print(f"偵測到手勢: {len(result.gestures) if result.gestures else 0}")

    if result.gestures and len(result.gestures) > 0:
        print(f"\n所有手勢 (共 {len(result.gestures[0])} 個):")
        for i, gesture in enumerate(result.gestures[0][:5]):
            print(f"  {i+1}. {gesture.category_name} - 信心度: {gesture.score:.3f}")

    # 使用辨識器
    gesture, confidence = detector.detect(str(full_path))
    print(f"\n最終辨識結果: {gesture.value} (信心度: {confidence:.3f})")


def main():
    """主函數"""
    print("=" * 60)
    print("MediaPipe RPS 辨識器詳細測試")
    print("=" * 60)

    # 建立辨識器
    detector = MediaPipeRPSDetector()

    if not detector.is_available():
        print(f"錯誤: {detector.init_error}")
        return

    # 測試圖片
    test_images = [
        "test_assets/imagetest1.png",
        "test_assets/imagetest2.png",
        "test_assets/石頭.jpg",
        "test_assets/布.jpg",
        "test_assets/剪刀.jpg",
    ]

    for img_path in test_images:
        test_image_detail(detector, img_path)

    print(f"\n{'='*60}")
    print("測試完成")
    print('='*60)


if __name__ == "__main__":
    main()
