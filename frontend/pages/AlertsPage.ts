import { createButton } from "../components/Button";
import { createEmptyState } from "../components/EmptyState";
import { renderPagination } from "../components/Pagination";
import { Alert, AlertsState, User } from "../types";
import { canAcknowledgeAlerts, canMarkFalsePositive } from "../utils/rbac";

const formatLabel = (value: string): string => value.replace(/_/g, ' ').replace(/\b\w/g, (char: string) => char.toUpperCase());

const renderAlertsToolbar = (state: AlertsState): HTMLElement => {
    const toolbar = document.createElement('div');
    toolbar.className = 'alerts-toolbar';

    // Header with actions
    const header = document.createElement('div');
    header.className = 'toolbar-header';
    
    const title = document.createElement('h2');
    title.textContent = 'Alerts';
    
    const actions = document.createElement('div');
    actions.className = 'toolbar-actions';
    
    // Create buttons using createButton component
    const toggleFiltersBtn = createButton({
        variant: 'secondary',
        icon: 'filter_list',
        children: 'Filters',
        ariaLabel: 'Toggle advanced filters'
    });
    toggleFiltersBtn.id = 'toggle-filters-btn';
    
    const exportBtn = createButton({
        variant: 'secondary',
        icon: 'download',
        children: 'Export CSV',
        ariaLabel: 'Export to CSV'
    });
    exportBtn.id = 'export-csv-btn';
    
    const refreshBtn = createButton({
        variant: 'secondary',
        icon: 'refresh',
        children: '',
        ariaLabel: 'Refresh alerts'
    });
    refreshBtn.id = 'refresh-alerts-btn';
    
    actions.appendChild(toggleFiltersBtn);
    actions.appendChild(exportBtn);
    actions.appendChild(refreshBtn);
    
    header.appendChild(title);
    header.appendChild(actions);
    
    // Basic filters
    const basicFilters = document.createElement('div');
    basicFilters.className = 'filter-group filter-group-basic';
    basicFilters.innerHTML = `
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
    `;
    
    // Advanced filters
    const advancedFilters = document.createElement('div');
    advancedFilters.id = 'advanced-filters';
    advancedFilters.className = 'filter-group filter-group-advanced';
    advancedFilters.style.display = 'none';
    advancedFilters.innerHTML = `
        <div class="filter-row">
            <div class="filter-item">
                <label for="severity-filter">Severity</label>
                <select id="severity-filter" data-filter="severity" aria-label="Filter by severity" class="filter-select">
                    <option value="">All Severities</option>
                    <option value="INFO" ${state.filters.severity === 'INFO' ? 'selected' : ''}>INFO</option>
                    <option value="LOW" ${state.filters.severity === 'LOW' ? 'selected' : ''}>LOW</option>
                    <option value="MEDIUM" ${state.filters.severity === 'MEDIUM' ? 'selected' : ''}>MEDIUM</option>
                    <option value="HIGH" ${state.filters.severity === 'HIGH' ? 'selected' : ''}>HIGH</option>
                    <option value="CRITICAL" ${state.filters.severity === 'CRITICAL' ? 'selected' : ''}>CRITICAL</option>
                </select>
            </div>
            <div class="filter-item">
                <label for="className-filter">Attack Type</label>
                <input type="text" id="className-filter" data-filter="className" placeholder="e.g., DDoS, PortScan..." value="${state.filters.className || ''}" aria-label="Filter by attack class" class="filter-input">
            </div>
            <div class="filter-item">
                <label for="srcIp-filter">Source IP</label>
                <input type="text" id="srcIp-filter" data-filter="srcIp" placeholder="e.g., 192.168.1.100" value="${state.filters.srcIp || ''}" aria-label="Filter by source IP" class="filter-input">
            </div>
            <div class="filter-item">
                <label for="dstIp-filter">Destination IP</label>
                <input type="text" id="dstIp-filter" data-filter="dstIp" placeholder="e.g., 10.0.0.50" value="${state.filters.dstIp || ''}" aria-label="Filter by destination IP" class="filter-input">
            </div>
        </div>
        <div class="filter-row">
            <div class="filter-item">
                <label for="minConfidence-filter">Min Confidence (%)</label>
                <input type="number" id="minConfidence-filter" data-filter="minConfidence" min="0" max="100" step="1" placeholder="0" value="${state.filters.minConfidence ?? ''}" aria-label="Minimum confidence threshold" class="filter-input">
            </div>
            <div class="filter-item">
                <label for="maxConfidence-filter">Max Confidence (%)</label>
                <input type="number" id="maxConfidence-filter" data-filter="maxConfidence" min="0" max="100" step="1" placeholder="100" value="${state.filters.maxConfidence ?? ''}" aria-label="Maximum confidence threshold" class="filter-input">
            </div>
            <div class="filter-item">
                <label for="startTime-filter">Start Time</label>
                <input type="datetime-local" id="startTime-filter" data-filter="startTime" value="${state.filters.startTime || ''}" aria-label="Filter by start time" class="filter-input">
            </div>
            <div class="filter-item">
                <label for="endTime-filter">End Time</label>
                <input type="datetime-local" id="endTime-filter" data-filter="endTime" value="${state.filters.endTime || ''}" aria-label="Filter by end time" class="filter-input">
            </div>
        </div>
    `;
    
    // Filter action buttons
    const filterRow = document.createElement('div');
    filterRow.className = 'filter-row';
    
    const applyBtn = createButton({
        variant: 'primary',
        children: 'Apply Filters'
    });
    applyBtn.id = 'apply-filters-btn';
    
    const clearBtn = createButton({
        variant: 'secondary',
        children: 'Clear All'
    });
    clearBtn.id = 'clear-filters-btn';
    
    filterRow.appendChild(applyBtn);
    filterRow.appendChild(clearBtn);
    advancedFilters.appendChild(filterRow);
    
    // Assemble toolbar
    toolbar.appendChild(header);
    toolbar.appendChild(basicFilters);
    toolbar.appendChild(advancedFilters);
    
    return toolbar;
};

const renderAlertsTable = (alerts: Alert[], state: AlertsState, user: User | null = null): HTMLElement => {
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    wrapper.id = 'alerts-table-wrapper';
    
    // If no alerts, show empty state
    if (alerts.length === 0) {
        const emptyState = createEmptyState({
            icon: 'security',
            title: 'No Alerts Found',
            description: 'There are currently no alerts matching your criteria. Try adjusting your filters or check back later.'
        });
        wrapper.appendChild(emptyState);
        return wrapper;
    }
    
    // Check user permissions
    const canAck = canAcknowledgeAlerts(user);
    const canMarkFP = canMarkFalsePositive(user);
    
    const priorityClasses: Record<Alert['priority'], string> = {
        critical: 'priority-critical', high: 'priority-high', medium: 'priority-medium', low: 'priority-low',
    };

    const statusClasses: Record<Alert['status'], string> = {
        new: 'status-new', investigating: 'status-investigating', resolved: 'status-resolved', false_positive: 'status-resolved',
    };
    
    // Severity color mapping
    const getSeverityBadgeClass = (severity?: string): string => {
        switch (severity?.toUpperCase()) {
            case 'CRITICAL': return 'severity-critical';
            case 'HIGH': return 'severity-high';
            case 'MEDIUM': return 'severity-medium';
            case 'LOW': return 'severity-low';
            case 'INFO': return 'severity-info';
            default: return 'severity-unknown';
        }
    };
    
    // Attack class color mapping
    const getClassBadgeClass = (className?: string): string => {
        if (!className) return 'class-unknown';
        const normalized = className.toLowerCase();
        if (normalized.includes('ddos')) return 'class-ddos';
        if (normalized.includes('portscan') || normalized.includes('port scan')) return 'class-portscan';
        if (normalized.includes('brute')) return 'class-bruteforce';
        if (normalized.includes('botnet')) return 'class-botnet';
        if (normalized.includes('web')) return 'class-webattack';
        return 'class-other';
    };
    
    const headers: { key: keyof Alert | 'actions'; label: string }[] = [
        { key: 'priority', label: 'Priority' },
        { key: 'severity', label: 'Severity' },
        { key: 'timestamp', label: 'Timestamp' },
        { key: 'className', label: 'Attack Type' },
        { key: 'srcIp', label: 'Source IP' },
        { key: 'dstIp', label: 'Dest IP' },
        { key: 'confidence', label: 'Confidence' },
        { key: 'status', label: 'Status' },
        { key: 'actions', label: 'Actions' },
    ];

    const renderHeader = (header: { key: keyof Alert | 'actions'; label: string }) => {
        if (header.key === 'actions') {
            return `<th class="actions-column">${header.label}</th>`;
        }
        const isSorted = state.sortColumn === header.key;
        const sortIcon = isSorted ? (state.sortDirection === 'asc' ? 'arrow_upward' : 'arrow_downward') : 'swap_vert';
        const ariaSort = isSorted ? (state.sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';
        return `<th class="sortable" data-sort-key="${header.key}" aria-sort="${ariaSort}">
                    ${header.label}
                    <span class="material-symbols-outlined sort-icon">${sortIcon}</span>
                </th>`;
    };

    const table = document.createElement('table');
    table.className = 'alerts-table';
    
    table.innerHTML = `
        <thead>
            <tr>
                ${headers.map(renderHeader).join('')}
            </tr>
        </thead>
        <tbody>
            ${alerts.map(alert => `
                <tr data-alert-id="${alert.id}">
                    <td>
                        <div class="priority-cell">
                            <span class="priority-indicator ${priorityClasses[alert.priority]}"></span>
                            ${formatLabel(alert.priority)}
                        </div>
                    </td>
                    <td>
                        <span class="severity-badge ${getSeverityBadgeClass(alert.severity)}">
                            ${alert.severity || 'N/A'}
                        </span>
                    </td>
                    <td>${new Date(alert.timestamp).toLocaleString()}</td>
                    <td>
                        <span class="class-badge ${getClassBadgeClass(alert.className)}">
                            ${alert.className || 'Unknown'}
                        </span>
                    </td>
                    <td class="monospace">${alert.srcIp || alert.source || 'N/A'}</td>
                    <td class="monospace">${alert.dstIp || 'N/A'}</td>
                    <td>
                        <div class="confidence-cell">
                            ${alert.confidence !== undefined ? `${(alert.confidence * 100).toFixed(1)}%` : 'N/A'}
                            ${alert.confidence !== undefined ? `<div class="confidence-bar"><div class="confidence-fill" style="width: ${alert.confidence * 100}%"></div></div>` : ''}
                        </div>
                    </td>
                    <td>
                        <span class="status-badge ${statusClasses[alert.status]}">
                            ${formatLabel(alert.status)}
                        </span>
                    </td>
                    <td class="actions-cell">
                        ${alert.status !== 'resolved' && alert.status !== 'false_positive' && (canAck || canMarkFP) ? `
                            ${canAck ? `
                                <button class="btn-icon ack-alert-btn" data-alert-id="${alert.id}" title="Acknowledge Alert" aria-label="Acknowledge alert ${alert.id}">
                                    <span class="material-symbols-outlined">check_circle</span>
                                </button>
                            ` : ''}
                            ${canMarkFP ? `
                                <button class="btn-icon fp-alert-btn" data-alert-id="${alert.id}" title="Mark as False Positive" aria-label="Mark alert ${alert.id} as false positive">
                                    <span class="material-symbols-outlined">cancel</span>
                                </button>
                            ` : ''}
                        ` : ''}
                        <button class="btn-icon view-alert-btn" data-alert-id="${alert.id}" title="View Details" aria-label="View details for alert ${alert.id}">
                            <span class="material-symbols-outlined">visibility</span>
                        </button>
                    </td>
                </tr>
            `).join('')}
        </tbody>
    `;
    
    wrapper.appendChild(table);
    return wrapper;
};

export const renderAlertsPage = (alerts: Alert[], totalAlerts: number, state: AlertsState, user: User | null = null): HTMLElement => {
    const main = document.createElement('main');
    main.className = 'main-content';
    
    const card = document.createElement('div');
    card.className = 'card full-height-card';
    
    const container = document.createElement('div');
    container.id = 'alerts-page-container';
    
    // Add toolbar
    container.appendChild(renderAlertsToolbar(state));
    
    // Add table with user permissions
    container.appendChild(renderAlertsTable(alerts, state, user));
    
    // Add pagination
    container.appendChild(renderPagination(totalAlerts, state));
    
    card.appendChild(container);
    main.appendChild(card);
    
    return main;
};

export const renderAlertsPageContent = (alerts: Alert[], totalAlerts: number, state: AlertsState, user: User | null = null): { table: HTMLElement, pagination: HTMLElement } => {
    const newTable = renderAlertsTable(alerts, state, user);
    const newPagination = renderPagination(totalAlerts, state);
    return { table: newTable, pagination: newPagination };
};

export const setupAlertsEventListeners = (onRefresh: () => void) => {
    // Sort functionality
    document.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        const sortableHeader = target.closest('.sortable[data-sort-key]') as HTMLElement;
        
        if (sortableHeader) {
            const sortKey = sortableHeader.dataset.sortKey as keyof Alert;
            if (sortKey) {
                // Toggle sort direction or set new column
                const currentSort = window.alertsState?.sortColumn;
                const currentDirection = window.alertsState?.sortDirection;
                
                if (currentSort === sortKey) {
                    window.alertsState.sortDirection = currentDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    window.alertsState.sortColumn = sortKey;
                    window.alertsState.sortDirection = 'asc';
                }
                
                onRefresh();
            }
        }
    });

    // Filter functionality
    document.addEventListener('input', (e) => {
        const target = e.target as HTMLInputElement | HTMLSelectElement;
        const filterKey = target.dataset.filter;
        
        if (filterKey && window.alertsState) {
            const value = target.type === 'number' ? 
                (target.value ? parseFloat(target.value) : undefined) :
                target.value;
            
            if (value !== undefined && value !== '') {
                window.alertsState.filters[filterKey] = value;
            } else {
                delete window.alertsState.filters[filterKey];
            }
            
            // Reset to first page when filtering
            window.alertsState.currentPage = 1;
            
            // Debounce filter updates
            clearTimeout(window.alertsFilterTimeout);
            window.alertsFilterTimeout = setTimeout(() => {
                onRefresh();
            }, 300);
        }
    });

    // Apply filters button
    document.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        if (target.id === 'apply-filters-btn' || target.closest('#apply-filters-btn')) {
            onRefresh();
        }
    });

    // Clear filters button
    document.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        if (target.id === 'clear-filters-btn' || target.closest('#clear-filters-btn')) {
            if (window.alertsState) {
                window.alertsState.filters = {};
                window.alertsState.currentPage = 1;
                
                // Clear all filter inputs
                document.querySelectorAll('[data-filter]').forEach((input: any) => {
                    if (input.type === 'number') {
                        input.value = '';
                    } else {
                        input.value = '';
                    }
                });
                
                onRefresh();
            }
        }
    });

    // Alert action buttons
    document.addEventListener('click', (e) => {
        const target = e.target as HTMLElement;
        const button = target.closest('.ack-alert-btn, .fp-alert-btn, .view-alert-btn') as HTMLElement;
        
        if (button) {
            const alertId = button.dataset.alertId;
            const action = button.classList.contains('ack-alert-btn') ? 'ack' :
                          button.classList.contains('fp-alert-btn') ? 'fp' : 'view';
            
            if (alertId) {
                handleAlertAction(alertId, action, onRefresh);
            }
        }
    });
};

const handleAlertAction = async (alertId: string, action: string, onRefresh: () => void) => {
    try {
        if (action === 'ack') {
            await fetch(`/api/alerts/${alertId}/acknowledge`, { method: 'POST' });
        } else if (action === 'fp') {
            await fetch(`/api/alerts/${alertId}/false-positive`, { method: 'POST' });
        } else if (action === 'view') {
            // Open alert details modal
            const alert = window.alerts?.find(a => a.id === alertId);
            if (alert) {
                // You can implement a modal here
                console.log('View alert:', alert);
            }
        }
        
        onRefresh();
    } catch (error) {
        console.error(`Failed to ${action} alert ${alertId}:`, error);
    }
};
