/**
 * =============================================================================
 * EmotionUploadModule - 情緒上傳分析模組
 * =============================================================================
 *
 * 這個模組負責處理圖片上傳和情緒分析功能，包括：
 * - 檔案選擇和預覽
 * - 情緒分析處理
 * - 結果顯示和狀態管理
 * - 檔案清理和資源釋放
 *
 * 主要方法：
 * - initialize(): 初始化模組
 * - analyzeSelectedFile(): 分析選擇的檔案
 * - clearFile(): 清除已選擇的檔案
 * - destroy(): 銷毀模組並清理資源
 * =============================================================================
 */

import { EmotionUploadController } from './upload/controller.js';

/**
 * 情緒上傳分析模組類別
 * @class EmotionUploadModule
 */
export class EmotionUploadModule {
    /**
     * 建構函式
     * @param {StatusManager} statusManager - 狀態管理器實例
     */
    constructor(statusManager) {
        this.statusManager = statusManager;
        this.controller = new EmotionUploadController(statusManager);
    }

    /**
     * 初始化模組 (BaseModule 生命週期)
     * @async
     */
    async initialize() {
        return this.controller.initialize();
    }

    /**
     * 分析選擇的檔案
     */
    analyzeSelectedFile() {
        return this.controller.analyzeSelectedFile();
    }

    /**
     * 清除檔案
     */
    clearFile() {
        return this.controller.clearFile();
    }

    /**
     * 銷毀模組 (BaseModule 生命週期)
     * @async
     */
    async destroy() {
        return this.controller.destroy();
    }
}
