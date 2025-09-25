/**
 * =============================================================================
 * EmotionRealtimeModule - 即時情緒檢測模組
 *
 * 負責處理即時攝影機串流和WebSocket通訊的模組，
 * 提供情緒分析功能，包含攝影機管理、影像串流和結果顯示。
 *
 * 主要功能：
 * - 攝影機權限請求和串流管理
 * - WebSocket連接和心跳機制
 * - 即時影像幀捕獲和分析
 * - 情緒檢測結果顯示
 * - 自動重連和錯誤處理
 * =============================================================================
 */

import { STREAM_CONFIG, STATUS_TYPES } from '../common/constants.js';
import { ButtonToggler } from '../common/ui-helpers.js';

/**
 * 即時情緒檢測模組類別
 * @class EmotionRealtimeModule
 */
export class EmotionRealtimeModule {
    /**
     * 建構函式
     * @param {StatusManager} statusManager - 狀態管理器實例
     */
    constructor(statusManager) {
        // 核心狀態
        this.statusManager = statusManager;
        this.isDetecting = false;      // 分析狀態
        this.isCameraActive = false;   // 攝影機狀態

        // WebSocket 和媒體資源
        this.localVideoStream = null;  // 攝影機串流
        this.videoElement = null;      // 顯示元素
        this.captureCanvas = null;     // 影像捕獲畫布
        this.captureContext = null;    // 畫布上下文
        this.analysisInterval = null;  // 分析間隔計時器
        this.streamWebSocket = null;   // WebSocket連接

        // DOM 元素引用
        this.elements = this._initializeElements();

        // UI 控制器
        this.startButtonToggler = new ButtonToggler(this.elements.startBtn);
        this.stopButtonToggler = new ButtonToggler(this.elements.stopBtn);

        // 心跳機制
        this.heartbeatInterval = null;
        this.lastHeartbeat = Date.now();

        this.init();
    }

    /**
     * 初始化 DOM 元素引用
     * @private
     * @returns {Object} DOM 元素映射物件
     */
    _initializeElements() {
        return {
            startBtn: document.getElementById('start-emotion-btn'),
            stopBtn: document.getElementById('stop-emotion-btn'),
            durationInput: document.getElementById('emotion-duration'),
            preview: document.getElementById('emotion-preview'),
            durationLabel: document.getElementById('detection-duration'),
            countLabel: document.getElementById('detection-count'),
            emotionIcon: document.getElementById('emotion-icon'),
            emotionName: document.getElementById('emotion-name')
        };
    }

    /**
     * 初始化模組
     * @private
     */
    init() {
        this.setupEventListeners();
        this.setButtonsState(false);
    }

    /**
     * 設置事件監聽器
     * @private
     */
    setupEventListeners() {
        this.elements.startBtn?.addEventListener('click', () => this.startDetection());
        this.elements.stopBtn?.addEventListener('click', () => this.stopDetection());
    }

    /**
     * 開始情緒檢測流程
     * @async
     * @public
     * @description 啟動完整的即時情緒檢測流程，包含攝影機權限請求、WebSocket連接和分析開始
     */
    async startDetection() {
        if (this.isDetecting) {
            this.statusManager.update('情緒檢測已在進行中', STATUS_TYPES.WARNING);
            return;
        }

        console.log('🚀 開始情緒檢測流程');

        try {
            // 啟動攝影機串流
            if (!this.isCameraActive) {
                await this._initializeCamera();
            }

            // 建立WebSocket連接
            this.statusManager.update('正在連接分析服務...', STATUS_TYPES.PROCESSING);
            this.setupStreamWebSocket();

            // 更新狀態
            this.isDetecting = true;
            this.setButtonsState(true);
            this.statusManager.update('開始情緒分析...', STATUS_TYPES.SUCCESS);
            console.log('🎯 情緒檢測狀態設置為啟動');

            // 等待video元素載入完成後開始分析
            this.videoElement.addEventListener('loadeddata', () => {
                console.log('🎬 Video元素載入完成，開始WebSocket分析');
                this.startWebSocketAnalysis(this.videoElement);
            });

            this.videoElement.addEventListener('error', (e) => {
                console.error('❌ Video元素載入錯誤:', e);
            });

        } catch (error) {
            this.statusManager.update(`啟動情緒檢測錯誤：${error.message}`, STATUS_TYPES.ERROR);
            this.handleCameraError(error);
        }
    }

    /**
     * 初始化攝影機串流
     * @private
     * @async
     * @description 請求攝影機權限、創建視訊元素和畫布
     */
    async _initializeCamera() {
        this.statusManager.update('正在啟動本地攝影機...', STATUS_TYPES.PROCESSING);
        console.log('📹 請求攝影機權限...');

        // 檢查瀏覽器支援
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('瀏覽器不支持攝影機訪問');
        }

        // 請求攝影機權限
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: STREAM_CONFIG.VIDEO_WIDTH,
                height: STREAM_CONFIG.VIDEO_HEIGHT,
                facingMode: 'user'
            }
        });

        console.log('✅ 攝影機權限獲取成功', stream);
        this.localVideoStream = stream;
        this.isCameraActive = true;

        // 創建視訊顯示元素
        this._createVideoElement();

        // 創建影像捕獲畫布
        this._createCaptureCanvas();

        // 顯示預覽
        this.showPreview();
        this.statusManager.update('本地攝影機已啟動', STATUS_TYPES.SUCCESS);
    }

    /**
     * 創建視訊顯示元素
     * @private
     */
    _createVideoElement() {
        this.videoElement = document.createElement('video');
        this.videoElement.srcObject = this.localVideoStream;
        this.videoElement.autoplay = true;
        this.videoElement.muted = true;
        this.videoElement.playsInline = true; // 防止iOS全螢幕播放
        this.videoElement.style.width = '100%';
        this.videoElement.style.maxWidth = '640px';
        this.videoElement.style.height = 'auto';
        this.videoElement.style.borderRadius = '8px';
        this.videoElement.style.objectFit = 'contain';

        // 添加到預覽區域
        if (this.elements.preview) {
            this.elements.preview.innerHTML = '';
            this.elements.preview.appendChild(this.videoElement);
            console.log('📺 Video元素已添加到預覽區域');
        } else {
            console.error('❌ 找不到預覽區域元素');
        }
    }

    /**
     * 創建影像捕獲畫布
     * @private
     */
    _createCaptureCanvas() {
        this.captureCanvas = document.createElement('canvas');
        this.captureCanvas.width = STREAM_CONFIG.VIDEO_WIDTH;
        this.captureCanvas.height = STREAM_CONFIG.VIDEO_HEIGHT;
        this.captureContext = this.captureCanvas.getContext('2d');
    }

    /**
     * 處理攝影機錯誤
     * @private
     * @param {Error} error - 攝影機錯誤物件
     * @description 根據錯誤類型提供用戶友好的錯誤訊息
     */
    handleCameraError(error) {
        let errorMessage = '攝影機啟動失敗：';

        if (error.name === 'NotAllowedError') {
            errorMessage += '用戶拒絕了攝影機權限';
        } else if (error.name === 'NotFoundError') {
            errorMessage += '未找到攝影機設備';
        } else if (error.name === 'NotReadableError') {
            errorMessage += '攝影機被其他應用程式佔用';
        } else {
            errorMessage += error.message;
        }

        this.statusManager.update(errorMessage, STATUS_TYPES.ERROR);
    }

    /**
     * 設置WebSocket連接
     * @private
     * @description 建立WebSocket連接並設置事件處理器，包含心跳機制和自動重連
     */
    setupStreamWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/emotion/stream`;
        console.log('嘗試連接WebSocket:', wsUrl);

        this.streamWebSocket = new WebSocket(wsUrl);

        // 初始化心跳機制
        this.heartbeatInterval = null;
        this.lastHeartbeat = Date.now();

        this.streamWebSocket.onopen = () => {
            console.log('✅ 影像串流WebSocket連接已建立');
            this.statusManager.update('WebSocket連接成功', STATUS_TYPES.SUCCESS);
            this.startHeartbeat();
        };

        this.streamWebSocket.onmessage = (event) => {
            this.lastHeartbeat = Date.now();

            // 處理心跳響應
            if (event.data === 'pong') {
                console.log('💓 收到心跳響應');
                return;
            }

            console.log('📨 收到WebSocket訊息:', event.data);
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketResult(data);
            } catch (error) {
                console.error('❌ 解析WebSocket訊息失敗:', error, '原始數據:', event.data);
            }
        };

        this.streamWebSocket.onerror = (error) => {
            console.error('❌ 影像串流WebSocket錯誤:', error);
            this.statusManager.update('WebSocket連接錯誤', STATUS_TYPES.ERROR);
            this.stopHeartbeat();
        };

        this.streamWebSocket.onclose = (event) => {
            console.log('🔌 影像串流WebSocket連接已關閉, 代碼:', event.code, '原因:', event.reason);
            this.stopHeartbeat();

            // 異常關閉時自動重連
            if (event.code !== 1000 && this.isDetecting) {
                console.log('🔄 嘗試重連WebSocket...');
                setTimeout(() => {
                    if (this.isDetecting) {
                        this.setupStreamWebSocket();
                    }
                }, 3000);
            }
        };
    }

    /**
     * 開始心跳機制
     * @private
     * @description 啟動WebSocket心跳機制，每5秒發送ping訊息，10秒超時
     */
    startHeartbeat() {
        this.stopHeartbeat(); // 確保之前的心跳已停止

        this.heartbeatInterval = setInterval(() => {
            if (this.streamWebSocket && this.streamWebSocket.readyState === WebSocket.OPEN) {
                // 檢查最後心跳時間，如果超過10秒沒有響應，認為連接斷開
                if (Date.now() - this.lastHeartbeat > 10000) {
                    console.log('💔 心跳超時，重新連接WebSocket');
                    this.streamWebSocket.close();
                    return;
                }

                // 發送心跳
                this.streamWebSocket.send(JSON.stringify({ type: 'ping' }));
                console.log('💓 發送心跳');
            }
        }, 5000); // 每5秒發送一次心跳
    }

    /**
     * 停止心跳機制
     * @private
     */
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    /**
     * 開始WebSocket影像分析
     * @private
     * @param {HTMLVideoElement} videoElement - 視訊元素
     * @description 定期捕獲影像幀並通過WebSocket發送到服務器進行分析
     */
    startWebSocketAnalysis(videoElement) {
        if (this.analysisInterval) {
            clearInterval(this.analysisInterval);
        }

        console.log(`⏰ 開始WebSocket分析，間隔: ${STREAM_CONFIG.ANALYSIS_INTERVAL}ms`);

        // 按照配置間隔分析
        this.analysisInterval = setInterval(() => {
            if (!this.isDetecting || !this.streamWebSocket || this.streamWebSocket.readyState !== WebSocket.OPEN) {
                console.log('⏸️ 分析間隔跳過 - 檢測未啟動或WebSocket未連接');
                return;
            }

            // 截取當前影像幀
            this.captureContext.drawImage(videoElement, 0, 0, STREAM_CONFIG.VIDEO_WIDTH, STREAM_CONFIG.VIDEO_HEIGHT);
            const imageData = this.captureCanvas.toDataURL('image/jpeg', STREAM_CONFIG.JPEG_QUALITY);

            // 發送影像幀到WebSocket
            const message = {
                type: 'frame',
                image: imageData,
                timestamp: Date.now() / 1000
            };

            console.log('📤 發送影像幀到WebSocket');
            this.streamWebSocket.send(JSON.stringify(message));
        }, STREAM_CONFIG.ANALYSIS_INTERVAL);
    }

    /**
     * 處理WebSocket結果
     * @private
     * @param {Object} data - WebSocket訊息數據
     * @description 處理從服務器收到的分析結果或錯誤訊息
     */
    handleWebSocketResult(data) {
        if (data.type === 'error') {
            console.error('情緒分析錯誤:', data.message);
            return;
        }

        if (data.type === 'result') {
            this.updateRealtimeDisplay(data);
        }
    }

    /**
     * 更新即時顯示結果
     * @private
     * @param {Object} result - 分析結果數據
     * @description 更新UI顯示情緒分析結果、信心度和統計資訊
     */
    updateRealtimeDisplay(result) {
        // 更新情緒圖標和名稱
        if (this.elements.emotionIcon) {
            this.elements.emotionIcon.textContent = result.emoji || '🎭';
        }

        if (this.elements.emotionName) {
            this.elements.emotionName.textContent = result.emotion_zh || '分析中';
        }

        // 更新信心度
        const confidenceEl = document.getElementById('emotion-confidence');
        if (confidenceEl) {
            const confidence = Math.round((result.confidence || 0) * 100);
            confidenceEl.textContent = `${confidence}%`;
        }

        // 更新檢測統計
        if (this.elements.countLabel) {
            const currentCount = parseInt(this.elements.countLabel.textContent) || 0;
            this.elements.countLabel.textContent = (currentCount + 1).toString();
        }

        // 更新檢測時間
        this.updateDetectionDuration();
    }

    /**
     * 更新檢測持續時間
     * @private
     * @description 計算並顯示從檢測開始到現在的持續時間
     */
    updateDetectionDuration() {
        if (!this.elements.durationLabel || !this.detectionStartTime) return;

        const elapsed = Math.floor((Date.now() - this.detectionStartTime) / 1000);
        const minutes = Math.floor(elapsed / 60);
        const seconds = elapsed % 60;
        this.elements.durationLabel.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }

    /**
     * 停止情緒檢測
     * @async
     * @public
     * @description 停止WebSocket分析和心跳機制，但保持攝影機運行
     */
    async stopDetection() {
        if (!this.isDetecting) return;

        // 清理WebSocket影像串流分析的資源
        if (this.analysisInterval) {
            clearInterval(this.analysisInterval);
            this.analysisInterval = null;
        }

        // 停止心跳機制
        this.stopHeartbeat();

        if (this.streamWebSocket) {
            this.streamWebSocket.close();
            this.streamWebSocket = null;
        }

        this.isDetecting = false;
        this.setButtonsState(false);
        this.resetStats();
        this.statusManager.update('情緒分析已停止，攝影機保持運行', STATUS_TYPES.INFO);
        console.log('🛑 情緒分析已停止，攝影機繼續運行');
    }

    /**
     * 完全停止攝影機
     * @async
     * @public
     * @description 停止攝影機串流並清理所有相關資源
     */
    async stopCamera() {
        console.log('📷 正在關閉攝影機...');

        // 停止分析如果正在進行
        if (this.isDetecting) {
            await this.stopDetection();
        }

        // 停止攝影機串流
        if (this.localVideoStream) {
            this.localVideoStream.getTracks().forEach(track => track.stop());
            this.localVideoStream = null;
        }

        // 清理video元素
        if (this.videoElement) {
            this.videoElement.srcObject = null;
            this.videoElement = null;
        }

        this.isCameraActive = false;
        this.hidePreview();
        this.statusManager.update('攝影機已關閉', STATUS_TYPES.INFO);
        console.log('✅ 攝影機已完全關閉');
    }

    /**
     * 設置按鈕狀態
     * @private
     * @param {boolean} isDetecting - 是否正在檢測
     * @description 根據檢測狀態啟用/禁用按鈕並記錄開始時間
     */
    setButtonsState(isDetecting) {
        if (this.elements.startBtn) {
            this.elements.startBtn.disabled = isDetecting;
        }
        if (this.elements.stopBtn) {
            this.elements.stopBtn.disabled = !isDetecting;
        }

        // 記錄開始時間
        if (isDetecting && !this.detectionStartTime) {
            this.detectionStartTime = Date.now();
        } else if (!isDetecting) {
            this.detectionStartTime = null;
        }
    }

    /**
     * 顯示預覽區域
     * @private
     */
    showPreview() {
        this.elements.preview?.classList.remove('hidden');
    }

    /**
     * 隱藏預覽區域
     * @private
     */
    hidePreview() {
        this.elements.preview?.classList.add('hidden');
        if (this.elements.preview) {
            this.elements.preview.innerHTML = '';
        }
    }

    /**
     * 檢查檢測是否活躍
     * @public
     * @returns {boolean} 檢測是否正在進行
     */
    isDetectionActive() {
        return this.isDetecting;
    }

    /**
     * 獲取當前統計資訊
     * @public
     * @returns {Object} 統計數據物件
     * @property {number} detectionsCount - 檢測次數
     * @property {number} elapsedTime - 經過時間(秒)
     * @property {boolean} isActive - 是否活躍
     */
    getCurrentStats() {
        const count = parseInt(this.elements.countLabel?.textContent) || 0;
        const elapsed = this.detectionStartTime ? Math.floor((Date.now() - this.detectionStartTime) / 1000) : 0;

        return {
            detectionsCount: count,
            elapsedTime: elapsed,
            isActive: this.isDetecting
        };
    }

    /**
     * 重置統計數據
     * @private
     * @description 將所有統計顯示重置為初始狀態
     */
    resetStats() {
        if (this.elements.countLabel) {
            this.elements.countLabel.textContent = '0';
        }
        if (this.elements.durationLabel) {
            this.elements.durationLabel.textContent = '0:00';
        }
        if (this.elements.emotionIcon) {
            this.elements.emotionIcon.textContent = '🎭';
        }
        if (this.elements.emotionName) {
            this.elements.emotionName.textContent = '等待檢測';
        }
    }

    /**
     * 銷毀模組
     * @public
     * @description 清理所有資源並移除事件監聽器
     */
    destroy() {
        this.stopCamera();

        // Remove event listeners
        this.elements.startBtn?.removeEventListener('click', () => this.startDetection());
        this.elements.stopBtn?.removeEventListener('click', () => this.stopDetection());
    }
}
