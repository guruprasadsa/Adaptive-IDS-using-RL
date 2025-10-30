import apiClient from '../utils/apiClient';

export interface CreateIncidentRequest {
    title: string;
    description: string;
    severity: 'low' | 'medium' | 'high' | 'critical';
    alert_ids?: string[];
}

export interface UpdateIncidentStatusRequest {
    status: 'open' | 'investigating' | 'contained' | 'resolved';
}

export interface AssignIncidentRequest {
    assigned_to: string;
}

export interface LinkAlertsRequest {
    alert_ids: string[];
}

export interface IncidentResponse {
    id: string;
    incident_id: string;
    title: string;
    description: string;
    status: string;
    severity: string;
    assigned_to: string | null;
    created_at: string;
    updated_at: string;
    related_alerts: string[];
}

/**
 * Create a new incident
 */
export const createIncident = async (data: CreateIncidentRequest): Promise<IncidentResponse> => {
    try {
        const response = await apiClient.post<IncidentResponse>('/incidents', data);
        return response.data;
    } catch (error) {
        console.error('Error creating incident:', error);
        throw error;
    }
};

/**
 * Update incident status
 */
export const updateIncidentStatus = async (
    incidentId: string, 
    status: UpdateIncidentStatusRequest['status']
): Promise<IncidentResponse> => {
    try {
        const response = await apiClient.patch<IncidentResponse>(
            `/incidents/${incidentId}/status`, 
            { status }
        );
        return response.data;
    } catch (error) {
        console.error('Error updating incident status:', error);
        throw error;
    }
};

/**
 * Assign incident to a user
 */
export const assignIncident = async (
    incidentId: string, 
    assignedTo: string
): Promise<IncidentResponse> => {
    try {
        const response = await apiClient.patch<IncidentResponse>(
            `/incidents/${incidentId}/assign`, 
            { assigned_to: assignedTo }
        );
        return response.data;
    } catch (error) {
        console.error('Error assigning incident:', error);
        throw error;
    }
};

/**
 * Link alerts to an incident
 */
export const linkAlertsToIncident = async (
    incidentId: string, 
    alertIds: string[]
): Promise<IncidentResponse> => {
    try {
        const response = await apiClient.post<IncidentResponse>(
            `/incidents/${incidentId}/alerts`, 
            { alert_ids: alertIds }
        );
        return response.data;
    } catch (error) {
        console.error('Error linking alerts to incident:', error);
        throw error;
    }
};

/**
 * Unlink an alert from an incident
 */
export const unlinkAlertFromIncident = async (
    incidentId: string, 
    alertId: string
): Promise<IncidentResponse> => {
    try {
        const response = await apiClient.delete<IncidentResponse>(
            `/incidents/${incidentId}/alerts/${alertId}`
        );
        return response.data;
    } catch (error) {
        console.error('Error unlinking alert from incident:', error);
        throw error;
    }
};
