// =============================================================================
// emotion_action.js - AI互動遊戲展場主控制器
//
// 負責協調和管理整個AI互動體驗平台的所有功能模組，
// 包括情緒分析、動作偵測、石頭剪刀布遊戲和AI繪畫等功能。
//
// 主要功能：
// - 應用程式初始化和模組協調
// - 分析模式切換和管理
// - 全域狀態管理和事件處理
// - 鍵盤快捷鍵支持
// - 資源清理和錯誤處理
// =============================================================================

// 導入核心依賴模組
import { ANALYSIS_MODES, STATUS_TYPES } from './common/constants.js';
import { StatusManager, TabSwitcher } from './common/ui-helpers.js';

// 導入功能模組
import { EmotionUploadModule } from './modules/emotion-upload.js';
import { EmotionRealtimeModule } from './modules/emotion-realtime.js';
import { ActionUploadModule } from './modules/action-upload.js';
import { ActionGameModule } from './modules/action-game.js';
import { RPSGameModule } from './modules/rps-game.js';
// 使用重構的手勢繪畫模組
import { GestureDrawingModule } from './modules/gesture-drawing.js';

/**
 * 主應用控制器類別
 * @class EmotionActionController
 * @description 整個應用程式的主要控制器，負責協調各功能模組、管理全域狀態和處理用戶交互
 */
class EmotionActionController {
    /**
     * 建構函式
     * @constructor
     * @description 初始化控制器實例，設置所有必要的屬性和狀態
     */
    constructor() {
        /**
         * 當前分析模式
         * @type {string}
         */
        this.currentMode = ANALYSIS_MODES.EMOTION;

        /**
         * 狀態管理器實例
         * @type {StatusManager}
         */
        this.statusManager = null;

        /**
         * 標籤切換器實例
         * @type {TabSwitcher}
         */
        this.tabSwitcher = null;

        /**
         * 功能模組集合
         * @type {Object.<string, Object>}
         */
        this.modules = {
            emotionUpload: null,    // 情緒檔案上傳模組
            emotionRealtime: null,  // 情緒即時分析模組
            actionUpload: null,     // 動作檔案上傳模組
            actionGame: null,       // 動作遊戲模組
            rpsGame: null,          // 石頭剪刀布遊戲模組
            gestureDrawing: null    // 手勢繪畫模組
        };

        /**
         * DOM元素引用集合
         * @type {Object.<string, HTMLElement|NodeList>}
         */
        this.elements = {
            status: document.getElementById('status-container'),
            modeButtons: document.querySelectorAll('.mode-btn'),
            analysisTabButtons: document.querySelectorAll('.tab-btn'),
            tabContents: document.querySelectorAll('.tab-content')
        };

        // 開始初始化
        this.init();
    }

    /**
     * 初始化應用程式
     * @private
     * @description 按順序初始化應用程式的各個組件：狀態管理器、標籤切換器、功能模組、事件監聽器和初始狀態
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
     * @private
     * @description 創建狀態管理器實例，用於處理應用程式的狀態消息顯示和管理
     */
    initStatusManager() {
        // 找到狀態消息元素，優先使用子元素，否則使用容器本身
        const statusElement = this.elements.status?.querySelector('.status-message') || this.elements.status;
        this.statusManager = new StatusManager(statusElement);
    }

    /**
     * 初始化標籤切換器
     * @private
     * @description 創建標籤切換器實例，用於管理不同分析模式的標籤頁切換
     */
    initTabSwitcher() {
        this.tabSwitcher = new TabSwitcher(
            this.elements.analysisTabButtons,
            this.elements.tabContents
        );
    }

    /**
     * 初始化功能模組
     * @private
     * @description 實例化並初始化所有功能模組，包括情緒分析、動作偵測和遊戲模組
     */
    initModules() {
        // 情緒分析模組 - 處理檔案上傳和即時攝影機分析
        this.modules.emotionUpload = new EmotionUploadModule(this.statusManager);
        this.modules.emotionRealtime = new EmotionRealtimeModule(this.statusManager);

        // 動作分析模組 - 處理動作檔案上傳和遊戲模式
        this.modules.actionUpload = new ActionUploadModule(this.statusManager);
        this.modules.actionGame = new ActionGameModule(this.statusManager);

        // 遊戲模組 - 石頭剪刀布和AI繪畫遊戲
        this.modules.rpsGame = new RPSGameModule(this.statusManager);
        this.modules.gestureDrawing = new GestureDrawingModule(this.statusManager);

        console.log('所有功能模組已初始化');
    }

    /**
     * 設置事件監聽器
     * @private
     * @description 設置所有必要的事件監聽器，包括模式切換按鈕、鍵盤快捷鍵和頁面卸載事件
     */
    setupEventListeners() {
        // 模式切換按鈕事件監聽器
        this.elements.modeButtons?.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                this.setAnalysisMode(mode);
            });
        });

        // 全域鍵盤快捷鍵監聽器
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // 頁面卸載時清理資源的事件監聽器
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    /**
     * 處理鍵盤快捷鍵
     * @private
     * @param {KeyboardEvent} e 鍵盤事件對象
     * @description 處理全域鍵盤快捷鍵，提供快速操作功能
     */
    handleKeyboardShortcuts(e) {
        // ESC 鍵 - 緊急停止所有檢測活動
        if (e.key === 'Escape') {
            this.stopAllActivities();
        }

        // Ctrl + 數字鍵 - 快速切換分析模式
        if (e.ctrlKey && e.key >= '1' && e.key <= '6') {
            e.preventDefault(); // 阻止瀏覽器預設行為
            const modes = ['emotion', 'action']; // 支援的模式列表
            const modeIndex = parseInt(e.key) - 1; // 轉換為陣列索引
            if (modes[modeIndex]) {
                this.setAnalysisMode(modes[modeIndex]);
            }
        }
    }

    /**
     * 設置分析模式
     * @public
     * @param {string} mode 目標分析模式 ('emotion', 'action', 'rps', 'drawing')
     * @description 切換應用程式的當前分析模式，更新UI狀態並停止不相容的活動
     */
    setAnalysisMode(mode) {
        // 如果已經是當前模式，無需切換
        if (this.currentMode === mode) return;

        // 停止當前模式的所有活動，避免資源衝突
        this.stopAllActivities();

        // 更新內部狀態
        this.currentMode = mode;

        // 更新用戶界面
        this.updateModeButtons(mode);
        this.updateModeDisplay(mode);

        // 重置標籤頁狀態
        this.resetTabStates(mode);

        // 發送模式切換事件，通知各模組
        document.dispatchEvent(new CustomEvent('modeSwitched', {
            detail: { mode: mode }
        }));

        // 顯示模式切換成功消息
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
     * @private
     * @param {string} activeMode 當前啟用的模式
     * @description 更新模式切換按鈕的視覺狀態，高亮顯示當前模式
     */
    updateModeButtons(activeMode) {
        this.elements.modeButtons?.forEach(button => {
            // 切換 'active' CSS類別來高亮當前模式按鈕
            button.classList.toggle('active', button.dataset.mode === activeMode);
        });
    }

    /**
     * 更新模式顯示面板
     * @private
     * @param {string} mode 當前模式
     * @description 顯示對應模式的內容面板，隱藏其他模式的面板
     */
    updateModeDisplay(mode) {
        const panels = document.querySelectorAll('.analysis-panel');
        panels?.forEach(panel => {
            const isActive = panel.id === `${mode}-panel`;
            // 切換活動狀態和可見性
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
     * 重置標籤頁狀態
     * @private
     * @param {string} mode 當前模式
     * @description 根據新模式重置標籤頁的預設狀態
     */
    resetTabStates(mode) {
        // 情緒模式預設顯示檔案上傳標籤
        if (mode === 'emotion') {
            this.tabSwitcher.switchTo('upload');
        }
        // 動作模式預設顯示遊戲標籤
        else if (mode === 'action') {
            this.tabSwitcher.switchTo('action-game');
        }
        // 石頭剪刀布和繪畫模式沒有標籤頁，不需要重置
    }

    /**
     * 設置應用程式初始狀態
     * @private
     * @description 設置應用程式啟動時的預設狀態
     */
    setInitialState() {
        // 預設啟動情緒分析模式
        this.setAnalysisMode('emotion');
        // 顯示歡迎消息
        this.statusManager.update('請選擇分析模式開始...', STATUS_TYPES.INFO);
    }

    /**
     * 停止所有活動
     * @public
     * @description 緊急停止所有正在運行的檢測和遊戲活動
     */
    stopAllActivities() {
        // 停止情緒即時檢測（只停止分析，保持攝影機運行）
        if (this.modules.emotionRealtime?.isDetectionActive()) {
            this.modules.emotionRealtime.stopDetection();
        }

        // 停止所有遊戲模組
        Object.values(this.modules).forEach(module => {
            if (module && typeof module.stopGame === 'function') {
                module.stopGame();
            }
        });
    }

    /**
     * 獲取應用程式當前狀態
     * @public
     * @returns {Object} 包含當前模式、統計數據和活動模組的狀態對象
     * @description 獲取應用程式的完整狀態信息，用於調試和監控
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
     * 清理應用程式資源
     * @public
     * @description 在頁面卸載或應用程式關閉時清理所有資源
     */
    cleanup() {
        console.log('正在清理應用程式資源...');

        // 停止所有活動
        this.stopAllActivities();

        // 調用各模組的清理方法
        Object.values(this.modules).forEach(module => {
            if (module && typeof module.destroy === 'function') {
                module.destroy();
            }
        });
    }

    /**
     * 清理情緒檔案選擇
     * @public
     * @description 清除情緒分析模組中選擇的檔案
     */
    clearEmotionFileSelection() {
        this.modules.emotionUpload?.clearFile();
    }

    /**
     * 清理動作檔案選擇
     * @public
     * @description 清除動作分析模組中選擇的檔案
     */
    clearActionFileSelection() {
        this.modules.actionUpload?.clearFile();
    }
}

// =============================================================================
// 應用程式入口點和初始化邏輯
//
// 負責應用程式的啟動流程、錯誤處理和全域資源管理。
// 確保應用程式在DOM完全載入後才開始初始化，避免資源載入問題。
// =============================================================================

/**
 * 全域應用程式控制器實例
 * @type {EmotionActionController|null}
 * @description 儲存應用程式控制器實例，供全域訪問和調試使用
 */
let appController = null;

/**
 * DOM載入完成事件監聽器
 * @description 當HTML文檔完全載入後初始化應用程式，確保所有DOM元素都可用
 */
document.addEventListener('DOMContentLoaded', () => {
    try {
        // 創建並初始化主應用程式控制器
        appController = new EmotionActionController();

        // 將控制器實例綁定到全域window對象，方便：
        // 1. 瀏覽器控制台調試
        // 2. HTML內嵌腳本調用
        // 3. 第三方腳本集成
        window.emotionActionApp = appController;

        // 向後兼容性：綁定舊版全域清理函數
        // 這些函數可能被HTML模板或其他腳本直接調用
        window.clearEmotionFileSelection = () => appController.clearEmotionFileSelection();
        window.clearActionFileSelection = () => appController.clearActionFileSelection();

        // 應用程式啟動成功日誌
        console.log('🎉 應用程式啟動成功！');

    } catch (error) {
        // 應用程式初始化失敗的錯誤處理
        console.error('❌ 應用程式初始化失敗:', error);

        // 嘗試在UI上顯示錯誤訊息，讓用戶知道發生了問題
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = '應用程式載入失敗，請刷新頁面重試';
            statusElement.className = 'status error';
        }

        // 可以考慮在這裡添加錯誤報告邏輯
        // 例如發送錯誤信息到服務器進行分析
    }
});

/**
 * 模組導出
 * @description 導出EmotionActionController類別供其他ES6模組使用
 * 這樣其他腳本可以import並實例化自己的控制器實例
 */
export { EmotionActionController };
