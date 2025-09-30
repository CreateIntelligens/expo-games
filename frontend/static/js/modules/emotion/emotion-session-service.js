/**
 * =============================================================================
 * emotion-session-service.js - 情緒分析會話服務
 *
 * 管理情緒分析的 WebSocket 會話，處理特定的訊息格式和協議
 * 封裝 WebSocketTransport，提供情緒分析專用的 API
 * =============================================================================
 */

import { WebSocketTransport } from '../shared/transport/websocket-transport.js';

/**
 * 情緒分析會話服務類別
 * 處理情緒分析特定的 WebSocket 通訊協議
 */
export class EmotionSessionService extends EventTarget {
    constructor() {
        super();

        // 使用共享的 WebSocket 傳輸層
        this.transport = new WebSocketTransport();
        this.isActive = false;
        this.setupTransportEvents();
    }

    /**
     * 設置傳輸層事件監聽
     */
    setupTransportEvents() {
        this.transport.addEventListener('open', () => {
            console.log('✅ 情緒分析會話已建立');
            this.isActive = true;
            this.dispatchEvent(new CustomEvent('sessionReady'));
        });

        this.transport.addEventListener('message', (event) => {
            this.handleMessage(event.detail);
        });

        this.transport.addEventListener('error', (event) => {
            console.error('❌ 情緒分析會話錯誤:', event.detail);
            this.dispatchEvent(new CustomEvent('sessionError', { detail: event.detail }));
        });

        this.transport.addEventListener('close', (event) => {
            console.log('🔌 情緒分析會話已關閉');
            this.isActive = false;
            this.dispatchEvent(new CustomEvent('sessionClosed', { detail: event.detail }));
        });

        this.transport.addEventListener('heartbeatTimeout', () => {
            console.log('💔 情緒分析會話心跳超時');
            this.dispatchEvent(new CustomEvent('heartbeatTimeout'));
        });

        this.transport.addEventListener('reconnected', () => {
            console.log('🔄 情緒分析會話重連成功');
            this.dispatchEvent(new CustomEvent('sessionReconnected'));
        });
    }

    /**
     * 開始情緒分析會話
     * @param {string} wsUrl - WebSocket URL，預設為 /ws/emotion
     */
    start(wsUrl = null) {
        if (!wsUrl) {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            wsUrl = `${protocol}//${window.location.host}/ws/emotion`;
        }

        console.log('🎭 開始情緒分析會話:', wsUrl);
        this.transport.connect(wsUrl);
    }

    /**
     * 停止情緒分析會話
     */
    stop() {
        console.log('🛑 停止情緒分析會話');
        this.isActive = false;
        this.transport.disconnect();
    }

    /**
     * 發送影像幀進行分析
     * @param {string} imageData - Base64 編碼的影像資料
     * @param {number} timestamp - 時間戳
     */
    sendFrame(imageData, timestamp = null) {
        if (!this.isActive || !this.transport.isSocketConnected()) {
            console.warn('⚠️ 會話未就緒，無法發送影像幀');
            return false;
        }

        const message = {
            type: 'frame',
            image: imageData,
            timestamp: timestamp || (Date.now() / 1000)
        };

        return this.transport.send(message);
    }

    /**
     * 發送心跳訊息
     */
    sendHeartbeat() {
        if (!this.isActive || !this.transport.isSocketConnected()) {
            return false;
        }

        return this.transport.send({ type: 'ping' });
    }

    /**
     * 處理接收到的訊息
     * @private
     * @param {Object} data - 接收到的訊息資料
     */
    handleMessage(data) {
        if (!data.type) {
            console.warn('收到無效的情緒分析訊息，缺少type字段:', data);
            return;
        }

        switch (data.type) {
            case 'result':
                // 情緒分析結果
                this.handleAnalysisResult(data);
                break;

            case 'error':
                // 分析錯誤
                this.handleAnalysisError(data);
                break;

            case 'ping':
                // 服務器心跳請求，回應 pong
                this.transport.send({ type: 'pong' });
                break;

            case 'pong':
                // 心跳響應，由底層 transport 處理
                break;

            default:
                console.warn('不支持的情緒分析訊息類型:', data.type, data);
                break;
        }
    }

    /**
     * 處理情緒分析結果
     * @private
     * @param {Object} data - 分析結果資料
     */
    handleAnalysisResult(data) {
        // 記錄分析結果
        if (data.face_detected) {
            const confidence = Math.round((data.confidence || 0) * 100);
            console.log(`🎭 檢測到情緒: ${data.emotion_zh} (${confidence}%)`);
        } else {
            console.log('❓ 未檢測到人臉');
        }

        // 觸發分析結果事件
        this.dispatchEvent(new CustomEvent('analysisResult', {
            detail: {
                emotion: data.emotion,
                emotion_zh: data.emotion_zh,
                confidence: data.confidence,
                face_detected: data.face_detected,
                emoji: data.emoji,
                timestamp: data.timestamp
            }
        }));
    }

    /**
     * 處理分析錯誤
     * @private
     * @param {Object} data - 錯誤資料
     */
    handleAnalysisError(data) {
        const errorMsg = data.message || '未知的分析錯誤';
        console.error('❌ 情緒分析錯誤:', errorMsg);

        this.dispatchEvent(new CustomEvent('analysisError', {
            detail: {
                message: errorMsg,
                code: data.code,
                timestamp: data.timestamp
            }
        }));
    }

    /**
     * 檢查會話是否活躍
     * @returns {boolean} 會話是否活躍
     */
    isSessionActive() {
        return this.isActive && this.transport.isSocketConnected();
    }

    /**
     * 獲取會話狀態
     * @returns {Object} 會話狀態資訊
     */
    getSessionStatus() {
        return {
            isActive: this.isActive,
            isConnected: this.transport.isSocketConnected(),
            readyState: this.transport.getReadyState()
        };
    }

    /**
     * 銷毀會話服務
     */
    destroy() {
        console.log('🗑️ 銷毀情緒分析會話服務');
        this.stop();
        this.transport.destroy();
    }
}
