/**
 * =============================================================================
 * camera-service.js - 攝影機服務模組
 *
 * 負責處理攝影機權限請求、串流管理、解析度設定等功能，
 * 提供統一的攝影機操作 API，供手勢繪畫與情緒分析等模組重用。
 * =============================================================================
 */

import { STREAM_CONFIG } from '/static/js/common/constants.js';

const DEFAULT_VIDEO_CONSTRAINTS = {
    width: { ideal: STREAM_CONFIG.VIDEO_WIDTH },
    height: { ideal: STREAM_CONFIG.VIDEO_HEIGHT },
    facingMode: 'user'
};

/**
 * 攝影機服務類別
 */
export class CameraService extends EventTarget {
    constructor() {
        super();

        this.isCameraActive = false;
        this.localVideoStream = null;
        this.videoElement = null;
        this.captureCanvas = null;
        this.captureContext = null;
        this.videoSize = [STREAM_CONFIG.VIDEO_WIDTH, STREAM_CONFIG.VIDEO_HEIGHT];
        this.constraints = { video: { ...DEFAULT_VIDEO_CONSTRAINTS } };
        this.pendingStart = null;
    }

    /**
     * 註冊事件監聽器，回傳移除函數
     */
    on(event, handler) {
        const wrapped = (evt) => handler(evt?.detail ?? evt);
        this.addEventListener(event, wrapped);
        return () => this.removeEventListener(event, wrapped);
    }

    /**
     * 取消事件監聽
     */
    off(event, handler) {
        this.removeEventListener(event, handler);
    }

    /**
     * 啟動攝影機
     * @param {MediaStreamConstraints} constraints
     */
    async start(constraints = {}) {
        if (this.isCameraActive && this.localVideoStream) {
            return { stream: this.localVideoStream, videoSize: [...this.videoSize] };
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            const error = new Error('瀏覽器不支持攝影機訪問');
            this.dispatchEvent(new CustomEvent('error', { detail: error }));
            throw error;
        }

        if (this.pendingStart) {
            return this.pendingStart;
        }

        const mergedConstraints = this._mergeConstraints(constraints);
        this.constraints = mergedConstraints;

        this.pendingStart = navigator.mediaDevices
            .getUserMedia(mergedConstraints)
            .then((stream) => {
                this.localVideoStream = stream;
                this.isCameraActive = true;
                this._updateVideoSizeFromStream(stream);
                this.createCaptureCanvas(true);

                const detail = {
                    stream,
                    videoSize: [...this.videoSize]
                };

                this.dispatchEvent(new CustomEvent('ready', { detail }));
                this.pendingStart = null;
                return detail;
            })
            .catch((error) => {
                console.error('❌ 攝影機啟動失敗:', error);
                this.pendingStart = null;
                this.dispatchEvent(new CustomEvent('error', { detail: error }));
                throw error;
            });

        return this.pendingStart;
    }

    /**
     * 合併攝影機約束條件
     * @private
     */
    _mergeConstraints(customConstraints = {}) {
        const merged = { ...customConstraints };
        if (customConstraints.video === undefined) {
            merged.video = { ...DEFAULT_VIDEO_CONSTRAINTS };
        } else if (typeof customConstraints.video === 'object') {
            merged.video = {
                ...DEFAULT_VIDEO_CONSTRAINTS,
                ...customConstraints.video
            };
        } else {
            // 允許布林或其他類型傳入，直接覆寫
            merged.video = customConstraints.video;
        }

        return merged;
    }

    /**
     * 根據串流更新實際解析度
     * @private
     */
    _updateVideoSizeFromStream(stream) {
        const track = stream?.getVideoTracks?.()[0];
        const settings = track?.getSettings?.() || {};
        const width = settings.width || this.videoSize[0];
        const height = settings.height || this.videoSize[1];

        if (width && height) {
            this.videoSize = [width, height];
        }
    }

    /**
     * 根據 video 元素更新解析度
     * @private
     */
    _updateVideoSizeFromElement(videoElement) {
        if (!videoElement) return;
        const { videoWidth, videoHeight } = videoElement;
        if (videoWidth && videoHeight) {
            this.videoSize = [videoWidth, videoHeight];
        }
    }

    /**
     * 將串流綁定到既有 video 元素
     */
    async attachToVideoElement(videoElement, { mirror = true, style = {} } = {}) {
        if (!videoElement) {
            throw new Error('缺少 video 元素');
        }

        if (!this.localVideoStream) {
            throw new Error('攝影機尚未啟動');
        }

        this.videoElement = videoElement;
        videoElement.srcObject = this.localVideoStream;
        videoElement.autoplay = true;
        videoElement.muted = true;
        videoElement.playsInline = true;

        const baseStyle = {
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: mirror ? 'scaleX(-1)' : 'none',
            display: 'block'
        };

        Object.assign(videoElement.style, baseStyle, style);

        await this._waitForVideoReady(videoElement);
        this._updateVideoSizeFromElement(videoElement);
        this.createCaptureCanvas(true);

        try {
            await videoElement.play();
        } catch (error) {
            // 某些瀏覽器可能阻止自動播放，可忽略錯誤
            console.warn('⚠️ 視訊自動播放被阻止:', error);
        }

        return videoElement;
    }

    /**
     * 建立並綁定新的 video 元素
     */
    async createVideoElement(container, options = {}) {
        const videoElement = document.createElement('video');

        if (container) {
            container.innerHTML = '';
            container.appendChild(videoElement);
        }

        await this.attachToVideoElement(videoElement, options);
        return videoElement;
    }

    /**
     * 等待影片載入完成
     * @private
     */
    _waitForVideoReady(videoElement) {
        if (!videoElement) {
            return Promise.resolve();
        }

        if (videoElement.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
            return Promise.resolve();
        }

        return new Promise((resolve, reject) => {
            const handleLoaded = () => {
                cleanup();
                resolve();
            };

            const handleError = (event) => {
                cleanup();
                reject(event?.error || new Error('Video 元素載入失敗'));
            };

            const cleanup = () => {
                videoElement.removeEventListener('loadeddata', handleLoaded);
                videoElement.removeEventListener('loadedmetadata', handleLoaded);
                videoElement.removeEventListener('error', handleError);
            };

            videoElement.addEventListener('loadeddata', handleLoaded, { once: true });
            videoElement.addEventListener('loadedmetadata', handleLoaded, { once: true });
            videoElement.addEventListener('error', handleError, { once: true });
        });
    }

    /**
     * 建立或更新捕獲畫布
     */
    createCaptureCanvas(force = false) {
        if (!this.videoSize[0] || !this.videoSize[1]) {
            return;
        }

        if (!this.captureCanvas || force) {
            this.captureCanvas = document.createElement('canvas');
            this.captureContext = this.captureCanvas.getContext('2d');
        }

        if (this.captureCanvas) {
            this.captureCanvas.width = this.videoSize[0];
            this.captureCanvas.height = this.videoSize[1];
        }
    }

    /**
     * 捕獲影像幀
     */
    captureFrame(format = 'jpeg', quality = STREAM_CONFIG.JPEG_QUALITY, options = {}) {
        const { mirror = false } = options;

        if (!this.videoElement) {
            console.warn('⚠️ 無法捕獲幀：尚未綁定 video 元素');
            return null;
        }

        if (!this.captureCanvas || !this.captureContext) {
            this.createCaptureCanvas(true);
        }

        if (!this.captureContext) {
            return null;
        }

        const [width, height] = this.videoSize;

        try {
            this.captureContext.save();
            this.captureContext.setTransform(1, 0, 0, 1, 0, 0);
            this.captureContext.clearRect(0, 0, width, height);

            if (mirror) {
                this.captureContext.translate(width, 0);
                this.captureContext.scale(-1, 1);
            }

            this.captureContext.drawImage(
                this.videoElement,
                0,
                0,
                width,
                height
            );

            this.captureContext.restore();

            const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
            const imageData = this.captureCanvas.toDataURL(mimeType, quality);

            if (!imageData || imageData === 'data:,' || imageData.length < 50) {
                return null;
            }

            return imageData;
        } catch (error) {
            console.error('❌ 影像擷取錯誤:', error);
            return null;
        }
    }

    /**
     * 停止攝影機
     */
    stop() {
        if (!this.isCameraActive) {
            return;
        }

        if (this.localVideoStream) {
            this.localVideoStream.getTracks().forEach((track) => track.stop());
        }

        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }

        this.localVideoStream = null;
        this.isCameraActive = false;
        this.videoElement = null;
        this.captureCanvas = null;
        this.captureContext = null;

        this.dispatchEvent(new CustomEvent('stopped'));
    }

    /**
     * 回傳攝影機串流
     */
    getStream() {
        return this.localVideoStream;
    }

    /**
     * 取得影像尺寸
     */
    getVideoSize() {
        return [...this.videoSize];
    }

    /**
     * 取得 video 元素
     */
    getVideoElement() {
        return this.videoElement;
    }

    /**
     * 檢查攝影機是否啟動
     */
    isActive() {
        return this.isCameraActive;
    }

    /**
     * 向後相容別名
     */
    isRunning() {
        return this.isActive();
    }

    /**
     * 取得當前狀態快照
     */
    getStatus() {
        return {
            active: this.isCameraActive,
            videoSize: [...this.videoSize],
            hasStream: !!this.localVideoStream
        };
    }

    /**
     * 清理資源
     */
    destroy() {
        this.stop();
        this.pendingStart = null;
        this.constraints = { video: { ...DEFAULT_VIDEO_CONSTRAINTS } };
    }

    /**
     * 將錯誤轉換為用戶可讀訊息
     */
    getErrorMessage(error) {
        let errorMessage = '攝影機啟動失敗：';

        if (!error) {
            return `${errorMessage}未知錯誤`;
        }

        if (error.name === 'NotAllowedError') {
            errorMessage += '用戶拒絕了攝影機權限';
        } else if (error.name === 'NotFoundError') {
            errorMessage += '未找到攝影機設備';
        } else if (error.name === 'NotReadableError') {
            errorMessage += '攝影機被其他應用程式佔用';
        } else {
            errorMessage += error.message || '未知錯誤';
        }

        return errorMessage;
    }
}

export default CameraService;
