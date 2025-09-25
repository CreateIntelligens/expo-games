# syntax=docker/dockerfile:1
FROM tensorflow/tensorflow:2.13.0-gpu AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    TF_FORCE_GPU_ALLOW_GROWTH=true \
    CUDA_VISIBLE_DEVICES=0 \
    MEDIAPIPE_DISABLE_GPU=0

WORKDIR /app

# 系統依賴
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

# 安裝 Python 依賴
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

EXPOSE 8896

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8896"]
