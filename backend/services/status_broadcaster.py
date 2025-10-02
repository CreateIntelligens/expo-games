# =============================================================================
# services/status_broadcaster.py - WebSocket 狀態廣播服務
# 管理 WebSocket 連線和狀態廣播功能
# =============================================================================

import asyncio
from typing import Any, Dict, Optional


class StatusBroadcaster:
    """
    非同步發布-訂閱輔助類別，用於向WebSocket客戶端推送狀態更新。

    此類別管理WebSocket連接的狀態廣播，提供線程安全的非同步消息分發機制。
    支持多個客戶端同時接收狀態更新，並自動清理斷開的連接。

    Attributes:
        _connections (set[asyncio.Queue]): 活躍的WebSocket連接隊列集合
        _lock (asyncio.Lock): 非同步鎖，用於保護連接集合的線程安全
        _loop (Optional[asyncio.AbstractEventLoop]): 事件循環引用
    """

    def __init__(self) -> None:
        """
        初始化StatusBroadcaster實例。

        建立空的連接集合和非同步鎖，為狀態廣播做準備。
        """
        self._connections: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        設定事件循環引用。

        Args:
            loop (asyncio.AbstractEventLoop): 要設定的非同步事件循環
        """
        self._loop = loop

    async def register(self) -> asyncio.Queue:
        """
        註冊新的WebSocket連接並返回消息隊列。

        建立新的非同步隊列並添加到活躍連接集合中，用於接收廣播消息。

        Returns:
            asyncio.Queue: 新建立的消息隊列，最大容量32條消息
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=32)
        async with self._lock:
            self._connections.add(queue)
        return queue

    async def unregister(self, queue: asyncio.Queue) -> None:
        """
        從活躍連接集合中移除指定的消息隊列。

        Args:
            queue (asyncio.Queue): 要移除的消息隊列
        """
        async with self._lock:
            self._connections.discard(queue)

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        向所有活躍的WebSocket連接廣播消息。

        遍歷所有連接隊列，嘗試發送消息。對於已滿或斷開的隊列進行清理。

        Args:
            message (Dict[str, Any]): 要廣播的消息字典
        """
        import logging
        logger = logging.getLogger(__name__)
        async with self._lock:
            dead = []
            conn_count = len(self._connections)
            logger.info(f"📢 廣播訊息到 {conn_count} 個連接: channel={message.get('channel')}, stage={message.get('stage')}")
            for queue in list(self._connections):
                try:
                    queue.put_nowait(message)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._connections.discard(queue)

    def _ensure_loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """
        確保獲取有效的事件循環引用。

        優先使用已設定的循環，如果無效則嘗試獲取當前運行循環。

        Returns:
            Optional[asyncio.AbstractEventLoop]: 有效的事件循環或None
        """
        if self._loop and not self._loop.is_closed():
            return self._loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop:
            self._loop = loop
        return loop

    def broadcast_sync(self, message: Dict[str, Any]) -> None:
        """
        在同步上下文中廣播消息。

        根據呼叫端是否已附著在事件迴圈上，選擇適當的排程策略：
        - 若目前執行緒正運行於目標事件迴圈，直接建立 task。
        - 否則透過 run_coroutine_threadsafe 排程協程。

        Args:
            message (Dict[str, Any]): 要廣播的消息字典
        """
        loop = self._ensure_loop()
        if not loop:
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is loop:
            loop.create_task(self.broadcast(message))
            return

        asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)

    def broadcast_threadsafe(self, message: Dict[str, Any]) -> None:
        """
        線程安全的廣播方法。

        包裝broadcast_sync方法，提供一致的介面。

        Args:
            message (Dict[str, Any]): 要廣播的消息字典
        """
        self.broadcast_sync(message)