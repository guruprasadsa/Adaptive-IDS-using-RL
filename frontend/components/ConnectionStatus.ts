/**
 * frontend/components/ConnectionStatus.ts
 * Connection status indicator component for monitoring backend connectivity
 */

import type { ConnectionStatus } from '../types';
import { useRealtimeClient } from '../utils/realtimeClient';
import { checkHealth } from '../utils/apiClient';

export class ConnectionStatusComponent {
    private element: HTMLElement | null = null;
    private status: ConnectionStatus = 'disconnected';
    private healthCheckInterval: NodeJS.Timeout | null = null;
    private realtimeUnsubscribe: (() => void) | null = null;

    constructor(private containerId: string) {}

    /**
     * Initialize and mount the component
     */
    mount(): void {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`Container #${this.containerId} not found`);
            return;
        }

        this.element = this.createElement();
        container.appendChild(this.element);

        // Start health checks
        this.startHealthChecks();

        // Subscribe to realtime connection status
        const realtimeClient = useRealtimeClient();
        this.realtimeUnsubscribe = realtimeClient.onStatusChange((status) => {
            this.updateStatus(status);
        });
    }

    /**
     * Unmount and cleanup the component
     */
    unmount(): void {
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
            this.healthCheckInterval = null;
        }

        if (this.realtimeUnsubscribe) {
            this.realtimeUnsubscribe();
            this.realtimeUnsubscribe = null;
        }

        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
            this.element = null;
        }
    }

    /**
     * Create the connection status element
     */
    private createElement(): HTMLElement {
        const wrapper = document.createElement('div');
        wrapper.className = 'connection-status';
        wrapper.innerHTML = `
            <div class="status-indicator ${this.getStatusClass()}" title="${this.getStatusText()}">
                <span class="status-dot"></span>
                <span class="status-text">${this.getStatusText()}</span>
            </div>
        `;

        // Add click handler to show more details
        const indicator = wrapper.querySelector('.status-indicator');
        if (indicator) {
            indicator.addEventListener('click', () => this.showDetails());
        }

        return wrapper;
    }

    /**
     * Update the connection status
     */
    private updateStatus(status: ConnectionStatus): void {
        this.status = status;
        
        if (!this.element) return;

        const indicator = this.element.querySelector('.status-indicator');
        const textElement = this.element.querySelector('.status-text');
        
        if (indicator && textElement) {
            // Remove all status classes
            indicator.classList.remove('status-connected', 'status-disconnected', 'status-reconnecting', 'status-error');
            
            // Add new status class
            indicator.classList.add(this.getStatusClass());
            
            // Update text
            textElement.textContent = this.getStatusText();
            indicator.setAttribute('title', this.getStatusText());
        }
    }

    /**
     * Get status-specific CSS class
     */
    private getStatusClass(): string {
        return `status-${this.status}`;
    }

    /**
     * Get human-readable status text
     */
    private getStatusText(): string {
        switch (this.status) {
            case 'connected':
                return 'Connected';
            case 'disconnected':
                return 'Disconnected';
            case 'reconnecting':
                return 'Reconnecting...';
            case 'error':
                return 'Connection Error';
            default:
                return 'Unknown';
        }
    }

    /**
     * Start periodic health checks
     */
    private startHealthChecks(): void {
        // Check immediately
        this.performHealthCheck();

        // Then check every 30 seconds
        this.healthCheckInterval = setInterval(() => {
            this.performHealthCheck();
        }, 30000);
    }

    /**
     * Perform a health check
     */
    private async performHealthCheck(): Promise<void> {
        try {
            const isHealthy = await checkHealth(5000);
            
            // Only update if realtime is not connected
            if (this.status === 'disconnected' || this.status === 'error') {
                this.updateStatus(isHealthy ? 'connected' : 'error');
            }
        } catch (error) {
            console.error('Health check failed:', error);
            if (this.status !== 'connected') {
                this.updateStatus('error');
            }
        }
    }

    /**
     * Show detailed connection information
     */
    private async showDetails(): Promise<void> {
        try {
            const health = await checkHealth();
            const message = health
                ? 'Backend is healthy and responding'
                : 'Unable to connect to backend';
            
            // In a real app, this would show a modal or toast
            alert(`Connection Status: ${this.getStatusText()}\n\n${message}`);
        } catch (error) {
            alert(`Connection Status: ${this.getStatusText()}\n\nBackend is not responding`);
        }
    }
}

/**
 * CSS styles for the connection status component
 * Add this to your main CSS file
 */
export const connectionStatusStyles = `
.connection-status {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 4px;
    background: rgba(0, 0, 0, 0.05);
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    transition: opacity 0.2s;
}

.status-indicator:hover {
    opacity: 0.8;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    animation: pulse 2s infinite;
}

.status-text {
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Status-specific colors */
.status-connected .status-dot {
    background: #22c55e;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.5);
}

.status-connected .status-text {
    color: #16a34a;
}

.status-disconnected .status-dot {
    background: #6b7280;
    animation: none;
}

.status-disconnected .status-text {
    color: #6b7280;
}

.status-reconnecting .status-dot {
    background: #f59e0b;
    animation: pulse 1s infinite;
}

.status-reconnecting .status-text {
    color: #d97706;
}

.status-error .status-dot {
    background: #ef4444;
    animation: pulse 1s infinite;
}

.status-error .status-text {
    color: #dc2626;
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}
`;

// Export a factory function for easy instantiation
export function createConnectionStatus(containerId: string): ConnectionStatusComponent {
    return new ConnectionStatusComponent(containerId);
}
