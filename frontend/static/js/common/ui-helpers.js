// =============================================================================
// ui-helpers.js - UI 輔助函數
// =============================================================================

import { STATUS_TYPES } from './constants.js';

/**
 * 狀態更新管理器
 */
export class StatusManager {
    constructor(statusElement) {
        this.statusElement = statusElement;
    }

    /**
     * 更新狀態顯示
     * @param {string} message - 狀態訊息
     * @param {string} type - 狀態類型
     */
    update(message, type = STATUS_TYPES.INFO) {
        if (!this.statusElement) return;

        this.statusElement.textContent = message;
        this.statusElement.className = `status ${type}`;

        // 自動清除成功和警告訊息
        if (type === STATUS_TYPES.SUCCESS || type === STATUS_TYPES.WARNING) {
            setTimeout(() => {
                if (this.statusElement.textContent === message) {
                    this.update('', STATUS_TYPES.INFO);
                }
            }, 3000);
        }
    }
}

/**
 * 按鈕狀態切換器
 */
export class ButtonToggler {
    constructor(button) {
        this.button = button;
        this.textNode = button?.querySelector('.btn-text');
        this.spinnerNode = button?.querySelector('.btn-spinner');
    }

    /**
     * 切換按鈕狀態
     * @param {boolean} isLoading - 是否為載入狀態
     */
    toggle(isLoading) {
        if (!this.button) return;

        this.button.disabled = isLoading;

        if (this.textNode) {
            this.textNode.style.display = isLoading ? 'none' : 'inline-flex';
        }

        if (this.spinnerNode) {
            this.spinnerNode.style.display = isLoading ? 'inline-flex' : 'none';
        }
    }
}

/**
 * 進度條控制器
 */
export class ProgressBar {
    constructor(container) {
        this.container = container;
        this.fillElement = container?.querySelector('.progress-fill');
        this.textElement = container?.querySelector('.progress-percentage');
    }

    /**
     * 更新進度
     * @param {number} loaded - 已載入量
     * @param {number} total - 總量
     */
    update(loaded, total) {
        if (!this.container) return;

        const percent = Math.min(100, Math.round((loaded / total) * 100));

        if (this.fillElement) {
            this.fillElement.style.width = `${percent}%`;
        }

        if (this.textElement) {
            this.textElement.textContent = `${percent}%`;
        }
    }

    /**
     * 顯示進度條
     */
    show() {
        this.container?.classList.remove('hidden');
    }

    /**
     * 隱藏進度條
     */
    hide() {
        this.container?.classList.add('hidden');
    }
}

/**
 * 模態框控制器
 */
export class ModalController {
    constructor(modalElement) {
        this.modal = modalElement;
        this.setupEventListeners();
    }

    setupEventListeners() {
        if (!this.modal) return;

        // 點擊背景關閉
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.hide();
            }
        });

        // ESC 鍵關閉
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.modal.classList.contains('hidden')) {
                this.hide();
            }
        });
    }

    /**
     * 顯示模態框
     */
    show() {
        this.modal?.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    /**
     * 隱藏模態框
     */
    hide() {
        this.modal?.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

/**
 * 標籤切換器
 */
export class TabSwitcher {
    constructor(tabButtons, tabContents) {
        this.tabButtons = tabButtons;
        this.tabContents = tabContents;
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.tabButtons?.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.dataset.tab;
                this.switchTo(tabId);
            });
        });
    }

    /**
     * 切換到指定標籤
     * @param {string} tabId - 標籤ID
     */
    switchTo(tabId) {
        // 更新按鈕狀態
        this.tabButtons?.forEach(button => {
            button.classList.toggle('active', button.dataset.tab === tabId);
        });

        // 更新內容顯示
        this.tabContents?.forEach(content => {
            content.classList.toggle('active', content.id === `${tabId}-tab`);
        });

        // 發送自定義事件通知標籤切換
        document.dispatchEvent(new CustomEvent('tabSwitched', {
            detail: { tabId: tabId }
        }));
    }
}

/**
 * 拖放處理器
 */
export class DropZoneHandler {
    constructor(dropZone, onFileDrop) {
        this.dropZone = dropZone;
        this.onFileDrop = onFileDrop;
        this.setupEventListeners();
    }

    setupEventListeners() {
        if (!this.dropZone) return;

        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            this.dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
        });

        this.dropZone.addEventListener('dragenter', () => {
            this.dropZone.classList.add('drag-over');
        });

        this.dropZone.addEventListener('dragover', () => {
            this.dropZone.classList.add('drag-over');
        });

        this.dropZone.addEventListener('dragleave', () => {
            this.dropZone.classList.remove('drag-over');
        });

        this.dropZone.addEventListener('drop', (e) => {
            const file = e.dataTransfer?.files?.[0];
            this.dropZone.classList.remove('drag-over');
            if (file && this.onFileDrop) {
                this.onFileDrop(file);
            }
        });

        this.dropZone.addEventListener('click', () => {
            const fileInput = this.dropZone.querySelector('input[type="file"]');
            fileInput?.click();
        });
    }
}

/**
 * 通知系統
 */
export class NotificationSystem {
    constructor() {
        this.container = this.createContainer();
    }

    createContainer() {
        let container = document.getElementById('notifications');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notifications';
            container.className = 'notifications-container';
            document.body.appendChild(container);
        }
        return container;
    }

    /**
     * 顯示通知
     * @param {string} message - 通知訊息
     * @param {string} type - 通知類型
     * @param {number} duration - 顯示時間
     */
    show(message, type = 'info', duration = 3000) {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;

        this.container.appendChild(notification);

        // 動畫效果
        setTimeout(() => notification.classList.add('show'), 10);

        // 自動移除
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                if (notification.parentNode) {
                    this.container.removeChild(notification);
                }
            }, 300);
        }, duration);
    }
}
