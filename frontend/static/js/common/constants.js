// =============================================================================
// constants.js - 應用程式常數定義
// =============================================================================

// 檔案類型支援
export const SUPPORTED_IMAGE_TYPES = [
    'image/jpeg', 'image/jpg', 'image/png', 'image/webp',
    'image/gif', 'image/bmp', 'image/tiff', 'image/svg+xml'
];

export const SUPPORTED_VIDEO_TYPES = [
    'video/mp4', 'video/webm', 'video/ogg', 'video/avi',
    'video/mov', 'video/wmv', 'video/flv', 'video/mkv'
];

export const SUPPORTED_IMAGE_EXTENSIONS = [
    '.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.svg'
];

export const SUPPORTED_VIDEO_EXTENSIONS = [
    '.mp4', '.webm', '.ogv', '.avi', '.mov', '.wmv', '.flv', '.mkv'
];

// 上傳限制
export const MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024; // 100MB

// 情緒表情符號映射
export const EMOTION_EMOJIS = {
    '開心': '😊',
    '悲傷': '😢',
    '生氣': '😠',
    '驚訝': '😲',
    '恐懼': '😨',
    '厭惡': '🤢',
    '中性': '😐',
    'happy': '😊',
    'sad': '😢',
    'angry': '😠',
    'surprise': '😲',
    'fear': '😨',
    'disgust': '🤢',
    'neutral': '😐'
};

// 狀態類型
export const STATUS_TYPES = {
    INFO: 'info',
    SUCCESS: 'success',
    WARNING: 'warning',
    ERROR: 'error',
    PROCESSING: 'processing'
};

// WebSocket配置
export const WEBSOCKET_CONFIG = {
    RECONNECT_INTERVAL: 3000,
    MAX_RECONNECT_ATTEMPTS: 5
};

// 分析模式
export const ANALYSIS_MODES = {
    EMOTION: 'emotion',
    ACTION: 'action'
};

// 串流配置
export const STREAM_CONFIG = {
    ANALYSIS_INTERVAL: 500, // 0.5秒
    VIDEO_WIDTH: 640,
    VIDEO_HEIGHT: 480,
    JPEG_QUALITY: 0.8
};