// =============================================================================
// emotion-upload.js - 情緒上傳分析模組
//
// 負責處理檔案上傳和情緒分析的模組，支援圖片和影片檔案的拖放上傳、
// 即時預覽、進度追蹤和串流分析結果顯示。
//
// 主要功能：
// - 檔案驗證和拖放上傳
// - 媒體檔案預覽
// - 圖片靜態分析
// - 影片串流分析
// - 分析結果視覺化
// =============================================================================

import { validateFile } from '../common/utils.js';
import { EMOTION_EMOJIS, STATUS_TYPES } from '../common/constants.js';
import { ButtonToggler, ProgressBar, DropZoneHandler } from '../common/ui-helpers.js';

/**
 * 情緒上傳分析模組類別
 * @class EmotionUploadModule
 */
export class EmotionUploadModule {
    /**
     * 建構函式
     * @param {StatusManager} statusManager - 狀態管理器實例
     */
    constructor(statusManager) {
        /**
         * 狀態管理器實例
         * @type {StatusManager}
         */
        this.statusManager = statusManager;

        /**
         * 當前選擇的檔案
         * @type {File|null}
         */
        this.selectedFile = null;

        /**
         * 檔案類型 ('image' 或 'video')
         * @type {string|null}
         */
        this.selectedFileKind = null;

        /**
         * 檔案預覽的Object URL
         * @type {string|null}
         */
        this.previewObjectUrl = null;

        // 防止重複分析的標記
        this.isAnalyzingImage = false;
        this.isAnalyzingVideo = false;

        // DOM 元素引用
        this.elements = {
            form: document.getElementById('emotion-upload-form'),
            dropZone: document.getElementById('emotion-drop-zone'),
            fileInput: document.getElementById('emotion-file-input'),
            filePreview: document.getElementById('emotion-file-preview'),
            uploadProgress: document.getElementById('emotion-upload-progress'),
            uploadResults: document.getElementById('emotion-upload-results'),
            uploadContent: document.getElementById('emotion-upload-content'),
            analyzeBtn: document.getElementById('emotion-analyze-btn')
        };

        // UI 控制器
        this.buttonToggler = new ButtonToggler(this.elements.analyzeBtn);
        this.progressBar = new ProgressBar(this.elements.uploadProgress);

        this.init();
    }

    /**
     * 初始化模組
     * @private
     * @description 設置檔案上傳和表單提交的事件監聽器
     */
    init() {
        this.setupFileUpload();
        this.setupFormSubmission();
    }

    /**
     * 設置檔案上傳功能
     * @private
     * @description 初始化拖放處理器和檔案輸入監聽器
     */
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

    /**
     * 設置表單提交處理
     * @private
     * @description 攔截表單提交事件並觸發檔案分析
     */
    setupFormSubmission() {
        this.elements.form?.addEventListener('submit', (event) => {
            event.preventDefault();
            this.analyzeSelectedFile();
        });
    }

    /**
     * 處理檔案選擇
     * @private
     * @param {File} file - 選擇的檔案物件
     * @description 驗證檔案並設置為當前選擇的檔案，顯示預覽並啟用分析按鈕
     */
    handleFileSelection(file) {
        const validation = validateFile(file);
        if (!validation.valid) {
            this.statusManager.update(validation.message, STATUS_TYPES.ERROR);
            this.clearFileSelection();
            return;
        }

        this.selectedFile = file;
        this.selectedFileKind = validation.type;

        this.renderFilePreview(file);

        // 確保按鈕立即啟用，使用setTimeout避免競態條件
        setTimeout(() => {
            if (this.elements.analyzeBtn) {
                this.elements.analyzeBtn.disabled = false;
            }
        }, 10);

        this.elements.uploadResults?.classList.add('hidden');
        this.statusManager.update(`已選擇檔案：${file.name}`, STATUS_TYPES.SUCCESS);
    }

    /**
     * 渲染檔案預覽
     * @private
     * @param {File} file - 要預覽的檔案
     * @description 創建檔案的Object URL並替換拖放區域為預覽界面
     */
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

    /**
     * 清除檔案選擇
     * @private
     * @description 重置所有檔案相關狀態，恢復原始拖放區域
     */
    clearFileSelection() {
        this.selectedFile = null;
        this.selectedFileKind = null;

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

    /**
     * 分析選擇的檔案
     * @private
     * @description 根據檔案類型選擇合適的分析方法（圖片或影片）
     */
    analyzeSelectedFile() {
        if (!this.selectedFile) {
            this.statusManager.update('請先選擇要分析的檔案', STATUS_TYPES.WARNING);
            return;
        }

        // 根據文件類型選擇不同的分析方式
        if (this.selectedFileKind === 'video') {
            this.analyzeVideoStream();
        } else {
            this.analyzeImageFile();
        }
    }

    /**
     * 分析圖片檔案
     * @private
     * @async
     * @description 上傳圖片檔案到服務器進行情緒分析，顯示上傳進度和處理結果
     */
    analyzeImageFile() {
        // 防止重複圖片分析
        if (this.isAnalyzingImage) {
            this.statusManager.update('圖片分析已在進行中，請稍候...', STATUS_TYPES.WARNING);
            return;
        }

        this.isAnalyzingImage = true;

        const formData = new FormData();
        formData.append('file', this.selectedFile);

        this.buttonToggler.toggle(true);
        this.statusManager.update('圖片上傳中，請稍候...', STATUS_TYPES.PROCESSING);
        this.progressBar.show();

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/emotion/analyze/image');

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
                if (xhr.status >= 200 && xhr.status < 300 && response.face_detected) {
                    // 分析成功
                    if (progressTextEl) progressTextEl.textContent = '分析完成';
                    this.statusManager.update(`檢測到情緒: ${response.emotion_zh}`, STATUS_TYPES.SUCCESS);
                    this.renderAnalysisResults(response);
                } else if (response.error) {
                    if (progressTextEl) progressTextEl.textContent = '分析失敗';
                    this.statusManager.update(response.error, STATUS_TYPES.ERROR);
                } else {
                    if (progressTextEl) progressTextEl.textContent = '分析失敗';
                    this.statusManager.update('未檢測到人臉或分析失敗', STATUS_TYPES.ERROR);
                }
            } catch (error) {
                if (progressTextEl) progressTextEl.textContent = '處理失敗';
                this.statusManager.update('無法解析伺服器回應', STATUS_TYPES.ERROR);
            }

            this.buttonToggler.toggle(false);
            this.isAnalyzingImage = false;
            setTimeout(() => this.progressBar.hide(), 600);
        };

        xhr.onerror = () => {
            this.buttonToggler.toggle(false);
            this.isAnalyzingImage = false; // 重置分析狀態
            this.progressBar.hide();
            this.statusManager.update('上傳過程中發生錯誤，請稍後再試。', STATUS_TYPES.ERROR);
        };

        xhr.send(formData);
    }

    /**
     * 分析影片串流
     * @private
     * @async
     * @description 上傳影片檔案並處理服務器端串流分析結果，實時顯示分析進度和情緒變化
     */
    analyzeVideoStream() {
        // 防止重複影片分析
        if (this.isAnalyzingVideo) {
            this.statusManager.update('影片分析已在進行中，請稍候...', STATUS_TYPES.WARNING);
            return;
        }

        this.isAnalyzingVideo = true;

        const formData = new FormData();
        formData.append('file', this.selectedFile);
        formData.append('frame_interval', '0.5');

        this.buttonToggler.toggle(true);
        this.statusManager.update('影片上傳中，準備開始串流分析...', STATUS_TYPES.PROCESSING);
        this.progressBar.show();

        fetch('/api/emotion/analyze/video', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.body;
        })
        .then(body => {
            this.statusManager.update('開始串流分析，逐幀檢測情緒...', STATUS_TYPES.PROCESSING);
            this.initStreamResults();

            const reader = body.getReader();
            const decoder = new TextDecoder();

            const readStream = () => {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        this.buttonToggler.toggle(false);
                        this.progressBar.hide();
                        this.statusManager.update('影片分析完成！', STATUS_TYPES.SUCCESS);
                        return;
                    }

                    const chunk = decoder.decode(value, { stream: true });
                    const lines = chunk.split('\n');

                    for (let line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.slice(6));
                                this.handleStreamResult(data);
                            } catch (e) {
                                console.error('解析串流數據失敗:', e);
                            }
                        }
                    }

                    readStream();
                }).catch(error => {
                    this.buttonToggler.toggle(false);
                    this.progressBar.hide();
                    this.statusManager.update(`串流分析錯誤: ${error.message}`, STATUS_TYPES.ERROR);
                });
            };

            readStream();
        })
        .catch(error => {
            this.buttonToggler.toggle(false);
            this.progressBar.hide();
            this.statusManager.update(`上傳失敗: ${error.message}`, STATUS_TYPES.ERROR);
        });
    }

    updateUploadProgress(loaded, total) {
        this.progressBar.update(loaded, total);

        // 更新拖放區域中的進度條
        const progressFillEl = this.elements.dropZone?.querySelector('.progress-fill');
        const progressTextEl = this.elements.dropZone?.querySelector('.progress-text');

        if (progressFillEl && progressTextEl) {
            const percent = Math.min(100, Math.round((loaded / total) * 100));
            progressFillEl.style.width = `${percent}%`;
            progressTextEl.textContent = `上傳中... ${percent}%`;
        }
    }

    renderAnalysisResults(response) {
        if (!this.elements.uploadContent) return;

        const summaryCard = this.buildSummaryCard(response);

        this.elements.uploadContent.innerHTML = `<div class="results-grid">${summaryCard}</div>`;
        this.elements.uploadResults?.classList.remove('hidden');
        
        // 隱藏檔案預覽和進度條
        this.elements.filePreview?.classList.add('hidden');
        this.progressBar.hide();
        
        this.elements.uploadResults?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    buildSummaryCard(results) {
        const emotionLabel = results.emotion_zh || '中性';
        const emoji = results.emoji || EMOTION_EMOJIS[emotionLabel] || '🎭';
        const confidenceValue = results.confidence || 0;
        const confidencePercent = Math.round(confidenceValue * 100);
        const confidenceClass = this.getConfidenceClass(confidenceValue);

        return `
            <article class="result-card">
                <div class="result-card__header">
                    <h3>${emoji} ${emotionLabel}</h3>
                </div>
                <div class="metric-grid">
                    <div class="metric">
                        <span class="metric-label">信心度</span>
                        <span class="metric-value confidence ${confidenceClass}">${confidencePercent}%</span>
                    </div>
                </div>
            </article>
        `;
    }

    buildDistributionCard(results) {
        if (!results.raw_scores) return '';

        const emotionMapping = {
            'happy': '開心',
            'sad': '悲傷',
            'angry': '生氣',
            'surprise': '驚訝',
            'fear': '恐懼',
            'disgust': '厭惡',
            'neutral': '中性'
        };

        const distributionRows = Object.entries(results.raw_scores)
            .sort(([, a], [, b]) => b - a)
            .map(([emotionEn, score]) => {
                const emotionZh = emotionMapping[emotionEn] || emotionEn;
                const emoji = EMOTION_EMOJIS[emotionZh] || '🎭';
                const percentage = score * 100;
                return `
                    <div class="distribution-row">
                        <div class="distribution-label">${emoji} ${emotionZh}</div>
                        <div class="distribution-bar">
                            <div class="distribution-fill" style="width: ${percentage}%"></div>
                        </div>
                        <div class="distribution-meta">
                            <span>${percentage.toFixed(1)}%</span>
                        </div>
                    </div>
                `;
            })
            .join('');

        return `
            <article class="result-card">
                <div class="result-card__header">
                    <h3>📊 DeepFace 情緒分析</h3>
                    <p class="result-card__summary">各情緒的檢測分數</p>
                </div>
                <div class="distribution-grid">
                    <div class="distribution-header"><span>情緒</span><span>分數</span></div>
                    ${distributionRows}
                </div>
            </article>
        `;
    }

    // Stream analysis methods
    streamResults = [];
    currentStreamFrame = 0;

    initStreamResults() {
        this.streamResults = [];
        this.currentStreamFrame = 0;

        if (this.elements.uploadContent) {
            this.elements.uploadContent.innerHTML = `
                <div class="stream-analysis">
                    <div class="stream-header">
                        <h3>🎬 影片串流分析</h3>
                        <div class="stream-stats">
                            <span>已分析: <span id="stream-frame-count">0</span> 幀</span>
                            <span class="divider"></span>
                            <span>進度: <span id="stream-progress">0%</span></span>
                            <span class="divider"></span>
                            <span>時間: <span id="stream-time">0.00s</span></span>
                        </div>
                    </div>
                    <div class="current-emotion">
                        <div class="emotion-display" id="current-emotion-display">
                            <div class="emotion-icon">🎭</div>
                            <div class="emotion-info">
                                <div class="emotion-name">準備中...</div>
                                <div class="emotion-confidence">等待分析</div>
                            </div>
                        </div>
                    </div>
                    <div class="emotion-timeline" id="emotion-timeline">
                        <h4>情緒時間軸</h4>
                        <div class="timeline-container"></div>
                    </div>
                </div>
            `;
        }

        this.elements.uploadResults?.classList.remove('hidden');
        this.elements.uploadResults?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    handleStreamResult(data) {
        if (data.error) {
            this.statusManager.update(data.error, STATUS_TYPES.ERROR);
            return;
        }

        if (data.completed) {
            if (data.message) {
                this.statusManager.update(data.message, STATUS_TYPES.SUCCESS);
            }
            return;
        }

        this.currentStreamFrame++;
        this.streamResults.push(data);

        this.updateStreamStats(data);
        this.updateCurrentEmotion(data);
        this.updateEmotionTimeline(data);
    }

    updateStreamStats(data) {
        const frameCountEl = document.getElementById('stream-frame-count');
        const progressEl = document.getElementById('stream-progress');
        const timeEl = document.getElementById('stream-time');

        if (frameCountEl) frameCountEl.textContent = this.currentStreamFrame;
        if (progressEl) progressEl.textContent = `${data.progress || 0}%`;
        if (timeEl) timeEl.textContent = `${data.frame_time || 0}s`;
    }

    updateCurrentEmotion(data) {
        const emotionDisplay = document.getElementById('current-emotion-display');
        if (!emotionDisplay) return;

        const emoji = data.emoji || '🎭';
        const emotionZh = data.emotion_zh || '分析中';
        const confidence = Math.round((data.confidence || 0) * 100);

        emotionDisplay.innerHTML = `
            <div class="emotion-icon">${emoji}</div>
            <div class="emotion-info">
                <div class="emotion-name">${emotionZh}</div>
                <div class="emotion-confidence">信心度: ${confidence}%</div>
            </div>
        `;
    }

    updateEmotionTimeline(data) {
        const timelineContainer = document.querySelector('.timeline-container');
        if (!timelineContainer) return;

        const timelineItem = document.createElement('div');
        timelineItem.className = 'timeline-item';

        const emoji = data.emoji || '🎭';
        const emotionZh = data.emotion_zh || '未知';
        const frameTime = data.frame_time || 0;
        const confidence = Math.round((data.confidence || 0) * 100);

        timelineItem.innerHTML = `
            <div class="timeline-time">${frameTime}s</div>
            <div class="timeline-emotion">
                <span class="timeline-emoji">${emoji}</span>
                <span class="timeline-name">${emotionZh}</span>
                <span class="timeline-confidence">${confidence}%</span>
            </div>
        `;

        timelineContainer.appendChild(timelineItem);

        const items = timelineContainer.querySelectorAll('.timeline-item');
        if (items.length > 20) {
            items[0].remove();
        }

        timelineItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // Helper methods
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    getConfidenceClass(confidence) {
        if (confidence >= 0.8) return 'high';
        if (confidence >= 0.6) return 'medium';
        return 'low';
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
                    ${this.selectedFileKind === 'video' ? '<div class="file-duration">解析影片長度中...</div>' : ''}
                </div>
                <div class="media-preview-container">
                    ${this.createMediaPreviewHTML()}
                </div>
                <div class="file-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                    <span class="progress-text">檔案已選擇，準備上傳</span>
                </div>
                <button type="button" class="remove-file-btn" onclick="clearEmotionFileSelection()" aria-label="移除檔案">✕</button>
            </div>
        `;

        this.elements.dropZone.innerHTML = previewHTML;
        this.elements.dropZone.classList.add('has-file');

        // 如果是影片，載入時長
        if (this.selectedFileKind === 'video') {
            const durationEl = this.elements.dropZone.querySelector('.file-duration');
            if (durationEl) {
                this.loadVideoDuration(file, durationEl);
            }
        }

        // 載入媒體預覽
        this.loadMediaPreview(file);
    }

    restoreOriginalDropZone() {
        if (!this.elements.dropZone || !this.originalDropZoneContent) return;

        this.elements.dropZone.innerHTML = this.originalDropZoneContent;
        this.elements.dropZone.classList.remove('has-file');
        this.elements.dropZone.classList.remove('drag-over');
    }

    createMediaPreviewHTML() {
        if (this.selectedFileKind === 'image') {
            return '<div class="image-placeholder">🖼️ 圖片載入中...</div>';
        } else if (this.selectedFileKind === 'video') {
            return '<div class="video-placeholder">🎬 影片載入中...</div>';
        }
        return '';
    }

    loadMediaPreview(file) {
        const container = this.elements.dropZone?.querySelector('.media-preview-container');
        if (!container) return;

        if (this.selectedFileKind === 'image') {
            const img = document.createElement('img');
            img.src = this.previewObjectUrl;
            img.alt = file.name;
            img.className = 'preview-image';
            img.style.cssText = 'max-width: 100%; max-height: 200px; object-fit: contain; border-radius: 8px;';

            img.onload = () => {
                container.innerHTML = '';
                container.appendChild(img);
            };

            img.onerror = () => {
                container.innerHTML = '<div class="preview-error">❌ 圖片預覽載入失敗</div>';
            };
        } else if (this.selectedFileKind === 'video') {
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
    }

    // Public methods
    clearFile() {
        this.clearFileSelection();
    }
}
