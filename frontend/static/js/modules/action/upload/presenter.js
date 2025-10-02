// =============================================================================
// Action Upload Presenter - 動作影片上傳 UI 呈現
// 負責所有 DOM 操作和 UI 更新
// =============================================================================

import { ButtonToggler, DropZoneHandler } from '../../../common/ui-helpers.js';

export class ActionUploadPresenter {
    constructor() {
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

        this.buttonToggler = new ButtonToggler(this.elements.analyzeBtn);
        this.dropZoneHandler = null;
        this.originalDropZoneContent = null;
    }

    setupDropZone(onFileSelect) {
        this.dropZoneHandler = new DropZoneHandler(
            this.elements.dropZone,
            onFileSelect
        );
    }

    setupFileInput(onFileSelect) {
        this.elements.fileInput?.addEventListener('change', (event) => {
            const file = event.target.files?.[0];
            if (file) {
                onFileSelect(file);
            }
        });
    }

    setupForm(onSubmit) {
        this.elements.form?.addEventListener('submit', onSubmit);
    }

    renderFilePreview(file, previewObjectUrl) {
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
        this.loadVideoDuration(file);

        // 載入影片預覽
        this.loadVideoPreview(previewObjectUrl);
    }

    restoreOriginalDropZone() {
        if (!this.elements.dropZone || !this.originalDropZoneContent) return;

        this.elements.dropZone.innerHTML = this.originalDropZoneContent;
        this.elements.dropZone.classList.remove('has-file');
        this.elements.dropZone.classList.remove('drag-over');
    }

    loadVideoDuration(file) {
        const durationEl = this.elements.dropZone?.querySelector('.file-duration');
        if (!durationEl) return;

        const video = document.createElement('video');
        const objectUrl = URL.createObjectURL(file);

        video.src = objectUrl;
        video.onloadedmetadata = () => {
            const minutes = Math.floor(video.duration / 60);
            const seconds = Math.floor(video.duration % 60);
            durationEl.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            URL.revokeObjectURL(objectUrl);
        };

        video.onerror = () => {
            durationEl.textContent = '無法解析長度';
            URL.revokeObjectURL(objectUrl);
        };
    }

    loadVideoPreview(previewObjectUrl) {
        const container = this.elements.dropZone?.querySelector('.media-preview-container');
        if (!container) return;

        const video = document.createElement('video');
        video.src = previewObjectUrl;
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

    showUploadProgress(percent) {
        const progressFillEl = this.elements.dropZone?.querySelector('.progress-fill');
        const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');

        if (progressFillEl) {
            progressFillEl.style.width = `${percent}%`;
        }
        if (progressTextEl) {
            progressTextEl.textContent = `上傳中... ${percent}%`;
        }
    }

    updateUploadProgress(loaded, total, customMessage = null) {
        const progressFillEl = this.elements.dropZone?.querySelector('.progress-fill');
        const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');

        if (progressFillEl && progressTextEl) {
            const percent = Math.min(100, Math.round((loaded / total) * 100));
            progressFillEl.style.width = `${percent}%`;
            progressTextEl.textContent = customMessage || `上傳中... ${percent}%`;
        }
    }

    setProgressComplete(message) {
        const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');
        if (progressTextEl) {
            progressTextEl.textContent = message;
        }
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

    enableAnalyzeButton() {
        setTimeout(() => {
            if (this.elements.analyzeBtn) {
                this.elements.analyzeBtn.disabled = false;
            }
        }, 10);
    }

    disableAnalyzeButton() {
        if (this.elements.analyzeBtn) {
            this.elements.analyzeBtn.disabled = true;
        }
    }

    setButtonLoading(isLoading) {
        this.buttonToggler.toggle(isLoading);
    }

    clearFileInput() {
        if (this.elements.fileInput) {
            this.elements.fileInput.value = '';
        }
    }

    hideResults() {
        this.elements.uploadResults?.classList.add('hidden');
    }

    // Helper methods
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}
