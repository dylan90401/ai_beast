/**
 * AI Beast Dashboard - Services Component
 *
 * Handles Docker service listing and management.
 */

const services = {
    currentServices: [],

    /**
     * Load and display services
     */
    async loadServices() {
        try {
            const container = document.getElementById('services-list');
            if (!container) return;

            container.innerHTML = '<div class="empty-state">Loading services...</div>';

            const result = await api.getServices();
            this.currentServices = result.services || [];

            this.renderServices();
            this.updateServiceCount();
        } catch (error) {
            console.error('Failed to load services:', error);
            const container = document.getElementById('services-list');
            if (container) {
                container.innerHTML = `<div class="empty-state text-danger">Failed to load services: ${error.message}</div>`;
            }
        }
    },

    /**
     * Render services list
     */
    renderServices() {
        const container = document.getElementById('services-list');
        if (!container) return;

        if (this.currentServices.length === 0) {
            container.innerHTML = '<div class="empty-state">No services found</div>';
            return;
        }

        container.innerHTML = this.currentServices.map(service => this.renderServiceItem(service)).join('');
    },

    /**
     * Render a single service item
     */
    renderServiceItem(service) {
        const statusClass = this.getStatusClass(service.status);
        const statusBadge = `<span class="badge ${statusClass}">${service.status || 'unknown'}</span>`;

        const isRunning = (service.status || '').toLowerCase().includes('running') ||
                         (service.status || '').toLowerCase().includes('up');

        return `
            <div class="list-item" data-service="${this.escapeHtml(service.name)}">
                <div class="list-item-content">
                    <div class="list-item-title">${this.escapeHtml(service.name)}</div>
                    <div class="list-item-meta">
                        ${statusBadge}
                        ${service.ports ? `<span>Ports: ${this.escapeHtml(service.ports)}</span>` : ''}
                        ${service.image ? `<span class="badge">${this.escapeHtml(service.image)}</span>` : ''}
                    </div>
                    ${service.container_id ? `<div class="list-item-path">${service.container_id}</div>` : ''}
                </div>
                <div class="list-item-actions">
                    ${isRunning
                        ? `<button class="btn btn-sm btn-danger" onclick="services.stopService('${this.escapeHtml(service.name)}')">Stop</button>`
                        : `<button class="btn btn-sm btn-success" onclick="services.startService('${this.escapeHtml(service.name)}')">Start</button>`
                    }
                    <button class="btn btn-sm" onclick="services.viewLogs('${this.escapeHtml(service.name)}')">Logs</button>
                </div>
            </div>
        `;
    },

    /**
     * Get CSS class for status badge
     */
    getStatusClass(status) {
        if (!status) return '';
        const s = status.toLowerCase();
        if (s.includes('running') || s.includes('up') || s.includes('healthy')) {
            return 'badge-success';
        }
        if (s.includes('exited') || s.includes('stopped') || s.includes('down')) {
            return 'badge-danger';
        }
        if (s.includes('starting') || s.includes('restarting')) {
            return 'badge-warning';
        }
        return '';
    },

    /**
     * Update service count in status bar
     */
    updateServiceCount() {
        const statusEl = document.getElementById('services-status');
        if (!statusEl) return;

        const running = this.currentServices.filter(s => {
            const status = (s.status || '').toLowerCase();
            return status.includes('running') || status.includes('up');
        }).length;

        statusEl.textContent = `${running}/${this.currentServices.length}`;
    },

    /**
     * Start a service
     */
    async startService(name) {
        try {
            app.showSuccess(`Starting ${name}...`);
            const result = await api.startService(name);

            if (result.ok) {
                app.showSuccess(`Service ${name} started`);
                await this.loadServices();
            } else {
                app.showError(result.error || 'Failed to start service');
            }
        } catch (error) {
            app.showError(`Failed to start service: ${error.message}`);
        }
    },

    /**
     * Stop a service
     */
    async stopService(name) {
        if (!confirm(`Stop service ${name}?`)) return;

        try {
            app.showSuccess(`Stopping ${name}...`);
            const result = await api.stopService(name);

            if (result.ok) {
                app.showSuccess(`Service ${name} stopped`);
                await this.loadServices();
            } else {
                app.showError(result.error || 'Failed to stop service');
            }
        } catch (error) {
            app.showError(`Failed to stop service: ${error.message}`);
        }
    },

    /**
     * View service logs
     */
    async viewLogs(name) {
        // Switch to logs tab and filter by service
        if (window.app) {
            window.app.switchTab('logs');
            // TODO: Implement service-specific log filtering
            app.showSuccess(`Viewing logs for ${name}...`);
        }
    },

    /**
     * Refresh services list
     */
    async refresh() {
        await this.loadServices();
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
