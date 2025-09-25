// =============================================================================
// rps-game.js - 剪刀石頭布遊戲模組
// =============================================================================

import { STATUS_TYPES } from '../common/constants.js';

export class RPSGameModule {
    constructor(statusManager) {
        this.statusManager = statusManager;
        this.isGameActive = false;

        this.init();
    }

    init() {
        console.log('RPS Game Module initialized');
        // TODO: 實現剪刀石頭布遊戲邏輯
    }

    startGame() {
        this.statusManager.update('剪刀石頭布遊戲功能開發中...', STATUS_TYPES.INFO);
        // TODO: 實現遊戲開始邏輯
    }

    stopGame() {
        // TODO: 實現遊戲結束邏輯
    }

    // Public methods
    isActive() {
        return this.isGameActive;
    }
}