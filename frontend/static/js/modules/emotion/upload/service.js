/**
 * =============================================================================
 * EmotionUploadService - 情緒上傳分析服務
 * =============================================================================
 *
 * 負責處理檔案上傳和 API 通信的業務邏輯。
 * 提供圖片和影片的情緒分析功能。
 */

export class EmotionUploadService {
    constructor() {
        this.isAnalyzingImage = false;
        this.isAnalyzingVideo = false;
    }

    /**
     * 分析圖片檔案
     * @param {File} file - 圖片檔案
     * @param {Object} callbacks - 回調函數 { onProgress, onSuccess, onError }
     * @returns {XMLHttpRequest} XHR 請求物件
     */
    analyzeImageFile(file, callbacks = {}) {
        if (this.isAnalyzingImage) {
            console.warn('⚠️ 圖片分析已在進行中，跳過重複請求');
            return null;
        }

        this.isAnalyzingImage = true;
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/emotion/analyze/image', true);

        // 上傳進度
        xhr.upload.onprogress = (event) => {
            if (event.lengthComputable && callbacks.onProgress) {
                callbacks.onProgress(event.loaded, event.total);
            }
        };

        // 請求完成
        xhr.onload = () => {
            this.isAnalyzingImage = false;

            try {
                const response = JSON.parse(xhr.responseText);

                if (xhr.status >= 200 && xhr.status < 300) {
                    // HTTP 狀態正常，檢查業務邏輯結果
                    if (response.face_detected === false) {
                        // 人臉檢測失敗，但這是正常的業務邏輯結果
                        const errorMsg = response.error || '未檢測到人臉';
                        console.warn('⚠️ 人臉檢測失敗:', errorMsg);
                        if (callbacks.onError) {
                            callbacks.onError(errorMsg);
                        }
                    } else {
                        // 成功檢測到人臉
                        console.log('✅ 圖片情緒分析成功:', response);
                        if (callbacks.onSuccess) {
                            callbacks.onSuccess(response);
                        }
                    }
                } else {
                    // HTTP 錯誤
                    const errorMsg = response.error || `HTTP ${xhr.status}: ${xhr.statusText}`;
                    console.error('❌ 圖片情緒分析失敗:', errorMsg);
                    if (callbacks.onError) {
                        callbacks.onError(errorMsg);
                    }
                }
            } catch (error) {
                console.error('❌ 解析回應失敗:', error);
                if (callbacks.onError) {
                    callbacks.onError('解析回應失敗');
                }
            }
        };

        // 請求錯誤
        xhr.onerror = () => {
            this.isAnalyzingImage = false;
            console.error('❌ 圖片上傳請求失敗');
            if (callbacks.onError) {
                callbacks.onError('網絡請求失敗');
            }
        };

        xhr.send(formData);
        return xhr;
    }

    /**
     * 分析影片串流
     * @param {File} file - 影片檔案
     * @param {Object} callbacks - 回調函數 { onStreamData, onComplete, onError }
     * @returns {Promise<void>}
     */
    async analyzeVideoStream(file, callbacks = {}) {
        if (this.isAnalyzingVideo) {
            console.warn('⚠️ 影片分析已在進行中，跳過重複請求');
            return;
        }

        this.isAnalyzingVideo = true;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/emotion/analyze/video', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            const readStream = () => {
                reader.read().then(({ done, value }) => {
                    if (done) {
                        console.log('✅ 影片串流分析完成');
                        this.isAnalyzingVideo = false;
                        if (callbacks.onComplete) {
                            callbacks.onComplete();
                        }
                        return;
                    }

                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (let line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.substring(6));
                                if (callbacks.onStreamData) {
                                    callbacks.onStreamData(data);
                                }
                            } catch (error) {
                                console.error('❌ 解析串流數據失敗:', error);
                            }
                        }
                    }

                    readStream();
                }).catch(error => {
                    console.error('❌ 讀取串流失敗:', error);
                    this.isAnalyzingVideo = false;
                    if (callbacks.onError) {
                        callbacks.onError(error.message);
                    }
                });
            };

            readStream();

        } catch (error) {
            console.error('❌ 影片串流分析失敗:', error);
            this.isAnalyzingVideo = false;
            if (callbacks.onError) {
                callbacks.onError(error.message);
            }
        }
    }

    /**
     * 檢查是否正在分析
     * @returns {boolean}
     */
    isAnalyzing() {
        return this.isAnalyzingImage || this.isAnalyzingVideo;
    }

    /**
     * 取消所有進行中的分析
     */
    cancelAll() {
        this.isAnalyzingImage = false;
        this.isAnalyzingVideo = false;
    }
}
