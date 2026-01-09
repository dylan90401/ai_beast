/**
 * AI Beast Dashboard - API Client
 *
 * Provides a clean interface for all dashboard API calls.
 */

class API {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
        this.token = localStorage.getItem('beast_token') || '';
    }

    /**
     * Make an API request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} JSON response
     */
    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (this.token) {
            headers['X-Beast-Token'] = this.token;
        }

        try {
            const response = await fetch(`${this.baseUrl}${endpoint}`, {
                ...options,
                headers,
            });

            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Request failed' }));
                throw new Error(error.error || `HTTP ${response.status}`);
            }

            return response.json();
        } catch (error) {
            console.error(`API Error [${endpoint}]:`, error);
            throw error;
        }
    }

    // ==================== Health & Status ====================

    async health() {
        return this.request('/api/health');
    }

    async getMetrics() {
        return this.request('/api/metrics');
    }

    // ==================== Configuration ====================

    async getConfig() {
        return this.request('/api/config');
    }

    async updatePaths(gutsDir, heavyDir) {
        return this.request('/api/paths', {
            method: 'POST',
            body: JSON.stringify({ guts_dir: gutsDir, heavy_dir: heavyDir }),
        });
    }

    // ==================== Models ====================

    async listModels(force = false) {
        return this.request(`/api/models?force=${force ? '1' : '0'}`);
    }

    async listAvailableModels() {
        return this.request('/api/models/available');
    }

    async pullModel(modelName) {
        return this.request('/api/models/pull', {
            method: 'POST',
            body: JSON.stringify({ model: modelName }),
        });
    }

    async deleteModel(path) {
        return this.request('/api/models/delete', {
            method: 'POST',
            body: JSON.stringify({ path }),
        });
    }

    async downloadModel(url, filename, destination, customPath) {
        return this.request('/api/models/download', {
            method: 'POST',
            body: JSON.stringify({
                url,
                filename,
                destination,
                custom_path: customPath,
            }),
        });
    }

    async getModelStorage() {
        return this.request('/api/models/storage');
    }

    async getDownloadStatus(downloadId) {
        return this.request(`/api/models/downloads?id=${downloadId || ''}`);
    }

    // ==================== Services ====================

    async getServices() {
        return this.request('/api/services');
    }

    async startService(name) {
        return this.request('/api/services/start', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async stopService(name) {
        return this.request('/api/services/stop', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    // ==================== Beast Commands ====================

    async runCommand(cmd) {
        return this.request(`/api/run?cmd=${encodeURIComponent(cmd)}`);
    }

    // ==================== Extensions ====================

    async listExtensions() {
        return this.request('/api/extensions');
    }

    async installExtension(name) {
        return this.request('/api/extensions/install', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async toggleExtension(name, enable) {
        return this.request('/api/toggle', {
            method: 'POST',
            body: JSON.stringify({ kind: 'extension', name, enable }),
        });
    }

    // ==================== Packs ====================

    async listPacks() {
        return this.request('/api/packs');
    }

    async togglePack(name, enable) {
        return this.request('/api/toggle', {
            method: 'POST',
            body: JSON.stringify({ kind: 'pack', name, enable }),
        });
    }

    // ==================== Tools ====================

    async listTools() {
        return this.request('/api/tools');
    }

    async installTool(name) {
        return this.request('/api/tools/install', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    async extractTool(name) {
        return this.request('/api/tools/extract', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    }

    // ==================== Capabilities ====================

    async listCapabilities() {
        return this.request('/api/capabilities');
    }

    async runCapabilityChecks() {
        return this.request('/api/capabilities/check', {
            method: 'POST',
        });
    }
}

// Global API instance
const api = new API();
