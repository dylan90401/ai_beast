/**
 * AI Beast Dashboard - Main Application
 *
 * Handles tab navigation, theme switching, and overall app state.
 */

class App {
    constructor() {
        this.currentTab = 'overview';
        this.autoRefreshInterval = null;
        this.autoRefreshDelay = 10000; // 10 seconds
        this.notifications = [];
    }

    /**
     * Initialize the application
     */
    async init() {
        this.setupTabs();
        this.setupTheme();
        this.setupEventListeners();
        await this.loadInitialData();
        this.startAutoRefresh();
    }

    /**
     * Setup tab navigation
     */
    setupTabs() {
        document.querySelectorAll('.tab[data-tab]').forEach(tab => {
            tab.addEventListener('click', () => {
                this.switchTab(tab.dataset.tab);
            });
        });
    }

    /**
     * Switch to a specific tab
     */
    switchTab(tabName) {
        // Hide all tab panels
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
        });

        // Deactivate all tabs
        document.querySelectorAll('.tab[data-tab]').forEach(tab => {
            tab.classList.remove('active');
        });

        // Show selected panel
        const panel = document.getElementById(`${tabName}-tab`);
        if (panel) {
            panel.classList.add('active');
        }

        // Activate selected tab
        const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
        if (tab) {
            tab.classList.add('active');
        }

        this.currentTab = tabName;
        this.loadTabData(tabName);
    }

    /**
     * Load data for a specific tab
     */
    async loadTabData(tabName) {
        switch (tabName) {
            case 'overview':
                await this.loadOverview();
                break;
            case 'models':
                if (typeof models !== 'undefined') {
                    await models.loadModels();
                }
                break;
            case 'services':
                if (typeof services !== 'undefined') {
                    await services.loadServices();
                }
                break;
            case 'config':
                await this.loadConfig();
                break;
            case 'logs':
                await this.loadLogs();
                break;
        }
    }

    /**
     * Load initial data on app start
     */
    async loadInitialData() {
        try {
            await this.loadOverview();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    /**
     * Load overview tab data
     */
    async loadOverview() {
        try {
            // Load metrics
            const { metrics } = await api.getMetrics();
            this.updateMetrics(metrics);

            // Load model/service status
            const modelData = await api.listModels();
            const ollamaStatus = document.getElementById('ollama-status');
            if (ollamaStatus) {
                ollamaStatus.textContent = modelData.ollama_running ? '✓ Running' : '✗ Stopped';
                ollamaStatus.className = `status-value ${modelData.ollama_running ? 'ok' : 'error'}`;
            }

            // Update services count
            if (typeof services !== 'undefined') {
                await services.loadServices();
            }
        } catch (error) {
            console.error('Failed to load overview:', error);
        }
    }

    /**
     * Update metrics display
     */
    updateMetrics(metrics) {
        if (!metrics) return;

        // Memory
        const memory = metrics.memory || {};
        const memPercent = memory.percent_used || 0;
        const memBar = document.getElementById('memory-bar');
        const memText = document.getElementById('memory-text');
        if (memBar) memBar.style.width = `${memPercent}%`;
        if (memText) memText.textContent = `${memory.used_gb || 0} GB / ${memory.total_gb || 0} GB`;

        // Disk
        const disk = metrics.disk_usage || {};
        const diskPercent = disk.percent_used || 0;
        const diskBar = document.getElementById('disk-bar');
        const diskText = document.getElementById('disk-text');
        if (diskBar) diskBar.style.width = `${diskPercent}%`;
        if (diskText) diskText.textContent = `${disk.used_gb || 0} GB / ${disk.total_gb || 0} GB`;
    }

    /**
     * Load configuration tab
     */
    async loadConfig() {
        try {
            const { config } = await api.getConfig();
            const gutsInput = document.getElementById('guts-dir');
            const heavyInput = document.getElementById('heavy-dir');

            if (gutsInput) gutsInput.value = config?.GUTS_DIR || '';
            if (heavyInput) heavyInput.value = config?.HEAVY_DIR || '';
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    }

    /**
     * Load logs tab
     */
    async loadLogs() {
        const output = document.getElementById('logs-output');
        if (output) {
            output.textContent = 'Logs feature coming soon...\n\nUse WebSocket connection for real-time logs.';
        }
    }

    /**
     * Setup theme toggle
     */
    setupTheme() {
        const savedTheme = localStorage.getItem('beast_theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);

        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.addEventListener('click', () => {
                const current = document.documentElement.getAttribute('data-theme');
                const newTheme = current === 'dark' ? 'light' : 'dark';
                document.documentElement.setAttribute('data-theme', newTheme);
                localStorage.setItem('beast_theme', newTheme);
                this.updateThemeIcon(newTheme);
            });
        }
    }

    /**
     * Update theme toggle icon
     */
    updateThemeIcon(theme) {
        const toggle = document.getElementById('theme-toggle');
        if (toggle) {
            toggle.textContent = theme === 'dark' ? '🌙' : '☀️';
        }
    }

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-all');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadTabData(this.currentTab);
            });
        }

        // Config form
        const configForm = document.getElementById('config-form');
        if (configForm) {
            configForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const gutsDir = document.getElementById('guts-dir')?.value;
                const heavyDir = document.getElementById('heavy-dir')?.value;

                try {
                    await api.updatePaths(gutsDir, heavyDir);
                    this.showSuccess('Configuration updated');
                } catch (error) {
                    this.showError(`Failed to update configuration: ${error.message}`);
                }
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + R to refresh
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                this.loadTabData(this.currentTab);
            }
        });
    }

    /**
     * Start auto-refresh for overview
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            if (this.currentTab === 'overview') {
                this.loadOverview();
            }
        }, this.autoRefreshDelay);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    /**
     * Show success notification
     */
    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    /**
     * Show error notification
     */
    showError(message) {
        this.showNotification(message, 'error');
    }

    /**
     * Show notification toast
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            background: ${type === 'error' ? 'var(--danger)' : type === 'success' ? 'var(--success)' : 'var(--primary)'};
            color: var(--bg-primary);
            font-weight: 500;
            box-shadow: var(--shadow);
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        `;

        document.body.appendChild(notification);

        // Remove after 3 seconds
        setTimeout(() => {
            notification.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);

        // Also log to console
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}

/**
 * Beast command runner utility
 */
const beast = {
    async run(cmd) {
        try {
            if (window.app) {
                window.app.showSuccess(`Running: ${cmd}...`);
            }

            const result = await api.runCommand(cmd);
            console.log('Command result:', result);

            if (result.ok) {
                if (window.app) {
                    window.app.showSuccess(`Command ${cmd} completed`);
                    window.app.loadTabData(window.app.currentTab);
                }
            } else {
                if (window.app) {
                    window.app.showError(result.error || `Command ${cmd} failed`);
                }
            }
        } catch (error) {
            console.error('Command failed:', error);
            if (window.app) {
                window.app.showError(`Command ${cmd} failed: ${error.message}`);
            }
        }
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
    window.app.init();
});

// Add fadeOut animation
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from { opacity: 1; transform: translateY(0); }
        to { opacity: 0; transform: translateY(10px); }
    }
`;
document.head.appendChild(style);
