// =============================================================================
// action-upload.js - 動作上傳分析模組
// =============================================================================

import { STATUS_TYPES, SUPPORTED_VIDEO_TYPES, SUPPORTED_VIDEO_EXTENSIONS } from '../common/constants.js';
import { ButtonToggler, DropZoneHandler } from '../common/ui-helpers.js';

export class ActionUploadModule {
    constructor(statusManager) {
        this.statusManager = statusManager;
        this.selectedFile = null;
        this.previewObjectUrl = null;

        // DOM elements
        this.elements = {
            form: document.getElementById('action-upload-form'),
            dropZone: document.getElementById('action-drop-zone'),
            fileInput: document.getElementById('action-file-input'),
            filePreview: document.getElementById('action-file-preview'),
            uploadResults: document.getElementById('action-upload-results'),
            uploadContent: document.getElementById('action-upload-content'),
            analyzeBtn: document.getElementById('action-analyze-btn')
        };

        // UI controllers
        this.buttonToggler = new ButtonToggler(this.elements.analyzeBtn);

        this.init();
    }

    init() {
        this.setupFileUpload();
        this.setupFormSubmission();
    }

    setupFileUpload() {
        // 設置拖放處理
        this.dropZoneHandler = new DropZoneHandler(
            this.elements.dropZone,
            (file) => this.handleFileSelection(file)
        );

        // 文件輸入變化
        this.elements.fileInput?.addEventListener('change', (event) => {
            const file = event.target.files?.[0];
            if (file) {
                this.handleFileSelection(file);
            }
        });
    }

    setupFormSubmission() {
        this.elements.form?.addEventListener('submit', (event) => {
            event.preventDefault();
            this.analyzeActionFile();
        });
    }

    handleFileSelection(file) {
        // 只接受影片檔案
        if (!SUPPORTED_VIDEO_TYPES.includes(file.type.toLowerCase()) &&
            !SUPPORTED_VIDEO_EXTENSIONS.includes(this.getFileExtension(file.name))) {
            this.statusManager.update('請選擇影片檔案（MP4、AVI、MOV等格式）', STATUS_TYPES.ERROR);
            this.clearFileSelection();
            return;
        }

        if (file.size > 100 * 1024 * 1024) { // 100MB 限制
            this.statusManager.update('影片檔案大小超過限制（100MB）', STATUS_TYPES.ERROR);
            this.clearFileSelection();
            return;
        }

        this.selectedFile = file;
        this.renderFilePreview(file);

        setTimeout(() => {
            if (this.elements.analyzeBtn) {
                this.elements.analyzeBtn.disabled = false;
            }
        }, 10);

        this.elements.uploadResults?.classList.add('hidden');
        this.statusManager.update(`已選擇影片檔案：${file.name}`, STATUS_TYPES.SUCCESS);
    }

    renderFilePreview(file) {
        if (!this.elements.dropZone) return;

        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
            this.previewObjectUrl = null;
        }

        this.previewObjectUrl = URL.createObjectURL(file);

        // 直接替換拖放區域的內容
        this.replaceDropZoneWithPreview(file);
    }

    clearFileSelection() {
        this.selectedFile = null;

        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
            this.previewObjectUrl = null;
        }

        // 恢復原始的拖放區域
        this.restoreOriginalDropZone();

        if (this.elements.analyzeBtn) {
            this.elements.analyzeBtn.disabled = true;
        }
        if (this.elements.fileInput) {
            this.elements.fileInput.value = '';
        }
    }

    analyzeActionFile() {
        if (!this.selectedFile) {
            this.statusManager.update('請先選擇要分析的影片檔案', STATUS_TYPES.WARNING);
            return;
        }

        const formData = new FormData();
        formData.append('file', this.selectedFile);

        this.buttonToggler.toggle(true);
        this.statusManager.update('影片上傳中，請稍候...', STATUS_TYPES.PROCESSING);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/action/analyze');

        xhr.upload.onprogress = (event) => {
            const total = event.total || this.selectedFile.size || 1;
            this.updateUploadProgress(event.loaded, total);
        };

        xhr.onload = () => {
            // 上傳完成，開始分析階段
            const progressFillEl = this.elements.dropZone?.querySelector('.progress-fill');
            const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');

            if (progressFillEl) progressFillEl.style.width = '100%';
            if (progressTextEl) progressTextEl.textContent = '上傳完成，開始分析...';

            try {
                const response = JSON.parse(xhr.responseText);
                if (xhr.status >= 200 && xhr.status < 300) {
                    // 分析成功
                    if (progressTextEl) progressTextEl.textContent = '分析完成';
                    this.statusManager.update('動作分析完成！', STATUS_TYPES.SUCCESS);
                    this.renderAnalysisResults(response);
                } else if (response.error) {
                    if (progressTextEl) progressTextEl.textContent = '分析失敗';
                    this.statusManager.update(response.error, STATUS_TYPES.ERROR);
                } else {
                    if (progressTextEl) progressTextEl.textContent = '分析失敗';
                    this.statusManager.update('動作分析失敗', STATUS_TYPES.ERROR);
                }
            } catch (error) {
                if (progressTextEl) progressTextEl.textContent = '處理失敗';
                this.statusManager.update('無法解析伺服器回應', STATUS_TYPES.ERROR);
            }

            this.buttonToggler.toggle(false);
        };

        xhr.onerror = () => {
            this.buttonToggler.toggle(false);
            const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');
            if (progressTextEl) progressTextEl.textContent = '上傳失敗';
            this.statusManager.update('上傳過程中發生錯誤，請稍後再試。', STATUS_TYPES.ERROR);
        };

        xhr.send(formData);
    }

    renderAnalysisResults(response) {
        if (!this.elements.uploadContent) return;

        this.elements.uploadContent.innerHTML = `
            <div class="results-grid">
                <article class="result-card">
                    <div class="result-card__header">
                        <h3>🤸 動作分析結果</h3>
                        <p class="result-card__summary">影片動作檢測完成</p>
                    </div>
                    <div class="metric-grid">
                        <div class="metric">
                            <span class="metric-label">檢測結果</span>
                            <span class="metric-value">${response.message || '分析完成'}</span>
                        </div>
                    </div>
                </article>
            </div>
        `;

        this.elements.uploadResults?.classList.remove('hidden');
        this.elements.uploadResults?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Helper methods
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getFileExtension(filename) {
        const lastDot = filename.lastIndexOf('.');
        return lastDot === -1 ? '' : filename.substring(lastDot).toLowerCase();
    }

    loadVideoDuration(file, targetElement) {
        const video = document.createElement('video');
        const objectUrl = URL.createObjectURL(file);

        video.src = objectUrl;
        video.onloadedmetadata = () => {
            const minutes = Math.floor(video.duration / 60);
            const seconds = Math.floor(video.duration % 60);
            targetElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            URL.revokeObjectURL(objectUrl);
        };

        video.onerror = () => {
            targetElement.textContent = '無法解析長度';
            URL.revokeObjectURL(objectUrl);
        };
    }

    updateUploadProgress(loaded, total) {
        // 更新拖放區域中的進度條
        const progressFillEl = this.elements.dropZone?.querySelector('.progress-fill');
        const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');

        if (progressFillEl && progressTextEl) {
            const percent = Math.min(100, Math.round((loaded / total) * 100));
            progressFillEl.style.width = `${percent}%`;
            progressTextEl.textContent = `上傳中... ${percent}%`;
        }
    }

    replaceDropZoneWithPreview(file) {
        if (!this.elements.dropZone) return;

        // 保存原始內容（第一次替換時）
        if (!this.originalDropZoneContent) {
            this.originalDropZoneContent = this.elements.dropZone.innerHTML;
        }

        // 創建新的預覽內容
        const previewHTML = `
            <div class="file-preview-content">
                <div class="file-info">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${this.formatFileSize(file.size)}</div>
                    <div class="file-duration">解析影片長度中...</div>
                </div>
                <div class="media-preview-container">
                    <div class="video-placeholder">🎬 影片載入中...</div>
                </div>
                <div class="file-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                    <span class="progress-text">檔案已選擇，準備上傳</span>
                </div>
                <button type="button" class="remove-file-btn" onclick="clearActionFileSelection()" aria-label="移除檔案">✕</button>
            </div>
        `;

        this.elements.dropZone.innerHTML = previewHTML;
        this.elements.dropZone.classList.add('has-file');

        // 載入影片時長
        const durationEl = this.elements.dropZone.querySelector('.file-duration');
        if (durationEl) {
            this.loadVideoDuration(file, durationEl);
        }

        // 載入影片預覽
        this.loadVideoPreview();
    }

    restoreOriginalDropZone() {
        if (!this.elements.dropZone || !this.originalDropZoneContent) return;

        this.elements.dropZone.innerHTML = this.originalDropZoneContent;
        this.elements.dropZone.classList.remove('has-file');
        this.elements.dropZone.classList.remove('drag-over');
    }

    loadVideoPreview() {
        const container = this.elements.dropZone?.querySelector('.media-preview-container');
        if (!container) return;

        const video = document.createElement('video');
        video.src = this.previewObjectUrl;
        video.controls = true;
        video.muted = true;
        video.className = 'preview-video';
        video.style.cssText = 'max-width: 100%; max-height: 200px; border-radius: 8px;';

        video.onloadedmetadata = () => {
            container.innerHTML = '';
            container.appendChild(video);
        };

        video.onerror = () => {
            container.innerHTML = '<div class="preview-error">❌ 影片預覽載入失敗</div>';
        };
    }

    // Public methods
    clearFile() {
        this.clearFileSelection();
    }
}