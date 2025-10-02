// =============================================================================
// Action Game Controller - 動作遊戲控制器
// 負責遊戲流程控制
// =============================================================================

import { STATUS_TYPES } from '../../../common/constants.js';
import { BaseModule } from '../../../app/base-module.js';

export class ActionGameController extends BaseModule {
    constructor(statusManager, options = {}) {
        super({ name: 'action-game', statusManager });
        this.isGameActive = false;
    }

    async _onInitialize() {
        console.log('✅ Action Game Module initialized');
        // TODO: 實現動作遊戲邏輯
    }

    async _onActivate() {
        this.updateStatus('動作遊戲功能開發中...', STATUS_TYPES.INFO);
        // TODO: 實現遊戲開始邏輯
    }

    async _onDeactivate() {
        this.isGameActive = false;
        // TODO: 實現遊戲結束邏輯
    }

    // 公共方法
    startGame() {
        return this.activate();
    }

    stopGame() {
        return this.deactivate();
    }

    isActive() {
        return this.isGameActive;
    }
}
