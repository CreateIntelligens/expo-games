// =============================================================================
// Action Upload Controller - 動作影片上傳控制器
// 負責協調 Service 和 Presenter，處理上傳流程
// =============================================================================

import { STATUS_TYPES } from '../../../common/constants.js';
import { BaseModule } from '../../../app/base-module.js';
import { ActionUploadService } from './service.js';
import { ActionUploadPresenter } from './presenter.js';

export class ActionUploadController extends BaseModule {
    constructor(statusManager, options = {}) {
        super({ name: 'action-upload', statusManager });

        this.service = new ActionUploadService();
        this.presenter = new ActionUploadPresenter();
    }

    async _onInitialize() {
        this.setupFileUpload();
        this.setupFormSubmission();
    }

    setupFileUpload() {
        // 設置拖放處理
        this.presenter.setupDropZone((file) => this.handleFileSelection(file));

        // 文件輸入變化
        this.presenter.setupFileInput((file) => this.handleFileSelection(file));
    }

    setupFormSubmission() {
        this.presenter.setupForm((event) => {
            event.preventDefault();
            this.analyzeActionFile();
        });
    }

    handleFileSelection(file) {
        // 驗證檔案
        const validation = this.service.validateFile(file);
        if (!validation.valid) {
            this.updateStatus(validation.message, STATUS_TYPES.ERROR);
            this.clearFileSelection();
            return;
        }

        // 設置檔案
        this.service.setFile(file);

        // 更新 UI
        this.presenter.renderFilePreview(file, this.service.previewObjectUrl);
        this.presenter.enableAnalyzeButton();
        this.presenter.hideResults();

        this.updateStatus(`已選擇影片檔案：${file.name}`, STATUS_TYPES.SUCCESS);
    }

    clearFileSelection() {
        this.service.clearFile();
        this.presenter.restoreOriginalDropZone();
        this.presenter.disableAnalyzeButton();
        this.presenter.clearFileInput();
    }

    analyzeActionFile() {
        const file = this.service.getFile();
        if (!file) {
            this.updateStatus('請先選擇要分析的影片檔案', STATUS_TYPES.WARNING);
            return;
        }

        this.presenter.setButtonLoading(true);
        this.presenter.showUploadProgress(0);
        this.updateStatus('影片上傳中，請稍候...', STATUS_TYPES.PROCESSING);

        this.service.uploadAndAnalyze(
            file,
            // onProgress
            (loaded, total) => {
                this.presenter.updateUploadProgress(loaded, total);
            },
            // onComplete
            (response) => {
                this.presenter.updateUploadProgress(100, 100, '上傳完成，開始分析...');
                this.presenter.setProgressComplete('分析完成');
                this.updateStatus('動作分析完成！', STATUS_TYPES.SUCCESS);
                this.presenter.renderAnalysisResults(response);
                this.presenter.setButtonLoading(false);
            },
            // onError
            (errorMessage) => {
                this.presenter.setProgressComplete('分析失敗');
                this.updateStatus(errorMessage, STATUS_TYPES.ERROR);
                this.presenter.setButtonLoading(false);
            }
        );
    }

    // Public methods
    clearFile() {
        this.clearFileSelection();
    }
}
