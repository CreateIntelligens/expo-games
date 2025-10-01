# =============================================================================
# gpu_runtime.py - GPU 執行環境配置輔助模組
# =============================================================================
# 集中管理所有 GPU 相關的環境設定，使程式碼的其他部分可以依賴單一位置
# 來切換 GPU / CPU 行為。透過 lru_cache 保持邏輯的冪等性，確保從多個
# 模組匯入時不會重複執行繁重的初始化工作。
# =============================================================================

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List

logger = logging.getLogger("gpu_runtime")

@dataclass
class GpuStatus:
    """
    GPU 狀態快照資料類別
    
    記錄 GPU 可用性資訊的執行時快照
    
    Attributes:
        tensorflow_ready (bool): TensorFlow GPU 是否就緒
        tensorflow_devices (List[str]): TensorFlow 偵測到的 GPU 裝置列表
        mediapipe_gpu_enabled (bool): MediaPipe GPU 是否啟用
        warnings (List[str]): 初始化過程中的警告訊息列表
    """

    tensorflow_ready: bool
    tensorflow_devices: List[str] = field(default_factory=list)
    mediapipe_gpu_enabled: bool = False
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """
        轉換為字典格式
        
        Returns:
            dict: 包含所有狀態資訊的字典
        """
        return {
            "tensorflow_ready": self.tensorflow_ready,
            "tensorflow_devices": self.tensorflow_devices,
            "mediapipe_gpu_enabled": self.mediapipe_gpu_enabled,
            "warnings": self.warnings,
        }

# GPU 環境變數配置
# 這些環境變數控制 TensorFlow 和 CUDA 的行為
GPU_ENV_VARS = {
    "TF_CPP_MIN_LOG_LEVEL": "2",  # 減少 TensorFlow 日誌輸出
    "TF_FORCE_GPU_ALLOW_GROWTH": "true",  # 啟用 GPU 記憶體動態增長
    "TF_ENABLE_ONEDNN_OPTS": "0",  # 提高 GPU 執行時的確定性
    "TF_DISABLE_SEGMENT_REDUCTION": "1",  # 禁用段落縮減優化
    "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0"),  # 指定可見的 CUDA 裝置
    "MEDIAPIPE_DISABLE_GPU": "0",  # 啟用 MediaPipe GPU 加速
    # 加強 GPU 記憶體控制
    "TF_GPU_ALLOCATOR": "cuda_malloc_async",  # 使用非同步 CUDA 記憶體分配器
    "TF_GPU_THREAD_MODE": "gpu_private",  # GPU 私有執行緒模式
    "CUDA_CACHE_DISABLE": "1",  # 禁用 CUDA 快取以減少記憶體使用
    "TF_CUDNN_USE_AUTOTUNE": "0",  # 禁用 cuDNN 自動調優以減少記憶體
}

@lru_cache(maxsize=1)
def configure_gpu_runtime() -> GpuStatus:
    """
    配置 GPU 執行環境
    
    確保 GPU 環境變數已設定，並配置 TensorFlow 的記憶體增長策略。
    使用 lru_cache 確保此函數只執行一次，避免重複的繁重初始化。
    
    Returns:
        GpuStatus: GPU 狀態物件，包含 TensorFlow 和 MediaPipe 的 GPU 配置資訊
        
    Note:
        - 此函數會自動偵測可用的 GPU 裝置
        - 為每個 GPU 設定 4GB 記憶體限制
        - 啟用記憶體動態增長以優化記憶體使用
        - 所有配置錯誤都會被記錄為警告，不會中斷程式執行
    """
    # 設定所有 GPU 相關環境變數
    for key, value in GPU_ENV_VARS.items():
        current = os.environ.get(key)
        if current != value:
            os.environ[key] = value

    # 初始化狀態變數
    tensorflow_devices: List[str] = []
    warnings: List[str] = []
    tensorflow_ready = False

    try:
        # 延遲匯入 TensorFlow，因為它很大但會被 lru_cache 快取
        import tensorflow as tf

        # 偵測可用的 GPU 裝置
        gpus = tf.config.list_physical_devices("GPU")
        tensorflow_devices = [gpu.name for gpu in gpus]
        tensorflow_ready = bool(gpus)

        if gpus:
            # 先設定記憶體限制，再啟用記憶體增長
            for gpu in gpus:
                try:
                    # 設定 GPU 記憶體限制為 4GB
                    # 這可以防止單一程序佔用所有 GPU 記憶體
                    tf.config.set_logical_device_configuration(
                        gpu,
                        [tf.config.LogicalDeviceConfiguration(memory_limit=4096)]
                    )
                    logger.info(f"已為 {gpu.name} 設定 4GB 記憶體限制")
                except Exception as exc:
                    warnings.append(f"無法為 {gpu.name} 設定記憶體限制: {exc}")
            
            # 記錄偵測到的邏輯 GPU 裝置
            logical_gpus = tf.config.list_logical_devices("GPU")
            logger.info("TensorFlow 偵測到的 GPU: %s", [dev.name for dev in logical_gpus])
        else:
            warnings.append("TensorFlow 未偵測到任何 GPU 裝置；將使用 CPU 模式")
    except Exception as exc:  # pragma: no cover - 缺少 TensorFlow GPU 支援
        warnings.append(f"TensorFlow GPU 初始化失敗: {exc}")
        tensorflow_ready = False

    # 檢查 MediaPipe GPU 是否啟用
    mediapipe_gpu_enabled = os.environ.get("MEDIAPIPE_DISABLE_GPU") == "0"
    if not mediapipe_gpu_enabled:
        warnings.append("MediaPipe GPU 路徑已透過 MEDIAPIPE_DISABLE_GPU != 0 禁用")

    # 建立狀態物件
    status = GpuStatus(
        tensorflow_ready=tensorflow_ready,
        tensorflow_devices=tensorflow_devices,
        mediapipe_gpu_enabled=mediapipe_gpu_enabled,
        warnings=warnings,
    )

    # 記錄所有警告訊息
    if warnings:
        for message in warnings:
            logger.warning(message)

    return status

def get_gpu_status_dict() -> dict:
    """
    取得 GPU 狀態字典
    
    提供便利的輔助函數用於 API 回應
    
    Returns:
        dict: GPU 狀態資訊的字典格式
        
    Example:
        >>> status = get_gpu_status_dict()
        >>> print(status['tensorflow_ready'])
        True
    """
    return configure_gpu_runtime().as_dict()
