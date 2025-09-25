# Expo Games Interactive Platform

面向展場或互動體驗中心的模組化 AI 遊戲平台，結合情緒辨識、動作偵測、手勢對戰與創意畫畫等功能。系統目標是以單一部署套件提供後端 API、WebSocket 即時互動、前端控制台與 Nginx HTTPS 入口，便於快速布署於現場設備或雲端。

## 🎮 主要功能

### 情緒分析模組 (Emotion Studio)
- **多模態分析**：支援圖片、影片、即時攝影機輸入
- **雙引擎支援**：MediaPipe (468點臉部網格) + DeepFace (深度學習特徵)
- **即時檢測**：WebSocket 推播情緒狀態變化
- **詳細報告**：情緒分布、信心度、特徵分析、趨勢統計

### 動作檢測遊戲 (Action Arena)
- **互動挑戰**：微笑、轉頭、挑眉、眨眼等動作識別
- **三種難度**：簡單(3個動作)、中等(5個動作)、困難(7個動作)
- **即時回饋**：進度條顯示、動作完成提示
- **遊戲化體驗**：計分系統、完成統計

### 石頭剪刀布對戰 (RPS Duel Stage)
- **手勢識別**：使用 MediaPipe Hands 精準識別石頭✊、剪刀✌️、布✋手勢
- **AI 對戰**：三種難度的 AI 對手（簡單隨機、中等記憶、困難策略）
- **即時對戰**：手勢捕捉倒數、同時出招、即時判定勝負
- **戰績統計**：回合記錄、勝負統計、策略分析

### AI 繪畫識別 (Sketch Lab)
- **虛擬繪畫**：用手指在空中繪畫，生成虛擬畫布
- **AI 識別**：智慧識別繪畫內容（圓形、方形、三角形、心形等）
- **多種模式**：食指繪畫、手勢控制（雙指擦除、五指清空）
- **即時反饋**：自動識別、建議提示、信心度評估

### 系統架構特色
- **容器化部署**：Docker + docker-compose 一鍵啟動
- **HTTPS 支持**：Nginx 反向代理 + 自動 SSL 憑證生成
- **響應式設計**：支援桌面和移動設備
- **WebSocket 通訊**：即時狀態推播和互動更新

## 🚀 快速開始

### 環境需求
- Docker 和 Docker Compose
- 攝影機設備（用於即時檢測功能）

### 啟動系統

```bash
# 克隆專案
git clone <repository-url>
cd expo-games

# 啟動所有服務（自動建置 + 背景運行）
docker compose up -d --build
```

### 訪問應用
- **主應用**: https://localhost:8896
- **健康檢查**: https://localhost:8896/health

系統啟動後，Nginx 會自動生成自簽 SSL 憑證，並提供 HTTPS 訪問。

## 📁 專案結構

```
expo-games/
├── backend/                    # FastAPI 後端服務
│   ├── app.py                 # 主應用程式，定義所有 API 路由
│   ├── config/
│   │   └── settings.py        # 環境變數和配置管理
│   ├── services/
│   │   ├── emotion_service.py         # 情緒分析服務
│   │   ├── action_detection_service.py # 動作檢測遊戲服務
│   │   └── status_broadcaster.py      # WebSocket 狀態推播
│   └── utils/
│       └── datetime_utils.py  # 時間工具函數
├── frontend/                  # 前端資源
│   ├── templates/
│   │   └── emotion_action.html # 主頁面模板
│   └── static/
│       ├── style.css          # 基礎樣式
│       ├── css/
│       │   └── emotion_action.css # 頁面專用樣式
│       └── js/
│           └── emotion_action.js  # 互動邏輯和 WebSocket 通訊
├── nginx/                     # Nginx 反向代理配置
│   ├── nginx.conf            # 主配置文件
│   ├── default.conf.template # 虛擬主機模板（支持環境變數）
│   ├── generate-ssl.sh       # SSL 憑證自動生成腳本
│   ├── substitute-env.sh     # 環境變數替換腳本
│   └── ssl/                  # SSL 憑證存放目錄
├── docs/                     # 文檔
│   └── architecture_overview.md # 系統架構說明
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
- **MediaPipe**: Google 機器學習管道，用於臉部特徵提取
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

## 📊 API 參考

### 情緒分析 API

```http
POST /api/emotion/start                # 啟動即時情緒檢測
POST /api/emotion/stop                 # 停止情緒檢測
GET  /api/emotion/status               # 獲取檢測狀態
POST /api/emotion/analyze              # 完整分析上傳的圖片/影片
POST /api/emotion/analyze/simple       # DeepFace 簡化分析 (推薦使用)
POST /api/emotion/analyze/deepface      # DeepFace 完整分析

# 簡化 API 回傳格式範例
{
  "emotion_zh": "開心",
  "emotion_en": "happy",
  "emoji": "😊",
  "confidence": 0.85
}
```

### 動作檢測 API

```http
POST /api/action/start      # 開始動作檢測遊戲
POST /api/action/stop       # 停止遊戲
GET  /api/action/status     # 獲取遊戲狀態
```

### 石頭剪刀布 API

```http
POST /api/rps/start         # 開始石頭剪刀布遊戲
POST /api/rps/stop          # 停止遊戲
GET  /api/rps/status        # 獲取遊戲狀態
```

### 手勢識別 API

```http
POST /api/gesture/start     # 啟動手勢檢測
POST /api/gesture/stop      # 停止手勢檢測
GET  /api/gesture/status    # 獲取檢測狀態
GET  /api/gesture/current   # 獲取當前手勢
```

### AI 繪畫 API

```http
POST /api/drawing/start     # 開始繪畫會話
POST /api/drawing/stop      # 停止繪畫會話
GET  /api/drawing/status    # 獲取繪畫狀態
POST /api/drawing/recognize # 手動識別繪畫
POST /api/drawing/clear     # 清空畫布
```

### WebSocket 端點

```
WS /ws/emotion              # 情緒檢測即時更新
WS /ws/action               # 動作遊戲即時更新
WS /ws/rps                  # 石頭剪刀布遊戲即時更新
WS /ws/gesture              # 手勢識別即時更新
WS /ws/drawing              # AI 繪畫即時更新
```

## 🔧 開發指南

### 本地開發

```bash
# 安裝 Python 依賴
pip install -r requirements.txt

# 設定環境變數
export PYTHONPATH="/path/to/expo-games"

# 啟動 FastAPI 開發服務器
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8896
```

### 運行測試

```bash
# 運行所有測試
pytest tests/

# 運行特定服務測試
pytest tests/test_status_broadcaster.py
pytest tests/test_emotion_service.py
pytest tests/test_action_detection_service.py
pytest tests/test_hand_gesture_service.py
pytest tests/test_rps_game_service.py
pytest tests/test_drawing_service.py
```

### Docker 開發

```bash
# 驗證配置
docker compose config

# 查看日誌
docker compose logs -f

# 重新建置
docker compose up -d --build

# 停止所有服務
docker compose down
```

## 🎯 展場部署建議

1. **硬體要求**
   - CPU: 4核心以上（MediaPipe 計算密集）
   - RAM: 4GB 以上
   - 攝影機: USB 網路攝影機
   - 網路: 支援 HTTPS 的穩定連線

2. **生產環境配置**
   - 替換 `nginx/ssl/` 中的自簽憑證為正式 SSL 憑證
   - 調整 `CORS_ALLOW_ORIGINS` 限制跨域訪問
   - 設定防火牆只開放必要端口

3. **監控和維護**
   - 查看容器狀態: `docker compose ps`
   - 監控系統資源使用情況
   - 定期備份配置和日誌

## 🔮 擴展規劃

- **多人對戰**: 雙人石頭剪刀布、團隊競賽模式
- **更多 AI 識別**: 文字識別、物體檢測、創意畫作分析
- **數據持久化**: 遊戲統計分析和歷史記錄
- **多語言支持**: 國際化展場適配
- **CI/CD 流程**: 自動化測試和部署
- **性能優化**: GPU 加速、快取機制、模型優化

## 📚 參考資源

### AI 技術實現參考
- **手勢繪畫**: https://steam.oxxostudio.tw/category/python/ai/ai-mediapipe-finger-draw.html
- **虛擬畫家**: https://github.com/MohamedAlaouiMhamdi/AI_virtual_Painter
- **石頭剪刀布**: https://steam.oxxostudio.tw/category/python/ai/ai-rock-paper-scissors.html
- **手勢遊戲**: https://github.com/ChetanNair/Rock-Paper-Scissors
- **微笑照片**: https://steam.oxxostudio.tw/category/python/ai/ai-smile-photo.html
- **DeepFace**: https://github.com/serengil/deepface
- **姿勢估計**: https://steam.oxxostudio.tw/category/python/ai/ai-mediapipe-pose.html
- **MediaPipe**: https://github.com/google/mediapipe

## 📄 授權

此專案採用與原始專案相同的授權條款。

---

🎮 **Expo Games Interactive Platform** - 讓每一場展覽都成為難忘的互動體驗！
