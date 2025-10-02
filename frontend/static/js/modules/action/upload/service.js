// =============================================================================
// Action Upload Service - 動作影片上傳服務
// 負責檔案驗證、上傳、API 通訊
// =============================================================================

import { SUPPORTED_VIDEO_TYPES, SUPPORTED_VIDEO_EXTENSIONS } from '../../../common/constants.js';

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB

export class ActionUploadService {
    constructor() {
        this.selectedFile = null;
        this.previewObjectUrl = null;
    }

    validateFile(file) {
        // 檢查檔案類型
        const fileExt = this.getFileExtension(file.name);
        const isValidType = SUPPORTED_VIDEO_TYPES.includes(file.type.toLowerCase()) ||
                           SUPPORTED_VIDEO_EXTENSIONS.includes(fileExt);

        if (!isValidType) {
            return {
                valid: false,
                message: '請選擇影片檔案（MP4、AVI、MOV等格式）'
            };
        }

        // 檢查檔案大小
        if (file.size > MAX_FILE_SIZE) {
            return {
                valid: false,
                message: '影片檔案大小超過限制（100MB）'
            };
        }

        return { valid: true };
    }

    setFile(file) {
        // 清理舊的預覽 URL
        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
        }

        this.selectedFile = file;
        this.previewObjectUrl = URL.createObjectURL(file);
    }

    clearFile() {
        this.selectedFile = null;

        if (this.previewObjectUrl) {
            URL.revokeObjectURL(this.previewObjectUrl);
            this.previewObjectUrl = null;
        }
    }

    getFile() {
        return this.selectedFile;
    }

    uploadAndAnalyze(file, onProgress, onComplete, onError) {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/action/analyze');

        xhr.upload.onprogress = (event) => {
            const total = event.total || file.size || 1;
            onProgress(event.loaded, total);
        };

        xhr.onload = () => {
            try {
                const response = JSON.parse(xhr.responseText);
                if (xhr.status >= 200 && xhr.status < 300) {
                    onComplete(response);
                } else if (response.error) {
                    onError(response.error);
                } else {
                    onError('動作分析失敗');
                }
            } catch (error) {
                onError('無法解析伺服器回應');
            }
        };

        xhr.onerror = () => {
            onError('上傳過程中發生錯誤，請稍後再試。');
        };

        xhr.send(formData);
    }

    // Helper methods
    getFileExtension(filename) {
        const lastDot = filename.lastIndexOf('.');
        return lastDot === -1 ? '' : filename.substring(lastDot).toLowerCase();
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    loadVideoDuration(file, callback) {
        const video = document.createElement('video');
        const objectUrl = URL.createObjectURL(file);

        video.src = objectUrl;
        video.onloadedmetadata = () => {
            const minutes = Math.floor(video.duration / 60);
            const seconds = Math.floor(video.duration % 60);
            const duration = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            callback(duration);
            URL.revokeObjectURL(objectUrl);
        };

        video.onerror = () => {
            callback('無法解析長度');
            URL.revokeObjectURL(objectUrl);
        };
    }
}
