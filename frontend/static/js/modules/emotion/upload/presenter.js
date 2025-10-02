/**
 * =============================================================================
 * EmotionUploadPresenter - 情緒上傳 UI 展示器
 * =============================================================================
 *
 * 負責所有 DOM 操作和 UI 更新。
 * 管理檔案預覽、進度顯示、結果渲染等視覺元素。
 */

import { EMOTION_EMOJIS } from '../../../common/constants.js';
import { ButtonToggler, ProgressBar, DropZoneHandler } from '../../../common/ui-helpers.js';

export class EmotionUploadPresenter {
    constructor() {
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

        // 狀態
        this.previewObjectUrl = null;
        this.originalDropZoneContent = null;
    }

    /**
     * 綁定事件處理函數
     * @param {Object} handlers - 事件處理函數 { onFileSelect, onFormSubmit }
     */
    bindEvents(handlers) {
        // 設置拖放處理器
        if (this.elements.dropZone && this.elements.fileInput) {
            new DropZoneHandler(
                this.elements.dropZone,
                this.elements.fileInput,
                (file) => handlers.onFileSelect?.(file)
            );
        }

        // 檔案輸入監聽器
        this.elements.fileInput?.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file && handlers.onFileSelect) {
                handlers.onFileSelect(file);
            }
        });

        // 表單提交監聽器
        this.elements.form?.addEventListener('submit', (event) => {
            event.preventDefault();
            if (handlers.onFormSubmit) {
                handlers.onFormSubmit();
            }
        });
    }

    /**
     * 渲染檔案預覽
     * @param {File} file - 檔案物件
     * @param {string} fileKind - 檔案類型 ('image' 或 'video')
     */
    renderFilePreview(file, fileKind) {
        // 清除舊的預覽
        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
        }

        this.previewObjectUrl = URL.createObjectURL(file);
        this.replaceDropZoneWithPreview(file, fileKind);
        this.loadMediaPreview(file, fileKind);
    }

    /**
     * 替換拖放區為預覽區
     * @param {File} file - 檔案物件
     * @param {string} fileKind - 檔案類型
     */
    replaceDropZoneWithPreview(file, fileKind) {
        const dropZone = this.elements.dropZone;
        if (!dropZone) return;

        if (!this.originalDropZoneContent) {
            this.originalDropZoneContent = dropZone.innerHTML;
        }

        dropZone.innerHTML = `
            <div class="file-info">
                <div class="file-icon">${fileKind === 'video' ? '🎥' : '📸'}</div>
                <div class="file-details">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${this.formatFileSize(file.size)}</div>
                    ${fileKind === 'video' ? '<div class="file-duration" id="video-duration">載入中...</div>' : ''}
                </div>
            </div>
            ${this.createMediaPreviewHTML(fileKind)}
            <button type="button" class="clear-file-btn" id="clear-file-btn">
                ✕ 清除檔案
            </button>
        `;

        if (fileKind === 'video') {
            const durationEl = document.getElementById('video-duration');
            if (durationEl) {
                this.loadVideoDuration(file, durationEl);
            }
        }
    }

    /**
     * 創建媒體預覽 HTML
     * @param {string} fileKind - 檔案類型
     * @returns {string} HTML 字串
     */
    createMediaPreviewHTML(fileKind) {
        if (fileKind === 'image') {
            return `
                <div class="media-preview">
                    <img id="preview-image" alt="預覽圖片" style="display:none;">
                </div>
            `;
        } else {
            return `
                <div class="media-preview">
                    <video id="preview-video" controls style="display:none;"></video>
                </div>
            `;
        }
    }

    /**
     * 載入媒體預覽
     * @param {File} file - 檔案物件
     * @param {string} fileKind - 檔案類型
     */
    loadMediaPreview(file, fileKind) {
        if (!this.previewObjectUrl) return;

        if (fileKind === 'image') {
            const img = document.getElementById('preview-image');
            if (!img) return;

            img.src = this.previewObjectUrl;
            img.onload = () => {
                img.style.display = 'block';
                console.log('✅ 圖片預覽已載入');
            };
            img.onerror = () => {
                console.error('❌ 圖片預覽載入失敗');
            };
        } else {
            const video = document.getElementById('preview-video');
            if (!video) return;

            video.src = this.previewObjectUrl;
            video.onloadedmetadata = () => {
                video.style.display = 'block';
                console.log('✅ 影片預覽已載入');
            };
            video.onerror = () => {
                console.error('❌ 影片預覽載入失敗');
            };
        }
    }

    /**
     * 載入影片時長
     * @param {File} file - 影片檔案
     * @param {HTMLElement} targetElement - 目標元素
     */
    loadVideoDuration(file, targetElement) {
        const url = URL.createObjectURL(file);
        const video = document.createElement('video');

        video.preload = 'metadata';
        video.onloadedmetadata = () => {
            const duration = Math.floor(video.duration);
            const minutes = Math.floor(duration / 60);
            const seconds = duration % 60;
            targetElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            URL.revokeObjectURL(url);
        };

        video.onerror = () => {
            targetElement.textContent = '無法載入';
            URL.revokeObjectURL(url);
        };

        video.src = url;
    }

    /**
     * 恢復原始拖放區
     */
    restoreOriginalDropZone() {
        if (this.elements.dropZone && this.originalDropZoneContent) {
            this.elements.dropZone.innerHTML = this.originalDropZoneContent;
        }
    }

    /**
     * 清除檔案選擇
     */
    clearFileSelection() {
        this.restoreOriginalDropZone();

        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
            this.previewObjectUrl = null;
        }

        if (this.elements.analyzeBtn) {
            this.elements.analyzeBtn.disabled = true;
        }

        if (this.elements.fileInput) {
            this.elements.fileInput.value = '';
        }

        this.elements.uploadResults.innerHTML = '';
        this.elements.uploadResults.style.display = 'none';
    }

    /**
     * 啟用分析按鈕
     */
    enableAnalyzeButton() {
        setTimeout(() => {
            if (this.elements.analyzeBtn) {
                this.elements.analyzeBtn.disabled = false;
            }
        }, 100);
    }

    /**
     * 更新上傳進度
     * @param {number} loaded - 已上傳大小
     * @param {number} total - 總大小
     */
    updateUploadProgress(loaded, total) {
        const percentage = Math.round((loaded / total) * 100);
        this.progressBar.update(percentage);

        const progressFillEl = this.elements.uploadProgress?.querySelector('.progress-fill');
        const progressTextEl = this.elements.uploadProgress?.querySelector('.progress-text');

        if (progressFillEl && progressTextEl) {
            progressFillEl.style.width = `${percentage}%`;
            progressTextEl.textContent = `上傳中: ${percentage}%`;
        }
    }

    /**
     * 渲染分析結果
     * @param {Object} response - API 回應
     */
    renderAnalysisResults(response) {
        this.elements.uploadResults.innerHTML = `
            ${this.buildSummaryCard(response)}
            ${this.buildDistributionCard(response)}
        `;
        this.elements.uploadResults.style.display = 'block';
    }

    /**
     * 建立摘要卡片
     * @param {Object} results - 分析結果
     * @returns {string} HTML 字串
     */
    buildSummaryCard(results) {
        // 支援兩種格式：新格式 (emotion_zh/emotion_en) 和舊格式 (dominant_emotion)
        const emotionZh = results.emotion_zh || results.dominant_emotion || '未知';
        const emotionEn = results.emotion_en || results.dominant_emotion || 'unknown';
        const confidence = results.confidence || 0;
        const emoji = results.emoji || EMOTION_EMOJIS[emotionEn] || '😐';

        return `
            <div class="result-card summary-card">
                <h3>分析摘要</h3>
                <div class="dominant-emotion">
                    <div class="emotion-icon">${emoji}</div>
                    <div class="emotion-details">
                        <div class="emotion-name">${emotionZh}</div>
                        <div class="emotion-confidence ${this.getConfidenceClass(confidence)}">
                            信心度: ${(confidence * 100).toFixed(1)}%
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 建立分布卡片
     * @param {Object} results - 分析結果
     * @returns {string} HTML 字串
     */
    buildDistributionCard(results) {
        // 支援兩種格式：新格式 (raw_scores) 和舊格式 (emotions)
        const emotions = results.raw_scores || results.emotions || {};

        // 如果沒有分布資料，不顯示此卡片
        if (Object.keys(emotions).length === 0) {
            return '';
        }

        let emotionRows = '';

        Object.entries(emotions)
            .sort(([, a], [, b]) => b - a)
            .forEach(([emotion, score]) => {
                const emoji = EMOTION_EMOJIS[emotion] || '😐';
                const percentage = (score * 100).toFixed(1);
                emotionRows += `
                    <div class="emotion-row">
                        <div class="emotion-label">
                            <span class="emotion-emoji">${emoji}</span>
                            <span class="emotion-text">${emotion}</span>
                        </div>
                        <div class="emotion-bar">
                            <div class="emotion-bar-fill" style="width: ${percentage}%"></div>
                        </div>
                        <div class="emotion-score">${percentage}%</div>
                    </div>
                `;
            });

        return `
            <div class="result-card distribution-card">
                <h3>情緒分布</h3>
                <div class="emotion-distribution">
                    ${emotionRows}
                </div>
            </div>
        `;
    }

    /**
     * 初始化串流結果區
     */
    initStreamResults() {
        if (this.elements.uploadContent) {
            this.elements.uploadContent.innerHTML = `
                <div class="stream-container">
                    <div class="stream-header">
                        <h3>🎬 影片串流分析進行中...</h3>
                        <div class="stream-stats">
                            <span id="stream-progress">處理中: 0%</span>
                            <span id="stream-time">時間: 0s</span>
                        </div>
                    </div>

                    <div class="current-emotion-display">
                        <div class="emotion-large-icon" id="current-emotion-icon">😐</div>
                        <div class="emotion-large-name" id="current-emotion-name">等待中...</div>
                        <div class="emotion-large-confidence" id="current-emotion-confidence">-</div>
                    </div>

                    <div class="emotion-timeline-container">
                        <h4>情緒時間軸</h4>
                        <div class="emotion-timeline" id="emotion-timeline"></div>
                    </div>
                </div>
            `;
        }

        // 顯示結果區域
        if (this.elements.uploadResults) {
            this.elements.uploadResults.style.display = 'block';
            this.elements.uploadResults.classList.remove('hidden');
        }
    }

    /**
     * 更新串流統計資訊
     * @param {Object} data - 串流數據
     */
    updateStreamStats(data) {
        const progressEl = document.getElementById('stream-progress');
        const timeEl = document.getElementById('stream-time');

        if (progressEl) progressEl.textContent = `處理中: ${data.progress || 0}%`;
        if (timeEl) timeEl.textContent = `時間: ${data.frame_time || 0}s`;
    }

    /**
     * 更新當前情緒顯示
     * @param {Object} data - 串流數據
     */
    updateCurrentEmotion(data) {
        const iconEl = document.getElementById('current-emotion-icon');
        const nameEl = document.getElementById('current-emotion-name');
        const confidenceEl = document.getElementById('current-emotion-confidence');

        // 支援兩種格式：新格式 (emotion_zh/emotion_en) 和舊格式 (dominant_emotion)
        const emotionZh = data.emotion_zh || data.dominant_emotion || '未知';
        const emotionEn = data.emotion_en || data.dominant_emotion || 'unknown';
        const confidence = data.confidence || 0;
        const emoji = data.emoji || EMOTION_EMOJIS[emotionEn] || '😐';

        if (iconEl) iconEl.textContent = emoji;
        if (nameEl) nameEl.textContent = emotionZh;
        if (confidenceEl) {
            confidenceEl.textContent = `信心度: ${(confidence * 100).toFixed(1)}%`;
            confidenceEl.className = `emotion-large-confidence ${this.getConfidenceClass(confidence)}`;
        }
    }

    /**
     * 更新情緒時間軸
     * @param {Object} data - 串流數據
     */
    updateEmotionTimeline(data) {
        const timeline = document.getElementById('emotion-timeline');
        if (!timeline) return;

        // 支援兩種格式：新格式 (emotion_zh/emotion_en) 和舊格式 (dominant_emotion)
        const emotionZh = data.emotion_zh || data.dominant_emotion || '未知';
        const emotionEn = data.emotion_en || data.dominant_emotion || 'unknown';
        const confidence = data.confidence || 0;
        const frameTime = data.frame_time || 0;
        const emoji = data.emoji || EMOTION_EMOJIS[emotionEn] || '😐';

        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `
            <div class="timeline-time">${frameTime.toFixed(1)}s</div>
            <div class="timeline-emotion">
                <span class="timeline-emoji">${emoji}</span>
                <span class="timeline-name">${emotionZh}</span>
            </div>
            <div class="timeline-confidence ${this.getConfidenceClass(confidence)}">
                ${(confidence * 100).toFixed(0)}%
            </div>
        `;

        timeline.appendChild(item);

        const items = timeline.querySelectorAll('.timeline-item');
        if (items.length > 20) {
            items[0].remove();
        }
    }

    /**
     * 格式化檔案大小
     * @param {number} bytes - 檔案大小（bytes）
     * @returns {string} 格式化後的大小
     */
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }

    /**
     * 獲取信心度樣式類別
     * @param {number} confidence - 信心度 (0-1)
     * @returns {string} CSS 類別名稱
     */
    getConfidenceClass(confidence) {
        if (confidence >= 0.7) return 'high-confidence';
        if (confidence >= 0.4) return 'medium-confidence';
        return 'low-confidence';
    }

    /**
     * 清理資源
     */
    destroy() {
        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
            this.previewObjectUrl = null;
        }
    }
}
