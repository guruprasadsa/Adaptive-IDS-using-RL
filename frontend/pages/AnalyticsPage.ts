/**
 * Analytics Page
 * Network traffic analytics, attack trends, and statistical insights
 */

import Chart from "chart.js/auto";
import { toast } from "../components/Toast";
import type { AlertTrend } from "../services/analyticsService";
import { exportAnalyticsToCSV, fetchAnalyticsData } from "../services/analyticsService";
import type { User } from "../types";

interface TimeRange {
    label: string;
    value: string;
    hours: number;
}

const timeRanges: TimeRange[] = [
    { label: 'Last Hour', value: '1h', hours: 1 },
    { label: 'Last 6 Hours', value: '6h', hours: 6 },
    { label: 'Last 24 Hours', value: '24h', hours: 24 },
    { label: 'Last 7 Days', value: '7d', hours: 168 },
    { label: 'Last 30 Days', value: '30d', hours: 720 },
];

// Remove local AnalyticsData interface - using the one from analyticsService

export const renderAnalyticsPage = (user: User | null = null): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    
    // Page container
    const container = document.createElement('div');
    container.className = 'analytics-container';
    container.id = 'analytics-container';
    
    // Header with controls
    const header = document.createElement('div');
    header.className = 'analytics-header';
    header.innerHTML = `
        <div class="header-left">
            <h2>Network Analytics</h2>
            <p class="subtitle">Real-time traffic analysis and attack trends</p>
        </div>
        <div class="header-actions">
            <select id="time-range-select" class="filter-select">
                ${timeRanges.map(range => `
                    <option value="${range.value}" ${range.value === '24h' ? 'selected' : ''}>
                        ${range.label}
                    </option>
                `).join('')}
            </select>
            <button class="btn btn-secondary" id="refresh-analytics-btn">
                <span class="material-symbols-outlined">refresh</span>
                Refresh
            </button>
            <button class="btn btn-secondary" id="export-analytics-btn">
                <span class="material-symbols-outlined">download</span>
                Export
            </button>
        </div>
    `;
    
    // Summary cards
    const summarySection = document.createElement('div');
    summarySection.className = 'analytics-summary';
    summarySection.innerHTML = `
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(220, 53, 69, 0.1);">
                <span class="material-symbols-outlined" style="color: #dc3545;">security</span>
            </div>
            <div class="stat-content">
                <div class="stat-value" id="total-alerts-stat">--</div>
                <div class="stat-label">Total Alerts</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(255, 193, 7, 0.1);">
                <span class="material-symbols-outlined" style="color: #ffc107;">warning</span>
            </div>
            <div class="stat-content">
                <div class="stat-value" id="critical-alerts-stat">--</div>
                <div class="stat-label">Critical Alerts</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(23, 162, 184, 0.1);">
                <span class="material-symbols-outlined" style="color: #17a2b8;">trending_up</span>
            </div>
            <div class="stat-content">
                <div class="stat-value" id="attack-types-stat">--</div>
                <div class="stat-label">Attack Types</div>
            </div>
        </div>
        <div class="stat-card">
            <div class="stat-icon" style="background: rgba(40, 167, 69, 0.1);">
                <span class="material-symbols-outlined" style="color: #28a745;">network_check</span>
            </div>
            <div class="stat-content">
                <div class="stat-value" id="unique-ips-stat">--</div>
                <div class="stat-label">Unique IPs</div>
            </div>
        </div>
    `;
    
    // Charts section
    const chartsSection = document.createElement('div');
    chartsSection.className = 'analytics-charts';
    
    // Alert trends chart
    const trendsCard = document.createElement('div');
    trendsCard.className = 'card analytics-card';
    trendsCard.innerHTML = `
        <div class="card-header">
            <h3>Alert Trends</h3>
            <span class="card-subtitle">Alerts over time</span>
        </div>
        <div class="card-body">
            <div id="alert-trends-chart" class="chart-container">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading chart data...</p>
                </div>
            </div>
        </div>
    `;
    
    // Severity distribution
    const severityCard = document.createElement('div');
    severityCard.className = 'card analytics-card';
    severityCard.innerHTML = `
        <div class="card-header">
            <h3>Severity Distribution</h3>
            <span class="card-subtitle">Alert severity breakdown</span>
        </div>
        <div class="card-body">
            <div id="severity-distribution" class="chart-container">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading distribution...</p>
                </div>
            </div>
        </div>
    `;
    
    chartsSection.appendChild(trendsCard);
    chartsSection.appendChild(severityCard);
    
    // Tables section
    const tablesSection = document.createElement('div');
    tablesSection.className = 'analytics-tables';
    
    // Top attacks
    const attacksCard = document.createElement('div');
    attacksCard.className = 'card analytics-table-card';
    attacksCard.innerHTML = `
        <div class="card-header">
            <h3>Top Attack Types</h3>
            <span class="card-subtitle">Most frequent attacks</span>
        </div>
        <div class="card-body">
            <div id="top-attacks-table" class="analytics-table">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading data...</p>
                </div>
            </div>
        </div>
    `;
    
    // Top source IPs
    const sourceIPsCard = document.createElement('div');
    sourceIPsCard.className = 'card analytics-table-card';
    sourceIPsCard.innerHTML = `
        <div class="card-header">
            <h3>Top Source IPs</h3>
            <span class="card-subtitle">Most active attackers</span>
        </div>
        <div class="card-body">
            <div id="top-source-ips-table" class="analytics-table">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading data...</p>
                </div>
            </div>
        </div>
    `;
    
    // Top destination IPs
    const destIPsCard = document.createElement('div');
    destIPsCard.className = 'card analytics-table-card';
    destIPsCard.innerHTML = `
        <div class="card-header">
            <h3>Top Destination IPs</h3>
            <span class="card-subtitle">Most targeted hosts</span>
        </div>
        <div class="card-body">
            <div id="top-dest-ips-table" class="analytics-table">
                <div class="loading-container">
                    <div class="loading-spinner"></div>
                    <p>Loading data...</p>
                </div>
            </div>
        </div>
    `;
    
    tablesSection.appendChild(attacksCard);
    tablesSection.appendChild(sourceIPsCard);
    tablesSection.appendChild(destIPsCard);
    
    // Assemble page
    container.appendChild(header);
    container.appendChild(summarySection);
    container.appendChild(chartsSection);
    container.appendChild(tablesSection);
    
    main.appendChild(container);
    
    // Load initial data
    setTimeout(() => loadAnalyticsData('24h'), 0);
    
    // Setup event listeners
    setTimeout(() => {
        const timeRangeSelect = document.getElementById('time-range-select') as HTMLSelectElement;
        const refreshBtn = document.getElementById('refresh-analytics-btn');
        const exportBtn = document.getElementById('export-analytics-btn');
        
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', () => {
                loadAnalyticsData(timeRangeSelect.value);
            });
        }
        
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                const currentRange = timeRangeSelect?.value || '24h';
                loadAnalyticsData(currentRange);
            });
        }
        
        if (exportBtn) {
            exportBtn.addEventListener('click', async () => {
                try {
                    const currentRange = timeRangeSelect?.value || '24h';
                    const data = await fetchAnalyticsData(currentRange);
                    exportAnalyticsToCSV(data, currentRange);
                    toast.show({ message: 'Analytics data exported successfully', type: 'success' });
                } catch (error) {
                    toast.show({ message: 'Failed to export analytics data', type: 'error' });
                }
            });
        }
    }, 0);
    
    return main;
};

/**
 * Load and display analytics data
 */
async function loadAnalyticsData(timeRange: string): Promise<void> {
    try {
        // Show loading state
        const summaryCards = ['total-alerts-stat', 'critical-alerts-stat', 'attack-types-stat', 'unique-ips-stat'];
        summaryCards.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
        
        // Fetch data
        const data = await fetchAnalyticsData(timeRange);
        
        // Update summary cards
        const totalAlertsEl = document.getElementById('total-alerts-stat');
        const criticalAlertsEl = document.getElementById('critical-alerts-stat');
        const attackTypesEl = document.getElementById('attack-types-stat');
        const uniqueIPsEl = document.getElementById('unique-ips-stat');
        
        if (totalAlertsEl) totalAlertsEl.textContent = data.summary.total_alerts.toLocaleString();
        if (criticalAlertsEl) criticalAlertsEl.textContent = data.summary.critical_alerts.toLocaleString();
        if (attackTypesEl) attackTypesEl.textContent = data.summary.attack_types.toString();
        if (uniqueIPsEl) uniqueIPsEl.textContent = data.summary.unique_ips.toLocaleString();
        
        // Update tables
        const topAttacksTable = document.getElementById('top-attacks-table');
        if (topAttacksTable) {
            topAttacksTable.innerHTML = renderTopAttacksTable(data.topAttacks);
        }
        
        const topSourceIPsTable = document.getElementById('top-source-ips-table');
        if (topSourceIPsTable) {
            topSourceIPsTable.innerHTML = renderTopSourceIPsTable(data.topSourceIPs);
        }
        
        const topDestIPsTable = document.getElementById('top-dest-ips-table');
        if (topDestIPsTable) {
            topDestIPsTable.innerHTML = renderTopDestIPsTable(data.topDestIPs);
        }
        
        // Update severity distribution
        const severityDistribution = document.getElementById('severity-distribution');
        if (severityDistribution) {
            severityDistribution.innerHTML = renderSeverityDistribution(data.severityDistribution);
        }
        
        // Update alert trends chart
        updateAlertTrendsChart(data.trends);
        
        toast.show({ message: 'Analytics data loaded successfully', type: 'success', duration: 2000 });
        
    } catch (error) {
        console.error('Failed to load analytics data:', error);
        toast.show({ message: 'Failed to load analytics data', type: 'error' });
    }
}

/**
 * Render top attacks table
 */
export function renderTopAttacksTable(attacks: { name: string; count: number; percentage: number }[]): string {
    if (attacks.length === 0) {
        return '<div class="empty-state-small">No attack data available</div>';
    }
    
    return `
        <table class="simple-table">
            <thead>
                <tr>
                    <th>Attack Type</th>
                    <th>Count</th>
                    <th>Percentage</th>
                    <th>Distribution</th>
                </tr>
            </thead>
            <tbody>
                ${attacks.map(attack => `
                    <tr>
                        <td><strong>${attack.name}</strong></td>
                        <td>${attack.count.toLocaleString()}</td>
                        <td>${attack.percentage.toFixed(1)}%</td>
                        <td>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${attack.percentage}%; background: #007bff;"></div>
                            </div>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

/**
 * Render top source IPs table
 */
export function renderTopSourceIPsTable(ips: { ip: string; count: number; severity: string }[]): string {
    if (ips.length === 0) {
        return '<div class="empty-state-small">No source IP data available</div>';
    }
    
    const getSeverityClass = (severity: string) => {
        const s = severity.toUpperCase();
        if (s === 'CRITICAL') return 'severity-critical';
        if (s === 'HIGH') return 'severity-high';
        if (s === 'MEDIUM') return 'severity-medium';
        if (s === 'LOW') return 'severity-low';
        return 'severity-info';
    };
    
    return `
        <table class="simple-table">
            <thead>
                <tr>
                    <th>Source IP</th>
                    <th>Alert Count</th>
                    <th>Max Severity</th>
                </tr>
            </thead>
            <tbody>
                ${ips.map(ip => `
                    <tr>
                        <td class="monospace">${ip.ip}</td>
                        <td>${ip.count.toLocaleString()}</td>
                        <td>
                            <span class="severity-badge ${getSeverityClass(ip.severity)}">
                                ${ip.severity}
                            </span>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

/**
 * Render top destination IPs table
 */
export function renderTopDestIPsTable(ips: { ip: string; count: number; protocol: string }[]): string {
    if (ips.length === 0) {
        return '<div class="empty-state-small">No destination IP data available</div>';
    }
    
    return `
        <table class="simple-table">
            <thead>
                <tr>
                    <th>Destination IP</th>
                    <th>Alert Count</th>
                    <th>Protocol</th>
                </tr>
            </thead>
            <tbody>
                ${ips.map(ip => `
                    <tr>
                        <td class="monospace">${ip.ip}</td>
                        <td>${ip.count.toLocaleString()}</td>
                        <td><span class="protocol-badge">${ip.protocol}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

/**
 * Render severity distribution
 */
export function renderSeverityDistribution(distribution: { severity: string; count: number; percentage: number }[]): string {
    if (distribution.length === 0) {
        return '<div class="empty-state-small">No severity data available</div>';
    }
    
    const getSeverityColor = (severity: string) => {
        const s = severity.toUpperCase();
        if (s === 'CRITICAL') return '#dc3545';
        if (s === 'HIGH') return '#fd7e14';
        if (s === 'MEDIUM') return '#ffc107';
        if (s === 'LOW') return '#28a745';
        if (s === 'INFO') return '#17a2b8';
        return '#6c757d';
    };
    
    return `
        <div class="severity-distribution-chart">
            ${distribution.map(item => `
                <div class="severity-item">
                    <div class="severity-item-header">
                        <span class="severity-label">${item.severity}</span>
                        <span class="severity-count">${item.count} (${item.percentage.toFixed(1)}%)</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" 
                             style="width: ${item.percentage}%; background: ${getSeverityColor(item.severity)};"></div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Keep a reference so we can destroy and re-create on updates
let alertTrendsChartInstance: Chart | null = null;

function updateAlertTrendsChart(trends: AlertTrend[]): void {
    const container = document.getElementById('alert-trends-chart');
    if (!container) return;

    if (!trends || trends.length === 0) {
        container.innerHTML = '<div class="empty-state-small">No trend data available</div>';
        if (alertTrendsChartInstance) {
            alertTrendsChartInstance.destroy();
            alertTrendsChartInstance = null;
        }
        return;
    }

    // Prepare labels and data
    const labels = trends.map(t => {
        const d = new Date(t.time);
        return isNaN(d.getTime()) ? t.time : d.toLocaleString();
    });
    const counts = trends.map(t => t.count);

    // Render/replace canvas
    container.innerHTML = '<canvas id="alert-trends-canvas" style="width: 100%; height: 300px;"></canvas>';
    const canvas = document.getElementById('alert-trends-canvas') as HTMLCanvasElement | null;
    if (!canvas) return;

    // Destroy existing chart if any
    if (alertTrendsChartInstance) {
        alertTrendsChartInstance.destroy();
        alertTrendsChartInstance = null;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    alertTrendsChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Alerts',
                    data: counts,
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.15)',
                    tension: 0.3,
                    fill: true,
                    pointRadius: 2,
                    pointHoverRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true },
                tooltip: { mode: 'index', intersect: false }
            },
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: {
                    ticks: { maxRotation: 0, autoSkip: true },
                    grid: { display: false }
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Alerts' }
                }
            }
        }
    });
}
