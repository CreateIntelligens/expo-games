// =============================================================================
// rps-game.js - 石頭剪刀布遊戲模組（簡化介面版本）
// 使用攝影機即時辨識 + WebSocket 串流，移除文字提示和歷史記錄
// 僅顯示：攝影機畫面 + 倒數動畫 + 對戰結果 + 結果訊息
// =============================================================================

import { CameraService } from './shared/camera/camera-service.js';
import { STATUS_TYPES } from '../common/constants.js';

export class RPSGameModule {
    constructor(statusManager) {
        this.statusManager = statusManager;
        this.isGameActive = false;
        this.websocket = null;
        this.websocketReadyPromise = null;
        this.cameraService = new CameraService();
        
        // 遊戲狀態
        this.currentStage = 'idle';  // idle, countdown, waiting, result
        this.countdownValue = 3;
        this.playerGesture = null;
        this.aiGesture = null;
        this.playerScore = 0;
        this.aiScore = 0;
        this.roundNumber = 0;

        // 串流控制
        this.captureInterval = null;
        this.captureRate = 500; // 每0.5秒捕捉一次

        // 即時辨識狀態
        this.currentGesture = null;
        this.currentConfidence = 0;
        this.waitingForGesture = false;  // 是否正在等待玩家出拳
        this.gestureWaitStartTime = 0;   // 開始等待手勢的時間
        this.gestureTimeoutTimer = null; // 超時計時器
        this.bestGestureSoFar = null;    // 目前為止最佳手勢
        this.bestConfidenceSoFar = 0;    // 目前為止最高信心度

        // WebSocket 串流
        this.streamInterval = null;

        // DOM 元素
        this.elements = {};

        this.init();
    }

    init() {
        console.log('✅ RPS Game Module (Camera) initialized');
        this.setupDOM();
        this.setupEventListeners();
        this.setupModeListener();
        // WebSocket 會在開始遊戲時才建立
    }

    setupModeListener() {
        // 監聽模式切換事件
        document.addEventListener('modeSwitched', (event) => {
            if (event.detail.mode === 'rps') {
                // 切換到 RPS 模式時啟動攝影機
                console.log('📹 RPS 模式啟動，準備攝影機...');
                this.initCamera().catch(error => {
                    console.error('❌ 攝影機啟動失敗:', error);
                });
            } else {
                // 切換到其他模式時停止攝影機
                if (this.cameraService.isActive()) {
                    console.log('📹 停止 RPS 攝影機');
                    this.cameraService.stop();
                }
            }
        });
    }

    async initCamera() {
        try {
            await this.cameraService.start();
            await this.cameraService.attachToVideoElement(this.elements.video, {
                mirror: true
            });

            // 顯示攝影機畫面
            if (this.elements.video) {
                this.elements.video.style.display = 'block';
            }

            console.log('📹 攝影機已就緒');

        } catch (error) {
            console.error('❌ 攝影機初始化失敗:', error);
            const message = this.cameraService.getErrorMessage(error);
            this.statusManager.update(message, STATUS_TYPES.ERROR);
            throw error;
        }
    }

    setupDOM() {
        // 控制按鈕
        this.elements.startButton = document.getElementById('start-rps-btn');
        this.elements.stopButton = document.getElementById('stop-rps-btn');
        
        // 遊戲顯示區域
        this.elements.gameDisplay = document.getElementById('rps-game-display');
        
        // 攝影機元素
        this.elements.video = document.getElementById('rps-video');
        this.elements.canvas = document.getElementById('rps-canvas');
        
        // 遊戲資訊
        this.elements.playerGesture = document.getElementById('rps-player-gesture');
        this.elements.aiGesture = document.getElementById('rps-ai-gesture');
        this.elements.playerStatus = document.getElementById('rps-player-status');
        this.elements.aiStatus = document.getElementById('rps-ai-status');
        this.elements.roundMessage = document.getElementById('rps-round-message');
        this.elements.playerScore = document.getElementById('rps-player-score');
        this.elements.aiScore = document.getElementById('rps-opponent-score');
        
        // 倒數顯示
        this.elements.countdownOverlay = document.getElementById('rps-countdown-overlay');
        this.elements.countdownNumber = document.getElementById('countdown-number');

        // 對戰結果顯示
        this.elements.battleDisplay = document.getElementById('rps-battle-display');
        this.elements.battlePlayerImage = document.getElementById('battle-player-image');
        this.elements.battlePlayerName = document.getElementById('battle-player-name');
        this.elements.battleAiImage = document.getElementById('battle-ai-image');
        this.elements.battleAiName = document.getElementById('battle-ai-name');
        this.elements.resultMessage = document.getElementById('rps-result-message');
        this.elements.resultText = document.getElementById('result-text');

        // 歷史記錄
        this.elements.historyList = document.getElementById('rps-history-list');
    }

    setupEventListeners() {
        // 開始遊戲
        if (this.elements.startButton) {
            this.elements.startButton.addEventListener('click', () => {
                this.startGame();
            });
        }

        // 停止遊戲
        if (this.elements.stopButton) {
            this.elements.stopButton.addEventListener('click', () => {
                this.stopGame();
            });
        }

        // 監聽攝影機事件
        this.cameraService.on('ready', () => {
            console.log('📹 攝影機就緒');
        });

        this.cameraService.on('error', (error) => {
            console.error('❌ 攝影機錯誤:', error);
            const message = this.cameraService.getErrorMessage(error);
            this.statusManager.update(message, STATUS_TYPES.ERROR);
            this.stopGame();
        });
    }

    async setupWebSocket() {
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
            return this.websocket;
        }

        if (this.websocket && this.websocket.readyState === WebSocket.CONNECTING && this.websocketReadyPromise) {
            return this.websocketReadyPromise;
        }

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
                            this.handleStreamResult(data);
                            break;
                        case 'game_state':
                            this.handleWebSocketMessage(data);
                            break;
                        case 'control_ack':
                            this.handleControlAck(data);
                            break;
                        case 'error':
                            console.error('❌ WebSocket 錯誤:', data.message);
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
                        this.setupWebSocket().catch((error) => {
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
                        this.startStreaming();
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

    handleStreamResult(data) {
        if (!data) {
            return;
        }

        const messageType = data.type || 'result';

        if (messageType === 'recognition_result' || messageType === 'result') {
            const gesture = data.gesture;
            const confidence = typeof data.confidence === 'number' ? data.confidence : 0;

            console.log(`👁️ 即時辨識: ${gesture} (${(confidence * 100).toFixed(1)}%)`);

            if (this.isGameActive && gesture && gesture !== 'unknown') {
                if (confidence > this.bestConfidenceSoFar) {
                    this.bestGestureSoFar = gesture;
                    this.bestConfidenceSoFar = confidence;
                    console.log(`📈 更新最佳手勢: ${gesture} (${(confidence * 100).toFixed(1)}%)`);
                }
            }

            const isValid = data.is_valid ?? (gesture && gesture !== 'unknown');
            if (isValid && confidence > 0.5) {
                this.updatePlayerStatus(`偵測到: ${this.getGestureEmoji(gesture)} (${(confidence * 100).toFixed(0)}%)`);
                this.currentGesture = gesture;
                this.currentConfidence = confidence;

                if (this.waitingForGesture && confidence > 0.6) {
                    console.log(`✅ 後端已自動設定手勢: ${gesture} (${(confidence * 100).toFixed(1)}%)`);
                    this.playerGesture = gesture;
                    this.playerImageData = this.cameraService.captureFrame('jpeg', 0.8, { mirror: true });
                    this.updatePlayerStatus(`你出了 ${this.getGestureEmoji(gesture)}`);

                    if (this.gestureTimeoutTimer) {
                        clearTimeout(this.gestureTimeoutTimer);
                        this.gestureTimeoutTimer = null;
                    }

                    this.waitingForGesture = false;
                }
            } else {
                this.updatePlayerStatus('請將手放在鏡頭前...');
                this.currentGesture = null;
            }
        } else if (messageType === 'error') {
            console.error('❌ 串流錯誤:', data.message);
        }
    }

    startStreaming() {
        if (this.streamInterval) {
            return;
        }

        if (!this.isGameActive) {
            return;
        }

        if (!this.cameraService.isActive()) {
            return;
        }

        if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            return;
        }

        console.log('📸 開始串流影像');

        this.streamInterval = setInterval(() => {
            if (!this.isGameActive) {
                return;
            }

            if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
                return;
            }

            if (!this.cameraService.isActive()) {
                return;
            }

            const imageData = this.cameraService.captureFrame('jpeg', 0.7, { mirror: true });

            if (imageData) {
                this.websocket.send(JSON.stringify({
                    type: 'frame',
                    image: imageData,
                    timestamp: Date.now()
                }));
            }
        }, 500);
    }

    stopStreaming() {
        if (this.streamInterval) {
            clearInterval(this.streamInterval);
            this.streamInterval = null;
        }
    }

    handleWebSocketMessage(data) {
        // 只處理 rps_game 頻道的訊息
        if (data.channel !== 'rps_game') {
            console.log('⏭️ 略過非 rps_game 頻道的訊息:', data.channel);
            return;
        }

        console.log(`🎮 處理 RPS 訊息 [${data.stage}]:`, data.message);

        const stage = data.stage;

        switch (stage) {
            case 'game_started':
                console.log('▶️ 遊戲開始');
                this.onGameStarted(data);
                break;

            case 'round_started':
                console.log('🔄 回合開始');
                this.onRoundStarted(data);
                break;

            case 'countdown':
                console.log(`⏱️ 倒數: ${data.data.count}`);
                this.onCountdown(data);
                break;

            case 'waiting_player':
                console.log('⏳ 等待玩家出拳');
                this.onWaitingPlayer(data);
                break;

            case 'result':
                console.log('📊 回合結果:', data.data.result);
                this.onResult(data);
                break;

            case 'game_finished':
                console.log('🏁 遊戲結束');
                this.onGameFinished(data);
                break;

            case 'game_stopped':
                console.log('⏹️ 遊戲停止');
                this.onGameStopped(data);
                break;

            case 'error':
                console.error('❌ 遊戲錯誤:', data.message);
                this.onError(data);
                break;

            default:
                console.warn('⚠️ 未知的訊息類型:', stage);
        }
    }


    handleControlAck(data) {
        const { action, status, message } = data;

        console.log('🎛️ 控制回應:', data);

        if (action === 'start_game') {
            if (status === 'started') {
                this.isGameActive = true;
                this.statusManager.update('遊戲開始！', STATUS_TYPES.SUCCESS);
                this.updateUIState('playing');
                this.startStreaming();
            } else {
                const errorMessage = message || '啟動遊戲失敗';
                this.statusManager.update(errorMessage, STATUS_TYPES.ERROR);
                this.updateUIState('idle');
                this.isGameActive = false;
                this.stopStreaming();
                if (this.elements.gameDisplay) {
                    this.elements.gameDisplay.classList.add('hidden');
                }
            }
        } else if (action === 'stop_game') {
            this.isGameActive = false;
            this.stopStreaming();
            this.statusManager.update(message || '遊戲已停止', STATUS_TYPES.INFO);
            this.updateUIState('idle');
            if (this.elements.gameDisplay) {
                this.elements.gameDisplay.classList.add('hidden');
            }
        } else if (action === 'submit_gesture') {
            console.log('📨 手動手勢提交確認:', data);
        }
    }

    // =========================================================================
    // 遊戲控制方法
    // =========================================================================

    async startGame() {
        try {
            console.log('🎮 開始啟動遊戲...');

            console.log('📹 啟動攝影機...');
            await this.initCamera();

            console.log('🔌 準備 WebSocket 連線...');
            await this.setupWebSocket();

            if (this.elements.gameDisplay) {
                this.elements.gameDisplay.classList.remove('hidden');
            }

            console.log('📤 透過 WebSocket 發送開始遊戲指令...');
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'game_control',
                    action: 'start_game',
                    target_score: 1
                }));
            }

            this.statusManager.update('正在啟動遊戲...', STATUS_TYPES.INFO);
            this.updateUIState('starting');

            // 重置最佳手勢追蹤
            this.bestGestureSoFar = null;
            this.bestConfidenceSoFar = 0;

        } catch (error) {
            console.error('❌ 啟動遊戲錯誤:', error);
            this.statusManager.update((error && error.message) || '啟動遊戲失敗', STATUS_TYPES.ERROR);
            this.updateUIState('idle');
            this.stopStreaming();
        }
    }

    async stopGame() {
        try {
            console.log('⏹️ 發送停止遊戲指令...');
            const wasActive = this.isGameActive;
            this.isGameActive = false;
            this.stopStreaming();
            this.stopCapture();

            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({
                    type: 'game_control',
                    action: 'stop_game'
                }));
            }

            if (this.elements.gameDisplay) {
                this.elements.gameDisplay.classList.add('hidden');
            }

            this.updateUIState('idle');
            this.statusManager.update(wasActive ? '遊戲停止中...' : '遊戲未啟動', STATUS_TYPES.INFO);

            if (this.gestureTimeoutTimer) {
                clearTimeout(this.gestureTimeoutTimer);
                this.gestureTimeoutTimer = null;
            }
            this.waitingForGesture = false;
            this.bestGestureSoFar = null;
            this.bestConfidenceSoFar = 0;

        } catch (error) {
            console.error('停止遊戲錯誤:', error);
            this.statusManager.update('停止遊戲失敗', STATUS_TYPES.ERROR);
        }
    }

    stopCapture() {
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
            this.captureInterval = null;
        }
    }

    // =========================================================================
    // WebSocket 事件處理
    // =========================================================================

    onGameStarted(data) {
        console.log('🎮 遊戲開始:', data);
        this.isGameActive = true;
        this.updateUIState('playing');
        this.playerScore = data.data.player_score || 0;
        this.aiScore = data.data.computer_score || 0;
        this.updateScores();
    }

    onRoundStarted(data) {
        console.log('🔄 回合開始:', data);
        this.roundNumber = data.data.round;
        this.updateRoundMessage(`第 ${this.roundNumber} 回合`);
        this.clearGestures();
    }

    onCountdown(data) {
        const count = data.data.count;
        this.showCountdown(count);
    }

    onWaitingPlayer(data) {
        console.log('⏳ 等待玩家出拳');
        console.log(`📊 目前最佳手勢: ${this.bestGestureSoFar} (${(this.bestConfidenceSoFar * 100).toFixed(1)}%)`);
        this.hideCountdown();
        // 簡化介面：移除所有文字提示和狀態顯示

        // 🎯 後端 WebSocket 串流已自動偵測並設定玩家手勢（信心度 > 60%）
        // 前端不需要再手動提交，只需等待後端處理即可
        this.waitingForGesture = true;
        this.gestureWaitStartTime = Date.now();

        // 🎯 設定超時保護：如果 3 秒內後端還沒設定手勢，自動停止遊戲
        this.gestureTimeoutTimer = setTimeout(() => {
            if (this.waitingForGesture) {
                console.warn(`⚠️ 3 秒內後端未自動設定手勢，可能沒有偵測到有效手勢`);
                console.log(`📊 最後追蹤到的手勢: ${this.bestGestureSoFar} (${(this.bestConfidenceSoFar * 100).toFixed(1)}%)`);
                // 簡化介面：移除錯誤提示顯示
                this.waitingForGesture = false;
                this.stopGame();
            }
        }, 3000);  // 3 秒超時保護
    }

    onResult(data) {
        console.log('📊 回合結果:', data);

        const resultData = data.data;

        // 顯示對戰結果（玩家 vs AI 的手勢圖片）
        this.showBattleResult(
            resultData.gestures.player,
            resultData.gestures.computer,
            this.playerImageData
        );

        // 顯示結果訊息（贏/輸/平手）
        this.showResultMessage(resultData.result, data.message);

        // 更新分數
        this.playerScore = resultData.scores.player;
        this.aiScore = resultData.scores.computer;
        this.updateScores();

        // 簡化介面：移除歷史記錄和文字訊息顯示

        // 🎯 只玩一回合，顯示結果 3 秒後再停止
        console.log('⏹️ 單回合遊戲結束，3 秒後停止');
        setTimeout(() => {
            this.stopGame();
        }, 3000);
    }

    onGameFinished(data) {
        console.log('🏁 遊戲結束:', data);
        this.updateRoundMessage(data.message);
        
        setTimeout(() => {
            this.stopGame();
        }, 3000);
    }

    onGameStopped(data) {
        console.log('⏹️ 遊戲已停止:', data);
        this.isGameActive = false;
        this.stopStreaming();
        this.updateUIState('idle');
        if (data && data.message) {
            this.statusManager.update(data.message, STATUS_TYPES.INFO);
        }
        if (this.elements.gameDisplay) {
            this.elements.gameDisplay.classList.add('hidden');
        }
    }

    onError(data) {
        console.error('❌ 遊戲錯誤:', data);
        this.statusManager.update(data.message, STATUS_TYPES.ERROR);
    }

    // =========================================================================
    // UI 更新方法
    // =========================================================================

    showCountdown(count) {
        console.log('📢 顯示倒數:', count);

        // 隱藏對戰結果和結果訊息
        if (this.elements.battleDisplay) {
            this.elements.battleDisplay.style.display = 'none';
        }
        if (this.elements.resultMessage) {
            this.elements.resultMessage.style.display = 'none';
        }

        // 顯示倒數
        if (this.elements.countdownOverlay) {
            this.elements.countdownOverlay.style.display = 'flex';
        }

        if (this.elements.countdownNumber) {
            this.elements.countdownNumber.textContent = count;
            // 重新觸發動畫
            this.elements.countdownNumber.style.animation = 'none';
            setTimeout(() => {
                this.elements.countdownNumber.style.animation = 'countdownPulse 1s ease-out';
            }, 10);
        }
    }

    hideCountdown() {
        console.log('📢 隱藏倒數');

        if (this.elements.countdownOverlay) {
            this.elements.countdownOverlay.style.display = 'none';
        }
    }

    showBattleResult(playerGesture, aiGesture, playerImageData = null) {
        console.log('📢 顯示對戰結果');

        // 隱藏倒數
        this.hideCountdown();

        // 顯示對戰結果
        if (this.elements.battleDisplay) {
            this.elements.battleDisplay.style.display = 'grid';
        }

        // 顯示玩家手勢
        if (this.elements.battlePlayerImage && playerImageData) {
            this.elements.battlePlayerImage.src = playerImageData;
        }
        if (this.elements.battlePlayerName) {
            this.elements.battlePlayerName.textContent = this.getGestureText(playerGesture);
        }

        // 顯示 AI 手勢圖片
        const aiImagePath = `/static/assets/rps/${aiGesture}.jpg`;
        if (this.elements.battleAiImage) {
            this.elements.battleAiImage.src = aiImagePath;
        }
        if (this.elements.battleAiName) {
            this.elements.battleAiName.textContent = this.getGestureText(aiGesture);
        }
    }

    showResultMessage(result, message) {
        console.log('📢 顯示結果訊息:', message);

        if (!this.elements.resultMessage) return;

        // 設定結果樣式
        this.elements.resultMessage.className = 'rps-result-message';
        this.elements.resultMessage.classList.add(result);

        // 設定結果文字
        if (this.elements.resultText) {
            this.elements.resultText.textContent = message;
        }

        // 顯示結果訊息
        this.elements.resultMessage.style.display = 'block';
    }

    showPlayerGesture(gesture) {
        const emoji = this.getGestureEmoji(gesture);
        if (this.elements.playerGesture) {
            this.elements.playerGesture.textContent = emoji;
        }
    }

    showAIGesture(gesture) {
        const emoji = this.getGestureEmoji(gesture);
        if (this.elements.aiGesture) {
            this.elements.aiGesture.textContent = emoji;
        }
        if (this.elements.aiStatus) {
            this.elements.aiStatus.textContent = `AI 出了 ${emoji}`;
        }
    }

    clearGestures() {
        if (this.elements.playerGesture) {
            this.elements.playerGesture.textContent = '❓';
        }
        if (this.elements.aiGesture) {
            this.elements.aiGesture.textContent = '❓';
        }
        if (this.elements.playerStatus) {
            this.elements.playerStatus.textContent = '準備中...';
        }
        if (this.elements.aiStatus) {
            this.elements.aiStatus.textContent = '準備中...';
        }
    }

    updateScores() {
        if (this.elements.playerScore) {
            this.elements.playerScore.textContent = this.playerScore;
        }
        if (this.elements.aiScore) {
            this.elements.aiScore.textContent = this.aiScore;
        }
    }

    updateRoundMessage(message) {
        if (this.elements.roundMessage) {
            this.elements.roundMessage.textContent = message;
        }
    }

    updatePlayerStatus(status) {
        if (this.elements.playerStatus) {
            this.elements.playerStatus.textContent = status;
        }
    }

    addToHistory(resultData) {
        if (!this.elements.historyList) return;

        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        
        const playerEmoji = this.getGestureEmoji(resultData.gestures.player);
        const aiEmoji = this.getGestureEmoji(resultData.gestures.computer);
        const resultEmoji = this.getResultEmoji(resultData.result);
        
        historyItem.innerHTML = `
            <span class="round-num">R${this.roundNumber}</span>
            <span class="history-gestures">你 ${playerEmoji} vs ${aiEmoji} AI</span>
            <span class="history-result">${resultEmoji}</span>
        `;
        
        this.elements.historyList.insertBefore(historyItem, this.elements.historyList.firstChild);
    }

    updateUIState(state) {
        const startButton = this.elements.startButton;
        const stopButton = this.elements.stopButton;

        switch (state) {
            case 'idle':
                if (startButton) startButton.disabled = false;
                if (stopButton) stopButton.disabled = true;
                break;

            case 'starting':
                if (startButton) startButton.disabled = true;
                if (stopButton) stopButton.disabled = true;
                break;

            case 'playing':
                if (startButton) startButton.disabled = true;
                if (stopButton) stopButton.disabled = false;
                break;
        }
    }

    // =========================================================================
    // 輔助方法
    // =========================================================================

    getGestureEmoji(gesture) {
        const emojis = {
            'rock': '✊',
            'paper': '✋',
            'scissors': '✌️'
        };
        return emojis[gesture] || '❓';
    }

    getGestureText(gesture) {
        const texts = {
            'rock': '石頭 ✊',
            'paper': '布 ✋',
            'scissors': '剪刀 ✌️'
        };
        return texts[gesture] || '未知';
    }

    getResultEmoji(result) {
        const emojis = {
            'win': '🎉 你贏了',
            'lose': '😢 你輸了',
            'draw': '🤝 平手'
        };
        return emojis[result] || '';
    }

    // =========================================================================
    // 公開方法
    // =========================================================================

    isActive() {
        return this.isGameActive;
    }

    destroy() {
        this.stopGame();
        
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        if (this.cameraService) {
            this.cameraService.destroy();
        }
    }
}
