/**
 * =============================================================================
 * GesturePresenter - 手勢繪畫展示器
 * =============================================================================
 *
 * 負責手勢繪畫模組的 DOM 操作和 UI 更新，將業務狀態轉換為視覺展示。
 * 與 Controller 協作，接收狀態對象並更新相應的 UI 元素。
 *
 * 主要功能：
 * - DOM 元素管理和樣式設置
 * - 按鈕狀態更新
 * - 手勢提示顯示
 * - 畫布渲染和覆蓋層管理
 * - 最終結果展示
 * - 事件監聽器綁定
 *
 * 設計原則：
 * - 純 UI 層，不包含業務邏輯
 * - 接受狀態對象，返回 UI 更新結果
 * - 框架無關，可在未來遷移到其他 UI 框架
 * =============================================================================
 */

import { captureFrame, mergeLayersAsync, clearCanvas, getCanvasStats } from '../shared/rendering/canvas-utils.js';

export class GesturePresenter {
    constructor() {
        // DOM 元素引用
        this.elements = {
            // 主要容器
            drawingDisplay: null,
            cameraContainer: null,
            canvasContainer: null,
            resultsContainer: null,

            // 媒體元素
            videoElement: null,
            canvasElement: null,
            overlayCanvas: null,

            // 控制元素
            startButton: null,
            stopButton: null,
            clearButton: null,
            colorButtons: null,
            brushSizeSlider: null,

            // 信息顯示
            gestureHints: null,
            strokeCountElement: null,
            colorDisplayElement: null,
            finalResultElement: null
        };

        // 畫布狀態
        this.canvasCtx = null;
        this.overlayCtx = null;
        this.localBrushSize = 10;
        this.localEraserSize = 26;
        this.lastLocalPoint = null;
        this.hasLocalContent = false;

        // 顏色調色盤（與會話服務保持同步）
        this.colorPalette = {
            black: '#111827',
            red: '#ef4444',
            blue: '#3b82f6',
            green: '#22c55e',
            yellow: '#facc15',
            purple: '#a855f7',
            cyan: '#22d3ee',
            white: '#f9fafb'
        };

        // 初始化 DOM 引用
        this.initializeDOMReferences();
        this.initializeCanvasContexts();
    }

    /**
     * 初始化 DOM 元素引用
     * @private
     */
    initializeDOMReferences() {
        // 主要容器
        this.elements.drawingDisplay = document.getElementById('gesture-drawing-display');
        this.elements.cameraContainer = document.querySelector('.gesture-camera-container');
        this.elements.canvasContainer = document.querySelector('.gesture-canvas-container');
        this.elements.resultsContainer = document.getElementById('gesture-drawing-results');

        // 媒體元素
        this.elements.videoElement = document.getElementById('gesture-video');
        this.elements.canvasElement = document.getElementById('gesture-canvas');
        this.elements.overlayCanvas = document.getElementById('gesture-overlay');
        this.elements.canvasPlaceholder = document.getElementById('gesture-canvas-placeholder');

        // 控制按鈕
        this.elements.startButton = document.getElementById('start-gesture-drawing');
        this.elements.stopButton = document.getElementById('stop-gesture-drawing');
        this.elements.clearButton = document.getElementById('clear-gesture-canvas');

        // 顏色控制
        this.elements.colorButtons = document.querySelectorAll('[data-color]');
        this.elements.brushSizeSlider = document.getElementById('gesture-brush-slider');

        // 信息顯示
        this.elements.gestureHints = document.getElementById('gesture-hints');
        this.elements.strokeCountElement = document.getElementById('gesture-stroke-count');
        this.elements.colorDisplayElement = document.getElementById('gesture-current-color');
        this.elements.finalResultElement = document.getElementById('gesture-final-result');

        console.log('🎨 GesturePresenter DOM 元素已初始化');
    }

    /**
     * 初始化畫布上下文
     * @private
     */
    initializeCanvasContexts() {
        if (this.elements.canvasElement) {
            this.canvasCtx = this.elements.canvasElement.getContext('2d', { alpha: true });
            if (this.canvasCtx) {
                this.canvasCtx.lineJoin = 'round';
                this.canvasCtx.lineCap = 'round';
                this.canvasCtx.imageSmoothingEnabled = true;
            }
        }

        if (this.elements.overlayCanvas) {
            this.overlayCtx = this.elements.overlayCanvas.getContext('2d');
        }
    }

    /**
     * 綁定按鈕事件監聽器
     * @param {Object} handlers - 事件處理函數
     * @param {Function} handlers.onStart - 開始繪畫處理函數
     * @param {Function} handlers.onStop - 停止繪畫處理函數
     * @param {Function} handlers.onClear - 清空畫布處理函數
     * @param {Function} handlers.onColorChange - 顏色變更處理函數
     * @param {Function} handlers.onBrushSizeChange - 筆刷大小變更處理函數
     */
    bindEventHandlers(handlers) {
        const { onStart, onStop, onClear, onColorChange, onBrushSizeChange } = handlers;

        // 綁定主要控制按鈕
        if (this.elements.startButton && onStart) {
            this.elements.startButton.addEventListener('click', onStart);
        }

        if (this.elements.stopButton && onStop) {
            this.elements.stopButton.addEventListener('click', onStop);
        }

        if (this.elements.clearButton && onClear) {
            this.elements.clearButton.addEventListener('click', onClear);
        }

        // 綁定顏色按鈕
        if (this.elements.colorButtons && onColorChange) {
            this.elements.colorButtons.forEach(button => {
                const color = button.getAttribute('data-color');
                if (color) {
                    button.addEventListener('click', () => onColorChange(color));
                }
            });
        }

        // 綁定筆刷大小滑桿
        if (this.elements.brushSizeSlider && onBrushSizeChange) {
            this.elements.brushSizeSlider.addEventListener('input', (e) => {
                const size = parseInt(e.target.value, 10);
                onBrushSizeChange(size);
            });
        }

        console.log('🎨 事件監聽器已綁定');
    }

    /**
     * 顯示繪畫區域
     */
    showDrawingDisplay() {
        if (this.elements.drawingDisplay) {
            this.elements.drawingDisplay.classList.remove('hidden');
            this.elements.drawingDisplay.style.display = 'block';
        }

        // 設置攝影機容器樣式
        if (this.elements.cameraContainer) {
            Object.assign(this.elements.cameraContainer.style, {
                position: 'relative',
                background: 'transparent'
            });
        }

        if (this.elements.canvasPlaceholder) {
            Object.assign(this.elements.canvasPlaceholder.style, {
                opacity: '0',
                pointerEvents: 'none'
            });
        }

        // 確保視頻元素可見（最底層）
        if (this.elements.videoElement) {
            Object.assign(this.elements.videoElement.style, {
                position: 'absolute',
                top: '0',
                left: '0',
                width: '100%',
                height: '100%',
                zIndex: '1',
                transform: 'scaleX(-1)', // 鏡像顯示
                display: 'block',
                visibility: 'visible',
                opacity: '1'
            });
        }

        // 設置覆蓋層（中層，用於手勢指示）
        if (this.elements.overlayCanvas) {
            Object.assign(this.elements.overlayCanvas.style, {
                position: 'absolute',
                top: '0',
                left: '0',
                width: '100%',
                height: '100%',
                zIndex: '2',
                pointerEvents: 'none',
                background: 'transparent',
                display: 'block',
                opacity: '0' // 預設隱藏
            });
        }

        // 設置繪畫畫布（最上層）
        if (this.elements.canvasContainer) {
            Object.assign(this.elements.canvasContainer.style, {
                position: 'absolute',
                top: '0',
                left: '0',
                width: '100%',
                height: '100%',
                zIndex: '3',
                pointerEvents: 'none',
                background: 'transparent'
            });

            // 繪畫畫布本身
            if (this.elements.canvasElement) {
                Object.assign(this.elements.canvasElement.style, {
                    position: 'absolute',
                    top: '0',
                    left: '0',
                    width: '100%',
                    height: '100%',
                    background: 'transparent',
                    display: 'none', // 初始隱藏，有內容時才顯示
                    opacity: '0'
                });
            }
        }

        console.log('🎨 繪畫顯示區域已顯示');
    }

    /**
     * 隱藏繪畫區域
     */
    hideDrawingDisplay() {
        if (this.elements.drawingDisplay) {
            this.elements.drawingDisplay.classList.add('hidden');
        }
        console.log('🎨 繪畫顯示區域已隱藏');
    }

    /**
     * 更新按鈕狀態
     * @param {boolean} isDrawing - 是否正在繪畫
     */
    updateButtonStates(isDrawing) {
        if (this.elements.startButton) {
            this.elements.startButton.disabled = isDrawing;
        }

        if (this.elements.stopButton) {
            this.elements.stopButton.disabled = !isDrawing;
        }

        if (this.elements.clearButton) {
            this.elements.clearButton.disabled = !isDrawing;
        }

        console.log('🎨 按鈕狀態已更新，繪畫中:', isDrawing);
    }

    /**
     * 更新手勢提示
     * @param {string} gesture - 當前手勢
     * @param {Array} fingersUp - 手指狀態
     */
    updateGestureHints(gesture, fingersUp = []) {
        if (!this.elements.gestureHints) return;

        const hints = {
            'drawing': '✏️ 正在繪畫...',
            'erasing': '🧽 正在擦除...',
            'clearing': '🗑️ 清空畫布',
            'idle': '👋 請伸出手指開始繪畫',
            'no_hand': '❌ 未檢測到手部'
        };

        const hintText = hints[gesture] || '準備中...';
        this.elements.gestureHints.textContent = hintText;

        // 添加動畫效果
        this.elements.gestureHints.classList.add('gesture-active');
        setTimeout(() => {
            if (this.elements.gestureHints) {
                this.elements.gestureHints.classList.remove('gesture-active');
            }
        }, 500);

        // 更新覆蓋層顯示手指狀態
        this.updateOverlay(fingersUp);
    }

    /**
     * 更新覆蓋層（顯示手指狀態）
     * @param {Array} fingersUp - 手指狀態 [拇指, 食指, 中指, 無名指, 小指]
     * @private
     */
    updateOverlay(fingersUp) {
        if (!this.overlayCtx || !this.elements.overlayCanvas) return;

        // 清除覆蓋層
        this.overlayCtx.clearRect(0, 0, this.elements.overlayCanvas.width, this.elements.overlayCanvas.height);

        // 如果有手指抬起，顯示覆蓋層
        const hasFingerUp = fingersUp.some(finger => finger);
        if (hasFingerUp) {
            this.elements.overlayCanvas.style.opacity = '1';

            // 繪製手指狀態指示器
            const fingerNames = ['拇指', '食指', '中指', '無名指', '小指'];
            fingersUp.forEach((isUp, index) => {
                if (isUp) {
                    this.overlayCtx.fillStyle = 'rgba(0, 255, 0, 0.7)';
                    this.overlayCtx.fillRect(10, 10 + index * 30, 20, 20);
                    
                    this.overlayCtx.fillStyle = 'white';
                    this.overlayCtx.font = '12px Arial';
                    this.overlayCtx.fillText(fingerNames[index], 35, 25 + index * 30);
                }
            });
        } else {
            this.elements.overlayCanvas.style.opacity = '0';
        }
    }

    /**
     * 更新畫布內容
     * @param {Object} canvasData - 畫布數據
     * @param {string} canvasData.canvasImage - 後端畫布圖像
     * @param {number} canvasData.strokeCount - 筆劃計數
     * @param {string} canvasData.currentColor - 當前顏色
     * @param {Array} canvasData.drawingPosition - 繪畫位置 [x, y]
     */
    updateCanvas(canvasData) {
        const { canvasImage, strokeCount, currentColor, drawingPosition } = canvasData;

        // 更新筆劃計數顯示
        if (this.elements.strokeCountElement && typeof strokeCount === 'number') {
            this.elements.strokeCountElement.textContent = strokeCount;
        }

        // 更新畫布可見性
        const hasContent = (strokeCount > 0) || this.hasLocalContent;
        
        if (this.elements.canvasContainer) {
            this.elements.canvasContainer.classList.toggle('has-content', hasContent);
        }

        if (this.elements.canvasElement) {
            if (hasContent) {
                this.elements.canvasElement.style.display = 'block';
                this.elements.canvasElement.style.opacity = '1';
            } else {
                this.elements.canvasElement.style.opacity = '0';
            }
        }

        console.log('🎨 畫布內容已更新，筆劃數:', strokeCount, '有內容:', hasContent);
    }

    /**
     * 渲染本地筆觸（即時回饋）
     * @param {string} gesture - 當前手勢
     * @param {Array} position - 繪畫位置 [x, y]
     * @param {string} color - 繪畫顏色
     */
    renderLocalStroke(gesture, position, color) {
        if (!this.canvasCtx || !this.elements.canvasElement || !position) {
            return;
        }

        const [x, y] = position;
        const strokeColor = this.resolveColor(color);

        this.canvasCtx.save();

        if (gesture === 'drawing') {
            // 繪畫模式
            this.canvasCtx.globalCompositeOperation = 'source-over';
            this.canvasCtx.strokeStyle = strokeColor;
            this.canvasCtx.fillStyle = strokeColor;
            this.canvasCtx.lineWidth = this.localBrushSize;

            if (this.lastLocalPoint) {
                // 繪製線條
                this.canvasCtx.beginPath();
                this.canvasCtx.moveTo(this.lastLocalPoint[0], this.lastLocalPoint[1]);
                this.canvasCtx.lineTo(x, y);
                this.canvasCtx.stroke();
            } else {
                // 繪製點
                this.canvasCtx.beginPath();
                this.canvasCtx.arc(x, y, this.localBrushSize / 2, 0, Math.PI * 2);
                this.canvasCtx.fill();
            }

            this.lastLocalPoint = [x, y];
            this.hasLocalContent = true;

        } else if (gesture === 'erasing') {
            // 擦除模式
            this.canvasCtx.globalCompositeOperation = 'destination-out';
            this.canvasCtx.beginPath();
            this.canvasCtx.arc(x, y, this.localEraserSize, 0, Math.PI * 2);
            this.canvasCtx.fill();
            this.lastLocalPoint = null;
            this.hasLocalContent = true;

        } else if (gesture === 'clearing') {
            // 清空模式
            this.clearLocalCanvas();

        } else {
            // 其他手勢，重置上一個點
            this.lastLocalPoint = null;
        }

        this.canvasCtx.restore();
    }

    /**
     * 清空本地畫布
     */
    clearLocalCanvas() {
        if (this.canvasCtx && this.elements.canvasElement) {
            clearCanvas(this.elements.canvasElement);
            this.lastLocalPoint = null;
            this.hasLocalContent = false;

            // 隱藏畫布
            this.elements.canvasElement.style.display = 'none';
            this.elements.canvasElement.style.opacity = '0';

            if (this.elements.canvasContainer) {
                this.elements.canvasContainer.classList.remove('has-content');
            }

            console.log('🗑️ 本地畫布已清空');
        }
    }

    /**
     * 更新顏色顯示
     * @param {string} colorName - 顏色名稱
     */
    updateColorDisplay(colorName) {
        if (!this.elements.colorDisplayElement) return;

        const colorNames = {
            'black': '黑色',
            'red': '紅色',
            'green': '綠色',
            'blue': '藍色',
            'yellow': '黃色',
            'purple': '紫色',
            'cyan': '青色',
            'white': '白色'
        };

        const displayName = colorNames[colorName] || colorName;
        this.elements.colorDisplayElement.textContent = displayName;

        // 更新顏色按鈕選中狀態
        this.elements.colorButtons?.forEach(button => {
            const buttonColor = button.getAttribute('data-color');
            button.classList.toggle('active', buttonColor === colorName);
        });

        console.log('🎨 顏色顯示已更新:', displayName);
    }

    /**
     * 高亮顯示顏色區域
     * @param {string} colorName - 顏色名稱
     */
    highlightColorZone(colorName) {
        const colorZones = document.querySelectorAll('.color-zone');
        colorZones.forEach(zone => {
            const zoneColor = zone.getAttribute('data-color');
            zone.classList.toggle('active', zoneColor === colorName);
        });
    }

    /**
     * 調整畫布尺寸
     * @param {Array} size - 畫布尺寸 [width, height]
     */
    adjustCanvasSize(size) {
        const [width, height] = size;

        if (this.elements.canvasElement) {
            this.elements.canvasElement.width = width;
            this.elements.canvasElement.height = height;
        }

        if (this.elements.overlayCanvas) {
            this.elements.overlayCanvas.width = width;
            this.elements.overlayCanvas.height = height;
        }

        console.log('📐 畫布尺寸已調整為:', size);
    }

    /**
     * 顯示最終結果
     * @param {string} imageData - Base64 編碼的圖片數據
     * @param {Function} onSave - 保存按鈕處理函數
     * @param {Function} onNewDrawing - 新繪畫按鈕處理函數
     */
    async showFinalResult(imageData, onSave, onNewDrawing) {
        if (!this.elements.resultsContainer || !imageData) {
            console.warn('⚠️ 無法顯示最終結果：容器或圖片數據不存在');
            return;
        }

        // 顯示結果容器
        this.elements.resultsContainer.classList.remove('hidden');
        this.elements.resultsContainer.style.display = 'block';

        // 清空並準備最終結果元素
        if (this.elements.finalResultElement) {
            this.elements.finalResultElement.innerHTML = '';

            // 創建圖片元素
            const imgElement = document.createElement('img');
            imgElement.src = imageData;
            imgElement.alt = '完成的繪畫作品';
            imgElement.style.cssText = `
                max-width: 100%;
                border-radius: 8px;
                margin-top: 1rem;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
                display: block;
            `;

            // 創建按鈕容器
            const buttonContainer = document.createElement('div');
            buttonContainer.style.cssText = `
                display: flex;
                gap: 0.5rem;
                justify-content: center;
                margin-top: 1rem;
            `;

            // 儲存按鈕
            const saveBtn = document.createElement('button');
            saveBtn.className = 'btn btn-primary';
            saveBtn.textContent = '儲存圖片';
            saveBtn.onclick = () => this.saveImage(imageData);

            // 新繪畫按鈕
            const newDrawingBtn = document.createElement('button');
            newDrawingBtn.className = 'btn btn-secondary';
            newDrawingBtn.textContent = '新繪畫';
            newDrawingBtn.onclick = onNewDrawing;

            // 組裝元素
            buttonContainer.appendChild(saveBtn);
            buttonContainer.appendChild(newDrawingBtn);

            this.elements.finalResultElement.appendChild(imgElement);
            this.elements.finalResultElement.appendChild(buttonContainer);

            console.log('🎨 最終結果已顯示');

            // 滾動到結果區域
            this.elements.resultsContainer.scrollIntoView({ 
                behavior: 'smooth', 
                block: 'end' 
            });
        }
    }

    /**
     * 隱藏最終結果
     */
    hideFinalResult() {
        if (this.elements.resultsContainer) {
            this.elements.resultsContainer.classList.add('hidden');
        }

        if (this.elements.finalResultElement) {
            this.elements.finalResultElement.innerHTML = '';
        }

        console.log('🎨 最終結果已隱藏');
    }

    /**
     * 保存圖片
     * @param {string} imageData - Base64 編碼的圖片數據
     * @private
     */
    saveImage(imageData) {
        try {
            const link = document.createElement('a');
            link.href = imageData;
            link.download = `gesture-drawing-${Date.now()}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            console.log('💾 圖片已保存');
        } catch (error) {
            console.error('❌ 保存圖片失敗:', error);
        }
    }

    /**
     * 解析顏色名稱為十六進制值
     * @param {string} colorName - 顏色名稱
     * @returns {string} 十六進制顏色值
     * @private
     */
    resolveColor(colorName) {
        const key = (colorName || 'black').toLowerCase();
        return this.colorPalette[key] || '#f9fafb';
    }

    /**
     * 左右反轉圖片
     * @param {string} imageBase64 - Base64 編碼的圖片
     * @returns {Promise<string>} 反轉後的 Base64 圖片
     */
    async flipImageHorizontally(imageBase64) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => {
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;
                const ctx = canvas.getContext('2d');

                // 水平翻轉
                ctx.translate(canvas.width, 0);
                ctx.scale(-1, 1);
                ctx.drawImage(img, 0, 0);

                resolve(canvas.toDataURL('image/png'));
            };
            img.onerror = reject;
            img.src = imageBase64;
        });
    }

    /**
     * 捕獲最終合成圖片
     * @returns {Promise<string|null>} Base64 編碼的合成圖片
     */
    async captureFinalComposite() {
        if (!this.elements.videoElement) {
            console.warn('⚠️ 無法捕獲合成圖片：視頻元素不存在');
            return null;
        }

        try {
            const videoSize = [
                this.elements.videoElement.videoWidth || 640,
                this.elements.videoElement.videoHeight || 480
            ];

            // 準備圖層
            const layers = [
                {
                    source: this.elements.videoElement,
                    opacity: 1.0
                }
            ];

            // 添加繪畫圖層（如果有內容）
            if (this.elements.canvasElement && this.hasLocalContent) {
                layers.push({
                    source: this.elements.canvasElement,
                    opacity: 1.0,
                    blendMode: 'source-over'
                });
            }

            // 合併圖層
            const compositeImage = await mergeLayersAsync(layers, videoSize[0], videoSize[1]);

            // 左右反轉圖片以符合使用者視角
            const flippedImage = await this.flipImageHorizontally(compositeImage);
            console.log('📸 最終合成圖片已生成（已反轉）');
            return flippedImage;

        } catch (error) {
            console.error('❌ 捕獲合成圖片失敗:', error);
            return null;
        }
    }

    /**
     * 重置展示器狀態
     */
    reset() {
        this.lastLocalPoint = null;
        this.hasLocalContent = false;
        this.clearLocalCanvas();
        this.hideFinalResult();
        if (this.elements.canvasPlaceholder) {
            Object.assign(this.elements.canvasPlaceholder.style, {
                opacity: '0',
                pointerEvents: 'none'
            });
        }
        console.log('🎨 展示器狀態已重置');
    }

    /**
     * 銷毀展示器，清理資源
     */
    destroy() {
        // 清理畫布上下文
        this.canvasCtx = null;
        this.overlayCtx = null;

        // 清理 DOM 引用
        Object.keys(this.elements).forEach(key => {
            this.elements[key] = null;
        });

        console.log('🗑️ GesturePresenter 資源已清理');
    }
}

export default GesturePresenter;
