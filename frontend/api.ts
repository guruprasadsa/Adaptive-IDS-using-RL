// API service for connecting to the backend Flask server

import { Alert, Incident } from './types';

const API_BASE_URL = 'http://localhost:5000/api';

export interface ModelMetrics {
    accuracy: number;
    precision_macro: number;
    recall_macro: number;
    f1_macro: number;
    roc_auc: number;
    balanced_accuracy: number;
    total_predictions: number;
    false_positives: number;
    false_negatives: number;
    true_positives: number;
    true_negatives: number;
}

export interface DashboardStats {
    total_alerts: number;
    critical_alerts: number;
    open_incidents: number;
    total_incidents: number;
    model_metrics: ModelMetrics;
    recent_alerts: Alert[];
    recent_incidents: Incident[];
}

export interface PredictionResult {
    prediction: string;
    prediction_index: number;
    confidence: number;
    probabilities: Record<string, number>;
    features_used: string[];
}

export interface AlertsResponse {
    alerts: Alert[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
}

export interface IncidentsResponse {
    incidents: Incident[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
}

class ApiService {
    private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const url = `${API_BASE_URL}${endpoint}`;
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
            ...options,
        });

        if (!response.ok) {
            throw new Error(`API request failed: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    // Health check
    async healthCheck(): Promise<{ status: string; model_loaded: boolean; timestamp: string }> {
        return this.request('/health');
    }

    // Prediction endpoint
    async predict(data: Record<string, any>): Promise<PredictionResult> {
        return this.request('/predict', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    // Dashboard stats
    async getDashboardStats(): Promise<DashboardStats> {
        return this.request('/dashboard/stats');
    }

    // Get alerts with pagination and filters
    async getAlerts(page: number = 1, perPage: number = 10, filters: Record<string, any> = {}): Promise<AlertsResponse> {
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: perPage.toString(),
            ...filters,
        });
        return this.request(`/alerts?${params}`);
    }

    // Get incidents with pagination and filters
    async getIncidents(page: number = 1, perPage: number = 10, filters: Record<string, any> = {}): Promise<IncidentsResponse> {
        const params = new URLSearchParams({
            page: page.toString(),
            per_page: perPage.toString(),
            ...filters,
        });
        return this.request(`/incidents?${params}`);
    }

    // Get a specific alert
    async getAlert(id: string): Promise<Alert> {
        return this.request(`/alerts/${id}`);
    }

    // Get a specific incident
    async getIncident(id: string): Promise<Incident> {
        return this.request(`/incidents/${id}`);
    }

    // Update alert status
    async updateAlertStatus(id: string, status: string): Promise<Alert> {
        return this.request(`/alerts/${id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status }),
        });
    }

    // Update incident status
    async updateIncidentStatus(id: string, status: string): Promise<Incident> {
        return this.request(`/incidents/${id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status }),
        });
    }

    // Get model metrics
    async getModelMetrics(): Promise<ModelMetrics> {
        return this.request('/model/metrics');
    }

    // Retrain model
    async retrainModel(): Promise<{ status: string; message: string }> {
        return this.request('/model/retrain', {
            method: 'POST',
        });
    }
}

export const apiService = new ApiService();
