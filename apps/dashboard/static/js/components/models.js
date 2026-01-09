/**
 * AI Beast Dashboard - Models Component
 *
 * Handles model listing, downloading, and management.
 */

const models = {
    currentModels: [],
    currentView: 'local',
    downloadInProgress: false,

    /**
     * Load and display models
     */
    async loadModels(force = false) {
        try {
            const container = document.getElementById('models-list');
            if (!container) return;

            container.innerHTML = '<div class="empty-state">Loading models...</div>';

            const { models: modelList, ollama_running } = await api.listModels(force);
            this.currentModels = modelList || [];

            // Update Ollama status indicator
            const ollamaStatus = document.getElementById('ollama-status');
            if (ollamaStatus) {
                ollamaStatus.textContent = ollama_running ? '✓ Running' : '✗ Stopped';
                ollamaStatus.className = `status-value ${ollama_running ? 'ok' : 'error'}`;
            }

            this.renderModels();
        } catch (error) {
            console.error('Failed to load models:', error);
            const container = document.getElementById('models-list');
            if (container) {
                container.innerHTML = `<div class="empty-state text-danger">Failed to load models: ${error.message}</div>`;
            }
        }
    },

    /**
     * Render the models list based on current view
     */
    renderModels() {
        const container = document.getElementById('models-list');
        if (!container) return;

        const filtered = this.currentModels.filter(m => {
            if (this.currentView === 'local') {
                return m.location !== 'ollama';
            } else if (this.currentView === 'ollama') {
                return m.location === 'ollama';
            }
            return true;
        });

        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">No models found</div>';
            return;
        }

        container.innerHTML = filtered.map(model => this.renderModelItem(model)).join('');
    },

    /**
     * Render a single model item
     */
    renderModelItem(model) {
        const locationBadge = this.getLocationBadge(model.location);
        const quantBadge = model.quantization
            ? `<span class="badge badge-quant">${model.quantization}</span>`
            : '';

        return `
            <div class="list-item" data-path="${this.escapeHtml(model.path)}">
                <div class="list-item-content">
                    <div class="list-item-title">${this.escapeHtml(model.name)}</div>
                    <div class="list-item-meta">
                        ${locationBadge}
                        <span>${model.size_human || 'Unknown size'}</span>
                        ${quantBadge}
                        <span class="badge">${model.model_type || 'unknown'}</span>
                    </div>
                    <div class="list-item-path">${this.escapeHtml(model.path)}</div>
                </div>
                <div class="list-item-actions">
                    ${model.location === 'ollama'
                        ? `<button class="btn btn-sm btn-danger" onclick="models.deleteOllamaModel('${this.escapeHtml(model.name)}')">Delete</button>`
                        : `<button class="btn btn-sm btn-danger" onclick="models.deleteLocalModel('${this.escapeHtml(model.path)}')">Delete</button>`
                    }
                </div>
            </div>
        `;
    },

    /**
     * Get badge HTML for model location
     */
    getLocationBadge(location) {
        const badges = {
            internal: '<span class="badge badge-success">Internal</span>',
            external: '<span class="badge badge-warning">External</span>',
            ollama: '<span class="badge">Ollama</span>',
            custom: '<span class="badge">Custom</span>',
        };
        return badges[location] || `<span class="badge">${location}</span>`;
    },

    /**
     * Switch model view (local/ollama/all)
     */
    switchView(view) {
        this.currentView = view;

        // Update tab states
        document.querySelectorAll('.tabs-secondary .tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.subtab === view);
        });

        this.renderModels();
    },

    /**
     * Refresh models list
     */
    async refresh() {
        await this.loadModels(true);
    },

    /**
     * Show download dialog
     */
    showDownloadDialog() {
        const modal = document.getElementById('download-modal');
        if (modal) {
            modal.classList.add('active');
            document.getElementById('download-url')?.focus();
        }
    },

    /**
     * Hide download dialog
     */
    hideDownloadDialog() {
        const modal = document.getElementById('download-modal');
        if (modal) {
            modal.classList.remove('active');
            document.getElementById('download-form')?.reset();
            document.getElementById('download-progress')?.classList.add('hidden');
        }
    },

    /**
     * Start model download
     */
    async startDownload(event) {
        event.preventDefault();

        if (this.downloadInProgress) {
            app.showError('Download already in progress');
            return;
        }

        const url = document.getElementById('download-url')?.value;
        const filename = document.getElementById('download-filename')?.value || null;
        const destination = document.getElementById('download-location')?.value || 'internal';

        if (!url) {
            app.showError('URL is required');
            return;
        }

        try {
            this.downloadInProgress = true;
            document.getElementById('download-progress')?.classList.remove('hidden');

            const result = await api.downloadModel(url, filename, destination, null);

            if (result.ok) {
                app.showSuccess('Download started');
                this.pollDownloadProgress(result.download_id);
            } else {
                app.showError(result.error || 'Download failed');
                this.downloadInProgress = false;
            }
        } catch (error) {
            app.showError(`Download failed: ${error.message}`);
            this.downloadInProgress = false;
        }
    },

    /**
     * Poll download progress
     */
    async pollDownloadProgress(downloadId) {
        const progressFill = document.getElementById('download-progress-fill');
        const progressText = document.getElementById('download-progress-text');

        const poll = async () => {
            try {
                const status = await api.getDownloadStatus(downloadId);

                if (status.completed) {
                    if (progressFill) progressFill.style.width = '100%';
                    if (progressText) progressText.textContent = 'Complete!';

                    setTimeout(() => {
                        this.hideDownloadDialog();
                        this.downloadInProgress = false;
                        this.loadModels(true);
                    }, 1000);
                    return;
                }

                if (status.error) {
                    app.showError(status.error);
                    this.downloadInProgress = false;
                    return;
                }

                const percent = status.percent || 0;
                if (progressFill) progressFill.style.width = `${percent}%`;
                if (progressText) progressText.textContent = `${percent.toFixed(1)}%`;

                setTimeout(poll, 1000);
            } catch (error) {
                console.error('Poll error:', error);
                setTimeout(poll, 2000);
            }
        };

        poll();
    },

    /**
     * Pull an Ollama model
     */
    async pullOllamaModel(modelName) {
        if (!modelName) {
            modelName = prompt('Enter model name (e.g., llama3.2:3b):');
            if (!modelName) return;
        }

        try {
            app.showSuccess(`Pulling ${modelName}...`);
            const result = await api.pullModel(modelName);

            if (result.ok) {
                app.showSuccess(`Model ${modelName} pulled successfully`);
                await this.loadModels(true);
            } else {
                app.showError(result.error || 'Pull failed');
            }
        } catch (error) {
            app.showError(`Failed to pull model: ${error.message}`);
        }
    },

    /**
     * Delete a local model
     */
    async deleteLocalModel(path) {
        if (!confirm(`Delete model at ${path}?`)) return;

        try {
            const result = await api.deleteModel(path);
            if (result.ok) {
                app.showSuccess('Model deleted');
                await this.loadModels(true);
            } else {
                app.showError(result.error || 'Delete failed');
            }
        } catch (error) {
            app.showError(`Failed to delete: ${error.message}`);
        }
    },

    /**
     * Delete an Ollama model
     */
    async deleteOllamaModel(name) {
        if (!confirm(`Delete Ollama model ${name}?`)) return;

        try {
            const result = await api.deleteModel(`ollama:${name}`);
            if (result.ok) {
                app.showSuccess('Model deleted');
                await this.loadModels(true);
            } else {
                app.showError(result.error || 'Delete failed');
            }
        } catch (error) {
            app.showError(`Failed to delete: ${error.message}`);
        }
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
};

// Setup subtab event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.tabs-secondary .tab').forEach(tab => {
        tab.addEventListener('click', () => {
            models.switchView(tab.dataset.subtab);
        });
    });

    // Download form submission
    document.getElementById('download-form')?.addEventListener('submit', (e) => {
        models.startDownload(e);
    });

    // Modal close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => {
            models.hideDownloadDialog();
        });
    });

    // Close modal on backdrop click
    document.getElementById('download-modal')?.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            models.hideDownloadDialog();
        }
    });
});
