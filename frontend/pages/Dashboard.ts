import { Alert } from '../types';
import { createTrafficChart } from '../components/Chart';

const renderStatCards = (dashboardStats?: any): string => {
    if (dashboardStats) {
        const dynamicCards = [
            { title: 'Total Alerts', value: dashboardStats.total_alerts.toString(), icon: 'shield_with_heart', colorClass: 'icon-orange' },
            { title: 'Critical Alerts', value: dashboardStats.critical_alerts.toString(), icon: 'report', colorClass: 'icon-red' },
            { title: 'Open Incidents', value: dashboardStats.open_incidents.toString(), icon: 'emergency_home', colorClass: 'icon-purple' },
            { title: 'Model Accuracy', value: `${(dashboardStats.model_metrics.accuracy * 100).toFixed(1)}%`, icon: 'model_training', colorClass: 'icon-green' },
        ];
        
        return dynamicCards.map(card => `
            <div class="card stat-card">
                <div class="stat-card-icon ${card.colorClass}">
                    <span class="material-symbols-outlined">${card.icon}</span>
                </div>
                <div class="stat-card-info">
                    <h3>${card.value}</h3>
                    <p>${card.title}</p>
                </div>
            </div>
        `).join('');
    }
    
    return statCards.map(card => `
        <div class="card stat-card">
            <div class="stat-card-icon ${card.colorClass}">
                <span class="material-symbols-outlined">${card.icon}</span>
            </div>
            <div class="stat-card-info">
                <h3>${card.value}</h3>
                <p>${card.title}</p>
            </div>
        </div>
    `).join('');
};

const renderRecentAlerts = (alerts?: Alert[]): string => {
    const priorityClasses: Record<Alert['priority'], string> = {
        critical: 'priority-critical',
        high: 'priority-high',
        medium: 'priority-medium',
        low: 'priority-low',
    };

    const alertsToShow = alerts || [];

    return `
        <div class="card col-span-2">
            <div class="card-header">
                <h3 class="card-title">Recent High-Priority Alerts</h3>
            </div>
            <ul class="alert-list">
                ${alertsToShow.slice(0, 4).map(alert => `
                    <li class="alert-item">
                        <div class="priority-indicator ${priorityClasses[alert.priority]}"></div>
                        <div class="alert-details">
                            <p>${alert.description}</p>
                            <span>Source: ${alert.source}</span>
                        </div>
                        <time class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</time>
                    </li>
                `).join('')}
            </ul>
        </div>
    `;
};

export const renderDashboard = (dashboardStats?: any, alerts?: Alert[]): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="grid-container grid-cols-4">
            ${renderStatCards(dashboardStats)}
            <div class="card col-span-2">
                <div class="card-header">
                    <h3 class="card-title">Real-time Network Traffic</h3>
                </div>
                <div class="chart-container">
                    <canvas id="trafficChart"></canvas>
                </div>
            </div>
            ${renderRecentAlerts(alerts)}
        </div>
    `;
    setTimeout(createTrafficChart, 0);
    return main;
};
