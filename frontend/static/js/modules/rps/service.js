/**
 * RPS Game Service
 * 負責 WebSocket 通訊、遊戲邏輯、API 調用
 */

import { EventBus } from '../../app/event-bus.js';

export class RPSGameService {
    constructor() {
        this.websocket = null;
        this.websocketReadyPromise = null;
        this.isGameActive = false;

        // 串流控制
        this.streamInterval = null;
        this.captureRate = 500; // 每 0.5 秒捕捉一次

        // 手勢追蹤
        this.bestGestureSoFar = null;
        this.bestConfidenceSoFar = 0;
        this.bestUnknownConfidence = 0;
        this.currentGesture = null;
        this.currentConfidence = 0;
        this.bestFrameData = null;
        this.bestFrameConfidence = 0;

        // 遊戲狀態
        this.waitingForGesture = false;
        this.gestureWaitStartTime = 0;
        this.gestureTimeoutTimer = null;
        this.playerGesture = null;
        this.playerImageData = null;
        this.roundNumber = 0;
        this.playerScore = 0;
        this.aiScore = 0;

        // 事件匯流排
        this.bus = new EventBus(['streamResult', 'gameState', 'controlAck', 'gestureSet', 'error']);
    }

    /**
     * 設定事件監聽器
     * @returns {() => void} 解除訂閱函式
     */
    on(event, callback) {
        return this.bus.on(event, callback);
    }

    off(event, callback) {
        return this.bus.off?.(event, callback);
    }

    /**
     * 建立 WebSocket 連線
     */
    async setupWebSocket(cameraService) {
        if (this.websocketReadyPromise) {
            return this.websocketReadyPromise;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/rps`;

        try {
            const ws = new WebSocket(wsUrl);
            this.websocket = ws;

            let rejectFn = null;
            const cleanupPromise = () => {
                this.websocketReadyPromise = null;
                rejectFn = null;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const messageType = data.type || data.stage;

                    switch (messageType) {
                        case 'recognition_result':
                        case 'result':
                            this._handleStreamResult(data);
                            break;
                        case 'game_state':
                            this.bus.emit('gameState', data);
                            break;
                        case 'control_ack':
                            this.bus.emit('controlAck', data);
                            break;
                        case 'gesture_set':
                            console.log(`✅ ${data.message}`);
                            this.bus.emit('gestureSet', data);
                            break;
                        case 'error':
                            console.error('❌ WebSocket 錯誤:', data.message);
                            this.bus.emit('error', data);
                            break;
                        case 'pong':
                            break;
                        default:
                            console.warn('⚠️ 未知的訊息類型:', data);
                    }
                } catch (error) {
                    console.error('❌ WebSocket 訊息解析錯誤:', error);
                }
            };

            ws.onclose = () => {
                console.log('🔌 RPS WebSocket 已關閉');
                if (rejectFn) {
                    rejectFn(new Error('WebSocket closed before ready'));
                }
                cleanupPromise();
                this.websocket = null;
                this.stopStreaming();
                if (this.isGameActive) {
                    console.log('🔄 5秒後嘗試重新連線...');
                    setTimeout(() => {
                        this.setupWebSocket(cameraService).catch((error) => {
                            console.error('❌ RPS WebSocket 重連失敗:', error);
                        });
                    }, 5000);
                }
            };

            this.websocketReadyPromise = new Promise((resolve, reject) => {
                rejectFn = reject;

                ws.onopen = () => {
                    console.log('✅ RPS 整合式 WebSocket 連線成功');
                    cleanupPromise();
                    resolve(ws);

                    ws.onerror = (error) => {
                        console.error('❌ RPS WebSocket 錯誤:', error);
                    };

                    if (this.isGameActive) {
                        this.startStreaming(cameraService);
                    }
                };

                ws.onerror = (error) => {
                    console.error('❌ RPS WebSocket 建立失敗:', error);
                    cleanupPromise();
                    reject(error);
                };
            });

            return this.websocketReadyPromise;
        } catch (error) {
            console.error('建立 WebSocket 連線失敗:', error);
            this.websocketReadyPromise = null;
            this.websocket = null;
            throw error;
        }
    }

    /**
     * 處理即時辨識結果
     */
    _handleStreamResult(data) {
        if (!data) return;

        const messageType = data.type || 'result';

        if (messageType === 'recognition_result' || messageType === 'result') {
            const gesture = data.gesture;
            const confidence = typeof data.confidence === 'number' ? data.confidence : 0;

            console.log(`👁️ 即時辨識: ${gesture} (${(confidence * 100).toFixed(1)}%)`);

            // 追蹤所有手勢
            if (this.isGameActive && gesture) {
                if (gesture !== 'unknown') {
                    if (confidence > this.bestConfidenceSoFar) {
                        this.bestGestureSoFar = gesture;
                        this.bestConfidenceSoFar = confidence;
                        console.log(`📈 更新最佳手勢: ${gesture} (${(confidence * 100).toFixed(1)}%)`);
                    }
                } else {
                    if (!this.bestUnknownConfidence || confidence > this.bestUnknownConfidence) {
                        this.bestUnknownConfidence = confidence;
                    }
                }
            }

            const isValid = data.is_valid ?? (gesture && gesture !== 'unknown');
            this.currentGesture = gesture;
            this.currentConfidence = confidence;

            // 觸發 StreamResult 事件
            this.bus.emit('streamResult', { gesture, confidence, isValid });
        } else if (messageType === 'error') {
            console.error('❌ 串流錯誤:', data.message);
            this.bus.emit('error', data);
        }
    }

    /**
     * 開始串流影像
     */
    startStreaming(cameraService) {
        console.log('📸 嘗試開始串流影像...', {
            hasInterval: !!this.streamInterval,
            isGameActive: this.isGameActive,
            cameraActive: cameraService.isActive(),
            wsReady: this.websocket?.readyState === WebSocket.OPEN
        });

        if (this.streamInterval) {
            console.log('⚠️ 串流已在進行中');
            return;
        }
        if (!this.isGameActive) {
            console.log('⚠️ 遊戲未啟動');
            return;
        }
        if (!cameraService.isActive()) {
            console.log('⚠️ 攝影機未啟動');
            return;
        }
        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            console.log('⚠️ WebSocket 未連接');
            return;
        }

        console.log('✅ 開始串流影像');

        this.streamInterval = setInterval(() => {
            if (!this.isGameActive) return;
            if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) return;
            if (!cameraService.isActive()) return;

            const imageData = cameraService.captureFrame('jpeg', 0.7, { mirror: true });

            if (imageData) {
                this.websocket.send(JSON.stringify({
                    type: 'frame',
                    image: imageData,
                    timestamp: Date.now()
                }));
            }
        }, 500);
    }

    /**
     * 停止串流影像
     */
    stopStreaming() {
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
    }

    /**
     * 發送遊戲控制指令
     */
    sendGameControl(action, data = {}) {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'game_control',
                action: action,
                ...data
            }));
        }
    }

    /**
     * 發送未偵測到手勢訊息
     */
    sendNoGestureDetected(cameraService) {
        // 捕捉當前畫面
        this.playerImageData = cameraService.captureFrame('jpeg', 0.8, { mirror: true });
        if (this.playerImageData) {
            this.bestFrameData = this.playerImageData;
            this.bestFrameConfidence = this.bestConfidenceSoFar || 0;
        }

        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send(JSON.stringify({
                type: 'no_gesture_detected',
                message: '未偵測到手勢',
                unknown_confidence: this.bestUnknownConfidence || 0,
                timestamp: Date.now()
            }));
        }
    }

    /**
     * 重置遊戲狀態
     */
    resetGameState() {
        this.bestGestureSoFar = null;
        this.bestConfidenceSoFar = 0;
        this.bestUnknownConfidence = 0;
        this.currentGesture = null;
        this.currentConfidence = 0;
        this.waitingForGesture = false;
        this.playerGesture = null;
        this.playerImageData = null;
        this.bestFrameData = null;
        this.bestFrameConfidence = 0;
    }

    /**
     * 關閉 WebSocket
     */
    closeWebSocket() {
        this.stopStreaming();
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
    }
}
