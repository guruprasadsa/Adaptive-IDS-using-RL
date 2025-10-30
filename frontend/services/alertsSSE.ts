/**
 * Alerts Real-Time Streaming Service
 * Connects to backend SSE endpoint for live alert updates
 */

export interface AlertSSEMessage {
  type: 'connected' | 'alert' | 'heartbeat';
  data?: any;
  timestamp?: string;
}

export type AlertSSECallback = (message: AlertSSEMessage) => void;
export type ErrorCallback = (error: Error) => void;

export class AlertsSSEClient {
  private eventSource: EventSource | null = null;
  private readonly baseUrl: string;
  private readonly token: string | null;
  private reconnectAttempts: number = 0;
  private maxReconnectAttempts: number = 10;
  private reconnectDelay: number = 1000; // Start with 1 second
  private maxReconnectDelay: number = 30000; // Max 30 seconds
  private callbacks: Set<AlertSSECallback> = new Set();
  private errorCallbacks: Set<ErrorCallback> = new Set();
  private isConnecting: boolean = false;

  constructor(baseUrl: string = 'http://localhost:5001', token: string | null = null) {
    this.baseUrl = baseUrl;
    this.token = token;
  }

  /**
   * Connect to SSE stream
   */
  connect(): void {
    if (this.eventSource || this.isConnecting) {
      console.warn('[AlertsSSE] Already connected or connecting');
      return;
    }

    this.isConnecting = true;
    const url = `${this.baseUrl}/api/alerts/stream`;
    
    try {
      // Create EventSource (token will be sent via cookie or can be added as query param if needed)
      this.eventSource = new EventSource(url, {
        withCredentials: true
      });

      // Connection opened
      this.eventSource.onopen = () => {
        console.log('[AlertsSSE] ✅ Connection established');
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        this.isConnecting = false;
      };

      // Receive messages
      this.eventSource.onmessage = (event: MessageEvent) => {
        try {
          const message: AlertSSEMessage = JSON.parse(event.data);
          this.notifyCallbacks(message);
        } catch (error) {
          console.error('[AlertsSSE] Failed to parse message:', error);
        }
      };

      // Handle errors
      this.eventSource.onerror = (error: Event) => {
        console.error('[AlertsSSE] Connection error:', error);
        this.isConnecting = false;
        
        // Close current connection
        if (this.eventSource) {
          this.eventSource.close();
          this.eventSource = null;
        }

        // Attempt reconnection with exponential backoff
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.reconnectAttempts++;
          const delay = Math.min(
            this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1),
            this.maxReconnectDelay
          );
          
          console.log(
            `[AlertsSSE] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`
          );
          
          setTimeout(() => this.connect(), delay);
        } else {
          console.error('[AlertsSSE] Max reconnection attempts reached');
          this.notifyError(new Error('Max reconnection attempts reached'));
        }
      };

    } catch (error) {
      console.error('[AlertsSSE] Failed to create EventSource:', error);
      this.isConnecting = false;
      this.notifyError(error as Error);
    }
  }

  /**
   * Disconnect from SSE stream
   */
  disconnect(): void {
    if (this.eventSource) {
      console.log('[AlertsSSE] Disconnecting...');
      this.eventSource.close();
      this.eventSource = null;
    }
    this.isConnecting = false;
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
  }

  /**
   * Subscribe to alert updates
   */
  subscribe(callback: AlertSSECallback): () => void {
    this.callbacks.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.callbacks.delete(callback);
    };
  }

  /**
   * Subscribe to errors
   */
  onError(callback: ErrorCallback): () => void {
    this.errorCallbacks.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.errorCallbacks.delete(callback);
    };
  }

  /**
   * Check if connected
   */
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }

  /**
   * Get connection state
   */
  getState(): string {
    if (!this.eventSource) return 'DISCONNECTED';
    
    switch (this.eventSource.readyState) {
      case EventSource.CONNECTING:
        return 'CONNECTING';
      case EventSource.OPEN:
        return 'CONNECTED';
      case EventSource.CLOSED:
        return 'CLOSED';
      default:
        return 'UNKNOWN';
    }
  }

  /**
   * Notify all subscribers
   */
  private notifyCallbacks(message: AlertSSEMessage): void {
    this.callbacks.forEach((callback) => {
      try {
        callback(message);
      } catch (error) {
        console.error('[AlertsSSE] Callback error:', error);
      }
    });
  }

  /**
   * Notify error subscribers
   */
  private notifyError(error: Error): void {
    this.errorCallbacks.forEach((callback) => {
      try {
        callback(error);
      } catch (err) {
        console.error('[AlertsSSE] Error callback error:', err);
      }
    });
  }
}

// Singleton instance
let alertsSSEClient: AlertsSSEClient | null = null;

/**
 * Get singleton SSE client instance
 */
export function getAlertsSSEClient(baseUrl?: string, token?: string | null): AlertsSSEClient {
  if (!alertsSSEClient) {
    alertsSSEClient = new AlertsSSEClient(baseUrl, token);
  }
  return alertsSSEClient;
}

/**
 * Destroy singleton instance
 */
export function destroyAlertsSSEClient(): void {
  if (alertsSSEClient) {
    alertsSSEClient.disconnect();
    alertsSSEClient = null;
  }
}

