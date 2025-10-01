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
    if (rpsWebSocket) {
        rpsWebSocket.close();
    }
});

// =============================================================================
// RPS 整合式 WebSocket 遊戲測試功能
// =============================================================================

let rpsWebSocket = null;
let rpsSelectedFile = null;
let rpsCameraStream = null;
let rpsStreamInterval = null;

/**
 * 連接整合式 RPS WebSocket
 */
function rpsConnect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/rps`;

    rpsLog(`🔌 連接整合式 WebSocket: ${wsUrl}`, 'info');

    rpsWebSocket = new WebSocket(wsUrl);

    rpsWebSocket.onopen = () => {
        document.getElementById('rpsConnectionStatus').textContent = '✅ 已連線';
        document.getElementById('rpsConnectionStatus').style.color = '#43e97b';
        document.getElementById('rpsConnectBtn').disabled = true;
        document.getElementById('rpsStartBtn').disabled = false;
        rpsLog('🎮 整合式 WebSocket 連線成功', 'success');
    };

    rpsWebSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            rpsHandleMessage(data);
        } catch (error) {
            rpsLog('❌ 訊息解析錯誤: ' + error.message, 'error');
        }
    };

    rpsWebSocket.onerror = () => {
        rpsLog('❌ WebSocket 錯誤', 'error');
    };

    rpsWebSocket.onclose = () => {
        document.getElementById('rpsConnectionStatus').textContent = '🔴 已斷線';
        document.getElementById('rpsConnectionStatus').style.color = '#f5576c';
        document.getElementById('rpsConnectBtn').disabled = false;
        document.getElementById('rpsStartBtn').disabled = true;
        document.getElementById('rpsStopBtn').disabled = true;
        rpsStopStreaming();
        rpsLog('🔌 整合式 WebSocket 連線已關閉', 'warning');
    };
}

/**
 * 處理 RPS WebSocket 訊息
 */
function rpsHandleMessage(data) {
    // 處理遊戲狀態廣播訊息
    if (data.channel === 'rps_game') {
        rpsLog(`[${data.stage}] ${data.message}`, data.stage);

        switch (data.stage) {
            case 'game_started':
                document.getElementById('rpsStartBtn').disabled = true;
                document.getElementById('rpsStopBtn').disabled = false;
                if (data.data.target_score) {
                    document.getElementById('rpsTargetScore').textContent = data.data.target_score;
                }
                break;

            case 'round_started':
                if (data.data.round) {
                    document.getElementById('rpsRound').textContent = data.data.round;
                }
                break;

            case 'countdown':
                rpsShowCountdown(data.data.count);
                break;

            case 'waiting_player':
                rpsHideCountdown();
                document.getElementById('rpsSubmitBtn').disabled = rpsSelectedFile === null;
                break;

            case 'result':
                if (data.data.scores) {
                    document.getElementById('rpsPlayerScore').textContent = data.data.scores.player;
                    document.getElementById('rpsComputerScore').textContent = data.data.scores.computer;
                }
                break;

            case 'game_finished':
            case 'game_stopped':
                document.getElementById('rpsStartBtn').disabled = false;
                document.getElementById('rpsStopBtn').disabled = true;
                document.getElementById('rpsSubmitBtn').disabled = true;
                break;
        }
    }
    // 處理即時辨識結果
    else if (data.type === 'recognition_result') {
        const gesture = data.gesture;
        const confidence = data.confidence || 0;
        const isValid = data.is_valid !== false;

        if (gesture && gesture !== 'unknown') {
            const emoji = {
                'rock': '✊',
                'paper': '✋',
                'scissors': '✌️'
            }[gesture] || '❓';

            document.getElementById('rpsCurrentGesture').textContent = emoji;
            document.getElementById('rpsCurrentConfidence').textContent = `${(confidence * 100).toFixed(1)}%`;
            document.getElementById('rpsGestureStatus').textContent = isValid ? '辨識中' : '無效';

            rpsLog(`👁️ 即時辨識: ${gesture} ${emoji} (${(confidence * 100).toFixed(1)}%)`, 'success');
        } else {
            document.getElementById('rpsCurrentGesture').textContent = '❓';
            document.getElementById('rpsCurrentConfidence').textContent = '0%';
            document.getElementById('rpsGestureStatus').textContent = '未辨識';
        }
    }
    // 處理控制確認
    else if (data.type === 'control_ack') {
        rpsLog(`✅ 控制確認: ${data.action} - ${data.status}`, 'success');
    }
    // 處理錯誤訊息
    else if (data.type === 'error') {
        rpsLog(`❌ 錯誤: ${data.message}`, 'error');
    }
    // 處理心跳回應
    else if (data.type === 'pong') {
        // 靜默處理心跳
    }
    // 其他未知訊息
    else {
        rpsLog(`⚠️ 未知訊息類型: ${JSON.stringify(data)}`, 'warning');
    }
}

/**
 * 開始遊戲
 */
async function rpsStartGame() {
    try {
        const formData = new FormData();
        formData.append('target_score', 3);

        const response = await fetch('/api/rps/start', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        rpsLog('開始遊戲: ' + JSON.stringify(result), 'api');
    } catch (error) {
        rpsLog('開始遊戲錯誤: ' + error.message, 'error');
    }
}

/**
 * 停止遊戲
 */
async function rpsStopGame() {
    try {
        const response = await fetch('/api/rps/stop', {
            method: 'POST'
        });

        const result = await response.json();
        rpsLog('停止遊戲: ' + JSON.stringify(result), 'api');
    } catch (error) {
        rpsLog('停止遊戲錯誤: ' + error.message, 'error');
    }
}

/**
 * 處理圖片選擇
 */
function rpsHandleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
        rpsLog('請選擇圖片檔案', 'error');
        return;
    }

    rpsSelectedFile = file;
    document.getElementById('rpsSubmitBtn').disabled = false;

    // 顯示預覽
    const reader = new FileReader();
    reader.onload = (e) => {
        const preview = document.getElementById('rpsPreviewImage');
        preview.src = e.target.result;
        document.getElementById('rpsPreview').style.display = 'block';
    };
    reader.readAsDataURL(file);

    rpsLog('已選擇檔案: ' + file.name, 'info');
}

/**
 * 提交手勢
 */
async function rpsSubmitGesture() {
    if (!rpsSelectedFile) {
        rpsLog('請先選擇圖片', 'error');
        return;
    }

    try {
        const formData = new FormData();
        formData.append('file', rpsSelectedFile);

        rpsLog('正在上傳並辨識...', 'info');

        const response = await fetch('/api/rps/submit', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.status === 'success') {
            const emoji = {
                'rock': '✊',
                'paper': '✋',
                'scissors': '✌️'
            }[result.gesture] || '❓';

            rpsLog(
                `辨識成功: ${result.gesture} ${emoji} (${(result.confidence * 100).toFixed(1)}%)`,
                'success'
            );
        } else {
            rpsLog('辨識失敗: ' + result.message, 'error');
        }
    } catch (error) {
        rpsLog('提交手勢錯誤: ' + error.message, 'error');
    }
}

/**
 * 顯示倒數
 */
function rpsShowCountdown(count) {
    const display = document.getElementById('rpsCountdownDisplay');
    const number = document.getElementById('rpsCountdownNumber');
    number.textContent = count;
    display.style.display = 'block';
}

/**
 * 隱藏倒數
 */
function rpsHideCountdown() {
    document.getElementById('rpsCountdownDisplay').style.display = 'none';
}

/**
 * 記錄日誌
 */
function rpsLog(message, type = 'info') {
    const logArea = document.getElementById('rpsLogArea');
    const time = new Date().toLocaleTimeString('zh-TW');

    const colors = {
        'info': '#666',
        'success': '#43e97b',
        'error': '#f5576c',
        'warning': '#ffa500',
        'api': '#667eea',
        'countdown': '#ffa500',
        'result': '#43e97b'
    };

    const color = colors[type] || '#666';

    const entry = document.createElement('div');
    entry.style.cssText = `
        padding: 8px;
        margin-bottom: 5px;
        border-left: 3px solid ${color};
        background: white;
        border-radius: 4px;
        font-size: 13px;
    `;
    entry.innerHTML = `<span style="color: #999;">[${time}]</span> <span style="color: ${color};">${message}</span>`;

    logArea.insertBefore(entry, logArea.firstChild);

    // 限制日誌數量
    while (logArea.children.length > 50) {
        logArea.removeChild(logArea.lastChild);
    }
}

/**
 * 清空日誌
 */
function rpsClearLog() {
    const logArea = document.getElementById('rpsLogArea');
    logArea.innerHTML = '<div style="color: #999;">日誌已清空</div>';
}

/**
 * 啟動攝影機
 */
async function rpsStartCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480 }
        });

        rpsCameraStream = stream;
        const video = document.getElementById('rpsTestVideo');
        video.srcObject = stream;
        video.style.display = 'block';

        document.getElementById('rpsCameraStartBtn').disabled = true;
        document.getElementById('rpsCameraStopBtn').disabled = false;
        document.getElementById('rpsStreamStartBtn').disabled = false;

        rpsLog('📹 攝影機已啟動', 'success');
    } catch (error) {
        rpsLog('❌ 啟動攝影機失敗: ' + error.message, 'error');
    }
}

/**
 * 停止攝影機
 */
function rpsStopCamera() {
    if (rpsCameraStream) {
        rpsCameraStream.getTracks().forEach(track => track.stop());
        rpsCameraStream = null;
    }

    const video = document.getElementById('rpsTestVideo');
    video.srcObject = null;
    video.style.display = 'none';

    document.getElementById('rpsCameraStartBtn').disabled = false;
    document.getElementById('rpsCameraStopBtn').disabled = true;
    document.getElementById('rpsStreamStartBtn').disabled = true;
    document.getElementById('rpsStreamStopBtn').disabled = true;

    rpsStopStreaming();
    rpsLog('📷 攝影機已停止', 'info');
}

/**
 * 開始串流
 */
function rpsStartStreaming() {
    if (!rpsCameraStream || !rpsWebSocket || rpsWebSocket.readyState !== WebSocket.OPEN) {
        rpsLog('❌ 無法開始串流：攝影機或 WebSocket 未就緒', 'error');
        return;
    }

    const video = document.getElementById('rpsTestVideo');
    const canvas = document.createElement('canvas');
    canvas.width = 640;
    canvas.height = 480;
    const ctx = canvas.getContext('2d');

    rpsStreamInterval = setInterval(() => {
        if (!rpsCameraStream || !rpsWebSocket || rpsWebSocket.readyState !== WebSocket.OPEN) {
            rpsStopStreaming();
            return;
        }

        ctx.drawImage(video, 0, 0, 640, 480);
        const imageData = canvas.toDataURL('image/jpeg', 0.7);

        rpsWebSocket.send(JSON.stringify({
            type: 'frame',
            image: imageData,
            timestamp: Date.now() / 1000
        }));
    }, 200); // 5 FPS

    document.getElementById('rpsStreamStartBtn').disabled = true;
    document.getElementById('rpsStreamStopBtn').disabled = false;
    document.getElementById('rpsTestGestureBtn').disabled = false;
    document.getElementById('rpsSimulateGestureBtn').disabled = false;

    rpsLog('🎥 開始影像串流 (5 FPS)', 'success');
}

/**
 * 停止串流
 */
function rpsStopStreaming() {
    if (rpsStreamInterval) {
        clearInterval(rpsStreamInterval);
        rpsStreamInterval = null;
    }

    document.getElementById('rpsStreamStartBtn').disabled = false;
    document.getElementById('rpsStreamStopBtn').disabled = true;
    document.getElementById('rpsTestGestureBtn').disabled = true;
    document.getElementById('rpsSimulateGestureBtn').disabled = true;

    rpsLog('🎬 停止影像串流', 'info');
}

/**
 * 測試手勢辨識
 */
function rpsTestGesture() {
    if (!rpsWebSocket || rpsWebSocket.readyState !== WebSocket.OPEN) {
        rpsLog('❌ WebSocket 未連接', 'error');
        return;
    }

    rpsLog('🧪 測試手勢辨識中...', 'info');

    // 模擬發送一個測試幀
    const testImage = 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcUFhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k=';

    rpsWebSocket.send(JSON.stringify({
        type: 'frame',
        image: testImage,
        timestamp: Date.now() / 1000
    }));
}

/**
 * 模擬隨機手勢
 */
function rpsSimulateGesture() {
    if (!rpsWebSocket || rpsWebSocket.readyState !== WebSocket.OPEN) {
        rpsLog('❌ WebSocket 未連接', 'error');
        return;
    }

    const gestures = ['rock', 'paper', 'scissors'];
    const randomGesture = gestures[Math.floor(Math.random() * gestures.length)];

    rpsLog(`🎲 模擬手勢提交: ${randomGesture}`, 'info');

    rpsWebSocket.send(JSON.stringify({
        type: 'submit_gesture',
        gesture: randomGesture,
        confidence: 0.85
    }));
}

/**
 * 重置統計
 */
function rpsResetStats() {
    document.getElementById('rpsRound').textContent = '0';
    document.getElementById('rpsPlayerScore').textContent = '0';
    document.getElementById('rpsComputerScore').textContent = '0';
    document.getElementById('rpsTargetScore').textContent = '3';
    document.getElementById('rpsCurrentGesture').textContent = '❓';
    document.getElementById('rpsCurrentConfidence').textContent = '0%';
    document.getElementById('rpsGestureStatus').textContent = '未辨識';

    rpsLog('📊 統計已重置', 'info');
}

/**
 * 斷開 WebSocket 連接
 */
function rpsDisconnect() {
    if (rpsWebSocket) {
        rpsWebSocket.close();
        rpsWebSocket = null;
    }

    rpsStopCamera();
    rpsStopStreaming();

    document.getElementById('rpsConnectionStatus').textContent = '🔴 已斷線';
    document.getElementById('rpsConnectionStatus').style.color = '#f5576c';
    document.getElementById('rpsConnectBtn').disabled = false;
    document.getElementById('rpsStartBtn').disabled = true;
    document.getElementById('rpsStopBtn').disabled = true;

    rpsLog('🔌 已斷開整合式 WebSocket 連接', 'warning');
}
