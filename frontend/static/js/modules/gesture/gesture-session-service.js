/**
 * =============================================================================
 * GestureSessionService - 手勢繪畫會話服務
 * =============================================================================
 *
 * 管理手勢繪畫 WebSocket 會話，包含協議編碼/解碼、消息處理與狀態同步。
 * 依賴共享的 WebSocketTransport 以實現重連與心跳機制。
 * =============================================================================
 */

import WebSocketTransport from '../shared/transport/websocket-transport.js';

export class GestureSessionService {
    constructor() {
        this.transport = null;
        this.transportSubscriptions = [];
        this.sessionId = null;
        this.isActive = false;
        this.eventHandlers = new Map();

        // 會話配置
        this.config = {
            mode: 'gesture_control',
            color: 'black',
            canvasSize: [640, 480],
            frameInterval: 1000 / 20, // 20 FPS
            wsUrl: this._getWebSocketUrl()
        };

        // 狀態追蹤
        this.currentGesture = 'idle';
        this.fingersUp = [false, false, false, false, false];
        this.strokeCount = 0;
        this.canvasImage = null;
        this.lastFrameTime = 0;

        // 顏色調色盤
        this.colorPalette = {
            black: '#111827',
            red: '#ef4444',
            blue: '#3b82f6',
            green: '#22c55e',
            yellow: '#facc15',
            purple: '#a855f7',
            cyan: '#22d3ee',
            white: '#f9fafb'
        };
    }

    // ===== 事件註冊 =====

    on(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
        return () => this.off(event, handler);
    }

    off(event, handler) {
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            const index = handlers.indexOf(handler);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
        }
    }

    emit(event, data) {
        if (this.eventHandlers.has(event)) {
            this.eventHandlers.get(event).forEach((handler) => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`❌ GestureSessionService event handler error for ${event}:`, error);
                }
            });
        }
    }

    // ===== 連線管理 =====

    _getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}/ws/drawing/gesture`;
    }

    async connect() {
        if (this.transport && this.transport.isReady()) {
            console.log('🎨 手勢會話已連接');
            return;
        }

        if (this.transport) {
            this.disconnect();
        }

        console.log('🔌 連接手勢繪畫會話...', this.config.wsUrl);

        this.transport = new WebSocketTransport({
            reconnectInterval: 3000,
            maxReconnectAttempts: 3,
            connectionTimeout: 10000
        });

        this.transportSubscriptions = [
            this.transport.on('open', () => {
                console.log('✅ 手勢會話連接成功');
            }),
            this.transport.on('message', (data) => {
                this.handleMessage(data);
            }),
            this.transport.on('error', (errorData) => {
                console.error('❌ 手勢會話錯誤:', errorData);
                this.emit('error', errorData);
            }),
            this.transport.on('close', (closeData) => {
                console.log('🔌 手勢會話連接關閉:', closeData);
                this.isActive = false;
                this.sessionId = null;
            }),
            this.transport.on('heartbeatTimeout', () => {
                console.warn('💔 手勢會話心跳超時');
            }),
            this.transport.on('reconnected', () => {
                console.log('🔄 手勢會話已重新連接');
            })
        ];

        await this.transport.connect(this.config.wsUrl);
    }

    async startSession(options = {}) {
        if (!this.transport || !this.transport.isReady()) {
            throw new Error('WebSocket 未連接，請先調用 connect()');
        }

        this.config = { ...this.config, ...options };

        console.log('🎨 開始手勢繪畫會話...', this.config);

        const message = {
            type: 'start_gesture_drawing',
            mode: this.config.mode,
            color: this.config.color,
            canvas_size: this.config.canvasSize,
            timestamp: Date.now() / 1000
        };

        this.transport.send(message);

        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error('開始繪畫會話超時'));
            }, 5000);

            const handleResponse = (data) => {
                if (data.type === 'drawing_started') {
                    clearTimeout(timeout);
                    this.sessionId = data.session_id;
                    this.isActive = true;
                    console.log('✅ 手勢繪畫會話已開始，session_id:', this.sessionId);
                    this.emit('sessionStarted', { sessionId: this.sessionId });
                    resolve(this.sessionId);
                } else if (data.type === 'error') {
                    clearTimeout(timeout);
                    reject(new Error(data.message));
                }
            };

            const unsubscribe = this.on('_tempResponse', handleResponse);

            setTimeout(() => {
                unsubscribe();
            }, 6000);
        });
    }

    async stopSession() {
        if (!this.isActive || !this.transport || !this.transport.isReady()) {
            console.log('🎨 手勢會話未啟動，無需停止');
            return;
        }

        console.log('🛑 停止手勢繪畫會話...');

        const message = {
            type: 'stop_drawing',
            session_id: this.sessionId,
            timestamp: Date.now() / 1000
        };

        this.transport.send(message);

        this.isActive = false;
        this.sessionId = null;

        // 立即斷開 WebSocket 連接以避免後續的心跳消息
        if (this.transport) {
            this.transport.disconnect();
            this.transport = null;
        }

        this.emit('sessionStopped');
    }

    sendFrame(frameData) {
        if (!this.isActive || !this.transport || !this.transport.isReady()) {
            return false;
        }

        const now = Date.now();
        if (now - this.lastFrameTime < this.config.frameInterval) {
            return false;
        }

        const message = {
            type: 'camera_frame',
            image: frameData,
            timestamp: now / 1000
        };

        const success = this.transport.send(message);
        if (success) {
            this.lastFrameTime = now;
        }

        return success;
    }

    async changeColor(colorName) {
        if (!this.isActive || !this.transport || !this.transport.isReady()) {
            throw new Error('會話未啟動');
        }

        const message = {
            type: 'change_color',
            color: colorName,
            timestamp: Date.now() / 1000
        };

        console.log('🎨 變更繪畫顏色:', colorName);
        this.transport.send(message);
        this.config.color = colorName;
    }

    async changeBrushSize(size) {
        if (!this.isActive || !this.transport || !this.transport.isReady()) {
            throw new Error('會話未啟動');
        }

        const message = {
            type: 'change_brush_size',
            size,
            timestamp: Date.now() / 1000
        };

        console.log('🖌️ 變更筆刷大小:', size);
        this.transport.send(message);
    }

    async clearCanvas() {
        if (!this.isActive || !this.transport || !this.transport.isReady()) {
            throw new Error('會話未啟動');
        }

        const message = {
            type: 'clear_canvas',
            timestamp: Date.now() / 1000
        };

        console.log('🗑️ 清空畫布');
        this.transport.send(message);

        this.strokeCount = 0;
        this.canvasImage = null;
    }

    handleMessage(data) {
        const messageType = data.type;
        console.log('📨 手勢會話收到消息:', messageType, Object.keys(data));

        switch (messageType) {
            case 'drawing_started':
            case 'drawing_stopped':
            case 'error':
                this.emit('_tempResponse', data);
                break;
            case 'color_changed':
                this.config.color = data.color;
                console.log('🎨 顏色已變更:', data.color);
                break;
            case 'connection_confirmed':
            case 'opened':
                console.log('✅ 會話連接已確認');
                break;
            case 'gesture_status':
                // 手勢狀態更新消息，在下方統一處理
                console.debug('👋 收到手勢狀態更新');
                break;
            case 'recognition_result':
                // AI 識別結果消息，在下方統一處理
                console.debug('🔍 收到圖形識別結果');
                break;
            case 'clear_canvas':
                // 畫布清空消息
                console.debug('🗑️ 畫布已清空');
                break;
            case 'ping':
                // 處理心跳 ping 消息，靜默忽略
                console.debug('💓 收到心跳 ping');
                break;
            case 'pong':
                // 處理心跳 pong 消息，靜默忽略
                console.debug('💓 收到心跳 pong');
                break;
            default:
                console.warn('⚠️ 未知的消息類型:', messageType, data);
                break;
        }

        if (data.current_gesture !== undefined || data.fingers_up !== undefined) {
            this.currentGesture = data.current_gesture || 'idle';
            this.fingersUp = data.fingers_up || [false, false, false, false, false];

            // 詳細顯示手指狀態
            const fingersCount = this.fingersUp.filter(f => f).length;
            console.log(`👆 手勢: ${this.currentGesture}, 手指狀態: [${this.fingersUp.join(', ')}], 總數: ${fingersCount}`);

            // 處理顏色變更通知
            if (data.color_changed && data.new_color) {
                console.log(`🎨 顏色已變更為: ${data.new_color}`);
                this.config.color = data.new_color;
                this.emit('colorChanged', { color: data.new_color });
            }

            // 處理畫布清空通知
            if (data.canvas_cleared) {
                console.log('🗑️ 畫布已清空');
                this.strokeCount = 0;
                this.emit('canvasCleared');
            }

            this.emit('gestureUpdate', {
                gesture: this.currentGesture,
                fingersUp: this.fingersUp,
                position: data.drawing_position
            });
        }

        if (data.canvas_base64 !== undefined || data.stroke_count !== undefined) {
            if (data.canvas_base64) {
                this.canvasImage = data.canvas_base64;
            }
            if (typeof data.stroke_count === 'number') {
                this.strokeCount = data.stroke_count;
            }

            this.emit('canvasUpdate', {
                canvasImage: this.canvasImage,
                strokeCount: this.strokeCount,
                currentColor: data.current_color || this.config.color,
                drawingPosition: data.drawing_position
            });
        }

        if (data.recognized_shape !== undefined || data.confidence !== undefined) {
            this.emit('recognitionResult', {
                shape: data.recognized_shape,
                confidence: data.confidence,
                message: data.message
            });
        }

        // 處理顏色選擇事件
        if (data.selected_color) {
            this.config.color = data.selected_color;
            this.emit('colorChanged', {
                color: data.selected_color,
                position: data.position
            });
        }

        if (messageType === 'error') {
            this.emit('error', {
                message: data.message,
                code: data.code
            });
        }
    }

    getSessionStatus() {
        return {
            isActive: this.isActive,
            sessionId: this.sessionId,
            currentGesture: this.currentGesture,
            fingersUp: this.fingersUp,
            strokeCount: this.strokeCount,
            currentColor: this.config.color,
            canvasSize: this.config.canvasSize,
            transportStatus: this.transport ? this.transport.getStatus() : null
        };
    }

    resolveColor(colorName) {
        const key = (colorName || 'black').toLowerCase();
        return this.colorPalette[key] || '#f9fafb';
    }

    getAvailableColors() {
        return Object.entries(this.colorPalette).map(([name, hex]) => ({ name, hex }));
    }

    disconnect() {
        console.log('🔌 斷開手勢繪畫會話');

        if (this.isActive) {
            this.stopSession().catch(console.error);
        }

        if (this.transportSubscriptions.length) {
            this.transportSubscriptions.forEach((unsubscribe) => {
                try {
                    unsubscribe?.();
                } catch (error) {
                    console.error('❌ 移除手勢會話監聽器失敗:', error);
                }
            });
            this.transportSubscriptions = [];
        }

        if (this.transport) {
            this.transport.disconnect();
            this.transport = null;
        }

        this.sessionId = null;
        this.isActive = false;
    }

    destroy() {
        console.log('🗑️ 清理手勢會話服務資源');
        this.disconnect();
        this.eventHandlers.clear();

        this.currentGesture = 'idle';
        this.fingersUp = [false, false, false, false, false];
        this.strokeCount = 0;
        this.canvasImage = null;
    }
}

export default GestureSessionService;
