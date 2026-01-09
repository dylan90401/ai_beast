/**
 * AI Beast Dashboard - WebSocket Client
 *
 * Provides real-time updates from the dashboard backend.
 */

class WebSocketClient {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.listeners = new Map();
        this.isConnecting = false;
        this.manualClose = false;
    }

    /**
     * Connect to WebSocket server
     */
    connect() {
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
            return;
        }

        this.isConnecting = true;
        this.manualClose = false;

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('[WebSocket] Connected');
                this.isConnecting = false;
                this.reconnectDelay = 1000;
                this.reconnectAttempts = 0;
                this.emit('connected');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleMessage(data);
                } catch (error) {
                    console.error('[WebSocket] Failed to parse message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
                this.isConnecting = false;
                this.emit('error', error);
            };

            this.ws.onclose = (event) => {
                console.log('[WebSocket] Disconnected', event.code, event.reason);
                this.isConnecting = false;
                this.emit('disconnected');

                if (!this.manualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.scheduleReconnect();
                }
            };
        } catch (error) {
            console.error('[WebSocket] Failed to connect:', error);
            this.isConnecting = false;
            this.scheduleReconnect();
        }
    }

    /**
     * Schedule a reconnection attempt
     */
    scheduleReconnect() {
        this.reconnectAttempts++;
        console.log(`[WebSocket] Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, this.reconnectDelay);

        // Exponential backoff
        this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
    }

    /**
     * Handle incoming WebSocket message
     */
    handleMessage(data) {
        // Emit event for specific message types
        if (data.type) {
            this.emit(data.type, data);
        }

        // Handle common update messages
        switch (data.type) {
            case 'update':
                this.handleUpdate(data.data);
                break;
            case 'metrics':
                this.handleMetrics(data.data);
                break;
            case 'log':
                this.handleLog(data.data);
                break;
            case 'notification':
                this.handleNotification(data.data);
                break;
            default:
                console.log('[WebSocket] Unknown message type:', data.type);
        }
    }

    /**
     * Handle periodic update messages
     */
    handleUpdate(data) {
        if (!data) return;

        // Update metrics
        if (data.metrics && window.app) {
            window.app.updateMetrics(data.metrics);
        }

        // Update model status
        if (data.models) {
            const ollamaStatus = document.getElementById('ollama-status');
            if (ollamaStatus && data.models.ollama_running !== undefined) {
                ollamaStatus.textContent = data.models.ollama_running ? '✓ Running' : '✗ Stopped';
                ollamaStatus.className = `status-value ${data.models.ollama_running ? 'ok' : 'error'}`;
            }
        }

        // Update services
        if (data.services && typeof services !== 'undefined') {
            services.currentServices = data.services;
            services.renderServices();
            services.updateServiceCount();
        }
    }

    /**
     * Handle metrics update
     */
    handleMetrics(data) {
        if (window.app) {
            window.app.updateMetrics(data);
        }
    }

    /**
     * Handle log message
     */
    handleLog(data) {
        const output = document.getElementById('logs-output');
        if (output && data.message) {
            const timestamp = data.timestamp ? `[${data.timestamp}] ` : '';
            const level = data.level ? `[${data.level.toUpperCase()}] ` : '';
            output.textContent += `${timestamp}${level}${data.message}\n`;
            output.scrollTop = output.scrollHeight;
        }
    }

    /**
     * Handle notification message
     */
    handleNotification(data) {
        if (window.app && data.message) {
            const type = data.type || 'info';
            if (type === 'error') {
                window.app.showError(data.message);
            } else {
                window.app.showSuccess(data.message);
            }
        }
    }

    /**
     * Send a message to the server
     */
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        console.warn('[WebSocket] Cannot send: not connected');
        return false;
    }

    /**
     * Subscribe to a message type
     */
    on(event, callback) {
        if (!this.listeners.has(event)) {
            this.listeners.set(event, []);
        }
        this.listeners.get(event).push(callback);
    }

    /**
     * Unsubscribe from a message type
     */
    off(event, callback) {
        if (this.listeners.has(event)) {
            const callbacks = this.listeners.get(event);
            const index = callbacks.indexOf(callback);
            if (index > -1) {
                callbacks.splice(index, 1);
            }
        }
    }

    /**
     * Emit an event to listeners
     */
    emit(event, data) {
        if (this.listeners.has(event)) {
            this.listeners.get(event).forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`[WebSocket] Listener error for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Close the WebSocket connection
     */
    close() {
        this.manualClose = true;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * Check if connected
     */
    get isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Initialize WebSocket client when DOM is ready
let ws = null;

document.addEventListener('DOMContentLoaded', () => {
    // Construct WebSocket URL based on current location
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/updates`;

    ws = new WebSocketClient(wsUrl);

    // Add connection status indicator
    ws.on('connected', () => {
        updateConnectionStatus(true);
    });

    ws.on('disconnected', () => {
        updateConnectionStatus(false);
    });

    // Connect after a short delay
    setTimeout(() => {
        ws.connect();
    }, 1000);
});

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    let indicator = document.getElementById('ws-status');

    if (!indicator) {
        // Create status indicator if it doesn't exist
        indicator = document.createElement('div');
        indicator.id = 'ws-status';
        indicator.style.cssText = `
            position: fixed;
            bottom: 10px;
            left: 10px;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 500;
            z-index: 9999;
            transition: all 0.3s ease;
        `;
        document.body.appendChild(indicator);
    }

    if (connected) {
        indicator.textContent = '● Live';
        indicator.style.background = 'var(--success)';
        indicator.style.color = 'var(--bg-primary)';
    } else {
        indicator.textContent = '○ Offline';
        indicator.style.background = 'var(--surface)';
        indicator.style.color = 'var(--text-secondary)';
    }
}
