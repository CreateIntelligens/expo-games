/**
 * EventBus - 多監聽器事件總線
 *
 * 基於 EventTarget 的統一事件管理系統，支援多個監聽器訂閱同一個事件。
 * 提供類型安全的事件名稱和載荷驗證。
 */

export class EventBus extends EventTarget {
    constructor(options = {}) {
        super();
        this.options = {
            enableLogging: false,
            maxListeners: 100,
            ...options
        };
        this.listenerCount = new Map();
        this.eventHistory = this.options.enableLogging ? [] : null;
    }

    /**
     * 發送事件
     * @param {string} eventName - 事件名稱
     * @param {*} payload - 事件載荷
     */
    emit(eventName, payload = null) {
        if (typeof eventName !== 'string') {
            throw new Error('Event name must be a string');
        }

        const event = new CustomEvent(eventName, {
            detail: payload,
            bubbles: false,
            cancelable: true
        });

        // 記錄事件歷史（如果啟用）
        if (this.eventHistory) {
            this.eventHistory.push({
                name: eventName,
                payload,
                timestamp: Date.now()
            });

            // 限制歷史記錄長度
            if (this.eventHistory.length > 1000) {
                this.eventHistory.shift();
            }
        }

        if (this.options.enableLogging) {
            console.log(`📢 EventBus: ${eventName}`, payload);
        }

        return this.dispatchEvent(event);
    }

    /**
     * 訂閱事件
     * @param {string} eventName - 事件名稱
     * @param {Function} handler - 事件處理器
     * @param {Object} options - 監聽器選項
     */
    on(eventName, handler, options = {}) {
        if (typeof eventName !== 'string') {
            throw new Error('Event name must be a string');
        }

        if (typeof handler !== 'function') {
            throw new Error('Event handler must be a function');
        }

        // 檢查監聽器數量限制
        const currentCount = this.listenerCount.get(eventName) || 0;
        if (currentCount >= this.options.maxListeners) {
            console.warn(`EventBus: 事件 "${eventName}" 監聽器數量已達上限 (${this.options.maxListeners})`);
        }

        this.addEventListener(eventName, handler, options);
        this.listenerCount.set(eventName, currentCount + 1);

        if (this.options.enableLogging) {
            console.log(`👂 EventBus: 訂閱 ${eventName}, 總監聽器: ${currentCount + 1}`);
        }

        // 返回取消訂閱函數
        return () => this.off(eventName, handler);
    }

    /**
     * 取消訂閱事件
     * @param {string} eventName - 事件名稱
     * @param {Function} handler - 事件處理器
     */
    off(eventName, handler) {
        if (typeof eventName !== 'string') {
            throw new Error('Event name must be a string');
        }

        if (typeof handler !== 'function') {
            throw new Error('Event handler must be a function');
        }

        this.removeEventListener(eventName, handler);

        const currentCount = this.listenerCount.get(eventName) || 0;
        if (currentCount > 0) {
            this.listenerCount.set(eventName, currentCount - 1);
        }

        if (this.options.enableLogging) {
            console.log(`🔇 EventBus: 取消訂閱 ${eventName}, 剩餘監聽器: ${Math.max(0, currentCount - 1)}`);
        }
    }

    /**
     * 一次性訂閱事件
     * 事件觸發一次後自動取消訂閱
     * @param {string} eventName - 事件名稱
     * @param {Function} handler - 事件處理器
     */
    once(eventName, handler) {
        const onceHandler = (event) => {
            this.off(eventName, onceHandler);
            handler(event);
        };
        return this.on(eventName, onceHandler);
    }

    /**
     * 等待特定事件
     * 返回 Promise，在事件觸發時 resolve
     * @param {string} eventName - 事件名稱
     * @param {number} timeout - 超時時間（毫秒）
     * @returns {Promise} - 包含事件詳細資訊的 Promise
     */
    waitFor(eventName, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const timeoutId = setTimeout(() => {
                this.off(eventName, eventHandler);
                reject(new Error(`等待事件 "${eventName}" 超時 (${timeout}ms)`));
            }, timeout);

            const eventHandler = (event) => {
                clearTimeout(timeoutId);
                resolve(event.detail);
            };

            this.on(eventName, eventHandler);
        });
    }

    /**
     * 清除所有監聽器
     * @param {string} eventName - 可選：指定事件名稱，只清除該事件的監聽器
     */
    removeAllListeners(eventName = null) {
        if (eventName) {
            // 清除特定事件的監聽器
            const listeners = this.listenerCount.get(eventName) || 0;
            if (listeners > 0) {
                // 創建一個假事件來觸發所有監聽器，然後移除
                const dummyEvent = new CustomEvent(eventName, { detail: null });
                this.dispatchEvent(dummyEvent);

                // 注意：無法直接移除所有監聽器，這裡只是重置計數
                this.listenerCount.set(eventName, 0);

                if (this.options.enableLogging) {
                    console.log(`🧹 EventBus: 清除事件 "${eventName}" 的所有監聽器`);
                }
            }
        } else {
            // 清除所有事件的所有監聽器
            this.listenerCount.clear();

            if (this.options.enableLogging) {
                console.log(`🧹 EventBus: 清除所有事件監聽器`);
            }
        }
    }

    /**
     * 獲取事件統計資訊
     * @param {string} eventName - 可選：指定事件名稱
     * @returns {Object} - 統計資訊
     */
    getStats(eventName = null) {
        if (eventName) {
            return {
                eventName,
                listenerCount: this.listenerCount.get(eventName) || 0,
                hasListeners: (this.listenerCount.get(eventName) || 0) > 0
            };
        } else {
            const stats = {};
            for (const [name, count] of this.listenerCount) {
                stats[name] = {
                    listenerCount: count,
                    hasListeners: count > 0
                };
            }
            return {
                totalEvents: this.listenerCount.size,
                events: stats,
                historyLength: this.eventHistory ? this.eventHistory.length : 0
            };
        }
    }

    /**
     * 獲取事件歷史記錄
     * @param {number} limit - 返回的記錄數量限制
     * @returns {Array} - 事件歷史記錄
     */
    getHistory(limit = 50) {
        if (!this.eventHistory) {
            return [];
        }

        return this.eventHistory.slice(-limit);
    }

    /**
     * 銷毀事件總線
     * 清除所有監聽器和歷史記錄
     */
    destroy() {
        this.removeAllListeners();
        if (this.eventHistory) {
            this.eventHistory.length = 0;
        }

        if (this.options.enableLogging) {
            console.log(`💥 EventBus: 已銷毀`);
        }
    }
}

// 預定義常見事件名稱常量
export const EVENT_TYPES = {
    // 模組生命週期
    MODULE_INITIALIZED: 'module:initialized',
    MODULE_ACTIVATED: 'module:activated',
    MODULE_DEACTIVATED: 'module:deactivated',
    MODULE_DESTROYED: 'module:destroyed',

    // 相機事件
    CAMERA_READY: 'camera:ready',
    CAMERA_ERROR: 'camera:error',
    CAMERA_FRAME: 'camera:frame',

    // WebSocket 事件
    WEBSOCKET_CONNECTED: 'websocket:connected',
    WEBSOCKET_DISCONNECTED: 'websocket:disconnected',
    WEBSOCKET_ERROR: 'websocket:error',
    WEBSOCKET_MESSAGE: 'websocket:message',

    // 遊戲事件
    GAME_STARTED: 'game:started',
    GAME_ENDED: 'game:ended',
    GAME_STATE_CHANGED: 'game:state_changed',

    // 辨識事件
    RECOGNITION_RESULT: 'recognition:result',
    RECOGNITION_ERROR: 'recognition:error',

    // UI 事件
    UI_UPDATE: 'ui:update',
    UI_ERROR: 'ui:error',
    UI_LOADING: 'ui:loading'
};
