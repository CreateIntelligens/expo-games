/**
 * =============================================================================
 * EmotionUploadController - 情緒上傳控制器
 * =============================================================================
 *
 * 協調 Service 和 Presenter，管理檔案上傳和情緒分析的完整流程。
 * 繼承 BaseModule 提供標準化生命週期管理。
 */

import { BaseModule } from '../../../app/base-module.js';
import { STATUS_TYPES } from '../../../common/constants.js';
import { validateFile } from '../../../common/utils.js';
import { EmotionUploadService } from './service.js';
import { EmotionUploadPresenter } from './presenter.js';

export class EmotionUploadController extends BaseModule {
    constructor(statusManager) {
        super({ name: 'emotion-upload', statusManager });

        this.service = new EmotionUploadService();
        this.presenter = new EmotionUploadPresenter();

        // 當前狀態
        this.selectedFile = null;
        this.selectedFileKind = null;
    }

    /**
     * 初始化控制器 (BaseModule 生命週期)
     */
    async _onInitialize() {
        this.setupEventHandlers();
        console.log('✅ EmotionUploadController 初始化完成');
    }

    /**
     * 設置事件處理函數
     * @private
     */
    setupEventHandlers() {
        this.presenter.bindEvents({
            onFileSelect: (file) => this.handleFileSelection(file),
            onFormSubmit: () => this.analyzeSelectedFile()
        });

        // 清除檔案按鈕 (動態創建，使用事件委派)
        document.addEventListener('click', (event) => {
            if (event.target.id === 'clear-file-btn') {
                this.clearFile();
            }
        });
    }

    /**
     * 處理檔案選擇
     * @param {File} file - 選擇的檔案
     */
    handleFileSelection(file) {
        const validation = validateFile(file);

        if (!validation.valid) {
            this.updateStatus(validation.error, STATUS_TYPES.ERROR);
            return;
        }

        this.selectedFile = file;
        this.selectedFileKind = validation.type;

        this.presenter.renderFilePreview(file, this.selectedFileKind);
        this.presenter.enableAnalyzeButton();

        this.updateStatus(
            `已選擇 ${this.selectedFileKind === 'video' ? '影片' : '圖片'}: ${file.name}`,
            STATUS_TYPES.SUCCESS
        );
    }

    /**
     * 分析選擇的檔案
     */
    analyzeSelectedFile() {
        if (!this.selectedFile) {
            this.updateStatus('請先選擇檔案', STATUS_TYPES.ERROR);
            return;
        }

        this.updateStatus('開始分析...', STATUS_TYPES.INFO);

        if (this.selectedFileKind === 'video') {
            this.analyzeVideoStream();
        } else {
            this.analyzeImageFile();
        }
    }

    /**
     * 分析圖片檔案
     * @private
     */
    analyzeImageFile() {
        this.presenter.progressBar.show();
        this.presenter.buttonToggler.toggle(true);

        this.service.analyzeImageFile(this.selectedFile, {
            onProgress: (loaded, total) => {
                this.presenter.updateUploadProgress(loaded, total);
            },
            onSuccess: (response) => {
                this.presenter.progressBar.hide();
                this.presenter.buttonToggler.toggle(false);
                this.presenter.renderAnalysisResults(response);
                this.updateStatus('圖片分析完成！', STATUS_TYPES.SUCCESS);
            },
            onError: (errorMsg) => {
                this.presenter.progressBar.hide();
                this.presenter.buttonToggler.toggle(false);
                this.updateStatus(`分析失敗: ${errorMsg}`, STATUS_TYPES.ERROR);
            }
        });
    }

    /**
     * 分析影片串流
     * @private
     */
    analyzeVideoStream() {
        this.presenter.buttonToggler.toggle(true);
        this.presenter.initStreamResults();
        this.updateStatus('影片串流分析中...', STATUS_TYPES.INFO);

        this.service.analyzeVideoStream(this.selectedFile, {
            onStreamData: (data) => {
                this.handleStreamResult(data);
            },
            onComplete: () => {
                this.presenter.buttonToggler.toggle(false);
                this.updateStatus('影片分析完成！', STATUS_TYPES.SUCCESS);
            },
            onError: (errorMsg) => {
                this.presenter.buttonToggler.toggle(false);
                this.updateStatus(`串流分析失敗: ${errorMsg}`, STATUS_TYPES.ERROR);
            }
        });
    }

    /**
     * 處理串流結果
     * @param {Object} data - 串流數據
     * @private
     */
    handleStreamResult(data) {
        if (data.error) {
            this.updateStatus(data.error, STATUS_TYPES.ERROR);
            return;
        }

        if (data.completed) {
            if (data.message) {
                this.updateStatus(data.message, STATUS_TYPES.SUCCESS);
            }
            return;
        }

        // 更新 UI
        this.presenter.updateStreamStats(data);
        this.presenter.updateCurrentEmotion(data);
        this.presenter.updateEmotionTimeline(data);
    }

    /**
     * 清除檔案選擇
     */
    clearFile() {
        this.selectedFile = null;
        this.selectedFileKind = null;
        this.presenter.clearFileSelection();
        this.updateStatus('已清除檔案', STATUS_TYPES.INFO);
    }

    /**
     * 銷毀控制器 (BaseModule 生命週期)
     */
    async _onDestroy() {
        this.service.cancelAll();
        this.presenter.destroy();
        this.selectedFile = null;
        this.selectedFileKind = null;
        console.log('✅ EmotionUploadController 已銷毀');
    }
}
