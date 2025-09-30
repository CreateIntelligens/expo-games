"""GPU runtime configuration helpers.

This module centralises all GPU related environment setup so the rest of the
codebase can rely on a single place to toggle GPU / CPU behaviour. It keeps the
logic idempotent via lru_cache so importing it from multiple modules will not
repeat heavy initialisation.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List


logger = logging.getLogger("gpu_runtime")


@dataclass
class GpuStatus:
    """Runtime snapshot that records GPU availability information."""

    tensorflow_ready: bool
    tensorflow_devices: List[str] = field(default_factory=list)
    mediapipe_gpu_enabled: bool = False
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "tensorflow_ready": self.tensorflow_ready,
            "tensorflow_devices": self.tensorflow_devices,
            "mediapipe_gpu_enabled": self.mediapipe_gpu_enabled,
            "warnings": self.warnings,
        }


GPU_ENV_VARS = {
    "TF_CPP_MIN_LOG_LEVEL": "2",
    "TF_FORCE_GPU_ALLOW_GROWTH": "true",
    "TF_ENABLE_ONEDNN_OPTS": "0",  # Better determinism on GPU runtime
    "TF_DISABLE_SEGMENT_REDUCTION": "1",
    "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0"),
    "MEDIAPIPE_DISABLE_GPU": "0",
    # 加強 GPU 記憶體控制
    "TF_GPU_ALLOCATOR": "cuda_malloc_async",
    "TF_GPU_THREAD_MODE": "gpu_private",
    "CUDA_CACHE_DISABLE": "1",  # 禁用 CUDA 快取以減少記憶體使用
    "TF_CUDNN_USE_AUTOTUNE": "0",  # 禁用 cuDNN 自動調優以減少記憶體
}


@lru_cache(maxsize=1)
def configure_gpu_runtime() -> GpuStatus:
    """Ensure GPU env vars are set and TensorFlow growth is configured."""

    for key, value in GPU_ENV_VARS.items():
        current = os.environ.get(key)
        if current != value:
            os.environ[key] = value

    tensorflow_devices: List[str] = []
    warnings: List[str] = []
    tensorflow_ready = False

    try:
        import tensorflow as tf  # Lazy import; heavy but cached thanks to lru_cache

        gpus = tf.config.list_physical_devices("GPU")
        tensorflow_devices = [gpu.name for gpu in gpus]
        tensorflow_ready = bool(gpus)

        if gpus:
            # 先設定記憶體限制，再啟用記憶體增長
            for gpu in gpus:
                try:
                    # 設定 GPU 記憶體限制為 4GB
                    tf.config.set_logical_device_configuration(
                        gpu,
                        [tf.config.LogicalDeviceConfiguration(memory_limit=4096)]
                    )
                    logger.info(f"Set GPU memory limit to 4GB for {gpu.name}")
                except Exception as exc:
                    warnings.append(f"Failed to set memory limit for {gpu.name}: {exc}")

            for gpu in gpus:
                try:
                    tf.config.experimental.set_memory_growth(gpu, True)
                except Exception as exc:  # pragma: no cover - depends on driver state
                    warnings.append(f"Failed to enable memory growth for {gpu.name}: {exc}")
            logical_gpus = tf.config.list_logical_devices("GPU")
            logger.info("TensorFlow GPUs detected: %s", [dev.name for dev in logical_gpus])
        else:
            warnings.append("TensorFlow did not detect any GPU devices; CPU fallback active.")
    except Exception as exc:  # pragma: no cover - absence of TensorFlow GPU support
        warnings.append(f"TensorFlow GPU initialisation failed: {exc}")
        tensorflow_ready = False

    mediapipe_gpu_enabled = os.environ.get("MEDIAPIPE_DISABLE_GPU") == "0"
    if not mediapipe_gpu_enabled:
        warnings.append("MediaPipe GPU path disabled via MEDIAPIPE_DISABLE_GPU != 0")

    status = GpuStatus(
        tensorflow_ready=tensorflow_ready,
        tensorflow_devices=tensorflow_devices,
        mediapipe_gpu_enabled=mediapipe_gpu_enabled,
        warnings=warnings,
    )

    if warnings:
        for message in warnings:
            logger.warning(message)

    return status


def get_gpu_status_dict() -> dict:
    """Convenience helper for API responses."""

    return configure_gpu_runtime().as_dict()
