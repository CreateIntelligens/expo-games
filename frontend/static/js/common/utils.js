// =============================================================================
// utils.js - 工具函數
// =============================================================================

import { SUPPORTED_IMAGE_TYPES, SUPPORTED_VIDEO_TYPES, SUPPORTED_IMAGE_EXTENSIONS, SUPPORTED_VIDEO_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES } from './constants.js';

/**
 * 格式化檔案大小
 * @param {number} bytes - 位元組數
 * @returns {string} 格式化後的檔案大小
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 獲取檔案副檔名
 * @param {string} filename - 檔案名
 * @returns {string} 副檔名
 */
export function getFileExtension(filename) {
    const lastDot = filename.lastIndexOf('.');
    return lastDot === -1 ? '' : filename.substring(lastDot).toLowerCase();
}

/**
 * 驗證檔案
 * @param {File} file - 檔案物件
 * @returns {Object} 驗證結果
 */
export function validateFile(file) {
    if (!file) {
        return { valid: false, message: '未選擇檔案' };
    }

    if (file.size > MAX_UPLOAD_SIZE_BYTES) {
        const limitMb = Math.round(MAX_UPLOAD_SIZE_BYTES / (1024 * 1024));
        return { valid: false, message: `檔案大小超過限制（${limitMb}MB）` };
    }

    const mimeType = (file.type || '').toLowerCase();
    const extension = getFileExtension(file.name);

    const isImage = SUPPORTED_IMAGE_TYPES.includes(mimeType) || SUPPORTED_IMAGE_EXTENSIONS.includes(extension);
    const isVideo = SUPPORTED_VIDEO_TYPES.includes(mimeType) || SUPPORTED_VIDEO_EXTENSIONS.includes(extension);

    if (!isImage && !isVideo) {
        return { valid: false, message: '不支援的檔案格式，請上傳指定的圖片或影片。' };
    }

    return { valid: true, type: isImage ? 'image' : 'video' };
}

/**
 * 信心度級別分類
 * @param {number} confidence - 信心度 (0-1)
 * @returns {string} 級別類別
 */
export function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return 'high';
    if (confidence >= 0.6) return 'medium';
    return 'low';
}

/**
 * 載入影片長度
 * @param {File} file - 影片檔案
 * @param {Element} targetElement - 目標元素
 */
export function loadVideoDuration(file, targetElement) {
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

/**
 * 防抖函數
 * @param {Function} func - 要防抖的函數
 * @param {number} wait - 等待時間
 * @returns {Function} 防抖後的函數
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 節流函數
 * @param {Function} func - 要節流的函數
 * @param {number} limit - 限制時間
 * @returns {Function} 節流後的函數
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * 生成唯一ID
 * @returns {string} 唯一ID
 */
export function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

/**
 * 深拷貝
 * @param {any} obj - 要拷貝的物件
 * @returns {any} 拷貝後的物件
 */
export function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
}