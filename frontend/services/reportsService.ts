import apiClient from '../utils/apiClient';

export interface GenerateReportRequest {
    report_type: 'alert-summary' | 'incident-timeline' | 'model-performance' | 'threat-intelligence' | 'compliance' | 'custom';
    date_range: '24h' | '7d' | '30d' | '90d' | 'ytd' | string; // Can also be "YYYY-MM-DD:YYYY-MM-DD"
    format: 'json' | 'csv' | 'pdf';
}

export interface ReportResponse {
    report_id: string;
    report_type: string;
    format: string;
    generated_at: string;
    date_range: string;
    data?: any;
    content?: string; // For CSV content
    size: number;
}

export interface RecentReport {
    id: string;
    name: string;
    type: string;
    report_type: string;
    generated_at: string;
    date_range: string;
    size: string;
    format: string;
}

export interface ReportSchedule {
    id: string;
    report_type: string;
    name: string;
    frequency: 'daily' | 'weekly' | 'monthly';
    day_of_week?: string;
    time: string;
    format: 'json' | 'csv' | 'pdf';
    recipients: string[];
    enabled: boolean;
    next_run?: string;
}

export interface CreateScheduleRequest {
    report_type: string;
    name: string;
    frequency: 'daily' | 'weekly' | 'monthly';
    day_of_week?: string;
    time?: string;
    format: 'json' | 'csv' | 'pdf';
    recipients?: string[];
    enabled?: boolean;
}

/**
 * Generate a new report
 */
export const generateReport = async (request: GenerateReportRequest): Promise<ReportResponse> => {
    try {
        const response = await apiClient.post<ReportResponse>('/reports/generate', request);
        return response.data;
    } catch (error) {
        console.error('Error generating report:', error);
        throw error;
    }
};

/**
 * Get list of recent reports
 */
export const getRecentReports = async (limit: number = 10): Promise<{ reports: RecentReport[], total: number }> => {
    try {
        const response = await apiClient.get<{ reports: RecentReport[], total: number }>(
            `/reports/recent?limit=${limit}`
        );
        return response.data;
    } catch (error) {
        console.error('Error fetching recent reports:', error);
        throw error;
    }
};

/**
 * Download a specific report
 */
export const downloadReport = async (reportId: string, format: string): Promise<Blob> => {
    try {
        const response = await apiClient.get(
            `/reports/${reportId}/download?format=${format}`,
            { responseType: 'blob' }
        );
        return response.data;
    } catch (error) {
        console.error('Error downloading report:', error);
        throw error;
    }
};

/**
 * Delete a report
 */
export const deleteReport = async (reportId: string): Promise<void> => {
    try {
        await apiClient.delete(`/reports/${reportId}`);
    } catch (error) {
        console.error('Error deleting report:', error);
        throw error;
    }
};

/**
 * Get all report schedules
 */
export const getReportSchedules = async (): Promise<{ schedules: ReportSchedule[], total: number }> => {
    try {
        const response = await apiClient.get<{ schedules: ReportSchedule[], total: number }>(
            '/reports/schedules'
        );
        return response.data;
    } catch (error) {
        console.error('Error fetching report schedules:', error);
        throw error;
    }
};

/**
 * Create a new report schedule
 */
export const createReportSchedule = async (schedule: CreateScheduleRequest): Promise<ReportSchedule> => {
    try {
        const response = await apiClient.post<ReportSchedule>('/reports/schedules', schedule);
        return response.data;
    } catch (error) {
        console.error('Error creating report schedule:', error);
        throw error;
    }
};

/**
 * Update a report schedule
 */
export const updateReportSchedule = async (
    scheduleId: string, 
    updates: Partial<CreateScheduleRequest>
): Promise<void> => {
    try {
        await apiClient.put(`/reports/schedules/${scheduleId}`, updates);
    } catch (error) {
        console.error('Error updating report schedule:', error);
        throw error;
    }
};

/**
 * Delete a report schedule
 */
export const deleteReportSchedule = async (scheduleId: string): Promise<void> => {
    try {
        await apiClient.delete(`/reports/schedules/${scheduleId}`);
    } catch (error) {
        console.error('Error deleting report schedule:', error);
        throw error;
    }
};

/**
 * Download report content as file
 */
export const downloadReportAsFile = (content: string, filename: string, format: 'csv' | 'json'): void => {
    const blob = new Blob([content], { 
        type: format === 'csv' ? 'text/csv' : 'application/json' 
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
};
