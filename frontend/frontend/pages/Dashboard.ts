import { Alert, StatCardData } from '../types';
import { defaultStatCards } from '../data';
import { createTrafficChart } from '../components/Chart';

const renderStatCards = (cards: StatCardData[]): string => {
    return cards.map(card => `
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

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

const renderRecentAlerts = (alerts: Alert[]): string => {
    const priorityClasses: Record<Alert['priority'], string> = {
        critical: 'priority-critical',
        high: 'priority-high',
        medium: 'priority-medium',
        low: 'priority-low',
    };

    return `
        <div class="card col-span-2">
            <div class="card-header">
                <h3 class="card-title">Recent High-Priority Alerts</h3>
            </div>
            <ul class="alert-list">
                ${alerts.slice(0, 4).map(alert => `
                    <li class="alert-item">
                        <div class="priority-indicator ${priorityClasses[alert.priority]}"></div>
                        <div class="alert-details">
                            <p>${alert.description}</p>
                            <span>${formatLabel(alert.type)} • ${alert.source}</span>
                        </div>
                        <time class="alert-time">${new Date(alert.timestamp).toLocaleTimeString()}</time>
                    </li>
                `).join('')}
            </ul>
        </div>
    `;
};

export const renderDashboard = (statCards: StatCardData[] = defaultStatCards, alerts: Alert[] = []): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="grid-container grid-cols-4">
            ${renderStatCards(statCards)}
            <div class="card col-span-2">
                <div class="card-header">
                    <h3 class="card-title">Real-time Network Traffic</h3>
                </div>
                <canvas id="trafficChart"></canvas>
            </div>
            ${renderRecentAlerts(alerts)}
        </div>
    `;
    setTimeout(createTrafficChart, 0);
    return main;
};
