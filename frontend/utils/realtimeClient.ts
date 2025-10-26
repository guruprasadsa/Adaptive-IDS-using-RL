/**
 * frontend/utils/realtimeClient.ts
 * Server-Sent Events client for real-time alert notifications
 * Updated to use /api/events endpoint with proper event types
 */

import type { Alert, ConnectionStatus, SSEMessage } from '../types';
import { tokenManager } from './apiClient';

// Use empty string for production (nginx proxy), localhost:5001 for development
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL !== undefined && import.meta.env.VITE_API_BASE_URL !== '' 
    ? import.meta.env.VITE_API_BASE_URL 
    : (import.meta.env.DEV ? 'http://localhost:5001' : '');
const RECONNECT_INTERVAL = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

export type EventCallback = (message: SSEMessage) => void;
export type AlertCallback = (alert: Alert) => void;
export type StatusCallback = (status: ConnectionStatus) => void;

export class RealtimeClient {
    private eventSource: EventSource | null = null;
    private reconnectAttempts = 0;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private eventCallbacks: Set<EventCallback> = new Set();
    private alertCallbacks: Set<AlertCallback> = new Set();
    private statusCallbacks: Set<StatusCallback> = new Set();
    private currentStatus: ConnectionStatus = 'disconnected';
    private manualDisconnect = false;
    private topic: string = 'alerts';

    constructor() {
        // Listen for authentication changes
        window.addEventListener('auth:logout', () => this.disconnect());
    }

    /**
     * Connect to the SSE stream
     * @param topic - Kafka topic to stream from ('alerts' or 'predictions')
     */
    connect(topic: string = 'alerts'): void {
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
        this.topic = topic;
        this.updateStatus('reconnecting');

        try {
            // EventSource doesn't support custom headers, so we pass token as query param
            const url = `${API_BASE_URL}/api/events?token=${encodeURIComponent(accessToken)}&topic=${encodeURIComponent(topic)}`;
            
            this.eventSource = new EventSource(url);

            // Handle connection opened
            this.eventSource.addEventListener('open', () => {
                console.log('SSE connection established');
                this.reconnectAttempts = 0;
                this.updateStatus('connected');
            });

            // Handle 'connected' event
            this.eventSource.addEventListener('connected', (event) => {
                const data = JSON.parse(event.data);
                console.log('SSE connected:', data);
                this.handleMessage({
                    type: 'connected',
                    timestamp: data.timestamp,
                    user_id: data.user_id,
                    topic: data.topic
                });
            });

            // Handle 'alert' events
            this.eventSource.addEventListener('alert', (event) => {
                try {
                    const alertData = JSON.parse(event.data);
                    console.log('SSE alert received:', alertData);
                    
                    this.handleMessage({
                        type: 'alert',
                        timestamp: new Date().toISOString(),
                        data: alertData
                    });
                    
                    // Notify alert-specific callbacks
                    this.alertCallbacks.forEach(callback => {
                        try {
                            callback(alertData);
                        } catch (error) {
                            console.error('Error in alert callback:', error);
                        }
                    });
                } catch (error) {
                    console.error('Failed to parse alert event:', error);
                }
            });

            // Handle 'prediction' events
            this.eventSource.addEventListener('prediction', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('SSE prediction received:', data);
                    this.handleMessage({
                        type: 'prediction',
                        timestamp: new Date().toISOString(),
                        data
                    });
                } catch (error) {
                    console.error('Failed to parse prediction event:', error);
                }
            });

            // Handle 'heartbeat' events
            this.eventSource.addEventListener('heartbeat', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.debug('SSE heartbeat:', data.timestamp);
                    this.handleMessage({
                        type: 'heartbeat',
                        timestamp: new Date().toISOString(),
                        data
                    });
                } catch (error) {
                    console.error('Failed to parse heartbeat event:', error);
                }
            });

            // Handle 'message' events (for traffic.stats and other generic messages)
            this.eventSource.addEventListener('message', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('SSE message received:', data);
                    
                    // Check if this is a traffic stats message
                    if (data.packets !== undefined || data.packets_per_second !== undefined) {
                        console.log('SSE traffic.stats:', data);
                        this.handleMessage({
                            type: 'message',
                            timestamp: new Date().toISOString(),
                            data
                        });
                    } else {
                        // Generic message
                        this.handleMessage({
                            type: 'message',
                            timestamp: new Date().toISOString(),
                            data
                        });
                    }
                } catch (error) {
                    console.error('Failed to parse message event:', error);
                }
            });

            // Handle 'error' events from server
            this.eventSource.addEventListener('error', (event: any) => {
                if (event.data) {
                    try {
                        const data = JSON.parse(event.data);
                        console.error('SSE server error:', data);
                        this.handleMessage({
                            type: 'error',
                            timestamp: new Date().toISOString(),
                            data
                        });
                    } catch (parseError) {
                        console.error('Failed to parse error event:', parseError);
                    }
                }
            });

            // Handle generic messages (fallback)
            this.eventSource.onmessage = (event) => {
                try {
                    const message: SSEMessage = JSON.parse(event.data);
                    console.log('SSE message received:', message);
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Failed to parse SSE message:', error);
                }
            };

            // Handle connection errors
            this.eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);
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
     * Subscribe to all SSE events
     */
    onEvent(callback: EventCallback): () => void {
        this.eventCallbacks.add(callback);
        
        // Return unsubscribe function
        return () => {
            this.eventCallbacks.delete(callback);
        };
    }

    /**
     * Subscribe to alert events specifically
     */
    onAlert(callback: AlertCallback): () => void {
        this.alertCallbacks.add(callback);
        
        // Return unsubscribe function
        return () => {
            this.alertCallbacks.delete(callback);
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
                this.connect(this.topic);
            }, delay);
            
            this.updateStatus('reconnecting');
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
        connect: (topic?: string) => client.connect(topic),
        disconnect: () => client.disconnect(),
        onEvent: (callback: EventCallback) => client.onEvent(callback),
        onAlert: (callback: AlertCallback) => client.onAlert(callback),
        onStatusChange: (callback: StatusCallback) => client.onStatusChange(callback),
        isConnected: () => client.isConnected(),
        getStatus: () => client.getStatus(),
    };
}

export default getRealtimeClient;
