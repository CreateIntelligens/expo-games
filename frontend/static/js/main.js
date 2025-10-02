// =============================================================================
// main.js - AI互動遊戲展場主控制器 (使用 ModuleRegistry 架構)
//
// 負責協調和管理整個AI互動體驗平台的所有功能模組，
// 使用標準化的模組生命週期管理和事件總線系統。
// =============================================================================

import { ANALYSIS_MODES, STATUS_TYPES } from './common/constants.js';
import { StatusManager, TabSwitcher } from './common/ui-helpers.js';
import { ModuleRegistry, FLAT_MODULE_LOADERS, MODULE_LOADERS } from './app/module-registry.js';

/**
 * 主應用控制器（使用 ModuleRegistry）
 */
class AppController {
    constructor() {
        this.currentMode = null;
        this.statusManager = null;
        this.tabSwitcher = null;
        this.registry = null;

        this.elements = {
            status: document.getElementById('status-container'),
            modeButtons: document.querySelectorAll('.mode-btn'),
            analysisTabButtons: document.querySelectorAll('.tab-btn'),
            tabContents: document.querySelectorAll('.tab-content')
        };

        this.init();
    }

    async init() {
        // 初始化狀態管理器
        this.initStatusManager();

        // 初始化標籤切換器
        this.initTabSwitcher();

        // 初始化模組註冊表
        await this.initModuleRegistry();

        // 設置事件監聽器
        this.setupEventListeners();

        // 設置初始狀態
        await this.setInitialState();

        console.log('🎉 應用程式已初始化（使用 ModuleRegistry 架構）');
    }

    initStatusManager() {
        const statusElement = this.elements.status?.querySelector('.status-message') || this.elements.status;
        this.statusManager = new StatusManager(statusElement);
    }

    initTabSwitcher() {
        this.tabSwitcher = new TabSwitcher(
            this.elements.analysisTabButtons,
            this.elements.tabContents
        );
    }

    async initModuleRegistry() {
        this.registry = new ModuleRegistry(this.statusManager, {
            enableLogging: true
        });

        // 註冊所有模組
        for (const [moduleName, loader] of Object.entries(FLAT_MODULE_LOADERS)) {
            this.registry.register(moduleName, loader);
        }

        console.log('📋 模組註冊完成:', Object.keys(FLAT_MODULE_LOADERS).join(', '));
    }

    setupEventListeners() {
        // 模式切換按鈕
        this.elements.modeButtons?.forEach(button => {
            button.addEventListener('click', () => {
                const mode = button.dataset.mode;
                this.setAnalysisMode(mode);
            });
        });

        // 鍵盤快捷鍵
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });

        // 頁面卸載清理
        window.addEventListener('beforeunload', () => {
            this.cleanup();
        });
    }

    handleKeyboardShortcuts(e) {
        // ESC - 停止所有活動
        if (e.key === 'Escape') {
            this.stopAllActivities();
        }

        // Ctrl + 數字 - 快速切換模式
        if (e.ctrlKey && e.key >= '1' && e.key <= '6') {
            e.preventDefault();
            const modes = ['emotion', 'action', 'rps', 'drawing'];
            const modeIndex = parseInt(e.key) - 1;
            if (modes[modeIndex]) {
                this.setAnalysisMode(modes[modeIndex]);
            }
        }
    }

    async setAnalysisMode(mode) {
        if (this.currentMode === mode) {
            return;
        }

        console.log(`🔄 切換模式: ${this.currentMode} → ${mode}`);

        // 停止所有活動模組
        await this.stopAllActivities();

        // 更新狀態
        this.currentMode = mode;
        this.updateModeButtons(mode);
        this.updateModeDisplay(mode);
        this.resetTabStates(mode);

        // 根據模式啟動對應模組
        await this.activateModeModules(mode);

        // 發送模式切換事件
        document.dispatchEvent(new CustomEvent('modeSwitched', {
            detail: { mode }
        }));

        const modeNames = {
            'emotion': '情緒分析',
            'action': '動作偵測',
            'rps': '猜拳',
            'drawing': '畫布'
        };

        this.statusManager.update(`已切換到${modeNames[mode] || mode}模式`, STATUS_TYPES.INFO);
    }

    async activateModeModules(mode) {
        try {
            switch (mode) {
                case 'emotion':
                    // 情緒模式：初始化模組以設置事件監聽器
                    this.registry.get('emotion-upload');
                    this.registry.get('emotion-realtime');
                    break;

                case 'action':
                    // 動作模式：初始化模組
                    this.registry.get('action-upload');
                    this.registry.get('action-game');
                    break;

                case 'rps':
                    // RPS 遊戲自動啟動
                    const rpsModule = this.registry.get('rps');
                    if (rpsModule && typeof rpsModule.activate === 'function') {
                        await rpsModule.activate();
                    }
                    break;

                case 'drawing':
                    // 繪畫模式：初始化模組（會自動監聽事件並開啟攝影機）
                    this.registry.get('gesture-drawing');
                    break;
            }
        } catch (error) {
            console.error('❌ 模組啟動失敗:', error);
            this.statusManager.update('模組啟動失敗，請重試', STATUS_TYPES.ERROR);
        }
    }

    updateModeButtons(activeMode) {
        this.elements.modeButtons?.forEach(button => {
            button.classList.toggle('active', button.dataset.mode === activeMode);
        });
    }

    updateModeDisplay(mode) {
        const panels = document.querySelectorAll('.analysis-panel');
        panels?.forEach(panel => {
            const isActive = panel.id === `${mode}-panel`;
            panel.classList.toggle('active', isActive);
            if (isActive) {
                panel.classList.remove('hidden');
                panel.style.display = 'block';
            } else {
                panel.classList.add('hidden');
                panel.style.display = 'none';
            }
        });
    }

    resetTabStates(mode) {
        if (mode === 'emotion') {
            this.tabSwitcher.switchTo('upload');
        } else if (mode === 'action') {
            this.tabSwitcher.switchTo('action-game');
        }
    }

    async setInitialState() {
        await this.setAnalysisMode('emotion');
        this.statusManager.update('請選擇分析模式開始...', STATUS_TYPES.INFO);
    }

    async stopAllActivities() {
        // 停止所有活躍模組
        const activeModules = this.registry.getAllActive();
        for (const [moduleName, module] of activeModules.entries()) {
            try {
                // 嘗試調用 deactivate 方法
                if (module && typeof module.deactivate === 'function') {
                    await module.deactivate();
                    console.log(`✅ 已停用模組: ${moduleName}`);
                }
            } catch (error) {
                console.error(`❌ 停用模組 ${moduleName} 失敗:`, error);
            }
        }
    }

    getAppState() {
        return {
            currentMode: this.currentMode,
            registryStats: this.registry.getStats(),
            activeModules: Array.from(this.registry.getAllActive().keys())
        };
    }

    async cleanup() {
        console.log('🧹 正在清理應用程式資源...');
        await this.registry.cleanup();
    }

    // 清理情緒檔案選擇的方法（供 HTML onclick 調用）
    clearEmotionFileSelection() {
        const module = this.registry.get('emotion-upload');
        if (module && typeof module.clearFile === 'function') {
            module.clearFile();
        }
    }

    clearActionFileSelection() {
        const module = this.registry.get('action-upload');
        if (module && typeof module.clearFile === 'function') {
            module.clearFile();
        }
    }
}

// =============================================================================
// 應用程式入口點
// =============================================================================

let appController = null;

document.addEventListener('DOMContentLoaded', async () => {
    try {
        appController = new AppController();

        // 綁定到全域
        window.emotionActionApp = appController;
        window.clearEmotionFileSelection = () => appController.clearEmotionFileSelection();
        window.clearActionFileSelection = () => appController.clearActionFileSelection();

        console.log('🎉 應用程式啟動成功！');

    } catch (error) {
        console.error('❌ 應用程式初始化失敗:', error);

        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.textContent = '應用程式載入失敗，請刷新頁面重試';
            statusElement.className = 'status error';
        }
    }
});

export { AppController };
