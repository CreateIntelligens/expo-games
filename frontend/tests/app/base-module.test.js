/**
 * BaseModule Tests
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { BaseModule } from '../../static/js/app/base-module.js';
import { STATUS_TYPES } from '../../static/js/common/constants.js';

describe('BaseModule', () => {
    let module;
    let mockStatusManager;

    beforeEach(() => {
        mockStatusManager = {
            update: vi.fn()
        };

        module = new BaseModule({
            name: 'test-module',
            statusManager: mockStatusManager
        });
    });

    it('應該正確初始化', () => {
        expect(module.name).toBe('test-module');
        expect(module.statusManager).toBe(mockStatusManager);
        expect(module._initialized).toBe(false);
        expect(module._active).toBe(false);
    });

    it('應該支援初始化（冪等）', async () => {
        await module.initialize();
        expect(module._initialized).toBe(true);

        // 再次初始化不應該報錯
        await module.initialize();
        expect(module._initialized).toBe(true);
    });

    it('應該支援啟動', async () => {
        await module.activate();
        expect(module._initialized).toBe(true);
        expect(module._active).toBe(true);
    });

    it('應該支援停用', async () => {
        await module.activate();
        await module.deactivate();
        expect(module._active).toBe(false);
        expect(module._initialized).toBe(true); // 仍然是初始化狀態
    });

    it('應該支援銷毀', async () => {
        await module.activate();
        await module.destroy();
        expect(module._active).toBe(false);
        expect(module._initialized).toBe(false);
    });

    it('應該呼叫 updateStatus', () => {
        module.updateStatus('測試訊息', STATUS_TYPES.SUCCESS);
        expect(mockStatusManager.update).toHaveBeenCalledWith('測試訊息', STATUS_TYPES.SUCCESS);
    });
});
