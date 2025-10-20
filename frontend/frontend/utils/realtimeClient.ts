/**
 * frontend/utils/realtimeClient.ts
 * Server-Sent Events client for real-time alert notifications
 */

import type { SSEMessage, ConnectionStatus } from '../types';
import { tokenManager } from './apiClient';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

export type EventCallback = (message: SSEMessage) => void;
export type StatusCallback = (status: ConnectionStatus) => void;

export class RealtimeClient {
    private eventSource: EventSource | null = null;
    private reconnectAttempts = 0;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private eventCallbacks: Set<EventCallback> = new Set();
    private statusCallbacks: Set<StatusCallback> = new Set();
    private currentStatus: ConnectionStatus = 'disconnected';
    private manualDisconnect = false;

    constructor() {
        // Listen for authentication changes
        window.addEventListener('auth:logout', () => this.disconnect());
    }

    /**
     * Connect to the SSE stream
     */
    connect(): void {
        if (this.eventSource) {
            console.warn('Already connected to SSE stream');
            return;
        }

        const accessToken = tokenManager.getAccessToken();
        if (!accessToken) {
            console.log('SSE: No access token available, skipping connection');
            this.updateStatus('disconnected');
            return;
        }

        this.manualDisconnect = false;
        this.updateStatus('reconnecting');

        try {
            // EventSource doesn't support custom headers, so we pass token as query param
            // In production, consider using WebSocket for better authentication support
            const url = `${API_BASE_URL}/api/stream/alerts?token=${encodeURIComponent(accessToken)}`;
            
            this.eventSource = new EventSource(url);

            this.eventSource.onopen = () => {
                console.log('SSE connection established');
                this.reconnectAttempts = 0;
                this.updateStatus('connected');
            };

            this.eventSource.onmessage = (event) => {
                try {
                    const message: SSEMessage = JSON.parse(event.data);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Failed to parse SSE message:', error);
                }
            };

            this.eventSource.onerror = (error) => {
                console.error('SSE error:', error);
                this.handleError();
            };
        } catch (error) {
            console.error('Failed to create EventSource:', error);
            this.handleError();
        }
    }

    /**
     * Disconnect from the SSE stream
     */
    disconnect(): void {
        this.manualDisconnect = true;
        
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.updateStatus('disconnected');
    }

    /**
     * Subscribe to SSE events
     */
    onEvent(callback: EventCallback): () => void {
        this.eventCallbacks.add(callback);
        
        // Return unsubscribe function
        return () => {
            this.eventCallbacks.delete(callback);
        };
    }

    /**
     * Subscribe to connection status changes
     */
    onStatusChange(callback: StatusCallback): () => void {
        this.statusCallbacks.add(callback);
        
        // Immediately call with current status
        callback(this.currentStatus);
        
        // Return unsubscribe function
        return () => {
            this.statusCallbacks.delete(callback);
        };
    }

    /**
     * Get current connection status
     */
    getStatus(): ConnectionStatus {
        return this.currentStatus;
    }

    /**
     * Check if connected
     */
    isConnected(): boolean {
        return this.currentStatus === 'connected';
    }

    private handleMessage(message: SSEMessage): void {
        // Notify all subscribers
        this.eventCallbacks.forEach(callback => {
            try {
                callback(message);
            } catch (error) {
                console.error('Error in SSE event callback:', error);
            }
        });
    }

    private handleError(): void {
        this.eventSource = null;
        this.updateStatus('error');

        // Don't reconnect if manually disconnected
        if (this.manualDisconnect) {
            return;
        }

        // Attempt to reconnect
        if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            this.reconnectAttempts++;
            const delay = RECONNECT_INTERVAL * Math.min(this.reconnectAttempts, 5);
            
            console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
            
            this.reconnectTimer = setTimeout(() => {
                this.connect();
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
            this.updateStatus('disconnected');
        }
    }

    private updateStatus(status: ConnectionStatus): void {
        if (this.currentStatus === status) {
            return;
        }

        this.currentStatus = status;
        
        // Notify all status subscribers
        this.statusCallbacks.forEach(callback => {
            try {
                callback(status);
            } catch (error) {
                console.error('Error in status change callback:', error);
            }
        });
    }
}

// Singleton instance
let realtimeClientInstance: RealtimeClient | null = null;

export function getRealtimeClient(): RealtimeClient {
    if (!realtimeClientInstance) {
        realtimeClientInstance = new RealtimeClient();
    }
    return realtimeClientInstance;
}

// React hook for using the realtime client
export function useRealtimeClient() {
    const client = getRealtimeClient();
    
    return {
        connect: () => client.connect(),
        disconnect: () => client.disconnect(),
        onEvent: (callback: EventCallback) => client.onEvent(callback),
        onStatusChange: (callback: StatusCallback) => client.onStatusChange(callback),
        isConnected: () => client.isConnected(),
        getStatus: () => client.getStatus(),
    };
}

export default getRealtimeClient;
