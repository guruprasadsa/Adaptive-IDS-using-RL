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
