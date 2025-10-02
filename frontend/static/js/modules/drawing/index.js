/**
 * =============================================================================
 * GestureDrawingModule - 手勢繪畫模組
 * =============================================================================
 *
 * 這個模組負責管理手勢繪畫功能，包括：
 * - 攝影機預覽初始化
 * - 手勢繪畫會話控制
 * - 畫布操作（清空、變更顏色、大小）
 * - 與其他模組的狀態同步
 *
 * 主要方法：
 * - initializeCameraPreview(): 初始化攝影機並顯示預覽
 * - startGestureDrawing(): 開始手勢繪畫會話
 * - stopGestureDrawing(): 停止手勢繪畫會話
 * - clearCanvas(): 清空繪畫畫布
 * - changeDrawingColor(): 變更繪畫顏色
 * - changeBrushSize(): 變更筆刷大小
 * =============================================================================
 */

import GestureController from './controller.js';
import { STATUS_TYPES } from '../../common/constants.js';

export class GestureDrawingModule {
    constructor(statusManager) {
        this.statusManager = statusManager;
        
        // 使用新的控制器架構
        this.controller = new GestureController(statusManager);
        
        // 狀態屬性
        this.isActive = false;

        // 監聽模式切換事件，自動初始化攝影機預覽
        this.setupModeChangeListener();

        console.log('🎨 GestureDrawingModule 已創建（使用新架構）');
    }

    /**
     * 設置模式切換監聽器
     * @private
     */
    setupModeChangeListener() {
        document.addEventListener('modeSwitched', async (event) => {
            if (event.detail.mode === 'drawing') {
                console.log('🎨 檢測到切換至繪畫模式，自動初始化攝影機預覽');
                try {
                    await this.initializeCameraPreview();
                } catch (error) {
                    console.error('❌ 繪畫模式攝影機自動初始化失敗:', error);
                }
            }
        });
    }

    /**
     * 初始化模組
     * @deprecated 會在需要時自動初始化
     */
    init() {
        console.log('🎨 GestureDrawingModule init() 調用');
        // 會在 initializePreview 時自動初始化，這裡不需要做任何事
    }

    /**
     * 設置 DOM 引用
     * @deprecated Presenter 會自動管理 DOM 引用
     */
    setupDOMReferences() {
        console.log('🎨 setupDOMReferences() 調用');
        // Presenter 會自動處理
    }

    /**
     * 設置事件監聽器
     * @deprecated Presenter 會自動綁定事件
     */
    setupEventListeners() {
        console.log('🎨 setupEventListeners() 調用');
        // 會自動處理事件綁定
    }

    /**
     * 初始化攝影機預覽（主要公共 API）
     * @async
     * @public
     */
    async initializeCameraPreview() {
        try {
            console.log('📹 初始化攝影機預覽（最新版本）...');
            await this.controller.initializePreview();
            console.log('✅ 攝影機預覽初始化完成');
        } catch (error) {
            console.error('❌ 攝影機預覽初始化失敗:', error);
            this.statusManager?.update(`攝影機預覽失敗: ${error.message}`, STATUS_TYPES.ERROR);
            throw error;
        }
    }

    /**
     * 開始手勢繪畫（主要公共 API）
     * @async
     * @public
     */
    async startGestureDrawing() {
        try {
            console.log('🎨 開始手勢繪畫（最新版本）...');
            await this.controller.startDrawing();
            this.isActive = true;
            console.log('✅ 手勢繪畫已啟動');
        } catch (error) {
            console.error('❌ 啟動手勢繪畫失敗:', error);
            this.statusManager?.update(`啟動失敗: ${error.message}`, STATUS_TYPES.ERROR);
            throw error;
        }
    }

    /**
     * 停止手勢繪畫（主要公共 API）
     * @async
     * @public
     * @param {boolean} closeCameraAlso - 是否關閉攝影機
     */
    async stopGestureDrawing(closeCameraAlso = false) {
        try {
            console.log('🛑 停止手勢繪畫（最新版本）...');
            await this.controller.stopDrawing(closeCameraAlso);
            this.isActive = false;
            console.log('✅ 手勢繪畫已停止');
        } catch (error) {
            console.error('❌ 停止手勢繪畫失敗:', error);
            this.statusManager?.update(`停止失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 清空畫布
     * @async
     * @public
     */
    async clearCanvas() {
        try {
            console.log('🗑️ 清空畫布...');
            await this.controller.clearCanvas();
        } catch (error) {
            console.error('❌ 清空畫布失敗:', error);
            this.statusManager?.update(`清空畫布失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 變更繪畫顏色（新增功能）
     * @async
     * @public
     * @param {string} colorName - 顏色名稱
     */
    async changeDrawingColor(colorName) {
        try {
            console.log('🎨 變更繪畫顏色（最新版本）:', colorName);
            await this.controller.changeColor(colorName);
        } catch (error) {
            console.error('❌ 變更顏色失敗:', error);
            this.statusManager?.update(`顏色變更失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    /**
     * 變更筆刷大小（新增功能）
     * @async
     * @public
     * @param {number} size - 筆刷大小
     */
    async changeBrushSize(size) {
        try {
            console.log('🖌️ 變更筆刷大小（最新版本）:', size);
            await this.controller.changeBrushSize(size);
        } catch (error) {
            console.error('❌ 變更筆刷大小失敗:', error);
            this.statusManager?.update(`筆刷大小變更失敗: ${error.message}`, STATUS_TYPES.ERROR);
        }
    }

    // ===== 狀態查詢方法 =====

    /**
     * 檢查繪畫是否活躍
     * @returns {boolean}
     */
    isDrawingActive() {
        const status = this.controller.getCurrentStatus();
        return status.isActive;
    }

    /**
     * 獲取當前狀態
     * @returns {Object}
     */
    getCurrentStatus() {
        return this.controller.getCurrentStatus();
    }

    /**
     * 設置攝影機串流
     * @deprecated 會自動管理攝影機
     * @param {MediaStream} stream - 媒體串流
     */
    setStream(stream) {
        console.log('🎨 setStream() 調用（忽略）');
        // 會自動管理攝影機串流
    }

    /**
     * 設置視頻元素
     * @deprecated Presenter 會自動管理 DOM 元素
     * @param {HTMLVideoElement} videoElement - 視頻元素
     */
    setVideoElement(videoElement) {
        console.log('🎨 setVideoElement() 調用（忽略）');
        // Presenter 會自動管理
    }

    // ===== 舊版方法的代理 =====

    /**
     * 開始攝影機
     * @deprecated 使用 initializeCameraPreview() 代替
     */
    async startCamera() {
        console.log('🎨 startCamera() 調用 -> initializeCameraPreview()');
        return this.initializeCameraPreview();
    }

    /**
     * 連接 WebSocket
     * @deprecated 會在 startDrawing 時自動連接
     */
    async connectWebSocket() {
        console.log('🎨 connectWebSocket() 調用（自動處理）');
        // 會在需要時自動連接
    }

    /**
     * 開始繪畫會話
     * @deprecated 使用 startGestureDrawing() 代替
     */
    async startDrawingSession() {
        console.log('🎨 startDrawingSession() 調用 -> startGestureDrawing()');
        return this.startGestureDrawing();
    }

    /**
     * 開始幀處理
     * @deprecated 會自動管理幀處理
     */
    startFrameProcessing() {
        console.log('🎨 startFrameProcessing() 調用（自動處理）');
        // 會自動處理
    }

    /**
     * 捕獲並發送幀
     * @deprecated 會自動管理幀傳輸
     */
    captureAndSendFrame() {
        // 會自動處理，不需要手動調用
    }

    // ===== 事件處理 =====

    /**
     * 處理 WebSocket 消息
     * @deprecated SessionService 會自動處理
     * @param {Object} data - 消息數據
     */
    handleWebSocketMessage(data) {
        console.log('🎨 handleWebSocketMessage() 調用（自動處理）');
        // 會自動處理消息
    }

    /**
     * 更新手勢狀態
     * @deprecated Presenter 會自動更新
     * @param {Object} data - 手勢數據
     */
    updateGestureStatus(data) {
        console.log('🎨 updateGestureStatus() 調用（自動處理）');
        // 會自動處理
    }

    /**
     * 更新畫布
     * @deprecated Presenter 會自動更新
     * @param {Object} data - 畫布數據
     */
    updateCanvas(data) {
        console.log('🎨 updateCanvas() 調用（自動處理）');
        // 會自動處理
    }

    // ===== 清理和銷毀 =====

    /**
     * 初始化模組 (BaseModule 生命週期)
     * @async
     */
    async initialize() {
        return this.controller.initialize();
    }

    /**
     * 銷毀模組 (BaseModule 生命週期)
     * @async
     */
    async destroy() {
        console.log('🗑️ 銷毀 GestureDrawingModule...');

        if (this.controller) {
            await this.controller.destroy();
            this.controller = null;
        }

        this.isActive = false;
        console.log('✅ GestureDrawingModule 已銷毀');
    }

    // ===== 調試和狀態檢查 =====

    /**
     * 獲取架構信息
     * @returns {Object} 架構信息
     */
    getArchitectureInfo() {
        return {
            version: '2.0',
            architecture: 'Controller + Services + Presenter',
            features: {
                sharedCameraService: true,
                websocketTransport: true,
                canvasUtils: true,
                modularArchitecture: true,
                eventDriven: true
            }
        };
    }

    /**
     * 檢查是否為最新版本
     * @returns {boolean} 總是返回 true
     */
    isModernArchitecture() {
        return true;
    }
}

export default GestureDrawingModule;
