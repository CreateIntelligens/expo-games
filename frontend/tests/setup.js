/**
 * Vitest Test Setup
 * Global configuration and mocks for all tests
 */

// Mock DOM globals
global.URL.createObjectURL = () => 'blob:mock-url';
global.URL.revokeObjectURL = () => {};

// Mock WebSocket
global.WebSocket = class MockWebSocket {
    constructor(url) {
        this.url = url;
        this.readyState = 0;
        setTimeout(() => {
            this.readyState = 1;
            if (this.onopen) {
                this.onopen(new Event('open'));
            }
        }, 0);
    }
    send() {}
    close() {
        this.readyState = 3;
    }
};

// Mock navigator.mediaDevices
global.navigator.mediaDevices = {
    getUserMedia: () => Promise.resolve({
        getTracks: () => [],
        getVideoTracks: () => []
    })
};
