/**
 * frontend/utils/csvExport.ts
 * CSV export utility for alerts
 */

import type { Alert } from '../types';

/**
 * Convert alerts to CSV format and trigger download
 */
export function exportAlertsToCSV(alerts: Alert[], filename: string = 'alerts.csv'): void {
    if (alerts.length === 0) {
        console.warn('No alerts to export');
        return;
    }

    // Define CSV columns
    const columns = [
        { key: 'id', label: 'ID' },
        { key: 'timestamp', label: 'Timestamp' },
        { key: 'priority', label: 'Priority' },
        { key: 'severity', label: 'Severity' },
        { key: 'status', label: 'Status' },
        { key: 'className', label: 'Attack Type' },
        { key: 'confidence', label: 'Confidence' },
        { key: 'srcIp', label: 'Source IP' },
        { key: 'srcPort', label: 'Source Port' },
        { key: 'dstIp', label: 'Destination IP' },
        { key: 'dstPort', label: 'Destination Port' },
        { key: 'protocol', label: 'Protocol' },
        { key: 'description', label: 'Description' },
        { key: 'modelVersion', label: 'Model Version' },
        { key: 'assignedTo', label: 'Assigned To' },
        { key: 'notes', label: 'Notes' },
    ];

    // Create CSV header row
    const headerRow = columns.map(col => escapeCSVValue(col.label)).join(',');

    // Create CSV data rows
    const dataRows = alerts.map(alert => {
        return columns.map(col => {
            const value = getAlertValue(alert, col.key as keyof Alert);
            return escapeCSVValue(value);
        }).join(',');
    });

    // Combine header and data
    const csvContent = [headerRow, ...dataRows].join('\n');

    // Create blob and download
    downloadCSV(csvContent, filename);
}

/**
 * Get value from alert object with proper formatting
 */
function getAlertValue(alert: Alert, key: keyof Alert): string {
    const value = alert[key];

    if (value === null || value === undefined) {
        return '';
    }

    // Format specific fields
    switch (key) {
        case 'timestamp':
            return new Date(value as string).toISOString();
        case 'confidence':
            return typeof value === 'number' ? `${(value * 100).toFixed(2)}%` : '';
        case 'srcPort':
        case 'dstPort':
            return typeof value === 'number' ? value.toString() : '';
        default:
            return String(value);
    }
}

/**
 * Escape CSV values (handle commas, quotes, newlines)
 */
function escapeCSVValue(value: string | number | boolean | null | undefined): string {
    if (value === null || value === undefined) {
        return '';
    }

    const stringValue = String(value);

    // Check if value needs to be quoted
    if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\n')) {
        // Escape double quotes by doubling them
        const escapedValue = stringValue.replace(/"/g, '""');
        return `"${escapedValue}"`;
    }

    return stringValue;
}

/**
 * Trigger CSV download in browser
 */
function downloadCSV(content: string, filename: string): void {
    // Create blob with UTF-8 BOM for Excel compatibility
    const BOM = '\uFEFF';
    const blob = new Blob([BOM + content], { type: 'text/csv;charset=utf-8;' });

    // Create download link
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.display = 'none';

    // Trigger download
    document.body.appendChild(link);
    link.click();

    // Cleanup
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    console.log(`Exported ${content.split('\n').length - 1} alerts to ${filename}`);
}

/**
 * Generate filename with timestamp
 */
export function generateCSVFilename(prefix: string = 'alerts'): string {
    const now = new Date();
    const timestamp = now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
    return `${prefix}_${timestamp}.csv`;
}
