export type NavItem = {
    id: string;
    label: string;
    icon: string;
};

export type StatCardData = {
    title: string;
    value: string;
    icon: string;
    colorClass: string;
};

export type Alert = {
    id: string;
    priority: 'low' | 'medium' | 'high' | 'critical';
    description: string;
    source: string;
    timestamp: string;
    status: 'new' | 'investigating' | 'resolved' | 'false_positive';
    type: string;
    confidence: number;
};

export type Incident = {
    id: string;
    title: string;
    status: 'open' | 'investigating' | 'contained' | 'resolved';
    severity: 'low' | 'medium' | 'high' | 'critical';
    assignedTo: string;
    createdAt: string;
    lastUpdatedAt: string;
    relatedAlertIds: string[];
    summary: string;
    description: string;
    affectedSystems: number;
    alertsCount: number;
};

export type AlertsState = {
    currentPage: number;
    itemsPerPage: number;
    sortColumn: keyof Alert;
    sortDirection: 'asc' | 'desc';
    filters: {
        priority: 'all' | Alert['priority'];
        status: 'all' | Alert['status'];
        search: string;
    };
};

export type IncidentsState = {
    currentPage: number;
    itemsPerPage: number;
    sortColumn: keyof Incident;
    sortDirection: 'asc' | 'desc';
    filters: {
        severity: 'all' | Incident['severity'];
        status: 'all' | Incident['status'];
        search: string;
    };
    expandedIncidentId: string | null;
};

// API Response Types
export type ModelMetrics = {
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
};

export type DashboardStats = {
    total_alerts: number;
    critical_alerts: number;
    open_incidents: number;
    total_incidents: number;
    model_metrics: ModelMetrics;
    recent_alerts: Alert[];
    recent_incidents: Incident[];
};

export type PredictionResult = {
    prediction: string;
    prediction_index: number;
    confidence: number;
    probabilities: Record<string, number>;
    features_used: string[];
};

export type AlertsResponse = {
    alerts: Alert[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
};

export type IncidentsResponse = {
    incidents: Incident[];
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
};

export type User = {
    id: number;
    username: string;
    email: string;
    role: string;
    created_at?: string;
    last_login?: string;
};

export type LoginResponse = {
    access_token: string;
    refresh_token: string;
    user: User;
};

export type RegisterResponse = {
    user: User;
};

export type HealthStatus = {
    status: string;
    model_loaded: boolean;
    database: string;
    timestamp: string;
    version: string;
};

export type ConnectionStatus = 'connected' | 'disconnected' | 'reconnecting' | 'error';

export type SSEMessage = {
    type: 'connected' | 'heartbeat' | 'alert' | 'incident' | 'error';
    timestamp: string;
    data?: any;
};
