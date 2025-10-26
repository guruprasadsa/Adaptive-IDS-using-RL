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
    // Extended fields from new backend API
    severity?: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
    className?: string;
    classIdx?: number;
    srcIp?: string;
    dstIp?: string;
    srcPort?: number;
    dstPort?: number;
    protocol?: string;
    modelVersion?: string;
    featureVersion?: string;
    assignedTo?: string | null;
    notes?: string | null;
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
        severity?: 'all' | 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
        className?: string;
        minConfidence?: number;
        maxConfidence?: number;
        srcIp?: string;
        dstIp?: string;
        startTime?: string;
        endTime?: string;
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

// User roles matching backend RBAC
export type UserRole = 'admin' | 'analyst' | 'viewer' | 'auditor';

// Permissions matching backend RBAC
export type Permission =
    // Alert permissions
    | 'view_alerts'
    | 'create_alerts'
    | 'update_alerts'
    | 'delete_alerts'
    | 'ack_alerts'
    | 'mark_false_positive'
    // Incident permissions
    | 'view_incidents'
    | 'create_incidents'
    | 'update_incidents'
    | 'delete_incidents'
    // Model permissions
    | 'view_models'
    | 'deploy_models'
    | 'train_models'
    // User management
    | 'view_users'
    | 'create_users'
    | 'update_users'
    | 'delete_users'
    // System configuration
    | 'view_config'
    | 'update_config'
    // Audit logs
    | 'view_audit_logs'
    // Integration management
    | 'manage_integrations';

export type User = {
    id: number;
    username: string;
    email: string;
    role: UserRole;
    is_active: boolean;
    created_at?: string;
    last_login?: string;
    permissions?: Permission[];
};

export type LoginResponse = {
    access_token: string;
    refresh_token: string;
    token_type: string;
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
    type: 'connected' | 'heartbeat' | 'alert' | 'prediction' | 'flow' | 'message' | 'error';
    timestamp: string;
    user_id?: number;
    topic?: string;
    data?: any;
};
