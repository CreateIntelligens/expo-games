/**
 * =============================================================================
 * emotion-controller.js - 情緒分析控制器
 *
 * 負責協調 CameraService、WebSocketTransport 和 EmotionPresenter
 * 實現情緒分析功能的主要邏輯控制
 * 從 emotion-realtime.js 中提取的控制邏輯
 * =============================================================================
 */

import { STREAM_CONFIG, STATUS_TYPES } from '/static/js/common/constants.js';
import { BaseModule } from '../../../app/base-module.js';
import { CameraService } from '../../shared/camera/camera-service.js';
import { WebSocketTransport } from '../../shared/transport/websocket-transport.js';
import { EmotionPresenter } from './presenter.js';

/**
 * 情緒分析控制器類別
 * 協調各個服務模組，實現完整的情緒分析流程
 */
export class EmotionController extends BaseModule {
    constructor(statusManager, options = {}) {
        super({ name: 'emotion-realtime', statusManager });

        // 核心服務
        this.cameraService = new CameraService();
        this.transport = new WebSocketTransport();
        this.presenter = new EmotionPresenter();

        // 狀態管理
        this.isDetecting = false;
        this.analysisInterval = null;

        // 綁定事件處理函數
        this.handleStartRequest = () => this.startDetection();
        this.handleStopRequest = () => this.stopDetection();
        this.onCameraReady = () => {
            console.log('📹 攝影機服務就緒');
        };
        this.onCameraError = (errorDetail) => {
            const error = errorDetail instanceof Error ? errorDetail : (errorDetail?.detail || errorDetail);
            const message = this.cameraService.getErrorMessage(error || new Error('未知錯誤'));
            this.updateStatus(message, STATUS_TYPES.ERROR);
        };
        this.onTransportOpen = () => {
            this.updateStatus('WebSocket連接成功', STATUS_TYPES.SUCCESS);
        };
        this.onTransportMessage = (data) => {
            this.handleWebSocketResult(data);
        };
        this.onTransportError = (event) => {
            const error = event instanceof Error ? event : (event?.detail || event);
            console.error('❌ WebSocket連接錯誤:', error);
            this.updateStatus('WebSocket連接錯誤', STATUS_TYPES.ERROR);
        };
        this.onHeartbeatTimeout = () => {
            console.warn('💔 心跳超時，準備重新連接 WebSocket');
        };

        this.cameraSubscriptions = [];
        this.transportSubscriptions = [];
    }

    /**
     * 初始化控制器（BaseModule 生命週期）
     */
    async _onInitialize() {
        this.setupEventListeners();
        this.presenter.setButtonsState(false);
    }

    /**
     * 設置事件監聽器
     */
    setupEventListeners() {
        // 綁定 UI 事件
        this.presenter.bindEvents(this.handleStartRequest, this.handleStopRequest);

        // 設置標籤切換回調
        this.presenter.setTabSwitchCallback(() => this.initializeCameraPreview());

        // 攝影機服務事件
        this.cameraSubscriptions.push(this.cameraService.on('ready', this.onCameraReady));
        this.cameraSubscriptions.push(this.cameraService.on('error', this.onCameraError));

        // WebSocket 事件
        this.transportSubscriptions.push(this.transport.on('open', this.onTransportOpen));
        this.transportSubscriptions.push(this.transport.on('message', this.onTransportMessage));
        this.transportSubscriptions.push(this.transport.on('error', this.onTransportError));
        this.transportSubscriptions.push(this.transport.on('heartbeatTimeout', this.onHeartbeatTimeout));
        this.transportSubscriptions.push(this.transport.on('close', () => {
            if (this.isDetecting) {
                this.updateStatus('WebSocket連線已關閉', STATUS_TYPES.WARNING);
            }
        }));
    }

    /**
     * 初始化攝影機預覽
     * @async
     * @description 僅初始化攝影機並顯示預覽，不啟動WebSocket分析
     */
    async initializeCameraPreview() {
        if (this.cameraService.isActive()) {
            this.updateStatus('攝影機預覽已啟動', STATUS_TYPES.INFO);
            return;
        }

        console.log('📹 初始化攝影機預覽...');

        try {
            await this.cameraService.start();

            const container = this.presenter.getCameraContainer();
            if (container) {
                await this.cameraService.createVideoElement(container, {
                    mirror: true,
                    style: {
                        maxWidth: '640px',
                        height: 'auto',
                        objectFit: 'contain',
                        borderRadius: '8px',
                        margin: '0 auto'
                    }
                });
                this.presenter.showPreview();
            }

            this.updateStatus('攝影機預覽已就緒，請點擊「開始情緒檢測」開始分析', STATUS_TYPES.SUCCESS);
            console.log('✅ 攝影機預覽初始化完成');

        } catch (error) {
            this.updateStatus(`攝影機預覽初始化錯誤：${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 開始情緒檢測流程
     * @async
     * @description 啟動完整的WebSocket分析流程，包含攝影機初始化、WebSocket連接和即時分析
     */
    async startDetection() {
        if (this.isDetecting) {
            this.updateStatus('情緒檢測已在進行中', STATUS_TYPES.WARNING);
            return;
        }

        console.log('🚀 開始情緒檢測流程');

        try {
            // 檢查攝影機是否已啟動
            if (!this.cameraService.isActive()) {
                this.updateStatus('正在啟動本地攝影機...', STATUS_TYPES.PROCESSING);
                await this.cameraService.start();

                // 創建視訊元素
                const container = this.presenter.getCameraContainer();
                if (container) {
                    await this.cameraService.createVideoElement(container, {
                        mirror: true,
                        style: {
                            maxWidth: '640px',
                            height: 'auto',
                            objectFit: 'contain',
                            borderRadius: '8px',
                            margin: '0 auto'
                        }
                    });
                    this.presenter.showPreview();
                }
            }

            // 建立WebSocket連接
            this.updateStatus('正在連接分析服務...', STATUS_TYPES.PROCESSING);
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/emotion`;
            await this.transport.connect(wsUrl);

            // 更新狀態
            this.isDetecting = true;
            this.presenter.setButtonsState(true);
            this.updateStatus('開始情緒分析...', STATUS_TYPES.SUCCESS);
            console.log('🎯 情緒檢測狀態設置為啟動');

            // 等待video元素載入完成後開始分析
            this.waitForVideoReady();

        } catch (error) {
            this.updateStatus(`啟動情緒檢測錯誤：${error.message}`, STATUS_TYPES.ERROR);
            this.isDetecting = false;
            this.presenter.setButtonsState(false);
        }
    }

    /**
     * 等待視訊元素準備就緒
     */
    waitForVideoReady() {
        const videoElement = this.cameraService.getVideoElement();

        const startAnalysisWhenReady = () => {
            if (videoElement && videoElement.readyState >= 2) { // HAVE_CURRENT_DATA 或更高
                console.log('🎬 Video元素已準備好，開始WebSocket分析');
                this.startWebSocketAnalysis(videoElement);
            } else {
                console.log('⏳ Video元素尚未準備好，等待中...', {
                    readyState: videoElement?.readyState,
                    videoWidth: videoElement?.videoWidth,
                    videoHeight: videoElement?.videoHeight
                });
                // 如果還沒準備好，500ms後再檢查
                setTimeout(startAnalysisWhenReady, 500);
            }
        };

        if (videoElement) {
            videoElement.addEventListener('loadeddata', () => {
                console.log('🎬 收到loadeddata事件');
                startAnalysisWhenReady();
            });

            videoElement.addEventListener('canplay', () => {
                console.log('🎬 收到canplay事件');
                startAnalysisWhenReady();
            });

            videoElement.addEventListener('error', (e) => {
                console.error('❌ Video元素載入錯誤:', e);
            });

            // 立即檢查一次（可能video已經準備好了）
            setTimeout(startAnalysisWhenReady, 1000);
        }
    }

    /**
     * 開始WebSocket影像分析
     * @param {HTMLVideoElement} videoElement - 視訊元素，用於捕獲影像幀
     * @description 定期捕獲影像幀並通過WebSocket發送到服務器進行分析
     */
    startWebSocketAnalysis(videoElement) {
        if (this.analysisInterval) {
            clearInterval(this.analysisInterval);
        }

        console.log(`⏰ 開始WebSocket分析，間隔: ${STREAM_CONFIG.ANALYSIS_INTERVAL}ms`);

        // 按照配置間隔分析
        this.analysisInterval = setInterval(() => {
            if (!this.isDetecting) {
                return;
            }

            // 檢查視訊元素是否準備好
            if (!videoElement || videoElement.videoWidth === 0 || videoElement.videoHeight === 0) {
                console.log('⏸️ 分析間隔跳過 - 視訊元素未準備好', {
                    videoElement: !!videoElement,
                    videoWidth: videoElement?.videoWidth,
                    videoHeight: videoElement?.videoHeight
                });
                return;
            }

            // 截取當前影像幀
            const imageData = this.cameraService.captureFrame();
            if (!imageData) {
                return;
            }

            // 發送影像幀到WebSocket
            const message = {
                type: 'frame',
                image: imageData,
                timestamp: Date.now() / 1000
            };

            const sent = this.transport.send(message);
            if (!sent) {
                console.log('⏸️ 分析間隔跳過 - WebSocket未連接');
            }
        }, STREAM_CONFIG.ANALYSIS_INTERVAL);
    }

    /**
     * 處理WebSocket結果
     * @param {Object} data - WebSocket訊息數據
     * @description 處理從服務器收到的分析結果或錯誤訊息
     */
    handleWebSocketResult(data) {
        console.log('📨 收到 WebSocket 訊息:', data);

        // 檢查訊息類型
        if (!data.type) {
            console.warn('收到無效的WebSocket訊息，缺少type字段:', data);
            return;
        }

        switch (data.type) {
            case 'result':
                // 情緒分析結果
                if (data.face_detected) {
                    const confidence = Math.round((data.confidence || 0) * 100);
                    console.log(`🎭 檢測到情緒: ${data.emotion_zh} (${confidence}%)`);
                } else {
                    console.log('❓ 未檢測到人臉');
                }
                this.presenter.updateRealtimeDisplay(data);
                break;

            case 'error':
                // 錯誤訊息
                const errorMsg = data.message || '未知錯誤';
                console.error('❌ 分析失敗:', errorMsg);
                this.updateStatus(`分析錯誤: ${errorMsg}`, STATUS_TYPES.ERROR);
                break;

            case 'ping':
            case 'pong':
                // 心跳訊息，忽略
                break;

            default:
                // 不支持的訊息類型
                console.warn('不支持的WebSocket訊息類型:', data.type, '完整訊息:', data);
                break;
        }
    }

    /**
     * 停止情緒檢測
     * @async
     * @description 停止WebSocket分析和心跳機制，但保持攝影機運行
     */
    async stopDetection() {
        if (!this.isDetecting) return;

        // 清理WebSocket影像串流分析的資源
        if (this.analysisInterval) {
            clearInterval(this.analysisInterval);
            this.analysisInterval = null;
        }

        // 斷開 WebSocket 連接
        this.transport.disconnect();

        this.isDetecting = false;
        this.presenter.setButtonsState(false);
        this.presenter.resetStats();
        this.updateStatus('情緒分析已停止，攝影機保持運行', STATUS_TYPES.INFO);
        console.log('🛑 情緒分析已停止，攝影機繼續運行');
    }

    /**
     * 完全停止攝影機
     * @async
     * @description 停止攝影機串流並清理所有相關資源
     */
    async stopCamera() {
        console.log('📷 正在關閉攝影機...');

        // 停止分析如果正在進行
        if (this.isDetecting) {
            await this.stopDetection();
        }

        // 停止攝影機
        this.cameraService.stop();
        this.presenter.hidePreview();
        this.updateStatus('攝影機已關閉', STATUS_TYPES.INFO);
        console.log('✅ 攝影機已完全關閉');
    }

    /**
     * 檢查檢測是否活躍
     * @returns {boolean} 檢測是否正在進行
     */
    isDetectionActive() {
        return this.isDetecting;
    }

    /**
     * 獲取當前統計資訊
     * @returns {Object} 統計數據物件
     */
    getCurrentStats() {
        return this.presenter.getCurrentStats();
    }

    /**
     * 銷毀控制器 (BaseModule 生命週期)
     * @description 清理所有資源並移除事件監聽器
     */
    async _onDestroy() {
        await this.stopCamera();
        this.transport.destroy();

        if (this.transportSubscriptions.length) {
            this.transportSubscriptions.forEach((unsubscribe) => {
                try {
                    unsubscribe?.();
                } catch (error) {
                    console.error('❌ 移除情緒 WebSocket 監聽器失敗:', error);
                }
            });
            this.transportSubscriptions = [];
        }

        if (this.cameraSubscriptions.length) {
            this.cameraSubscriptions.forEach((unsubscribe) => {
                try {
                    unsubscribe?.();
                } catch (error) {
                    console.error('❌ 移除情緒攝影機監聽器失敗:', error);
                }
            });
            this.cameraSubscriptions = [];
        }

        this.presenter.unbindEvents(this.handleStartRequest, this.handleStopRequest);
    }
}
