// =============================================================================
// emotion_action.js - 模組化主控制器
// =============================================================================

// 導入所有模組
import { ANALYSIS_MODES, STATUS_TYPES } from './common/constants.js';
import { StatusManager, TabSwitcher } from './common/ui-helpers.js';
import { EmotionUploadModule } from './modules/emotion-upload.js';
import { EmotionRealtimeModule } from './modules/emotion-realtime.js';
import { ActionUploadModule } from './modules/action-upload.js';
import { ActionGameModule } from './modules/action-game.js';
import { RPSGameModule } from './modules/rps-game.js';
import { DrawingGameModule } from './modules/drawing-game.js';

/**
 * 主應用控制器
 * 負責協調各個功能模組和管理全域狀態
 */
class EmotionActionController {
    constructor() {
        // 狀態管理
        this.currentMode = ANALYSIS_MODES.EMOTION;
        this.statusManager = null;
        this.tabSwitcher = null;

        // 功能模組
        this.modules = {
            emotionUpload: null,
            emotionRealtime: null,
            actionUpload: null,
            actionGame: null,
            rpsGame: null,
            drawingGame: null
        };

        // DOM 元素
        this.elements = {
            status: document.getElementById('status-container'),
            modeButtons: document.querySelectorAll('.mode-btn'),
            analysisTabButtons: document.querySelectorAll('.tab-btn'),
            tabContents: document.querySelectorAll('.tab-content')
        };

        this.init();
    }

    /**
     * 初始化應用程式
     */
    init() {
        this.initStatusManager();
        this.initTabSwitcher();
        this.initModules();
        this.setupEventListeners();
        this.setInitialState();

        console.log('EmotionAction 應用程式已初始化');
    }

    /**
     * 初始化狀態管理器
     */
    initStatusManager() {
        // 找到狀態消息元素
        const statusElement = this.elements.status?.querySelector('.status-message') || this.elements.status;
        this.statusManager = new StatusManager(statusElement);
    }

    /**
     * 初始化標籤切換器
     */
    initTabSwitcher() {
        this.tabSwitcher = new TabSwitcher(
            this.elements.analysisTabButtons,
            this.elements.tabContents
        );
    }

    /**
     * 初始化功能模組
     */
    initModules() {
        // 情緒分析模組
        this.modules.emotionUpload = new EmotionUploadModule(this.statusManager);
        this.modules.emotionRealtime = new EmotionRealtimeModule(this.statusManager);

        // 動作分析模組
        this.modules.actionUpload = new ActionUploadModule(this.statusManager);
        this.modules.actionGame = new ActionGameModule(this.statusManager);

        // 遊戲模組
        this.modules.rpsGame = new RPSGameModule(this.statusManager);
        this.modules.drawingGame = new DrawingGameModule(this.statusManager);

        console.log('所有功能模組已初始化');
    }

    /**
     * 設置事件監聽器
     */
    setupEventListeners() {
        // 模式切換按鈕
        this.elements.modeButtons?.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                this.setAnalysisMode(mode);
            });
        });

        // 全域鍵盤快捷鍵
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // 頁面卸載時清理資源
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    /**
     * 處理鍵盤快捷鍵
     * @param {KeyboardEvent} e 鍵盤事件
     */
    handleKeyboardShortcuts(e) {
        // ESC 鍵停止所有檢測
        if (e.key === 'Escape') {
            this.stopAllActivities();
        }

        // Ctrl + 1-6 快速切換模式
        if (e.ctrlKey && e.key >= '1' && e.key <= '6') {
            e.preventDefault();
            const modes = ['emotion', 'action'];
            const modeIndex = parseInt(e.key) - 1;
            if (modes[modeIndex]) {
                this.setAnalysisMode(modes[modeIndex]);
            }
        }
    }

    /**
     * 設置分析模式
     * @param {string} mode 分析模式
     */
    setAnalysisMode(mode) {
        if (this.currentMode === mode) return;

        // 停止當前活動
        this.stopAllActivities();

        // 更新模式
        this.currentMode = mode;

        // 更新UI
        this.updateModeButtons(mode);
        this.updateModeDisplay(mode);

        // 重置標籤狀態
        this.resetTabStates(mode);

        // 更新狀態消息
        const modeNames = {
            'emotion': '情緒分析',
            'action': '動作偵測',
            'rps': '石頭剪刀布',
            'drawing': 'AI 畫布'
        };
        
        this.statusManager.update(`已切換到${modeNames[mode] || mode}模式`, STATUS_TYPES.INFO);
    }

    /**
     * 更新模式按鈕狀態
     * @param {string} activeMode 啟用的模式
     */
    updateModeButtons(activeMode) {
        this.elements.modeButtons?.forEach(button => {
            button.classList.toggle('active', button.dataset.mode === activeMode);
        });
    }

    /**
     * 更新模式顯示
     * @param {string} mode 當前模式
     */
    updateModeDisplay(mode) {
        const panels = document.querySelectorAll('.analysis-panel');
        panels?.forEach(panel => {
            const isActive = panel.id === `${mode}-panel`;
            panel.classList.toggle('active', isActive);
            if (isActive) {
                panel.classList.remove('hidden');
                panel.style.display = 'block'; // 確保顯示
            } else {
                panel.classList.add('hidden');
                panel.style.display = 'none'; // 確保隱藏
            }
        });
    }

    /**
     * 重置標籤狀態
     * @param {string} mode 當前模式
     */
    resetTabStates(mode) {
        if (mode === 'emotion') {
            this.tabSwitcher.switchTo('upload');
        } else if (mode === 'action') {
            this.tabSwitcher.switchTo('action-game');
        }
        // rps 和 drawing 模式沒有標籤，不需要重置
    }

    /**
     * 設置初始狀態
     */
    setInitialState() {
        this.setAnalysisMode('emotion');
        this.statusManager.update('請選擇分析模式開始...', STATUS_TYPES.INFO);
    }

    /**
     * 停止所有活動
     */
    stopAllActivities() {
        // 停止即時檢測（只停止分析，保持攝影機運行）
        if (this.modules.emotionRealtime?.isDetectionActive()) {
            this.modules.emotionRealtime.stopDetection();
        }

        // 停止所有遊戲
        Object.values(this.modules).forEach(module => {
            if (module && typeof module.stopGame === 'function') {
                module.stopGame();
            }
        });
    }

    /**
     * 獲取應用程式狀態
     * @returns {Object} 當前狀態
     */
    getAppState() {
        return {
            currentMode: this.currentMode,
            emotionRealtimeStats: this.modules.emotionRealtime?.getCurrentStats(),
            activeModules: Object.keys(this.modules).filter(key => {
                const module = this.modules[key];
                return module && (
                    (typeof module.isActive === 'function' && module.isActive()) ||
                    (typeof module.isDetectionActive === 'function' && module.isDetectionActive())
                );
            })
        };
    }

    /**
     * 清理資源
     */
    cleanup() {
        console.log('正在清理應用程式資源...');

        // 停止所有活動
        this.stopAllActivities();

        // 清理模組
        Object.values(this.modules).forEach(module => {
            if (module && typeof module.destroy === 'function') {
                module.destroy();
            }
        });
    }

    /**
     * 公開方法：清理檔案選擇
     */
    clearEmotionFileSelection() {
        this.modules.emotionUpload?.clearFile();
    }

    clearActionFileSelection() {
        this.modules.actionUpload?.clearFile();
    }
}

// =============================================================================
// 應用程式入口點
// =============================================================================

let appController = null;

document.addEventListener('DOMContentLoaded', () => {
    try {
        // 初始化應用程式控制器
        appController = new EmotionActionController();

        // 將控制器綁定到全域，方便調試和HTML調用
        window.emotionActionApp = appController;

        // 為了向後兼容，綁定清理函數到全域
        window.clearEmotionFileSelection = () => appController.clearEmotionFileSelection();
        window.clearActionFileSelection = () => appController.clearActionFileSelection();

        console.log('🎉 應用程式啟動成功！');

    } catch (error) {
        console.error('❌ 應用程式初始化失敗:', error);

        // 顯示錯誤訊息
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = '應用程式載入失敗，請刷新頁面重試';
            statusElement.className = 'status error';
        }
    }
});

// 導出控制器類別 (供其他腳本使用)
export { EmotionActionController };
