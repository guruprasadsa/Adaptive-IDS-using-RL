import { Alert, AlertsState } from "../types";
import { renderPagination } from "../components/Pagination";

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

const renderAlertsToolbar = (state: AlertsState): string => `
    <div class="alerts-toolbar">
        <div class="filter-group">
            <div class="search-wrapper">
                <span class="material-symbols-outlined">search</span>
                <input type="search" id="alert-search-input" class="search-input" placeholder="Search alerts..." value="${state.filters.search}" aria-label="Search alerts">
            </div>
            <select id="priority-filter" data-filter="priority" aria-label="Filter by priority" class="filter-select">
                <option value="all" ${state.filters.priority === 'all' ? 'selected' : ''}>All Priorities</option>
                <option value="critical" ${state.filters.priority === 'critical' ? 'selected' : ''}>Critical</option>
                <option value="high" ${state.filters.priority === 'high' ? 'selected' : ''}>High</option>
                <option value="medium" ${state.filters.priority === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="low" ${state.filters.priority === 'low' ? 'selected' : ''}>Low</option>
            </select>
            <select id="status-filter" data-filter="status" aria-label="Filter by status" class="filter-select">
                <option value="all" ${state.filters.status === 'all' ? 'selected' : ''}>All Statuses</option>
                <option value="new" ${state.filters.status === 'new' ? 'selected' : ''}>New</option>
                <option value="investigating" ${state.filters.status === 'investigating' ? 'selected' : ''}>Investigating</option>
                <option value="resolved" ${state.filters.status === 'resolved' ? 'selected' : ''}>Resolved</option>
                <option value="false_positive" ${state.filters.status === 'false_positive' ? 'selected' : ''}>False Positive</option>
            </select>
        </div>
    </div>
`;

const renderAlertsTable = (alerts: Alert[], state: AlertsState): HTMLElement => {
    const wrapper = document.createElement('div');
    wrapper.className = 'alerts-table-wrapper';
    
    const priorityClasses: Record<Alert['priority'], string> = {
        critical: 'priority-critical', high: 'priority-high', medium: 'priority-medium', low: 'priority-low',
    };

    const statusClasses: Record<Alert['status'], string> = {
        new: 'status-new', investigating: 'status-investigating', resolved: 'status-resolved', false_positive: 'status-resolved',
    };
    
    const headers: { key: keyof Alert; label: string }[] = [
        { key: 'priority', label: 'Priority' },
        { key: 'timestamp', label: 'Timestamp' },
        { key: 'description', label: 'Description' },
        { key: 'source', label: 'Source IP' },
        { key: 'status', label: 'Status' },
    ];

    const renderHeader = (header: { key: keyof Alert; label: string }) => {
        const isSorted = state.sortColumn === header.key;
        const sortIcon = isSorted ? (state.sortDirection === 'asc' ? 'arrow_upward' : 'arrow_downward') : 'swap_vert';
        const ariaSort = isSorted ? (state.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';
        return `<th class="sortable" data-sort-key="${header.key}" aria-sort="${ariaSort}">
                    ${header.label}
                    <span class="material-symbols-outlined sort-icon">${sortIcon}</span>
                </th>`;
    };

    wrapper.innerHTML = `
        <table class="alerts-table">
            <thead>
                <tr>
                    ${headers.map(renderHeader).join('')}
                </tr>
            </thead>
            <tbody>
                ${alerts.map(alert => `
                    <tr>
                        <td>
                            <div class="priority-cell">
                                <span class="priority-indicator ${priorityClasses[alert.priority]}"></span>
                                ${formatLabel(alert.priority)}
                            </div>
                        </td>
                        <td>${new Date(alert.timestamp).toLocaleString()}</td>
                        <td>${alert.description}</td>
                        <td>${alert.source}</td>
                        <td><span class="status-badge ${statusClasses[alert.status]}">${formatLabel(alert.status)}</span></td>
                    </tr>
                `).join('')}
                 ${alerts.length === 0 ? `<tr><td colspan="5" class="no-results">No alerts found.</td></tr>` : ''}
            </tbody>
        </table>
    `;
    return wrapper;
};

export const renderAlertsPage = (alerts: Alert[], totalAlerts: number, state: AlertsState): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="card full-height-card">
            <div id="alerts-page-container">
                ${renderAlertsToolbar(state)}
            </div>
        </div>
    `;
    const container = main.querySelector('#alerts-page-container');
    if (container) {
        container.append(renderAlertsTable(alerts, state));
        container.append(renderPagination(totalAlerts, state));
    }
    return main;
};

export const renderAlertsPageContent = (alerts: Alert[], totalAlerts: number, state: AlertsState): { table: HTMLElement, pagination: HTMLElement } => {
    const newTable = renderAlertsTable(alerts, state);
    const newPagination = renderPagination(totalAlerts, state);
    return { table: newTable, pagination: newPagination };
};
