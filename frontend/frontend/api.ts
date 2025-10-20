// API service for connecting to the backend Flask server
// Enhanced with better error handling, retry logic, and caching

import apiClient, { tokenManager, retryRequest, cachedGet, clearCache } from './utils/apiClient';
import type { 
    Alert, 
    Incident, 
    ModelMetrics, 
    DashboardStats, 
    PredictionResult, 
    AlertsResponse, 
    IncidentsResponse, 
    User, 
    LoginResponse, 
    RegisterResponse 
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000';

// Re-export token manager for convenience
export { tokenManager, clearCache };

class ApiService {
    // Token management - delegate to tokenManager
    getAccessToken(): string | null {
        return tokenManager.getAccessToken();
    }

    getRefreshToken(): string | null {
        return tokenManager.getRefreshToken();
    }

    setTokens(accessToken: string, refreshToken: string): void {
        tokenManager.setTokens(accessToken, refreshToken);
    }

    clearTokens(): void {
        tokenManager.clearTokens();
        clearCache(); // Clear API cache on logout
    }

    isAuthenticated(): boolean {
        return tokenManager.isAuthenticated();
    }

    // Authentication endpoints
    async register(username: string, email: string, password: string): Promise<RegisterResponse> {
        const response = await apiClient.post<RegisterResponse>('/auth/register', {
            username,
            email,
            password
        });
        return response.data;
    }

    async login(emailOrUsername: string, password: string): Promise<LoginResponse> {
        const response = await apiClient.post<LoginResponse>('/auth/login', {
            email_or_username: emailOrUsername,
            password
        });

        // Store tokens
        this.setTokens(response.data.access_token, response.data.refresh_token);

        return response.data;
    }

    async logout(): Promise<void> {
        const refreshToken = this.getRefreshToken();
        
        try {
            await apiClient.post('/auth/logout', { refresh_token: refreshToken });
        } finally {
            // Always clear tokens locally
            this.clearTokens();
        }
    }

    async getCurrentUser(): Promise<User> {
        const response = await apiClient.get<User>('/auth/me');
        return response.data;
    }

    async refreshAccessToken(): Promise<void> {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token available');
        }

        const response = await apiClient.post('/auth/refresh', {
            refresh_token: refreshToken
        });

        const { access_token } = response.data;
        tokenManager.setTokens(access_token, refreshToken);
    }

    // Health check with caching
    async healthCheck(): Promise<{ status: string; model_loaded: boolean; database: string; timestamp: string; version: string }> {
        return await cachedGet('/health', 10000); // Cache for 10 seconds
    }

    // Prediction endpoint
    async predict(data: Record<string, any>): Promise<PredictionResult> {
        const response = await apiClient.post<PredictionResult>('/predict', data);
        return response.data;
    }

    // Dashboard stats with caching
    async getDashboardStats(): Promise<DashboardStats> {
        return await cachedGet('/dashboard/stats', 30000); // Cache for 30 seconds
    }

    // Get alerts with pagination and filters
    async getAlerts(page: number = 1, perPage: number = 10, filters: Record<string, any> = {}): Promise<AlertsResponse> {
        const response = await apiClient.get<AlertsResponse>('/alerts', {
            params: {
                page,
                per_page: perPage,
                ...filters
            }
        });
        return response.data;
    }

    // Get incidents with pagination and filters
    async getIncidents(page: number = 1, perPage: number = 10, filters: Record<string, any> = {}): Promise<IncidentsResponse> {
        const response = await apiClient.get<IncidentsResponse>('/incidents', {
            params: {
                page,
                per_page: perPage,
                ...filters
            }
        });
        return response.data;
    }

    // Get a specific alert
    async getAlert(id: string): Promise<Alert> {
        const response = await apiClient.get<Alert>(`/alerts/${id}`);
        return response.data;
    }

    // Get a specific incident
    async getIncident(id: string): Promise<Incident> {
        const response = await apiClient.get<Incident>(`/incidents/${id}`);
        return response.data;
    }

    // Update alert status
    async updateAlertStatus(id: string, status: string): Promise<Alert> {
        const response = await apiClient.patch<Alert>(`/alerts/${id}/status`, { status });
        clearCache('alerts'); // Invalidate alerts cache
        return response.data;
    }

    // Update incident status
    async updateIncidentStatus(id: string, status: string): Promise<Incident> {
        const response = await apiClient.patch<Incident>(`/incidents/${id}/status`, { status });
        clearCache('incidents'); // Invalidate incidents cache
        return response.data;
    }

    // Get model metrics with caching
    async getModelMetrics(): Promise<ModelMetrics> {
        return await cachedGet('/model/metrics', 300000); // Cache for 5 minutes
    }

    // Retrain model
    async retrainModel(): Promise<{ status: string; message: string }> {
        const response = await apiClient.post<{ status: string; message: string }>('/model/retrain');
        return response.data;
    }
}

export const apiService = new ApiService();
