# =============================================================================
# utils/datetime_utils.py - 日期時間工具函數
# 提供時間戳記和日期處理功能
# =============================================================================

from datetime import datetime


def _now_ts() -> str:
    """
    生成檔案名稱用的時間戳記。

    Returns:
        str: 格式為 YYYYMMDD_HHMMSS 的時間戳記字串

    Example:
        >>> ts = _now_ts()
        >>> print(ts)
        20250919_163655
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")