# Expo Games Interactive Platform

Modular AI-powered interactive gaming platform with emotion recognition, gesture detection, and real-time multiplayer capabilities.

## Features

- **Emotion Analysis**: Real-time facial emotion detection using MediaPipe + DeepFace
- **Action Detection**: Interactive pose/action recognition games
- **RPS Gesture Game**: Real-time rock-paper-scissors with MediaPipe hand tracking
- **AI Drawing**: Gesture-controlled virtual painting with shape recognition
- **WebSocket Real-time**: Bidirectional communication for live interactions
- **Docker Deployment**: Single-command containerized deployment with HTTPS

## Tech Stack

- **Backend**: FastAPI, MediaPipe, DeepFace, OpenCV, TensorFlow
- **Frontend**: Vanilla JavaScript, WebSocket API, Canvas API
- **Infrastructure**: Docker, Nginx, SSL/TLS, GPU acceleration
- **AI/ML**: MediaPipe Solutions, DeepFace, TensorFlow Serving

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Camera device (for real-time features)

### Launch
```bash
git clone <repository-url>
cd expo-games
docker compose up -d --build
```

Access: https://localhost:8896 (auto-generates self-signed SSL)

## 📁 專案結構

```
expo-games/
├── backend/                    # FastAPI 後端服務
│   ├── app.py                 # 主應用程式，定義所有 API 路由
│   ├── config/
│   │   └── settings.py        # 環境變數和配置管理
│   ├── models/
│   │   └── gesture_recognizer.task    # MediaPipe 手勢辨識模型
│   ├── services/
│   │   ├── emotion_service.py         # 情緒分析服務
│   │   ├── action_detection_service.py # 動作檢測遊戲服務
│   │   ├── drawing_service.py         # AI 繪畫服務 (WebSocket)
│   │   ├── hand_gesture_service.py    # 手勢識別服務 (MediaPipe)
│   │   ├── mediapipe_rps_detector.py  # MediaPipe 手勢辨識器
│   │   ├── rps_game_service.py        # 猜拳遊戲服務 (MediaPipe 版本)
│   │   └── status_broadcaster.py      # WebSocket 狀態推播
│   └── utils/
│       ├── datetime_utils.py          # 時間工具函數
│       ├── hand_tracking_module.py    # MediaPipe 手勢追蹤模組
│       └── drawing_engine.py          # 繪畫引擎核心
├── frontend/                  # 前端資源
│   ├── templates/
│   │   └── index.html # 主頁面模板
│   └── static/
│       ├── style.css          # 基礎樣式
│       ├── css/
│       │   ├── emotion_action.css     # 頁面專用樣式
│       │   ├── drawing.css            # 手勢繪畫樣式
│       │   └── rps.css           # 猜拳遊戲樣式 + 動畫
│       └── js/
│           ├── emotion_action.js      # 互動邏輯和 WebSocket 通訊
│           └── modules/
│               ├── shared/                # 共享服務（camera / transport / rendering）
│               ├── emotion/               # 情緒分析控制器與展示器
│               ├── gesture/               # 手勢繪畫控制器與展示器
│               ├── emotion-upload.js      # 情緒檔案上傳模組
│               ├── emotion-realtime.js    # 情緒即時分析入口
│               ├── action-upload.js       # 動作檔案上傳模組
│               ├── action-game.js         # 動作遊戲模組
│               ├── rps-game.js            #  猜拳遊戲模組 (MediaPipe + WebSocket)
│               └── modules/drawing/       # 手勢繪畫模組
│       └── assets/rps/                    # 猜拳遊戲素材
│           ├── rock.jpg                   # 石頭圖片
│           ├── paper.jpg                  # 布圖片
│           └── scissors.jpg               # 剪刀圖片
├── nginx/                     # Nginx 反向代理配置
│   ├── nginx.conf            # 主配置文件
│   ├── default.conf.template # 虛擬主機模板（支持環境變數）
│   ├── generate-ssl.sh       # SSL 憑證自動生成腳本
│   ├── substitute-env.sh     # 環境變數替換腳本
│   └── ssl/                  # SSL 憑證存放目錄
├── docs/                     # 文檔
│   ├── architecture-spec.md           # 全域架構規格
│   ├── realtime-modules-architecture.md # 即時模組分層規劃
│   ├── websocket-protocol.md          # WebSocket 協議文檔
│   └── RPS_API.md                     # ⭐ 猜拳遊戲 API 文檔
├── docker-compose.yml        # 容器編排配置
├── Dockerfile               # 應用程式容器建置
├── requirements.txt         # Python 依賴
└── .env                    # 環境變數配置
```

## ⚙️ 環境配置

編輯 `.env` 文件來自定義系統配置：

```env
# FastAPI 應用程式設定
APP_TITLE=Expo Games Interactive
APP_PORT=8896                # 內部 FastAPI 端口

# Nginx 對外端口設定
EXTERNAL_PORT=8896          # 外部訪問端口

# 檔案上傳限制
MAX_FILE_SIZE_MB=50         # 最大上傳文件大小 (MB)

# CORS 設定
CORS_ALLOW_ORIGINS=*        # 允許的跨域來源
```

## 🏗️ 部署架構

### 統一容器部署
- **單一容器**: 所有依賴直接安裝在同一容器中 (簡化部署)
- **PyTorch + CUDA**: 使用 `nvidia/cuda:11.8.0-runtime-ubuntu20.04` 基底映像
- **Python 3.10**: 支援最新的依賴套件
- **GPU 支援**: 自動檢測 CUDA 可用性，回落至 CPU 模式

### 網路結構
```
[用戶] -> [Nginx Proxy:8896] -> [FastAPI App:8896] -> [AI 模型服務]
```

- **Nginx**: SSL/TLS 終端、反向代理、靜態檔案服務
- **FastAPI**: API 端點、WebSocket 連線、業務邏輯
- **AI 模型**: DeepFace、MediaPipe 整合在應用容器中

## 🛠️ 技術架構

### 後端技術棧
- **FastAPI**: 現代高性能 Web 框架
- **MediaPipe**: Google 機器學習管道，用於臉部特徵提取和手勢辨識
- **DeepFace**: 深度學習人臉識別和情緒分析
- **OpenCV**: 計算機視覺庫，處理影像和影片
- **TensorFlow**: 深度學習框架，支援 GPU 加速
- **WebSocket**: 即時雙向通訊
- **Uvicorn**: ASGI 服務器

### 前端技術棧
- **原生 JavaScript**: 無框架依賴的高效互動
- **現代 CSS**: Flexbox/Grid 響應式布局
- **WebSocket API**: 即時狀態更新
- **File API**: 拖放上傳支持

### 基礎設施
- **Nginx**: 反向代理、HTTPS 終止、靜態文件服務
- **Docker**: 容器化部署和隔離
- **SSL/TLS**: 自動憑證生成和 HTTPS 加密

## API Reference

### Emotion Analysis
```http
POST /api/emotion/analyze              # Full analysis (MediaPipe + DeepFace)
POST /api/emotion/analyze/simple       # Simplified DeepFace analysis
POST /api/emotion/analyze/deepface      # DeepFace only
WS   /ws/emotion                       # Real-time emotion detection
```

### Action Detection
```http
POST /api/action/start                 # Start action game
POST /api/action/stop                  # Stop game
GET  /api/action/status                # Get game status
```

### RPS Game (MediaPipe)
```http
WS   /ws/rps                           # Real-time game updates
```

### Gesture Recognition
```http
POST /api/gesture/start                # Start gesture detection
POST /api/gesture/stop                 # Stop detection
GET  /api/gesture/status               # Get detection status
GET  /api/gesture/current              # Get current gesture
```

### AI Drawing
```http
POST /api/drawing/start                # Start drawing session
POST /api/drawing/stop                 # Stop session
GET  /api/drawing/status               # Get drawing status
POST /api/drawing/recognize            # Manual shape recognition
POST /api/drawing/clear                # Clear canvas
WS   /ws/drawing                       # Real-time drawing updates
```

See [`docs/RPS_API.md`](docs/RPS_API.md) and [`docs/websocket-protocol.md`](docs/websocket-protocol.md) for detailed specs.

## Development

### Local Development
```bash
pip install -r requirements.txt
export PYTHONPATH="/path/to/expo-games"
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8896
```

### Testing
```bash
pytest tests/
```

### Docker Development
```bash
docker compose logs -f
docker compose up -d --build
docker compose down
```

## License

See original project license.
