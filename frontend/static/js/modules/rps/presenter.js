/**
 * RPS Game Presenter
 * 負責 UI 更新、DOM 操作、動畫效果
 */

export class RPSGamePresenter {
    constructor() {
        this.elements = {};
    }

    /**
     * 初始化 DOM 元素
     */
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

    /**
     * 顯示/隱藏遊戲畫面
     */
    showGameDisplay() {
        if (this.elements.gameDisplay) {
            this.elements.gameDisplay.classList.remove('hidden');
        }
    }

    hideGameDisplay() {
        if (this.elements.gameDisplay) {
            this.elements.gameDisplay.classList.add('hidden');
        }
    }

    /**
     * 顯示倒數
     */
    showCountdown(count) {
        if (this.elements.battleDisplay) {
            this.elements.battleDisplay.style.display = 'none';
        }
        if (this.elements.resultMessage) {
            this.elements.resultMessage.style.display = 'none';
        }

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
        if (this.elements.countdownOverlay) {
            this.elements.countdownOverlay.style.display = 'none';
        }
    }

    /**
     * 顯示對戰結果
     */
    showBattleResult(playerGesture, aiGesture, playerImageData = null) {
        this.hideCountdown();

        // 顯示對戰結果
        if (this.elements.battleDisplay) {
            this.elements.battleDisplay.style.display = 'grid';
        }

        // 顯示玩家手勢
        if (this.elements.battlePlayerImage) {
            const fallbackImage = this.getPlayerPlaceholderImage(playerGesture);
            const safeImageSource = playerImageData || fallbackImage;
            this.elements.battlePlayerImage.src = safeImageSource;
            this.elements.battlePlayerImage.alt = `玩家手勢 ${this.getGestureText(playerGesture)}`;
        }
        if (this.elements.battlePlayerName) {
            this.elements.battlePlayerName.textContent = this.getGestureText(playerGesture);
        }

        // 顯示 AI 手勢圖片
        const aiImagePath = `/static/assets/rps/${aiGesture}.jpg`;
        if (this.elements.battleAiImage) {
            this.elements.battleAiImage.src = aiImagePath;
            this.elements.battleAiImage.alt = `AI 手勢 ${this.getGestureText(aiGesture)}`;
        }
        if (this.elements.battleAiName) {
            this.elements.battleAiName.textContent = this.getGestureText(aiGesture);
        }
    }

    /**
     * 顯示結果訊息
     */
    showResultMessage(result, message) {
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

    /**
     * 更新玩家狀態
     */
    updatePlayerStatus(status) {
        if (this.elements.playerStatus) {
            this.elements.playerStatus.textContent = status;
        }
    }

    /**
     * 更新分數
     */
    updateScores(playerScore, aiScore) {
        if (this.elements.playerScore) {
            this.elements.playerScore.textContent = playerScore;
        }
        if (this.elements.aiScore) {
            this.elements.aiScore.textContent = aiScore;
        }
    }

    /**
     * 更新回合訊息
     */
    updateRoundMessage(message) {
        if (this.elements.roundMessage) {
            this.elements.roundMessage.textContent = message;
        }
    }

    /**
     * 顯示手勢
     */
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

    /**
     * 清除手勢
     */
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

    /**
     * 更新 UI 狀態（按鈕）
     */
    updateUIState(state) {
        const startButton = this.elements.startButton;
        const stopButton = this.elements.stopButton;

        switch (state) {
            case 'idle':
                if (startButton) startButton.disabled = false;
                if (stopButton) stopButton.disabled = true;
                break;

            case 'starting':
            case 'playing':
                if (startButton) startButton.disabled = true;
                if (stopButton) stopButton.disabled = false;
                break;
        }
    }

    /**
     * 輔助方法：手勢轉 Emoji
     */
    getGestureEmoji(gesture) {
        const emojis = {
            'rock': '✊',
            'paper': '✋',
            'scissors': '✌️',
            'unknown': '😡'
        };
        return emojis[gesture] || '❓';
    }

    getPlayerPlaceholderImage(gesture) {
        const emoji = this.getGestureEmoji(gesture);
        const label = this.getGestureText(gesture);

        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">
                <rect width="240" height="240" rx="18" fill="#1f2937" />
                <text x="50%" y="45%" font-size="90" text-anchor="middle" dominant-baseline="middle">${emoji}</text>
                <text x="50%" y="78%" font-size="28" text-anchor="middle" fill="#f9fafb">${label}</text>
            </svg>
        `.trim();

        return `data:image/svg+xml,${encodeURIComponent(svg)}`;
    }

    getGestureText(gesture) {
        const texts = {
            'rock': '石頭 ✊',
            'paper': '布 ✋',
            'scissors': '剪刀 ✌️',
            'unknown': '亂比 😡'
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
}
