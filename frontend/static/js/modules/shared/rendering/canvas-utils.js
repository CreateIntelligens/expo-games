/**
 * =============================================================================
 * CanvasUtils - 共享畫布工具類
 * =============================================================================
 *
 * 提供畫布操作的通用工具函數，包含幀捕獲、圖層合併、離屏畫布管理等。
 * 用於手勢繪畫、情感分析等需要畫布操作的模組。
 *
 * 主要功能：
 * - 視頻幀捕獲
 * - 圖層合併
 * - 離屏畫布管理
 * - 圖片格式轉換
 * - 畫布清理工具
 * =============================================================================
 */

/**
 * 從視頻元素捕獲幀
 * @param {HTMLVideoElement} video - 視頻元素
 * @param {number} width - 輸出寬度
 * @param {number} height - 輸出高度
 * @param {string} format - 圖片格式 ('jpeg' | 'png')
 * @param {number} quality - 圖片品質 (0-1)
 * @returns {string|null} Base64 編碼的圖片數據
 */
export function captureFrame(video, width, height, format = 'jpeg', quality = 0.8) {
    if (!video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        console.warn('⚠️ 無法捕獲幀：視頻未就緒');
        return null;
    }

    try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');

        canvas.width = width;
        canvas.height = height;

        // 繪製視頻幀
        ctx.drawImage(video, 0, 0, width, height);

        // 轉換為指定格式
        const mimeType = format === 'png' ? 'image/png' : 'image/jpeg';
        return canvas.toDataURL(mimeType, quality);

    } catch (error) {
        console.error('❌ 捕獲幀失敗:', error);
        return null;
    }
}

/**
 * 創建離屏畫布
 * @param {number} width - 畫布寬度
 * @param {number} height - 畫布高度
 * @returns {Object} { canvas, ctx } 畫布和上下文
 */
export function createOffscreenCanvas(width, height) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    canvas.width = width;
    canvas.height = height;

    return { canvas, ctx };
}

/**
 * 合併多個畫布圖層
 * @param {Array} layers - 圖層數組 [{ source, opacity?, blendMode? }]
 * @param {number} width - 輸出寬度
 * @param {number} height - 輸出高度
 * @returns {string} 合併後的 base64 圖片數據
 */
export function mergeLayers(layers, width, height) {
    if (!layers || layers.length === 0) {
        console.warn('⚠️ 沒有圖層可合併');
        return null;
    }

    try {
        const { canvas, ctx } = createOffscreenCanvas(width, height);

        // 設置白色背景
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, width, height);

        // 合併每個圖層
        layers.forEach(layer => {
            if (!layer.source) return;

            ctx.save();

            // 設置透明度
            if (layer.opacity !== undefined) {
                ctx.globalAlpha = layer.opacity;
            }

            // 設置混合模式
            if (layer.blendMode) {
                ctx.globalCompositeOperation = layer.blendMode;
            }

            // 繪製圖層
            if (typeof layer.source === 'string') {
                // Base64 圖片
                const img = new Image();
                img.src = layer.source;
                ctx.drawImage(img, 0, 0, width, height);
            } else if (layer.source instanceof HTMLCanvasElement) {
                // Canvas 元素
                ctx.drawImage(layer.source, 0, 0, width, height);
            } else if (layer.source instanceof HTMLVideoElement) {
                // Video 元素
                ctx.drawImage(layer.source, 0, 0, width, height);
            }

            ctx.restore();
        });

        return canvas.toDataURL('image/png');

    } catch (error) {
        console.error('❌ 合併圖層失敗:', error);
        return null;
    }
}

/**
 * 異步合併圖層（處理需要載入的圖片）
 * @param {Array} layers - 圖層數組
 * @param {number} width - 輸出寬度
 * @param {number} height - 輸出高度
 * @returns {Promise<string>} 合併後的 base64 圖片數據
 */
export async function mergeLayersAsync(layers, width, height) {
    if (!layers || layers.length === 0) {
        throw new Error('沒有圖層可合併');
    }

    const { canvas, ctx } = createOffscreenCanvas(width, height);

    // 設置白色背景
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, width, height);

    // 處理每個圖層
    for (const layer of layers) {
        if (!layer.source) continue;

        ctx.save();

        // 設置透明度
        if (layer.opacity !== undefined) {
            ctx.globalAlpha = layer.opacity;
        }

        // 設置混合模式
        if (layer.blendMode) {
            ctx.globalCompositeOperation = layer.blendMode;
        }

        // 繪製圖層
        if (typeof layer.source === 'string') {
            // 異步載入 Base64 圖片
            const img = await loadImage(layer.source);
            ctx.drawImage(img, 0, 0, width, height);
        } else if (layer.source instanceof HTMLCanvasElement) {
            // Canvas 元素
            ctx.drawImage(layer.source, 0, 0, width, height);
        } else if (layer.source instanceof HTMLVideoElement) {
            // Video 元素
            ctx.drawImage(layer.source, 0, 0, width, height);
        }

        ctx.restore();
    }

    return canvas.toDataURL('image/png');
}

/**
 * 載入圖片
 * @param {string} src - 圖片來源 (URL 或 base64)
 * @returns {Promise<HTMLImageElement>}
 */
export function loadImage(src) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        
        img.onload = () => resolve(img);
        img.onerror = (error) => reject(error);
        
        img.src = src;
    });
}

/**
 * 調整畫布大小並保持內容
 * @param {HTMLCanvasElement} sourceCanvas - 原始畫布
 * @param {number} newWidth - 新寬度
 * @param {number} newHeight - 新高度
 * @returns {HTMLCanvasElement} 調整大小後的畫布
 */
export function resizeCanvas(sourceCanvas, newWidth, newHeight) {
    const { canvas, ctx } = createOffscreenCanvas(newWidth, newHeight);
    
    // 繪製原始畫布內容，自動縮放
    ctx.drawImage(sourceCanvas, 0, 0, newWidth, newHeight);
    
    return canvas;
}

/**
 * 清空畫布
 * @param {HTMLCanvasElement} canvas - 畫布元素
 * @param {string} fillColor - 填充顏色 (可選)
 */
export function clearCanvas(canvas, fillColor = null) {
    const ctx = canvas.getContext('2d');
    
    if (fillColor) {
        ctx.fillStyle = fillColor;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
    } else {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

/**
 * 創建圓角矩形路徑
 * @param {CanvasRenderingContext2D} ctx - 畫布上下文
 * @param {number} x - X 坐標
 * @param {number} y - Y 坐標
 * @param {number} width - 寬度
 * @param {number} height - 高度
 * @param {number} radius - 圓角半徑
 */
export function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
}

/**
 * 繪製帶陰影的文字
 * @param {CanvasRenderingContext2D} ctx - 畫布上下文
 * @param {string} text - 文字內容
 * @param {number} x - X 坐標
 * @param {number} y - Y 坐標
 * @param {Object} options - 選項 { color, shadowColor, shadowBlur, shadowOffset }
 */
export function drawTextWithShadow(ctx, text, x, y, options = {}) {
    const {
        color = '#000000',
        shadowColor = 'rgba(0, 0, 0, 0.5)',
        shadowBlur = 2,
        shadowOffset = { x: 1, y: 1 }
    } = options;

    ctx.save();

    // 繪製陰影
    ctx.fillStyle = shadowColor;
    ctx.filter = `blur(${shadowBlur}px)`;
    ctx.fillText(text, x + shadowOffset.x, y + shadowOffset.y);

    // 繪製主文字
    ctx.filter = 'none';
    ctx.fillStyle = color;
    ctx.fillText(text, x, y);

    ctx.restore();
}

/**
 * 獲取畫布像素數據統計
 * @param {HTMLCanvasElement} canvas - 畫布元素
 * @param {Object} region - 區域 { x, y, width, height } (可選，默認整個畫布)
 * @returns {Object} 像素統計 { totalPixels, transparentPixels, hasContent }
 */
export function getCanvasStats(canvas, region = null) {
    const ctx = canvas.getContext('2d');
    
    const { x, y, width, height } = region || {
        x: 0,
        y: 0,
        width: canvas.width,
        height: canvas.height
    };

    const imageData = ctx.getImageData(x, y, width, height);
    const data = imageData.data;
    
    let totalPixels = data.length / 4;
    let transparentPixels = 0;
    let coloredPixels = 0;

    // 檢查每個像素
    for (let i = 0; i < data.length; i += 4) {
        const alpha = data[i + 3];
        
        if (alpha === 0) {
            transparentPixels++;
        } else if (alpha > 0) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            
            // 檢查是否為有顏色的像素（非純黑或純白）
            if ((r > 10 || g > 10 || b > 10) && (r < 245 || g < 245 || b < 245)) {
                coloredPixels++;
            }
        }
    }

    return {
        totalPixels,
        transparentPixels,
        coloredPixels,
        hasContent: coloredPixels > 0 || (totalPixels - transparentPixels) > totalPixels * 0.1
    };
}

/**
 * 將畫布內容複製到另一個畫布
 * @param {HTMLCanvasElement} sourceCanvas - 源畫布
 * @param {HTMLCanvasElement} targetCanvas - 目標畫布
 * @param {Object} options - 選項 { x, y, width, height, targetX, targetY }
 */
export function copyCanvas(sourceCanvas, targetCanvas, options = {}) {
    const {
        x = 0,
        y = 0,
        width = sourceCanvas.width,
        height = sourceCanvas.height,
        targetX = 0,
        targetY = 0
    } = options;

    const targetCtx = targetCanvas.getContext('2d');
    targetCtx.drawImage(sourceCanvas, x, y, width, height, targetX, targetY, width, height);
}

/**
 * 創建漸變
 * @param {CanvasRenderingContext2D} ctx - 畫布上下文
 * @param {string} type - 漸變類型 ('linear' | 'radial')
 * @param {Array} coordinates - 座標 [x0, y0, x1, y1] 或 [x0, y0, r0, x1, y1, r1]
 * @param {Array} colorStops - 色彩停止點 [{ offset, color }]
 * @returns {CanvasGradient}
 */
export function createGradient(ctx, type, coordinates, colorStops) {
    let gradient;

    if (type === 'linear') {
        const [x0, y0, x1, y1] = coordinates;
        gradient = ctx.createLinearGradient(x0, y0, x1, y1);
    } else if (type === 'radial') {
        const [x0, y0, r0, x1, y1, r1] = coordinates;
        gradient = ctx.createRadialGradient(x0, y0, r0, x1, y1, r1);
    } else {
        throw new Error(`不支援的漸變類型: ${type}`);
    }

    // 添加色彩停止點
    colorStops.forEach(stop => {
        gradient.addColorStop(stop.offset, stop.color);
    });

    return gradient;
}

export default {
    captureFrame,
    createOffscreenCanvas,
    mergeLayers,
    mergeLayersAsync,
    loadImage,
    resizeCanvas,
    clearCanvas,
    roundRect,
    drawTextWithShadow,
    getCanvasStats,
    copyCanvas,
    createGradient
};
