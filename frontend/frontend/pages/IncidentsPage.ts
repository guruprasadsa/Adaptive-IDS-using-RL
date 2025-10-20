import { Incident, IncidentsState, Alert } from "../types";
import { renderPagination } from "../components/Pagination";

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

const renderIncidentsToolbar = (state: IncidentsState): string => `
    <div class="alerts-toolbar">
        <div class="filter-group">
            <div class="search-wrapper">
                <span class="material-symbols-outlined">search</span>
                <input type="search" id="incident-search-input" class="search-input" placeholder="Search incidents..." value="${state.filters.search}" aria-label="Search incidents">
            </div>
            <select id="severity-filter" data-filter="severity" aria-label="Filter by severity" class="filter-select">
                <option value="all" ${state.filters.severity === 'all' ? 'selected' : ''}>All Severities</option>
                <option value="critical" ${state.filters.severity === 'critical' ? 'selected' : ''}>Critical</option>
                <option value="high" ${state.filters.severity === 'high' ? 'selected' : ''}>High</option>
                <option value="medium" ${state.filters.severity === 'medium' ? 'selected' : ''}>Medium</option>
                <option value="low" ${state.filters.severity === 'low' ? 'selected' : ''}>Low</option>
            </select>
            <select id="incident-status-filter" data-filter="status" aria-label="Filter by status" class="filter-select">
                <option value="all" ${state.filters.status === 'all' ? 'selected' : ''}>All Statuses</option>
                <option value="open" ${state.filters.status === 'open' ? 'selected' : ''}>Open</option>
                <option value="investigating" ${state.filters.status === 'investigating' ? 'selected' : ''}>Investigating</option>
                <option value="contained" ${state.filters.status === 'contained' ? 'selected' : ''}>Contained</option>
                <option value="resolved" ${state.filters.status === 'resolved' ? 'selected' : ''}>Resolved</option>
            </select>
        </div>
    </div>
`;

const renderIncidentDetailsRow = (incident: Incident, alerts: Alert[]): string => {
    const relatedAlerts = alerts.filter(a => incident.relatedAlertIds.includes(a.id));
    return `
        <tr class="incident-details-row">
            <td colspan="6">
                <div class="incident-details-content">
                    <h4>Summary</h4>
                    <p>${incident.summary}</p>
                    <p class="incident-description">${incident.description}</p>
                    <h4 class="related-alerts-header">Related Alerts (${relatedAlerts.length})</h4>
                    <ul class="related-alerts-list">
                        ${relatedAlerts.map(alert => `<li><strong>${formatLabel(alert.priority)}:</strong> ${alert.description} (Source: ${alert.source})</li>`).join('')}
                    </ul>
                </div>
            </td>
        </tr>
    `;
};

const renderIncidentsTable = (incidents: Incident[], state: IncidentsState, alerts: Alert[]): HTMLElement => {
    const wrapper = document.createElement('div');
    wrapper.className = 'alerts-table-wrapper';

    const severityClasses: Record<Incident['severity'], string> = {
        critical: 'priority-critical', high: 'priority-high', medium: 'priority-medium', low: 'priority-low',
    };
    const statusClasses: Record<Incident['status'], string> = {
        open: 'status-new',
        investigating: 'status-investigating',
        contained: 'status-resolved',
        resolved: 'status-resolved'
    };
    
    const headers: { key: keyof Omit<Incident, 'relatedAlertIds' | 'summary' | 'createdAt' | 'id'>; label: string }[] = [
        { key: 'severity', label: 'Severity' },
        { key: 'title', label: 'Title' },
        { key: 'status', label: 'Status' },
        { key: 'assignedTo', label: 'Assigned To' },
        { key: 'lastUpdatedAt', label: 'Last Updated' },
    ];

    const renderHeader = (header: { key: keyof Incident; label: string }) => {
        const isSorted = state.sortColumn === header.key;
        const sortIcon = isSorted ? (state.sortDirection === 'asc' ? 'arrow_upward' : 'arrow_downward') : 'swap_vert';
        const ariaSort = isSorted ? (state.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';
        return `<th class="sortable" data-sort-key="${header.key}" aria-sort="${ariaSort}">
                    ${header.label}
                    <span class="material-symbols-outlined sort-icon">${sortIcon}</span>
                </th>`;
    };

    wrapper.innerHTML = `
        <table class="alerts-table incidents-table">
            <thead>
                <tr>
                    ${headers.map(renderHeader).join('')}
                </tr>
            </thead>
            <tbody>
                ${incidents.map(incident => `
                    <tr class="incident-row" data-incident-id="${incident.id}" aria-expanded="${state.expandedIncidentId === incident.id}">
                        <td>
                            <div class="priority-cell">
                                <span class="priority-indicator ${severityClasses[incident.severity]}"></span>
                                ${formatLabel(incident.severity)}
                            </div>
                        </td>
                        <td>${incident.title}</td>
                        <td><span class="status-badge ${statusClasses[incident.status]}">${formatLabel(incident.status)}</span></td>
                        <td>${incident.assignedTo}</td>
                        <td>${new Date(incident.lastUpdatedAt).toLocaleString()}</td>
                    </tr>
                    ${state.expandedIncidentId === incident.id ? renderIncidentDetailsRow(incident, alerts) : ''}
                `).join('')}
                ${incidents.length === 0 ? `<tr><td colspan="5" class="no-results">No incidents found.</td></tr>` : ''}
            </tbody>
        </table>
    `;
    return wrapper;
};


export const renderIncidentsPage = (incidents: Incident[], totalIncidents: number, state: IncidentsState, alerts: Alert[]): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    main.innerHTML = `
        <div class="card full-height-card">
            <div id="incidents-page-container">
                ${renderIncidentsToolbar(state)}
            </div>
        </div>
    `;
    const container = main.querySelector('#incidents-page-container');
    if (container) {
        container.append(renderIncidentsTable(incidents, state, alerts));
        container.append(renderPagination(totalIncidents, state, true));
    }
    return main;
};

export const renderIncidentsPageContent = (incidents: Incident[], totalIncidents: number, state: IncidentsState, alerts: Alert[]): { table: HTMLElement, pagination: HTMLElement } => {
    const newTable = renderIncidentsTable(incidents, state, alerts);
    const newPagination = renderPagination(totalIncidents, state, true);
    return { table: newTable, pagination: newPagination };
};
