/**
 * =============================================================================
 * websocket-transport.js - WebSocket 傳輸模組
 *
 * 提供統一的 WebSocket 操作 API，包含連線管理、自動重連與心跳機制。
 * =============================================================================
 */

const DEFAULT_OPTIONS = {
    reconnectInterval: 3000,
    maxReconnectAttempts: 3,
    connectionTimeout: 10000
};

export class WebSocketTransport extends EventTarget {
    constructor(options = {}) {
        super();

        this.options = { ...DEFAULT_OPTIONS, ...options };
        this.streamWebSocket = null;
        this.isConnected = false;
        this.shouldReconnect = true;
        this.reconnectAttempts = 0;
        this.url = null;

        this.heartbeatInterval = null;
        this.lastHeartbeat = Date.now();

        this.pendingConnectPromise = null;
    }

    on(event, handler) {
        const wrapped = (evt) => handler(evt?.detail ?? evt);
        this.addEventListener(event, wrapped);
        return () => this.removeEventListener(event, wrapped);
    }

    off(event, handler) {
        this.removeEventListener(event, handler);
    }

    async connect(wsUrl) {
        this.url = wsUrl || this.url;
        if (!this.url) {
            throw new Error('WebSocket URL 未設置');
        }

        if (this.isReady()) {
            return;
        }

        if (this.pendingConnectPromise) {
            return this.pendingConnectPromise;
        }

        this.shouldReconnect = true;

        this.pendingConnectPromise = new Promise((resolve, reject) => {
            const socket = new WebSocket(this.url);
            this.streamWebSocket = socket;
            let settled = false;

            const cleanupPending = () => {
                if (!settled) {
                    settled = true;
                    this.pendingConnectPromise = null;
                }
            };

            const timeoutId = setTimeout(() => {
                if (!settled) {
                    const timeoutError = new Error('WebSocket 連接超時');
                    this.dispatchEvent(new CustomEvent('error', { detail: timeoutError }));
                    try {
                        socket.close();
                    } catch (error) {
                        console.error('❌ 關閉逾時 WebSocket 失敗:', error);
                    }
                }
            }, this.options.connectionTimeout);

            socket.onopen = () => {
                settled = true;
                clearTimeout(timeoutId);

                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.lastHeartbeat = Date.now();
                this.startHeartbeat();
                this.dispatchEvent(new CustomEvent('open'));

                this.pendingConnectPromise = null;
                resolve();
            };

            socket.onmessage = (event) => {
                this.lastHeartbeat = Date.now();

                if (event.data === 'pong' || event.data === '"pong"') {
                    return;
                }

                try {
                    const parsed = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
                    this.dispatchEvent(new CustomEvent('message', { detail: parsed }));
                } catch (error) {
                    console.error('❌ 解析 WebSocket 訊息失敗:', error);
                    this.dispatchEvent(new CustomEvent('error', { detail: error }));
                }
            };

            socket.onerror = (event) => {
                const error = event?.error || new Error('WebSocket 連接錯誤');
                this.dispatchEvent(new CustomEvent('error', { detail: error }));

                if (!settled) {
                    settled = true;
                    clearTimeout(timeoutId);
                    this.pendingConnectPromise = null;
                    reject(error);
                }
            };

            socket.onclose = (event) => {
                clearTimeout(timeoutId);
                this.isConnected = false;
                this.stopHeartbeat();
                this.dispatchEvent(new CustomEvent('close', { detail: event }));

                const shouldReconnect = this._shouldAttemptReconnect(event);

                if (!settled) {
                    settled = true;
                    this.pendingConnectPromise = null;
                    if (shouldReconnect) {
                        this._scheduleReconnect(false);
                    }
                    reject(new Error(event.reason || 'WebSocket 連接關閉'));
                } else if (shouldReconnect) {
                    this._scheduleReconnect(true);
                } else if (this.shouldReconnect === false) {
                    this.dispatchEvent(new CustomEvent('disconnect'));
                }
            };
        }).finally(() => {
            if (this.pendingConnectPromise) {
                this.pendingConnectPromise = null;
            }
        });

        return this.pendingConnectPromise;
    }

    send(payload) {
        if (!this.isReady()) {
            console.warn('⚠️ WebSocket 未連接，無法發送訊息');
            return false;
        }

        try {
            const message = typeof payload === 'string' ? payload : JSON.stringify(payload);
            this.streamWebSocket.send(message);
            return true;
        } catch (error) {
            this.dispatchEvent(new CustomEvent('error', { detail: error }));
            return false;
        }
    }

    disconnect(code = 1000) {
        this.shouldReconnect = false;
        this.stopHeartbeat();

        if (this.streamWebSocket) {
            try {
                this.streamWebSocket.close(code);
            } catch (error) {
                console.error('❌ 主動斷開 WebSocket 失敗:', error);
            }
            this.streamWebSocket = null;
        }

        this.isConnected = false;
        this.pendingConnectPromise = null;
    }

    startHeartbeat() {
        this.stopHeartbeat();

        this.heartbeatInterval = setInterval(() => {
            if (!this.isReady()) {
                return;
            }

            if (Date.now() - this.lastHeartbeat > this.options.connectionTimeout) {
                this.dispatchEvent(new CustomEvent('heartbeatTimeout'));
                try {
                    this.streamWebSocket.close();
                } catch (error) {
                    console.error('❌ 關閉逾時 WebSocket 失敗:', error);
                }
                return;
            }

            this.send({ type: 'ping' });
        }, 5000);
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }

    isReady() {
        return !!this.streamWebSocket && this.streamWebSocket.readyState === WebSocket.OPEN;
    }

    isSocketConnected() {
        return this.isReady();
    }

    getStatus() {
        return {
            url: this.url,
            isConnected: this.isReady(),
            readyState: this.streamWebSocket ? this.streamWebSocket.readyState : WebSocket.CLOSED,
            reconnectAttempts: this.reconnectAttempts
        };
    }

    destroy() {
        this.shouldReconnect = false;
        this.disconnect();
    }

    _shouldAttemptReconnect(event) {
        if (!this.shouldReconnect) {
            return false;
        }
        return event?.code !== 1000;
    }

    _scheduleReconnect(fromCloseEvent = false) {
        if (!this.shouldReconnect) {
            return;
        }

        if (this.options.maxReconnectAttempts !== undefined && this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            this.dispatchEvent(new CustomEvent('reconnectFailed'));
            return;
        }

        this.reconnectAttempts += 1;

        setTimeout(() => {
            this.connect().then(() => {
                this.dispatchEvent(new CustomEvent('reconnected', {
                    detail: { attempts: this.reconnectAttempts }
                }));
            }).catch((error) => {
                this.dispatchEvent(new CustomEvent('error', { detail: error }));
            });
        }, this.options.reconnectInterval);

        if (fromCloseEvent) {
            this.dispatchEvent(new CustomEvent('reconnecting', {
                detail: { attempts: this.reconnectAttempts }
            }));
        }
    }
}

export default WebSocketTransport;
