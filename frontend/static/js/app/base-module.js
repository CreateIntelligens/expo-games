/**
 * =============================================================================
 * base-module.js - Shared lifecycle base class for feature modules
 * =============================================================================
 */

import { STATUS_TYPES } from '../common/constants.js';

/**
 * Provides a consistent lifecycle contract:
 * - initialize(): one-time setup (idempotent)
 * - activate(options): enter active state
 * - deactivate(): leave active state
 * - destroy(): teardown resources
 *
 * Subclasses override the protected hooks (e.g. _onInitialize) instead of
 * overriding the public lifecycle methods directly.
 */
export class BaseModule {
    constructor({ name = 'module', statusManager = null } = {}) {
        this.name = name;
        this.statusManager = statusManager;
        this._initialized = false;
        this._active = false;
    }

    /**
     * Public initialize entrypoint (idempotent).
     */
    async initialize() {
        if (this._initialized) {
            return;
        }
        await this._onInitialize();
        this._initialized = true;
    }

    /**
     * Public activate entrypoint.
     * @param {object} options optional activation payload
     */
    async activate(options = {}) {
        await this.initialize();
        if (this._active) {
            return;
        }
        await this._onActivate(options);
        this._active = true;
    }

    /**
     * Public deactivate entrypoint.
     */
    async deactivate() {
        if (!this._active) {
            return;
        }
        await this._onDeactivate();
        this._active = false;
    }

    /**
     * Public destroy entrypoint (idempotent).
     */
    async destroy() {
        await this.deactivate();
        if (!this._initialized) {
            return;
        }
        await this._onDestroy();
        this._initialized = false;
    }

    /**
     * @returns {boolean} whether the module is currently initialized
     */
    isInitialized() {
        return this._initialized;
    }

    /**
     * @returns {boolean} whether the module is currently active
     */
    isActive() {
        return this._active;
    }

    /**
     * Hook for subclasses to perform one-time initialization.
     * @protected
     */
    async _onInitialize() {}

    /**
     * Hook for subclasses to run when activated.
     * @protected
     */
    async _onActivate() {}

    /**
     * Hook for subclasses to run when deactivated.
     * @protected
     */
    async _onDeactivate() {}

    /**
     * Hook for subclasses to tear down resources.
     * @protected
     */
    async _onDestroy() {}

    /**
     * Helper to update global status messages in a consistent way.
     * @protected
     */
    updateStatus(message, type = STATUS_TYPES.INFO) {
        if (this.statusManager && typeof this.statusManager.update === 'function') {
            this.statusManager.update(message, type);
        }
    }
}

export default BaseModule;
