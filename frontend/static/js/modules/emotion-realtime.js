/**
 * =============================================================================
 * emotion-realtime.js - 即時情緒檢測模組
 *
 * 使用新的模組化架構重新實現情緒分析功能
 * 保持與原始模組相同的 API，但使用分離的服務類別
 * =============================================================================
 */

import { EmotionController } from './emotion/emotion-controller.js';

/**
 * 即時情緒檢測模組類別
 * 使用新的模組化架構，保持向後相容性
 */
export class EmotionRealtimeModule {
    /**
     * 建構函式
     * @param {StatusManager} statusManager - 狀態管理器實例
     */
    constructor(statusManager) {
        // 使用新的控制器架構
        this.controller = new EmotionController(statusManager);

        // 保持向後相容性的屬性映射
        this.statusManager = statusManager;
    }

    /**
     * 初始化攝影機預覽
     * @async
     * @public
     */
    async initializeCameraPreview() {
        return this.controller.initializeCameraPreview();
    }

    /**
     * 開始情緒檢測流程
     * @async
     * @public
     */
    async startDetection() {
        return this.controller.startDetection();
    }

    /**
     * 停止情緒檢測
     * @async
     * @public
     */
    async stopDetection() {
        return this.controller.stopDetection();
    }

    /**
     * 完全停止攝影機
     * @async
     * @public
     */
    async stopCamera() {
        return this.controller.stopCamera();
    }

    /**
     * 檢查檢測是否活躍
     * @public
     * @returns {boolean} 檢測是否正在進行
     */
    isDetectionActive() {
        return this.controller.isDetectionActive();
    }

    /**
     * 獲取當前統計資訊
     * @public
     * @returns {Object} 統計數據物件
     */
    getCurrentStats() {
        return this.controller.getCurrentStats();
    }

    /**
     * 銷毀模組
     * @public
     */
    destroy() {
        this.controller.destroy();
    }
}