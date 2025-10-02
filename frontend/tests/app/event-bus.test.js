/**
 * EventBus Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { EventBus, EVENT_TYPES } from '../../static/js/app/event-bus.js';

describe('EventBus', () => {
    let eventBus;

    beforeEach(() => {
        eventBus = new EventBus({ enableLogging: false });
    });

    it('應該正確初始化', () => {
        expect(eventBus).toBeInstanceOf(EventBus);
        expect(eventBus.listenerCount.size).toBe(0);
    });

    it('應該支援事件訂閱和發送', () => {
        const handler = vi.fn();
        eventBus.on('test-event', handler);

        eventBus.emit('test-event', { data: 'test' });

        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('應該支援多個監聽器', () => {
        const handler1 = vi.fn();
        const handler2 = vi.fn();

        eventBus.on('test-event', handler1);
        eventBus.on('test-event', handler2);

        eventBus.emit('test-event', { data: 'test' });

        expect(handler1).toHaveBeenCalledTimes(1);
        expect(handler2).toHaveBeenCalledTimes(1);
    });

    it('應該支援取消訂閱', () => {
        const handler = vi.fn();
        eventBus.on('test-event', handler);
        eventBus.off('test-event', handler);

        eventBus.emit('test-event', { data: 'test' });

        expect(handler).not.toHaveBeenCalled();
    });

    it('應該支援一次性訂閱', () => {
        const handler = vi.fn();
        eventBus.once('test-event', handler);

        eventBus.emit('test-event', { data: 'test1' });
        eventBus.emit('test-event', { data: 'test2' });

        expect(handler).toHaveBeenCalledTimes(1);
    });

    it('應該支援 waitFor', async () => {
        setTimeout(() => {
            eventBus.emit('async-event', { result: 'success' });
        }, 100);

        const result = await eventBus.waitFor('async-event', 1000);
        expect(result.result).toBe('success');
    });

    it('waitFor 應該在超時後拋出錯誤', async () => {
        await expect(
            eventBus.waitFor('never-emitted', 100)
        ).rejects.toThrow('等待事件 "never-emitted" 超時');
    });

    it('應該提供統計資訊', () => {
        eventBus.on('event1', () => {});
        eventBus.on('event1', () => {});
        eventBus.on('event2', () => {});

        const stats = eventBus.getStats();
        expect(stats.totalEvents).toBe(2);
        expect(stats.events['event1'].listenerCount).toBe(2);
        expect(stats.events['event2'].listenerCount).toBe(1);
    });
});
