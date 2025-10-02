/**
 * =============================================================================
 * GestureController - 手勢繪畫控制器
 * =============================================================================
 *
 * 協調手勢繪畫模組的各個服務和展示器，管理完整的生命週期。
 * 作為模組的主要入口點，對外提供簡潔的 API。
 *
 * 主要功能：
 * - 協調 CameraService、GestureSessionService 和 GesturePresenter
 * - 管理模組生命週期（初始化、啟動、停止、清理）
 * - 處理狀態更新和 StatusManager 通知
 * - 提供統一的 API 介面
 * - 錯誤處理和恢復機制
 *
 * 架構設計：
 * - 保持控制器輕量（<200行）
 * - 將具體實現委托給服務層
 * - 事件驅動的架構模式
 * - 清晰的錯誤邊界
 * =============================================================================
 */

import { BaseModule } from '../../app/base-module.js';
import CameraService from '../shared/camera/camera-service.js';
import GestureSessionService from '../gesture/service.js';
import GesturePresenter from './presenter.js';
import { STATUS_TYPES } from '/static/js/common/constants.js';

export class GestureController extends BaseModule {
    constructor(statusManager) {
        super({ name: 'gesture-drawing', statusManager });

        // 核心服務
        this.cameraService = new CameraService();
        this.sessionService = new GestureSessionService();
        this.presenter = new GesturePresenter();

        // 事件解除函數
        this.cameraSubscriptions = [];
        this.sessionSubscriptions = [];

        // 狀態管理
        this.isActive = false;
        this.frameProcessingId = null;

        // 綁定方法到實例
        this.handleCameraReady = this.handleCameraReady.bind(this);
        this.handleCameraError = this.handleCameraError.bind(this);
        this.handleSessionStarted = this.handleSessionStarted.bind(this);
        this.handleSessionStopped = this.handleSessionStopped.bind(this);
        this.handleGestureUpdate = this.handleGestureUpdate.bind(this);
        this.handleCanvasUpdate = this.handleCanvasUpdate.bind(this);
        this.handleRecognitionResult = this.handleRecognitionResult.bind(this);
        this.handleSessionError = this.handleSessionError.bind(this);

        // 事件處理函數（供 presenter 使用）
        this.eventHandlers = {
            onStart: () => this.startDrawing(),
            onStop: () => this.stopDrawing(),
            onClear: () => this.clearCanvas(),
            onColorChange: (color) => this.changeColor(color),
            onBrushSizeChange: (size) => this.changeBrushSize(size)
        };

        console.log('🎨 GestureController 已創建');
    }

    /**
     * 初始化控制器 (BaseModule 生命週期)
     * @async
     */
    async _onInitialize() {
        console.log('🎨 初始化手勢繪畫控制器...');

        // 註冊服務事件
        this.setupServiceEvents();

        // 綁定 UI 事件處理函數
        this.presenter.bindEventHandlers(this.eventHandlers);

        console.log('✅ GestureController 初始化完成');
    }

    /**
     * 設置服務事件監聽
     * @private
     */
    setupServiceEvents() {
        // 攝影機服務事件
        this.cameraSubscriptions.push(this.cameraService.on('ready', this.handleCameraReady));
        this.cameraSubscriptions.push(this.cameraService.on('error', this.handleCameraError));

        // 會話服務事件
        this.sessionSubscriptions.push(this.sessionService.on('sessionStarted', this.handleSessionStarted));
        this.sessionSubscriptions.push(this.sessionService.on('sessionStopped', this.handleSessionStopped));
        this.sessionSubscriptions.push(this.sessionService.on('gestureUpdate', this.handleGestureUpdate));
        this.sessionSubscriptions.push(this.sessionService.on('canvasUpdate', this.handleCanvasUpdate));
        this.sessionSubscriptions.push(this.sessionService.on('recognitionResult', this.handleRecognitionResult));
        this.sessionSubscriptions.push(this.sessionService.on('colorChanged', (data) => this.handleColorChanged(data)));
        this.sessionSubscriptions.push(this.sessionService.on('canvasCleared', () => this.handleCanvasCleared()));
        this.sessionSubscriptions.push(this.sessionService.on('error', this.handleSessionError));
    }

    /**
     * 初始化攝影機預覽（模式切換時調用）
     * @async
     */
    async initializePreview() {
        try {
            console.log('📹 初始化攝影機預覽...');

            if (!this.isInitialized) {
                await this.initialize();
            }

            // 顯示繪畫區域 UI
            this.presenter.showDrawingDisplay();

            // 啟動攝影機
            await this.cameraService.start({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'
                }
            });

            // 確保立即綁定串流顯示預覽
            if (this.presenter.elements?.videoElement) {
                await this.cameraService.attachToVideoElement(this.presenter.elements.videoElement, {
                    mirror: true,
                    style: {
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover'
                    }
                });
            } else if (this.presenter.elements?.cameraContainer) {
                await this.cameraService.createVideoElement(this.presenter.elements.cameraContainer, {
                    mirror: true,
                    style: {
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover'
                    }
                });
            }

            this.updateStatus('攝影機預覽已就緒，請點擊「開始手勢繪畫」', STATUS_TYPES.SUCCESS);

        } catch (error) {
            console.error('❌ 初始化攝影機預覽失敗:', error);
            this.updateStatus(`攝影機預覽失敗: ${error.message}`, STATUS_TYPES.ERROR);
            throw error;
        }
    }

    /**
     * 開始手勢繪畫
     * @async
     */
    async startDrawing() {
        try {
            console.log('🎨 GestureController.startDrawing() 被調用');
            this.updateStatus('啟動手勢繪畫...', STATUS_TYPES.INFO);

            // 確保攝影機已啟動
            if (!this.cameraService.isRunning()) {
                await this.initializePreview();
            }

            // 連接會話服務
            await this.sessionService.connect();

            // 獲取攝影機尺寸並調整畫布
            const videoSize = this.cameraService.getVideoSize();
            this.presenter.adjustCanvasSize(videoSize);

            // 開始繪畫會話
            await this.sessionService.startSession({
                canvasSize: videoSize,
                color: 'black',
                mode: 'gesture_control'
            });

            // 開始幀處理循環
            this.startFrameProcessing();

            this.isActive = true;
            this.presenter.updateButtonStates(true);
            this.presenter.updateColorDisplay('black');

            console.log('✅ 手勢繪畫已啟動');

        } catch (error) {
            console.error('❌ 啟動手勢繪畫失敗:', error);
            this.updateStatus(`啟動失敗: ${error.message}`, STATUS_TYPES.ERROR);
            await this.stopDrawing();
        }
    }

    /**
     * 停止手勢繪畫
     * @async
     * @param {boolean} closeCamera - 是否關閉攝影機
     */
    async stopDrawing(closeCamera = false) {
        try {
            console.log('🛑 停止手勢繪畫...');

            this.isActive = false;

            // 停止幀處理
            this.stopFrameProcessing();

            // 捕獲最終圖片（在停止會話前）
            const finalImage = await this.presenter.captureFinalComposite();

            // 停止會話
            if (this.sessionService.getSessionStatus().isActive) {
                await this.sessionService.stopSession();
            }

            // 關閉攝影機（如果需要）
            if (closeCamera) {
                this.cameraService.stop();
                this.presenter.hideDrawingDisplay();
                this.updateStatus('手勢繪畫已完全停止', STATUS_TYPES.INFO);
            } else {
                // 顯示最終結果
                if (finalImage) {
                    await this.presenter.showFinalResult(
                        finalImage,
                        null, // 保存由 presenter 內部處理
                        () => this.startNewDrawing()
                    );
                    this.updateStatus('繪畫已完成，顯示最終作品', STATUS_TYPES.SUCCESS);
                } else {
                    this.updateStatus('繪畫已停止', STATUS_TYPES.INFO);
                }
            }

            // 更新 UI 狀態
            this.presenter.updateButtonStates(false);

        } catch (error) {
            console.error('❌ 停止手勢繪畫失敗:', error);
            this.updateStatus(`停止失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 清空畫布
     * @async
     */
    async clearCanvas() {
        try {
            console.log('🗑️ 清空畫布...');

            if (!this.isActive) {
                this.updateStatus('請先開始繪畫會話', STATUS_TYPES.WARNING);
                return;
            }

            await this.sessionService.clearCanvas();
            this.presenter.clearLocalCanvas();

            this.updateStatus('畫布已清空', STATUS_TYPES.SUCCESS);

        } catch (error) {
            console.error('❌ 清空畫布失敗:', error);
            this.updateStatus(`清空畫布失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 變更繪畫顏色
     * @async
     * @param {string} colorName - 顏色名稱
     */
    async changeColor(colorName) {
        try {
            console.log('🎨 變更顏色:', colorName);

            if (!this.isActive) {
                this.updateStatus('請先開始繪畫會話', STATUS_TYPES.WARNING);
                return;
            }

            await this.sessionService.changeColor(colorName);
            this.presenter.updateColorDisplay(colorName);

            this.updateStatus(`顏色已變更為 ${colorName}`, STATUS_TYPES.SUCCESS);

        } catch (error) {
            console.error('❌ 變更顏色失敗:', error);
            this.updateStatus(`顏色變更失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 變更筆刷大小
     * @async
     * @param {number} size - 筆刷大小
     */
    async changeBrushSize(size) {
        try {
            console.log('🖌️ 變更筆刷大小:', size);

            if (!this.isActive) {
                this.updateStatus('請先開始繪畫會話', STATUS_TYPES.WARNING);
                return;
            }

            await this.sessionService.changeBrushSize(size);
            this.updateStatus(`筆刷大小已變更為 ${size}`, STATUS_TYPES.SUCCESS);

        } catch (error) {
            console.error('❌ 變更筆刷大小失敗:', error);
            this.updateStatus(`筆刷大小變更失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 開始新的繪畫
     * @async
     */
    async startNewDrawing() {
        try {
            console.log('🆕 開始新的繪畫...');

            // 隱藏最終結果
            this.presenter.hideFinalResult();

            // 重置展示器狀態
            this.presenter.reset();

            // 重新開始繪畫
            await this.startDrawing();

        } catch (error) {
            console.error('❌ 開始新繪畫失敗:', error);
            this.updateStatus(`開始新繪畫失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 開始幀處理循環
     * @private
     */
    startFrameProcessing() {
        const frameInterval = 1000 / 20; // 20 FPS
        let lastFrameTime = 0;

        const processFrame = (currentTime) => {
            if (!this.isActive) return;

            if (currentTime - lastFrameTime >= frameInterval) {
                this.processVideoFrame();
                lastFrameTime = currentTime;
            }

            this.frameProcessingId = requestAnimationFrame(processFrame);
        };

        this.frameProcessingId = requestAnimationFrame(processFrame);
        console.log('📡 幀處理循環已啟動');
    }

    /**
     * 停止幀處理循環
     * @private
     */
    stopFrameProcessing() {
        if (this.frameProcessingId) {
            cancelAnimationFrame(this.frameProcessingId);
            this.frameProcessingId = null;
            console.log('📡 幀處理循環已停止');
        }
    }

    /**
     * 處理視頻幀
     * @private
     */
    processVideoFrame() {
        if (!this.cameraService.isRunning() || !this.sessionService.getSessionStatus().isActive) {
            return;
        }

        const frameData = this.cameraService.captureFrame('jpeg', 0.8);
        if (frameData) {
            this.sessionService.sendFrame(frameData);
        }
    }

    // ===== 事件處理函數 =====

    /**
     * 處理攝影機就緒事件
     * @private
     */
    async handleCameraReady({ stream, videoSize } = {}) {
        console.log('📹 攝影機就緒，解析度:', videoSize);

        const videoElement = this.presenter.elements?.videoElement;
        if (videoElement) {
            try {
                await this.cameraService.attachToVideoElement(videoElement, {
                    mirror: true,
                    style: {
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover'
                    }
                });
            } catch (error) {
                console.error('❌ 綁定攝影機串流失敗:', error);
                this.updateStatus(`攝影機綁定失敗: ${error.message}`, STATUS_TYPES.ERROR);
            }
        }
    }

    /**
     * 處理攝影機錯誤事件
     * @private
     */
    handleCameraError(errorDetail) {
        const error = errorDetail instanceof Error ? errorDetail : (errorDetail?.detail || errorDetail);
        const message = error?.message ? error.message : this.cameraService.getErrorMessage(error || new Error('未知錯誤'));
        console.error('❌ 攝影機錯誤:', message);
        this.updateStatus(message, STATUS_TYPES.ERROR);
    }

    /**
     * 處理會話開始事件
     * @private
     */
    handleSessionStarted({ sessionId }) {
        console.log('✅ 繪畫會話已開始:', sessionId);
        this.updateStatus('手勢繪畫已啟動，開始偵測手勢', STATUS_TYPES.SUCCESS);
    }

    /**
     * 處理會話停止事件
     * @private
     */
    handleSessionStopped() {
        console.log('🛑 繪畫會話已停止');
        this.isActive = false;
    }

    /**
     * 處理手勢更新事件
     * @private
     */
    handleGestureUpdate({ gesture, fingersUp, position }) {
        // 更新手勢提示
        this.presenter.updateGestureHints(gesture, fingersUp);

        // 渲染本地筆觸（即時回饋）
        const currentColor = this.sessionService.getSessionStatus().currentColor;
        this.presenter.renderLocalStroke(gesture, position, currentColor);
    }

    /**
     * 處理畫布更新事件
     * @private
     */
    handleCanvasUpdate(canvasData) {
        this.presenter.updateCanvas(canvasData);
    }

    /**
     * 處理識別結果事件
     * @private
     */
    handleRecognitionResult({ shape, confidence, message }) {
        console.log('🤖 AI 識別結果:', { shape, confidence });
        if (message) {
            this.updateStatus(message, STATUS_TYPES.SUCCESS);
        }
    }

    /**
     * 處理顏色變更事件
     * @private
     */
    handleColorChanged(data) {
        const { color, position } = data;
        console.log('🎨 顏色已透過手勢切換:', color, '位置:', position);
        this.presenter.updateColorDisplay(color);
        this.presenter.highlightColorZone(color);
        this.updateStatus(`顏色已切換為 ${color}`, STATUS_TYPES.SUCCESS);
    }

    /**
     * 處理畫布清空事件
     * @private
     */
    handleCanvasCleared() {
        console.log('🗑️ 畫布已透過手勢清空');
        this.updateStatus('畫布已清空', STATUS_TYPES.INFO);
    }

    /**
     * 處理會話錯誤事件
     * @private
     */
    handleSessionError(errorDetail) {
        const message = typeof errorDetail === 'string'
            ? errorDetail
            : (errorDetail?.message || '未知錯誤');
        console.error('❌ 會話錯誤:', message);
        this.updateStatus(`會話錯誤: ${message}`, STATUS_TYPES.ERROR);
    }

    // ===== 狀態查詢 API =====

    /**
     * 檢查繪畫是否活躍
     * @returns {boolean}
     */
    isDrawingActive() {
        return this.isActive;
    }

    /**
     * 獲取當前狀態
     * @returns {Object}
     */
    getCurrentStatus() {
        return {
            isActive: this.isActive,
            ...this.sessionService.getSessionStatus(),
            cameraRunning: this.cameraService.isRunning()
        };
    }

    // ===== 清理資源 =====

    /**
     * 銷毀控制器 (BaseModule 生命週期)
     * @async
     */
    async _onDestroy() {
        console.log('🗑️ 清理 GestureController 資源...');

        // 停止所有活動
        this.stopFrameProcessing();
        await this.stopDrawing(true);

        // 清理服務
        if (this.cameraSubscriptions.length) {
            this.cameraSubscriptions.forEach((unsubscribe) => {
                try {
                    unsubscribe?.();
                } catch (error) {
                    console.error('❌ 移除攝影機事件監聽器失敗:', error);
                }
            });
            this.cameraSubscriptions = [];
        }

        if (this.sessionSubscriptions.length) {
            this.sessionSubscriptions.forEach((unsubscribe) => {
                try {
                    unsubscribe?.();
                } catch (error) {
                    console.error('❌ 移除會話事件監聽器失敗:', error);
                }
            });
            this.sessionSubscriptions = [];
        }

        if (this.cameraService) {
            this.cameraService.destroy();
            this.cameraService = null;
        }

        if (this.sessionService) {
            this.sessionService.destroy();
            this.sessionService = null;
        }

        if (this.presenter) {
            this.presenter.destroy();
            this.presenter = null;
        }

        // 重置狀態
        this.isActive = false;

        console.log('✅ GestureController 資源清理完成');
    }
}

export default GestureController;
