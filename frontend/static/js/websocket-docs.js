/**
 * =============================================================================
 * websocket-docs.js - WebSocket API 文檔互動功能
 *
 * 提供 WebSocket API 文檔頁面的互動測試功能，
 * 包含連接測試、日誌記錄、狀態顯示和端點展開/收起等功能。
 *
 * 主要功能：
 * - WebSocket 連接測試和狀態監控
 * - 即時訊息日誌記錄和顯示
 * - 端點文檔的互動展開/收起
 * - 自動 URL 生成和錯誤處理
 * - 頁面載入和離開時的資源清理
 * =============================================================================
 */

let websocket = null;
let reconnectInterval = null;

// DOM 元素
const connectionStatus = document.getElementById('connectionStatus');
const connectBtn = document.getElementById('connectBtn');
const disconnectBtn = document.getElementById('disconnectBtn');
const clearLogBtn = document.getElementById('clearLogBtn');
const logArea = document.getElementById('logArea');
const wsUrlInput = document.getElementById('wsUrl');

// 事件監聽器 - 在 DOMContentLoaded 中設置

/**
 * 切換端點內容顯示
 * @param {HTMLElement} header - 端點標題元素，包含展開/收起箭頭
 * @description 切換 WebSocket 端點文檔的詳細內容顯示狀態
 *              點擊標題時展開或收起對應的內容區域
 */
function toggleEndpoint(header) {
    const content = header.nextElementSibling;
    const arrow = header.querySelector('.toggle-arrow');

    content.classList.toggle('active');
    arrow.classList.toggle('active');
}

/**
 * 連接 WebSocket
 * @description 建立 WebSocket 連接並設置事件處理器
 *              包含連接狀態更新、訊息處理和錯誤處理
 * @note 如果已經有活躍連接，會跳過重複連接
 * @note 自動處理 wss:// 和 ws:// 協議選擇
 */
function connectWebSocket() {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        log('已經連接了');
        return;
    }

    const url = wsUrlInput.value;
    log(`嘗試連接: ${url}`);

    updateConnectionStatus('connecting');

    try {
        websocket = new WebSocket(url);

        websocket.onopen = function(event) {
            log('✅ WebSocket 連接成功');
            updateConnectionStatus('connected');
            if (connectBtn) connectBtn.disabled = true;
            if (disconnectBtn) disconnectBtn.disabled = false;
        };

        websocket.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                log(`📨 收到訊息: ${JSON.stringify(data, null, 2)}`);
            } catch (e) {
                log(`📨 收到文字訊息: ${event.data}`);
            }
        };

        websocket.onclose = function(event) {
            log(`🔌 連接關閉: 代碼=${event.code}, 原因=${event.reason}`);
            updateConnectionStatus('disconnected');
            if (connectBtn) connectBtn.disabled = false;
            if (disconnectBtn) disconnectBtn.disabled = true;
        };

        websocket.onerror = function(error) {
            log(`❌ WebSocket 錯誤: ${error}`);
            updateConnectionStatus('disconnected');
        };

    } catch (error) {
        log(`❌ 連接失敗: ${error.message}`);
        updateConnectionStatus('disconnected');
    }
}

/**
 * 斷開 WebSocket 連接
 * @description 正常關閉 WebSocket 連接並更新 UI 狀態
 *              使用關閉代碼 1000 (正常關閉) 和原因說明
 * @note 會自動清理 WebSocket 實例並重新啟用連接按鈕
 */
function disconnectWebSocket() {
    if (websocket) {
        log('🔌 正在關閉連接...');
        websocket.close(1000, '用戶手動關閉');
        websocket = null;
    }
    if (connectBtn) connectBtn.disabled = false;
    if (disconnectBtn) disconnectBtn.disabled = true;
}

/**
 * 更新連接狀態顯示
 * @param {string} status - 連接狀態 ('connected', 'disconnected', 'connecting')
 * @description 更新連接狀態指示器的 CSS 類別和工具提示文字
 *              通過視覺變化讓用戶了解當前 WebSocket 連接狀態
 */
function updateConnectionStatus(status) {
    if (connectionStatus) {
        connectionStatus.className = `status-indicator status-${status}`;

        const statusText = {
            'connected': '已連接',
            'disconnected': '未連接',
            'connecting': '連接中'
        };

        connectionStatus.title = statusText[status] || status;
    }
}

/**
 * 添加日誌記錄
 * @param {string} message - 日誌訊息
 * @description 將訊息添加到日誌區域，包含時間戳並自動滾動到底部
 *              用於記錄 WebSocket 連接、訊息收發和錯誤等重要事件
 */
function log(message) {
    if (logArea) {
        const timestamp = new Date().toLocaleTimeString();
        logArea.textContent += `[${timestamp}] ${message}\n`;
        logArea.scrollTop = logArea.scrollHeight;
    }
}

/**
 * 清除日誌
 * @description 清空所有日誌記錄，重新開始記錄新的訊息
 *              用於清理過多的日誌內容或重新開始測試
 */
function clearLog() {
    if (logArea) {
        logArea.textContent = '';
    }
}

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', function() {
    // 設置事件監聽器
    if (connectBtn) {
        connectBtn.addEventListener('click', connectWebSocket);
    }
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectWebSocket);
    }
    if (clearLogBtn) {
        clearLogBtn.addEventListener('click', clearLog);
    }

    // 自動設定 WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    if (wsUrlInput) {
        wsUrlInput.value = `${protocol}//${host}/ws/emotion`;
    }

    updateConnectionStatus('disconnected');
    if (connectBtn) connectBtn.disabled = false;
    if (disconnectBtn) disconnectBtn.disabled = true;

    log('WebSocket API 文檔頁面已載入');
    log('點擊"連接"按鈕來測試 WebSocket 連接');
});

// 頁面離開時清理
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close();
    }
});
