/**
 * =============================================================================
 * module-registry.js - Feature module lifecycle coordinator
 * =============================================================================
 *
 * Responsibilities:
 * - Lazy instantiate feature modules via loader functions
 * - Inject shared context (status manager, registry) into modules
 * - Offer utilities for querying active modules and aggregated stats
 * - Provide unified access to all module instances
 */

import { EmotionUploadModule } from '../modules/emotion/upload.js';
import { EmotionRealtimeModule } from '../modules/emotion/realtime.js';
import { ActionUploadController } from '../modules/action/upload/controller.js';
import { ActionGameController } from '../modules/action/game/controller.js';
import { RPSGameController } from '../modules/rps/controller.js';
import GestureDrawingModule from '../modules/drawing/index.js';

/**
 * Canonical loader table for all feature modules. Loaders receive a context
 * object and must synchronously return a module instance.
 */
export const MODULE_LOADERS = {
    emotion: {
        upload: ({ statusManager }) => new EmotionUploadModule(statusManager),
        realtime: ({ statusManager }) => new EmotionRealtimeModule(statusManager)
    },
    action: {
        upload: ({ statusManager }) => new ActionUploadController(statusManager),
        game: ({ statusManager }) => new ActionGameController(statusManager)
    },
    rps: ({ statusManager }) => new RPSGameController(statusManager),
    gesture: {
        drawing: ({ statusManager }) => new GestureDrawingModule(statusManager)
    }
};

export const FLAT_MODULE_LOADERS = {
    'emotion-upload': MODULE_LOADERS.emotion.upload,
    'emotion-realtime': MODULE_LOADERS.emotion.realtime,
    'action-upload': MODULE_LOADERS.action.upload,
    'action-game': MODULE_LOADERS.action.game,
    rps: MODULE_LOADERS.rps,
    'gesture-drawing': MODULE_LOADERS.gesture.drawing
};

const DEFAULT_OPTIONS = {
    enableLogging: false,
    strictMode: true
};

export class ModuleRegistry {
    /**
     * @param {StatusManager|null} statusManager shared status manager
     * @param {object} [options] optional config
     */
    constructor(statusManager = null, options = {}) {
        this.statusManager = statusManager;
        this.options = { ...DEFAULT_OPTIONS, ...options };
        this._entries = new Map();
    }

    /**
     * Register a single module loader.
     * @param {string} name unique identifier (e.g. "emotion-upload")
     * @param {(ctx: object) => any} loader function returning module instance
     */
    register(name, loader) {
        if (this._entries.has(name) && this.options.strictMode) {
            throw new Error(`ModuleRegistry: module "${name}" already registered`);
        }

        this._entries.set(name, {
            loader,
            instance: null,
            initialized: false
        });

        this._log('debug', `Registered module loader: ${name}`);
    }

    /**
     * Register multiple loaders at once using an object map.
     * @param {Record<string, (ctx: object) => any>} loaders
     */
    registerMultiple(loaders) {
        if (!loaders) return;
        Object.entries(loaders).forEach(([name, loader]) => this.register(name, loader));
    }

    /**
     * Lazily obtain a module instance. Instantiates and initializes on demand.
     * @param {string} name module identifier
     * @returns {any|null} module instance or null if not found
     */
    get(name) {
        const entry = this._entries.get(name);
        if (!entry) {
            if (this.options.strictMode) {
                throw new Error(`ModuleRegistry: unknown module "${name}"`);
            }
            this._log('warn', `ModuleRegistry: requested unknown module "${name}"`);
            return null;
        }

        if (!entry.instance) {
            entry.instance = this._createInstance(name, entry.loader);
            entry.initialized = false;
        }

        if (entry.instance && !entry.initialized && typeof entry.instance.initialize === 'function') {
            try {
                const maybePromise = entry.instance.initialize();
                if (maybePromise?.catch) {
                    maybePromise.catch((error) => this._log('error', `Module ${name} initialize failed`, error));
                }
            } catch (error) {
                this._log('error', `Module ${name} initialize threw`, error);
            }
            entry.initialized = true;
        }

        return entry.instance;
    }

    /**
     * Return a map of active modules keyed by name.
     * @returns {Map<string, any>}
     */
    getAllActive() {
        const result = new Map();
        for (const [name, entry] of this._entries.entries()) {
            const instance = entry.instance;
            if (this._isModuleActive(instance)) {
                result.set(name, instance);
            }
        }
        return result;
    }

    /**
     * Return registry statistics for diagnostics.
     */
    getStats() {
        let instantiated = 0;
        let active = 0;
        for (const entry of this._entries.values()) {
            if (entry.instance) {
                instantiated += 1;
                if (this._isModuleActive(entry.instance)) {
                    active += 1;
                }
            }
        }
        return {
            registered: this._entries.size,
            instantiated,
            active
        };
    }

    /**
     * Destroy all modules and reset registry.
     */
    async cleanup() {
        for (const [name, entry] of this._entries.entries()) {
            if (!entry.instance) continue;
            try {
                if (typeof entry.instance.destroy === 'function') {
                    await entry.instance.destroy();
                } else if (typeof entry.instance.deactivate === 'function') {
                    await entry.instance.deactivate();
                } else if (typeof entry.instance.stopGame === 'function') {
                    entry.instance.stopGame();
                }
            } catch (error) {
                this._log('error', `Module ${name} cleanup failed`, error);
            }
            entry.instance = null;
            entry.initialized = false;
        }
    }

    /**
     * Helper to create module instances with context injection.
     * @private
     */
    _createInstance(name, loader) {
        if (typeof loader !== 'function') {
            throw new Error(`ModuleRegistry: loader for "${name}" is not a function`);
        }
        const context = {
            statusManager: this.statusManager,
            registry: this,
            name
        };

        let instance;
        try {
            instance = loader(context);
        } catch (error) {
            this._log('error', `Module ${name} loader threw`, error);
            throw error;
        }

        if (instance?.initialize && typeof instance.initialize !== 'function') {
            this._log('warn', `Module ${name} initialize property is not a function`);
        }

        this._log('info', `Module instantiated: ${name}`);
        return instance;
    }

    /**
     * Determine if a module is "active" based on common properties/methods.
     * @private
     */
    _isModuleActive(instance) {
        if (!instance) return false;
        if (typeof instance.isActive === 'function') {
            return Boolean(instance.isActive());
        }
        if (typeof instance.isDetectionActive === 'function') {
            return Boolean(instance.isDetectionActive());
        }
        if (typeof instance.isActive === 'boolean') {
            return instance.isActive;
        }
        if (typeof instance.isDetectionActive === 'boolean') {
            return instance.isDetectionActive;
        }
        if ('isGameActive' in instance) {
            return Boolean(instance.isGameActive);
        }
        return false;
    }

    _log(level, message, detail) {
        if (!this.options.enableLogging) return;
        const prefix = '[ModuleRegistry]';
        switch (level) {
            case 'error':
                console.error(prefix, message, detail ?? '');
                break;
            case 'warn':
                console.warn(prefix, message, detail ?? '');
                break;
            default:
                console.log(prefix, message, detail ?? '');
        }
    }
}

export default ModuleRegistry;
