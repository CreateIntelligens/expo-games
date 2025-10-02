/**
 * =============================================================================
 * emotion-presenter.js - 情緒分析展示模組
 *
 * 負責處理情緒分析功能的 UI 更新和顯示邏輯
 * 從 emotion-realtime.js 中提取的 UI 相關功能
 * =============================================================================
 */

import { ButtonToggler } from '/static/js/common/ui-helpers.js';

/**
 * 情緒分析展示類別
 * 處理 UI 元素的更新、按鈕狀態管理和統計顯示
 */
export class EmotionPresenter {
    constructor() {
        // DOM 元素引用
        this.elements = this._initializeElements();

        // UI 控制器
        this.startButtonToggler = new ButtonToggler(this.elements.startBtn);
        this.stopButtonToggler = new ButtonToggler(this.elements.stopBtn);

        // 統計資訊
        this.detectionStartTime = null;
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
            preview: document.getElementById('emotion-preview'),
            durationLabel: document.getElementById('detection-duration'),
            countLabel: document.getElementById('detection-count'),
            emotionIcon: document.getElementById('emotion-icon'),
            emotionName: document.getElementById('emotion-name'),
            liveIndicator: document.getElementById('emotion-live-indicator'),
            liveIndicatorLabel: document.getElementById('emotion-live-indicator-label')
        };
    }

    /**
     * 顯示預覽區域
     */
    showPreview() {
        this.elements.preview?.classList.remove('hidden');
    }

    /**
     * 隱藏預覽區域
     */
    hidePreview() {
        this.elements.preview?.classList.add('hidden');
        if (this.elements.preview) {
            this.elements.preview.innerHTML = '';
        }
    }

    /**
     * 設置按鈕狀態
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

        // 更新狀態徽章
        if (this.elements.liveIndicator) {
            this.elements.liveIndicator.classList.toggle('active', isDetecting);
        }

        if (this.elements.liveIndicatorLabel) {
            this.elements.liveIndicatorLabel.textContent = isDetecting ? '分析中' : '待命';
        }
    }

    /**
     * 更新即時顯示結果
     * @param {Object} result - 分析結果數據
     * @description 更新UI顯示情緒分析結果、信心度和統計資訊
     */
    updateRealtimeDisplay(result) {
        const faceDetected = result.face_detected === undefined ? true : !!result.face_detected;

        // 正規化情緒標籤
        let emotionLabel = result.emotion_zh || '未檢測到';
        if (emotionLabel === '中性') {
            emotionLabel = '面無表情';
        }
        if (!faceDetected) {
            emotionLabel = '沒分析到臉';
        }

        // 更新底部詳細資訊區域
        if (this.elements.emotionIcon) {
            this.elements.emotionIcon.textContent = faceDetected ? (result.emoji || '❓') : '🙈';
        }

        if (this.elements.emotionName) {
            this.elements.emotionName.textContent = emotionLabel;
        }

        // 更新信心度
        const confidenceEl = document.getElementById('emotion-confidence');
        if (confidenceEl) {
            if (faceDetected) {
                const confidence = Math.round((result.confidence || 0) * 100);
                confidenceEl.textContent = `${confidence}%`;
            } else {
                confidenceEl.textContent = '--';
            }
        }

        // 更新檢測統計
        if (faceDetected && this.elements.countLabel) {
            const currentCount = parseInt(this.elements.countLabel.textContent) || 0;
            this.elements.countLabel.textContent = (currentCount + 1).toString();
        }

        // 更新檢測時間
        this.updateDetectionDuration();
    }

    /**
     * 更新檢測持續時間
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
     * 重置統計數據
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

        if (this.elements.liveIndicator) {
            this.elements.liveIndicator.classList.remove('active');
        }

        if (this.elements.liveIndicatorLabel) {
            this.elements.liveIndicatorLabel.textContent = '待命';
        }
    }

    /**
     * 獲取當前統計資訊
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
            isActive: !!this.detectionStartTime
        };
    }

    /**
     * 創建視訊容器
     * @returns {HTMLElement|null} 攝影機容器元素
     */
    getCameraContainer() {
        return document.querySelector('.camera-container') || this.elements.preview;
    }

    /**
     * 綁定事件監聽器
     * @param {Function} onStart - 開始檢測回調
     * @param {Function} onStop - 停止檢測回調
     */
    bindEvents(onStart, onStop) {
        this.elements.startBtn?.addEventListener('click', onStart);
        this.elements.stopBtn?.addEventListener('click', onStop);

        // 監聽標籤切換事件，當切換到攝影機分析標籤時初始化預覽
        document.addEventListener('tabSwitched', (e) => {
            if (e.detail.tabId === 'webcam') {
                // 通知控制器初始化攝影機預覽
                if (this.onTabSwitched) {
                    this.onTabSwitched();
                }
            }
        });
    }

    /**
     * 設置標籤切換回調
     * @param {Function} callback - 標籤切換回調函數
     */
    setTabSwitchCallback(callback) {
        this.onTabSwitched = callback;
    }

    /**
     * 移除事件監聽器
     * @param {Function} onStart - 開始檢測回調
     * @param {Function} onStop - 停止檢測回調
     */
    unbindEvents(onStart, onStop) {
        this.elements.startBtn?.removeEventListener('click', onStart);
        this.elements.stopBtn?.removeEventListener('click', onStop);
    }
}
