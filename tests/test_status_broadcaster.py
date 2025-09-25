import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.status_broadcaster import StatusBroadcaster

@pytest.fixture
def broadcaster():
    loop = asyncio.get_event_loop()
    bc = StatusBroadcaster()
    bc.set_loop(loop)
    return bc

class TestStatusBroadcaster:

    def test_initialization(self, broadcaster):
        assert broadcaster._connections == set()
        assert broadcaster._lock is not None

    @pytest.mark.asyncio
    async def test_register_client(self, broadcaster):
        queue = await broadcaster.register()
        assert isinstance(queue, asyncio.Queue)
        assert len(broadcaster._connections) == 1
        assert queue in broadcaster._connections

    @pytest.mark.asyncio
    async def test_unregister_client(self, broadcaster):
        queue = await broadcaster.register()
        assert len(broadcaster._connections) == 1
        await broadcaster.unregister(queue)
        assert len(broadcaster._connections) == 0

    @pytest.mark.asyncio
    async def test_broadcast_message(self, broadcaster):
        queue1 = await broadcaster.register()
        queue2 = await broadcaster.register()

        test_message = {"channel": "test", "data": "hello"}
        await broadcaster.broadcast(test_message)

        # Check if messages are in queues
        assert await queue1.get() == test_message
        assert await queue2.get() == test_message

    @pytest.mark.asyncio
    async def test_broadcast_with_full_queue(self, broadcaster):
        queue1 = await broadcaster.register()
        queue2 = asyncio.Queue(maxsize=1) # Create a small queue
        broadcaster._connections.add(queue2)

        await queue2.put("full") # Fill the queue

        test_message = {"channel": "test", "data": "hello"}
        await broadcaster.broadcast(test_message)

        # The full queue should be removed
        assert queue2 not in broadcaster._connections
        assert len(broadcaster._connections) == 1
        # The other queue should still get the message
        assert await queue1.get() == test_message

    def test_broadcast_threadsafe(self, broadcaster):
        test_message = {"channel": "test", "data": "hello"}
        
        with patch.object(broadcaster, 'broadcast_sync') as mock_broadcast_sync:
            broadcaster.broadcast_threadsafe(test_message)
            mock_broadcast_sync.assert_called_once_with(test_message)