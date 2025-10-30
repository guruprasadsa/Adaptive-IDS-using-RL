import { createTrafficChart } from '../components/Chart';
import { createEmptyState } from '../components/EmptyState';
import { createMetricCard } from '../components/MetricCard';
import { defaultStatCards } from '../data';
import { Alert, StatCardData } from '../types';

const renderStatCards = (cards: StatCardData[]): HTMLElement[] => {
    return cards.map(card => createMetricCard({
        label: card.title,
        value: card.value,
        icon: card.icon,
        colorClass: card.colorClass.replace('icon-', 'metric-')
    }));
};

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

// Format timestamp to relative time (e.g., "2m ago", "Just now")
const formatRelativeTime = (timestamp: string): string => {
    const now = new Date().getTime();
    const time = new Date(timestamp).getTime();
    const diffMs = now - time;
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    
    if (diffSeconds < 5) return 'Just now';
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return new Date(timestamp).toLocaleDateString();
};

const renderRecentAlerts = (alerts: Alert[]): HTMLElement => {
    const priorityClasses: Record<Alert['priority'], string> = {
        critical: 'priority-critical',
        high: 'priority-high',
        medium: 'priority-medium',
        low: 'priority-low',
    };

    const card = document.createElement('div');
    card.className = 'card col-span-2';

    const header = document.createElement('div');
    header.className = 'card-header';
    header.innerHTML = '<h3 class="card-title">Recent High-Priority Alerts</h3>';
    card.appendChild(header);

    if (alerts.length === 0) {
        const emptyState = createEmptyState({
            icon: 'check_circle',
            title: 'No Recent Alerts',
            description: 'All clear! No high-priority alerts at this time.'
        });
        card.appendChild(emptyState);
        return card;
    }

    const alertList = document.createElement('ul');
    alertList.className = 'alert-list';

    alerts.slice(0, 4).forEach(alert => {
        const listItem = document.createElement('li');
        listItem.className = 'alert-item';
        
        listItem.innerHTML = `
            <div class="priority-indicator ${priorityClasses[alert.priority]}"></div>
            <div class="alert-details">
                <p>${alert.description}</p>
                <span>${formatLabel(alert.className || 'Unknown')} • ${alert.srcIp || alert.source || 'N/A'}</span>
            </div>
            <time class="alert-time">${formatRelativeTime(alert.timestamp)}</time>
        `;
        
        alertList.appendChild(listItem);
    });

    card.appendChild(alertList);
    return card;
};

export const renderDashboard = (statCards: StatCardData[] = defaultStatCards, alerts: Alert[] = []): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';

    // Create grid container
    const gridContainer = document.createElement('div');
    gridContainer.className = 'grid-container grid-cols-4';

    // Add stat cards
    const statCardElements = renderStatCards(statCards);
    statCardElements.forEach(card => gridContainer.appendChild(card));

    // Add traffic chart card
    const chartCard = document.createElement('div');
    chartCard.className = 'card col-span-2';
    chartCard.innerHTML = `
        <div class="card-header">
            <h3 class="card-title">Real-time Network Traffic</h3>
        </div>
        <canvas id="trafficChart"></canvas>
    `;
    gridContainer.appendChild(chartCard);

    // Add recent alerts card
    const alertsCard = renderRecentAlerts(alerts);
    gridContainer.appendChild(alertsCard);

    main.appendChild(gridContainer);
    
    // Initialize chart on next tick
    setTimeout(createTrafficChart, 0);
    
    return main;
};
