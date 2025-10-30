/**
 * Analytics Data Service
 * Handles fetching and managing analytics data
 */

import apiClient from '../utils/apiClient';

export interface AnalyticsSummary {
    total_alerts: number;
    critical_alerts: number;
    attack_types: number;
    unique_ips: number;
}

export interface TopAttack {
    name: string;
    count: number;
    percentage: number;
}

export interface TopSourceIP {
    ip: string;
    count: number;
    severity: string;
}

export interface TopDestIP {
    ip: string;
    count: number;
    protocol: string;
}

export interface SeverityDistribution {
    severity: string;
    count: number;
    percentage: number;
}

export interface AlertTrend {
    time: string;
    count: number;
}

export interface AnalyticsData {
    summary: AnalyticsSummary;
    topAttacks: TopAttack[];
    topSourceIPs: TopSourceIP[];
    topDestIPs: TopDestIP[];
    severityDistribution: SeverityDistribution[];
    trends: AlertTrend[];
}

/**
 * Fetch all analytics data for a given time range
 */
export async function fetchAnalyticsData(timeRange: string = '24h'): Promise<AnalyticsData> {
    try {
        const [summary, topAttacks, sourceIPs, destIPs, distribution, trends] = await Promise.all([
            apiClient.get(`/analytics/summary?time_range=${timeRange}`),
            apiClient.get(`/analytics/top-attacks?time_range=${timeRange}&limit=10`),
            apiClient.get(`/analytics/top-source-ips?time_range=${timeRange}&limit=10`),
            apiClient.get(`/analytics/top-dest-ips?time_range=${timeRange}&limit=10`),
            apiClient.get(`/analytics/severity-distribution?time_range=${timeRange}`),
            apiClient.get(`/analytics/trends?time_range=${timeRange}`)
        ]);

        return {
            summary: summary.data,
            topAttacks: topAttacks.data,
            topSourceIPs: sourceIPs.data,
            topDestIPs: destIPs.data,
            severityDistribution: distribution.data,
            trends: trends.data
        };
    } catch (error) {
        console.error('Failed to fetch analytics data:', error);
        throw error;
    }
}

/**
 * Export analytics data as CSV
 */
export function exportAnalyticsToCSV(data: AnalyticsData, timeRange: string): void {
    const timestamp = new Date().toISOString().split('T')[0];
    const filename = `analytics_${timeRange}_${timestamp}.csv`;
    
    // Build CSV content
    let csvContent = 'Analytics Report\n';
    csvContent += `Time Range: ${timeRange}\n`;
    csvContent += `Generated: ${new Date().toLocaleString()}\n\n`;
    
    // Summary
    csvContent += 'Summary\n';
    csvContent += 'Metric,Value\n';
    csvContent += `Total Alerts,${data.summary.total_alerts}\n`;
    csvContent += `Critical Alerts,${data.summary.critical_alerts}\n`;
    csvContent += `Attack Types,${data.summary.attack_types}\n`;
    csvContent += `Unique IPs,${data.summary.unique_ips}\n\n`;
    
    // Top Attacks
    csvContent += 'Top Attack Types\n';
    csvContent += 'Attack Type,Count,Percentage\n';
    data.topAttacks.forEach(attack => {
        csvContent += `${attack.name},${attack.count},${attack.percentage}%\n`;
    });
    csvContent += '\n';
    
    // Top Source IPs
    csvContent += 'Top Source IPs\n';
    csvContent += 'IP Address,Count,Max Severity\n';
    data.topSourceIPs.forEach(ip => {
        csvContent += `${ip.ip},${ip.count},${ip.severity}\n`;
    });
    csvContent += '\n';
    
    // Top Destination IPs
    csvContent += 'Top Destination IPs\n';
    csvContent += 'IP Address,Count,Protocol\n';
    data.topDestIPs.forEach(ip => {
        csvContent += `${ip.ip},${ip.count},${ip.protocol}\n`;
    });
    csvContent += '\n';
    
    // Severity Distribution
    csvContent += 'Severity Distribution\n';
    csvContent += 'Severity,Count,Percentage\n';
    data.severityDistribution.forEach(item => {
        csvContent += `${item.severity},${item.count},${item.percentage}%\n`;
    });
    
    // Create and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
}
