# =============================================================================
# Dockerfile - AI Interactive Games Platform Container
#
# This Dockerfile builds a GPU-enabled container for the AI Interactive Games Platform.
# Uses TensorFlow 2.13.0 GPU base image with MediaPipe and DeepFace for computer vision tasks.
# Application code is mounted via volumes for development flexibility.
#
# Dependencies: TensorFlow 2.13.0-gpu, MediaPipe, DeepFace, FastAPI, uvicorn
# Key Features: GPU acceleration, computer vision, real-time processing
# =============================================================================

# syntax=docker/dockerfile:1

# 使用 TensorFlow 2.13.0 GPU 基礎映像檔，符合 DeepFace 需求
FROM tensorflow/tensorflow:2.13.0-gpu AS runtime

# 設定環境變數以優化 Python 和 TensorFlow 效能
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    CUDA_VISIBLE_DEVICES=0

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 - headless GPU 運算所需的圖形庫和媒體處理工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    ffmpeg \
    libgomp1 \
    libglx0 \
    libegl1 \
    mesa-utils \
    libgl1-mesa-dev \
    libegl1-mesa-dev \
    && rm -rf /var/lib/apt/lists/*

# 複製 Python 依賴檔案並安裝
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# 暴露應用程式端口
EXPOSE 8896

# 啟動 FastAPI 應用程式
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8896"]
