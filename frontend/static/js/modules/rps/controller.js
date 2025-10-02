/**
 * RPS Game Controller
 * 主控制器，協調 Service 和 Presenter
 */

import { CameraService } from '../shared/camera/camera-service.js';
import { STATUS_TYPES } from '../../common/constants.js';
import { RPSGameService } from './service.js';
import { RPSGamePresenter } from './presenter.js';
import { BaseModule } from '../../app/base-module.js';

export class RPSGameController extends BaseModule {
    constructor(statusManager) {
        super({ name: 'rps-game', statusManager });

        // 唯一實例 ID，用於調試
        this.instanceId = 'RPS_' + Math.random().toString(36).substr(2, 9);
        console.log(`🎮 RPS Controller 實例創建: ${this.instanceId}`);

        this.cameraService = new CameraService();
        this.gameService = new RPSGameService();
        this.presenter = new RPSGamePresenter();

        this._uiUnbinders = [];
        this._serviceUnbinders = [];
        this._modeSwitchHandler = null;
        this._isStarting = false; // 防止重複啟動遊戲
        this._gameStarted = false; // 標記遊戲是否已成功開始
        this._lastGameStateSignature = null; // 避免重複處理相同狀態
        this._bestCaptureConfidence = 0; // 追蹤最佳截圖信心度
        this._lastControlAckKey = null;
        this._lastControlAckTimestamp = 0;
        this._autoStopTimer = null;
    }

    async _onInitialize() {
        console.log('✅ RPS Game Controller initialized');
        this.presenter.setupDOM();
        this._bindUIEvents();
        this._bindServiceEvents();
        this._bindModeSwitchListener();
    }

    /**
     * 設定模式切換監聽器
     */
    _bindModeSwitchListener() {
        if (this._modeSwitchHandler) {
            return;
        }

        this._modeSwitchHandler = (event) => {
            if (event.detail.mode === 'rps') {
                console.log('📹 RPS 模式啟動，準備攝影機...');
                this.initCamera().catch(error => {
                    console.error('❌ 攝影機啟動失敗:', error);
                });
            } else {
                if (this.cameraService.isActive()) {
                    console.log('📹 停止 RPS 攝影機');
                    this.cameraService.stop();
                }
            }
        };

        document.addEventListener('modeSwitched', this._modeSwitchHandler);
    }

    /**
     * 設定 UI 事件監聽器
     */
    _bindUIEvents() {
        // 開始遊戲
        if (this.presenter.elements.startButton) {
            const handler = () => this.startGame();
            this.presenter.elements.startButton.addEventListener('click', handler);
            this._uiUnbinders.push(() => this.presenter.elements.startButton.removeEventListener('click', handler));
        }

        // 停止遊戲
        if (this.presenter.elements.stopButton) {
            const handler = () => this.stopGame();
            this.presenter.elements.stopButton.addEventListener('click', handler);
            this._uiUnbinders.push(() => this.presenter.elements.stopButton.removeEventListener('click', handler));
        }

        // 監聽攝影機事件
        const cameraReadyUnsub = this.cameraService.on('ready', () => {
            console.log('📹 攝影機就緒');
        });

        const cameraErrorUnsub = this.cameraService.on('error', (error) => {
            console.error('❌ 攝影機錯誤:', error);
            const message = this.cameraService.getErrorMessage(error);
            this.statusManager.update(message, STATUS_TYPES.ERROR);
            this.stopGame();
        });

        this._uiUnbinders.push(cameraReadyUnsub);
        this._uiUnbinders.push(cameraErrorUnsub);
    }

    /**
     * 設定 Service 事件監聽器
     */
    _bindServiceEvents() {
        console.log(`🔗 [${this.instanceId}] 綁定 Service 事件監聽器`);

        // 即時辨識結果
        const streamResultHandler = ({ gesture, confidence, isValid }) => {
            if (isValid && confidence > 0.5) {
                this.presenter.updatePlayerStatus(`偵測到: ${this.presenter.getGestureEmoji(gesture)} (${(confidence * 100).toFixed(0)}%)`);

                if (this.gameService.waitingForGesture && confidence > 0.6) {
                    console.log(`✅ 後端已自動設定手勢: ${gesture} (${(confidence * 100).toFixed(1)}%)`);
                    this.gameService.playerGesture = gesture;
                    const capturedFrame = this.cameraService.captureFrame('jpeg', 0.8, { mirror: true });
                    if (capturedFrame) {
                        this.gameService.playerImageData = capturedFrame;
                        this.gameService.bestFrameData = capturedFrame;
                        this.gameService.bestFrameConfidence = confidence;
                        this._bestCaptureConfidence = Math.max(this._bestCaptureConfidence, confidence);
                    }
                    this.presenter.updatePlayerStatus(`你出了 ${this.presenter.getGestureEmoji(gesture)}`);

                    if (this.gameService.gestureTimeoutTimer) {
                        clearTimeout(this.gameService.gestureTimeoutTimer);
                        this.gameService.gestureTimeoutTimer = null;
                    }

                    this.gameService.waitingForGesture = false;
                }
            } else {
                this.presenter.updatePlayerStatus('請將手放在鏡頭前...');
            }

            // 只在等待手勢時才更新最佳畫面
            if (this.gameService.waitingForGesture && gesture && gesture !== 'unknown' && confidence > this._bestCaptureConfidence && this.cameraService.isActive()) {
                const bestFrame = this.cameraService.captureFrame('jpeg', 0.85, { mirror: true });
                if (bestFrame) {
                    this.gameService.playerImageData = bestFrame;
                    this.gameService.bestFrameData = bestFrame;
                    this.gameService.bestFrameConfidence = confidence;
                    this._bestCaptureConfidence = confidence;
                }
            }
        };
        this._serviceUnbinders.push(this.gameService.on('streamResult', streamResultHandler));

        // 遊戲狀態更新
        const gameStateHandler = (event) => {
            const payload = event?.detail ?? event;

            if (!payload) {
                console.warn(`⚠️ [${this.instanceId}] 收到無效的遊戲狀態事件`, event);
                return;
            }

            this.handleGameStateMessage(payload);
        };
        this._serviceUnbinders.push(this.gameService.on('gameState', gameStateHandler));

        // 控制確認
        const controlAckHandler = (data) => {
            console.log(`🎛️ [${this.instanceId}] 控制回應:`, data);
            console.log(`🎛️ [${this.instanceId}] data.detail:`, data.detail);

            // 修正：data 是 CustomEvent，真正的資料在 data.detail
            const payload = data.detail || data;
            const { action, status } = payload;

            const controlAckKey = JSON.stringify({
                action,
                status,
                message: payload.message,
                target: payload.target_score,
                stage: payload.stage
            });

            if (
                controlAckKey &&
                controlAckKey === this._lastControlAckKey &&
                Date.now() - this._lastControlAckTimestamp < 2000
            ) {
                return;
            }

            this._lastControlAckKey = controlAckKey;
            this._lastControlAckTimestamp = Date.now();

            console.log(`🎛️ [${this.instanceId}] action="${action}", status="${status}"`);

            if (action === 'start_game' && status === 'started') {
                // 防止重複處理開始遊戲成功
                if (this._gameStarted) {
                    return;
                }
                this._gameStarted = true;

                console.log(`✅ [${this.instanceId}] 設定遊戲狀態並啟動串流`);
                this.gameService.isGameActive = true;
                this.statusManager.update('遊戲開始！', STATUS_TYPES.SUCCESS);
                this.presenter.updateUIState('playing');

                // 確認串流啟動
                console.log(`📸 [${this.instanceId}] 準備啟動串流...`);
                this.gameService.startStreaming(this.cameraService);
                console.log(`📸 [${this.instanceId}] startStreaming 已呼叫`);
            } else if (action === 'stop_game') {
                this._gameStarted = false; // 重置標記
                this.gameService.isGameActive = false;
                this.presenter.updateUIState('idle');
            } else {
                console.log(`⚠️ [${this.instanceId}] 未匹配的 action/status 組合`);
            }
        };
        this._serviceUnbinders.push(this.gameService.on('controlAck', controlAckHandler));

        // 錯誤
        const errorHandler = (data) => {
            if (data?.message) {
                this.statusManager.update(data.message, STATUS_TYPES.ERROR);
            }
        };
        this._serviceUnbinders.push(this.gameService.on('error', errorHandler));
    }

    /**
     * 初始化攝影機
     */
    async initCamera() {
        try {
            await this.cameraService.start();
            await this.cameraService.attachToVideoElement(this.presenter.elements.video, {
                mirror: true
            });

            // 顯示攝影機畫面
            if (this.presenter.elements.video) {
                this.presenter.elements.video.style.display = 'block';
            }

            console.log('📹 攝影機已就緒');

        } catch (error) {
            console.error('❌ 攝影機初始化失敗:', error);
            const message = this.cameraService.getErrorMessage(error);
            this.statusManager.update(message, STATUS_TYPES.ERROR);
            throw error;
        }
    }

    /**
     * 開始遊戲
     */
    async startGame() {
        // 防止重複啟動
        if (this._isStarting || this.gameService.isGameActive) {
            console.log('⚠️ 遊戲已在啟動中或進行中，忽略重複請求');
            return;
        }

        if (this._autoStopTimer) {
            clearTimeout(this._autoStopTimer);
            this._autoStopTimer = null;
        }

        this._isStarting = true;

        try {
            console.log('🎮 開始啟動遊戲...');

            // 1. 啟動攝影機
            await this.initCamera();

            // 2. 建立 WebSocket 連線
            await this.gameService.setupWebSocket(this.cameraService);

            // 3. 顯示遊戲畫面
            this.presenter.showGameDisplay();

            // 4. 發送開始遊戲指令
            console.log('📤 透過 WebSocket 發送開始遊戲指令...');
            // 固定為單回合模式（target_score 保留為 API 相容性，實際不使用）
            this.gameService.sendGameControl('start_game', { target_score: 1 });
            this.statusManager.update('正在啟動遊戲...', STATUS_TYPES.INFO);
            this.presenter.updateUIState('starting');

            // 重置遊戲狀態
            this.gameService.resetGameState();
            this.gameService.bestFrameData = null;
            this.gameService.bestFrameConfidence = 0;
            this._lastGameStateSignature = null;
            this._bestCaptureConfidence = 0;
            this._lastControlAckKey = null;
            this._lastControlAckTimestamp = 0;
            this._autoStopTimer = null;

        } catch (error) {
            console.error('❌ 啟動遊戲錯誤:', error);
            this.statusManager.update((error && error.message) || '啟動遊戲失敗', STATUS_TYPES.ERROR);
            this.presenter.updateUIState('idle');
            this.gameService.stopStreaming();
        } finally {
            this._isStarting = false;
        }
    }

    /**
     * 停止遊戲
     */
    async stopGame() {
        try {
            console.log('⏹️ 發送停止遊戲指令...');
            this.gameService.isGameActive = false;
            this.gameService.stopStreaming();
            this._bestCaptureConfidence = 0;
            this.gameService.bestFrameData = null;
            this.gameService.bestFrameConfidence = 0;
            this.gameService.playerImageData = null;
            this._lastControlAckKey = null;
            this._lastControlAckTimestamp = 0;
            if (this._autoStopTimer) {
                clearTimeout(this._autoStopTimer);
                this._autoStopTimer = null;
            }
            this._gameStarted = false;

            this.gameService.sendGameControl('stop_game');

            this.presenter.hideGameDisplay();
            this.presenter.updateUIState('idle');

        } catch (error) {
            console.error('停止遊戲錯誤:', error);
        }
    }

    /**
     * 處理遊戲狀態訊息
     */
    handleGameStateMessage(data) {
        const channel = data.channel;
        if (channel && channel !== 'rps_game') {
            console.log(`⚠️ [${this.instanceId}] 忽略非 rps_game 頻道: ${channel}`);
            return;
        }

        const stage = data.stage;

        const stateSignature = `${stage || 'unknown'}|${data.timestamp || ''}`;
        if (stateSignature && stateSignature === this._lastGameStateSignature) {
            return;
        }
        this._lastGameStateSignature = stateSignature;

        if (stage) {
            console.log(`🎯 [${this.instanceId}] 處理遊戲階段: ${stage}`);
        }

        switch (stage) {
            case 'game_started':
                this.onGameStarted(data);
                break;
            case 'round_started':
                this.onRoundStarted(data);
                break;
            case 'countdown':
                this.onCountdown(data);
                break;
            case 'waiting_player':
                this.onWaitingPlayer(data);
                break;
            case 'result':
                this.onResult(data);
                break;
            case 'game_finished':
                // 單回合模式，已在 onResult 處理
                break;
            case 'game_stopped':
                this.gameService.isGameActive = false;
                this.gameService.stopStreaming();
                this.presenter.updateUIState('idle');
                break;
            case 'error':
                console.error('❌ 遊戲錯誤:', data.message);
                this.statusManager.update(data.message, STATUS_TYPES.ERROR);
                break;
            default:
                console.log(`⚠️ [${this.instanceId}] 未處理的遊戲階段: ${stage}`);
        }
    }

    onGameStarted(data) {
        console.log('🎮 遊戲開始');
        this.gameService.playerScore = data.data.player_score || 0;
        this.gameService.aiScore = data.data.computer_score || 0;
        this.presenter.updateScores(this.gameService.playerScore, this.gameService.aiScore);
    }

    onRoundStarted(data) {
        this.gameService.roundNumber = data.data.round;
        this.presenter.updateRoundMessage(`第 ${this.gameService.roundNumber} 回合`);
        this.presenter.clearGestures();
    }

    onCountdown(data) {
        const count = data.data?.count;
        if (count !== undefined) {
            this.presenter.showCountdown(count);
        }
    }

    onWaitingPlayer(data) {
        this.presenter.hideCountdown();
        this.gameService.waitingForGesture = true;
        this.gameService.gestureWaitStartTime = Date.now();

        // 設定超時保護（倒數後額外 2 秒）
        this.gameService.gestureTimeoutTimer = setTimeout(() => {
            if (this.gameService.waitingForGesture) {
                if (this.gameService.bestGestureSoFar && this.gameService.bestConfidenceSoFar > 0) {
                    console.log(`使用最佳手勢: ${this.gameService.bestGestureSoFar} (${(this.gameService.bestConfidenceSoFar * 100).toFixed(1)}%)`);
                    if (!this.gameService.playerGesture) {
                        this.gameService.playerGesture = this.gameService.bestGestureSoFar;
                    }
                    if (!this.gameService.playerImageData && this.gameService.bestFrameData) {
                        this.gameService.playerImageData = this.gameService.bestFrameData;
                        this._bestCaptureConfidence = this.gameService.bestFrameConfidence || this._bestCaptureConfidence;
                    }
                } else {
                    console.warn(`⚠️ 未偵測到有效手勢 (unknown 信心度: ${(this.gameService.bestUnknownConfidence * 100).toFixed(1)}%)`);
                    this.gameService.sendNoGestureDetected(this.cameraService);
                }

                this.gameService.waitingForGesture = false;
            }
        }, 2000);
    }

    onResult(data) {
        const resultData = data.data;
        console.log(`📊 ${data.message}`);

        if (!this.gameService.playerImageData) {
            if (this.gameService.bestFrameData) {
                this.gameService.playerImageData = this.gameService.bestFrameData;
            } else {
                this.gameService.playerImageData = this.cameraService.captureFrame('jpeg', 0.85, { mirror: true });
            }
        }

        this.gameService.isGameActive = false;
        this._gameStarted = false;

        // 顯示對戰結果
        this.presenter.showBattleResult(
            resultData.gestures.player,
            resultData.gestures.computer,
            this.gameService.playerImageData
        );

        // 顯示結果訊息
        this.presenter.showResultMessage(resultData.result, data.message);

        // 更新分數
        this.gameService.playerScore = resultData.scores.player;
        this.gameService.aiScore = resultData.scores.computer;
        this.presenter.updateScores(this.gameService.playerScore, this.gameService.aiScore);

        // 3 秒後自動停止
        if (this._autoStopTimer) {
            clearTimeout(this._autoStopTimer);
        }
        this._autoStopTimer = setTimeout(() => {
            this._autoStopTimer = null;
            if (!this.gameService.isGameActive && !this._isStarting) {
                this.stopGame();
            }
        }, 3000);
    }

    /**
     * 清理資源
     */
    destroy() {
        this.stopGame();
        this.gameService.closeWebSocket();
        if (this.cameraService) {
            this.cameraService.destroy();
        }
    }

    async _onDeactivate() {
        await this.stopGame();
        if (this.cameraService.isActive()) {
            this.cameraService.stop();
        }
    }

    async _onDestroy() {
        this._serviceUnbinders.forEach((unsubscribe) => unsubscribe?.());
        this._serviceUnbinders = [];

        this._uiUnbinders.forEach((unsubscribe) => unsubscribe?.());
        this._uiUnbinders = [];

        if (this._modeSwitchHandler) {
            document.removeEventListener('modeSwitched', this._modeSwitchHandler);
            this._modeSwitchHandler = null;
        }

        this.gameService.closeWebSocket();
        this.cameraService.destroy?.();
    }
}
